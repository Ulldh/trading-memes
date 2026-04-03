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
    from config import MODELS_DIR, PROCESSED_DIR, SIGNAL_THRESHOLDS
except ImportError:
    MODELS_DIR = Path("data/models")
    PROCESSED_DIR = Path("data/processed")
    SIGNAL_THRESHOLDS = {"STRONG": 0.60, "MEDIUM": 0.40, "WEAK": 0.30}

logger = get_logger(__name__)


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
        """
        Carga la lista de columnas de features usadas en entrenamiento.

        Prioridad:
        1. metadata.json de la version activa del modelo (mas confiable)
        2. feature_columns.json en la raiz de models/ (puede estar desactualizado)
        3. training_metadata.joblib (legacy)
        4. X_train.csv (ultimo recurso)

        Es CRITICO usar las features exactas con las que se entreno el modelo.
        Si el FeatureBuilder genera mas features de las que el modelo conoce,
        _prepare_features() filtrara y alineara las columnas correctamente.
        """
        import json

        # 1. Intentar desde metadata.json de la version activa (PRIORIDAD)
        latest_file = self._models_dir / "latest_version.txt"
        if latest_file.exists():
            version = latest_file.read_text().strip()
            meta_path = self._models_dir / version / "metadata.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    metadata = json.load(f)
                feature_names = metadata.get("feature_names", [])
                if feature_names:
                    logger.info(
                        f"Feature columns cargadas desde {version}/metadata.json: "
                        f"{len(feature_names)} features"
                    )
                    return feature_names

        # 2. Fallback: feature_columns.json en raiz de models/
        fc_path = self._models_dir / "feature_columns.json"
        if fc_path.exists():
            with open(fc_path) as f:
                cols = json.load(f)
            logger.warning(
                f"Usando feature_columns.json (puede estar desactualizado): "
                f"{len(cols)} features"
            )
            return cols

        # 3. Fallback: training_metadata.joblib (legacy)
        meta_path = self._models_dir / "training_metadata.joblib"
        if meta_path.exists():
            metadata = joblib.load(meta_path)
            return metadata.get("feature_names", [])

        # 4. Ultimo recurso: X_train.csv
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

        # Fallback al threshold por defecto (0.30 para no perder gems reales).
        # Con pocos datos de entrenamiento, los modelos producen probabilidades
        # bajas incluso para gems verdaderos. Un threshold de 0.50 descarta
        # practicamente todos los candidatos. 0.30 es mas conservador que el
        # optimo teorico (0.20) para reducir falsos positivos en produccion.
        logger.info("Usando threshold por defecto: 0.30")
        return 0.30

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
        # El builder puede generar mas features de las que el modelo conoce
        # (ej: features nuevos agregados despues del entrenamiento).
        # Solo usamos las features con las que se entreno el modelo.
        if self.feature_columns:
            # Detectar columnas extra (generadas pero no usadas por el modelo)
            extra_cols = set(df.columns) - set(self.feature_columns)
            if extra_cols:
                logger.debug(
                    f"Descartando {len(extra_cols)} features extra no usadas "
                    f"por el modelo (builder genera {len(df.columns)}, "
                    f"modelo espera {len(self.feature_columns)})"
                )

            # Agregar columnas faltantes como 0
            missing_cols = [col for col in self.feature_columns if col not in df.columns]
            for col in missing_cols:
                df[col] = 0.0
            if missing_cols:
                logger.debug(
                    f"Agregando {len(missing_cols)} features faltantes con valor 0: "
                    f"{missing_cols[:5]}{'...' if len(missing_cols) > 5 else ''}"
                )

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

    def score_all_new(self, min_ohlcv_days: int = 3) -> pd.DataFrame:
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
    # SCORE + GUARDAR EN SUPABASE (para daily-collect.yml)
    # ============================================================

    def _get_model_version(self) -> str:
        """
        Obtiene la version del modelo actual desde latest_version.txt.

        Lee el archivo local si existe. Retorna 'unknown' si no se
        puede determinar la version.
        """
        latest_file = self._models_dir / "latest_version.txt"
        if latest_file.exists():
            return latest_file.read_text().strip()
        return "unknown"

    def _extract_estimator(self, model):
        """
        Extrae el estimador base de un Pipeline/ImbPipeline.

        Modelos nuevos (v22+) se guardan sin el wrapper ImbPipeline,
        asi que este metodo retorna el modelo directamente.
        Modelos antiguos (v21 y anteriores) estan envueltos en
        ImbPipeline([("smote", SMOTE), ("rf", RFC)]) y necesitan
        extraccion para evitar que SMOTE se aplique en inferencia.

        Compatible con ambos formatos para retrocompatibilidad.

        Args:
            model: Modelo que puede ser Pipeline, ImbPipeline o estimador directo.

        Returns:
            Estimador listo para predict/predict_proba sin SMOTE.
        """
        # Pipeline / ImbPipeline: tienen atributo 'steps' (lista de tuplas)
        # (modelos antiguos guardados con wrapper SMOTE)
        if hasattr(model, "steps"):
            estimator = model.steps[-1][1]
            logger.debug(
                f"Estimador extraido de pipeline (modelo legacy): "
                f"{type(estimator).__name__}"
            )
            return estimator
        # named_steps (alternativa menos comun)
        if hasattr(model, "named_steps"):
            estimator = list(model.named_steps.values())[-1]
            logger.debug(
                f"Estimador extraido de named_steps: {type(estimator).__name__}"
            )
            return estimator
        # Modelo directo (v22+ sin wrapper) o CalibratedClassifierCV
        return model

    def _prepare_features_batch(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepara un DataFrame completo de features para prediccion batch.

        Aplica one-hot encoding de chain, alinea columnas con el modelo,
        reemplaza infinitos/NaN con medianas de training, y retorna
        la matriz lista para predict_proba.

        Args:
            features_df: DataFrame con features de multiples tokens (de BD).

        Returns:
            DataFrame con las columnas correctas para el modelo.
        """
        df = features_df.copy()

        # Eliminar columnas no-feature (token_id se usa como indice, no como feature)
        non_feature_cols = ["token_id", "computed_at"]
        for col in non_feature_cols:
            if col in df.columns:
                df = df.drop(columns=[col])

        # One-hot encoding de chain si existe
        if "chain" in df.columns:
            for ch in ["solana", "ethereum", "base"]:
                df[f"chain_{ch}"] = (df["chain"] == ch).astype(int)
            df = df.drop(columns=["chain"])

        # Alinear columnas con las que espera el modelo
        if self.feature_columns:
            # Agregar columnas faltantes como 0
            missing_cols = [col for col in self.feature_columns if col not in df.columns]
            for col in missing_cols:
                df[col] = 0.0
            if missing_cols:
                logger.debug(
                    f"Batch: {len(missing_cols)} features faltantes agregados con valor 0"
                )

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

    def score_and_save(self, min_ohlcv_days: int = 3) -> pd.DataFrame:
        """
        Califica tokens usando features pre-calculados de la BD (batch).

        Optimizado para velocidad: carga TODOS los features de una vez
        desde la tabla features (1 query) en lugar de recalcularlos
        por token (N llamadas API). Prediccion vectorizada con numpy.

        Flujo:
        1. Identifica tokens sin score para la version actual del modelo.
        2. Carga features pre-calculados de la BD (1 query).
        3. Prepara la matriz de features (alineacion, encoding, imputacion).
        4. Prediccion batch (vectorizada, no loop).
        5. Upsert de scores en la tabla 'scores' via SupabaseStorage.

        Args:
            min_ohlcv_days: Minimo dias de OHLCV requeridos (default 3).

        Returns:
            DataFrame con los scores generados (puede estar vacio).
        """
        model_version = self._get_model_version()
        logger.info(
            f"score_and_save: modelo={self.model_name}, "
            f"version={model_version}, min_ohlcv={min_ohlcv_days}d"
        )

        # Paso 1: Obtener token_ids sin score para la version actual
        tokens_df = self.storage.query("""
            SELECT DISTINCT t.token_id, t.chain, t.symbol
            FROM tokens t
            INNER JOIN ohlcv o ON t.token_id = o.token_id
                AND o.timeframe = 'day'
            INNER JOIN features f ON t.token_id = f.token_id
            LEFT JOIN scores s ON t.token_id = s.token_id
                AND s.model_version = ?
            WHERE s.token_id IS NULL
            GROUP BY t.token_id, t.chain, t.symbol
            HAVING COUNT(o.id) >= ?
        """, (model_version, min_ohlcv_days))

        if tokens_df.empty:
            logger.info("score_and_save: no hay tokens nuevos para calificar")
            return pd.DataFrame()

        target_token_ids = set(tokens_df["token_id"].tolist())
        logger.info(f"score_and_save: {len(target_token_ids)} tokens por calificar")

        # Paso 2: Cargar features pre-calculados de la BD (1 query)
        all_features_df = self.storage.get_features_df()
        if all_features_df.empty:
            logger.warning("score_and_save: no hay features en la BD")
            return pd.DataFrame()

        # Filtrar solo los tokens que necesitan score
        features_df = all_features_df[
            all_features_df["token_id"].isin(target_token_ids)
        ].copy()

        if features_df.empty:
            logger.warning(
                "score_and_save: tokens sin score no tienen features en BD"
            )
            return pd.DataFrame()

        logger.info(
            f"score_and_save: {len(features_df)} tokens con features cargados "
            f"de BD (de {len(target_token_ids)} sin score)"
        )

        # Paso 3: Preparar matriz de features para prediccion batch
        # Guardar token_ids antes de preparar (se elimina en _prepare_features_batch)
        scored_token_ids = features_df["token_id"].values.copy()

        try:
            X = self._prepare_features_batch(features_df)
        except Exception as e:
            logger.error(f"score_and_save: error preparando features: {e}")
            return pd.DataFrame()

        # Paso 4: Prediccion batch vectorizada
        # Extraer estimador base del pipeline (evitar SMOTE en inferencia)
        estimator = self._extract_estimator(self.model)

        try:
            probabilities = estimator.predict_proba(X)[:, 1]
        except Exception as e:
            logger.error(f"score_and_save: error en predict_proba: {e}")
            return pd.DataFrame()

        # Paso 5: Construir resultados
        # Crear lookup de chain/symbol desde tokens_df
        token_info = tokens_df.set_index("token_id")[["chain", "symbol"]].to_dict("index")
        scored_at = datetime.now(timezone.utc).isoformat()

        results = []
        for i, token_id in enumerate(scored_token_ids):
            prob = float(probabilities[i])
            prediction = int(prob >= self.optimal_threshold)

            # Determinar senal
            signal = "NONE"
            for level, threshold in sorted(
                SIGNAL_THRESHOLDS.items(), key=lambda x: -x[1]
            ):
                if prob >= threshold:
                    signal = level
                    break

            info = token_info.get(token_id, {})
            results.append({
                "token_id": token_id,
                "probability": round(prob, 4),
                "signal": signal,
                "prediction": prediction,
                "chain": info.get("chain", ""),
                "symbol": info.get("symbol", ""),
                "model_name": self.model_name,
                "model_version": model_version,
                "scored_at": scored_at,
            })

        if not results:
            logger.info("score_and_save: ningun token pudo ser calificado")
            return pd.DataFrame()

        # Crear DataFrame y ordenar por probabilidad
        df = pd.DataFrame(results)
        df = df.sort_values("probability", ascending=False).reset_index(drop=True)

        # Preparar dicts para upsert en Supabase
        score_dicts = [
            {
                "token_id": row["token_id"],
                "probability": float(row["probability"]),
                "signal": row["signal"],
                "prediction": int(row["prediction"]),
                "model_name": row["model_name"],
                "model_version": row["model_version"],
                "scored_at": row["scored_at"],
            }
            for _, row in df.iterrows()
        ]

        # Upsert scores en Supabase
        try:
            self.storage.upsert_scores(score_dicts)
            logger.info(
                f"score_and_save: {len(score_dicts)} scores guardados "
                f"(version={model_version})"
            )
        except Exception as e:
            logger.error(f"score_and_save: error guardando scores: {e}")
            # Retornar el DataFrame aunque falle el guardado,
            # para que el caller pueda reintentar el upsert
            raise

        # Resumen de senales
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
