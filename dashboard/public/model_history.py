"""
model_history.py - Bitacora de versiones del modelo ML.

Muestra el historial de versiones del modelo con metricas clave,
permitiendo al usuario ver como ha evolucionado el detector de gems.

Secciones:
  1. KPI cards de la version actual en produccion
  2. Timeline/tabla de todas las versiones
  3. Grafico de evolucion de metricas
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go


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
    st.title("Bitácora del Modelo")
    st.caption(
        "Historial de versiones del modelo ML. Cada iteración se entrena "
        "con más datos y mejora su capacidad de detectar gems."
    )

    # ------------------------------------------------------------------
    # 1. KPI cards de la version en produccion
    # ------------------------------------------------------------------
    current = next((v for v in MODEL_VERSIONS if v["is_current"]), MODEL_VERSIONS[0])

    st.subheader(f"Versión actual: {current['version']}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("RF F1 Score", f"{current['rf_f1']:.3f}")
    col2.metric("Gems de entrenamiento", current["gems"])
    col3.metric("Features", current["features"])
    col4.metric("Fecha", current["date"])

    st.divider()

    # ------------------------------------------------------------------
    # 2. Tabla de todas las versiones
    # ------------------------------------------------------------------
    st.subheader("Historial de versiones")

    df = pd.DataFrame(MODEL_VERSIONS)
    # Marcar la version actual
    df["estado"] = df["is_current"].apply(lambda x: "🟢 Producción" if x else "")
    df = df[["version", "date", "rf_f1", "gems", "features", "highlights", "estado"]]
    df.columns = ["Versión", "Fecha", "RF F1", "Gems", "Features", "Cambios clave", "Estado"]

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "RF F1": st.column_config.NumberColumn(format="%.3f"),
            "Gems": st.column_config.NumberColumn(format="%d"),
            "Features": st.column_config.NumberColumn(format="%d"),
        },
    )

    st.divider()

    # ------------------------------------------------------------------
    # 3. Grafico de evolucion de metricas
    # ------------------------------------------------------------------
    st.subheader("Evolución de métricas")

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
            line=dict(color="#00d4aa", width=2),
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
            line=dict(color="#ffaa00", width=2, dash="dash"),
            marker=dict(size=10),
            yaxis="y2",
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=400,
        yaxis=dict(
            title="RF F1 Score",
            titlefont=dict(color="#00d4aa"),
            tickfont=dict(color="#00d4aa"),
            gridcolor="rgba(255,255,255,0.05)",
        ),
        yaxis2=dict(
            title="Gems",
            titlefont=dict(color="#ffaa00"),
            tickfont=dict(color="#ffaa00"),
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

    # ------------------------------------------------------------------
    # 4. Detalle expandible por version
    # ------------------------------------------------------------------
    st.subheader("Detalle por versión")

    for v in MODEL_VERSIONS:
        label = f"**{v['version']}** — {v['date']}"
        if v["is_current"]:
            label += " 🟢 Producción"

        with st.expander(label, expanded=v["is_current"]):
            c1, c2, c3 = st.columns(3)
            c1.metric("RF F1", f"{v['rf_f1']:.3f}")
            c2.metric("Gems", v["gems"])
            c3.metric("Features", v["features"])
            st.markdown(f"**Cambios clave:** {v['highlights']}")
