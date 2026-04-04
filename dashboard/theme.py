"""
theme.py — CSS global y componentes de estilo reutilizables.

Inyecta estilos premium en el dashboard para un look de
trading terminal profesional (estilo TradingView / DexScreener).

Uso:
    from dashboard.theme import inject_global_css
    inject_global_css()  # llamar una vez en app.py
"""

import streamlit as st


# =============================================================================
# Paleta de colores — terminal premium
# =============================================================================

ACCENT = "#00ff41"
ACCENT_DIM = "rgba(0, 255, 65, 0.15)"
ACCENT_GLOW = "0 0 20px rgba(0, 255, 65, 0.3)"
BG_DARK = "#0a0a0a"
BG_CARD = "#0d1117"
BG_CARD_HOVER = "#161b22"
BG_SURFACE = "#1a1a2e"
BORDER = "rgba(255, 255, 255, 0.06)"
BORDER_ACCENT = "rgba(0, 255, 65, 0.2)"
TEXT_PRIMARY = "#e0e0e0"
TEXT_MUTED = "#6b7280"
GOLD = "#fbbf24"
DANGER = "#ef4444"


def inject_global_css():
    """Inyecta CSS global en la pagina. Llamar una vez desde app.py."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


# =============================================================================
# CSS Global — estilos agresivos para aspecto de trading terminal premium
# =============================================================================

_GLOBAL_CSS = f"""
<style>
/* ======================================================================
   VARIABLES CSS GLOBALES
   ====================================================================== */
:root {{
    --accent: {ACCENT};
    --accent-dim: {ACCENT_DIM};
    --accent-glow: {ACCENT_GLOW};
    --bg-dark: {BG_DARK};
    --bg-card: {BG_CARD};
    --bg-card-hover: {BG_CARD_HOVER};
    --bg-surface: {BG_SURFACE};
    --border: {BORDER};
    --border-accent: {BORDER_ACCENT};
    --text-primary: {TEXT_PRIMARY};
    --text-muted: {TEXT_MUTED};
    --gold: {GOLD};
    --danger: {DANGER};
}}

/* ======================================================================
   FONDO CON GRID ANIMADA SUTIL — efecto tech/terminal
   ====================================================================== */
.stApp {{
    background-image:
        linear-gradient(rgba(0,255,65,0.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,255,65,0.02) 1px, transparent 1px) !important;
    background-size: 60px 60px !important;
}}

/* Animacion de scanline sutil */
.stApp::before {{
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 0;
    background: repeating-linear-gradient(
        0deg,
        transparent,
        transparent 2px,
        rgba(0,255,65,0.008) 2px,
        rgba(0,255,65,0.008) 4px
    );
}}

/* ======================================================================
   SIDEBAR — gradiente premium con separacion visual clara
   ====================================================================== */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #0d1117 0%, #0a0e14 50%, #070a0f 100%) !important;
    border-right: 1px solid rgba(0,255,65,0.08) !important;
}}

section[data-testid="stSidebar"] .stMarkdown p {{
    font-size: 0.92rem;
}}

/* Sidebar nav items hover */
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"] {{
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}}

section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"]:hover {{
    background: rgba(0,255,65,0.05) !important;
}}

section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"][aria-current="page"] {{
    background: rgba(0,255,65,0.08) !important;
    border-left: 2px solid #00ff41 !important;
}}

/* ======================================================================
   METRIC CARDS — glass-morphism con glow en hover
   ====================================================================== */
div[data-testid="stMetric"] {{
    background: linear-gradient(135deg, rgba(13,17,23,0.95), rgba(22,27,34,0.95)) !important;
    border: 1px solid rgba(0,255,65,0.08) !important;
    border-radius: 16px !important;
    padding: 20px 24px !important;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    position: relative;
    overflow: hidden;
}}

div[data-testid="stMetric"]::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,255,65,0.3), transparent);
    opacity: 0;
    transition: opacity 0.3s ease;
}}

