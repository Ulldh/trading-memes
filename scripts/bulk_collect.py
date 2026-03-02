#!/usr/bin/env python3
"""
bulk_collect.py - Recoleccion masiva de tokens para alcanzar 1000+.

Usa TODAS las fuentes disponibles:
  - GeckoTerminal: new_pools (10 paginas), trending_pools, top_pools (5 paginas)
  - DexScreener: token_profiles, boosted_tokens

Luego ejecuta el pipeline completo de enriquecimiento:
  - DexScreener pairs (buyers/sellers)
  - OHLCV historico
  - Holders (Solana)
  - Contratos (EVM)
  - Features

Uso:
    python scripts/bulk_collect.py              # Una ronda completa
    python scripts/bulk_collect.py --rounds 3   # 3 rondas (espera entre rondas)
    python scripts/bulk_collect.py --features   # Recalcular features al final
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Agregar el directorio raiz al path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.api import CoinGeckoClient, DexScreenerClient, SolanaRPC, EtherscanClient
from src.data.collector import DataCollector
from src.data.storage import Storage
from src.utils.logger import get_logger
from config import SUPPORTED_CHAINS

logger = get_logger("bulk_collect")


def discover_from_all_sources(collector: DataCollector, pages_new: int = 10, pages_top: int = 5) -> list[dict]:
    """
    Descubre tokens de TODAS las fuentes disponibles.

    Args:
        collector: Instancia de DataCollector
        pages_new: Paginas de new_pools por chain
        pages_top: Paginas de top_pools por chain

    Returns:
        Lista combinada de tokens descubiertos (deduplicados)
    """
    all_tokens = []
    seen_ids = set()

    def add_tokens(tokens: list[dict], source: str):
        """Agrega tokens evitando duplicados."""
        added = 0
        for t in tokens:
            tid = t.get("token_address") or t.get("token_id")
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                all_tokens.append(t)
                added += 1
        logger.info(f"  [{source}] {added} nuevos (de {len(tokens)} encontrados)")

    chains = list(SUPPORTED_CHAINS.keys())

    # --- Fuente 1: New pools (GeckoTerminal) - 10 paginas ---
    logger.info(f"=== FUENTE 1: New Pools ({pages_new} paginas x {len(chains)} chains) ===")
    new_tokens = collector.discover_new_pools(chains=chains, pages=pages_new)
    add_tokens(new_tokens, "new_pools")

    # --- Fuente 2: Trending pools (GeckoTerminal) ---
    logger.info("=== FUENTE 2: Trending Pools ===")
    for chain in chains:
        chain_config = SUPPORTED_CHAINS.get(chain, {})
        gecko_chain_id = chain_config.get("geckoterminal_id", chain)
        try:
            trending = collector.gecko.get_trending_pools(gecko_chain_id)
            # Convertir al formato esperado (agregar chain)
            for t in trending:
                t["chain"] = chain
            add_tokens(trending, f"trending_{chain}")
        except Exception as e:
            logger.warning(f"Error obteniendo trending para {chain}: {e}")

    # --- Fuente 3: Top pools por volumen (GeckoTerminal) ---
    logger.info(f"=== FUENTE 3: Top Pools ({pages_top} paginas x {len(chains)} chains) ===")
    for chain in chains:
        chain_config = SUPPORTED_CHAINS.get(chain, {})
        gecko_chain_id = chain_config.get("geckoterminal_id", chain)
        for page in range(1, pages_top + 1):
            try:
                top = collector.gecko.get_top_pools(gecko_chain_id, page=page)
                for t in top:
                    t["chain"] = chain
                add_tokens(top, f"top_{chain}_p{page}")
            except Exception as e:
                logger.warning(f"Error obteniendo top pools {chain} p{page}: {e}")

    # --- Fuente 4: Token profiles (DexScreener) ---
    logger.info("=== FUENTE 4: DexScreener Token Profiles ===")
    try:
        profiles = collector.dex.get_token_profiles()
        for p in profiles:
            # Mapear formato DexScreener a formato esperado
            chain_id = p.get("chain_id", "").lower()
            # Mapear chainId de DexScreener a nuestros nombres
            chain_map = {"solana": "solana", "ethereum": "ethereum", "base": "base"}
            chain = chain_map.get(chain_id)
            if chain and p.get("token_address"):
                p["chain"] = chain
        profiles_filtered = [p for p in profiles if p.get("chain") in chains]
        add_tokens(profiles_filtered, "dex_profiles")
    except Exception as e:
        logger.warning(f"Error obteniendo profiles: {e}")

    # --- Fuente 5: Boosted tokens (DexScreener) ---
    logger.info("=== FUENTE 5: DexScreener Boosted Tokens ===")
    try:
        boosted = collector.dex.get_boosted_tokens()
        for b in boosted:
            chain_id = b.get("chain_id", "").lower()
            chain_map = {"solana": "solana", "ethereum": "ethereum", "base": "base"}
            chain = chain_map.get(chain_id)
            if chain and b.get("token_address"):
                b["chain"] = chain
        boosted_filtered = [b for b in boosted if b.get("chain") in chains]
        add_tokens(boosted_filtered, "dex_boosted")
    except Exception as e:
        logger.warning(f"Error obteniendo boosted: {e}")

    logger.info(f"\n>>> TOTAL DESCUBIERTOS: {len(all_tokens)} tokens unicos <<<")
    return all_tokens


def enrich_tokens(collector: DataCollector, tokens: list[dict]):
    """
    Ejecuta el pipeline de enriquecimiento completo sobre TODOS
    los tokens descubiertos. Los metodos del collector ya manejan
    duplicados internamente (discover_new_pools ya guarda en BD).
    """
    if not tokens:
        logger.info("No hay tokens para enriquecer.")
        return

    # Filtrar tokens que ya tienen OHLCV para solo enriquecer los que faltan
    storage = collector.storage
    tokens_con_ohlcv = set()
    try:
        df = storage.query("SELECT DISTINCT token_id FROM ohlcv")
        tokens_con_ohlcv = set(df["token_id"].tolist())
    except Exception:
        pass

    tokens_sin_ohlcv = [
        t for t in tokens
        if (t.get("token_address") or t.get("token_id")) not in tokens_con_ohlcv
    ]
    logger.info(
        f"Tokens a enriquecer: {len(tokens_sin_ohlcv)} sin OHLCV "
        f"(de {len(tokens)} descubiertos, {len(tokens_con_ohlcv)} ya tienen OHLCV)"
    )

    if not tokens_sin_ohlcv:
        logger.info("Todos los tokens ya tienen OHLCV.")
        return

    # Pipeline de enriquecimiento (solo tokens sin datos)
    logger.info("--- Enriqueciendo con DexScreener ---")
    collector.enrich_with_dexscreener(tokens_sin_ohlcv)

    logger.info("--- Recopilando OHLCV ---")
    collector.collect_ohlcv(tokens_sin_ohlcv)

    logger.info("--- Recopilando holders (Solana) ---")
    collector.collect_holders(tokens_sin_ohlcv)

    logger.info("--- Verificando contratos (EVM) ---")
    collector.collect_contract_info(tokens_sin_ohlcv)


def rebuild_features(storage: Storage):
    """Recalcula features para TODOS los tokens."""
    from src.features.builder import FeatureBuilder

    logger.info("=== RECALCULANDO FEATURES ===")
    builder = FeatureBuilder(storage)
    df = builder.build_all_features()

    if not df.empty:
        storage.save_features_df(df)
        logger.info(f"Features guardados: {len(df)} tokens x {len(df.columns)} features")
    else:
        logger.warning("No se pudieron calcular features")


def print_stats(storage: Storage):
    """Imprime estadisticas actuales de la BD."""
    stats = storage.stats()
    tokens_by_chain = storage.query("SELECT chain, COUNT(*) as cnt FROM tokens GROUP BY chain")
    total = storage.query("SELECT COUNT(*) as total FROM tokens").iloc[0]["total"]

    print("\n" + "=" * 50)
    print(f"  ESTADO DE LA BASE DE DATOS")
    print("=" * 50)
    print(f"  Total tokens: {total}")
    for _, row in tokens_by_chain.iterrows():
        print(f"    {row['chain']:12s}: {row['cnt']}")
    ohlcv = storage.query("SELECT COUNT(DISTINCT token_id) as t, COUNT(*) as v FROM ohlcv")
    print(f"  Tokens con OHLCV: {ohlcv.iloc[0]['t']} ({ohlcv.iloc[0]['v']} velas)")
    features = storage.query("SELECT COUNT(*) as cnt FROM features")
    print(f"  Tokens con features: {features.iloc[0]['cnt']}")
    labels = storage.query("SELECT COUNT(*) as cnt FROM labels")
    print(f"  Tokens con labels: {labels.iloc[0]['cnt']}")
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Recoleccion masiva de tokens")
    parser.add_argument("--rounds", type=int, default=1, help="Numero de rondas de descubrimiento")
    parser.add_argument("--pages-new", type=int, default=10, help="Paginas de new_pools por chain")
    parser.add_argument("--pages-top", type=int, default=5, help="Paginas de top_pools por chain")
    parser.add_argument("--features", action="store_true", help="Recalcular features al final")
    parser.add_argument("--wait", type=int, default=120, help="Segundos de espera entre rondas")
    args = parser.parse_args()

    storage = Storage()
    collector = DataCollector()

    print_stats(storage)
    inicio = time.time()

    for ronda in range(1, args.rounds + 1):
        logger.info(f"\n{'#' * 60}")
        logger.info(f"RONDA {ronda}/{args.rounds} - {datetime.now(timezone.utc).isoformat()}")
        logger.info(f"{'#' * 60}")

        # Descubrir de todas las fuentes
        tokens = discover_from_all_sources(
            collector,
            pages_new=args.pages_new,
            pages_top=args.pages_top
        )

        # Enriquecer (solo tokens nuevos)
        enrich_tokens(collector, tokens)

        print_stats(storage)

        # Esperar entre rondas (para evitar rate limits)
        if ronda < args.rounds:
            logger.info(f"Esperando {args.wait}s antes de la siguiente ronda...")
            time.sleep(args.wait)

    # Recalcular features si se pidio
    if args.features:
        rebuild_features(storage)

    duracion = time.time() - inicio
    logger.info(f"\nRecoleccion masiva completada en {duracion:.0f}s ({duracion/60:.1f} min)")
    print_stats(storage)


if __name__ == "__main__":
    main()
