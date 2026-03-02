"""
liquidity.py - Calculo de features de liquidez.

La liquidez es la cantidad de dinero disponible en un pool de trading.
Es clave porque:
    - Baja liquidez = facil de manipular el precio
    - Liquidez que desaparece de golpe = posible rug pull
    - Relacion volumen/liquidez alta = alta actividad de trading

Features que calcula:
    - initial_liquidity_usd: Liquidez al momento del primer snapshot
    - liquidity_growth_24h: Crecimiento porcentual de liquidez en 24h
    - liquidity_growth_7d: Crecimiento porcentual de liquidez en 7 dias
    - liq_to_mcap_ratio: Liquidez / Market Cap (salud del pool)
    - volume_to_liq_ratio_24h: Volumen 24h / Liquidez (actividad relativa)
    - liquidity_stability: Coeficiente de variacion de la liquidez diaria
"""

import pandas as pd
from datetime import timedelta
from typing import Optional

from src.utils.helpers import safe_divide, pct_change, safe_float


def compute_liquidity_features(snapshots_df: pd.DataFrame) -> dict:
    """
    Calcula features de liquidez a partir de snapshots de pool.

    Args:
        snapshots_df: DataFrame de pool_snapshots ordenado por tiempo.
                      Columnas esperadas: snapshot_time, liquidity_usd,
                      market_cap, volume_24h.

    Returns:
        Dict con los features de liquidez. Valores None si no hay datos.

    Ejemplo:
        >>> features = compute_liquidity_features(snapshots_df)
        >>> features["initial_liquidity_usd"]
        50000.0
    """

    # Inicializar todos los features con None
    features = {
        "initial_liquidity_usd": None,
        "liquidity_growth_24h": None,
        "liquidity_growth_7d": None,
        "liq_to_mcap_ratio": None,
        "volume_to_liq_ratio_24h": None,
        "liquidity_stability": None,
        "liquidity_to_fdv_ratio": None,
    }

    # Verificar que tenemos datos
    if snapshots_df is None or snapshots_df.empty:
        return features

    # Hacer una copia para no modificar el original
    df = snapshots_df.copy()

    # Convertir snapshot_time a datetime si es string
    df["snapshot_time"] = pd.to_datetime(df["snapshot_time"], utc=True)

    # Ordenar por tiempo (por seguridad)
    df = df.sort_values("snapshot_time").reset_index(drop=True)

    # --- initial_liquidity_usd: liquidez en el primer snapshot ---
    first_liq = safe_float(df["liquidity_usd"].iloc[0])
    features["initial_liquidity_usd"] = first_liq if first_liq > 0 else None

    # Tiempo del primer snapshot (referencia)
    first_time = df["snapshot_time"].iloc[0]

    # --- liquidity_growth_24h: cambio porcentual en 24 horas ---
    # Buscar el snapshot mas cercano a 24h despues del primero
    target_24h = first_time + timedelta(hours=24)
    snapshot_24h = _find_closest_snapshot(df, target_24h)
    if snapshot_24h is not None and first_liq > 0:
        liq_24h = safe_float(snapshot_24h["liquidity_usd"])
        features["liquidity_growth_24h"] = pct_change(first_liq, liq_24h)

    # --- liquidity_growth_7d: cambio porcentual en 7 dias ---
    target_7d = first_time + timedelta(days=7)
    snapshot_7d = _find_closest_snapshot(df, target_7d)
    if snapshot_7d is not None and first_liq > 0:
        liq_7d = safe_float(snapshot_7d["liquidity_usd"])
        features["liquidity_growth_7d"] = pct_change(first_liq, liq_7d)

    # --- liq_to_mcap_ratio: liquidez / market cap del ultimo snapshot ---
    # Un ratio saludable suele ser > 0.05 (5%)
    latest = df.iloc[-1]
    latest_liq = safe_float(latest.get("liquidity_usd"))
    latest_mcap = safe_float(latest.get("market_cap"))
    features["liq_to_mcap_ratio"] = safe_divide(latest_liq, latest_mcap)

    # --- liquidity_to_fdv_ratio: liquidez / FDV (proxy de solidez) ---
    latest_fdv = safe_float(latest.get("fdv"))
    features["liquidity_to_fdv_ratio"] = safe_divide(latest_liq, latest_fdv)

    # --- volume_to_liq_ratio_24h: volumen 24h / liquidez ---
    # Ratios muy altos pueden indicar wash trading o alta especulacion
    latest_volume = safe_float(latest.get("volume_24h"))
    features["volume_to_liq_ratio_24h"] = safe_divide(
        latest_volume, latest_liq
    )

    # --- liquidity_stability: coeficiente de variacion de la liquidez ---
    # CV = desviacion estandar / media
    # Valores bajos = liquidez estable (bueno)
    # Valores altos = liquidez volatil (riesgo de rug pull)
    liq_values = df["liquidity_usd"].apply(safe_float)
    liq_values = liq_values[liq_values > 0]  # Filtrar ceros

    if len(liq_values) >= 2:
        mean_liq = liq_values.mean()
        std_liq = liq_values.std()
        features["liquidity_stability"] = safe_divide(std_liq, mean_liq)

    return features


def _find_closest_snapshot(
    df: pd.DataFrame,
    target_time: pd.Timestamp
) -> Optional[pd.Series]:
    """
    Encuentra el snapshot mas cercano a un tiempo objetivo.

    Args:
        df: DataFrame con columna 'snapshot_time' (ya en datetime).
        target_time: Tiempo objetivo a buscar.

    Returns:
        La fila (Series) mas cercana, o None si el DataFrame esta vacio.
    """
    if df.empty:
        return None

    # Calcular la diferencia absoluta entre cada snapshot y el objetivo
    time_diffs = (df["snapshot_time"] - target_time).abs()

    # Obtener el indice del mas cercano
    closest_idx = time_diffs.idxmin()

    return df.loc[closest_idx]
