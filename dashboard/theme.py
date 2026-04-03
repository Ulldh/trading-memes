"""
theme.py — CSS global y componentes de estilo reutilizables.

Inyecta estilos personalizados en el dashboard para un look
profesional y coherente con la landing (terminal/hacker aesthetic).

Uso:
    from dashboard.theme import inject_global_css
    inject_global_css()  # llamar una vez en app.py
"""

import streamlit as st


# =============================================================================
# Paleta de colores (misma que constants.py, pero como CSS vars)
# =============================================================================

ACCENT = "#00ff41"
ACCENT_DIM = "rgba(0, 255, 65, 0.15)"
ACCENT_GLOW = "0 0 20px rgba(0, 255, 65, 0.3)"
BG_DARK = "#0a0a0a"
BG_CARD = "#111111"
BG_CARD_HOVER = "#1a1a1a"
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
# CSS Global — estilos que se aplican a todo el dashboard
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
    --border: {BORDER};
    --border-accent: {BORDER_ACCENT};
    --text-primary: {TEXT_PRIMARY};
    --text-muted: {TEXT_MUTED};
    --gold: {GOLD};
    --danger: {DANGER};
}}

/* ======================================================================
   SIDEBAR — aspecto premium
   ====================================================================== */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #0d0d0d 0%, #0a0a0a 100%) !important;
    border-right: 1px solid var(--border) !important;
}}

section[data-testid="stSidebar"] .stMarkdown p {{
    font-size: 0.92rem;
}}

/* ======================================================================
   METRIC CARDS — efecto tarjeta con borde sutil
   ====================================================================== */
div[data-testid="stMetric"] {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    transition: border-color 0.2s ease;
}}

div[data-testid="stMetric"]:hover {{
    border-color: var(--border-accent);
}}

div[data-testid="stMetric"] label {{
    color: var(--text-muted) !important;
    font-size: 0.8rem !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: var(--text-primary) !important;
}}

div[data-testid="stMetric"] [data-testid="stMetricDelta"] {{
    font-size: 0.85rem;
}}

/* ======================================================================
   DATAFRAMES / TABLAS — aspecto mas limpio
   ====================================================================== */
div[data-testid="stDataFrame"] {{
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    overflow: hidden;
}}

/* ======================================================================
   BOTONES — consistencia visual
   ====================================================================== */
button[kind="primary"] {{
    border-radius: 8px !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px;
}}

button[kind="secondary"] {{
    border-radius: 8px !important;
    border: 1px solid var(--border) !important;
}}

/* ======================================================================
   EXPANDERS — bordes sutiles
   ====================================================================== */
div[data-testid="stExpander"] {{
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    overflow: hidden;
}}

div[data-testid="stExpander"] details {{
    border: none !important;
}}

/* ======================================================================
   TABS — estilo limpio
   ====================================================================== */
button[data-baseweb="tab"] {{
    font-weight: 500 !important;
    letter-spacing: 0.3px;
}}

/* ======================================================================
   SELECTBOX / INPUT — bordes coherentes
   ====================================================================== */
div[data-baseweb="select"] > div {{
    border-radius: 8px !important;
    border-color: var(--border) !important;
}}

input[type="text"], input[type="email"], input[type="password"] {{
    border-radius: 8px !important;
}}

/* ======================================================================
   DIVIDER — mas sutil
   ====================================================================== */
hr {{
    border-color: var(--border) !important;
    opacity: 0.5;
}}

/* ======================================================================
   PROGRESS BAR — color acento
   ====================================================================== */
div[data-testid="stProgress"] > div > div {{
    background-color: var(--accent) !important;
}}

/* ======================================================================
   PLOTLY CHARTS — fondo transparente
   ====================================================================== */
.js-plotly-plot .plotly {{
    border-radius: 12px;
}}

/* ======================================================================
   SCROLL SUAVE
   ====================================================================== */
html {{
    scroll-behavior: smooth;
}}

/* ======================================================================
   CAPTIONS — color atenuado consistente
   ====================================================================== */