div[data-testid="stMetric"]:hover {{
    border-color: rgba(0,255,65,0.2) !important;
    box-shadow: 0 0 30px rgba(0,255,65,0.06), 0 8px 32px rgba(0,0,0,0.3) !important;
    transform: translateY(-1px);
}}

div[data-testid="stMetric"]:hover::before {{
    opacity: 1;
}}

div[data-testid="stMetric"] label {{
    color: var(--text-muted) !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 500 !important;
}}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    font-size: 1.8rem !important;
    font-weight: 800 !important;
    color: #ffffff !important;
    text-shadow: 0 0 20px rgba(0,255,65,0.15);
    letter-spacing: -0.5px;
}}

div[data-testid="stMetric"] [data-testid="stMetricDelta"] {{
    font-size: 0.8rem !important;
    font-weight: 600 !important;
}}

/* ======================================================================
   DATAFRAMES / TABLAS — dark rows, accent header, sin bordes visibles
   ====================================================================== */
div[data-testid="stDataFrame"] {{
    border: 1px solid rgba(0,255,65,0.06) !important;
    border-radius: 16px !important;
    overflow: hidden !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.2);
}}

/* Header de tabla */
div[data-testid="stDataFrame"] th {{
    background: rgba(0,255,65,0.06) !important;
    color: #00ff41 !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    font-size: 0.7rem !important;
    letter-spacing: 1px !important;
    border-bottom: 1px solid rgba(0,255,65,0.1) !important;
}}

/* Filas alternadas */
div[data-testid="stDataFrame"] tr:nth-child(even) {{
    background: rgba(13,17,23,0.5) !important;
}}

div[data-testid="stDataFrame"] tr:nth-child(odd) {{
    background: rgba(22,27,34,0.3) !important;
}}

div[data-testid="stDataFrame"] tr:hover {{
    background: rgba(0,255,65,0.03) !important;
}}

div[data-testid="stDataFrame"] td {{
    border-color: rgba(255,255,255,0.02) !important;
}}

/* ======================================================================
   BOTONES — glow verde en hover, transiciones suaves
   ====================================================================== */
button[kind="primary"],
.stButton > button[kind="primary"] {{
    border-radius: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px !important;
    text-transform: uppercase !important;
    font-size: 0.8rem !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    border: none !important;
    box-shadow: 0 0 15px rgba(0,255,65,0.15) !important;
}}

button[kind="primary"]:hover,
.stButton > button[kind="primary"]:hover {{
    box-shadow: 0 0 30px rgba(0,255,65,0.3), 0 0 60px rgba(0,255,65,0.1) !important;
    transform: translateY(-1px) !important;
}}

button[kind="secondary"],
.stButton > button[kind="secondary"] {{
    border-radius: 10px !important;
    border: 1px solid rgba(0,255,65,0.15) !important;
    background: rgba(0,255,65,0.03) !important;
    transition: all 0.3s ease !important;
}}

button[kind="secondary"]:hover,
.stButton > button[kind="secondary"]:hover {{
    border-color: rgba(0,255,65,0.3) !important;
    background: rgba(0,255,65,0.06) !important;
    box-shadow: 0 0 20px rgba(0,255,65,0.08) !important;
}}

/* Download button */
.stDownloadButton > button {{
    border-radius: 10px !important;
    border: 1px solid rgba(0,255,65,0.15) !important;
    transition: all 0.3s ease !important;
}}

.stDownloadButton > button:hover {{
    border-color: rgba(0,255,65,0.3) !important;
    box-shadow: 0 0 15px rgba(0,255,65,0.1) !important;
}}

/* ======================================================================
   EXPANDERS — glass-morphism
   ====================================================================== */
div[data-testid="stExpander"] {{
    background: linear-gradient(135deg, rgba(13,17,23,0.6), rgba(22,27,34,0.6)) !important;
    border: 1px solid rgba(0,255,65,0.06) !important;
    border-radius: 16px !important;
    overflow: hidden;
    backdrop-filter: blur(5px);
}}

div[data-testid="stExpander"] details {{
    border: none !important;
}}

