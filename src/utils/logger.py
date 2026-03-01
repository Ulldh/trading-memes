"""
logger.py - Configuracion centralizada de logging.

Uso:
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Mensaje informativo")
    logger.error("Algo salio mal")
"""

import logging
import sys

# Importar config de forma segura (puede fallar si se ejecuta aislado)
try:
    from config import LOG_LEVEL, LOG_FORMAT
except ImportError:
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    """
    Crea y devuelve un logger configurado.

    Args:
        name: Nombre del logger (normalmente __name__ del modulo).

    Returns:
        Logger configurado con formato y nivel apropiados.
    """
    logger = logging.getLogger(name)

    # Solo configurar si no tiene handlers (evita duplicados)
    if not logger.handlers:
        logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

        # Handler para consola
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

        formatter = logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger
