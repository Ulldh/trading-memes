"""
auth.py - Autenticacion y gestion de sesiones con Supabase Auth.

Provee funciones para login, registro, verificacion de sesion,
y control de acceso basado en roles (admin/pro/free).

Usa SUPABASE_ANON_KEY (no service_role) porque Supabase Auth
requiere la anon key para operaciones de autenticacion.

NOTA: Los emails de confirmacion y reset se configuran en:
Supabase Dashboard -> Authentication -> Email Templates
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
            st.error(t("auth.error_invalid_credentials", "Email o contrasena incorrectos."))
        else:
            logger.exception("Error de autenticacion en login")
            st.error("Se produjo un error inesperado. Intentalo de nuevo.")
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
            st.success(t("auth.register_success",
                         "Cuenta creada. Revisa tu email para confirmar "
                         "y luego ya puedes iniciar sesion."))
            return True
        return False
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower():
            st.error(t("auth.error_already_registered",
                        "Este email ya esta registrado. Intenta iniciar sesion."))
        else:
            logger.exception("Error en registro de usuario")
            st.error("Se produjo un error inesperado. Intentalo de nuevo.")
        return False


def logout():
    """Cierra sesion limpiando todo el session_state de auth."""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.role = "free"
    st.session_state.profile = None
    st.session_state.access_token = None
    st.session_state.login_time = 0
    st.session_state.pop("pending_plan", None)


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

    Si el usuario ya esta autenticado y tiene un plan pendiente
    (viene de la landing con ?plan=pro|enterprise), redirige a Stripe.
    """
    init_session_state()
    if is_authenticated():
        _check_session_freshness()
        # Si el usuario ya logueado llega con ?plan=pro|enterprise desde la landing,
        # guardar el plan en session_state para que _maybe_redirect_to_stripe lo procese.
        qp = st.query_params
        plan_from_url = qp.get("plan", "")
        if plan_from_url in ("pro", "enterprise"):
            st.session_state["pending_plan"] = plan_from_url
        # Mostrar mensaje de retorno de Stripe si aplica
        payment_status = qp.get("payment", "")
        if payment_status == "success":
            st.success(t(
                "auth.payment_success",
                "Pago completado! Tu plan se activara en breves instantes."
            ))
        elif payment_status == "cancelled":
            st.info(t(
                "auth.payment_cancelled",
                "El pago fue cancelado. Puedes reintentar desde tu perfil "
                "o seleccionando un plan de nuevo."
            ))
        # Comprobar si hay plan pendiente para redirigir a Stripe
        _maybe_redirect_to_stripe()
        return
    render_login_page()
    st.stop()


def require_admin():
    """Verifica que el usuario sea admin. Redirige a overview si no.

    Primero verifica autenticacion, luego verifica rol.
    Si el usuario no es admin, muestra las paginas publicas disponibles.
    """
    require_auth()
    if not is_admin():
        st.info(t("access.admin_required", "Bienvenido. Usa el menu lateral para navegar por las secciones disponibles."))
        st.markdown("### Paginas disponibles")
        st.markdown("""
        - **Resumen** — Estadisticas del mercado
        - **Senales** — Tokens con mayor potencial
        - **Buscar Token** — Analizar cualquier token
        - **Watchlist** — Tus tokens favoritos
        - **Academia** — Aprende sobre memecoins
        """)
        st.stop()


def require_pro():
    """Verifica que el usuario sea pro o admin.

    Muestra un mensaje con link de suscripcion si el usuario
    no tiene el plan adecuado.
    """
    require_auth()
    if not is_pro():
        st.warning(t("paywall.requires_pro_generic", "Esta funcion requiere suscripcion Pro."))
        st.info(t('paywall.subscribe_link', 'Visita la seccion Planes para suscribirte.'))
        st.stop()


def reset_password(email: str) -> bool:
    """Envia email de restablecimiento de contrasena via Supabase Auth.

    Retorna True si el email se envio correctamente (o si Supabase
    no reporta error, por seguridad no revela si el email existe).
    """
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.auth.reset_password_email(
            email,
            options={"redirect_to": "https://app.memedetector.es"},
        )
        return True
    except Exception as e:
        logger.exception("Error al enviar email de recuperacion de contrasena")
        st.error("Se produjo un error inesperado. Intentalo de nuevo.")
        return False


