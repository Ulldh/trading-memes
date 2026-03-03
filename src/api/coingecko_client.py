"""
coingecko_client.py - Cliente para las APIs de GeckoTerminal y CoinGecko.

Este modulo proporciona acceso a dos APIs relacionadas:

1. GeckoTerminal (PRINCIPAL): API gratuita sin autenticacion para datos de pools
   DEX (exchanges descentralizados). Aqui obtenemos precios, volumen, liquidez
   y datos OHLCV de tokens en tiempo real.

2. CoinGecko Demo API: API con key gratuita (demo) para obtener datos de mercado
   de criptomonedas mayores como Bitcoin, Ethereum y Solana. Usamos estos datos
   como contexto de mercado (si BTC baja, las memecoins tambien suelen bajar).

Ambas APIs tienen un limite de 30 llamadas por minuto.

Uso:
    from src.api.coingecko_client import CoinGeckoClient

    cliente = CoinGeckoClient()

    # Buscar pools nuevos en Solana
    pools_nuevos = cliente.get_new_pools("solana")

    # Obtener info detallada de un pool
    info = cliente.get_pool_info("solana", "DireccionDelPool123...")

    # Obtener velas OHLCV para analisis tecnico
    velas = cliente.get_pool_ohlcv("solana", "DireccionDelPool123...")

    # Contexto de mercado: precio historico de Bitcoin
    btc_precios = cliente.get_coin_price_history("bitcoin", days=7)
"""

import requests
from typing import Optional

# Importamos la clase base que nos da rate limiting, cache y retries gratis
from src.api.base_client import BaseAPIClient
from src.utils.logger import get_logger
from src.utils.helpers import safe_float, safe_int

# Importar configuracion del proyecto
try:
    from config import API_URLS, RATE_LIMITS, COINGECKO_API_KEY
except ImportError:
    # Valores por defecto si no se encuentra config.py
    API_URLS = {
        "geckoterminal": "https://api.geckoterminal.com/api/v2",
        "coingecko": "https://api.coingecko.com/api/v3",
    }
    RATE_LIMITS = {"geckoterminal": 30, "coingecko": 30}
    COINGECKO_API_KEY = ""

# Logger para este modulo (todos los mensajes tendran el prefijo "coingecko_client")
logger = get_logger(__name__)


