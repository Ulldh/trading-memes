#!/usr/bin/env python3
"""
DEEP DATA ANALYSIS: What makes a GEM a GEM?
============================================
Analisis exhaustivo de las 19 features seleccionadas en v20
para entender que diferencia a los gems (10x+) del resto.
"""

import sys
import os
import json
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy import stats
from itertools import combinations

# Asegurar que el proyecto esta en el path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ============================================================
# CONFIGURACION
# ============================================================

V20_FEATURES = [
    'rsi_7d', 'atr_pct_7d', 'return_30d', 'return_48h', 'bb_lower_7d',
    'bb_pct_b_7d', 'sellers_24h', 'avg_tx_size_usd', 'bb_bandwidth_7d',
    'launch_hour_utc', 'up_days_ratio_7d', 'liq_to_mcap_ratio',
    'volume_spike_ratio', 'volume_trend_slope', 'drawdown_from_peak_7d',
    'initial_liquidity_usd', 'liquidity_to_fdv_ratio',
    'volume_to_liq_ratio_24h', 'volume_sustainability_3d'
]

# ============================================================
# 0. LOAD DATA
# ============================================================

def load_data():
    """Carga features y labels desde Supabase, los mergea."""
    from src.data.supabase_storage import SupabaseStorage
    storage = SupabaseStorage()

    print("=" * 80)
    print("0. CARGANDO DATOS DESDE SUPABASE")
    print("=" * 80)

    # Features
    features_df = storage.get_features_df()
    print(f"   Features: {features_df.shape[0]} tokens, {features_df.shape[1]} columnas")

    # Labels
    labels_df = storage.query("SELECT token_id, label_binary, label_multi, max_multiple, tier, tier_numeric FROM labels")
    print(f"   Labels:   {labels_df.shape[0]} tokens")

    # Merge
    df = features_df.merge(labels_df, on="token_id", how="inner")
    print(f"   Merged:   {df.shape[0]} tokens con features + labels")

    # Filtrar solo los que tienen label_binary
    df = df[df["label_binary"].notna()].copy()
    df["label_binary"] = df["label_binary"].astype(int)

    gems = df[df["label_binary"] == 1]
    non_gems = df[df["label_binary"] == 0]
    print(f"   Gems:     {len(gems)} ({len(gems)/len(df)*100:.1f}%)")
    print(f"   Non-gems: {len(non_gems)} ({len(non_gems)/len(df)*100:.1f}%)")

    return df, gems, non_gems


# ============================================================
# 1. STATISTICAL COMPARISON
# ============================================================

