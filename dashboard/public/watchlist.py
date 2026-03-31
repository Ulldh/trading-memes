"""
watchlist.py - Pagina de watchlist de tokens.

Permite al usuario:
- Ver tokens en su watchlist con datos actualizados
- Eliminar tokens de la watchlist
- Ver un resumen rapido de cada token monitoreado

PRO enhancements:
- Probabilidad del modelo (score) si fue re-scored
- Ultima actualizacion timestamp
"""
import logging
from html import escape

import streamlit as st
import pandas as pd

from src.data.supabase_storage import get_storage as _get_storage

logger = logging.getLogger(__name__)
from src.utils.helpers import truncate_address
from dashboard.constants import LABEL_COLORS
from dashboard.i18n import t


@st.cache_resource
def get_storage():
    return _get_storage()


def _is_pro_or_admin() -> bool:
    """Verifica si el usuario actual es Pro o Admin."""
    role = st.session_state.get("role", "free")
    if role == "admin":
        return True
    plan = st.session_state.get("profile", {}).get("subscription_plan", "free")
    return plan in ("pro", "enterprise") or role == "pro"


@st.cache_data(ttl=300)
def _load_scores_for_tokens(token_ids: tuple) -> dict:
    """Carga los scores mas recientes para una lista de tokens.

    Returns:
        dict: {token_id: {"probability": float, "signal": str, "scored_at": str}}
    """
    if not token_ids:
        return {}
    storage = _get_storage()
    scores = {}
    try:
        # Buscar scores recientes para cada token
        placeholders = ",".join(["?" for _ in token_ids])
        df_scores = storage.query(
            f"SELECT token_id, probability, signal, scored_at "
            f"FROM scores WHERE token_id IN ({placeholders}) "
            f"ORDER BY scored_at DESC",
            tuple(token_ids),
        )
        if not df_scores.empty:
            # Quedarse con el score mas reciente por token
            for _, row in df_scores.iterrows():
                tid = row["token_id"]
                if tid not in scores:
                    scores[tid] = {
                        "probability": row.get("probability", 0.0),
                        "signal": row.get("signal", "NONE"),
                        "scored_at": row.get("scored_at", ""),
                    }
    except Exception:
        pass
    return scores


