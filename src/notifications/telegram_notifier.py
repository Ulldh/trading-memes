"""
telegram_notifier.py — Envio de alertas de gems por Telegram.

Cuando el scorer detecta senales STRONG o MEDIUM nuevas,
envia alertas a los usuarios suscritos via Telegram Bot API.

Flujo:
1. Recibe DataFrame con senales nuevas (output de score_and_save).
2. Consulta usuarios con telegram_chat_id y alert_preferences habilitadas.
3. Filtra senales segun preferencias de cada usuario (nivel, cadenas, score).
4. Deduplica contra alert_history para no repetir alertas.
5. Envia mensajes formateados via Telegram Bot API.
6. Registra en alert_history las alertas enviadas exitosamente.

Rate limiting:
- Maximo MAX_ALERTS_PER_USER alertas por usuario por ejecucion.
- Timeout de 10 segundos por llamada a Telegram API.
- Si falla el envio a un usuario, continua con los demas.

Uso desde scripts/score_tokens.py:
    from src.notifications.telegram_notifier import notify_subscribers
    notify_subscribers(strong_medium_df)
"""

import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

from src.utils.logger import get_logger
from src.data.supabase_storage import get_storage

logger = get_logger(__name__)

# Maximo de alertas por usuario por ejecucion (evita spam)
MAX_ALERTS_PER_USER = 10

# Timeout para llamadas a la API de Telegram (segundos)
TELEGRAM_TIMEOUT = 10

# Emojis por nivel de senal (consistente con alerts_config.py)
_SIGNAL_EMOJI = {
    "STRONG": "\U0001f7e2",   # verde
    "MEDIUM": "\U0001f7e1",   # amarillo
    "WEAK": "\U0001f535",     # azul
}

# Mapeo de cadenas a su ID en DexScreener
_CHAIN_DEXSCREENER = {
    "solana": "solana",
    "ethereum": "ethereum",
    "base": "base",
    "bsc": "bsc",
    "arbitrum": "arbitrum",
}

# Mapeo de cadenas a su ID en GeckoTerminal
_CHAIN_GECKO = {
    "solana": "solana",
    "ethereum": "eth",
    "base": "base",
    "bsc": "bsc",
    "arbitrum": "arbitrum",
}

# Orden de senales para determinar nivel minimo
_SIGNAL_ORDER = {"STRONG": 3, "MEDIUM": 2, "WEAK": 1}


# ============================================================
# TELEGRAM BOT API
# ============================================================

def _get_bot_token() -> str:
    """Obtiene el token del bot de Telegram desde variables de entorno."""
    try:
        from config import TELEGRAM_BOT_TOKEN  # type: ignore[attr-defined]
        return TELEGRAM_BOT_TOKEN
    except (ImportError, AttributeError):
        return os.getenv("TELEGRAM_BOT_TOKEN", "")


def send_telegram_message(chat_id: str, text: str, bot_token: str = "") -> dict:
    """
    Envia un mensaje de Telegram via Bot API.

    Args:
        chat_id: ID del chat del usuario.
        text: Texto del mensaje (soporta MarkdownV2).
        bot_token: Token del bot. Si vacio, lo obtiene del env.

    Returns:
        Dict con 'ok' (bool) y 'description' (str).
    """
    token = bot_token or _get_bot_token()
    if not token:
        return {"ok": False, "description": "TELEGRAM_BOT_TOKEN no configurado."}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=TELEGRAM_TIMEOUT)
        data = resp.json()
        return {
            "ok": data.get("ok", False),
            "description": data.get("description", "Mensaje enviado."),
        }
    except requests.Timeout:
        return {"ok": False, "description": "Timeout conectando con Telegram API."}
    except requests.RequestException as e:
        return {"ok": False, "description": f"Error de conexion: {e}"}


# ============================================================
# FORMATO DEL MENSAJE DE ALERTA
# ============================================================

