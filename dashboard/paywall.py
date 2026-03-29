"""
paywall.py — Componente de paywall para features premium.

Si Stripe esta configurado (STRIPE_SECRET_KEY + STRIPE_PRICE_ID_PRO),
genera una URL de checkout real. Si no, muestra mensaje "Proximamente".
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


def check_feature_access(feature: str) -> bool:
    """Verifica si el usuario tiene acceso a una feature.

    Args:
        feature: 'token_lookup', 'shap_analysis', 'telegram_alerts', 'api_access'

    Returns:
        True si tiene acceso, False si no.
    """
    role = st.session_state.get("role", "free")
    if role == "admin":
        return True  # Admin tiene acceso total

    plan = st.session_state.get("profile", {}).get("subscription_plan", "free")

    from src.billing.subscription import get_plan_limits
    limits = get_plan_limits(plan)
    return limits.get(feature, False)


def show_upgrade_prompt(feature_name: str = "esta función"):
    """Muestra prompt de upgrade cuando el usuario no tiene acceso.

    Si Stripe esta configurado, genera una URL de checkout real.
    Si no, muestra un mensaje de "Proximamente".
    """
    st.warning(f"🔒 {feature_name} requiere suscripción Pro.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Plan Pro — $29/mes**
        - ✅ Todas las señales diarias
        - ✅ Búsqueda de tokens ilimitada
        - ✅ Análisis SHAP
        - ✅ Alertas Telegram
        - ✅ Watchlist de 10 tokens
        """)
    with col2:
        st.markdown("""
        **Plan Enterprise — $99/mes**
        - ✅ Todo lo de Pro
        - ✅ API access
        - ✅ Watchlist ilimitada
        - ✅ Soporte prioritario
        """)

    # Intentar obtener URL real de Stripe Checkout
    checkout_url = _get_checkout_url("pro")

    if checkout_url:
        st.link_button("🚀 Suscribirse", checkout_url, type="primary")
    else:
        # Stripe no configurado — mostrar mensaje informativo
        st.info(
            "💳 Pagos próximamente. Estamos configurando el sistema de "
            "suscripciones. Contacta info@memedetector.es para más información."
        )


def limit_signals(df, plan: str = "free"):
    """Limita el número de señales visibles segun plan."""
    from src.billing.subscription import get_plan_limits
    limits = get_plan_limits(plan)
    max_visible = limits.get("max_signals_visible", 3)

    if len(df) > max_visible:
        st.info(f"Mostrando {max_visible} de {len(df)} señales. Suscríbete a Pro para ver todas.")
        return df.head(max_visible)
    return df
