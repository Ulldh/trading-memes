"""
rugcheck_client.py — Cliente para RugCheck API (solo Solana).

Analiza tokens de Solana para detectar riesgo de rug pull.
RugCheck inspecciona la estructura on-chain del token y reporta
riesgos especificos como freeze authority, mutable metadata,
concentracion de LP, etc.

API: https://api.rugcheck.xyz/v1/tokens/{mint}/report
Rate limit: ~60 req/min (fair use)
Coste: Gratis

Ejemplo:
    from src.api.rugcheck_client import RugCheckClient

    client = RugCheckClient()
    report = client.get_report("DireccionDelTokenSolana...")
    print(f"Risk score: {report.get('risk_score')}")
    print(f"Riesgos: {report.get('risk_count')}")
"""

import time

import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)

# URL base de la API de RugCheck
RUGCHECK_BASE_URL = "https://api.rugcheck.xyz/v1"

# Tiempo minimo entre llamadas (1 segundo = 60 req/min)
MIN_INTERVAL_SECONDS = 1.0


class RugCheckClient:
    """
    Cliente simple para RugCheck API (solo tokens de Solana).

    A diferencia de los otros clientes, este NO hereda de BaseAPIClient
    porque RugCheck tiene una API mucho mas simple (un solo endpoint,
    sin paginacion, sin API key). Implementamos rate limiting manual
    con un sleep entre llamadas.

    RugCheck analiza:
    - Freeze authority: si el creador puede congelar transfers
    - Mutable metadata: si los metadatos del token pueden cambiar
    - LP concentration: si la liquidez esta concentrada en pocas wallets
    - Mint authority: si se pueden crear mas tokens
    - Y otros riesgos especificos de Solana

    Ejemplo:
        client = RugCheckClient()
        report = client.get_report("SolanaTokenMint...")
        if report.get("risk_score", 0) > 50:
            print("Token con riesgo alto de rug pull")
    """

    def __init__(self, timeout: int = 15):
        """
        Inicializa el cliente de RugCheck.

        Args:
            timeout: Timeout en segundos para cada peticion HTTP.
        """
        self.timeout = timeout
        self._last_call_time = 0.0
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "MemecoinGemDetector/1.0",
        })
        logger.info("RugCheckClient inicializado")

    def get_report(self, mint_address: str) -> dict:
        """
        Obtiene el reporte de seguridad de un token de Solana.

        Llama a RugCheck y parsea la respuesta para extraer:
        - risk_score: puntuacion de riesgo 0-100 (mayor = mas peligroso)
        - risk_level: nivel textual (Good, Warning, Danger)
        - risk_count: numero de riesgos detectados
        - risks: lista de riesgos individuales con nombre y descripcion
        - has_freeze_authority: si el creador puede congelar transfers
        - has_mutable_metadata: si los metadatos pueden cambiar

        Args:
            mint_address: Direccion mint del token de Solana.

        Returns:
            Dict con los datos parseados del reporte.
            Dict vacio si la llamada falla o el token no se encuentra.

        Ejemplo:
            >>> report = client.get_report("So11111111111111111111111111111112")
            >>> print(report["risk_score"])
            15
            >>> print(report["risk_level"])
            "Good"
        """
        if not mint_address:
            return {}

        # Rate limiting manual: esperar si la ultima llamada fue reciente
        elapsed = time.time() - self._last_call_time
        if elapsed < MIN_INTERVAL_SECONDS:
            time.sleep(MIN_INTERVAL_SECONDS - elapsed)

        url = f"{RUGCHECK_BASE_URL}/tokens/{mint_address}/report"

        try:
            self._last_call_time = time.time()
            response = self._session.get(url, timeout=self.timeout)

            if response.status_code == 404:
                logger.debug(
                    f"RugCheck: token no encontrado: {mint_address[:10]}..."
                )
                return {}

            if response.status_code == 429:
                logger.warning("RugCheck: rate limited (429), esperando 5s")
                time.sleep(5)
                return {}

            response.raise_for_status()
            data = response.json()

            return self._parse_report(data)

        except requests.exceptions.Timeout:
            logger.warning(
                f"RugCheck: timeout para {mint_address[:10]}..."
            )
            return {}

        except requests.exceptions.ConnectionError:
            logger.warning(
                f"RugCheck: error de conexion para {mint_address[:10]}..."
            )
            return {}

        except requests.exceptions.RequestException as e:
            logger.warning(
                f"RugCheck: error para {mint_address[:10]}...: {e}"
            )
            return {}

        except (ValueError, KeyError) as e:
            logger.warning(
                f"RugCheck: error parseando respuesta para "
                f"{mint_address[:10]}...: {e}"
            )
            return {}

    def _parse_report(self, data: dict) -> dict:
        """
        Parsea la respuesta cruda de RugCheck a formato limpio.

        RugCheck devuelve un JSON con estructura variable.
        Extraemos los campos mas utiles y normalizamos.

        Args:
            data: Dict crudo de la respuesta de RugCheck.

        Returns:
            Dict con campos parseados.
        """
        if not data or not isinstance(data, dict):
            return {}

        # Extraer score y level del campo "score" o "riskLevel"
        # La estructura puede variar segun version de la API
        risk_score = data.get("score", data.get("riskScore"))
        risk_level = data.get("riskLevel", data.get("risk_level", ""))

        # Normalizar risk_score a 0-100
        # RugCheck puede devolver scores en diferentes rangos
        if risk_score is not None:
            try:
                risk_score = float(risk_score)
                # Si el score viene como 0-1000, normalizar a 0-100
                if risk_score > 100:
                    risk_score = min(risk_score / 10, 100)
            except (ValueError, TypeError):
                risk_score = None

        # Extraer lista de riesgos individuales
        risks = data.get("risks", [])
        if not isinstance(risks, list):
            risks = []

        # Extraer flags especificas de los riesgos
        risk_names = set()
        for risk in risks:
            if isinstance(risk, dict):
                name = risk.get("name", "").lower()
                risk_names.add(name)
            elif isinstance(risk, str):
                risk_names.add(risk.lower())

        # Buscar flags especificas en los riesgos reportados
        has_freeze = any(
            "freeze" in r for r in risk_names
        )
        has_mutable = any(
            "mutable" in r or "metadata" in r for r in risk_names
        )

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_count": len(risks),
            "risks": risks,
            "has_freeze_authority": has_freeze,
            "has_mutable_metadata": has_mutable,
        }
