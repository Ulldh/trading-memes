"""
test_ml_pipeline_v2.py - Tests para los fixes criticos de la Fase 0 del pipeline ML.

Cubre:
- XGBoost cross-validation (0.1)
- Threshold optimization (0.2)
- Calibracion de probabilidades (0.3)
- Exclusion de tokens de entrenamiento en backtester (0.4)
- Sensitivity analysis del labeler (0.5)
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier

from src.models.evaluator import ModelEvaluator
from src.models.trainer import ModelTrainer


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def synthetic_data():
    """Genera datos sinteticos desbalanceados para tests."""
    X, y = make_classification(
        n_samples=200,
        n_features=10,
        n_informative=5,
        n_redundant=2,
        weights=[0.8, 0.2],
        random_state=42,
    )
    return X, y


@pytest.fixture
def trained_rf(synthetic_data):
    """Entrena un RF basico sobre datos sinteticos."""
    X, y = synthetic_data
    model = RandomForestClassifier(n_estimators=50, random_state=42)
    model.fit(X, y)
    return model


@pytest.fixture
def evaluator():
    """Instancia de ModelEvaluator."""
    return ModelEvaluator()


@pytest.fixture
def trainer():
    """Instancia de ModelTrainer."""
    return ModelTrainer(random_seed=42)


# ============================================================
# 0.1 - XGBoost Cross-Validation
# ============================================================

class TestXGBoostCV:
    """Verifica que XGBoost tiene cross-validation como RF."""

    def test_xgboost_has_cv_scores(self, trainer):
        """results['xgboost'] debe tener cv_f1_mean y cv_f1_std."""
        # Crear datos sinteticos como DataFrames
        np.random.seed(42)
        n = 100
        features_df = pd.DataFrame({
            "token_id": [f"token_{i}" for i in range(n)],
            "feat_1": np.random.randn(n),
            "feat_2": np.random.randn(n),
            "feat_3": np.random.randn(n),
            "feat_4": np.random.randn(n),
            "feat_5": np.random.randn(n),
        })
        labels_df = pd.DataFrame({
            "token_id": [f"token_{i}" for i in range(n)],
            "label_binary": np.random.choice([0, 1], size=n, p=[0.7, 0.3]),
        })

        results = trainer.train_all(features_df, labels_df, target="label_binary")

        # Verificar que XGBoost tiene metricas de CV
        assert "xgboost" in results
        xgb_results = results["xgboost"]
        assert "cv_f1_mean" in xgb_results, "XGBoost debe tener cv_f1_mean"
        assert "cv_f1_std" in xgb_results, "XGBoost debe tener cv_f1_std"
        assert isinstance(xgb_results["cv_f1_mean"], float)
        assert isinstance(xgb_results["cv_f1_std"], float)
        assert xgb_results["cv_f1_mean"] >= 0.0
        assert xgb_results["cv_f1_std"] >= 0.0


# ============================================================
# 0.2 - Threshold Optimization
# ============================================================

class TestThresholdOptimization:
    """Verifica que find_optimal_threshold encuentra el threshold optimo."""

    def test_find_optimal_threshold(self, evaluator, synthetic_data, trained_rf):
        """Debe encontrar un threshold optimo entre 0.1 y 0.9."""
        X, y = synthetic_data
        y_prob = trained_rf.predict_proba(X)[:, 1]

        result = evaluator.find_optimal_threshold(y, y_prob)

        assert "best_threshold" in result
        assert "best_f1" in result
        assert "all_results" in result
        assert len(result["all_results"]) > 0

    def test_threshold_bounds(self, evaluator, synthetic_data, trained_rf):
        """El threshold optimo debe estar en [0.1, 0.9]."""
        X, y = synthetic_data
        y_prob = trained_rf.predict_proba(X)[:, 1]

        result = evaluator.find_optimal_threshold(y, y_prob)

        assert 0.1 <= result["best_threshold"] <= 0.9
        assert 0.0 <= result["best_f1"] <= 1.0

    def test_threshold_all_results_structure(self, evaluator, synthetic_data, trained_rf):
        """Cada resultado debe tener threshold, f1, precision, recall."""
        X, y = synthetic_data
        y_prob = trained_rf.predict_proba(X)[:, 1]

        result = evaluator.find_optimal_threshold(y, y_prob)

        for r in result["all_results"]:
            assert "threshold" in r
            assert "f1" in r
            assert "precision" in r
            assert "recall" in r

    def test_evaluate_includes_optimal_threshold(self, evaluator, synthetic_data, trained_rf):
        """evaluate() debe incluir optimal_threshold cuando hay probabilidades."""
        X, y = synthetic_data
        X_df = pd.DataFrame(X, columns=[f"f{i}" for i in range(X.shape[1])])
        y_series = pd.Series(y)

        result = evaluator.evaluate(trained_rf, X_df, y_series, "TestModel")

        assert "optimal_threshold" in result
        assert result["optimal_threshold"]["best_threshold"] >= 0.1
        assert result["optimal_threshold"]["best_threshold"] <= 0.9


# ============================================================
# 0.3 - Calibracion de Probabilidades
# ============================================================

class TestCalibration:
    """Verifica la calibracion de modelos."""

    def test_calibration_wrapping(self, trainer, synthetic_data):
        """Un modelo calibrado debe mantener predict y predict_proba."""
        X, y = synthetic_data
        model = RandomForestClassifier(n_estimators=50, random_state=42)
        model.fit(X, y)

        calibrated = trainer.calibrate_model(model, X, y, method="sigmoid")

        # Debe tener los metodos necesarios
        assert hasattr(calibrated, "predict")
        assert hasattr(calibrated, "predict_proba")

        # Debe poder predecir
        preds = calibrated.predict(X)
        assert len(preds) == len(X)

        probs = calibrated.predict_proba(X)
        assert probs.shape == (len(X), 2)

    def test_calibrated_proba_between_0_1(self, trainer, synthetic_data):
        """Las probabilidades calibradas deben estar en [0, 1]."""
        X, y = synthetic_data
        model = RandomForestClassifier(n_estimators=50, random_state=42)
        model.fit(X, y)

        calibrated = trainer.calibrate_model(model, X, y)

        probs = calibrated.predict_proba(X)
        assert np.all(probs >= 0.0), "Hay probabilidades < 0"
        assert np.all(probs <= 1.0), "Hay probabilidades > 1"
        # Las probabilidades de cada fila deben sumar ~1
        row_sums = probs.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-6)

    def test_train_all_calibrates_models(self, trainer):
        """train_all debe calibrar los modelos y marcarlos como calibrated."""
        np.random.seed(42)
        n = 100
        features_df = pd.DataFrame({
            "token_id": [f"token_{i}" for i in range(n)],
            "feat_1": np.random.randn(n),
            "feat_2": np.random.randn(n),
            "feat_3": np.random.randn(n),
            "feat_4": np.random.randn(n),
            "feat_5": np.random.randn(n),
        })
        labels_df = pd.DataFrame({
            "token_id": [f"token_{i}" for i in range(n)],
            "label_binary": np.random.choice([0, 1], size=n, p=[0.7, 0.3]),
        })

        results = trainer.train_all(features_df, labels_df)

        # Verificar que los modelos estan calibrados
        for name in ["random_forest", "xgboost"]:
            if name in results and "error" not in results[name]:
                assert results[name].get("calibrated") is True, \
                    f"{name} debe estar marcado como calibrado"


# ============================================================
# 0.4 - Backtester Excluye Train Tokens
# ============================================================

class TestBacktesterExcludeTokens:
    """Verifica que el backtester excluye tokens de entrenamiento."""

    def test_backtester_excludes_train_tokens(self):
        """Con exclude_tokens, deben filtrarse del backtest."""
        from src.models.backtester import Backtester

        # Mock de storage y scorer
        mock_storage = MagicMock()
        mock_scorer = MagicMock()

        # Simular 5 tokens con labels
        labels_data = pd.DataFrame({
            "token_id": ["t1", "t2", "t3", "t4", "t5"],
            "label_multi": ["gem", "failure", "neutral", "gem", "failure"],
            "label_binary": [1, 0, 0, 1, 0],
            "max_multiple": [15.0, 0.05, 1.2, 12.0, 0.03],
            "final_multiple": [8.0, 0.01, 0.8, 6.0, 0.01],
            "chain": ["solana"] * 5,
            "symbol": ["A", "B", "C", "D", "E"],
        })
        mock_storage.query.return_value = labels_data

        # Simular scores
        def fake_score(token_id):
            return {
                "probability": 0.9 if token_id in ["t1", "t4"] else 0.1,
                "signal": "STRONG" if token_id in ["t1", "t4"] else "NONE",
            }
        mock_scorer.score_token.side_effect = fake_score

        bt = Backtester(storage=mock_storage, scorer=mock_scorer)

        # Excluir t1 y t2 (tokens de entrenamiento)
        result = bt.backtest_historical(
            signal_threshold="MEDIUM",
            exclude_tokens=["t1", "t2"],
        )

        # Solo deberian evaluarse t3, t4, t5 (3 tokens)
        assert result["total_tokens"] == 3
        # t4 es gem y tiene senal -> true positive
        assert result["true_positives"] == 1

    def test_load_train_tokens_from_metadata(self):
        """load_train_tokens debe leer de metadata.json."""
        from src.models.backtester import Backtester

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Crear estructura de version
            v1_dir = tmpdir / "v1"
            v1_dir.mkdir()

            # Crear metadata con train_token_ids
            metadata = {
                "version": "v1",
                "train_token_ids": ["token_a", "token_b", "token_c"],
            }
            with open(v1_dir / "metadata.json", "w") as f:
                json.dump(metadata, f)

            # Crear latest_version.txt
            with open(tmpdir / "latest_version.txt", "w") as f:
                f.write("v1")

            bt = Backtester(storage=MagicMock(), scorer=MagicMock())
            tokens = bt.load_train_tokens(models_dir=tmpdir)

            assert tokens == ["token_a", "token_b", "token_c"]

    def test_load_train_tokens_empty_when_no_metadata(self):
        """load_train_tokens retorna lista vacia si no hay metadata."""
        from src.models.backtester import Backtester

        with tempfile.TemporaryDirectory() as tmpdir:
            bt = Backtester(storage=MagicMock(), scorer=MagicMock())
            tokens = bt.load_train_tokens(models_dir=Path(tmpdir))
            assert tokens == []


# ============================================================
# 0.5 - Sensitivity Analysis del Labeler
# ============================================================

class TestSensitivityAnalysis:
    """Verifica el sensitivity analysis del labeler."""

    def test_sensitivity_analysis_returns_dataframe(self):
        """sensitivity_analysis debe retornar DataFrame con estructura correcta."""
        from src.models.labeler import Labeler

        mock_storage = MagicMock()

        # Simular tokens
        mock_storage.get_all_tokens.return_value = pd.DataFrame({
            "token_id": ["t1", "t2", "t3"],
        })

        # Simular OHLCV con datos suficientes (10 dias)
        def fake_ohlcv(token_id, timeframe="day"):
            np.random.seed(hash(token_id) % 2**31)
            n = 15
            base_price = np.random.uniform(0.001, 1.0)
            # Generar precios con algo de variacion
            prices = base_price * np.cumprod(1 + np.random.randn(n) * 0.1)
            return pd.DataFrame({
                "token_id": [token_id] * n,
                "open": prices * 0.99,
                "high": prices * 1.05,
                "low": prices * 0.95,
                "close": prices,
                "volume": np.random.uniform(1000, 100000, n),
            })
        mock_storage.get_ohlcv.side_effect = fake_ohlcv

        labeler = Labeler(mock_storage)
        df = labeler.sensitivity_analysis()

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        # Verificar columnas clave
        assert "gem_min_multiple" in df.columns
        assert "gem_sustain_multiple" in df.columns
        assert "gem_sustain_days" in df.columns
        assert "binary_threshold" in df.columns
        assert "gem_count" in df.columns
        assert "gem_pct" in df.columns

        # Verificar que hay combinaciones (5 * 3 * 4 * 4 = 240)
        assert len(df) == 5 * 3 * 4 * 4


# ============================================================
# 0.3+0.4 - Train Token IDs guardados en metadata
# ============================================================

class TestTrainTokenIds:
    """Verifica que train_token_ids se guardan en el metadata."""

    def test_train_token_ids_saved(self, trainer):
        """Despues de train_all, _train_token_ids debe existir."""
        np.random.seed(42)
        n = 50
        features_df = pd.DataFrame({
            "token_id": [f"token_{i}" for i in range(n)],
            "feat_1": np.random.randn(n),
            "feat_2": np.random.randn(n),
        })
        labels_df = pd.DataFrame({
            "token_id": [f"token_{i}" for i in range(n)],
            "label_binary": np.random.choice([0, 1], size=n, p=[0.7, 0.3]),
        })

        trainer.train_all(features_df, labels_df)

        assert hasattr(trainer, "_train_token_ids")
        assert len(trainer._train_token_ids) > 0
        # Debe ser ~80% del total (test_size=0.2)
        assert len(trainer._train_token_ids) == int(n * 0.8) or \
               abs(len(trainer._train_token_ids) - int(n * 0.8)) <= 1

    def test_train_token_ids_in_versioned_metadata(self, trainer):
        """save_models_versioned debe incluir train_token_ids en metadata.json."""
        np.random.seed(42)
        n = 50
        features_df = pd.DataFrame({
            "token_id": [f"token_{i}" for i in range(n)],
            "feat_1": np.random.randn(n),
            "feat_2": np.random.randn(n),
        })
        labels_df = pd.DataFrame({
            "token_id": [f"token_{i}" for i in range(n)],
            "label_binary": np.random.choice([0, 1], size=n, p=[0.7, 0.3]),
        })

        trainer.train_all(features_df, labels_df)

        with tempfile.TemporaryDirectory() as tmpdir:
            version_dir = trainer.save_models_versioned(base_path=Path(tmpdir))

            # Leer metadata.json
            metadata_path = version_dir / "metadata.json"
            assert metadata_path.exists()

            with open(metadata_path) as f:
                metadata = json.load(f)

            assert "train_token_ids" in metadata
            assert len(metadata["train_token_ids"]) > 0
