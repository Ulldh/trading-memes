"""
security.py — Features de seguridad del contrato via GoPlus/RugCheck.

Estos features son criticos para detectar rugs y honeypots tempranamente.
Un token con is_honeypot=True o sell_tax>50% es practicamente un rug garantizado.

GoPlus (todas las cadenas):
    Analiza contratos inteligentes y detecta honeypots, taxes ocultos,
    owner privileges peligrosos, funciones de blacklist/mint, etc.

RugCheck (solo Solana):
    Analiza tokens on-chain y reporta riesgos especificos como
    freeze authority, mutable metadata, concentracion de LP, etc.

Features que calcula:
    - is_honeypot: Si el token es un honeypot (no se puede vender)
    - buy_tax_pct: Porcentaje de tax al comprar (0-100)
    - sell_tax_pct: Porcentaje de tax al vender (0-100)
    - is_open_source: Si el codigo fuente esta verificado
    - has_hidden_owner: Si el owner esta oculto
    - can_take_back_ownership: Si el owner puede recuperar ownership
    - has_selfdestruct: Si el contrato puede autodestruirse
    - is_mintable: Si se pueden crear tokens nuevos
    - owner_can_change_balance: Si el owner puede modificar balances
    - goplus_risk_count: Numero total de flags de riesgo activas
    - rugcheck_risk_score: Score de riesgo de RugCheck (0-100)
    - rugcheck_risk_count: Numero de riesgos reportados por RugCheck

Uso:
    from src.features.security import compute_security_features

    goplus_data = goplus_client.get_token_security("solana", "addr...")
    rugcheck_data = rugcheck_client.get_report("addr...")
    features = compute_security_features(goplus_data, rugcheck_data)
"""

from typing import Optional


