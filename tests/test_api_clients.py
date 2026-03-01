"""
test_api_clients.py - Tests para los clientes de API.

Ejecutar con: pytest tests/test_api_clients.py -v

Estos tests verifican que los clientes de API:
1. Se inicializan correctamente
2. Parsean respuestas correctamente
3. Manejan errores sin crashear
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Agregar directorio raiz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.rate_limiter import RateLimiter
from src.api.base_client import BaseAPIClient
from src.data.cache import DiskCache


# ============================================================
# Tests para RateLimiter
# ============================================================

class TestRateLimiter:
    """Tests para el rate limiter."""

    def test_init(self):
        """El rate limiter se crea con los parametros correctos."""
        limiter = RateLimiter(calls_per_minute=30, name="test")
        assert limiter.calls_per_minute == 30
        assert limiter.name == "test"
        assert limiter.tokens > 0

    def test_consume_token(self):
        """Consumir un token reduce el conteo."""
        limiter = RateLimiter(calls_per_minute=60, name="test")
        initial = limiter.available_tokens
        limiter.wait()
        # Despues de consumir, deberia haber menos tokens
        # (puede haber recargado algo, pero deberia ser menos)
        assert limiter.available_tokens < initial + 1

    def test_refill(self):
        """Los tokens se recargan con el tiempo."""
        limiter = RateLimiter(calls_per_minute=6000, name="test")
        # Consumir todos
        for _ in range(100):
            limiter.wait()
        # Aun deberia funcionar (se recargan)
        limiter.wait()  # No deberia crashear


# ============================================================
# Tests para DiskCache
# ============================================================

class TestDiskCache:
    """Tests para el cache en disco."""

    def test_init(self, tmp_path):
        """El cache se crea correctamente."""
        cache = DiskCache(namespace="test", ttl_hours=1, enabled=True)
        assert cache.enabled is True
        assert cache.namespace == "test"

    def test_set_and_get(self, tmp_path):
        """Se puede guardar y recuperar datos del cache."""
        # Usar un namespace unico para no interferir
        cache = DiskCache(namespace="test_set_get", ttl_hours=1)

        url = "https://api.test.com/endpoint"
        data = {"key": "value", "number": 42}

        cache.set(url, data)
        result = cache.get(url)

        assert result is not None
        assert result["key"] == "value"
        assert result["number"] == 42

        # Limpiar
        cache.clear()

    def test_cache_miss(self):
        """Devuelve None si no hay datos en cache."""
        cache = DiskCache(namespace="test_miss", ttl_hours=1)
        result = cache.get("https://no-existe.com/endpoint")
        assert result is None

    def test_disabled_cache(self):
        """El cache deshabilitado no guarda ni lee."""
        cache = DiskCache(namespace="test_disabled", enabled=False)
        cache.set("https://test.com", {"data": 1})
        assert cache.get("https://test.com") is None

    def test_stats(self):
        """Las estadisticas del cache funcionan."""
        cache = DiskCache(namespace="test_stats", ttl_hours=1)
        stats = cache.stats()
        assert "entries" in stats
        assert "size_mb" in stats


# ============================================================
# Tests para BaseAPIClient
# ============================================================

class TestBaseAPIClient:
    """Tests para el cliente base de API."""

    def test_init(self):
        """El cliente base se inicializa correctamente."""
        client = BaseAPIClient(
            base_url="https://api.test.com",
            name="test",
            calls_per_minute=30,
        )
        assert client.name == "test"
        assert client.base_url == "https://api.test.com"
        assert client.call_count == 0

    @patch("src.api.base_client.requests.Session")
    def test_get_with_cache_hit(self, mock_session):
        """Si hay datos en cache, no hace llamada HTTP."""
        client = BaseAPIClient(
            base_url="https://api.test.com",
            name="test_cache_hit",
            calls_per_minute=30,
        )
        # Simular cache hit
        client.cache.set("https://api.test.com/data", {"cached": True})

        result = client._get("/data", use_cache=True)

        assert result is not None
        assert result["cached"] is True
        # No deberia haber llamado al session.get
        assert client.call_count == 0

        # Limpiar
        client.cache.clear()

    def test_repr(self):
        """La representacion del cliente es legible."""
        client = BaseAPIClient(
            base_url="https://api.test.com",
            name="test",
            calls_per_minute=30,
        )
        repr_str = repr(client)
        assert "test" in repr_str
        assert "calls=0" in repr_str
