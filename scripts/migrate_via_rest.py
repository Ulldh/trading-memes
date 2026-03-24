#!/usr/bin/env python3
"""
migrate_via_rest.py - Migra SQLite a Supabase via REST API (PostgREST).

Usa supabase-py con el anon key para insertar datos via la REST API.
Requiere permisos temporales de INSERT en las tablas (se crean via MCP
y se revocan despues de la migracion).

Ventaja: No necesita conexion directa a PostgreSQL (IPv6/pooler issues).

Uso:
    python scripts/migrate_via_rest.py
    python scripts/migrate_via_rest.py --dry-run
    python scripts/migrate_via_rest.py --tables tokens,labels
"""

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# Agregar directorio raiz al path
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.data.storage import Storage
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

BATCH_SIZE = 500  # PostgREST acepta ~1000, usamos 500 para seguridad

# Columnas que son INTEGER en Supabase (requieren conversion float->int)
INTEGER_COLUMNS = {
    "pool_snapshots": {"buyers_24h", "sellers_24h", "makers_24h", "tx_count_24h"},
    "holder_snapshots": {"rank"},
    "labels": {"label_binary"},
    "api_usage": {"status_code", "response_time_ms"},
    "tokens": {"decimals"},
}

# Columnas que son BOOLEAN en Supabase (SQLite guarda como 0.0/1.0)
BOOLEAN_COLUMNS = {
    "contract_info": {"is_verified", "is_renounced", "has_mint_authority"},
}

# Configuracion de conflictos por tabla para upsert
TABLE_CONFLICT = {
    "tokens": "token_id",
    "contract_info": "token_id",
    "labels": "token_id",
    "watchlist": "token_id",
    "features": "token_id",
    "ohlcv": "pool_address,timeframe,timestamp",
}


def _get_supabase_client():
    """Crea cliente supabase-py con anon key (REST API)."""
    try:
        from config import SUPABASE_URL, SUPABASE_ANON_KEY
    except ImportError:
        import os
        SUPABASE_URL = os.getenv("SUPABASE_URL", "")
        SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise ValueError("SUPABASE_URL y SUPABASE_ANON_KEY necesarios en .env")

    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def _clean_row(row: dict, table: str) -> dict:
    """Limpia valores NaN y convierte tipos para JSON/PostgREST."""
    int_cols = INTEGER_COLUMNS.get(table, set())
    bool_cols = BOOLEAN_COLUMNS.get(table, set())
    cleaned = {}
    for k, v in row.items():
        if k == "id":
            continue  # Excluir id autogenerado
        if pd.isna(v):
            cleaned[k] = None
        elif k in bool_cols:
            cleaned[k] = bool(v)
        elif k in int_cols:
            cleaned[k] = int(v)
        elif isinstance(v, (int, float)):
            import numpy as np
            if isinstance(v, (np.integer,)):
                cleaned[k] = int(v)
            elif isinstance(v, (np.floating,)):
                cleaned[k] = float(v)
            else:
                cleaned[k] = float(v) if isinstance(v, float) else int(v)
        else:
            cleaned[k] = str(v)
    return cleaned


def _migrate_table(
    client,
    sqlite_storage: Storage,
    table: str,
    dry_run: bool = False,
) -> dict:
    """Migra una tabla de SQLite a Supabase via REST API."""
    logger.info(f"--- Migrando tabla: {table} ---")

    # Leer datos de SQLite
    source_df = sqlite_storage.query(f"SELECT * FROM {table}")
    source_count = len(source_df)
    logger.info(f"  SQLite: {source_count} filas")

    if source_count == 0 or dry_run:
        return {
            "table": table,
            "source_count": source_count,
            "migrated_count": 0,
            "errors": 0,
        }

    # Tabla features necesita tratamiento especial (columnas -> JSONB)
    if table == "features":
        return _migrate_features(client, source_df, source_count)

    # Determinar estrategia de insercion
    conflict = TABLE_CONFLICT.get(table)

    migrated = 0
    errors = 0

    for start in tqdm(range(0, source_count, BATCH_SIZE), desc=f"  {table}", unit="batch"):
        batch_df = source_df.iloc[start:start + BATCH_SIZE]
        rows = [_clean_row(row, table) for _, row in batch_df.iterrows()]

        try:
            if conflict:
                client.table(table).upsert(rows, on_conflict=conflict).execute()
            else:
                client.table(table).insert(rows).execute()
            migrated += len(rows)
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"  Error en batch {start}: {error_msg[:200]}")
            errors += 1

    logger.info(f"  Migradas: {migrated} filas, {errors} errores")
    return {
        "table": table,
        "source_count": source_count,
        "migrated_count": migrated,
        "errors": errors,
    }


