"""
overview.py - Pagina de resumen general del dataset.

Muestra estadisticas clave del proyecto:
- Hero section con bienvenida personalizada y metricas clave
- Market Pulse: resumen del dia para todos los usuarios
- Top senales del dia con cards estilizadas
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
    ACCENT, ACCENT_DIM, GOLD, BG_CARD, BORDER, TEXT_MUTED,
)

logger = logging.getLogger(__name__)


@st.cache_resource
def get_storage():
    """Crea una instancia de Storage cacheada para no reconectar cada vez."""
    return _get_storage()


# ======================================================================
# Plotly layout base — fondo transparente, estilo coherente
# ======================================================================

_PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e0e0e0"),
    margin=dict(l=40, r=40, t=40, b=40),
)


def render():
    """Renderiza la pagina de Trading Dashboard."""

    # --- Welcome experience para nuevos usuarios Free ---
    _render_welcome_message()

    storage = get_storage()

    # ------------------------------------------------------------------
    # 0. Hero Section — saludo personalizado + KPIs compactos
    # ------------------------------------------------------------------
    _render_hero_section(storage)

    st.divider()

    # ------------------------------------------------------------------
    # 1. Market Pulse — resumen del dia (visible para todos)
    # ------------------------------------------------------------------
    _render_market_pulse(storage)

    st.divider()

    # ------------------------------------------------------------------
    # 2. Graficos: cadenas + labels lado a lado
    # ------------------------------------------------------------------
    col_chart_l, col_chart_r = st.columns(2)

    with col_chart_l:
        _render_chain_distribution(storage)

    with col_chart_r:
        _render_label_distribution(storage)

    st.divider()

    # ------------------------------------------------------------------
    # 3. Tokens descubiertos por semana (bar chart)
    # ------------------------------------------------------------------
    _render_weekly_discoveries(storage)

    st.divider()

    # ------------------------------------------------------------------
    # 4. Frescura de los datos
    # ------------------------------------------------------------------
    _render_data_freshness(storage)


# ======================================================================
# Hero Section — saludo y metricas principales
# ======================================================================

def _render_hero_section(storage):
    """Bloque hero con saludo personalizado, plan badge y KPIs principales."""

    # Obtener datos del usuario
    user_email = st.session_state.get("user", {}).get("email", "")
    profile = st.session_state.get("profile", {}) or {}
    display_name = profile.get("display_name", "")
    user_name = escape(display_name or (user_email.split("@")[0] if user_email else "trader"))
    role = st.session_state.get("role", "free")

    # Badge de plan
    role_config = {
        "admin": {"color": "#ef4444", "label": "Admin"},
        "pro": {"color": "#00ff41", "label": "Pro"},
        "free": {"color": "#6b7280", "label": "Free"},
    }
    rc = role_config.get(role, role_config["free"])

    # Saludo personalizado con badge
    st.markdown(
        f"<div style='margin-bottom: 20px;'>"
        f"<h2 style='margin: 0 0 4px 0;'>Bienvenido, "
        f"<span style='color: {ACCENT};'>{user_name}</span></h2>"
        f"<span style='background: {rc['color']}15; color: {rc['color']}; "
        f"padding: 3px 12px; border-radius: 6px; font-size: 0.75rem; "
        f"font-weight: 700; border: 1px solid {rc['color']}30; "
        f"letter-spacing: 0.5px;'>{rc['label']}</span>"
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

    # --- KPIs principales en 4 columnas ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Tokens monitoreados",
        f"{stats.get('tokens', 0):,}",
        help="Memecoins activos en seguimiento diario.",
    )
    col2.metric(
        "Senales STRONG",
        f"{strong_count}",
        delta=f"{medium_count} MEDIUM" if medium_count > 0 else None,
        help="Senales de alta confianza generadas por el modelo hoy.",
    )
    col3.metric(
        "Nuevos esta semana",
        f"{new_week:,}",
        delta=f"+{new_today} hoy",
        help="Tokens descubiertos en los ultimos 7 dias.",
    )
    col4.metric(
        "Gems encontrados",
        f"{gems_total:,}",
        help="Tokens confirmados como gems (10x+) en datos historicos.",
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
            <div style="padding: 24px; border-radius: 12px;
                        border: 1px solid rgba(0, 255, 65, 0.2);
                        background: linear-gradient(135deg, rgba(0, 255, 65, 0.03), rgba(0, 82, 255, 0.03));
                        margin-bottom: 16px;">
                <h3 style="margin-top: 0; color: #e0e0e0;">
                    Bienvenido a <span style="color: #00ff41;">Meme Detector</span>, {user_name}!
                </h3>
                <p style="color: #9ca3af;">Tu cuenta <strong style="color: #6b7280;">Free</strong> incluye:</p>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 12px 0;">
                    <div style="background: rgba(255,255,255,0.02); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                        <span style="color: #00ff41;">&#10003;</span> <strong>Overview</strong> <span style="color: #6b7280;">— Market Pulse</span>
                    </div>
                    <div style="background: rgba(255,255,255,0.02); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                        <span style="color: #00ff41;">&#10003;</span> <strong>3 senales diarias</strong> <span style="color: #6b7280;">— Top tokens</span>
                    </div>
                    <div style="background: rgba(255,255,255,0.02); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                        <span style="color: #00ff41;">&#10003;</span> <strong>Track Record</strong> <span style="color: #6b7280;">— Historial</span>
                    </div>
                    <div style="background: rgba(255,255,255,0.02); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                        <span style="color: #00ff41;">&#10003;</span> <strong>Watchlist</strong> <span style="color: #6b7280;">— 3 tokens</span>
                    </div>
                </div>
                <p style="color: #9ca3af; margin-top: 16px; margin-bottom: 8px;">
                    Con <strong style="color: #00ff41;">Pro ($29/mes)</strong> desbloqueas:
                </p>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                    <div style="background: rgba(255,255,255,0.02); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                        <span style="color: #fbbf24;">&#128273;</span> Todas las senales diarias
                    </div>
                    <div style="background: rgba(255,255,255,0.02); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                        <span style="color: #fbbf24;">&#128273;</span> Busqueda de tokens ilimitada
                    </div>
                    <div style="background: rgba(255,255,255,0.02); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                        <span style="color: #fbbf24;">&#128273;</span> Academia Pro
                    </div>
                    <div style="background: rgba(255,255,255,0.02); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
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

    st.divider()


# ======================================================================
# Market Pulse — widget de resumen diario con top senales estilizadas
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

    Muestra KPIs del dia y las top 3 senales como cards con estilo premium.
    """
    st.markdown(
        f"<h3 style='margin-bottom: 4px;'>"
        f"<span style='color: {ACCENT};'>:</span> Market Pulse</h3>",
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

    col1.metric(
        "Tokens rastreados",
        f"{total_tokens:,}",
        help="Numero total de memecoins en nuestra base de datos.",
    )
    col2.metric(
        "Nuevos (24h)",
        f"{new_tokens_24h:,}",
        help="Tokens descubiertos en las ultimas 24 horas.",
    )
    col3.metric(
        "Senales activas",
        f"{total_signals:,}",
        help="Total de senales generadas por el modelo hoy.",
    )

    # --- Top 3 senales del dia como cards estilizadas ---
    if not df_signals.empty and total_signals > 0:
        st.markdown("")
        st.markdown(
            f"<p style='font-weight: 600; font-size: 0.95rem; margin-bottom: 8px;'>"
            f"Top senales del dia</p>",
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
            # Glow solo para STRONG
            glow = f"box-shadow: 0 0 20px {signal_color}25;" if signal == "STRONG" else ""

            with cols[i]:
                if is_premium:
                    # Pro/Admin ve todo
                    symbol = row.get("symbol", "???")
                    prob = row.get("probability", 0.0)
                    chain = row.get("chain", "")
                    chain_html = chain_badge_html(chain) if chain else ""

                    st.markdown(
                        f"<div aria-label='{symbol}: senal {signal}, {prob:.0%}' "
                        f"style='background: {BG_CARD}; "
                        f"border: 1px solid {signal_color}30; "
                        f"border-left: 3px solid {signal_color}; "
                        f"padding: 14px 16px; border-radius: 10px; {glow}'>"
                        f"<div style='display: flex; justify-content: space-between; "
                        f"align-items: center; margin-bottom: 8px;'>"
                        f"<strong style='font-size: 1.05rem;'>{symbol}</strong>"
                        f"{chain_html}"
                        f"</div>"
                        f"<div>{signal_badge_html(signal)}"
                        f"<span style='color: {TEXT_MUTED}; margin-left: 8px; "
                        f"font-size: 0.85rem;'>{prob:.0%}</span></div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    # Free: muestra senal pero oculta datos
                    st.markdown(
                        f"<div aria-label='Senal {signal} — detalles ocultos (plan Pro)' "
                        f"style='background: {BG_CARD}; "
                        f"border: 1px solid {signal_color}30; "
                        f"border-left: 3px solid {signal_color}; "
                        f"padding: 14px 16px; border-radius: 10px;'>"
                        f"<div style='margin-bottom: 8px;'>"
                        f"<strong style='filter: blur(5px); font-size: 1.05rem;' "
                        f"aria-hidden='true'>??????</strong></div>"
                        f"<div>{signal_badge_html(signal)}"
                        f"<span style='filter: blur(5px); color: {TEXT_MUTED}; "
                        f"margin-left: 8px;' aria-hidden='true'>??%</span></div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

        # CTA para Free users
        if not is_premium:
            st.markdown("")
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
    st.subheader("Tokens por cadena")

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
        hole=0.5,
    )
    fig_chain.update_traces(
        textposition="inside", textinfo="percent+label",
        textfont_size=12,
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
    st.subheader("Clasificaciones")

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
        hole=0.5,
    )
    fig_labels.update_traces(
        textposition="inside", textinfo="percent+label",
        textfont_size=12,
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
    """Bar chart de tokens descubiertos por semana con color acento."""
    st.subheader("Tokens descubiertos por semana")

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
            opacity=0.85,
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
        yaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
    )
    st.plotly_chart(fig_weekly, use_container_width=True)
    total_nuevos = df_weekly["tokens_nuevos"].sum()
    st.caption(f"Total: {total_nuevos:,} tokens en {len(df_weekly)} semanas")


# ======================================================================
# Frescura de los datos
# ======================================================================

def _render_data_freshness(storage):
    """Muestra timestamps de la ultima actualizacion de datos."""
    st.subheader("Frescura de los datos")

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
            st.metric("Ultimo pool snapshot", str(last_snap)[:19])
        else:
            st.info("No hay snapshots todavia.")

    try:
        df_last_ohlcv = storage.query("SELECT MAX(timestamp) as last_time FROM ohlcv")
        last_ohlcv = df_last_ohlcv["last_time"].iloc[0] if not df_last_ohlcv.empty else None
    except Exception:
        last_ohlcv = None

    with col_fresh2:
        if last_ohlcv:
            st.metric("Ultimo registro OHLCV", str(last_ohlcv)[:19])
        else:
            st.info("No hay datos OHLCV todavia.")
