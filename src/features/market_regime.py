"""
market_regime.py — Detecta el regimen de mercado (bull/bear/crab).

Los gems se comportan diferente en mercados alcistas vs bajistas.
El modelo necesita saber en que fase estamos para predecir mejor.

Conceptos clave:
    - Un mercado "bull" tiene tendencia alcista: BTC esta por encima de su
      media movil de 20 dias y con retornos positivos recientes.
    - Un mercado "bear" tiene tendencia bajista: BTC esta por debajo de su
      media movil y con retornos negativos.
    - Un mercado "crab" (cangrejo) se mueve de lado sin tendencia clara,
      con baja volatilidad.

Features que calcula:
    - regime_bull: 1 si BTC > SMA(20) y retorno 7d > 2%
    - regime_bear: 1 si BTC < SMA(20) y retorno 7d < -2%
    - regime_crab: 1 si no es bull ni bear (mercado lateral)
    - btc_sma20_distance: distancia porcentual entre BTC y su SMA(20)
    - btc_volatility_20d: desviacion estandar de retornos diarios en 20 dias
    - market_momentum: promedio de retornos 7d de BTC, ETH y SOL

Uso:
    >>> features = compute_market_regime_features(
    ...     launch_time="2024-01-15T12:00:00Z",
    ...     btc_prices=btc_df,
    ...     eth_prices=eth_df,
    ...     sol_prices=sol_df,
    ... )
    >>> features["regime_bull"]
    1  # Mercado alcista
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.utils.helpers import pct_change, safe_float


def compute_market_regime_features(
    launch_time: str,
    btc_prices: pd.DataFrame,
    eth_prices: pd.DataFrame,
    sol_prices: pd.DataFrame,
) -> dict:
    """
    Calcula features de regimen de mercado al momento del lanzamiento.

    Analiza el estado de BTC, ETH y SOL para determinar si el mercado
    esta en fase alcista (bull), bajista (bear) o lateral (crab).

    Args:
        launch_time: Timestamp ISO del lanzamiento del token.
            Ejemplo: "2024-01-15T12:00:00Z"
        btc_prices: DataFrame con precios diarios de BTC.
            Columnas requeridas: [timestamp, price].
        eth_prices: DataFrame con precios diarios de ETH.
            Columnas requeridas: [timestamp, price].
        sol_prices: DataFrame con precios diarios de SOL.
            Columnas requeridas: [timestamp, price].

    Returns:
        Dict con 6 features de regimen de mercado.
        Si no hay datos suficientes, los valores seran None o 0.

    Ejemplo:
        >>> features = compute_market_regime_features(
        ...     "2024-01-15T12:00:00Z", btc_df, eth_df, sol_df
        ... )
        >>> features["btc_sma20_distance"]
        0.05  # BTC esta 5% por encima de su SMA20
    """
    # Inicializar todos los features con valores por defecto
    features = {
        "regime_bull": 0,
        "regime_bear": 0,
        "regime_crab": 0,
        "btc_sma20_distance": None,
        "btc_volatility_20d": None,
        "market_momentum": None,
    }

    # Parsear el timestamp de lanzamiento
    launch_dt = _parse_launch_time(launch_time)
    if launch_dt is None:
        return features

    # --- Calcular SMA20 y distancia de BTC ---
    # La SMA (Simple Moving Average) de 20 dias es un indicador clasico
    # de tendencia. Si el precio esta por encima, la tendencia es alcista.
    btc_sma20_dist = _compute_sma_distance(btc_prices, launch_dt, window=20)
    features["btc_sma20_distance"] = btc_sma20_dist

    # --- Calcular volatilidad de BTC en 20 dias ---
    # La desviacion estandar de retornos diarios mide cuanto varia
    # el precio de BTC. Alta volatilidad = mercado inestable.
    features["btc_volatility_20d"] = _compute_volatility(
        btc_prices, launch_dt, window=20
    )

    # --- Calcular retornos 7d de BTC, ETH y SOL ---
    btc_return_7d = _compute_return(btc_prices, launch_dt, days=7)
    eth_return_7d = _compute_return(eth_prices, launch_dt, days=7)
    sol_return_7d = _compute_return(sol_prices, launch_dt, days=7)

    # --- Market momentum: promedio de retornos 7d ---
    # Un momentum positivo significa que el mercado crypto en general sube,
    # lo que suele favorecer a los memecoins.
    valid_returns = [r for r in [btc_return_7d, eth_return_7d, sol_return_7d] if r is not None]
    if valid_returns:
        features["market_momentum"] = round(sum(valid_returns) / len(valid_returns), 6)

    # --- Clasificar regimen ---
    # BULL: BTC por encima de SMA20 Y retorno 7d positivo (> 2%)
    # BEAR: BTC por debajo de SMA20 Y retorno 7d negativo (< -2%)
    # CRAB: todo lo demas (mercado sin tendencia clara)
    if btc_sma20_dist is not None and btc_return_7d is not None:
        if btc_sma20_dist > 0 and btc_return_7d > 0.02:
            features["regime_bull"] = 1
        elif btc_sma20_dist < 0 and btc_return_7d < -0.02:
            features["regime_bear"] = 1
        else:
            features["regime_crab"] = 1
    else:
        # Sin datos suficientes, marcamos como crab (neutral) por defecto
        features["regime_crab"] = 1

    return features


# ============================================================
# FUNCIONES AUXILIARES (privadas)
# ============================================================


def _parse_launch_time(launch_time: str) -> Optional[datetime]:
    """
    Parsea el timestamp de lanzamiento a datetime UTC.

    Args:
        launch_time: String ISO 8601 (ej: "2024-01-15T12:00:00Z").

    Returns:
        Datetime en UTC, o None si no se puede parsear.
    """
    if not launch_time or not isinstance(launch_time, str):
        return None

    try:
        # Reemplazar 'Z' por '+00:00' para compatibilidad con fromisoformat
        clean_str = launch_time.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)

        # Si no tiene timezone, asumir UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except (ValueError, TypeError):
        return None


def _get_prices_before_launch(
    prices_df: pd.DataFrame,
    launch_dt: datetime,
    window: int,
) -> Optional[pd.DataFrame]:
    """
    Obtiene los precios de los ultimos 'window' dias antes del lanzamiento.

    Filtra el DataFrame de precios para quedarse solo con las filas
    anteriores al lanzamiento, y toma las ultimas 'window' filas.

    Args:
        prices_df: DataFrame con columnas [timestamp, price].
        launch_dt: Fecha del lanzamiento.
        window: Cuantos dias atras queremos (ej: 20).

    Returns:
        DataFrame filtrado y ordenado, o None si no hay datos.
    """
    if prices_df is None or prices_df.empty:
        return None

    df = prices_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Filtrar precios anteriores al lanzamiento
    # Incluimos el dia del lanzamiento (launch_dt + 1 dia)
    cutoff = launch_dt + timedelta(days=1)
    df_before = df[df["timestamp"] <= cutoff]

    if df_before.empty or len(df_before) < 2:
        return None

    # Tomar los ultimos 'window' dias (o los que haya)
    return df_before.tail(window + 5)  # +5 de margen por gaps


def _compute_sma_distance(
    prices_df: pd.DataFrame,
    launch_dt: datetime,
    window: int = 20,
) -> Optional[float]:
    """
    Calcula la distancia porcentual entre el precio actual y la SMA.

    La SMA (Simple Moving Average) es el promedio de los ultimos N precios.
    La distancia indica si el precio esta por encima (+) o debajo (-).

    Formula: (precio_actual - SMA) / SMA

    Args:
        prices_df: DataFrame con columnas [timestamp, price].
        launch_dt: Fecha de referencia.
        window: Ventana de la SMA en dias (default 20).

    Returns:
        Distancia como decimal (0.05 = 5% por encima), o None.

    Ejemplo:
        Si BTC = $50,000 y SMA20 = $48,000:
        distancia = (50000 - 48000) / 48000 = 0.0417 (4.17% por encima)
    """
    df_before = _get_prices_before_launch(prices_df, launch_dt, window)
    if df_before is None or len(df_before) < window:
        return None

    # Convertir precios a numerico
    prices = df_before["price"].apply(safe_float).values

    # SMA = promedio de los ultimos 'window' precios
    sma = np.mean(prices[-window:])

    if sma <= 0:
        return None

    # Precio mas reciente (el mas cercano al lanzamiento)
    current_price = safe_float(prices[-1])

    if current_price <= 0:
        return None

    # Distancia porcentual: positivo = por encima, negativo = por debajo
    distance = (current_price - sma) / sma
    return round(distance, 6)


def _compute_volatility(
    prices_df: pd.DataFrame,
    launch_dt: datetime,
    window: int = 20,
) -> Optional[float]:
    """
    Calcula la volatilidad (desviacion estandar de retornos diarios).

    La volatilidad mide cuanto varia el precio dia a dia.
    Alta volatilidad = el precio cambia mucho (mercado inestable).
    Baja volatilidad = el precio cambia poco (mercado estable/lateral).

    Args:
        prices_df: DataFrame con columnas [timestamp, price].
        launch_dt: Fecha de referencia.
        window: Ventana en dias (default 20).

    Returns:
        Desviacion estandar de retornos diarios, o None.

    Ejemplo:
        Volatilidad de 0.03 = los retornos diarios varian +-3% en promedio.
    """
    df_before = _get_prices_before_launch(prices_df, launch_dt, window)
    if df_before is None or len(df_before) < 5:
        return None

    # Convertir a numerico y calcular retornos diarios
    prices = df_before["price"].apply(safe_float).values

    # Filtrar ceros para evitar division por cero
    prices = prices[prices > 0]
    if len(prices) < 5:
        return None

    # Retornos diarios: (precio_hoy - precio_ayer) / precio_ayer
    returns = np.diff(prices) / prices[:-1]

    # Desviacion estandar de los retornos
    volatility = float(np.std(returns))
    return round(volatility, 6)


def _compute_return(
    prices_df: pd.DataFrame,
    launch_dt: datetime,
    days: int = 7,
) -> Optional[float]:
    """
    Calcula el retorno de un activo en los ultimos N dias antes del lanzamiento.

    Busca el precio de hace 'days' dias y el precio mas reciente,
    y calcula el retorno porcentual entre ambos.

    Args:
        prices_df: DataFrame con columnas [timestamp, price].
        launch_dt: Fecha de referencia.
        days: Ventana de retorno en dias (default 7).

    Returns:
        Retorno como decimal (0.05 = 5% de subida), o None.
    """
    df_before = _get_prices_before_launch(prices_df, launch_dt, days + 5)
    if df_before is None or len(df_before) < 2:
        return None

    prices = df_before["price"].apply(safe_float).values
    prices = prices[prices > 0]

    if len(prices) < 2:
        return None

    # Tomar el precio de hace ~N dias y el mas reciente
    old_idx = max(0, len(prices) - days - 1)
    old_price = prices[old_idx]
    new_price = prices[-1]

    if old_price <= 0:
        return None

    return_val = (new_price - old_price) / old_price
    return round(return_val, 6)
