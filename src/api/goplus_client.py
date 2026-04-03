"""
goplus_client.py — Cliente para GoPlus Security API.

Proporciona datos de seguridad de tokens: honeypot detection,
tax analysis, owner privileges, contract risks.

API: https://api.gopluslabs.io/api/v1/token_security/{chain_id}
Rate limit: ~100 req/min (fair use, sin API key)
Coste: Gratis

GoPlus analiza contratos inteligentes y detecta riesgos como:
- Honeypots: tokens que no se pueden vender despues de comprar
- Taxes ocultos: comisiones de compra/venta excesivas
- Owner privileges: funciones peligrosas que el owner puede ejecutar
- Mintable: si se pueden crear tokens nuevos (dilucion)

Ejemplo:
    from src.api.goplus_client import GoPlusClient

    client = GoPlusClient()
    # Un solo token
    data = client.get_token_security("solana", "DireccionDelToken...")
    print(data.get("is_honeypot"))

    # Batch de hasta 100 tokens
    results = client.get_tokens_security("ethereum", ["addr1", "addr2"])
"""

from typing import Optional

from src.api.base_client import BaseAPIClient
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Mapeo de nombres de cadena internos al chain_id que usa GoPlus
# GoPlus usa IDs numericos para EVM y "solana" como string
GOPLUS_CHAIN_IDS = {
    "solana": "solana",
    "ethereum": "1",
    "base": "8453",
    "bsc": "56",
    "arbitrum": "42161",
}


