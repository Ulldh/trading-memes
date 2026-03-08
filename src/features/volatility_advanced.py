"""
volatility_advanced.py - Calculo de features avanzados de volatilidad y analisis tecnico.

Este modulo implementa indicadores tecnicos sofisticados para capturar patrones
de volatilidad que pueden predecir "gems" vs "rugs":
    - Bollinger Bands: Detecta sobrecompra/sobreventa y volatilidad extrema
    - ATR (Average True Range): Mide volatilidad absoluta
    - RSI (Relative Strength Index): Detecta momentum y reversiones
    - Rangos intraday: Captura volatilidad dentro de cada candle
    - Volatility spikes: Detecta movimientos anomalos (pumps/dumps)

Conceptos clave:
    - Bollinger Bands: Bandas de volatilidad (precio +/- 2 std dev)
      - %B indica posicion del precio entre bandas (0=banda baja, 1=banda alta)
      - Bandwidth indica el ancho de las bandas (alta volatilidad = bandas anchas)
    - ATR: Promedio del "true range" (rango real incluyendo gaps)
    - RSI: Momentum indicator (0-100). >70 = sobrecompra, <30 = sobreventa
    - Volatility spikes: Movimientos mayores a 2 desviaciones estandar

Features que calcula (11 en total):
    Bollinger Bands (7d):
        - bb_upper_7d: Precio de banda superior
        - bb_lower_7d: Precio de banda inferior
        - bb_pct_b_7d: %B (0-1, posicion entre bandas)
        - bb_bandwidth_7d: Ancho de banda normalizado

    ATR (7d):
        - atr_7d: Average True Range absoluto
        - atr_pct_7d: ATR como % del precio actual

    RSI (7d):
        - rsi_7d: Relative Strength Index (0-100)
        - rsi_divergence_7d: Diferencia entre RSI y su promedio

    Rango Intraday (7d):
        - avg_intraday_range_7d: Promedio de (high-low)/open
        - max_intraday_range_7d: Maximo rango observado

    Volatility Spikes (7d):
        - volatility_spike_count_7d: Numero de spikes anomalos
"""

import numpy as np
import pandas as pd
from datetime import timedelta
from typing import Optional

from src.utils.helpers import safe_float, safe_divide


