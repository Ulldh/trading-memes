"""
alerts_config.py — Configuración de alertas Telegram personales.

Permite a suscriptores Pro configurar que tipo de señales recibir
en su Telegram: score minimo, cadenas, nivel de senal, y alertas
de sistema (health monitor, drift). Incluye vista previa del mensaje
y envio de prueba.

Requisitos:
- Cuenta Pro (verificada via paywall)
- Bot de Telegram configurado (TELEGRAM_BOT_TOKEN en env)
- Chat ID del usuario (se guarda en tabla profiles de Supabase)
"""

import logging
import os
from datetime import datetime

import streamlit as st
import requests

from src.data.supabase_storage import get_storage as _get_storage

logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES
# ============================================================

# Cadenas soportadas para filtrar senales
CHAINS_DISPONIBLES = ["Solana", "Ethereum", "Base"]

# Niveles de senal (de mas estricto a mas permisivo)
NIVELES_SENAL = {
    "STRONG only": ["STRONG"],
    "MEDIUM+": ["STRONG", "MEDIUM"],
    "ALL": ["STRONG", "MEDIUM", "WEAK"],
}

# Colores para la vista previa (consistentes con constants.py)
_SIGNAL_EMOJI = {
    "STRONG": "🟢",
    "MEDIUM": "🟡",
    "WEAK": "🔵",
}


# ============================================================
# HELPERS
# ============================================================

@st.cache_resource
def get_storage():
    """Crea una instancia de Storage cacheada para no reconectar cada vez."""
    return _get_storage()


def _get_bot_token() -> str:
    """Obtiene el token del bot de Telegram desde variables de entorno."""
    try:
        from config import TELEGRAM_BOT_TOKEN
        return TELEGRAM_BOT_TOKEN
    except (ImportError, AttributeError):
        return os.getenv("TELEGRAM_BOT_TOKEN", "")


def _send_telegram_message(chat_id: str, text: str) -> dict:
    """
    Envia un mensaje de Telegram via Bot API.

    Args:
        chat_id: ID del chat del usuario.
        text: Texto del mensaje (soporta Markdown).

    Returns:
        Dict con 'ok' (bool) y 'description' (str) del resultado.
    """
    bot_token = _get_bot_token()
    if not bot_token:
        return {"ok": False, "description": "TELEGRAM_BOT_TOKEN no configurado en el servidor."}

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        return {
            "ok": data.get("ok", False),
            "description": data.get("description", "Mensaje enviado correctamente."),
        }
    except requests.RequestException as e:
        return {"ok": False, "description": f"Error de conexion: {e}"}


def _load_user_profile() -> dict:
    """
    Carga el perfil del usuario actual desde Supabase.

    Busca por user_id en session_state. Retorna dict vacio si no hay perfil.
    """
    user_id = st.session_state.get("user", {}).get("id")
    if not user_id:
        return {}

    try:
        storage = get_storage()
        df = storage.query(
            "SELECT * FROM profiles WHERE id = ?", (user_id,)
        )
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception:
        pass

    return {}


def _save_telegram_chat_id(user_id: str, chat_id: str) -> bool:
    """
    Guarda el chat_id de Telegram en la tabla profiles.

    Returns:
        True si se guardo correctamente, False en caso de error.
    """
    try:
        storage = get_storage()
        storage.execute(
            "UPDATE profiles SET telegram_chat_id = ? WHERE id = ?",
            (chat_id, user_id),
        )
        return True
    except Exception as e:
        logger.exception("Error al guardar chat ID de Telegram")
        st.error("Se produjo un error inesperado. Inténtalo de nuevo.")
        return False


