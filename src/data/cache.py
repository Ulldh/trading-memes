"""
cache.py - Cache local en disco para respuestas de API.

Guarda las respuestas de cada API como archivos JSON en disco.
Esto evita repetir llamadas innecesarias y preserva datos historicos.

Estructura del cache:
    .cache/
    ├── geckoterminal/
    │   ├── abc123def456.json    # Hash de la URL como nombre
    │   └── ...
    ├── dexscreener/
    │   └── ...
    └── ...
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Any

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Importar config de forma segura
try:
    from config import CACHE_DIR, CACHE_TTL_HOURS, CACHE_ENABLED
except ImportError:
    CACHE_DIR = Path(".cache")
    CACHE_TTL_HOURS = 24
    CACHE_ENABLED = True


class DiskCache:
    """
    Cache en disco que guarda respuestas de API como archivos JSON.

    Cada entrada tiene un TTL (Time To Live) despues del cual se considera
    expirada y se vuelve a consultar la API.

    Args:
        namespace: Nombre de la API (crea un subdirectorio).
        ttl_hours: Horas que la entrada es valida.
        enabled: Si False, el cache no guarda ni lee nada.

    Ejemplo:
        cache = DiskCache(namespace="geckoterminal", ttl_hours=24)

        # Buscar en cache
        data = cache.get("https://api.geckoterminal.com/pools/...")
        if data is None:
            data = requests.get(...).json()
            cache.set("https://api.geckoterminal.com/pools/...", data)
    """

    def __init__(
        self,
        namespace: str = "default",
        ttl_hours: float = CACHE_TTL_HOURS,
        enabled: bool = CACHE_ENABLED,
    ):
        self.namespace = namespace
        self.ttl_seconds = ttl_hours * 3600
        self.enabled = enabled

        # Crear directorio del cache
        self.cache_dir = Path(CACHE_DIR) / namespace
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _make_key(self, url: str, params: Optional[dict] = None) -> str:
        """
        Genera un hash unico para una combinacion URL + parametros.

        Args:
            url: URL de la peticion.
            params: Parametros de query string.

        Returns:
            Hash MD5 como string hexadecimal.
        """
        # Combinar URL y params ordenados para un hash consistente
        key_parts = url
        if params:
            sorted_params = sorted(params.items())
            key_parts += str(sorted_params)

        return hashlib.md5(key_parts.encode()).hexdigest()

    def _get_path(self, key: str) -> Path:
        """Devuelve la ruta del archivo de cache para un key dado."""
        return self.cache_dir / f"{key}.json"

    def get(self, url: str, params: Optional[dict] = None) -> Optional[Any]:
        """
        Busca una respuesta en el cache.

        Args:
            url: URL original de la peticion.
            params: Parametros de la peticion.

        Returns:
            Los datos cacheados (dict/list) o None si no hay cache o expiro.
        """
        if not self.enabled:
            return None

        key = self._make_key(url, params)
        path = self._get_path(key)

        if not path.exists():
            return None

        try:
            with open(path, "r") as f:
                cached = json.load(f)

            # Verificar si expiro
            cached_at = cached.get("_cached_at", 0)
            if time.time() - cached_at > self.ttl_seconds:
                logger.debug(f"Cache EXPIRADO: {url[:80]}...")
                return None

            logger.debug(f"Cache HIT: {url[:80]}...")
            return cached.get("data")

        except (json.JSONDecodeError, KeyError):
            # Cache corrupto, ignorar
            logger.warning(f"Cache corrupto, eliminando: {path}")
            path.unlink(missing_ok=True)
            return None

    def set(self, url: str, data: Any, params: Optional[dict] = None):
        """
        Guarda una respuesta en el cache.

        Args:
            url: URL original de la peticion.
            data: Datos a cachear (debe ser serializable a JSON).
            params: Parametros de la peticion.
        """
        if not self.enabled:
            return

        key = self._make_key(url, params)
        path = self._get_path(key)

        try:
            cache_entry = {
                "_cached_at": time.time(),
                "_url": url,
                "data": data,
            }

            with open(path, "w") as f:
                json.dump(cache_entry, f, indent=2, default=str)

            logger.debug(f"Cache SET: {url[:80]}...")

        except (TypeError, OSError) as e:
            logger.warning(f"No se pudo cachear {url[:80]}: {e}")

    def clear(self):
        """Elimina todas las entradas del cache para este namespace."""
        if not self.cache_dir.exists():
            return

        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
            count += 1

        logger.info(f"Cache '{self.namespace}' limpiado: {count} entradas eliminadas")

    def stats(self) -> dict:
        """Devuelve estadisticas del cache."""
        if not self.cache_dir.exists():
            return {"entries": 0, "size_mb": 0}

        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)

        return {
            "entries": len(files),
            "size_mb": round(total_size / (1024 * 1024), 2),
        }