def build_alert_message(signal_data: dict) -> str:
    """
    Construye el mensaje de alerta formateado para Telegram.

    Args:
        signal_data: Dict con claves: token_id, symbol, chain,
                     probability, signal.

    Returns:
        String con formato Markdown para Telegram.
    """
    signal = signal_data.get("signal", "STRONG")
    emoji = _SIGNAL_EMOJI.get(signal, "\u26aa")
    symbol = signal_data.get("symbol", "???")
    chain = signal_data.get("chain", "unknown")
    probability = signal_data.get("probability", 0.0)
    token_id = signal_data.get("token_id", "")

    # Construir enlaces a exploradores
    chain_lower = chain.lower()
    dex_chain = _CHAIN_DEXSCREENER.get(chain_lower, chain_lower)
    gecko_chain = _CHAIN_GECKO.get(chain_lower, chain_lower)

    dex_link = f"https://dexscreener.com/{dex_chain}/{token_id}"
    gecko_link = f"https://www.geckoterminal.com/{gecko_chain}/pools/{token_id}"

    # Nombre de la cadena formateada
    chain_display = chain.capitalize()

    msg = (
        f"{emoji} *SENAL {signal}*\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"*Token:* {symbol}\n"
        f"*Chain:* {chain_display}\n"
        f"*Confianza:* {probability:.1%}\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f4ca [DexScreener]({dex_link})\n"
        f"\U0001f4c8 [GeckoTerminal]({gecko_link})\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\u26a0\ufe0f _DYOR — Esto no es consejo financiero_\n"
        f"_Gem Detector — {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC_"
    )

    return msg


# ============================================================
# CONSULTAS A SUPABASE
# ============================================================

def _get_subscribers(storage) -> list[dict]:
    """
    Obtiene la lista de usuarios suscritos a alertas de Telegram.

    Cruza profiles (telegram_chat_id) con alert_preferences (enabled, filtros).
    Usuarios sin entrada en alert_preferences reciben STRONG por defecto.

    Args:
        storage: Instancia de SupabaseStorage.

    Returns:
        Lista de dicts con: user_id, telegram_chat_id, min_signal,
        chains, min_probability, enabled.
    """
    try:
        df = storage.query("""
            SELECT
                p.id AS user_id,
                p.telegram_chat_id,
                COALESCE(ap.min_signal, 'STRONG') AS min_signal,
                COALESCE(ap.chains, '["solana","ethereum","base"]') AS chains,
                COALESCE(ap.min_probability, 0.6) AS min_probability,
                COALESCE(ap.enabled, true) AS enabled
            FROM profiles p
            LEFT JOIN alert_preferences ap ON p.id = ap.user_id
            WHERE p.telegram_chat_id IS NOT NULL
              AND p.telegram_chat_id != ''
        """)

        if df.empty:
            return []

        subscribers = []
        for _, row in df.iterrows():
            # Parsear chains (puede venir como string JSON o lista)
            chains = row.get("chains", '["solana","ethereum","base"]')
            if isinstance(chains, str):
                import json
                try:
                    chains = json.loads(chains)
                except (json.JSONDecodeError, TypeError):
                    chains = ["solana", "ethereum", "base"]

            subscribers.append({
                "user_id": str(row["user_id"]),
                "telegram_chat_id": str(row["telegram_chat_id"]),
                "min_signal": row.get("min_signal", "STRONG"),
                "chains": [c.lower() for c in chains] if chains else ["solana", "ethereum", "base"],
                "min_probability": float(row.get("min_probability", 0.6)),
                "enabled": bool(row.get("enabled", True)),
            })

        return subscribers

    except Exception as e:
        logger.error(f"Error consultando suscriptores de alertas: {e}")
        return []


