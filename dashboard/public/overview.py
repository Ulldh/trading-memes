"""
overview.py - Pagina de resumen general del dataset.

Muestra estadisticas clave del proyecto estilo trading terminal premium:
- Hero section con bienvenida personalizada, glow y KPI cards custom
- Market Pulse: resumen del dia con top senales como trading cards
- Distribucion de tokens por cadena y labels (graficos)
- Tokens descubiertos por semana
- Frescura de los datos (ultima actualizacion)
"""
import logging
from html import escape
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from src.data.supabase_storage import get_storage as _get_storage
from dashboard.constants import LABEL_COLORS, CHAIN_COLORS, SIGNAL_COLORS
from dashboard.theme import (
    signal_badge_html, chain_badge_html, card_container,
    kpi_card_html, blurred_signal_card_html,
    ACCENT, ACCENT_DIM, GOLD, BG_CARD, BG_SURFACE,
    BORDER, TEXT_MUTED, DANGER,
)

logger = logging.getLogger(__name__)


@st.cache_resource
def get_storage():
    """Crea una instancia de Storage cacheada para no reconectar cada vez."""
    return _get_storage()


# ======================================================================
# Plotly layout base — fondo transparente, estilo coherente premium
# ======================================================================

_PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e0e0e0", size=13),
    margin=dict(l=40, r=40, t=40, b=40),
    xaxis=dict(gridcolor="rgba(0,255,65,0.03)", zeroline=False),
    yaxis=dict(gridcolor="rgba(0,255,65,0.03)", zeroline=False),
)


def render():
    """Renderiza la pagina de Trading Dashboard — estilo premium."""

    # --- Welcome experience para nuevos usuarios Free ---
    _render_welcome_message()

    storage = get_storage()

    # ------------------------------------------------------------------
    # 0. Hero Section — saludo personalizado + KPIs premium
    # ------------------------------------------------------------------
    _render_hero_section(storage)

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 1. Market Pulse — resumen del dia (visible para todos)
    # ------------------------------------------------------------------
    _render_market_pulse(storage)

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 2. Graficos: cadenas + labels lado a lado
    # ------------------------------------------------------------------
    col_chart_l, col_chart_r = st.columns(2)

    with col_chart_l:
        _render_chain_distribution(storage)

    with col_chart_r:
        _render_label_distribution(storage)

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 3. Tokens descubiertos por semana (bar chart)
    # ------------------------------------------------------------------
    _render_weekly_discoveries(storage)

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 4. Frescura de los datos
    # ------------------------------------------------------------------
    _render_data_freshness(storage)


# ======================================================================
# Hero Section — saludo con glow y KPI cards premium
# ======================================================================

