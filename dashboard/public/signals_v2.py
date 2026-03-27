"""
signals_v2.py - Senales del dia (version comercial).

Pagina principal del producto: muestra los tokens que el modelo ML
ha detectado con mayor probabilidad de ser "gems" (10x+).

Orientada a suscriptores — lenguaje accesible, sin jerga tecnica,
visualizaciones limpias y un disclaimer claro.

Secciones:
  1. KPI cards: total senales, STRONG, mejor score, chains activas
  2. Tabla principal: tokens del dia ordenados por score
  3. Distribucion de senales (donut chart)
  4. Distribucion por chain (bar chart horizontal)
  5. Disclaimer legal
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.data.supabase_storage import get_storage as _get_storage
from dashboard.constants import SIGNAL_COLORS, CHAIN_COLORS

try:
    from src.models.scorer import SIGNAL_THRESHOLDS
except ImportError:
    SIGNAL_THRESHOLDS = {"STRONG": 0.80, "MEDIUM": 0.65, "WEAK": 0.50}


# ============================================================
# Helpers
# ============================================================

@st.cache_resource
def get_storage():
    """Instancia de Storage cacheada (evita reconexion por cada render)."""
    return _get_storage()


@st.cache_data(ttl=300)
def load_todays_signals() -> pd.DataFrame:
    """
    Carga las senales del dia desde Supabase (tabla scores + tokens).

    Hace JOIN con tokens para obtener name, symbol, chain y pool_address.
    Si no hay senales de hoy, devuelve TODAS las senales mas recientes
    (para entornos donde el scorer no se ejecuta diariamente).

    Returns:
        DataFrame con columnas: token_id, probability, signal, prediction,
        model_name, model_version, scored_at, name, symbol, chain, pool_address.
    """
    storage = get_storage()

    # Primero intentar senales de hoy
    df = storage.get_scores(min_probability=0.0, scored_today=True)

    # Si no hay de hoy, traer las mas recientes (hasta 200)
    if df.empty:
        df = storage.get_scores(min_probability=0.0)
        if not df.empty:
            df = df.head(200)

    return df


def _dexscreener_url(chain: str, pool_address: str) -> str:
    """Construye la URL de DexScreener para un token."""
    chain_slug = {
        "solana": "solana",
        "ethereum": "ethereum",
        "base": "base",
    }.get(chain, chain)
    return f"https://dexscreener.com/{chain_slug}/{pool_address}"


def _chain_badge(chain: str) -> str:
    """Devuelve el nombre legible de la cadena con emoji."""
    badges = {
        "solana": "Solana",
        "ethereum": "Ethereum",
        "base": "Base",
    }
    return badges.get(chain, chain.capitalize() if chain else "Desconocida")


# ============================================================
# Render principal
# ============================================================

def render():
    """Senales del dia — pagina principal del producto."""

    st.header(":fire: Senales del Dia")
    st.caption(
        "Tokens con mayor probabilidad de ser gems, detectados por nuestro modelo ML. "
        "Actualizado diariamente a las 07:00 UTC."
    )

    df = load_todays_signals()

    # --- Estado vacio: mensaje amigable ---
    if df.empty:
        st.info(
            ":hourglass_flowing_sand: **No hay senales disponibles en este momento.**\n\n"
            "El modelo se ejecuta diariamente a las 07:00 UTC. "
            "Las senales aparecen aqui automaticamente tras cada analisis."
        )
        return

    # ======================================================
    # 1. KPI CARDS
    # ======================================================
    _render_kpis(df)

    st.divider()

    # ======================================================
    # 2. TABLA PRINCIPAL
    # ======================================================
    _render_signals_table(df)

    st.divider()

    # ======================================================
    # 3 y 4. GRAFICOS: distribucion de senales + chains
    # ======================================================
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        _render_signal_distribution(df)

    with col_chart2:
        _render_chain_distribution(df)

    st.divider()

    # ======================================================
    # 5. DISCLAIMER
    # ======================================================
    _render_disclaimer()


# ============================================================
# Secciones individuales
# ============================================================

def _render_kpis(df: pd.DataFrame):
    """Tarjetas KPI en la parte superior."""

    total = len(df)
    strong_count = (df["signal"] == "STRONG").sum() if "signal" in df.columns else 0
    best_score = df["probability"].max() if "probability" in df.columns else 0.0
    chains_activas = df["chain"].nunique() if "chain" in df.columns else 0

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total senales",
        total,
        help="Numero total de tokens analizados con senal activa.",
    )
    col2.metric(
        "Senales STRONG",
        strong_count,
        help=f"Tokens con probabilidad >= {SIGNAL_THRESHOLDS['STRONG']:.0%}. Alta confianza.",
    )
    col3.metric(
        "Mejor score",
        f"{best_score:.1%}",
        help="La probabilidad mas alta asignada por el modelo hoy.",
    )
    col4.metric(
        "Chains activas",
        chains_activas,
        help="Numero de blockchains con senales (Solana, Ethereum, Base).",
    )


def _render_signals_table(df: pd.DataFrame):
    """Tabla principal de senales del dia, ordenada por score descendente."""

    st.subheader("Candidatos detectados")

    # Filtros rapidos
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        signal_options = ["Todas"] + [s for s in ["STRONG", "MEDIUM", "WEAK"] if s in df["signal"].values]
        selected_signal = st.selectbox(
            "Nivel de senal",
            signal_options,
            help="Filtra por nivel de confianza del modelo.",
        )

    with col_f2:
        if "chain" in df.columns:
            chain_options = ["Todas"] + sorted(df["chain"].dropna().unique().tolist())
        else:
            chain_options = ["Todas"]
        selected_chain = st.selectbox(
            "Blockchain",
            chain_options,
            help="Filtra por blockchain.",
        )

    # Aplicar filtros
    df_filtered = df.copy()
    if selected_signal != "Todas":
        df_filtered = df_filtered[df_filtered["signal"] == selected_signal]
    if selected_chain != "Todas":
        df_filtered = df_filtered[df_filtered["chain"] == selected_chain]

    if df_filtered.empty:
        st.info("No hay senales con los filtros seleccionados.")
        return

    # Ordenar por probabilidad descendente
    df_filtered = df_filtered.sort_values("probability", ascending=False).reset_index(drop=True)

    # Preparar columnas para mostrar
    display_data = []
    for _, row in df_filtered.iterrows():
        name = row.get("name", "")
        symbol = row.get("symbol", "")
        token_label = f"{name} ({symbol})" if name and symbol else (symbol or name or str(row.get("token_id", ""))[:12])

        chain = row.get("chain", "")
        chain_label = _chain_badge(chain)

        probability = row.get("probability", 0.0)
        signal = row.get("signal", "NONE")

        # Link a DexScreener
        pool_addr = row.get("pool_address", "")
        if pool_addr and chain:
            link = _dexscreener_url(chain, pool_addr)
        else:
            link = ""

        display_data.append({
            "Token": token_label,
            "Chain": chain_label,
            "Score": probability,
            "Senal": signal,
            "DexScreener": link,
        })

    df_display = pd.DataFrame(display_data)

    # Configuracion de columnas para st.dataframe
    column_config = {
        "Token": st.column_config.TextColumn(
            "Token",
            help="Nombre y simbolo del token.",
            width="medium",
        ),
        "Chain": st.column_config.TextColumn(
            "Chain",
            help="Blockchain donde opera el token.",
            width="small",
        ),
        "Score": st.column_config.ProgressColumn(
            "Score",
            help="Probabilidad de ser gem (0% - 100%). Mayor = mejor.",
            format="%.0f%%",
            min_value=0.0,
            max_value=1.0,
        ),
        "Senal": st.column_config.TextColumn(
            "Senal",
            help="STRONG (>80%), MEDIUM (>65%), WEAK (>50%).",
            width="small",
        ),
        "DexScreener": st.column_config.LinkColumn(
            "DexScreener",
            help="Ver en DexScreener para mas informacion del token.",
            display_text="Ver",
            width="small",
        ),
    }

    st.dataframe(
        df_display,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        height=min(len(df_display) * 38 + 40, 600),
    )

    st.caption(f"Mostrando {len(df_display)} de {len(df)} senales.")


def _render_signal_distribution(df: pd.DataFrame):
    """Donut chart con distribucion de senales (STRONG/MEDIUM/WEAK)."""

    st.subheader("Distribucion de senales")

    if "signal" not in df.columns:
        st.info("Sin datos de senales.")
        return

    # Contar por tipo de senal
    signal_counts = df["signal"].value_counts().reset_index()
    signal_counts.columns = ["Senal", "Cantidad"]

    # Filtrar solo las senales conocidas para orden consistente
    order = ["STRONG", "MEDIUM", "WEAK", "NONE"]
    signal_counts["Senal"] = pd.Categorical(
        signal_counts["Senal"], categories=order, ordered=True
    )
    signal_counts = signal_counts.sort_values("Senal").dropna(subset=["Senal"])

    fig = px.pie(
        signal_counts,
        names="Senal",
        values="Cantidad",
        color="Senal",
        color_discrete_map=SIGNAL_COLORS,
        hole=0.45,
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label+value",
        textfont_size=12,
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(t=20, b=20, l=20, r=20),
        height=350,
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_chain_distribution(df: pd.DataFrame):
    """Bar chart horizontal con distribucion por blockchain."""

    st.subheader("Senales por blockchain")

    if "chain" not in df.columns:
        st.info("Sin datos de cadena.")
        return

    chain_counts = df["chain"].value_counts().reset_index()
    chain_counts.columns = ["Chain", "Cantidad"]

    # Nombres legibles
    chain_counts["Chain_label"] = chain_counts["Chain"].apply(_chain_badge)

    fig = px.bar(
        chain_counts,
        y="Chain_label",
        x="Cantidad",
        color="Chain",
        color_discrete_map=CHAIN_COLORS,
        orientation="h",
        text="Cantidad",
    )

    fig.update_traces(
        textposition="outside",
        textfont_size=13,
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(t=20, b=20, l=20, r=20),
        height=350,
        xaxis_title="Numero de senales",
        yaxis_title="",
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_disclaimer():
    """Disclaimer legal al pie de la pagina."""

    st.warning(
        ":warning: **Esto NO es consejo financiero.**\n\n"
        "Los memecoins son extremadamente volatiles y la gran mayoria pierde todo su valor. "
        "Las senales de este modelo son herramientas de analisis, no recomendaciones de inversion. "
        "Haz tu propia investigacion (DYOR) y nunca inviertas mas de lo que puedas permitirte perder."
    )