def _handle_payment_query_params():
    """Procesa query params de retorno de Stripe (?payment=success|cancelled).

    Se llama al inicio de render_login_page para mostrar mensajes
    de confirmacion o reintento antes del formulario de login.
    """
    qp = st.query_params
    payment_status = qp.get("payment", "")

    if payment_status == "success":
        st.success(t(
            "auth.payment_success",
            "Pago completado! Tu plan se activara en breves instantes. "
            "Inicia sesion para continuar."
        ))
    elif payment_status == "cancelled":
        st.info(t(
            "auth.payment_cancelled",
            "El pago fue cancelado. Puedes reintentar desde tu perfil "
            "o seleccionando un plan de nuevo."
        ))


def _maybe_redirect_to_stripe():
    """Redirige a Stripe Checkout si el usuario tiene un plan pendiente.

    Comprueba si el usuario acaba de hacer login con un plan de pago
    pendiente (pro/enterprise) y su rol actual es free. Si Stripe
    esta configurado, crea una sesion de checkout y redirige.
    """
    plan_requested = st.session_state.get("pending_plan", "")
    role = st.session_state.get("role", "free")

    if plan_requested in ("pro", "enterprise") and role == "free":
        try:
            from src.billing.stripe_client import create_checkout_session, is_configured
            if is_configured():
                user = st.session_state.get("user", {}) or {}
                checkout_url = create_checkout_session(
                    user_email=user.get("email", ""),
                    plan=plan_requested,
                    user_id=user.get("id", ""),
                )
                if checkout_url:
                    # Limpiar el plan pendiente para que no se repita
                    st.session_state.pop("pending_plan", None)
                    st.markdown(
                        f'<meta http-equiv="refresh" content="0;url={checkout_url}">',
                        unsafe_allow_html=True,
                    )
                    st.info(t(
                        "auth.redirecting_stripe",
                        "Redirigiendo a la pasarela de pago..."
                    ))
                    st.stop()
        except ImportError:
            logger.warning("stripe_client no disponible, omitiendo redireccion a Stripe")
        except Exception:
            logger.exception("Error al crear sesion de Stripe Checkout")