def compute_volatility_advanced_features(ohlcv_df: pd.DataFrame) -> dict:
    """
    Calcula features avanzados de volatilidad a partir de datos OHLCV.

    Args:
        ohlcv_df: DataFrame con columnas [timestamp, open, high, low, close, volume]
                  ordenado por timestamp (mas antiguo primero).

    Returns:
        Dict con todos los features de volatilidad avanzada.
        Valores None para features que no se pudieron calcular.

    Ejemplo:
        >>> features = compute_volatility_advanced_features(ohlcv_df)
        >>> features["rsi_7d"]
        45.2  # RSI neutral (ni sobrecompra ni sobreventa)
        >>> features["bb_pct_b_7d"]
        0.85  # Precio cerca de banda superior (posible sobrecompra)
    """

    # Inicializar todos los features con None
    features = {
        # Bollinger Bands
        "bb_upper_7d": None,
        "bb_lower_7d": None,
        "bb_pct_b_7d": None,
        "bb_bandwidth_7d": None,
        # ATR
        "atr_7d": None,
        "atr_pct_7d": None,
        # RSI
        "rsi_7d": None,
        "rsi_divergence_7d": None,
        # Intraday Range
        "avg_intraday_range_7d": None,
        "max_intraday_range_7d": None,
        # Volatility Spikes
        "volatility_spike_count_7d": None,
    }

    # Verificar que hay datos
    if ohlcv_df is None or ohlcv_df.empty:
        return features

    # Copiar y preparar el DataFrame
    df = ohlcv_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Tiempo del primer candle (referencia para ventanas)
    first_time = df["timestamp"].iloc[0]

    # ============================================================
    # FILTRAR VENTANA DE 7 DIAS
    # ============================================================
    # La mayoria de features usan ventana de 7 dias
    mask_7d = df["timestamp"] <= first_time + timedelta(days=7)
    df_7d = df[mask_7d].copy()

    if len(df_7d) < 2:
        # No hay suficientes datos para calcular features
        return features

    # ============================================================
    # BOLLINGER BANDS (7 DIAS)
    # ============================================================
    # Bandas de Bollinger = SMA +/- (2 * std dev)
    # Detectan cuando el precio esta en niveles extremos
    try:
        close_series = df_7d["close"].apply(safe_float)

        # Media movil simple (SMA)
        sma = close_series.mean()

        # Desviacion estandar
        std = close_series.std()

        if pd.notna(sma) and pd.notna(std) and std > 0:
            # Banda superior = SMA + 2*std
            bb_upper = sma + (2 * std)
            features["bb_upper_7d"] = float(bb_upper)

            # Banda inferior = SMA - 2*std (clamped a 0, precios no pueden ser negativos)
            bb_lower = max(0, sma - (2 * std))
            features["bb_lower_7d"] = float(bb_lower)

            # %B = (precio_actual - banda_inferior) / (banda_superior - banda_inferior)
            # %B = 0: precio en banda inferior (sobreventa)
            # %B = 1: precio en banda superior (sobrecompra)
            # %B > 1: precio por encima de banda superior (momentum extremo)
            current_price = safe_float(df_7d["close"].iloc[-1])
            if current_price > 0:
                pct_b = safe_divide(
                    current_price - bb_lower,
                    bb_upper - bb_lower
                )
                features["bb_pct_b_7d"] = pct_b

            # Bandwidth = (banda_superior - banda_inferior) / SMA
            # Mide el ancho de las bandas normalizado por el precio
            # Bandwidth alto = alta volatilidad
            bandwidth = safe_divide(bb_upper - bb_lower, sma)
            features["bb_bandwidth_7d"] = bandwidth

    except Exception as e:
        # Si hay error en el calculo, los features quedan None
        pass

    # ============================================================
    # ATR - AVERAGE TRUE RANGE (7 DIAS)
    # ============================================================
    # ATR mide la volatilidad promedio considerando gaps entre candles
    # True Range = max de:
    #   1. high - low (rango de la candle)
    #   2. |high - close_anterior| (gap hacia arriba)
    #   3. |low - close_anterior| (gap hacia abajo)
    try:
        if len(df_7d) >= 2:
            high = df_7d["high"].apply(safe_float)
            low = df_7d["low"].apply(safe_float)
            close = df_7d["close"].apply(safe_float)

            # Close anterior (shift 1)
            close_prev = close.shift(1)

            # Calcular los 3 componentes del True Range
            tr1 = high - low  # Rango de la candle
            tr2 = (high - close_prev).abs()  # Gap hacia arriba
            tr3 = (low - close_prev).abs()  # Gap hacia abajo

            # True Range = max de los 3
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            # ATR = promedio del True Range (excluyendo primera fila que es NaN)
            atr = true_range.iloc[1:].mean()

            if pd.notna(atr):
                features["atr_7d"] = float(atr)

                # ATR como % del precio actual
                # Normaliza el ATR para poder comparar entre tokens
                current_price = safe_float(df_7d["close"].iloc[-1])
                if current_price > 0:
                    atr_pct = safe_divide(atr, current_price)
                    features["atr_pct_7d"] = atr_pct

    except Exception as e:
        pass

    # ============================================================
    # RSI - RELATIVE STRENGTH INDEX (7 DIAS)
    # ============================================================
    # RSI mide el momentum del precio
    # RSI > 70: sobrecompra (posible correccion bajista)
    # RSI < 30: sobreventa (posible rebote alcista)
    # Formula: RSI = 100 - (100 / (1 + RS))
    # donde RS = promedio_ganancias / promedio_perdidas
    try:
        if len(df_7d) >= 3:
            close = df_7d["close"].apply(safe_float)

            # Calcular cambios de precio entre candles
            price_changes = close.diff()

            # Separar ganancias y perdidas
            gains = price_changes.where(price_changes > 0, 0)
            losses = -price_changes.where(price_changes < 0, 0)

            # Promedio de ganancias y perdidas
            avg_gain = gains.mean()
            avg_loss = losses.mean()

            if pd.notna(avg_gain) and pd.notna(avg_loss) and avg_loss > 0:
                # RS = ratio de ganancias vs perdidas
                rs = avg_gain / avg_loss

                # RSI = 100 - (100 / (1 + RS))
                rsi = 100 - (100 / (1 + rs))
                features["rsi_7d"] = float(rsi)

                # Divergencia del RSI respecto a 50 (punto neutral)
                # Divergencia positiva = momentum alcista
                # Divergencia negativa = momentum bajista
                rsi_divergence = rsi - 50
                features["rsi_divergence_7d"] = float(rsi_divergence)

            elif avg_loss == 0:
                # Caso especial: solo ganancias, sin perdidas
                # RSI = 100 (momentum alcista extremo)
                features["rsi_7d"] = 100.0
                features["rsi_divergence_7d"] = 50.0

    except Exception as e:
        pass

    # ============================================================
    # RANGO INTRADAY (7 DIAS)
    # ============================================================
    # Mide la volatilidad dentro de cada candle (high - low)
    # Normalizado por el precio de apertura
    try:
        high = df_7d["high"].apply(safe_float)
        low = df_7d["low"].apply(safe_float)
        open_price = df_7d["open"].apply(safe_float)

        # Rango intraday = (high - low) / open
        # Esto nos dice que % se movio el precio dentro de cada candle
        intraday_ranges = []

        for i in range(len(df_7d)):
            h = high.iloc[i]
            l = low.iloc[i]
            o = open_price.iloc[i]

            if o > 0:
                range_pct = safe_divide(h - l, o)
                if range_pct is not None:
                    intraday_ranges.append(range_pct)

        if len(intraday_ranges) > 0:
            # Promedio del rango intraday
            features["avg_intraday_range_7d"] = float(np.mean(intraday_ranges))

            # Maximo rango observado (detecta dias de alta volatilidad)
            features["max_intraday_range_7d"] = float(np.max(intraday_ranges))

    except Exception as e:
        pass

    # ============================================================
    # VOLATILITY SPIKES (7 DIAS)
    # ============================================================
    # Detecta movimientos anomalos de precio (spikes)
    # Spike = retorno que excede 2 desviaciones estandar del promedio
    # Muchos spikes = token muy volatil o manipulado
    try:
        if len(df_7d) >= 3:
            close = df_7d["close"].apply(safe_float)

            # Calcular retornos entre candles
            returns = close.pct_change().dropna()

            if len(returns) >= 2:
                # Promedio y std de los retornos
                mean_return = returns.mean()
                std_return = returns.std()

                if pd.notna(std_return) and std_return > 0:
                    # Umbral para detectar spike = +/- 2 desviaciones estandar
                    threshold = 2 * std_return

                    # Contar cuantos retornos exceden el umbral
                    spike_count = ((returns - mean_return).abs() > threshold).sum()
                    features["volatility_spike_count_7d"] = int(spike_count)

    except Exception as e:
        pass

    return features


def _bollinger_bands(
    prices: pd.Series,
    window: int = 20,
    num_std: int = 2
) -> tuple:
    """
    Calcula Bollinger Bands para una serie de precios.

    Args:
        prices: Serie de precios (close).
        window: Ventana para la media movil (default: 20).
        num_std: Numero de desviaciones estandar (default: 2).

    Returns:
        Tupla (upper_band, sma, lower_band).

    Nota:
        Esta es una funcion auxiliar. No se usa directamente en el modulo
        porque calculamos BB sobre toda la ventana de 7d, no con rolling window.
    """
    sma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()

    upper_band = sma + (num_std * std)
    lower_band = sma - (num_std * std)

    return upper_band, sma, lower_band
