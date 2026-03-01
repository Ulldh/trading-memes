"""
base_client.py - Clase base para todos los clientes de API.

Proporciona funcionalidad comun:
- Rate limiting automatico (no exceder limites de la API)
- Reintentos con backoff exponencial (si la API falla, reintenta)
- Cache en disco (no repetir llamadas innecesarias)
- Guardado de respuestas crudas en JSON (nunca perder datos)
- Logging consistente

Todos los clientes de API (CoinGecko, DexScreener, etc.) heredan
de esta clase para tener estas capacidades automaticamente.
"""

import json
import time
from pathlib import Path
from typing import Optional, Any

import requests

from src.api.rate_limiter import RateLimiter
from src.data.cache import DiskCache
from src.utils.logger import get_logger

# Importar config de forma segura
try:
    from config import RAW_DIR
except ImportError:
    RAW_DIR = Path("data/raw")

logger = get_logger(__name__)


class BaseAPIClient:
    """
    Clase base para clientes de API con rate limiting, retries y cache.

    Args:
        base_url: URL base de la API (ej: "https://api.geckoterminal.com/api/v2").
        name: Nombre identificador del cliente (ej: "geckoterminal").
        calls_per_minute: Limite de llamadas por minuto.
        cache_ttl_hours: Horas de validez del cache.
        max_retries: Numero maximo de reintentos ante errores.
        timeout: Timeout en segundos para cada peticion HTTP.

    Ejemplo:
        class MiCliente(BaseAPIClient):
            def __init__(self):
                super().__init__(
                    base_url="https://api.ejemplo.com",
                    name="ejemplo",
                    calls_per_minute=30,
                )

            def get_data(self):
                return self._get("/endpoint")
    """

    def __init__(
        self,
        base_url: str,
        name: str,
        calls_per_minute: int = 30,
        cache_ttl_hours: float = 24,
        max_retries: int = 3,
        timeout: int = 30,
        enable_usage_tracking: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.name = name
        self.max_retries = max_retries
        self.timeout = timeout
        self.enable_usage_tracking = enable_usage_tracking

        # Crear rate limiter para esta API
        self.rate_limiter = RateLimiter(
            calls_per_minute=calls_per_minute,
            name=name,
        )

        # Crear cache en disco para esta API
        self.cache = DiskCache(
            namespace=name,
            ttl_hours=cache_ttl_hours,
        )

        # Sesion HTTP reutilizable (mantiene conexiones abiertas)
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "MemecoinGemDetector/1.0",
        })

        # Directorio para guardar respuestas crudas
        self.raw_dir = Path(RAW_DIR) / name
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        # Contador de llamadas (para estadisticas)
        self._call_count = 0

        # Storage para tracking de API usage (lazy load)
        self._storage = None

        logger.info(f"Cliente '{name}' inicializado ({calls_per_minute} calls/min)")

    def _get_storage(self):
        """Lazy load de Storage para evitar imports circulares."""
        if self._storage is None and self.enable_usage_tracking:
            try:
                from src.data.storage import Storage
                self._storage = Storage()
            except Exception as e:
                logger.debug(f"No se pudo inicializar Storage para tracking: {e}")
                self.enable_usage_tracking = False
        return self._storage

    def _log_api_call(
        self,
        endpoint: str,
        status_code: int = None,
        response_time_ms: int = None,
        error_message: str = None,
    ):
        """Registra una llamada API en la base de datos para tracking."""
        if not self.enable_usage_tracking:
            return

        try:
            storage = self._get_storage()
            if storage:
                storage.log_api_call(
                    api_name=self.name,
                    endpoint=endpoint,
                    status_code=status_code,
                    response_time_ms=response_time_ms,
                    error_message=error_message,
                )
        except Exception as e:
            # No fallar por logging, solo advertir
            logger.debug(f"Error logging API call: {e}")

    def _get(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        use_cache: bool = True,
        save_raw: bool = False,
    ) -> Optional[dict]:
        """
        Hace una peticion GET con rate limiting, cache y retries.

        Args:
            endpoint: Ruta del endpoint (ej: "/networks/solana/pools").
            params: Parametros de query string.
            use_cache: Si True, busca primero en cache.
            save_raw: Si True, guarda la respuesta JSON cruda en disco.

        Returns:
            Respuesta JSON como dict, o None si fallo.
        """
        url = f"{self.base_url}{endpoint}"

        # 1. Buscar en cache
        if use_cache:
            cached = self.cache.get(url, params)
            if cached is not None:
                return cached

        # 2. Hacer la peticion con retries
        for attempt in range(1, self.max_retries + 1):
            start_time = time.time()
            try:
                # Esperar por rate limiter antes de llamar
                self.rate_limiter.wait()

                response = self.session.get(
                    url, params=params, timeout=self.timeout
                )
                response_time_ms = int((time.time() - start_time) * 1000)
                self._call_count += 1

                # Log API call
                self._log_api_call(
                    endpoint=endpoint,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                )

                # Manejar codigos de error HTTP
                if response.status_code == 429:
                    # Too Many Requests - esperar mas
                    wait = 2 ** attempt * 10  # 20s, 40s, 80s
                    logger.warning(
                        f"{self.name}: Rate limited (429), "
                        f"esperando {wait}s (intento {attempt}/{self.max_retries})"
                    )
                    time.sleep(wait)
                    continue

                if response.status_code == 404:
                    logger.debug(f"{self.name}: No encontrado (404): {endpoint}")
                    return None

                response.raise_for_status()

                # Parsear JSON
                data = response.json()

                # 3. Guardar en cache
                if use_cache:
                    self.cache.set(url, data, params)

                # 4. Guardar respuesta cruda si se pide
                if save_raw:
                    self._save_raw(endpoint, params, data)

                return data

            except requests.exceptions.Timeout:
                logger.warning(
                    f"{self.name}: Timeout en {endpoint} "
                    f"(intento {attempt}/{self.max_retries})"
                )
                self._log_api_call(endpoint=endpoint, error_message="Timeout")

            except requests.exceptions.ConnectionError as e:
                logger.warning(
                    f"{self.name}: Error de conexion en {endpoint} "
                    f"(intento {attempt}/{self.max_retries})"
                )
                self._log_api_call(endpoint=endpoint, error_message=f"ConnectionError: {str(e)[:100]}")

            except requests.exceptions.HTTPError as e:
                logger.error(
                    f"{self.name}: HTTP {e.response.status_code} en {endpoint}"
                )
                self._log_api_call(
                    endpoint=endpoint,
                    status_code=e.response.status_code,
                    error_message=f"HTTPError: {str(e)[:100]}",
                )
                if e.response.status_code >= 500:
                    # Error del servidor, reintentar
                    time.sleep(2 ** attempt)
                    continue
                return None

            except (requests.exceptions.RequestException, ValueError) as e:
                logger.error(f"{self.name}: Error inesperado: {e}")
                self._log_api_call(endpoint=endpoint, error_message=f"Exception: {str(e)[:100]}")
                return None

            # Backoff exponencial entre reintentos
            if attempt < self.max_retries:
                wait = 2 ** attempt
                logger.debug(f"Reintentando en {wait}s...")
                time.sleep(wait)

        logger.error(
            f"{self.name}: Fallo despues de {self.max_retries} intentos: {endpoint}"
        )
        return None

    def _post(
        self,
        endpoint: str,
        json_body: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Hace una peticion POST (usado para Solana RPC).

        Args:
            endpoint: Ruta del endpoint.
            json_body: Body de la peticion como dict.

        Returns:
            Respuesta JSON como dict, o None si fallo.
        """
        url = f"{self.base_url}{endpoint}"

        for attempt in range(1, self.max_retries + 1):
            try:
                self.rate_limiter.wait()

                response = self.session.post(
                    url, json=json_body, timeout=self.timeout
                )
                self._call_count += 1

                if response.status_code == 429:
                    wait = 2 ** attempt * 10
                    logger.warning(f"{self.name}: Rate limited, esperando {wait}s")
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"{self.name}: Error POST {endpoint} "
                    f"(intento {attempt}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)

        return None

    def _save_raw(self, endpoint: str, params: Optional[dict], data: Any):
        """Guarda la respuesta cruda como JSON en data/raw/{api_name}/."""
        # Crear nombre de archivo limpio
        clean_name = endpoint.strip("/").replace("/", "_")
        if params:
            param_str = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
            clean_name += f"__{param_str}"

        # Limitar largo del nombre
        clean_name = clean_name[:200]
        timestamp = int(time.time())
        filename = f"{clean_name}__{timestamp}.json"

        filepath = self.raw_dir / filename
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except OSError as e:
            logger.warning(f"No se pudo guardar raw: {e}")

    @property
    def call_count(self) -> int:
        """Numero total de llamadas HTTP realizadas."""
        return self._call_count

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"calls={self._call_count})"
        )
