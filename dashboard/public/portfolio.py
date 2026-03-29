"""
portfolio.py - Portfolio Tracker (seguimiento de posiciones).

Pagina publica donde los suscriptores pueden registrar sus compras,
monitorear sus posiciones y ver su rendimiento (P&L) en tiempo real.

Secciones:
  1. Formulario para anadir posiciones (expandable)
  2. KPIs resumen: total invertido, valor actual, P&L, posiciones activas
  3. Tabla de posiciones con precio actual y P&L
  4. Gráfico de valor del portfolio
  5. Métricas de rendimiento (mejor/peor trade, win rate)

Datos:
  - Posiciones almacenadas en st.session_state (por sesión)
  - Precios actuales obtenidos de OHLCV/pool_snapshots en Supabase
  - Futuro: tabla user_portfolio en Supabase
"""

from datetime import date, datetime
from html import escape
from typing import Optional

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.data.supabase_storage import get_storage as _get_storage


# ============================================================
# Helpers
# ============================================================

@st.cache_resource
def get_storage():
    """Instancia de Storage cacheada (evita reconexion por cada render)."""
    return _get_storage()


@st.cache_data(ttl=300)
def _fetch_current_price(token_address: str, chain: str) -> Optional[float]:
    """
    Obtiene el precio actual de un token desde la base de datos.

    Intenta primero pool_snapshots (precio mas reciente),
    luego OHLCV (ultimo cierre diario).

    Args:
        token_address: Direccion del token (token_id).
        chain: Blockchain (solana, ethereum, base).

    Returns:
        Precio en USD o None si no se encuentra.
    """
    storage = get_storage()

    # Intento 1: pool_snapshots (dato mas fresco)
    try:
        df_snap = storage.query(
            "SELECT price_usd FROM pool_snapshots "
            "WHERE token_id = ? ORDER BY snapshot_time DESC LIMIT 1",
            (token_address,),
        )
        if not df_snap.empty and df_snap["price_usd"].iloc[0] is not None:
            price = float(df_snap["price_usd"].iloc[0])
            if price > 0:
                return price
    except Exception:
        pass

    # Intento 2: OHLCV (ultimo cierre diario)
    try:
        df_ohlcv = storage.query(
            "SELECT close FROM ohlcv "
            "WHERE token_id = ? AND timeframe = 'day' "
            "ORDER BY timestamp DESC LIMIT 1",
            (token_address,),
        )
        if not df_ohlcv.empty and df_ohlcv["close"].iloc[0] is not None:
            price = float(df_ohlcv["close"].iloc[0])
            if price > 0:
                return price
    except Exception:
        pass

    return None


@st.cache_data(ttl=300)
def _fetch_token_info(token_address: str) -> dict:
    """
    Obtiene nombre y simbolo del token desde la base de datos.

    Args:
        token_address: Direccion del token (token_id).

    Returns:
        Dict con 'name' y 'symbol' (vacios si no se encuentra).
    """
    storage = get_storage()
    try:
        df = storage.query(
            "SELECT name, symbol FROM tokens WHERE token_id = ? LIMIT 1",
            (token_address,),
        )
        if not df.empty:
            return {
                "name": df["name"].iloc[0] or "",
                "symbol": df["symbol"].iloc[0] or "",
            }
    except Exception:
        pass
    return {"name": "", "symbol": ""}


def _chain_badge(chain: str) -> str:
    """Devuelve el nombre legible de la cadena."""
    badges = {
        "solana": "Solana",
        "ethereum": "Ethereum",
        "base": "Base",
    }
    return badges.get(chain.lower(), chain.capitalize() if chain else "Desconocida")


def _format_usd(value: float) -> str:
    """Formatea un valor monetario en USD de forma legible."""
    if abs(value) >= 1_000_000:
        return f"${value:,.0f}"
    elif abs(value) >= 1:
        return f"${value:,.2f}"
    elif abs(value) >= 0.01:
        return f"${value:,.4f}"
    else:
        return f"${value:,.8f}"


def _format_pnl_pct(pnl_pct: float) -> str:
    """Formatea P&L porcentual con signo."""
    sign = "+" if pnl_pct >= 0 else ""
    return f"{sign}{pnl_pct:.1f}%"


