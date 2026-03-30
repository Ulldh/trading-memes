"""
birdeye_client.py - Cliente para la API de Birdeye (multi-chain).

Birdeye proporciona datos historicos completos para tokens en Solana,
Ethereum y Base, desde su creacion. Clave para backfill de datos,
ya que GeckoTerminal solo da las ultimas 30 velas diarias.

Endpoints disponibles:
    GET /defi/ohlcv              — Velas OHLCV para un token
    GET /defi/token_overview     — Precio, volumen, liquidez, mcap, holders
    GET /defi/token_security     — Seguridad: mint authority, freeze, top10%
    GET /defi/token_creation_info — Fecha y creador del token
    GET /defi/v3/token/holder    — Top holders con porcentajes
    GET /defi/v2/tokens-new_listing — Tokens recien listados
    GET /defi/v3/token/meme-list — Lista de meme tokens
    GET /defi/v3/token/trade-data-single — Datos de trading (buys/sells)

Cadenas soportadas: solana, ethereum, base.

Tiers de API:
    - Free: 1 rps (60 calls/min), sin costo
    - Lite: 15 rps (900 calls/min), $39/mes
    - Pro: 50 rps, $99/mes

Autenticacion:
    Header X-API-KEY con la key obtenida en https://bds.birdeye.so

Uso:
    from src.api.birdeye_client import BirdeyeClient

    client = BirdeyeClient()

    # OHLCV diario de un token Solana (ultimos 90 dias)
    ohlcv = client.get_token_ohlcv(
        address="TokenAddress123...",
        time_from=1700000000,
        time_to=1707776000,
        timeframe="1D",
    )

    # Overview de un token en Ethereum
    overview = client.get_token_overview(
        address="0x1234...",
        chain="ethereum",
    )

    # Seguridad de un token en Base
    security = client.get_token_security(
        address="0xabcd...",
        chain="base",
    )
"""

from datetime import datetime, timezone
from typing import Optional

from src.api.base_client import BaseAPIClient
from src.utils.helpers import safe_float
from src.utils.logger import get_logger

try:
    from config import API_URLS, RATE_LIMITS, BIRDEYE_API_KEY
except ImportError:
    API_URLS = {"birdeye": "https://public-api.birdeye.so"}
    RATE_LIMITS = {"birdeye": 900}
    BIRDEYE_API_KEY = ""

logger = get_logger(__name__)

# Cadenas soportadas por Birdeye y su nombre en el header x-chain
SUPPORTED_CHAINS = {
    "solana": "solana",
    "ethereum": "ethereum",
    "base": "base",
}


