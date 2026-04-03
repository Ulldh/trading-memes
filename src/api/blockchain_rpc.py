"""
blockchain_rpc.py - Clientes para interactuar directamente con blockchains.

Este modulo contiene dos clases:

1. SolanaRPC: Se conecta al nodo RPC de Solana (via Helius) para obtener
   datos on-chain como holders y supply de un token. Estos datos NO estan
   disponibles en las APIs de precio (GeckoTerminal, DexScreener).

2. EtherscanClient: Se conecta a la API de Etherscan/Basescan para verificar
   contratos y obtener metadatos de tokens en Ethereum/Base.

¿Por que necesitamos datos on-chain?
- Distribucion de holders: Si un solo wallet tiene el 90% del supply,
  puede hacer un "rug pull" (vender todo de golpe y destruir el precio).
  Esto es una ENORME red flag para memecoins.
- Verificacion de contrato: Un contrato verificado es mas confiable que
  uno sin verificar (aunque no garantiza seguridad).
- Supply total: Necesario para calcular el market cap real.

Uso:
    from src.api.blockchain_rpc import SolanaRPC, EtherscanClient

    # Datos on-chain de Solana
    solana = SolanaRPC()
    holders = solana.get_token_largest_accounts("MintAddress123...")
    supply = solana.get_token_supply("MintAddress123...")

    # Verificar contrato en Ethereum
    etherscan = EtherscanClient()
    verificado = etherscan.is_contract_verified("0xContractAddress...")
"""

from typing import Optional

# Clase base que nos da rate limiting, retries, cache
from src.api.base_client import BaseAPIClient
from src.utils.logger import get_logger
from src.utils.helpers import safe_float, safe_int

# Importar configuracion
try:
    from config import (
        API_URLS, RATE_LIMITS, HELIUS_API_KEY,
        ETHERSCAN_API_KEY, BASESCAN_API_KEY, ETHERSCAN_CHAIN_IDS,
    )
except ImportError:
    API_URLS = {
        "helius": "https://mainnet.helius-rpc.com/?api-key=",
        "etherscan": "https://api.etherscan.io/v2/api",
    }
    RATE_LIMITS = {"helius": 50, "etherscan": 300}
    HELIUS_API_KEY = ""
    ETHERSCAN_API_KEY = ""
    BASESCAN_API_KEY = ""
    ETHERSCAN_CHAIN_IDS = {"ethereum": 1, "base": 8453, "bsc": 56, "arbitrum": 42161}

# Logger para este modulo
logger = get_logger(__name__)


# ====================================================================
# SOLANA RPC (via Helius)
# ====================================================================