def compute_security_features(
    goplus_data: dict,
    rugcheck_data: Optional[dict] = None,
) -> dict:
    """
    Calcula features de seguridad combinando GoPlus y RugCheck.

    Este modulo combina datos de dos fuentes de seguridad para crear
    un perfil completo de riesgo del token. Los features son binarios
    (0/1) o numericos (0-100), ideales para modelos ML.

    Args:
        goplus_data: Dict con datos de GoPlus (output de GoPlusClient).
                     Keys esperadas: is_honeypot, buy_tax, sell_tax,
                     is_open_source, hidden_owner, etc.
                     Puede ser dict vacio si GoPlus no tiene datos.
        rugcheck_data: Dict con datos de RugCheck (output de RugCheckClient).
                       Keys esperadas: risk_score, risk_count.
                       None si no es token de Solana o no disponible.

    Returns:
        Dict plano con todos los features de seguridad.
        Valores None indican dato no disponible.

    Ejemplo:
        >>> goplus = {"is_honeypot": True, "sell_tax": 99.0}
        >>> features = compute_security_features(goplus)
        >>> features["is_honeypot"]
        1
        >>> features["sell_tax_pct"]
        99.0
        >>> features["goplus_risk_count"]
        1  # is_honeypot es una flag de riesgo
    """
    # Inicializar todos los features con None (dato no disponible)
    features = {
        "is_honeypot": None,
        "buy_tax_pct": None,
        "sell_tax_pct": None,
        "is_open_source": None,
        "has_hidden_owner": None,
        "can_take_back_ownership": None,
        "has_selfdestruct": None,
        "is_mintable": None,
        "owner_can_change_balance": None,
        "goplus_risk_count": None,
        "rugcheck_risk_score": None,
        "rugcheck_risk_count": None,
    }

    # ============================================================
    # FEATURES DE GOPLUS (todas las cadenas)
    # ============================================================
    if goplus_data and isinstance(goplus_data, dict):
        # --- is_honeypot: 1 si es honeypot, 0 si no ---
        # Un honeypot es un token que se puede comprar pero NO vender.
        # Es la forma mas comun de scam en memecoins.
        hp = goplus_data.get("is_honeypot")
        if hp is not None:
            features["is_honeypot"] = 1 if hp else 0

        # --- Taxes de compra y venta (0-100%) ---
        # Taxes > 10% son sospechosos, > 50% es practicamente scam
        features["buy_tax_pct"] = _safe_float(goplus_data.get("buy_tax"))
        features["sell_tax_pct"] = _safe_float(goplus_data.get("sell_tax"))

        # --- is_open_source: codigo verificado ---
        # Tokens con codigo verificado son mas transparentes
        os_val = goplus_data.get("is_open_source")
        if os_val is not None:
            features["is_open_source"] = 1 if os_val else 0

        # --- has_hidden_owner: owner oculto ---
        # Si el owner esta oculto, no se puede auditar quien controla el contrato
        ho = goplus_data.get("hidden_owner")
        if ho is not None:
            features["has_hidden_owner"] = 1 if ho else 0

        # --- can_take_back_ownership ---
        # Si el owner puede recuperar ownership despues de renunciar,
        # el "renounce" es falso y no protege a los holders
        ctbo = goplus_data.get("can_take_back_ownership")
        if ctbo is not None:
            features["can_take_back_ownership"] = 1 if ctbo else 0

        # --- has_selfdestruct ---
        # Si el contrato puede autodestruirse, se pierde todo
        sd = goplus_data.get("selfdestruct")
        if sd is not None:
            features["has_selfdestruct"] = 1 if sd else 0

        # --- is_mintable ---
        # Si se pueden crear tokens nuevos, hay riesgo de dilucion
        mint = goplus_data.get("is_mintable")
        if mint is not None:
            features["is_mintable"] = 1 if mint else 0

        # --- owner_can_change_balance ---
        # Si el owner puede modificar balances directamente,
        # puede robarse los tokens de cualquier holder
        ocb = goplus_data.get("owner_change_balance")
        if ocb is not None:
            features["owner_can_change_balance"] = 1 if ocb else 0

        # --- goplus_risk_count: contar flags de riesgo activas ---
        # Cuantas mas flags de riesgo, mas peligroso el token
        risk_flags = [
            goplus_data.get("is_honeypot"),
            goplus_data.get("hidden_owner"),
            goplus_data.get("can_take_back_ownership"),
            goplus_data.get("selfdestruct"),
            goplus_data.get("is_blacklisted"),
            goplus_data.get("is_mintable"),
            goplus_data.get("owner_change_balance"),
        ]
        # Contar solo las flags que son True (excluir None y False)
        active_flags = sum(1 for f in risk_flags if f is True or f == 1)
        # Agregar tax alto como flag adicional
        buy_tax = _safe_float(goplus_data.get("buy_tax"))
        sell_tax = _safe_float(goplus_data.get("sell_tax"))
        if buy_tax is not None and buy_tax > 10:
            active_flags += 1
        if sell_tax is not None and sell_tax > 10:
            active_flags += 1

        features["goplus_risk_count"] = active_flags

    # ============================================================
    # FEATURES DE RUGCHECK (solo Solana)
    # ============================================================
    if rugcheck_data and isinstance(rugcheck_data, dict):
        # --- rugcheck_risk_score: score de riesgo 0-100 ---
        # Mayor score = mas peligroso
        score = rugcheck_data.get("risk_score")
        if score is not None:
            try:
                features["rugcheck_risk_score"] = float(score)
            except (ValueError, TypeError):
                pass

        # --- rugcheck_risk_count: numero de riesgos detectados ---
        count = rugcheck_data.get("risk_count")
        if count is not None:
            try:
                features["rugcheck_risk_count"] = int(count)
            except (ValueError, TypeError):
                pass

    return features


def _safe_float(value) -> Optional[float]:
    """
    Convierte valor a float de forma segura.

    Maneja None, strings vacios, y valores no numericos
    sin lanzar excepciones.

    Args:
        value: Valor a convertir.

    Returns:
        Float o None si no se puede convertir.
    """
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
