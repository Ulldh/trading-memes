"""
subscription.py — Gestión de suscripciones en tabla profiles.

NOTE: Las funciones activate_subscription() y cancel_subscription() son stubs.
El procesamiento real de webhooks de Stripe se hace en la Edge Function de Supabase:
  supabase/functions/stripe-webhook/index.ts
"""
from src.data.supabase_storage import get_storage
from src.utils.logger import get_logger

logger = get_logger(__name__)


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
    """
    Stub: activar suscripcion.

    NOTE: Actual webhook processing in supabase/functions/stripe-webhook/index.ts
    La Edge Function de Supabase maneja checkout.session.completed y
    customer.subscription.updated, actualizando profiles directamente.
    Este stub existe solo por compatibilidad. No se usa en produccion.
    """
    logger.info(
        f"activate_subscription() llamado para user={user_id}, plan={plan}. "
        f"NOTA: El procesamiento real esta en la Edge Function stripe-webhook."
    )
    return False


def cancel_subscription(user_id: str) -> bool:
    """
    Stub: cancelar suscripcion.

    NOTE: Actual webhook processing in supabase/functions/stripe-webhook/index.ts
    La Edge Function de Supabase maneja customer.subscription.deleted,
    actualizando profiles directamente.
    Este stub existe solo por compatibilidad. No se usa en produccion.
    """
    logger.info(
        f"cancel_subscription() llamado para user={user_id}. "
        f"NOTA: El procesamiento real esta en la Edge Function stripe-webhook."
    )
    return False


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
        "academy_pro": False,
    },
    "pro": {
        "max_signals_visible": 999,
        "max_watchlist": 10,
        "token_lookup": True,
        "shap_analysis": True,
        "telegram_alerts": True,
        "api_access": False,
        "academy_pro": True,
    },
    "enterprise": {
        "max_signals_visible": 999,
        "max_watchlist": 999,
        "token_lookup": True,
        "shap_analysis": True,
        "telegram_alerts": True,
        "api_access": True,
        "academy_pro": True,
    },
}


def get_plan_limits(plan: str = "free") -> dict:
    """Retorna limites del plan."""
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
