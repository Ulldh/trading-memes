"""
test_explainer.py - Tests para SHAPExplainer.

Testea SHAP con RF directo y con CalibratedClassifierCV (el fix de A2).
"""

import numpy as np
import pandas as pd
import pytest

from src.models.explainer import SHAPExplainer


# ============================================================
# INICIALIZACION
# ============================================================

def test_init_with_raw_rf(trained_rf, synthetic_data):
    """Inicializa sin error con RF directo."""
    X, _ = synthetic_data
    explainer = SHAPExplainer(trained_rf, X)
    assert explainer.explainer is not None


def test_init_with_calibrated_rf(trained_calibrated_rf, synthetic_data):
    """Inicializa sin error con CalibratedClassifierCV (el fix)."""
    X, _ = synthetic_data
    explainer = SHAPExplainer(trained_calibrated_rf, X)
    assert explainer.explainer is not None


# ============================================================
# SHAP VALUES
# ============================================================

def test_get_shap_values_shape(trained_rf, synthetic_data):
    """Shape de SHAP values = (n_samples, n_features)."""
    X, _ = synthetic_data
    explainer = SHAPExplainer(trained_rf, X)

    X_subset = X.iloc[:20]
    shap_values = explainer.get_shap_values(X_subset)

    assert shap_values.shape == (20, X.shape[1])


def test_get_shap_values_class1(trained_rf, synthetic_data):
    """Para clasificacion binaria, retorna SHAP de la clase positiva."""
    X, _ = synthetic_data
    explainer = SHAPExplainer(trained_rf, X)

    X_subset = X.iloc[:10]
    shap_values = explainer.get_shap_values(X_subset)

    # Debe ser 2D (no 3D), ya que selecciona clase 1
    assert shap_values.ndim == 2


# ============================================================
# TOP FEATURES
# ============================================================

def test_get_top_features_returns_dataframe(trained_rf, synthetic_data):
    """Top features devuelve DataFrame con columnas correctas."""
    X, _ = synthetic_data
    explainer = SHAPExplainer(trained_rf, X)

    top = explainer.get_top_features(X.iloc[:30], n=5)

    assert isinstance(top, pd.DataFrame)
    assert "rank" in top.columns
    assert "feature" in top.columns
    assert "mean_abs_shap" in top.columns
    assert len(top) == 5


def test_get_top_features_sorted(trained_rf, synthetic_data):
    """Top features estan ordenados por mean_abs_shap descendente."""
    X, _ = synthetic_data
    explainer = SHAPExplainer(trained_rf, X)

    top = explainer.get_top_features(X.iloc[:30], n=5)

    shap_vals = top["mean_abs_shap"].tolist()
    assert shap_vals == sorted(shap_vals, reverse=True)


# ============================================================
# EXPLICACION INDIVIDUAL
# ============================================================

def test_explain_single_token_structure(trained_rf, synthetic_data):
    """explain_single_token devuelve estructura correcta."""
    X, _ = synthetic_data
    explainer = SHAPExplainer(trained_rf, X)

    result = explainer.explain_single_token(X.iloc[:30], idx=0)

    assert "idx" in result
    assert "expected_value" in result
    assert "prediction" in result
    assert "top_positive" in result
    assert "top_negative" in result
    assert result["idx"] == 0
    assert isinstance(result["expected_value"], float)


def test_explain_single_token_invalid_idx(trained_rf, synthetic_data):
    """idx fuera de rango -> dict vacio."""
    X, _ = synthetic_data
    explainer = SHAPExplainer(trained_rf, X)

    result = explainer.explain_single_token(X.iloc[:10], idx=999)
    assert result == {}
