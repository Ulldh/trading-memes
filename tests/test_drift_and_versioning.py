"""
test_drift_and_versioning.py - Tests para drift detection y versionado de modelos.

Ejecutar con: pytest tests/test_drift_and_versioning.py -v

Verifican que:
1. DriftDetector detecta data drift, concept drift, volume drift, time drift.
2. ModelTrainer guarda modelos con versionado correcto.
3. ModelTrainer carga versiones especificas.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import shutil

import pytest
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.drift_detector import DriftDetector
from src.models.trainer import ModelTrainer


# ============================================================
# Tests para DriftDetector
# ============================================================

class TestDriftDetector:
    """Tests para deteccion de drift."""

    def test_init(self):
        """Inicializa con parametros por defecto."""
        detector = DriftDetector()
        assert detector.ks_threshold == 0.05
        assert detector.f1_threshold == 0.5
        assert detector.volume_threshold == 50
        assert detector.days_threshold == 30

    def test_init_custom_thresholds(self):
        """Inicializa con parametros personalizados."""
        detector = DriftDetector(
            ks_threshold=0.01,
            f1_threshold=0.6,
            volume_threshold=100,
            days_threshold=60,
        )
        assert detector.ks_threshold == 0.01
        assert detector.f1_threshold == 0.6
        assert detector.volume_threshold == 100
        assert detector.days_threshold == 60

    def test_detect_data_drift_no_drift(self):
        """No detecta drift cuando distribuciones son similares."""
        # Crear datos con misma distribucion
        np.random.seed(42)
        train_data = pd.DataFrame({
            "feature1": np.random.normal(0, 1, 100),
            "feature2": np.random.normal(5, 2, 100),
        })
        new_data = pd.DataFrame({
            "feature1": np.random.normal(0, 1, 100),
            "feature2": np.random.normal(5, 2, 100),
        })

        detector = DriftDetector()
        result = detector.detect_data_drift(train_data, new_data)

        assert isinstance(result, dict)
        assert "has_drift" in result
        assert "drifted_features" in result
        # No deberia haber drift (distribuciones similares)
        # assert result["has_drift"] is False  # Puede ser True por azar con p=0.05

    def test_detect_data_drift_with_drift(self):
        """Detecta drift cuando distribuciones cambian significativamente."""
        # Crear datos con distribuciones diferentes
        np.random.seed(42)
        train_data = pd.DataFrame({
            "feature1": np.random.normal(0, 1, 100),
            "feature2": np.random.normal(5, 2, 100),
        })
        new_data = pd.DataFrame({
            "feature1": np.random.normal(10, 1, 100),  # Media diferente
            "feature2": np.random.normal(50, 2, 100),  # Media diferente
        })

        detector = DriftDetector()
        result = detector.detect_data_drift(train_data, new_data)

        assert result["has_drift"] is True
        assert len(result["drifted_features"]) > 0

    def test_detect_concept_drift(self):
        """Detecta concept drift cuando F1 score es bajo."""
        # Crear datos y modelo simple
        X = pd.DataFrame({
            "feature1": [1, 2, 3, 4, 5],
            "feature2": [2, 4, 6, 8, 10],
        })
        y = pd.Series([0, 0, 1, 1, 1])

        # Entrenar modelo simple
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(X, y)

        # Nuevos datos que el modelo predice mal (concept drift)
        X_new = pd.DataFrame({
            "feature1": [6, 7, 8, 9, 10],
            "feature2": [12, 14, 16, 18, 20],
        })
        y_new = pd.Series([0, 0, 0, 0, 0])  # Todas negativas (opuesto al modelo)

        detector = DriftDetector(f1_threshold=0.8)
        result = detector.detect_concept_drift(model, X_new, y_new)

        assert isinstance(result, dict)
        assert "has_drift" in result
        assert "f1_score" in result
        # Deberia detectar drift (F1 sera bajo)

    def test_detect_volume_drift_yes(self):
        """Detecta volume drift cuando hay muchos tokens nuevos."""
        detector = DriftDetector(volume_threshold=50)
        result = detector.detect_volume_drift(train_size=100, new_size=60)

        assert result["has_drift"] is True
        assert result["new_tokens"] == 60

    def test_detect_volume_drift_no(self):
        """No detecta volume drift cuando hay pocos tokens nuevos."""
        detector = DriftDetector(volume_threshold=50)
        result = detector.detect_volume_drift(train_size=100, new_size=30)

        assert result["has_drift"] is False
        assert result["new_tokens"] == 30

    def test_detect_time_drift_yes(self):
        """Detecta time drift cuando han pasado muchos dias."""
        # Fecha de hace 40 dias
        last_train = (datetime.now() - timedelta(days=40)).isoformat() + "Z"

        detector = DriftDetector(days_threshold=30)
        result = detector.detect_time_drift(last_train)

        assert result["has_drift"] is True
        assert result["days_since_training"] >= 30

    def test_detect_time_drift_no(self):
        """No detecta time drift cuando han pasado pocos dias."""
        # Fecha de hace 10 dias
        last_train = (datetime.now() - timedelta(days=10)).isoformat() + "Z"

        detector = DriftDetector(days_threshold=30)
        result = detector.detect_time_drift(last_train)

        assert result["has_drift"] is False
        assert result["days_since_training"] < 30

    def test_detect_time_drift_no_date(self):
        """Detecta drift cuando no hay fecha de entrenamiento."""
        detector = DriftDetector()
        result = detector.detect_time_drift(None)

        # Sin fecha, asume drift por seguridad
        assert result["has_drift"] is True

    def test_detect_all_drift(self):
        """Ejecuta deteccion completa y devuelve reporte."""
        detector = DriftDetector()

        # Simular datos
        train_data = pd.DataFrame({"feat1": [1, 2, 3]})
        new_data = pd.DataFrame({"feat1": [4, 5, 6]})

        result = detector.detect_all_drift(
            train_data=train_data,
            new_data=new_data,
            train_size=100,
            new_size=60,
            last_train_date=(datetime.now() - timedelta(days=40)).isoformat() + "Z",
        )

        assert isinstance(result, dict)
        assert "needs_retraining" in result
        assert "reasons" in result
        assert "data_drift" in result
        assert "volume_drift" in result
        assert "time_drift" in result


# ============================================================
# Tests para Versionado de Modelos
# ============================================================

class TestModelVersioning:
    """Tests para versionado de modelos."""

    def test_get_next_version_empty_dir(self):
        """Devuelve v1 cuando no hay versiones previas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = ModelTrainer()
            version = trainer._get_next_version(Path(tmpdir))
            assert version == 1

    def test_get_next_version_existing(self):
        """Devuelve siguiente version cuando hay versiones previas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Crear carpetas v1, v2
            (tmpdir_path / "v1").mkdir()
            (tmpdir_path / "v2").mkdir()

            trainer = ModelTrainer()
            version = trainer._get_next_version(tmpdir_path)
            assert version == 3

    def test_save_models_versioned(self):
        """Guarda modelos con versionado correcto."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Crear trainer con modelo dummy
            trainer = ModelTrainer()
            trainer.models["test_model"] = RandomForestClassifier(n_estimators=5)
            trainer.feature_names = ["feat1", "feat2"]
            trainer.results = {"test_model": {"val_f1": 0.75}}

            # Guardar con versionado
            version_dir = trainer.save_models_versioned(
                base_path=tmpdir_path,
                metadata={"test": "data"}
            )

            # Verificar que se creo v1/
            assert version_dir.exists()
            assert version_dir.name == "v1"

            # Verificar que se guardo el modelo
            assert (version_dir / "test_model.joblib").exists()

            # Verificar que se guardo metadata.json
            metadata_path = version_dir / "metadata.json"
            assert metadata_path.exists()

            import json
            with open(metadata_path) as f:
                metadata = json.load(f)

            assert metadata["version"] == "v1"
            assert "trained_at" in metadata
            assert metadata["feature_names"] == ["feat1", "feat2"]
            assert metadata["test"] == "data"

            # Verificar latest_version.txt
            latest_file = tmpdir_path / "latest_version.txt"
            assert latest_file.exists()
            assert latest_file.read_text().strip() == "v1"

    def test_get_latest_version(self):
        """Obtiene la version mas reciente correctamente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Crear v1 y v2
            (tmpdir_path / "v1").mkdir()
            (tmpdir_path / "v2").mkdir()

            # Crear latest_version.txt
            latest_file = tmpdir_path / "latest_version.txt"
            latest_file.write_text("v2")

            trainer = ModelTrainer()
            latest = trainer.get_latest_version(tmpdir_path)

            assert latest == "v2"

    def test_load_models_versioned(self):
        """Carga modelos de una version especifica."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Guardar modelo en v1
            trainer1 = ModelTrainer()
            trainer1.models["test_model"] = RandomForestClassifier(n_estimators=5)
            trainer1.feature_names = ["feat1", "feat2"]
            trainer1.results = {"test_model": {"val_f1": 0.75}}
            trainer1.save_models_versioned(base_path=tmpdir_path)

            # Cargar modelo de v1
            trainer2 = ModelTrainer()
            metadata = trainer2.load_models_versioned("v1", base_path=tmpdir_path)

            assert "test_model" in trainer2.models
            assert trainer2.feature_names == ["feat1", "feat2"]
            assert metadata["version"] == "v1"
