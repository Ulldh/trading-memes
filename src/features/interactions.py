"""
interactions.py - Features de interaccion entre señales existentes.

Las memecoins "gem" suelen mostrar señales compuestas: no es una sola metrica
la que predice el exito, sino la combinacion de varias. Por ejemplo, un spike
de volumen SOLO no dice mucho, pero un spike de volumen + acumulacion de
ballenas es una señal mucho mas fuerte.

Este modulo toma el dict de features ya calculados por todos los demas modulos
y genera combinaciones (multiplicaciones, ratios, productos) que capturan
estas señales compuestas.

IMPORTANTE: Este modulo debe ejecutarse DESPUES de todos los demas modulos
de features, ya que depende de los valores que ellos calculan.

Features que calcula (8 en total):

    Señales de compra:
        - whale_volume_signal: Ballenas comprando + spike de volumen
        - buyer_momentum: Compradores creciendo + momentum positivo
        - technical_strength: RSI alcista + precio sobre VWAP

    Salud del token:
        - liquidity_health: Liquidez creciendo + baja volatilidad
        - volume_liquidity_efficiency: Volumen sostenido relativo a liquidez

    Riesgo:
        - smart_risk_score: Mint authority + concentracion de holders
        - concentration_trend: Top holder grande + rotacion de ballenas

    Normalizacion:
        - age_adjusted_return: Retorno normalizado por edad del token
"""

import math

from src.utils.helpers import safe_divide, safe_float


