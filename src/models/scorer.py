"""
scorer.py - Sistema de puntuacion y senales para gem candidates.

GemScorer califica tokens con probabilidad de ser "gem" usando
los modelos entrenados. Genera senales con niveles de confianza:
  - STRONG: probabilidad >= 80%
  - MEDIUM: probabilidad >= 65%
  - WEAK: probabilidad >= 50%

Tambien proporciona explicaciones SHAP individuales para cada
prediccion, permitiendo entender POR QUE el modelo piensa que
un token puede ser un gem.

Clase:
    GemScorer: Interfaz de alto nivel para generar senales.

Uso:
    from src.models.scorer import GemScorer

    scorer = GemScorer()

    # Calificar un token individual
    result = scorer.score_token("abc123...")
    print(result["probability"], result["signal"])

    # Calificar todos los tokens nuevos
    candidates = scorer.score_all_new()
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import joblib

from src.data.supabase_storage import get_storage
from src.features.builder import FeatureBuilder
from src.utils.logger import get_logger

try:
    from config import MODELS_DIR, PROCESSED_DIR
except ImportError:
    MODELS_DIR = Path("data/models")
    PROCESSED_DIR = Path("data/processed")

logger = get_logger(__name__)

# Umbrales de senal
SIGNAL_THRESHOLDS = {
    "STRONG": 0.80,    # >= 80% probabilidad de gem
    "MEDIUM": 0.65,    # >= 65%
    "WEAK": 0.50,      # >= 50%
}


class GemScorer:
    """
    Genera puntuaciones y senales de gem para tokens.

    Carga los modelos entrenados y los usa para calificar tokens
    basandose en sus features. Opcionalmente genera explicaciones
    SHAP para cada prediccion.

    Args:
        storage: Instancia de Storage (si None, crea una nueva).
        model_name: Nombre del modelo a usar ('random_forest' por defecto).
        models_dir: Directorio de modelos (por defecto MODELS_DIR).

    Ejemplo:
        scorer = GemScorer()
        result = scorer.score_token("DireccionDelToken...")
        print(f"Probabilidad gem: {result['probability']:.1%}")
        print(f"Senal: {result['signal']}")
    """

    def __init__(
        self,
        storage=None,
        model_name: str = "random_forest",
        models_dir: Optional[Path] = None,
    ):
        self.storage = storage or get_storage()
        self.builder = FeatureBuilder(self.storage)
        self.model_name = model_name
        self._models_dir = Path(models_dir) if models_dir else MODELS_DIR

        # Cargar modelo
        self.model = self._load_model(model_name)

        # Cargar columnas de features esperadas
        self.feature_columns = self._load_feature_columns()

        # Cargar threshold optimo desde metadata del entrenamiento
        self.optimal_threshold = self._load_optimal_threshold(model_name)

        # Cargar medianas de training para imputacion consistente
        self.train_medians = self._load_train_medians()

        logger.info(
            f"GemScorer inicializado: modelo={model_name}, "
            f"features={len(self.feature_columns)}, "
            f"threshold={self.optimal_threshold:.2f}"
        )

    def _load_model(self, name: str):
        """Carga un modelo desde disco."""
        # Intentar diferentes patrones de nombre
        for suffix in ["", "_v1", "_v2"]:
            filepath = self._models_dir / f"{name}{suffix}.joblib"
            if filepath.exists():
                model = joblib.load(filepath)
                logger.info(f"Modelo cargado: {filepath}")
                return model

        raise FileNotFoundError(
            f"Modelo '{name}' no encontrado en {self._models_dir}. "
            "Ejecuta retrain.sh primero."
        )

    def _load_feature_columns(self) -> list:
        """Carga la lista de columnas de features usadas en entrenamiento."""
        # Intentar desde feature_columns.json
        import json
        fc_path = self._models_dir / "feature_columns.json"
        if fc_path.exists():
            with open(fc_path) as f:
                return json.load(f)

        # Intentar desde training_metadata.joblib
        meta_path = self._models_dir / "training_metadata.joblib"
        if meta_path.exists():
            metadata = joblib.load(meta_path)
            return metadata.get("feature_names", [])

        # Intentar desde X_train.csv
        xt_path = PROCESSED_DIR / "X_train.csv"
        if xt_path.exists():
            df = pd.read_csv(xt_path, nrows=1)
            return df.columns.tolist()

        logger.warning("No se encontraron columnas de features. Usando features del modelo.")
        return []

    def _load_optimal_threshold(self, model_name: str) -> float:
        """Carga el threshold optimo desde metadata del entrenamiento."""
        import json

        # Buscar en la version mas reciente
        latest_file = self._models_dir / "latest_version.txt"
        if latest_file.exists():
            version = latest_file.read_text().strip()
            meta_path = self._models_dir / version / "metadata.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    metadata = json.load(f)
                results = metadata.get("results", {})
                model_results = results.get(model_name, {})
                threshold = model_results.get("optimal_threshold")
                if threshold is not None:
                    logger.info(f"Threshold optimo cargado: {threshold}")
                    return float(threshold)

        # Fallback al threshold por defecto
        logger.info("Usando threshold por defecto: 0.50")
        return 0.50

    def _load_train_medians(self) -> dict:
        """Carga las medianas de training para imputacion consistente."""
        import json

        # Buscar en la version mas reciente
        latest_file = self._models_dir / "latest_version.txt"
        if latest_file.exists():
            version = latest_file.read_text().strip()
            # Intentar archivo separado primero
            medians_path = self._models_dir / version / "train_medians.json"
            if medians_path.exists():
                with open(medians_path) as f:
                    medians = json.load(f)
                logger.info(f"Medianas de training cargadas: {len(medians)} features")
                return medians

            # Fallback a metadata.json
            meta_path = self._models_dir / version / "metadata.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    metadata = json.load(f)
                medians = metadata.get("train_medians", {})
                if medians:
                    logger.info(f"Medianas de training cargadas desde metadata: {len(medians)} features")
                    return medians

        logger.info("No se encontraron medianas de training, usando fillna(0)")
        return {}

    # ============================================================
    # PREPARAR FEATURES PARA PREDICCION
    # ============================================================

    def _prepare_features(self, features_dict: dict) -> pd.DataFrame:
        """
        Prepara un dict de features para que sea compatible con el modelo.

        Incluye one-hot encoding de chain y alineacion con las columnas
        que el modelo espera.

        Args:
            features_dict: Dict de features calculados por FeatureBuilder.

        Returns:
            DataFrame de 1 fila con las columnas correctas.
        """
        # Crear DataFrame de una fila
        row = {k: v for k, v in features_dict.items() if k != "token_id"}
        df = pd.DataFrame([row])

        # One-hot encoding de chain si existe
        if "chain" in df.columns:
            chain_val = df["chain"].iloc[0]
            df = df.drop(columns=["chain"])
            # Agregar columnas de chain
            for ch in ["solana", "ethereum", "base"]:
                df[f"chain_{ch}"] = 1 if chain_val == ch else 0

        # Alinear columnas con las que espera el modelo
        if self.feature_columns:
            # Agregar columnas faltantes como 0
            for col in self.feature_columns:
                if col not in df.columns:
                    df[col] = 0
            # Seleccionar solo las columnas del modelo, en el orden correcto
            df = df[self.feature_columns]

        # Reemplazar infinitos con NaN para que las medianas los manejen
        df = df.replace([np.inf, -np.inf], np.nan)

        # Rellenar NaN con medianas de training (consistencia train/inference)
        if self.train_medians:
            df = df.fillna(self.train_medians)

        # Fallback: rellenar restantes con 0 y convertir tipos
        df = df.infer_objects(copy=False).fillna(0)

        return df

    # ============================================================
    # SCORE TOKEN INDIVIDUAL
    # ============================================================

    def score_token(self, token_id: str) -> dict:
        """
        Califica un token individual con probabilidad de ser gem.

        Flujo:
        1. Calcula features del token.
        2. Prepara features para el modelo.
        3. Predice probabilidad de gem.
        4. Asigna nivel de senal (STRONG/MEDIUM/WEAK/NONE).

        Args:
            token_id: ID del token (contract address).

        Returns:
            Dict con:
            - token_id: str
            - probability: float (0.0-1.0)
            - signal: str (STRONG/MEDIUM/WEAK/NONE)
            - prediction: int (1=gem, 0=no-gem)
            - features_used: int (numero de features calculados)
            - scored_at: str (timestamp ISO)
        """
        logger.info(f"Scoring token: {token_id[:10]}...")

        # Calcular features
        features = self.builder.build_features_for_token(token_id)

        if len(features) <= 1:  # Solo tiene token_id
            logger.warning(f"No hay features para {token_id}")
            return {
                "token_id": token_id,
                "probability": 0.0,
                "signal": "NONE",
                "prediction": 0,
                "features_used": 0,
                "scored_at": datetime.now(timezone.utc).isoformat(),
                "error": "No hay datos suficientes para calcular features",
            }

        # Preparar para prediccion
        X = self._prepare_features(features)

        # Predecir usando threshold optimo en lugar del 0.50 por defecto
        probability = float(self.model.predict_proba(X)[0][1])
        prediction = int(probability >= self.optimal_threshold)

        # Determinar senal
        signal = "NONE"
        for level, threshold in sorted(
            SIGNAL_THRESHOLDS.items(), key=lambda x: -x[1]
        ):
            if probability >= threshold:
                signal = level
                break

        result = {
            "token_id": token_id,
            "probability": round(probability, 4),
            "signal": signal,
            "prediction": prediction,
            "features_used": len(features) - 1,  # Menos token_id
            "scored_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            f"Token {token_id[:10]}: prob={probability:.1%}, "
            f"signal={signal}, pred={prediction}"
        )

        return result

    # ============================================================
    # SCORE TODOS LOS TOKENS NUEVOS
    # ============================================================

    def score_all_new(self, min_ohlcv_days: int = 7) -> pd.DataFrame:
        """
        Califica todos los tokens sin label que tengan suficiente OHLCV.

        Filtra tokens que:
        - No tienen label asignado todavia.
        - Tienen al menos min_ohlcv_days dias de datos OHLCV.

        Args:
            min_ohlcv_days: Minimo de dias de OHLCV requeridos.

        Returns:
            DataFrame con columnas: token_id, chain, symbol, probability,
            signal, prediction, features_used, scored_at.
            Ordenado por probabilidad descendente.
        """
        logger.info(f"Scoring tokens nuevos (min {min_ohlcv_days} dias OHLCV)...")

        # Obtener tokens sin label con OHLCV suficiente
        tokens_df = self.storage.query("""
            SELECT DISTINCT t.token_id, t.chain, t.symbol
            FROM tokens t
            INNER JOIN ohlcv o ON t.token_id = o.token_id AND o.timeframe = 'day'
            LEFT JOIN labels l ON t.token_id = l.token_id
            WHERE l.token_id IS NULL
            GROUP BY t.token_id
            HAVING COUNT(o.id) >= ?
        """, (min_ohlcv_days,))

        if tokens_df.empty:
            logger.info("No hay tokens nuevos para calificar")
            return pd.DataFrame()

        logger.info(f"Calificando {len(tokens_df)} tokens nuevos...")

        results = []
        for _, row in tokens_df.iterrows():
            token_id = row["token_id"]
            try:
                result = self.score_token(token_id)
                result["chain"] = row["chain"]
                result["symbol"] = row.get("symbol", "")
                results.append(result)
            except Exception as e:
                logger.warning(f"Error scoring {token_id[:10]}: {e}")

        if not results:
            return pd.DataFrame()

        # Crear DataFrame y ordenar por probabilidad
        df = pd.DataFrame(results)
        df = df.sort_values("probability", ascending=False).reset_index(drop=True)

        # Resumen
        for signal in ["STRONG", "MEDIUM", "WEAK"]:
            count = (df["signal"] == signal).sum()
            if count > 0:
                logger.info(f"  {signal}: {count} tokens")

        return df

    # ============================================================
    # GUARDAR SENALES A CSV
    # ============================================================

    def save_signals(
        self, df: pd.DataFrame, output_dir: Optional[Path] = None
    ) -> Path:
        """
        Guarda las senales en un CSV con timestamp.

        Args:
            df: DataFrame con senales (output de score_all_new).
            output_dir: Directorio de destino. Por defecto 'signals/'.

        Returns:
            Path al archivo CSV creado.
        """
        signals_dir = Path(output_dir) if output_dir else Path("signals")
        signals_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d")
        filepath = signals_dir / f"candidates_{date_str}.csv"

        df.to_csv(filepath, index=False)
        logger.info(f"Senales guardadas: {filepath} ({len(df)} tokens)")

        return filepath
