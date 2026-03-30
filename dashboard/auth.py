"""
auth.py - Autenticación y gestión de sesiones con Supabase Auth.

Provee funciones para login, registro, verificación de sesión,
y control de acceso basado en roles (admin/pro/free).

Usa SUPABASE_ANON_KEY (no service_role) porque Supabase Auth
requiere la anon key para operaciones de autenticación.

NOTA: Los emails de confirmacion y reset se configuran en:
Supabase Dashboard → Authentication → Email Templates
URL: https://supabase.com/dashboard/project/xayfwuqbbqtyerxzjbec/auth/templates
"""
import logging
import os
import time

import streamlit as st
from supabase import create_client, Client

from dashboard.i18n import t

logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    """Crea cliente Supabase con ANON key (para auth).

    La anon key es la correcta para Auth — service_role
    bypassea RLS y no debe usarse en el cliente.
    Retorna None si las variables de entorno no estan configuradas.
    """
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        st.error("SUPABASE_URL o SUPABASE_ANON_KEY no configuradas.")
        return None
    return create_client(url, key)


def init_session_state():
    """Inicializa variables de sesión para auth.

    Se llama al principio de cada request de Streamlit
    para asegurar que todas las keys existan en session_state.
    """
    defaults = {
        "authenticated": False,
        "user": None,          # dict con id, email
        "role": "free",        # admin, pro, free
        "profile": None,       # dict completo del profile
        "access_token": None,
        "login_time": 0,       # timestamp del ultimo login/refresh
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def login(email: str, password: str) -> bool:
    """Login con Supabase Auth. Retorna True si exitoso.

    Usa sign_in_with_password que valida credenciales contra
    la tabla auth.users de Supabase. Si el login es exitoso,
    carga el perfil del usuario desde la tabla 'profiles'.

    Incluye rate limiting exponencial basado en session_state:
    tras 5 fallos consecutivos, se bloquea con backoff creciente.
    """
    # --- Rate limiting: bloquear tras demasiados intentos fallidos ---
    failures = st.session_state.get("login_failures", 0)
    last_fail = st.session_state.get("last_failure_time", 0)
    if failures >= 5:
        wait = min(2 ** (failures - 4), 300)
        elapsed = time.time() - last_fail
        if elapsed < wait:
            st.error(f"Demasiados intentos. Espera {int(wait - elapsed)} segundos.")
            return False

    client = get_supabase_client()
    if not client:
        return False
    try:
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        user = response.user
        session = response.session

        st.session_state.authenticated = True
        st.session_state.user = {"id": user.id, "email": user.email}
        st.session_state.access_token = session.access_token
        st.session_state.login_time = time.time()

        # Reset rate limiting on success
        st.session_state.login_failures = 0

        # Cargar perfil (role, subscription, etc.)
        _load_profile(client, user.id)
        return True
    except Exception as e:
        # Incrementar contador de fallos para rate limiting
        st.session_state.login_failures = st.session_state.get("login_failures", 0) + 1
        st.session_state.last_failure_time = time.time()

        error_msg = str(e)
        if "Invalid login" in error_msg or "invalid" in error_msg.lower():
            st.error(t("auth.error_invalid_credentials", "Email o contraseña incorrectos."))
        else:
            logger.exception("Error de autenticacion en login")
            st.error("Se produjo un error inesperado. Inténtalo de nuevo.")
        return False


def register(email: str, password: str) -> bool:
    """Registro con Supabase Auth. Retorna True si exitoso.

    Crea un nuevo usuario en auth.users. Supabase puede enviar
    un email de confirmacion dependiendo de la config del proyecto.
    El perfil en 'profiles' se crea automáticamente via trigger SQL.
    """
    client = get_supabase_client()
    if not client:
        return False
    try:
        response = client.auth.sign_up({
            "email": email,
            "password": password
        })
        if response.user:
            st.success(t("auth.register_success",
                         "Cuenta creada. Revisa tu email para confirmar "
                         "y luego ya puedes iniciar sesión."))
            return True
        return False
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower():
            st.error(t("auth.error_already_registered",
                        "Este email ya esta registrado. Intenta iniciar sesión."))
        else:
            logger.exception("Error en registro de usuario")
            st.error("Se produjo un error inesperado. Inténtalo de nuevo.")
        return False


def logout():
    """Cierra sesión limpiando todo el session_state de auth."""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.role = "free"
    st.session_state.profile = None
    st.session_state.access_token = None
    st.session_state.login_time = 0


def _load_profile(client: Client, user_id: str):
    """Carga el perfil del usuario (role, subscription, etc.).

    Consulta la tabla 'profiles' por el user_id.
    Si el perfil no existe aun (puede haber delay en el trigger),
    se asigna el rol 'free' por defecto.
    """
    try:
        response = (
            client.table("profiles")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
        profile = response.data
        st.session_state.profile = profile
        st.session_state.role = profile.get("role", "free")
    except Exception:
        # El perfil puede no existir aun (delay del trigger)
        # o la tabla profiles puede no haberse creado todavia
        st.session_state.role = "free"


def is_authenticated() -> bool:
    """Verifica si el usuario esta autenticado."""
    return st.session_state.get("authenticated", False)


def is_admin() -> bool:
    """Verifica si el usuario es admin."""
    return st.session_state.get("role") == "admin"


def is_pro() -> bool:
    """Verifica si el usuario es pro o admin.

    Los admins tienen acceso a todo lo que tiene pro,
    por eso se incluyen en esta verificacion.
    """
    return st.session_state.get("role") in ("pro", "admin")


def _check_session_freshness():
    """Refresh Supabase token if it's about to expire (50+ min old).

    Los tokens de Supabase expiran por defecto en 1 hora.
    Si el login_time tiene mas de 50 minutos, intentamos refrescar.
    Si falla, forzamos re-login limpiando el session_state.
    """
    login_time = st.session_state.get("login_time", 0)
    if not login_time or time.time() - login_time <= 3000:
        return  # Token aun fresco (< 50 min)

    try:
        client = get_supabase_client()
        if not client:
            return
        response = client.auth.refresh_session()
        if response and response.session:
            st.session_state.access_token = response.session.access_token
            st.session_state.login_time = time.time()
    except Exception as e:
        logger.warning(f"Session refresh failed: {e}")
        # Force re-login
        for key in ["authenticated", "user", "access_token", "login_time"]:
            st.session_state.pop(key, None)
        st.rerun()


def require_auth():
    """Muestra login si no autenticado. Llama st.stop() si no pasa.

    Usar al inicio de cualquier pagina que requiera autenticacion:
        from auth import require_auth
        require_auth()
        # ... resto de la pagina
    """
    init_session_state()
    if is_authenticated():
        _check_session_freshness()
        return
    render_login_page()
    st.stop()


def require_admin():
    """Verifica que el usuario sea admin. Redirige a overview si no.

    Primero verifica autenticación, luego verifica rol.
    Si el usuario no es admin, muestra las páginas públicas disponibles.
    """
    require_auth()
    if not is_admin():
        st.info(t("access.admin_required", "Bienvenido. Usa el menú lateral para navegar por las secciones disponibles."))
        st.markdown("### Páginas disponibles")
        st.markdown("""
        - 📊 **Resumen** — Estadísticas del mercado
        - 📈 **Señales** — Tokens con mayor potencial
        - 🔍 **Buscar Token** — Analizar cualquier token
        - ⭐ **Watchlist** — Tus tokens favoritos
        - 🎓 **Academia** — Aprende sobre memecoins
        """)
        st.stop()


def require_pro():
    """Verifica que el usuario sea pro o admin.

    Muestra un mensaje con link de suscripción si el usuario
    no tiene el plan adecuado.
    """
    require_auth()
    if not is_pro():
        st.warning(t("paywall.requires_pro_generic", "Esta función requiere suscripción Pro."))
        st.markdown(f"[{t('paywall.subscribe_link', 'Suscribirse →')}](#)")  # TODO: Link a Stripe
        st.stop()


def reset_password(email: str) -> bool:
    """Envia email de restablecimiento de contraseña via Supabase Auth.

    Retorna True si el email se envio correctamente (o si Supabase
    no reporta error, por seguridad no revela si el email existe).
    """
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.auth.reset_password_email(email)
        return True
    except Exception as e:
        logger.exception("Error al enviar email de recuperacion de contrasena")
        st.error("Se produjo un error inesperado. Inténtalo de nuevo.")
        return False


def render_login_page():
    """Renderiza la pagina de login/registro con tabs.

    Incluye validación de campos, confirmacion de contraseña
    en registro, longitud minima de contraseña (6 chars),
    recuperacion de contraseña y aviso de terminos de servicio.
    """
    st.title(t("auth.login_title", "🔒 Trading Memes"))
    st.markdown(t("auth.login_subtitle", "Detector de Gems en Memecoins con Machine Learning"))

    tab_login, tab_register = st.tabs([
        t("auth.tab_login", "Iniciar Sesión"),
        t("auth.tab_register", "Crear Cuenta"),
    ])

    with tab_login:
        # --- Formulario de login ---
        email = st.text_input(t("auth.email", "Email"), key="login_email")
        password = st.text_input(
            t("auth.password", "Contraseña"), type="password", key="login_password"
        )
        if st.button(t("auth.login_btn", "Acceder"), type="primary", key="btn_login"):
            if email and password:
                if login(email, password):
                    st.rerun()
            else:
                st.warning(t("auth.error_empty_fields", "Introduce email y contraseña."))

        # --- Recuperar contrasena ---
        st.markdown("---")
        with st.expander(t("auth.forgot_password", "¿Olvidaste tu contraseña?")):
            reset_email = st.text_input(
                t("auth.reset_email_label",
                  "Introduce tu email para restablecer la contraseña"),
                key="reset_email",
            )
            if st.button(t("auth.reset_btn", "Enviar enlace de recuperacion"), key="btn_reset"):
                if reset_email:
                    if reset_password(reset_email):
                        st.success(t("auth.reset_success",
                                     "Te hemos enviado un email para restablecer "
                                     "tu contraseña. Revisa tu bandeja de entrada."))
                else:
                    st.warning(t("auth.error_empty_email", "Introduce tu email."))

    with tab_register:
        reg_email = st.text_input(t("auth.email", "Email"), key="reg_email")
        reg_pass = st.text_input(
            t("auth.password", "Contraseña"), type="password", key="reg_password",
            help=t("auth.password_hint",
                   "Minimo 8 caracteres, al menos una mayúscula y un número"),
        )
        st.caption(t("auth.password_hint",
                      "Minimo 8 caracteres, al menos una mayúscula y un número"))
        reg_pass2 = st.text_input(
            t("auth.confirm_password", "Confirmar contraseña"),
            type="password", key="reg_password2",
        )
        if st.button(t("auth.register_btn", "Crear cuenta"), type="primary", key="btn_register"):
            if not reg_email or not reg_pass:
                st.warning(t("auth.error_fill_all", "Completa todos los campos."))
            elif reg_pass != reg_pass2:
                st.error(t("auth.error_password_mismatch", "Las contraseñas no coinciden."))
            elif len(reg_pass) < 8:
                st.error(t("auth.error_password_length",
                           "La contraseña debe tener al menos 8 caracteres."))
            elif not any(c.isupper() for c in reg_pass):
                st.error(t("auth.error_password_uppercase",
                           "La contraseña debe contener al menos una mayúscula."))
            elif not any(c.isdigit() for c in reg_pass):
                st.error(t("auth.error_password_digit",
                           "La contraseña debe contener al menos un número."))
            else:
                register(reg_email, reg_pass)

        # Aviso de terminos de servicio
        st.caption(t("auth.tos_notice",
                      "Al crear tu cuenta aceptas los Terminos de Servicio."))


def render_sidebar_user_info():
    """Muestra info del usuario en el sidebar + boton logout.

    Incluye email, badge del plan (Admin/Pro/Free),
    Pro member since + dias hasta renovacion,
    y boton para cerrar sesion.
    """
    if is_authenticated():
        user = st.session_state.get("user", {})
        role = st.session_state.get("role", "free")
        profile = st.session_state.get("profile", {}) or {}

        plan = profile.get("subscription_plan", role)

        role_badges = {
            "admin": f"🔴 {t('roles.admin', 'Admin')}",
            "pro": f"🟢 {t('roles.pro', 'Pro')}",
            "free": f"⚪ {t('roles.free', 'Free')}",
        }
        badge = role_badges.get(role, f"⚪ {t('roles.free', 'Free')}")

        st.sidebar.markdown(f"**{user.get('email', '')}**")

        # Pro/Admin: badge prominente con estilo
        if role in ("pro", "admin"):
            badge_color = "#2ecc71" if role == "pro" else "#e74c3c"
            badge_text = t('roles.pro', 'Pro') if role == "pro" else t('roles.admin', 'Admin')
            st.sidebar.markdown(
                f"<div style='background-color:{badge_color}; color:white; "
                f"padding:6px 12px; border-radius:8px; text-align:center; "
                f"font-weight:bold; margin:4px 0 8px 0;'>"
                f"{badge_text}</div>",
                unsafe_allow_html=True,
            )

            # Pro member since (si hay created_at en el profile)
            sub_start = profile.get("subscription_start") or profile.get("created_at")
            if sub_start and role == "pro":
                try:
                    from datetime import datetime
                    if isinstance(sub_start, str):
                        sub_date = datetime.fromisoformat(
                            sub_start.replace("Z", "+00:00")
                        )
                    else:
                        sub_date = sub_start
                    st.sidebar.caption(
                        f"{t('pro.member_since', 'Miembro Pro desde')}: "
                        f"{sub_date.strftime('%d/%m/%Y')}"
                    )
                except Exception:
                    pass

            # Dias hasta renovacion (si hay subscription_end)
            sub_end = profile.get("subscription_end")
            if sub_end and role == "pro":
                try:
                    from datetime import datetime, timezone
                    if isinstance(sub_end, str):
                        end_date = datetime.fromisoformat(
                            sub_end.replace("Z", "+00:00")
                        )
                    else:
                        end_date = sub_end
                    now = datetime.now(timezone.utc)
                    if not hasattr(end_date, "tzinfo") or end_date.tzinfo is None:
                        from datetime import timezone as tz
                        end_date = end_date.replace(tzinfo=tz.utc)
                    days_left = (end_date - now).days
                    if days_left > 0:
                        st.sidebar.caption(
                            f"{t('pro.renewal_in', 'Renovacion en')}: "
                            f"{days_left} {t('pro.days', 'dias')}"
                        )
                    elif days_left == 0:
                        st.sidebar.caption(
                            t("pro.renews_today", "Se renueva hoy")
                        )
                except Exception:
                    pass
        else:
            # Free: mostrar badge simple
            st.sidebar.markdown(f"{t('roles.plan_label', 'Plan')}: {badge}")

        if st.sidebar.button(f"🔓 {t('app.logout', 'Cerrar sesion')}"):
            logout()
            st.rerun()
