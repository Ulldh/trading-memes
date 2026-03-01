"""
helpers.py - Funciones de utilidad reutilizables.

Funciones pequeñas que se usan en multiples modulos del proyecto.
"""

import math
import re
from datetime import datetime, timezone
from typing import Optional, Union


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Division segura que devuelve un valor por defecto si el denominador es 0 o NaN.

    Args:
        numerator: Numero de arriba.
        denominator: Numero de abajo.
        default: Valor a devolver si no se puede dividir.

    Returns:
        Resultado de la division o el valor por defecto.

    Ejemplo:
        >>> safe_divide(10, 2)
        5.0
        >>> safe_divide(10, 0)
        0.0
    """
    if denominator is None or denominator == 0:
        return default
    if math.isnan(denominator) or math.isnan(numerator):
        return default
    return numerator / denominator


def pct_change(old_value: float, new_value: float) -> Optional[float]:
    """
    Calcula el cambio porcentual entre dos valores.

    Args:
        old_value: Valor anterior.
        new_value: Valor nuevo.

    Returns:
        Cambio porcentual como decimal (0.5 = 50%), o None si old_value es 0.

    Ejemplo:
        >>> pct_change(100, 150)
        0.5
        >>> pct_change(100, 50)
        -0.5
    """
    if old_value is None or old_value == 0:
        return None
    return (new_value - old_value) / old_value


def timestamp_to_datetime(ts: Union[int, float]) -> datetime:
    """
    Convierte un timestamp Unix (segundos) a datetime UTC.

    Args:
        ts: Timestamp Unix en segundos.

    Returns:
        Datetime en UTC.

    Ejemplo:
        >>> timestamp_to_datetime(1700000000)
        datetime.datetime(2023, 11, 14, 22, 13, 20, tzinfo=datetime.timezone.utc)
    """
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def safe_float(value, default: float = 0.0) -> float:
    """
    Convierte un valor a float de forma segura.

    Args:
        value: Valor a convertir (puede ser str, int, None, etc.).
        default: Valor por defecto si la conversion falla.

    Returns:
        El valor como float o el default.
    """
    if value is None:
        return default
    try:
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


def safe_int(value, default: int = 0) -> int:
    """
    Convierte un valor a int de forma segura.

    Args:
        value: Valor a convertir.
        default: Valor por defecto si la conversion falla.

    Returns:
        El valor como int o el default.
    """
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def truncate_address(address: str, chars: int = 6) -> str:
    """
    Acorta una direccion blockchain para visualizacion.

    Args:
        address: Direccion completa.
        chars: Numero de caracteres a mostrar al inicio y final.

    Returns:
        Direccion truncada (ej: "0xAbCd...1234").
    """
    if not address or len(address) <= chars * 2:
        return address or ""
    return f"{address[:chars]}...{address[-chars:]}"


def detect_chain(address: str) -> Optional[str]:
    """
    Detecta la blockchain de una direccion por su formato.

    Solana usa base58 (32-44 caracteres, sin 0/O/I/l).
    EVM (Ethereum, Base) usa 0x + 40 caracteres hexadecimales.

    Args:
        address: Contract address del token.

    Returns:
        "solana", "ethereum" o None si no se reconoce el formato.

    Ejemplo:
        >>> detect_chain("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263")
        'solana'
        >>> detect_chain("0x6982508145454Ce325dDbE47a25d4ec3d2311933")
        'ethereum'
    """
    if not address or not isinstance(address, str):
        return None

    address = address.strip()

    # EVM: 0x + 40 hex chars (Ethereum, Base, etc.)
    if re.match(r"^0x[0-9a-fA-F]{40}$", address):
        return "ethereum"

    # Solana: base58 (caracteres [1-9A-HJ-NP-Za-km-z], 32-44 chars)
    if re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", address):
        return "solana"

    return None


def log_scale(value: float, base: float = 10.0) -> Optional[float]:
    """
    Calcula log en base dada, manejando valores <= 0.

    Args:
        value: Valor a transformar.
        base: Base del logaritmo.

    Returns:
        log_base(value) o None si value <= 0.
    """
    if value is None or value <= 0:
        return None
    return math.log(value) / math.log(base)
