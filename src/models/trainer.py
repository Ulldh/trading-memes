"""
trainer.py - Pipeline de entrenamiento de modelos de Machine Learning.

Este modulo maneja el flujo completo de entrenamiento:
1. Preparacion de datos (merge, limpieza, split).
2. Seleccion automatica de features (varianza, correlacion, importancia).
3. Entrenamiento de Random Forest (con SMOTE para balanceo).
4. Entrenamiento de XGBoost (con early stopping).
5. Entrenamiento de LightGBM (opcional, si esta instalado).
6. Evaluacion de ensembles (soft_voting, weighted_voting, stacking).
7. Guardado y carga de modelos entrenados.
8. Versionado automatico de modelos (v1, v2, v3, etc.).

Clases:
    ModelTrainer: Orquesta el entrenamiento de multiples modelos.

Dependencias:
    - scikit-learn: Para Random Forest, metricas, y utilidades.
    - xgboost: Para el clasificador XGBoost.
    - imblearn: Para SMOTE (sobre-muestreo de clase minoritaria).
    - joblib: Para serializar/deserializar modelos.
    - pandas: Para manipulacion de datos.
    - lightgbm (opcional): Para el clasificador LightGBM.
"""

from pathlib import Path
from typing import Optional
import json
from datetime import datetime
import os

import numpy as np
import pandas as pd
import joblib

# Modelos de clasificacion
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

# Utilidades de sklearn
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score, cross_val_predict
from sklearn.metrics import (
    classification_report,
    accuracy_score,
    f1_score,
    roc_auc_score,
)

# Calibracion de probabilidades (Platt scaling / isotonic regression)
from sklearn.calibration import CalibratedClassifierCV

# SMOTE para balanceo de clases (sobre-muestreo sintetico)
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

from src.utils.logger import get_logger

# Modulos de Fase 5: feature selection, regularizacion, ensemble
from src.models.feature_selector import FeatureSelector
from src.models.regularization import get_regularized_rf_params, get_regularized_xgb_params

# LightGBM y EnsembleBuilder: importacion segura (pueden no estar instalados)
try:
    from src.models.ensemble import EnsembleBuilder, LIGHTGBM_AVAILABLE
except ImportError:
    LIGHTGBM_AVAILABLE = False

# Importar configuracion del proyecto
try:
    from config import ML_CONFIG, MODELS_DIR
except ImportError:
    # Valores por defecto si no se puede importar config
    ML_CONFIG = {
        "random_seed": 42,
        "test_size": 0.2,
        "cv_folds": 5,
        "smote_sampling": 0.5,
        "rf_params": {
            "n_estimators": 300,
            "max_depth": 15,
            "min_samples_leaf": 5,
            "class_weight": "balanced",
            "random_state": 42,
            "n_jobs": -1,
        },
        "xgb_params": {
            "n_estimators": 500,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "eval_metric": "logloss",
            "early_stopping_rounds": 50,
        },
    }
    MODELS_DIR = Path("data/models")

logger = get_logger(__name__)


