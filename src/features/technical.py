"""
technical.py - Features de analisis tecnico a partir de datos OHLCV.

Este modulo calcula indicadores tecnicos clasicos que capturan patrones de
momentum, perfil de volumen y edad del token:

    - Momentum: Detecta la fuerza y direccion del movimiento del precio.
      Un token con momentum creciente puede ser señal de interes real.
    - Volume Profile: Analiza la relacion entre precio y volumen para
      detectar acumulacion, distribucion o divergencias.
    - Token Age: Edad del token y timing del lanzamiento, que pueden
      indicar la fase del ciclo de vida en que se encuentra.

Conceptos clave:
    - RSI (Relative Strength Index): Mide fuerza relativa del precio (0-100).
      >70 = sobrecompra, <30 = sobreventa.
    - VWAP (Volume Weighted Average Price): Precio medio ponderado por volumen.
      Precio > VWAP = el token cotiza por encima de su "precio justo".
    - OBV (On-Balance Volume): Acumula volumen con signo del precio.
      OBV creciente = acumulacion (buena señal).
    - Momentum: Cambio porcentual del precio en ventanas de tiempo.

Features que calcula (11 en total):

    Momentum (4):
        - rsi_14: RSI de 14 periodos (0-100)
        - momentum_3d: Retorno porcentual ultimos 3 dias
        - momentum_7d: Retorno porcentual ultimos 7 dias
        - price_acceleration: momentum_3d - momentum_7d (aceleracion)

    Volume Profile (4):
        - vwap_ratio: close / VWAP (>1 = por encima de precio justo)
        - obv_trend: Pendiente de OBV en ultimos 7 dias (regresion lineal)
        - volume_momentum: volumen actual / volumen medio 7d
        - volume_price_corr: Correlacion precio-volumen en 7d

    Token Age (3):
        - hours_since_launch: Horas desde el primer candle
        - is_first_week: 1 si token tiene < 7 dias, 0 si no
        - launch_hour_utc: Hora UTC del primer candle (0-23)
"""

import numpy as np
import pandas as pd
from datetime import timedelta

from src.utils.helpers import safe_float, safe_divide
from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_technical_features(ohlcv_df: pd.DataFrame) -> dict:
    """
    Extrae features de analisis tecnico de datos OHLCV.

    Calcula indicadores de momentum, perfil de volumen y edad del token
    a partir de los datos de velas (candles). Todas las features se calculan
    de forma segura, devolviendo None cuando no hay datos suficientes.

    Args:
        ohlcv_df: DataFrame con columnas [timestamp, open, high, low, close, volume]
                  ordenado por timestamp (mas antiguo primero).

    Returns:
        dict con features calculadas. Valores None si no se pueden calcular.

    Ejemplo:
        >>> features = extract_technical_features(ohlcv_df)
        >>> features["rsi_14"]
        55.3  # RSI neutral
        >>> features["vwap_ratio"]
        1.05  # Precio 5% por encima del VWAP
    """

    # Inicializar todos los features con None
    features = {
        # Momentum
        "rsi_14": None,
        "momentum_3d": None,
        "momentum_7d": None,
        "price_acceleration": None,
        # Volume Profile
        "vwap_ratio": None,
        "obv_trend": None,
        "volume_momentum": None,
        "volume_price_corr": None,
        # Token Age
        "hours_since_launch": None,
        "is_first_week": None,
        "launch_hour_utc": None,
    }

    # Verificar que hay datos
    if ohlcv_df is None or ohlcv_df.empty:
        return features

    # Copiar y preparar el DataFrame
    df = ohlcv_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Necesitamos al menos 3 candles para calcular la mayoria de features
    if len(df) < 3:
        # Aun con pocos datos, podemos calcular token age
        _compute_token_age_features(df, features)
        return features

    # Convertir columnas numericas de forma segura
    df["close"] = df["close"].apply(safe_float)
    df["open"] = df["open"].apply(safe_float)
    df["high"] = df["high"].apply(safe_float)
    df["low"] = df["low"].apply(safe_float)
    df["volume"] = df["volume"].apply(safe_float)

    # Tiempo del primer y ultimo candle
    first_time = df["timestamp"].iloc[0]
    last_time = df["timestamp"].iloc[-1]

    # ============================================================
    # MOMENTUM (4 features)
    # ============================================================

    # --- RSI de 14 periodos ---
    # RSI = 100 - 100 / (1 + avg_gain / avg_loss)
    # Mide si el precio ha subido o bajado mas en los ultimos 14 periodos
    _compute_rsi_14(df, features)

    # --- Momentum 3d y 7d ---
    # Cambio porcentual del precio en ventanas de 3 y 7 dias
    _compute_momentum(df, first_time, features)

    # --- Price Acceleration ---
    # Diferencia entre momentum corto y largo plazo
    # Positivo = el token se esta acelerando (momentum creciente)
    # Negativo = el token se esta frenando
    if features["momentum_3d"] is not None and features["momentum_7d"] is not None:
        features["price_acceleration"] = features["momentum_3d"] - features["momentum_7d"]

    # ============================================================
    # VOLUME PROFILE (4 features)
    # ============================================================

    # --- VWAP Ratio ---
    # VWAP = suma(precio * volumen) / suma(volumen)
    # Ratio > 1 = precio por encima del promedio ponderado (demanda fuerte)
    _compute_vwap_ratio(df, features)

    # --- OBV Trend ---
    # On-Balance Volume: acumula volumen cuando el precio sube, resta cuando baja
    # Pendiente positiva de OBV = acumulacion (buena señal)
    _compute_obv_trend(df, first_time, features)

    # --- Volume Momentum ---
    # Volumen del ultimo candle vs promedio de 7 dias
    # > 1 = volumen por encima del promedio (interes creciente)
    _compute_volume_momentum(df, first_time, features)

    # --- Volume-Price Correlation ---
    # Correlacion entre cambios de precio y cambios de volumen en 7d
    # Correlacion positiva = precio y volumen se mueven juntos (tendencia sana)
    _compute_volume_price_corr(df, first_time, features)

    # ============================================================
    # TOKEN AGE (3 features)
    # ============================================================
    _compute_token_age_features(df, features)

    return features


