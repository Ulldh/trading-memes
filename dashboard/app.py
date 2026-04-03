"""
app.py - Dashboard principal del Memecoin Gem Detector.

Ejecutar con: streamlit run dashboard/app.py

Navegacion basada en roles:
- Publico (todos los usuarios autenticados): Overview, Señales, Buscar Token, Watchlist
- Admin (solo operador): Modelos, Features, Exploracion, Sistema
"""
import os
import sys
import datetime
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
from dashboard.theme import inject_global_css

# Inyectar CSS global para aspecto premium (una sola vez)
inject_global_css()

# Set HTML lang attribute for accessibility
_locale = st.session_state.get("locale", "es")
_locale = _locale if _locale in ("es", "en", "pt", "de", "fr") else "es"
st.markdown(f'<script>document.documentElement.lang="{_locale}";</script>', unsafe_allow_html=True)

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
from public.model_history import render as render_model_history
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
if render_model_history:
    public_pages.append(st.Page(render_model_history, title="Bitácora ML", icon=":material/history:", url_path="model-history"))
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

st.sidebar.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

# --- Countdown hasta proximo pipeline scan (estilo trading terminal premium) ---
_now_utc = datetime.datetime.now(datetime.timezone.utc)
_next_runs = []
for _hour in [6, 18]:
    _candidate = _now_utc.replace(hour=_hour, minute=0, second=0, microsecond=0)
    if _candidate <= _now_utc:
        _candidate += datetime.timedelta(days=1)
    _next_runs.append(_candidate)
_next_run = min(_next_runs)
_delta = _next_run - _now_utc
_hours, _remainder = divmod(int(_delta.total_seconds()), 3600)
_minutes, _seconds = divmod(_remainder, 60)

st.sidebar.markdown(
    f"<div style='"
    f"background: linear-gradient(135deg, rgba(0,255,65,0.04), rgba(0,255,65,0.01)); "
    f"border: 1px solid rgba(0,255,65,0.1); "
    f"border-radius: 12px; padding: 14px 16px; margin: 4px 0 12px 0; text-align: center; "
    f"position: relative; overflow: hidden;'>"
    # Linea decorativa superior
    f"<div style='position: absolute; top: 0; left: 0; right: 0; height: 1px; "
    f"background: linear-gradient(90deg, transparent, rgba(0,255,65,0.25), transparent);'></div>"
    # Indicador de estado vivo
    f"<div style='display: flex; align-items: center; justify-content: center; "
    f"gap: 6px; margin-bottom: 6px;'>"
    f"<div style='width: 6px; height: 6px; border-radius: 50%; "
    f"background: #00ff41; box-shadow: 0 0 8px rgba(0,255,65,0.5);'></div>"
    f"<span style='color: #6b7280; font-size: 0.6rem; text-transform: uppercase; "
    f"letter-spacing: 1.5px; font-weight: 700;'>Proximo scan</span></div>"
    # Timer grande
    f"<span style='color: #00ff41; font-size: 1.5rem; font-weight: 800; "
    f"font-family: monospace; letter-spacing: 3px; "
    f"text-shadow: 0 0 20px rgba(0,255,65,0.3);'>"
    f"{_hours:02d}:{_minutes:02d}:{_seconds:02d}</span>"
    f"</div>",
    unsafe_allow_html=True,
)

st.sidebar.markdown(
    "<div style='text-align: center; margin: 0 0 8px 0;'>"
    "<span style='color: #374151; font-size: 0.7rem; font-weight: 600;'>"
    "Gem Detector</span>"
    "<span style='color: #1a1a2e;'> &middot; </span>"
    "<span style='color: #374151; font-size: 0.65rem;'>"
    "ML para detectar memecoins 10x+</span></div>",
    unsafe_allow_html=True,
)

# --- Version footer premium ---
st.sidebar.markdown(
    "<div style='position: fixed; bottom: 12px; color: #2a2a3e; "
    "font-size: 0.6rem; letter-spacing: 1px; font-weight: 600;'>"
    "v2.3 &middot; memedetector.es</div>",
    unsafe_allow_html=True,
)

pg.run()