def _get_already_sent(storage, user_id: str, token_ids: list[str]) -> set[str]:
    """
    Consulta alert_history para saber que alertas ya se enviaron a este usuario.

    Args:
        storage: Instancia de SupabaseStorage.
        user_id: UUID del usuario.
        token_ids: Lista de token_ids a verificar.

    Returns:
        Set de token_ids que ya fueron notificados a este usuario.
    """
    if not token_ids:
        return set()

    try:
        # Construir placeholders para la query IN
        placeholders = ", ".join(["?"] * len(token_ids))
        params = (user_id, *token_ids)

        df = storage.query(
            f"SELECT DISTINCT token_id FROM alert_history "
            f"WHERE user_id = ? AND token_id IN ({placeholders})",
            params,
        )
        if df.empty:
            return set()
        return set(df["token_id"].tolist())

    except Exception as e:
        # Si la tabla no existe todavia, retornar vacio (primera ejecucion)
        logger.warning(f"Error consultando alert_history (tabla puede no existir): {e}")
        return set()


def _record_sent_alert(storage, user_id: str, signal_data: dict) -> bool:
    """
    Registra una alerta enviada en alert_history para deduplicacion.

    Args:
        storage: Instancia de SupabaseStorage.
        user_id: UUID del usuario.
        signal_data: Dict con datos de la senal.

    Returns:
        True si se registro correctamente.
    """
    try:
        row = {
            "user_id": user_id,
            "token_id": signal_data["token_id"],
            "signal": signal_data["signal"],
            "chain": signal_data.get("chain", ""),
            "symbol": signal_data.get("symbol", ""),
            "probability": float(signal_data.get("probability", 0)),
        }

        storage._client.table("alert_history").upsert(
            row, on_conflict="user_id,token_id,signal"
        ).execute()
        return True

    except Exception as e:
        logger.warning(f"Error registrando alerta en alert_history: {e}")
        return False


# ============================================================
# FILTRADO DE SENALES POR PREFERENCIAS DEL USUARIO
# ============================================================

def _filter_signals_for_user(
    signals_df: pd.DataFrame, subscriber: dict
) -> pd.DataFrame:
    """
    Filtra senales segun las preferencias del usuario.

    Aplica filtros de:
    - Nivel minimo de senal (STRONG, MEDIUM, WEAK)
    - Cadenas seleccionadas
    - Score minimo (min_probability)

    Args:
        signals_df: DataFrame con columnas: token_id, symbol, chain,
                    probability, signal.
        subscriber: Dict con preferencias del usuario.

    Returns:
        DataFrame filtrado con solo las senales que el usuario quiere recibir.
    """
    if signals_df.empty:
        return signals_df.copy()

    df = signals_df.copy()

    # Filtro 1: Nivel minimo de senal
    min_signal = subscriber.get("min_signal", "STRONG")
    min_order = _SIGNAL_ORDER.get(min_signal, 3)
    df = df[df["signal"].map(lambda s: _SIGNAL_ORDER.get(s, 0) >= min_order)]

    # Filtro 2: Cadenas seleccionadas
    user_chains = subscriber.get("chains", ["solana", "ethereum", "base"])
    df = df[df["chain"].str.lower().isin(user_chains)]

    # Filtro 3: Score minimo
    min_prob = subscriber.get("min_probability", 0.6)
    df = df[df["probability"] >= min_prob]

    return df


# ============================================================
# FUNCION PRINCIPAL: NOTIFICAR SUSCRIPTORES
# ============================================================

