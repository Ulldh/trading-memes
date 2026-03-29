"""
welcome.py - Tour de bienvenida para nuevos usuarios.

Se muestra solo en la primera visita del usuario (controlado
por session_state). Explica que hace la app, como funciona,
y cuales son los primeros pasos recomendados.
"""

import streamlit as st


def render():
    """Bienvenida — tutorial rapido para nuevos usuarios."""

    # Si el usuario ya vio el tour, mostrar mensaje corto con opcion de verlo otra vez
    if st.session_state.get("welcome_seen", False):
        st.info("Ya completaste el tour de bienvenida.")
        if st.button("Ver tour de nuevo"):
            st.session_state.welcome_seen = False
            st.rerun()
        return

    # -------------------------------------------------------------------------
    # Cabecera
    # -------------------------------------------------------------------------
    st.header("Bienvenido a Meme Detector")

    # -------------------------------------------------------------------------
    # Paso 1: Que es esto
    # -------------------------------------------------------------------------
    st.markdown("### Que hacemos?")
    st.info(
        "Analizamos miles de memecoins diariamente con Machine Learning "
        "para encontrar las que tienen mayor potencial de ser 'gems' (10x+)."
    )

    st.write("")

    # -------------------------------------------------------------------------
    # Paso 2: Como funciona (3 columnas)
    # -------------------------------------------------------------------------
    st.markdown("### ¿Cómo funciona")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**1. Recopilamos**")
        st.caption(
            "Datos de +5,000 tokens de Solana, Ethereum y Base cada dia."
        )
    with col2:
        st.markdown("**2. Analizamos**")
        st.caption(
            "94 características por token: liquidez, holders, volumen, momentum..."
        )
    with col3:
        st.markdown("**3. Alertamos**")
        st.caption(
            "Recibes las mejores señales en el dashboard y por Telegram."
        )

    st.write("")

    # -------------------------------------------------------------------------
    # Paso 3: Primeros pasos
    # -------------------------------------------------------------------------
    st.markdown("### Primeros pasos")
    st.markdown(
        """
1. **Señales** — Revisa las señales del dia en la pestana "Señales"
2. **Watchlist** — Anade tokens que te interesen para seguirlos
3. **Alertas** — Configura alertas Telegram para no perderte nada
4. **Track Record** — Revisa nuestro historial de aciertos
        """
    )

    st.write("")

    # -------------------------------------------------------------------------
    # Controles: no mostrar de nuevo / comenzar
    # -------------------------------------------------------------------------
    if st.checkbox("No mostrar de nuevo"):
        st.session_state.welcome_seen = True

    if st.button("Comenzar", type="primary"):
        st.session_state.welcome_seen = True
        st.rerun()
