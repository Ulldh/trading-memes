#!/usr/bin/env python3
"""
backfill_historical.py — Rellena la BD con tokens historicos.

Busca tokens que ya existen en los DEX pero que nuestro pipeline diario
no descubrio (porque solo mira "new_pools"). Esto es CRITICO para
entrenar el modelo con mas gems y rugs historicos.

Fuentes de descubrimiento:
  1. gecko_deep   — GeckoTerminal paginas 30-100 (new_pools que nos perdimos)
  2. gecko_volume — GeckoTerminal top pools por volumen 24h
  3. coingecko_gainers — CoinGecko top gainers por categoria meme
  4. dex_search   — DexScreener busqueda por keywords de narrativas
  5. all          — Las 4 fuentes anteriores

Uso:
    python scripts/backfill_historical.py --source all --max-tokens 5000
    python scripts/backfill_historical.py --source gecko_deep --pages 50
    python scripts/backfill_historical.py --source dex_search --keywords "pepe,doge"
    python scripts/backfill_historical.py --source coingecko_gainers
    python scripts/backfill_historical.py --dry-run --source all

El script es idempotente: ejecutar multiples veces es seguro (upsert).
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Agregar el directorio raiz al path para imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.api.coingecko_client import CoinGeckoClient
from src.api.dexscreener_client import DexScreenerClient
from src.data.supabase_storage import get_storage
from src.utils.helpers import safe_float
from src.utils.logger import get_logger

# Importar configuracion de cadenas soportadas
try:
    from config import SUPPORTED_CHAINS
except ImportError:
    SUPPORTED_CHAINS = {
        "solana": {"geckoterminal_id": "solana", "dexscreener_id": "solana"},
        "ethereum": {"geckoterminal_id": "eth", "dexscreener_id": "ethereum"},
        "base": {"geckoterminal_id": "base", "dexscreener_id": "base"},
        "bsc": {"geckoterminal_id": "bsc", "dexscreener_id": "bsc"},
        "arbitrum": {"geckoterminal_id": "arbitrum", "dexscreener_id": "arbitrum"},
    }

logger = get_logger(__name__)


# ================================================================
# KEYWORDS PARA BUSQUEDA POR NARRATIVA (DexScreener)
# ================================================================
# Narrativas y temas populares en el mundo de las memecoins.
# Cada keyword genera ~30 resultados en DexScreener.
DEFAULT_KEYWORDS = [
    "pepe", "doge", "shib", "trump", "ai", "cat", "wojak",
    "chad", "based", "moon", "inu", "floki", "elon", "grok",
    "bonk", "wif", "popcat", "brett", "toshi", "mog",
]

# Categorias de CoinGecko relevantes para memecoins
COINGECKO_CATEGORIES = [
    "meme-token",
    "solana-meme-coins",
    "base-meme-coins",
    "dog-themed-coins",
    "cat-themed-coins",
    "frog-themed-coins",
    "political-meme-coins",
]


class HistoricalBackfiller:
    """
    Descubre y guarda tokens historicos desde multiples fuentes.

    Todas las fuentes usan APIs gratuitas (GeckoTerminal, DexScreener)
    o con key demo (CoinGecko). No consume CU de Birdeye.

    El script es idempotente: usa upsert_token() para no duplicar.
    """

    def __init__(self, dry_run: bool = False, chains: Optional[list[str]] = None):
        """
        Inicializa los clientes de API y el storage.

        Args:
            dry_run: Si True, solo cuenta tokens sin guardarlos.
            chains: Lista de cadenas a procesar. None = todas.
        """
        self.dry_run = dry_run
        self.chains = chains or list(SUPPORTED_CHAINS.keys())
        self.gecko = CoinGeckoClient()
        self.dex = DexScreenerClient()
        self.storage = get_storage() if not dry_run else None

        # Tokens existentes en la DB (para deduplicacion rapida)
        self._existing_ids: Optional[set] = None

        # Contadores globales
        self.stats = {
            "total_discovered": 0,
            "total_new": 0,
            "total_existing": 0,
            "ohlcv_collected": 0,
            "ohlcv_errors": 0,
            "by_source": {},
        }

    def _load_existing_ids(self) -> set:
        """
        Carga IDs de tokens existentes en la DB para deduplicacion.

        Se cachea en memoria para no repetir la query por cada token.
        """
        if self._existing_ids is not None:
            return self._existing_ids

        if self.dry_run or not self.storage:
            self._existing_ids = set()
            return self._existing_ids

        try:
            df = self.storage.query("SELECT token_id FROM tokens")
            self._existing_ids = set(df["token_id"].tolist()) if not df.empty else set()
            logger.info(f"Tokens existentes en DB: {len(self._existing_ids)}")
        except Exception as e:
            logger.warning(f"Error cargando tokens existentes: {e}")
            self._existing_ids = set()

        return self._existing_ids

    def _save_token(
        self, token_id: str, chain: str, name: str, symbol: str,
        pool_address: str = "", dex: str = "", source: str = "",
    ) -> bool:
        """
        Guarda un token en la DB via upsert. Retorna True si es nuevo.

        Args:
            token_id: Direccion del contrato del token.
            chain: Cadena del token ("solana", "ethereum", etc.)
            name: Nombre del token.
            symbol: Ticker del token.
            pool_address: Direccion del pool (opcional).
            dex: Nombre del DEX donde se encontro.
            source: Fuente de descubrimiento (para tracking).

        Returns:
            True si el token es nuevo (no existia en la DB).
        """
        if not token_id or not chain:
            return False

        existing = self._load_existing_ids()
        is_new = token_id not in existing

        if not self.dry_run and self.storage:
            try:
                self.storage.upsert_token({
                    "token_id": token_id,
                    "chain": chain,
                    "name": name[:100] if name else "",
                    "symbol": symbol[:20] if symbol else "",
                    "pool_address": pool_address,
                    "dex": dex or source,
                    "created_at": None,
                    "total_supply": None,
                    "decimals": None,
                })
                if is_new:
                    existing.add(token_id)
            except Exception as e:
                logger.debug(f"Error guardando token {token_id[:12]}...: {e}")
                return False

        self.stats["total_discovered"] += 1
        if is_new:
            self.stats["total_new"] += 1
        else:
            self.stats["total_existing"] += 1

        return is_new

    def _collect_ohlcv_for_token(
        self, token_id: str, chain: str, pool_address: str,
    ) -> bool:
        """
        Recopila OHLCV via GeckoTerminal para un token con pool_address.

        Args:
            token_id: Direccion del token.
            chain: Cadena del token.
            pool_address: Direccion del pool (requerido por GeckoTerminal).

        Returns:
            True si se obtuvieron velas correctamente.
        """
        if self.dry_run or not pool_address or not self.storage:
            return False

        chain_config = SUPPORTED_CHAINS.get(chain, {})
        gecko_chain_id = chain_config.get("geckoterminal_id", chain)

        try:
            velas = self.gecko.get_pool_ohlcv(
                chain=gecko_chain_id,
                pool_address=pool_address,
                timeframe="day",
                limit=100,  # Maximo historial posible
            )

            if not velas:
                return False

            ohlcv_rows = []
            for vela in velas:
                ts_valor = vela.get("timestamp", 0)
                if ts_valor:
                    ts_iso = datetime.fromtimestamp(
                        ts_valor, tz=timezone.utc
                    ).isoformat()
                else:
                    ts_iso = ""

                ohlcv_rows.append({
                    "token_id": token_id,
                    "chain": chain,
                    "pool_address": pool_address,
                    "timeframe": "day",
                    "timestamp": ts_iso,
                    "open": safe_float(vela.get("open")),
                    "high": safe_float(vela.get("high")),
                    "low": safe_float(vela.get("low")),
                    "close": safe_float(vela.get("close")),
                    "volume": safe_float(vela.get("volume")),
                })

            if ohlcv_rows:
                self.storage.insert_ohlcv_batch(ohlcv_rows)
                return True

        except Exception as e:
            logger.debug(f"Error OHLCV para {token_id[:12]}...: {e}")

        return False

    # ================================================================
    # FUENTE 1: GeckoTerminal paginas profundas (new_pools 30-100)
    # ================================================================

    def backfill_gecko_deep(
        self,
        pages: int = 70,
        start_page: int = 31,
        collect_ohlcv: bool = True,
        max_tokens: int = 10000,
    ) -> dict:
        """
        Descubre tokens de GeckoTerminal paginas profundas (31-100).

        El pipeline diario solo consulta las primeras 30 paginas de
        new_pools. Aqui vamos a las paginas 31-100 para encontrar
        tokens que nos perdimos.

        100 paginas x 5 cadenas x 20 tokens/pagina = ~10,000 tokens
        Rate: 30 calls/min = ~17 minutos para 500 paginas

        Args:
            pages: Numero de paginas adicionales a consultar.
            start_page: Pagina donde empezar (31 = despues de las daily).
            collect_ohlcv: Si True, tambien recopila OHLCV.
            max_tokens: Limite maximo de tokens a procesar.

        Returns:
            Dict con estadisticas de esta fuente.
        """
        source = "gecko_deep"
        source_stats = {"discovered": 0, "new": 0, "ohlcv": 0}

        logger.info("=" * 60)
        logger.info(
            f"FUENTE 1: GeckoTerminal deep pages ({start_page}-{start_page + pages - 1})"
        )
        logger.info(f"Cadenas: {self.chains}")
        logger.info("=" * 60)

        tokens_processed = 0

        for chain in self.chains:
            chain_config = SUPPORTED_CHAINS.get(chain, {})
            gecko_chain_id = chain_config.get("geckoterminal_id", chain)

            logger.info(f"Escaneando '{chain}' paginas {start_page}-{start_page + pages - 1}...")

            for page in range(start_page, start_page + pages):
                if tokens_processed >= max_tokens:
                    logger.info(f"Limite de {max_tokens} tokens alcanzado, deteniendo")
                    break

                try:
                    pools = self.gecko.get_new_pools(gecko_chain_id, page=page)

                    if not pools:
                        logger.info(f"Sin mas pools en '{chain}' pagina {page}")
                        break

                    for pool in pools:
                        token_id = pool.get("base_token_address", "")
                        pool_address = pool.get("pool_address", "")
                        name = pool.get("name", "")
                        symbol = name.split(" / ")[0].strip() if " / " in name else name

                        if not token_id:
                            token_id = pool_address

                        is_new = self._save_token(
                            token_id=token_id,
                            chain=chain,
                            name=name,
                            symbol=symbol,
                            pool_address=pool_address,
                            dex=pool.get("dex", ""),
                            source=source,
                        )

                        source_stats["discovered"] += 1
                        if is_new:
                            source_stats["new"] += 1

                        # Recopilar OHLCV para tokens nuevos con pool_address
                        if is_new and collect_ohlcv and pool_address:
                            if self._collect_ohlcv_for_token(token_id, chain, pool_address):
                                source_stats["ohlcv"] += 1
                                self.stats["ohlcv_collected"] += 1
                            else:
                                self.stats["ohlcv_errors"] += 1

                        tokens_processed += 1

                    # Pausa entre paginas (rate limit: 30 calls/min)
                    time.sleep(0.5)

                except Exception as e:
                    logger.warning(f"Error en '{chain}' pagina {page}: {e}")
                    continue

                # Progreso cada 10 paginas
                if (page - start_page + 1) % 10 == 0:
                    logger.info(
                        f"  '{chain}' pagina {page}: "
                        f"{source_stats['discovered']} descubiertos, "
                        f"{source_stats['new']} nuevos"
                    )

        self.stats["by_source"][source] = source_stats
        logger.info(
            f"Gecko deep completado: {source_stats['discovered']} descubiertos, "
            f"{source_stats['new']} nuevos, {source_stats['ohlcv']} con OHLCV"
        )
        return source_stats

    # ================================================================
    # FUENTE 2: GeckoTerminal top pools por volumen
    # ================================================================

    def backfill_gecko_volume(
        self,
        pages: int = 20,
        collect_ohlcv: bool = True,
        max_tokens: int = 5000,
    ) -> dict:
        """
        Descubre tokens de los pools con mayor volumen en GeckoTerminal.

        Obtiene pools ordenados por volumen 24h descendente. Estos son
        los tokens mas activos del mercado — muchos son memecoins
        establecidas que ya completaron su ciclo (ideal para training).

        Args:
            pages: Paginas a consultar por cadena.
            collect_ohlcv: Si True, recopila OHLCV para tokens nuevos.
            max_tokens: Limite de tokens total.

        Returns:
            Dict con estadisticas.
        """
        source = "gecko_volume"
        source_stats = {"discovered": 0, "new": 0, "ohlcv": 0}

        logger.info("=" * 60)
        logger.info(f"FUENTE 2: GeckoTerminal top pools por volumen ({pages} paginas)")
        logger.info("=" * 60)

        tokens_processed = 0

        for chain in self.chains:
            chain_config = SUPPORTED_CHAINS.get(chain, {})
            gecko_chain_id = chain_config.get("geckoterminal_id", chain)

            logger.info(f"Top pools por volumen en '{chain}'...")

            for page in range(1, pages + 1):
                if tokens_processed >= max_tokens:
                    break

                try:
                    # get_top_pools ya ordena por volumen descendente
                    pools = self.gecko.get_top_pools(gecko_chain_id, page=page)

                    if not pools:
                        break

                    for pool in pools:
                        token_id = pool.get("base_token_address", "")
                        pool_address = pool.get("pool_address", "")
                        name = pool.get("name", "")
                        symbol = name.split(" / ")[0].strip() if " / " in name else name

                        if not token_id:
                            token_id = pool_address

                        is_new = self._save_token(
                            token_id=token_id,
                            chain=chain,
                            name=name,
                            symbol=symbol,
                            pool_address=pool_address,
                            dex=pool.get("dex", ""),
                            source=source,
                        )

                        source_stats["discovered"] += 1
                        if is_new:
                            source_stats["new"] += 1

                        if is_new and collect_ohlcv and pool_address:
                            if self._collect_ohlcv_for_token(token_id, chain, pool_address):
                                source_stats["ohlcv"] += 1
                                self.stats["ohlcv_collected"] += 1
                            else:
                                self.stats["ohlcv_errors"] += 1

                        tokens_processed += 1

                    time.sleep(0.5)

                except Exception as e:
                    logger.warning(f"Error top pools '{chain}' pagina {page}: {e}")
                    continue

        self.stats["by_source"][source] = source_stats
        logger.info(
            f"Gecko volume completado: {source_stats['discovered']} descubiertos, "
            f"{source_stats['new']} nuevos, {source_stats['ohlcv']} con OHLCV"
        )
        return source_stats

    # ================================================================
    # FUENTE 3: CoinGecko top gainers por categoria
    # ================================================================

    def backfill_coingecko_gainers(
        self, max_tokens: int = 5000,
    ) -> dict:
        """
        Descubre tokens top gainers de CoinGecko por categorias meme.

        Usa la API de CoinGecko Demo para obtener tokens ordenados por
        cambio de precio 24h descendente en categorias de memecoins.
        Captura tokens que estan pumping AHORA (potenciales gems).

        Nota: No recopila OHLCV porque CoinGecko no devuelve pool_address.
        El OHLCV se obtiene despues en el pipeline diario.

        Args:
            max_tokens: Limite de tokens total.

        Returns:
            Dict con estadisticas.
        """
        source = "coingecko_gainers"
        source_stats = {"discovered": 0, "new": 0}

        logger.info("=" * 60)
        logger.info("FUENTE 3: CoinGecko top gainers por categorias meme")
        logger.info(f"Categorias: {COINGECKO_CATEGORIES}")
        logger.info("=" * 60)

        tokens_processed = 0

        for categoria in COINGECKO_CATEGORIES:
            if tokens_processed >= max_tokens:
                break

            try:
                # Pedir 250 tokens por pagina (maximo CoinGecko)
                # Pagina 1 es suficiente para la mayoria de categorias
                for page in range(1, 4):  # Hasta 3 paginas = 750 tokens/categoria
                    if tokens_processed >= max_tokens:
                        break

                    tokens_cat = self.gecko.get_category_coins(
                        category=categoria,
                        per_page=250,
                        page=page,
                    )

                    if not tokens_cat:
                        break

                    logger.info(
                        f"CoinGecko '{categoria}' pagina {page}: "
                        f"{len(tokens_cat)} tokens en chains soportadas"
                    )

                    for item in tokens_cat:
                        address = item.get("token_address", "")
                        chain = item.get("chain", "")

                        if not address or chain not in self.chains:
                            continue

                        is_new = self._save_token(
                            token_id=address,
                            chain=chain,
                            name=item.get("name", ""),
                            symbol=item.get("symbol", ""),
                            source=f"coingecko-{categoria}",
                        )

                        source_stats["discovered"] += 1
                        if is_new:
                            source_stats["new"] += 1
                        tokens_processed += 1

                    # CoinGecko Demo tiene 30 calls/min — pausa entre paginas
                    time.sleep(2.5)

            except Exception as e:
                logger.warning(f"Error CoinGecko categoria '{categoria}': {e}")
                continue

        self.stats["by_source"][source] = source_stats
        logger.info(
            f"CoinGecko gainers completado: {source_stats['discovered']} descubiertos, "
            f"{source_stats['new']} nuevos"
        )
        return source_stats

    # ================================================================
    # FUENTE 4: DexScreener busqueda por keywords
    # ================================================================

    def backfill_dex_search(
        self,
        keywords: Optional[list[str]] = None,
        collect_ohlcv: bool = True,
        max_tokens: int = 5000,
    ) -> dict:
        """
        Descubre tokens buscando por keywords de narrativas en DexScreener.

        Cada keyword retorna ~30 tokens de todas las cadenas. Los keywords
        cubren las narrativas mas populares de memecoins: animales, memes,
        figuras publicas, temas AI, etc.

        Args:
            keywords: Lista de keywords. None usa DEFAULT_KEYWORDS.
            collect_ohlcv: Si True, recopila OHLCV para tokens con pool.
            max_tokens: Limite de tokens total.

        Returns:
            Dict con estadisticas.
        """
        source = "dex_search"
        source_stats = {"discovered": 0, "new": 0, "ohlcv": 0}
        cadenas_soportadas = set(self.chains)

        if keywords is None:
            keywords = DEFAULT_KEYWORDS

        logger.info("=" * 60)
        logger.info(f"FUENTE 4: DexScreener busqueda por {len(keywords)} keywords")
        logger.info(f"Keywords: {keywords}")
        logger.info("=" * 60)

        tokens_processed = 0

        for keyword in keywords:
            if tokens_processed >= max_tokens:
                break

            try:
                resultados = self.dex.search_pairs(keyword)

                if not resultados:
                    logger.debug(f"Sin resultados para '{keyword}'")
                    continue

                logger.info(f"DexScreener '{keyword}': {len(resultados)} pares encontrados")

                for par in resultados:
                    chain = par.get("chain", "")
                    token_id = par.get("base_token_address", "")
                    pool_address = par.get("pair_address", "")

                    # Solo cadenas soportadas
                    if chain not in cadenas_soportadas or not token_id:
                        continue

                    is_new = self._save_token(
                        token_id=token_id,
                        chain=chain,
                        name=par.get("base_token_name", ""),
                        symbol=par.get("base_token_symbol", ""),
                        pool_address=pool_address,
                        dex=par.get("dex", ""),
                        source=f"dex-search-{keyword}",
                    )

                    source_stats["discovered"] += 1
                    if is_new:
                        source_stats["new"] += 1

                    if is_new and collect_ohlcv and pool_address:
                        if self._collect_ohlcv_for_token(token_id, chain, pool_address):
                            source_stats["ohlcv"] += 1
                            self.stats["ohlcv_collected"] += 1
                        else:
                            self.stats["ohlcv_errors"] += 1

                    tokens_processed += 1

                # DexScreener tiene 300 calls/min pero paginacion es generosa
                time.sleep(0.3)

            except Exception as e:
                logger.warning(f"Error DexScreener keyword '{keyword}': {e}")
                continue

        self.stats["by_source"][source] = source_stats
        logger.info(
            f"DexScreener search completado: {source_stats['discovered']} descubiertos, "
            f"{source_stats['new']} nuevos, {source_stats['ohlcv']} con OHLCV"
        )
        return source_stats

    # ================================================================
    # ORQUESTADOR: EJECUTAR TODAS LAS FUENTES
    # ================================================================

    def run(
        self,
        source: str = "all",
        pages: int = 70,
        max_tokens: int = 5000,
        keywords: Optional[list[str]] = None,
        collect_ohlcv: bool = True,
    ) -> dict:
        """
        Ejecuta el backfill desde las fuentes seleccionadas.

        Args:
            source: Fuente a usar ("gecko_deep", "gecko_volume",
                "coingecko_gainers", "dex_search", "all").
            pages: Paginas para gecko_deep (default: 70).
            max_tokens: Limite global de tokens (repartido entre fuentes).
            keywords: Keywords para dex_search.
            collect_ohlcv: Si True, recopila OHLCV para tokens con pool.

        Returns:
            Dict con estadisticas globales.
        """
        inicio = time.time()

        logger.info("#" * 60)
        logger.info("BACKFILL HISTORICO INICIADO")
        logger.info(f"Fuente: {source}")
        logger.info(f"Max tokens: {max_tokens}")
        logger.info(f"Cadenas: {self.chains}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info(f"OHLCV: {collect_ohlcv}")
        logger.info("#" * 60)

        if source in ("gecko_deep", "all"):
            self.backfill_gecko_deep(
                pages=pages,
                collect_ohlcv=collect_ohlcv,
                max_tokens=max_tokens,
            )

        if source in ("gecko_volume", "all"):
            self.backfill_gecko_volume(
                pages=20,
                collect_ohlcv=collect_ohlcv,
                max_tokens=max_tokens,
            )

        if source in ("coingecko_gainers", "all"):
            self.backfill_coingecko_gainers(
                max_tokens=max_tokens,
            )

        if source in ("dex_search", "all"):
            self.backfill_dex_search(
                keywords=keywords,
                collect_ohlcv=collect_ohlcv,
                max_tokens=max_tokens,
            )

        duracion = time.time() - inicio
        self.stats["duration_seconds"] = round(duracion, 2)

        # Resumen final
        logger.info("#" * 60)
        logger.info("BACKFILL HISTORICO COMPLETADO")
        logger.info(f"Total descubiertos: {self.stats['total_discovered']}")
        logger.info(f"Total nuevos:       {self.stats['total_new']}")
        logger.info(f"Total existentes:   {self.stats['total_existing']}")
        logger.info(f"OHLCV recopilados:  {self.stats['ohlcv_collected']}")
        logger.info(f"OHLCV errores:      {self.stats['ohlcv_errors']}")
        logger.info(f"Duracion:           {duracion:.1f}s")
        logger.info("Por fuente:")
        for src, src_stats in self.stats["by_source"].items():
            logger.info(f"  {src}: {src_stats}")
        logger.info("#" * 60)

        # Mostrar estado de la DB si no es dry run
        if not self.dry_run and self.storage:
            try:
                db_stats = self.storage.stats()
                logger.info(f"DB totals: {db_stats}")
            except Exception as e:
                logger.debug(f"Error obteniendo stats de DB: {e}")

        return self.stats


# ================================================================
# PUNTO DE ENTRADA
# ================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rellena la BD con tokens historicos de multiples fuentes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python scripts/backfill_historical.py --source all --max-tokens 5000
  python scripts/backfill_historical.py --source gecko_deep --pages 50
  python scripts/backfill_historical.py --source dex_search --keywords "pepe,doge,ai"
  python scripts/backfill_historical.py --source coingecko_gainers
  python scripts/backfill_historical.py --source gecko_volume --chains solana,base
  python scripts/backfill_historical.py --dry-run --source all
        """,
    )

    parser.add_argument(
        "--source",
        type=str,
        default="all",
        choices=["gecko_deep", "gecko_volume", "coingecko_gainers", "dex_search", "all"],
        help="Fuente de descubrimiento (default: all)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=5000,
        help="Limite total de tokens a procesar (default: 5000)",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=70,
        help="Paginas para gecko_deep (default: 70, rango 31-100)",
    )
    parser.add_argument(
        "--chains",
        type=str,
        default=None,
        help="Cadenas separadas por coma (default: todas). Ej: solana,base",
    )
    parser.add_argument(
        "--keywords",
        type=str,
        default=None,
        help="Keywords para dex_search, separados por coma. Ej: pepe,doge,ai",
    )
    parser.add_argument(
        "--no-ohlcv",
        action="store_true",
        help="No recopilar OHLCV (solo descubrir tokens)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo mostrar cuantos tokens se encontrarian, sin guardar",
    )

    args = parser.parse_args()

    # Parsear cadenas
    chains = None
    if args.chains:
        chains = [c.strip() for c in args.chains.split(",")]

    # Parsear keywords
    keywords = None
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",")]

    # Ejecutar backfill
    backfiller = HistoricalBackfiller(
        dry_run=args.dry_run,
        chains=chains,
    )

    stats = backfiller.run(
        source=args.source,
        pages=args.pages,
        max_tokens=args.max_tokens,
        keywords=keywords,
        collect_ohlcv=not args.no_ohlcv,
    )

    # Resumen para stdout (GitHub Actions lo captura)
    print(f"\nResultado: {stats}")