def statistical_comparison(df, gems, non_gems):
    """Compara estadisticamente gems vs non-gems para cada feature."""
    print("\n" + "=" * 80)
    print("1. COMPARACION ESTADISTICA: GEMS vs NON-GEMS")
    print("=" * 80)

    results = []

    for feat in V20_FEATURES:
        g = gems[feat].dropna()
        ng = non_gems[feat].dropna()

        if len(g) < 5 or len(ng) < 5:
            continue

        # Estadisticas basicas
        g_mean, g_med, g_std = g.mean(), g.median(), g.std()
        ng_mean, ng_med, ng_std = ng.mean(), ng.median(), ng.std()

        # Mann-Whitney U test (no asume normalidad)
        try:
            u_stat, p_value = stats.mannwhitneyu(g, ng, alternative='two-sided')
            # Rank-biserial correlation (effect size para Mann-Whitney)
            n1, n2 = len(g), len(ng)
            rank_biserial = 1 - (2 * u_stat) / (n1 * n2)
        except Exception:
            p_value = 1.0
            rank_biserial = 0.0

        # Cohen's d
        pooled_std = np.sqrt(((len(g) - 1) * g_std**2 + (len(ng) - 1) * ng_std**2) / (len(g) + len(ng) - 2))
        cohens_d = (g_mean - ng_mean) / pooled_std if pooled_std > 0 else 0

        # Direccion
        direction = "GEMS MAYOR" if g_med > ng_med else "GEMS MENOR"

        results.append({
            "feature": feat,
            "gem_mean": g_mean,
            "gem_median": g_med,
            "gem_std": g_std,
            "non_gem_mean": ng_mean,
            "non_gem_median": ng_med,
            "non_gem_std": ng_std,
            "ratio_medians": g_med / ng_med if ng_med != 0 else float('inf'),
            "p_value": p_value,
            "cohens_d": cohens_d,
            "rank_biserial": rank_biserial,
            "direction": direction,
            "significant": p_value < 0.05,
            "n_gems": len(g),
            "n_non_gems": len(ng),
        })

    results_df = pd.DataFrame(results).sort_values("p_value")

    print("\n--- RANKING POR SIGNIFICANCIA ESTADISTICA (Mann-Whitney U) ---\n")
    print(f"{'Feature':<28} {'p-value':>10} {'Cohen d':>9} {'Rank-Bis':>9} {'Gem Med':>12} {'Non-Gem Med':>12} {'Ratio':>8} {'Dir':>14}")
    print("-" * 115)

    for _, r in results_df.iterrows():
        sig = "***" if r["p_value"] < 0.001 else "**" if r["p_value"] < 0.01 else "*" if r["p_value"] < 0.05 else ""
        print(f"{r['feature']:<28} {r['p_value']:>10.2e} {r['cohens_d']:>+9.3f} {r['rank_biserial']:>+9.3f} {r['gem_median']:>12.4f} {r['non_gem_median']:>12.4f} {r['ratio_medians']:>8.2f} {r['direction']:>14} {sig}")

    # Top 5 mas discriminativas
    top5 = results_df.head(5)["feature"].tolist()
    print(f"\n   TOP 5 FEATURES MAS DISCRIMINATIVAS:")
    for i, feat in enumerate(top5, 1):
        row = results_df[results_df["feature"] == feat].iloc[0]
        print(f"   {i}. {feat} (p={row['p_value']:.2e}, d={row['cohens_d']:+.3f}, {row['direction']})")

    return results_df, top5


# ============================================================
# 2. DISTRIBUTION ANALYSIS
# ============================================================

def distribution_analysis(df, gems, non_gems, top5):
    """Analisis de distribucion con percentiles para top 5 features."""
    print("\n" + "=" * 80)
    print("2. ANALISIS DE DISTRIBUCION: PERCENTILES Y SWEET SPOTS")
    print("=" * 80)

    percentiles = [10, 25, 50, 75, 90]

    for feat in top5:
        g = gems[feat].dropna()
        ng = non_gems[feat].dropna()

        print(f"\n--- {feat} ---")
        print(f"   {'Percentile':>12} {'Gems':>15} {'Non-Gems':>15} {'Ratio':>10}")
        print(f"   {'-'*55}")

        for p in percentiles:
            g_val = np.percentile(g, p)
            ng_val = np.percentile(ng, p)
            ratio = g_val / ng_val if ng_val != 0 else float('inf')
            print(f"   {'P' + str(p):>12} {g_val:>15.4f} {ng_val:>15.4f} {ratio:>10.2f}")

        # Sweet spots: donde gems estan sobre-representados
        print(f"\n   SWEET SPOTS (bins donde gems estan sobre-representados):")
        all_vals = df[feat].dropna()

        # Crear bins basados en quantiles de toda la poblacion
        try:
            bins = pd.qcut(all_vals, q=10, duplicates='drop')
            bin_analysis = df.dropna(subset=[feat]).groupby(bins, observed=True)["label_binary"].agg(["sum", "count"])
            bin_analysis["gem_rate"] = bin_analysis["sum"] / bin_analysis["count"]
            overall_gem_rate = df["label_binary"].mean()
            bin_analysis["overrepresentation"] = bin_analysis["gem_rate"] / overall_gem_rate

            for idx, row in bin_analysis.iterrows():
                marker = " <<<" if row["overrepresentation"] > 1.5 else ""
                bar = "█" * int(min(row["overrepresentation"] * 10, 40))
                print(f"   {str(idx):>35}  gems={int(row['sum']):>3}/{int(row['count']):>4}  rate={row['gem_rate']:.3f}  OR={row['overrepresentation']:.2f}x {bar}{marker}")
        except Exception as e:
            print(f"   Error en bins: {e}")


# ============================================================
# 3. CORRELATION WITH GEM PROBABILITY
# ============================================================

