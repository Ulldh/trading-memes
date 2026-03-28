"""
watchlist.py - Pagina de watchlist de tokens.

Permite al usuario:
- Ver tokens en su watchlist con datos actualizados
- Eliminar tokens de la watchlist
- Ver un resumen rapido de cada token monitoreado
"""
from html import escape

import streamlit as st
import pandas as pd

from src.data.supabase_storage import get_storage as _get_storage
from src.utils.helpers import truncate_address
from dashboard.constants import LABEL_COLORS


@st.cache_resource
def get_storage():
    return _get_storage()


def render():
    """Renderiza la pagina de Watchlist."""
    st.title("Watchlist")

    st.info(
        "**Que es esto?** Tu lista personal de tokens para monitorear. "
        "Agrega tokens desde la pagina de Busqueda de Token para seguir "
        "su evolucion de precio, liquidez y actividad."
    )

    storage = get_storage()
    watchlist_df = storage.get_watchlist()

    if watchlist_df.empty:
        st.warning("Tu watchlist esta vacia.")
        st.caption(
            "Ve a **Buscar Token**, busca un token y haz clic en "
            "'Agregar a Watchlist' para empezar a monitorear."
        )
        return

    st.caption(f"**{len(watchlist_df)} tokens** en tu watchlist")

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
            label_html = f" <span style='color:{color}; font-weight:bold;'>[{safe_label.upper()}]</span>"

        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 0.5])

            with col1:
                st.markdown(
                    f"**{safe_name}** ({safe_symbol}){label_html} - {chain.title()}",
                    unsafe_allow_html=True,
                )
                st.caption(truncate_address(token_id, chars=8))

            with col2:
                if price is not None:
                    if price < 0.01:
                        st.metric("Precio", f"${price:.8f}")
                    else:
                        st.metric("Precio", f"${price:,.4f}")
                else:
                    st.metric("Precio", "N/A")

            with col3:
                if volume is not None:
                    st.metric("Vol 24h", f"${volume:,.0f}")
                else:
                    st.metric("Vol 24h", "N/A")

            with col4:
                if liquidity is not None:
                    st.metric("Liquidez", f"${liquidity:,.0f}")
                else:
                    st.metric("Liquidez", "N/A")

            with col5:
                if st.button("X", key=f"remove_{token_id}", help="Eliminar de watchlist"):
                    try:
                        storage.remove_from_watchlist(token_id)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar de watchlist: {e}")

            st.divider()
