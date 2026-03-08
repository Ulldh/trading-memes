"""
price_action.py - Calculo de features de accion del precio (OHLCV).

Analiza los movimientos de precio, volumen y volatilidad del token.
Estos son los features mas importantes para predecir "gems":
    - Retornos: Cuanto gano/perdio en diferentes ventanas de tiempo
    - Volatilidad: Que tan bruscos son los movimientos de precio
    - Volumen: Actividad de trading y su tendencia
    - Drawdown: Cuanto cayo el precio desde su maximo

Conceptos clave:
    - OHLCV: Open (apertura), High (maximo), Low (minimo), Close (cierre), Volume
    - Retorno: (precio_final / precio_inicial) - 1
    - Drawdown: Caida desde el punto mas alto
    - Regresion lineal: Para detectar tendencia en el volumen

Features que calcula:
    - return_24h, return_48h, return_30d: Retornos por ventana
    - max_return_7d: Maximo multiple alcanzado en 7 dias
    - drawdown_from_peak_7d: Caida maxima desde el pico en 7 dias
    - volatility_24h: Volatilidad (desviacion std) en 24h
    - volatility_7d: Volatilidad en 7 dias
    - volume_spike_ratio: Pico de volumen vs promedio
    - green_candle_ratio_24h: Proporcion de velas verdes en 24h
    - first_hour_return: Retorno en la primera hora
    - volume_trend_slope: Pendiente de la tendencia de volumen
"""

import numpy as np
import pandas as pd
from datetime import timedelta
from typing import Optional

from src.utils.helpers import safe_float, safe_divide


