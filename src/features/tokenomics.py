"""
tokenomics.py - Calculo de features de tokenomics (distribucion de holders).

Este modulo analiza la distribucion de holders (poseedores) de un token
para detectar concentracion excesiva, que suele ser señal de riesgo.

Conceptos clave:
    - Herfindahl Index: Mide la concentracion de mercado. Valores altos
      indican que pocos holders controlan la mayoria del supply.
    - Mint Authority: Si el creador puede crear mas tokens, hay riesgo
      de inflacion (dilucion del valor).

Features que calcula:
    - top1_holder_pct: % del supply del holder mas grande
    - top5_holder_pct: % acumulado de los 5 mayores holders
    - top10_holder_pct: % acumulado de los 10 mayores holders
    - holder_herfindahl: Indice de concentracion Herfindahl
    - has_mint_authority: Si el contrato puede emitir mas tokens
    - total_supply_log: log10 del total supply (para normalizar)
"""

import pandas as pd
import numpy as np
from typing import Optional

from src.utils.helpers import safe_float, safe_divide, log_scale


def compute_tokenomics_features(
    holders_df: pd.DataFrame,
    contract_info: dict
) -> dict:
    """
    Calcula features de tokenomics a partir de datos de holders y contrato.

    Args:
        holders_df: DataFrame con columnas [rank, amount, pct_of_supply].
                    Cada fila es un holder, ordenados por rank (1 = mayor).
        contract_info: Dict con informacion del contrato, incluyendo
                       'has_mint_authority' y 'total_supply'.

    Returns:
        Dict con los features calculados. Si no hay datos suficientes,
        los valores seran None.

    Ejemplo:
        >>> import pandas as pd
        >>> holders = pd.DataFrame({
        ...     "rank": [1, 2, 3],
        ...     "pct_of_supply": [15.0, 10.0, 5.0]
        ... })
        >>> info = {"has_mint_authority": False, "total_supply": 1e9}
        >>> features = compute_tokenomics_features(holders, info)
        >>> features["top1_holder_pct"]
        15.0
    """

    # Inicializar todos los features con None (por si no se pueden calcular)
    features = {
        "top1_holder_pct": None,
        "top5_holder_pct": None,
        "top10_holder_pct": None,
        "holder_herfindahl": None,
        "has_mint_authority": None,
        "total_supply_log": None,
    }

    # --- Features derivados de holders ---
    # Solo calcular si tenemos datos de holders
    if holders_df is not None and not holders_df.empty:
        # Asegurarnos de que los datos estan ordenados por rank (1 = mayor holder)
        df = holders_df.sort_values("rank").reset_index(drop=True)

        # Convertir pct_of_supply a float de forma segura
        pct_values = df["pct_of_supply"].apply(safe_float)

        # top1_holder_pct: porcentaje del holder mas grande
        if len(pct_values) >= 1:
            features["top1_holder_pct"] = pct_values.iloc[0]

        # top5_holder_pct: suma del porcentaje de los 5 mayores holders
        if len(pct_values) >= 1:
            features["top5_holder_pct"] = pct_values.head(5).sum()

        # top10_holder_pct: suma del porcentaje de los 10 mayores holders
        if len(pct_values) >= 1:
            features["top10_holder_pct"] = pct_values.head(10).sum()

        # holder_herfindahl: Indice de Herfindahl-Hirschman (HHI)
        # Formula: sum((pct/100)^2) para cada holder
        # Rango: 0 (distribucion perfecta) a 1 (un solo holder tiene todo)
        # Valores > 0.25 indican alta concentracion
        pct_as_fraction = pct_values / 100.0  # Convertir porcentaje a fraccion
        features["holder_herfindahl"] = float((pct_as_fraction ** 2).sum())

    # --- Features derivados del contrato ---
    if contract_info is not None:
        # has_mint_authority: Si el creador puede crear mas tokens (riesgo)
        features["has_mint_authority"] = bool(
            contract_info.get("has_mint_authority", False)
        )

        # total_supply_log: log10 del total supply
        # Usamos log para normalizar valores que varian enormemente
        # (ej: 1 millon vs 1 trillon)
        total_supply = safe_float(contract_info.get("total_supply"), default=0.0)
        features["total_supply_log"] = log_scale(total_supply, base=10.0)

    return features


def compute_whale_movement_features(all_holders_df: pd.DataFrame) -> dict:
    """
    Calcula features de movimiento de ballenas comparando snapshots de holders.

    Detecta acumulacion/distribucion de whales y cambios en la concentracion.
    Requiere al menos 2 snapshots de holders para funcionar.

    Args:
        all_holders_df: DataFrame con TODOS los snapshots de holders.
                        Columnas: snapshot_time, rank, holder_address, pct_of_supply.

    Returns:
        Dict con features de whale movement.
    """
    features = {
        "whale_accumulation_7d": None,
        "top5_concentration_change_7d": None,
        "new_whale_count": None,
        "whale_turnover_rate": None,
    }

    if all_holders_df is None or all_holders_df.empty:
        return features

    df = all_holders_df.copy()

    # Asegurar tipos y orden
    if "snapshot_time" not in df.columns:
        return features
    df["snapshot_time"] = pd.to_datetime(df["snapshot_time"], errors="coerce")
    df = df.dropna(subset=["snapshot_time"])

    # Obtener snapshots unicos
    unique_times = sorted(df["snapshot_time"].unique())
    if len(unique_times) < 2:
        return features

    # Snapshot mas reciente y mas antiguo
    latest_time = unique_times[-1]
    earliest_time = unique_times[0]

    latest_snap = df[df["snapshot_time"] == latest_time].copy()
    earliest_snap = df[df["snapshot_time"] == earliest_time].copy()

    # --- whale_accumulation_7d: Cambio en % del top1 holder ---
    if not latest_snap.empty and not earliest_snap.empty:
        latest_top1 = latest_snap.sort_values("rank").head(1)
        earliest_top1 = earliest_snap.sort_values("rank").head(1)

        if not latest_top1.empty and not earliest_top1.empty:
            latest_pct = safe_float(latest_top1["pct_of_supply"].iloc[0])
            earliest_pct = safe_float(earliest_top1["pct_of_supply"].iloc[0])
            features["whale_accumulation_7d"] = latest_pct - earliest_pct

    # --- top5_concentration_change_7d: Cambio en concentracion top5 ---
    latest_top5_pct = safe_float(
        latest_snap.sort_values("rank").head(5)["pct_of_supply"].apply(safe_float).sum()
    )
    earliest_top5_pct = safe_float(
        earliest_snap.sort_values("rank").head(5)["pct_of_supply"].apply(safe_float).sum()
    )
    if latest_top5_pct > 0 or earliest_top5_pct > 0:
        features["top5_concentration_change_7d"] = latest_top5_pct - earliest_top5_pct

    # --- new_whale_count: Nuevos holders en top20 ---
    # Compara las direcciones del top20 entre snapshots
    if "holder_address" in df.columns:
        latest_top20 = set(
            latest_snap.sort_values("rank").head(20)["holder_address"].dropna()
        )
        earliest_top20 = set(
            earliest_snap.sort_values("rank").head(20)["holder_address"].dropna()
        )
        if latest_top20 and earliest_top20:
            new_whales = latest_top20 - earliest_top20
            features["new_whale_count"] = len(new_whales)

            # --- whale_turnover_rate: % de top20 que cambio ---
            features["whale_turnover_rate"] = safe_divide(
                len(new_whales), len(latest_top20)
            )

    return features