# ============================================================
# FUNCIONES AUXILIARES (privadas)
# ============================================================


def _compute_rsi_14(df: pd.DataFrame, features: dict) -> None:
    """
    Calcula RSI de 14 periodos.

    RSI (Relative Strength Index) mide la velocidad y magnitud de los
    cambios de precio. Usa los ultimos 14 candles disponibles (o todos
    si hay menos de 14, siempre que sean al menos 3).

    Formula:
        RSI = 100 - 100 / (1 + RS)
        RS = promedio_ganancias / promedio_perdidas

    Args:
        df: DataFrame OHLCV preparado.
        features: Dict donde se almacena el resultado.
    """
    try:
        # Usar hasta 14 periodos (o lo que haya disponible)
        period = min(14, len(df))
        if period < 3:
            return

        # Tomar los ultimos N candles para el calculo
        close = df["close"].iloc[-period:]

        # Calcular cambios de precio entre candles consecutivos
        price_changes = close.diff().dropna()

        if len(price_changes) < 2:
            return

        # Separar ganancias y perdidas
        gains = price_changes.where(price_changes > 0, 0)
        losses = -price_changes.where(price_changes < 0, 0)

        # Promedio de ganancias y perdidas
        avg_gain = gains.mean()
        avg_loss = losses.mean()

        if pd.notna(avg_gain) and pd.notna(avg_loss):
            if avg_loss > 0:
                # RS = ratio ganancias / perdidas
                rs = avg_gain / avg_loss
                # RSI = 100 - 100 / (1 + RS)
                rsi = 100.0 - (100.0 / (1.0 + rs))
                features["rsi_14"] = float(rsi)
            elif avg_gain > 0:
                # Solo ganancias, sin perdidas -> RSI = 100
                features["rsi_14"] = 100.0
            else:
                # Sin cambios -> RSI = 50 (neutral)
                features["rsi_14"] = 50.0

    except (ValueError, ZeroDivisionError, IndexError, TypeError) as e:
        # Si hay error en el calculo, el feature queda None
        logger.debug(f"Error calculando rsi_14: {e}")


def _compute_momentum(df: pd.DataFrame, first_time: pd.Timestamp, features: dict) -> None:
    """
    Calcula momentum de 3 y 7 dias.

    Momentum = cambio porcentual del precio de cierre entre dos puntos
    en el tiempo. Ejemplo: si el precio paso de $1 a $1.50 en 3 dias,
    momentum_3d = 0.5 (50%).

    Args:
        df: DataFrame OHLCV preparado.
        first_time: Timestamp del primer candle.
        features: Dict donde se almacenan los resultados.
    """
    try:
        last_close = safe_float(df["close"].iloc[-1])
        if last_close <= 0:
            return

        # Momentum 3d: buscar el candle mas cercano a 3 dias antes del ultimo
        last_time = df["timestamp"].iloc[-1]

        target_3d = last_time - timedelta(days=3)
        close_3d = _get_close_at_time(df, target_3d)
        if close_3d is not None and close_3d > 0:
            features["momentum_3d"] = (last_close / close_3d) - 1.0

        # Momentum 7d: buscar el candle mas cercano a 7 dias antes del ultimo
        target_7d = last_time - timedelta(days=7)
        close_7d = _get_close_at_time(df, target_7d)
        if close_7d is not None and close_7d > 0:
            features["momentum_7d"] = (last_close / close_7d) - 1.0

    except (ValueError, ZeroDivisionError, IndexError, TypeError) as e:
        logger.debug(f"Error calculando momentum: {e}")


