#!/usr/bin/env python3
"""
migrate_to_supabase.py - Migra todos los datos de SQLite a Supabase PostgreSQL.

Lee cada tabla de la DB SQLite local y la inserta en Supabase
en batches de 1000 filas. Verifica que los conteos coincidan.

Requisitos:
    - SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en .env
    - Schema ya creado en Supabase (via migraciones MCP)
    - pip install psycopg2-binary

Uso:
    python scripts/migrate_to_supabase.py
    python scripts/migrate_to_supabase.py --dry-run
    python scripts/migrate_to_supabase.py --tables tokens,ohlcv
"""

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# Agregar el directorio raiz al path para imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.data.storage import Storage
from src.data.supabase_storage import SupabaseStorage
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Orden de migracion (respeta foreign keys)
MIGRATION_ORDER = [
    "tokens",
    "pool_snapshots",
    "ohlcv",
    "holder_snapshots",
    "contract_info",
    "labels",
    "features",
    "api_usage",
    "watchlist",
]

BATCH_SIZE = 1000


def migrate_table(
    sqlite_storage: Storage,
    supa_storage: SupabaseStorage,
    table: str,
    dry_run: bool = False,
) -> dict:
    """
    Migra una tabla de SQLite a Supabase.

    Args:
        sqlite_storage: Instancia de Storage (SQLite).
        supa_storage: Instancia de SupabaseStorage.
        table: Nombre de la tabla a migrar.
        dry_run: Si True, solo muestra conteos sin insertar.

    Returns:
        Dict con: table, source_count, migrated_count, target_count.
    """
    logger.info(f"--- Migrando tabla: {table} ---")

    # Leer datos de SQLite
    source_df = sqlite_storage.query(f"SELECT * FROM {table}")
    source_count = len(source_df)
    logger.info(f"  SQLite: {source_count} filas")

    if source_count == 0:
        logger.info(f"  Tabla {table} vacia, saltando")
        return {"table": table, "source_count": 0, "migrated_count": 0, "target_count": 0}

    if dry_run:
        return {"table": table, "source_count": source_count, "migrated_count": 0, "target_count": 0}

    # Tabla features usa JSONB en Supabase, necesita tratamiento especial
    if table == "features":
        _migrate_features(sqlite_storage, supa_storage, source_df)
    else:
        _migrate_generic(supa_storage, table, source_df)

    # Verificar conteo en destino
    target_df = supa_storage.query(f"SELECT COUNT(*) as n FROM {table}")
    target_count = int(target_df["n"].iloc[0])
    logger.info(f"  Supabase: {target_count} filas (esperadas: {source_count})")

    return {
        "table": table,
        "source_count": source_count,
        "migrated_count": source_count,
        "target_count": target_count,
    }


def _migrate_generic(supa_storage: SupabaseStorage, table: str, df: pd.DataFrame):
    """Migra una tabla generica por batches con INSERT ... ON CONFLICT DO NOTHING."""
    columns = [c for c in df.columns if c != "id"]  # Excluir id (autogenerado)
    placeholders = ", ".join(["%s"] * len(columns))
    col_names = ", ".join(columns)

    # Determinar columna de conflicto segun la tabla
    conflict_cols = {
        "tokens": "token_id",
        "contract_info": "token_id",
        "labels": "token_id",
        "watchlist": "token_id",
    }
    conflict = conflict_cols.get(table)
    conflict_clause = f"ON CONFLICT ({conflict}) DO NOTHING" if conflict else ""

    # Para ohlcv, usar su UNIQUE constraint
    if table == "ohlcv":
        conflict_clause = "ON CONFLICT (pool_address, timeframe, timestamp) DO NOTHING"

    sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) {conflict_clause}"

    total = len(df)
    for start in tqdm(range(0, total, BATCH_SIZE), desc=f"  {table}", unit="batch"):
        batch = df.iloc[start:start + BATCH_SIZE]
        params = [
            tuple(None if pd.isna(v) else v for v in row)
            for row in batch[columns].values
        ]
        try:
            supa_storage.execute_many(sql, params)
        except Exception as e:
            logger.warning(f"  Error en batch {start}-{start + len(batch)}: {e}")