def _build_preview_message(prefs: dict) -> str:
    """
    Construye un mensaje de ejemplo basado en las preferencias actuales.

    Genera un mensaje Telegram simulado con datos ficticios para que
    el usuario vea como luciran sus alertas.
    """
    score_min = prefs.get("score_minimo", 0.65)
    chains = prefs.get("chains", CHAINS_DISPONIBLES)
    nivel = prefs.get("nivel_minimo", "MEDIUM+")
    niveles_activos = NIVELES_SENAL.get(nivel, ["STRONG", "MEDIUM"])

    # Senal de ejemplo
    signal_level = niveles_activos[0]  # Mejor senal del nivel configurado
    emoji = _SIGNAL_EMOJI.get(signal_level, "⚪")

    chain_ejemplo = chains[0] if chains else "Solana"

    msg = (
        f"{emoji} *SENAL {signal_level}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*Token:* EXAMPLE/SOL\n"
        f"*Chain:* {chain_ejemplo}\n"
        f"*Score:* {score_min + 0.10:.2f}\n"
        f"*Precio:* $0.00234\n"
        f"*Vol 24h:* $125,430\n"
        f"*Liquidez:* $45,200\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"_Gem Detector v12 — {datetime.now().strftime('%d/%m/%Y %H:%M')}_"
    )

    return msg


def _build_test_message() -> str:
    """Mensaje de prueba para verificar la conexion."""
    return (
        "✅ *Conexion exitosa*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Tu Telegram esta conectado con Gem Detector.\n"
        "Recibiras alertas segun tu configuración.\n"
        f"\n_Test enviado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}_"
    )


# ============================================================
# PREFERENCIAS (Supabase + session_state como cache)
# ============================================================

_DEFAULTS = {
    "alert_senales_diarias": True,
    "alert_score_minimo": 0.65,
    "alert_chains": CHAINS_DISPONIBLES.copy(),
    "alert_nivel_minimo": "MEDIUM+",
    "alert_health_monitor": True,
    "alert_drift_alerts": False,
}

# Mapeo entre las claves internas de session_state y las columnas de la tabla
_NIVEL_TO_MIN_SIGNAL = {
    "STRONG only": "STRONG",
    "MEDIUM+": "MEDIUM",
    "ALL": "WEAK",
}
_MIN_SIGNAL_TO_NIVEL = {v: k for k, v in _NIVEL_TO_MIN_SIGNAL.items()}

# Mapeo de cadenas: UI usa capitalizadas, BD usa minusculas
_CHAINS_TO_DB = {c: c.lower() for c in CHAINS_DISPONIBLES}
_CHAINS_FROM_DB = {c.lower(): c for c in CHAINS_DISPONIBLES}


def _load_preferences_from_db(user_id: str) -> dict:
    """
    Carga las preferencias desde Supabase y las convierte al formato
    interno de session_state.

    Returns:
        Dict con las claves de _DEFAULTS, con valores de DB o defaults.
    """
    prefs = _DEFAULTS.copy()
    if not user_id:
        return prefs

    try:
        storage = get_storage()
        row = storage.get_alert_preferences(user_id)
        if row:
            # min_signal -> nivel_minimo
            min_signal = row.get("min_signal")
            if min_signal and min_signal in _MIN_SIGNAL_TO_NIVEL:
                prefs["alert_nivel_minimo"] = _MIN_SIGNAL_TO_NIVEL[min_signal]

            # chains (jsonb list de strings minusculas) -> lista capitalizadas
            chains_db = row.get("chains")
            if chains_db and isinstance(chains_db, list) and len(chains_db) > 0:
                prefs["alert_chains"] = [
                    _CHAINS_FROM_DB.get(c, c.capitalize()) for c in chains_db
                ]

            # min_probability -> score_minimo
            prob = row.get("min_probability")
            if prob is not None:
                prefs["alert_score_minimo"] = float(prob)

            # enabled -> senales_diarias (interpretamos enabled como el toggle principal)
            enabled = row.get("enabled")
            if enabled is not None:
                prefs["alert_senales_diarias"] = bool(enabled)
    except Exception:
        logger.exception("Error cargando preferencias desde Supabase")

    return prefs