class SolanaRPC(BaseAPIClient):
    """
    Cliente para el nodo RPC de Solana usando Helius como proveedor.

    ¿Que es un RPC?
    RPC (Remote Procedure Call) es la forma de comunicarse directamente
    con la blockchain. En vez de usar una API REST normal, enviamos
    peticiones JSON-RPC (un formato especial) via POST.

    Formato JSON-RPC:
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "nombre_del_metodo",
        "params": [parametros...]
    }

    Helius es un proveedor de nodos RPC para Solana. Ofrece un free tier
    con ~50 calls/segundo. Necesitas una API key (se configura en .env).

    Args:
        api_key: API key de Helius. Si no se pasa, se usa la de config.py.

    Ejemplo:
        >>> solana = SolanaRPC()
        >>> holders = solana.get_token_largest_accounts("MintAddress...")
        >>> for h in holders[:5]:
        ...     print(h["address"], h["ui_amount"])
    """

    def __init__(self, api_key: Optional[str] = None):
        # La API key se puede pasar directamente o usar la de config
        self._api_key = api_key or HELIUS_API_KEY

        # La URL de Helius ya incluye la API key como parametro
        # Formato: https://mainnet.helius-rpc.com/?api-key=TU_KEY
        helius_url = API_URLS.get("helius", "")

        # Si la URL de config ya tiene la key, usarla directamente.
        # Si no, construirla con la key que tenemos.
        if self._api_key and self._api_key not in helius_url:
            helius_url = (
                f"https://mainnet.helius-rpc.com/?api-key={self._api_key}"
            )

        # Inicializar la clase base
        # Nota: para RPC, la base_url es la URL completa (no tiene endpoints)
        super().__init__(
            base_url=helius_url,
            name="helius",
            calls_per_minute=RATE_LIMITS.get("helius", 50),
        )

        logger.info("SolanaRPC (Helius) inicializado")

    def _rpc_call(self, method: str, params: list) -> Optional[dict]:
        """
        Hace una llamada JSON-RPC al nodo de Solana.

        Este es un metodo interno que construye el cuerpo JSON-RPC
        y usa _post() de BaseAPIClient para enviar la peticion.

        Args:
            method: Nombre del metodo RPC (ej: "getTokenLargestAccounts").
            params: Lista de parametros para el metodo.

        Returns:
            La respuesta completa del RPC como dict, o None si fallo.
            La respuesta tiene formato: {"jsonrpc": "2.0", "result": {...}}
        """
        # Construir el cuerpo de la peticion JSON-RPC
        # Este es el formato estandar que todos los nodos blockchain entienden
        cuerpo = {
            "jsonrpc": "2.0",       # Version del protocolo (siempre "2.0")
            "id": 1,                # ID de la peticion (para correlacionar)
            "method": method,       # Metodo a ejecutar
            "params": params,       # Parametros del metodo
        }

        logger.debug(f"RPC call: {method}")

        # Usar _post() de BaseAPIClient
        # endpoint="" porque la URL completa ya esta en base_url
        respuesta = self._post(endpoint="", json_body=cuerpo)

        if not respuesta:
            logger.warning(f"RPC call fallida: {method}")
            return None

        # Verificar si hay error en la respuesta RPC
        # (diferente a errores HTTP - el HTTP puede ser 200 pero el RPC fallo)
        if "error" in respuesta:
            error = respuesta["error"]
            logger.error(
                f"RPC error en {method}: "
                f"codigo={error.get('code')}, "
                f"mensaje={error.get('message')}"
            )
            return None

        return respuesta

    def get_token_largest_accounts(
        self, mint_address: str
    ) -> list[dict]:
        """
        Obtiene las 20 cuentas con mas tokens de un mint (token) dado.

        Esto es CRITICO para detectar rug pulls:
        - Si 1 wallet tiene >50% del supply: MUY PELIGROSO
        - Si top 10 wallets tienen >80%: PELIGROSO
        - Distribucion uniforme: Mejor senal

        NOTA: Solana devuelve "cuentas de token" (token accounts), no
        wallets directamente. Una wallet puede tener multiples token accounts,
        pero generalmente hay una por token.

        Args:
            mint_address: Direccion del mint (contrato del token) en Solana.

        Returns:
            Lista de diccionarios con los top 20 holders.
            Cada dict tiene:
            - address: Direccion de la cuenta de token
            - amount: Cantidad raw (sin decimales)
            - decimals: Numero de decimales del token
            - ui_amount: Cantidad legible (con decimales aplicados)
            Lista vacia si hay error.

        Ejemplo:
            >>> holders = solana.get_token_largest_accounts("MintAddr...")
            >>> top_holder = holders[0]
            >>> print(f"Top holder tiene {top_holder['ui_amount']} tokens")
        """
        logger.info(
            f"Obteniendo top holders del token {mint_address[:10]}..."
        )

        # Llamar al metodo RPC "getTokenLargestAccounts"
        # Solo necesita la direccion del mint como parametro
        respuesta = self._rpc_call(
            method="getTokenLargestAccounts",
            params=[mint_address],
        )

        if not respuesta:
            return []

        # La respuesta tiene el formato:
        # {"result": {"value": [
        #     {"address": "...", "amount": "123", "decimals": 9, "uiAmount": 0.123},
        #     ...
        # ]}}
        try:
            cuentas_raw = respuesta.get("result", {}).get("value", [])
        except (AttributeError, TypeError):
            logger.warning("Formato inesperado en respuesta de holders")
            return []

        # Parsear cada cuenta a un formato limpio
        holders = []
        for cuenta in cuentas_raw:
            holders.append({
                "address": cuenta.get("address", ""),
                "amount": cuenta.get("amount", "0"),
                "decimals": safe_int(cuenta.get("decimals")),
                "ui_amount": safe_float(cuenta.get("uiAmount")),
            })

        logger.info(
            f"Token {mint_address[:10]}...: "
            f"{len(holders)} holders principales obtenidos"
        )
        return holders

    def get_token_supply(self, mint_address: str) -> Optional[dict]:
        """
        Obtiene el supply total de un token en Solana.

        El supply total es necesario para calcular:
        - Market cap real (supply * precio)
        - Porcentaje de concentracion de holders
        - FDV (Fully Diluted Valuation)

        Args:
            mint_address: Direccion del mint (contrato del token) en Solana.

        Returns:
            Diccionario con:
            - amount: Supply total raw (string, sin decimales)
            - decimals: Numero de decimales del token
            - ui_amount: Supply total legible (float, con decimales)
            Retorna None si hay error.

        Ejemplo:
            >>> supply = solana.get_token_supply("MintAddr...")
            >>> print(f"Supply total: {supply['ui_amount']:,.0f} tokens")
        """
        logger.info(
            f"Obteniendo supply del token {mint_address[:10]}..."
        )

        # Llamar al metodo RPC "getTokenSupply"
        respuesta = self._rpc_call(
            method="getTokenSupply",
            params=[mint_address],
        )

        if not respuesta:
            return None

        # La respuesta tiene el formato:
        # {"result": {"value": {
        #     "amount": "1000000000",
        #     "decimals": 9,
        #     "uiAmount": 1.0
        # }}}
        try:
            valor = respuesta.get("result", {}).get("value", {})
        except (AttributeError, TypeError):
            logger.warning("Formato inesperado en respuesta de supply")
            return None

        if not valor:
            logger.warning(f"No se obtuvo supply para {mint_address[:10]}...")
            return None

        resultado = {
            "amount": valor.get("amount", "0"),
            "decimals": safe_int(valor.get("decimals")),
            "ui_amount": safe_float(valor.get("uiAmount")),
        }

        logger.info(
            f"Supply de {mint_address[:10]}...: "
            f"{resultado['ui_amount']:,.0f} tokens"
        )
        return resultado


