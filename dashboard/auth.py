"""
auth.py - Autenticacion y gestion de sesiones con Supabase Auth.

Provee funciones para login, registro, verificacion de sesion,
y control de acceso basado en roles (admin/pro/free).

Usa SUPABASE_ANON_KEY (no service_role) porque Supabase Auth
requiere la anon key para operaciones de autenticacion.
"""
import os
import streamlit as st
from supabase import create_client, Client


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
    """Inicializa variables de sesion para auth.

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
            st.error("Email o contrasena incorrectos.")
        else:
            st.error(f"Error de autenticacion: {error_msg}")
        return False


def register(email: str, password: str) -> bool:
    """Registro con Supabase Auth. Retorna True si exitoso.

    Crea un nuevo usuario en auth.users. Supabase puede enviar
    un email de confirmacion dependiendo de la config del proyecto.
    El perfil en 'profiles' se crea automaticamente via trigger SQL.
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
            st.success("Cuenta creada. Revisa tu email para confirmar.")
            return True
        return False
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower():
            st.error("Este email ya esta registrado. Intenta iniciar sesion.")
        else:
            st.error(f"Error en registro: {error_msg}")
        return False


def logout():
    """Cierra sesion limpiando todo el session_state de auth."""
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
    """Verifica que el usuario sea admin. Muestra error si no.

    Primero verifica autenticacion, luego verifica rol.
    """
    require_auth()
    if not is_admin():
        st.error("Acceso restringido. Se requiere rol de administrador.")
        st.stop()


def require_pro():
    """Verifica que el usuario sea pro o admin.

    Muestra un mensaje con link de suscripcion si el usuario
    no tiene el plan adecuado.
    """
    require_auth()
    if not is_pro():
        st.warning("Esta funcion requiere suscripcion Pro.")
        st.markdown("[Suscribirse →](#)")  # TODO: Link a Stripe
        st.stop()


def render_login_page():
    """Renderiza la pagina de login/registro con tabs.

    Incluye validacion de campos, confirmacion de contrasena
    en registro, y longitud minima de contrasena (6 chars).
    """
    st.title("🔒 Trading Memes")
    st.markdown("Detector de Gems en Memecoins con Machine Learning")

    tab_login, tab_register = st.tabs(["Iniciar Sesion", "Crear Cuenta"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Contrasena", type="password", key="login_password")
        if st.button("Acceder", type="primary", key="btn_login"):
            if email and password:
                if login(email, password):
                    st.rerun()
            else:
                st.warning("Introduce email y contrasena.")

    with tab_register:
        reg_email = st.text_input("Email", key="reg_email")
        reg_pass = st.text_input("Contrasena", type="password", key="reg_password")
        reg_pass2 = st.text_input(
            "Confirmar contrasena", type="password", key="reg_password2"
        )
        if st.button("Crear cuenta", type="primary", key="btn_register"):
            if not reg_email or not reg_pass:
                st.warning("Completa todos los campos.")
            elif reg_pass != reg_pass2:
                st.error("Las contrasenas no coinciden.")
            elif len(reg_pass) < 6:
                st.error("La contrasena debe tener al menos 6 caracteres.")
            else:
                register(reg_email, reg_pass)


def render_sidebar_user_info():
    """Muestra info del usuario en el sidebar + boton logout.

    Incluye email, badge del plan (Admin/Pro/Free),
    y boton para cerrar sesion.
    """
    if is_authenticated():
        user = st.session_state.get("user", {})
        role = st.session_state.get("role", "free")

        role_badges = {
            "admin": "🔴 Admin",
            "pro": "🟢 Pro",
            "free": "⚪ Free",
        }
        badge = role_badges.get(role, "⚪ Free")

        st.sidebar.markdown(f"**{user.get('email', '')}**")
        st.sidebar.markdown(f"Plan: {badge}")

        if st.sidebar.button("🔓 Cerrar sesion"):
            logout()
            st.rerun()
