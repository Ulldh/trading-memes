"""
test_telegram_notifier.py — Tests para el modulo de alertas de Telegram.

Testea:
- Formato de mensajes de alerta
- Filtrado de senales por preferencias de usuario
- Rate limiting (max alertas por usuario)
- Deduplicacion contra historial
- Manejo de errores (Telegram API caido, bot token ausente)
- Integracion con score_tokens.py (no rompe el pipeline)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Asegurar que el proyecto esta en el path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.notifications.telegram_notifier import (
    MAX_ALERTS_PER_USER,
    build_alert_message,
    send_telegram_message,
    notify_subscribers,
    _filter_signals_for_user,
    _get_subscribers,
    _get_already_sent,
    _record_sent_alert,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def sample_signal():
    """Una senal STRONG de ejemplo."""
    return {
        "token_id": "0xabc123def456",
        "symbol": "PEPE",
        "chain": "solana",
        "probability": 0.892,
        "signal": "STRONG",
    }


@pytest.fixture
def sample_signals_df():
    """DataFrame con varias senales de ejemplo."""
    return pd.DataFrame([
        {
            "token_id": "token_strong_1",
            "symbol": "PEPE",
            "chain": "solana",
            "probability": 0.85,
            "signal": "STRONG",
        },
        {
            "token_id": "token_strong_2",
            "symbol": "DOGE",
            "chain": "ethereum",
            "probability": 0.72,
            "signal": "STRONG",
        },
        {
            "token_id": "token_medium_1",
            "symbol": "SHIB",
            "chain": "base",
            "probability": 0.55,
            "signal": "MEDIUM",
        },
        {
            "token_id": "token_medium_2",
            "symbol": "WIF",
            "chain": "solana",
            "probability": 0.45,
            "signal": "MEDIUM",
        },
    ])


@pytest.fixture
def subscriber_strong_only():
    """Suscriptor que solo quiere senales STRONG."""
    return {
        "user_id": "user-uuid-1",
        "telegram_chat_id": "123456789",
        "min_signal": "STRONG",
        "chains": ["solana", "ethereum", "base"],
        "min_probability": 0.6,
        "enabled": True,
    }


@pytest.fixture
def subscriber_medium_plus():
    """Suscriptor que quiere STRONG + MEDIUM."""
    return {
        "user_id": "user-uuid-2",
        "telegram_chat_id": "987654321",
        "min_signal": "MEDIUM",
        "chains": ["solana", "ethereum", "base"],
        "min_probability": 0.4,
        "enabled": True,
    }


@pytest.fixture
def subscriber_solana_only():
    """Suscriptor que solo quiere senales de Solana."""
    return {
        "user_id": "user-uuid-3",
        "telegram_chat_id": "111222333",
        "min_signal": "MEDIUM",
        "chains": ["solana"],
        "min_probability": 0.4,
        "enabled": True,
    }


# ============================================================
# TESTS: FORMATO DE MENSAJE
# ============================================================

class TestBuildAlertMessage:
    """Tests para la construccion del mensaje de alerta."""

    def test_strong_signal_format(self, sample_signal):
        """El mensaje de una senal STRONG incluye todos los campos."""
        msg = build_alert_message(sample_signal)

        assert "SENAL STRONG" in msg
        assert "PEPE" in msg
        assert "Solana" in msg
        assert "89.2%" in msg
        assert "DexScreener" in msg
        assert "GeckoTerminal" in msg
        assert "DYOR" in msg
        assert "dexscreener.com/solana/0xabc123def456" in msg

    def test_medium_signal_format(self):
        """El mensaje de una senal MEDIUM usa el emoji amarillo."""
        signal = {
            "token_id": "0xdef789",
            "symbol": "WIF",
            "chain": "ethereum",
            "probability": 0.55,
            "signal": "MEDIUM",
        }
        msg = build_alert_message(signal)

        assert "SENAL MEDIUM" in msg
        assert "WIF" in msg
        assert "Ethereum" in msg
        assert "55.0%" in msg

    def test_dexscreener_link_correct_chain(self):
        """El enlace de DexScreener usa el ID correcto de la cadena."""
        for chain, expected_id in [
            ("solana", "solana"),
            ("ethereum", "ethereum"),
            ("base", "base"),
            ("bsc", "bsc"),
        ]:
            signal = {
                "token_id": "0xtest",
                "symbol": "TEST",
                "chain": chain,
                "probability": 0.7,
                "signal": "STRONG",
            }
            msg = build_alert_message(signal)
            assert f"dexscreener.com/{expected_id}/0xtest" in msg

    def test_missing_fields_use_defaults(self):
        """Campos faltantes no rompen el formato."""
        msg = build_alert_message({})
        assert "SENAL STRONG" in msg  # default
        assert "???" in msg  # symbol default
        assert "0.0%" in msg  # probability default


# ============================================================
# TESTS: ENVIO DE TELEGRAM
# ============================================================

class TestSendTelegramMessage:
    """Tests para el envio de mensajes via Telegram Bot API."""

    @patch("src.notifications.telegram_notifier.requests.post")
    def test_successful_send(self, mock_post):
        """Envio exitoso retorna ok=True."""
        mock_post.return_value.json.return_value = {
            "ok": True,
            "description": "Message sent",
        }

        result = send_telegram_message("12345", "Hola", bot_token="fake-token")

        assert result["ok"] is True
        mock_post.assert_called_once()

    @patch("src.notifications.telegram_notifier.requests.post")
    def test_failed_send(self, mock_post):
        """Envio fallido retorna ok=False con descripcion."""
        mock_post.return_value.json.return_value = {
            "ok": False,
            "description": "Chat not found",
        }

        result = send_telegram_message("invalid", "Hola", bot_token="fake-token")

        assert result["ok"] is False
        assert "Chat not found" in result["description"]

    def test_no_bot_token(self):
        """Sin bot token retorna error inmediato sin hacer request."""
        with patch(
            "src.notifications.telegram_notifier._get_bot_token", return_value=""
        ):
            result = send_telegram_message("12345", "Hola")
            assert result["ok"] is False
            assert "TELEGRAM_BOT_TOKEN" in result["description"]

    @patch("src.notifications.telegram_notifier.requests.post")
    def test_timeout_handling(self, mock_post):
        """Un timeout en la API de Telegram se maneja sin crashear."""
        import requests
        mock_post.side_effect = requests.Timeout("Connection timed out")

        result = send_telegram_message("12345", "Hola", bot_token="fake-token")

        assert result["ok"] is False
        assert "Timeout" in result["description"]

    @patch("src.notifications.telegram_notifier.requests.post")
    def test_connection_error_handling(self, mock_post):
        """Un error de conexion se maneja sin crashear."""
        import requests
        mock_post.side_effect = requests.ConnectionError("DNS resolution failed")

        result = send_telegram_message("12345", "Hola", bot_token="fake-token")

        assert result["ok"] is False
        assert "Error de conexion" in result["description"]

    @patch("src.notifications.telegram_notifier.requests.post")
    def test_disable_web_preview(self, mock_post):
        """Los mensajes deshabilitan la preview de enlaces."""
        mock_post.return_value.json.return_value = {"ok": True}

        send_telegram_message("12345", "Hola", bot_token="fake-token")

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["disable_web_page_preview"] is True


# ============================================================
# TESTS: FILTRADO DE SENALES
# ============================================================

class TestFilterSignals:
    """Tests para el filtrado de senales segun preferencias."""

    def test_strong_only_filters_medium(
        self, sample_signals_df, subscriber_strong_only
    ):
        """STRONG only filtra todas las senales MEDIUM."""
        filtered = _filter_signals_for_user(
            sample_signals_df, subscriber_strong_only
        )
        assert len(filtered) == 2
        assert all(filtered["signal"] == "STRONG")

    def test_medium_plus_includes_both(
        self, sample_signals_df, subscriber_medium_plus
    ):
        """MEDIUM+ incluye senales STRONG y MEDIUM."""
        filtered = _filter_signals_for_user(
            sample_signals_df, subscriber_medium_plus
        )
        assert len(filtered) == 4
        assert set(filtered["signal"].unique()) == {"STRONG", "MEDIUM"}

    def test_chain_filter(self, sample_signals_df, subscriber_solana_only):
        """Filtro por cadena solo incluye senales de Solana."""
        filtered = _filter_signals_for_user(
            sample_signals_df, subscriber_solana_only
        )
        assert all(filtered["chain"].str.lower() == "solana")
        assert len(filtered) == 2  # PEPE (STRONG) + WIF (MEDIUM)

    def test_probability_filter(self, sample_signals_df):
        """Filtro por score minimo excluye senales con baja probabilidad."""
        subscriber = {
            "user_id": "test",
            "telegram_chat_id": "12345",
            "min_signal": "MEDIUM",
            "chains": ["solana", "ethereum", "base"],
            "min_probability": 0.70,
            "enabled": True,
        }
        filtered = _filter_signals_for_user(sample_signals_df, subscriber)
        assert len(filtered) == 2  # Solo PEPE (0.85) y DOGE (0.72)
        assert all(filtered["probability"] >= 0.70)

    def test_all_filters_combined(self, sample_signals_df):
        """Multiples filtros se aplican conjuntamente."""
        subscriber = {
            "user_id": "test",
            "telegram_chat_id": "12345",
            "min_signal": "STRONG",
            "chains": ["solana"],
            "min_probability": 0.80,
            "enabled": True,
        }
        filtered = _filter_signals_for_user(sample_signals_df, subscriber)
        assert len(filtered) == 1
        assert filtered.iloc[0]["symbol"] == "PEPE"

    def test_empty_df_returns_empty(self, subscriber_strong_only):
        """Un DataFrame vacio retorna un DataFrame vacio."""
        filtered = _filter_signals_for_user(
            pd.DataFrame(columns=["token_id", "symbol", "chain", "probability", "signal"]),
            subscriber_strong_only,
        )
        assert filtered.empty


# ============================================================
# TESTS: DEDUPLICACION
# ============================================================

class TestDeduplication:
    """Tests para la deduplicacion contra alert_history."""

    def test_get_already_sent_with_history(self):
        """Retorna set de token_ids ya enviados."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = pd.DataFrame({
            "token_id": ["token_1", "token_2"]
        })

        result = _get_already_sent(
            mock_storage, "user-1", ["token_1", "token_2", "token_3"]
        )

        assert result == {"token_1", "token_2"}

    def test_get_already_sent_empty_history(self):
        """Sin historial retorna set vacio."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = pd.DataFrame()

        result = _get_already_sent(
            mock_storage, "user-1", ["token_1"]
        )

        assert result == set()

    def test_get_already_sent_empty_token_ids(self):
        """Lista vacia de token_ids retorna set vacio sin consultar."""
        mock_storage = MagicMock()

        result = _get_already_sent(mock_storage, "user-1", [])

        assert result == set()
        mock_storage.query.assert_not_called()

    def test_get_already_sent_handles_db_error(self):
        """Error de BD retorna set vacio (tabla puede no existir)."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = Exception("relation does not exist")

        result = _get_already_sent(
            mock_storage, "user-1", ["token_1"]
        )

        assert result == set()

    def test_record_sent_alert_success(self, sample_signal):
        """Registrar alerta exitosamente retorna True."""
        mock_storage = MagicMock()
        mock_table = MagicMock()
        mock_storage._client.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = None

        result = _record_sent_alert(mock_storage, "user-1", sample_signal)

        assert result is True
        mock_storage._client.table.assert_called_with("alert_history")

    def test_record_sent_alert_handles_error(self, sample_signal):
        """Error al registrar retorna False sin crashear."""
        mock_storage = MagicMock()
        mock_storage._client.table.side_effect = Exception("DB error")

        result = _record_sent_alert(mock_storage, "user-1", sample_signal)

        assert result is False


