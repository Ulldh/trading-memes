"""
model_history.py - Bitacora de versiones del modelo ML.

Muestra el historial de versiones del modelo con metricas clave,
permitiendo al usuario ver como ha evolucionado el detector de gems.

Secciones:
  1. KPI cards de la version actual en produccion
  2. Timeline visual con cards por version
  3. Grafico de evolucion de metricas (dual-axis)
  4. Detalle expandible por version
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from dashboard.theme import ACCENT, GOLD, BG_CARD, BORDER, TEXT_MUTED


# ============================================================
# Datos estaticos de versiones del modelo
# ============================================================

MODEL_VERSIONS = [
    {
        "version": "v23",
        "date": "2026-04-03",
        "gems": 260,
        "features": 22,
        "rf_f1": 0.480,
        "highlights": "contract_age_hours recovered, 5 pipeline optimizations",
        "is_current": True,
    },
    {
        "version": "v22",
        "date": "2026-04-03",
        "gems": 260,
        "features": 22,
        "rf_f1": 0.480,
        "highlights": "219->260 gems, +7% RF F1 vs v21",
        "is_current": False,
    },
    {
        "version": "v21",
        "date": "2026-03-28",
        "gems": 194,
        "features": 22,
        "rf_f1": 0.449,
        "highlights": "52% STRONG gem rate, 71% win rate (2x+)",
        "is_current": False,
    },
    {
        "version": "v19",
        "date": "2026-03-26",
        "gems": 150,
        "features": 20,
        "rf_f1": 0.500,
        "highlights": "Clean baseline after data leakage fix",
        "is_current": False,
    },
]


def render():
    """Renderiza la pagina de historial de versiones del modelo."""
    st.markdown(
        f"<h2 style='margin-bottom: 0;'>"
        f"Bitacora del <span style='color: {ACCENT};'>Modelo</span></h2>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Historial de versiones del modelo ML. Cada iteracion se entrena "
        "con mas datos y mejora su capacidad de detectar gems."
    )

    # ------------------------------------------------------------------
    # 1. KPI cards de la version en produccion
    # ------------------------------------------------------------------
    current = next((v for v in MODEL_VERSIONS if v["is_current"]), MODEL_VERSIONS[0])

    # Badge de version actual con glow
    st.markdown(
        f"<div style='display: inline-block; background: {ACCENT}15; "
        f"color: {ACCENT}; padding: 4px 14px; border-radius: 6px; "
        f"font-weight: 700; font-size: 0.85rem; "
        f"border: 1px solid {ACCENT}30; margin-bottom: 12px; "
        f"box-shadow: 0 0 12px {ACCENT}20;'>"
        f"En produccion: {current['version']}</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("RF F1 Score", f"{current['rf_f1']:.3f}")
    col2.metric("Gems entrenamiento", current["gems"])
    col3.metric("Features", current["features"])
    col4.metric("Fecha", current["date"])

    st.divider()

    # ------------------------------------------------------------------
    # 2. Timeline visual con cards
    # ------------------------------------------------------------------
    st.subheader("Historial de versiones")

    for v in MODEL_VERSIONS:
        is_cur = v["is_current"]
        border = ACCENT if is_cur else BORDER
        glow = f"box-shadow: 0 0 15px {ACCENT}15;" if is_cur else ""
        badge = (
            f"<span style='background: {ACCENT}20; color: {ACCENT}; "
            f"padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; "
            f"font-weight: 700; margin-left: 8px;'>PRODUCCION</span>"
            if is_cur else ""
        )

        st.markdown(
            f"<div style='background: {BG_CARD}; border: 1px solid {border}; "
            f"border-left: 3px solid {border}; border-radius: 10px; "
            f"padding: 14px 18px; margin-bottom: 8px; {glow}'>"
            # Header: version + fecha + badge
            f"<div style='display: flex; align-items: center; margin-bottom: 6px;'>"
            f"<strong style='font-size: 1.05rem;'>{v['version']}</strong>"
            f"<span style='color: {TEXT_MUTED}; margin-left: 12px; "
            f"font-size: 0.85rem;'>{v['date']}</span>"
            f"{badge}"
            f"</div>"
            # Metricas inline
            f"<div style='display: flex; gap: 20px; color: {TEXT_MUTED}; "
            f"font-size: 0.85rem;'>"
            f"<span>F1: <strong style='color: {ACCENT};'>{v['rf_f1']:.3f}</strong></span>"
            f"<span>Gems: <strong style='color: {GOLD};'>{v['gems']}</strong></span>"
            f"<span>Features: <strong>{v['features']}</strong></span>"
            f"</div>"
            # Highlights
            f"<div style='color: {TEXT_MUTED}; font-size: 0.8rem; margin-top: 6px;'>"
            f"{v['highlights']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ------------------------------------------------------------------
    # 3. Grafico de evolucion de metricas
    # ------------------------------------------------------------------
    st.subheader("Evolucion de metricas")

    # Ordenar por fecha (mas antiguo primero)
    df_chart = pd.DataFrame(MODEL_VERSIONS).sort_values("date")

    fig = go.Figure()

    # RF F1 Score (eje izquierdo)
    fig.add_trace(
        go.Scatter(
            x=df_chart["version"],
            y=df_chart["rf_f1"],
            name="RF F1 Score",
            mode="lines+markers",
            line=dict(color=ACCENT, width=2),
            marker=dict(size=10),
            yaxis="y",
        )
    )

    # Gems (eje derecho)
    fig.add_trace(
        go.Scatter(
            x=df_chart["version"],
            y=df_chart["gems"],
            name="Gems",
            mode="lines+markers",
            line=dict(color=GOLD, width=2, dash="dash"),
            marker=dict(size=10),
            yaxis="y2",
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=400,
        font=dict(color="#e0e0e0"),
        yaxis=dict(
            title="RF F1 Score",
            titlefont=dict(color=ACCENT),
            tickfont=dict(color=ACCENT),
            gridcolor="rgba(255,255,255,0.04)",
        ),
        yaxis2=dict(
            title="Gems",
            titlefont=dict(color=GOLD),
            tickfont=dict(color=GOLD),
            overlaying="y",
            side="right",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=60, r=60, t=40, b=40),
    )

    st.plotly_chart(fig, use_container_width=True)
