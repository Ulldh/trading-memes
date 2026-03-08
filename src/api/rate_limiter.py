"""
rate_limiter.py - Rate limiter con algoritmo Token Bucket.

Controla cuantas llamadas por minuto hacemos a cada API para no exceder
los limites gratuitos. Cada API tiene su propio "cubo" de tokens.

Concepto Token Bucket:
- El cubo se llena con tokens a una tasa constante (ej: 30 tokens/minuto).
- Cada llamada consume 1 token.
- Si no hay tokens disponibles, esperamos a que se recargue.
- Permite "rafagas" cortas si hay tokens acumulados.
"""

import time
import threading
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Rate limiter thread-safe usando algoritmo Token Bucket.

    Args:
        calls_per_minute: Numero maximo de llamadas permitidas por minuto.
        name: Nombre identificador (para logs).

    Ejemplo:
        limiter = RateLimiter(calls_per_minute=30, name="geckoterminal")
        limiter.wait()  # Espera si es necesario antes de hacer una llamada
    """

    def __init__(self, calls_per_minute: int, name: str = "default"):
        self.name = name
        self.calls_per_minute = calls_per_minute

        # Convertir a tokens por segundo
        # Ej: 30 calls/min = 0.5 tokens/segundo
        self.tokens_per_second = calls_per_minute / 60.0

        # Limitar rafaga inicial para evitar 429 en APIs estrictas.
        # Un burst de 30 calls instantaneas dispara rate limits aunque
        # el promedio sea correcto. Limitamos a 5 tokens de burst.
        self.max_tokens = min(calls_per_minute, 5)
        self.tokens = float(self.max_tokens)

        # Timestamp de la ultima vez que recargamos tokens
        self.last_refill = time.monotonic()

        # Lock para thread safety (multiples hilos pueden llamar wait())
        self._lock = threading.Lock()

        logger.debug(
            f"RateLimiter '{name}' creado: {calls_per_minute} calls/min"
        )

    def _refill(self):
        """Recarga tokens basado en el tiempo transcurrido."""
        now = time.monotonic()
        elapsed = now - self.last_refill

        # Calcular cuantos tokens nuevos se generaron
        new_tokens = elapsed * self.tokens_per_second

        # Agregar tokens sin exceder el maximo
        self.tokens = min(self.max_tokens, self.tokens + new_tokens)
        self.last_refill = now

    def wait(self):
        """
        Espera hasta que haya un token disponible, luego consume uno.

        Este metodo es BLOQUEANTE: si no hay tokens, duerme el hilo
        hasta que se recargue uno. Es thread-safe.
        """
        with self._lock:
            self._refill()

            if self.tokens >= 1:
                # Hay token disponible, consumirlo inmediatamente
                self.tokens -= 1
                return

            # No hay tokens, calcular cuanto hay que esperar
            wait_time = (1 - self.tokens) / self.tokens_per_second
            logger.debug(
                f"RateLimiter '{self.name}': esperando {wait_time:.2f}s"
            )

        # Esperar FUERA del lock (para no bloquear otros hilos)
        time.sleep(wait_time)

        # Consumir el token despues de esperar
        with self._lock:
            self._refill()
            self.tokens = max(0, self.tokens - 1)

    @property
    def available_tokens(self) -> float:
        """Tokens disponibles actualmente (informativo)."""
        with self._lock:
            self._refill()
            return self.tokens