# ====================================================================
# ETHERSCAN / BASESCAN CLIENT
# ====================================================================

class EtherscanClient(BaseAPIClient):
    """
    Cliente para la API V2 de Etherscan (unificada para todas las cadenas EVM).

    Etherscan V2 usa una sola URL base con un parametro `chainid` para
    seleccionar la cadena (Ethereum=1, Base=8453, etc.). Una sola API key
    funciona para todas las cadenas.

    Usamos esta API para:
    - Verificar si un contrato esta verificado (codigo fuente publico)
    - Obtener el codigo fuente del contrato
    - Obtener metadatos del token (nombre, simbolo, supply)

    Args:
        api_key: API key de Etherscan. Si no se pasa, se usa la de config.py.
        chain: Cadena objetivo ("ethereum" o "base"). Default: "ethereum".

    Ejemplo:
        >>> # Para Ethereum
        >>> etherscan = EtherscanClient(chain="ethereum")
        >>> verificado = etherscan.is_contract_verified("0xContrato...")
        >>>
        >>> # Para Base (misma API key, diferente chainid)
        >>> basescan = EtherscanClient(chain="base")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        chain: str = "ethereum",
    ):
        # V2 API: una sola key para todas las cadenas
        self._api_key = api_key or ETHERSCAN_API_KEY or BASESCAN_API_KEY
        self._chain = chain
        self._chain_id = ETHERSCAN_CHAIN_IDS.get(chain, 1)

        # V2 URL unificada
        url = API_URLS.get("etherscan", "https://api.etherscan.io/v2/api")

        # Nombre para logging (Etherscan V2 soporta todas las EVM chains)
        chain_names = {
            "base": "basescan",
            "bsc": "bscscan",
            "arbitrum": "arbiscan",
        }
        name = chain_names.get(chain, "etherscan")

        # Inicializar la clase base
        super().__init__(
            base_url=url,
            name=name,
            calls_per_minute=RATE_LIMITS.get("etherscan", 300),
        )

        logger.info(
            f"EtherscanClient V2 inicializado (chain={chain}, chainid={self._chain_id})"
        )

    def _etherscan_get(
        self,
        module: str,
        action: str,
        extra_params: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Hace una peticion a la API de Etherscan/Basescan.

        Todas las peticiones a Etherscan siguen el mismo formato:
        ?module=X&action=Y&apikey=Z&otrosParams...

        Este metodo construye los parametros automaticamente.

        Args:
            module: Modulo de la API (ej: "contract", "token").
            action: Accion a ejecutar (ej: "getabi", "getsourcecode").
            extra_params: Parametros adicionales (ej: {"address": "0x..."}).

        Returns:
            Diccionario con la respuesta, o None si hay error.
            Etherscan devuelve: {"status": "1", "message": "OK", "result": ...}
        """
        # Construir los parametros base que toda peticion V2 necesita
        # chainid es OBLIGATORIO en V2 para identificar la cadena
        params = {
            "chainid": self._chain_id,
            "module": module,
            "action": action,
            "apikey": self._api_key,
        }

        # Agregar parametros extras si los hay
        if extra_params:
            params.update(extra_params)

        # Hacer la peticion GET
        # endpoint="" porque Etherscan usa parametros de query, no rutas
        respuesta = self._get(endpoint="", params=params)

        if not respuesta:
            return None

        # Verificar el status de la respuesta de Etherscan
        # "1" = exito, "0" = error o sin datos
        if respuesta.get("status") == "0":
            mensaje = respuesta.get("message", "")
            resultado = respuesta.get("result", "")

            # "NOTOK" indica un error real (key invalida, rate limit, etc.)
            # Otros mensajes como "No data found" no son errores criticos
            if mensaje == "NOTOK":
                logger.error(f"{self.name}: Error de API: {resultado}")
                return None

            # Si no es un error critico, devolver la respuesta de todos modos
            # (puede ser que simplemente no haya datos)
            logger.debug(
                f"{self.name}: status=0, mensaje='{mensaje}', "
                f"resultado='{str(resultado)[:100]}'"
            )

        return respuesta

    def is_contract_verified(self, address: str) -> bool:
        """
        Verifica si un contrato inteligente tiene su codigo fuente verificado.

        ¿Que significa "contrato verificado"?
        Cuando un desarrollador despliega un contrato en la blockchain, solo
        el bytecode (codigo compilado) es publico. "Verificar" significa subir
        el codigo fuente original a Etherscan para que cualquiera pueda leerlo
        y auditarlo.

        Para nuestro detector de memecoins:
        - Contrato verificado: Senal positiva (transparencia)
        - Contrato NO verificado: Red flag (puede ocultar funciones maliciosas)

        Args:
            address: Direccion del contrato en la blockchain.

        Returns:
            True si el contrato esta verificado, False en caso contrario.

        Ejemplo:
            >>> if etherscan.is_contract_verified("0xContrato..."):
            ...     print("Contrato verificado - buena senal")
            ... else:
            ...     print("CUIDADO: Contrato no verificado")
        """
        logger.info(f"Verificando contrato {address[:10]}...")

        # Intentar obtener el ABI del contrato
        # Si el contrato esta verificado, el ABI estara disponible
        # Si no, devolvera un mensaje de error
        respuesta = self._etherscan_get(
            module="contract",
            action="getabi",
            extra_params={"address": address},
        )

        if not respuesta:
            # Si la peticion fallo completamente, asumimos no verificado
            return False

        # Un contrato verificado tiene status "1" y el ABI en result
        # Un contrato no verificado tiene status "0" y un mensaje de error
        esta_verificado = respuesta.get("status") == "1"

        if esta_verificado:
            logger.info(f"Contrato {address[:10]}... esta VERIFICADO")
        else:
            logger.info(f"Contrato {address[:10]}... NO esta verificado")

        return esta_verificado

    def get_contract_source(self, address: str) -> Optional[dict]:
        """
        Obtiene el codigo fuente y metadatos de un contrato verificado.

        Incluye: nombre del contrato, compilador usado, codigo fuente,
        ABI, y configuracion de optimizacion.

        Esto nos permite detectar patrones sospechosos en el contrato:
        - Funciones de "mint" que pueden crear tokens infinitos
        - Funciones de "pause" que pueden bloquear ventas
        - Funciones de "blacklist" que pueden bloquear wallets
        - Proxies que pueden cambiar la logica del contrato

        Args:
            address: Direccion del contrato.

        Returns:
            Diccionario con datos del contrato:
            - contract_name: Nombre del contrato
            - compiler_version: Version del compilador Solidity
            - optimization_used: Si usa optimizacion
            - source_code: Codigo fuente del contrato
            - abi: ABI del contrato (interfaz publica)
            - is_proxy: Si es un contrato proxy
            Retorna None si hay error o no esta verificado.

        Ejemplo:
            >>> source = etherscan.get_contract_source("0xContrato...")
            >>> if source:
            ...     print(f"Nombre: {source['contract_name']}")
            ...     print(f"Proxy: {source['is_proxy']}")
        """
        logger.info(f"Obteniendo codigo fuente de {address[:10]}...")

        respuesta = self._etherscan_get(
            module="contract",
            action="getsourcecode",
            extra_params={"address": address},
        )

        if not respuesta:
            return None

        # El resultado es una lista con un solo elemento
        result = respuesta.get("result")
        if not result or not isinstance(result, list) or len(result) == 0:
            logger.warning(
                f"No se encontro codigo fuente para {address[:10]}..."
            )
            return None

        # Extraer los datos del primer (y unico) elemento
        contrato = result[0]

        # Si el codigo fuente esta vacio, el contrato no esta verificado
        source_code = contrato.get("SourceCode", "")
        if not source_code:
            logger.info(f"Contrato {address[:10]}... no tiene codigo fuente")
            return None

        return {
            "contract_name": contrato.get("ContractName", ""),
            "compiler_version": contrato.get("CompilerVersion", ""),
            "optimization_used": contrato.get("OptimizationUsed", "0") == "1",
            "source_code": source_code,
            "abi": contrato.get("ABI", ""),
            "constructor_arguments": contrato.get("ConstructorArguments", ""),
            "is_proxy": contrato.get("Proxy", "0") == "1",
            "implementation_address": contrato.get("Implementation", ""),
        }

    def get_token_info(self, address: str) -> Optional[dict]:
        """
        Obtiene metadatos de un token ERC-20.

        Incluye nombre, simbolo, decimales, supply total y otra info
        basica del token. Util para verificar la legitimidad del token
        y obtener datos que no estan disponibles en las APIs de precio.

        Args:
            address: Direccion del contrato del token.

        Returns:
            Diccionario con metadatos del token:
            - name: Nombre del token
            - symbol: Simbolo/ticker
            - decimals: Numero de decimales
            - total_supply: Supply total
            - website: Sitio web del proyecto
            - social_links: Links a redes sociales
            Retorna None si hay error o el token no existe.

        Ejemplo:
            >>> info = etherscan.get_token_info("0xTokenAddr...")
            >>> if info:
            ...     print(f"{info['name']} ({info['symbol']})")
        """
        logger.info(f"Obteniendo info del token {address[:10]}...")

        respuesta = self._etherscan_get(
            module="token",
            action="tokeninfo",
            extra_params={"contractaddress": address},
        )

        if not respuesta:
            return None

        # El resultado puede ser una lista o un string de error
        result = respuesta.get("result")

        # Si result es un string, es un mensaje de error
        if isinstance(result, str):
            logger.warning(
                f"No se encontro info del token {address[:10]}...: {result}"
            )
            return None

        # Si es una lista, tomar el primer elemento
        if isinstance(result, list) and len(result) > 0:
            token_data = result[0]
        elif isinstance(result, dict):
            token_data = result
        else:
            logger.warning(
                f"Formato inesperado en respuesta de token info: "
                f"{type(result)}"
            )
            return None

        return {
            "name": token_data.get("tokenName", ""),
            "symbol": token_data.get("symbol", ""),
            "decimals": safe_int(token_data.get("divisor")),
            "total_supply": token_data.get("totalSupply", ""),
            "token_type": token_data.get("tokenType", ""),
            "website": token_data.get("website", ""),
            "email": token_data.get("email", ""),
            "description": token_data.get("description", ""),
            "social_links": {
                "twitter": token_data.get("twitter", ""),
                "telegram": token_data.get("telegram", ""),
                "discord": token_data.get("discord", ""),
                "facebook": token_data.get("facebook", ""),
                "reddit": token_data.get("reddit", ""),
            },
        }