def compute_price_action_features(ohlcv_df: pd.DataFrame) -> dict:
    """
    Calcula features de price action a partir de datos OHLCV.

    Args:
        ohlcv_df: DataFrame con columnas [timestamp, open, high, low, close, volume]
                  ordenado por timestamp (mas antiguo primero).

    Returns:
        Dict con todos los features de price action.
        Valores None para features que no se pudieron calcular.

    Ejemplo:
        >>> features = compute_price_action_features(ohlcv_df)
        >>> features["return_24h"]
        0.5  # 50% de retorno
    """

    # Inicializar todos los features con None
    # NOTA: return_7d fue eliminado porque es target leakage (correlacion directa
    # con el label binario que usa close_day7/close_day1).
    features = {
        "return_24h": None,
        "return_48h": None,
        "return_30d": None,
        "max_return_7d": None,
        "drawdown_from_peak_7d": None,
        "volatility_24h": None,
        "volatility_7d": None,
        "volume_spike_ratio": None,
        "green_candle_ratio_24h": None,
        "first_hour_return": None,
        "volume_trend_slope": None,
        "volume_concentration_ratio": None,
        "price_recovery_ratio": None,
        "volume_sustainability_3d": None,
        "close_to_high_ratio_7d": None,
        "up_days_ratio_7d": None,
        "volume_price_divergence": None,
    }

    # Verificar que hay datos
    if ohlcv_df is None or ohlcv_df.empty:
        return features

    # Copiar y preparar el DataFrame
    df = ohlcv_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Precio de cierre inicial (primer candle)
    close_0 = safe_float(df["close"].iloc[0])
    if close_0 <= 0:
        return features  # Sin precio inicial no podemos calcular retornos

    # Tiempo del primer candle (referencia para ventanas)
    first_time = df["timestamp"].iloc[0]

    # ============================================================
    # RETORNOS EN DIFERENTES VENTANAS DE TIEMPO
    # ============================================================
    # Retorno = (precio_ahora / precio_inicial) - 1
    # Ej: si paso de $1 a $1.50, retorno = 0.5 (50%)

    features["return_24h"] = _compute_return_at_window(
        df, first_time, close_0, hours=24
    )
    features["return_48h"] = _compute_return_at_window(
        df, first_time, close_0, hours=48
    )
    features["return_30d"] = _compute_return_at_window(
        df, first_time, close_0, hours=24 * 30
    )

    # ============================================================
    # MAXIMO RETORNO EN 7 DIAS
    # ============================================================
    # Cual fue el maximo multiple que alcanzo el token en sus primeros 7 dias
    # Esto captura "pumps" aunque luego haya dumpeado
    mask_7d = df["timestamp"] <= first_time + timedelta(days=7)
    df_7d = df[mask_7d]

    if not df_7d.empty:
        max_high = safe_float(df_7d["high"].max())
        features["max_return_7d"] = safe_divide(max_high, close_0) - 1.0

        # ============================================================
        # DRAWDOWN DESDE EL PICO EN 7 DIAS
        # ============================================================
        # Drawdown = (max_high - min_low_despues_del_pico) / max_high
        # Mide cuanto cayo el precio desde su punto mas alto
        if max_high > 0:
            # Encontrar el indice del maximo
            peak_idx = df_7d["high"].idxmax()

            # Solo mirar los datos DESPUES del pico
            df_after_peak = df_7d.loc[peak_idx:]
            if len(df_after_peak) > 1:
                min_low_after = safe_float(df_after_peak["low"].min())
                features["drawdown_from_peak_7d"] = safe_divide(
                    max_high - min_low_after, max_high
                )
            else:
                # Si el pico esta en el ultimo candle, no hay drawdown aun
                features["drawdown_from_peak_7d"] = 0.0

    # ============================================================
    # VOLATILIDAD
    # ============================================================
    # Volatilidad = desviacion estandar de los retornos
    # Alta volatilidad = movimientos de precio muy bruscos

    # Volatilidad en las primeras 24h (usando candles horarias)
    mask_24h = df["timestamp"] <= first_time + timedelta(hours=24)
    df_24h = df[mask_24h]

    if len(df_24h) >= 2:
        # Calcular retornos entre candles consecutivas
        returns_24h = df_24h["close"].pct_change().dropna()
        if len(returns_24h) >= 2:
            features["volatility_24h"] = float(returns_24h.std())

    # Volatilidad en 7 dias
    if len(df_7d) >= 2:
        returns_7d = df_7d["close"].pct_change().dropna()
        if len(returns_7d) >= 2:
            features["volatility_7d"] = float(returns_7d.std())

    # ============================================================
    # VOLUME SPIKE RATIO (ventana 7d)
    # ============================================================
    # Compara el volumen maximo contra el promedio en ventana de 7 dias
    # Un ratio alto indica un pico anormal de volumen (hype o manipulacion)
    if not df_7d.empty:
        volumes = df_7d["volume"].apply(safe_float)
        volumes = volumes[volumes > 0]
    else:
        volumes = pd.Series(dtype=float)

    if len(volumes) >= 2:
        max_vol = volumes.max()
        mean_vol = volumes.mean()
        features["volume_spike_ratio"] = safe_divide(max_vol, mean_vol)

    # ============================================================
    # GREEN CANDLE RATIO EN 24H
    # ============================================================
    # Proporcion de velas donde el precio subio (close > open)
    # Ratio alto = presion compradora sostenida
    if not df_24h.empty:
        green_candles = (df_24h["close"] > df_24h["open"]).sum()
        total_candles = len(df_24h)
        features["green_candle_ratio_24h"] = safe_divide(
            green_candles, total_candles
        )

    # ============================================================
    # RETORNO DE LA PRIMERA HORA
    # ============================================================
    # Como se comporto el precio en la primera hora de vida
    # Subidas extremas en la primera hora suelen ser red flags
    mask_1h = df["timestamp"] <= first_time + timedelta(hours=1)
    df_1h = df[mask_1h]

    if len(df_1h) >= 2:
        close_1h = safe_float(df_1h["close"].iloc[-1])
        if close_0 > 0:
            features["first_hour_return"] = (close_1h / close_0) - 1.0

    # ============================================================
    # TENDENCIA DEL VOLUMEN (regresion lineal, ventana 7d)
    # ============================================================
    # Usamos numpy polyfit para ajustar una linea recta al volumen
    # Pendiente positiva = volumen creciendo (buena senal)
    # Pendiente negativa = volumen cayendo (senal de desinteres)
    # Normalizado por media para que sea comparable entre tokens
    if len(volumes) >= 3:
        try:
            # x = indices (0, 1, 2, ...), y = volumen
            x = np.arange(len(volumes))
            y = volumes.values.astype(float)

            # polyfit grado 1 devuelve [pendiente, intercepto]
            slope, _ = np.polyfit(x, y, 1)
            # Normalizar por media de volumen para comparabilidad
            vol_mean = volumes.mean()
            slope = slope / vol_mean if vol_mean > 0 else 0
            features["volume_trend_slope"] = float(slope)
        except (np.linalg.LinAlgError, ValueError):
            # Si la regresion falla (ej: todos los valores iguales)
            features["volume_trend_slope"] = None

    # ============================================================
    # NUEVAS FEATURES v5: Sostenibilidad y concentracion
    # ============================================================

    # volume_concentration_ratio: max(vol_7d) / mean(vol_7d)
    # Detecta spikes artificiales de volumen (ratio alto = sospechoso)
    if not df_7d.empty:
        vols_7d = df_7d["volume"].apply(safe_float)
        vols_7d = vols_7d[vols_7d > 0]
        if len(vols_7d) >= 2:
            features["volume_concentration_ratio"] = safe_divide(
                vols_7d.max(), vols_7d.mean()
            )

    # price_recovery_ratio: close actual / min(low_7d)
    # Capacidad de recuperar despues de una caida
    if not df_7d.empty:
        min_low_7d = safe_float(df_7d["low"].min())
        last_close = safe_float(df_7d["close"].iloc[-1])
        if min_low_7d > 0:
            features["price_recovery_ratio"] = safe_divide(last_close, min_low_7d)

    # volume_sustainability_3d: mean(vol segunda mitad) / mean(vol primera mitad)
    # Volumen que se mantiene vs que colapsa despues del hype inicial
    if not df_7d.empty:
        vols_7d_all = df_7d["volume"].apply(safe_float)
        vols_7d_all = vols_7d_all[vols_7d_all > 0]
        if len(vols_7d_all) >= 4:
            mid = len(vols_7d_all) // 2
            first_half_mean = vols_7d_all.iloc[:mid].mean()
            second_half_mean = vols_7d_all.iloc[mid:].mean()
            if first_half_mean > 0:
                features["volume_sustainability_3d"] = safe_divide(
                    second_half_mean, first_half_mean
                )

    # close_to_high_ratio_7d: close actual / max(high_7d)
    # Posicion del precio actual vs el maximo historico en 7d
    if not df_7d.empty:
        max_high_7d = safe_float(df_7d["high"].max())
        last_close_7d = safe_float(df_7d["close"].iloc[-1])
        if max_high_7d > 0:
            features["close_to_high_ratio_7d"] = safe_divide(
                last_close_7d, max_high_7d
            )

    # up_days_ratio_7d: % de dias verdes (close > open) en 7d
    if not df_7d.empty and len(df_7d) >= 2:
        up_days = (df_7d["close"] > df_7d["open"]).sum()
        features["up_days_ratio_7d"] = safe_divide(up_days, len(df_7d))

    # volume_price_divergence: volumen sube pero precio baja = acumulacion
    # 1.0 si slope > 0 y return_30d < 0, 0.0 en caso contrario
    if features["volume_trend_slope"] is not None and features["return_30d"] is not None:
        if features["volume_trend_slope"] > 0 and features["return_30d"] < 0:
            features["volume_price_divergence"] = 1.0
        else:
            features["volume_price_divergence"] = 0.0

    return features


def _compute_return_at_window(
    df: pd.DataFrame,
    first_time: pd.Timestamp,
    close_0: float,
    hours: int
) -> Optional[float]:
    """
    Calcula el retorno del precio en una ventana de tiempo especifica.

    Args:
        df: DataFrame OHLCV ordenado por timestamp.
        first_time: Timestamp del primer candle.
        close_0: Precio de cierre del primer candle.
        hours: Ventana de tiempo en horas.

    Returns:
        Retorno como decimal (0.5 = 50%), o None si no hay datos.
    """
    target_time = first_time + timedelta(hours=hours)

    # Filtrar candles dentro de la ventana
    mask = df["timestamp"] <= target_time
    df_window = df[mask]

    if df_window.empty:
        return None

    # Usar el ultimo cierre disponible dentro de la ventana
    close_end = safe_float(df_window["close"].iloc[-1])

    if close_0 <= 0 or close_end <= 0:
        return None

    return (close_end / close_0) - 1.0