def _init_preferences(user_id: str = ""):
    """
    Inicializa las preferencias en session_state.

    Si ya estan cargadas para este usuario, no vuelve a consultar Supabase.
    Si cambia el usuario o es la primera carga, consulta Supabase.
    """
    loaded_for = st.session_state.get("_alert_prefs_loaded_for")
    if loaded_for == user_id and "alert_senales_diarias" in st.session_state:
        return  # Ya cargadas para este usuario

    prefs = _load_preferences_from_db(user_id)
    for key, value in prefs.items():
        st.session_state[key] = value
    st.session_state["_alert_prefs_loaded_for"] = user_id


def _save_preferences_to_db(user_id: str, prefs: dict) -> bool:
    """
    Persiste las preferencias en Supabase y actualiza session_state.

    Args:
        user_id: UUID del usuario.
        prefs: Dict con claves de _DEFAULTS (valores de formulario).

    Returns:
        True si se guardo correctamente.
    """
    if not user_id:
        return False

    # Convertir formato UI a formato DB
    nivel = prefs.get("alert_nivel_minimo", "MEDIUM+")
    chains_ui = prefs.get("alert_chains", CHAINS_DISPONIBLES)

    db_prefs = {
        "min_signal": _NIVEL_TO_MIN_SIGNAL.get(nivel, "MEDIUM"),
        "chains": [_CHAINS_TO_DB.get(c, c.lower()) for c in chains_ui],
        "min_probability": prefs.get("alert_score_minimo", 0.65),
        "enabled": prefs.get("alert_senales_diarias", True),
    }

    try:
        storage = get_storage()
        return storage.upsert_alert_preferences(user_id, db_prefs)
    except Exception:
        logger.exception("Error guardando preferencias en Supabase")
        return False


# ============================================================
# RENDER PRINCIPAL
# ============================================================