def _migrate_features(
    sqlite_storage: Storage,
    supa_storage: SupabaseStorage,
    source_df: pd.DataFrame,
):
    """
    Migra la tabla features de SQLite (columnas planas) a Supabase (JSONB).

    SQLite tiene: token_id, col1, col2, ..., computed_at
    Supabase tiene: token_id, data (JSONB), computed_at
    """
    logger.info("  Features: convirtiendo columnas planas a JSONB...")

    # Columnas que no son features
    meta_cols = {"token_id", "computed_at", "index"}
    feature_cols = [c for c in source_df.columns if c not in meta_cols]

    sql = """
        INSERT INTO features (token_id, data, computed_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (token_id) DO UPDATE SET
            data = EXCLUDED.data,
            computed_at = EXCLUDED.computed_at
    """

    total = len(source_df)
    for start in tqdm(range(0, total, BATCH_SIZE), desc="  features", unit="batch"):
        batch = source_df.iloc[start:start + BATCH_SIZE]
        params = []
        for _, row in batch.iterrows():
            token_id = row.get("token_id") or row.get("index")
            computed_at = row.get("computed_at")

            data = {}
            for col in feature_cols:
                val = row[col]
                if pd.isna(val):
                    data[col] = None
                elif isinstance(val, (int, float)):
                    data[col] = float(val)
                else:
                    data[col] = str(val)

            params.append((token_id, json.dumps(data), computed_at))

        try:
            supa_storage.execute_many(sql, params)
        except Exception as e:
            logger.warning(f"  Error en batch features: {e}")


def run_migration(tables: list[str] = None, dry_run: bool = False) -> dict:
    """
    Ejecuta la migracion completa de SQLite a Supabase.

    Args:
        tables: Lista de tablas a migrar. Si None, migra todas.
        dry_run: Si True, solo muestra conteos.

    Returns:
        Dict con estadisticas por tabla.
    """
    sqlite_storage = Storage()
    supa_storage = SupabaseStorage()

    tables_to_migrate = tables or MIGRATION_ORDER

    logger.info("=" * 60)
    logger.info("MIGRACION SQLite -> Supabase")
    logger.info(f"Tablas: {tables_to_migrate}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("=" * 60)

    start_time = time.time()
    results = []

    for table in tables_to_migrate:
        if table not in MIGRATION_ORDER:
            logger.warning(f"Tabla '{table}' no reconocida, saltando")
            continue

        result = migrate_table(sqlite_storage, supa_storage, table, dry_run=dry_run)
        results.append(result)

    duration = time.time() - start_time

    # Resumen final
    logger.info("=" * 60)
    logger.info("MIGRACION COMPLETADA")
    logger.info(f"Duracion: {duration:.1f}s")
    logger.info("")

    all_ok = True
    for r in results:
        status = "OK" if r["source_count"] == r["target_count"] or dry_run else "MISMATCH"
        if status == "MISMATCH":
            all_ok = False
        logger.info(
            f"  {r['table']:20s} | SQLite: {r['source_count']:>6} | "
            f"Supabase: {r['target_count']:>6} | {status}"
        )

    if not dry_run and all_ok:
        logger.info("\nTodas las tablas migradas correctamente!")
    elif not dry_run:
        logger.warning("\nAlgunas tablas tienen diferencias de conteo (posibles duplicados filtrados)")

    logger.info("=" * 60)

    return {"results": results, "duration_seconds": round(duration, 2), "all_match": all_ok}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrar datos de SQLite local a Supabase PostgreSQL"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Solo mostrar conteos, no migrar"
    )
    parser.add_argument(
        "--tables", type=str, default=None,
        help="Tablas a migrar separadas por coma (default: todas)"
    )

    args = parser.parse_args()
    tables = args.tables.split(",") if args.tables else None

    result = run_migration(tables=tables, dry_run=args.dry_run)

    print(f"\nResultado: {json.dumps(result, indent=2, default=str)}")
