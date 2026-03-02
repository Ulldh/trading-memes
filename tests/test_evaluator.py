"""
test_evaluator.py - Tests para ModelEvaluator.

Cubre: evaluate(), find_optimal_threshold(), compare_models().
Usa datos sinteticos de conftest.py.
"""

import numpy as np
import pandas as pd
import pytest
from sklearn.tree import DecisionTreeClassifier


# ============================================================
# EVALUATE
# ============================================================

def test_evaluate_returns_all_metrics(evaluator, trained_rf, synthetic_data):
    """evaluate() devuelve todas las metricas esperadas."""
    X, y = synthetic_data
    result = evaluator.evaluate(trained_rf, X, y, model_name="test_rf")

    expected_keys = {
        "accuracy", "precision", "recall", "f1",
        "roc_auc", "pr_auc", "confusion_matrix", "y_pred", "y_prob",
    }
    assert expected_keys.issubset(result.keys())
    assert 0 <= result["accuracy"] <= 1
    assert 0 <= result["f1"] <= 1
    assert result["y_pred"] is not None
    assert result["y_prob"] is not None


def test_evaluate_without_predict_proba(evaluator, synthetic_data):
    """Modelo sin predict_proba -> roc_auc y pr_auc = None."""
    X, y = synthetic_data

    # DecisionTreeClassifier tiene predict_proba, pero podemos mockear
    class NoProbModel:
        def predict(self, X):
            return np.zeros(len(X), dtype=int)

    model = NoProbModel()
    result = evaluator.evaluate(model, X, y, model_name="no_prob")

    assert result["roc_auc"] is None
    assert result["pr_auc"] is None
    assert result["y_prob"] is None


def test_evaluate_single_class(evaluator, trained_rf, synthetic_data):
    """No crashea cuando y_test tiene una sola clase."""
    X, _ = synthetic_data
    y_single = pd.Series(np.zeros(len(X), dtype=int))

    result = evaluator.evaluate(trained_rf, X, y_single, model_name="single_class")
    # No debe crashear; roc_auc puede ser None por una sola clase
    assert result["accuracy"] is not None
    assert result["f1"] is not None


def test_evaluate_includes_optimal_threshold(evaluator, trained_rf, synthetic_data):
    """evaluate() incluye optimal_threshold cuando hay probabilidades y 2+ clases."""
    X, y = synthetic_data
    result = evaluator.evaluate(trained_rf, X, y, model_name="test_rf")

    assert "optimal_threshold" in result
    ot = result["optimal_threshold"]
    assert "best_threshold" in ot
    assert "best_f1" in ot
    assert "all_results" in ot


# ============================================================
# FIND OPTIMAL THRESHOLD
# ============================================================

def test_find_optimal_threshold_structure(evaluator, trained_rf, synthetic_data):
    """find_optimal_threshold() devuelve estructura correcta."""
    X, y = synthetic_data
    y_prob = trained_rf.predict_proba(X)[:, 1]

    result = evaluator.find_optimal_threshold(y, y_prob)

    assert isinstance(result["best_threshold"], float)
    assert isinstance(result["best_f1"], float)
    assert isinstance(result["all_results"], list)
    assert len(result["all_results"]) > 0
    # Cada resultado tiene las keys correctas
    first = result["all_results"][0]
    assert {"threshold", "f1", "precision", "recall"} == set(first.keys())


def test_find_optimal_threshold_best_is_max(evaluator, trained_rf, synthetic_data):
    """best_f1 es realmente el maximo de todos los resultados."""
    X, y = synthetic_data
    y_prob = trained_rf.predict_proba(X)[:, 1]

    result = evaluator.find_optimal_threshold(y, y_prob)

    all_f1s = [r["f1"] for r in result["all_results"]]
    assert result["best_f1"] == max(all_f1s)


def test_find_optimal_threshold_custom_range(evaluator, trained_rf, synthetic_data):
    """Thresholds personalizados se respetan."""
    X, y = synthetic_data
    y_prob = trained_rf.predict_proba(X)[:, 1]

    custom = np.array([0.3, 0.5, 0.7])
    result = evaluator.find_optimal_threshold(y, y_prob, thresholds=custom)

    thresholds_returned = [r["threshold"] for r in result["all_results"]]
    assert len(thresholds_returned) == 3
    assert set(thresholds_returned) == {0.3, 0.5, 0.7}


# ============================================================
# COMPARE MODELS
# ============================================================

def test_compare_models_sorted_by_f1(evaluator, trained_rf, synthetic_data):
    """compare_models() ordena por F1 descendente."""
    X, y = synthetic_data
    metrics_a = evaluator.evaluate(trained_rf, X, y, model_name="RF")

    # Crear un modelo peor
    dt = DecisionTreeClassifier(max_depth=1, random_state=42)
    dt.fit(X, y)
    metrics_b = evaluator.evaluate(dt, X, y, model_name="DT")

    comparison = evaluator.compare_models({"RF": metrics_a, "DT": metrics_b})

    assert len(comparison) == 2
    # F1 debe estar ordenado descendente
    f1_vals = comparison["f1"].tolist()
    assert f1_vals == sorted(f1_vals, reverse=True)


def test_compare_models_empty(evaluator):
    """Dict vacio -> DataFrame vacio."""
    comparison = evaluator.compare_models({})
    assert isinstance(comparison, pd.DataFrame)
    assert len(comparison) == 0


def test_compare_models_multiple(evaluator, trained_rf, synthetic_data):
    """3 modelos, estructura correcta."""
    X, y = synthetic_data
    metrics = evaluator.evaluate(trained_rf, X, y, model_name="RF")

    comparison = evaluator.compare_models({
        "RF1": metrics,
        "RF2": metrics,
        "RF3": metrics,
    })

    assert len(comparison) == 3
    assert "modelo" in comparison.columns
    assert "f1" in comparison.columns
    assert "roc_auc" in comparison.columns
