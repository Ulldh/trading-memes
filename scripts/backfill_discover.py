#!/usr/bin/env python3
"""
backfill_discover.py - Descubrir tokens historicos para backfill.

Pagina Pump.fun con offsets altos para encontrar tokens de hace 3-6 meses
que ya tienen historial OHLCV maduro y pueden ser etiquetados inmediatamente.

Tambien busca pool_address via DexScreener para los tokens que no la tienen,
ya que sin pool_address no se puede obtener OHLCV de ninguna fuente.

Uso:
    python scripts/backfill_discover.py
    python scripts/backfill_discover.py --offset 5000 --pages 60
    python scripts/backfill_discover.py --dry-run
"""

import argparse
import sys
import time
from pathlib import Path

# Agregar el directorio raiz al path para imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.api.solana_discovery_client import SolanaDiscoveryClient
from src.api.dexscreener_client import DexScreenerClient
from src.data.storage import Storage
from src.utils.logger import get_logger
from src.utils.helpers import safe_float

logger = get_logger(__name__)


def discover_historical_tokens(
    offset: int = 1000,
    max_pages: int = 60,
    limit: int = 50,
    dry_run: bool = False,
) -> dict:
    """
    Descubre tokens historicos de Pump.fun y los guarda en la DB.

    Args:
        offset: Offset inicial para paginar Pump.fun. Offsets altos
            traen tokens mas antiguos (sort ASC por fecha de creacion).
        max_pages: Paginas maximas a recorrer (cada una trae 50 tokens).
        limit: Tokens por pagina (max 50).
        dry_run: Si True, solo muestra cuantos encontraria sin guardar.

    Returns:
        Dict con estadisticas: tokens_discovered, tokens_new, pool_enriched.
    """
    storage = Storage()
    discovery = SolanaDiscoveryClient()
    dex = DexScreenerClient()

    # Estadisticas
    stats = {
        "tokens_discovered": 0,
        "tokens_new": 0,
        "tokens_existing": 0,
        "pool_enriched": 0,
        "pool_errors": 0,
    }

    logger.info("=" * 60)
    logger.info("BACKFILL DISCOVER: Buscando tokens historicos de Pump.fun")
    logger.info(f"Offset: {offset}, Max pages: {max_pages}, Limit: {limit}")
    logger.info("=" * 60)

    # Paso 1: Descubrir tokens historicos
    tokens = discovery.get_pumpfun_historical(
        offset=offset,
        limit=limit,
        max_pages=max_pages,
    )

    stats["tokens_discovered"] = len(tokens)
    logger.info(f"Descubiertos: {len(tokens)} tokens de Pump.fun")

    if dry_run:
        logger.info("[DRY RUN] No se guardan tokens en la DB")
        return stats

    if not tokens:
        logger.info("No se descubrieron tokens, saliendo")
        return stats

    # Paso 2: Guardar tokens nuevos en la DB
    # Obtener tokens existentes para no duplicar
    existing_df = storage.get_all_tokens(chain="solana")
    existing_ids = set(existing_df["token_id"].tolist()) if not existing_df.empty else set()

    new_tokens = []
    for token in tokens:
        token_id = token.get("token_address") or token.get("token_id", "")
        if not token_id:
            continue

        if token_id in existing_ids:
            stats["tokens_existing"] += 1
            continue

        storage.upsert_token({
            "token_id": token_id,
            "chain": "solana",
            "name": token.get("name", ""),
            "symbol": token.get("symbol", ""),
            "dex": token.get("dex", "pump-fun"),
        })
        new_tokens.append(token)
        stats["tokens_new"] += 1

    logger.info(
        f"Guardados: {stats['tokens_new']} nuevos, "
        f"{stats['tokens_existing']} ya existian"
    )

    # Paso 3: Buscar pool_address via DexScreener para tokens nuevos
    # Sin pool_address no podemos obtener OHLCV
    if new_tokens:
        logger.info(f"Buscando pool_address para {len(new_tokens)} tokens nuevos...")

        for i, token in enumerate(new_tokens):
            token_id = token.get("token_address") or token.get("token_id", "")
            if not token_id:
                continue

            try:
                pares = dex.get_token_pairs("solana", token_id)
                if pares:
                    par = pares[0]
                    pool_address = par.get("pair_address", "")
                    dex_name = par.get("dex", "")
                    if pool_address:
                        storage.upsert_token({
                            "token_id": token_id,
                            "chain": "solana",
                            "pool_address": pool_address,
                            "dex": dex_name,
                        })
                        stats["pool_enriched"] += 1
                else:
                    stats["pool_errors"] += 1
            except Exception as e:
                logger.debug(f"Error buscando pool para {token_id[:10]}...: {e}")
                stats["pool_errors"] += 1

            # Progreso cada 50 tokens
            if (i + 1) % 50 == 0:
                logger.info(
                    f"Pool enrichment: {i + 1}/{len(new_tokens)} "
                    f"({stats['pool_enriched']} con pool)"
                )

            # Respetar rate limits de DexScreener
            time.sleep(0.2)

    # Resumen final
    logger.info("=" * 60)
    logger.info("BACKFILL DISCOVER COMPLETADO")
    logger.info(f"  Descubiertos:  {stats['tokens_discovered']}")
    logger.info(f"  Nuevos:        {stats['tokens_new']}")
    logger.info(f"  Ya existian:   {stats['tokens_existing']}")
    logger.info(f"  Con pool addr: {stats['pool_enriched']}")
    logger.info(f"  Sin pool:      {stats['pool_errors']}")
    logger.info("=" * 60)

    # Mostrar estado actualizado de la DB
    db_stats = storage.stats()
    logger.info(f"DB totals: {db_stats}")

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Descubrir tokens historicos de Pump.fun para backfill"
    )
    parser.add_argument(
        "--offset", type=int, default=1000,
        help="Offset inicial para paginar Pump.fun (default: 1000)"
    )
    parser.add_argument(
        "--pages", type=int, default=60,
        help="Paginas maximas a recorrer (default: 60, = ~3000 tokens)"
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Tokens por pagina (default: 50)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Solo descubrir, no guardar en DB"
    )

    args = parser.parse_args()

    stats = discover_historical_tokens(
        offset=args.offset,
        max_pages=args.pages,
        limit=args.limit,
        dry_run=args.dry_run,
    )

    print(f"\nResultado: {stats}")
