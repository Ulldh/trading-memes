"""
app.py - Dashboard principal del Memecoin Gem Detector.

Ejecutar con: streamlit run dashboard/app.py

Navegacion basada en roles:
- Publico (todos los usuarios autenticados): Overview, Senales, Buscar Token, Watchlist
- Admin (solo operador): Modelos, Features, Exploracion, Sistema
"""
import os
import sys
from pathlib import Path

# Agregar la raiz del proyecto al path para que los imports funcionen
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

# --- Intentar cargar el modulo de autenticacion Supabase ---
# Si auth.py aun no existe (se crea en paralelo), usamos el gate legacy con contrasena
try:
    from dashboard.auth import (
        require_auth,
        is_admin,
        is_pro,
        render_sidebar_user_info,
    )
    _AUTH_AVAILABLE = True
except ImportError:
    _AUTH_AVAILABLE = False


# =============================================================================
# Fallback legacy: gate con contrasena (se eliminara cuando auth.py este listo)
# =============================================================================

def _legacy_check_password():
    """Gate legacy con contrasena simple (variable de entorno DASHBOARD_PASSWORD).

    Se usa SOLO si el modulo dashboard.auth no esta disponible.
    """
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    # Pantalla de login legacy
    st.set_page_config(
        page_title="Trading Memes - Login",
        page_icon=":material/lock:",
        layout="centered",
    )

    st.title(":material/lock: Trading Memes Dashboard")
    st.markdown("Introduce la contrasena para acceder.")

    password = st.text_input("Contrasena", type="password", key="password_input")

    if st.button("Acceder", type="primary"):
        dashboard_password = os.getenv("DASHBOARD_PASSWORD", "")
        if not dashboard_password:
            st.error("DASHBOARD_PASSWORD no configurada en el servidor.")
            return False
        if password == dashboard_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Contrasena incorrecta.")

    return False


# =============================================================================
# Gate de autenticacion
# =============================================================================

if _AUTH_AVAILABLE:
    # Auth con Supabase — muestra login si no esta autenticado, llama st.stop()
    require_auth()
else:
    # Fallback legacy — bloquea hasta que se introduzca la contrasena
    if not _legacy_check_password():
        st.stop()


# =============================================================================
# Configuracion de pagina (solo se ejecuta si el usuario esta autenticado)
# =============================================================================

st.set_page_config(
    page_title="Trading Memes - Gem Detector",
    page_icon=":material/diamond:",
    layout="wide",
)


# =============================================================================
# Sidebar: info del usuario
# =============================================================================

if _AUTH_AVAILABLE:
    render_sidebar_user_info()
else:
    # Fallback legacy: boton de cerrar sesion simple
    with st.sidebar:
        if st.button(":material/lock_open: Cerrar sesion"):
            st.session_state.authenticated = False
            st.rerun()


# =============================================================================
# Importar funciones render de cada vista
# =============================================================================

# Imports: intentar desde public/admin (Fase B), fallback a views/
try:
    from public.overview import render as render_overview
    from public.signals import render as render_signals
    from public.token_lookup import render as render_token_lookup
    from public.watchlist import render as render_watchlist
    from admin.model_results import render as render_model_results
    from admin.feature_importance import render as render_feature_importance
    from admin.eda import render as render_eda
    from admin.system_health import render as render_system_health
    # Nuevas vistas (Fase C+D)
    from public.signals_v2 import render as render_signals_v2
    from public.track_record import render as render_track_record
    from admin.drift_monitor import render as render_drift_monitor
    from admin.retrain_panel import render as render_retrain_panel
except ImportError:
    from views.overview import render as render_overview
    from views.eda import render as render_eda
    from views.model_results import render as render_model_results
    from views.feature_importance import render as render_feature_importance
    from views.token_lookup import render as render_token_lookup
    from views.signals import render as render_signals
    from views.system_health import render as render_system_health
    from views.watchlist import render as render_watchlist
    render_signals_v2 = None
    render_track_record = None
    render_drift_monitor = None
    render_retrain_panel = None


# =============================================================================
# Navegacion basada en roles
# =============================================================================

# --- Paginas publicas (todos los usuarios autenticados) ---
public_pages = [
    st.Page(render_overview, title="Resumen", icon=":material/dashboard:", url_path="overview"),
]
# Usar signals_v2 si disponible, sino fallback a signals original
if render_signals_v2:
    public_pages.append(st.Page(render_signals_v2, title="Senales", icon=":material/trending_up:", url_path="signals"))
else:
    public_pages.append(st.Page(render_signals, title="Senales", icon=":material/trending_up:", url_path="signals"))
public_pages.extend([
    st.Page(render_token_lookup, title="Buscar Token", icon=":material/search:", url_path="token-lookup"),
    st.Page(render_watchlist, title="Watchlist", icon=":material/bookmark:", url_path="watchlist"),
])
if render_track_record:
    public_pages.append(st.Page(render_track_record, title="Track Record", icon=":material/emoji_events:", url_path="track-record"))

# --- Paginas de administracion (solo admin) ---
admin_pages = []
_is_admin = is_admin() if _AUTH_AVAILABLE else True  # Legacy: todo visible

if _is_admin:
    admin_pages = [
        st.Page(render_model_results, title="Modelos", icon=":material/psychology:", url_path="model-results"),
        st.Page(render_feature_importance, title="Features", icon=":material/bar_chart:", url_path="feature-importance"),
        st.Page(render_eda, title="Exploracion", icon=":material/analytics:", url_path="eda"),
        st.Page(render_system_health, title="Sistema", icon=":material/monitor_heart:", url_path="system-health"),
    ]
    if render_drift_monitor:
        admin_pages.append(st.Page(render_drift_monitor, title="Drift Monitor", icon=":material/monitoring:", url_path="drift-monitor"))
    if render_retrain_panel:
        admin_pages.append(st.Page(render_retrain_panel, title="Retrain", icon=":material/model_training:", url_path="retrain"))

# --- Construir navegacion agrupada ---
nav_config = {"Aplicacion": public_pages}
if admin_pages:
    nav_config["Administracion"] = admin_pages

pg = st.navigation(nav_config)


# =============================================================================
# Sidebar: descripcion de la herramienta
# =============================================================================

st.sidebar.divider()
st.sidebar.caption(
    "**Gem Detector** - Herramienta de Machine Learning para analizar memecoins "
    "y detectar cuales tienen potencial de ser 'gems' (10x+)."
)

pg.run()