def render_login_page():
    """Renderiza la pagina de login/registro con estilo premium trading terminal.

    Incluye validacion de campos, confirmacion de contrasena
    en registro, longitud minima de contrasena (8 chars),
    recuperacion de contrasena, aviso de terminos de servicio,
    y flujo de redireccion a Stripe para planes de pago.

    Query params soportados:
      - ?tab=register|login — pestana inicial
      - ?plan=free|pro|enterprise — plan seleccionado desde la landing
      - ?payment=success|cancelled — retorno de Stripe Checkout
    """
    # --- Branding centrado premium con estilo terminal ---
    st.markdown(
        "<div style='text-align: center; padding: 60px 0 20px 0;'>"
        # Logo/titulo con glow
        "<h1 style='font-size: 2.8rem; margin-bottom: 6px; font-weight: 900; "
        "letter-spacing: -1px;'>"
        "<span style='color: #00ff41; text-shadow: 0 0 40px rgba(0,255,65,0.4), "
        "0 0 80px rgba(0,255,65,0.15);'>Meme</span>"
        "<span style='color: #ffffff;'> Detector</span></h1>"
        # Indicador de terminal
        "<div style='display: inline-block; background: rgba(0,255,65,0.06); "
        "border: 1px solid rgba(0,255,65,0.12); border-radius: 20px; "
        "padding: 4px 16px; margin-bottom: 8px;'>"
        "<span style='color: #00ff41; font-size: 0.65rem; font-weight: 700; "
        "letter-spacing: 2px; text-transform: uppercase;'>"
        "&#9679; TRADING TERMINAL</span></div>"
        # Subtitulo
        "<p style='color: #6b7280; font-size: 0.9rem; margin: 8px 0 0 0; "
        "max-width: 400px; margin-left: auto; margin-right: auto;'>"
        f"{t('auth.login_subtitle', 'Detector de Gems en Memecoins con Machine Learning')}"
        "</p></div>",
        unsafe_allow_html=True,
    )

    # --- Procesar retorno de Stripe (success/cancelled) ---
    _handle_payment_query_params()

    # --- Leer query params: tab y plan ---
    qp = st.query_params
    default_tab = qp.get("tab", "login")
    # Guardar plan solicitado desde la landing (free/pro/enterprise)
    plan_from_url = qp.get("plan", "")
    if plan_from_url and plan_from_url in ("free", "pro", "enterprise"):
        st.session_state["pending_plan"] = plan_from_url

    # --- Layout centrado: columnas estrechas para simular tarjeta ---
    _spacer_l, col_form, _spacer_r = st.columns([1.2, 1.6, 1.2])

    with col_form:
        tab_labels = [
            t("auth.tab_login", "Iniciar Sesion"),
            t("auth.tab_register", "Crear Cuenta"),
        ]
        # st.tabs no soporta default index, pero podemos reordenar para que el tab
        # deseado aparezca primero. Si tab=register, ponemos Crear Cuenta primero.
        if default_tab == "register":
            tab_register, tab_login = st.tabs(list(reversed(tab_labels)))
        else:
            tab_login, tab_register = st.tabs(tab_labels)

        with tab_login:
            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            # --- Formulario de login ---
            email = st.text_input(
                t("auth.email", "Email"), key="login_email",
                placeholder="tu@email.com",
            )
            password = st.text_input(
                t("auth.password", "Contrasena"), type="password", key="login_password",
                placeholder="Tu contrasena",
            )
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            if st.button(
                t("auth.login_btn", "Acceder"),
                type="primary", key="btn_login",
                use_container_width=True,
            ):
                if email and password:
                    if login(email, password):
                        # Comprobar si hay plan pendiente para redirigir a Stripe
                        _maybe_redirect_to_stripe()
                        st.rerun()
                else:
                    st.warning(t("auth.error_empty_fields", "Introduce email y contrasena."))

            # --- Recuperar contrasena ---
            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            with st.expander(t("auth.forgot_password", "Olvidaste tu contrasena?")):
                reset_email = st.text_input(
                    t("auth.reset_email_label",
                      "Introduce tu email para restablecer la contrasena"),
                    key="reset_email",
                )
                if st.button(
                    t("auth.reset_btn", "Enviar enlace de recuperacion"),
                    key="btn_reset",
                    use_container_width=True,
                ):
                    if reset_email:
                        if reset_password(reset_email):
                            st.success(t("auth.reset_success",
                                         "Te hemos enviado un email para restablecer "
                                         "tu contrasena. Revisa tu bandeja de entrada."))
                    else:
                        st.warning(t("auth.error_empty_email", "Introduce tu email."))

        with tab_register:
            # Mostrar plan seleccionado si viene de la landing — estilo premium
            pending = st.session_state.get("pending_plan", "")
            if pending and pending != "free":
                st.markdown(
                    f"<div style='"
                    f"background: linear-gradient(135deg, rgba(0,255,65,0.04), rgba(0,255,65,0.02)); "
                    f"border: 1px solid rgba(0,255,65,0.15); border-radius: 12px; "
                    f"padding: 14px 18px; margin: 8px 0;'>"
                    f"<div style='display: flex; align-items: center; gap: 8px;'>"
                    f"<span style='color: #00ff41; font-size: 1.1rem;'>&#9889;</span>"
                    f"<div>"
                    f"<div style='font-size: 0.7rem; color: #6b7280; "
                    f"text-transform: uppercase; letter-spacing: 1px; font-weight: 600;'>"
                    f"Plan seleccionado</div>"
                    f"<strong style='color: #00ff41; font-size: 1.1rem; "
                    f"text-shadow: 0 0 10px rgba(0,255,65,0.2);'>"
                    f"{pending.upper()}</strong>"
                    f"</div></div>"
                    f"<p style='color: #9ca3af; font-size: 0.8rem; margin: 8px 0 0 0;'>"
                    f"Crea tu cuenta y tras iniciar sesion seras redirigido al pago.</p>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            reg_email = st.text_input(
                t("auth.email", "Email"), key="reg_email",
                placeholder="tu@email.com",
            )
            reg_pass = st.text_input(
                t("auth.password", "Contrasena"), type="password", key="reg_password",
                placeholder="Minimo 8 caracteres",
                help=t("auth.password_hint",
                       "Minimo 8 caracteres, al menos una mayuscula y un numero"),
            )
            st.caption(t("auth.password_hint",
                          "Minimo 8 caracteres, al menos una mayuscula y un numero"))
            reg_pass2 = st.text_input(
                t("auth.confirm_password", "Confirmar contrasena"),
                type="password", key="reg_password2",
                placeholder="Repite tu contrasena",
            )
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            if st.button(
                t("auth.register_btn", "Crear cuenta"),
                type="primary", key="btn_register",
                use_container_width=True,
            ):
                if not reg_email or not reg_pass:
                    st.warning(t("auth.error_fill_all", "Completa todos los campos."))
                elif reg_pass != reg_pass2:
                    st.error(t("auth.error_password_mismatch", "Las contrasenas no coinciden."))
                elif len(reg_pass) < 8:
                    st.error(t("auth.error_password_length",
                               "La contrasena debe tener al menos 8 caracteres."))
                elif not any(c.isupper() for c in reg_pass):
                    st.error(t("auth.error_password_uppercase",
                               "La contrasena debe contener al menos una mayuscula."))
                elif not any(c.isdigit() for c in reg_pass):
                    st.error(t("auth.error_password_digit",
                               "La contrasena debe contener al menos un numero."))
                else:
                    register(reg_email, reg_pass)

            # Aviso de terminos de servicio
            st.caption(t("auth.tos_notice",
                          "Al crear tu cuenta aceptas los Terminos de Servicio."))


