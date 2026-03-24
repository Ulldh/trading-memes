"""
solana_discovery_client.py - Cliente para fuentes de descubrimiento en Solana.

Agrupa 3 fuentes de tokens de Solana:
  1. Pump.fun (API no oficial) - Tokens recien lanzados y top por market cap
  2. Jupiter Token List - Tokens verificados en el DEX Jupiter
  3. Raydium Token List - Tokens listados en Raydium

Estas fuentes complementan a GeckoTerminal y DexScreener para descubrir
tokens que aun no aparecen en los agregadores principales.

NOTA: Pump.fun tiene una API no oficial que puede cambiar sin aviso.
Por eso implementamos un circuit breaker que desactiva la fuente tras
3 fallos consecutivos, evitando perder tiempo con una API rota.

Uso:
    from src.api.solana_discovery_client import SolanaDiscoveryClient

    cliente = SolanaDiscoveryClient()

    # Tokens recientes de Pump.fun
    nuevos = cliente.get_pumpfun_latest(limit=50)

    # Tokens top por market cap en Pump.fun
    top = cliente.get_pumpfun_top(limit=50)

    # Lista completa de tokens verificados en Jupiter
    jupiter = cliente.get_jupiter_tokens()

    # Lista de tokens en Raydium
    raydium = cliente.get_raydium_tokens()
"""

import os
import time
from typing import Optional

from src.api.base_client import BaseAPIClient
from src.utils.logger import get_logger
from src.utils.helpers import safe_float

# Importar configuracion
try:
    from config import API_URLS, RATE_LIMITS
except ImportError:
    API_URLS = {
        "pumpfun": "https://frontend-api-v3.pump.fun",
        "jupiter": "https://lite-api.jup.ag/tokens/v1",
        "raydium": "https://api-v3.raydium.io",
    }
    RATE_LIMITS = {"pumpfun": 30, "jupiter": 60, "raydium": 60}

logger = get_logger(__name__)


