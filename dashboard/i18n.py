"""
i18n.py — Sistema de internacionalización simple para Streamlit.
Carga traducciones desde archivos JSON en dashboard/locales/.
"""
import json
from pathlib import Path
import streamlit as st

LOCALES_DIR = Path(__file__).parent / "locales"
SUPPORTED_LOCALES = ["es", "en", "de", "pt", "fr"]
DEFAULT_LOCALE = "es"

_translations = {}


def _load_translations():
    """Carga todos los archivos de traducción al iniciar."""
    global _translations
    if _translations:
        return
    for locale in SUPPORTED_LOCALES:
        filepath = LOCALES_DIR / f"{locale}.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                _translations[locale] = json.load(f)


def get_locale() -> str:
    """Obtiene el idioma actual de la sesión."""
    if "locale" not in st.session_state:
        st.session_state.locale = DEFAULT_LOCALE
    return st.session_state.locale


def set_locale(locale: str):
    """Establece el idioma de la sesión."""
    if locale in SUPPORTED_LOCALES:
        st.session_state.locale = locale


def t(key: str, default: str = "") -> str:
    """Traduce una clave al idioma actual.

    Args:
        key: Clave con punto como separador (ej: "auth.login_btn")
        default: Texto por defecto si no se encuentra la clave

    Returns:
        Texto traducido o default
    """
    _load_translations()
    locale = get_locale()
    translations = _translations.get(locale, _translations.get(DEFAULT_LOCALE, {}))

    # Navigate nested keys: "auth.login_btn" -> translations["auth"]["login_btn"]
    parts = key.split(".")
    current = translations
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default or key

    return current if isinstance(current, str) else default or key


def render_language_selector():
    """Renderiza el selector de idioma en el sidebar."""
    flags = {
        "es": "🇪🇸 Español",
        "en": "🇬🇧 English",
        "de": "🇩🇪 Deutsch",
        "pt": "🇧🇷 Português",
        "fr": "🇫🇷 Français",
    }

    current = get_locale()
    options = list(flags.keys())

    selected = st.sidebar.selectbox(
        "🌐 Idioma",
        options=options,
        format_func=lambda x: flags[x],
        index=options.index(current) if current in options else 0,
        key="language_selector",
    )

    if selected != current:
        set_locale(selected)
        st.rerun()
