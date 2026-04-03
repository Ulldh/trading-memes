"""
profile.py — Perfil de usuario: gestionar cuenta y suscripcion.

Muestra informacion de la cuenta con estilo premium de trading terminal.
Permite editar el display name, ver el estado de suscripcion,
la conexion con Telegram, y eliminar la cuenta (zona de peligro).

Estilo premium coherente con la paleta terminal (#00ff41).
"""

import logging
import streamlit as st

from src.data.supabase_storage import get_storage as _get_storage
from dashboard.theme import (
    role_badge_html, card_container,
    ACCENT, GOLD, BG_CARD, BG_SURFACE, BORDER, TEXT_MUTED, DANGER,
)

# Importar stripe_client con try/except (las keys pueden no estar configuradas)
try:
    from src.billing.stripe_client import (
        create_checkout_session as _create_checkout,
        create_portal_session as _create_portal,
        is_configured as _stripe_configured,
    )
except Exception:
    _create_checkout = None  # type: ignore[assignment]
    _create_portal = None  # type: ignore[assignment]
    _stripe_configured = lambda: False  # noqa: E731

# Importar stripe directamente para cancelar suscripciones en eliminacion de cuenta
try:
    import stripe as _stripe_lib
except Exception:
    _stripe_lib = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

@st.cache_resource
def _get_db():
    """Instancia de storage cacheada."""
    return _get_storage()


def _load_profile(user_id: str) -> dict:
    """Carga el perfil del usuario desde Supabase.

    Retorna dict con los campos de la tabla profiles,
    o dict vacio si no se encuentra.
    """
    try:
        storage = _get_db()
        df = storage.query(
            "SELECT * FROM profiles WHERE id = ?", (user_id,)
        )
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception:
        pass
    return {}


def _update_display_name(user_id: str, new_name: str) -> bool:
    """Actualiza el display_name en la tabla profiles.

    Returns:
        True si se actualizo correctamente, False en caso de error.
    """
    try:
        storage = _get_db()
        storage.execute(
            "UPDATE profiles SET display_name = ? WHERE id = ?",
            (new_name.strip(), user_id),
        )
        return True
    except Exception as e:
        logger.exception("Error al guardar display_name en perfil")
        st.error("Se produjo un error inesperado. Intentalo de nuevo.")
        return False


def _cancel_stripe_subscriptions(stripe_customer_id: str) -> None:
    """Cancela todas las suscripciones activas de un cliente en Stripe.

    Si Stripe no esta configurado o la llamada falla, solo loguea un
    warning sin bloquear la eliminacion de la cuenta.
    """
    if not _stripe_lib or not stripe_customer_id:
        return
    if not callable(_stripe_configured) or not _stripe_configured():
        return

    try:
        subscriptions = _stripe_lib.Subscription.list(
            customer=stripe_customer_id,
            status="active",
        )
        for sub in subscriptions.auto_paging_iter():
            try:
                _stripe_lib.Subscription.cancel(sub.id)
                logger.info("Stripe subscription %s cancelled for customer %s", sub.id, stripe_customer_id)
            except Exception as e:
                logger.warning("Failed to cancel Stripe subscription %s: %s", sub.id, e)
    except Exception as e:
        logger.warning("Failed to list Stripe subscriptions for customer %s: %s", stripe_customer_id, e)


def _delete_user_account(user_id: str) -> bool:
    """Elimina la cuenta del usuario.

    Borra el perfil de la tabla profiles. La eliminacion de auth.users
    debe hacerse via Supabase Admin o un edge function con service_role.
    Cancela suscripciones activas en Stripe antes de eliminar.
    Retorna True si la operacion fue exitosa.
    """
    try:
        storage = _get_db()

        # Cancelar suscripciones Stripe antes de eliminar el perfil
        try:
            profile = _load_profile(user_id)
            stripe_customer_id = profile.get("stripe_customer_id", "")
            if stripe_customer_id:
                _cancel_stripe_subscriptions(stripe_customer_id)
        except Exception as e:
            logger.warning("Could not cancel Stripe subscriptions during account deletion: %s", e)

        # Eliminar datos asociados (watchlist, alertas, etc.)
        for table in ("watchlist", "alert_preferences"):
            try:
                storage.execute(
                    f"DELETE FROM {table} WHERE user_id = ?", (user_id,)
                )
            except Exception:
                pass  # La tabla puede no existir todavia
        # Eliminar perfil
        storage.execute("DELETE FROM profiles WHERE id = ?", (user_id,))
        return True
    except Exception as e:
        logger.exception("Error al eliminar la cuenta del usuario")
        st.error("Se produjo un error inesperado. Intentalo de nuevo.")
        return False


