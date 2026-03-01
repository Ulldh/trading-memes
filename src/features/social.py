"""
social.py - Calculo de features sociales / de actividad de trading.

Analiza metricas de compradores, vendedores y transacciones.
Estos datos vienen principalmente de DexScreener y pool snapshots.

Conceptos clave:
    - Buyer/Seller ratio: Si hay mas compradores que vendedores,
      hay presion de compra (demanda). Ratio > 1 es bullish.
    - Makers: Creadores de ordenes en el order book (market makers).
    - Avg tx size: Si el tamaño promedio de transaccion es grande,
      puede indicar "ballenas" (whales) operando.
    - Boosts: DexScreener permite "boostar" tokens pagando.
      Tokens boosteados atraen mas atencion.

Features que calcula:
    - buyers_24h: Numero de compradores en 24h
    - sellers_24h: Numero de vendedores en 24h
    - buyer_seller_ratio_24h: Ratio compradores/vendedores
    - makers_24h: Numero de market makers
    - tx_count_24h: Total de transacciones en 24h
    - avg_tx_size_usd: Tamaño promedio de transaccion en USD
    - is_boosted: Si el token tiene boosts activos en DexScreener
"""

from typing import Optional

import pandas as pd
import numpy as np

from src.utils.helpers import safe_divide, safe_float


def compute_social_features(snapshot: dict) -> dict:
    """
    Calcula features de actividad social/trading.

    Args:
        snapshot: Dict con datos de un pool snapshot o par de DexScreener.
                  Keys esperadas: buyers_24h, sellers_24h, makers_24h,
                  tx_count_24h, volume_24h, boosts (o is_boosted).

    Returns:
        Dict con los features sociales calculados.

    Ejemplo:
        >>> data = {
        ...     "buyers_24h": 150,
        ...     "sellers_24h": 80,
        ...     "makers_24h": 30,
        ...     "tx_count_24h": 500,
        ...     "volume_24h": 100000,
        ...     "boosts": 3,
        ... }
        >>> features = compute_social_features(data)
        >>> features["buyer_seller_ratio_24h"]
        1.875
    """

    # Inicializar todos los features con None
    features = {
        "buyers_24h": None,
        "sellers_24h": None,
        "buyer_seller_ratio_24h": None,
        "makers_24h": None,
        "tx_count_24h": None,
        "avg_tx_size_usd": None,
        "is_boosted": None,
    }

    # Verificar que tenemos datos
    if snapshot is None:
        return features

    # --- buyers_24h: Numero de compradores en las ultimas 24h ---
    # Directo del snapshot
    buyers = safe_float(snapshot.get("buyers_24h"), default=0.0)
    features["buyers_24h"] = buyers if buyers > 0 else None

    # --- sellers_24h: Numero de vendedores en las ultimas 24h ---
    sellers = safe_float(snapshot.get("sellers_24h"), default=0.0)
    features["sellers_24h"] = sellers if sellers > 0 else None

    # --- buyer_seller_ratio_24h: Ratio compradores / vendedores ---
    # Ratio > 1: mas compradores que vendedores (presion de compra)
    # Ratio < 1: mas vendedores que compradores (presion de venta)
    # safe_divide evita division por cero si no hay vendedores
    features["buyer_seller_ratio_24h"] = safe_divide(buyers, sellers)

    # --- makers_24h: Market makers activos ---
    makers = safe_float(snapshot.get("makers_24h"), default=0.0)
    features["makers_24h"] = makers if makers > 0 else None

    # --- tx_count_24h: Numero total de transacciones ---
    tx_count = safe_float(snapshot.get("tx_count_24h"), default=0.0)
    features["tx_count_24h"] = tx_count if tx_count > 0 else None

    # --- avg_tx_size_usd: Tamaño promedio de cada transaccion ---
    # volume_24h / tx_count_24h
    # Transacciones grandes = whales; pequeñas = retail
    volume_24h = safe_float(snapshot.get("volume_24h"), default=0.0)
    features["avg_tx_size_usd"] = safe_divide(volume_24h, tx_count)

    # --- is_boosted: Si el token tiene boosts en DexScreener ---
    # Los boosts son pagados y dan visibilidad extra al token
    # Puede venir como "boosts" (numero) o "is_boosted" (bool)
    boosts_value = snapshot.get("boosts")
    is_boosted_value = snapshot.get("is_boosted")

    if is_boosted_value is not None:
        # Si ya viene como booleano, usarlo directamente
        features["is_boosted"] = bool(is_boosted_value)
    elif boosts_value is not None:
        # Si viene como numero, es boosted si > 0
        features["is_boosted"] = safe_float(boosts_value) > 0
    else:
        features["is_boosted"] = False

    return features


