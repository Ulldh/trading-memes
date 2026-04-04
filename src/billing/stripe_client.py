"""
stripe_client.py — Integracion con Stripe para pagos y suscripciones.

Requiere: pip install stripe
Env vars: STRIPE_SECRET_KEY, STRIPE_PRICE_ID_PRO, STRIPE_PRICE_ID_ENTERPRISE,
          STRIPE_PRICE_ID_PRO_ANNUAL, STRIPE_PRICE_ID_ENTERPRISE_ANNUAL
"""
import os

import stripe

# Configurar Stripe con la secret key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

# IDs de precios mensuales
PRICE_IDS = {
    "pro": os.getenv("STRIPE_PRICE_ID_PRO", ""),
    "enterprise": os.getenv("STRIPE_PRICE_ID_ENTERPRISE", ""),
}

# IDs de precios anuales (20% de descuento vs mensual)
# Pro Annual: $279/ano (vs $348 = $29*12)
# Enterprise Annual: $949/ano (vs $1,188 = $99*12)
PRICE_IDS_ANNUAL = {
    "pro": os.getenv("STRIPE_PRICE_ID_PRO_ANNUAL", ""),
    "enterprise": os.getenv("STRIPE_PRICE_ID_ENTERPRISE_ANNUAL", ""),
}


def is_configured() -> bool:
    """Retorna True si Stripe tiene la API key configurada."""
    return bool(stripe.api_key)


def create_checkout_session(
    user_email: str,
    plan: str = "pro",
    billing_period: str = "monthly",
    success_url: str = "",
    cancel_url: str = "",
    user_id: str = "",
    is_first_subscription: bool = False,
) -> str:
    """Crea una sesion de Stripe Checkout. Retorna la URL de checkout.

    Si Stripe no esta configurado (sin API key o sin price ID),
    retorna cadena vacia.

    Args:
        user_email: Email del usuario (pre-rellena el campo en Stripe).
        plan: 'pro' o 'enterprise'.
        billing_period: 'monthly' o 'annual'. Selecciona el price ID correspondiente.
        success_url: URL de redireccion tras pago exitoso.
        cancel_url: URL de redireccion si cancela.
        user_id: ID de Supabase Auth del usuario (para vincular perfil).
        is_first_subscription: Si True y plan es 'pro', anade 14 dias de prueba gratis.
    """
    # Seleccionar price ID segun periodo de facturacion
    if billing_period == "annual":
        price_id = PRICE_IDS_ANNUAL.get(plan, "")
        # Fallback a mensual si no hay precio anual configurado
        if not price_id:
            price_id = PRICE_IDS.get(plan, PRICE_IDS.get("pro", ""))
    else:
        price_id = PRICE_IDS.get(plan, PRICE_IDS.get("pro", ""))

    if not price_id or not stripe.api_key:
        return ""  # Stripe no configurado

    # Configurar trial de 14 dias solo para Pro, primera suscripcion
    subscription_data = {}
    if is_first_subscription and plan == "pro":
        subscription_data["trial_period_days"] = 14

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer_email=user_email,
        client_reference_id=user_id or None,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url or "https://app.memedetector.es/?payment=success",
        cancel_url=cancel_url or "https://app.memedetector.es/?payment=cancelled",
        metadata={"plan": plan, "billing_period": billing_period},
        **({"subscription_data": subscription_data} if subscription_data else {}),
    )
    return session.url


def create_portal_session(stripe_customer_id: str) -> str:
    """Crea una sesion del Customer Portal de Stripe.

    Permite al usuario gestionar su suscripcion (cancelar, cambiar plan, etc.).
    Retorna la URL del portal, o cadena vacia si no esta configurado.
    """
    if not stripe.api_key or not stripe_customer_id:
        return ""

    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url="https://app.memedetector.es/",
    )
    return session.url


def get_subscription_status(stripe_subscription_id: str) -> dict:
    """Obtiene el estado actual de una suscripcion en Stripe.

    Retorna dict con status, current_period_end, cancel_at_period_end y plan.
    Si Stripe no esta configurado, retorna status 'unknown'.
    """
    if not stripe.api_key or not stripe_subscription_id:
        return {"status": "unknown"}

    sub = stripe.Subscription.retrieve(stripe_subscription_id)
    return {
        "status": sub.status,
        "current_period_end": sub.current_period_end,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "plan": sub.plan.id if sub.plan else None,
    }


def handle_webhook_event(
    payload: str, sig_header: str, webhook_secret: str
) -> dict:
    """Procesa un evento webhook de Stripe.

    Verifica la firma del webhook y retorna el evento parseado.
    Lanza stripe.error.SignatureVerificationError si la firma es invalida.
    """
    event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    return {
        "type": event.type,
        "data": event.data.object,
    }
