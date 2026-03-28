"""
test_scoring_pipeline.py - Tests para el pipeline de scoring completo.

Cubre:
- SupabaseStorage.upsert_scores() y get_scores()
- GemScorer.score_and_save() y _get_model_version()
- scripts/score_tokens.py main()

Usa mocks para Supabase API (nunca toca la API real en tests).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

# Asegurar imports del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.scorer import GemScorer, SIGNAL_THRESHOLDS


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def mock_supabase_client():
    """Cliente de Supabase mockeado para tests sin API real."""
    client = MagicMock()

    # Mock para verificacion de conexion en __init__
    mock_resp = MagicMock()
    mock_resp.count = 100
    client.table.return_value.select.return_value.execute.return_value = mock_resp

    return client


@pytest.fixture
def mock_storage(mock_supabase_client):
    """SupabaseStorage con cliente mockeado."""
    from src.data.supabase_storage import SupabaseStorage
    storage = SupabaseStorage(client=mock_supabase_client)
    return storage


@pytest.fixture
def sample_scores():
    """Lista de scores validos para tests."""
    return [
        {
            "token_id": "tok_alpha",
            "probability": 0.92,
            "signal": "STRONG",
            "prediction": 1,
            "model_name": "random_forest",
            "model_version": "v12",
        },
        {
            "token_id": "tok_beta",
            "probability": 0.71,
            "signal": "MEDIUM",
            "prediction": 1,
            "model_name": "random_forest",
            "model_version": "v12",
        },
        {
            "token_id": "tok_gamma",
            "probability": 0.35,
            "signal": "NONE",
            "prediction": 0,
            "model_name": "random_forest",
            "model_version": "v12",
        },
    ]


@pytest.fixture
def scorer_with_mocks(tmp_path, mock_storage):
    """
    GemScorer con modelo falso en disco y storage mockeado.

    Crea un mini RandomForest entrenado, lo guarda en tmp_path,
    y construye un GemScorer que usa mock_storage en lugar de Supabase real.
    """
    import joblib
    from sklearn.datasets import make_classification

    # Entrenar mini-modelo
    X, y = make_classification(n_samples=100, n_features=5, random_state=42)
    feature_names = [f"feat_{i}" for i in range(5)]
    rf = RandomForestClassifier(n_estimators=5, random_state=42)
    rf.fit(X, y)

    # Guardar modelo y feature_columns
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    joblib.dump(rf, models_dir / "random_forest.joblib")

    with open(models_dir / "feature_columns.json", "w") as f:
        json.dump(feature_names, f)

    # Crear scorer con storage mockeado
    scorer = GemScorer(
        storage=mock_storage,
        model_name="random_forest",
        models_dir=models_dir,
    )
    return scorer


# ============================================================
# TESTS: SupabaseStorage.upsert_scores()
# ============================================================

class TestUpsertScores:
    """Tests para SupabaseStorage.upsert_scores()."""

    def test_happy_path_upserts_scores(self, mock_storage, sample_scores,
                                       mock_supabase_client):
        """Upsert de lista de scores validos llama a la tabla correcta."""
        mock_storage.upsert_scores(sample_scores)

        # Verificar que se llamo a table("scores").upsert(...)
        mock_supabase_client.table.assert_called_with("scores")
        upsert_call = (
            mock_supabase_client.table.return_value.upsert
        )
        assert upsert_call.called

        # Verificar que se paso on_conflict="token_id"
        call_kwargs = upsert_call.call_args
        assert call_kwargs[1].get("on_conflict") == "token_id"

    def test_empty_list_no_upsert(self, mock_storage, mock_supabase_client):
        """Lista vacia no genera llamadas a la API."""
        # Resetear mocks para contar llamadas limpias
        mock_supabase_client.reset_mock()

        # Mockear verificacion de conexion de nuevo (se reseteo)
        mock_resp = MagicMock()
        mock_resp.count = 0
        mock_supabase_client.table.return_value.select.return_value.execute.return_value = mock_resp

        mock_storage.upsert_scores([])

        # No deberia haber llamado a upsert
        upsert_mock = mock_supabase_client.table.return_value.upsert
        assert not upsert_mock.called

    def test_skips_scores_without_token_id(self, mock_storage, mock_supabase_client):
        """Scores sin token_id se descartan silenciosamente."""
        scores_con_invalido = [
            {
                # Falta token_id
                "probability": 0.5,
                "signal": "WEAK",
                "prediction": 1,
                "model_name": "random_forest",
                "model_version": "v12",
            },
            {
                "token_id": "",  # token_id vacio tambien es invalido
                "probability": 0.5,
                "signal": "WEAK",
                "prediction": 1,
                "model_name": "random_forest",
                "model_version": "v12",
            },
        ]
        # No debe hacer upsert porque ningun score tiene token_id valido
        mock_supabase_client.reset_mock()
        mock_storage.upsert_scores(scores_con_invalido)

        upsert_mock = mock_supabase_client.table.return_value.upsert
        assert not upsert_mock.called

    def test_normalizes_fields(self, mock_storage, mock_supabase_client):
        """Campos se normalizan: probability->float, prediction->int, defaults."""
        scores = [{
            "token_id": "tok_normalize",
            "probability": "0.75",  # string, debe convertirse a float
            "prediction": "1",      # string, debe convertirse a int
            # signal, model_name, model_version no incluidos -> defaults
        }]
        mock_storage.upsert_scores(scores)

        upsert_call = mock_supabase_client.table.return_value.upsert
        assert upsert_call.called
        # Verificar que se envio el batch con tipos correctos
        batch = upsert_call.call_args[0][0]
        assert isinstance(batch[0]["probability"], float)
        assert isinstance(batch[0]["prediction"], int)
        assert batch[0]["signal"] == "NONE"  # default
        assert batch[0]["model_name"] == "random_forest"  # default
        assert batch[0]["model_version"] == "unknown"  # default

    def test_includes_scored_at_when_provided(self, mock_storage, mock_supabase_client):
        """scored_at se incluye en el row si se proporciona."""
        ts = "2026-03-25T10:00:00+00:00"
        scores = [{
            "token_id": "tok_with_ts",
            "probability": 0.8,
            "signal": "STRONG",
            "prediction": 1,
            "model_name": "random_forest",
            "model_version": "v12",
            "scored_at": ts,
        }]
        mock_storage.upsert_scores(scores)

        batch = (
            mock_supabase_client.table.return_value.upsert.call_args[0][0]
        )
        assert batch[0]["scored_at"] == ts

    def test_omits_scored_at_when_not_provided(self, mock_storage,
                                                mock_supabase_client):
        """Sin scored_at, el campo no se envia (Supabase usa DEFAULT NOW())."""
        scores = [{
            "token_id": "tok_no_ts",
            "probability": 0.6,
            "signal": "WEAK",
            "prediction": 1,
            "model_name": "random_forest",
            "model_version": "v12",
        }]
        mock_storage.upsert_scores(scores)

        batch = (
            mock_supabase_client.table.return_value.upsert.call_args[0][0]
        )
        assert "scored_at" not in batch[0]


# ============================================================
# TESTS: SupabaseStorage.get_scores()
# ============================================================

class TestGetScores:
    """Tests para SupabaseStorage.get_scores()."""

    def test_query_with_min_probability(self, mock_storage):
        """Filtra scores por probabilidad minima."""
        # Mockear _rpc_query para devolver datos simulados
        fake_data = [
            {"token_id": "tok1", "probability": 0.9, "signal": "STRONG",
             "name": "Alpha", "symbol": "ALP", "chain": "solana",
             "pool_address": "pool1"},
            {"token_id": "tok2", "probability": 0.7, "signal": "MEDIUM",
             "name": "Beta", "symbol": "BET", "chain": "ethereum",
             "pool_address": "pool2"},
        ]
        with patch.object(mock_storage, "_rpc_query", return_value=fake_data):
            df = mock_storage.get_scores(min_probability=0.65)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_query_with_scored_today(self, mock_storage):
        """scored_today=True agrega filtro de fecha en el SQL."""
        with patch.object(mock_storage, "_rpc_query", return_value=[]) as rpc_mock:
            mock_storage.get_scores(scored_today=True)

        # Verificar que el SQL incluye el filtro de fecha
        sql_arg = rpc_mock.call_args[0][0]
        assert "CURRENT_DATE" in sql_arg
        assert "scored_at::date" in sql_arg

    def test_query_without_scored_today(self, mock_storage):
        """scored_today=False NO agrega filtro de fecha."""
        with patch.object(mock_storage, "_rpc_query", return_value=[]) as rpc_mock:
            mock_storage.get_scores(scored_today=False)

        sql_arg = rpc_mock.call_args[0][0]
        assert "CURRENT_DATE" not in sql_arg

    def test_empty_results_returns_empty_df(self, mock_storage):
        """Sin resultados devuelve DataFrame vacio."""
        with patch.object(mock_storage, "_rpc_query", return_value=[]):
            df = mock_storage.get_scores(min_probability=0.99)

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_min_probability_in_sql(self, mock_storage):
        """El valor de min_probability se inyecta correctamente en el SQL."""
        with patch.object(mock_storage, "_rpc_query", return_value=[]) as rpc_mock:
            mock_storage.get_scores(min_probability=0.75)

        sql_arg = rpc_mock.call_args[0][0]
        assert "0.75" in sql_arg

    def test_results_ordered_by_probability_desc(self, mock_storage):
        """El SQL ordena por probabilidad descendente."""
        with patch.object(mock_storage, "_rpc_query", return_value=[]) as rpc_mock:
            mock_storage.get_scores()

        sql_arg = rpc_mock.call_args[0][0]
        assert "ORDER BY s.probability DESC" in sql_arg


# ============================================================
# TESTS: GemScorer._get_model_version()
# ============================================================

class TestGetModelVersion:
    """Tests para GemScorer._get_model_version()."""

    def test_reads_version_from_file(self, scorer_with_mocks, tmp_path):
        """Lee la version del modelo desde latest_version.txt."""
        # Crear el archivo de version
        models_dir = tmp_path / "models"
        latest_file = models_dir / "latest_version.txt"
        latest_file.write_text("v12\n")

        version = scorer_with_mocks._get_model_version()
        assert version == "v12"

    def test_returns_unknown_when_file_missing(self, scorer_with_mocks):
        """Si latest_version.txt no existe, retorna 'unknown'."""
        # No creamos el archivo, asi que no existe
        version = scorer_with_mocks._get_model_version()
        assert version == "unknown"

    def test_strips_whitespace(self, scorer_with_mocks, tmp_path):
        """Strip de espacios y newlines en el archivo de version."""
        models_dir = tmp_path / "models"
        latest_file = models_dir / "latest_version.txt"
        latest_file.write_text("  v15  \n\n")

        version = scorer_with_mocks._get_model_version()
        assert version == "v15"


# ============================================================
# TESTS: GemScorer.score_and_save()
# ============================================================

class TestScoreAndSave:
    """Tests para GemScorer.score_and_save() (batch con features de BD)."""

    def _make_features_df(self, token_ids, n_features=5):
        """Helper: crea un DataFrame de features simulado (como get_features_df)."""
        data = {"token_id": token_ids}
        for i in range(n_features):
            data[f"feat_{i}"] = [0.5 + i * 0.1] * len(token_ids)
        return pd.DataFrame(data)

    def test_happy_path_scores_and_saves(self, scorer_with_mocks, mock_storage):
        """Califica tokens en batch y guarda scores en Supabase."""
        # Simular tokens sin score
        tokens_df = pd.DataFrame({
            "token_id": ["tok_1", "tok_2"],
            "chain": ["solana", "ethereum"],
            "symbol": ["AAA", "BBB"],
        })
        features_df = self._make_features_df(["tok_1", "tok_2"])

        mock_storage.query = MagicMock(return_value=tokens_df)
        mock_storage.get_features_df = MagicMock(return_value=features_df)
        mock_storage.upsert_scores = MagicMock()

        with patch.object(
            scorer_with_mocks, "_get_model_version", return_value="v12"
        ):
            df = scorer_with_mocks.score_and_save()

        # Verificar que retorna DataFrame con resultados
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

        # Verificar que se llamo a upsert_scores
        mock_storage.upsert_scores.assert_called_once()
        upsert_arg = mock_storage.upsert_scores.call_args[0][0]
        assert len(upsert_arg) == 2
        # Verificar que cada score tiene model_name y model_version
        assert all(s["model_name"] == "random_forest" for s in upsert_arg)
        assert all(s["model_version"] == "v12" for s in upsert_arg)

        # Verificar que NO se llamo a score_token (batch, no loop)
        # score_and_save ya no usa score_token internamente

    def test_no_unscored_tokens_returns_empty(self, scorer_with_mocks,
                                               mock_storage):
        """Sin tokens nuevos para calificar, retorna DataFrame vacio."""
        # Simular consulta que retorna vacio
        mock_storage.query = MagicMock(return_value=pd.DataFrame())
        mock_storage.upsert_scores = MagicMock()

        with patch.object(
            scorer_with_mocks, "_get_model_version", return_value="v12"
        ):
            df = scorer_with_mocks.score_and_save()

        assert isinstance(df, pd.DataFrame)
        assert df.empty

        # No deberia haber intentado upsert
        mock_storage.upsert_scores.assert_not_called()

    def test_empty_features_returns_empty(self, scorer_with_mocks,
                                           mock_storage):
        """Si no hay features en BD, retorna DataFrame vacio."""
        tokens_df = pd.DataFrame({
            "token_id": ["tok_1"],
            "chain": ["solana"],
            "symbol": ["AAA"],
        })
        mock_storage.query = MagicMock(return_value=tokens_df)
        mock_storage.get_features_df = MagicMock(return_value=pd.DataFrame())
        mock_storage.upsert_scores = MagicMock()

        with patch.object(
            scorer_with_mocks, "_get_model_version", return_value="v12"
        ):
            df = scorer_with_mocks.score_and_save()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        mock_storage.upsert_scores.assert_not_called()

    def test_upsert_failure_raises(self, scorer_with_mocks, mock_storage):
        """Si upsert_scores falla, se propaga la excepcion."""
        tokens_df = pd.DataFrame({
            "token_id": ["tok_1"],
            "chain": ["solana"],
            "symbol": ["AAA"],
        })
        features_df = self._make_features_df(["tok_1"])

        mock_storage.query = MagicMock(return_value=tokens_df)
        mock_storage.get_features_df = MagicMock(return_value=features_df)
        mock_storage.upsert_scores = MagicMock(
            side_effect=Exception("Error de conexion Supabase")
        )

        with patch.object(
            scorer_with_mocks, "_get_model_version", return_value="v12"
        ):
            with pytest.raises(Exception, match="Error de conexion Supabase"):
                scorer_with_mocks.score_and_save()

    def test_results_sorted_by_probability(self, scorer_with_mocks,
                                            mock_storage):
        """El DataFrame resultante esta ordenado por probabilidad descendente."""
        tokens_df = pd.DataFrame({
            "token_id": ["tok_low", "tok_high", "tok_mid"],
            "chain": ["solana", "solana", "solana"],
            "symbol": ["LOW", "HIGH", "MID"],
        })
        features_df = self._make_features_df(["tok_low", "tok_high", "tok_mid"])

        mock_storage.query = MagicMock(return_value=tokens_df)
        mock_storage.get_features_df = MagicMock(return_value=features_df)
        mock_storage.upsert_scores = MagicMock()

        with patch.object(
            scorer_with_mocks, "_get_model_version", return_value="v12"
        ):
            df = scorer_with_mocks.score_and_save()

        # Verificar que los resultados estan ordenados por probabilidad desc
        probs = df["probability"].tolist()
        assert probs == sorted(probs, reverse=True)

    def test_filters_only_target_tokens(self, scorer_with_mocks,
                                         mock_storage):
        """Solo califica tokens que aparecen en la query (sin score previo)."""
        # Solo tok_1 necesita score
        tokens_df = pd.DataFrame({
            "token_id": ["tok_1"],
            "chain": ["solana"],
            "symbol": ["AAA"],
        })
        # Pero la BD tiene features para tok_1 y tok_extra
        features_df = self._make_features_df(["tok_1", "tok_extra"])

        mock_storage.query = MagicMock(return_value=tokens_df)
        mock_storage.get_features_df = MagicMock(return_value=features_df)
        mock_storage.upsert_scores = MagicMock()

        with patch.object(
            scorer_with_mocks, "_get_model_version", return_value="v12"
        ):
            df = scorer_with_mocks.score_and_save()

        # Solo tok_1 debe tener score
        assert len(df) == 1
        assert df.iloc[0]["token_id"] == "tok_1"
        # tok_extra no debe estar
        assert "tok_extra" not in df["token_id"].values

    def test_batch_prediction_no_score_token_calls(self, scorer_with_mocks,
                                                     mock_storage):
        """score_and_save usa prediccion batch, no llama a score_token."""
        tokens_df = pd.DataFrame({
            "token_id": ["tok_1", "tok_2"],
            "chain": ["solana", "solana"],
            "symbol": ["A", "B"],
        })
        features_df = self._make_features_df(["tok_1", "tok_2"])

        mock_storage.query = MagicMock(return_value=tokens_df)
        mock_storage.get_features_df = MagicMock(return_value=features_df)
        mock_storage.upsert_scores = MagicMock()

        with patch.object(
            scorer_with_mocks, "score_token", wraps=scorer_with_mocks.score_token
        ) as mock_score:
            with patch.object(
                scorer_with_mocks, "_get_model_version", return_value="v12"
            ):
                scorer_with_mocks.score_and_save()

        # score_token NO debe haber sido llamado (batch prediction)
        mock_score.assert_not_called()


# ============================================================
# TESTS: GemScorer modelo no encontrado
# ============================================================

class TestScorerModelNotFound:
    """Tests para manejo de modelo no encontrado."""

    def test_init_raises_if_model_missing(self, tmp_path, mock_storage):
        """FileNotFoundError si el modelo no existe en disco."""
        models_dir = tmp_path / "empty_models"
        models_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="no encontrado"):
            GemScorer(
                storage=mock_storage,
                model_name="random_forest",
                models_dir=models_dir,
            )


# ============================================================
# TESTS: scripts/score_tokens.py main()
# ============================================================

class TestScoreTokensScript:
    """Tests para el script score_tokens.py main()."""

    def test_main_returns_0_when_model_missing(self, tmp_path):
        """Si no hay modelos descargados ni locales, retorna 0 (skip graceful)."""
        from scripts.score_tokens import main

        # Directorio vacio sin modelos
        empty_dir = tmp_path / "no_models"
        empty_dir.mkdir()

        # Parchear config.MODELS_DIR (donde score_tokens lo importa)
        # y download_all (donde score_tokens lo importa)
        with patch("config.MODELS_DIR", empty_dir):
            with patch(
                "scripts.download_models.download_all",
                return_value={"downloaded": []},
            ):
                result = main(model_name="random_forest")

        assert result == 0

    def test_main_returns_0_when_no_tokens(self, tmp_path):
        """Si no hay tokens para calificar, retorna 0."""
        import joblib
        from sklearn.datasets import make_classification
        from scripts.score_tokens import main

        # Crear modelo temporal
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        X, y = make_classification(n_samples=50, n_features=5, random_state=42)
        rf = RandomForestClassifier(n_estimators=3, random_state=42)
        rf.fit(X, y)
        joblib.dump(rf, models_dir / "random_forest.joblib")

        with open(models_dir / "feature_columns.json", "w") as f:
            json.dump([f"feat_{i}" for i in range(5)], f)

        # Mock para que GemScorer retorne scorer con score_all_new vacio
        mock_scorer_instance = MagicMock()
        mock_scorer_instance.score_all_new.return_value = pd.DataFrame()

        with patch("config.MODELS_DIR", models_dir):
            with patch(
                "src.models.scorer.GemScorer",
                return_value=mock_scorer_instance,
            ):
                result = main(model_name="random_forest")

        assert result == 0
