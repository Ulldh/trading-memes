"""
Landing page con pricing — propuesta de valor y planes de suscripción.

Esta pagina es publica (no requiere autenticación). Muestra la propuesta
de valor del producto, como funciona, los planes de precios y un FAQ.
"""

import streamlit as st


def render():
    """Landing page con pricing — propuesta de valor y planes de suscripción."""

    # -------------------------------------------------------------------------
    # 1. Hero section
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div style="text-align: center; padding: 2rem 0 1rem 0;">
            <h1 style="font-size: 2.8rem; margin-bottom: 0.2rem;">
                Trading Memes — Gem Detector
            </h1>
            <p style="font-size: 1.25rem; opacity: 0.85; max-width: 640px; margin: 0.8rem auto;">
                Detecta las proximas memecoins 10x antes que nadie.<br>
                Machine Learning analiza miles de tokens diariamente
                para encontrar los que tienen mayor potencial.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # -------------------------------------------------------------------------
    # 2. Stats bar (social proof)
    # -------------------------------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Tokens analizados", value="5,000+")
    with col2:
        st.metric(label="Blockchains", value="4", help="Solana, Ethereum, Base, Tron")
    with col3:
        st.metric(label="Señales diarias", value="07:30 UTC")
    with col4:
        st.metric(label="Modelo", value="Semanal", help="Reentrenamiento automatico semanal")

    st.divider()

    # -------------------------------------------------------------------------
    # 3. Como funciona (3 columnas)
    # -------------------------------------------------------------------------
    st.markdown("### ¿Cómo funciona")
    st.write("")

    hw1, hw2, hw3 = st.columns(3)
    with hw1:
        st.markdown(
            """
            #### Recopilacion de datos
            Recopilamos datos de **+5,000 memecoins** diariamente
            desde multiples fuentes: DEXs, blockchains y APIs sociales.
            """
        )
    with hw2:
        st.markdown(
            """
            #### Análisis ML
            Nuestro modelo de Machine Learning analiza
            **94 características** por token para predecir su potencial.
            """
        )
    with hw3:
        st.markdown(
            """
            #### Señales a tu Telegram
            Recibes las mejores señales directamente
            en **Telegram**, filtradas y ordenadas por probabilidad.
            """
        )

    st.divider()

    # -------------------------------------------------------------------------
    # 4. Pricing tiers (3 columnas)
    # -------------------------------------------------------------------------
    st.markdown("### Planes")
    st.write("")

    tier_free, tier_pro, tier_enterprise = st.columns(3)

    # --- Free ----------------------------------------------------------------
    with tier_free:
        st.markdown("#### Free")
        st.markdown(
            """
- Resumen del mercado
- 3 señales diarias
- Watchlist basica (3 tokens)
- ~~Busqueda de tokens~~
- ~~Alertas Telegram~~
- ~~Track Record completo~~
            """
        )
        st.markdown("**Gratis**")
        if st.button("Crear cuenta gratuita", key="cta_free", use_container_width=True):
            st.info("Proximamente — registro de usuarios en desarrollo.")

    # --- Pro (recomendado) ---------------------------------------------------
    with tier_pro:
        with st.container(border=True):
            st.markdown("#### Pro  &nbsp; `Recomendado`")
            st.markdown(
                """
- Todo lo de Free
- **Todas** las señales diarias
- Busqueda ilimitada de tokens
- Alertas Telegram personalizadas
- Track Record completo
- Watchlist de 10 tokens
- Análisis SHAP por token
                """
            )
            st.markdown("**$29 / mes**")
            if st.button("Empezar con Pro", key="cta_pro", type="primary", use_container_width=True):
                st.info("Proximamente — pasarela de pago en desarrollo.")

    # --- Enterprise ----------------------------------------------------------
    with tier_enterprise:
        st.markdown("#### Enterprise")
        st.markdown(
            """
- Todo lo de Pro
- API access
- Watchlist ilimitada
- Soporte prioritario
- Datos exportables
            """
        )
        st.markdown("**$99 / mes**")
        if st.button("Contactar ventas", key="cta_enterprise", use_container_width=True):
            st.info("Proximamente — escribe a soporte@tradingmemes.io")

    st.divider()

    # -------------------------------------------------------------------------
    # 5. FAQ (expanders)
    # -------------------------------------------------------------------------
    st.markdown("### Preguntas frecuentes")
    st.write("")

    with st.expander("¿Qué es un gem?"):
        st.write(
            "Un **gem** es un memecoin que consigue un retorno de al menos "
            "**10x** desde su precio de deteccion. Nuestro modelo esta "
            "entrenado para identificar patrones que diferencian a estos "
            "tokens de los miles que van a cero."
        )

    with st.expander("¿Cómo funciona el modelo?"):
        st.write(
            "Usamos **Random Forest** y **XGBoost** entrenados con datos "
            "históricos de miles de memecoins. Analizamos 94 características: "
            "liquidez, concentracion de holders, volumen, momentum, "
            "contexto de mercado y mas. El modelo se reentrena semanalmente "
            "para adaptarse a las condiciones del mercado."
        )

    with st.expander("¿Con qué frecuencia se actualizan las señales?"):
        st.write(
            "La recoleccion de datos se ejecuta **diariamente a las 06:00 UTC**. "
            "Las señales se generan y envian a Telegram a las **07:30 UTC**. "
            "Ademas, el modelo se reentrena **cada lunes** para incorporar "
            "los datos mas recientes."
        )

    with st.expander("¿Puedo cancelar en cualquier momento?"):
        st.write(
            "Si. Puedes cancelar tu suscripción en cualquier momento desde "
            "tu panel de usuario. No hay contratos ni permanencia minima. "
            "Al cancelar, mantendras el acceso hasta el final del periodo "
            "de facturación vigente."
        )

    with st.expander("¿Qué blockchains soportan?"):
        st.write(
            "Actualmente soportamos **Solana**, **Ethereum** y **Base**. "
            "Tron esta en fase de integracion. Planeamos anadir mas "
            "cadenas segun la demanda de la comunidad."
        )

    st.divider()

    # -------------------------------------------------------------------------
    # 6. Footer — disclaimer y enlaces
    # -------------------------------------------------------------------------
    st.warning(
        "Esto NO es consejo financiero. Los memecoins son altamente "
        "especulativos. Investiga siempre por tu cuenta (DYOR)."
    )

    foot1, foot2, foot3 = st.columns(3)
    with foot1:
        st.markdown("[Twitter / X](https://x.com/tradingmemes_io)")
    with foot2:
        st.markdown("[Telegram grupo](https://t.me/tradingmemes_io)")
    with foot3:
        st.markdown("[soporte@tradingmemes.io](mailto:soporte@tradingmemes.io)")
