"""
app.py - Dashboard principal del Memecoin Gem Detector.

Ejecutar con: streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

# Agregar la raiz del proyecto al path para que los imports funcionen
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

st.set_page_config(
    page_title="Memecoin Gem Detector",
    page_icon="💎",
    layout="wide",
)

# Importar funciones render de cada vista
from views.overview import render as render_overview
from views.eda import render as render_eda
from views.model_results import render as render_model_results
from views.feature_importance import render as render_feature_importance
from views.token_lookup import render as render_token_lookup
from views.signals import render as render_signals
from views.system_health import render as render_system_health
from views.watchlist import render as render_watchlist

# st.navigation() REEMPLAZA la auto-deteccion de paginas de Streamlit.
# Asi controlamos nosotros que paginas aparecen y en que orden.
pg = st.navigation([
    st.Page(render_overview, title="Overview", icon=":material/dashboard:", url_path="overview"),
    st.Page(render_eda, title="Analisis Exploratorio", icon=":material/query_stats:", url_path="eda"),
    st.Page(render_model_results, title="Resultados del Modelo", icon=":material/model_training:", url_path="model-results"),
    st.Page(render_feature_importance, title="Importancia de Features", icon=":material/target:", url_path="feature-importance"),
    st.Page(render_token_lookup, title="Buscar Token", icon=":material/search:", url_path="token-lookup"),
    st.Page(render_signals, title="Senales", icon=":material/notifications_active:", url_path="signals"),
    st.Page(render_watchlist, title="Watchlist", icon=":material/bookmark:", url_path="watchlist"),
    st.Page(render_system_health, title="System Health", icon=":material/health_and_safety:", url_path="system-health"),
])

st.sidebar.divider()
st.sidebar.caption(
    "**Gem Detector** - Herramienta de Machine Learning para analizar memecoins "
    "y detectar cuales tienen potencial de ser 'gems' (10x+).\n\n"
    "**Paginas:**\n"
    "- **Overview**: Resumen de datos recopilados.\n"
    "- **Analisis Exploratorio**: Graficos interactivos de features.\n"
    "- **Resultados del Modelo**: Metricas de rendimiento (RF vs XGBoost).\n"
    "- **Importancia de Features**: Que aprende el modelo (SHAP).\n"
    "- **Buscar Token**: Prediccion individual por contract address.\n"
    "- **Senales**: Alertas diarias de gem candidates + backtesting.\n"
    "- **Watchlist**: Tu lista personal de tokens para monitorear.\n"
    "- **System Health**: Estado del sistema, APIs, servicios y espacio."
)

pg.run()
