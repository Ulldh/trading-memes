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

        Solo se procesan tokens que tienen una pool_address valida,
        ya que el endpoint de GeckoTerminal requiere la direccion del pool.

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
        logger.info("=" * 60)

        if not tokens:
            logger.info("No hay tokens para OHLCV, saltando paso 3")
            return

        # Filtrar solo tokens que tengan pool_address
        # (sin pool_address no podemos pedir OHLCV a GeckoTerminal)
        tokens_con_pool = [
            t for t in tokens if t.get("pool_address")
        ]

        if not tokens_con_pool:
            logger.info(
                "Ningun token tiene pool_address, saltando OHLCV"
            )
            return

        logger.info(
            f"Procesando OHLCV para {len(tokens_con_pool)} tokens "
            f"(de {len(tokens)} total)"
        )

        # Contadores para resumen
        exitos = 0
        errores = 0
        total_velas = 0

        # Iterar con barra de progreso
        for token in tqdm(tokens_con_pool, desc="OHLCV", unit="token"):
            try:
                chain = token.get("chain", "")
                chain_config = SUPPORTED_CHAINS.get(chain, {})
                gecko_chain_id = chain_config.get("geckoterminal_id", chain)
                pool_address = token.get("pool_address", "")
                token_id = token.get("token_id", "")

                # Obtener velas OHLCV de GeckoTerminal
                velas = self.gecko.get_pool_ohlcv(
                    chain=gecko_chain_id,
                    pool_address=pool_address,
                    timeframe=timeframe,
                    limit=limit,
                )

                if not velas:
                    logger.debug(
                        f"Sin OHLCV para {token_id[:10]}..."
                    )
                    errores += 1
                    time.sleep(0.1)
                    continue

                # Convertir cada vela a un dict compatible con storage
                ohlcv_rows = []
                for vela in velas:
                    # Convertir timestamp Unix a ISO format
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

                # Guardar todas las velas de este token en un solo batch
                if ohlcv_rows:
                    self.storage.insert_ohlcv_batch(ohlcv_rows)
                    exitos += 1
                    total_velas += len(ohlcv_rows)

            except Exception as e:
                token_id = token.get("token_id", "desconocido")
                logger.warning(
                    f"Error recopilando OHLCV para {token_id[:10]}...: {e}"
                )
                errores += 1

            # Pausa entre tokens para GeckoTerminal (30/min = 0.5/s refill)
            # Con 0.5s garantizamos no exceder el rate limit en loops largos
            time.sleep(0.5)

        # Resumen del paso
        logger.info(
            f"OHLCV completado: {exitos} tokens, "
            f"{total_velas} velas totales, {errores} errores"
        )

    # ================================================================
    # PASO 4: RECOPILAR HOLDERS (solo Solana)
    # ================================================================

    def collect_holders(self, tokens: list[dict]) -> None:
        """
        Recopila los top 20 holders para tokens de Solana.

        Los holders son las wallets que poseen mas tokens. Analizar la
        concentracion de holders es clave para detectar rugs:
        - Si 1 wallet tiene >50% del supply, riesgo de rug pull
        - Si top 10 holders tienen >80%, concentracion peligrosa

        Solo funciona para tokens de Solana, ya que usa la API de
        Helius (RPC de Solana). Para Ethereum/Base, esta informacion
        se podria obtener de Etherscan en el futuro.

        Args:
            tokens: Lista de tokens (output de discover_new_pools).
                Solo se procesan tokens donde chain == "solana".

        Ejemplo:
            >>> tokens = collector.discover_new_pools(chains=["solana"])
            >>> collector.collect_holders(tokens)
        """
        logger.info("=" * 60)
        logger.info("PASO 4: Recopilando holders (solo Solana)...")
        logger.info("=" * 60)

        if not tokens:
            logger.info("No hay tokens para holders, saltando paso 4")
            return

        # Filtrar solo tokens de Solana
        solana_tokens = [
            t for t in tokens if t.get("chain") == "solana"
        ]

        if not solana_tokens:
            logger.info(
                "No hay tokens de Solana, saltando recopilacion de holders"
            )
            return

        logger.info(f"Procesando holders para {len(solana_tokens)} tokens de Solana")

        # Timestamp actual para el snapshot
        snapshot_time = datetime.now(timezone.utc).isoformat()

        # Contadores
        exitos = 0
        errores = 0

        # Iterar con barra de progreso
        for token in tqdm(solana_tokens, desc="Holders", unit="token"):
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

                if not holders_data:
                    logger.debug(
                        f"Sin holders para {token_id[:10]}..."
                    )
                    errores += 1
                    time.sleep(0.1)
                    continue

                # Construir lista de holder snapshots
                # Cada holder tiene: address, amount
                holder_rows = []
                for rank, holder in enumerate(holders_data[:20], start=1):
                    # Calcular porcentaje del supply total
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

                # Guardar todos los holders de este token
                if holder_rows:
                    self.storage.insert_holder_snapshot(holder_rows)
                    exitos += 1

            except Exception as e:
                token_id = token.get("token_id", "desconocido")
                logger.warning(
                    f"Error recopilando holders para {token_id[:10]}...: {e}"
                )
                errores += 1

            # Pausa breve entre tokens
            time.sleep(0.3)

        # Resumen del paso
        logger.info(
            f"Holders completado: {exitos} tokens procesados, {errores} errores"
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
    # PIPELINE COMPLETO: RECOPILACION DIARIA
    # ================================================================

    def run_daily_collection(
        self, chains: Optional[list[str]] = None,
        max_tokens_ohlcv: int = 200,
    ) -> dict:
        """
        Ejecuta el pipeline completo de recopilacion diaria.

        Llama a los pasos en orden:
            1.  Descubrir pools nuevos (GeckoTerminal, 10 paginas/cadena)
            1B. Descubrir tokens desde DexScreener (boosted, profiles, CTO)
            1C. Descubrir tokens desde categorias CoinGecko (meme-token, etc.)
            2.  Enriquecer con DexScreener (buyers/sellers)
            3.  Obtener OHLCV historico
            4.  Obtener holders (solo Solana)
            5.  Verificar contratos (Etherscan + RPC)
            6.  Actualizar OHLCV de tokens existentes

        Este metodo esta diseñado para ejecutarse una vez al dia
        (ej: con un cron job o un scheduler de Python).

        Args:
            chains: Lista de cadenas a procesar. Si es None, usa todas
                las soportadas (solana, ethereum, base).
            max_tokens_ohlcv: Maximo de tokens existentes a actualizar en
                el paso 6 (OHLCV update). Default 200. En CI se controla
                via env var MAX_TOKENS_OHLCV (default 500 para cron).

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
            f"(GeckoTerminal + DexScreener + CoinGecko)"
        )

        # --- Paso 2: Enriquecer con DexScreener ---
        self.enrich_with_dexscreener(tokens)

        # --- Paso 3: Recopilar OHLCV ---
        self.collect_ohlcv(tokens)

        # --- Paso 4: Recopilar holders (solo Solana) ---
        self.collect_holders(tokens)

        # --- Paso 5: Verificar contratos ---
        self.collect_contract_info(tokens)

        # --- Paso 6: Actualizar OHLCV de tokens existentes ---
        ohlcv_update_stats = self.update_existing_ohlcv(max_tokens=max_tokens_ohlcv)

        # Calcular duracion total
        duracion = time.time() - inicio

        # Construir diccionario de estadisticas
        stats = {
            "tokens_discovered": len(tokens),
            "tokens_gecko": len(tokens) - len(dex_tokens) - len(cg_tokens),
            "tokens_dexscreener": len(dex_tokens),
            "tokens_coingecko_categories": len(cg_tokens),
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

        # --- 4. Holders (solo Solana) ---
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
            except Exception as e:
                logger.warning(f"Error obteniendo holders: {e}")

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
                    # Limitacion: is_proxy=False NO implica ownership renunciado.
                    # Dejamos False (desconocido) hasta tener fuente fiable.
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
        max_tokens: int = 500,
        timeframe: str = "day",
        limit: int = 14,
    ) -> dict:
        """
        Actualiza OHLCV para tokens existentes que ya tienen pool_address.

        El pipeline diario solo recopila OHLCV para tokens NUEVOS descubiertos
        en esa sesion. Este metodo complementa eso actualizando candles para
        tokens que ya estan en la BD pero pueden tener datos desactualizados.

        Prioriza tokens que:
        1. Tienen pool_address (necesario para GeckoTerminal)
        2. No tienen OHLCV todavia, o
        3. Su ultimo OHLCV tiene mas de 1 dia de antiguedad

        Args:
            max_tokens: Maximo de tokens a procesar (para controlar rate limits).
            timeframe: Periodo de cada vela ("day", "hour").
            limit: Numero de velas a pedir por token (14 dias cubre bien).

        Returns:
            Dict con estadisticas: tokens_processed, candles_added, errors.
        """
        logger.info("=" * 60)
        logger.info("PASO 6: Actualizando OHLCV de tokens existentes...")
        logger.info("=" * 60)

        # Buscar tokens con pool_address que necesitan OHLCV actualizado
        # Prioridad 1: tokens sin ningun OHLCV
        # Prioridad 2: tokens cuyo ultimo OHLCV tiene >1 dia
        # Consulta compatible con PostgreSQL (Supabase):
        # - No se pueden usar alias en HAVING, repetimos la expresion
        # - DATE('now', '-1 day') es SQLite; en PG: CURRENT_DATE - INTERVAL '1 day'
        # - timestamp::date para extraer la fecha del timestamp
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
            logger.info("Todos los tokens con pool_address tienen OHLCV actualizado")
            return {"tokens_processed": 0, "candles_added": 0, "errors": 0}

        logger.info(
            f"Actualizando OHLCV para {len(tokens_df)} tokens "
            f"({timeframe}, hasta {limit} velas cada uno)"
        )

        exitos = 0
        errores = 0
        total_velas = 0

        for _, row in tqdm(tokens_df.iterrows(), total=len(tokens_df),
                           desc="OHLCV update", unit="token"):
            try:
                chain = row["chain"]
                chain_config = SUPPORTED_CHAINS.get(chain, {})
                gecko_chain_id = chain_config.get("geckoterminal_id", chain)
                pool_address = row["pool_address"]
                token_id = row["token_id"]

                velas = self.gecko.get_pool_ohlcv(
                    chain=gecko_chain_id,
                    pool_address=pool_address,
                    timeframe=timeframe,
                    limit=limit,
                )

                if not velas:
                    errores += 1
                    continue

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
                        "timeframe": timeframe,
                        "timestamp": ts_iso,
                        "open": safe_float(vela.get("open")),
                        "high": safe_float(vela.get("high")),
                        "low": safe_float(vela.get("low")),
                        "close": safe_float(vela.get("close")),
                        "volume": safe_float(vela.get("volume")),
                    })

                if ohlcv_rows:
                    self.storage.insert_ohlcv_batch(ohlcv_rows)
                    exitos += 1
                    total_velas += len(ohlcv_rows)

            except Exception as e:
                logger.warning(
                    f"Error actualizando OHLCV para {row['token_id'][:10]}...: {e}"
                )
                errores += 1

            # Pausa entre tokens para GeckoTerminal (30/min = 0.5/s refill)
            time.sleep(0.5)

        stats = {
            "tokens_processed": exitos,
            "candles_added": total_velas,
            "errors": errores,
        }

        logger.info(
            f"OHLCV update completado: {exitos} tokens, "
            f"{total_velas} velas nuevas, {errores} errores"
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
    max_ohlcv = int(_os.getenv("MAX_TOKENS_OHLCV", "500"))
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
