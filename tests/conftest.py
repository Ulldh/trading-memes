"""
conftest.py - Fixtures compartidas para todos los tests.

Proporciona datos sinteticos, modelos pre-entrenados y storage temporal
para evitar duplicar setup en cada archivo de tests.
"""

import sys
from pathlib import Path

# Asegurar que el proyecto esta en el path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV

from src.data.storage import Storage
from src.models.evaluator import ModelEvaluator


@pytest.fixture
def synthetic_data():
    """Genera datos sinteticos desbalanceados (80/20) para tests."""
    X, y = make_classification(
        n_samples=200,
        n_features=10,
        n_informative=5,
        n_redundant=2,
        weights=[0.8, 0.2],
        random_state=42,
    )
    feature_names = [f"feature_{i}" for i in range(X.shape[1])]
    X_df = pd.DataFrame(X, columns=feature_names)
    return X_df, pd.Series(y, name="label")


@pytest.fixture
def trained_rf(synthetic_data):
    """RF entrenado sobre datos sinteticos."""
    X, y = synthetic_data
    rf = RandomForestClassifier(n_estimators=20, random_state=42)
    rf.fit(X, y)
    return rf


@pytest.fixture
def trained_calibrated_rf(synthetic_data):
    """RF + CalibratedClassifierCV entrenado sobre datos sinteticos."""
    X, y = synthetic_data
    rf = RandomForestClassifier(n_estimators=20, random_state=42)
    cal_rf = CalibratedClassifierCV(rf, cv=3, method="sigmoid")
    cal_rf.fit(X, y)
    return cal_rf


@pytest.fixture
def evaluator():
    """Instancia de ModelEvaluator."""
    return ModelEvaluator()


@pytest.fixture
def tmp_storage(tmp_path):
    """Storage con SQLite temporal (no toca la DB real)."""
    db_path = tmp_path / "test.db"
    return Storage(db_path=db_path)
