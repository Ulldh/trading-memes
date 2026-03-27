"""
profile.py — Perfil de usuario: gestionar cuenta y suscripcion.

Muestra informacion de la cuenta, permite editar el display name,
ver el estado de suscripcion, la conexion con Telegram, y eliminar
la cuenta (zona de peligro).
"""

import streamlit as st

from src.data.supabase_storage import get_storage as _get_storage


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
        st.error(f"Error al guardar el nombre: {e}")
        return False


def _delete_user_account(user_id: str) -> bool:
    """Elimina la cuenta del usuario.

    Borra el perfil de la tabla profiles. La eliminacion de auth.users
    debe hacerse via Supabase Admin o un edge function con service_role.
    Retorna True si la operacion fue exitosa.
    """
    try:
        storage = _get_db()
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
        st.error(f"Error al eliminar la cuenta: {e}")
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
    """Perfil de usuario — gestionar cuenta y suscripcion."""
    st.header(":material/person: Mi Perfil")

    # Obtener datos del usuario de session_state
    user = st.session_state.get("user", {})
    user_id = user.get("id")
    email = user.get("email", "—")
    role = st.session_state.get("role", "free")

    if not user_id:
        st.warning("No se encontro informacion de la sesion. Inicia sesion de nuevo.")
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
    if plan == "free":
        st.info(
            "Estas en el plan gratuito. Suscribete a **Pro** para desbloquear "
            "todas las senales, busqueda de tokens, alertas Telegram y mas."
        )
        # TODO: Reemplazar con URL real de Stripe Checkout cuando este listo
        stripe_url = st.session_state.get("stripe_checkout_url", "#")
        st.link_button(
            "Mejorar a Pro — $29/mes",
            stripe_url,
            type="primary",
        )
    elif plan in ("pro", "enterprise"):
        st.success(f"Tienes el plan **{plan_label}** activo.")
        # TODO: Reemplazar con URL real del portal de Stripe
        portal_url = st.session_state.get("stripe_portal_url", "#")
        st.link_button(
            "Gestionar suscripcion (Stripe)",
            portal_url,
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
            "dashboard/public/alerts_config.py",
            label="Configurar alertas de Telegram",
            icon=":material/notifications:",
        )
    else:
        st.warning(
            "Telegram no conectado. Conecta tu cuenta de Telegram para "
            "recibir senales y alertas directamente en tu movil."
        )
        st.page_link(
            "dashboard/public/alerts_config.py",
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
            "y perfil. Tu suscripcion activa (si la hay) no se cancelara "
            "automaticamente en Stripe — contacta a info@memedetector.es "
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
