"""
subscription.py — Gestión de suscripciones en tabla profiles.
"""
from src.data.supabase_storage import get_storage


def get_subscription(user_id: str) -> dict:
    """Obtiene estado de suscripción del usuario."""
    storage = get_storage()
    result = storage.query(
        "SELECT subscription_status, subscription_plan, subscription_end, "
        "stripe_customer_id, max_watchlist_tokens FROM profiles WHERE id = ?",
        (user_id,)
    )
    if result:
        return result[0]
    return {"subscription_status": "inactive", "subscription_plan": "free"}


def activate_subscription(user_id: str, plan: str, stripe_customer_id: str,
                          period_end: str) -> bool:
    """Activa suscripción (llamado por webhook Stripe)."""
    # UPDATE profiles SET subscription_status='active', subscription_plan=plan,
    # stripe_customer_id=..., subscription_end=..., max_watchlist_tokens=...
    # WHERE id = user_id
    pass  # TODO: implement when Stripe is ready


def cancel_subscription(user_id: str) -> bool:
    """Cancela suscripción (llamado por webhook Stripe)."""
    pass  # TODO


def is_subscription_active(user_id: str) -> bool:
    """Verifica si la suscripción está activa y no expirada."""
    sub = get_subscription(user_id)
    return sub.get("subscription_status") == "active"


# Limites por plan
PLAN_LIMITS = {
    "free": {
        "max_signals_visible": 3,
        "max_watchlist": 3,
        "token_lookup": False,
        "shap_analysis": False,
        "telegram_alerts": False,
        "api_access": False,
    },
    "pro": {
        "max_signals_visible": 999,
        "max_watchlist": 10,
        "token_lookup": True,
        "shap_analysis": True,
        "telegram_alerts": True,
        "api_access": False,
    },
    "enterprise": {
        "max_signals_visible": 999,
        "max_watchlist": 999,
        "token_lookup": True,
        "shap_analysis": True,
        "telegram_alerts": True,
        "api_access": True,
    },
}


def get_plan_limits(plan: str = "free") -> dict:
    """Retorna limites del plan."""
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