def notify_subscribers(new_signals_df: pd.DataFrame) -> dict:
    """
    Envia alertas de Telegram a todos los usuarios suscritos.

    Flujo completo:
    1. Verifica que el bot token esta configurado.
    2. Obtiene suscriptores con Telegram conectado y alertas habilitadas.
    3. Para cada suscriptor, filtra senales segun sus preferencias.
    4. Deduplica contra alert_history.
    5. Envia mensajes (max MAX_ALERTS_PER_USER por usuario).
    6. Registra alertas enviadas en alert_history.

    Args:
        new_signals_df: DataFrame con las senales nuevas. Debe tener columnas:
            token_id, symbol, chain, probability, signal.

    Returns:
        Dict con estadisticas: total_sent, total_failed, total_skipped,
        users_notified.
    """
    stats = {
        "total_sent": 0,
        "total_failed": 0,
        "total_skipped": 0,
        "total_deduplicated": 0,
        "users_notified": 0,
    }

    # Validar que hay senales para enviar
    if new_signals_df is None or new_signals_df.empty:
        logger.info("notify_subscribers: no hay senales nuevas para notificar")
        return stats

    # Verificar bot token
    bot_token = _get_bot_token()
    if not bot_token:
        logger.warning(
            "notify_subscribers: TELEGRAM_BOT_TOKEN no configurado. "
            "Saltando alertas de Telegram."
        )
        return stats

    # Obtener storage
    try:
        storage = get_storage()
    except Exception as e:
        logger.error(f"notify_subscribers: error obteniendo storage: {e}")
        return stats

    # Obtener suscriptores
    subscribers = _get_subscribers(storage)
    if not subscribers:
        logger.info("notify_subscribers: no hay usuarios con Telegram conectado")
        return stats

    # Filtrar solo suscriptores con alertas habilitadas
    active_subscribers = [s for s in subscribers if s.get("enabled", True)]
    logger.info(
        f"notify_subscribers: {len(active_subscribers)} suscriptores activos "
        f"de {len(subscribers)} con Telegram conectado"
    )

    if not active_subscribers:
        logger.info("notify_subscribers: ningun suscriptor tiene alertas habilitadas")
        return stats

    # Procesar cada suscriptor
    for subscriber in active_subscribers:
        user_id = subscriber["user_id"]
        chat_id = subscriber["telegram_chat_id"]

        # Filtrar senales segun preferencias del usuario
        user_signals = _filter_signals_for_user(new_signals_df, subscriber)

        if user_signals.empty:
            logger.debug(
                f"notify_subscribers: usuario {user_id[:8]}... "
                f"sin senales que cumplan sus filtros"
            )
            continue

        # Deduplicar contra historial de alertas enviadas
        token_ids = user_signals["token_id"].tolist()
        already_sent = _get_already_sent(storage, user_id, token_ids)

        if already_sent:
            before_count = len(user_signals)
            user_signals = user_signals[
                ~user_signals["token_id"].isin(already_sent)
            ]
            deduped = before_count - len(user_signals)
            stats["total_deduplicated"] += deduped
            if deduped > 0:
                logger.debug(
                    f"notify_subscribers: {deduped} alertas deduplicadas "
                    f"para usuario {user_id[:8]}..."
                )

        if user_signals.empty:
            continue

        # Limitar a MAX_ALERTS_PER_USER por ejecucion
        # Ordenar por probabilidad descendente para enviar las mejores primero
        user_signals = user_signals.sort_values(
            "probability", ascending=False
        ).head(MAX_ALERTS_PER_USER)

        # Enviar alertas
        user_sent = 0
        for _, signal_row in user_signals.iterrows():
            signal_data = signal_row.to_dict()

            # Construir y enviar mensaje
            message = build_alert_message(signal_data)
            result = send_telegram_message(chat_id, message, bot_token)

            if result["ok"]:
                user_sent += 1
                stats["total_sent"] += 1

                # Registrar en alert_history
                _record_sent_alert(storage, user_id, signal_data)
            else:
                stats["total_failed"] += 1
                logger.warning(
                    f"notify_subscribers: fallo envio a {user_id[:8]}...: "
                    f"{result['description']}"
                )
                # Si falla un envio a este usuario, no seguir intentando
                # (probablemente el chat_id es invalido o bot bloqueado)
                break

        if user_sent > 0:
            stats["users_notified"] += 1
            logger.info(
                f"notify_subscribers: {user_sent} alertas enviadas a "
                f"usuario {user_id[:8]}..."
            )

    # Calcular skipped
    stats["total_skipped"] = (
        len(new_signals_df) * len(active_subscribers)
        - stats["total_sent"]
        - stats["total_failed"]
        - stats["total_deduplicated"]
    )

    # Resumen
    logger.info(
        f"notify_subscribers: RESUMEN — "
        f"{stats['total_sent']} enviadas, "
        f"{stats['total_failed']} fallidas, "
        f"{stats['total_deduplicated']} deduplicadas, "
        f"{stats['users_notified']} usuarios notificados"
    )

    return stats
