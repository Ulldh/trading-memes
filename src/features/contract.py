"""
contract.py - Calculo de features del contrato inteligente.

Analiza propiedades tecnicas del contrato del token que pueden
indicar legitimidad o riesgo.

Conceptos clave:
    - Verificado: El codigo fuente del contrato es publico y verificado
      en el explorador de bloques. Tokens no verificados son red flag.
    - Renounced: El creador renuncio al ownership (control) del contrato.
      Sin ownership no puede modificar reglas ni hacer rug pull via contrato.
    - Contract age: Tiempo desde el deploy hasta el primer trade.
      Contratos deployados justo antes del primer trade son comunes
      en tokens legitimos, pero contratos muy viejos sin trades previos
      pueden ser sospechosos.

Features que calcula:
    - is_verified: Si el contrato esta verificado
    - is_renounced: Si el ownership fue renunciado
    - contract_age_hours: Horas entre el deploy y el primer trade
"""

from datetime import datetime, timezone
from typing import Optional


def compute_contract_features(
    contract_info: dict,
    created_at: str,
    first_trade_at: str
) -> dict:
    """
    Calcula features basados en informacion del contrato.

    Args:
        contract_info: Dict con informacion del contrato.
                       Keys esperadas: is_verified, is_renounced, deploy_timestamp.
        created_at: Timestamp ISO del deploy del contrato (ej: "2024-01-15T10:30:00Z").
        first_trade_at: Timestamp ISO del primer trade del token.

    Returns:
        Dict con los features del contrato.

    Ejemplo:
        >>> info = {"is_verified": True, "is_renounced": True}
        >>> created = "2024-01-15T10:00:00Z"
        >>> first_trade = "2024-01-15T12:00:00Z"
        >>> features = compute_contract_features(info, created, first_trade)
        >>> features["contract_age_hours"]
        2.0
    """

    # Inicializar features con None
    features = {
        "is_verified": None,
        "is_renounced": None,
        "contract_age_hours": None,
    }

    # --- Features del contrato ---
    if contract_info is not None:
        # is_verified: Codigo fuente verificado en el explorer
        # Tokens verificados son mas transparentes
        is_verified = contract_info.get("is_verified")
        if is_verified is not None:
            features["is_verified"] = bool(is_verified)

        # is_renounced: El creador renuncio al control del contrato
        # Buena señal = no puede modificar el contrato
        is_renounced = contract_info.get("is_renounced")
        if is_renounced is not None:
            features["is_renounced"] = bool(is_renounced)

    # --- contract_age_hours: tiempo entre deploy y primer trade ---
    # Calcular la diferencia en horas entre el deploy y el primer trade
    deploy_time = _parse_timestamp(created_at, contract_info)
    trade_time = _parse_iso_timestamp(first_trade_at)

    if deploy_time is not None and trade_time is not None:
        # timedelta.total_seconds() / 3600 = horas
        delta = trade_time - deploy_time
        # Solo tiene sentido si el trade fue DESPUES del deploy
        age_hours = delta.total_seconds() / 3600.0
        features["contract_age_hours"] = max(age_hours, 0.0)

    return features


def _parse_iso_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    Parsea un string ISO 8601 a datetime con timezone UTC.

    Maneja varios formatos comunes:
        - "2024-01-15T10:30:00Z"
        - "2024-01-15T10:30:00+00:00"
        - "2024-01-15T10:30:00"
        - "2024-01-15 10:30:00"

    Args:
        timestamp_str: String con la fecha en formato ISO.

    Returns:
        Datetime en UTC, o None si no se puede parsear.
    """
    if not timestamp_str or not isinstance(timestamp_str, str):
        return None

    try:
        # Intentar parsear con fromisoformat (Python 3.11+)
        # Reemplazar 'Z' por '+00:00' para compatibilidad
        clean_str = timestamp_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)

        # Si no tiene timezone, asumir UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except (ValueError, TypeError):
        return None


def _parse_timestamp(
    created_at: str,
    contract_info: Optional[dict]
) -> Optional[datetime]:
    """
    Obtiene el timestamp de deploy del contrato.

    Intenta primero usar deploy_timestamp de contract_info,
    y si no esta disponible, usa created_at.

    Args:
        created_at: Timestamp ISO del campo created_at del token.
        contract_info: Dict con informacion del contrato.

    Returns:
        Datetime del deploy, o None.
    """
    # Intentar con deploy_timestamp del contrato primero
    if contract_info is not None:
        deploy_ts = contract_info.get("deploy_timestamp")
        result = _parse_iso_timestamp(deploy_ts)
        if result is not None:
            return result

    # Fallback: usar created_at del token
    return _parse_iso_timestamp(created_at)


def compute_contract_risk_features(contract_source: dict) -> dict:
    """
    Calcula features de riesgo del contrato analizando source code / ABI.

    Solo aplica a contratos EVM (Ethereum, Base) con codigo verificado.
    Busca patrones peligrosos en el ABI o source code del contrato.

    Args:
        contract_source: Dict con informacion del contrato verificado.
                         Keys esperadas: source_code, abi (como string o list).

    Returns:
        Dict con features de riesgo del contrato.
    """
    import re

    features = {
        "is_proxy": None,
        "has_mint_function": None,
        "has_pause_function": None,
        "has_blacklist_function": None,
        "contract_risk_score": None,
    }

    if contract_source is None:
        return features

    source_code = str(contract_source.get("source_code", "") or "").lower()
    abi_raw = contract_source.get("abi", "")
    abi_str = str(abi_raw).lower() if abi_raw else ""

    # Combinar source + ABI para busqueda
    searchable = source_code + " " + abi_str

    if not searchable.strip():
        return features

    # --- is_proxy: Contrato proxy (puede cambiar logica, riesgo alto) ---
    proxy_patterns = [
        r"delegatecall", r"upgradeto", r"implementation\(\)",
        r"transparentupgradeableproxy", r"uupsproxy",
    ]
    features["is_proxy"] = any(
        re.search(p, searchable) for p in proxy_patterns
    )

    # --- has_mint_function: Puede crear tokens nuevos (inflacion) ---
    mint_patterns = [
        r"function\s+mint\b", r"\"mint\"", r"_mint\(",
    ]
    features["has_mint_function"] = any(
        re.search(p, searchable) for p in mint_patterns
    )

    # --- has_pause_function: Puede pausar transfers (congelar fondos) ---
    pause_patterns = [
        r"function\s+pause\b", r"\"pause\"", r"whennotpaused",
        r"function\s+unpause\b",
    ]
    features["has_pause_function"] = any(
        re.search(p, searchable) for p in pause_patterns
    )

    # --- has_blacklist_function: Puede bloquear wallets especificas ---
    blacklist_patterns = [
        r"blacklist", r"blocklist", r"banned", r"isblocked",
        r"function\s+ban\b", r"function\s+block\b",
    ]
    features["has_blacklist_function"] = any(
        re.search(p, searchable) for p in blacklist_patterns
    )

    # --- contract_risk_score: Score compuesto 0-10 ---
    # Cada factor de riesgo suma puntos
    score = 0
    if features["is_proxy"]:
        score += 3  # Proxy = riesgo alto (logica puede cambiar)
    if features["has_mint_function"]:
        score += 3  # Mint = riesgo alto (inflacion)
    if features["has_pause_function"]:
        score += 2  # Pause = riesgo medio (puede congelar)
    if features["has_blacklist_function"]:
        score += 2  # Blacklist = riesgo medio (puede bloquear)

    features["contract_risk_score"] = min(score, 10)

    return features
