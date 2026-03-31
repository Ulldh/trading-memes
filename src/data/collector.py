"""
collector.py - Orquestador de recopilacion de datos.

Este modulo coordina la recopilacion de datos de todas las APIs
y los guarda en la base de datos SQLite. Diseñado para ejecutarse
diariamente como script de recopilacion prospectiva.

Flujo de recopilacion:
    1. Descubrir pools nuevos (GeckoTerminal)
    2. Enriquecer con datos de DexScreener (buyers/sellers)
    3. Obtener OHLCV historico (GeckoTerminal)
    4. Obtener holders top 20 (Solana RPC, solo para Solana)
    5. Verificar contratos (Etherscan, solo para ETH/Base)

Uso:
    from src.data.collector import DataCollector

    # Recopilacion diaria completa
    collector = DataCollector()
    stats = collector.run_daily_collection()
    print(stats)

    # Buscar info de un solo token
    data = collector.collect_single_token("DireccionDelToken...", "solana")
"""

import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from tqdm import tqdm

# Importar clientes de API del proyecto
from src.api import (
    BirdeyeClient,
    CoinGeckoClient,
    DexScreenerClient,
    SolanaRPC,
    EtherscanClient,
    SolanaDiscoveryClient,
)

# Importar almacenamiento (factory que elige SQLite o Supabase segun config)
from src.data.supabase_storage import get_storage

# Importar helpers para conversiones seguras
from src.utils.helpers import safe_float, safe_int

# Importar logger para registrar lo que hace el modulo
from src.utils.logger import get_logger

# Importar configuracion del proyecto
try:
    from config import SUPPORTED_CHAINS, PROCESSED_DIR
except ImportError:
    # Valores por defecto si config.py no esta disponible
    from pathlib import Path
    SUPPORTED_CHAINS = {
        "solana": {
            "geckoterminal_id": "solana",
            "dexscreener_id": "solana",
            "native_token": "SOL",
        },
        "ethereum": {
            "geckoterminal_id": "eth",
            "dexscreener_id": "ethereum",
            "native_token": "ETH",
        },
        "base": {
            "geckoterminal_id": "base",
            "dexscreener_id": "base",
            "native_token": "ETH",
        },
    }
    PROCESSED_DIR = Path("data/processed")

# Logger para este modulo
logger = get_logger(__name__)