def render():
    """Renderiza la pagina de Watchlist."""
    st.title(t("pro.watchlist_title", "Watchlist"))

    st.info(
        t("pro.watchlist_desc",
          "**¿Que es esto?** Tu lista personal de tokens para monitorear. "
          "Agrega tokens desde la pagina de Busqueda de Token para seguir "
          "su evolucion de precio, liquidez y actividad.")
    )

    storage = get_storage()
    _user_id = st.session_state.get("user", {}).get("id")
    watchlist_df = storage.get_watchlist(user_id=_user_id)

    if watchlist_df.empty:
        st.warning(t("pro.watchlist_empty", "Tu watchlist esta vacia."))
        st.caption(
            t("pro.watchlist_hint",
              "Ve a **Buscar Token**, busca un token y haz clic en "
              "'Agregar a Watchlist' para empezar a monitorear.")
        )
        return

    is_pro = _is_pro_or_admin()

    # Enforce plan limits on display for downgraded users
    if not is_pro:
        from src.billing.subscription import get_plan_limits
        role = st.session_state.get("role", "free")
        plan = (st.session_state.get("profile") or {}).get("subscription_plan", role)
        limits = get_plan_limits(plan)
        max_wl = limits.get("max_watchlist", 3)
        if len(watchlist_df) > max_wl:
            st.warning(
                t("pro.watchlist_limit_exceeded",
                  "Tu plan permite **{max} tokens** en la watchlist. "
                  "Mostrando los primeros {max}. Actualiza a **Pro** para monitorear hasta 10."
                ).format(max=max_wl)
            )
            watchlist_df = watchlist_df.head(max_wl)

    st.caption(
        t("pro.watchlist_count",
          "**{count} tokens** en tu watchlist").format(count=len(watchlist_df))
    )

    # Cargar scores si es Pro (para mostrar probabilidad del modelo)
    scores_map = {}
    if is_pro:
        token_ids = tuple(watchlist_df["token_id"].tolist())
        scores_map = _load_scores_for_tokens(token_ids)

    # ------------------------------------------------------------------
    # Tabla de watchlist
    # ------------------------------------------------------------------
    for idx, row in watchlist_df.iterrows():
        token_id = row["token_id"]
        name = row.get("name") or "Sin nombre"
        symbol = row.get("symbol") or "???"
        chain = row.get("chain", "?")
        label = row.get("label_multi")
        price = row.get("price_usd")
        volume = row.get("volume_24h")
        liquidity = row.get("liquidity_usd")

        # Sanitizar variables antes de interpolar en HTML
        safe_name = escape(str(name))
        safe_symbol = escape(str(symbol))

        # Label badge
        label_html = ""
        if label:
            safe_label = escape(str(label))
            color = LABEL_COLORS.get(label, "#95a5a6")
            label_html = (
                f" <span style='color:{color}; font-weight:bold;'>"
                f"[{safe_label.upper()}]</span>"
            )

        with st.container():
            # Pro: añadir columna extra para score del modelo
            if is_pro:
                col1, col2, col3, col4, col_model, col5 = st.columns(
                    [2, 1, 1, 1, 1, 0.5]
                )
            else:
                col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 0.5])
                col_model = None

            with col1:
                st.markdown(
                    f"**{safe_name}** ({safe_symbol}){label_html} - {chain.title()}",
                    unsafe_allow_html=True,
                )
                st.caption(truncate_address(token_id, chars=8))

            with col2:
                if price is not None:
                    if price < 0.01:
                        st.metric(
                            t("pro.wl_price", "Precio"),
                            f"${price:.8f}",
                        )
                    else:
                        st.metric(
                            t("pro.wl_price", "Precio"),
                            f"${price:,.4f}",
                        )
                else:
                    st.metric(t("pro.wl_price", "Precio"), "N/A")

            with col3:
                if volume is not None:
                    st.metric(t("pro.wl_vol", "Vol 24h"), f"${volume:,.0f}")
                else:
                    st.metric(t("pro.wl_vol", "Vol 24h"), "N/A")

            with col4:
                if liquidity is not None:
                    st.metric(
                        t("pro.wl_liquidity", "Liquidez"),
                        f"${liquidity:,.0f}",
                    )
                else:
                    st.metric(t("pro.wl_liquidity", "Liquidez"), "N/A")

            # Pro: columna de score del modelo
            if is_pro and col_model is not None:
                with col_model:
                    score_data = scores_map.get(token_id)
                    if score_data:
                        prob = score_data.get("probability", 0.0)
                        signal = score_data.get("signal", "NONE")
                        scored_at = score_data.get("scored_at", "")

                        # Mostrar score con color
                        if prob >= 0.70:
                            score_color = "#2ecc71"
                        elif prob >= 0.50:
                            score_color = "#f39c12"
                        else:
                            score_color = "#e74c3c"

                        st.metric(
                            t("pro.wl_model_score", "Score ML"),
                            f"{prob:.0%}",
                            help=f"Signal: {signal}",
                        )

                        # Ultima actualizacion
                        if scored_at:
                            scored_str = str(scored_at)[:16]
                            st.caption(
                                f"{t('pro.wl_last_update', 'Actualizado')}: {scored_str}"
                            )
                    else:
                        st.metric(
                            t("pro.wl_model_score", "Score ML"),
                            "N/A",
                            help=t("pro.wl_no_score",
                                   "Token no scored aun."),
                        )

            with col5:
                if st.button(
                    f"Eliminar {safe_symbol}",
                    key=f"remove_{token_id}",
                    help=t("pro.wl_remove", "Eliminar de watchlist"),
                ):
                    try:
                        storage.remove_from_watchlist(token_id, user_id=_user_id)
                        st.rerun()
                    except Exception as e:
                        logger.exception("Error al eliminar token de watchlist")
                        st.error("Se produjo un error inesperado. Inténtalo de nuevo.")

            st.divider()
