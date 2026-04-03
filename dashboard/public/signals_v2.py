"""
signals_v2.py - Senales del dia (version comercial premium).

Pagina principal del producto: muestra los tokens que el modelo ML
ha detectado con mayor probabilidad de ser "gems" (10x+).

Orientada a suscriptores — lenguaje accesible, sin jerga tecnica,
visualizaciones estilo trading terminal profesional.

Secciones:
  1. KPI cards: total senales, STRONG, mejor score, chains activas
  2. Tabla principal: tokens del dia como trading cards premium
  3. Distribucion de senales (donut chart)
  4. Distribucion por chain (bar chart horizontal)
  5. Disclaimer legal

PRO enhancements:
  - Indicador de confianza del modelo (Alta/Media/Baja) por senal
  - Barra de probabilidad visual con glow
  - Badge de chain (SOL/ETH/BASE) junto a cada token
  - Tiempo desde que el token fue descubierto
  - Quick link a DexScreener y GeckoTerminal
  - Boton de exportar CSV (solo Pro/Admin)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone

from src.data.supabase_storage import get_storage as _get_storage
from dashboard.constants import SIGNAL_COLORS, CHAIN_COLORS
from dashboard.i18n import t
from dashboard.theme import (
    signal_badge_html, chain_badge_html,
    kpi_card_html, signal_card_html,
    ACCENT, GOLD, BG_CARD, BG_SURFACE, BORDER, TEXT_MUTED,
)

try:
    from config import SIGNAL_THRESHOLDS
except ImportError:
    SIGNAL_THRESHOLDS = {"STRONG": 0.60, "MEDIUM": 0.40, "WEAK": 0.30}


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


def _chain_icon(chain: str) -> str:
    """Devuelve un icono de blockchain para uso en la tabla Pro."""
    icons = {
        "solana": "🟣",
        "ethereum": "🔵",
        "base": "🔷",
    }
    return icons.get(chain, "⚪")


def _geckoterminal_url(chain: str, pool_address: str) -> str:
    """Construye la URL de GeckoTerminal para un token."""
    chain_slug = {
        "solana": "solana",
        "ethereum": "eth",
        "base": "base",
    }.get(chain, chain)
    return f"https://www.geckoterminal.com/{chain_slug}/pools/{pool_address}"


def _confidence_badge(probability: float) -> str:
    """Devuelve badge de confianza: Alta/Media/Baja segun probabilidad."""
    if probability >= 0.70:
        return t("pro.confidence_high", "Alta")
    elif probability >= 0.50:
        return t("pro.confidence_medium", "Media")
    else:
        return t("pro.confidence_low", "Baja")


def _confidence_color(probability: float) -> str:
    """Devuelve color CSS segun nivel de confianza (paleta terminal)."""
    if probability >= 0.70:
        return "#00ff41"  # verde terminal
    elif probability >= 0.50:
        return "#fbbf24"  # oro
    else:
        return "#ef4444"  # rojo


def _time_since_discovered(first_seen) -> str:
    """Calcula tiempo transcurrido desde que se descubrio el token."""
    if not first_seen:
        return "N/A"
    try:
        if isinstance(first_seen, str):
            # Intentar parsear ISO format
            first_seen = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
        if not hasattr(first_seen, "tzinfo") or first_seen.tzinfo is None:
            first_seen = first_seen.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - first_seen
        days = delta.days
        hours = delta.seconds // 3600

        if days > 30:
            return f"{days // 30}m {days % 30}d"
        elif days > 0:
            return f"{days}d {hours}h"
        else:
            return f"{hours}h"
    except Exception:
        return "N/A"


def _time_since_scored(scored_at) -> str:
    """Devuelve cadena legible de tiempo transcurrido desde que se calculo el score.

    Ejemplos: 'Hace 2h', 'Hace 18h', 'Hace 3d'
    """
    if not scored_at:
        return ""
    try:
        if isinstance(scored_at, str):
            scored_at = datetime.fromisoformat(scored_at.replace("Z", "+00:00"))
        if not hasattr(scored_at, "tzinfo") or scored_at.tzinfo is None:
            scored_at = scored_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - scored_at
        total_hours = int(delta.total_seconds() // 3600)
        days = delta.days

        if days >= 2:
            return f"Hace {days}d"
        elif total_hours >= 1:
            return f"Hace {total_hours}h"
        else:
            minutes = int(delta.total_seconds() // 60)
            return f"Hace {minutes}min" if minutes > 0 else "Ahora"
    except Exception:
        return ""


def _is_pro_or_admin() -> bool:
    """Verifica si el usuario actual es Pro o Admin."""
    role = st.session_state.get("role", "free")
    if role == "admin":
        return True
    plan = st.session_state.get("profile", {}).get("subscription_plan", "free")
    return plan in ("pro", "enterprise") or role == "pro"


# ============================================================
# Plotly layout premium
# ============================================================

_PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e0e0e0", size=13),
    margin=dict(t=20, b=20, l=20, r=20),
    xaxis=dict(gridcolor="rgba(0,255,65,0.03)", zeroline=False),
    yaxis=dict(gridcolor="rgba(0,255,65,0.03)", zeroline=False),
)


# ============================================================
# Render principal
# ============================================================

def render():
    """Senales del dia — pagina principal del producto."""

    # Header premium con indicador de estado
    st.markdown(
        f"<div style='display: flex; align-items: center; gap: 10px; "
        f"margin-bottom: 4px;'>"
        f"<div style='width: 8px; height: 8px; border-radius: 50%; "
        f"background: {ACCENT}; box-shadow: 0 0 10px {ACCENT}60;'></div>"
        f"<h2 style='margin: 0; font-weight: 800; letter-spacing: -0.5px;'>"
        f"<span style='color: {ACCENT}; text-shadow: 0 0 20px rgba(0,255,65,0.2);'>"
        f"Senales</span> del Dia</h2>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        t("pro.signals_subtitle",
          "Tokens con mayor probabilidad de ser gems, detectados por nuestro modelo ML. "
          "Actualizado 2x/dia (06:00 y 18:00 UTC).")
    )

    df = load_todays_signals()

    # --- Limitar senales para usuarios Free ---
    from dashboard.paywall import limit_signals
    role = st.session_state.get("role", "free")
    plan = st.session_state.get("profile", {}).get("subscription_plan", "free")
    if role != "admin":
        df = limit_signals(df, plan=plan)

    # --- Estado vacio: mensaje amigable ---
    if df.empty:
        st.info(
            t("pro.no_signals",
              ":hourglass_flowing_sand: **No hay senales disponibles en este momento.**\n\n"
              "El modelo se ejecuta diariamente a las 07:00 UTC. "
              "Las senales aparecen aqui automaticamente tras cada analisis.")
        )
        return

    # ======================================================
    # 1. KPI CARDS — estilo premium con HTML personalizado
    # ======================================================
    _render_kpis(df)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # ======================================================
    # 2. TABLA PRINCIPAL (con mejoras Pro)
    # ======================================================
    is_pro = _is_pro_or_admin()
    _render_signals_table(df, is_pro=is_pro)

    # --- Exportar CSV (solo Pro/Admin) ---
    if is_pro:
        _render_export_csv(df)
    else:
        st.caption(
            t("pro.export_pro_only",
              "Exportar a CSV disponible con suscripcion Pro.")
        )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # ======================================================
    # 3 y 4. GRAFICOS: distribucion de senales + chains
    # ======================================================
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        _render_signal_distribution(df)

    with col_chart2:
        _render_chain_distribution(df)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # ======================================================
    # 5. DISCLAIMER
    # ======================================================
    _render_disclaimer()


# ============================================================
# Secciones individuales
# ============================================================

def _render_kpis(df: pd.DataFrame):
    """Tarjetas KPI premium en la parte superior."""

    total = len(df)
    strong_count = (df["signal"] == "STRONG").sum() if "signal" in df.columns else 0
    best_score = df["probability"].max() if "probability" in df.columns else 0.0
    chains_activas = df["chain"].nunique() if "chain" in df.columns else 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            kpi_card_html(
                icon="&#128200;",
                label=t("pro.kpi_total", "Total senales"),
                value=str(total),
                color=ACCENT,
            ),
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            kpi_card_html(
                icon="&#9889;",
                label=t("pro.kpi_strong", "Senales STRONG"),
                value=str(strong_count),
                color=ACCENT,
            ),
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            kpi_card_html(
                icon="&#127942;",
                label=t("pro.kpi_best", "Mejor score"),
                value=f"{best_score:.0%}",
                color=GOLD,
            ),
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            kpi_card_html(
                icon="&#128279;",
                label=t("pro.kpi_chains", "Chains activas"),
                value=str(chains_activas),
                color=ACCENT,
            ),
            unsafe_allow_html=True,
        )


def _render_signals_table(df: pd.DataFrame, is_pro: bool = False):
    """Tabla principal de senales del dia, con filtros y cards premium.

    Si is_pro=True, muestra vista enriquecida con indicadores de confianza,
    iconos de chain, tiempo desde descubrimiento y links multiples.
    """

    # Seccion header
    st.markdown(
        f"<h4 style='font-weight: 700; margin-bottom: 4px;'>"
        f"{t('pro.candidates_title', 'Candidatos detectados')}</h4>",
        unsafe_allow_html=True,
    )

    # Filtros rapidos
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        signal_options = ["Todas"] + [s for s in ["STRONG", "MEDIUM", "WEAK"] if s in df["signal"].values]
        selected_signal = st.selectbox(
            t("pro.filter_signal", "Nivel de senal"),
            signal_options,
            help=t("pro.filter_signal_help", "Filtra por nivel de confianza del modelo."),
        )

    with col_f2:
        if "chain" in df.columns:
            chain_options = ["Todas"] + sorted(df["chain"].dropna().unique().tolist())
        else:
            chain_options = ["Todas"]
        selected_chain = st.selectbox(
            "Blockchain",
            chain_options,
            help=t("pro.filter_chain_help", "Filtra por blockchain."),
        )

    # Aplicar filtros
    df_filtered = df.copy()
    if selected_signal != "Todas":
        df_filtered = df_filtered[df_filtered["signal"] == selected_signal]
    if selected_chain != "Todas":
        df_filtered = df_filtered[df_filtered["chain"] == selected_chain]

    if df_filtered.empty:
        st.info(t("pro.no_filtered_signals", "No hay senales con los filtros seleccionados."))
        return

    # Ordenar por probabilidad descendente
    df_filtered = df_filtered.sort_values("probability", ascending=False).reset_index(drop=True)

    if is_pro:
        # --- Vista Pro: trading cards premium ---
        _render_pro_signal_cards(df_filtered)
    else:
        # --- Vista Free: tabla basica ---
        _render_basic_signals_table(df_filtered)

    st.caption(
        t("pro.showing_count", "Mostrando {count} de {total} senales.").format(
            count=len(df_filtered), total=len(df)
        )
    )


def _render_basic_signals_table(df_filtered: pd.DataFrame):
    """Tabla basica de senales para usuarios Free."""
    display_data = []
    for _, row in df_filtered.iterrows():
        name = row.get("name", "")
        symbol = row.get("symbol", "")
        token_label = f"{name} ({symbol})" if name and symbol else (symbol or name or str(row.get("token_id", ""))[:12])

        chain = row.get("chain", "")
        chain_label = _chain_badge(chain)

        probability = row.get("probability", 0.0)
        signal = row.get("signal", "NONE")
        scored_at = row.get("scored_at", None)
        scored_str = _time_since_scored(scored_at)
        market_cap = row.get("market_cap", None)

        # Formatear market cap
        if market_cap and market_cap > 0:
            if market_cap >= 1_000_000:
                mc_str = f"${market_cap / 1_000_000:.1f}M"
            elif market_cap >= 1_000:
                mc_str = f"${market_cap / 1_000:.0f}K"
            else:
                mc_str = f"${market_cap:,.0f}"
        else:
            mc_str = "N/A"

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
            "Market Cap": mc_str,
            "Actualizado": scored_str,
            "DexScreener": link,
        })

    df_display = pd.DataFrame(display_data)

    column_config = {
        "Token": st.column_config.TextColumn(
            "Token",
            help=t("pro.col_token_help", "Nombre y simbolo del token."),
            width="medium",
        ),
        "Chain": st.column_config.TextColumn(
            "Chain",
            help=t("pro.col_chain_help", "Blockchain donde opera el token."),
            width="small",
        ),
        "Score": st.column_config.ProgressColumn(
            "Score",
            help=t("pro.col_score_help", "Probabilidad de ser gem (0% - 100%). Mayor = mejor."),
            format="%.0f%%",
            min_value=0.0,
            max_value=1.0,
        ),
        "Senal": st.column_config.TextColumn(
            t("pro.col_signal", "Senal"),
            help="STRONG (>80%), MEDIUM (>65%), WEAK (>50%).",
            width="small",
        ),
        "Market Cap": st.column_config.TextColumn(
            "Market Cap",
            help="Capitalizacion de mercado del token (ultimo snapshot).",
            width="small",
        ),
        "Actualizado": st.column_config.TextColumn(
            "Actualizado",
            help="Tiempo transcurrido desde que se calculo el score.",
            width="small",
        ),
        "DexScreener": st.column_config.LinkColumn(
            "DexScreener",
            help=t("pro.col_dex_help", "Ver en DexScreener para mas informacion del token."),
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


def _render_pro_signal_cards(df_filtered: pd.DataFrame):
    """Vista Pro: cada senal como trading card premium con indicadores de confianza."""

    for idx, row in df_filtered.iterrows():
        name = row.get("name", "")
        symbol = row.get("symbol", "")

        chain = row.get("chain", "")
        probability = row.get("probability", 0.0)
        signal = row.get("signal", "NONE")
        pool_addr = row.get("pool_address", "")
        first_seen = row.get("first_seen", None)
        scored_at = row.get("scored_at", None)
        market_cap = row.get("market_cap", None)

        # Colores y badges
        conf_badge = _confidence_badge(probability)
        conf_color = _confidence_color(probability)
        signal_color = SIGNAL_COLORS.get(signal, "#374151")
        time_str = _time_since_discovered(first_seen)
        scored_str = _time_since_scored(scored_at)

        # Market cap formateado
        mc_str = ""
        if market_cap and market_cap > 0:
            if market_cap >= 1_000_000:
                mc_str = f"${market_cap / 1_000_000:.1f}M"
            elif market_cap >= 1_000:
                mc_str = f"${market_cap / 1_000:.0f}K"
            else:
                mc_str = f"${market_cap:,.0f}"

        # Links con estilo premium
        dex_link = ""
        gecko_link = ""
        if pool_addr and chain:
            dex_link = _dexscreener_url(chain, pool_addr)
            gecko_link = _geckoterminal_url(chain, pool_addr)

        links_html = ""
        if dex_link:
            links_html += (
                f"<a href='{dex_link}' target='_blank' "
                f"style='color: {TEXT_MUTED}; text-decoration: none; font-size: 0.75rem; "
                f"margin-right: 12px; padding: 3px 10px; "
                f"background: rgba(255,255,255,0.03); border-radius: 6px; "
                f"border: 1px solid rgba(255,255,255,0.05); "
                f"transition: all 0.2s;'>"
                f"DexScreener &nearr;</a>"
            )
        if gecko_link:
            links_html += (
                f"<a href='{gecko_link}' target='_blank' "
                f"style='color: {TEXT_MUTED}; text-decoration: none; font-size: 0.75rem; "
                f"padding: 3px 10px; "
                f"background: rgba(255,255,255,0.03); border-radius: 6px; "
                f"border: 1px solid rgba(255,255,255,0.05); "
                f"transition: all 0.2s;'>"
                f"GeckoTerminal &nearr;</a>"
            )

        # Info secundaria (MC, tiempo, scored)
        meta_parts = []
        if mc_str:
            meta_parts.append(f"MC: {mc_str}")
        if time_str != "N/A":
            meta_parts.append(f"Descubierto: {time_str}")
        if scored_str:
            meta_parts.append(scored_str)
        meta_html = " &middot; ".join(meta_parts)

        # Renderizar trading card premium
        st.markdown(
            signal_card_html(
                symbol=symbol,
                name=name,
                chain=chain,
                signal=signal,
                probability=probability,
                signal_color=signal_color,
                meta_html=meta_html,
                links_html=links_html,
                conf_badge=conf_badge,
                conf_color=conf_color,
                mc_str=mc_str,
            ),
            unsafe_allow_html=True,
        )


def _render_export_csv(df: pd.DataFrame):
    """Boton de exportar senales a CSV (solo Pro/Admin)."""
    # Preparar datos para exportar
    export_data = []
    for _, row in df.iterrows():
        name = row.get("name", "")
        symbol = row.get("symbol", "")
        chain = row.get("chain", "")
        probability = row.get("probability", 0.0)
        signal = row.get("signal", "NONE")
        pool_addr = row.get("pool_address", "")
        token_id = row.get("token_id", "")
        scored_at = row.get("scored_at", "")

        dex_url = ""
        if pool_addr and chain:
            dex_url = _dexscreener_url(chain, pool_addr)

        export_data.append({
            "Token": name,
            "Simbolo": symbol,
            "Chain": chain,
            "Token ID": token_id,
            "Score": f"{probability:.4f}",
            "Senal": signal,
            "Confianza": _confidence_badge(probability),
            "DexScreener": dex_url,
            "Fecha Score": str(scored_at)[:19] if scored_at else "",
        })

    df_export = pd.DataFrame(export_data)
    csv_data = df_export.to_csv(index=False).encode("utf-8")

    st.download_button(
        label=t("pro.export_csv", "Exportar CSV"),
        data=csv_data,
        file_name="senales_memedetector.csv",
        mime="text/csv",
        help=t("pro.export_csv_help",
               "Descarga las senales actuales como archivo CSV."),
    )


def _render_signal_distribution(df: pd.DataFrame):
    """Donut chart premium con distribucion de senales (STRONG/MEDIUM/WEAK)."""

    st.markdown(
        f"<h4 style='font-weight: 700; margin-bottom: 4px;'>"
        f"{t('pro.dist_title', 'Distribucion de senales')}</h4>",
        unsafe_allow_html=True,
    )

    if "signal" not in df.columns:
        st.info(t("pro.no_signal_data", "Sin datos de senales."))
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
        hole=0.55,
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        textfont_size=13,
        marker=dict(line=dict(color='rgba(0,0,0,0.3)', width=1)),
    )
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        showlegend=False,
        height=350,
    )

    st.plotly_chart(fig, use_container_width=True)
    dist_parts = ", ".join(f"{r['Cantidad']} {r['Senal']}" for _, r in signal_counts.iterrows())
    st.caption(f"Distribucion: {dist_parts}")


def _render_chain_distribution(df: pd.DataFrame):
    """Bar chart horizontal premium con distribucion por blockchain."""

    st.markdown(
        f"<h4 style='font-weight: 700; margin-bottom: 4px;'>"
        f"{t('pro.chain_dist_title', 'Senales por blockchain')}</h4>",
        unsafe_allow_html=True,
    )

    if "chain" not in df.columns:
        st.info(t("pro.no_chain_data", "Sin datos de cadena."))
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
        marker_line_width=0,
    )
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        showlegend=False,
        height=350,
        xaxis_title=t("pro.chart_signals_count", "Numero de senales"),
        yaxis_title="",
    )

    st.plotly_chart(fig, use_container_width=True)
    chain_parts = ", ".join(f"{r['Chain_label']}: {r['Cantidad']}" for _, r in chain_counts.iterrows())
    st.caption(f"Senales por chain: {chain_parts}")


def _render_disclaimer():
    """Disclaimer legal al pie de la pagina con estilo premium."""

    st.markdown(
        f"<div style='"
        f"background: linear-gradient(135deg, rgba(239,68,68,0.04), rgba(239,68,68,0.02)); "
        f"border: 1px solid rgba(239,68,68,0.12); "
        f"border-left: 3px solid rgba(239,68,68,0.4); "
        f"border-radius: 12px; padding: 16px 20px; margin-top: 8px;'>"
        f"<strong style='color: #ef4444; font-size: 0.85rem;'>"
        f"&#9888; Esto NO es consejo financiero.</strong>"
        f"<p style='color: {TEXT_MUTED}; font-size: 0.8rem; margin: 8px 0 0 0; line-height: 1.5;'>"
        f"{t('pro.disclaimer_text', 'Los memecoins son extremadamente volatiles y la gran mayoria pierde todo su valor. Las senales de este modelo son herramientas de analisis, no recomendaciones de inversion. Haz tu propia investigacion (DYOR) y nunca inviertas mas de lo que puedas permitirte perder.')}"
        f"</p></div>",
        unsafe_allow_html=True,
    )
