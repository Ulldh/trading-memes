"""
dexscreener_client.py - Cliente para la API de DexScreener.

DexScreener es un agregador de datos de exchanges descentralizados (DEX).
Proporciona datos en tiempo real de pares de trading (tokens listados en
DEXes como Raydium, Uniswap, etc.).

Ventajas de DexScreener:
- No necesita autenticacion (API publica)
- Limite generoso: 300 llamadas por minuto
- Datos de multiples cadenas en una sola API
- Incluye perfiles de tokens (redes sociales, website)
- Sistema de "boost" que indica tokens promocionados

Usamos DexScreener como complemento a GeckoTerminal para:
- Verificar datos cruzados (si ambas APIs reportan lo mismo, mas confiable)
- Obtener datos de redes sociales y websites del token
- Detectar tokens "boosted" (que pagan por promocion)
- Obtener datos de transacciones detallados (compras/ventas por ventana)

Uso:
    from src.api.dexscreener_client import DexScreenerClient

    cliente = DexScreenerClient()

    # Buscar todos los pares de un token
    pares = cliente.get_token_pairs("solana", "DireccionDelToken123...")

    # Buscar pares por nombre
    resultados = cliente.search_pairs("PEPE")

    # Ver tokens actualmente "boosted" (promocionados)
    boosted = cliente.get_boosted_tokens()
"""

from typing import Optional

# Importamos la clase base que nos da rate limiting, cache y retries
from src.api.base_client import BaseAPIClient
from src.utils.logger import get_logger
from src.utils.helpers import safe_float, safe_int

# Importar configuracion
try:
    from config import API_URLS, RATE_LIMITS
except ImportError:
    API_URLS = {"dexscreener": "https://api.dexscreener.com"}
    RATE_LIMITS = {"dexscreener": 300}

# Logger para este modulo
logger = get_logger(__name__)


class DexScreenerClient(BaseAPIClient):
    """
    Cliente para la API de DexScreener.

    Hereda de BaseAPIClient, lo que significa que tiene automaticamente:
    - Rate limiting (no excede 300 calls/min)
    - Reintentos con backoff exponencial
    - Cache en disco
    - Guardado de respuestas crudas

    La API de DexScreener no necesita autenticacion.

    Ejemplo:
        >>> cliente = DexScreenerClient()
        >>> pares = cliente.get_token_pairs("solana", "DireccionToken...")
        >>> print(pares[0]["price_usd"])
    """

    def __init__(self):
        # Inicializar la clase base con la URL y rate limit de DexScreener
        super().__init__(
            base_url=API_URLS.get("dexscreener", "https://api.dexscreener.com"),
            name="dexscreener",
            calls_per_minute=RATE_LIMITS.get("dexscreener", 300),
        )

        logger.info("DexScreenerClient inicializado")

    # ================================================================
    # ENDPOINTS PUBLICOS
    # ================================================================

    def get_token_pairs(self, chain: str, token_address: str) -> list[dict]:
        """
        Obtiene todos los pares de trading donde aparece un token.

        Un token puede tener multiples pares. Por ejemplo, BONK puede
        tener pares: BONK/SOL, BONK/USDC, BONK/USDT.
        El par con mayor liquidez suele ser el mas confiable para precios.

        Args:
            chain: Cadena blockchain (ej: "solana", "ethereum", "base").
            token_address: Direccion del contrato del token.

        Returns:
            Lista de diccionarios con datos de cada par.
            Cada dict contiene: price_usd, volume_24h, liquidity_usd,
            price_changes, txns (transacciones), etc.
            Lista vacia si hay error o el token no existe.

        Ejemplo:
            >>> pares = cliente.get_token_pairs("solana", "0xAbc...")
            >>> for par in pares:
            ...     print(par["pair_name"], par["price_usd"])
        """
        logger.info(
            f"Obteniendo pares del token {token_address[:10]}... en '{chain}'"
        )

        # DexScreener usa /tokens/v1/{chain}/{address}
        respuesta = self._get(f"/tokens/v1/{chain}/{token_address}")

        # La respuesta es directamente una lista de pares (no envuelta en "data")
        if not respuesta:
            logger.warning(
                f"No se encontraron pares para {token_address[:10]}... en '{chain}'"
            )
            return []

        # DexScreener devuelve una lista directamente en este endpoint
        # Si es un dict con clave "pairs", extraemos de ahi
        pares_raw = respuesta if isinstance(respuesta, list) else []

        # Parsear cada par
        pares_limpios = []
        for par_raw in pares_raw:
            par_parseado = self._parsear_par(par_raw)
            if par_parseado:
                pares_limpios.append(par_parseado)

        logger.info(
            f"Token {token_address[:10]}...: "
            f"{len(pares_limpios)} pares encontrados"
        )
        return pares_limpios

    def get_pair_info(self, chain: str, pair_address: str) -> Optional[dict]:
        """
        Obtiene informacion detallada de un par de trading especifico.

        A diferencia de get_token_pairs (que busca por token), este
        endpoint busca por la direccion del par/pool directamente.

        Args:
            chain: Cadena blockchain (ej: "solana", "ethereum", "base").
            pair_address: Direccion del par/pool.

        Returns:
            Diccionario con datos del par, o None si no se encontro.

        Ejemplo:
            >>> par = cliente.get_pair_info("solana", "0xPoolAddress...")
            >>> if par:
            ...     print(f"Precio: ${par['price_usd']}")
        """
        logger.info(
            f"Obteniendo info del par {pair_address[:10]}... en '{chain}'"
        )

        respuesta = self._get(f"/pairs/v1/{chain}/{pair_address}")

        if not respuesta:
            logger.warning(f"No se encontro el par {pair_address[:10]}...")
            return None

        # La respuesta puede ser una lista con un solo elemento o un dict
        if isinstance(respuesta, list):
            if len(respuesta) == 0:
                return None
            return self._parsear_par(respuesta[0])

        return self._parsear_par(respuesta)

    def search_pairs(self, query: str) -> list[dict]:
        """
        Busca pares de trading por nombre, simbolo o direccion.

        Util para encontrar rapidamente un token cuando solo conocemos
        su nombre o ticker (ej: "PEPE", "BONK", "WIF").

        Args:
            query: Texto de busqueda (nombre, simbolo o direccion).

        Returns:
            Lista de diccionarios con los pares que coinciden.
            Lista vacia si no hay resultados.

        Ejemplo:
            >>> resultados = cliente.search_pairs("BONK")
            >>> for r in resultados[:5]:
            ...     print(r["pair_name"], r["chain"], r["price_usd"])
        """
        logger.info(f"Buscando pares con query: '{query}'")

        # El endpoint de busqueda es diferente a los demas
        # Usa el prefijo /latest/dex/search
        respuesta = self._get(
            "/latest/dex/search",
            params={"q": query},
        )

        if not respuesta or "pairs" not in respuesta:
            logger.warning(f"Sin resultados para busqueda: '{query}'")
            return []

        # La respuesta de busqueda envuelve los pares en {"pairs": [...]}
        resultados = []
        for par_raw in respuesta["pairs"]:
            par_parseado = self._parsear_par(par_raw)
            if par_parseado:
                resultados.append(par_parseado)

        logger.info(f"Busqueda '{query}': {len(resultados)} resultados")
        return resultados

    def get_token_profiles(self) -> list[dict]:
        """
        Obtiene los perfiles de tokens mas recientes.

        Los perfiles incluyen informacion extra como website, redes
        sociales, y si el token ha sido "boosted" (promocionado).

        Un token con perfil completo (website, Twitter, Telegram)
        tiende a ser mas confiable que uno sin ninguna info.

        Returns:
            Lista de diccionarios con perfiles de tokens.
            Cada dict tiene: url, chainId, tokenAddress, icon,
            description, links (redes sociales), etc.
            Lista vacia si hay error.

        Ejemplo:
            >>> perfiles = cliente.get_token_profiles()
            >>> for p in perfiles[:5]:
            ...     print(p.get("token_address"), p.get("description"))
        """
        logger.info("Obteniendo perfiles de tokens recientes")

        respuesta = self._get("/token-profiles/latest/v1")

        if not respuesta:
            logger.warning("No se obtuvieron perfiles de tokens")
            return []

        # La respuesta es directamente una lista de perfiles
        perfiles_raw = respuesta if isinstance(respuesta, list) else []

        # Parsear cada perfil
        perfiles = []
        for perfil_raw in perfiles_raw:
            perfil = self._parsear_perfil(perfil_raw)
            if perfil:
                perfiles.append(perfil)

        logger.info(f"Se obtuvieron {len(perfiles)} perfiles de tokens")
        return perfiles

    def get_boosted_tokens(self) -> list[dict]:
        """
        Obtiene los tokens actualmente "boosted" (promocionados).

        En DexScreener, los creadores de tokens pueden pagar para
        "boostear" su token, lo que le da mas visibilidad.

        ATENCION: Un token boosted NO significa que sea bueno.
        De hecho, muchos scams pagan por boost para atraer victimas.
        Usamos este dato como una feature mas, no como senal de compra.

        Returns:
            Lista de diccionarios con tokens boosted.
            Cada dict tiene: token_address, chain, amount (de boost),
            total_amount, icon, description, links, etc.
            Lista vacia si hay error.

        Ejemplo:
            >>> boosted = cliente.get_boosted_tokens()
            >>> for t in boosted[:3]:
            ...     print(t.get("token_address"), t.get("amount"))
        """
        logger.info("Obteniendo tokens boosted")

        respuesta = self._get("/token-boosts/latest/v1")

        if not respuesta:
            logger.warning("No se obtuvieron tokens boosted")
            return []

        # La respuesta es directamente una lista
        tokens_raw = respuesta if isinstance(respuesta, list) else []

        tokens = []
        for token_raw in tokens_raw:
            token = self._parsear_perfil(token_raw)
            if token:
                tokens.append(token)

        logger.info(f"Se obtuvieron {len(tokens)} tokens boosted")
        return tokens

    # ================================================================
    # METODOS PRIVADOS DE PARSEO
    # ================================================================

    def _parsear_par(self, par_raw: dict) -> Optional[dict]:
        """
        Convierte un par crudo de DexScreener a un diccionario limpio.

        DexScreener devuelve datos en un formato plano (no anidado como
        GeckoTerminal), lo que facilita el parseo. Sin embargo, algunos
        campos son opcionales y pueden no estar presentes.

        Campos clave que extraemos:
        - Precio y cambios de precio en ventanas de tiempo
        - Volumen en ventanas de tiempo
        - Liquidez en USD
        - FDV y market cap
        - Transacciones (compras y ventas por ventana)
        - Fecha de creacion del par
        - Info del token (website, redes sociales)

        Args:
            par_raw: Diccionario crudo de la respuesta de DexScreener.

        Returns:
            Diccionario limpio con datos del par, o None si es invalido.
        """
        try:
            # Extraer datos de precio en diferentes ventanas de tiempo
            # DexScreener usa "priceChange" con sub-claves m5, h1, h6, h24
            price_change = par_raw.get("priceChange", {}) or {}

            # Extraer datos de volumen por ventana de tiempo
            volume = par_raw.get("volume", {}) or {}

            # Extraer datos de liquidez
            liquidity = par_raw.get("liquidity", {}) or {}

            # Extraer transacciones (compras y ventas)
            # Formato: {"m5": {"buys": 10, "sells": 5}, "h1": {...}, ...}
            txns = par_raw.get("txns", {}) or {}

            # Extraer informacion del token (website, socials, etc.)
            info = par_raw.get("info", {}) or {}

            # Extraer datos de los tokens del par (base y quote)
            base_token = par_raw.get("baseToken", {}) or {}
            quote_token = par_raw.get("quoteToken", {}) or {}

            return {
                # Identificadores del par
                "pair_address": par_raw.get("pairAddress", ""),
                "pair_name": (
                    f"{base_token.get('symbol', '?')}"
                    f"/{quote_token.get('symbol', '?')}"
                ),
                "chain": par_raw.get("chainId", ""),
                "dex": par_raw.get("dexId", ""),

                # Datos del token base (el memecoin que nos interesa)
                "base_token_address": base_token.get("address", ""),
                "base_token_name": base_token.get("name", ""),
                "base_token_symbol": base_token.get("symbol", ""),

                # Datos del token quote (SOL, ETH, USDC, etc.)
                "quote_token_address": quote_token.get("address", ""),
                "quote_token_symbol": quote_token.get("symbol", ""),

                # Precio actual
                "price_usd": safe_float(par_raw.get("priceUsd")),
                "price_native": safe_float(par_raw.get("priceNative")),

                # Cambios de precio porcentuales
                "price_change_5m": safe_float(price_change.get("m5")),
                "price_change_1h": safe_float(price_change.get("h1")),
                "price_change_6h": safe_float(price_change.get("h6")),
                "price_change_24h": safe_float(price_change.get("h24")),

                # Volumen en USD por ventana de tiempo
                "volume_5m": safe_float(volume.get("m5")),
                "volume_1h": safe_float(volume.get("h1")),
                "volume_6h": safe_float(volume.get("h6")),
                "volume_24h": safe_float(volume.get("h24")),

                # Liquidez disponible en el pool
                "liquidity_usd": safe_float(liquidity.get("usd")),
                "liquidity_base": safe_float(liquidity.get("base")),
                "liquidity_quote": safe_float(liquidity.get("quote")),

                # Valor de mercado
                "fdv": safe_float(par_raw.get("fdv")),
                "market_cap": safe_float(par_raw.get("marketCap")),

                # Transacciones (compras y ventas) por ventana
                # Esto es MUY util: si hay muchas mas compras que ventas,
                # indica demanda. Si hay mas ventas, indica presion bajista.
                "txns_5m_buys": safe_int(
                    txns.get("m5", {}).get("buys")
                ),
                "txns_5m_sells": safe_int(
                    txns.get("m5", {}).get("sells")
                ),
                "txns_1h_buys": safe_int(
                    txns.get("h1", {}).get("buys")
                ),
                "txns_1h_sells": safe_int(
                    txns.get("h1", {}).get("sells")
                ),
                "txns_6h_buys": safe_int(
                    txns.get("h6", {}).get("buys")
                ),
                "txns_6h_sells": safe_int(
                    txns.get("h6", {}).get("sells")
                ),
                "txns_24h_buys": safe_int(
                    txns.get("h24", {}).get("buys")
                ),
                "txns_24h_sells": safe_int(
                    txns.get("h24", {}).get("sells")
                ),

                # Fecha de creacion del par (timestamp en milisegundos)
                "pair_created_at": par_raw.get("pairCreatedAt"),

                # Informacion del token (redes sociales, website)
                # Util para evaluar legitimidad del proyecto
                "websites": info.get("websites", []),
                "socials": info.get("socials", []),
                "image_url": info.get("imageUrl", ""),
            }

        except (AttributeError, TypeError) as e:
            # Si algo falla al parsear, loguear y devolver None
            logger.debug(f"Error parseando par de DexScreener: {e}")
            return None

    def _parsear_perfil(self, perfil_raw: dict) -> Optional[dict]:
        """
        Convierte un perfil/boost crudo de DexScreener a un dict limpio.

        Los perfiles y boosts tienen una estructura similar, por eso
        usamos el mismo metodo de parseo para ambos.

        Args:
            perfil_raw: Diccionario crudo del perfil o boost.

        Returns:
            Diccionario limpio con datos del perfil, o None si invalido.
        """
        try:
            return {
                "url": perfil_raw.get("url", ""),
                "chain": perfil_raw.get("chainId", ""),
                "token_address": perfil_raw.get("tokenAddress", ""),
                "icon": perfil_raw.get("icon", ""),
                "header": perfil_raw.get("header", ""),
                "description": perfil_raw.get("description", ""),
                "links": perfil_raw.get("links", []),
                # Campos especificos de boosts
                "amount": safe_float(perfil_raw.get("amount")),
                "total_amount": safe_float(perfil_raw.get("totalAmount")),
            }
        except (AttributeError, TypeError) as e:
            logger.debug(f"Error parseando perfil de DexScreener: {e}")
            return None