class BirdeyeClient(BaseAPIClient):
    """
    Cliente para Birdeye API (datos de tokens multi-chain).

    Hereda de BaseAPIClient para reusar rate limiting, retries y cache.
    Requiere BIRDEYE_API_KEY en .env para funcionar.

    Cadenas soportadas: solana, ethereum, base.

    Timeframes soportados para OHLCV:
        1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 8H, 12H, 1D, 3D, 1W, 1M
    """

    def __init__(self):
        super().__init__(
            base_url=API_URLS.get("birdeye", "https://public-api.birdeye.so"),
            name="birdeye",
            calls_per_minute=RATE_LIMITS.get("birdeye", 900),
            cache_ttl_hours=168,  # 7 dias — datos historicos no cambian
        )

        self._api_key = BIRDEYE_API_KEY

        # Agregar header de autenticacion a la sesion
        if self._api_key:
            self.session.headers.update({
                "X-API-KEY": self._api_key,
            })
            logger.info("BirdeyeClient inicializado con API key")
        else:
            logger.warning(
                "BirdeyeClient sin API key. "
                "Obtener en https://bds.birdeye.so y agregar BIRDEYE_API_KEY al .env"
            )

    @property
    def is_available(self) -> bool:
        """True si hay API key configurada."""
        return bool(self._api_key)

    def _set_chain(self, chain: str) -> str:
        """
        Establece el header x-chain y valida la cadena.

        Args:
            chain: Nombre de la cadena ("solana", "ethereum", "base").

        Returns:
            Nombre validado de la cadena para el header.

        Raises:
            ValueError: Si la cadena no esta soportada.
        """
        chain_lower = chain.lower()
        if chain_lower not in SUPPORTED_CHAINS:
            raise ValueError(
                f"Cadena '{chain}' no soportada. "
                f"Opciones: {list(SUPPORTED_CHAINS.keys())}"
            )
        header_value = SUPPORTED_CHAINS[chain_lower]
        self.session.headers["x-chain"] = header_value
        return header_value

    def _extract_data(self, respuesta: Optional[dict], label: str) -> Optional[dict]:
        """
        Extrae el campo 'data' de una respuesta Birdeye estandar.

        Birdeye siempre responde con {"success": bool, "data": {...}}.
        Este helper valida el success y devuelve data.

        Args:
            respuesta: Respuesta cruda de la API.
            label: Etiqueta para logs (ej: "token_overview").

        Returns:
            El contenido de 'data', o None si hay error.
        """
        if not respuesta:
            return None

        if not respuesta.get("success"):
            logger.debug(f"Birdeye {label}: respuesta no exitosa")
            return None

        return respuesta.get("data")

    # ==================================================================
    # OHLCV (ya existentes, ahora con multi-chain real)
    # ==================================================================

    def get_token_ohlcv(
        self,
        address: str,
        time_from: int,
        time_to: int,
        timeframe: str = "1D",
        chain: str = "solana",
    ) -> list[dict]:
        """
        Obtiene velas OHLCV historicas para un token.

        Args:
            address: Direccion del contrato del token.
            time_from: Timestamp Unix (segundos) del inicio del rango.
            time_to: Timestamp Unix (segundos) del fin del rango.
            timeframe: Periodo de cada vela. Opciones:
                1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 8H, 12H, 1D, 3D, 1W, 1M.
                Para backfill historico, usar "1D" (velas diarias).
            chain: Cadena del token ("solana", "ethereum", "base").

        Returns:
            Lista de dicts con keys: timestamp (ISO), open, high, low, close, volume.
            Lista vacia si hay error o no hay API key.

        Ejemplo:
            >>> client = BirdeyeClient()
            >>> ohlcv = client.get_token_ohlcv(
            ...     address="So11111111111111111111111111111111111111112",
            ...     time_from=1700000000,
            ...     time_to=1707776000,
            ... )
            >>> len(ohlcv)
            90
        """
        if not self._api_key:
            logger.debug("Birdeye: sin API key, saltando")
            return []

        # Establecer cadena en el header x-chain
        self._set_chain(chain)

        respuesta = self._get(
            "/defi/ohlcv",
            params={
                "address": address,
                "type": timeframe,
                "time_from": time_from,
                "time_to": time_to,
            },
            use_cache=True,
        )

        if not respuesta:
            return []

        # Birdeye responde con {"success": true, "data": {"items": [...]}}
        if not respuesta.get("success"):
            logger.debug(f"Birdeye: respuesta no exitosa para {address[:10]}...")
            return []

        items = respuesta.get("data", {}).get("items", [])
        if not items:
            return []

        # Parsear cada vela al formato estandar del proyecto
        velas = []
        for item in items:
            ts_unix = item.get("unixTime", 0)
            if not ts_unix:
                continue

            ts_iso = datetime.fromtimestamp(ts_unix, tz=timezone.utc).isoformat()

            velas.append({
                "timestamp": ts_iso,
                "open": safe_float(item.get("o")),
                "high": safe_float(item.get("h")),
                "low": safe_float(item.get("l")),
                "close": safe_float(item.get("c")),
                "volume": safe_float(item.get("v")),
            })

        logger.debug(f"Birdeye: {len(velas)} velas para {address[:10]}... ({chain})")
        return velas

    def get_token_ohlcv_full(
        self,
        address: str,
        created_at_unix: int,
        days: int = 90,
        timeframe: str = "1D",
        chain: str = "solana",
    ) -> list[dict]:
        """
        Obtiene OHLCV completo desde la creacion del token.

        Metodo de conveniencia que calcula time_from y time_to
        automaticamente a partir de la fecha de creacion del token.

        Args:
            address: Direccion del token.
            created_at_unix: Timestamp Unix de creacion del token (segundos).
            days: Dias de datos a obtener desde la creacion (default 90).
            timeframe: Periodo de vela (default "1D").
            chain: Cadena del token ("solana", "ethereum", "base").

        Returns:
            Lista de dicts OHLCV, o lista vacia si hay error.
        """
        time_from = created_at_unix
        time_to = created_at_unix + (days * 86400)  # 86400 = segundos en un dia

        # No pedir datos del futuro
        now_unix = int(datetime.now(timezone.utc).timestamp())
        time_to = min(time_to, now_unix)

        return self.get_token_ohlcv(
            address=address,
            time_from=time_from,
            time_to=time_to,
            timeframe=timeframe,
            chain=chain,
        )

    # ==================================================================
    # TOKEN OVERVIEW — Precio, volumen, liquidez, mcap, holders
    # Reemplaza multiples llamadas a GeckoTerminal + DexScreener
    # ==================================================================

    def get_token_overview(
        self,
        address: str,
        chain: str = "solana",
    ) -> Optional[dict]:
        """
        Obtiene datos completos de un token: precio, volumen, liquidez, mcap, holders.

        Una sola llamada reemplaza varias a GeckoTerminal + DexScreener.
        Devuelve datos listos para feature engineering.

        Args:
            address: Direccion del contrato del token.
            chain: Cadena del token ("solana", "ethereum", "base").

        Returns:
            Dict con keys normalizadas:
                - price, price_change_24h, price_change_1h
                - volume_24h, volume_change_24h
                - liquidity, mc (market cap)
                - holder_count
                - buy_24h, sell_24h (conteo de transacciones)
                - unique_wallet_24h
                - trade_24h (total transacciones)
                - supply, decimals, symbol, name
            None si hay error o no hay API key.

        Ejemplo:
            >>> overview = client.get_token_overview("So111...", chain="solana")
            >>> overview["price"]
            0.00123
            >>> overview["holder_count"]
            4521
        """
        if not self._api_key:
            logger.debug("Birdeye: sin API key, saltando token_overview")
            return None

        self._set_chain(chain)

        respuesta = self._get(
            "/defi/token_overview",
            params={"address": address},
            use_cache=True,
        )

        data = self._extract_data(respuesta, "token_overview")
        if not data:
            return None

        # Normalizar campos a formato estandar del proyecto
        resultado = {
            "address": address,
            "chain": chain,
            "symbol": data.get("symbol"),
            "name": data.get("name"),
            "decimals": data.get("decimals"),
            "price": safe_float(data.get("price")),
            "price_change_1h": safe_float(data.get("priceChange1hPercent")),
            "price_change_4h": safe_float(data.get("priceChange4hPercent")),
            "price_change_6h": safe_float(data.get("priceChange6hPercent")),
            "price_change_8h": safe_float(data.get("priceChange8hPercent")),
            "price_change_12h": safe_float(data.get("priceChange12hPercent")),
            "price_change_24h": safe_float(data.get("priceChange24hPercent")),
            "volume_24h": safe_float(data.get("v24hUSD")),
            "volume_change_24h": safe_float(data.get("v24hChangePercent")),
            "liquidity": safe_float(data.get("liquidity")),
            "mc": safe_float(data.get("mc")),
            "holder_count": data.get("holder"),
            "buy_24h": data.get("buy24h"),
            "sell_24h": data.get("sell24h"),
            "unique_wallet_24h": data.get("uniqueWallet24h"),
            "trade_24h": data.get("trade24h"),
            "supply": safe_float(data.get("supply")),
        }

        logger.debug(
            f"Birdeye token_overview: {address[:10]}... ({chain}) "
            f"price={resultado['price']}, holders={resultado['holder_count']}"
        )
        return resultado

    # ==================================================================
    # TOKEN SECURITY — Deteccion de rugs
    # ==================================================================

    def get_token_security(
        self,
        address: str,
        chain: str = "solana",
    ) -> Optional[dict]:
        """
        Obtiene datos de seguridad del token para deteccion de rugs.

        Incluye: ownership renounced, mint authority, freeze authority,
        concentracion de top 10 holders, si es Token-2022, etc.

        Args:
            address: Direccion del contrato del token.
            chain: Cadena del token ("solana", "ethereum", "base").

        Returns:
            Dict con keys normalizadas:
                - owner_address, creator_address
                - owner_balance, owner_percentage
                - creation_tx, creation_slot, creation_time
                - mint_authority, freeze_authority (Solana)
                - is_token_2022 (Solana)
                - is_true_token (verificado por Birdeye)
                - top10_holder_percent, top10_holder_balance
                - total_supply
                - mutable_metadata (si los metadatos pueden cambiar)
            None si hay error o no hay API key.

        Ejemplo:
            >>> security = client.get_token_security("So111...", chain="solana")
            >>> security["top10_holder_percent"]
            42.5
            >>> security["mint_authority"]
            None  # Bueno: nadie puede mintear mas
        """
        if not self._api_key:
            logger.debug("Birdeye: sin API key, saltando token_security")
            return None

        self._set_chain(chain)

        respuesta = self._get(
            "/defi/token_security",
            params={"address": address},
            use_cache=True,
        )

        data = self._extract_data(respuesta, "token_security")
        if not data:
            return None

        # Normalizar campos a formato estandar
        resultado = {
            "address": address,
            "chain": chain,
            "owner_address": data.get("ownerAddress"),
            "creator_address": data.get("creatorAddress"),
            "owner_balance": safe_float(data.get("ownerBalance")),
            "owner_percentage": safe_float(data.get("ownerPercentage")),
            "creation_tx": data.get("creationTx"),
            "creation_slot": data.get("creationSlot"),
            "creation_time": data.get("creationTime"),
            "mint_authority": data.get("mintAuthority"),
            "freeze_authority": data.get("freezeAuthority"),
            "is_token_2022": data.get("isToken2022"),
            "is_true_token": data.get("isTrueToken"),
            "top10_holder_balance": safe_float(data.get("top10HolderBalance")),
            "top10_holder_percent": safe_float(data.get("top10HolderPercent")),
            "total_supply": safe_float(data.get("totalSupply")),
            "mutable_metadata": data.get("mutableMetadata"),
        }

        logger.debug(
            f"Birdeye token_security: {address[:10]}... ({chain}) "
            f"top10={resultado['top10_holder_percent']}%, "
            f"mint_auth={resultado['mint_authority']}"
        )
        return resultado

    # ==================================================================
    # TOKEN CREATION INFO — Fecha de creacion y creador
    # Rellena los 353 tokens con created_at faltante
    # ==================================================================

    def get_token_creation_info(
        self,
        address: str,
        chain: str = "solana",
    ) -> Optional[dict]:
        """
        Obtiene la fecha de creacion, creador y tx hash de un token.

        Util para rellenar tokens sin created_at en la DB (353 tokens).

        Args:
            address: Direccion del contrato del token.
            chain: Cadena del token ("solana", "ethereum", "base").

        Returns:
            Dict con keys normalizadas:
                - tx_hash: Hash de la transaccion de creacion.
                - creator_address: Direccion del creador.
                - created_at_unix: Timestamp Unix de creacion (segundos).
                - created_at_iso: Fecha ISO de creacion.
                - slot: Slot de Solana donde se creo (solo Solana).
                - block_number: Numero de bloque (EVM chains).
            None si hay error o no hay API key.

        Ejemplo:
            >>> info = client.get_token_creation_info("So111...", chain="solana")
            >>> info["created_at_iso"]
            '2024-11-15T10:23:45+00:00'
        """
        if not self._api_key:
            logger.debug("Birdeye: sin API key, saltando token_creation_info")
            return None

        self._set_chain(chain)

        respuesta = self._get(
            "/defi/token_creation_info",
            params={"address": address},
            use_cache=True,
        )

        data = self._extract_data(respuesta, "token_creation_info")
        if not data:
            return None

        # Parsear timestamp a ISO
        created_unix = data.get("blockUnixTime") or data.get("creationTime")
        created_iso = None
        if created_unix:
            try:
                created_iso = datetime.fromtimestamp(
                    int(created_unix), tz=timezone.utc
                ).isoformat()
            except (ValueError, OSError):
                pass

        resultado = {
            "address": address,
            "chain": chain,
            "tx_hash": data.get("txHash"),
            "creator_address": data.get("owner") or data.get("creatorAddress"),
            "created_at_unix": created_unix,
            "created_at_iso": created_iso,
            "slot": data.get("slot"),
            "block_number": data.get("blockNumber"),
        }

        logger.debug(
            f"Birdeye token_creation_info: {address[:10]}... ({chain}) "
            f"created={resultado['created_at_iso']}"
        )
        return resultado

    # ==================================================================
    # TOKEN HOLDERS — Top holders con porcentajes (multi-chain)
    # Actualmente solo Helius para Solana; esto habilita ETH y Base
    # ==================================================================

    def get_token_holder(
        self,
        address: str,
        chain: str = "solana",
        limit: int = 20,
    ) -> Optional[list[dict]]:
        """
        Obtiene los top holders de un token con sus porcentajes.

        Multi-chain: funciona para Solana, Ethereum y Base.
        (Actualmente Helius solo cubre Solana.)

        Args:
            address: Direccion del contrato del token.
            chain: Cadena del token ("solana", "ethereum", "base").
            limit: Cantidad de top holders a pedir (max 20, default 20).

        Returns:
            Lista de dicts, cada uno con:
                - wallet: Direccion del holder.
                - amount: Cantidad de tokens que tiene.
                - percentage: Porcentaje del supply total.
                - usd_value: Valor en USD (si disponible).
            None si hay error o no hay API key.

        Ejemplo:
            >>> holders = client.get_token_holder("0x1234...", chain="ethereum")
            >>> holders[0]["percentage"]
            15.2
        """
        if not self._api_key:
            logger.debug("Birdeye: sin API key, saltando token_holder")
            return None

        self._set_chain(chain)

        respuesta = self._get(
            "/defi/v3/token/holder",
            params={
                "address": address,
                "limit": min(limit, 20),  # API max es 20
            },
            use_cache=True,
        )

        data = self._extract_data(respuesta, "token_holder")
        if not data:
            return None

        items = data.get("items", [])
        if not items:
            return []

        # Normalizar cada holder
        holders = []
        for item in items:
            holders.append({
                "wallet": item.get("owner") or item.get("address"),
                "amount": safe_float(item.get("uiAmount") or item.get("amount")),
                "percentage": safe_float(item.get("percentage")),
                "usd_value": safe_float(item.get("valueUsd")),
            })

        logger.debug(
            f"Birdeye token_holder: {address[:10]}... ({chain}) "
            f"{len(holders)} holders"
        )
        return holders

    # ==================================================================
    # NEW LISTINGS — Tokens recien listados (descubrimiento)
    # ==================================================================

    def get_new_listings(
        self,
        chain: str = "solana",
        limit: int = 50,
    ) -> Optional[list[dict]]:
        """
        Obtiene tokens recien listados. Fuente de descubrimiento de memecoins nuevas.

        Args:
            chain: Cadena a consultar ("solana", "ethereum", "base").
            limit: Cantidad de tokens a pedir (max 50, default 50).

        Returns:
            Lista de dicts, cada uno con:
                - address: Direccion del contrato.
                - symbol, name: Identificadores del token.
                - price, liquidity, mc: Datos de mercado.
                - listed_at: Timestamp de cuando se listo.
            None si hay error o no hay API key.

        Ejemplo:
            >>> nuevos = client.get_new_listings(chain="solana", limit=20)
            >>> len(nuevos)
            20
        """
        if not self._api_key:
            logger.debug("Birdeye: sin API key, saltando new_listings")
            return None

        self._set_chain(chain)

        respuesta = self._get(
            "/defi/v2/tokens/new_listing",
            params={"limit": min(limit, 50)},
            use_cache=False,  # Sin cache: queremos datos frescos
        )

        data = self._extract_data(respuesta, "new_listings")
        if not data:
            return None

        items = data.get("items", data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = [items] if items else []

        tokens = []
        for item in items:
            tokens.append({
                "address": item.get("address"),
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "price": safe_float(item.get("price")),
                "liquidity": safe_float(item.get("liquidity")),
                "mc": safe_float(item.get("mc")),
                "volume_24h": safe_float(item.get("v24hUSD")),
                "listed_at": item.get("createdAt") or item.get("listedAt"),
                "chain": chain,
            })

        logger.debug(
            f"Birdeye new_listings: {len(tokens)} tokens nuevos ({chain})"
        )
        return tokens

    # ==================================================================
    # MEME LIST — Lista de meme tokens (directamente lo que buscamos)
    # ==================================================================

    def get_meme_list(
        self,
        chain: str = "solana",
        limit: int = 50,
    ) -> Optional[list[dict]]:
        """
        Obtiene una lista de meme tokens. Literalmente lo que buscamos.

        Args:
            chain: Cadena a consultar ("solana", "ethereum", "base").
            limit: Cantidad de tokens a pedir (max 50, default 50).

        Returns:
            Lista de dicts, cada uno con:
                - address: Direccion del contrato.
                - symbol, name: Identificadores del token.
                - price, liquidity, mc: Datos de mercado.
                - volume_24h: Volumen 24h en USD.
                - price_change_24h: Cambio de precio 24h.
            None si hay error o no hay API key.

        Ejemplo:
            >>> memes = client.get_meme_list(chain="solana", limit=30)
            >>> memes[0]["symbol"]
            'BONK'
        """
        if not self._api_key:
            logger.debug("Birdeye: sin API key, saltando meme_list")
            return None

        self._set_chain(chain)

        respuesta = self._get(
            "/defi/v3/token/meme-list",
            params={"limit": min(limit, 50)},
            use_cache=False,  # Sin cache: queremos datos frescos
        )

        data = self._extract_data(respuesta, "meme_list")
        if not data:
            return None

        items = data.get("items", data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = [items] if items else []

        tokens = []
        for item in items:
            tokens.append({
                "address": item.get("address"),
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "price": safe_float(item.get("price")),
                "liquidity": safe_float(item.get("liquidity")),
                "mc": safe_float(item.get("mc")),
                "volume_24h": safe_float(item.get("v24hUSD")),
                "price_change_24h": safe_float(item.get("priceChange24hPercent")),
                "chain": chain,
            })

        logger.debug(
            f"Birdeye meme_list: {len(tokens)} meme tokens ({chain})"
        )
        return tokens

    # ==================================================================
    # TRADE DATA — Datos de trading: buys, sells, traders unicos
    # Mejor fuente para features sociales/momentum que DexScreener
    # ==================================================================

    def get_token_trade_data(
        self,
        address: str,
        chain: str = "solana",
    ) -> Optional[dict]:
        """
        Obtiene datos de trading de un token: compras, ventas, traders unicos.

        Mejor fuente para features sociales y momentum que DexScreener.
        Incluye datos de 30m, 1h, 2h, 4h, 8h, 24h.

        Args:
            address: Direccion del contrato del token.
            chain: Cadena del token ("solana", "ethereum", "base").

        Returns:
            Dict con keys normalizadas para varios periodos:
                - buy_30m, sell_30m, unique_wallets_30m
                - buy_1h, sell_1h, unique_wallets_1h
                - buy_2h, sell_2h, unique_wallets_2h
                - buy_4h, sell_4h, unique_wallets_4h
                - buy_8h, sell_8h, unique_wallets_8h
                - buy_24h, sell_24h, unique_wallets_24h
                - volume_buy_24h, volume_sell_24h (en USD)
                - trade_24h (total transacciones)
            None si hay error o no hay API key.

        Ejemplo:
            >>> trades = client.get_token_trade_data("So111...", chain="solana")
            >>> trades["buy_24h"]
            1523
            >>> trades["unique_wallets_24h"]
            890
        """
        if not self._api_key:
            logger.debug("Birdeye: sin API key, saltando trade_data")
            return None

        self._set_chain(chain)

        respuesta = self._get(
            "/defi/v3/token/trade-data/single",
            params={"address": address},
            use_cache=True,
        )

        data = self._extract_data(respuesta, "trade_data")
        if not data:
            return None

        # Normalizar a formato plano para feature engineering
        resultado = {
            "address": address,
            "chain": chain,
        }

        # Extraer datos por periodo temporal
        for period in ["30m", "1h", "2h", "4h", "8h", "24h"]:
            period_key = period.replace("m", "m").replace("h", "h")
            resultado[f"buy_{period_key}"] = data.get(f"buy{period}")
            resultado[f"sell_{period_key}"] = data.get(f"sell{period}")
            resultado[f"unique_wallets_{period_key}"] = data.get(
                f"uniqueWallet{period}"
            )

        # Volumen en USD de 24h
        resultado["volume_buy_24h"] = safe_float(data.get("volumeBuy24hUSD"))
        resultado["volume_sell_24h"] = safe_float(data.get("volumeSell24hUSD"))
        resultado["trade_24h"] = data.get("trade24h")

        logger.debug(
            f"Birdeye trade_data: {address[:10]}... ({chain}) "
            f"buy_24h={resultado.get('buy_24h')}, "
            f"unique_24h={resultado.get('unique_wallets_24h')}"
        )
        return resultado
