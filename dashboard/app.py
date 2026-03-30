"""
app.py - Dashboard principal del Memecoin Gem Detector.

Ejecutar con: streamlit run dashboard/app.py

Navegacion basada en roles:
- Publico (todos los usuarios autenticados): Overview, Señales, Buscar Token, Watchlist
- Admin (solo operador): Modelos, Features, Exploracion, Sistema
"""
import os
import sys
from pathlib import Path

# Agregar la raiz del proyecto al path para que los imports funcionen
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

# =============================================================================
# Configuracion de pagina — DEBE ser la primera llamada a Streamlit
# =============================================================================

st.set_page_config(
    page_title="Meme Detector — Detecta Gems en Memecoins",
    page_icon="💎",
    layout="wide",
    menu_items={
        "Get Help": "https://t.me/Ull_trading_bot",
        "Report a Bug": "mailto:info@memedetector.es",
        "About": "Meme Detector analiza miles de memecoins con ML para encontrar las próximas gems 10x+. https://www.memedetector.es",
    },
)

from dashboard.i18n import render_language_selector

# --- Intentar cargar el modulo de autenticacion Supabase ---
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
# Gate de autenticacion
# =============================================================================

if _AUTH_AVAILABLE:
    # Auth con Supabase — muestra login si no esta autenticado, llama st.stop()
    require_auth()
else:
    # Auth no disponible — bloquear acceso con mensaje de mantenimiento
    st.error("Sistema de autenticación no disponible. Contacta info@memedetector.es")
    st.stop()


# =============================================================================
# Sidebar: info del usuario
# =============================================================================

if _AUTH_AVAILABLE:
    render_sidebar_user_info()
else:
    # Fallback legacy: boton de cerrar sesion simple
    with st.sidebar:
        if st.button(":material/lock_open: Cerrar sesión"):
            st.session_state.authenticated = False
            st.rerun()

# --- Selector de idioma ---
render_language_selector()


# =============================================================================
# Importar funciones render de cada vista
# =============================================================================

# Imports desde public/ y admin/
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
from public.portfolio import render as render_portfolio
from public.alerts_config import render as render_alerts_config
from public.pricing import render as render_pricing
from public.profile import render as render_profile
from public.legal import render as render_legal
from public.academy import render as render_academy
from admin.drift_monitor import render as render_drift_monitor
from admin.retrain_panel import render as render_retrain_panel


# =============================================================================
# Navegacion basada en roles
# =============================================================================

# --- Paginas publicas (todos los usuarios autenticados) ---
public_pages = [
    st.Page(render_overview, title="Resumen", icon=":material/dashboard:", url_path="overview"),
]
# Usar signals_v2 si disponible, sino fallback a signals original
if render_signals_v2:
    public_pages.append(st.Page(render_signals_v2, title="Señales", icon=":material/trending_up:", url_path="signals"))
else:
    public_pages.append(st.Page(render_signals, title="Señales", icon=":material/trending_up:", url_path="signals"))
public_pages.extend([
    st.Page(render_token_lookup, title="Buscar Token", icon=":material/search:", url_path="token-lookup"),
    st.Page(render_watchlist, title="Watchlist", icon=":material/bookmark:", url_path="watchlist"),
])
if render_portfolio:
    public_pages.append(st.Page(render_portfolio, title="Portfolio", icon=":material/account_balance_wallet:", url_path="portfolio"))
if render_track_record:
    public_pages.append(st.Page(render_track_record, title="Track Record", icon=":material/emoji_events:", url_path="track-record"))
if render_alerts_config:
    public_pages.append(st.Page(render_alerts_config, title="Alertas", icon=":material/notifications:", url_path="alerts"))
if render_profile:
    public_pages.append(st.Page(render_profile, title="Mi Perfil", icon=":material/person:", url_path="profile"))
if render_academy:
    public_pages.append(st.Page(render_academy, title="Academia", icon=":material/school:", url_path="academy"))
if render_pricing:
    public_pages.append(st.Page(render_pricing, title="Planes", icon=":material/payments:", url_path="pricing"))

# --- Paginas de administracion (solo admin) ---
admin_pages = []
_is_admin = is_admin() if _AUTH_AVAILABLE else False  # Sin auth: nada visible

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
# --- Paginas informativas ---
info_pages = []
if render_legal:
    info_pages.append(st.Page(render_legal, title="Legal", icon=":material/gavel:", url_path="legal"))

nav_config = {"Aplicacion": public_pages}
if admin_pages:
    nav_config["Administracion"] = admin_pages
if info_pages:
    nav_config["Informacion"] = info_pages

pg = st.navigation(nav_config, position="sidebar")


# =============================================================================
# Sidebar: descripcion de la herramienta
# =============================================================================

st.sidebar.divider()
st.sidebar.caption(
    "**Gem Detector** - Herramienta de Machine Learning para analizar memecoins "
    "y detectar cuales tienen potencial de ser 'gems' (10x+)."
)

pg.run()