def _pnl_color(value: float) -> str:
    """Devuelve color verde para ganancia, rojo para perdida."""
    if value > 0:
        return "#2ecc71"  # Verde
    elif value < 0:
        return "#e74c3c"  # Rojo
    return "#95a5a6"      # Gris (sin cambio)


def _init_portfolio():
    """Inicializa el portfolio en session_state si no existe."""
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = []


# ============================================================
# Render principal
# ============================================================

def render():
    """Portfolio Tracker — seguimiento de posiciones del usuario."""

    st.header(":briefcase: Portfolio")
    st.caption(
        "Registra tus compras y monitorea tu rendimiento en tiempo real."
    )

    _init_portfolio()

    # ======================================================
    # 1. FORMULARIO PARA ANADIR POSICIONES
    # ======================================================
    _render_add_position_form()

    # --- Estado vacio: mensaje amigable ---
    if not st.session_state.portfolio:
        st.info(
            ":inbox_tray: **Aun no has anadido posiciones.**\n\n"
            "Usa el formulario de arriba para registrar tu primera compra "
            "y empezar a hacer seguimiento de tu portfolio."
        )
        _render_disclaimer()
        return

    # Calcular datos actualizados para todas las posiciones
    positions_data = _compute_positions_data()

    # ======================================================
    # 2. KPI CARDS
    # ======================================================
    _render_kpis(positions_data)

    st.divider()

    # ======================================================
    # 3. TABLA DE POSICIONES
    # ======================================================
    _render_positions_table(positions_data)

    st.divider()

    # ======================================================
    # 4 y 5. GRAFICO + METRICAS DE RENDIMIENTO
    # ======================================================
    col_chart, col_metrics = st.columns([3, 2])

    with col_chart:
        _render_portfolio_chart(positions_data)

    with col_metrics:
        _render_performance_metrics(positions_data)

    st.divider()

    # ======================================================
    # 6. DISCLAIMER
    # ======================================================
    _render_disclaimer()


# ============================================================
# Secciones individuales
# ============================================================

def _render_add_position_form():
    """Formulario expandible para anadir una nueva posicion."""

    with st.expander(":heavy_plus_sign: Anadir nueva posicion", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            token_address = st.text_input(
                "Direccion del token",
                placeholder="Ej: 0x1234... o So1111...",
                help="La dirección del contrato del token en la blockchain.",
            )
            chain = st.selectbox(
                "Blockchain",
                ["Solana", "Ethereum", "Base"],
                help="La red donde compraste el token.",
            )
            buy_date = st.date_input(
                "Fecha de compra",
                value=date.today(),
                help="Cuando realizaste la compra.",
            )

        with col2:
            buy_price = st.number_input(
                "Precio de compra (USD)",
                min_value=0.0,
                format="%.10f",
                help="El precio por token al momento de tu compra.",
            )
            amount_invested = st.number_input(
                "Cantidad invertida (USD)",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                help="Total en dolares que invertiste en esta posicion.",
            )

        # Boton para anadir
        if st.button(":heavy_plus_sign: Anadir posicion", type="primary", use_container_width=True):
            # Validaciones
            if not token_address.strip():
                st.error("Introduce la dirección del token.")
                return
            if buy_price <= 0:
                st.error("El precio de compra debe ser mayor a 0.")
                return
            if amount_invested <= 0:
                st.error("La cantidad invertida debe ser mayor a 0.")
                return

            # Obtener info del token
            token_info = _fetch_token_info(token_address.strip())

            # Calcular tokens comprados
            tokens_bought = amount_invested / buy_price

            # Crear posicion
            position = {
                "id": len(st.session_state.portfolio),
                "token_address": token_address.strip(),
                "chain": chain.lower(),
                "buy_price": buy_price,
                "amount_invested": amount_invested,
                "tokens_bought": tokens_bought,
                "buy_date": buy_date.isoformat(),
                "name": token_info["name"],
                "symbol": token_info["symbol"],
                "active": True,
            }

            st.session_state.portfolio.append(position)
            st.success(
                f"Posicion anadida: "
                f"{token_info['symbol'] or token_address[:12]}... "
                f"— {_format_usd(amount_invested)} invertidos."
            )
            st.rerun()


def _compute_positions_data() -> list[dict]:
    """
    Calcula datos actualizados (precio actual, P&L) para cada posicion.

    Returns:
        Lista de dicts con toda la info de cada posicion incluyendo
        precio actual y calculo de ganancia/perdida.
    """
    positions = []

    for pos in st.session_state.portfolio:
        if not pos.get("active", True):
            continue

        current_price = _fetch_current_price(pos["token_address"], pos["chain"])

        # Calcular P&L
        if current_price is not None:
            current_value = pos["tokens_bought"] * current_price
            pnl_usd = current_value - pos["amount_invested"]
            pnl_pct = ((current_price / pos["buy_price"]) - 1) * 100
            price_available = True
        else:
            current_value = pos["amount_invested"]  # Asumir sin cambio
            pnl_usd = 0.0
            pnl_pct = 0.0
            price_available = False

        positions.append({
            **pos,
            "current_price": current_price,
            "current_value": current_value,
            "pnl_usd": pnl_usd,
            "pnl_pct": pnl_pct,
            "price_available": price_available,
        })

    return positions


def _render_kpis(positions: list[dict]):
    """Tarjetas KPI en la parte superior del portfolio."""

    total_invested = sum(p["amount_invested"] for p in positions)
    total_current = sum(p["current_value"] for p in positions)
    total_pnl = total_current - total_invested
    total_pnl_pct = ((total_current / total_invested) - 1) * 100 if total_invested > 0 else 0.0
    active_count = len(positions)

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total invertido",
        _format_usd(total_invested),
        help="Suma total del capital invertido en todas las posiciones.",
    )

    col2.metric(
        "Valor actual",
        _format_usd(total_current),
        delta=_format_pnl_pct(total_pnl_pct) if total_invested > 0 else None,
        delta_color="normal",
        help="Valor actual estimado de tu portfolio.",
    )

    col3.metric(
        "Ganancia / Perdida",
        _format_usd(abs(total_pnl)),
        delta=_format_pnl_pct(total_pnl_pct),
        delta_color="normal",
        help="Ganancia o perdida total en dolares y porcentaje.",
    )

    col4.metric(
        "Posiciones activas",
        active_count,
        help="Número de posiciones abiertas en tu portfolio.",
    )