def compute_temporal_social_features(snapshots_df: pd.DataFrame) -> dict:
    """
    Calcula features sociales temporales usando multiples snapshots.

    Analiza como evolucionan compradores, vendedores y volumen a lo largo
    del tiempo, detectando tendencias y aceleraciones.

    Args:
        snapshots_df: DataFrame con columnas snapshot_time, buyers_24h,
                      sellers_24h, volume_24h, tx_count_24h.

    Returns:
        Dict con features temporales calculados.
    """
    features = {
        "buyer_growth_rate": None,
        "seller_growth_rate": None,
        "buyer_seller_ratio_trend": None,
        "volume_consistency": None,
        "tx_acceleration": None,
    }

    if snapshots_df is None or snapshots_df.empty or len(snapshots_df) < 2:
        return features

    df = snapshots_df.copy()

    # Asegurar orden cronologico
    if "snapshot_time" in df.columns:
        df["snapshot_time"] = pd.to_datetime(df["snapshot_time"], errors="coerce")
        df = df.dropna(subset=["snapshot_time"]).sort_values("snapshot_time")

    if len(df) < 2:
        return features

    # --- buyer_growth_rate: Tasa de cambio de compradores entre primer y ultimo snapshot ---
    if "buyers_24h" in df.columns:
        buyers = df["buyers_24h"].dropna()
        if len(buyers) >= 2:
            first_buyers = safe_float(buyers.iloc[0])
            last_buyers = safe_float(buyers.iloc[-1])
            features["buyer_growth_rate"] = safe_divide(
                last_buyers - first_buyers, max(first_buyers, 1)
            )

    # --- seller_growth_rate: Tasa de cambio de vendedores ---
    if "sellers_24h" in df.columns:
        sellers = df["sellers_24h"].dropna()
        if len(sellers) >= 2:
            first_sellers = safe_float(sellers.iloc[0])
            last_sellers = safe_float(sellers.iloc[-1])
            features["seller_growth_rate"] = safe_divide(
                last_sellers - first_sellers, max(first_sellers, 1)
            )

    # --- buyer_seller_ratio_trend: Pendiente del ratio B/S a lo largo del tiempo ---
    if "buyers_24h" in df.columns and "sellers_24h" in df.columns:
        ratios = []
        for _, row in df.iterrows():
            b = safe_float(row.get("buyers_24h"))
            s = safe_float(row.get("sellers_24h"))
            ratios.append(safe_divide(b, max(s, 1)))
        if len(ratios) >= 2:
            features["buyer_seller_ratio_trend"] = safe_divide(
                ratios[-1] - ratios[0], len(ratios) - 1
            )

    # --- volume_consistency: Coeficiente de variacion del volumen (std/mean) ---
    # Bajo = volumen estable. Alto = volumen erratico.
    if "volume_24h" in df.columns:
        volumes = pd.to_numeric(df["volume_24h"], errors="coerce").dropna()
        if len(volumes) >= 2:
            mean_vol = volumes.mean()
            std_vol = volumes.std()
            features["volume_consistency"] = safe_divide(std_vol, max(mean_vol, 1))

    # --- tx_acceleration: Cambio en velocidad de transacciones (segunda derivada) ---
    if "tx_count_24h" in df.columns:
        tx = pd.to_numeric(df["tx_count_24h"], errors="coerce").dropna()
        if len(tx) >= 3:
            diffs = tx.diff().dropna()
            if len(diffs) >= 2:
                accel = diffs.diff().dropna()
                features["tx_acceleration"] = float(accel.mean()) if len(accel) > 0 else None

    return features
