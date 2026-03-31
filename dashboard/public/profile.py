"""
profile.py — Perfil de usuario: gestiónar cuenta y suscripción.

Muestra información de la cuenta, permite editar el display name,
ver el estado de suscripción, la conexion con Telegram, y eliminar
la cuenta (zona de peligro).
"""

import logging
import streamlit as st

from src.data.supabase_storage import get_storage as _get_storage

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
        st.error("Se produjo un error inesperado. Inténtalo de nuevo.")
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

    Borra el perfil de la tabla profiles. La eliminación de auth.users
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
        st.error("Se produjo un error inesperado. Inténtalo de nuevo.")
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
    """Perfil de usuario — gestiónar cuenta y suscripción."""
    st.header(":material/person: Mi Perfil")

    # Obtener datos del usuario de session_state
    user = st.session_state.get("user", {})
    user_id = user.get("id")
    email = user.get("email", "—")
    role = st.session_state.get("role", "free")

    if not user_id:
        st.warning("No se encontro información de la sesión. Inicia sesión de nuevo.")
        st.stop()

    # Cargar perfil actualizado desde la base de datos
    profile = _load_profile(user_id)

    # -----------------------------------------------------------------
    # 1. Informacion de la cuenta
    # -----------------------------------------------------------------
    st.subheader("Cuenta")

    col_info1, col_info2 = st.columns(2)
    with col_info1:
        st.markdown(f"**Email:** {email}")
        badge = _ROLE_BADGES.get(role, "Free")
        st.markdown(f"**Plan actual:** {badge}")
    with col_info2:
        created_at = profile.get("created_at", "—")
        if created_at and created_at != "—":
            # Formatear fecha legible (quitar parte de tiempo si existe)
            fecha = str(created_at)[:10]
            st.markdown(f"**Miembro desde:** {fecha}")
        else:
            st.markdown("**Miembro desde:** —")

    st.divider()

    # -----------------------------------------------------------------
    # 2. Editar nombre de visualizacion
    # -----------------------------------------------------------------
    st.subheader("Nombre de visualizacion")
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

    st.divider()

    # -----------------------------------------------------------------
    # 3. Estado de suscripcion
    # -----------------------------------------------------------------
    st.subheader("Suscripcion")

    plan = profile.get("subscription_plan", "free")
    status = profile.get("subscription_status", "inactive")
    end_date = profile.get("subscription_end")

    plan_label = _PLAN_LABELS.get(plan, plan)
    status_label = "Activa" if status == "active" else "Inactiva"
    status_color = "green" if status == "active" else "gray"

    col_sub1, col_sub2 = st.columns(2)
    with col_sub1:
        st.markdown(f"**Plan:** {plan_label}")
        st.markdown(f"**Estado:** :{status_color}[{status_label}]")
    with col_sub2:
        if end_date:
            st.markdown(f"**Fecha de renovacion:** {str(end_date)[:10]}")
        else:
            st.markdown("**Fecha de renovacion:** —")

    st.write("")

    # CTA segun plan actual
    _stripe_ok = callable(_stripe_configured) and _stripe_configured()

    if plan == "free":
        st.info(
            "Estas en el plan gratuito. Suscribete a **Pro** para desbloquear "
            "todas las señales, busqueda de tokens, alertas Telegram y mas."
        )
        if _stripe_ok and _create_checkout is not None:
            try:
                checkout_url = _create_checkout(user_email=email, plan="pro")
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
                    "💳 Pagos próximamente. Contacta info@memedetector.es "
                    "para más información."
                )
        else:
            st.info(
                "💳 Pagos próximamente. Contacta info@memedetector.es "
                "para más información."
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
                    "Gestiónar suscripción (Stripe)",
                    portal_url,
                )
            else:
                st.caption("No se pudo generar el enlace al portal de Stripe.")
        else:
            st.caption(
                "Gestión de suscripción no disponible. "
                "Contacta info@memedetector.es."
            )

    st.divider()

    # -----------------------------------------------------------------
    # 4. Conexion con Telegram
    # -----------------------------------------------------------------
    st.subheader("Telegram")

    telegram_chat_id = profile.get("telegram_chat_id")

    if telegram_chat_id:
        st.success(f"Telegram conectado (Chat ID: `{telegram_chat_id}`)")
        st.page_link(
            "alerts",
            label="Configurar alertas de Telegram",
            icon=":material/notifications:",
        )
    else:
        st.warning(
            "Telegram no conectado. Conecta tu cuenta de Telegram para "
            "recibir señales y alertas directamente en tu móvil."
        )
        st.page_link(
            "alerts",
            label="Conectar Telegram",
            icon=":material/link:",
        )

    st.divider()

    # -----------------------------------------------------------------
    # 5. Zona de peligro
    # -----------------------------------------------------------------
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
