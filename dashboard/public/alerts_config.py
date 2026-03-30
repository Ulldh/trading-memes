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

import os
from datetime import datetime

import streamlit as st
import requests

from src.data.supabase_storage import get_storage as _get_storage


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
        st.error(f"Error al guardar chat ID: {e}")
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
# PREFERENCIAS (session_state)
# ============================================================

def _init_preferences():
    """Inicializa las preferencias de alerta en session_state si no existen."""
    defaults = {
        "alert_senales_diarias": True,
        "alert_score_minimo": 0.65,
        "alert_chains": CHAINS_DISPONIBLES.copy(),
        "alert_nivel_minimo": "MEDIUM+",
        "alert_health_monitor": True,
        "alert_drift_alerts": False,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


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

    # Inicializar preferencias
    _init_preferences()

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
            # Guardar en session_state
            st.session_state["alert_senales_diarias"] = senales_diarias
            st.session_state["alert_score_minimo"] = score_minimo
            st.session_state["alert_chains"] = chains_seleccionadas
            st.session_state["alert_nivel_minimo"] = nivel_minimo
            st.session_state["alert_health_monitor"] = health_monitor
            st.session_state["alert_drift_alerts"] = drift_alerts

            st.success("Preferencias guardadas correctamente.")

            # TODO: Persistir en Supabase cuando se cree la tabla alert_preferences
            # o columna JSONB en profiles

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
    Muestra placeholder del historial de alertas.

    Cuando se implemente la tabla alert_log en Supabase,
    esta función se reemplazara por una consulta real.
    """
    # Intentar cargar historial real de Supabase (futuro)
    try:
        storage = get_storage()
        df = storage.query(
            "SELECT created_at, type, message, status "
            "FROM alert_log "
            "WHERE user_id = ? "
            "ORDER BY created_at DESC "
            "LIMIT 10",
            (st.session_state.get("user", {}).get("id", ""),),
        )
        if not df.empty:
            # Truncar mensajes largos para la tabla
            df["message"] = df["message"].str[:80] + "..."
            df.columns = ["Fecha", "Tipo", "Mensaje", "Estado"]
            st.dataframe(df, use_container_width=True, hide_index=True)
            return
    except Exception:
        pass  # Tabla no existe todavia — mostrar placeholder

    # Placeholder con datos de ejemplo para que el usuario vea el formato
    st.info(
        "No hay alertas registradas todavia. Cuando el sistema de alertas "
        "diarias este activo, aqui veras un historial de los mensajes enviados."
    )

    # Tabla de ejemplo (datos ficticios para mostrar formato)
    import pandas as pd

    ejemplo = pd.DataFrame({
        "Fecha": ["2026-03-27 08:00", "2026-03-26 08:00", "2026-03-25 08:00"],
        "Tipo": ["Senal diaria", "Health Monitor", "Senal diaria"],
        "Mensaje": [
            "STRONG: TOKEN_A/SOL — Score 0.89...",
            "Sistema OK: 11 APIs activas, 4028 tok...",
            "MEDIUM: TOKEN_B/ETH — Score 0.72...",
        ],
        "Estado": ["Enviado", "Enviado", "Enviado"],
    })

    st.dataframe(
        ejemplo,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Estado": st.column_config.TextColumn(
                width="small",
            ),
            "Tipo": st.column_config.TextColumn(
                width="medium",
            ),
        },
    )
    st.caption("_Datos de ejemplo — se reemplazaran con alertas reales._")
