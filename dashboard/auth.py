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
import os
import streamlit as st
from supabase import create_client, Client

from dashboard.i18n import t


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
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def login(email: str, password: str) -> bool:
    """Login con Supabase Auth. Retorna True si exitoso.

    Usa sign_in_with_password que valida credenciales contra
    la tabla auth.users de Supabase. Si el login es exitoso,
    carga el perfil del usuario desde la tabla 'profiles'.
    """
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

        # Cargar perfil (role, subscription, etc.)
        _load_profile(client, user.id)
        return True
    except Exception as e:
        error_msg = str(e)
        if "Invalid login" in error_msg or "invalid" in error_msg.lower():
            st.error(t("auth.error_invalid_credentials", "Email o contraseña incorrectos."))
        else:
            st.error(f"{t('auth.error_auth', 'Error de autenticación')}: {error_msg}")
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
            st.error(f"{t('auth.error_register', 'Error en registro')}: {error_msg}")
        return False


def logout():
    """Cierra sesión limpiando todo el session_state de auth."""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.role = "free"
    st.session_state.profile = None
    st.session_state.access_token = None


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


def require_auth():
    """Muestra login si no autenticado. Llama st.stop() si no pasa.

    Usar al inicio de cualquier pagina que requiera autenticacion:
        from auth import require_auth
        require_auth()
        # ... resto de la pagina
    """
    init_session_state()
    if is_authenticated():
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
        st.error(f"{t('auth.error_reset', 'Error al enviar email de recuperacion')}: {e}")
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
    y boton para cerrar sesión.
    """
    if is_authenticated():
        user = st.session_state.get("user", {})
        role = st.session_state.get("role", "free")

        role_badges = {
            "admin": f"🔴 {t('roles.admin', 'Admin')}",
            "pro": f"🟢 {t('roles.pro', 'Pro')}",
            "free": f"⚪ {t('roles.free', 'Free')}",
        }
        badge = role_badges.get(role, f"⚪ {t('roles.free', 'Free')}")

        st.sidebar.markdown(f"**{user.get('email', '')}**")
        st.sidebar.markdown(f"{t('roles.plan_label', 'Plan')}: {badge}")

        if st.sidebar.button(f"🔓 {t('app.logout', 'Cerrar sesión')}"):
            logout()
            st.rerun()
