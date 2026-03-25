"""
test_drift_detection.py - Tests para los metodos nuevos del DriftDetector.

Cubre:
- detect_feature_drift() — comparacion de medianas entre train y actual
- generate_report() — reporte completo ligero (time + volume + feature)
- load_from_local() — carga de artefactos desde disco
- save_drift_report() — persistencia en SupabaseStorage

Ejecutar con: pytest tests/test_drift_detection.py -v
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.drift_detector import DriftDetector


# ============================================================
# TestDetectFeatureDrift (metodo estatico)
# ============================================================

class TestDetectFeatureDrift:
    """Tests para DriftDetector.detect_feature_drift()."""

    def test_no_drift_all_within_threshold(self):
        """No dispara drift cuando todas las features estan dentro del umbral."""
        train = {"feat_a": 1.0, "feat_b": 2.0, "feat_c": 3.0}
        current = {"feat_a": 1.1, "feat_b": 2.2, "feat_c": 3.1}

        result = DriftDetector.detect_feature_drift(train, current)

        assert result["triggered"] is False
        assert result["total_features"] == 3
        assert result["drifted_count"] == 0
        assert result["drifted_ratio"] == 0.0
        assert result["details"] == {}

    def test_drift_detected_above_ratio(self):
        """Dispara drift cuando >20% de features tienen shift >50%."""
        # 3 de 5 features (60%) con shift grande → triggered=True
        train = {
            "f1": 1.0, "f2": 2.0, "f3": 3.0, "f4": 4.0, "f5": 5.0,
        }
        current = {
            "f1": 2.0,   # shift 100% → drift
            "f2": 4.0,   # shift 100% → drift
            "f3": 6.0,   # shift 100% → drift
            "f4": 4.1,   # shift 2.5% → ok
            "f5": 5.2,   # shift 4% → ok
        }

        result = DriftDetector.detect_feature_drift(train, current)

        assert result["triggered"] is True
        assert result["drifted_count"] == 3
        assert result["total_features"] == 5
        assert result["drifted_ratio"] == 0.6
        # Solo features con drift aparecen en details
        assert "f1" in result["details"]
        assert "f2" in result["details"]
        assert "f3" in result["details"]
        assert "f4" not in result["details"]
        assert "f5" not in result["details"]

    def test_train_median_zero_uses_epsilon(self):
        """Cuando la mediana de train es 0, usa epsilon (1e-6) como denominador."""
        train = {"feat_zero": 0.0, "feat_normal": 10.0}
        current = {"feat_zero": 0.001, "feat_normal": 10.5}

        result = DriftDetector.detect_feature_drift(train, current)

        # feat_zero: abs(0.001 - 0) / max(0, 1e-6) = 0.001/1e-6 = 1000 → drift
        # feat_normal: abs(10.5 - 10) / 10 = 0.05 → no drift
        assert result["drifted_count"] == 1
        assert "feat_zero" in result["details"]
        assert result["details"]["feat_zero"]["shift_pct"] > 0.5

    def test_empty_medians_dict(self):
        """Medianas vacias devuelven triggered=False con todo a cero."""
        result = DriftDetector.detect_feature_drift({}, {})

        assert result["triggered"] is False
        assert result["total_features"] == 0
        assert result["drifted_count"] == 0
        assert result["drifted_ratio"] == 0.0
        assert result["details"] == {}

    def test_only_drifted_in_details(self):
        """El dict details contiene SOLO features con drift, no todas."""
        train = {"a": 1.0, "b": 1.0, "c": 1.0, "d": 1.0, "e": 1.0}
        current = {"a": 1.0, "b": 1.0, "c": 1.0, "d": 1.0, "e": 5.0}

        result = DriftDetector.detect_feature_drift(train, current)

        # Solo 'e' tiene shift (400%) → 1/5 = 20%, no > 20% → triggered=False
        assert result["triggered"] is False
        assert result["drifted_count"] == 1
        assert len(result["details"]) == 1
        assert "e" in result["details"]
        # Verificar estructura del detail
        detail = result["details"]["e"]
        assert detail["train"] == 1.0
        assert detail["current"] == 5.0
        assert detail["shift_pct"] == 4.0

    def test_no_common_features(self):
        """Sin features en comun devuelve triggered=False."""
        train = {"feat_x": 1.0}
        current = {"feat_y": 2.0}

        result = DriftDetector.detect_feature_drift(train, current)

        assert result["triggered"] is False
        assert result["total_features"] == 0

    def test_exact_ratio_boundary(self):
        """Cuando drifted_ratio == min_drifted_ratio (exacto), NO dispara (es >)."""
        # 1 de 5 = 0.20 → no es > 0.20
        train = {"a": 1.0, "b": 1.0, "c": 1.0, "d": 1.0, "e": 1.0}
        current = {"a": 10.0, "b": 1.0, "c": 1.0, "d": 1.0, "e": 1.0}

        result = DriftDetector.detect_feature_drift(
            train, current, min_drifted_ratio=0.20,
        )

        # 1/5 = 0.20, y triggered requiere > 0.20
        assert result["triggered"] is False

    def test_custom_thresholds(self):
        """Umbrales personalizados cambian el resultado."""
        train = {"a": 1.0, "b": 2.0}
        current = {"a": 1.3, "b": 2.6}  # 30% shift cada una

        # Con threshold 25% → ambas drifted (2/2 = 100% > 20%) → triggered
        result = DriftDetector.detect_feature_drift(
            train, current, threshold_pct=0.25, min_drifted_ratio=0.10,
        )
        assert result["triggered"] is True
        assert result["drifted_count"] == 2

        # Con threshold 50% → ninguna drifted → not triggered
        result2 = DriftDetector.detect_feature_drift(
            train, current, threshold_pct=0.50, min_drifted_ratio=0.10,
        )
        assert result2["triggered"] is False
        assert result2["drifted_count"] == 0


# ============================================================
# TestGenerateReport (classmethod)
# ============================================================

class TestGenerateReport:
    """Tests para DriftDetector.generate_report()."""

    def _mock_storage_with_labels(self, total_labels):
        """Helper: crea mock de get_storage() que devuelve N labels."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = [{"cnt": total_labels}]
        return mock_storage

    def test_happy_path_all_fields_present(self):
        """Genera reporte con todos los campos esperados."""
        metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_size": 1000,
        }
        train_medians = {"f1": 1.0, "f2": 2.0}
        current_medians = {"f1": 1.0, "f2": 2.0}

        mock_storage = self._mock_storage_with_labels(1000)

        with patch(
            "src.data.supabase_storage.get_storage", return_value=mock_storage,
        ):
            report = DriftDetector.generate_report(
                "v12", metadata, train_medians, current_medians,
            )

        # Verificar todos los campos del reporte
        expected_keys = {
            "model_version", "needs_retraining", "reasons",
            "time_drift_days", "time_drift_triggered",
            "volume_drift_new_labels", "volume_drift_triggered",
            "feature_drift_count", "feature_drift_total",
            "feature_drift_triggered", "feature_drift_details",
            "overall_score", "report_json",
        }
        assert expected_keys.issubset(set(report.keys()))
        assert report["model_version"] == "v12"

    def test_time_drift_triggered(self):
        """Time drift se dispara cuando han pasado >30 dias."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        metadata = {"trained_at": old_date, "train_size": 1000}
        train_m = {"f1": 1.0}
        current_m = {"f1": 1.0}

        mock_storage = self._mock_storage_with_labels(1000)

        with patch(
            "src.data.supabase_storage.get_storage", return_value=mock_storage,
        ):
            report = DriftDetector.generate_report(
                "v12", metadata, train_m, current_m,
            )

        assert report["time_drift_triggered"] is True
        assert "time_drift" in report["reasons"]
        assert report["time_drift_days"] >= 45

    def test_volume_drift_triggered(self):
        """Volume drift se dispara cuando hay >50 labels nuevos."""
        metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_size": 1000,
        }
        train_m = {"f1": 1.0}
        current_m = {"f1": 1.0}

        # 1100 labels totales - 1000 train = 100 nuevos > 50
        mock_storage = self._mock_storage_with_labels(1100)

        with patch(
            "src.data.supabase_storage.get_storage", return_value=mock_storage,
        ):
            report = DriftDetector.generate_report(
                "v12", metadata, train_m, current_m,
            )

        assert report["volume_drift_triggered"] is True
        assert "volume_drift" in report["reasons"]
        assert report["volume_drift_new_labels"] == 100

    def test_feature_drift_triggered(self):
        """Feature drift se dispara cuando suficientes features cambian."""
        metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_size": 1000,
        }
        # 3/4 features con shift >50% (75% > 20%) → triggered
        train_m = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0}
        current_m = {"a": 5.0, "b": 10.0, "c": 15.0, "d": 4.1}

        mock_storage = self._mock_storage_with_labels(1000)

        with patch(
            "src.data.supabase_storage.get_storage", return_value=mock_storage,
        ):
            report = DriftDetector.generate_report(
                "v12", metadata, train_m, current_m,
            )

        assert report["feature_drift_triggered"] is True
        assert "feature_drift" in report["reasons"]
        assert report["feature_drift_count"] == 3

    def test_no_drift_at_all(self):
        """Sin drift → needs_retraining=False y reasons vacio."""
        metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_size": 1000,
        }
        train_m = {"f1": 1.0, "f2": 2.0}
        current_m = {"f1": 1.0, "f2": 2.0}

        # Sin labels nuevos
        mock_storage = self._mock_storage_with_labels(1000)

        with patch(
            "src.data.supabase_storage.get_storage", return_value=mock_storage,
        ):
            report = DriftDetector.generate_report(
                "v12", metadata, train_m, current_m,
            )

        assert report["needs_retraining"] is False
        assert report["reasons"] == []
        assert report["time_drift_triggered"] is False
        assert report["volume_drift_triggered"] is False
        assert report["feature_drift_triggered"] is False

    def test_overall_score_calculation(self):
        """Verifica calculo de overall_score ponderado (0.3/0.3/0.4)."""
        # Forzar: time NO triggered (10 dias de 30 → time_score = 10/30 ≈ 0.333)
        # volume NO triggered (25 de 50 → volume_score = 25/50 = 0.5)
        # feature drift_ratio = 0.0 → feature_score = 0.0
        trained_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        metadata = {"trained_at": trained_at, "train_size": 1000}
        train_m = {"f1": 1.0}
        current_m = {"f1": 1.0}

        # 1025 - 1000 = 25 nuevos labels (no triggered, < 50)
        mock_storage = self._mock_storage_with_labels(1025)

        with patch(
            "src.data.supabase_storage.get_storage", return_value=mock_storage,
        ):
            report = DriftDetector.generate_report(
                "v12", metadata, train_m, current_m,
            )

        # time_score = min(10/30, 1.0) ≈ 0.3333
        # volume_score = min(25/50, 1.0) = 0.5
        # feature_score = 0.0
        # overall = 0.3*0.3333 + 0.3*0.5 + 0.4*0.0 = 0.1 + 0.15 + 0 = 0.25
        # Puede variar ligeramente por dias exactos, asi que usamos approx
        assert report["needs_retraining"] is False
        assert 0.1 <= report["overall_score"] <= 0.5

    def test_storage_query_failure_graceful(self):
        """Si get_storage() falla, asume sin labels nuevos y continua."""
        metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_size": 1000,
        }
        train_m = {"f1": 1.0}
        current_m = {"f1": 1.0}

        mock_storage = MagicMock()
        mock_storage.query.side_effect = Exception("DB no disponible")

        with patch(
            "src.data.supabase_storage.get_storage", return_value=mock_storage,
        ):
            report = DriftDetector.generate_report(
                "v12", metadata, train_m, current_m,
            )

        # No debe lanzar excepcion, volume_drift_new_labels = 0
        assert report["volume_drift_new_labels"] == 0
        assert report["volume_drift_triggered"] is False

    def test_report_json_contains_sub_reports(self):
        """report_json incluye time_drift, volume_drift, feature_drift."""
        metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_size": 1000,
        }
        mock_storage = self._mock_storage_with_labels(1000)

        with patch(
            "src.data.supabase_storage.get_storage", return_value=mock_storage,
        ):
            report = DriftDetector.generate_report(
                "v12", metadata, {"f1": 1.0}, {"f1": 1.0},
            )

        rj = report["report_json"]
        assert "time_drift" in rj
        assert "volume_drift" in rj
        assert "feature_drift" in rj

    def test_feature_drift_details_limited_to_top_10(self):
        """feature_drift_details solo incluye top 10 features por shift."""
        metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_size": 1000,
        }
        # 15 features todas con shift >50%
        train_m = {f"f{i}": 1.0 for i in range(15)}
        current_m = {f"f{i}": 10.0 + i for i in range(15)}

        mock_storage = self._mock_storage_with_labels(1000)

        with patch(
            "src.data.supabase_storage.get_storage", return_value=mock_storage,
        ):
            report = DriftDetector.generate_report(
                "v12", metadata, train_m, current_m,
            )

        # Top 10 solamente
        assert len(report["feature_drift_details"]) <= 10


# ============================================================
# TestLoadFromLocal (metodo estatico)
# ============================================================

class TestLoadFromLocal:
    """Tests para DriftDetector.load_from_local()."""

    def test_happy_path_loads_both_files(self, tmp_path):
        """Carga metadata.json y train_medians.json correctamente."""
        # Preparar estructura: tmp_path/v12/metadata.json, train_medians.json
        version_dir = tmp_path / "v12"
        version_dir.mkdir()

        metadata = {"trained_at": "2026-03-15T10:00:00Z", "train_size": 1200}
        medians = {"feat_a": 0.5, "feat_b": 1.0, "feat_c": 3.14}

        (version_dir / "metadata.json").write_text(json.dumps(metadata))
        (version_dir / "train_medians.json").write_text(json.dumps(medians))

        with patch("config.MODELS_DIR", tmp_path):
            meta, meds = DriftDetector.load_from_local("v12")

        assert meta["trained_at"] == "2026-03-15T10:00:00Z"
        assert meta["train_size"] == 1200
        assert meds["feat_a"] == 0.5
        assert len(meds) == 3

    def test_version_auto_detection(self, tmp_path):
        """Detecta version desde latest_version.txt cuando no se especifica."""
        # Crear latest_version.txt
        (tmp_path / "latest_version.txt").write_text("v12")

        version_dir = tmp_path / "v12"
        version_dir.mkdir()
        (version_dir / "metadata.json").write_text(
            json.dumps({"trained_at": "2026-03-15", "train_size": 500})
        )
        (version_dir / "train_medians.json").write_text(
            json.dumps({"f1": 1.0})
        )

        with patch("config.MODELS_DIR", tmp_path):
            meta, meds = DriftDetector.load_from_local()  # sin version

        assert meta["train_size"] == 500
        assert meds["f1"] == 1.0

    def test_metadata_not_found_raises(self, tmp_path):
        """FileNotFoundError si metadata.json no existe."""
        version_dir = tmp_path / "v12"
        version_dir.mkdir()
        # No crear metadata.json

        with patch("config.MODELS_DIR", tmp_path):
            with pytest.raises(FileNotFoundError, match="metadata.json"):
                DriftDetector.load_from_local("v12")

    def test_medians_not_found_raises(self, tmp_path):
        """FileNotFoundError si train_medians.json no existe."""
        version_dir = tmp_path / "v12"
        version_dir.mkdir()
        (version_dir / "metadata.json").write_text(json.dumps({"x": 1}))
        # No crear train_medians.json

        with patch("config.MODELS_DIR", tmp_path):
            with pytest.raises(FileNotFoundError, match="train_medians.json"):
                DriftDetector.load_from_local("v12")

    def test_latest_version_not_found_raises(self, tmp_path):
        """FileNotFoundError si latest_version.txt no existe y no se da version."""
        with patch("config.MODELS_DIR", tmp_path):
            with pytest.raises(FileNotFoundError, match="latest_version.txt"):
                DriftDetector.load_from_local()  # sin version, sin archivo


# ============================================================
# TestSaveDriftReport (SupabaseStorage)
# ============================================================

class TestSaveDriftReport:
    """Tests para SupabaseStorage.save_drift_report()."""

    def _make_mock_storage(self):
        """Helper: crea SupabaseStorage con cliente mock."""
        from src.data.supabase_storage import SupabaseStorage

        mock_client = MagicMock()
        # Mock para verificacion de conexion en __init__
        mock_resp = MagicMock()
        mock_resp.count = 100
        mock_client.table.return_value.select.return_value.execute.return_value = mock_resp

        storage = SupabaseStorage.__new__(SupabaseStorage)
        storage._client = mock_client
        return storage

    def test_happy_path_saves_report(self):
        """Guarda reporte con todos los campos correctamente."""
        storage = self._make_mock_storage()

        report = {
            "model_version": "v12",
            "needs_retraining": True,
            "reasons": ["time_drift", "feature_drift"],
            "time_drift_days": 45,
            "time_drift_triggered": True,
            "volume_drift_new_labels": 30,
            "volume_drift_triggered": False,
            "feature_drift_count": 5,
            "feature_drift_total": 20,
            "feature_drift_triggered": True,
            "feature_drift_details": {"f1": {"shift_pct": 1.5}},
            "overall_score": 0.72,
            "report_json": {"time_drift": {}, "volume_drift": {}},
        }

        # Mockear insert para que funcione
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = MagicMock()
        storage._client.table.return_value = mock_table

        storage.save_drift_report(report)

        # Verificar que se llamo insert con los datos correctos
        mock_table.insert.assert_called_once()
        inserted_row = mock_table.insert.call_args[0][0]
        assert inserted_row["model_version"] == "v12"
        assert inserted_row["needs_retraining"] is True
        assert inserted_row["overall_score"] == 0.72

    def test_missing_model_version_does_not_save(self):
        """Si falta model_version, no intenta guardar."""
        storage = self._make_mock_storage()

        report = {
            "needs_retraining": True,
            "reasons": ["time_drift"],
        }

        # Resetear mock para verificar que NO se llama insert
        mock_table = MagicMock()
        storage._client.table.return_value = mock_table

        storage.save_drift_report(report)

        # No debe llamar insert
        mock_table.insert.assert_not_called()

    def test_defaults_for_missing_fields(self):
        """Campos opcionales usan valores por defecto correctos."""
        storage = self._make_mock_storage()

        # Reporte minimo: solo model_version
        report = {"model_version": "v12"}

        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = MagicMock()
        storage._client.table.return_value = mock_table

        storage.save_drift_report(report)

        mock_table.insert.assert_called_once()
        inserted_row = mock_table.insert.call_args[0][0]
        assert inserted_row["model_version"] == "v12"
        assert inserted_row["needs_retraining"] is False
        assert inserted_row["reasons"] == []
        assert inserted_row["overall_score"] == 0.0

    def test_get_drift_reports_filters_by_version(self):
        """get_drift_reports filtra por model_version correctamente."""
        storage = self._make_mock_storage()

        mock_query = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [
            {"model_version": "v12", "needs_retraining": True},
        ]
        mock_query.select.return_value.order.return_value.limit.return_value.eq.return_value.execute.return_value = mock_resp
        storage._client.table.return_value = mock_query

        df = storage.get_drift_reports(model_version="v12", limit=10)

        assert isinstance(df, pd.DataFrame)
        # Verificar que se llamo eq con model_version
        mock_query.select.return_value.order.return_value.limit.return_value.eq.assert_called_once_with(
            "model_version", "v12"
        )
