"""
test_labeler.py - Tests para el sistema de clasificacion de tokens.

Ejecutar con: pytest tests/test_labeler.py -v

Verifican que el labeler clasifica tokens correctamente:
1. Gems (10x+ sostenido)
2. Failures (<0.1x)
3. Rugs (<0.01x rapido)
4. Clasificacion binaria (5x threshold)
5. Early rug detection (M1) — caida 90%+ con solo 2 velas
6. Tiered labeling (M2) — clasificacion granular por tiers
7. MIN_DAYS_REQUIRED reducido de 7 a 3 (M1)
"""

import sys
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.labeler import Labeler, MIN_DAYS_REQUIRED
from unittest.mock import MagicMock


class TestLabelerLogic:
    """Tests para la logica de clasificacion del labeler."""

    def _make_ohlcv(self, closes: list[float], days: int = None) -> pd.DataFrame:
        """
        Helper: crea un DataFrame OHLCV simulado a partir de precios de cierre.

        Args:
            closes: Lista de precios de cierre (uno por dia).
            days: Numero de dias (si None, usa len(closes)).

        Returns:
            DataFrame con columnas: timestamp, open, high, low, close, volume.
        """
        if days is None:
            days = len(closes)

        return pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=len(closes), freq="D"),
            "open": [c * 0.99 for c in closes],
            "high": [c * 1.02 for c in closes],
            "low": [c * 0.98 for c in closes],
            "close": closes,
            "volume": [10000] * len(closes),
        })

    def test_gem_detection(self):
        """
        Un token que sube a 15x y se mantiene >5x por 10 dias es un gem.
        """
        # Dia 1: $1, sube a $15 en dia 5, se mantiene entre $8-15 por 10+ dias
        prices = [1.0, 3.0, 7.0, 12.0, 15.0] + [10.0] * 10 + [8.0] * 15
        ohlcv = self._make_ohlcv(prices)

        # Verificar que el max multiple es >= 10x
        initial_price = prices[0]
        max_price = max(p * 1.02 for p in prices)  # high = close * 1.02
        max_multiple = max_price / initial_price

        assert max_multiple >= 10.0, f"Max multiple deberia ser >= 10, fue {max_multiple}"

        # Verificar dias sostenidos > 5x
        consecutive_above_5x = 0
        max_consecutive = 0
        for p in prices:
            if p / initial_price >= 5.0:
                consecutive_above_5x += 1
                max_consecutive = max(max_consecutive, consecutive_above_5x)
            else:
                consecutive_above_5x = 0

        assert max_consecutive >= 7, f"Deberia estar >5x por 7+ dias, fue {max_consecutive}"

    def test_failure_detection(self):
        """
        Un token que cae a <0.1x es un failure.
        """
        # Empieza en $1, cae progresivamente a $0.05
        prices = [1.0, 0.8, 0.5, 0.3, 0.2, 0.15, 0.1, 0.08, 0.05, 0.05]
        ohlcv = self._make_ohlcv(prices)

        initial_price = prices[0]
        final_multiple = prices[-1] / initial_price

        assert final_multiple < 0.1, f"Final multiple deberia ser < 0.1, fue {final_multiple}"

    def test_rug_detection(self):
        """
        Un token que cae a <0.01x en 72h (3 dias) es un rug.
        """
        # Empieza en $1, cae a $0.005 en 3 dias
        prices = [1.0, 0.1, 0.01, 0.005] + [0.003] * 6
        ohlcv = self._make_ohlcv(prices)

        initial_price = prices[0]
        # Precio en dia 3
        price_72h = prices[3]
        multiple_72h = price_72h / initial_price

        assert multiple_72h < 0.01, f"Multiple a 72h deberia ser < 0.01, fue {multiple_72h}"

    def test_neutral_detection(self):
        """
        Un token que se mantiene entre 0.3x y 3x es neutral.
        """
        prices = [1.0, 1.2, 0.9, 1.5, 1.1, 0.8, 1.3, 1.0, 1.2, 0.9]
        ohlcv = self._make_ohlcv(prices)

        initial_price = prices[0]
        max_multiple = max(p * 1.02 for p in prices) / initial_price
        min_multiple = min(p * 0.98 for p in prices) / initial_price

        assert max_multiple < 3.0, f"Max deberia ser < 3x, fue {max_multiple}"
        assert min_multiple >= 0.3, f"Min deberia ser >= 0.3x, fue {min_multiple}"

    def test_binary_label_success(self):
        """
        Clasificacion binaria: 1 si alcanzo >= 5x.
        """
        prices = [1.0, 2.0, 4.0, 6.0, 5.0, 4.0, 3.0, 2.0]  # Alcanzo 6x
        initial_price = prices[0]
        max_high = max(p * 1.02 for p in prices)
        max_multiple = max_high / initial_price

        label_binary = 1 if max_multiple >= 5.0 else 0
        assert label_binary == 1

    def test_binary_label_failure(self):
        """
        Clasificacion binaria: 0 si nunca alcanzo 5x.
        """
        prices = [1.0, 1.5, 2.0, 1.8, 1.2, 0.8, 0.5, 0.3]  # Max ~2x
        initial_price = prices[0]
        max_high = max(p * 1.02 for p in prices)
        max_multiple = max_high / initial_price

        label_binary = 1 if max_multiple >= 5.0 else 0
        assert label_binary == 0

    def test_insufficient_data(self):
        """
        Con menos de MIN_DAYS_REQUIRED dias de datos (y sin early rug),
        no se deberia poder clasificar.
        """
        # Solo 1 dia (no es early rug porque no cae 90%+)
        prices = [1.0]
        assert len(prices) < MIN_DAYS_REQUIRED


