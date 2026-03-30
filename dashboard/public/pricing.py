"""
Landing page con pricing — propuesta de valor y planes de suscripción.

Esta pagina es publica (no requiere autenticación). Muestra la propuesta
de valor del producto, como funciona, los planes de precios y un FAQ.
"""

import streamlit as st

# Importar stripe_client con try/except (las keys pueden no estar configuradas)
try:
    from src.billing.stripe_client import create_checkout_session, is_configured as _stripe_configured
except Exception:
    create_checkout_session = None  # type: ignore[assignment]
    _stripe_configured = lambda: False  # noqa: E731


def _get_checkout_url(plan: str = "pro") -> str:
    """Genera URL de Stripe Checkout para el usuario actual.

    Retorna la URL o cadena vacia si Stripe no esta configurado.
    """
    if create_checkout_session is None or not _stripe_configured():
        return ""

    email = st.session_state.get("user", {}).get("email", "")
    if not email:
        return ""

    try:
        return create_checkout_session(user_email=email, plan=plan) or ""
    except Exception:
        return ""


def render():
    """Landing page con pricing — propuesta de valor y planes de suscripción."""

    # -------------------------------------------------------------------------
    # 1. Hero section
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div style="text-align: center; padding: 2rem 0 1rem 0;">
            <h1 style="font-size: 2.8rem; margin-bottom: 0.2rem;">
                Meme Detector — Gem Detector
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

    # Detectar si el usuario esta logueado y si Stripe esta configurado
    _stripe_ok = callable(_stripe_configured) and _stripe_configured()
    user_email = st.session_state.get("user", {}).get("email", "")

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
            st.switch_page("dashboard/public/login.py")

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
            if _stripe_ok and user_email:
                checkout_url = _get_checkout_url("pro")
                if checkout_url:
                    st.link_button(
                        "Empezar con Pro",
                        checkout_url,
                        type="primary",
                        use_container_width=True,
                    )
                else:
                    st.info(
                        "No se pudo generar el enlace de pago. "
                        "Contacta info@memedetector.es"
                    )
            elif user_email:
                # Logueado pero Stripe no configurado
                st.info(
                    "Pagos proximamente. Contacta info@memedetector.es "
                    "para mas informacion."
                )
            else:
                # No logueado — redirigir a registro
                if st.button("Empezar con Pro", key="cta_pro", type="primary", use_container_width=True):
                    st.switch_page("dashboard/public/login.py")

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
        if _stripe_ok and user_email:
            checkout_url = _get_checkout_url("enterprise")
            if checkout_url:
                st.link_button(
                    "Contactar ventas",
                    checkout_url,
                    use_container_width=True,
                )
            else:
                st.info(
                    "No se pudo generar el enlace de pago. "
                    "Contacta info@memedetector.es"
                )
        elif user_email:
            st.info(
                "Pagos proximamente. Contacta info@memedetector.es "
                "para mas informacion."
            )
        else:
            if st.button("Contactar ventas", key="cta_enterprise", use_container_width=True):
                st.switch_page("dashboard/public/login.py")

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
        st.markdown("[Twitter / X](https://x.com/memedetector_es)")
    with foot2:
        st.markdown("[Telegram grupo](https://t.me/memedetector_es)")
    with foot3:
        st.markdown("[info@memedetector.es](mailto:info@memedetector.es)")
