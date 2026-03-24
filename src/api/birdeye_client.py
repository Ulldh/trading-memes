"""
birdeye_client.py - Cliente para la API de Birdeye (Solana).

Birdeye proporciona datos OHLCV historicos completos para cualquier token
de Solana, desde su creacion. Esto es clave para el backfill de datos,
ya que GeckoTerminal solo da las ultimas 30 velas diarias.

Endpoint principal:
    GET /defi/ohlcv — Velas OHLCV para un token dado un rango de tiempo.

Tiers de API:
    - Free: 1 rps (60 calls/min), sin costo
    - Lite: 15 rps (900 calls/min), $39/mes primer mes
    - Pro: 50 rps, $99/mes

Autenticacion:
    Header X-API-KEY con la key obtenida en https://bds.birdeye.so

Uso:
    from src.api.birdeye_client import BirdeyeClient

    client = BirdeyeClient()

    # OHLCV diario de un token (ultimos 90 dias)
    ohlcv = client.get_token_ohlcv(
        address="TokenAddress123...",
        time_from=1700000000,
        time_to=1707776000,
        timeframe="1D",
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
    RATE_LIMITS = {"birdeye": 60}
    BIRDEYE_API_KEY = ""

logger = get_logger(__name__)


class BirdeyeClient(BaseAPIClient):
    """
    Cliente para Birdeye API (datos historicos de tokens Solana).

    Hereda de BaseAPIClient para reusar rate limiting, retries y cache.
    Requiere BIRDEYE_API_KEY en .env para funcionar.

    Timeframes soportados para OHLCV:
        1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 8H, 12H, 1D, 3D, 1W, 1M
    """

    def __init__(self):
        super().__init__(
            base_url=API_URLS.get("birdeye", "https://public-api.birdeye.so"),
            name="birdeye",
            calls_per_minute=RATE_LIMITS.get("birdeye", 60),
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
            address: Direccion del contrato del token en Solana.
            time_from: Timestamp Unix (segundos) del inicio del rango.
            time_to: Timestamp Unix (segundos) del fin del rango.
            timeframe: Periodo de cada vela. Opciones:
                1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 8H, 12H, 1D, 3D, 1W, 1M.
                Para backfill historico, usar "1D" (velas diarias).
            chain: Cadena del token (default "solana").

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

        # Birdeye usa header x-chain para indicar la cadena
        self.session.headers["x-chain"] = chain

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

        logger.debug(f"Birdeye: {len(velas)} velas para {address[:10]}...")
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
            chain: Cadena del token (default "solana").

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
