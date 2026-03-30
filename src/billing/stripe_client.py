"""
stripe_client.py — Integracion con Stripe para pagos y suscripciones.

Requiere: pip install stripe
Env vars: STRIPE_SECRET_KEY, STRIPE_PRICE_ID_PRO, STRIPE_PRICE_ID_ENTERPRISE
"""
import os

import stripe

# Configurar Stripe con la secret key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

PRICE_IDS = {
    "pro": os.getenv("STRIPE_PRICE_ID_PRO", ""),
    "enterprise": os.getenv("STRIPE_PRICE_ID_ENTERPRISE", ""),
}


def is_configured() -> bool:
    """Retorna True si Stripe tiene la API key configurada."""
    return bool(stripe.api_key)


def create_checkout_session(
    user_email: str,
    plan: str = "pro",
    success_url: str = "",
    cancel_url: str = "",
) -> str:
    """Crea una sesion de Stripe Checkout. Retorna la URL de checkout.

    Si Stripe no esta configurado (sin API key o sin price ID),
    retorna cadena vacia.
    """
    price_id = PRICE_IDS.get(plan, PRICE_IDS["pro"])
    if not price_id or not stripe.api_key:
        return ""  # Stripe no configurado

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer_email=user_email,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url or "https://app.memedetector.es/?payment=success",
        cancel_url=cancel_url or "https://app.memedetector.es/?payment=cancelled",
        metadata={"plan": plan},
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