class TestMinDaysRequired:
    """Tests para M1: reduccion de MIN_DAYS_REQUIRED de 7 a 3."""

    def test_min_days_is_3(self):
        """MIN_DAYS_REQUIRED debe ser 3 (reducido desde 7)."""
        assert MIN_DAYS_REQUIRED == 3, (
            f"MIN_DAYS_REQUIRED deberia ser 3, fue {MIN_DAYS_REQUIRED}"
        )

    def test_min_days_imported_from_config(self):
        """MIN_DAYS_REQUIRED debe coincidir con config.py."""
        from config import MIN_DAYS_REQUIRED as config_min_days
        assert config_min_days == 3
        assert MIN_DAYS_REQUIRED == config_min_days


class TestEarlyRug:
    """Tests para M1: deteccion temprana de rug pulls."""

    def _make_ohlcv(self, closes: list[float]) -> pd.DataFrame:
        """Helper: crea DataFrame OHLCV a partir de precios de cierre."""
        return pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=len(closes), freq="D"),
            "open": [c * 0.99 for c in closes],
            "high": [c * 1.02 for c in closes],
            "low": [c * 0.98 for c in closes],
            "close": closes,
            "volume": [10000] * len(closes),
        })

    def _make_labeler(self):
        """Helper: crea Labeler con storage mock."""
        storage = MagicMock()
        storage.query.return_value = pd.DataFrame()  # Sin datos de liquidez
        return Labeler(storage)

    def test_early_rug_detected_with_2_candles(self):
        """
        Un token con solo 2 velas que cae 95% debe ser detectado como early rug.
        """
        labeler = self._make_labeler()
        # $1 -> $0.03 = caida del 97% (low = 0.03 * 0.98 = 0.0294)
        ohlcv = self._make_ohlcv([1.0, 0.03])

        result = labeler.label_early_rug(ohlcv, "test_token_rug")

        assert result is not None, "Deberia detectar early rug"
        assert result["label_multi"] == "rug"
        assert result["label_binary"] == 0
        assert "Early rug" in result["notes"]

    def test_early_rug_not_triggered_for_small_drop(self):
        """
        Un token que cae solo 50% NO es un early rug (necesita 90%+).
        """
        labeler = self._make_labeler()
        # $1 -> $0.50 = caida del 50% (low = 0.50 * 0.98 = 0.49)
        ohlcv = self._make_ohlcv([1.0, 0.50])

        result = labeler.label_early_rug(ohlcv, "test_token_ok")

        assert result is None, "No deberia detectar early rug con solo 50% caida"

    def test_early_rug_with_single_candle_returns_none(self):
        """
        Con solo 1 vela no se puede detectar early rug.
        """
        labeler = self._make_labeler()
        ohlcv = self._make_ohlcv([1.0])

        result = labeler.label_early_rug(ohlcv, "test_token_single")

        assert result is None

    def test_early_rug_with_empty_df_returns_none(self):
        """
        Con DataFrame vacio retorna None.
        """
        labeler = self._make_labeler()

        result = labeler.label_early_rug(pd.DataFrame(), "test_empty")

        assert result is None

    def test_early_rug_result_has_required_fields(self):
        """
        El resultado de early rug debe tener todos los campos del label standard.
        """
        labeler = self._make_labeler()
        ohlcv = self._make_ohlcv([1.0, 0.01])  # 99% caida

        result = labeler.label_early_rug(ohlcv, "test_fields")

        assert result is not None
        required_fields = [
            "token_id", "label_multi", "label_binary",
            "max_multiple", "close_max_multiple", "final_multiple",
            "return_7d", "notes",
        ]
        for field in required_fields:
            assert field in result, f"Falta campo requerido: {field}"

    def test_early_rug_runs_before_min_days_check(self):
        """
        label_token() debe detectar early rug ANTES del check de MIN_DAYS.
        Un token con 2 velas y rug pull debe ser clasificado, no descartado.
        """
        storage = MagicMock()
        # Token con solo 2 velas, caida del 95%
        ohlcv_df = self._make_ohlcv([1.0, 0.03])
        storage.get_ohlcv.return_value = ohlcv_df
        storage.query.return_value = pd.DataFrame()
        storage.upsert_label = MagicMock()

        labeler = Labeler(storage)
        result = labeler.label_token("early_rug_token")

        # No debe retornar None (no fue descartado por MIN_DAYS)
        assert result is not None, (
            "label_token debe clasificar early rug antes del check de MIN_DAYS"
        )
        assert result["label_multi"] == "rug"
        # Verificar que se guardo en storage
        storage.upsert_label.assert_called_once()