def _render_positions_table(positions: list[dict]):
    """Tabla principal de posiciones con P&L y acciones."""

    st.subheader("Tus posiciones")

    # Preparar datos para la tabla
    display_data = []
    for pos in positions:
        name = pos.get("name", "")
        symbol = pos.get("symbol", "")
        token_label = (
            f"{name} ({symbol})" if name and symbol
            else (symbol or name or pos["token_address"][:16] + "...")
        )

        chain_label = _chain_badge(pos["chain"])

        if pos["price_available"]:
            current_price_str = _format_usd(pos["current_price"])
            pnl_pct_str = _format_pnl_pct(pos["pnl_pct"])
            current_value_str = _format_usd(pos["current_value"])
        else:
            current_price_str = "No disponible"
            pnl_pct_str = "—"
            current_value_str = "—"

        display_data.append({
            "Token": token_label,
            "Chain": chain_label,
            "Precio compra": _format_usd(pos["buy_price"]),
            "Precio actual": current_price_str,
            "P&L": pnl_pct_str,
            "Valor actual": current_value_str,
            "Invertido": _format_usd(pos["amount_invested"]),
            "Fecha": pos["buy_date"],
        })

    df_display = pd.DataFrame(display_data)

    # Mostrar tabla
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=min(len(df_display) * 38 + 40, 500),
        column_config={
            "Token": st.column_config.TextColumn("Token", width="medium"),
            "Chain": st.column_config.TextColumn("Chain", width="small"),
            "Precio compra": st.column_config.TextColumn("Precio compra", width="small"),
            "Precio actual": st.column_config.TextColumn("Precio actual", width="small"),
            "P&L": st.column_config.TextColumn("P&L", width="small"),
            "Valor actual": st.column_config.TextColumn("Valor actual", width="small"),
            "Invertido": st.column_config.TextColumn("Invertido", width="small"),
            "Fecha": st.column_config.TextColumn("Fecha", width="small"),
        },
    )

    # Botones para cerrar posiciones
    st.caption("Cerrar posiciones:")
    cols = st.columns(min(len(positions), 4))
    for idx, pos in enumerate(positions):
        col_idx = idx % min(len(positions), 4)
        name = pos.get("symbol") or pos["token_address"][:12]
        with cols[col_idx]:
            if st.button(
                f":x: {name}",
                key=f"close_{pos['id']}",
                help=f"Cerrar posicion de {name}",
            ):
                # Marcar como inactiva
                for p in st.session_state.portfolio:
                    if p["id"] == pos["id"]:
                        p["active"] = False
                        break
                st.success(f"Posicion de {name} cerrada.")
                st.rerun()