def _get_close_at_time(df: pd.DataFrame, target_time: pd.Timestamp) -> float:
    """
    Encuentra el precio de cierre mas cercano a un tiempo objetivo.

    Busca el candle cuyo timestamp es mas cercano al target_time y
    devuelve su precio de cierre.

    Args:
        df: DataFrame OHLCV con columna 'timestamp' ya en datetime.
        target_time: Tiempo objetivo a buscar.

    Returns:
        Precio de cierre del candle mas cercano, o None si no hay datos.
    """
    if df.empty:
        return None

    # Calcular diferencia absoluta con el target
    time_diffs = (df["timestamp"] - target_time).abs()
    closest_idx = time_diffs.idxmin()
    close_val = safe_float(df.loc[closest_idx, "close"])

    return close_val if close_val > 0 else None


def _compute_vwap_ratio(df: pd.DataFrame, features: dict) -> None:
    """
    Calcula el ratio close / VWAP.

    VWAP (Volume Weighted Average Price) = suma(precio_tipico * volumen) / suma(volumen)
    donde precio_tipico = (high + low + close) / 3.

    Ratio > 1: el precio actual esta por encima del precio justo ponderado por volumen.
    Ratio < 1: el precio actual esta por debajo (posible oportunidad o debilidad).

    Args:
        df: DataFrame OHLCV preparado.
        features: Dict donde se almacena el resultado.
    """
    try:
        # Precio tipico = (high + low + close) / 3
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0

        # Filtrar candles con volumen > 0
        valid_mask = df["volume"] > 0
        if valid_mask.sum() < 1:
            return

        # VWAP = suma(precio_tipico * volumen) / suma(volumen)
        tp_vol = (typical_price * df["volume"])[valid_mask]
        total_vol = df["volume"][valid_mask].sum()

        vwap = safe_divide(tp_vol.sum(), total_vol)
        if vwap <= 0:
            return

        # Ratio = precio actual / VWAP
        current_close = safe_float(df["close"].iloc[-1])
        if current_close > 0:
            features["vwap_ratio"] = safe_divide(current_close, vwap)

    except (ValueError, ZeroDivisionError, IndexError, TypeError) as e:
        logger.debug(f"Error calculando vwap_ratio: {e}")


def _compute_obv_trend(df: pd.DataFrame, first_time: pd.Timestamp, features: dict) -> None:
    """
    Calcula la tendencia del On-Balance Volume (OBV) en 7 dias.

    OBV acumula volumen con el signo del cambio de precio:
    - Si close > close_anterior: OBV += volumen
    - Si close < close_anterior: OBV -= volumen
    - Si close == close_anterior: OBV no cambia

    La pendiente de OBV (regresion lineal) indica tendencia:
    - Pendiente positiva = acumulacion (compradores dominan)
    - Pendiente negativa = distribucion (vendedores dominan)

    Args:
        df: DataFrame OHLCV preparado.
        first_time: Timestamp del primer candle.
        features: Dict donde se almacena el resultado.
    """
    try:
        # Filtrar ventana de 7 dias
        mask_7d = df["timestamp"] <= first_time + timedelta(days=7)
        df_7d = df[mask_7d]

        if len(df_7d) < 3:
            return

        # Calcular OBV
        close = df_7d["close"].values
        volume = df_7d["volume"].values

        obv = np.zeros(len(close))
        obv[0] = volume[0]

        for i in range(1, len(close)):
            if close[i] > close[i - 1]:
                obv[i] = obv[i - 1] + volume[i]
            elif close[i] < close[i - 1]:
                obv[i] = obv[i - 1] - volume[i]
            else:
                obv[i] = obv[i - 1]

        # Regresion lineal de OBV para obtener la pendiente
        x = np.arange(len(obv))
        slope, _ = np.polyfit(x, obv, 1)

        # Normalizar por volumen medio para comparabilidad entre tokens
        vol_mean = np.mean(volume[volume > 0]) if np.any(volume > 0) else 0
        if vol_mean > 0:
            features["obv_trend"] = float(slope / vol_mean)
        else:
            features["obv_trend"] = 0.0

    except (np.linalg.LinAlgError, ValueError, ZeroDivisionError, IndexError, TypeError) as e:
        logger.debug(f"Error calculando obv_trend: {e}")