.stCaption, div[data-testid="stCaptionContainer"] {{
    color: var(--text-muted) !important;
}}
</style>
"""


# =============================================================================
# Componentes HTML reutilizables
# =============================================================================

def signal_badge_html(signal: str, size: str = "normal") -> str:
    """Genera HTML para un badge de senal con color y glow.

    Args:
        signal: Nivel de senal (STRONG, MEDIUM, WEAK, NONE)
        size: 'small' o 'normal'

    Returns:
        String HTML con el badge estilizado.
    """
    colors = {
        "STRONG": ACCENT,
        "MEDIUM": GOLD,
        "WEAK": TEXT_MUTED,
        "NONE": "#374151",
    }
    color = colors.get(signal, TEXT_MUTED)

    # Glow solo para STRONG
    glow = f"box-shadow: 0 0 12px {color}40;" if signal == "STRONG" else ""
    padding = "2px 8px" if size == "small" else "4px 14px"
    font_size = "0.75rem" if size == "small" else "0.85rem"

    return (
        f"<span role='status' aria-label='Senal: {signal}' "
        f"style='background: {color}20; color: {color}; "
        f"padding: {padding}; border-radius: 6px; "
        f"font-size: {font_size}; font-weight: 700; "
        f"border: 1px solid {color}40; {glow} "
        f"display: inline-block;'>"
        f"{signal}</span>"
    )


def chain_badge_html(chain: str) -> str:
    """Genera HTML para un badge de blockchain con icono y color.

    Args:
        chain: Nombre de la cadena (solana, ethereum, base)

    Returns:
        String HTML con el badge estilizado.
    """
    config = {
        "solana": {"color": "#9945FF", "icon": "S", "label": "Solana"},
        "ethereum": {"color": "#627EEA", "icon": "E", "label": "Ethereum"},
        "base": {"color": "#0052FF", "icon": "B", "label": "Base"},
    }
    c = config.get(chain, {"color": TEXT_MUTED, "icon": "?", "label": chain or "?"})

    return (
        f"<span style='background: {c['color']}20; color: {c['color']}; "
        f"padding: 2px 10px; border-radius: 6px; font-size: 0.8rem; "
        f"font-weight: 600; border: 1px solid {c['color']}30; "
        f"display: inline-block;'>"
        f"{c['icon']} {c['label']}</span>"
    )


def role_badge_html(role: str) -> str:
    """Genera HTML para un badge de rol de usuario.

    Args:
        role: Rol del usuario (admin, pro, free)

    Returns:
        String HTML con el badge estilizado.
    """
    config = {
        "admin": {"color": DANGER, "label": "Admin", "icon": ""},
        "pro": {"color": ACCENT, "label": "Pro", "icon": ""},
        "free": {"color": TEXT_MUTED, "label": "Free", "icon": ""},
    }
    c = config.get(role, config["free"])

    return (
        f"<div role='status' aria-label='Plan: {c['label']}' "
        f"style='background: {c['color']}15; color: {c['color']}; "
        f"padding: 6px 16px; border-radius: 8px; text-align: center; "
        f"font-weight: 700; font-size: 0.85rem; "
        f"border: 1px solid {c['color']}30; "
        f"margin: 4px 0 8px 0; letter-spacing: 0.5px;'>"
        f"{c['icon']} {c['label']}</div>"
    )


def card_container(content_html: str, border_color: str = "", glow: bool = False) -> str:
    """Genera HTML para un contenedor tipo tarjeta.

    Args:
        content_html: Contenido HTML dentro de la tarjeta.
        border_color: Color del borde izquierdo (por defecto borde sutil).
        glow: Si True, aplica glow al borde.

    Returns:
        String HTML con la tarjeta estilizada.
    """
    border_style = f"border-left: 3px solid {border_color};" if border_color else ""
    glow_style = f"box-shadow: 0 0 15px {border_color}20;" if glow and border_color else ""

    return (
        f"<div style='background: {BG_CARD}; "
        f"border: 1px solid {BORDER}; border-radius: 12px; "
        f"padding: 16px 20px; margin: 8px 0; "
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
        f"<div style='display: inline-block; background: {BG_CARD}; "
        f"border: 1px solid {BORDER}; border-radius: 8px; "
        f"padding: 8px 16px; margin: 4px;'>"
        f"<span style='color: {TEXT_MUTED}; font-size: 0.75rem; "
        f"text-transform: uppercase; letter-spacing: 0.5px;'>{label}</span><br>"
        f"<span style='color: {color}; font-size: 1.1rem; "
        f"font-weight: 700;'>{value}</span></div>"
    )