def correlation_analysis(df, gems, non_gems):
    """Correlaciones lineales y no lineales con label_binary."""
    print("\n" + "=" * 80)
    print("3. CORRELACION CON GEM PROBABILITY")
    print("=" * 80)

    # Point-biserial correlation (label_binary es binaria)
    print("\n--- CORRELACION POINT-BISERIAL ---\n")
    corr_results = []

    for feat in V20_FEATURES:
        valid = df[[feat, "label_binary"]].dropna()
        if len(valid) < 10:
            continue
        corr, p_val = stats.pointbiserialr(valid["label_binary"], valid[feat])
        corr_results.append({"feature": feat, "correlation": corr, "p_value": p_val, "abs_corr": abs(corr)})

    corr_df = pd.DataFrame(corr_results).sort_values("abs_corr", ascending=False)

    print(f"{'Feature':<28} {'Corr':>10} {'p-value':>12} {'Strength':>12}")
    print("-" * 65)
    for _, r in corr_df.iterrows():
        strength = "FUERTE" if r["abs_corr"] > 0.2 else "MODERADA" if r["abs_corr"] > 0.1 else "DEBIL"
        print(f"{r['feature']:<28} {r['correlation']:>+10.4f} {r['p_value']:>12.2e} {strength:>12}")

    # Non-linear analysis: buscar si gems se concentran en rangos especificos
    print("\n--- ANALISIS NO-LINEAL: CONCENTRACION EN RANGOS ---\n")

    for feat in V20_FEATURES:
        valid = df[[feat, "label_binary"]].dropna()
        if len(valid) < 10:
            continue

        # Dividir en quintiles y ver gem rate
        try:
            valid["quintile"] = pd.qcut(valid[feat], q=5, labels=["Q1(low)", "Q2", "Q3", "Q4", "Q5(high)"], duplicates='drop')
            gem_rates = valid.groupby("quintile", observed=True)["label_binary"].mean()

            # Detectar patron no-lineal: si gem rate no es monotona
            rates = gem_rates.values
            if len(rates) >= 3:
                # Check if middle quintiles have higher rate than extremes
                max_rate = max(rates)
                min_rate = min(rates)
                max_idx = np.argmax(rates)

                # Solo reportar si hay variacion significativa
                if max_rate > 0.05 and max_rate / (min_rate + 1e-6) > 2:
                    print(f"   {feat}:")
                    for q, rate in gem_rates.items():
                        bar = "█" * int(rate * 200)
                        print(f"      {q:>10}: {rate:.4f} {bar}")

                    # Identificar si es lineal o no-lineal
                    if max_idx in [0, len(rates)-1]:
                        print(f"      --> Relacion MONOTONA (mejor en extremo)")
                    else:
                        print(f"      --> Relacion NO-LINEAL (mejor en Q{max_idx+1})")
                    print()
        except Exception:
            pass

    return corr_df


# ============================================================
# 4. GEM PROFILE
# ============================================================

