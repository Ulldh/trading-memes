#!/usr/bin/env python3
"""
backfill_ohlcv.py - Backfill masivo de OHLCV via Birdeye.

Lee tokens Solana de la DB que tienen OHLCV insuficiente (menos de 7 velas
diarias) y obtiene su historial completo via Birdeye API.

Para cada token:
    1. Determina la fecha de creacion (created_at en DB, o primera vela existente)
    2. Pide OHLCV diario desde creacion hasta creacion + 90 dias
    3. Guarda las velas nuevas en la tabla ohlcv

Birdeye free tier: 1 rps = 60 calls/min. Para 5000 tokens = ~83 min.

Uso:
    python scripts/backfill_ohlcv.py
    python scripts/backfill_ohlcv.py --max-tokens 500
    python scripts/backfill_ohlcv.py --min-ohlcv 0 --days 60
    python scripts/backfill_ohlcv.py --dry-run
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

# Agregar el directorio raiz al path para imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.api.birdeye_client import BirdeyeClient
from src.data.storage import Storage
from src.utils.logger import get_logger
from src.utils.helpers import safe_float

logger = get_logger(__name__)


def backfill_ohlcv(
    max_tokens: int = 5000,
    min_ohlcv: int = 7,
    days: int = 90,
    dry_run: bool = False,
) -> dict:
    """
    Backfill masivo de OHLCV via Birdeye para tokens Solana.

    Args:
        max_tokens: Maximo de tokens a procesar (controla duracion).
        min_ohlcv: Solo procesar tokens con menos de N velas diarias.
            7 = tokens que no pueden ser etiquetados por el labeler (return_7d).
        days: Dias de OHLCV a pedir desde la creacion del token.
        dry_run: Si True, solo muestra candidatos sin llamar a Birdeye.

    Returns:
        Dict con estadisticas: tokens_processed, candles_added, errors, skipped.
    """
    storage = Storage()
    birdeye = BirdeyeClient()

    stats = {
        "candidates": 0,
        "tokens_processed": 0,
        "candles_added": 0,
        "errors": 0,
        "skipped_no_date": 0,
    }

    if not birdeye.is_available:
        logger.error(
            "Birdeye API key no configurada. "
            "Agregar BIRDEYE_API_KEY al .env (obtener en https://bds.birdeye.so)"
        )
        return stats

    logger.info("=" * 60)
    logger.info("BACKFILL OHLCV: Obteniendo historico via Birdeye")
    logger.info(f"Max tokens: {max_tokens}, Min OHLCV: {min_ohlcv}, Dias: {days}")
    logger.info("=" * 60)

    # Buscar tokens Solana con OHLCV insuficiente
    # Prioridad: tokens sin OHLCV primero, luego los con pocas velas
    candidates_df = storage.query("""
        SELECT t.token_id, t.created_at,
               COUNT(CASE WHEN o.timeframe = 'day' THEN 1 END) as ohlcv_count
        FROM tokens t
        LEFT JOIN ohlcv o ON t.token_id = o.token_id
        WHERE t.chain = 'solana'
        GROUP BY t.token_id
        HAVING ohlcv_count < ?
        ORDER BY ohlcv_count ASC
        LIMIT ?
    """, (min_ohlcv, max_tokens))

    stats["candidates"] = len(candidates_df)
    logger.info(f"Candidatos encontrados: {len(candidates_df)} tokens con <{min_ohlcv} velas diarias")

    if candidates_df.empty:
        logger.info("No hay candidatos para backfill, todos tienen OHLCV suficiente")
        return stats

    if dry_run:
        logger.info("[DRY RUN] No se hacen llamadas a Birdeye")
        # Mostrar resumen de candidatos
        no_ohlcv = (candidates_df["ohlcv_count"] == 0).sum()
        has_some = (candidates_df["ohlcv_count"] > 0).sum()
        has_date = candidates_df["created_at"].notna().sum()
        logger.info(f"  Sin OHLCV:     {no_ohlcv}")
        logger.info(f"  Con algo:      {has_some}")
        logger.info(f"  Con fecha:     {has_date}")
        logger.info(f"  Sin fecha:     {len(candidates_df) - has_date}")
        return stats

    # Procesar cada token
    for _, row in tqdm(candidates_df.iterrows(), total=len(candidates_df),
                       desc="Backfill OHLCV", unit="token"):
        token_id = row["token_id"]
        created_at = row["created_at"]

        # Determinar timestamp de inicio
        created_unix = _parse_created_at(created_at)
        if not created_unix:
            # Sin fecha de creacion, intentar con 180 dias atras como fallback
            now = int(datetime.now(timezone.utc).timestamp())
            created_unix = now - (180 * 86400)
            stats["skipped_no_date"] += 1

        try:
            velas = birdeye.get_token_ohlcv_full(
                address=token_id,
                created_at_unix=created_unix,
                days=days,
                timeframe="1D",
                chain="solana",
            )

            if not velas:
                stats["errors"] += 1
                continue

            # Convertir al formato de storage.insert_ohlcv_batch
            ohlcv_rows = []
            for vela in velas:
                ohlcv_rows.append({
                    "token_id": token_id,
                    "chain": "solana",
                    "pool_address": token_id,  # Birdeye usa token address, no pool
                    "timeframe": "day",
                    "timestamp": vela["timestamp"],
                    "open": vela.get("open"),
                    "high": vela.get("high"),
                    "low": vela.get("low"),
                    "close": vela.get("close"),
                    "volume": vela.get("volume"),
                })

            if ohlcv_rows:
                storage.insert_ohlcv_batch(ohlcv_rows)
                stats["tokens_processed"] += 1
                stats["candles_added"] += len(ohlcv_rows)

        except Exception as e:
            logger.warning(f"Error en backfill para {token_id[:10]}...: {e}")
            stats["errors"] += 1

    # Resumen final
    logger.info("=" * 60)
    logger.info("BACKFILL OHLCV COMPLETADO")
    logger.info(f"  Candidatos:    {stats['candidates']}")
    logger.info(f"  Procesados:    {stats['tokens_processed']}")
    logger.info(f"  Velas nuevas:  {stats['candles_added']}")
    logger.info(f"  Errores:       {stats['errors']}")
    logger.info(f"  Sin fecha:     {stats['skipped_no_date']} (usaron fallback 180d)")
    logger.info("=" * 60)

    # Estado de la DB
    db_stats = storage.stats()
    logger.info(f"DB totals: {db_stats}")

    return stats


def _parse_created_at(created_at) -> int | None:
    """
    Convierte created_at (texto ISO o timestamp) a Unix timestamp (segundos).

    Args:
        created_at: Valor de la columna tokens.created_at.
            Puede ser ISO string, timestamp numerico, o None.

    Returns:
        Timestamp Unix en segundos, o None si no se puede parsear.
    """
    if not created_at:
        return None

    # Si ya es numerico
    try:
        ts = float(created_at)
        # Si parece milisegundos (>2000000000), convertir a segundos
        if ts > 2_000_000_000:
            ts = ts / 1000
        return int(ts)
    except (ValueError, TypeError):
        pass

    # Intentar parsear como ISO string
    try:
        # Manejar varios formatos ISO
        for fmt in [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S+00:00",
            "%Y-%m-%d %H:%M:%S",
        ]:
            try:
                dt = datetime.strptime(str(created_at), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return int(dt.timestamp())
            except ValueError:
                continue
    except Exception:
        pass

    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Backfill masivo de OHLCV via Birdeye para tokens Solana"
    )
    parser.add_argument(
        "--max-tokens", type=int, default=5000,
        help="Maximo de tokens a procesar (default: 5000)"
    )
    parser.add_argument(
        "--min-ohlcv", type=int, default=7,
        help="Solo tokens con menos de N velas diarias (default: 7)"
    )
    parser.add_argument(
        "--days", type=int, default=90,
        help="Dias de OHLCV desde creacion (default: 90)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Solo mostrar candidatos, no llamar a Birdeye"
    )

    args = parser.parse_args()

    stats = backfill_ohlcv(
        max_tokens=args.max_tokens,
        min_ohlcv=args.min_ohlcv,
        days=args.days,
        dry_run=args.dry_run,
    )

    print(f"\nResultado: {stats}")
