"""
test_builder.py - Tests para FeatureBuilder.

Usa tmp_storage de conftest.py con datos minimos inyectados.
"""

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from src.features.builder import FeatureBuilder


@pytest.fixture
def builder_with_token(tmp_storage):
    """FeatureBuilder con un token basico en storage."""
    tmp_storage.upsert_token({
        "token_id": "tok_test",
        "chain": "solana",
        "name": "TestCoin",
        "symbol": "TC",
        "pool_address": "pool_test",
        "created_at": "2026-02-20T12:00:00Z",
    })
    # Insertar OHLCV minimo para que price_action funcione
    rows = [
        {
            "token_id": "tok_test", "chain": "solana", "pool_address": "pool_test",
            "timeframe": "day", "timestamp": f"2026-02-{20+i:02d}T00:00:00Z",
            "open": 0.001 + i * 0.0001, "high": 0.0015 + i * 0.0001,
            "low": 0.0005 + i * 0.0001, "close": 0.0012 + i * 0.0001,
            "volume": 10000 + i * 1000,
        }
        for i in range(10)
    ]
    tmp_storage.insert_ohlcv_batch(rows)
    return FeatureBuilder(tmp_storage), tmp_storage


# ============================================================
# BUILD FEATURES FOR TOKEN
# ============================================================

def test_build_features_returns_dict_with_token_id(builder_with_token):
    """Siempre incluye token_id en el resultado."""
    builder, _ = builder_with_token
    features = builder.build_features_for_token("tok_test")
    assert isinstance(features, dict)
    assert features["token_id"] == "tok_test"


def test_build_features_token_not_found(builder_with_token):
    """Token inexistente -> dict con solo token_id."""
    builder, _ = builder_with_token
    features = builder.build_features_for_token("nonexistent_token")
    assert features["token_id"] == "nonexistent_token"
    assert len(features) == 1


def test_build_features_module_error_resilience(builder_with_token):
    """Si un modulo de features falla, los demas continuan."""
    builder, _ = builder_with_token

    # Patchear tokenomics para que falle
    with patch(
        "src.features.builder.compute_tokenomics_features",
        side_effect=RuntimeError("Boom"),
    ):
        features = builder.build_features_for_token("tok_test")

    # Debe tener features de otros modulos (price_action, temporal, etc.)
    assert features["token_id"] == "tok_test"
    assert len(features) > 1


def test_build_features_includes_temporal(builder_with_token):
    """Features temporales presentes cuando hay created_at."""
    builder, _ = builder_with_token
    features = builder.build_features_for_token("tok_test")

    # Al menos alguno de los features temporales debe existir
    temporal_keys = {"launch_day_of_week", "launch_hour_utc", "launch_is_weekend", "days_since_launch"}
    found = temporal_keys.intersection(features.keys())
    assert len(found) > 0, f"No se encontraron features temporales. Keys: {list(features.keys())}"


def test_build_features_includes_volatility(builder_with_token):
    """Features de volatilidad presentes cuando hay OHLCV."""
    builder, _ = builder_with_token
    features = builder.build_features_for_token("tok_test")

    # volatility_advanced genera features como max_drawdown, etc.
    # Verificar que al menos hay mas de solo token_id + temporal
    assert len(features) > 5


# ============================================================
# BUILD ALL FEATURES
# ============================================================

def test_build_all_features_returns_dataframe(builder_with_token):
    """build_all_features() devuelve DataFrame con token_id como indice."""
    builder, _ = builder_with_token
    df = builder.build_all_features()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.index.name == "token_id"


def test_build_all_features_empty_storage(tmp_storage):
    """0 tokens -> DataFrame vacio."""
    builder = FeatureBuilder(tmp_storage)
    df = builder.build_all_features()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0


def test_build_features_calls_multiple_modules(builder_with_token):
    """Verifica que se llaman multiples modulos de features."""
    builder, _ = builder_with_token
    features = builder.build_features_for_token("tok_test")

    # Con OHLCV y created_at, debe haber features de price_action + temporal + volatility
    # El dict resultante debe tener bastantes keys
    assert len(features) >= 5, f"Muy pocos features: {len(features)}"