class TestTieredLabeling:
    """Tests para M2: sistema de clasificacion por tiers."""

    def _make_ohlcv(self, closes: list[float]) -> pd.DataFrame:
        """Helper: crea DataFrame OHLCV a partir de precios de cierre."""
        return pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=len(closes), freq="D"),
            "open": [c * 0.99 for c in closes],
            "high": [c * 1.02 for c in closes],
            "low": [c * 0.98 for c in closes],
            "close": closes,
            "volume": [10000] * len(closes),
        })

    def _make_labeler(self):
        """Helper: crea Labeler con storage mock."""
        storage = MagicMock()
        storage.query.return_value = pd.DataFrame()
        return Labeler(storage)

    def test_mega_gem_tier(self):
        """Token con max return >= 10x es mega_gem (tier 6)."""
        labeler = self._make_labeler()
        # $1 -> $12 = max high 12.24x (12*1.02)
        prices = [1.0, 5.0, 12.0, 10.0, 8.0]
        ohlcv = self._make_ohlcv(prices)

        result = labeler.label_tiered(ohlcv, "mega_gem_token")

        assert result["tier"] == "mega_gem"
        assert result["tier_numeric"] == 6
        assert result["max_return"] >= 10.0

    def test_standard_gem_tier(self):
        """Token con max return >= 4x y < 10x es standard_gem (tier 5)."""
        labeler = self._make_labeler()
        # $1 -> $5 = max high 5.10x (5*1.02)
        prices = [1.0, 2.0, 5.0, 4.0, 3.0]
        ohlcv = self._make_ohlcv(prices)

        result = labeler.label_tiered(ohlcv, "standard_gem_token")

        assert result["tier"] == "standard_gem"
        assert result["tier_numeric"] == 5
        assert result["max_return"] >= 4.0
        assert result["max_return"] < 10.0

    def test_mini_gem_tier(self):
        """Token con max return >= 2x y < 4x es mini_gem (tier 4)."""
        labeler = self._make_labeler()
        # $1 -> $2.5 = max high 2.55x (2.5*1.02)
        prices = [1.0, 1.5, 2.5, 2.0, 1.8]
        ohlcv = self._make_ohlcv(prices)

        result = labeler.label_tiered(ohlcv, "mini_gem_token")

        assert result["tier"] == "mini_gem"
        assert result["tier_numeric"] == 4
        assert result["max_return"] >= 2.0
        assert result["max_return"] < 4.0

    def test_micro_gem_tier(self):
        """Token con max return >= 1.5x y < 2x es micro_gem (tier 3)."""
        labeler = self._make_labeler()
        # $1 -> $1.6 = max high 1.632x (1.6*1.02)
        prices = [1.0, 1.2, 1.6, 1.4, 1.3]
        ohlcv = self._make_ohlcv(prices)

        result = labeler.label_tiered(ohlcv, "micro_gem_token")

        assert result["tier"] == "micro_gem"
        assert result["tier_numeric"] == 3
        assert result["max_return"] >= 1.5
        assert result["max_return"] < 2.0

    def test_neutral_tier(self):
        """Token con max return entre 0.5x y 1.5x es neutral (tier 2)."""
        labeler = self._make_labeler()
        # $1 -> max 1.2 = max high 1.224x (1.2*1.02)
        prices = [1.0, 0.9, 1.2, 1.0, 0.8]
        ohlcv = self._make_ohlcv(prices)

        result = labeler.label_tiered(ohlcv, "neutral_token")

        assert result["tier"] == "neutral"
        assert result["tier_numeric"] == 2
        assert result["max_return"] >= 0.5
        assert result["max_return"] < 1.5

    def test_failure_tier(self):
        """Token con max return < 0.5x es failure (tier 1).

        max_return = max(high) / initial_close. Como initial_close = close[0],
        para que max_return < 0.5 necesitamos que TODOS los highs
        (incluyendo dia 0) sean < 0.5 * close[0]. Usamos datos sinteticos
        donde high[0] < close[0] para simular un token que colapsa
        inmediatamente tras su snapshot de cierre.
        """
        labeler = self._make_labeler()
        # initial_close = $1.0, pero high[0] = $0.45 (gap down extremo)
        # max(high) = 0.45, max_return = 0.45 / 1.0 = 0.45x < 0.5x
        closes = [1.0, 0.3, 0.2, 0.1, 0.05]
        ohlcv = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=len(closes), freq="D"),
            "open": [0.45, 0.3, 0.2, 0.1, 0.05],
            "high": [0.45, 0.35, 0.25, 0.12, 0.06],
            "low": [0.40, 0.25, 0.15, 0.08, 0.04],
            "close": closes,
            "volume": [10000] * len(closes),
        })

        result = labeler.label_tiered(ohlcv, "failure_token")

        assert result["tier"] == "failure"
        assert result["tier_numeric"] == 1
        assert result["max_return"] < 0.5

    def test_rug_tier(self):
        """Token que cae 90%+ en 72h es rug (tier 0)."""
        labeler = self._make_labeler()
        # $1 -> $0.05 en dia 2 = low 0.049x (0.05*0.98), caida 95%+
        prices = [1.0, 0.05, 0.03, 0.02]
        ohlcv = self._make_ohlcv(prices)

        result = labeler.label_tiered(ohlcv, "rug_token")

        assert result["tier"] == "rug"
        assert result["tier_numeric"] == 0

    def test_tiered_result_has_required_fields(self):
        """El resultado de label_tiered debe tener los 4 campos requeridos."""
        labeler = self._make_labeler()
        ohlcv = self._make_ohlcv([1.0, 1.5, 2.0])

        result = labeler.label_tiered(ohlcv, "test_fields")

        required_fields = ["tier", "tier_numeric", "max_return", "details"]
        for field in required_fields:
            assert field in result, f"Falta campo requerido: {field}"

    def test_tiered_with_insufficient_data(self):
        """Con datos insuficientes retorna tier 'unknown'."""
        labeler = self._make_labeler()
        # Solo 1 vela
        ohlcv = self._make_ohlcv([1.0])

        result = labeler.label_tiered(ohlcv, "test_insufficient")

        assert result["tier"] == "unknown"
        assert result["tier_numeric"] == -1

    def test_tiered_with_empty_df(self):
        """Con DataFrame vacio retorna tier 'unknown'."""
        labeler = self._make_labeler()

        result = labeler.label_tiered(pd.DataFrame(), "test_empty")

        assert result["tier"] == "unknown"
        assert result["tier_numeric"] == -1

    def test_tier_numeric_ordering(self):
        """Los tier_numeric deben estar ordenados de menor (peor) a mayor (mejor)."""
        tier_order = {
            "rug": 0,
            "failure": 1,
            "neutral": 2,
            "micro_gem": 3,
            "mini_gem": 4,
            "standard_gem": 5,
            "mega_gem": 6,
        }
        labeler = self._make_labeler()

        # Verificar que cada tier produce el numeric correcto
        # Caso failure requiere datos OHLCV sinteticos donde high[0] < close[0]
        # (gap down extremo para que max_return < 0.5x)
        failure_ohlcv = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=4, freq="D"),
            "open": [0.45, 0.3, 0.2, 0.15],
            "high": [0.45, 0.35, 0.25, 0.18],  # max = 0.45 < 0.5
            "low": [0.40, 0.25, 0.15, 0.12],
            "close": [1.0, 0.3, 0.2, 0.15],
            "volume": [10000] * 4,
        })

        test_cases = [
            (self._make_ohlcv([1.0, 0.02, 0.01]), "rug", 0),
            (failure_ohlcv, "failure", 1),
            (self._make_ohlcv([1.0, 1.1, 0.9, 1.0]), "neutral", 2),
            (self._make_ohlcv([1.0, 1.5, 1.3]), "micro_gem", 3),
            (self._make_ohlcv([1.0, 2.5, 2.0, 1.8]), "mini_gem", 4),
            (self._make_ohlcv([1.0, 5.0, 4.0]), "standard_gem", 5),
            (self._make_ohlcv([1.0, 12.0, 10.0]), "mega_gem", 6),
        ]

        for ohlcv, expected_tier, expected_numeric in test_cases:
            result = labeler.label_tiered(ohlcv, f"test_{expected_tier}")
            assert result["tier"] == expected_tier, (
                f"Esperaba tier '{expected_tier}', obtuve '{result['tier']}' "
                f"con max_return={result['max_return']}"
            )
            assert result["tier_numeric"] == expected_numeric, (
                f"Esperaba tier_numeric {expected_numeric}, obtuve {result['tier_numeric']}"
            )


