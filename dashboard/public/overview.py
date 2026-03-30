"""
overview.py - Pagina de resumen general del dataset.

Muestra estadisticas clave del proyecto:
- Market Pulse: resumen del dia para todos los usuarios
- Conteo de tokens, snapshots, OHLCV y labels
- Distribución de tokens por cadena (pie chart)
- Distribución de labels (pie chart)
- Tokens descubiertos por semana (bar chart)
- Frescura de los datos (ultima actualización)
"""
import logging
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from src.data.supabase_storage import get_storage as _get_storage
from dashboard.constants import LABEL_COLORS, CHAIN_COLORS, SIGNAL_COLORS

logger = logging.getLogger(__name__)


@st.cache_resource
def get_storage():
    """Crea una instancia de Storage cacheada para no reconectar cada vez."""
    return _get_storage()


def render():
    """Renderiza la pagina de Overview."""
    st.title("Overview del Dataset")

    # --- Welcome experience para nuevos usuarios Free ---
    _render_welcome_message()

    st.info(
        "**¿Qué es esto?** Esta pagina muestra un resumen de todos los datos que hemos "
        "recopilado sobre memecoins. Piensa en ello como el \"inventario\" de nuestro "
        "proyecto: cuantos tokens tenemos, de que blockchains vienen, y como estan "
        "clasificados."
    )

    storage = get_storage()

    # ------------------------------------------------------------------
    # 0. Market Pulse — resumen del dia (visible para todos)
    # ------------------------------------------------------------------
    _render_market_pulse(storage)

    st.divider()

    # ------------------------------------------------------------------
    # 1. Metricas principales (KPIs)
    # ------------------------------------------------------------------
    st.subheader("Métricas principales")

    st.caption(
        "Cada número representa cuantos registros tenemos en la base de datos. "
        "Mas datos = modelos mas confiables."
    )

    try:
        stats = storage.stats()
    except Exception as e:
        logger.exception("Error al conectar con la base de datos en overview")
        st.error("Se produjo un error inesperado. Inténtalo de nuevo.")
        return

    # Mostrar conteos en columnas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Tokens",
        f"{stats.get('tokens', 0):,}",
        help="Número total de memecoins que estamos rastreando.",
    )
    col2.metric(
        "Snapshots",
        f"{stats.get('pool_snapshots', 0):,}",
        help="Fotos del estado de cada token (precio, volumen, liquidez) tomadas en un momento dado.",
    )
    col3.metric(
        "Registros OHLCV",
        f"{stats.get('ohlcv', 0):,}",
        help="Velas de precio (Open-High-Low-Close-Volume). Cada vela es un dia de datos de precio.",
    )
    col4.metric(
        "Labels asignados",
        f"{stats.get('labels', 0):,}",
        help="Tokens que ya clasificamos como 'gem', 'failure', etc. Esto es lo que el modelo aprende.",
    )

    # Fila adicional
    col5, col6, col7, col8 = st.columns(4)
    col5.metric(
        "Holders snapshots",
        f"{stats.get('holder_snapshots', 0):,}",
        help="Datos de quienes poseen cada token (los 'holders'). Requiere API key de Helius.",
    )
    col6.metric(
        "Contratos analizados",
        f"{stats.get('contract_info', 0):,}",
        help="Tokens cuyo contrato inteligente verificamos (si es seguro, si puede crear mas tokens, etc.).",
    )
    col7.metric(
        "Features calculados",
        f"{stats.get('features', 0):,}",
        help="Tokens para los que ya calculamos las 'features' (características numericas que el modelo usa para predecir).",
    )
    col8.metric(
        "Tablas en la DB",
        len(stats),
        help="Número de tablas en la base de datos SQLite.",
    )

    st.divider()

    # ------------------------------------------------------------------
    # 2. Distribucion de tokens por cadena (pie chart)
    # ------------------------------------------------------------------
    st.subheader("Distribución de tokens por cadena")

    st.caption(
        "Cada memecoin vive en una blockchain (Solana, Ethereum o Base). "
        "Este grafico muestra cuantos tokens tenemos de cada una. "
        "Solana es la mas popular para memecoins por sus transacciones rapidas y baratas."
    )

    try:
        df_tokens = storage.query("SELECT chain, COUNT(*) as count FROM tokens GROUP BY chain")
    except Exception:
        df_tokens = pd.DataFrame()

    if df_tokens.empty:
        st.info("No hay tokens en la base de datos todavia.")
    else:
        fig_chain = px.pie(
            df_tokens,
            names="chain",
            values="count",
            title="Tokens por blockchain",
            color="chain",
            color_discrete_map=CHAIN_COLORS,
            hole=0.4,
        )
        fig_chain.update_traces(textposition="inside", textinfo="percent+label+value")
        st.plotly_chart(fig_chain, use_container_width=True)
        chain_summary = ", ".join(f"{r['chain']}: {r['count']}" for _, r in df_tokens.iterrows())
        st.caption(f"Distribucion por cadena: {chain_summary}")

    st.divider()

    # ------------------------------------------------------------------
    # 3. Distribucion de labels (pie chart)
    # ------------------------------------------------------------------
    st.subheader("Clasificaciones asignadas")

    st.caption(
        "Cada token del 'seed dataset' (nuestros ejemplos conocidos) esta clasificado "
        "segun su rendimiento histórico:\n"
        "- **Gem**: Alcanzo 10x o mas y se mantuvo (las joyas que buscamos).\n"
        "- **Moderate success**: Subio entre 3x-10x pero no tanto como un gem.\n"
        "- **Failure**: Perdio 90%+ de su valor (la mayoria de memecoins acaban asi)."
    )

    try:
        df_labels = storage.query(
            "SELECT label_multi, COUNT(*) as count FROM labels GROUP BY label_multi"
        )
    except Exception:
        df_labels = pd.DataFrame()

    if df_labels.empty:
        st.info("No hay labels asignados todavia.")
    else:
        fig_labels = px.pie(
            df_labels,
            names="label_multi",
            values="count",
            title="Clasificacion de tokens conocidos",
            color="label_multi",
            color_discrete_map=LABEL_COLORS,
            hole=0.4,
        )
        fig_labels.update_traces(textposition="inside", textinfo="percent+label+value")
        st.plotly_chart(fig_labels, use_container_width=True)
        label_summary = ", ".join(f"{r['label_multi']}: {r['count']}" for _, r in df_labels.iterrows())
        st.caption(f"Clasificaciones: {label_summary}")

    st.divider()

    # ------------------------------------------------------------------
    # 4. Tokens descubiertos por semana (bar chart)
    # ------------------------------------------------------------------
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
    else:
        df_first_seen["first_seen"] = pd.to_datetime(df_first_seen["first_seen"], errors="coerce")
        df_first_seen = df_first_seen.dropna(subset=["first_seen"])

        if not df_first_seen.empty:
            df_first_seen["week"] = df_first_seen["first_seen"].dt.to_period("W").apply(
                lambda r: r.start_time
            )
            df_weekly = df_first_seen.groupby("week").size().reset_index(name="tokens_nuevos")
            df_weekly = df_weekly.sort_values("week")

            fig_weekly = px.bar(
                df_weekly,
                x="week",
                y="tokens_nuevos",
                title="Nuevos tokens descubiertos por semana",
                labels={"week": "Semana", "tokens_nuevos": "Tokens nuevos"},
                color_discrete_sequence=["#9b59b6"],
            )
            fig_weekly.update_layout(xaxis_title="Semana", yaxis_title="Cantidad de tokens")
            st.plotly_chart(fig_weekly, use_container_width=True)
            total_nuevos = df_weekly["tokens_nuevos"].sum()
            st.caption(f"Total de tokens descubiertos: {total_nuevos} en {len(df_weekly)} semanas")

    st.divider()

    # ------------------------------------------------------------------
    # 5. Frescura de los datos
    # ------------------------------------------------------------------
    st.subheader("Frescura de los datos")

    st.caption(
        "Indica cuando fue la ultima vez que recopilamos datos. "
        "Si la fecha es muy antigua, conviene ejecutar la recopilacion de nuevo."
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


# ======================================================================
# Welcome message para nuevos usuarios Free
# ======================================================================

def _render_welcome_message():
    """Muestra un mensaje de bienvenida la primera vez que un usuario Free visita el dashboard.

    Usa session_state para mostrarlo solo una vez por sesion.
    Solo se muestra a usuarios Free (no Pro ni Admin).
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
    user_name = user_email.split("@")[0] if user_email else "trader"

    # Mostrar el mensaje de bienvenida como un container destacado
    with st.container():
        st.markdown(
            f"""
            <div style="padding: 20px; border-radius: 10px;
                        border: 1px solid rgba(46, 204, 113, 0.3);
                        background: linear-gradient(135deg, rgba(46, 204, 113, 0.05), rgba(52, 152, 219, 0.05));
                        margin-bottom: 16px;">
                <h3 style="margin-top: 0;">Bienvenido a Meme Detector, {user_name}!</h3>
                <p>Tu cuenta <strong>Free</strong> incluye:</p>
                <table aria-label="Funciones incluidas en plan Free" style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 4px 12px;">&#9989; <strong>Overview</strong> — Resumen del mercado y Market Pulse</td>
                        <td style="padding: 4px 12px;">&#9989; <strong>3 señales diarias</strong> — Top tokens detectados</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 12px;">&#9989; <strong>Track Record</strong> — Historial del modelo</td>
                        <td style="padding: 4px 12px;">&#9989; <strong>Watchlist</strong> — Hasta 3 tokens</td>
                    </tr>
                </table>
                <p style="margin-top: 12px;">Con <strong>Pro ($29/mes)</strong> desbloqueas:</p>
                <table aria-label="Funciones del plan Pro" style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 4px 12px;">&#128273; Todas las señales diarias (sin limite)</td>
                        <td style="padding: 4px 12px;">&#128273; Busqueda de tokens ilimitada</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 12px;">&#128273; Academia Pro (contenido avanzado)</td>
                        <td style="padding: 4px 12px;">&#128273; Alertas Telegram en tiempo real</td>
                    </tr>
                </table>
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
# Market Pulse — widget de resumen diario
# ======================================================================

@st.cache_data(ttl=300)
def _load_market_pulse_data():
    """Carga datos para el widget Market Pulse: tokens de hoy, nuevos, top señales."""
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

    # Top señales del dia (sin limite, necesitamos el total y top 3)
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
    """Renderiza el widget Market Pulse en la parte superior del overview."""

    st.subheader(":satellite: Market Pulse")
    st.caption(
        "Resumen rapido del estado del mercado hoy. "
        "Datos actualizados diariamente a las 07:00 UTC."
    )

    total_tokens, new_tokens_24h, df_signals = _load_market_pulse_data()

    total_signals = len(df_signals) if not df_signals.empty else 0

    # --- KPI cards del Market Pulse ---
    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Tokens rastreados",
        f"{total_tokens:,}",
        help="Número total de memecoins en nuestra base de datos.",
    )
    col2.metric(
        "Nuevos (24h)",
        f"{new_tokens_24h:,}",
        help="Tokens descubiertos en las ultimas 24 horas.",
    )
    col3.metric(
        "Señales activas",
        f"{total_signals:,}",
        help="Total de señales generadas por el modelo hoy.",
    )

    # --- Top 3 señales del dia (teaser para Free) ---
    if not df_signals.empty and total_signals > 0:
        st.markdown("---")
        st.markdown("**Top señales del dia**")

        role = st.session_state.get("role", "free")
        plan = st.session_state.get("profile", {}).get("subscription_plan", "free")
        is_premium = (role == "admin" or plan in ("pro", "enterprise"))

        # Ordenar por probabilidad y tomar top 3
        df_top3 = df_signals.sort_values("probability", ascending=False).head(3)

        cols = st.columns(3)
        for i, (_, row) in enumerate(df_top3.iterrows()):
            signal = row.get("signal", "NONE")
            signal_color = SIGNAL_COLORS.get(signal, "#95a5a6")

            with cols[i]:
                if is_premium:
                    # Pro/Admin ve todo
                    symbol = row.get("symbol", "???")
                    prob = row.get("probability", 0.0)
                    st.markdown(
                        f"<div aria-label='{symbol}: senal {signal}, {prob:.0%}' "
                        f"style='border-left: 4px solid {signal_color}; "
                        f"padding: 8px 12px; border-radius: 4px; "
                        f"background: rgba(255,255,255,0.03);'>"
                        f"<strong>{symbol}</strong><br>"
                        f"<span style='color: {signal_color}; font-weight: bold;'>"
                        f"{signal}</span> — {prob:.0%}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    # Free: muestra señal pero oculta probabilidad
                    st.markdown(
                        f"<div aria-label='Senal {signal} — token y probabilidad ocultos (plan Pro)' "
                        f"style='border-left: 4px solid {signal_color}; "
                        f"padding: 8px 12px; border-radius: 4px; "
                        f"background: rgba(255,255,255,0.03);'>"
                        f"<strong style='filter: blur(5px);' aria-hidden='true'>??????</strong><br>"
                        f"<span style='color: {signal_color}; font-weight: bold;'>"
                        f"{signal}</span> — "
                        f"<span style='filter: blur(5px);' aria-hidden='true'>??%</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

        # CTA para Free users
        if not is_premium:
            st.markdown("")
            if total_signals > 3:
                st.info(
                    f":lock: Hay **{total_signals} señales** disponibles hoy. "
                    f"Actualiza a **Pro** para ver todas las señales con datos completos."
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
