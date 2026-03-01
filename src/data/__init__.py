"""Modulos de recopilacion y almacenamiento de datos."""

from .storage import Storage
from .cache import DiskCache


def __getattr__(name):
    """Lazy import para evitar circular imports."""
    if name == "DataCollector":
        from .collector import DataCollector
        return DataCollector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["DataCollector", "Storage", "DiskCache"]