class SolanaDiscoveryClient(BaseAPIClient):
    """
    Cliente para descubrimiento de tokens en Solana desde multiples fuentes.

    Hereda de BaseAPIClient para reusar rate limiting, retries y cache.
    La base URL apunta a Pump.fun como fuente principal, y Jupiter/Raydium
    se llaman directamente con self.session (JSON estatico).

    El circuit breaker de Pump.fun se activa tras 3 fallos consecutivos
    y desactiva esa fuente para evitar esperas innecesarias.
    """

    def __init__(self):
        # Inicializar con Pump.fun como base (tiene rate limiting propio)
        super().__init__(
            base_url=API_URLS.get("pumpfun", "https://frontend-api-v3.pump.fun"),
            name="pumpfun",
            calls_per_minute=RATE_LIMITS.get("pumpfun", 30),
        )

        # URLs de Jupiter y Raydium (JSON estatico, no necesitan BaseAPIClient)
        self._jupiter_url = API_URLS.get("jupiter", "https://tokens.jup.ag")
        self._raydium_url = API_URLS.get("raydium", "https://api-v3.raydium.io")

        # Circuit breaker para Pump.fun (API no oficial)
        self._pumpfun_failures = 0
        self._pumpfun_circuit_open = False
        self._pumpfun_max_failures = 3

        logger.info("SolanaDiscoveryClient inicializado (Pump.fun + Jupiter + Raydium)")

    # ================================================================
    # PUMP.FUN - API no oficial (con circuit breaker)
    # ================================================================

    def get_pumpfun_latest(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """
        Obtiene los tokens mas recientes de Pump.fun.

        Pump.fun es el launcher de memecoins mas popular de Solana.
        Cada dia se lanzan cientos de tokens aqui. Los tokens mas nuevos
        suelen tener alta volatilidad y potencial de ser "gems".

        NOTA: API no oficial. Si falla 3 veces, se desactiva automaticamente.

        Args:
            limit: Cantidad de tokens a obtener (max 50 por pagina).
            offset: Offset para paginacion.

        Returns:
            Lista de diccionarios con tokens. Cada dict tiene:
            token_address, chain ("solana"), name, symbol, dex ("pump-fun").
            Lista vacia si circuit breaker esta abierto o hay error.
        """
        if self._pumpfun_circuit_open:
            logger.debug("Pump.fun circuit breaker abierto, saltando")
            return []

        logger.info(f"Obteniendo tokens recientes de Pump.fun (limit={limit}, offset={offset})")

        respuesta = self._pumpfun_request(
            "/coins",
            params={
                "sort": "created_timestamp",
                "order": "DESC",
                "limit": limit,
                "offset": offset,
                "includeNsfw": "false",
            },
        )

        if respuesta is None:
            return []

        # Parsear cada token
        tokens = []
        items = respuesta if isinstance(respuesta, list) else []
        for coin in items:
            parsed = self._parsear_pumpfun_coin(coin)
            if parsed:
                tokens.append(parsed)

        logger.info(f"Pump.fun latest: {len(tokens)} tokens obtenidos")
        return tokens

    def get_pumpfun_top(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """
        Obtiene los tokens top por market cap de Pump.fun.

        Estos son los tokens de Pump.fun que han logrado mayor traccion.
        Suelen ser mas estables que los recien lanzados.

        Args:
            limit: Cantidad de tokens a obtener.
            offset: Offset para paginacion.

        Returns:
            Lista de diccionarios con tokens.
            Lista vacia si circuit breaker esta abierto o hay error.
        """
        if self._pumpfun_circuit_open:
            logger.debug("Pump.fun circuit breaker abierto, saltando")
            return []

        logger.info(f"Obteniendo top tokens de Pump.fun (limit={limit}, offset={offset})")

        respuesta = self._pumpfun_request(
            "/coins",
            params={
                "sort": "market_cap",
                "order": "DESC",
                "limit": limit,
                "offset": offset,
                "includeNsfw": "false",
            },
        )

        if respuesta is None:
            return []

        tokens = []
        items = respuesta if isinstance(respuesta, list) else []
        for coin in items:
            parsed = self._parsear_pumpfun_coin(coin)
            if parsed:
                tokens.append(parsed)

        logger.info(f"Pump.fun top: {len(tokens)} tokens obtenidos")
        return tokens

    def _pumpfun_request(self, endpoint: str, params: Optional[dict] = None) -> Optional[list]:
        """
        Hace una peticion a Pump.fun con circuit breaker.

        Si la peticion falla, incrementa el contador de fallos.
        Tras 3 fallos consecutivos, abre el circuit breaker y
        todas las peticiones siguientes retornan None inmediatamente.

        Un exito resetea el contador de fallos.
        """
        try:
            respuesta = self._get(endpoint, params=params, use_cache=False)

            if respuesta is not None:
                # Exito: resetear contador de fallos
                self._pumpfun_failures = 0
                return respuesta

            # Respuesta None pero sin excepcion (404, etc.)
            self._pumpfun_failures += 1

        except Exception as e:
            logger.warning(f"Pump.fun error: {e}")
            self._pumpfun_failures += 1

        # Verificar circuit breaker
        if self._pumpfun_failures >= self._pumpfun_max_failures:
            self._pumpfun_circuit_open = True
            logger.warning(
                f"Pump.fun circuit breaker ABIERTO tras "
                f"{self._pumpfun_failures} fallos consecutivos"
            )

        return None

    def _parsear_pumpfun_coin(self, coin: dict) -> Optional[dict]:
        """
        Convierte un token de Pump.fun al formato estandar.

        La API de Pump.fun devuelve:
        - mint: direccion del token (equivale a token_address)
        - name, symbol: nombre y ticker
        - market_cap: market cap en USD
        - created_timestamp: timestamp de creacion en ms
        """
        try:
            mint = coin.get("mint", "")
            if not mint:
                return None

            return {
                "token_address": mint,
                "chain": "solana",
                "name": coin.get("name", ""),
                "symbol": (coin.get("symbol") or "").upper(),
                "dex": "pump-fun",
                "market_cap": safe_float(coin.get("market_cap")),
            }

        except (AttributeError, TypeError) as e:
            logger.debug(f"Error parseando token de Pump.fun: {e}")
            return None

    # ================================================================
    # PUMP.FUN - Descubrimiento historico (tokens antiguos)
    # ================================================================

    def get_pumpfun_historical(
        self,
        offset: int = 0,
        limit: int = 50,
        max_pages: int = 10,
    ) -> list[dict]:
        """
        Descubre tokens historicos de Pump.fun paginando con offset alto.

        A diferencia de get_pumpfun_latest (tokens nuevos), este metodo
        ordena por created_timestamp ASC para obtener tokens antiguos
        (3-6+ meses atras) que ya tienen historial OHLCV maduro.

        Args:
            offset: Offset inicial para empezar a paginar (ej: 5000).
            limit: Tokens por pagina (max 50 segun Pump.fun API).
            max_pages: Paginas maximas a recorrer desde el offset.

        Returns:
            Lista acumulada de tokens historicos. Cada dict tiene:
            token_address, chain, name, symbol, dex, market_cap.
            Lista vacia si circuit breaker abierto o error.
        """
        if self._pumpfun_circuit_open:
            logger.debug("Pump.fun circuit breaker abierto, saltando historicos")
            return []

        logger.info(
            f"Descubriendo tokens historicos de Pump.fun "
            f"(offset={offset}, limit={limit}, max_pages={max_pages})"
        )

        all_tokens = []
        current_offset = offset

        for page in range(max_pages):
            respuesta = self._pumpfun_request(
                "/coins",
                params={
                    "sort": "created_timestamp",
                    "order": "ASC",
                    "limit": limit,
                    "offset": current_offset,
                    "includeNsfw": "false",
                },
            )

            if respuesta is None:
                logger.warning(f"Pump.fun historicos: respuesta None en offset={current_offset}")
                break

            items = respuesta if isinstance(respuesta, list) else []
            if not items:
                logger.info(f"Pump.fun historicos: sin mas tokens en offset={current_offset}")
                break

            for coin in items:
                parsed = self._parsear_pumpfun_coin(coin)
                if parsed:
                    all_tokens.append(parsed)

            current_offset += limit
            logger.info(
                f"Pump.fun historicos pagina {page + 1}/{max_pages}: "
                f"{len(items)} tokens (acumulado: {len(all_tokens)})"
            )

        logger.info(f"Pump.fun historicos: {len(all_tokens)} tokens descubiertos total")
        return all_tokens

    # ================================================================
    # JUPITER TOKEN LIST (JSON estatico)
    # ================================================================

    def get_jupiter_tokens(self) -> list[dict]:
        """
        Obtiene la lista de tokens verificados de Jupiter.

        Jupiter es el agregador de DEXes mas usado de Solana.
        Su token list incluye tokens que han pasado verificacion basica.

        NOTA (2026-03): Jupiter migro a v2 API con API key obligatoria.
        La v1 gratuita fue desactivada. Si no hay JUPITER_API_KEY en .env,
        esta fuente queda deshabilitada y retorna lista vacia.

        Para obtener API key gratuita: https://portal.jup.ag

        Returns:
            Lista de diccionarios con tokens. Cada dict tiene:
            token_address, chain ("solana"), name, symbol.
            Lista vacia si hay error o no hay API key.
        """
        logger.info("Obteniendo token list de Jupiter")

        # V2 API requiere API key (generar gratis en portal.jup.ag)
        api_key = os.environ.get("JUPITER_API_KEY", "")
        if not api_key:
            logger.warning(
                "Jupiter API key no configurada. "
                "La v1 gratuita fue desactivada (2026-03). "
                "Genera una key gratis en https://portal.jup.ag y "
                "agrega JUPITER_API_KEY al .env"
            )
            return []

        url = "https://api.jup.ag/tokens/v2/mints/tradable"

        try:
            respuesta = self.session.get(
                url,
                headers={"x-api-key": api_key},
                timeout=30,
            )

            if respuesta.status_code != 200:
                logger.warning(f"Jupiter API retorno {respuesta.status_code}")
                return []

            data = respuesta.json()

            # La respuesta es una lista directa de tokens
            items = data if isinstance(data, list) else []

            tokens = []
            for item in items:
                address = item.get("address", "")
                if not address:
                    continue

                tokens.append({
                    "token_address": address,
                    "chain": "solana",
                    "name": item.get("name", ""),
                    "symbol": (item.get("symbol") or "").upper(),
                })

            logger.info(f"Jupiter: {len(tokens)} tokens verificados obtenidos")
            return tokens

        except Exception as e:
            logger.warning(f"Error obteniendo tokens de Jupiter: {e}")
            return []

    # ================================================================
    # RAYDIUM TOKEN LIST (JSON estatico)
    # ================================================================

    def get_raydium_tokens(self) -> list[dict]:
        """
        Obtiene la lista de tokens de Raydium.

        Raydium es el DEX principal de Solana (antes de Jupiter).
        Su lista de tokens incluye tokens que tienen pools activos.

        Returns:
            Lista de diccionarios con tokens. Cada dict tiene:
            token_address, chain ("solana"), name, symbol.
            Lista vacia si hay error.
        """
        logger.info("Obteniendo token list de Raydium")

        url = f"{self._raydium_url}/mint/list"

        try:
            respuesta = self.session.get(url, timeout=30)

            if respuesta.status_code != 200:
                logger.warning(f"Raydium API retorno {respuesta.status_code}")
                return []

            data = respuesta.json()

            # Raydium puede envolver los datos en {"data": {"mintList": [...]}}
            # o directamente como lista, dependiendo de la version
            if isinstance(data, dict):
                items = (
                    data.get("data", {}).get("mintList", [])
                    or data.get("data", {}).get("data", [])
                    or data.get("data", [])
                    or []
                )
            elif isinstance(data, list):
                items = data
            else:
                items = []

            tokens = []
            for item in items:
                # Raydium usa "address" o "mint" segun el endpoint
                address = ""
                if isinstance(item, dict):
                    address = item.get("address") or item.get("mint", "")
                elif isinstance(item, str):
                    # A veces la lista es directamente de strings (addresses)
                    address = item

                if not address:
                    continue

                name = item.get("name", "") if isinstance(item, dict) else ""
                symbol = item.get("symbol", "") if isinstance(item, dict) else ""

                tokens.append({
                    "token_address": address,
                    "chain": "solana",
                    "name": name,
                    "symbol": (symbol or "").upper(),
                })

            logger.info(f"Raydium: {len(tokens)} tokens obtenidos")
            return tokens

        except Exception as e:
            logger.warning(f"Error obteniendo tokens de Raydium: {e}")
            return []
