"""
test_scorer.py - Tests para GemScorer.

Usa mocks para evitar dependencias de disco (modelos, feature_columns).
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from src.models.scorer import GemScorer, SIGNAL_THRESHOLDS


# ============================================================
# FIXTURES LOCALES
# ============================================================

@pytest.fixture
def mock_scorer(tmp_path, tmp_storage):
    """GemScorer con modelo falso guardado en disco."""
    # Entrenar un mini-modelo y guardarlo
    from sklearn.datasets import make_classification
    import joblib

    X, y = make_classification(n_samples=100, n_features=5, random_state=42)
    feature_names = [f"feat_{i}" for i in range(5)]

    rf = RandomForestClassifier(n_estimators=5, random_state=42)
    rf.fit(X, y)

    models_dir = tmp_path / "models"
    models_dir.mkdir()
    joblib.dump(rf, models_dir / "random_forest.joblib")

    # Guardar feature_columns
    with open(models_dir / "feature_columns.json", "w") as f:
        json.dump(feature_names, f)

    # Inyectar un token en storage
    tmp_storage.upsert_token({
        "token_id": "tok_scorer_test",
        "chain": "solana",
        "name": "ScorerCoin",
        "symbol": "SCR",
        "pool_address": "pool_scr",
        "created_at": "2026-02-15T10:00:00Z",
    })

    scorer = GemScorer(
        storage=tmp_storage,
        model_name="random_forest",
        models_dir=models_dir,
    )
    return scorer


# ============================================================
# _prepare_features
# ============================================================

def test_prepare_features_aligns_columns(mock_scorer):
    """Columnas alineadas con feature_columns."""
    features = {
        "token_id": "tok1",
        "feat_0": 1.0,
        "feat_2": 3.0,
        # feat_1, feat_3, feat_4 faltantes -> 0
    }
    df = mock_scorer._prepare_features(features)
    assert list(df.columns) == mock_scorer.feature_columns
    assert df["feat_1"].iloc[0] == 0  # Faltante -> 0
    assert df["feat_0"].iloc[0] == 1.0


def test_prepare_features_fills_nan(mock_scorer):
    """NaN -> 0."""
    features = {
        "token_id": "tok1",
        "feat_0": None,
        "feat_1": float("nan"),
        "feat_2": 2.0,
    }
    df = mock_scorer._prepare_features(features)
    assert df["feat_0"].iloc[0] == 0
    assert df["feat_1"].iloc[0] == 0
    assert df["feat_2"].iloc[0] == 2.0


# ============================================================
# SIGNAL LEVELS
# ============================================================

def test_signal_strong():
    """prob >= 0.80 -> STRONG."""
    signal = _determine_signal(0.85)
    assert signal == "STRONG"


def test_signal_medium():
    """prob >= 0.65 -> MEDIUM."""
    signal = _determine_signal(0.70)
    assert signal == "MEDIUM"


def test_signal_weak():
    """prob >= 0.50 -> WEAK."""
    signal = _determine_signal(0.55)
    assert signal == "WEAK"


def test_signal_none():
    """prob < 0.50 -> NONE."""
    signal = _determine_signal(0.30)
    assert signal == "NONE"


def _determine_signal(probability: float) -> str:
    """Replica la logica de determinacion de senal de GemScorer."""
    signal = "NONE"
    for level, threshold in sorted(
        SIGNAL_THRESHOLDS.items(), key=lambda x: -x[1]
    ):
        if probability >= threshold:
            signal = level
            break
    return signal


# ============================================================
# SCORE TOKEN
# ============================================================

def test_score_token_returns_structure(mock_scorer):
    """score_token devuelve estructura correcta."""
    # Mockear build_features_for_token para evitar DB compleja
    fake_features = {
        "token_id": "tok_scorer_test",
        "feat_0": 0.5, "feat_1": 0.3, "feat_2": 0.8,
        "feat_3": 0.1, "feat_4": 0.6,
    }
    with patch.object(
        mock_scorer.builder, "build_features_for_token", return_value=fake_features
    ):
        result = mock_scorer.score_token("tok_scorer_test")

    assert "token_id" in result
    assert "probability" in result
    assert "signal" in result
    assert "prediction" in result
    assert "features_used" in result
    assert result["signal"] in {"STRONG", "MEDIUM", "WEAK", "NONE"}
    assert 0.0 <= result["probability"] <= 1.0


def test_score_token_no_features(mock_scorer):
    """Token sin datos -> signal=NONE con error msg."""
    # build_features devuelve solo token_id (sin features reales)
    with patch.object(
        mock_scorer.builder, "build_features_for_token",
        return_value={"token_id": "tok_empty"}
    ):
        result = mock_scorer.score_token("tok_empty")

    assert result["signal"] == "NONE"
    assert result["features_used"] == 0
    assert "error" in result