# ============================================================
# TESTS: RATE LIMITING
# ============================================================

class TestRateLimiting:
    """Tests para el rate limiting de alertas."""

    def test_max_alerts_per_user_constant(self):
        """La constante MAX_ALERTS_PER_USER existe y tiene un valor razonable."""
        assert MAX_ALERTS_PER_USER == 10

    @patch("src.notifications.telegram_notifier.send_telegram_message")
    @patch("src.notifications.telegram_notifier._record_sent_alert")
    @patch("src.notifications.telegram_notifier._get_already_sent")
    @patch("src.notifications.telegram_notifier._get_subscribers")
    @patch("src.notifications.telegram_notifier.get_storage")
    @patch("src.notifications.telegram_notifier._get_bot_token")
    def test_max_alerts_respected(
        self, mock_token, mock_storage_fn, mock_subscribers,
        mock_already_sent, mock_record, mock_send,
    ):
        """No se envian mas de MAX_ALERTS_PER_USER alertas a un usuario."""
        mock_token.return_value = "fake-token"
        mock_storage_fn.return_value = MagicMock()
        mock_subscribers.return_value = [{
            "user_id": "user-1",
            "telegram_chat_id": "12345",
            "min_signal": "MEDIUM",
            "chains": ["solana"],
            "min_probability": 0.0,
            "enabled": True,
        }]
        mock_already_sent.return_value = set()
        mock_record.return_value = True
        mock_send.return_value = {"ok": True, "description": "Sent"}

        # Crear 20 senales (mas que el limite)
        signals = pd.DataFrame([
            {
                "token_id": f"token_{i}",
                "symbol": f"TOKEN{i}",
                "chain": "solana",
                "probability": 0.9 - i * 0.01,
                "signal": "STRONG",
            }
            for i in range(20)
        ])

        stats = notify_subscribers(signals)

        # Solo debe enviar MAX_ALERTS_PER_USER
        assert mock_send.call_count == MAX_ALERTS_PER_USER
        assert stats["total_sent"] == MAX_ALERTS_PER_USER