class DataCollector:
    """
    Orquestador central de recopilacion de datos.

    Coordina llamadas a todas las APIs (GeckoTerminal, DexScreener,
    Solana RPC, Etherscan) y guarda los resultados en la base de datos
    SQLite a traves de la clase Storage.

    Cada metodo maneja errores de forma individual por token, de modo
    que si un token falla, los demas siguen procesandose normalmente.

    Args:
        storage: Instancia de Storage para guardar datos. Si no se pasa,
            se crea una nueva con la ruta por defecto (data/trading_memes.db).

    Ejemplo:
        collector = DataCollector()

        # Recopilacion diaria completa
        stats = collector.run_daily_collection()
        print(f"Tokens descubiertos: {stats['tokens_discovered']}")

        # Un solo token
        data = collector.collect_single_token("abc123...", "solana")
    """

    def __init__(self, storage=None):
        """
        Inicializa todos los clientes de API y el almacenamiento.

        Se crean instancias de cada cliente de API. Cada uno ya tiene
        rate limiting, retries y cache integrados (heredados de BaseAPIClient).
        """
        # Almacenamiento (factory elige SQLite o Supabase segun STORAGE_BACKEND)
        self.storage = storage or get_storage()

        # Cliente unificado para GeckoTerminal + CoinGecko Demo
        self.gecko = CoinGeckoClient()

        # Cliente para DexScreener (datos de buyers/sellers)
        self.dex = DexScreenerClient()

        # Cliente RPC para Solana (holders via Helius)
        self.solana_rpc = SolanaRPC()

        # Clientes Etherscan V2 - uno por cadena EVM (misma API key, distinto chainid)
        self._etherscan_clients = {
            "ethereum": EtherscanClient(chain="ethereum"),
            "base": EtherscanClient(chain="base"),
        }

        # Cliente de descubrimiento Solana (Pump.fun, Jupiter, Raydium)
        self.solana_discovery = SolanaDiscoveryClient()

        # Cliente Birdeye para OHLCV multi-chain (Solana, Ethereum, Base)
        # Birdeye tiene 900 calls/min (Lite) vs GeckoTerminal 30/min
        # Se usa como fuente primaria de OHLCV, con GeckoTerminal como fallback
        self.birdeye = BirdeyeClient()
        if self.birdeye.is_available:
            logger.info("BirdeyeClient disponible — OHLCV primario via Birdeye")
        else:
            logger.info("BirdeyeClient no disponible — OHLCV solo via GeckoTerminal")

        logger.info("DataCollector inicializado con todos los clientes de API")

    def _etherscan_for(self, chain: str) -> EtherscanClient:
        """Devuelve el cliente Etherscan V2 para la cadena indicada."""
        return self._etherscan_clients.get(chain, self._etherscan_clients["ethereum"])

    # ================================================================
    # PASO 1: DESCUBRIR POOLS NUEVOS
    # ================================================================

    def discover_new_pools(
        self, chains: Optional[list[str]] = None, pages: int = 10
    ) -> list[dict]:
        """
        Descubre pools nuevos en GeckoTerminal para todas las cadenas soportadas.

        Itera sobre cada cadena (solana, ethereum, base) y por cada una
        obtiene varias paginas de pools recientes. Cada pool se parsea
        y se guarda en la base de datos como token.

        Args:
            chains: Lista de cadenas a consultar. Si es None, usa todas
                las cadenas de SUPPORTED_CHAINS (solana, ethereum, base).
            pages: Numero de paginas a consultar por cadena (cada pagina
                tiene ~20 pools). Default 10 = ~200 tokens/cadena.
                Mas paginas = mas tokens descubiertos pero mas llamadas
                a la API.

        Returns:
            Lista de diccionarios con los tokens descubiertos. Cada dict
            tiene: token_id, chain, name, symbol, pool_address, price_usd,
            volume_24h, liquidity_usd, fdv, created_at, etc.

        Ejemplo:
            >>> collector = DataCollector()
            >>> tokens = collector.discover_new_pools(chains=["solana"], pages=2)
            >>> print(f"Descubiertos: {len(tokens)} tokens en Solana")
        """
        logger.info("=" * 60)
        logger.info("PASO 1: Descubriendo pools nuevos...")
        logger.info("=" * 60)

        # Si no se especifican cadenas, usar todas las soportadas
        if chains is None:
            chains = list(SUPPORTED_CHAINS.keys())

        # Lista para acumular todos los tokens descubiertos
        all_tokens: list[dict] = []

        # Iterar sobre cada cadena
        for chain in chains:
            # Obtener el ID que usa GeckoTerminal para esta cadena
            # Ej: "solana" -> "solana", "ethereum" -> "eth", "base" -> "base"
            chain_config = SUPPORTED_CHAINS.get(chain, {})
            gecko_chain_id = chain_config.get("geckoterminal_id", chain)

            logger.info(f"Buscando pools nuevos en '{chain}' ({pages} paginas)...")

            # Iterar sobre cada pagina
            for page in range(1, pages + 1):
                try:
                    # Llamar a GeckoTerminal para obtener pools nuevos
                    pools = self.gecko.get_new_pools(gecko_chain_id, page=page)

                    if not pools:
                        logger.info(
                            f"No hay mas pools en '{chain}' pagina {page}, saltando"
                        )
                        break

                    # Parsear cada pool y convertirlo a formato de token
                    for pool in pools:
                        try:
                            # Construir el dict del token a partir del pool
                            token = self._pool_to_token(pool, chain)

                            if token and token.get("token_id"):
                                # Guardar en la base de datos (upsert = insertar o actualizar)
                                self.storage.upsert_token(token)
                                all_tokens.append(token)

                        except Exception as e:
                            # Si un pool individual falla, no detener el resto
                            pool_addr = pool.get("pool_address", "desconocido")
                            logger.warning(
                                f"Error procesando pool {pool_addr[:10]}... "
                                f"en '{chain}': {e}"
                            )
                            continue

                    # Pausa breve entre paginas para no saturar la API
                    time.sleep(0.3)

                except Exception as e:
                    logger.error(
                        f"Error obteniendo pagina {page} de '{chain}': {e}"
                    )
                    continue

        # Resumen final del paso
        logger.info(
            f"Descubrimiento completado: {len(all_tokens)} tokens nuevos "
            f"en {len(chains)} cadenas"
        )
        return all_tokens

    # ================================================================
    # PASO 1B: DESCUBRIR TOKENS DESDE DEXSCREENER
    # ================================================================

    def discover_from_dexscreener(self) -> list[dict]:
        """
        Descubre tokens adicionales usando endpoints de DexScreener.

        DexScreener tiene 3 fuentes de descubrimiento que complementan
        a GeckoTerminal:
        1. Boosted tokens: tokens que pagaron por promocion (activos)
        2. Token profiles: tokens recientes con info social
        3. Community takeovers: tokens revividos por la comunidad

        Solo se añaden tokens de cadenas soportadas (solana, ethereum, base).
        Los tokens que ya existen en la BD se actualizan (upsert).

        Returns:
            Lista de diccionarios con tokens descubiertos.
        """
        logger.info("=" * 60)
        logger.info("PASO 1B: Descubriendo tokens desde DexScreener...")
        logger.info("=" * 60)

        all_tokens: list[dict] = []
        cadenas_soportadas = set(SUPPORTED_CHAINS.keys())

        # --- 1. Tokens boosted (pagaron por promocion = proyectos activos) ---
        try:
            boosted = self.dex.get_boosted_tokens()
            logger.info(f"DexScreener boosted: {len(boosted)} tokens obtenidos")

            for item in boosted:
                chain = item.get("chain", "")
                address = item.get("token_address", "")

                # Solo cadenas soportadas y con direccion valida
                if chain not in cadenas_soportadas or not address:
                    continue

                token = {
                    "token_id": address,
                    "chain": chain,
                    "name": item.get("description", "")[:100],
                    "symbol": "",
                    "pool_address": "",
                    "dex": "dexscreener-boost",
                    "created_at": None,
                    "total_supply": None,
                    "decimals": None,
                }

                try:
                    self.storage.upsert_token(token)
                    all_tokens.append(token)
                except Exception as e:
                    logger.debug(f"Error guardando token boosted {address[:10]}...: {e}")

        except Exception as e:
            logger.warning(f"Error obteniendo tokens boosted de DexScreener: {e}")

        # --- 2. Perfiles de tokens recientes (con info social) ---
        try:
            profiles = self.dex.get_token_profiles()
            logger.info(f"DexScreener profiles: {len(profiles)} tokens obtenidos")

            for item in profiles:
                chain = item.get("chain", "")
                address = item.get("token_address", "")

                if chain not in cadenas_soportadas or not address:
                    continue

                token = {
                    "token_id": address,
                    "chain": chain,
                    "name": item.get("description", "")[:100],
                    "symbol": "",
                    "pool_address": "",
                    "dex": "dexscreener-profile",
                    "created_at": None,
                    "total_supply": None,
                    "decimals": None,
                }

                try:
                    self.storage.upsert_token(token)
                    all_tokens.append(token)
                except Exception as e:
                    logger.debug(f"Error guardando token profile {address[:10]}...: {e}")

        except Exception as e:
            logger.warning(f"Error obteniendo perfiles de DexScreener: {e}")

        # --- 3. Community takeovers (tokens revividos) ---
        try:
            takeovers = self.dex.get_community_takeovers()
            logger.info(f"DexScreener takeovers: {len(takeovers)} tokens obtenidos")

            for item in takeovers:
                chain = item.get("chain", "")
                address = item.get("token_address", "")

                if chain not in cadenas_soportadas or not address:
                    continue

                token = {
                    "token_id": address,
                    "chain": chain,
                    "name": item.get("description", "")[:100],
                    "symbol": "",
                    "pool_address": "",
                    "dex": "dexscreener-cto",
                    "created_at": None,
                    "total_supply": None,
                    "decimals": None,
                }

                try:
                    self.storage.upsert_token(token)
                    all_tokens.append(token)
                except Exception as e:
                    logger.debug(f"Error guardando token CTO {address[:10]}...: {e}")

        except Exception as e:
            logger.warning(f"Error obteniendo community takeovers de DexScreener: {e}")

        logger.info(
            f"Descubrimiento DexScreener completado: "
            f"{len(all_tokens)} tokens nuevos añadidos"
        )
        return all_tokens

    # ================================================================
    # PASO 1C: DESCUBRIR TOKENS DESDE COINGECKO CATEGORIAS
    # ================================================================

    def discover_from_coingecko_categories(self) -> list[dict]:
        """
        Descubre memecoins usando categorias de CoinGecko.

        CoinGecko tiene categorias tematicas de tokens. Consultamos las
        mas relevantes para memecoins. La API devuelve tokens con sus
        contract addresses por chain, filtramos por cadenas soportadas.

        Categorias consultadas:
        - meme-token: categoria principal de memecoins
        - solana-meme-coins: memecoins especificas de Solana

        Returns:
            Lista de diccionarios con tokens descubiertos.
        """
        logger.info("=" * 60)
        logger.info("PASO 1C: Descubriendo tokens desde categorias CoinGecko...")
        logger.info("=" * 60)

        all_tokens: list[dict] = []

        # Categorias de CoinGecko relevantes para memecoins
        # Los slugs se obtienen de: https://api.coingecko.com/api/v3/coins/categories/list
        categorias = [
            "meme-token",
            "solana-meme-coins",
        ]

        for categoria in categorias:
            try:
                tokens_cat = self.gecko.get_category_coins(
                    category=categoria,
                    per_page=250,
                    page=1,
                )

                logger.info(
                    f"CoinGecko categoria '{categoria}': "
                    f"{len(tokens_cat)} tokens en chains soportadas"
                )

                for item in tokens_cat:
                    address = item.get("token_address", "")
                    chain = item.get("chain", "")

                    if not address or not chain:
                        continue

                    token = {
                        "token_id": address,
                        "chain": chain,
                        "name": item.get("name", ""),
                        "symbol": item.get("symbol", ""),
                        "pool_address": "",
                        "dex": f"coingecko-{categoria}",
                        "created_at": None,
                        "total_supply": None,
                        "decimals": None,
                    }

                    try:
                        self.storage.upsert_token(token)
                        all_tokens.append(token)
                    except Exception as e:
                        logger.debug(
                            f"Error guardando token CoinGecko {address[:10]}...: {e}"
                        )

                # Pausa entre categorias para respetar rate limits (30/min)
                time.sleep(2.0)

            except Exception as e:
                logger.warning(
                    f"Error obteniendo categoria '{categoria}' de CoinGecko: {e}"
                )
                continue

        logger.info(
            f"Descubrimiento CoinGecko categorias completado: "
            f"{len(all_tokens)} tokens nuevos añadidos"
        )
        return all_tokens

    # ================================================================
    # PASO 1D: DESCUBRIR TOKENS DESDE BIRDEYE
    # ================================================================

    def discover_from_birdeye(self) -> list[dict]:
        """
        Descubre memecoins usando Birdeye como fuente de descubrimiento.

        Birdeye tiene dos endpoints de descubrimiento especialmente utiles:
        1. New Listings: tokens recien creados en cada cadena
        2. Meme List: tokens categorizados como memes (exactamente lo que buscamos)

        Se consultan ambos endpoints para las 3 cadenas soportadas.
        Con Birdeye Lite (900/min), estas 6 llamadas son insignificantes.

        Returns:
            Lista de diccionarios con tokens descubiertos.
        """
        logger.info("=" * 60)
        logger.info("PASO 1D: Descubriendo tokens desde Birdeye...")
        logger.info("=" * 60)

        if not self.birdeye.is_available:
            logger.info("Birdeye no disponible, saltando paso 1D")
            return []

        all_tokens: list[dict] = []
        cadenas = list(SUPPORTED_CHAINS.keys())

        # --- 1. New Listings: tokens recien creados en cada cadena ---
        for chain in cadenas:
            try:
                nuevos = self.birdeye.get_new_listings(chain=chain, limit=50)
                if nuevos:
                    logger.info(
                        f"Birdeye new_listings ({chain}): "
                        f"{len(nuevos)} tokens obtenidos"
                    )
                    for item in nuevos:
                        address = item.get("address", "")
                        if not address:
                            continue

                        token = {
                            "token_id": address,
                            "chain": chain,
                            "name": item.get("name", "")[:100],
                            "symbol": item.get("symbol", ""),
                            "pool_address": "",
                            "dex": "birdeye-new-listing",
                            "created_at": item.get("listed_at"),
                            "total_supply": None,
                            "decimals": None,
                        }

                        try:
                            self.storage.upsert_token(token)
                            all_tokens.append(token)
                        except Exception as e:
                            logger.debug(
                                f"Error guardando token Birdeye new_listing "
                                f"{address[:10]}...: {e}"
                            )

                else:
                    logger.debug(f"Birdeye new_listings ({chain}): sin resultados")

            except Exception as e:
                logger.warning(
                    f"Error obteniendo new_listings Birdeye ({chain}): {e}"
                )

        # --- 2. Meme List: tokens categorizados como memes ---
        for chain in cadenas:
            try:
                memes = self.birdeye.get_meme_list(chain=chain, limit=50)
                if memes:
                    logger.info(
                        f"Birdeye meme_list ({chain}): "
                        f"{len(memes)} tokens obtenidos"
                    )
                    for item in memes:
                        address = item.get("address", "")
                        if not address:
                            continue

                        token = {
                            "token_id": address,
                            "chain": chain,
                            "name": item.get("name", "")[:100],
                            "symbol": item.get("symbol", ""),
                            "pool_address": "",
                            "dex": "birdeye-meme-list",
                            "created_at": None,
                            "total_supply": None,
                            "decimals": None,
                        }

                        try:
                            self.storage.upsert_token(token)
                            all_tokens.append(token)
                        except Exception as e:
                            logger.debug(
                                f"Error guardando token Birdeye meme_list "
                                f"{address[:10]}...: {e}"
                            )

                else:
                    logger.debug(f"Birdeye meme_list ({chain}): sin resultados")

            except Exception as e:
                logger.warning(
                    f"Error obteniendo meme_list Birdeye ({chain}): {e}"
                )

        logger.info(
            f"Descubrimiento Birdeye completado: "
            f"{len(all_tokens)} tokens nuevos añadidos"
        )
        return all_tokens

    # ================================================================
    # PASO 2: ENRIQUECER CON DEXSCREENER
    # ================================================================

    def enrich_with_dexscreener(self, tokens: list[dict]) -> None:
        """
        Enriquece los tokens con datos de DexScreener.

        DexScreener proporciona datos adicionales que GeckoTerminal no tiene,
        como conteos de buyers/sellers en multiples ventanas de tiempo,
        cambios de precio detallados, y datos de boost (promocion).

        Los datos se guardan como pool_snapshots en la base de datos.

        Args:
            tokens: Lista de tokens descubiertos (output de discover_new_pools).
                Cada token debe tener al menos 'token_id' y 'chain'.

        Ejemplo:
            >>> tokens = collector.discover_new_pools()
            >>> collector.enrich_with_dexscreener(tokens)
        """
        logger.info("=" * 60)
        logger.info("PASO 2: Enriqueciendo con datos de DexScreener...")
        logger.info("=" * 60)

        if not tokens:
            logger.info("No hay tokens para enriquecer, saltando paso 2")
            return

        # Timestamp actual en formato ISO para el snapshot
        snapshot_time = datetime.now(timezone.utc).isoformat()

        # Contadores para resumen final
        exitos = 0
        errores = 0

        # Iterar con barra de progreso (tqdm)
        for token in tqdm(tokens, desc="DexScreener", unit="token"):
            try:
                # Obtener el ID de cadena que usa DexScreener
                chain = token.get("chain", "")
                chain_config = SUPPORTED_CHAINS.get(chain, {})
                dex_chain_id = chain_config.get("dexscreener_id", chain)

                # Obtener la direccion del token
                token_id = token.get("token_id", "")
                if not token_id:
                    continue

                # Llamar a DexScreener para obtener pares de trading
                # La API devuelve una lista de pares donde este token participa
                pair_data = self.dex.get_token_pairs(dex_chain_id, token_id)

                if not pair_data:
                    logger.debug(
                        f"Sin datos DexScreener para {token_id[:10]}..."
                    )
                    errores += 1
                    time.sleep(0.1)
                    continue

                # Tomar el primer par (el de mayor liquidez normalmente)
                # DexScreener ordena por liquidez descendente
                pair = pair_data[0] if isinstance(pair_data, list) else pair_data

                # El dexscreener_client ya parsea los datos a formato plano
                # con keys como: price_usd, volume_24h, txns_24h_buys, etc.
                buyers = safe_int(pair.get("txns_24h_buys"))
                sellers = safe_int(pair.get("txns_24h_sells"))

                # Construir el snapshot con todos los datos disponibles
                snapshot = {
                    "token_id": token_id,
                    "chain": chain,
                    "snapshot_time": snapshot_time,
                    "price_usd": safe_float(pair.get("price_usd")),
                    "volume_24h": safe_float(pair.get("volume_24h")),
                    "liquidity_usd": safe_float(pair.get("liquidity_usd")),
                    "market_cap": safe_float(pair.get("market_cap")),
                    "fdv": safe_float(pair.get("fdv")),
                    # Buyers y sellers en 24h
                    "buyers_24h": buyers,
                    "sellers_24h": sellers,
                    # Makers = buyers + sellers unicos
                    "makers_24h": buyers + sellers,
                    "source": "dexscreener",
                }

                # Guardar el snapshot en la base de datos
                self.storage.insert_pool_snapshot(snapshot)
                exitos += 1

            except Exception as e:
                # Si un token individual falla, seguir con el siguiente
                token_id = token.get("token_id", "desconocido")
                logger.warning(
                    f"Error enriqueciendo token {token_id[:10]}...: {e}"
                )
                errores += 1

            # Pausa breve entre tokens (respetar rate limits)
            time.sleep(0.2)

        # Resumen del paso
        logger.info(
            f"Enriquecimiento DexScreener completado: "
            f"{exitos} exitos, {errores} errores"
        )

    # ================================================================
    # PASO 3: RECOPILAR OHLCV
    # ================================================================

    def _fetch_ohlcv_birdeye(
        self, token_id: str, chain: str, limit: int = 30,
    ) -> list[dict]:
        """
        Obtiene OHLCV via Birdeye para cualquier chain soportada.

        Birdeye tiene 900 calls/min (Lite) vs GeckoTerminal 30/min,
        por lo que es preferible usarlo siempre que este disponible.
        Soporta Solana, Ethereum y Base via el header x-chain.

        Args:
            token_id: Direccion del contrato del token.
            chain: Cadena ("solana", "ethereum", "base").
            limit: Dias de velas a pedir (se calcula time_from/time_to).

        Returns:
            Lista de dicts OHLCV en formato Birdeye (timestamp ISO,
            open, high, low, close, volume), o lista vacia si falla.
        """
        if not self.birdeye.is_available:
            return []

        now_unix = int(datetime.now(timezone.utc).timestamp())
        time_from = now_unix - (limit * 86400)

        return self.birdeye.get_token_ohlcv(
            address=token_id,
            time_from=time_from,
            time_to=now_unix,
            timeframe="1D",
            chain=chain,
        )

    def _birdeye_velas_to_rows(
        self, velas: list[dict], token_id: str, chain: str,
        pool_address: str, timeframe: str,
    ) -> list[dict]:
        """
        Convierte velas Birdeye al formato de storage.insert_ohlcv_batch().

        Birdeye devuelve velas con timestamp ISO y keys open/high/low/close/volume.
        Este helper las convierte al formato exacto que espera la base de datos.

        Args:
            velas: Lista de dicts Birdeye (output de get_token_ohlcv).
            token_id: ID del token.
            chain: Cadena del token.
            pool_address: Direccion del pool (puede ser token_id si no hay pool).
            timeframe: Timeframe para la DB ("day", "hour").

        Returns:
            Lista de dicts listos para insert_ohlcv_batch().
        """
        rows = []
        for vela in velas:
            rows.append({
                "token_id": token_id,
                "chain": chain,
                "pool_address": pool_address or token_id,
                "timeframe": timeframe,
                "timestamp": vela.get("timestamp", ""),
                "open": safe_float(vela.get("open")),
                "high": safe_float(vela.get("high")),
                "low": safe_float(vela.get("low")),
                "close": safe_float(vela.get("close")),
                "volume": safe_float(vela.get("volume")),
            })
        return rows

    def collect_ohlcv(
        self,
        tokens: list[dict],
        timeframe: str = "day",
        limit: int = 30,
    ) -> None:
        """
        Recopila datos OHLCV (velas de precio) para cada token.

        OHLCV = Open, High, Low, Close, Volume. Son los datos basicos
        para graficos de velas japonesas e indicadores tecnicos como
        RSI, MACD, medias moviles, etc.

        Estrategia de fuentes:
        - Si Birdeye esta disponible, se usa como fuente primaria para
          TODAS las cadenas (Solana, Ethereum, Base). Birdeye tiene
          900 calls/min vs GeckoTerminal 30/min.
        - Si Birdeye falla o no esta disponible, se usa GeckoTerminal
          como fallback (requiere pool_address).
        - Tokens sin pool_address y sin Birdeye se saltan.

        Args:
            tokens: Lista de tokens (output de discover_new_pools).
            timeframe: Periodo de cada vela. Opciones:
                - "day" (una vela por dia, ideal para vista general)
                - "hour" (una vela por hora, mas detalle)
                - "minute" (una vela por minuto, microestructura)
            limit: Numero maximo de velas a obtener por token.
                30 dias es suficiente para nuestro LABEL_WINDOW_DAYS.

        Ejemplo:
            >>> tokens = collector.discover_new_pools()
            >>> collector.collect_ohlcv(tokens, timeframe="day", limit=30)
        """
        logger.info("=" * 60)
        logger.info(f"PASO 3: Recopilando OHLCV ({timeframe}, {limit} velas)...")
        if self.birdeye.is_available:
            logger.info("Fuente primaria: Birdeye (900/min), fallback: GeckoTerminal")
        else:
            logger.info("Fuente: GeckoTerminal (Birdeye no disponible)")
        logger.info("=" * 60)

        if not tokens:
            logger.info("No hay tokens para OHLCV, saltando paso 3")
            return

        # Con Birdeye, podemos procesar tokens incluso sin pool_address
        # (Birdeye usa token address directamente, no necesita pool)
        if self.birdeye.is_available:
            tokens_procesables = [t for t in tokens if t.get("token_id")]
        else:
            # Sin Birdeye, solo tokens con pool_address (requerido por GeckoTerminal)
            tokens_procesables = [t for t in tokens if t.get("pool_address")]

        if not tokens_procesables:
            logger.info(
                "Ningun token procesable para OHLCV, saltando"
            )
            return

        logger.info(
            f"Procesando OHLCV para {len(tokens_procesables)} tokens "
            f"(de {len(tokens)} total)"
        )

        # Contadores para resumen
        exitos = 0
        exitos_birdeye = 0
        exitos_gecko = 0
        errores = 0
        total_velas = 0

        # Iterar con barra de progreso
        for token in tqdm(tokens_procesables, desc="OHLCV", unit="token"):
            try:
                chain = token.get("chain", "")
                chain_config = SUPPORTED_CHAINS.get(chain, {})
                gecko_chain_id = chain_config.get("geckoterminal_id", chain)
                pool_address = token.get("pool_address", "")
                token_id = token.get("token_id", "")

                ohlcv_rows = []

                # --- Intento 1: Birdeye (primario, mas rapido) ---
                if self.birdeye.is_available:
                    birdeye_velas = self._fetch_ohlcv_birdeye(
                        token_id=token_id, chain=chain, limit=limit,
                    )
                    if birdeye_velas:
                        ohlcv_rows = self._birdeye_velas_to_rows(
                            birdeye_velas, token_id, chain,
                            pool_address, timeframe,
                        )
                        exitos_birdeye += 1

                # --- Intento 2: GeckoTerminal (fallback) ---
                if not ohlcv_rows and pool_address:
                    velas = self.gecko.get_pool_ohlcv(
                        chain=gecko_chain_id,
                        pool_address=pool_address,
                        timeframe=timeframe,
                        limit=limit,
                    )

                    if velas:
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
                                "timeframe": timeframe,
                                "timestamp": ts_iso,
                                "open": safe_float(vela.get("open")),
                                "high": safe_float(vela.get("high")),
                                "low": safe_float(vela.get("low")),
                                "close": safe_float(vela.get("close")),
                                "volume": safe_float(vela.get("volume")),
                            })
                        exitos_gecko += 1

                if not ohlcv_rows:
                    logger.debug(f"Sin OHLCV para {token_id[:10]}...")
                    errores += 1
                    time.sleep(0.1)
                    continue

                # Guardar todas las velas de este token en un solo batch
                self.storage.insert_ohlcv_batch(ohlcv_rows)
                exitos += 1
                total_velas += len(ohlcv_rows)

            except Exception as e:
                token_id = token.get("token_id", "desconocido")
                logger.warning(
                    f"Error recopilando OHLCV para {token_id[:10]}...: {e}"
                )
                errores += 1

            # Pausa entre tokens: Birdeye es rapido (900/min = 0.07s)
            # pero mantenemos 0.15s para seguridad. Si usamos GeckoTerminal
            # fallback, BaseAPIClient ya tiene rate limiting interno.
            time.sleep(0.15 if self.birdeye.is_available else 0.5)

        # Resumen del paso
        logger.info(
            f"OHLCV completado: {exitos} tokens, "
            f"{total_velas} velas totales, {errores} errores"
        )
        if self.birdeye.is_available:
            logger.info(
                f"  Fuentes: Birdeye={exitos_birdeye}, "
                f"GeckoTerminal fallback={exitos_gecko}"
            )

    # ================================================================
    # PASO 4: RECOPILAR HOLDERS (Solana via Helius + ETH/Base via Birdeye)
    # ================================================================

    def _save_birdeye_holders(
        self, token_id: str, chain: str, holders: list[dict],
    ) -> None:
        """
        Convierte holders de Birdeye al formato de holder_snapshots y los guarda.

        Birdeye devuelve holders con keys: wallet, amount, percentage, usd_value.
        Este metodo los convierte al esquema de la tabla holder_snapshots:
        token_id, chain, snapshot_time, rank, holder_address, amount, pct_of_supply.

        Args:
            token_id: Direccion del token.
            chain: Cadena del token ("solana", "ethereum", "base").
            holders: Lista de dicts de Birdeye (output de get_token_holder).
        """
        snapshot_time = datetime.now(timezone.utc).isoformat()

        holder_rows = []
        for rank, holder in enumerate(holders[:20], start=1):
            holder_rows.append({
                "token_id": token_id,
                "chain": chain,
                "snapshot_time": snapshot_time,
                "rank": rank,
                "holder_address": holder.get("wallet", ""),
                "amount": safe_float(holder.get("amount")),
                "pct_of_supply": safe_float(holder.get("percentage")),
            })

        if holder_rows:
            self.storage.insert_holder_snapshot(holder_rows)

    def collect_holders(self, tokens: list[dict]) -> None:
        """
        Recopila los top 20 holders para tokens de todas las cadenas.

        Los holders son las wallets que poseen mas tokens. Analizar la
        concentracion de holders es clave para detectar rugs:
        - Si 1 wallet tiene >50% del supply, riesgo de rug pull
        - Si top 10 holders tienen >80%, concentracion peligrosa

        Fuentes de datos:
        - Solana: Helius RPC (primario) + Birdeye (fallback)
        - Ethereum/Base: Birdeye (unica fuente disponible)

        Args:
            tokens: Lista de tokens (output de discover_new_pools).

        Ejemplo:
            >>> tokens = collector.discover_new_pools()
            >>> collector.collect_holders(tokens)
        """
        logger.info("=" * 60)
        logger.info("PASO 4: Recopilando holders (Solana + ETH/Base)...")
        logger.info("=" * 60)

        if not tokens:
            logger.info("No hay tokens para holders, saltando paso 4")
            return

        # --- 4A: Holders de Solana via Helius RPC ---
        solana_tokens = [
            t for t in tokens if t.get("chain") == "solana"
        ]

        # Timestamp actual para el snapshot
        snapshot_time = datetime.now(timezone.utc).isoformat()

        # Contadores
        exitos_helius = 0
        exitos_birdeye = 0
        errores = 0

        if solana_tokens:
            logger.info(
                f"4A: Procesando holders para {len(solana_tokens)} tokens "
                f"de Solana via Helius RPC"
            )

            for token in tqdm(solana_tokens, desc="Holders Solana", unit="token"):
                try:
                    token_id = token.get("token_id", "")
                    if not token_id:
                        continue

                    # Obtener total supply para calcular porcentaje
                    total_supply = safe_float(token.get("total_supply"))

                    # Llamar a Solana RPC (Helius) para obtener top holders
                    holders_data = self.solana_rpc.get_token_largest_accounts(
                        token_id
                    )

                    if holders_data:
                        # Construir lista de holder snapshots
                        holder_rows = []
                        for rank, holder in enumerate(holders_data[:20], start=1):
                            amount = safe_float(holder.get("amount"))
                            if total_supply and total_supply > 0:
                                pct = (amount / total_supply) * 100
                            else:
                                pct = 0.0

                            holder_rows.append({
                                "token_id": token_id,
                                "chain": "solana",
                                "snapshot_time": snapshot_time,
                                "rank": rank,
                                "holder_address": holder.get("address", ""),
                                "amount": amount,
                                "pct_of_supply": pct,
                            })

                        if holder_rows:
                            self.storage.insert_holder_snapshot(holder_rows)
                            exitos_helius += 1
                            continue  # Exito con Helius, no necesitamos Birdeye

                    # Fallback: Birdeye para Solana si Helius falla
                    if self.birdeye.is_available:
                        holders_be = self.birdeye.get_token_holder(
                            token_id, chain="solana", limit=20,
                        )
                        if holders_be:
                            self._save_birdeye_holders(token_id, "solana", holders_be)
                            exitos_birdeye += 1
                            time.sleep(0.07)
                            continue

                    logger.debug(f"Sin holders para {token_id[:10]}...")
                    errores += 1

                except Exception as e:
                    token_id = token.get("token_id", "desconocido")
                    logger.warning(
                        f"Error recopilando holders para {token_id[:10]}...: {e}"
                    )
                    errores += 1

                # Pausa breve entre tokens
                time.sleep(0.3)

        # --- 4B: Holders de ETH/Base via Birdeye ---
        if self.birdeye.is_available:
            eth_base_tokens = [
                t for t in tokens
                if t.get("chain") in ("ethereum", "base")
            ]

            if eth_base_tokens:
                logger.info(
                    f"4B: Procesando holders para {len(eth_base_tokens)} tokens "
                    f"de ETH/Base via Birdeye"
                )

                for token in tqdm(eth_base_tokens, desc="Holders ETH/Base", unit="token"):
                    try:
                        token_id = token.get("token_id", "")
                        chain = token.get("chain", "")
                        if not token_id:
                            continue

                        holders = self.birdeye.get_token_holder(
                            token_id, chain=chain, limit=20,
                        )
                        if holders:
                            self._save_birdeye_holders(token_id, chain, holders)
                            exitos_birdeye += 1
                        else:
                            errores += 1

                    except Exception as e:
                        logger.debug(
                            f"Birdeye holder error {token_id[:10]}...: {e}"
                        )
                        errores += 1

                    # Pausa entre llamadas Birdeye (15 rps = 0.07s)
                    time.sleep(0.07)

        # Resumen del paso
        logger.info(
            f"Holders completado: Helius={exitos_helius}, "
            f"Birdeye={exitos_birdeye}, errores={errores}"
        )

    # ================================================================
    # PASO 5: VERIFICAR CONTRATOS
    # ================================================================

    def collect_contract_info(self, tokens: list[dict]) -> None:
        """
        Verifica informacion de contratos para cada token.

        Dependiendo de la cadena, se hacen diferentes verificaciones:

        - Ethereum/Base: Se usa Etherscan/Basescan para verificar si el
          contrato tiene codigo fuente verificado y si el ownership esta
          renunciado (renounced). Un contrato no verificado es sospechoso.

        - Solana: Se usa Solana RPC para verificar si la mint authority
          esta deshabilitada. Si la mint authority esta activa, el creador
          puede crear mas tokens y diluir a los holders (rug pull).

        Args:
            tokens: Lista de tokens (output de discover_new_pools).

        Ejemplo:
            >>> tokens = collector.discover_new_pools()
            >>> collector.collect_contract_info(tokens)
        """
        logger.info("=" * 60)
        logger.info("PASO 5: Verificando contratos...")
        logger.info("=" * 60)

        if not tokens:
            logger.info("No hay tokens para verificar, saltando paso 5")
            return

        # Contadores
        exitos = 0
        errores = 0

        # Iterar con barra de progreso
        for token in tqdm(tokens, desc="Contratos", unit="token"):
            try:
                token_id = token.get("token_id", "")
                chain = token.get("chain", "")

                if not token_id or not chain:
                    continue

                # Diccionario base para informacion del contrato
                contract_info = {
                    "token_id": token_id,
                    "chain": chain,
                    "is_verified": None,
                    "is_renounced": None,
                    "has_mint_authority": None,
                    "deploy_timestamp": None,
                }

                if chain in ("ethereum", "base"):
                    # --- Verificacion via Etherscan V2 ---
                    ethclient = self._etherscan_for(chain)
                    is_verified = ethclient.is_contract_verified(token_id)
                    contract_info["is_verified"] = is_verified

                    # Intentar obtener source code para mas detalles
                    source = ethclient.get_contract_source(token_id)
                    if source:
                        # Limitacion: la API de Etherscan no expone si el ownership
                        # fue renunciado. is_proxy=False NO implica renounced.
                        # Dejamos False (desconocido) hasta tener una fuente fiable.
                        contract_info["is_renounced"] = False
                        contract_info["deploy_timestamp"] = source.get(
                            "deploy_timestamp"
                        )

                elif chain == "solana":
                    # --- Verificacion via Solana RPC ---
                    # En Solana, usamos get_token_supply para verificar el token
                    supply_info = self.solana_rpc.get_token_supply(token_id)

                    if supply_info:
                        # Si tiene supply, el token existe y es valido
                        contract_info["is_verified"] = True
                        # No podemos saber mint authority sin Helius
                        # pero marcamos como verificado

                # Guardar en la base de datos
                self.storage.upsert_contract_info(contract_info)
                exitos += 1

            except Exception as e:
                token_id = token.get("token_id", "desconocido")
                logger.warning(
                    f"Error verificando contrato de {token_id[:10]}...: {e}"
                )
                errores += 1

            # Pausa breve entre tokens
            time.sleep(0.5)

        # Resumen del paso
        logger.info(
            f"Verificacion de contratos completada: "
            f"{exitos} verificados, {errores} errores"
        )

    # ================================================================
    # PASO 5B: SEGURIDAD VIA BIRDEYE (todas las cadenas)
    # ================================================================

    def collect_birdeye_security(self, tokens: list[dict]) -> None:
        """
        Obtiene datos de seguridad via Birdeye para tokens sin contract_info.

        Birdeye get_token_security() funciona para Solana, Ethereum y Base.
        Complementa Etherscan (solo ETH/Base) y Solana RPC con datos como:
        - ownerAddress (si ownership esta renunciado)
        - mintAuthority / freezeAuthority (Solana)
        - top10HolderPercent (concentracion de holders)
        - mutableMetadata (si metadatos pueden cambiar)

        Solo se procesan tokens que NO tienen contract_info en la DB para
        evitar llamadas duplicadas.

        Args:
            tokens: Lista de tokens descubiertos en esta sesion.
        """
        logger.info("=" * 60)
        logger.info("PASO 5B: Seguridad via Birdeye (todas las cadenas)...")
        logger.info("=" * 60)

        if not self.birdeye.is_available:
            logger.info("Birdeye no disponible, saltando paso 5B")
            return

        if not tokens:
            logger.info("No hay tokens para seguridad, saltando paso 5B")
            return

        # Buscar tokens sin contract_info en la DB
        # Usamos una query para obtener tokens que no tienen registro
        try:
            existing_df = self.storage.query("""
                SELECT token_id FROM contract_info
            """)
            existing_ids = set(existing_df["token_id"].tolist()) if not existing_df.empty else set()
        except Exception:
            existing_ids = set()

        # Filtrar tokens sin contract_info
        tokens_sin_info = [
            t for t in tokens
            if t.get("token_id") and t.get("token_id") not in existing_ids
        ]

        if not tokens_sin_info:
            logger.info("Todos los tokens ya tienen contract_info, saltando paso 5B")
            return

        logger.info(
            f"Procesando seguridad Birdeye para {len(tokens_sin_info)} tokens "
            f"sin contract_info"
        )

        exitos = 0
        errores = 0

        for token in tqdm(tokens_sin_info, desc="Security Birdeye", unit="token"):
            try:
                token_id = token.get("token_id", "")
                chain = token.get("chain", "")
                if not token_id or not chain:
                    continue

                security = self.birdeye.get_token_security(token_id, chain=chain)
                if not security:
                    errores += 1
                    time.sleep(0.07)
                    continue

                # Mapear datos de Birdeye al esquema de contract_info
                owner_addr = security.get("owner_address")
                mint_auth = security.get("mint_authority")
                freeze_auth = security.get("freeze_authority")

                # Determinar si ownership esta renunciado:
                # - Si owner_address es None o "11111111..." (Solana null address)
                #   o "0x0000..." (EVM null address), se considera renunciado
                is_renounced = False
                if owner_addr is None:
                    is_renounced = True
                elif owner_addr in (
                    "11111111111111111111111111111111",
                    "0x0000000000000000000000000000000000000000",
                    "",
                ):
                    is_renounced = True

                # Mint authority activa = riesgo de rug
                has_mint = bool(mint_auth) if mint_auth else False

                contract_info = {
                    "token_id": token_id,
                    "chain": chain,
                    "is_verified": security.get("is_true_token"),
                    "is_renounced": is_renounced,
                    "has_mint_authority": has_mint,
                    "deploy_timestamp": security.get("creation_time"),
                }

                self.storage.upsert_contract_info(contract_info)
                exitos += 1

            except Exception as e:
                logger.debug(f"Birdeye security error {token_id[:10]}...: {e}")
                errores += 1

            # Pausa entre llamadas Birdeye (15 rps)
            time.sleep(0.07)

        logger.info(
            f"Seguridad Birdeye completada: {exitos} exitos, {errores} errores"
        )

    # ================================================================
    # PASO 5C: FECHA DE CREACION VIA BIRDEYE (tokens sin created_at)
    # ================================================================

    def collect_birdeye_creation_dates(self, tokens: list[dict] = None) -> None:
        """
        Rellena la fecha de creacion para tokens que no la tienen.

        Muchos tokens (353+) tienen created_at NULL o un valor fallback
        de 180 dias atras. Birdeye get_token_creation_info() devuelve la
        fecha real de creacion del token en cualquier cadena.

        Si no se pasan tokens, consulta la DB para encontrar todos los
        tokens sin created_at.

        Args:
            tokens: Lista de tokens a procesar. Si es None, consulta
                la DB para encontrar tokens sin created_at.
        """
        logger.info("=" * 60)
        logger.info("PASO 5C: Fechas de creacion via Birdeye...")
        logger.info("=" * 60)

        if not self.birdeye.is_available:
            logger.info("Birdeye no disponible, saltando paso 5C")
            return

        # Si no se pasan tokens, buscar en la DB los que no tienen created_at
        if tokens is None:
            try:
                missing_df = self.storage.query("""
                    SELECT token_id, chain
                    FROM tokens
                    WHERE created_at IS NULL
                    LIMIT 1000
                """)
                if missing_df.empty:
                    logger.info("Todos los tokens tienen created_at, saltando paso 5C")
                    return
                tokens_to_process = missing_df.to_dict("records")
            except Exception as e:
                logger.warning(f"Error consultando tokens sin created_at: {e}")
                return
        else:
            # Filtrar tokens sin created_at consultando la DB (el dict local
            # puede no tener created_at aunque la DB si lo tenga)
            try:
                has_dates_df = self.storage.query("""
                    SELECT token_id FROM tokens
                    WHERE created_at IS NOT NULL
                """)
                has_dates = set(has_dates_df["token_id"].tolist()) if not has_dates_df.empty else set()
            except Exception:
                has_dates = set()
            tokens_to_process = [
                t for t in tokens
                if t.get("token_id") and t["token_id"] not in has_dates
            ]

        if not tokens_to_process:
            logger.info("No hay tokens sin created_at, saltando paso 5C")
            return

        logger.info(
            f"Procesando fechas de creacion para {len(tokens_to_process)} tokens"
        )

        exitos = 0
        errores = 0

        for token in tqdm(tokens_to_process, desc="Creation dates", unit="token"):
            try:
                token_id = token.get("token_id", "")
                chain = token.get("chain", "")
                if not token_id or not chain:
                    continue

                creation_info = self.birdeye.get_token_creation_info(
                    token_id, chain=chain,
                )
                if not creation_info or not creation_info.get("created_at_iso"):
                    errores += 1
                    time.sleep(0.07)
                    continue

                # Actualizar el token con la fecha de creacion real
                self.storage.upsert_token({
                    "token_id": token_id,
                    "chain": chain,
                    "created_at": creation_info["created_at_iso"],
                })
                exitos += 1

            except Exception as e:
                logger.debug(
                    f"Birdeye creation_info error {token_id[:10]}...: {e}"
                )
                errores += 1

            # Pausa entre llamadas Birdeye (15 rps)
            time.sleep(0.07)

        logger.info(
            f"Fechas de creacion completadas: {exitos} actualizados, "
            f"{errores} errores"
        )

    # ================================================================
    # PASO 5D: TRADE DATA VIA BIRDEYE (buys/sells/traders unicos)
    # ================================================================

    def collect_birdeye_trade_data(self, tokens: list[dict]) -> None:
        """
        Obtiene datos de trading via Birdeye para todos los tokens.

        get_token_trade_data() proporciona buys, sells, traders unicos,
        volumen buy/sell en multiples ventanas temporales (30m a 24h).
        Mejor granularidad que DexScreener para features sociales/momentum.

        Los datos se guardan como pool_snapshots con source="birdeye-trade".

        Args:
            tokens: Lista de tokens a procesar.
        """
        logger.info("=" * 60)
        logger.info("PASO 5D: Trade data via Birdeye...")
        logger.info("=" * 60)

        if not self.birdeye.is_available:
            logger.info("Birdeye no disponible, saltando paso 5D")
            return

        if not tokens:
            logger.info("No hay tokens para trade data, saltando paso 5D")
            return

        # Saltar tokens que ya tienen snapshot birdeye-trade hoy
        try:
            existing_trade_df = self.storage.query("""
                SELECT DISTINCT token_id FROM pool_snapshots
                WHERE source = 'birdeye-trade'
                  AND snapshot_time::date = CURRENT_DATE
            """)
            existing_trade = set(existing_trade_df["token_id"].tolist()) if not existing_trade_df.empty else set()
        except Exception:
            existing_trade = set()

        tokens_to_process = [t for t in tokens if t.get("token_id") and t["token_id"] not in existing_trade]
        skipped = len(tokens) - len(tokens_to_process)
        if skipped:
            logger.info(f"5D: Saltando {skipped} tokens que ya tienen trade data hoy")

        if not tokens_to_process:
            logger.info("Todos los tokens ya tienen trade data hoy, saltando paso 5D")
            return

        logger.info(
            f"Procesando trade data Birdeye para {len(tokens_to_process)} tokens"
        )

        snapshot_time = datetime.now(timezone.utc).isoformat()
        exitos = 0
        errores = 0

        for token in tqdm(tokens_to_process, desc="Trade data", unit="token"):
            try:
                token_id = token.get("token_id", "")
                chain = token.get("chain", "")
                if not token_id or not chain:
                    continue

                trade_data = self.birdeye.get_token_trade_data(
                    token_id, chain=chain,
                )
                if not trade_data:
                    errores += 1
                    time.sleep(0.07)
                    continue

                # Guardar como pool_snapshot para que las features lo lean
                snapshot = {
                    "token_id": token_id,
                    "chain": chain,
                    "snapshot_time": snapshot_time,
                    "price_usd": None,  # No disponible en trade data
                    "volume_24h": (
                        safe_float(trade_data.get("volume_buy_24h", 0))
                        + safe_float(trade_data.get("volume_sell_24h", 0))
                    ),
                    "liquidity_usd": None,
                    "market_cap": None,
                    "fdv": None,
                    "buyers_24h": trade_data.get("buy_24h"),
                    "sellers_24h": trade_data.get("sell_24h"),
                    "makers_24h": (
                        safe_int(trade_data.get("buy_24h") or 0)
                        + safe_int(trade_data.get("sell_24h") or 0)
                    ),
                    "tx_count_24h": trade_data.get("trade_24h"),
                    "source": "birdeye-trade",
                }

                self.storage.insert_pool_snapshot(snapshot)
                exitos += 1

            except Exception as e:
                logger.debug(
                    f"Birdeye trade_data error {token_id[:10]}...: {e}"
                )
                errores += 1

            # Pausa entre llamadas Birdeye (15 rps)
            time.sleep(0.07)

        logger.info(
            f"Trade data completado: {exitos} exitos, {errores} errores"
        )

    # ================================================================
    # PASO 5E: TOKEN OVERVIEW VIA BIRDEYE (datos completos en 1 call)
    # ================================================================

    def collect_birdeye_token_overview(self, tokens: list[dict]) -> None:
        """
        Obtiene datos completos de tokens via Birdeye token_overview.

        Una sola llamada devuelve: precio, volumen, liquidez, mcap,
        holders count, buys/sells, unique wallets, supply, price changes.
        Complementa/reemplaza DexScreener para datos de mercado.

        Se guardan como pool_snapshot con source="birdeye-overview".
        Ademas, actualiza datos basicos del token (total_supply, decimals).

        Args:
            tokens: Lista de tokens a procesar.
        """
        logger.info("=" * 60)
        logger.info("PASO 5E: Token overview via Birdeye...")
        logger.info("=" * 60)

        if not self.birdeye.is_available:
            logger.info("Birdeye no disponible, saltando paso 5E")
            return

        if not tokens:
            logger.info("No hay tokens para overview, saltando paso 5E")
            return

        # Saltar tokens que ya tienen snapshot birdeye-overview hoy
        try:
            existing_overview_df = self.storage.query("""
                SELECT DISTINCT token_id FROM pool_snapshots
                WHERE source = 'birdeye-overview'
                  AND snapshot_time::date = CURRENT_DATE
            """)
            existing_overview = set(existing_overview_df["token_id"].tolist()) if not existing_overview_df.empty else set()
        except Exception:
            existing_overview = set()

        tokens_to_process = [t for t in tokens if t.get("token_id") and t["token_id"] not in existing_overview]
        skipped = len(tokens) - len(tokens_to_process)
        if skipped:
            logger.info(f"5E: Saltando {skipped} tokens que ya tienen overview hoy")

        if not tokens_to_process:
            logger.info("Todos los tokens ya tienen overview hoy, saltando paso 5E")
            return

        logger.info(
            f"Procesando token overview Birdeye para {len(tokens_to_process)} tokens"
        )

        snapshot_time = datetime.now(timezone.utc).isoformat()
        exitos = 0
        errores = 0

        for token in tqdm(tokens_to_process, desc="Token overview", unit="token"):
            try:
                token_id = token.get("token_id", "")
                chain = token.get("chain", "")
                if not token_id or not chain:
                    continue

                overview = self.birdeye.get_token_overview(
                    token_id, chain=chain,
                )
                if not overview:
                    errores += 1
                    time.sleep(0.07)
                    continue

                # Guardar snapshot con datos de mercado completos
                snapshot = {
                    "token_id": token_id,
                    "chain": chain,
                    "snapshot_time": snapshot_time,
                    "price_usd": overview.get("price"),
                    "volume_24h": overview.get("volume_24h"),
                    "liquidity_usd": overview.get("liquidity"),
                    "market_cap": overview.get("mc"),
                    "fdv": None,  # No disponible en overview
                    "buyers_24h": overview.get("buy_24h"),
                    "sellers_24h": overview.get("sell_24h"),
                    "makers_24h": overview.get("unique_wallet_24h"),
                    "tx_count_24h": overview.get("trade_24h"),
                    "source": "birdeye-overview",
                }
                self.storage.insert_pool_snapshot(snapshot)

                # Actualizar datos basicos del token si tenemos nueva info
                update_data = {
                    "token_id": token_id,
                    "chain": chain,
                }
                if overview.get("supply"):
                    update_data["total_supply"] = overview["supply"]
                if overview.get("decimals") is not None:
                    update_data["decimals"] = overview["decimals"]
                if overview.get("name") and not token.get("name"):
                    update_data["name"] = overview["name"]
                if overview.get("symbol") and not token.get("symbol"):
                    update_data["symbol"] = overview["symbol"]

                if len(update_data) > 2:  # Mas que solo token_id y chain
                    self.storage.upsert_token(update_data)

                exitos += 1

            except Exception as e:
                logger.debug(
                    f"Birdeye overview error {token_id[:10]}...: {e}"
                )
                errores += 1

            # Pausa entre llamadas Birdeye (15 rps)
            time.sleep(0.07)

        logger.info(
            f"Token overview completado: {exitos} exitos, {errores} errores"
        )

    # ================================================================
    # PASO 5F: BIRDEYE ENRICHMENT PARA TOKENS EXISTENTES SIN DATOS
    # ================================================================

    def enrich_existing_tokens_birdeye(self, max_tokens: int = 200) -> dict:
        """
        Enriquece tokens existentes en la DB que no tienen holder data
        o contract_info, usando Birdeye.

        Esto cubre los ~2,665 tokens ETH+Base sin holders y tokens sin
        contract_info que ya estaban en la DB antes de esta sesion.

        Solo se ejecuta si Birdeye esta disponible.

        Args:
            max_tokens: Maximo de tokens a procesar por tipo (holders, security).

        Returns:
            Dict con estadisticas: holders_added, security_added, dates_added.
        """
        logger.info("=" * 60)
        logger.info("PASO 7: Enriquecimiento Birdeye de tokens existentes...")
        logger.info("=" * 60)

        if not self.birdeye.is_available:
            logger.info("Birdeye no disponible, saltando paso 7")
            return {"holders_added": 0, "security_added": 0, "dates_added": 0}

        stats = {"holders_added": 0, "security_added": 0, "dates_added": 0}

        # --- 7A: Holders para ETH/Base tokens sin holder_snapshots ---
        try:
            missing_holders_df = self.storage.query("""
                SELECT t.token_id, t.chain
                FROM tokens t
                LEFT JOIN holder_snapshots h ON t.token_id = h.token_id
                WHERE h.token_id IS NULL
                  AND t.chain IN ('ethereum', 'base')
                LIMIT ?
            """, (max_tokens,))

            if not missing_holders_df.empty:
                logger.info(
                    f"7A: {len(missing_holders_df)} tokens ETH/Base sin holders"
                )
                exitos = 0
                for _, row in tqdm(
                    missing_holders_df.iterrows(),
                    total=len(missing_holders_df),
                    desc="Holders existentes",
                    unit="token",
                ):
                    try:
                        holders = self.birdeye.get_token_holder(
                            row["token_id"], chain=row["chain"], limit=20,
                        )
                        if holders:
                            self._save_birdeye_holders(
                                row["token_id"], row["chain"], holders,
                            )
                            exitos += 1
                    except Exception as e:
                        logger.debug(
                            f"Birdeye holder error {row['token_id'][:10]}...: {e}"
                        )
                    time.sleep(0.07)
                stats["holders_added"] = exitos
                logger.info(f"7A: {exitos} tokens con holders nuevos")
            else:
                logger.info("7A: Todos los tokens ETH/Base ya tienen holders")
        except Exception as e:
            logger.warning(f"Error en paso 7A: {e}")

        # --- 7B: Security para tokens sin contract_info ---
        try:
            missing_security_df = self.storage.query("""
                SELECT t.token_id, t.chain
                FROM tokens t
                LEFT JOIN contract_info c ON t.token_id = c.token_id
                WHERE c.token_id IS NULL
                LIMIT ?
            """, (max_tokens,))

            if not missing_security_df.empty:
                logger.info(
                    f"7B: {len(missing_security_df)} tokens sin contract_info"
                )
                exitos = 0
                for _, row in tqdm(
                    missing_security_df.iterrows(),
                    total=len(missing_security_df),
                    desc="Security existentes",
                    unit="token",
                ):
                    try:
                        security = self.birdeye.get_token_security(
                            row["token_id"], chain=row["chain"],
                        )
                        if security:
                            owner_addr = security.get("owner_address")
                            mint_auth = security.get("mint_authority")

                            is_renounced = False
                            if owner_addr is None:
                                is_renounced = True
                            elif owner_addr in (
                                "11111111111111111111111111111111",
                                "0x0000000000000000000000000000000000000000",
                                "",
                            ):
                                is_renounced = True

                            contract_info = {
                                "token_id": row["token_id"],
                                "chain": row["chain"],
                                "is_verified": security.get("is_true_token"),
                                "is_renounced": is_renounced,
                                "has_mint_authority": bool(mint_auth) if mint_auth else False,
                                "deploy_timestamp": security.get("creation_time"),
                            }
                            self.storage.upsert_contract_info(contract_info)
                            exitos += 1
                    except Exception as e:
                        logger.debug(
                            f"Birdeye security error {row['token_id'][:10]}...: {e}"
                        )
                    time.sleep(0.07)
                stats["security_added"] = exitos
                logger.info(f"7B: {exitos} tokens con security nueva")
            else:
                logger.info("7B: Todos los tokens ya tienen contract_info")
        except Exception as e:
            logger.warning(f"Error en paso 7B: {e}")

        # --- 7C: Fechas de creacion para tokens sin created_at ---
        try:
            missing_dates_df = self.storage.query("""
                SELECT token_id, chain
                FROM tokens
                WHERE created_at IS NULL
                LIMIT ?
            """, (max_tokens,))

            if not missing_dates_df.empty:
                logger.info(
                    f"7C: {len(missing_dates_df)} tokens sin created_at"
                )
                exitos = 0
                for _, row in tqdm(
                    missing_dates_df.iterrows(),
                    total=len(missing_dates_df),
                    desc="Dates existentes",
                    unit="token",
                ):
                    try:
                        creation = self.birdeye.get_token_creation_info(
                            row["token_id"], chain=row["chain"],
                        )
                        if creation and creation.get("created_at_iso"):
                            self.storage.upsert_token({
                                "token_id": row["token_id"],
                                "chain": row["chain"],
                                "created_at": creation["created_at_iso"],
                            })
                            exitos += 1
                    except Exception as e:
                        logger.debug(
                            f"Birdeye creation error {row['token_id'][:10]}...: {e}"
                        )
                    time.sleep(0.07)
                stats["dates_added"] = exitos
                logger.info(f"7C: {exitos} tokens con fecha de creacion nueva")
            else:
                logger.info("7C: Todos los tokens ya tienen created_at")
        except Exception as e:
            logger.warning(f"Error en paso 7C: {e}")

        logger.info(
            f"Enriquecimiento Birdeye completado: "
            f"holders={stats['holders_added']}, "
            f"security={stats['security_added']}, "
            f"dates={stats['dates_added']}"
        )
        return stats

    # ================================================================
    # PIPELINE COMPLETO: RECOPILACION DIARIA
    # ================================================================

    def run_daily_collection(
        self, chains: Optional[list[str]] = None,
        max_tokens_ohlcv: int = 1000,
    ) -> dict:
        """
        Ejecuta el pipeline completo de recopilacion diaria.

        Llama a los pasos en orden:
            1.  Descubrir pools nuevos (GeckoTerminal, 10 paginas/cadena)
            1B. Descubrir tokens desde DexScreener (boosted, profiles, CTO)
            1C. Descubrir tokens desde categorias CoinGecko (meme-token, etc.)
            1D. Descubrir tokens desde Birdeye (new listings + meme list)
            2.  Enriquecer con DexScreener (buyers/sellers)
            3.  Obtener OHLCV historico
            4.  Obtener holders (Solana via Helius + ETH/Base via Birdeye)
            5.  Verificar contratos (Etherscan + RPC)
            5B. Seguridad via Birdeye (todas las cadenas, tokens sin info)
            5C. Fechas de creacion via Birdeye (tokens sin created_at)
            5D. Trade data via Birdeye (buys/sells/traders unicos)
            5E. Token overview via Birdeye (datos completos en 1 call)
            6.  Actualizar OHLCV de tokens existentes
            7.  Enriquecer tokens existentes via Birdeye (holders, security, dates)

        Este metodo esta diseñado para ejecutarse una vez al dia
        (ej: con un cron job o un scheduler de Python).

        Args:
            chains: Lista de cadenas a procesar. Si es None, usa todas
                las soportadas (solana, ethereum, base).
            max_tokens_ohlcv: Maximo de tokens existentes a actualizar en
                el paso 6 (OHLCV update). Default 1000. Con Birdeye (900/min),
                1000 tokens = ~3 min. En CI se controla via env var
                MAX_TOKENS_OHLCV.

        Returns:
            Diccionario con estadisticas de la recopilacion:
            - tokens_discovered: Cantidad de tokens nuevos encontrados
            - enriched: Tokens enriquecidos con DexScreener
            - ohlcv_collected: Tokens con OHLCV recopilado
            - holders_collected: Tokens con holders recopilados
            - contracts_checked: Tokens con contratos verificados
            - duration_seconds: Duracion total en segundos
            - timestamp: Momento de la recopilacion

        Ejemplo:
            >>> collector = DataCollector()
            >>> stats = collector.run_daily_collection(chains=["solana"])
            >>> print(f"Tokens: {stats['tokens_discovered']}")
            >>> print(f"Duracion: {stats['duration_seconds']:.0f}s")
        """
        # Registrar hora de inicio
        inicio = time.time()
        timestamp = datetime.now(timezone.utc).isoformat()

        logger.info("#" * 60)
        logger.info(f"RECOPILACION DIARIA INICIADA - {timestamp}")
        logger.info(f"Cadenas: {chains or list(SUPPORTED_CHAINS.keys())}")
        logger.info("#" * 60)

        # Resetear circuit breaker de Pump.fun al inicio de cada run diario
        # (si estaba abierto de un run anterior, le damos otra oportunidad)
        self.solana_discovery.reset_circuit_breaker()

        # --- Paso 1: Descubrir pools nuevos (GeckoTerminal) ---
        tokens = self.discover_new_pools(chains=chains)

        # --- Paso 1B: Descubrir tokens desde DexScreener ---
        dex_tokens = self.discover_from_dexscreener()
        tokens.extend(dex_tokens)

        # --- Paso 1C: Descubrir tokens desde categorias CoinGecko ---
        cg_tokens = self.discover_from_coingecko_categories()
        tokens.extend(cg_tokens)

        # --- Paso 1D: Descubrir tokens desde Birdeye ---
        birdeye_tokens = self.discover_from_birdeye()
        tokens.extend(birdeye_tokens)

        # Deduplicar tokens por token_id (puede haber solapamiento entre fuentes)
        seen_ids: set[str] = set()
        unique_tokens: list[dict] = []
        for token in tokens:
            tid = token.get("token_id", "")
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                unique_tokens.append(token)
        tokens = unique_tokens
        logger.info(
            f"Total tokens descubiertos (deduplicados): {len(tokens)} "
            f"(GeckoTerminal + DexScreener + CoinGecko + Birdeye)"
        )

        # --- Paso 2: Enriquecer con DexScreener ---
        self.enrich_with_dexscreener(tokens)

        # --- Paso 3: Recopilar OHLCV ---
        self.collect_ohlcv(tokens)

        # --- Paso 4: Recopilar holders (Solana + ETH/Base via Birdeye) ---
        self.collect_holders(tokens)

        # --- Paso 5: Verificar contratos (Etherscan + RPC) ---
        self.collect_contract_info(tokens)

        # --- Paso 5B: Seguridad via Birdeye (tokens sin contract_info) ---
        self.collect_birdeye_security(tokens)

        # --- Paso 5C: Fechas de creacion via Birdeye ---
        self.collect_birdeye_creation_dates(tokens)

        # --- Paso 5D: Trade data via Birdeye (buys/sells/traders) ---
        self.collect_birdeye_trade_data(tokens)

        # --- Paso 5E: Token overview via Birdeye (datos completos) ---
        self.collect_birdeye_token_overview(tokens)

        # --- Paso 6: Actualizar OHLCV de tokens existentes ---
        ohlcv_update_stats = self.update_existing_ohlcv(max_tokens=max_tokens_ohlcv)

        # --- Paso 7: Enriquecer tokens existentes sin datos via Birdeye ---
        # max_tokens=200 por tipo (holders, security, dates) = hasta ~600 calls
        # Reducido de 3000 para ahorrar CU Birdeye (~50K/dia presupuesto).
        birdeye_enrich_stats = self.enrich_existing_tokens_birdeye(max_tokens=200)

        # Calcular duracion total
        duracion = time.time() - inicio

        # Construir diccionario de estadisticas
        stats = {
            "tokens_discovered": len(tokens),
            "tokens_gecko": len(tokens) - len(dex_tokens) - len(cg_tokens) - len(birdeye_tokens),
            "tokens_dexscreener": len(dex_tokens),
            "tokens_coingecko_categories": len(cg_tokens),
            "tokens_birdeye": len(birdeye_tokens),
            "birdeye_enrichment": birdeye_enrich_stats,
            "chains_processed": chains or list(SUPPORTED_CHAINS.keys()),
            "duration_seconds": round(duracion, 2),
            "timestamp": timestamp,
        }

        # Obtener conteos actuales de la base de datos para el resumen
        db_stats = self.storage.stats()
        stats["db_totals"] = db_stats

        logger.info("#" * 60)
        logger.info("RECOPILACION DIARIA COMPLETADA")
        logger.info(f"Tokens descubiertos: {stats['tokens_discovered']}")
        logger.info(f"Birdeye enrichment: {birdeye_enrich_stats}")
        logger.info(f"Duracion: {duracion:.1f} segundos")
        logger.info(f"Totales en DB: {db_stats}")
        logger.info("#" * 60)

        return stats

    # ================================================================
    # RECOPILACION DE UN SOLO TOKEN
    # ================================================================

    def collect_single_token(self, token_address: str, chain: str) -> dict:
        """
        Recopila todos los datos disponibles para un token individual.

        Util para la funcionalidad de busqueda del dashboard: el usuario
        ingresa una direccion de token y queremos obtener toda la info
        disponible de todas las APIs.

        Args:
            token_address: Direccion del contrato del token en la blockchain.
            chain: Cadena del token ("solana", "ethereum" o "base").

        Returns:
            Diccionario con toda la informacion recopilada:
            - token: Datos basicos del token
            - pool_snapshot: Snapshot de DexScreener
            - ohlcv: Lista de velas OHLCV
            - holders: Lista de top holders (solo Solana)
            - contract_info: Informacion del contrato
            Cada seccion puede ser None si la API fallo.

        Ejemplo:
            >>> data = collector.collect_single_token(
            ...     "DireccionDelToken123...", "solana"
            ... )
            >>> print(data["token"]["name"])
            >>> print(f"Holders: {len(data.get('holders', []))}")
        """
        logger.info(
            f"Recopilando datos para token {token_address[:10]}... "
            f"en '{chain}'"
        )

        # Diccionario para acumular todos los datos recopilados
        resultado: dict = {
            "token": None,
            "pool_snapshot": None,
            "ohlcv": [],
            "holders": [],
            "contract_info": None,
        }

        # Obtener IDs de cadena para cada API
        chain_config = SUPPORTED_CHAINS.get(chain, {})
        gecko_chain_id = chain_config.get("geckoterminal_id", chain)
        dex_chain_id = chain_config.get("dexscreener_id", chain)

        # --- 1. Buscar token en GeckoTerminal ---
        try:
            pools = self.gecko.search_pools(token_address)
            if pools:
                # Tomar el primer pool que coincida
                pool = pools[0]
                token_data = self._pool_to_token(pool, chain)
                if token_data:
                    token_data["token_id"] = token_address
                    self.storage.upsert_token(token_data)
                    resultado["token"] = token_data
        except Exception as e:
            logger.warning(f"Error buscando token en GeckoTerminal: {e}")

        # --- 2. Datos de DexScreener ---
        try:
            pair_data = self.dex.get_token_pairs(dex_chain_id, token_address)
            if pair_data:
                pair = pair_data[0] if isinstance(pair_data, list) else pair_data
                # El dexscreener_client ya parsea a formato plano
                buyers = safe_int(pair.get("txns_24h_buys"))
                sellers = safe_int(pair.get("txns_24h_sells"))

                snapshot = {
                    "token_id": token_address,
                    "chain": chain,
                    "snapshot_time": datetime.now(timezone.utc).isoformat(),
                    "price_usd": safe_float(pair.get("price_usd")),
                    "volume_24h": safe_float(pair.get("volume_24h")),
                    "liquidity_usd": safe_float(pair.get("liquidity_usd")),
                    "market_cap": safe_float(pair.get("market_cap")),
                    "fdv": safe_float(pair.get("fdv")),
                    "buyers_24h": buyers,
                    "sellers_24h": sellers,
                    "makers_24h": buyers + sellers,
                    "source": "dexscreener",
                }
                self.storage.insert_pool_snapshot(snapshot)
                resultado["pool_snapshot"] = snapshot
        except Exception as e:
            logger.warning(f"Error obteniendo datos de DexScreener: {e}")

        # --- 3. OHLCV ---
        try:
            pool_address = (
                resultado.get("token", {}) or {}
            ).get("pool_address", "")
            if pool_address:
                velas = self.gecko.get_pool_ohlcv(
                    chain=gecko_chain_id,
                    pool_address=pool_address,
                    timeframe="day",
                    limit=30,
                )
                if velas:
                    ohlcv_rows = []
                    for vela in velas:
                        ts_valor = vela.get("timestamp", 0)
                        ts_iso = (
                            datetime.fromtimestamp(
                                ts_valor, tz=timezone.utc
                            ).isoformat()
                            if ts_valor
                            else ""
                        )
                        ohlcv_rows.append({
                            "token_id": token_address,
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
                    self.storage.insert_ohlcv_batch(ohlcv_rows)
                    resultado["ohlcv"] = ohlcv_rows
        except Exception as e:
            logger.warning(f"Error obteniendo OHLCV: {e}")

        # --- 4. Holders (Solana via Helius + ETH/Base via Birdeye) ---
        if chain == "solana":
            try:
                holders_data = self.solana_rpc.get_token_largest_accounts(
                    token_address
                )
                if holders_data:
                    total_supply = safe_float(
                        (resultado.get("token", {}) or {}).get("total_supply")
                    )
                    snapshot_time = datetime.now(timezone.utc).isoformat()
                    holder_rows = []
                    for rank, holder in enumerate(holders_data[:20], start=1):
                        amount = safe_float(holder.get("amount"))
                        pct = (
                            (amount / total_supply) * 100
                            if total_supply and total_supply > 0
                            else 0.0
                        )
                        holder_rows.append({
                            "token_id": token_address,
                            "chain": "solana",
                            "snapshot_time": snapshot_time,
                            "rank": rank,
                            "holder_address": holder.get("address", ""),
                            "amount": amount,
                            "pct_of_supply": pct,
                        })
                    self.storage.insert_holder_snapshot(holder_rows)
                    resultado["holders"] = holder_rows
                elif self.birdeye.is_available:
                    # Fallback: Birdeye para Solana
                    holders_be = self.birdeye.get_token_holder(
                        token_address, chain="solana", limit=20,
                    )
                    if holders_be:
                        self._save_birdeye_holders(token_address, "solana", holders_be)
                        resultado["holders"] = holders_be
            except Exception as e:
                logger.warning(f"Error obteniendo holders: {e}")
        else:
            # ETH/Base: usar Birdeye para holders
            if self.birdeye.is_available:
                try:
                    holders_be = self.birdeye.get_token_holder(
                        token_address, chain=chain, limit=20,
                    )
                    if holders_be:
                        self._save_birdeye_holders(token_address, chain, holders_be)
                        resultado["holders"] = holders_be
                except Exception as e:
                    logger.warning(f"Error obteniendo holders Birdeye: {e}")

        # --- 5. Info de contrato ---
        try:
            contract_info = {
                "token_id": token_address,
                "chain": chain,
                "is_verified": None,
                "is_renounced": None,
                "has_mint_authority": None,
                "deploy_timestamp": None,
            }

            if chain in ("ethereum", "base"):
                ethclient = self._etherscan_for(chain)
                is_verified = ethclient.is_contract_verified(
                    token_address
                )
                contract_info["is_verified"] = is_verified

                source = ethclient.get_contract_source(token_address)
                if source:
                    contract_info["is_renounced"] = False

            elif chain == "solana":
                supply_info = self.solana_rpc.get_token_supply(
                    token_address
                )
                if supply_info:
                    contract_info["is_verified"] = True

            self.storage.upsert_contract_info(contract_info)
            resultado["contract_info"] = contract_info

        except Exception as e:
            logger.warning(f"Error verificando contrato: {e}")

        # --- 5B. Seguridad Birdeye (complementa Etherscan/RPC) ---
        if self.birdeye.is_available:
            try:
                security = self.birdeye.get_token_security(
                    token_address, chain=chain,
                )
                if security:
                    resultado["birdeye_security"] = security
            except Exception as e:
                logger.debug(f"Error obteniendo seguridad Birdeye: {e}")

        # --- 5C. Trade data Birdeye ---
        if self.birdeye.is_available:
            try:
                trade_data = self.birdeye.get_token_trade_data(
                    token_address, chain=chain,
                )
                if trade_data:
                    resultado["birdeye_trade_data"] = trade_data
                    # Guardar como snapshot
                    snapshot_time = datetime.now(timezone.utc).isoformat()
                    snapshot = {
                        "token_id": token_address,
                        "chain": chain,
                        "snapshot_time": snapshot_time,
                        "price_usd": None,
                        "volume_24h": (
                            safe_float(trade_data.get("volume_buy_24h", 0))
                            + safe_float(trade_data.get("volume_sell_24h", 0))
                        ),
                        "liquidity_usd": None,
                        "market_cap": None,
                        "fdv": None,
                        "buyers_24h": trade_data.get("buy_24h"),
                        "sellers_24h": trade_data.get("sell_24h"),
                        "makers_24h": (
                            safe_int(trade_data.get("buy_24h") or 0)
                            + safe_int(trade_data.get("sell_24h") or 0)
                        ),
                        "tx_count_24h": trade_data.get("trade_24h"),
                        "source": "birdeye-trade",
                    }
                    self.storage.insert_pool_snapshot(snapshot)
            except Exception as e:
                logger.debug(f"Error obteniendo trade data Birdeye: {e}")

        # --- 5D. Token overview Birdeye ---
        if self.birdeye.is_available:
            try:
                overview = self.birdeye.get_token_overview(
                    token_address, chain=chain,
                )
                if overview:
                    resultado["birdeye_overview"] = overview
                    # Guardar como snapshot
                    snapshot_time = datetime.now(timezone.utc).isoformat()
                    snapshot = {
                        "token_id": token_address,
                        "chain": chain,
                        "snapshot_time": snapshot_time,
                        "price_usd": overview.get("price"),
                        "volume_24h": overview.get("volume_24h"),
                        "liquidity_usd": overview.get("liquidity"),
                        "market_cap": overview.get("mc"),
                        "fdv": None,
                        "buyers_24h": overview.get("buy_24h"),
                        "sellers_24h": overview.get("sell_24h"),
                        "makers_24h": overview.get("unique_wallet_24h"),
                        "tx_count_24h": overview.get("trade_24h"),
                        "source": "birdeye-overview",
                    }
                    self.storage.insert_pool_snapshot(snapshot)
            except Exception as e:
                logger.debug(f"Error obteniendo overview Birdeye: {e}")

        logger.info(
            f"Recopilacion de token {token_address[:10]}... completada"
        )
        return resultado

    # ================================================================
    # CONTEXTO DE MERCADO (BTC, ETH, SOL)
    # ================================================================

    def collect_market_context(self, days: int = 90) -> None:
        """
        Obtiene historial de precios de BTC, ETH y SOL como contexto de mercado.

        Las memecoins estan muy correlacionadas con el mercado general:
        - Si BTC sube, las memecoins tienden a subir mas (alta beta)
        - Si BTC baja, las memecoins caen mas fuerte

        Por eso, incluimos precios de BTC, ETH y SOL como features
        del modelo ML para contexto de mercado.

        Los datos se guardan como archivos Parquet en data/processed/
        para uso posterior en el calculo de features.

        Args:
            days: Numero de dias de historial a obtener.
                90 dias es suficiente para cubrir nuestra ventana de
                observacion de 30 dias con margen.

        Ejemplo:
            >>> collector.collect_market_context(days=90)
            # Crea archivos:
            #   data/processed/btc_price_history.parquet
            #   data/processed/eth_price_history.parquet
            #   data/processed/sol_price_history.parquet
        """
        logger.info("=" * 60)
        logger.info(
            f"Recopilando contexto de mercado ({days} dias)..."
        )
        logger.info("=" * 60)

        # Monedas de referencia para contexto de mercado
        # Usamos los IDs de CoinGecko
        reference_coins = {
            "bitcoin": "btc",
            "ethereum": "eth",
            "solana": "sol",
        }

        for coin_id, short_name in reference_coins.items():
            try:
                logger.info(f"Obteniendo historial de {coin_id}...")

                # Llamar a CoinGecko Demo API para obtener historial
                historial = self.gecko.get_coin_price_history(
                    coin_id=coin_id, days=days
                )

                if not historial or not historial.get("prices"):
                    logger.warning(
                        f"No se obtuvo historial de {coin_id}"
                    )
                    continue

                # Convertir a DataFrame para facilitar el manejo
                # La respuesta tiene formato: [[timestamp_ms, precio], ...]
                df = pd.DataFrame(
                    historial["prices"],
                    columns=["timestamp_ms", "price_usd"],
                )

                # Convertir timestamp de milisegundos a datetime
                df["timestamp"] = pd.to_datetime(
                    df["timestamp_ms"], unit="ms", utc=True
                )

                # Agregar columnas de volumen y market cap si estan disponibles
                if historial.get("total_volumes"):
                    df_vol = pd.DataFrame(
                        historial["total_volumes"],
                        columns=["timestamp_ms", "volume_usd"],
                    )
                    df["volume_usd"] = df_vol["volume_usd"]

                if historial.get("market_caps"):
                    df_mc = pd.DataFrame(
                        historial["market_caps"],
                        columns=["timestamp_ms", "market_cap_usd"],
                    )
                    df["market_cap_usd"] = df_mc["market_cap_usd"]

                # Eliminar la columna de timestamp en milisegundos
                # (ya tenemos la columna 'timestamp' en formato datetime)
                df = df.drop(columns=["timestamp_ms"])

                # Establecer timestamp como indice
                df = df.set_index("timestamp")

                # Guardar como Parquet en data/processed/
                # Parquet es un formato binario eficiente para DataFrames
                output_path = PROCESSED_DIR / f"{short_name}_price_history.parquet"
                df.to_parquet(output_path, engine="pyarrow")

                logger.info(
                    f"Historial de {coin_id} guardado: "
                    f"{len(df)} registros en {output_path}"
                )

                # Pausa entre monedas
                time.sleep(1.0)

            except Exception as e:
                logger.error(
                    f"Error obteniendo contexto de mercado para {coin_id}: {e}"
                )
                continue

        logger.info("Contexto de mercado completado")

    # ================================================================
    # PASO 6: ACTUALIZAR OHLCV DE TOKENS EXISTENTES
    # ================================================================

    def update_existing_ohlcv(
        self,
        max_tokens: int = 300,
        timeframe: str = "day",
        limit: int = 14,
    ) -> dict:
        """
        Actualiza OHLCV para tokens existentes en la base de datos.

        El pipeline diario solo recopila OHLCV para tokens NUEVOS descubiertos
        en esa sesion. Este metodo complementa eso actualizando candles para
        tokens que ya estan en la BD pero pueden tener datos desactualizados.

        Estrategia de fuentes:
        - Si Birdeye esta disponible, se usa como fuente primaria.
          Con Birdeye no necesitamos pool_address (usa token address).
        - Si Birdeye falla, GeckoTerminal como fallback (requiere pool_address).

        Prioriza tokens que:
        1. No tienen OHLCV todavia, o
        2. Su ultimo OHLCV tiene mas de 1 dia de antiguedad

        Args:
            max_tokens: Maximo de tokens a procesar (para controlar rate limits).
            timeframe: Periodo de cada vela ("day", "hour").
            limit: Numero de velas a pedir por token (14 dias cubre bien).

        Returns:
            Dict con estadisticas: tokens_processed, candles_added, errors.
        """
        logger.info("=" * 60)
        logger.info("PASO 6: Actualizando OHLCV de tokens existentes...")
        if self.birdeye.is_available:
            logger.info("Fuente primaria: Birdeye, fallback: GeckoTerminal")
        logger.info("=" * 60)

        # Buscar tokens que necesitan OHLCV actualizado
        # Con Birdeye no necesitamos pool_address, asi que incluimos todos los tokens
        # Prioridad 1: tokens sin ningun OHLCV
        # Prioridad 2: tokens cuyo ultimo OHLCV tiene >1 dia
        # Consulta compatible con PostgreSQL (Supabase):
        # - No se pueden usar alias en HAVING, repetimos la expresion
        # - DATE('now', '-1 day') es SQLite; en PG: CURRENT_DATE - INTERVAL '1 day'
        # - timestamp::date para extraer la fecha del timestamp
        if self.birdeye.is_available:
            # Con Birdeye: incluir todos los tokens (no necesitan pool_address)
            tokens_df = self.storage.query("""
                SELECT t.token_id, t.chain, t.pool_address,
                       MAX(o.timestamp::date) as last_ohlcv_date,
                       COUNT(o.id) as ohlcv_count
                FROM tokens t
                LEFT JOIN ohlcv o ON t.token_id = o.token_id
                GROUP BY t.token_id, t.chain, t.pool_address
                HAVING COUNT(o.id) = 0
                    OR MAX(o.timestamp::date) < (CURRENT_DATE - INTERVAL '1 day')
                ORDER BY COUNT(o.id) ASC, MAX(o.timestamp::date) ASC NULLS FIRST
                LIMIT ?
            """, (max_tokens,))
        else:
            # Sin Birdeye: solo tokens con pool_address (requerido por GeckoTerminal)
            tokens_df = self.storage.query("""
                SELECT t.token_id, t.chain, t.pool_address,
                       MAX(o.timestamp::date) as last_ohlcv_date,
                       COUNT(o.id) as ohlcv_count
                FROM tokens t
                LEFT JOIN ohlcv o ON t.token_id = o.token_id
                WHERE t.pool_address IS NOT NULL AND t.pool_address != ''
                GROUP BY t.token_id, t.chain, t.pool_address
                HAVING COUNT(o.id) = 0
                    OR MAX(o.timestamp::date) < (CURRENT_DATE - INTERVAL '1 day')
                ORDER BY COUNT(o.id) ASC, MAX(o.timestamp::date) ASC NULLS FIRST
                LIMIT ?
            """, (max_tokens,))

        if tokens_df.empty:
            logger.info("Todos los tokens tienen OHLCV actualizado")
            return {"tokens_processed": 0, "candles_added": 0, "errors": 0}

        logger.info(
            f"Actualizando OHLCV para {len(tokens_df)} tokens "
            f"({timeframe}, hasta {limit} velas cada uno)"
        )

        exitos = 0
        exitos_birdeye = 0
        exitos_gecko = 0
        errores = 0
        total_velas = 0

        for _, row in tqdm(tokens_df.iterrows(), total=len(tokens_df),
                           desc="OHLCV update", unit="token"):
            try:
                chain = row["chain"]
                chain_config = SUPPORTED_CHAINS.get(chain, {})
                gecko_chain_id = chain_config.get("geckoterminal_id", chain)
                pool_address = row["pool_address"] or ""
                token_id = row["token_id"]

                ohlcv_rows = []

                # --- Intento 1: Birdeye (primario, mas rapido) ---
                if self.birdeye.is_available:
                    birdeye_velas = self._fetch_ohlcv_birdeye(
                        token_id=token_id, chain=chain, limit=limit,
                    )
                    if birdeye_velas:
                        ohlcv_rows = self._birdeye_velas_to_rows(
                            birdeye_velas, token_id, chain,
                            pool_address, timeframe,
                        )
                        exitos_birdeye += 1

                # --- Intento 2: GeckoTerminal (fallback) ---
                if not ohlcv_rows and pool_address:
                    velas = self.gecko.get_pool_ohlcv(
                        chain=gecko_chain_id,
                        pool_address=pool_address,
                        timeframe=timeframe,
                        limit=limit,
                    )

                    if velas:
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
                                "timeframe": timeframe,
                                "timestamp": ts_iso,
                                "open": safe_float(vela.get("open")),
                                "high": safe_float(vela.get("high")),
                                "low": safe_float(vela.get("low")),
                                "close": safe_float(vela.get("close")),
                                "volume": safe_float(vela.get("volume")),
                            })
                        exitos_gecko += 1

                if not ohlcv_rows:
                    errores += 1
                    continue

                self.storage.insert_ohlcv_batch(ohlcv_rows)
                exitos += 1
                total_velas += len(ohlcv_rows)

            except Exception as e:
                logger.warning(
                    f"Error actualizando OHLCV para {row['token_id'][:10]}...: {e}"
                )
                errores += 1

            # Pausa entre tokens: Birdeye es rapido (900/min = 0.07s)
            # pero mantenemos 0.15s para seguridad.
            time.sleep(0.15 if self.birdeye.is_available else 0.5)

        stats = {
            "tokens_processed": exitos,
            "candles_added": total_velas,
            "errors": errores,
        }

        logger.info(
            f"OHLCV update completado: {exitos} tokens, "
            f"{total_velas} velas nuevas, {errores} errores"
        )
        if self.birdeye.is_available:
            logger.info(
                f"  Fuentes: Birdeye={exitos_birdeye}, "
                f"GeckoTerminal fallback={exitos_gecko}"
            )
        return stats

    # ================================================================
    # ENRICHMENT: POOL ADDRESSES PARA TOKENS DE SOLANA
    # ================================================================

    def enrich_solana_pool_addresses(self, tokens: list[dict]) -> None:
        """
        Busca pool_address via DexScreener para tokens Solana que no la tienen.

        Tokens descubiertos desde Jupiter, Raydium o Pump.fun no traen
        pool_address. Sin pool_address no podemos obtener OHLCV de
        GeckoTerminal. Este metodo usa DexScreener para encontrar el
        par con mayor liquidez y actualizar el token en la base de datos.

        Args:
            tokens: Lista de tokens. Se procesan solo los que tienen
                chain == "solana" y pool_address vacio.
        """
        # Filtrar tokens de Solana sin pool_address
        sin_pool = [
            t for t in tokens
            if t.get("chain") == "solana"
            and not t.get("pool_address")
        ]

        if not sin_pool:
            logger.info("No hay tokens Solana sin pool_address para enriquecer")
            return

        logger.info(f"Enriqueciendo pool addresses para {len(sin_pool)} tokens Solana")

        exitos = 0
        errores = 0

        for token in tqdm(sin_pool, desc="Pool addr", unit="token"):
            try:
                token_id = token.get("token_address") or token.get("token_id", "")
                if not token_id:
                    continue

                # Buscar pares en DexScreener (devuelve ordenados por liquidez)
                pares = self.dex.get_token_pairs("solana", token_id)

                if not pares:
                    errores += 1
                    time.sleep(0.1)
                    continue

                # Tomar el par con mayor liquidez (primer resultado)
                par = pares[0]
                pool_address = par.get("pair_address", "")
                dex = par.get("dex", "")

                if pool_address:
                    # Actualizar en la base de datos
                    self.storage.upsert_token({
                        "token_id": token_id,
                        "chain": "solana",
                        "pool_address": pool_address,
                        "dex": dex,
                    })
                    # Actualizar el dict en memoria para los siguientes pasos
                    token["pool_address"] = pool_address
                    token["dex"] = dex
                    token["token_id"] = token_id
                    exitos += 1

            except Exception as e:
                logger.debug(f"Error enriqueciendo pool address: {e}")
                errores += 1

            # Respetar rate limits de DexScreener (300/min)
            time.sleep(0.2)

        logger.info(
            f"Pool addresses enriquecidas: {exitos} exitos, {errores} sin par"
        )

    # ================================================================
    # METODOS PRIVADOS DE UTILIDAD
    # ================================================================

    def _pool_to_token(self, pool: dict, chain: str) -> Optional[dict]:
        """
        Convierte un diccionario de pool (de GeckoTerminal) a un dict
        con el formato esperado por storage.upsert_token().

        GeckoTerminal devuelve datos del pool (ej: SOL/BONK), y necesitamos
        extraer la informacion del token base (el memecoin, no SOL/ETH/etc).

        El pool_id de GeckoTerminal tiene formato "network_poolAddress",
        por ejemplo: "solana_0xAbc123..."

        Args:
            pool: Diccionario con datos del pool parseados por CoinGeckoClient.
            chain: Nombre de la cadena ("solana", "ethereum", "base").

        Returns:
            Diccionario compatible con storage.upsert_token(), o None si
            no se puede parsear.
        """
        try:
            pool_address = pool.get("pool_address", "")

            # La direccion del token base viene de relationships.base_token
            # Es la direccion del contrato del memecoin (no del pool LP)
            base_token_address = pool.get("base_token_address", "")

            # El nombre del pool suele ser "TOKEN / SOL" o "TOKEN / ETH"
            name = pool.get("name", "")
            symbol = name.split(" / ")[0].strip() if " / " in name else name

            # token_id = direccion del contrato del token (no del pool)
            token_id = base_token_address or pool_address

            return {
                "token_id": token_id,
                "chain": chain,
                "name": name,
                "symbol": symbol,
                "pool_address": pool_address,
                "dex": pool.get("dex"),
                "created_at": pool.get("created_at"),
                "total_supply": None,  # No disponible en GeckoTerminal
                "decimals": None,      # No disponible en GeckoTerminal
                # Campos extra que no van a storage pero son utiles para
                # los siguientes pasos del pipeline
                "price_usd": safe_float(pool.get("price_usd")),
                "volume_24h": safe_float(pool.get("volume_24h")),
                "liquidity_usd": safe_float(pool.get("liquidity_usd")),
                "fdv_usd": safe_float(pool.get("fdv_usd")),
            }

        except Exception as e:
            logger.debug(f"Error convirtiendo pool a token: {e}")
            return None