def _migrate_features(client, source_df: pd.DataFrame, source_count: int) -> dict:
    """Migra features: columnas planas en SQLite -> JSONB en Supabase."""
    logger.info("  Features: convirtiendo columnas planas a JSONB...")

    meta_cols = {"token_id", "computed_at", "index", "id"}
    feature_cols = [c for c in source_df.columns if c not in meta_cols]

    migrated = 0
    errors = 0

    for start in tqdm(range(0, source_count, BATCH_SIZE), desc="  features", unit="batch"):
        batch = source_df.iloc[start:start + BATCH_SIZE]
        rows = []
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

            entry = {"token_id": str(token_id), "data": data}
            if computed_at and not pd.isna(computed_at):
                entry["computed_at"] = str(computed_at)
            rows.append(entry)

        try:
            client.table("features").upsert(
                rows, on_conflict="token_id"
            ).execute()
            migrated += len(rows)
        except Exception as e:
            logger.warning(f"  Error en batch features: {str(e)[:200]}")
            errors += 1

    logger.info(f"  Features migradas: {migrated}, errores: {errors}")
    return {
        "table": "features",
        "source_count": source_count,
        "migrated_count": migrated,
        "errors": errors,
    }


def _verify_counts(client, results: list) -> list:
    """Verifica conteos en Supabase vs SQLite."""
    verified = []
    for r in results:
        table = r["table"]
        try:
            resp = client.table(table).select("*", count="exact", head=True).execute()
            target_count = resp.count or 0
        except Exception:
            target_count = -1

        status = "OK" if r["source_count"] == target_count else "DIFF"
        r["target_count"] = target_count
        r["status"] = status
        verified.append(r)
    return verified


def run_migration(tables: list = None, dry_run: bool = False) -> dict:
    """Ejecuta la migracion completa de SQLite a Supabase via REST."""
    sqlite_storage = Storage()
    client = _get_supabase_client()

    tables_to_migrate = tables or MIGRATION_ORDER

    logger.info("=" * 60)
    logger.info("MIGRACION SQLite -> Supabase (via REST API)")
    logger.info(f"Tablas: {tables_to_migrate}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Batch size: {BATCH_SIZE}")
    logger.info("=" * 60)

    start_time = time.time()
    results = []

    for table in tables_to_migrate:
        if table not in MIGRATION_ORDER:
            logger.warning(f"Tabla '{table}' no reconocida, saltando")
            continue
        result = _migrate_table(client, sqlite_storage, table, dry_run=dry_run)
        results.append(result)

    duration = time.time() - start_time

    # Verificar conteos
    if not dry_run:
        logger.info("\nVerificando conteos...")
        results = _verify_counts(client, results)

    # Resumen
    logger.info("=" * 60)
    logger.info("MIGRACION COMPLETADA")
    logger.info(f"Duracion: {duration:.1f}s")
    logger.info("")

    for r in results:
        target = r.get("target_count", "N/A")
        status = r.get("status", "DRY")
        logger.info(
            f"  {r['table']:20s} | SQLite: {r['source_count']:>6} | "
            f"Supabase: {str(target):>6} | {status}"
        )

    logger.info("=" * 60)
    return {"results": results, "duration_seconds": round(duration, 2)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrar datos de SQLite a Supabase via REST API"
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