def gem_profile(df, gems, non_gems):
    """Perfil del gem promedio vs non-gem promedio."""
    print("\n" + "=" * 80)
    print("4. PERFIL DEL GEM: PROMEDIO vs NON-GEM")
    print("=" * 80)

    print("\n--- GEM PROMEDIO vs NON-GEM PROMEDIO ---\n")
    print(f"{'Feature':<28} {'Gem Avg':>12} {'Non-Gem Avg':>12} {'Diff %':>10} {'Gem tiene':>15}")
    print("-" * 80)

    for feat in V20_FEATURES:
        g_avg = gems[feat].mean()
        ng_avg = non_gems[feat].mean()
        pct_diff = ((g_avg - ng_avg) / abs(ng_avg) * 100) if ng_avg != 0 else float('inf')
        direction = "MAS" if g_avg > ng_avg else "MENOS"
        print(f"{feat:<28} {g_avg:>12.4f} {ng_avg:>12.4f} {pct_diff:>+10.1f}% {direction:>15}")

    # Perfil del gem mediano (mas robusto que la media)
    print("\n--- GEM MEDIANO (perfil robusto) ---\n")
    print(f"{'Feature':<28} {'Gem P50':>12} {'Non-Gem P50':>12} {'Diff %':>10}")
    print("-" * 65)

    for feat in V20_FEATURES:
        g_med = gems[feat].median()
        ng_med = non_gems[feat].median()
        pct_diff = ((g_med - ng_med) / abs(ng_med) * 100) if ng_med != 0 else float('inf')
        print(f"{feat:<28} {g_med:>12.4f} {ng_med:>12.4f} {pct_diff:>+10.1f}%")

    # Subtipos de gems
    print("\n--- SUBTIPOS DE GEMS (clustering) ---\n")

    # Usar max_multiple para clasificar subtipos
    if "max_multiple" in gems.columns:
        gems_with_mult = gems[gems["max_multiple"].notna()].copy()
        if len(gems_with_mult) > 0:
            print(f"   Gems con max_multiple: {len(gems_with_mult)}")
            print(f"   Distribucion de max_multiple:")
            print(f"      Min:    {gems_with_mult['max_multiple'].min():.2f}x")
            print(f"      P25:    {gems_with_mult['max_multiple'].quantile(0.25):.2f}x")
            print(f"      Median: {gems_with_mult['max_multiple'].median():.2f}x")
            print(f"      P75:    {gems_with_mult['max_multiple'].quantile(0.75):.2f}x")
            print(f"      Max:    {gems_with_mult['max_multiple'].max():.2f}x")

            # Subtipos: small gems (10-50x), medium (50-100x), mega (100x+)
            small = gems_with_mult[gems_with_mult["max_multiple"] < 50]
            medium = gems_with_mult[(gems_with_mult["max_multiple"] >= 50) & (gems_with_mult["max_multiple"] < 100)]
            mega = gems_with_mult[gems_with_mult["max_multiple"] >= 100]

            print(f"\n   SUBTIPOS:")
            print(f"      Small Gems (10-50x):   {len(small)} ({len(small)/len(gems_with_mult)*100:.0f}%)")
            print(f"      Medium Gems (50-100x):  {len(medium)} ({len(medium)/len(gems_with_mult)*100:.0f}%)")
            print(f"      Mega Gems (100x+):      {len(mega)} ({len(mega)/len(gems_with_mult)*100:.0f}%)")

            # Comparar features entre subtipos
            if len(small) >= 5 and len(mega) >= 3:
                print(f"\n   DIFERENCIAS SMALL vs MEGA GEMS:")
                print(f"   {'Feature':<28} {'Small Med':>12} {'Mega Med':>12} {'Diff':>10}")
                print(f"   {'-'*65}")
                for feat in V20_FEATURES:
                    s_med = small[feat].median()
                    m_med = mega[feat].median()
                    diff = ((m_med - s_med) / abs(s_med) * 100) if s_med != 0 else float('inf')
                    marker = " <<<" if abs(diff) > 100 else ""
                    print(f"   {feat:<28} {s_med:>12.4f} {m_med:>12.4f} {diff:>+10.1f}%{marker}")

    # Uso de tiers si existen
    if "tier" in df.columns:
        tier_dist = gems[gems["tier"].notna()]["tier"].value_counts()
        if len(tier_dist) > 0:
            print(f"\n   DISTRIBUCION POR TIER (gems):")
            for tier, count in tier_dist.items():
                print(f"      {tier}: {count}")

    if "label_multi" in df.columns:
        multi_dist = gems[gems["label_multi"].notna()]["label_multi"].value_counts()
        if len(multi_dist) > 0:
            print(f"\n   DISTRIBUCION POR LABEL MULTI (gems):")
            for label, count in multi_dist.items():
                print(f"      {label}: {count}")


# ============================================================
# 5. MISSING DATA ANALYSIS
# ============================================================