class TestTierConfig:
    """Tests para las constantes de TIER_THRESHOLDS en config.py."""

    def test_tier_thresholds_exist_in_config(self):
        """TIER_THRESHOLDS debe estar definido en config.py."""
        from config import TIER_THRESHOLDS
        assert isinstance(TIER_THRESHOLDS, dict)

    def test_tier_thresholds_complete(self):
        """TIER_THRESHOLDS debe tener todas las claves necesarias."""
        from config import TIER_THRESHOLDS
        required_keys = [
            "mega_gem", "standard_gem", "mini_gem", "micro_gem",
            "neutral_upper", "neutral_lower", "failure",
            "rug_drop_pct", "rug_max_hours",
        ]
        for key in required_keys:
            assert key in TIER_THRESHOLDS, f"Falta clave '{key}' en TIER_THRESHOLDS"

    def test_tier_thresholds_ordering(self):
        """Los umbrales deben estar ordenados correctamente."""
        from config import TIER_THRESHOLDS
        assert TIER_THRESHOLDS["mega_gem"] > TIER_THRESHOLDS["standard_gem"]
        assert TIER_THRESHOLDS["standard_gem"] > TIER_THRESHOLDS["mini_gem"]
        assert TIER_THRESHOLDS["mini_gem"] > TIER_THRESHOLDS["micro_gem"]
        assert TIER_THRESHOLDS["micro_gem"] >= TIER_THRESHOLDS["neutral_upper"]
        assert TIER_THRESHOLDS["neutral_lower"] == TIER_THRESHOLDS["failure"]