# ============================================================
# TESTS: NOTIFY_SUBSCRIBERS INTEGRACION
# ============================================================

class TestNotifySubscribers:
    """Tests de integracion para notify_subscribers."""

    def test_empty_df_returns_zero_stats(self):
        """DataFrame vacio retorna stats en cero."""
        stats = notify_subscribers(pd.DataFrame())

        assert stats["total_sent"] == 0
        assert stats["users_notified"] == 0

    def test_none_df_returns_zero_stats(self):
        """None retorna stats en cero."""
        stats = notify_subscribers(None)

        assert stats["total_sent"] == 0

    @patch("src.notifications.telegram_notifier._get_bot_token")
    def test_no_bot_token_skips_gracefully(self, mock_token, sample_signals_df):
        """Sin bot token, no crashea y retorna stats en cero."""
        mock_token.return_value = ""

        stats = notify_subscribers(sample_signals_df)

        assert stats["total_sent"] == 0

    @patch("src.notifications.telegram_notifier.send_telegram_message")
    @patch("src.notifications.telegram_notifier._record_sent_alert")
    @patch("src.notifications.telegram_notifier._get_already_sent")
    @patch("src.notifications.telegram_notifier._get_subscribers")
    @patch("src.notifications.telegram_notifier.get_storage")
    @patch("src.notifications.telegram_notifier._get_bot_token")
    def test_successful_notification_flow(
        self, mock_token, mock_storage_fn, mock_subscribers,
        mock_already_sent, mock_record, mock_send, sample_signals_df,
    ):
        """Flujo completo exitoso: envia alertas y registra en historial."""
        mock_token.return_value = "fake-token"
        mock_storage_fn.return_value = MagicMock()
        mock_subscribers.return_value = [{
            "user_id": "user-1",
            "telegram_chat_id": "12345",
            "min_signal": "MEDIUM",
            "chains": ["solana", "ethereum", "base"],
            "min_probability": 0.4,
            "enabled": True,
        }]
        mock_already_sent.return_value = set()
        mock_record.return_value = True
        mock_send.return_value = {"ok": True, "description": "Sent"}

        stats = notify_subscribers(sample_signals_df)

        assert stats["total_sent"] == 4  # Todas las senales pasan los filtros
        assert stats["users_notified"] == 1
        assert mock_send.call_count == 4
        assert mock_record.call_count == 4

    @patch("src.notifications.telegram_notifier.send_telegram_message")
    @patch("src.notifications.telegram_notifier._record_sent_alert")
    @patch("src.notifications.telegram_notifier._get_already_sent")
    @patch("src.notifications.telegram_notifier._get_subscribers")
    @patch("src.notifications.telegram_notifier.get_storage")
    @patch("src.notifications.telegram_notifier._get_bot_token")
    def test_deduplication_skips_already_sent(
        self, mock_token, mock_storage_fn, mock_subscribers,
        mock_already_sent, mock_record, mock_send, sample_signals_df,
    ):
        """Senales ya enviadas se deduplican y no se envian de nuevo."""
        mock_token.return_value = "fake-token"
        mock_storage_fn.return_value = MagicMock()
        mock_subscribers.return_value = [{
            "user_id": "user-1",
            "telegram_chat_id": "12345",
            "min_signal": "MEDIUM",
            "chains": ["solana", "ethereum", "base"],
            "min_probability": 0.4,
            "enabled": True,
        }]
        # 2 de 4 ya fueron enviadas
        mock_already_sent.return_value = {"token_strong_1", "token_medium_1"}
        mock_record.return_value = True
        mock_send.return_value = {"ok": True, "description": "Sent"}

        stats = notify_subscribers(sample_signals_df)

        assert stats["total_sent"] == 2
        assert stats["total_deduplicated"] == 2

    @patch("src.notifications.telegram_notifier.send_telegram_message")
    @patch("src.notifications.telegram_notifier._record_sent_alert")
    @patch("src.notifications.telegram_notifier._get_already_sent")
    @patch("src.notifications.telegram_notifier._get_subscribers")
    @patch("src.notifications.telegram_notifier.get_storage")
    @patch("src.notifications.telegram_notifier._get_bot_token")
    def test_disabled_subscriber_skipped(
        self, mock_token, mock_storage_fn, mock_subscribers,
        mock_already_sent, mock_record, mock_send, sample_signals_df,
    ):
        """Suscriptor con enabled=False no recibe alertas."""
        mock_token.return_value = "fake-token"
        mock_storage_fn.return_value = MagicMock()
        mock_subscribers.return_value = [{
            "user_id": "user-1",
            "telegram_chat_id": "12345",
            "min_signal": "MEDIUM",
            "chains": ["solana", "ethereum", "base"],
            "min_probability": 0.4,
            "enabled": False,
        }]

        stats = notify_subscribers(sample_signals_df)

        assert stats["total_sent"] == 0
        mock_send.assert_not_called()

    @patch("src.notifications.telegram_notifier.send_telegram_message")
    @patch("src.notifications.telegram_notifier._record_sent_alert")
    @patch("src.notifications.telegram_notifier._get_already_sent")
    @patch("src.notifications.telegram_notifier._get_subscribers")
    @patch("src.notifications.telegram_notifier.get_storage")
    @patch("src.notifications.telegram_notifier._get_bot_token")
    def test_telegram_failure_stops_user_continues_others(
        self, mock_token, mock_storage_fn, mock_subscribers,
        mock_already_sent, mock_record, mock_send, sample_signals_df,
    ):
        """Si Telegram falla para un usuario, para con ese pero sigue con otros."""
        mock_token.return_value = "fake-token"
        mock_storage_fn.return_value = MagicMock()
        mock_subscribers.return_value = [
            {
                "user_id": "user-fail",
                "telegram_chat_id": "bad-chat",
                "min_signal": "MEDIUM",
                "chains": ["solana", "ethereum", "base"],
                "min_probability": 0.4,
                "enabled": True,
            },
            {
                "user_id": "user-ok",
                "telegram_chat_id": "good-chat",
                "min_signal": "MEDIUM",
                "chains": ["solana", "ethereum", "base"],
                "min_probability": 0.4,
                "enabled": True,
            },
        ]
        mock_already_sent.return_value = set()
        mock_record.return_value = True

        # Primer usuario falla, segundo OK
        def side_effect(chat_id, text, bot_token=""):
            if chat_id == "bad-chat":
                return {"ok": False, "description": "Chat not found"}
            return {"ok": True, "description": "Sent"}

        mock_send.side_effect = side_effect

        stats = notify_subscribers(sample_signals_df)

        # user-fail: 1 intento fallido, para
        # user-ok: 4 envios exitosos
        assert stats["total_sent"] == 4
        assert stats["total_failed"] == 1
        assert stats["users_notified"] == 1

    @patch("src.notifications.telegram_notifier._get_subscribers")
    @patch("src.notifications.telegram_notifier.get_storage")
    @patch("src.notifications.telegram_notifier._get_bot_token")
    def test_no_subscribers_returns_gracefully(
        self, mock_token, mock_storage_fn, mock_subscribers, sample_signals_df,
    ):
        """Sin suscriptores, retorna stats en cero sin error."""
        mock_token.return_value = "fake-token"
        mock_storage_fn.return_value = MagicMock()
        mock_subscribers.return_value = []

        stats = notify_subscribers(sample_signals_df)

        assert stats["total_sent"] == 0
        assert stats["users_notified"] == 0