# ============================================================
# BADGES Y MAPEOS
# ============================================================

_ROLE_BADGES = {
    "admin": ":red[Admin]",
    "pro": ":green[Pro]",
    "free": "Free",
}

_PLAN_LABELS = {
    "free": "Gratuito",
    "pro": "Pro ($29/mes)",
    "enterprise": "Enterprise ($99/mes)",
}


# ============================================================
# RENDER
# ============================================================

def render():
    """Perfil de usuario — gestionar cuenta y suscripcion con estilo premium."""

    # Obtener datos del usuario de session_state
    user = st.session_state.get("user", {})
    user_id = user.get("id")
    email = user.get("email", "")
    role = st.session_state.get("role", "free")

    if not user_id:
        st.warning("No se encontro informacion de la sesion. Inicia sesion de nuevo.")
        st.stop()

    # Cargar perfil actualizado desde la base de datos
    profile = _load_profile(user_id)
    display_name = profile.get("display_name", "")

    # Obtener iniciales para el avatar
    if display_name:
        initials = display_name[:2].upper()
    elif email:
        initials = email[:2].upper()
    else:
        initials = "U"

    # Color del rol
    role_colors = {"admin": DANGER, "pro": ACCENT, "free": TEXT_MUTED}
    rc = role_colors.get(role, TEXT_MUTED)

    # -----------------------------------------------------------------
    # 1. Header con avatar premium y datos principales
    # -----------------------------------------------------------------
    user_display = display_name or (email.split('@')[0] if email else 'User')

    st.markdown(
        f"<div style='display: flex; align-items: center; gap: 24px; "
        f"margin-bottom: 28px; padding: 28px; "
        f"background: linear-gradient(135deg, rgba(13,17,23,0.95), rgba(22,27,34,0.95)); "
        f"border: 1px solid rgba(0,255,65,0.06); border-radius: 20px; "
        f"backdrop-filter: blur(10px); "
        f"box-shadow: 0 4px 30px rgba(0,0,0,0.2);'>"
        # Avatar circular con gradient border y glow
        f"<div style='width: 80px; height: 80px; border-radius: 50%; "
        f"background: linear-gradient(135deg, {rc}20, {rc}08); "
        f"border: 3px solid {rc}40; "
        f"display: flex; align-items: center; justify-content: center; "
        f"flex-shrink: 0; box-shadow: 0 0 25px {rc}15;'>"
        f"<span style='color: {rc}; font-weight: 800; "
        f"font-size: 1.6rem;'>{initials}</span>"
        f"</div>"
        # Info
        f"<div style='flex: 1;'>"
        f"<h2 style='margin: 0 0 6px 0; font-weight: 800; font-size: 1.6rem; "
        f"color: #ffffff; letter-spacing: -0.3px;'>{user_display}</h2>"
        f"<span style='color: {TEXT_MUTED}; font-size: 0.85rem;'>{email}</span>"
        f"</div>"
        # Role badge
        f"<div>"
        f"<span style='background: linear-gradient(135deg, {rc}12, {rc}06); "
        f"color: {rc}; padding: 6px 20px; border-radius: 20px; "
        f"font-weight: 800; font-size: 0.75rem; "
        f"border: 1px solid {rc}25; letter-spacing: 1.5px; "
        f"text-transform: uppercase;'>"
        f"{role.upper()}</span>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Fecha de miembro
    created_at = profile.get("created_at", "")
    if created_at:
        fecha = str(created_at)[:10]
        st.caption(f"Miembro desde: {fecha}")

    # -----------------------------------------------------------------
    # 2. Editar nombre de visualizacion — seccion con card
    # -----------------------------------------------------------------
    st.markdown(
        f"<div style='display: flex; align-items: center; gap: 8px; "
        f"margin: 20px 0 8px 0;'>"
        f"<div style='width: 6px; height: 6px; border-radius: 50%; "
        f"background: {ACCENT}; box-shadow: 0 0 8px {ACCENT}60;'></div>"
        f"<h4 style='margin: 0; font-weight: 700;'>Nombre de visualizacion</h4>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.caption("Este nombre se mostrara en tu perfil y en el dashboard.")

    current_name = profile.get("display_name", "")
    new_name = st.text_input(
        "Display name",
        value=current_name or "",
        max_chars=50,
        label_visibility="collapsed",
        placeholder="Tu nombre o alias",
    )

    if st.button("Guardar nombre", type="primary", key="btn_save_name"):
        if new_name.strip():
            if _update_display_name(user_id, new_name):
                st.success("Nombre actualizado correctamente.")
                # Actualizar profile en session_state
                if st.session_state.get("profile"):
                    st.session_state.profile["display_name"] = new_name.strip()
        else:
            st.warning("El nombre no puede estar vacio.")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # -----------------------------------------------------------------
    # 3. Estado de suscripcion — card premium
    # -----------------------------------------------------------------
    st.markdown(
        f"<div style='display: flex; align-items: center; gap: 8px; "
        f"margin: 12px 0 8px 0;'>"
        f"<div style='width: 6px; height: 6px; border-radius: 50%; "
        f"background: {ACCENT}; box-shadow: 0 0 8px {ACCENT}60;'></div>"
        f"<h4 style='margin: 0; font-weight: 700;'>Suscripcion</h4>"
        f"</div>",
        unsafe_allow_html=True,
    )

    plan = profile.get("subscription_plan", "free")
    status = profile.get("subscription_status", "inactive")
    end_date = profile.get("subscription_end")

    plan_label = _PLAN_LABELS.get(plan, plan)
    status_label = "Activa" if status == "active" else "Inactiva"
    status_color = ACCENT if status == "active" else TEXT_MUTED

    # Card de suscripcion
    st.markdown(
        f"<div style='"
        f"background: linear-gradient(135deg, rgba(13,17,23,0.95), rgba(22,27,34,0.95)); "
        f"border: 1px solid rgba(0,255,65,0.06); border-radius: 16px; "
        f"padding: 24px; margin: 8px 0;'>"
        f"<div style='display: flex; justify-content: space-between; align-items: flex-start; "
        f"flex-wrap: wrap; gap: 16px;'>"
        # Plan
        f"<div>"
        f"<div style='color: {TEXT_MUTED}; font-size: 0.7rem; "
        f"text-transform: uppercase; letter-spacing: 1px; font-weight: 600; "
        f"margin-bottom: 4px;'>Plan</div>"
        f"<div style='color: #ffffff; font-size: 1.2rem; font-weight: 800;'>"
        f"{plan_label}</div>"
        f"</div>"
        # Estado
        f"<div>"
        f"<div style='color: {TEXT_MUTED}; font-size: 0.7rem; "
        f"text-transform: uppercase; letter-spacing: 1px; font-weight: 600; "
        f"margin-bottom: 4px;'>Estado</div>"
        f"<div style='display: flex; align-items: center; gap: 6px;'>"
        f"<div style='width: 8px; height: 8px; border-radius: 50%; "
        f"background: {status_color}; box-shadow: 0 0 8px {status_color}40;'></div>"
        f"<span style='color: {status_color}; font-weight: 700;'>{status_label}</span>"
        f"</div></div>"
        # Renovacion
        f"<div>"
        f"<div style='color: {TEXT_MUTED}; font-size: 0.7rem; "
        f"text-transform: uppercase; letter-spacing: 1px; font-weight: 600; "
        f"margin-bottom: 4px;'>Renovacion</div>"
        f"<div style='color: #ffffff; font-weight: 700;'>"
        f"{str(end_date)[:10] if end_date else '&#8212;'}</div>"
        f"</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    st.write("")

    # CTA segun plan actual
    _stripe_ok = callable(_stripe_configured) and _stripe_configured()

    if plan == "free":
        st.info(
            "Estas en el plan gratuito. Suscribete a **Pro** para desbloquear "
            "todas las senales, busqueda de tokens, alertas Telegram y mas."
        )
        if _stripe_ok and _create_checkout is not None:
            try:
                checkout_url = _create_checkout(user_email=email, plan="pro", user_id=user_id or "")
            except Exception:
                checkout_url = ""
            if checkout_url:
                st.link_button(
                    "Mejorar a Pro — $29/mes",
                    checkout_url,
                    type="primary",
                )
            else:
                st.info(
                    "Pagos proximamente. Contacta info@memedetector.es "
                    "para mas informacion."
                )
        else:
            st.info(
                "Pagos proximamente. Contacta info@memedetector.es "
                "para mas informacion."
            )
    elif plan in ("pro", "enterprise"):
        st.success(f"Tienes el plan **{plan_label}** activo.")
        stripe_customer_id = profile.get("stripe_customer_id", "")
        if _stripe_ok and _create_portal is not None and stripe_customer_id:
            try:
                portal_url = _create_portal(stripe_customer_id)
            except Exception:
                portal_url = ""
            if portal_url:
                st.link_button(
                    "Gestionar suscripcion (Stripe)",
                    portal_url,
                )
            else:
                st.caption("No se pudo generar el enlace al portal de Stripe.")
        else:
            st.caption(
                "Gestion de suscripcion no disponible. "
                "Contacta info@memedetector.es."
            )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # -----------------------------------------------------------------
    # 4. Conexion con Telegram — seccion premium
    # -----------------------------------------------------------------
    st.markdown(
        f"<div style='display: flex; align-items: center; gap: 8px; "
        f"margin: 12px 0 8px 0;'>"
        f"<div style='width: 6px; height: 6px; border-radius: 50%; "
        f"background: {ACCENT}; box-shadow: 0 0 8px {ACCENT}60;'></div>"
        f"<h4 style='margin: 0; font-weight: 700;'>Telegram</h4>"
        f"</div>",
        unsafe_allow_html=True,
    )

    telegram_chat_id = profile.get("telegram_chat_id")

    if telegram_chat_id:
        st.markdown(
            f"<div style='"
            f"background: linear-gradient(135deg, rgba(0,255,65,0.04), rgba(0,255,65,0.02)); "
            f"border: 1px solid rgba(0,255,65,0.1); border-radius: 12px; "
            f"padding: 14px 18px; margin: 8px 0;'>"
            f"<div style='display: flex; align-items: center; gap: 8px;'>"
            f"<div style='width: 8px; height: 8px; border-radius: 50%; "
            f"background: {ACCENT}; box-shadow: 0 0 8px {ACCENT}60;'></div>"
            f"<span style='color: {ACCENT}; font-weight: 700;'>Conectado</span>"
            f"<span style='color: {TEXT_MUTED}; font-size: 0.8rem; margin-left: 8px;'>"
            f"Chat ID: {telegram_chat_id}</span>"
            f"</div></div>",
            unsafe_allow_html=True,
        )
        st.page_link(
            "alerts",
            label="Configurar alertas de Telegram",
            icon=":material/notifications:",
        )
    else:
        st.markdown(
            f"<div style='"
            f"background: linear-gradient(135deg, rgba(251,191,36,0.04), rgba(251,191,36,0.02)); "
            f"border: 1px solid rgba(251,191,36,0.1); border-radius: 12px; "
            f"padding: 14px 18px; margin: 8px 0;'>"
            f"<div style='display: flex; align-items: center; gap: 8px;'>"
            f"<div style='width: 8px; height: 8px; border-radius: 50%; "
            f"background: {GOLD}; box-shadow: 0 0 8px {GOLD}60;'></div>"
            f"<span style='color: {GOLD}; font-weight: 700;'>No conectado</span>"
            f"</div>"
            f"<p style='color: {TEXT_MUTED}; font-size: 0.8rem; margin: 8px 0 0 0;'>"
            f"Conecta tu cuenta de Telegram para recibir senales y alertas "
            f"directamente en tu movil.</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.page_link(
            "alerts",
            label="Conectar Telegram",
            icon=":material/link:",
        )

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    # -----------------------------------------------------------------
    # 5. Zona de peligro — estilo rojo premium con borde de advertencia
    # -----------------------------------------------------------------
    st.markdown(
        f"<div style='border: 1px solid rgba(239,68,68,0.15); border-radius: 16px; "
        f"padding: 2px; margin-top: 8px; "
        f"background: linear-gradient(135deg, rgba(239,68,68,0.02), transparent);'>",
        unsafe_allow_html=True,
    )
    with st.expander(":material/warning: Zona de peligro", expanded=False):
        st.markdown(
            "**Eliminar cuenta**: esta accion es irreversible. Se eliminaran "
            "todos tus datos, incluyendo watchlists, preferencias de alertas "
            "y perfil. Si tienes una suscripcion activa en Stripe, se "
            "cancelara automaticamente. Contacta info@memedetector.es "
            "si necesitas un reembolso."
        )

        # Doble confirmacion: checkbox + boton
        confirm = st.checkbox(
            "Entiendo que esta accion es irreversible y quiero eliminar mi cuenta",
            key="confirm_delete",
        )

        if st.button(
            "Eliminar mi cuenta",
            type="primary",
            disabled=not confirm,
            key="btn_delete_account",
        ):
            # Segunda confirmacion con dialog/warning
            if "delete_confirmed" not in st.session_state:
                st.session_state.delete_confirmed = False

            if not st.session_state.delete_confirmed:
                st.session_state.delete_confirmed = True
                st.warning(
                    "Haz clic de nuevo en 'Eliminar mi cuenta' para confirmar "
                    "definitivamente."
                )
                st.rerun()
            else:
                # Ejecutar eliminacion
                if _delete_user_account(user_id):
                    st.success("Cuenta eliminada. Redirigiendo...")
                    # Limpiar sesion
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()
                else:
                    st.session_state.delete_confirmed = False
    # Cerrar div del borde rojo de zona de peligro
    st.markdown("</div>", unsafe_allow_html=True)