def extract_interaction_features(features_dict: dict) -> dict:
    """
    Calcula features de interaccion a partir de features ya calculados.

    Toma el dict de features existentes (de todos los modulos) y genera
    combinaciones que capturan señales compuestas. Cada feature de interaccion
    es el producto o ratio de 2+ features base, diseñado para amplificar
    señales que son mas predictivas en combinacion.

    Args:
        features_dict: Dict con todas las features ya calculadas para un token.
                       Viene del acumulador all_features de FeatureBuilder.

    Returns:
        dict con 8 features de interaccion. Valores por defecto 0.0 si
        alguna feature base es None o falta.

    Ejemplo:
        >>> feats = {"whale_accumulation_7d": 5.0, "volume_spike_ratio": 3.0, ...}
        >>> interactions = extract_interaction_features(feats)
        >>> interactions["whale_volume_signal"]
        15.0  # 5.0 * 3.0 = señal fuerte de pump
    """

    # Inicializar todas las features de interaccion con 0.0
    interactions = {
        "whale_volume_signal": 0.0,
        "liquidity_health": 0.0,
        "buyer_momentum": 0.0,
        "smart_risk_score": 0.0,
        "technical_strength": 0.0,
        "age_adjusted_return": 0.0,
        "volume_liquidity_efficiency": 0.0,
        "concentration_trend": 0.0,
    }

    # Helper local para obtener un valor numerico del dict de features.
    # Si el valor es None, falta o no es numerico, devuelve el default.
    def _get(key: str, default: float = 0.0) -> float:
        """Obtiene un valor numerico del dict de features de forma segura."""
        val = features_dict.get(key)
        if val is None:
            return default
        return safe_float(val, default=default)

    # ============================================================
    # 1. WHALE VOLUME SIGNAL
    # ============================================================
    # Ballenas acumulando + spike de volumen = señal fuerte de pump
    # whale_accumulation_7d: cambio en % del top1 holder (positivo = acumulacion)
    # volume_spike_ratio: max(vol) / mean(vol) en 7d (alto = spike)
    whale_acc = _get("whale_accumulation_7d")
    vol_spike = _get("volume_spike_ratio")
    interactions["whale_volume_signal"] = whale_acc * vol_spike

    # ============================================================
    # 2. LIQUIDITY HEALTH
    # ============================================================
    # Liquidez creciendo + baja volatilidad = token saludable
    # liquidity_growth_7d: crecimiento % de liquidez en 7d
    # volatility_7d: desviacion std de retornos en 7d (menor = mas estable)
    # Penalizamos la volatilidad: (1 - min(vol, 1.0)) → 0 si vol >= 1, 1 si vol = 0
    liq_growth = _get("liquidity_growth_7d")
    vol_7d = _get("volatility_7d")
    interactions["liquidity_health"] = liq_growth * (1.0 - min(vol_7d, 1.0))

    # ============================================================
    # 3. BUYER MOMENTUM
    # ============================================================
    # Compradores creciendo + momentum de precio positivo = fase de acumulacion
    # buyer_growth_rate: tasa de cambio de compradores entre snapshots
    # momentum_7d: retorno % del precio en 7 dias
    buyer_gr = _get("buyer_growth_rate")
    mom_7d = _get("momentum_7d")
    interactions["buyer_momentum"] = buyer_gr * mom_7d

    # ============================================================
    # 4. SMART RISK SCORE
    # ============================================================
    # Mint authority activa + holders muy concentrados = alto riesgo de rug
    # has_mint_authority: bool (True/False, se convierte a 1.0/0.0)
    # holder_herfindahl: indice de concentracion (0 a 1, mayor = mas concentrado)
    # Usamos 1 / (herfindahl + 0.01) para amplificar el riesgo cuando hay concentracion
    has_mint = _get("has_mint_authority")
    # has_mint_authority es bool, convertir a float (True → 1.0, False → 0.0)
    mint_val = float(has_mint) if has_mint else 0.0
    herfindahl = _get("holder_herfindahl")
    interactions["smart_risk_score"] = mint_val * safe_divide(
        1.0, herfindahl + 0.01
    )

    # ============================================================
    # 5. TECHNICAL STRENGTH
    # ============================================================
    # RSI en zona alcista + precio por encima del VWAP = tecnicamente fuerte
    # rsi_14: RSI de 14 periodos (0-100), normalizamos a 0-1
    # vwap_ratio: close / VWAP (>1 = por encima del precio justo)
    rsi = _get("rsi_14")
    vwap = _get("vwap_ratio")
    interactions["technical_strength"] = (rsi / 100.0) * max(vwap, 0.0)

    # ============================================================
    # 6. AGE ADJUSTED RETURN
    # ============================================================
    # Normaliza el retorno por la edad del token usando log.
    # Un 100% en 2 dias es mas impresionante que 100% en 30 dias.
    # log(horas + 1) crece rapido al inicio y se aplana despues.
    ret_7d = _get("return_24h")  # Usamos return_24h ya que return_7d fue eliminado
    hours = _get("hours_since_launch", default=0.0)
    # Asegurar que hours >= 0 para evitar log de negativo
    safe_hours = max(hours, 0.0)
    log_age = math.log(safe_hours + 1.0)
    if log_age > 0:
        interactions["age_adjusted_return"] = safe_divide(ret_7d, log_age)

    # ============================================================
    # 7. VOLUME LIQUIDITY EFFICIENCY
    # ============================================================
    # Que tan eficientemente se genera volumen relativo a la liquidez
    # volume_sustainability_3d: vol segunda mitad / vol primera mitad (>1 = sostenido)
    # liq_to_mcap_ratio: liquidez / market cap
    vol_sust = _get("volume_sustainability_3d")
    liq_mcap = _get("liq_to_mcap_ratio")
    interactions["volume_liquidity_efficiency"] = safe_divide(
        vol_sust, liq_mcap + 0.01
    )

    # ============================================================
    # 8. CONCENTRATION TREND
    # ============================================================
    # Si el top holder es grande Y hay alta rotacion de ballenas → distribucion (bueno)
    # Si el top holder es grande Y baja rotacion → ballena sentada (riesgo)
    # top1_holder_pct: % del supply del holder mas grande
    # whale_turnover_rate: % de top20 que cambio entre snapshots
    top1 = _get("top1_holder_pct")
    turnover = _get("whale_turnover_rate")
    interactions["concentration_trend"] = top1 * turnover

    return interactions