def _render_portfolio_chart(positions: list[dict]):
    """Gráfico del valor del portfolio (barras por posicion)."""

    st.subheader("Valor por posicion")

    if not positions:
        return

    # Preparar datos
    names = []
    invested = []
    current = []

    for pos in positions:
        name = pos.get("symbol") or pos.get("name") or pos["token_address"][:12]
        names.append(name)
        invested.append(pos["amount_invested"])
        current.append(pos["current_value"])

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Invertido",
        x=names,
        y=invested,
        marker_color="#3498db",
        text=[_format_usd(v) for v in invested],
        textposition="auto",
    ))

    fig.add_trace(go.Bar(
        name="Valor actual",
        x=names,
        y=current,
        marker_color=[_pnl_color(c - i) for c, i in zip(current, invested)],
        text=[_format_usd(v) for v in current],
        textposition="auto",
    ))

    fig.update_layout(
        barmode="group",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=40, b=20, l=20, r=20),
        height=350,
        yaxis_title="USD",
        xaxis_title="",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cccccc"),
    )

    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")

    st.plotly_chart(fig, use_container_width=True)


def _render_performance_metrics(positions: list[dict]):
    """Métricas de rendimiento del portfolio."""

    st.subheader("Rendimiento")

    if not positions:
        return

    # Solo considerar posiciones con precio disponible para metricas
    priced = [p for p in positions if p["price_available"]]

    if not priced:
        st.info("Sin datos de precio disponibles para calcular métricas.")
        return

    pnl_values = [p["pnl_pct"] for p in priced]
    best_trade = max(priced, key=lambda p: p["pnl_pct"])
    worst_trade = min(priced, key=lambda p: p["pnl_pct"])
    wins = sum(1 for p in priced if p["pnl_pct"] > 0)
    win_rate = (wins / len(priced)) * 100 if priced else 0

    # Mejor trade
    best_name = escape(str(best_trade.get("symbol") or best_trade["token_address"][:12]))
    st.markdown(
        f"**Mejor trade**  \n"
        f"<span style='color: {_pnl_color(best_trade['pnl_pct'])}; "
        f"font-size: 1.3em; font-weight: bold;'>"
        f"{_format_pnl_pct(best_trade['pnl_pct'])}</span>  \n"
        f"{best_name}",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Peor trade
    worst_name = escape(str(worst_trade.get("symbol") or worst_trade["token_address"][:12]))
    st.markdown(
        f"**Peor trade**  \n"
        f"<span style='color: {_pnl_color(worst_trade['pnl_pct'])}; "
        f"font-size: 1.3em; font-weight: bold;'>"
        f"{_format_pnl_pct(worst_trade['pnl_pct'])}</span>  \n"
        f"{worst_name}",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Win rate
    win_color = "#2ecc71" if win_rate >= 50 else "#e74c3c"
    st.markdown(
        f"**Win rate**  \n"
        f"<span style='color: {win_color}; "
        f"font-size: 1.3em; font-weight: bold;'>"
        f"{win_rate:.0f}%</span>  \n"
        f"{wins} de {len(priced)} posiciones en ganancia",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Media P&L
    avg_pnl = sum(pnl_values) / len(pnl_values) if pnl_values else 0
    st.markdown(
        f"**P&L promedio**  \n"
        f"<span style='color: {_pnl_color(avg_pnl)}; "
        f"font-size: 1.3em; font-weight: bold;'>"
        f"{_format_pnl_pct(avg_pnl)}</span>",
        unsafe_allow_html=True,
    )


def _render_disclaimer():
    """Disclaimer legal al pie de la pagina."""

    st.warning(
        ":warning: **Esto NO es consejo financiero.**\n\n"
        "Los datos de precio se obtienen de nuestra base de datos y pueden "
        "no reflejar el precio exacto de mercado en tiempo real. "
        "Las posiciones se guardan solo durante tu sesión actual. "
        "Haz tu propia investigacion (DYOR) y nunca inviertas mas de lo "
        "que puedas permitirte perder."
    )