def missing_data_analysis(df, gems, non_gems):
    """Analisis de datos faltantes: patron informativo?"""
    print("\n" + "=" * 80)
    print("5. ANALISIS DE DATOS FALTANTES")
    print("=" * 80)

    print(f"\n{'Feature':<28} {'Gem NaN%':>10} {'Non-Gem NaN%':>13} {'Diff':>8} {'Informativo?':>14}")
    print("-" * 75)

    informative_missing = []

    for feat in V20_FEATURES:
        g_nan_pct = gems[feat].isna().mean() * 100
        ng_nan_pct = non_gems[feat].isna().mean() * 100
        diff = g_nan_pct - ng_nan_pct

        # Test si missing rate es diferente
        gem_missing = gems[feat].isna().sum()
        gem_present = len(gems) - gem_missing
        ng_missing = non_gems[feat].isna().sum()
        ng_present = len(non_gems) - ng_missing

        try:
            _, p_val = stats.fisher_exact([[gem_present, gem_missing], [ng_present, ng_missing]])
            informative = "SI" if p_val < 0.05 else "no"
        except Exception:
            informative = "?"

        print(f"{feat:<28} {g_nan_pct:>10.1f}% {ng_nan_pct:>13.1f}% {diff:>+8.1f}pp {informative:>14}")

        if informative == "SI":
            informative_missing.append(feat)

    if informative_missing:
        print(f"\n   FEATURES CON PATRON DE NaN INFORMATIVO:")
        for feat in informative_missing:
            print(f"   - {feat}: los gems tienen {'MAS' if gems[feat].isna().mean() > non_gems[feat].isna().mean() else 'MENOS'} datos faltantes")
    else:
        print(f"\n   No se detectaron patrones informativos en datos faltantes.")

    # Total missing per token
    print(f"\n--- NaN TOTALES POR TOKEN ---")
    gems_nan_per_token = gems[V20_FEATURES].isna().sum(axis=1)
    ng_nan_per_token = non_gems[V20_FEATURES].isna().sum(axis=1)
    print(f"   Gems:     media={gems_nan_per_token.mean():.1f}, mediana={gems_nan_per_token.median():.0f}")
    print(f"   Non-Gems: media={ng_nan_per_token.mean():.1f}, mediana={ng_nan_per_token.median():.0f}")


# ============================================================
# 6. FEATURE INTERACTION ANALYSIS
# ============================================================