div[data-testid="stExpander"] summary {{
    font-weight: 600 !important;
}}

div[data-testid="stExpander"]:hover {{
    border-color: rgba(0,255,65,0.12) !important;
}}

/* ======================================================================
   TABS — estilo clean con indicador verde
   ====================================================================== */
button[data-baseweb="tab"] {{
    font-weight: 600 !important;
    letter-spacing: 0.3px;
    border-radius: 8px 8px 0 0 !important;
    transition: all 0.2s ease !important;
}}

button[data-baseweb="tab"]:hover {{
    background: rgba(0,255,65,0.03) !important;
}}

/* Indicador activo del tab */
div[data-baseweb="tab-highlight"] {{
    background-color: #00ff41 !important;
    box-shadow: 0 0 10px rgba(0,255,65,0.3) !important;
}}

/* ======================================================================
   SELECTBOX / INPUT — bordes coherentes con glow en focus
   ====================================================================== */
div[data-baseweb="select"] > div {{
    border-radius: 10px !important;
    border-color: rgba(0,255,65,0.1) !important;
    background: rgba(13,17,23,0.8) !important;
    transition: all 0.2s ease !important;
}}

div[data-baseweb="select"] > div:hover {{
    border-color: rgba(0,255,65,0.2) !important;
}}

div[data-baseweb="select"] > div:focus-within {{
    border-color: rgba(0,255,65,0.4) !important;
    box-shadow: 0 0 15px rgba(0,255,65,0.08) !important;
}}

input[type="text"], input[type="email"], input[type="password"] {{
    border-radius: 10px !important;
    border-color: rgba(0,255,65,0.1) !important;
    background: rgba(13,17,23,0.8) !important;
    transition: all 0.2s ease !important;
}}

input[type="text"]:focus, input[type="email"]:focus, input[type="password"]:focus {{
    border-color: rgba(0,255,65,0.4) !important;
    box-shadow: 0 0 15px rgba(0,255,65,0.08) !important;
}}

/* ======================================================================
   DIVIDER — linea verde sutil
   ====================================================================== */
hr {{
    border-color: rgba(0,255,65,0.06) !important;
    opacity: 1 !important;
}}

/* ======================================================================
   PROGRESS BAR — gradiente verde con glow
   ====================================================================== */
