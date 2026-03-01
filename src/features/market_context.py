"""
market_context.py - Features de contexto de mercado al momento del lanzamiento.

El exito de un memecoin no depende solo de sus metricas internas,
sino tambien del estado general del mercado crypto al momento de su
lanzamiento.

Conceptos clave:
    - Si BTC/ETH/SOL estan en rally, hay mas apetito por riesgo
      y los memecoins tienden a beneficiarse.
    - El dia de la semana y hora UTC importan: la actividad crypto
      varia segun las zonas horarias (Asia, Europa, Americas).
    - La cadena (Solana, Ethereum, Base) y el DEX (Raydium, Uniswap)
      afectan la accesibilidad y costos de trading.

Features que calcula:
    - btc_return_7d_at_launch: Retorno de BTC en 7 dias alrededor del lanzamiento
    - eth_return_7d_at_launch: Retorno de ETH en 7 dias alrededor del lanzamiento
    - sol_return_7d_at_launch: Retorno de SOL en 7 dias alrededor del lanzamiento
    - launch_day_of_week: Dia de la semana (0=Lunes, 6=Domingo)
    - launch_hour_utc: Hora UTC del lanzamiento (0-23)
    - chain: Cadena (para one-hot encoding posterior)
    - dex: DEX (para one-hot encoding posterior)
"""

import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.utils.helpers import pct_change, safe_float


def compute_market_context_features(
    launch_time: str,
    btc_prices: pd.DataFrame,
    eth_prices: pd.DataFrame,
    sol_prices: pd.DataFrame,
    chain: str,
    dex: str
) -> dict:
    """
    Calcula features de contexto de mercado al momento del lanzamiento.

    Args:
        launch_time: Timestamp ISO del lanzamiento del token.
        btc_prices: DataFrame con precios diarios de BTC [timestamp, price].
        eth_prices: DataFrame con precios diarios de ETH [timestamp, price].
        sol_prices: DataFrame con precios diarios de SOL [timestamp, price].
        chain: Cadena del token (ej: "solana", "ethereum", "base").
        dex: DEX donde se lanzo (ej: "raydium", "uniswap_v3").

    Returns:
        Dict con los features de contexto de mercado.

    Ejemplo:
        >>> features = compute_market_context_features(
        ...     "2024-01-15T12:00:00Z", btc_df, eth_df, sol_df,
        ...     "solana", "raydium"
        ... )
        >>> features["launch_day_of_week"]
        0  # Lunes
    """

    # Inicializar todos los features con None
    features = {
        "btc_return_7d_at_launch": None,
        "eth_return_7d_at_launch": None,
        "sol_return_7d_at_launch": None,
        "launch_day_of_week": None,
        "launch_hour_utc": None,
        "chain": chain,
        "dex": dex,
    }

    # Parsear el timestamp de lanzamiento
    launch_dt = _parse_launch_time(launch_time)
    if launch_dt is None:
        return features

    # --- launch_day_of_week: Dia de la semana ---
    # weekday() devuelve 0=Lunes, 6=Domingo
    features["launch_day_of_week"] = launch_dt.weekday()

    # --- launch_hour_utc: Hora UTC del lanzamiento ---
    features["launch_hour_utc"] = launch_dt.hour

    # --- Retornos de BTC/ETH/SOL en la ventana de 7 dias ---
    # Calculamos el retorno del activo en los 7 dias centrados
    # alrededor del lanzamiento (3.5 dias antes y 3.5 dias despues)
    features["btc_return_7d_at_launch"] = _compute_asset_return_around_launch(
        btc_prices, launch_dt, days=7
    )
    features["eth_return_7d_at_launch"] = _compute_asset_return_around_launch(
        eth_prices, launch_dt, days=7
    )
    features["sol_return_7d_at_launch"] = _compute_asset_return_around_launch(
        sol_prices, launch_dt, days=7
    )

    return features


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


def _compute_asset_return_around_launch(
    prices_df: pd.DataFrame,
    launch_dt: datetime,
    days: int = 7
) -> Optional[float]:
    """
    Calcula el retorno de un activo (BTC/ETH/SOL) en una ventana
    de N dias centrada alrededor del lanzamiento.

    Busca el precio mas cercano a (launch - days/2) y (launch + days/2),
    y calcula el retorno porcentual entre ambos.

    Args:
        prices_df: DataFrame con columnas [timestamp, price].
        launch_dt: Datetime del lanzamiento del token.
        days: Ventana total en dias (por defecto 7).

    Returns:
        Retorno como decimal (0.1 = 10%), o None si no hay datos.
    """
    # Verificar que hay datos de precios
    if prices_df is None or prices_df.empty:
        return None

    # Preparar el DataFrame de precios
    df = prices_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Definir ventana: 3.5 dias antes y 3.5 dias despues
    half_window = timedelta(days=days / 2)
    start_time = launch_dt - half_window
    end_time = launch_dt + half_window

    # Encontrar el precio mas cercano al inicio de la ventana
    price_start = _find_closest_price(df, start_time)

    # Encontrar el precio mas cercano al final de la ventana
    price_end = _find_closest_price(df, end_time)

    if price_start is None or price_end is None:
        return None

    # Calcular retorno porcentual
    return pct_change(price_start, price_end)


def _find_closest_price(
    df: pd.DataFrame,
    target_time: datetime
) -> Optional[float]:
    """
    Encuentra el precio mas cercano a un tiempo objetivo.

    Args:
        df: DataFrame con columnas [timestamp, price].
        target_time: Tiempo objetivo.

    Returns:
        Precio mas cercano, o None si el DataFrame esta vacio.
    """
    if df.empty:
        return None

    # Calcular diferencia absoluta entre cada timestamp y el objetivo
    time_diffs = (df["timestamp"] - target_time).abs()

    # Obtener el indice del mas cercano
    closest_idx = time_diffs.idxmin()

    price = safe_float(df.loc[closest_idx, "price"])
    return price if price > 0 else None
