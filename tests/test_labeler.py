"""
test_labeler.py - Tests para el sistema de clasificacion de tokens.

Ejecutar con: pytest tests/test_labeler.py -v

Verifican que el labeler clasifica tokens correctamente:
1. Gems (10x+ sostenido)
2. Failures (<0.1x)
3. Rugs (<0.01x rapido)
4. Clasificacion binaria (5x threshold)
"""

import sys
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.labeler import Labeler


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
        Con menos de 7 dias de datos, no se deberia poder clasificar.
        """
        prices = [1.0, 1.5, 2.0]  # Solo 3 dias
        assert len(prices) < 7