class ModelTrainer:
    """
    Orquesta el entrenamiento de modelos de clasificacion para detectar memecoins "gem".

    Entrena tres tipos de modelos:
    - Random Forest: Robusto, interpretable, con SMOTE para balanceo de clases.
    - XGBoost: Alto rendimiento, con early stopping para evitar overfitting.
    - LightGBM (opcional): Gradient boosting rapido, si esta instalado.

    Tambien evalua estrategias de ensemble (soft_voting, weighted_voting, stacking)
    y realiza seleccion automatica de features para reducir overfitting.

    Todos los modelos se entrenan para clasificacion binaria por defecto
    (1 = token exitoso, 0 = no exitoso), pero tambien soportan multiclase.

    Args:
        random_seed: Semilla para reproducibilidad de resultados.

    Atributos:
        models: Diccionario {nombre_modelo: modelo_entrenado}.
        results: Diccionario {nombre_modelo: metricas}.
        _selected_features: Lista de features seleccionadas (si se uso feature selection).
        _feature_selection_info: Info de features eliminadas por cada filtro.

    Ejemplo:
        trainer = ModelTrainer(random_seed=42)

        # Entrenar todos los modelos (con feature selection y LightGBM)
        resultados = trainer.train_all(features_df, labels_df, target="label_binary")

        # Ver metricas
        print(resultados["random_forest"])

        # Guardar modelos
        trainer.save_models(Path("data/models"))
    """

    def __init__(self, random_seed: int = 42):
        """
        Inicializa el trainer con una semilla aleatoria.

        Args:
            random_seed: Semilla para reproducibilidad (por defecto 42).
        """
        self.random_seed = random_seed
        self.models: dict = {}        # nombre -> modelo entrenado
        self.results: dict = {}       # nombre -> diccionario de metricas
        self.feature_names: list = [] # nombres de las features usadas
        self._selected_features: list = []  # features tras seleccion (vacio si no se aplica)
        self._feature_selection_info: dict = {}  # info de seleccion (removed, selected, etc.)
        self._ensemble_builder: object = None  # EnsembleBuilder (si se usa)
        self._ensemble_results: dict = {}  # resultados de evaluacion de ensembles

    # ============================================================
    # PREPARACION DE DATOS
    # ============================================================

    def prepare_data(
        self,
        features_df: pd.DataFrame,
        labels_df: pd.DataFrame,
        target: str = "label_binary",
    ) -> tuple:
        """
        Prepara los datos para entrenamiento: merge, limpieza, y split.

        Pasos:
        1. Merge de features y labels por token_id.
        2. Eliminar filas donde el target es NaN.
        3. Rellenar NaN en features con la mediana de cada columna.
        4. Separar features (X) y target (y).
        5. Dividir en train/test con estratificacion.

        Args:
            features_df: DataFrame con features calculados (debe tener 'token_id').
            labels_df: DataFrame con labels (debe tener 'token_id' y la columna target).
            target: Nombre de la columna objetivo ('label_binary' o 'label_multi').

        Returns:
            Tupla de (X_train, X_test, y_train, y_test, feature_names).

        Raises:
            ValueError: Si no hay datos suficientes o la columna target no existe.
        """
        logger.info(
            f"Preparando datos: {len(features_df)} features, "
            f"{len(labels_df)} labels, target='{target}'"
        )

        # --- Paso 1: Merge por token_id ---
        # Asegurarnos de que token_id sea columna (no indice)
        if "token_id" not in features_df.columns and features_df.index.name == "token_id":
            features_df = features_df.reset_index()
        if "token_id" not in labels_df.columns and labels_df.index.name == "token_id":
            labels_df = labels_df.reset_index()

        # Merge inner: solo tokens que estan en ambos DataFrames
        merged_df = features_df.merge(labels_df, on="token_id", how="inner")
        logger.info(f"Despues de merge: {len(merged_df)} tokens con features y labels")

        if merged_df.empty:
            raise ValueError(
                "No hay tokens en comun entre features y labels. "
                "Verifica que ambos DataFrames tengan 'token_id'."
            )

        # --- Paso 2: Verificar que la columna target existe ---
        if target not in merged_df.columns:
            raise ValueError(
                f"La columna target '{target}' no existe en el DataFrame. "
                f"Columnas disponibles: {list(merged_df.columns)}"
            )

        # Eliminar filas donde el target es NaN
        antes = len(merged_df)
        merged_df = merged_df.dropna(subset=[target])
        despues = len(merged_df)
        if antes != despues:
            logger.info(f"Eliminadas {antes - despues} filas con target NaN")

        if merged_df.empty:
            raise ValueError("No quedan datos despues de eliminar NaN en el target.")

        # --- Paso 3: Separar features (X) y target (y) ---
        # Columnas que NO son features (son metadata o targets)
        non_feature_cols = [
            "token_id", "label_multi", "label_binary",
            "max_multiple", "final_multiple", "return_7d", "notes",
            "labeled_at", "computed_at",
            # Columnas de texto/metadata que pueden venir del storage
            "chain", "symbol", "name", "dex_id", "pool_address",
            "first_seen", "last_updated",
        ]
        # Manejar sufijos _x/_y del merge (colision de nombres entre features y labels)
        # return_7d existe en ambos DFs -> pandas genera return_7d_x (feature) y return_7d_y (label)
        suffixed_label_cols = [f"{col}_y" for col in non_feature_cols if f"{col}_y" in merged_df.columns]
        non_feature_cols.extend(suffixed_label_cols)
        # Renombrar features con sufijo _x a su nombre original
        rename_map = {}
        for col in merged_df.columns:
            if col.endswith("_x"):
                base = col[:-2]
                if base not in merged_df.columns and f"{base}_y" in merged_df.columns:
                    rename_map[col] = base
        if rename_map:
            merged_df = merged_df.rename(columns=rename_map)
            logger.info(f"Renombradas columnas con sufijo _x: {rename_map}")
        feature_cols = [
            col for col in merged_df.columns
            if col not in non_feature_cols
        ]

        # Filtrar solo columnas numericas (excluir strings, bools, objects)
        feature_cols = [
            col for col in feature_cols
            if pd.api.types.is_numeric_dtype(merged_df[col])
        ]

        # Filtrar features excluidos por configuración
        try:
            from config import EXCLUDED_FEATURES
            cols_to_drop = [c for c in EXCLUDED_FEATURES if c in feature_cols]
            if cols_to_drop:
                feature_cols = [c for c in feature_cols if c not in EXCLUDED_FEATURES]
                logger.info(f"Eliminados {len(cols_to_drop)} features excluidos: {cols_to_drop}")
        except ImportError:
            pass

        if not feature_cols:
            raise ValueError("No se encontraron columnas de features.")

        X = merged_df[feature_cols].copy()
        y = merged_df[target].copy()

        self.feature_names = feature_cols
        logger.info(f"Features seleccionados: {len(feature_cols)} columnas")

        # --- Paso 4: Split train/test con estratificacion ---
        test_size = ML_CONFIG.get("test_size", 0.2)

        # Verificar que hay al menos 2 clases y suficientes muestras
        unique_classes = y.nunique()
        if unique_classes < 2:
            raise ValueError(
                f"Solo hay {unique_classes} clase(s) en el target. "
                "Se necesitan al menos 2 clases para entrenar."
            )

        # Verificar que cada clase tiene suficientes muestras para estratificar
        min_class_count = y.value_counts().min()
        if min_class_count < 2:
            logger.warning(
                f"La clase minoritaria solo tiene {min_class_count} muestra(s). "
                "Esto puede causar problemas con estratificacion."
            )
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=test_size,
                random_state=self.random_seed,
            )
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=test_size,
                random_state=self.random_seed,
                stratify=y,
            )

        # --- Paso 5: Reemplazar infinitos y rellenar NaN ---
        # Primero reemplazar inf/-inf con NaN para que la mediana los maneje
        X_train = X_train.replace([np.inf, -np.inf], np.nan)
        X_test = X_test.replace([np.inf, -np.inf], np.nan)

        # IMPORTANTE: la mediana se calcula SOLO en train y se aplica a ambos
        train_medians = X_train.median()
        self._train_medians = train_medians  # Guardar para scorer

        nan_train = X_train.isna().sum().sum()
        nan_test = X_test.isna().sum().sum()
        if nan_train > 0 or nan_test > 0:
            logger.info(f"NaN encontrados: {nan_train} en train, {nan_test} en test")
        X_train = X_train.fillna(train_medians).fillna(0)
        X_test = X_test.fillna(train_medians).fillna(0)

        logger.info(
            f"Split: train={len(X_train)} ({(1-test_size)*100:.0f}%), "
            f"test={len(X_test)} ({test_size*100:.0f}%)"
        )
        logger.info(f"Distribucion train:\n{y_train.value_counts().to_string()}")
        logger.info(f"Distribucion test:\n{y_test.value_counts().to_string()}")

        return X_train, X_test, y_train, y_test, feature_cols

    # ============================================================
    # ENTRENAMIENTO: Random Forest
    # ============================================================

    def train_random_forest(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        rf_params_override: dict | None = None,
    ) -> RandomForestClassifier:
        """
        Entrena un Random Forest con SMOTE para balanceo de clases.

        SMOTE (Synthetic Minority Over-sampling Technique) crea ejemplos
        sinteticos de la clase minoritaria para que el modelo no este
        sesgado hacia la clase mayoritaria.

        Usa hiperparametros regularizados de regularization.py por defecto,
        con class_weight='balanced' y cross-validation de 5 folds.

        Args:
            X_train: Features de entrenamiento.
            y_train: Labels de entrenamiento.
            X_val: Features de validacion (para reportar metricas).
            y_val: Labels de validacion.
            rf_params_override: Hiperparametros personalizados (override de regularizados).

        Returns:
            Modelo RandomForestClassifier entrenado.
        """
        logger.info("--- Entrenando Random Forest ---")

        # --- Configurar el modelo (regularizados por defecto) ---
        rf_params = get_regularized_rf_params(random_seed=self.random_seed)
        # Permitir override parcial (ej: de Optuna)
        if rf_params_override:
            rf_params.update(rf_params_override)
        rf_params["random_state"] = self.random_seed
        smote_ratio = ML_CONFIG.get("smote_sampling", 0.5)

        # --- Cross-validation con SMOTE DENTRO de cada fold ---
        # IMPORTANTE: SMOTE se aplica dentro de cada fold para que las
        # muestras sinteticas no contaminen la validacion del fold.
        cv_folds = ML_CONFIG.get("cv_folds", 5)
        try:
            skf = StratifiedKFold(
                n_splits=cv_folds,
                shuffle=True,
                random_state=self.random_seed,
            )
            smote_rf_pipeline = ImbPipeline([
                ("smote", SMOTE(
                    sampling_strategy=smote_ratio,
                    random_state=self.random_seed,
                )),
                ("classifier", RandomForestClassifier(**rf_params)),
            ])
            cv_scores = cross_val_score(
                smote_rf_pipeline, X_train, y_train,
                cv=skf, scoring="f1", n_jobs=-1,
            )
            logger.info(
                f"CV ({cv_folds} folds, SMOTE por fold) F1: "
                f"{cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})"
            )
        except ValueError as e:
            logger.warning(f"Cross-validation fallo ({e}). Continuando sin CV.")
            cv_scores = np.array([0.0])

        # --- Entrenar el modelo final con ImbPipeline (misma config que CV) ---
        # IMPORTANTE: usar el mismo pipeline que CV para consistencia.
        # El modelo guardado es el pipeline completo (funciona con predict/predict_proba).
        model = ImbPipeline([
            ("smote", SMOTE(
                sampling_strategy=smote_ratio,
                random_state=self.random_seed,
            )),
            ("classifier", RandomForestClassifier(**rf_params)),
        ])
        model.fit(X_train, y_train)
        logger.info("Random Forest (ImbPipeline) entrenado exitosamente")

        # --- Evaluar en el set de validacion ---
        y_pred_val = model.predict(X_val)
        val_f1 = f1_score(y_val, y_pred_val, average="binary", zero_division=0)
        val_acc = accuracy_score(y_val, y_pred_val)
        logger.info(f"Validacion: F1={val_f1:.4f}, Accuracy={val_acc:.4f}")

        # --- Guardar modelo y metricas ---
        self.models["random_forest"] = model
        self.results["random_forest"] = {
            "cv_f1_mean": float(cv_scores.mean()),
            "cv_f1_std": float(cv_scores.std()),
            "val_f1": float(val_f1),
            "val_accuracy": float(val_acc),
        }

        return model

    # ============================================================
    # ENTRENAMIENTO: XGBoost
    # ============================================================

    def train_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        xgb_params_override: dict | None = None,
    ) -> XGBClassifier:
        """
        Entrena un XGBoost con early stopping y scale_pos_weight.

        Usa hiperparametros regularizados de regularization.py por defecto
        para reducir el overfitting observado en v12 (gap CV-Val de 0.131).

        scale_pos_weight: Ajusta el peso de la clase positiva para compensar
        el desbalanceo. Se calcula dinamicamente segun el ratio de clases.

        Early stopping: Detiene el entrenamiento si no mejora en N rondas,
        evitando overfitting.

        Args:
            X_train: Features de entrenamiento.
            y_train: Labels de entrenamiento.
            X_val: Features de validacion (usado para early stopping).
            y_val: Labels de validacion.
            xgb_params_override: Hiperparametros personalizados (override de regularizados).

        Returns:
            Modelo XGBClassifier entrenado.
        """
        logger.info("--- Entrenando XGBoost ---")

        # --- Calcular scale_pos_weight para compensar desbalanceo ---
        # Es la proporcion de negativos a positivos
        n_negative = int((y_train == 0).sum())
        n_positive = int((y_train == 1).sum())

        if n_positive > 0:
            scale_pos_weight = n_negative / n_positive
        else:
            # Si no hay positivos, usar 1.0 como fallback
            logger.warning("No hay muestras positivas en el set de entrenamiento")
            scale_pos_weight = 1.0

        logger.info(
            f"Clases: {n_negative} negativos, {n_positive} positivos | "
            f"scale_pos_weight={scale_pos_weight:.2f}"
        )

        # --- Configurar el modelo (regularizados por defecto) ---
        xgb_params = get_regularized_xgb_params(random_seed=self.random_seed)
        # Permitir override parcial (ej: de Optuna)
        if xgb_params_override:
            xgb_params.update(xgb_params_override)
        xgb_params["random_state"] = self.random_seed
        xgb_params["scale_pos_weight"] = scale_pos_weight

        # early_stopping_rounds es parametro del constructor en XGBoost >= 2.0
        xgb_params.setdefault("early_stopping_rounds", 50)

        model = XGBClassifier(**xgb_params)

        # --- Cross-validation en datos de entrenamiento ---
        # Modelo sin early_stopping para CV (cross_val_score no pasa eval_set)
        cv_folds = ML_CONFIG.get("cv_folds", 5)
        cv_scores = np.array([0.0])
        try:
            xgb_cv_params = {k: v for k, v in xgb_params.items()
                             if k != "early_stopping_rounds"}
            cv_model = XGBClassifier(**xgb_cv_params)
            skf = StratifiedKFold(
                n_splits=cv_folds,
                shuffle=True,
                random_state=self.random_seed,
            )
            cv_scores = cross_val_score(
                cv_model, X_train, y_train,
                cv=skf, scoring="f1", n_jobs=-1,
            )
            logger.info(
                f"XGBoost CV ({cv_folds} folds) F1: "
                f"{cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})"
            )
        except ValueError as e:
            logger.warning(f"XGBoost cross-validation fallo ({e}). Continuando sin CV.")
            cv_scores = np.array([0.0])

        # --- Entrenar con early stopping ---
        # El eval_set permite monitorear el rendimiento en validacion
        # Si no mejora en 'early_stopping_rounds' iteraciones, para de entrenar
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,  # No imprimir cada iteracion
        )

        # Reportar en que iteracion paro
        best_iteration = getattr(model, "best_iteration", None)
        if best_iteration is not None:
            logger.info(f"XGBoost: mejor iteracion = {best_iteration}")
        else:
            logger.info(f"XGBoost: entreno las {xgb_params.get('n_estimators', 500)} iteraciones")

        # --- Evaluar en el set de validacion ---
        y_pred_val = model.predict(X_val)
        val_f1 = f1_score(y_val, y_pred_val, average="binary", zero_division=0)
        val_acc = accuracy_score(y_val, y_pred_val)
        logger.info(f"Validacion: F1={val_f1:.4f}, Accuracy={val_acc:.4f}")

        # --- Guardar modelo y metricas ---
        self.models["xgboost"] = model
        self.results["xgboost"] = {
            "cv_f1_mean": float(cv_scores.mean()),
            "cv_f1_std": float(cv_scores.std()),
            "best_iteration": best_iteration,
            "val_f1": float(val_f1),
            "val_accuracy": float(val_acc),
            "scale_pos_weight": float(scale_pos_weight),
        }

        return model

    # ============================================================
    # CALIBRACION DE PROBABILIDADES
    # ============================================================

    def calibrate_model(self, model, X_cal, y_cal, method="sigmoid"):
        """
        Calibra las probabilidades de un modelo ya entrenado.

        predict_proba() de RF y XGBoost NO devuelve probabilidades calibradas.
        Un 80% no significa realmente 80% de probabilidad de ser gem.
        La calibracion corrige esto usando Platt scaling (sigmoid) o
        isotonic regression.

        IMPORTANTE: X_cal/y_cal deben ser datos NO vistos por el modelo
        (ej: X_test, y_test) para que la calibracion sea honesta.

        Args:
            model: Modelo ya entrenado (con predict y predict_proba).
            X_cal: Features para calibracion (datos NO vistos por el modelo).
            y_cal: Labels para calibracion.
            method: "sigmoid" (Platt scaling, bueno para datasets pequeños)
                    o "isotonic" (mas flexible, necesita mas datos).

        Returns:
            Modelo calibrado con predict_proba() ajustado.
        """
        logger.info(f"Calibrando modelo con metodo '{method}'...")
        # FrozenEstimator evita que CalibratedClassifierCV re-entrene el modelo.
        # Solo ajusta la funcion de calibracion sobre los datos proporcionados.
        # (reemplaza cv="prefit" que fue eliminado en sklearn 1.6+)
        from sklearn.frozen import FrozenEstimator
        calibrated = CalibratedClassifierCV(
            FrozenEstimator(model), method=method, cv=3
        )
        calibrated.fit(X_cal, y_cal)
        logger.info("Modelo calibrado exitosamente")
        return calibrated

    # ============================================================
    # ENTRENAMIENTO: Ensemble
    # ============================================================

    def train_ensemble(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ):
        """
        Crea un VotingClassifier soft combinando RF + XGBoost.

        Soft voting promedia las probabilidades de ambos modelos.
        Requiere que RF y XGBoost ya esten entrenados.

        Args:
            X_train: Features de entrenamiento.
            y_train: Labels de entrenamiento.
            X_val: Features de validacion.
            y_val: Labels de validacion.

        Returns:
            VotingClassifier entrenado, o None si falla.
        """
        from src.models.optimizer import ModelOptimizer

        logger.info("--- Creando Ensemble (VotingClassifier) ---")

        rf_model = self.models.get("random_forest")
        xgb_model = self.models.get("xgboost")

        if rf_model is None or xgb_model is None:
            logger.warning("Ensemble requiere RF y XGBoost entrenados")
            return None

        optimizer = ModelOptimizer(random_seed=self.random_seed)
        ensemble = optimizer.create_ensemble(
            X_train, y_train,
            rf_model=rf_model, xgb_model=xgb_model,
        )

        # Evaluar ensemble
        y_pred = ensemble.predict(X_val)
        val_f1 = f1_score(y_val, y_pred, average="binary", zero_division=0)
        val_acc = accuracy_score(y_val, y_pred)

        logger.info(f"Ensemble validacion: F1={val_f1:.4f}, Accuracy={val_acc:.4f}")

        self.models["ensemble"] = ensemble
        self.results["ensemble"] = {
            "val_f1": float(val_f1),
            "val_accuracy": float(val_acc),
        }

        return ensemble

    # ============================================================
    # PIPELINE COMPLETO
    # ============================================================

    def train_all(
        self,
        features_df: pd.DataFrame,
        labels_df: pd.DataFrame,
        target: str = "label_binary",
        use_feature_selection: bool = True,
    ) -> dict:
        """
        Pipeline completo: prepara datos, selecciona features, entrena modelos, evalua ensembles.

        Este es el metodo principal que ejecuta todo el flujo de entrenamiento:
        1. Prepara los datos (merge, limpieza, split).
        2. Seleccion automatica de features (varianza, correlacion, importancia).
        3. Entrena Random Forest con SMOTE + hiperparametros regularizados.
        4. Entrena XGBoost con early stopping + hiperparametros regularizados.
        5. Entrena LightGBM (si esta disponible).
        6. Evalua ensembles (soft_voting, weighted_voting, stacking).
        7. Calibra probabilidades y busca threshold optimo.
        8. Devuelve diccionario con todos los resultados.

        Args:
            features_df: DataFrame con features calculados.
            labels_df: DataFrame con labels.
            target: Columna objetivo ('label_binary' por defecto).
            use_feature_selection: Si True, aplica seleccion automatica de features
                                   para reducir overfitting (default True).

        Returns:
            Diccionario con estructura:
            {
                "random_forest": {metricas...},
                "xgboost": {metricas...},
                "lightgbm": {metricas...},  # solo si LightGBM disponible
                "data_info": {info del dataset...},
            }
        """
        logger.info("=" * 60)
        logger.info("INICIO DEL PIPELINE DE ENTRENAMIENTO (v2 - Fase 5)")
        logger.info("=" * 60)

        # --- Paso 1: Preparar datos ---
        X_train, X_test, y_train, y_test, feature_names = self.prepare_data(
            features_df, labels_df, target=target
        )

        # Guardar datos de test para evaluacion posterior
        self._X_test = X_test
        self._y_test = y_test
        self._X_train = X_train
        self._y_train = y_train

        # Extraer token_ids del merge para excluir del backtesting
        # (evita data leakage: el backtester no debe evaluar tokens de entrenamiento)
        if "token_id" not in features_df.columns and features_df.index.name == "token_id":
            feat_tmp = features_df.reset_index()
        else:
            feat_tmp = features_df
        if "token_id" not in labels_df.columns and labels_df.index.name == "token_id":
            lab_tmp = labels_df.reset_index()
        else:
            lab_tmp = labels_df
        merged_tmp = feat_tmp.merge(lab_tmp, on="token_id", how="inner")
        # Indices de train en el merged DataFrame
        all_token_ids = merged_tmp["token_id"].values
        train_indices = X_train.index
        self._train_token_ids = list(all_token_ids[train_indices])

        # --- Paso 1b: Seleccion automatica de features ---
        original_feature_count = len(feature_names)
        if use_feature_selection:
            try:
                X_train, X_test, feature_names = self._run_feature_selection(
                    X_train, X_test, y_train, feature_names
                )
                # Actualizar feature_names internos
                self.feature_names = feature_names
                self._X_train = X_train
                self._X_test = X_test
            except Exception as e:
                logger.warning(f"Feature selection fallo: {e}. Continuando con todas las features.")

        # Informacion del dataset
        data_info = {
            "total_samples": len(X_train) + len(X_test),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "n_features": len(feature_names),
            "n_features_original": original_feature_count,
            "feature_names": feature_names,
            "target": target,
            "class_distribution": y_train.value_counts().to_dict(),
        }

        # --- Paso 2: Entrenar Random Forest (hiperparametros regularizados) ---
        try:
            self.train_random_forest(X_train, y_train, X_test, y_test)
        except Exception as e:
            logger.error(f"Error entrenando Random Forest: {e}")
            self.results["random_forest"] = {"error": str(e)}

        # --- Paso 3: Entrenar XGBoost (hiperparametros regularizados) ---
        try:
            self.train_xgboost(X_train, y_train, X_test, y_test)
        except Exception as e:
            logger.error(f"Error entrenando XGBoost: {e}")
            self.results["xgboost"] = {"error": str(e)}

        # --- Paso 3b: Entrenar LightGBM (si esta disponible) ---
        try:
            self._train_lightgbm(X_train, y_train, X_test, y_test)
        except Exception as e:
            logger.warning(f"LightGBM no disponible o fallo: {e}")

        # --- Paso 4: Calibrar probabilidades de todos los modelos ---
        # IMPORTANTE: calibrar con X_test/y_test (datos NO vistos) para
        # que las probabilidades sean realistas, no optimistas.
        for name in list(self.models.keys()):
            try:
                logger.info(f"Calibrando modelo: {name}")
                calibrated = self.calibrate_model(self.models[name], X_test, y_test)
                self.models[name] = calibrated

                # Re-evaluar metricas con modelo calibrado
                y_pred_cal = calibrated.predict(X_test)
                cal_f1 = f1_score(y_test, y_pred_cal, average="binary", zero_division=0)
                self.results[name]["calibrated"] = True
                self.results[name]["val_f1_calibrated"] = float(cal_f1)
                logger.info(f"  {name} calibrado: F1={cal_f1:.4f}")
            except Exception as e:
                logger.warning(f"Calibracion fallo para {name}: {e}")
                if name in self.results and isinstance(self.results[name], dict):
                    self.results[name]["calibrated"] = False

        # --- Paso 4b: Calcular threshold optimo via CV en TRAIN ---
        # IMPORTANTE: usar out-of-fold predictions en train (no X_test)
        # para evitar optimizar el threshold sobre datos de evaluacion.
        for name in list(self.models.keys()):
            try:
                # Crear estimador fresco para OOF predictions
                if name == "random_forest":
                    rf_p = get_regularized_rf_params(random_seed=self.random_seed)
                    smote_ratio_t = ML_CONFIG.get("smote_sampling", 0.5)
                    cv_est = ImbPipeline([
                        ("smote", SMOTE(
                            sampling_strategy=smote_ratio_t,
                            random_state=self.random_seed,
                        )),
                        ("clf", RandomForestClassifier(**rf_p)),
                    ])
                elif name == "xgboost":
                    xgb_p = get_regularized_xgb_params(random_seed=self.random_seed)
                    n_neg = int((y_train == 0).sum())
                    n_pos = int((y_train == 1).sum())
                    xgb_p["scale_pos_weight"] = n_neg / n_pos if n_pos > 0 else 1.0
                    xgb_p.pop("early_stopping_rounds", None)
                    cv_est = XGBClassifier(**xgb_p)
                else:
                    # Para lightgbm u otros, saltar threshold optimization
                    continue

                skf_t = StratifiedKFold(
                    n_splits=5, shuffle=True,
                    random_state=self.random_seed,
                )
                y_prob_oof = cross_val_predict(
                    cv_est, X_train, y_train,
                    cv=skf_t, method="predict_proba",
                )[:, 1]

                best_t, best_f1 = 0.5, 0.0
                for t in np.arange(0.10, 0.91, 0.05):
                    y_pred_t = (y_prob_oof >= t).astype(int)
                    f1_t = f1_score(y_train, y_pred_t, zero_division=0)
                    if f1_t > best_f1:
                        best_f1 = f1_t
                        best_t = round(float(t), 2)
                self.results[name]["optimal_threshold"] = best_t
                self.results[name]["optimal_threshold_f1"] = float(best_f1)
                logger.info(
                    f"  {name} threshold optimo (CV en train): {best_t:.2f} "
                    f"(F1_oof={best_f1:.4f})"
                )
            except Exception as e:
                logger.warning(f"Threshold optimization fallo para {name}: {e}")

        # --- Paso 5: Evaluar ensembles (soft_voting, weighted_voting, stacking) ---
        try:
            self._evaluate_ensembles(X_train, y_train, X_test, y_test)
        except Exception as e:
            logger.warning(f"Evaluacion de ensemble fallo: {e}")

        # --- Paso 5b: Crear ensemble legacy si esta habilitado (retrocompatibilidad) ---
        if ML_CONFIG.get("use_ensemble", False):
            try:
                ensemble = self.train_ensemble(X_train, y_train, X_test, y_test)
                if ensemble is not None:
                    logger.info("Ensemble legacy creado exitosamente")
            except Exception as e:
                logger.warning(f"Ensemble legacy fallo: {e}")

        # --- Resumen ---
        self.results["data_info"] = data_info
        logger.info("=" * 60)
        logger.info("PIPELINE DE ENTRENAMIENTO COMPLETADO")
        for name, metrics in self.results.items():
            if name != "data_info" and isinstance(metrics, dict) and "error" not in metrics:
                val_f1 = metrics.get("val_f1")
                if val_f1 is not None:
                    logger.info(f"  {name}: F1={val_f1:.4f}")
        if self._ensemble_results:
            best_ensemble = max(
                self._ensemble_results.items(),
                key=lambda x: x[1].get("f1", 0) if isinstance(x[1], dict) else 0,
            )
            logger.info(
                f"  Mejor ensemble: {best_ensemble[0]} "
                f"(F1={best_ensemble[1].get('f1', 0):.4f})"
            )
        logger.info("=" * 60)

        return self.results

    # ============================================================
    # SELECCION AUTOMATICA DE FEATURES (Fase 5)
    # ============================================================

    def _run_feature_selection(
        self,
        X_train: pd.DataFrame,
        X_test: pd.DataFrame,
        y_train: pd.Series,
        feature_names: list[str],
    ) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
        """
        Ejecuta el pipeline de seleccion automatica de features.

        Entrena un RF rapido para estimar importancias, y luego ejecuta
        el pipeline auto_select de FeatureSelector (varianza -> correlacion -> importancia).

        Args:
            X_train: Features de entrenamiento.
            X_test: Features de validacion.
            y_train: Labels de entrenamiento.
            feature_names: Lista de nombres de features originales.

        Returns:
            Tupla de (X_train_filtered, X_test_filtered, selected_features).
        """
        logger.info("=" * 60)
        logger.info("SELECCION AUTOMATICA DE FEATURES")
        logger.info("=" * 60)

        # Entrenar un RF rapido para estimar importancias
        # (pocos arboles, sin SMOTE, solo para ranking de features)
        quick_rf = RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            random_state=self.random_seed,
            n_jobs=-1,
            class_weight="balanced",
        )
        quick_rf.fit(X_train, y_train)

        # Ejecutar pipeline de seleccion
        selector = FeatureSelector(X_train, y_train, feature_names)
        X_filtered, selected_features = selector.auto_select(model=quick_rf)

        # Guardar informacion de seleccion
        original_count = len(feature_names)
        selected_count = len(selected_features)
        removed_features = [f for f in feature_names if f not in selected_features]

        self._selected_features = selected_features
        self._feature_selection_info = {
            "original_count": original_count,
            "selected_count": selected_count,
            "removed": removed_features,
            "selected": selected_features,
            "removal_report": selector.get_removal_report(),
        }

        # Aplicar seleccion a ambos sets
        X_train_filtered = X_train[selected_features].copy()
        X_test_filtered = X_test[selected_features].copy()

        logger.info(
            f"Feature selection: {original_count} -> {selected_count} features "
            f"({len(removed_features)} eliminadas)"
        )

        return X_train_filtered, X_test_filtered, selected_features

    # ============================================================
    # ENTRENAMIENTO: LightGBM (Fase 5)
    # ============================================================

    def _train_lightgbm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ):
        """
        Entrena LightGBM via EnsembleBuilder y registra metricas.

        Si LightGBM no esta instalado, lanza un warning y retorna sin error.

        Args:
            X_train: Features de entrenamiento.
            y_train: Labels de entrenamiento.
            X_val: Features de validacion.
            y_val: Labels de validacion.
        """
        if not LIGHTGBM_AVAILABLE:
            logger.warning(
                "LightGBM no esta instalado. Saltando entrenamiento LightGBM. "
                "Instalar con: pip install lightgbm>=4.0"
            )
            return

        logger.info("--- Entrenando LightGBM ---")

        # Crear EnsembleBuilder con los modelos base ya entrenados
        base_models = {}
        for name in ["random_forest", "xgboost"]:
            if name in self.models:
                base_models[name] = self.models[name]

        if not base_models:
            logger.warning("No hay modelos base entrenados para crear EnsembleBuilder")
            return

        self._ensemble_builder = EnsembleBuilder(base_models)

        # Entrenar LightGBM via EnsembleBuilder
        lgb_model = self._ensemble_builder.train_lightgbm(
            X_train, y_train, X_val, y_val,
            random_seed=self.random_seed,
        )

        # Evaluar LightGBM en validacion
        y_pred_val = lgb_model.predict(X_val)
        val_f1 = f1_score(y_val, y_pred_val, average="binary", zero_division=0)
        val_acc = accuracy_score(y_val, y_pred_val)

        # Cross-validation para LightGBM
        import lightgbm as lgb
        cv_folds = ML_CONFIG.get("cv_folds", 5)
        cv_scores = np.array([0.0])
        try:
            lgb_cv_params = {
                "objective": "binary",
                "num_leaves": 31,
                "max_depth": 6,
                "learning_rate": 0.05,
                "n_estimators": 500,
                "is_unbalance": True,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "reg_alpha": 0.1,
                "reg_lambda": 0.1,
                "random_state": self.random_seed,
                "verbose": -1,
                "n_jobs": -1,
            }
            lgb_cv_model = lgb.LGBMClassifier(**lgb_cv_params)
            skf = StratifiedKFold(
                n_splits=cv_folds, shuffle=True, random_state=self.random_seed,
            )
            cv_scores = cross_val_score(
                lgb_cv_model, X_train, y_train,
                cv=skf, scoring="f1", n_jobs=-1,
            )
            logger.info(
                f"LightGBM CV ({cv_folds} folds) F1: "
                f"{cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})"
            )
        except Exception as e:
            logger.warning(f"LightGBM cross-validation fallo: {e}")

        logger.info(f"LightGBM validacion: F1={val_f1:.4f}, Accuracy={val_acc:.4f}")

        # Registrar modelo y metricas
        self.models["lightgbm"] = lgb_model
        self.results["lightgbm"] = {
            "cv_f1_mean": float(cv_scores.mean()),
            "cv_f1_std": float(cv_scores.std()),
            "val_f1": float(val_f1),
            "val_accuracy": float(val_acc),
        }

    # ============================================================
    # EVALUACION DE ENSEMBLES (Fase 5)
    # ============================================================

    def _evaluate_ensembles(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ):
        """
        Evalua estrategias de ensemble: soft_voting, weighted_voting, stacking.

        Requiere al menos 2 modelos base entrenados. Si LightGBM no esta
        disponible, evalua ensemble con RF + XGBoost.

        Guarda los resultados en self._ensemble_results y el meta-learner
        de stacking en self._stacking_meta_learner.

        Args:
            X_train: Features de entrenamiento (para stacking).
            y_train: Labels de entrenamiento (para stacking).
            X_val: Features de validacion.
            y_val: Labels de validacion.
        """
        # Necesitamos al menos 2 modelos para ensemble
        base_models = {
            name: model for name, model in self.models.items()
            if name in ["random_forest", "xgboost", "lightgbm"]
        }

        if len(base_models) < 2:
            logger.warning(
                f"Solo hay {len(base_models)} modelo(s) base. "
                "Ensemble requiere al menos 2. Saltando."
            )
            return

        logger.info("=" * 60)
        logger.info("EVALUACION DE ENSEMBLES")
        logger.info(f"Modelos base: {list(base_models.keys())}")
        logger.info("=" * 60)

        # Crear o reutilizar EnsembleBuilder
        if self._ensemble_builder is not None:
            # Ya tiene los modelos (incluyendo LightGBM si se entreno)
            ensemble = self._ensemble_builder
            # Asegurar que tiene todos los modelos base actualizados (post-calibracion)
            ensemble.models = dict(base_models)
        else:
            ensemble = EnsembleBuilder(base_models)
            self._ensemble_builder = ensemble

        # Evaluar todas las estrategias
        ensemble_results = ensemble.evaluate_ensemble(
            X_val, y_val,
            X_train=X_train,
            y_train=y_train,
        )

        # Filtrar solo resultados de ensemble (no modelos individuales)
        ensemble_methods = ["soft_voting", "weighted_voting", "stacking"]
        for method in ensemble_methods:
            if method in ensemble_results:
                self._ensemble_results[f"ensemble_{method}"] = ensemble_results[method]

        # Guardar meta-learner si stacking es el mejor
        best_method = ensemble.get_best_method()
        logger.info(f"Mejor metodo global: {best_method}")

        if ensemble.meta_learner is not None:
            self._stacking_meta_learner = ensemble.meta_learner

        # Guardar best_model info
        self._ensemble_results["_best_method"] = best_method
        best_f1 = ensemble_results.get(best_method, {}).get("f1", 0)
        self._ensemble_results["_best_f1"] = best_f1

    # ============================================================
    # GUARDAR / CARGAR MODELOS
    # ============================================================

    def save_models(self, path: Optional[Path] = None):
        """
        Guarda todos los modelos entrenados en disco usando joblib.

        joblib es mas eficiente que pickle para objetos con arrays numpy grandes,
        como los modelos de sklearn y xgboost.

        Args:
            path: Directorio donde guardar los modelos. Por defecto usa MODELS_DIR.
        """
        save_dir = Path(path) if path else MODELS_DIR
        save_dir.mkdir(parents=True, exist_ok=True)

        for name, model in self.models.items():
            filepath = save_dir / f"{name}.joblib"
            joblib.dump(model, filepath)
            logger.info(f"Modelo '{name}' guardado en: {filepath}")

        # Guardar tambien los nombres de features (necesarios para prediccion)
        metadata = {
            "feature_names": self.feature_names,
            "results": self.results,
        }
        metadata_path = save_dir / "training_metadata.joblib"
        joblib.dump(metadata, metadata_path)
        logger.info(f"Metadata guardada en: {metadata_path}")

    def load_models(self, path: Optional[Path] = None):
        """
        Carga modelos previamente guardados desde disco.

        Args:
            path: Directorio donde estan los modelos. Por defecto usa MODELS_DIR.
        """
        load_dir = Path(path) if path else MODELS_DIR

        if not load_dir.exists():
            raise FileNotFoundError(f"Directorio de modelos no encontrado: {load_dir}")

        # Cargar cada archivo .joblib como modelo
        model_files = list(load_dir.glob("*.joblib"))
        if not model_files:
            raise FileNotFoundError(f"No se encontraron modelos en: {load_dir}")

        for filepath in model_files:
            name = filepath.stem  # nombre sin extension
            if name == "training_metadata":
                # Cargar metadata en lugar de como modelo
                metadata = joblib.load(filepath)
                self.feature_names = metadata.get("feature_names", [])
                self.results = metadata.get("results", {})
                logger.info(f"Metadata cargada: {len(self.feature_names)} features")
            else:
                self.models[name] = joblib.load(filepath)
                logger.info(f"Modelo '{name}' cargado desde: {filepath}")

        logger.info(f"Total modelos cargados: {len(self.models)}")

    # ============================================================
    # VERSIONADO DE MODELOS
    # ============================================================

    def _get_next_version(self, base_dir: Path) -> int:
        """
        Encuentra el siguiente numero de version disponible.

        Busca carpetas con formato v1, v2, v3, etc. y devuelve el siguiente.

        Args:
            base_dir: Directorio base donde estan las versiones.

        Returns:
            Numero de la siguiente version (ej: si existe v2, devuelve 3).
        """
        if not base_dir.exists():
            return 1

        # Buscar carpetas con formato v{N}
        versions = []
        for path in base_dir.iterdir():
            if path.is_dir() and path.name.startswith("v"):
                try:
                    version_num = int(path.name[1:])  # "v2" -> 2
                    versions.append(version_num)
                except ValueError:
                    continue

        # Devolver siguiente version
        return max(versions) + 1 if versions else 1

    def save_models_versioned(
        self,
        base_path: Optional[Path] = None,
        metadata: Optional[dict] = None,
    ) -> Path:
        """
        Guarda modelos con versionado automatico (v1, v2, v3, etc.).

        Estructura creada:
            data/models/
                v1/
                    random_forest.joblib
                    xgboost.joblib
                    metadata.json          # Info completa de la version
                v2/
                    ...
                random_forest.joblib  -> v2/random_forest.joblib (symlink)
                xgboost.joblib        -> v2/xgboost.joblib (symlink)
                latest_version.txt    # Contiene "v2"

        El metadata.json contiene:
            - version: Numero de version (ej: "v2")
            - trained_at: Timestamp ISO del entrenamiento
            - train_samples: Numero de tokens en entrenamiento
            - test_samples: Numero de tokens en test
            - feature_names: Lista de features usados
            - results: Metricas de evaluacion (F1, accuracy, etc.)
            - hyperparameters: Parametros de cada modelo

        Args:
            base_path: Directorio base (default: MODELS_DIR).
            metadata: Metadata adicional para incluir en JSON.

        Returns:
            Path al directorio de la version guardada (ej: data/models/v2).

        Ejemplo:
            >>> trainer = ModelTrainer()
            >>> trainer.train_all(features_df, labels_df)
            >>> version_dir = trainer.save_models_versioned()
            >>> print(f"Modelos guardados en: {version_dir}")
        """
        base_dir = Path(base_path) if base_path else MODELS_DIR
        base_dir.mkdir(parents=True, exist_ok=True)

        # Obtener siguiente numero de version
        version_num = self._get_next_version(base_dir)
        version_name = f"v{version_num}"
        version_dir = base_dir / version_name

        logger.info(f"Guardando modelos en version: {version_name}")
        version_dir.mkdir(parents=True, exist_ok=True)

        # ============================================================
        # 1. GUARDAR MODELOS EN CARPETA VERSIONADA
        # ============================================================
        for name, model in self.models.items():
            filepath = version_dir / f"{name}.joblib"
            joblib.dump(model, filepath)
            logger.info(f"  {name}.joblib -> {version_name}/")

        # Guardar ensemble meta-learner si existe
        if hasattr(self, "_stacking_meta_learner") and self._stacking_meta_learner is not None:
            meta_path = version_dir / "ensemble_meta.joblib"
            joblib.dump(self._stacking_meta_learner, meta_path)
            logger.info(f"  ensemble_meta.joblib -> {version_name}/")

        # ============================================================
        # 2. PREPARAR METADATA JSON (estructura v2 - Fase 5)
        # ============================================================
        metadata_dict = {
            "version": version_name,
            "trained_at": datetime.now().isoformat() + "Z",
            "feature_names": self.feature_names,
            "num_features": len(self.feature_names),
            "results": {},
            "hyperparameters": {},
        }

        # Añadir informacion de feature selection (si se aplico)
        if self._feature_selection_info:
            metadata_dict["feature_selection"] = self._feature_selection_info

        # Añadir informacion de resultados (train_samples, f1, etc.)
        for model_name, metrics in self.results.items():
            if isinstance(metrics, dict):
                # Filtrar valores serializables
                clean_metrics = {}
                for k, v in metrics.items():
                    if isinstance(v, (int, float, str, bool, type(None))):
                        clean_metrics[k] = v
                    elif isinstance(v, (list, dict)):
                        clean_metrics[k] = v
                metadata_dict["results"][model_name] = clean_metrics

        # Añadir resultados de ensemble (soft_voting, weighted_voting, stacking)
        if self._ensemble_results:
            for method_name, method_metrics in self._ensemble_results.items():
                if isinstance(method_metrics, dict):
                    clean = {}
                    for k, v in method_metrics.items():
                        if isinstance(v, (int, float, str, bool, type(None))):
                            clean[k] = v
                    metadata_dict["results"][method_name] = clean

            # Guardar mejor modelo global y su F1
            best_method = self._ensemble_results.get("_best_method", "")
            best_f1 = self._ensemble_results.get("_best_f1", 0)
            metadata_dict["best_model"] = best_method
            metadata_dict["best_f1"] = best_f1

        # Añadir hiperparametros regularizados (no los de config legacy)
        metadata_dict["hyperparameters"]["random_forest"] = get_regularized_rf_params(
            random_seed=self.random_seed
        )
        metadata_dict["hyperparameters"]["xgboost"] = get_regularized_xgb_params(
            random_seed=self.random_seed
        )

        # Añadir train_token_ids para que el backtester pueda excluirlos
        if hasattr(self, "_train_token_ids"):
            metadata_dict["train_token_ids"] = self._train_token_ids

        # Guardar medianas de training para consistencia train/inference
        if hasattr(self, "_train_medians"):
            metadata_dict["train_medians"] = {
                k: float(v) if pd.notna(v) else 0.0
                for k, v in self._train_medians.to_dict().items()
            }
            # Guardar tambien como archivo separado para facil acceso
            medians_path = version_dir / "train_medians.json"
            with open(medians_path, "w") as f:
                json.dump(metadata_dict["train_medians"], f, indent=2)
            logger.info(f"  train_medians.json -> {version_name}/")

        # Añadir metadata adicional si se proporciono
        if metadata:
            metadata_dict.update(metadata)

        # Guardar metadata JSON
        metadata_path = version_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata_dict, f, indent=2, default=str)
        logger.info(f"  metadata.json -> {version_name}/")

        # ============================================================
        # 3. CREAR SYMLINKS A LA VERSION ACTUAL (retrocompatibilidad)
        # ============================================================
        for name in self.models.keys():
            symlink_path = base_dir / f"{name}.joblib"
            target_path = version_dir / f"{name}.joblib"

            # Eliminar symlink anterior si existe
            if symlink_path.exists() or symlink_path.is_symlink():
                symlink_path.unlink()

            # Crear symlink relativo
            try:
                # Usar ruta relativa para que funcione al mover el proyecto
                relative_target = Path(version_name) / f"{name}.joblib"
                symlink_path.symlink_to(relative_target)
                logger.info(f"  Symlink: {name}.joblib -> {version_name}/")
            except OSError as e:
                # En Windows puede fallar si no hay permisos de admin
                logger.warning(f"No se pudo crear symlink para {name}: {e}")

        # ============================================================
        # 4. GUARDAR ARCHIVO DE VERSION ACTUAL
        # ============================================================
        latest_version_file = base_dir / "latest_version.txt"
        with open(latest_version_file, "w") as f:
            f.write(version_name)
        logger.info(f"  latest_version.txt -> {version_name}")

        logger.info(f"✅ Modelos guardados exitosamente en: {version_dir}")
        return version_dir

    def get_latest_version(self, base_path: Optional[Path] = None) -> Optional[str]:
        """
        Obtiene el nombre de la version mas reciente.

        Args:
            base_path: Directorio base (default: MODELS_DIR).

        Returns:
            Nombre de la version (ej: "v3"), o None si no hay versiones.

        Ejemplo:
            >>> trainer = ModelTrainer()
            >>> latest = trainer.get_latest_version()
            >>> print(f"Ultima version: {latest}")
        """
        base_dir = Path(base_path) if base_path else MODELS_DIR

        # Intentar leer latest_version.txt
        latest_file = base_dir / "latest_version.txt"
        if latest_file.exists():
            return latest_file.read_text().strip()

        # Si no existe, buscar la version mas alta
        version_num = self._get_next_version(base_dir) - 1
        if version_num > 0:
            return f"v{version_num}"

        return None

    def load_models_versioned(
        self,
        version: Optional[str] = None,
        base_path: Optional[Path] = None,
    ) -> dict:
        """
        Carga modelos de una version especifica.

        Args:
            version: Nombre de la version (ej: "v2"). Si es None, carga la ultima.
            base_path: Directorio base (default: MODELS_DIR).

        Returns:
            Dict con metadata de la version cargada.

        Raises:
            FileNotFoundError: Si la version no existe.

        Ejemplo:
            >>> trainer = ModelTrainer()
            >>> metadata = trainer.load_models_versioned("v2")
            >>> print(f"Modelos v2 cargados: F1={metadata['results']['random_forest']['val_f1']}")
        """
        base_dir = Path(base_path) if base_path else MODELS_DIR

        # Si no se especifica version, usar la ultima
        if version is None:
            version = self.get_latest_version(base_dir)
            if version is None:
                raise FileNotFoundError("No se encontraron versiones de modelos")

        version_dir = base_dir / version

        if not version_dir.exists():
            raise FileNotFoundError(f"Version '{version}' no encontrada en {base_dir}")

        logger.info(f"Cargando modelos desde version: {version}")

        # Cargar modelos
        self.load_models(version_dir)

        # Cargar metadata
        metadata_path = version_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            # Asignar feature_names y results desde metadata
            self.feature_names = metadata.get("feature_names", [])
            self.results = metadata.get("results", {})

            logger.info(f"Metadata cargada: {metadata.get('trained_at', 'N/A')}")
            logger.info(f"Features: {len(self.feature_names)}, Results: {len(self.results)}")
            return metadata
        else:
            logger.warning(f"No se encontro metadata.json en {version_dir}")
            return {}