def render_sidebar_user_info():
    """Muestra info del usuario en el sidebar + boton logout.

    Incluye avatar con iniciales y glow, email, badge del plan premium,
    Pro member since + dias hasta renovacion,
    y boton para cerrar sesion. Estilo trading terminal.
    """
    if is_authenticated():
        user = st.session_state.get("user", {})
        role = st.session_state.get("role", "free")
        profile = st.session_state.get("profile", {}) or {}

        plan = profile.get("subscription_plan", role)
        email = user.get("email", "")

        # Obtener iniciales para el avatar circular
        display_name = profile.get("display_name", "")
        if display_name:
            initials = display_name[:2].upper()
        elif email:
            initials = email[:2].upper()
        else:
            initials = "U"

        # Colores segun rol — con glow
        role_config = {
            "admin": {"color": "#ef4444", "label": t('roles.admin', 'ADMIN'), "glow": "0 0 15px rgba(239,68,68,0.2)"},
            "pro": {"color": "#00ff41", "label": t('roles.pro', 'PRO'), "glow": "0 0 15px rgba(0,255,65,0.2)"},
            "free": {"color": "#6b7280", "label": t('roles.free', 'FREE'), "glow": "none"},
        }
        rc = role_config.get(role, role_config["free"])

        # --- Avatar + nombre + badge en bloque visual premium ---
        st.sidebar.markdown(
            f"<div style='text-align: center; margin: 0 0 12px 0;'>"
            # Avatar circular con glow
            f"<div style='width: 52px; height: 52px; border-radius: 50%; "
            f"background: linear-gradient(135deg, {rc['color']}15, {rc['color']}08); "
            f"border: 2px solid {rc['color']}35; "
            f"display: inline-flex; align-items: center; justify-content: center; "
            f"margin-bottom: 8px; box-shadow: {rc['glow']};'>"
            f"<span style='color: {rc['color']}; font-weight: 800; "
            f"font-size: 1.1rem;'>{initials}</span>"
            f"</div><br>"
            # Nombre o email
            f"<span style='font-weight: 700; font-size: 0.9rem; color: #ffffff;'>"
            f"{display_name or email.split('@')[0] if email else 'User'}</span><br>"
            f"<span style='color: #6b7280; font-size: 0.7rem;'>{email}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Badge de plan — pastilla premium
        st.sidebar.markdown(
            f"<div role='status' aria-label='Plan: {rc['label']}' "
            f"style='background: linear-gradient(135deg, {rc['color']}10, {rc['color']}05); "
            f"color: {rc['color']}; "
            f"padding: 6px 16px; border-radius: 20px; text-align: center; "
            f"font-weight: 800; font-size: 0.7rem; "
            f"border: 1px solid {rc['color']}20; "
            f"margin: 0 0 8px 0; letter-spacing: 1.5px; "
            f"text-transform: uppercase;'>"
            f"{rc['label']}</div>",
            unsafe_allow_html=True,
        )

        # Pro/Admin: info de suscripcion
        if role in ("pro", "admin"):
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

        if st.sidebar.button(
            f":material/logout: {t('app.logout', 'Cerrar sesion')}",
            use_container_width=True,
        ):
            logout()
            st.rerun()