def feature_interaction_analysis(df, gems, non_gems):
    """Busca combinaciones de 2 features especialmente predictivas."""
    print("\n" + "=" * 80)
    print("6. ANALISIS DE INTERACCIONES ENTRE FEATURES")
    print("=" * 80)

    overall_gem_rate = df["label_binary"].mean()
    print(f"\n   Gem rate general: {overall_gem_rate:.4f} ({overall_gem_rate*100:.2f}%)")

    # Para cada par de features, dividir en cuadrantes (above/below median)
    # y buscar cuadrantes con alta concentracion de gems

    interaction_results = []

    for f1, f2 in combinations(V20_FEATURES, 2):
        valid = df[[f1, f2, "label_binary"]].dropna()
        if len(valid) < 50:
            continue

        med1 = valid[f1].median()
        med2 = valid[f2].median()

        # 4 cuadrantes
        q_hh = valid[(valid[f1] >= med1) & (valid[f2] >= med2)]  # high-high
        q_hl = valid[(valid[f1] >= med1) & (valid[f2] < med2)]   # high-low
        q_lh = valid[(valid[f1] < med1) & (valid[f2] >= med2)]   # low-high
        q_ll = valid[(valid[f1] < med1) & (valid[f2] < med2)]    # low-low

        for quadrant, q_data, q_name in [
            ("HH", q_hh, f"{f1}>=med & {f2}>=med"),
            ("HL", q_hl, f"{f1}>=med & {f2}<med"),
            ("LH", q_lh, f"{f1}<med & {f2}>=med"),
            ("LL", q_ll, f"{f1}<med & {f2}<med"),
        ]:
            if len(q_data) < 10:
                continue
            gem_rate = q_data["label_binary"].mean()
            n_gems = q_data["label_binary"].sum()
            lift = gem_rate / overall_gem_rate if overall_gem_rate > 0 else 0

            if lift > 2.5 and n_gems >= 5:
                interaction_results.append({
                    "feature_1": f1,
                    "feature_2": f2,
                    "quadrant": quadrant,
                    "description": q_name,
                    "gem_rate": gem_rate,
                    "n_gems": int(n_gems),
                    "n_total": len(q_data),
                    "lift": lift,
                })

    if interaction_results:
        int_df = pd.DataFrame(interaction_results).sort_values("lift", ascending=False)

        print(f"\n--- TOP INTERACCIONES CON LIFT > 2.5x ---\n")
        print(f"{'Feature 1':<24} {'Feature 2':<24} {'Quad':>5} {'Gem Rate':>10} {'Gems':>6} {'Total':>7} {'Lift':>7}")
        print("-" * 90)

        for _, r in int_df.head(30).iterrows():
            print(f"{r['feature_1']:<24} {r['feature_2']:<24} {r['quadrant']:>5} {r['gem_rate']:>10.4f} {r['n_gems']:>6} {r['n_total']:>7} {r['lift']:>7.2f}x")

        # Top 5 interacciones mas fuertes
        print(f"\n   TOP 5 COMBINACIONES MAS PREDICTIVAS:")
        for i, (_, r) in enumerate(int_df.head(5).iterrows(), 1):
            print(f"   {i}. {r['feature_1']} + {r['feature_2']} ({r['quadrant']})")
            print(f"      Gem rate: {r['gem_rate']:.4f} ({r['lift']:.1f}x lift), {int(r['n_gems'])} gems de {r['n_total']} tokens")
    else:
        print("\n   No se encontraron interacciones con lift > 2.5x")

    # Analisis especifico: triples (top 3 features)
    print(f"\n--- ANALISIS DE TRIPLES (3 features) ---")

    # Usar las 6 features mas discriminativas
    top6 = V20_FEATURES[:6]  # Placeholder, usaremos las de la seccion 1

    triple_results = []
    for f1, f2, f3 in combinations(V20_FEATURES, 3):
        valid = df[[f1, f2, f3, "label_binary"]].dropna()
        if len(valid) < 50:
            continue

        med1, med2, med3 = valid[f1].median(), valid[f2].median(), valid[f3].median()

        # "All high" y "all low" octantes
        all_high = valid[(valid[f1] >= med1) & (valid[f2] >= med2) & (valid[f3] >= med3)]
        all_low = valid[(valid[f1] < med1) & (valid[f2] < med2) & (valid[f3] < med3)]

        for octant, o_data, o_name in [("HHH", all_high, "all>=med"), ("LLL", all_low, "all<med")]:
            if len(o_data) < 10:
                continue
            gem_rate = o_data["label_binary"].mean()
            n_gems = o_data["label_binary"].sum()
            lift = gem_rate / overall_gem_rate if overall_gem_rate > 0 else 0

            if lift > 3.0 and n_gems >= 3:
                triple_results.append({
                    "features": f"{f1} + {f2} + {f3}",
                    "octant": octant,
                    "gem_rate": gem_rate,
                    "n_gems": int(n_gems),
                    "n_total": len(o_data),
                    "lift": lift,
                })

    if triple_results:
        triple_df = pd.DataFrame(triple_results).sort_values("lift", ascending=False)
        print(f"\n   TOP TRIPLES CON LIFT > 3x:\n")
        for _, r in triple_df.head(10).iterrows():
            print(f"   {r['features']} ({r['octant']}): gem_rate={r['gem_rate']:.4f}, {int(r['n_gems'])} gems/{r['n_total']} tokens, lift={r['lift']:.1f}x")
    else:
        print("   No se encontraron triples con lift > 3x")

    return interaction_results


# ============================================================
# 7. EXECUTIVE SUMMARY
# ============================================================

def executive_summary(stat_df, corr_df, df, gems, non_gems, top5):
    """Resumen ejecutivo con hallazgos clave."""
    print("\n" + "=" * 80)
    print("7. RESUMEN EJECUTIVO: QUE HACE A UN GEM")
    print("=" * 80)

    overall_gem_rate = df["label_binary"].mean()

    print(f"""
    DATOS:
    - {len(df)} tokens analizados
    - {len(gems)} gems ({len(gems)/len(df)*100:.1f}%)
    - {len(non_gems)} non-gems ({len(non_gems)/len(df)*100:.1f}%)
    - 19 features seleccionadas en v20
    """)

    # Features significativas
    sig = stat_df[stat_df["significant"] == True]
    print(f"    FEATURES ESTADISTICAMENTE SIGNIFICATIVAS: {len(sig)} de 19")
    print()

    for _, r in sig.iterrows():
        effect = "grande" if abs(r['cohens_d']) > 0.8 else "medio" if abs(r['cohens_d']) > 0.5 else "pequeño"
        print(f"    - {r['feature']}: p={r['p_value']:.2e}, efecto {effect} (d={r['cohens_d']:+.3f})")

    # Perfil del gem ideal
    print(f"""
    PERFIL DEL GEM IDEAL (basado en medianas):
    """)

    for _, r in stat_df[stat_df["significant"] == True].iterrows():
        direction = "ALTO" if r["direction"] == "GEMS MAYOR" else "BAJO"
        print(f"    - {r['feature']}: {direction} (gem={r['gem_median']:.4f} vs non-gem={r['non_gem_median']:.4f})")

    print(f"""
    CONCLUSION:
    Un gem tipico se caracteriza por tener valores diferenciados en las features
    estadisticamente significativas listadas arriba. El modelo v20 con AUC 0.89
    captura estas señales, pero el F1 de ~0.47 indica que la precision/recall
    aun tiene margen de mejora (solo 66 gems en train set, clase muy desbalanceada).

    RECOMENDACIONES:
    1. Acumular mas gems (actualmente {len(gems)}, idealmente 300+) para mejorar estabilidad
    2. Las interacciones de features sugieren que COMBINACIONES son mas predictivas que features individuales
    3. Considerar features derivadas de las interacciones mas fuertes como nuevas features
    4. El patron de missing data puede ser informativo — considerar 'is_missing' features
    """)


