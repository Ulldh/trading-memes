"""
paywall.py — Componente de paywall para features premium.
"""
import streamlit as st


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
    """Muestra prompt de upgrade cuando el usuario no tiene acceso."""
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

    # TODO: Replace with actual Stripe Checkout URL
    stripe_url = st.session_state.get("stripe_checkout_url", "#")
    st.link_button("🚀 Suscribirse", stripe_url, type="primary")


def limit_signals(df, plan: str = "free"):
    """Limita el numero de señales visibles segun plan."""
    from src.billing.subscription import get_plan_limits
    limits = get_plan_limits(plan)
    max_visible = limits.get("max_signals_visible", 3)

    if len(df) > max_visible:
        st.info(f"Mostrando {max_visible} de {len(df)} señales. Suscríbete a Pro para ver todas.")
        return df.head(max_visible)
    return df