class CoinGeckoClient(BaseAPIClient):
    """
    Cliente unificado para GeckoTerminal y CoinGecko Demo API.

    Hereda de BaseAPIClient, lo que significa que automaticamente tiene:
    - Rate limiting (no excede 30 calls/min)
    - Reintentos con backoff exponencial
    - Cache en disco
    - Guardado de respuestas crudas

    GeckoTerminal se usa como API principal (datos de pools DEX).
    CoinGecko Demo se usa solo para contexto de mercado (BTC, ETH, SOL).

    Args:
        coingecko_api_key: Key para CoinGecko Demo API. Si no se pasa,
            se usa la key de config.py / .env.
    """

    def __init__(self, coingecko_api_key: Optional[str] = None):
        # Inicializar la clase base con la URL de GeckoTerminal
        # como API principal
        super().__init__(
            base_url=API_URLS["geckoterminal"],
            name="geckoterminal",
            calls_per_minute=RATE_LIMITS.get("geckoterminal", 30),
        )

        # Guardar la API key de CoinGecko Demo
        # (usamos la que nos pasen, o la de config.py)
        self._cg_api_key = coingecko_api_key or COINGECKO_API_KEY
        self._cg_base_url = API_URLS.get(
            "coingecko", "https://api.coingecko.com/api/v3"
        )

        # Crear una sesion HTTP separada para CoinGecko Demo
        # porque necesita un header especial con la API key
        self._cg_session = requests.Session()
        self._cg_session.headers.update({
            "Accept": "application/json",
            "User-Agent": "MemecoinGemDetector/1.0",
        })
        # Solo agregar el header de autenticacion si tenemos una key
        if self._cg_api_key:
            self._cg_session.headers["x-cg-demo-key"] = self._cg_api_key

        logger.info("CoinGeckoClient inicializado (GeckoTerminal + CoinGecko Demo)")

    # ================================================================
    # GECKOTERMINAL - Endpoints principales (no necesitan autenticacion)
    # ================================================================

    def get_new_pools(self, chain: str, page: int = 1) -> list[dict]:
        """
        Obtiene pools creados recientemente en una cadena (ultimas 48h).

        Esto es CLAVE para descubrir memecoins nuevas apenas se lanzan.
        Cuanto antes detectemos un token prometedor, mejor sera la entrada.

        Args:
            chain: Identificador de la cadena (ej: "solana", "eth", "base").
            page: Numero de pagina para paginacion (empieza en 1).

        Returns:
            Lista de diccionarios con datos limpios de cada pool.
            Cada dict tiene: name, pool_address, token_address, price_usd,
            volume_24h, liquidity_usd, fdv, created_at, etc.
            Retorna lista vacia si hay error.

        Ejemplo:
            >>> cliente = CoinGeckoClient()
            >>> pools = cliente.get_new_pools("solana")
            >>> for pool in pools[:3]:
            ...     print(pool["name"], pool["price_usd"])
        """
        logger.info(f"Obteniendo pools nuevos en '{chain}' (pagina {page})")

        # Hacer la peticion GET (heredada de BaseAPIClient)
        # El endpoint sigue el formato de la API de GeckoTerminal
        respuesta = self._get(
            f"/networks/{chain}/new_pools",
            params={"page": page},
        )

        # Si la peticion fallo, devolver lista vacia
        if not respuesta or "data" not in respuesta:
            logger.warning(f"No se obtuvieron pools nuevos para '{chain}'")
            return []

        # Parsear la respuesta: GeckoTerminal envuelve los datos en
        # {"data": [{"id": ..., "attributes": {...}}, ...]}
        pools_limpios = []
        for pool_raw in respuesta["data"]:
            pool_parseado = self._parsear_pool(pool_raw)
            if pool_parseado:
                pools_limpios.append(pool_parseado)

        logger.info(f"Se obtuvieron {len(pools_limpios)} pools nuevos en '{chain}'")
        return pools_limpios

    def get_pool_info(self, chain: str, pool_address: str) -> Optional[dict]:
        """
        Obtiene datos detallados de un pool especifico.

        Incluye: precio actual, volumen 24h, liquidez, FDV (Fully Diluted
        Valuation), y cambios de precio en diferentes ventanas de tiempo.

        Args:
            chain: Identificador de la cadena (ej: "solana", "eth", "base").
            pool_address: Direccion del pool en la blockchain.

        Returns:
            Diccionario con datos limpios del pool, o None si no se encontro.

        Ejemplo:
            >>> info = cliente.get_pool_info("solana", "0xAbCdEf...")
            >>> print(info["price_usd"], info["liquidity_usd"])
        """
        logger.info(f"Obteniendo info del pool {pool_address[:10]}... en '{chain}'")

        respuesta = self._get(f"/networks/{chain}/pools/{pool_address}")

        if not respuesta or "data" not in respuesta:
            logger.warning(f"No se encontro el pool {pool_address[:10]}...")
            return None

        return self._parsear_pool(respuesta["data"])

    def get_pool_ohlcv(
        self,
        chain: str,
        pool_address: str,
        timeframe: str = "day",
        limit: int = 100,
    ) -> list[dict]:
        """
        Obtiene datos OHLCV (velas) de un pool para analisis tecnico.

        OHLCV significa: Open, High, Low, Close, Volume.
        Son los datos basicos para graficar velas japonesas y calcular
        indicadores tecnicos como RSI, MACD, medias moviles, etc.

        Args:
            chain: Identificador de la cadena (ej: "solana", "eth", "base").
            pool_address: Direccion del pool.
            timeframe: Periodo de cada vela. Valores validos:
                - "day" (1 vela por dia)
                - "hour" (1 vela por hora)
                - "minute" (1 vela por minuto)
            limit: Cantidad maxima de velas a obtener (max 1000).

        Returns:
            Lista de diccionarios con las velas. Cada dict tiene:
            timestamp, open, high, low, close, volume.
            Lista vacia si hay error.

        Ejemplo:
            >>> velas = cliente.get_pool_ohlcv("solana", "0xAbc...", "hour", 24)
            >>> for vela in velas[-3:]:
            ...     print(vela["close"], vela["volume"])
        """
        logger.info(
            f"Obteniendo OHLCV ({timeframe}) del pool "
            f"{pool_address[:10]}... en '{chain}'"
        )

        # GeckoTerminal usa el formato: /pools/{address}/ohlcv/{timeframe}
        respuesta = self._get(
            f"/networks/{chain}/pools/{pool_address}/ohlcv/{timeframe}",
            params={"limit": limit},
        )

        if not respuesta:
            logger.warning("No se obtuvieron datos OHLCV")
            return []

        # La API retorna los datos OHLCV en:
        # {"data": {"attributes": {"ohlcv_list": [[ts, o, h, l, c, v], ...]}}}
        try:
            # Navegar la estructura anidada de la respuesta
            ohlcv_raw = (
                respuesta
                .get("data", {})
                .get("attributes", {})
                .get("ohlcv_list", [])
            )
        except (AttributeError, TypeError):
            logger.warning("Formato inesperado en respuesta OHLCV")
            return []

        # Convertir cada lista [ts, o, h, l, c, v] a un diccionario legible
        velas = []
        for candle in ohlcv_raw:
            # Verificar que la vela tenga los 6 campos esperados
            if len(candle) >= 6:
                velas.append({
                    "timestamp": safe_int(candle[0]),       # Unix timestamp
                    "open": safe_float(candle[1]),          # Precio de apertura
                    "high": safe_float(candle[2]),          # Precio maximo
                    "low": safe_float(candle[3]),           # Precio minimo
                    "close": safe_float(candle[4]),         # Precio de cierre
                    "volume": safe_float(candle[5]),        # Volumen en USD
                })

        logger.info(f"Se obtuvieron {len(velas)} velas OHLCV")
        return velas

    def search_pools(self, query: str) -> list[dict]:
        """
        Busca pools por nombre del token o direccion.

        Util para encontrar un token especifico cuando conocemos
        su nombre (ej: "PEPE", "BONK") o su direccion.

        Args:
            query: Texto de busqueda (nombre, simbolo o direccion del token).

        Returns:
            Lista de diccionarios con pools que coinciden con la busqueda.
            Lista vacia si no hay resultados.

        Ejemplo:
            >>> resultados = cliente.search_pools("BONK")
            >>> for r in resultados[:3]:
            ...     print(r["name"], r["pool_address"])
        """
        logger.info(f"Buscando pools con query: '{query}'")

        respuesta = self._get(
            "/search/pools",
            params={"query": query},
        )

        if not respuesta or "data" not in respuesta:
            logger.warning(f"Sin resultados para busqueda: '{query}'")
            return []

        # Parsear cada pool del resultado
        resultados = []
        for pool_raw in respuesta["data"]:
            pool_parseado = self._parsear_pool(pool_raw)
            if pool_parseado:
                resultados.append(pool_parseado)

        logger.info(f"Busqueda '{query}': {len(resultados)} resultados")
        return resultados

    def get_trending_pools(self, chain: str) -> list[dict]:
        """
        Obtiene los pools en tendencia (trending) de una cadena.

        Los pools trending son aquellos con mayor actividad reciente.
        Util para detectar tokens que estan ganando atencion rapidamente.

        Args:
            chain: Identificador de la cadena (ej: "solana", "eth", "base").

        Returns:
            Lista de diccionarios con datos de los pools trending.
            Lista vacia si hay error.

        Ejemplo:
            >>> trending = cliente.get_trending_pools("solana")
            >>> print(f"Hay {len(trending)} pools trending")
        """
        logger.info(f"Obteniendo pools trending en '{chain}'")

        respuesta = self._get(f"/networks/{chain}/trending_pools")

        if not respuesta or "data" not in respuesta:
            logger.warning(f"No se obtuvieron pools trending para '{chain}'")
            return []

        pools = []
        for pool_raw in respuesta["data"]:
            pool_parseado = self._parsear_pool(pool_raw)
            if pool_parseado:
                pools.append(pool_parseado)

        logger.info(f"Se obtuvieron {len(pools)} pools trending en '{chain}'")
        return pools

    def get_top_pools(self, chain: str, page: int = 1) -> list[dict]:
        """
        Obtiene los pools con mayor volumen en una cadena.

        Util para tener una referencia de los tokens mas activos
        y comparar con tokens mas nuevos o mas pequenos.

        Args:
            chain: Identificador de la cadena (ej: "solana", "eth", "base").
            page: Numero de pagina (empieza en 1).

        Returns:
            Lista de diccionarios con datos de los top pools.
            Lista vacia si hay error.

        Ejemplo:
            >>> top = cliente.get_top_pools("solana")
            >>> for pool in top[:5]:
            ...     print(pool["name"], pool["volume_24h"])
        """
        logger.info(f"Obteniendo top pools en '{chain}' (pagina {page})")

        respuesta = self._get(
            f"/networks/{chain}/pools",
            params={"page": page},
        )

        if not respuesta or "data" not in respuesta:
            logger.warning(f"No se obtuvieron top pools para '{chain}'")
            return []

        pools = []
        for pool_raw in respuesta["data"]:
            pool_parseado = self._parsear_pool(pool_raw)
            if pool_parseado:
                pools.append(pool_parseado)

        logger.info(f"Se obtuvieron {len(pools)} top pools en '{chain}'")
        return pools

    # ================================================================
    # COINGECKO DEMO API - Contexto de mercado (necesita API key)
    # ================================================================

    def _cg_get(self, endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
        """
        Hace una peticion GET a la API de CoinGecko Demo.

        Es un metodo privado (empieza con _) porque es interno.
        Los metodos publicos (get_coin_price_history, get_coin_info)
        usan este metodo internamente.

        A diferencia de _get() de BaseAPIClient, este metodo usa la sesion
        de CoinGecko con el header x-cg-demo-key para autenticacion.

        Args:
            endpoint: Ruta del endpoint (ej: "/coins/bitcoin/market_chart").
            params: Parametros de query string.

        Returns:
            Respuesta JSON como dict, o None si hay error.
        """
        url = f"{self._cg_base_url}{endpoint}"

        # Respetar el rate limiter (compartido con GeckoTerminal)
        self.rate_limiter.wait()

        try:
            respuesta = self._cg_session.get(
                url, params=params, timeout=self.timeout
            )
            self._call_count += 1

            # Verificar errores HTTP
            if respuesta.status_code == 429:
                logger.warning("CoinGecko Demo: Rate limited (429)")
                return None

            if respuesta.status_code == 404:
                logger.debug(f"CoinGecko Demo: No encontrado (404): {endpoint}")
                return None

            respuesta.raise_for_status()
            return respuesta.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"CoinGecko Demo: Error en {endpoint}: {e}")
            return None

    def get_coin_price_history(
        self, coin_id: str, days: int = 30
    ) -> Optional[dict]:
        """
        Obtiene el historial de precios de una criptomoneda.

        Usamos esto principalmente para BTC, ETH y SOL como
        contexto de mercado. Si el mercado general esta bajista,
        las memecoins suelen caer aun mas.

        Args:
            coin_id: ID de CoinGecko (ej: "bitcoin", "ethereum", "solana").
            days: Cantidad de dias de historial (max 365 para demo).

        Returns:
            Diccionario con listas de datos:
            - "prices": [[timestamp, precio], ...]
            - "market_caps": [[timestamp, market_cap], ...]
            - "total_volumes": [[timestamp, volumen], ...]
            Retorna None si hay error.

        Ejemplo:
            >>> historial = cliente.get_coin_price_history("bitcoin", days=7)
            >>> ultimo_precio = historial["prices"][-1][1]
            >>> print(f"Bitcoin: ${ultimo_precio:,.2f}")
        """
        logger.info(f"Obteniendo historial de precios de '{coin_id}' ({days} dias)")

        respuesta = self._cg_get(
            f"/coins/{coin_id}/market_chart",
            params={
                "vs_currency": "usd",
                "days": days,
            },
        )

        if not respuesta:
            logger.warning(f"No se obtuvo historial de '{coin_id}'")
            return None

        # La respuesta ya viene limpia: {prices: [...], market_caps: [...], ...}
        # Solo validamos que tenga las claves esperadas
        resultado = {
            "prices": respuesta.get("prices", []),
            "market_caps": respuesta.get("market_caps", []),
            "total_volumes": respuesta.get("total_volumes", []),
        }

        logger.info(
            f"Historial de '{coin_id}': {len(resultado['prices'])} puntos de precio"
        )
        return resultado

    def get_coin_info(self, coin_id: str) -> Optional[dict]:
        """
        Obtiene informacion detallada de una criptomoneda.

        Incluye descripcion, links, datos de mercado actuales, etc.
        Util para obtener el precio actual y market cap de BTC/ETH/SOL.

        Args:
            coin_id: ID de CoinGecko (ej: "bitcoin", "ethereum", "solana").

        Returns:
            Diccionario con datos limpios de la moneda:
            - id, symbol, name
            - current_price_usd
            - market_cap_usd
            - total_volume_usd
            - price_change_24h_pct
            - ath (all time high), atl (all time low)
            Retorna None si hay error.

        Ejemplo:
            >>> info = cliente.get_coin_info("ethereum")
            >>> print(f"ETH: ${info['current_price_usd']:,.2f}")
        """
        logger.info(f"Obteniendo info de moneda '{coin_id}'")

        respuesta = self._cg_get(f"/coins/{coin_id}")

        if not respuesta:
            logger.warning(f"No se obtuvo info de '{coin_id}'")
            return None

        # Extraer y limpiar los datos mas relevantes
        # La respuesta de CoinGecko es MUY extensa, asi que solo
        # extraemos lo que necesitamos
        market_data = respuesta.get("market_data", {})

        resultado = {
            "id": respuesta.get("id", ""),
            "symbol": respuesta.get("symbol", ""),
            "name": respuesta.get("name", ""),
            # Precios y metricas de mercado
            "current_price_usd": safe_float(
                market_data.get("current_price", {}).get("usd")
            ),
            "market_cap_usd": safe_float(
                market_data.get("market_cap", {}).get("usd")
            ),
            "total_volume_usd": safe_float(
                market_data.get("total_volume", {}).get("usd")
            ),
            # Cambios de precio
            "price_change_24h_pct": safe_float(
                market_data.get("price_change_percentage_24h")
            ),
            "price_change_7d_pct": safe_float(
                market_data.get("price_change_percentage_7d")
            ),
            "price_change_30d_pct": safe_float(
                market_data.get("price_change_percentage_30d")
            ),
            # ATH y ATL (maximos y minimos historicos)
            "ath_usd": safe_float(
                market_data.get("ath", {}).get("usd")
            ),
            "atl_usd": safe_float(
                market_data.get("atl", {}).get("usd")
            ),
        }

        logger.info(f"Info de '{coin_id}': precio=${resultado['current_price_usd']}")
        return resultado

    # ================================================================
    # COINGECKO DEMO API - Descubrimiento por categorias
    # ================================================================

    def get_category_coins(
        self, category: str, per_page: int = 250, page: int = 1
    ) -> list[dict]:
        """
        Obtiene coins de una categoria especifica de CoinGecko.

        Util para descubrir memecoins agrupadas por tematica:
        meme-token, dog-themed-coins, cat-themed-coins, etc.

        La API devuelve monedas con sus contract addresses por chain,
        lo que nos permite filtrar por cadenas soportadas (solana, ethereum, base).

        Args:
            category: Slug de la categoria en CoinGecko. Ejemplos:
                - "meme-token"
                - "dog-themed-coins"
                - "cat-themed-coins"
                - "frog-themed-coins"
                - "political-meme-coins"
            per_page: Resultados por pagina (max 250).
            page: Numero de pagina (empieza en 1).

        Returns:
            Lista de diccionarios con tokens descubiertos. Cada dict tiene:
            token_address, chain, name, symbol.
            Lista vacia si hay error.
        """
        logger.info(
            f"Obteniendo coins de categoria '{category}' (pagina {page})"
        )

        respuesta = self._cg_get(
            "/coins/markets",
            params={
                "vs_currency": "usd",
                "category": category,
                "per_page": per_page,
                "page": page,
            },
        )

        if not respuesta or not isinstance(respuesta, list):
            logger.warning(f"Sin resultados para categoria '{category}'")
            return []

        # Mapeo de platform IDs de CoinGecko a nuestras chains
        platform_map = {
            "solana": "solana",
            "ethereum": "ethereum",
            "base": "base",
        }

        tokens = []
        for coin in respuesta:
            # El campo "platforms" contiene las addresses por chain
            # Ejemplo: {"solana": "abc123...", "ethereum": "0xabc..."}
            platforms = coin.get("platforms", {}) or {}

            for platform_id, address in platforms.items():
                chain = platform_map.get(platform_id.lower())
                if chain and address:
                    tokens.append({
                        "token_address": address,
                        "chain": chain,
                        "name": coin.get("name", ""),
                        "symbol": (coin.get("symbol") or "").upper(),
                    })

        logger.info(
            f"Categoria '{category}': {len(tokens)} tokens en chains soportadas"
        )
        return tokens

    # ================================================================
    # METODO PRIVADO DE PARSEO
    # ================================================================

    def _parsear_pool(self, pool_raw: dict) -> Optional[dict]:
        """
        Convierte un pool crudo de GeckoTerminal a un diccionario limpio.

        GeckoTerminal devuelve los datos en un formato anidado:
        {
            "id": "solana_0xAbc...",
            "type": "pool",
            "attributes": {
                "name": "SOL / BONK",
                "address": "0xAbc...",
                "base_token_price_usd": "0.00001234",
                ...
            }
        }

        Este metodo extrae los campos utiles y los convierte a tipos
        de Python apropiados (float, int, etc.) para facilitar su uso.

        Args:
            pool_raw: Diccionario crudo de la respuesta de GeckoTerminal.

        Returns:
            Diccionario con datos limpios del pool, o None si el formato
            es invalido.
        """
        try:
            # Los datos reales estan dentro de "attributes"
            attrs = pool_raw.get("attributes", {})

            # Si no hay attributes, intentar usar el dict directamente
            # (por si la estructura es diferente)
            if not attrs:
                attrs = pool_raw

            # Extraer base_token_address de relationships
            # Formato: "solana_3i3DNgQ..." -> "3i3DNgQ..."
            rels = pool_raw.get("relationships", {})
            base_token_id = (
                rels.get("base_token", {})
                .get("data", {})
                .get("id", "")
            )
            # Quitar el prefijo "network_" para obtener solo la direccion
            base_token_address = (
                base_token_id.split("_", 1)[1]
                if "_" in base_token_id
                else ""
            )

            # Extraer DEX de relationships (ej: "pump-fun", "raydium")
            dex_id = (
                rels.get("dex", {})
                .get("data", {})
                .get("id", "")
            )

            return {
                # Identificadores basicos
                "pool_id": pool_raw.get("id", ""),
                "name": attrs.get("name", ""),
                "pool_address": attrs.get("address", ""),
                "base_token_address": base_token_address,
                "dex": dex_id,

                # Precios
                "price_usd": safe_float(attrs.get("base_token_price_usd")),
                "price_native": safe_float(
                    attrs.get("base_token_price_native_currency")
                ),

                # Volumen de trading en diferentes ventanas de tiempo
                "volume_5m": safe_float(
                    attrs.get("volume_usd", {}).get("m5")
                ),
                "volume_1h": safe_float(
                    attrs.get("volume_usd", {}).get("h1")
                ),
                "volume_6h": safe_float(
                    attrs.get("volume_usd", {}).get("h6")
                ),
                "volume_24h": safe_float(
                    attrs.get("volume_usd", {}).get("h24")
                ),

                # Cambios de precio porcentuales
                "price_change_5m": safe_float(
                    attrs.get("price_change_percentage", {}).get("m5")
                ),
                "price_change_1h": safe_float(
                    attrs.get("price_change_percentage", {}).get("h1")
                ),
                "price_change_6h": safe_float(
                    attrs.get("price_change_percentage", {}).get("h6")
                ),
                "price_change_24h": safe_float(
                    attrs.get("price_change_percentage", {}).get("h24")
                ),

                # Transacciones (compras y ventas)
                "txns_5m_buys": safe_int(
                    attrs.get("transactions", {}).get("m5", {}).get("buys")
                ),
                "txns_5m_sells": safe_int(
                    attrs.get("transactions", {}).get("m5", {}).get("sells")
                ),
                "txns_1h_buys": safe_int(
                    attrs.get("transactions", {}).get("h1", {}).get("buys")
                ),
                "txns_1h_sells": safe_int(
                    attrs.get("transactions", {}).get("h1", {}).get("sells")
                ),
                "txns_24h_buys": safe_int(
                    attrs.get("transactions", {}).get("h24", {}).get("buys")
                ),
                "txns_24h_sells": safe_int(
                    attrs.get("transactions", {}).get("h24", {}).get("sells")
                ),

                # Liquidez y valor de mercado
                "liquidity_usd": safe_float(
                    attrs.get("reserve_in_usd")
                ),
                "fdv_usd": safe_float(attrs.get("fdv_usd")),
                "market_cap_usd": safe_float(attrs.get("market_cap_usd")),

                # Fecha de creacion del pool
                "created_at": attrs.get("pool_created_at", ""),
            }

        except (AttributeError, TypeError) as e:
            # Si algo falla al parsear, loguear y devolver None
            logger.debug(f"Error parseando pool: {e}")
            return None