def _compute_volume_momentum(df: pd.DataFrame, first_time: pd.Timestamp, features: dict) -> None:
    """
    Calcula el ratio entre el volumen actual y el volumen medio de 7 dias.

    Volume momentum > 1 = volumen por encima del promedio (interes creciente).
    Volume momentum < 1 = volumen por debajo del promedio (desinteres).

    Args:
        df: DataFrame OHLCV preparado.
        first_time: Timestamp del primer candle.
        features: Dict donde se almacena el resultado.
    """
    try:
        # Ventana de 7 dias
        mask_7d = df["timestamp"] <= first_time + timedelta(days=7)
        df_7d = df[mask_7d]

        if len(df_7d) < 2:
            return

        # Filtrar volumenes > 0
        volumes = df_7d["volume"]
        valid_vols = volumes[volumes > 0]

        if len(valid_vols) < 2:
            return

        # Volumen del ultimo candle vs media
        last_vol = safe_float(valid_vols.iloc[-1])
        mean_vol = valid_vols.mean()

        features["volume_momentum"] = safe_divide(last_vol, mean_vol)

    except (ValueError, ZeroDivisionError, IndexError, TypeError) as e:
        logger.debug(f"Error calculando volume_momentum: {e}")


def _compute_volume_price_corr(df: pd.DataFrame, first_time: pd.Timestamp, features: dict) -> None:
    """
    Calcula la correlacion entre cambios de precio y cambios de volumen en 7 dias.

    Correlacion positiva: precio y volumen se mueven juntos (tendencia sana).
    Correlacion negativa: precio sube pero volumen baja (tendencia debil).
    Cerca de 0: no hay relacion clara.

    Args:
        df: DataFrame OHLCV preparado.
        first_time: Timestamp del primer candle.
        features: Dict donde se almacena el resultado.
    """
    try:
        # Ventana de 7 dias
        mask_7d = df["timestamp"] <= first_time + timedelta(days=7)
        df_7d = df[mask_7d]

        if len(df_7d) < 4:
            return

        # Calcular cambios porcentuales
        price_changes = df_7d["close"].pct_change().dropna()
        volume_changes = df_7d["volume"].pct_change().dropna()

        # Alinear indices (ambos empiezan desde el segundo candle)
        if len(price_changes) < 3 or len(volume_changes) < 3:
            return

        # Reemplazar inf/nan por 0 para evitar problemas en correlacion
        price_changes = price_changes.replace([np.inf, -np.inf], 0).fillna(0)
        volume_changes = volume_changes.replace([np.inf, -np.inf], 0).fillna(0)

        # Verificar que hay varianza (correlacion necesita variacion en ambas series)
        if price_changes.std() == 0 or volume_changes.std() == 0:
            features["volume_price_corr"] = 0.0
            return

        # Correlacion de Pearson
        corr = price_changes.corr(volume_changes)

        if pd.notna(corr):
            features["volume_price_corr"] = float(corr)

    except (ValueError, ZeroDivisionError, IndexError, TypeError) as e:
        logger.debug(f"Error calculando volume_price_corr: {e}")


def _compute_token_age_features(df: pd.DataFrame, features: dict) -> None:
    """
    Calcula features de edad del token basados en timestamps OHLCV.

    Usa el primer y ultimo candle para determinar:
    - Horas desde el lanzamiento
    - Si el token tiene menos de 7 dias (primera semana)
    - Hora UTC de lanzamiento (puede indicar region del equipo)

    Args:
        df: DataFrame OHLCV preparado (con timestamp ya en datetime UTC).
        features: Dict donde se almacenan los resultados.
    """
    try:
        if df.empty:
            return

        first_time = df["timestamp"].iloc[0]
        last_time = df["timestamp"].iloc[-1]

        # Horas desde el primer candle hasta el ultimo
        delta = last_time - first_time
        hours = delta.total_seconds() / 3600.0
        features["hours_since_launch"] = float(hours)

        # Es primera semana? (< 7 dias = 168 horas)
        features["is_first_week"] = 1 if hours < 168.0 else 0

        # Hora UTC del primer candle (0-23)
        # Puede indicar la region/zona horaria del equipo del token
        features["launch_hour_utc"] = int(first_time.hour)

    except (ValueError, ZeroDivisionError, IndexError, TypeError) as e:
        logger.debug(f"Error calculando token_age: {e}")