def _render_hero_section(storage):
    """Bloque hero con saludo personalizado, plan badge y KPIs como cards HTML."""

    # Obtener datos del usuario
    user_email = st.session_state.get("user", {}).get("email", "")
    profile = st.session_state.get("profile", {}) or {}
    display_name = profile.get("display_name", "")
    user_name = escape(display_name or (user_email.split("@")[0] if user_email else "trader"))
    role = st.session_state.get("role", "free")

    # Badge de plan
    role_config = {
        "admin": {"color": "#ef4444", "label": "ADMIN", "bg": "rgba(239,68,68,0.08)"},
        "pro": {"color": "#00ff41", "label": "PRO", "bg": "rgba(0,255,65,0.08)"},
        "free": {"color": "#6b7280", "label": "FREE", "bg": "rgba(107,114,128,0.08)"},
    }
    rc = role_config.get(role, role_config["free"])

    # Saludo personalizado con glow effect
    st.markdown(
        f"<div style='margin-bottom: 24px;'>"
        f"<h1 style='margin: 0 0 8px 0; font-size: 2rem; font-weight: 800; "
        f"letter-spacing: -0.5px;'>"
        f"Bienvenido, "
        f"<span style='color: {ACCENT}; text-shadow: 0 0 30px rgba(0,255,65,0.3);'>"
        f"{user_name}</span></h1>"
        f"<span style='background: {rc['bg']}; color: {rc['color']}; "
        f"padding: 4px 16px; border-radius: 20px; font-size: 0.7rem; "
        f"font-weight: 800; border: 1px solid {rc['color']}25; "
        f"letter-spacing: 1.5px; text-transform: uppercase;'>{rc['label']}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Cargar metricas
    try:
        stats = storage.stats()
    except Exception:
        logger.exception("Error al conectar con la base de datos en overview")
        st.error("Se produjo un error inesperado. Intentalo de nuevo.")
        return

    # Senales activas por tipo
    try:
        df_signals = storage.get_scores(min_probability=0.0, scored_today=True)
        if df_signals.empty:
            df_signals = storage.get_scores(min_probability=0.0)
            if not df_signals.empty:
                df_signals = df_signals.head(200)
    except Exception:
        df_signals = pd.DataFrame()

    strong_count = int((df_signals["signal"] == "STRONG").sum()) if not df_signals.empty and "signal" in df_signals.columns else 0
    medium_count = int((df_signals["signal"] == "MEDIUM").sum()) if not df_signals.empty and "signal" in df_signals.columns else 0

    # Tokens nuevos hoy
    try:
        df_new_today = storage.query(
            "SELECT COUNT(*) as n FROM tokens "
            "WHERE first_seen >= CURRENT_DATE - INTERVAL '1 day'"
        )
        new_today = int(df_new_today["n"].iloc[0]) if not df_new_today.empty else 0
    except Exception:
        new_today = 0

    try:
        df_new_week = storage.query(
            "SELECT COUNT(*) as n FROM tokens "
            "WHERE first_seen >= CURRENT_DATE - INTERVAL '7 days'"
        )
        new_week = int(df_new_week["n"].iloc[0]) if not df_new_week.empty else 0
    except Exception:
        new_week = 0

    # Gems encontrados total
    try:
        df_gems = storage.query(
            "SELECT COUNT(*) as n FROM labels WHERE label_binary = 1"
        )
        gems_total = int(df_gems["n"].iloc[0]) if not df_gems.empty else 0
    except Exception:
        gems_total = 0

    # Resumen rapido de senales
    if strong_count > 0:
        st.markdown(
            f"<div style='background: rgba(0,255,65,0.04); "
            f"border: 1px solid rgba(0,255,65,0.1); border-radius: 12px; "
            f"padding: 12px 20px; margin-bottom: 20px; "
            f"display: inline-block;'>"
            f"<span style='color: {ACCENT}; font-weight: 700; "
            f"text-shadow: 0 0 15px rgba(0,255,65,0.3);'>"
            f"{strong_count} senales STRONG</span>"
            f"<span style='color: {TEXT_MUTED};'> activas hoy</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # --- KPIs principales como cards HTML premium ---
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            kpi_card_html(
                icon="&#128202;",
                label="Tokens monitoreados",
                value=f"{stats.get('tokens', 0):,}",
                subtitle="En seguimiento diario",
                color=ACCENT,
            ),
            unsafe_allow_html=True,
        )

    with col2:
        subtitle_strong = f"+{medium_count} MEDIUM" if medium_count > 0 else "Senales de alta confianza"
        st.markdown(
            kpi_card_html(
                icon="&#9889;",
                label="Senales STRONG",
                value=str(strong_count),
                subtitle=subtitle_strong,
                color=ACCENT,
            ),
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            kpi_card_html(
                icon="&#128640;",
                label="Nuevos esta semana",
                value=f"{new_week:,}",
                subtitle=f"+{new_today} hoy",
                color=GOLD,
            ),
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            kpi_card_html(
                icon="&#128142;",
                label="Gems encontrados",
                value=f"{gems_total:,}",
                subtitle="Tokens 10x+ confirmados",
                color=ACCENT,
            ),
            unsafe_allow_html=True,
        )

    # Datos tecnicos en expander (para quien quiera verlos)
    with st.expander("Ver estadisticas tecnicas de la base de datos"):
        st.caption("Metricas internas del pipeline de datos.")
        tcol1, tcol2, tcol3, tcol4 = st.columns(4)
        tcol1.metric("Snapshots", f"{stats.get('pool_snapshots', 0):,}",
                     help="Fotos del estado de cada token (precio, volumen, liquidez).")
        tcol2.metric("Registros OHLCV", f"{stats.get('ohlcv', 0):,}",
                     help="Velas de precio historicas.")
        tcol3.metric("Features calculados", f"{stats.get('features', 0):,}",
                     help="Tokens con features ML calculadas.")
        tcol4.metric("Labels asignados", f"{stats.get('labels', 0):,}",
                     help="Tokens clasificados en el seed dataset.")


# ======================================================================
# Welcome message para nuevos usuarios Free
# ======================================================================

def _render_welcome_message():
    """Muestra un mensaje de bienvenida la primera vez que un usuario Free visita el dashboard.

    Usa session_state para mostrarlo solo una vez por sesion.
    Solo se muestra a usuarios Free (no Pro ni Admin).
    Estilo premium coherente con la paleta terminal.
    """
    # No mostrar si ya fue visto en esta sesion
    if st.session_state.get("welcome_shown", False):
        return

    # Solo para usuarios Free
    role = st.session_state.get("role", "free")
    plan = st.session_state.get("profile", {}).get("subscription_plan", "free")
    if role == "admin" or plan in ("pro", "enterprise"):
        return

    # Obtener nombre del usuario para personalizar
    user_email = st.session_state.get("user", {}).get("email", "")
    user_name = escape(user_email.split("@")[0]) if user_email else "trader"

    # Mostrar el mensaje de bienvenida con estilo premium
    with st.container():
        st.markdown(
            f"""
            <div style="padding: 28px; border-radius: 16px;
                        border: 1px solid rgba(0, 255, 65, 0.12);
                        background: linear-gradient(135deg, rgba(13,17,23,0.95), rgba(22,27,34,0.95));
                        backdrop-filter: blur(10px);
                        margin-bottom: 16px;
                        box-shadow: 0 4px 30px rgba(0,0,0,0.2);">
                <h3 style="margin-top: 0; color: #ffffff; font-weight: 800;">
                    Bienvenido a <span style="color: #00ff41; text-shadow: 0 0 20px rgba(0,255,65,0.3);">Meme Detector</span>, {user_name}!
                </h3>
                <p style="color: #9ca3af;">Tu cuenta <strong style="color: #6b7280; letter-spacing: 1px;">FREE</strong> incluye:</p>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 12px 0;">
                    <div style="background: rgba(0,255,65,0.03); padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(0,255,65,0.06);">
                        <span style="color: #00ff41;">&#10003;</span> <strong>Overview</strong> <span style="color: #6b7280;">— Market Pulse</span>
                    </div>
                    <div style="background: rgba(0,255,65,0.03); padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(0,255,65,0.06);">
                        <span style="color: #00ff41;">&#10003;</span> <strong>3 senales diarias</strong> <span style="color: #6b7280;">— Top tokens</span>
                    </div>
                    <div style="background: rgba(0,255,65,0.03); padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(0,255,65,0.06);">
                        <span style="color: #00ff41;">&#10003;</span> <strong>Track Record</strong> <span style="color: #6b7280;">— Historial</span>
                    </div>
                    <div style="background: rgba(0,255,65,0.03); padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(0,255,65,0.06);">
                        <span style="color: #00ff41;">&#10003;</span> <strong>Watchlist</strong> <span style="color: #6b7280;">— 3 tokens</span>
                    </div>
                </div>
                <p style="color: #9ca3af; margin-top: 16px; margin-bottom: 8px;">
                    Con <strong style="color: #00ff41; text-shadow: 0 0 10px rgba(0,255,65,0.2);">Pro ($29/mes)</strong> desbloqueas:
                </p>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                    <div style="background: rgba(251,191,36,0.03); padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(251,191,36,0.08);">
                        <span style="color: #fbbf24;">&#128273;</span> Todas las senales diarias
                    </div>
                    <div style="background: rgba(251,191,36,0.03); padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(251,191,36,0.08);">
                        <span style="color: #fbbf24;">&#128273;</span> Busqueda de tokens ilimitada
                    </div>
                    <div style="background: rgba(251,191,36,0.03); padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(251,191,36,0.08);">
                        <span style="color: #fbbf24;">&#128273;</span> Academia Pro
                    </div>
                    <div style="background: rgba(251,191,36,0.03); padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(251,191,36,0.08);">
                        <span style="color: #fbbf24;">&#128273;</span> Alertas Telegram
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Boton para cerrar el mensaje de bienvenida
    if st.button("Entendido, empezar a explorar", type="primary", key="dismiss_welcome"):
        st.session_state.welcome_shown = True
        st.rerun()

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)


# ======================================================================
# Market Pulse — widget de resumen diario con top senales premium
# ======================================================================

@st.cache_data(ttl=300)
def _load_market_pulse_data():
    """Carga datos para el widget Market Pulse: tokens de hoy, nuevos, top senales."""
    storage = get_storage()

    # Total de tokens rastreados
    try:
        df_total = storage.query("SELECT COUNT(*) as total FROM tokens")
        total_tokens = int(df_total["total"].iloc[0]) if not df_total.empty else 0
    except Exception:
        total_tokens = 0

    # Tokens descubiertos en las ultimas 24h
    try:
        df_new = storage.query(
            "SELECT COUNT(*) as nuevos FROM tokens "
            "WHERE first_seen >= CURRENT_DATE - INTERVAL '1 day'"
        )
        new_tokens_24h = int(df_new["nuevos"].iloc[0]) if not df_new.empty else 0
    except Exception:
        new_tokens_24h = 0

    # Top senales del dia (sin limite, necesitamos el total y top 3)
    try:
        df_signals = storage.get_scores(min_probability=0.0, scored_today=True)
        if df_signals.empty:
            # Fallback: traer las mas recientes
            df_signals = storage.get_scores(min_probability=0.0)
            if not df_signals.empty:
                df_signals = df_signals.head(200)
    except Exception:
        df_signals = pd.DataFrame()

    return total_tokens, new_tokens_24h, df_signals


def _render_market_pulse(storage):
    """Renderiza el widget Market Pulse en la parte superior del overview.

    Muestra KPIs del dia y las top 3 senales como cards premium.
    """
    # Header con estilo terminal
    st.markdown(
        f"<div style='display: flex; align-items: center; gap: 10px; "
        f"margin-bottom: 4px;'>"
        f"<div style='width: 8px; height: 8px; border-radius: 50%; "
        f"background: {ACCENT}; box-shadow: 0 0 10px {ACCENT}60;'></div>"
        f"<h3 style='margin: 0; font-weight: 800; letter-spacing: -0.3px;'>"
        f"Market Pulse</h3>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Resumen rapido del estado del mercado hoy. "
        "Datos actualizados 2x/dia (06:00 y 18:00 UTC)."
    )

    total_tokens, new_tokens_24h, df_signals = _load_market_pulse_data()

    total_signals = len(df_signals) if not df_signals.empty else 0

    # --- KPI cards del Market Pulse ---
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            kpi_card_html(
                icon="&#127760;",
                label="Tokens rastreados",
                value=f"{total_tokens:,}",
                color=ACCENT,
            ),
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            kpi_card_html(
                icon="&#10024;",
                label="Nuevos (24h)",
                value=f"{new_tokens_24h:,}",
                color=GOLD,
            ),
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            kpi_card_html(
                icon="&#128200;",
                label="Senales activas",
                value=f"{total_signals:,}",
                color=ACCENT,
            ),
            unsafe_allow_html=True,
        )

    # --- Top 3 senales del dia como trading cards ---
    if not df_signals.empty and total_signals > 0:
        st.markdown(
            f"<div style='margin: 20px 0 12px 0;'>"
            f"<h4 style='margin: 0; font-weight: 700; color: #ffffff;'>"
            f"Top senales del dia</h4>"
            f"</div>",
            unsafe_allow_html=True,
        )

        role = st.session_state.get("role", "free")
        plan = st.session_state.get("profile", {}).get("subscription_plan", "free")
        is_premium = (role == "admin" or plan in ("pro", "enterprise"))

        # Ordenar por probabilidad y tomar top 3
        df_top3 = df_signals.sort_values("probability", ascending=False).head(3)

        cols = st.columns(3)
        for i, (_, row) in enumerate(df_top3.iterrows()):
            signal = row.get("signal", "NONE")
            signal_color = SIGNAL_COLORS.get(signal, "#374151")
            probability = row.get("probability", 0.0)
            score_pct = int(probability * 100)

            with cols[i]:
                if is_premium:
                    # Pro/Admin ve todo — card premium
                    symbol = row.get("symbol", "???")
                    chain = row.get("chain", "")

                    # Links
                    pool_addr = row.get("pool_address", "")
                    dex_link = ""
                    if pool_addr and chain:
                        chain_slug = {"solana": "solana", "ethereum": "ethereum", "base": "base"}.get(chain, chain)
                        dex_link = f"https://dexscreener.com/{chain_slug}/{pool_addr}"

                    link_html = ""
                    if dex_link:
                        link_html = (
                            f"<a href='{dex_link}' target='_blank' "
                            f"style='color: {TEXT_MUTED}; text-decoration: none; "
                            f"font-size: 0.7rem; transition: color 0.2s;'>"
                            f"DexScreener &nearr;</a>"
                        )

                    # Glow para STRONG
                    glow = f"box-shadow: 0 0 25px {signal_color}12, 0 4px 24px rgba(0,0,0,0.2);" if signal == "STRONG" else "box-shadow: 0 4px 24px rgba(0,0,0,0.15);"

                    st.markdown(
                        f"<div aria-label='{symbol}: senal {signal}, {probability:.0%}' "
                        f"style='background: linear-gradient(135deg, rgba(13,17,23,0.95), rgba(22,27,34,0.95)); "
                        f"border: 1px solid rgba(0,255,65,0.06); "
                        f"border-left: 3px solid {signal_color}; "
                        f"padding: 18px 20px; border-radius: 16px; "
                        f"backdrop-filter: blur(10px); {glow}'>"
                        # Nombre + badges
                        f"<div style='display: flex; justify-content: space-between; "
                        f"align-items: center; margin-bottom: 10px;'>"
                        f"<strong style='font-size: 1.1rem; color: #ffffff; "
                        f"font-weight: 800;'>{symbol}</strong>"
                        f"{chain_badge_html(chain)}"
                        f"</div>"
                        # Signal badge + score
                        f"<div style='display: flex; align-items: center; gap: 8px; "
                        f"margin-bottom: 10px;'>"
                        f"{signal_badge_html(signal)}"
                        f"<span style='color: {signal_color}; font-weight: 800; "
                        f"font-size: 1.1rem; text-shadow: 0 0 15px {signal_color}30;'>"
                        f"{probability:.0%}</span>"
                        f"</div>"
                        # Score bar
                        f"<div style='background: {BG_SURFACE}; border-radius: 8px; "
                        f"height: 5px; overflow: hidden; margin-bottom: 8px;'>"
                        f"<div style='width: {score_pct}%; height: 100%; border-radius: 8px; "
                        f"background: linear-gradient(90deg, {signal_color}cc, {signal_color}); "
                        f"box-shadow: 0 0 8px {signal_color}40;'></div>"
                        f"</div>"
                        # Link
                        f"<div style='text-align: right;'>{link_html}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    # Free: tarjeta borrosa
                    st.markdown(
                        blurred_signal_card_html(signal, signal_color),
                        unsafe_allow_html=True,
                    )

        # CTA para Free users
        if not is_premium:
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            if total_signals > 3:
                st.info(
                    f":lock: Hay **{total_signals} senales** disponibles hoy. "
                    f"Actualiza a **Pro** para ver todas las senales con datos completos."
                )
            # Boton de upgrade usando el paywall existente
            try:
                from dashboard.paywall import _get_checkout_url
                checkout_url = _get_checkout_url("pro")
                if checkout_url:
                    st.link_button(":rocket: Actualizar a Pro", checkout_url, type="primary")
                else:
                    st.markdown(
                        ":rocket: **[Ver planes y precios](/pricing)**"
                    )
            except ImportError:
                st.markdown(
                    ":rocket: **[Ver planes y precios](/pricing)**"
                )


# ======================================================================
# Distribucion de tokens por cadena
# ======================================================================

def _render_chain_distribution(storage):
    """Donut chart de tokens por blockchain con estilo premium."""
    st.markdown(
        f"<h4 style='font-weight: 700; margin-bottom: 4px;'>Tokens por cadena</h4>",
        unsafe_allow_html=True,
    )

    st.caption(
        "Distribucion de memecoins por blockchain. "
        "Solana es la mas popular por sus transacciones rapidas y baratas."
    )

    try:
        df_tokens = storage.query("SELECT chain, COUNT(*) as count FROM tokens GROUP BY chain")
    except Exception:
        df_tokens = pd.DataFrame()

    if df_tokens.empty:
        st.info("No hay tokens en la base de datos todavia.")
        return

    fig_chain = px.pie(
        df_tokens,
        names="chain",
        values="count",
        color="chain",
        color_discrete_map=CHAIN_COLORS,
        hole=0.55,
    )
    fig_chain.update_traces(
        textposition="inside", textinfo="percent+label",
        textfont_size=13,
        marker=dict(line=dict(color='rgba(0,0,0,0.3)', width=1)),
    )
    fig_chain.update_layout(
        **_PLOTLY_LAYOUT,
        showlegend=False,
        height=350,
    )
    st.plotly_chart(fig_chain, use_container_width=True)
    chain_summary = ", ".join(f"{r['chain']}: {r['count']:,}" for _, r in df_tokens.iterrows())
    st.caption(f"Distribucion: {chain_summary}")


# ======================================================================
# Distribucion de labels
# ======================================================================

def _render_label_distribution(storage):
    """Donut chart de clasificaciones con estilo premium."""
    st.markdown(
        f"<h4 style='font-weight: 700; margin-bottom: 4px;'>Clasificaciones</h4>",
        unsafe_allow_html=True,
    )

    st.caption(
        "Rendimiento historico de tokens conocidos: "
        "Gem (10x+), Moderate success (3-10x), Failure (<-90%)."
    )

    try:
        df_labels = storage.query(
            "SELECT label_multi, COUNT(*) as count FROM labels GROUP BY label_multi"
        )
    except Exception:
        df_labels = pd.DataFrame()

    if df_labels.empty:
        st.info("No hay labels asignados todavia.")
        return

    fig_labels = px.pie(
        df_labels,
        names="label_multi",
        values="count",
        color="label_multi",
        color_discrete_map=LABEL_COLORS,
        hole=0.55,
    )
    fig_labels.update_traces(
        textposition="inside", textinfo="percent+label",
        textfont_size=13,
        marker=dict(line=dict(color='rgba(0,0,0,0.3)', width=1)),
    )
    fig_labels.update_layout(
        **_PLOTLY_LAYOUT,
        showlegend=False,
        height=350,
    )
    st.plotly_chart(fig_labels, use_container_width=True)
    label_summary = ", ".join(f"{r['label_multi']}: {r['count']:,}" for _, r in df_labels.iterrows())
    st.caption(f"Clasificaciones: {label_summary}")


# ======================================================================
# Tokens descubiertos por semana
# ======================================================================

def _render_weekly_discoveries(storage):
    """Bar chart de tokens descubiertos por semana con estilo premium."""
    st.markdown(
        f"<h4 style='font-weight: 700; margin-bottom: 4px;'>Tokens descubiertos por semana</h4>",
        unsafe_allow_html=True,
    )

    st.caption(
        "Muestra cuando anadimos cada token a nuestra base de datos. "
        "A medida que recopilemos datos diariamente, este grafico crecera."
    )

    try:
        df_first_seen = storage.query("SELECT first_seen FROM tokens WHERE first_seen IS NOT NULL")
    except Exception:
        df_first_seen = pd.DataFrame()

    if df_first_seen.empty:
        st.info("No hay datos de fecha de descubrimiento.")
        return

    df_first_seen["first_seen"] = pd.to_datetime(df_first_seen["first_seen"], errors="coerce")
    df_first_seen = df_first_seen.dropna(subset=["first_seen"])

    if df_first_seen.empty:
        return

    df_first_seen["week"] = df_first_seen["first_seen"].dt.to_period("W").apply(
        lambda r: r.start_time
    )
    df_weekly = df_first_seen.groupby("week").size().reset_index(name="tokens_nuevos")
    df_weekly = df_weekly.sort_values("week")

    fig_weekly = go.Figure()
    fig_weekly.add_trace(
        go.Bar(
            x=df_weekly["week"],
            y=df_weekly["tokens_nuevos"],
            marker_color=ACCENT,
            marker_line_width=0,
            opacity=0.9,
            text=df_weekly["tokens_nuevos"],
            textposition="outside",
            textfont=dict(color=TEXT_MUTED, size=11),
        )
    )
    fig_weekly.update_layout(
        **_PLOTLY_LAYOUT,
        xaxis_title="Semana",
        yaxis_title="Tokens nuevos",
        height=380,
    )
    st.plotly_chart(fig_weekly, use_container_width=True)
    total_nuevos = df_weekly["tokens_nuevos"].sum()
    st.caption(f"Total: {total_nuevos:,} tokens en {len(df_weekly)} semanas")


# ======================================================================
# Frescura de los datos
# ======================================================================

def _render_data_freshness(storage):
    """Muestra timestamps de la ultima actualizacion de datos con estilo premium."""
    st.markdown(
        f"<h4 style='font-weight: 700; margin-bottom: 4px;'>Frescura de los datos</h4>",
        unsafe_allow_html=True,
    )

    st.caption(
        "Indica cuando fue la ultima vez que recopilamos datos. "
        "El pipeline se ejecuta automaticamente 2x/dia."
    )

    col_fresh1, col_fresh2 = st.columns(2)

    try:
        df_last_snap = storage.query("SELECT MAX(snapshot_time) as last_time FROM pool_snapshots")
        last_snap = df_last_snap["last_time"].iloc[0] if not df_last_snap.empty else None
    except Exception:
        last_snap = None

    with col_fresh1:
        if last_snap:
            snap_str = str(last_snap)[:19]
            st.markdown(
                f"<div style='"
                f"background: linear-gradient(135deg, rgba(13,17,23,0.95), rgba(22,27,34,0.95)); "
                f"border: 1px solid rgba(0,255,65,0.06); border-radius: 16px; "
                f"padding: 20px 24px;'>"
                f"<div style='color: {TEXT_MUTED}; font-size: 0.7rem; "
                f"text-transform: uppercase; letter-spacing: 1px; "
                f"margin-bottom: 8px; font-weight: 600;'>Ultimo pool snapshot</div>"
                f"<div style='color: #ffffff; font-size: 1.1rem; font-weight: 700; "
                f"font-family: monospace; letter-spacing: 0.5px;'>{snap_str}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("No hay snapshots todavia.")

    try:
        df_last_ohlcv = storage.query("SELECT MAX(timestamp) as last_time FROM ohlcv")
        last_ohlcv = df_last_ohlcv["last_time"].iloc[0] if not df_last_ohlcv.empty else None
    except Exception:
        last_ohlcv = None

    with col_fresh2:
        if last_ohlcv:
            ohlcv_str = str(last_ohlcv)[:19]
            st.markdown(
                f"<div style='"
                f"background: linear-gradient(135deg, rgba(13,17,23,0.95), rgba(22,27,34,0.95)); "
                f"border: 1px solid rgba(0,255,65,0.06); border-radius: 16px; "
                f"padding: 20px 24px;'>"
                f"<div style='color: {TEXT_MUTED}; font-size: 0.7rem; "
                f"text-transform: uppercase; letter-spacing: 1px; "
                f"margin-bottom: 8px; font-weight: 600;'>Ultimo registro OHLCV</div>"
                f"<div style='color: #ffffff; font-size: 1.1rem; font-weight: 700; "
                f"font-family: monospace; letter-spacing: 0.5px;'>{ohlcv_str}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("No hay datos OHLCV todavia.")