div[data-testid="stProgress"] > div > div {{
    background: linear-gradient(90deg, #00cc33, #00ff41) !important;
    box-shadow: 0 0 12px rgba(0,255,65,0.3) !important;
    border-radius: 4px !important;
}}

/* ======================================================================
   PLOTLY CHARTS — fondo transparente + borde sutil
   ====================================================================== */
.js-plotly-plot .plotly {{
    border-radius: 16px;
}}

div[data-testid="stPlotlyChart"] {{
    background: linear-gradient(135deg, rgba(13,17,23,0.5), rgba(22,27,34,0.3)) !important;
    border: 1px solid rgba(0,255,65,0.04) !important;
    border-radius: 16px !important;
    padding: 8px !important;
}}

/* ======================================================================
   SCROLL SUAVE + SCROLLBAR PERSONALIZADA
   ====================================================================== */
html {{
    scroll-behavior: smooth;
}}

::-webkit-scrollbar {{
    width: 6px;
    height: 6px;
}}

::-webkit-scrollbar-track {{
    background: transparent;
}}

::-webkit-scrollbar-thumb {{
    background: rgba(0,255,65,0.15);
    border-radius: 3px;
}}

::-webkit-scrollbar-thumb:hover {{
    background: rgba(0,255,65,0.3);
}}

/* ======================================================================
   CAPTIONS — color atenuado consistente
   ====================================================================== */
.stCaption, div[data-testid="stCaptionContainer"] {{
    color: var(--text-muted) !important;
}}

/* ======================================================================
   INFO / WARNING / SUCCESS / ERROR — estilos premium
   ====================================================================== */
div[data-testid="stAlert"] {{
    border-radius: 12px !important;
    border-left-width: 3px !important;
    backdrop-filter: blur(5px) !important;
}}

/* ======================================================================
   HEADERS — glow sutil en el texto
   ====================================================================== */
.stApp h1 {{
    text-shadow: 0 0 40px rgba(0,255,65,0.1);
}}

.stApp h2 {{
    text-shadow: 0 0 30px rgba(0,255,65,0.08);
}}

/* ======================================================================
   CHECKBOX — estilo coherente
   ====================================================================== */
div[data-baseweb="checkbox"] {{
    transition: all 0.2s ease;
}}

/* ======================================================================
   LINK BUTTON — estilo premium
   ====================================================================== */
.stLinkButton > a {{
    border-radius: 10px !important;
    transition: all 0.3s ease !important;
}}

.stLinkButton > a:hover {{
    box-shadow: 0 0 20px rgba(0,255,65,0.1) !important;
}}

/* ======================================================================
   ANIMACION DE PULSO PARA BADGES STRONG
   ====================================================================== */
@keyframes pulse-green {{
    0%, 100% {{ box-shadow: 0 0 8px rgba(0,255,65,0.2); }}
    50% {{ box-shadow: 0 0 20px rgba(0,255,65,0.4); }}
}}

.badge-strong-pulse {{
    animation: pulse-green 2s ease-in-out infinite;
}}

@keyframes glow-fade {{
    0%, 100% {{ opacity: 0.6; }}
    50% {{ opacity: 1; }}
}}

.glow-text {{
    animation: glow-fade 3s ease-in-out infinite;
}}

/* ======================================================================
   MULTISELECT / TAGS — coherente
   ====================================================================== */
span[data-baseweb="tag"] {{
    border-radius: 6px !important;
    background: rgba(0,255,65,0.1) !important;
    border: 1px solid rgba(0,255,65,0.2) !important;
}}

/* ======================================================================
   TOAST — fondo oscuro
   ====================================================================== */
div[data-testid="stToast"] {{
    background: rgba(13,17,23,0.95) !important;
    border: 1px solid rgba(0,255,65,0.1) !important;
    border-radius: 12px !important;
    backdrop-filter: blur(10px) !important;
}}
</style>
"""


# =============================================================================
# Componentes HTML reutilizables — version premium
# =============================================================================

def signal_badge_html(signal: str, size: str = "normal") -> str:
    """Genera HTML para un badge de senal con color, glow y forma de pastilla.

    Args:
        signal: Nivel de senal (STRONG, MEDIUM, WEAK, NONE)
        size: 'small' o 'normal'

    Returns:
        String HTML con el badge estilizado como pastilla premium.
    """
    colors = {
        "STRONG": ACCENT,
        "MEDIUM": GOLD,
        "WEAK": TEXT_MUTED,
        "NONE": "#374151",
    }
    color = colors.get(signal, TEXT_MUTED)

    # Glow y animacion solo para STRONG
    if signal == "STRONG":
        glow = (
            f"box-shadow: 0 0 12px {color}40, 0 0 24px {color}15; "
        )
        pulse_class = "badge-strong-pulse"
    else:
        glow = ""
        pulse_class = ""

    padding = "2px 10px" if size == "small" else "5px 16px"
    font_size = "0.7rem" if size == "small" else "0.8rem"

    return (
        f"<span role='status' aria-label='Senal: {signal}' "
        f"class='{pulse_class}' "
        f"style='background: {color}15; color: {color}; "
        f"padding: {padding}; border-radius: 20px; "
        f"font-size: {font_size}; font-weight: 700; "
        f"border: 1px solid {color}30; {glow} "
        f"letter-spacing: 0.5px; "
        f"display: inline-block;'>"
        f"{signal}</span>"
    )


def chain_badge_html(chain: str) -> str:
    """Genera HTML para un badge de blockchain con icono y color.

    Args:
        chain: Nombre de la cadena (solana, ethereum, base)

    Returns:
        String HTML con el badge estilizado como pastilla.
    """
    config = {
        "solana": {"color": "#9945FF", "icon": "S", "label": "SOL"},
        "ethereum": {"color": "#627EEA", "icon": "E", "label": "ETH"},
        "base": {"color": "#0052FF", "icon": "B", "label": "BASE"},
    }
    c = config.get(chain, {"color": TEXT_MUTED, "icon": "?", "label": chain or "?"})

    return (
        f"<span style='background: {c['color']}12; color: {c['color']}; "
        f"padding: 2px 10px; border-radius: 20px; font-size: 0.7rem; "
        f"font-weight: 700; border: 1px solid {c['color']}20; "
        f"letter-spacing: 0.5px; "
        f"display: inline-block;'>"
        f"{c['icon']}&middot;{c['label']}</span>"
    )


def role_badge_html(role: str) -> str:
    """Genera HTML para un badge de rol de usuario estilo premium.

    Args:
        role: Rol del usuario (admin, pro, free)

    Returns:
        String HTML con el badge estilizado.
    """
    config = {
        "admin": {"color": DANGER, "label": "ADMIN", "icon": ""},
        "pro": {"color": ACCENT, "label": "PRO", "icon": ""},
        "free": {"color": TEXT_MUTED, "label": "FREE", "icon": ""},
    }
    c = config.get(role, config["free"])

    return (
        f"<div role='status' aria-label='Plan: {c['label']}' "
        f"style='background: linear-gradient(135deg, {c['color']}10, {c['color']}05); "
        f"color: {c['color']}; "
        f"padding: 8px 20px; border-radius: 10px; text-align: center; "
        f"font-weight: 800; font-size: 0.8rem; "
        f"border: 1px solid {c['color']}25; "
        f"margin: 4px 0 8px 0; letter-spacing: 1.5px; "
        f"text-transform: uppercase;'>"
        f"{c['icon']} {c['label']}</div>"
    )


def card_container(content_html: str, border_color: str = "", glow: bool = False) -> str:
    """Genera HTML para un contenedor tipo tarjeta con glass-morphism.

    Args:
        content_html: Contenido HTML dentro de la tarjeta.
        border_color: Color del borde izquierdo (por defecto borde sutil).
        glow: Si True, aplica glow al borde.

    Returns:
        String HTML con la tarjeta estilizada.
    """
    border_style = f"border-left: 3px solid {border_color};" if border_color else ""
    glow_style = (
        f"box-shadow: 0 0 20px {border_color}15, 0 4px 24px rgba(0,0,0,0.2);"
        if glow and border_color
        else "box-shadow: 0 4px 24px rgba(0,0,0,0.15);"
    )

    return (
        f"<div style='background: linear-gradient(135deg, rgba(13,17,23,0.95), rgba(22,27,34,0.95)); "
        f"border: 1px solid rgba(0,255,65,0.06); border-radius: 16px; "
        f"padding: 20px 24px; margin: 8px 0; "
        f"backdrop-filter: blur(10px); "
        f"-webkit-backdrop-filter: blur(10px); "
        f"transition: all 0.3s ease; "
        f"{border_style} {glow_style}'>"
        f"{content_html}</div>"
    )


def stat_pill(label: str, value: str, color: str = ACCENT) -> str:
    """Genera HTML para una pastilla de estadistica compacta.

    Args:
        label: Texto descriptivo (ej: "Tokens")
        value: Valor a mostrar (ej: "8,385")
        color: Color del valor

    Returns:
        String HTML con la pastilla estilizada.
    """
    return (
        f"<div style='display: inline-block; "
        f"background: linear-gradient(135deg, rgba(13,17,23,0.95), rgba(22,27,34,0.95)); "
        f"border: 1px solid rgba(0,255,65,0.06); border-radius: 12px; "
        f"padding: 12px 20px; margin: 4px;'>"
        f"<span style='color: {TEXT_MUTED}; font-size: 0.7rem; "
        f"text-transform: uppercase; letter-spacing: 1px; "
        f"font-weight: 500;'>{label}</span><br>"
        f"<span style='color: {color}; font-size: 1.3rem; "
        f"font-weight: 800; text-shadow: 0 0 20px {color}30;'>{value}</span></div>"
    )


# =============================================================================
# Componentes HTML para KPI cards premium (overview / signals)
# =============================================================================

def kpi_card_html(
    icon: str,
    label: str,
    value: str,
    subtitle: str = "",
    color: str = ACCENT,
) -> str:
    """Genera HTML para una tarjeta KPI premium con icono, numero grande y label.

    Args:
        icon: Emoji del icono
        label: Etiqueta superior (ej: "STRONG SIGNALS")
        value: Valor grande (ej: "42")
        subtitle: Texto secundario debajo del valor (ej: "+5 hoy")
        color: Color del acento

    Returns:
        String HTML de la tarjeta KPI completa.
    """
    subtitle_html = (
        f"<div style='color: {TEXT_MUTED}; font-size: 0.75rem; "
        f"margin-top: 4px;'>{subtitle}</div>"
        if subtitle else ""
    )

    return (
        f"<div style='"
        f"background: linear-gradient(135deg, rgba(13,17,23,0.95), rgba(22,27,34,0.95)); "
        f"border: 1px solid rgba(0,255,65,0.06); "
        f"border-radius: 16px; padding: 24px; "
        f"backdrop-filter: blur(10px); "
        f"-webkit-backdrop-filter: blur(10px); "
        f"transition: all 0.3s ease; "
        f"position: relative; overflow: hidden;'>"
        # Linea superior decorativa
        f"<div style='position: absolute; top: 0; left: 0; right: 0; height: 1px; "
        f"background: linear-gradient(90deg, transparent, {color}40, transparent);'></div>"
        # Icono
        f"<div style='font-size: 1.5rem; margin-bottom: 8px; "
        f"filter: saturate(0.8);'>{icon}</div>"
        # Label
        f"<div style='color: {TEXT_MUTED}; font-size: 0.65rem; "
        f"text-transform: uppercase; letter-spacing: 1.5px; "
        f"font-weight: 600; margin-bottom: 6px;'>{label}</div>"
        # Valor grande
        f"<div style='color: #ffffff; font-size: 2rem; font-weight: 800; "
        f"text-shadow: 0 0 25px {color}25; "
        f"letter-spacing: -1px; line-height: 1;'>{value}</div>"
        # Subtitulo
        f"{subtitle_html}"
        f"</div>"
    )


def signal_card_html(
    symbol: str,
    name: str,
    chain: str,
    signal: str,
    probability: float,
    signal_color: str,
    meta_html: str = "",
    links_html: str = "",
    conf_badge: str = "",
    conf_color: str = "",
    mc_str: str = "",
    extra_badges: str = "",
) -> str:
    """Genera HTML para una tarjeta de senal premium estilo trading card.

    Args:
        symbol: Simbolo del token (ej: "$BONK")
        name: Nombre completo del token
        chain: Blockchain (solana, ethereum, base)
        signal: Nivel de senal (STRONG, MEDIUM, WEAK)
        probability: Probabilidad (0.0 - 1.0)
        signal_color: Color hex del nivel de senal
        meta_html: HTML de metadata (MC, tiempo, etc.)
        links_html: HTML de enlaces (DexScreener, GeckoTerminal)
        conf_badge: Badge de confianza (Alta/Media/Baja)
        conf_color: Color de confianza
        mc_str: Market cap formateado
        extra_badges: HTML de badges adicionales (ej: rug badge)

    Returns:
        String HTML de la tarjeta de senal completa.
    """
    score_pct = int(probability * 100)

    # Glow para STRONG
    if signal == "STRONG":
        glow = (
            f"box-shadow: 0 0 25px {signal_color}12, "
            f"0 4px 24px rgba(0,0,0,0.2); "
        )
        border_glow = f"border-color: {signal_color}25;"
    else:
        glow = "box-shadow: 0 4px 24px rgba(0,0,0,0.15);"
        border_glow = ""

    # Badge de confianza
    conf_html = ""
    if conf_badge and conf_color:
        conf_html = (
            f"<span style='background: {conf_color}12; color: {conf_color}; "
            f"padding: 2px 10px; border-radius: 20px; font-size: 0.65rem; "
            f"font-weight: 700; border: 1px solid {conf_color}20; "
            f"letter-spacing: 0.3px;'>"
            f"CONF: {conf_badge}</span>"
        )

    # Market cap badge
    mc_html = ""
    if mc_str:
        mc_html = (
            f"<span style='background: rgba(255,255,255,0.04); color: {TEXT_MUTED}; "
            f"padding: 2px 10px; border-radius: 20px; font-size: 0.65rem; "
            f"font-weight: 600; border: 1px solid rgba(255,255,255,0.06);'>"
            f"MC {mc_str}</span>"
        )

    token_label = f"{name} ({symbol})" if name and symbol else (symbol or name or "???")

    return (
        f"<div style='"
        f"background: linear-gradient(135deg, rgba(13,17,23,0.95), rgba(22,27,34,0.95)); "
        f"border: 1px solid rgba(0,255,65,0.06); "
        f"border-left: 3px solid {signal_color}; "
        f"border-radius: 16px; "
        f"padding: 20px 24px; margin-bottom: 10px; "
        f"backdrop-filter: blur(10px); "
        f"-webkit-backdrop-filter: blur(10px); "
        f"transition: all 0.3s ease; "
        f"{glow} {border_glow}' "
        f"aria-label='{token_label}: senal {signal}, {probability:.0%}'>"
        # Fila 1: nombre + badges
        f"<div style='display: flex; align-items: center; flex-wrap: wrap; gap: 8px; "
        f"margin-bottom: 10px;'>"
        f"<span style='font-size: 1.15rem; font-weight: 800; color: #ffffff; "
        f"letter-spacing: -0.3px;'>{token_label}</span>"
        f"{signal_badge_html(signal, 'small')}"
        f"{chain_badge_html(chain)}"
        f"{conf_html}"
        f"{mc_html}"
        f"{extra_badges}"
        f"</div>"
        # Fila 2: barra de score + porcentaje
        f"<div style='display: flex; align-items: center; gap: 12px;'>"
        f"<div style='flex: 1; background: {BG_SURFACE}; border-radius: 8px; "
        f"height: 6px; overflow: hidden;'>"
        f"<div style='width: {score_pct}%; height: 100%; border-radius: 8px; "
        f"background: linear-gradient(90deg, {signal_color}cc, {signal_color}); "
        f"box-shadow: 0 0 10px {signal_color}40; "
        f"transition: width 0.5s ease;'></div>"
        f"</div>"
        f"<span style='color: {signal_color}; font-weight: 800; "
        f"font-size: 1rem; min-width: 48px; text-align: right; "
        f"text-shadow: 0 0 15px {signal_color}30;'>{probability:.0%}</span>"
        f"</div>"
        # Fila 3: metadata + links
        f"<div style='display: flex; justify-content: space-between; "
        f"align-items: center; margin-top: 10px; flex-wrap: wrap; gap: 4px;'>"
        f"<span style='color: {TEXT_MUTED}; font-size: 0.75rem;'>{meta_html}</span>"
        f"<div>{links_html}</div>"
        f"</div>"
        f"</div>"
    )


def rug_badge_html(label_multi: str) -> str:
    """Badge de advertencia para tokens clasificados como rug o pump_and_dump.

    Genera una pastilla roja compacta con icono que se muestra junto
    al badge de senal en las tarjetas de senales y overview.

    Args:
        label_multi: Etiqueta multiclase del labeler (rug, pump_and_dump, etc.)

    Returns:
        String HTML con el badge rojo, o cadena vacia si no aplica.
    """
    if label_multi == "rug":
        color = DANGER
        icon = "&#9760;"  # calavera
        label = "RUG"
    elif label_multi == "pump_and_dump":
        color = "#ff6b35"  # naranja
        icon = "&#9888;"   # warning
        label = "P&amp;D"
    else:
        return ""

    return (
        f"<span role='status' aria-label='Alerta: {label}' "
        f"style='background: {color}20; color: {color}; "
        f"padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; "
        f"font-weight: 700; border: 1px solid {color}40; "
        f"letter-spacing: 0.3px; display: inline-block;'>"
        f"{icon} {label}</span>"
    )


def rug_warning_card_html(label_multi: str) -> str:
    """Tarjeta de advertencia prominente para tokens rug/pump_and_dump.

    Se muestra en la pagina de busqueda de token cuando el token
    tiene un label peligroso. Es informativa, no bloqueante.

    Args:
        label_multi: Etiqueta multiclase del labeler.

    Returns:
        String HTML con la tarjeta de advertencia, o cadena vacia si no aplica.
    """
    if label_multi == "rug":
        color = DANGER
        icon = "&#9760;"
        title = "RUG PULL DETECTADO"
        msg = (
            "Este token fue clasificado como <strong>rug pull</strong>: "
            "el precio colapso mas del 99% en las primeras horas. "
            "Es extremadamente probable que los creadores hayan retirado la liquidez."
        )
    elif label_multi == "pump_and_dump":
        color = "#ff6b35"
        icon = "&#9888;"
        title = "PUMP &amp; DUMP DETECTADO"
        msg = (
            "Este token fue clasificado como <strong>pump &amp; dump</strong>: "
            "subio significativamente pero no mantuvo el precio. "
            "Patron tipico de manipulacion coordinada."
        )
    else:
        return ""

    return (
        f"<div style='background: linear-gradient(135deg, {color}08, {color}04); "
        f"border: 1px solid {color}30; border-left: 4px solid {color}; "
        f"border-radius: 12px; padding: 16px 20px; margin: 12px 0;'>"
        f"<div style='display: flex; align-items: center; gap: 8px; margin-bottom: 8px;'>"
        f"<span style='font-size: 1.3rem;'>{icon}</span>"
        f"<span style='color: {color}; font-weight: 800; font-size: 0.85rem; "
        f"letter-spacing: 1px; text-transform: uppercase;'>{title}</span>"
        f"</div>"
        f"<p style='color: {TEXT_MUTED}; font-size: 0.82rem; margin: 0; line-height: 1.5;'>"
        f"{msg}</p>"
        f"</div>"
    )


def blurred_signal_card_html(signal: str, signal_color: str) -> str:
    """Genera HTML para una tarjeta de senal borrosa (usuarios Free).

    Args:
        signal: Nivel de senal (STRONG, MEDIUM, WEAK)
        signal_color: Color del nivel de senal

    Returns:
        String HTML de la tarjeta borrosa.
    """
    return (
        f"<div style='"
        f"background: linear-gradient(135deg, rgba(13,17,23,0.95), rgba(22,27,34,0.95)); "
        f"border: 1px solid rgba(0,255,65,0.06); "
        f"border-left: 3px solid {signal_color}; "
        f"border-radius: 16px; padding: 20px 24px;' "
        f"aria-label='Senal {signal} — detalles ocultos (plan Pro)'>"
        f"<div style='margin-bottom: 10px;'>"
        f"<span style='filter: blur(6px); font-size: 1.15rem; font-weight: 800; "
        f"color: #ffffff;' aria-hidden='true'>TOKEN_SYMBOL</span>"
        f"<span style='margin-left: 8px;'>{signal_badge_html(signal, 'small')}</span>"
        f"</div>"
        f"<div style='display: flex; align-items: center; gap: 12px;'>"
        f"<div style='flex: 1; background: {BG_SURFACE}; border-radius: 8px; "
        f"height: 6px; overflow: hidden;'>"
        f"<div style='width: 75%; height: 100%; border-radius: 8px; "
        f"background: linear-gradient(90deg, {signal_color}80, {signal_color}40); "
        f"filter: blur(3px);'></div>"
        f"</div>"
        f"<span style='filter: blur(5px); color: {TEXT_MUTED};' "
        f"aria-hidden='true'>??%</span>"
        f"</div>"
        f"</div>"
    )