# ================================================================
# PUNTO DE ENTRADA PARA EJECUCION DIRECTA
# ================================================================
# Si ejecutas este archivo directamente: python -m src.data.collector
# se ejecuta la recopilacion diaria completa.

if __name__ == "__main__":
    import os as _os

    logger.info("Iniciando recopilacion diaria desde linea de comandos...")

    # Leer limite de tokens OHLCV desde variable de entorno (GitHub Actions lo pasa)
    max_ohlcv = int(_os.getenv("MAX_TOKENS_OHLCV", "300"))
    logger.info(f"MAX_TOKENS_OHLCV = {max_ohlcv}")

    # Crear el collector con configuracion por defecto
    collector = DataCollector()

    # Ejecutar pipeline completo
    stats = collector.run_daily_collection(max_tokens_ohlcv=max_ohlcv)

    # Tambien recopilar contexto de mercado
    collector.collect_market_context()

    # Mostrar resumen final
    print("\n" + "=" * 60)
    print("RESUMEN DE RECOPILACION DIARIA")
    print("=" * 60)
    print(f"Tokens descubiertos: {stats['tokens_discovered']}")
    print(f"Duracion: {stats['duration_seconds']:.1f} segundos")
    print(f"Cadenas: {stats['chains_processed']}")
    print(f"Totales en DB: {stats.get('db_totals', {})}")
    print("=" * 60)