class GoPlusClient(BaseAPIClient):
    """
    Cliente para GoPlus Security API.

    Hereda de BaseAPIClient para obtener rate limiting, retries,
    cache en disco y logging automatico.

    GoPlus es una API gratuita que analiza la seguridad de tokens
    en multiples blockchains. No requiere API key.

    Args:
        calls_per_minute: Limite de llamadas por minuto (default 60,
            conservador respecto al limite real de ~100/min).
        cache_ttl_hours: Horas de validez del cache (default 12h,
            los datos de seguridad no cambian frecuentemente).

    Ejemplo:
        client = GoPlusClient()
        data = client.get_token_security("ethereum", "0x...")
        if data.get("is_honeypot"):
            print("ALERTA: Este token es un honeypot!")
    """

    def __init__(
        self,
        calls_per_minute: int = 60,
        cache_ttl_hours: float = 12,
    ):
        super().__init__(
            base_url="https://api.gopluslabs.io/api/v1",
            name="goplus",
            calls_per_minute=calls_per_minute,
            cache_ttl_hours=cache_ttl_hours,
            max_retries=2,
            timeout=15,
            # No necesitamos tracking de API usage para GoPlus (es gratis)
            enable_usage_tracking=False,
        )

    def get_token_security(
        self, chain: str, token_address: str
    ) -> dict:
        """
        Obtiene datos de seguridad para un token individual.

        Llama a GoPlus y parsea la respuesta para extraer los campos
        mas relevantes para deteccion de rugs y honeypots.

        Args:
            chain: Nombre de la cadena ("solana", "ethereum", "base", etc.)
            token_address: Direccion del contrato del token.

        Returns:
            Dict con los datos de seguridad parseados:
            - is_honeypot: bool (True = no se puede vender)
            - buy_tax: float 0-100 (porcentaje de tax al comprar)
            - sell_tax: float 0-100 (porcentaje de tax al vender)
            - is_open_source: bool (codigo fuente verificado)
            - hidden_owner: bool (owner oculto)
            - can_take_back_ownership: bool
            - selfdestruct: bool (contrato puede autodestruirse)
            - is_blacklisted: bool (tiene funcion de blacklist)
            - is_mintable: bool (puede crear tokens nuevos)
            - owner_change_balance: bool (owner puede cambiar balances)
            - lp_holder_count: int (holders del pool de liquidez)
            - holder_count: int (holders del token)
            Dict vacio si la llamada falla o el token no se encuentra.

        Ejemplo:
            >>> data = client.get_token_security("ethereum", "0xabc...")
            >>> data["is_honeypot"]
            False
            >>> data["sell_tax"]
            5.0
        """
        result = self.get_tokens_security(chain, [token_address])
        # get_tokens_security retorna {address: data}, extraer el valor
        addr_lower = token_address.lower()
        return result.get(addr_lower, result.get(token_address, {}))

    def get_tokens_security(
        self, chain: str, addresses: list[str]
    ) -> dict:
        """
        Obtiene datos de seguridad para un batch de tokens (hasta 100).

        GoPlus soporta multiples direcciones separadas por coma en
        una sola llamada, lo que es mucho mas eficiente que llamar
        de a uno.

        Args:
            chain: Nombre de la cadena ("solana", "ethereum", "base", etc.)
            addresses: Lista de direcciones de tokens (max 100 por llamada).

        Returns:
            Dict donde cada key es una direccion (lowercase) y el valor
            es un dict con los datos de seguridad parseados.
            Dict vacio si la cadena no esta soportada o la llamada falla.

        Ejemplo:
            >>> results = client.get_tokens_security("ethereum", ["0xabc", "0xdef"])
            >>> for addr, data in results.items():
            ...     print(f"{addr}: honeypot={data.get('is_honeypot')}")
        """
        # Validar que la cadena esta soportada
        chain_id = GOPLUS_CHAIN_IDS.get(chain)
        if chain_id is None:
            logger.debug(f"GoPlus: cadena '{chain}' no soportada")
            return {}

        if not addresses:
            return {}

        # Limitar a 100 direcciones por llamada (limite de GoPlus)
        addresses = addresses[:100]

        # Construir el endpoint segun la cadena
        # GoPlus usa diferentes endpoints para Solana vs EVM
        if chain_id == "solana":
            endpoint = f"/solana/token_security"
            params = {"contract_addresses": ",".join(addresses)}
        else:
            endpoint = f"/token_security/{chain_id}"
            params = {"contract_addresses": ",".join(addresses)}

        # Hacer la llamada a GoPlus
        response = self._get(endpoint, params=params, use_cache=True)

        if not response:
            return {}

        # GoPlus devuelve { "code": 1, "result": { "addr": {...}, ... } }
        code = response.get("code")
        if code != 1:
            logger.warning(
                f"GoPlus: respuesta con code={code} "
                f"(esperado 1) para {chain}"
            )
            return {}

        result_data = response.get("result", {})
        if not result_data or not isinstance(result_data, dict):
            return {}

        # Parsear cada token en el resultado
        parsed = {}
        for addr, token_data in result_data.items():
            if not isinstance(token_data, dict):
                continue
            parsed[addr.lower()] = self._parse_token_security(token_data)

        return parsed

    def _parse_token_security(self, data: dict) -> dict:
        """
        Parsea la respuesta cruda de GoPlus a un formato limpio.

        GoPlus devuelve strings "0"/"1" en lugar de booleans,
        y porcentajes como strings ("0.05" para 5%). Este metodo
        normaliza todo a tipos Python nativos.

        Args:
            data: Dict crudo de GoPlus para un token.

        Returns:
            Dict con campos parseados y tipos correctos.
        """
        return {
            # Honeypot: "1" = es honeypot, "0" = no
            "is_honeypot": self._to_bool(data.get("is_honeypot")),
            # Taxes: GoPlus devuelve como decimal (0.05 = 5%)
            "buy_tax": self._tax_to_pct(data.get("buy_tax")),
            "sell_tax": self._tax_to_pct(data.get("sell_tax")),
            # Codigo fuente verificado
            "is_open_source": self._to_bool(data.get("is_open_source")),
            # Owner oculto (no se puede identificar)
            "hidden_owner": self._to_bool(data.get("hidden_owner")),
            # Owner puede recuperar ownership despues de renunciar
            "can_take_back_ownership": self._to_bool(
                data.get("can_take_back_ownership")
            ),
            # Contrato tiene funcion selfdestruct
            "selfdestruct": self._to_bool(data.get("selfdestruct")),
            # Token tiene funcion de blacklist/whitelist
            "is_blacklisted": self._to_bool(data.get("is_blacklisted")),
            # Se pueden crear (mint) tokens nuevos
            "is_mintable": self._to_bool(data.get("is_mintable")),
            # Owner puede cambiar balances directamente
            "owner_change_balance": self._to_bool(
                data.get("owner_change_balance")
            ),
            # Conteo de holders del LP (pool de liquidez)
            "lp_holder_count": self._to_int(data.get("lp_holder_count")),
            # Conteo total de holders del token
            "holder_count": self._to_int(data.get("holder_count")),
        }

    @staticmethod
    def _to_bool(value) -> Optional[bool]:
        """
        Convierte valor de GoPlus ("0"/"1"/None) a bool.

        GoPlus devuelve "0" y "1" como strings, no como booleanos.
        None se mantiene como None (dato no disponible).
        """
        if value is None or value == "":
            return None
        # GoPlus usa "1" para True y "0" para False
        if isinstance(value, str):
            return value == "1"
        return bool(value)

    @staticmethod
    def _tax_to_pct(value) -> Optional[float]:
        """
        Convierte tax de GoPlus (decimal como string) a porcentaje.

        GoPlus devuelve taxes como string decimal: "0.05" = 5%
        Convertimos a porcentaje (0-100) para consistencia con
        nuestros features.
        """
        if value is None or value == "":
            return None
        try:
            # "0.05" -> 5.0, "1.0" -> 100.0
            return float(value) * 100
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_int(value) -> Optional[int]:
        """Convierte valor a int de forma segura."""
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
