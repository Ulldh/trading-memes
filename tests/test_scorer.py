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
    """prob >= 0.60 -> STRONG."""
    signal = _determine_signal(0.65)
    assert signal == "STRONG"


def test_signal_medium():
    """prob >= 0.40 -> MEDIUM."""
    signal = _determine_signal(0.45)
    assert signal == "MEDIUM"


def test_signal_weak():
    """prob >= 0.30 -> WEAK."""
    signal = _determine_signal(0.35)
    assert signal == "WEAK"


def test_signal_none():
    """prob < 0.30 -> NONE."""
    signal = _determine_signal(0.20)
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


# ============================================================
# FEATURE COLUMNS: PRIORIDAD metadata.json SOBRE feature_columns.json
# ============================================================

def test_load_feature_columns_prefers_metadata_json(tmp_path, tmp_storage):
    """metadata.json de la version activa tiene prioridad sobre feature_columns.json."""
    from sklearn.datasets import make_classification
    import joblib

    # Features distintos en metadata.json vs feature_columns.json
    metadata_features = ["alpha", "beta", "gamma", "delta", "epsilon"]
    stale_features = ["old_a", "old_b", "old_c", "old_d"]

    # Entrenar modelo con 5 features (como metadata_features)
    X, y = make_classification(n_samples=50, n_features=5, random_state=42)
    rf = RandomForestClassifier(n_estimators=3, random_state=42)
    rf.fit(X, y)

    models_dir = tmp_path / "models"
    models_dir.mkdir()
    joblib.dump(rf, models_dir / "random_forest.joblib")

    # Crear feature_columns.json VIEJO (no deberia usarse)
    with open(models_dir / "feature_columns.json", "w") as f:
        json.dump(stale_features, f)

    # Crear latest_version.txt + metadata.json con features correctos
    (models_dir / "latest_version.txt").write_text("v99")
    v99_dir = models_dir / "v99"
    v99_dir.mkdir()
    with open(v99_dir / "metadata.json", "w") as f:
        json.dump({
            "version": "v99",
            "feature_names": metadata_features,
            "results": {
                "random_forest": {"optimal_threshold": 0.55}
            },
        }, f)

    scorer = GemScorer(
        storage=tmp_storage,
        model_name="random_forest",
        models_dir=models_dir,
    )

    # Debe usar las features de metadata.json, NO de feature_columns.json
    assert scorer.feature_columns == metadata_features
    assert scorer.feature_columns != stale_features


def test_prepare_features_discards_extra_columns(mock_scorer):
    """Features extra del builder (no conocidos por el modelo) se descartan."""
    features = {
        "token_id": "tok1",
        "feat_0": 1.0,
        "feat_1": 2.0,
        "feat_2": 3.0,
        "feat_3": 4.0,
        "feat_4": 5.0,
        # Features extra que el modelo NO conoce (simulando builder con mas features)
        "extra_technical_1": 99.0,
        "extra_interaction_2": 88.0,
        "extra_sentiment_3": 77.0,
    }
    df = mock_scorer._prepare_features(features)

    # Solo debe tener las 5 columnas del modelo
    assert list(df.columns) == mock_scorer.feature_columns
    assert len(df.columns) == 5
    # Las features extra NO deben estar presentes
    assert "extra_technical_1" not in df.columns
    assert "extra_interaction_2" not in df.columns
    assert "extra_sentiment_3" not in df.columns