# ============================================================
# TESTS: GET_SUBSCRIBERS
# ============================================================

class TestGetSubscribers:
    """Tests para la obtencion de suscriptores."""

    def test_parses_subscribers_correctly(self):
        """Parsea correctamente los datos de Supabase."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = pd.DataFrame([{
            "user_id": "uuid-1",
            "telegram_chat_id": "12345",
            "min_signal": "MEDIUM",
            "chains": '["solana", "ethereum"]',
            "min_probability": 0.5,
            "enabled": True,
        }])

        result = _get_subscribers(mock_storage)

        assert len(result) == 1
        assert result[0]["user_id"] == "uuid-1"
        assert result[0]["telegram_chat_id"] == "12345"
        assert result[0]["min_signal"] == "MEDIUM"
        assert result[0]["chains"] == ["solana", "ethereum"]
        assert result[0]["min_probability"] == 0.5

    def test_handles_db_error_gracefully(self):
        """Error de BD retorna lista vacia."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = Exception("DB connection failed")

        result = _get_subscribers(mock_storage)

        assert result == []

    def test_empty_query_returns_empty(self):
        """Sin suscriptores retorna lista vacia."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = pd.DataFrame()

        result = _get_subscribers(mock_storage)

        assert result == []

    def test_default_preferences_when_no_alert_prefs(self):
        """Usuarios sin alert_preferences usan defaults (STRONG, todas las cadenas)."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = pd.DataFrame([{
            "user_id": "uuid-1",
            "telegram_chat_id": "12345",
            "min_signal": "STRONG",
            "chains": '["solana","ethereum","base"]',
            "min_probability": 0.6,
            "enabled": True,
        }])

        result = _get_subscribers(mock_storage)

        assert result[0]["min_signal"] == "STRONG"
        assert "solana" in result[0]["chains"]