def render():
    """Configuración de Alertas Telegram — personaliza tus notificaciones."""

    # --- Gate de acceso Pro ---
    try:
        from dashboard.paywall import check_feature_access, show_upgrade_prompt
        if not check_feature_access("telegram_alerts"):
            show_upgrade_prompt("Alertas Telegram")
            return
    except ImportError:
        pass  # Sin paywall en desarrollo

    st.header("🔔 Alertas Telegram")
    st.caption("Configura que señales quieres recibir en tu Telegram personal.")

    # Obtener user_id e inicializar preferencias (carga desde Supabase si necesario)
    user_id = st.session_state.get("user", {}).get("id", "")
    _init_preferences(user_id)

    # Cargar perfil del usuario
    profile = _load_user_profile()
    telegram_connected = bool(profile.get("telegram_chat_id"))

    # ==============================================================
    # SECCION 1: Estado de conexion con Telegram
    # ==============================================================
    st.subheader("Conexion con Telegram")

    if telegram_connected:
        chat_id = profile["telegram_chat_id"]
        # Mostrar estado conectado con estilo
        st.success(
            f"Telegram conectado — Chat ID: `{chat_id[:4]}...{chat_id[-4:]}`"
            if len(str(chat_id)) > 8
            else f"Telegram conectado — Chat ID: `{chat_id}`"
        )

        # Opcion para desconectar
        if st.button("Desconectar Telegram", type="secondary"):
            user_id = st.session_state.get("user", {}).get("id")
            if user_id and _save_telegram_chat_id(user_id, ""):
                st.success("Telegram desconectado correctamente.")
                st.rerun()
    else:
        st.warning("Telegram no conectado. Sigue estos pasos para conectar:")

        st.markdown("""
        **Cómo conectar tu Telegram:**

        1. Abre Telegram y busca **@Ull_trading_bot**
        2. Envia el comando `/start`
        3. El bot te respondera con tu **Chat ID**
        4. Copia ese Chat ID y pegalo aqui abajo
        """)

        # Input para el Chat ID
        col_input, col_btn = st.columns([3, 1])
        with col_input:
            new_chat_id = st.text_input(
                "Tu Chat ID de Telegram",
                placeholder="Ej: 1558705287",
                help="Número que te da el bot al enviar /start.",
                label_visibility="collapsed",
            )
        with col_btn:
            conectar_clicked = st.button("Conectar", type="primary", use_container_width=True)

        if conectar_clicked:
            if not new_chat_id or not new_chat_id.strip().lstrip("-").isdigit():
                st.error("Introduce un Chat ID valido (solo números).")
            else:
                user_id = st.session_state.get("user", {}).get("id")
                if not user_id:
                    st.error("No se encontro tu sesión. Inicia sesión de nuevo.")
                else:
                    # Verificar enviando un mensaje de prueba
                    result = _send_telegram_message(
                        new_chat_id.strip(),
                        _build_test_message(),
                    )
                    if result["ok"]:
                        if _save_telegram_chat_id(user_id, new_chat_id.strip()):
                            st.success(
                                "Telegram conectado correctamente. "
                                "Revisa tu Telegram para confirmar."
                            )
                            st.rerun()
                    else:
                        st.error(
                            f"No se pudo conectar: {result['description']}. "
                            "Verifica que el Chat ID es correcto y que has "
                            "iniciado el bot con /start."
                        )

    st.divider()

    # ==============================================================
    # SECCION 2: Preferencias de alertas
    # ==============================================================
    st.subheader("Preferencias de alertas")

    st.caption(
        "Personaliza que tipo de alertas quieres recibir. "
        "Los cambios se aplican inmediatamente al guardar."
    )

    with st.form("alert_preferences_form"):
        # --- Senales diarias ---
        senales_diarias = st.toggle(
            "Señales diarias",
            value=st.session_state["alert_senales_diarias"],
            help="Recibe las señales del modelo ML cada dia (tokens con potencial de ser gems).",
        )

        # --- Score minimo ---
        score_minimo = st.slider(
            "Score minimo",
            min_value=0.50,
            max_value=0.95,
            value=st.session_state["alert_score_minimo"],
            step=0.05,
            format="%.2f",
            help=(
                "Solo recibiras alertas de tokens con score igual o superior a este valor. "
                "Mas alto = menos alertas pero mas fiables."
            ),
        )

        # --- Cadenas ---
        chains_seleccionadas = st.multiselect(
            "Cadenas",
            options=CHAINS_DISPONIBLES,
            default=st.session_state["alert_chains"],
            help="Filtra señales por blockchain. Selecciona las cadenas que te interesan.",
        )

        # --- Nivel minimo ---
        nivel_minimo = st.radio(
            "Nivel minimo de senal",
            options=list(NIVELES_SENAL.keys()),
            index=list(NIVELES_SENAL.keys()).index(
                st.session_state["alert_nivel_minimo"]
            ),
            horizontal=True,
            help=(
                "STRONG only: solo señales de alta confianza. "
                "MEDIUM+: incluye señales moderadas. "
                "ALL: todas las señales (mas ruido)."
            ),
        )

        st.markdown("---")
        st.markdown("**Alertas de sistema**")

        # --- Health Monitor ---
        health_monitor = st.toggle(
            "Health Monitor diario",
            value=st.session_state["alert_health_monitor"],
            help="Recibe un resumen diario del estado del sistema (APIs, datos, modelos).",
        )

        # --- Drift Alerts ---
        drift_alerts = st.toggle(
            "Alertas de drift semanal",
            value=st.session_state["alert_drift_alerts"],
            help=(
                "Recibe notificacion cuando se detecta drift en el modelo "
                "(cambios en la distribución de datos que pueden degradar las predicciones)."
            ),
        )

        # --- Boton guardar ---
        guardar_clicked = st.form_submit_button(
            "Guardar preferencias",
            type="primary",
            use_container_width=True,
        )

    if guardar_clicked:
        # Validar que al menos una cadena esta seleccionada
        if not chains_seleccionadas:
            st.error("Selecciona al menos una cadena.")
        else:
            # Actualizar session_state (cache local)
            st.session_state["alert_senales_diarias"] = senales_diarias
            st.session_state["alert_score_minimo"] = score_minimo
            st.session_state["alert_chains"] = chains_seleccionadas
            st.session_state["alert_nivel_minimo"] = nivel_minimo
            st.session_state["alert_health_monitor"] = health_monitor
            st.session_state["alert_drift_alerts"] = drift_alerts

            # Persistir en Supabase
            saved = _save_preferences_to_db(user_id, {
                "alert_senales_diarias": senales_diarias,
                "alert_score_minimo": score_minimo,
                "alert_chains": chains_seleccionadas,
                "alert_nivel_minimo": nivel_minimo,
            })
            if saved:
                st.success("Preferencias guardadas correctamente.")
            else:
                st.warning(
                    "Preferencias aplicadas en esta sesion, pero no se pudieron "
                    "guardar en la nube. Intentalo de nuevo."
                )

    st.divider()

    # ==============================================================
    # SECCION 3: Vista previa del mensaje
    # ==============================================================
    st.subheader("Vista previa")

    st.caption(
        "Asi lucira una alerta tipica con tu configuración actual."
    )

    # Construir preview con las preferencias actuales
    prefs = {
        "score_minimo": st.session_state["alert_score_minimo"],
        "chains": st.session_state["alert_chains"],
        "nivel_minimo": st.session_state["alert_nivel_minimo"],
    }
    preview_msg = _build_preview_message(prefs)

    # Mostrar en un contenedor estilizado (simula burbuja de Telegram)
    st.code(preview_msg, language=None)

    # Boton de mensaje de prueba
    col_test, col_spacer = st.columns([1, 2])
    with col_test:
        if telegram_connected:
            if st.button("Enviar mensaje de prueba", type="secondary", use_container_width=True):
                chat_id = profile.get("telegram_chat_id", "")
                result = _send_telegram_message(chat_id, _build_test_message())
                if result["ok"]:
                    st.success("Mensaje de prueba enviado. Revisa tu Telegram.")
                else:
                    st.error(f"Error al enviar: {result['description']}")
        else:
            st.button(
                "Enviar mensaje de prueba",
                type="secondary",
                disabled=True,
                help="Conecta tu Telegram primero para enviar mensajes de prueba.",
                use_container_width=True,
            )

    st.divider()

    # ==============================================================
    # SECCION 4: Historial de alertas
    # ==============================================================
    st.subheader("Historial de alertas")

    st.caption(
        "Últimas 10 alertas enviadas a tu Telegram. "
        "Este historial se poblara automáticamente cuando el sistema "
        "de alertas este activo."
    )

    # Placeholder — futuro: consultar tabla alert_log en Supabase
    # Por ahora mostramos un mensaje informativo
    _show_alert_history_placeholder()


def _show_alert_history_placeholder():
    """
    Muestra el historial de alertas del usuario.

    Consulta la tabla alert_history en Supabase. Si la tabla no existe
    todavia o no hay alertas, muestra un mensaje informativo.
    """
    try:
        storage = get_storage()
        df = storage.query(
            "SELECT sent_at, signal, symbol, chain, probability "
            "FROM alert_history "
            "WHERE user_id = ? "
            "ORDER BY sent_at DESC "
            "LIMIT 10",
            (st.session_state.get("user", {}).get("id", ""),),
        )
        if not df.empty:
            # Formatear probabilidad como porcentaje
            df["probability"] = df["probability"].apply(
                lambda x: f"{x:.1%}" if x else "—"
            )
            df.columns = ["Fecha", "Senal", "Token", "Chain", "Confianza"]
            st.dataframe(df, use_container_width=True, hide_index=True)
            return
    except Exception:
        pass  # Tabla alert_history no existe todavia

    st.info(
        "No hay alertas registradas todavia. Cuando el sistema de alertas "
        "diarias este activo, aqui veras un historial de los mensajes enviados "
        "a tu Telegram."
    )