# ============================================================
# 8. ADDITIONAL: ALL 52 FEATURES ANALYSIS (exploration)
# ============================================================

def all_features_quick_scan(df, gems, non_gems):
    """Scan rapido de TODAS las features disponibles, no solo las 19 seleccionadas."""
    print("\n" + "=" * 80)
    print("8. SCAN RAPIDO: TODAS LAS FEATURES DISPONIBLES")
    print("=" * 80)

    # Identificar todas las columnas numericas (excepto metadata)
    skip_cols = {"token_id", "label_binary", "label_multi", "max_multiple", "tier", "tier_numeric",
                 "return_7d", "final_multiple", "notes"}
    numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c not in skip_cols]

    print(f"\n   Total features numericas disponibles: {len(numeric_cols)}")
    print(f"   En v20: {len(V20_FEATURES)}")
    print(f"   No seleccionadas: {len(numeric_cols) - len(V20_FEATURES)}")

    # Test rapido de todas
    results = []
    for feat in numeric_cols:
        g = gems[feat].dropna()
        ng = non_gems[feat].dropna()
        if len(g) < 5 or len(ng) < 5:
            continue
        try:
            _, p_value = stats.mannwhitneyu(g, ng, alternative='two-sided')
            corr, _ = stats.pointbiserialr(df[feat].dropna().index.map(lambda i: df.loc[i, "label_binary"] if i in df.index else 0), df[feat].dropna())
        except Exception:
            p_value = 1.0
            corr = 0.0

        in_v20 = feat in V20_FEATURES
        results.append({"feature": feat, "p_value": p_value, "in_v20": in_v20})

    results_df = pd.DataFrame(results).sort_values("p_value")

    # Features NO en v20 que son significativas
    missed = results_df[(~results_df["in_v20"]) & (results_df["p_value"] < 0.05)]
    if len(missed) > 0:
        print(f"\n   FEATURES SIGNIFICATIVAS NO INCLUIDAS EN v20:")
        for _, r in missed.iterrows():
            print(f"   - {r['feature']} (p={r['p_value']:.2e}) <<<")
    else:
        print(f"\n   Todas las features significativas ya estan en v20.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║   DEEP ANALYSIS: WHAT MAKES A GEM A GEM?                       ║")
    print("║   Trading Memes - Memecoin Gem Detector                        ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()

    # Load data
    df, gems, non_gems = load_data()

    # 1. Statistical comparison
    stat_df, top5 = statistical_comparison(df, gems, non_gems)

    # 2. Distribution analysis
    distribution_analysis(df, gems, non_gems, top5)

    # 3. Correlation analysis
    corr_df = correlation_analysis(df, gems, non_gems)

    # 4. Gem profile
    gem_profile(df, gems, non_gems)

    # 5. Missing data
    missing_data_analysis(df, gems, non_gems)

    # 6. Feature interactions
    interaction_results = feature_interaction_analysis(df, gems, non_gems)

    # 7. Executive summary
    executive_summary(stat_df, corr_df, df, gems, non_gems, top5)

    # 8. All features scan
    all_features_quick_scan(df, gems, non_gems)

    print("\n" + "=" * 80)
    print("ANALISIS COMPLETADO")
    print("=" * 80)
