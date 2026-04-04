"""
tuner.py - Optimizacion de hiperparametros con Optuna.

Este modulo automatiza la busqueda de los mejores hiperparametros para
los modelos de clasificacion (Random Forest, XGBoost, LightGBM) usando
Optuna, un framework de optimizacion bayesiana.

Cada funcion objetivo usa TimeSeriesSplit (por defecto) o StratifiedKFold
con SMOTE dentro de cada fold para evitar data leakage.
La metrica objetivo es F1 (binary).

TimeSeriesSplit es el modo por defecto porque los datos de tokens estan
ordenados cronologicamente y el modelo debe predecir el futuro, no el
pasado. Usar StratifiedKFold en tuning pero TimeSeriesSplit en
entrenamiento optimizaria para una distribucion distinta (data leakage
temporal).

Clases:
    HyperparamTuner: Busca los mejores hiperparametros para cada modelo.

Dependencias:
    - optuna: Framework de optimizacion bayesiana.
    - scikit-learn: Modelos, metricas, cross-validation.
    - xgboost: Clasificador XGBoost.
    - lightgbm (opcional): Clasificador LightGBM.
    - imblearn: SMOTE para balanceo dentro de cada fold.

Ejemplo:
    tuner = HyperparamTuner(X_train, y_train, X_val, y_val, n_trials=50)
    mejores_params = tuner.tune_all()
    tuner.save_results("data/models/tuning_results.json")
"""

import json
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold, TimeSeriesSplit

# SMOTE para balanceo de clases dentro de cada fold
from imblearn.over_sampling import SMOTE

from src.utils.logger import get_logger

# Importar configuracion del proyecto
try:
    from config import ML_CONFIG
except ImportError:
    ML_CONFIG = {
        "random_seed": 42,
        "smote_sampling": 0.5,
        "cv_folds": 5,
    }

logger = get_logger(__name__)

# ============================================================
# Importar optuna de forma segura
# ============================================================
try:
    import optuna
    # Reducir ruido de logs de Optuna (solo mostrar warnings y errores)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    logger.warning(
        "Optuna no esta instalado. Instalar con: pip install optuna>=3.0"
    )

# XGBoost siempre disponible en este proyecto
from xgboost import XGBClassifier

# LightGBM es opcional
try:
    from lightgbm import LGBMClassifier
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False


class HyperparamTuner:
    """
    Optimizacion automatica de hiperparametros con Optuna.

    Usa optimizacion bayesiana (TPE sampler) para encontrar los mejores
    hiperparametros para Random Forest, XGBoost y LightGBM. Cada trial
    evalua una configuracion usando TimeSeriesSplit (o StratifiedKFold)
    con SMOTE aplicado dentro de cada fold (evita data leakage).

    Args:
        X_train: Features de entrenamiento (DataFrame o ndarray).
        y_train: Labels de entrenamiento (Series o ndarray).
        X_val: Features de validacion.
        y_val: Labels de validacion.
        n_trials: Numero de trials de Optuna (por defecto 50).
        random_seed: Semilla para reproducibilidad.
        temporal_cv: Si True (default), usa TimeSeriesSplit para respetar
                     el orden cronologico. Si False, usa StratifiedKFold.

    Atributos:
        best_params: Diccionario {modelo: mejores_hiperparametros}.
        studies: Diccionario {modelo: estudio_optuna}.

    Ejemplo:
        tuner = HyperparamTuner(X_train, y_train, X_val, y_val, n_trials=50)
        params = tuner.tune_random_forest()
        # params = {"n_estimators": 350, "max_depth": 10, ...}
    """

    def __init__(
        self,
        X_train,
        y_train,
        X_val,
        y_val,
        n_trials: int = 50,
        random_seed: int = None,
        temporal_cv: bool = True,
    ):
        """
        Inicializa el tuner con datos de entrenamiento y validacion.

        Args:
            X_train: Features de entrenamiento.
            y_train: Labels de entrenamiento.
            X_val: Features de validacion.
            y_val: Labels de validacion.
            n_trials: Numero de trials por modelo (default 50).
            random_seed: Semilla aleatoria (default: ML_CONFIG["random_seed"]).
            temporal_cv: Si True (default), usa TimeSeriesSplit para CV.
                         Si False, usa StratifiedKFold (comportamiento anterior).
        """
        if not OPTUNA_AVAILABLE:
            raise ImportError(
                "Optuna es necesario para tuning de hiperparametros. "
                "Instalar con: pip install optuna>=3.0"
            )

        # Convertir a numpy si son DataFrames/Series (Optuna trabaja mejor con arrays)
        self.X_train = np.asarray(X_train)
        self.y_train = np.asarray(y_train)
        self.X_val = np.asarray(X_val)
        self.y_val = np.asarray(y_val)
        self.n_trials = n_trials
        self.random_seed = random_seed or ML_CONFIG.get("random_seed", 42)
        self.smote_ratio = ML_CONFIG.get("smote_sampling", 0.5)
        self.cv_folds = ML_CONFIG.get("cv_folds", 5)
        self.temporal_cv = temporal_cv

        # Almacenar resultados
        self.best_params: dict = {}
        self.studies: dict = {}

        cv_label = "TimeSeriesSplit" if self.temporal_cv else "StratifiedKFold"
        logger.info(
            f"HyperparamTuner inicializado: {self.n_trials} trials, "
            f"{self.cv_folds}-fold CV ({cv_label}), seed={self.random_seed}"
        )

    # ============================================================
    # UTILIDAD: Cross-validation con SMOTE por fold
    # ============================================================

    def _cv_score_with_smote(self, model, X, y) -> float:
        """
        Calcula F1 medio usando TimeSeriesSplit o StratifiedKFold con SMOTE.

        Si temporal_cv=True (default), usa TimeSeriesSplit para respetar
        el orden cronologico de los datos. Los tokens estan ordenados por
        fecha de descubrimiento, y el modelo debe predecir el futuro.

        Si temporal_cv=False, usa StratifiedKFold (comportamiento original).

        SMOTE se aplica SOLO en el set de entrenamiento de cada fold,
        nunca en el set de validacion. Esto evita data leakage.

        Args:
            model: Clasificador sklearn-compatible (con fit/predict).
            X: Features (ndarray).
            y: Labels (ndarray).

        Returns:
            F1 score medio de los K folds.
        """
        if self.temporal_cv:
            # TimeSeriesSplit: respeta el orden cronologico.
            # No usa shuffle porque el orden temporal es fundamental.
            cv_splitter = TimeSeriesSplit(n_splits=self.cv_folds)
        else:
            # StratifiedKFold: aleatorio con estratificacion (modo legacy).
            cv_splitter = StratifiedKFold(
                n_splits=self.cv_folds,
                shuffle=True,
                random_state=self.random_seed,
            )
        smote = SMOTE(
            sampling_strategy=self.smote_ratio,
            random_state=self.random_seed,
        )

        scores = []
        for train_idx, val_idx in cv_splitter.split(X, y):
            X_fold_train, X_fold_val = X[train_idx], X[val_idx]
            y_fold_train, y_fold_val = y[train_idx], y[val_idx]

            # Aplicar SMOTE solo al fold de entrenamiento
            try:
                X_resampled, y_resampled = smote.fit_resample(
                    X_fold_train, y_fold_train
                )
            except ValueError:
                # Si SMOTE falla (pocas muestras), usar datos originales
                X_resampled, y_resampled = X_fold_train, y_fold_train

            # Entrenar y evaluar
            model_clone = _clone_model(model)
            model_clone.fit(X_resampled, y_resampled)
            y_pred = model_clone.predict(X_fold_val)
            fold_f1 = f1_score(y_fold_val, y_pred, average="binary", zero_division=0)
            scores.append(fold_f1)

        return float(np.mean(scores))

    # ============================================================
    # TUNING: Random Forest
    # ============================================================

    def tune_random_forest(self) -> dict:
        """
        Optimiza hiperparametros de Random Forest con Optuna.

        Espacio de busqueda:
            - n_estimators: 100-500
            - max_depth: 3-15
            - min_samples_split: 2-20
            - min_samples_leaf: 1-10
            - max_features: sqrt, log2, o float 0.3-0.8
            - class_weight: balanced, balanced_subsample

        Objetivo: Maximizar F1 (binary) con TimeSeriesSplit (o StratifiedKFold) + SMOTE.

        Returns:
            dict con los mejores hiperparametros encontrados.
        """
        logger.info("=== Optimizando Random Forest ===")

        def objective(trial: optuna.Trial) -> float:
            """Funcion objetivo para Optuna: evalua una config de RF."""
            # Definir espacio de busqueda
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 500),
                "max_depth": trial.suggest_int("max_depth", 3, 15),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
                "class_weight": trial.suggest_categorical(
                    "class_weight", ["balanced", "balanced_subsample"]
                ),
                "random_state": self.random_seed,
                "n_jobs": -1,
            }

            # max_features: puede ser string o float
            max_features_type = trial.suggest_categorical(
                "max_features_type", ["sqrt", "log2", "float"]
            )
            if max_features_type == "float":
                params["max_features"] = trial.suggest_float(
                    "max_features_float", 0.3, 0.8
                )
            else:
                params["max_features"] = max_features_type

            model = RandomForestClassifier(**params)
            return self._cv_score_with_smote(model, self.X_train, self.y_train)

        # Crear y ejecutar estudio
        sampler = optuna.samplers.TPESampler(seed=self.random_seed)
        study = optuna.create_study(
            direction="maximize",
            sampler=sampler,
            study_name="random_forest_tuning",
        )

        # Suprimir warnings de convergencia durante tuning
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            study.optimize(objective, n_trials=self.n_trials, show_progress_bar=False)

        # Extraer mejores parametros
        best = study.best_params.copy()

        # Reconstruir max_features desde los parametros de Optuna
        max_features_type = best.pop("max_features_type")
        if max_features_type == "float":
            best["max_features"] = best.pop("max_features_float")
        else:
            best["max_features"] = max_features_type
            best.pop("max_features_float", None)  # Limpiar si existe

        # Agregar parametros fijos
        best["random_state"] = self.random_seed
        best["n_jobs"] = -1

        self.best_params["random_forest"] = best
        self.studies["random_forest"] = study

        logger.info(
            f"RF mejor F1 (CV): {study.best_value:.4f} | "
            f"Params: {best}"
        )

        return best

    # ============================================================
    # TUNING: XGBoost
    # ============================================================

    def tune_xgboost(self) -> dict:
        """
        Optimiza hiperparametros de XGBoost con Optuna.

        Espacio de busqueda:
            - max_depth: 3-8
            - learning_rate: 0.01-0.3 (log uniform)
            - n_estimators: 100-800
            - min_child_weight: 1-10
            - gamma: 0-0.5
            - subsample: 0.6-1.0
            - colsample_bytree: 0.6-1.0
            - reg_alpha: 0-1
            - reg_lambda: 0.5-3
            - scale_pos_weight: calculado automaticamente

        Objetivo: Maximizar F1 (binary) con TimeSeriesSplit (o StratifiedKFold) + SMOTE.

        Returns:
            dict con los mejores hiperparametros encontrados.
        """
        logger.info("=== Optimizando XGBoost ===")

        # Calcular scale_pos_weight del ratio de clases
        n_negative = int((self.y_train == 0).sum())
        n_positive = int((self.y_train == 1).sum())
        scale_pos_weight = n_negative / n_positive if n_positive > 0 else 1.0

        def objective(trial: optuna.Trial) -> float:
            """Funcion objetivo para Optuna: evalua una config de XGBoost."""
            params = {
                "max_depth": trial.suggest_int("max_depth", 3, 8),
                "learning_rate": trial.suggest_float(
                    "learning_rate", 0.01, 0.3, log=True
                ),
                "n_estimators": trial.suggest_int("n_estimators", 100, 800),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "gamma": trial.suggest_float("gamma", 0.0, 0.5),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float(
                    "colsample_bytree", 0.6, 1.0
                ),
                "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 1.0),
                "reg_lambda": trial.suggest_float("reg_lambda", 0.5, 3.0),
                "scale_pos_weight": scale_pos_weight,
                "random_state": self.random_seed,
                "eval_metric": "logloss",
                "verbosity": 0,  # Silenciar XGBoost
            }

            model = XGBClassifier(**params)
            return self._cv_score_with_smote(model, self.X_train, self.y_train)

        # Crear y ejecutar estudio
        sampler = optuna.samplers.TPESampler(seed=self.random_seed)
        study = optuna.create_study(
            direction="maximize",
            sampler=sampler,
            study_name="xgboost_tuning",
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            study.optimize(objective, n_trials=self.n_trials, show_progress_bar=False)

        # Extraer mejores parametros y agregar fijos
        best = study.best_params.copy()
        best["scale_pos_weight"] = scale_pos_weight
        best["random_state"] = self.random_seed
        best["eval_metric"] = "logloss"

        self.best_params["xgboost"] = best
        self.studies["xgboost"] = study

        logger.info(
            f"XGB mejor F1 (CV): {study.best_value:.4f} | "
            f"Params: {best}"
        )

        return best

    # ============================================================
    # TUNING: LightGBM
    # ============================================================

    def tune_lightgbm(self) -> dict:
        """
        Optimiza hiperparametros de LightGBM con Optuna.

        Espacio de busqueda:
            - num_leaves: 15-63
            - max_depth: 3-10
            - learning_rate: 0.01-0.3 (log uniform)
            - n_estimators: 100-800
            - min_child_samples: 5-30
            - subsample: 0.6-1.0
            - colsample_bytree: 0.6-1.0
            - reg_alpha: 0-1
            - reg_lambda: 0-3
            - is_unbalance: True

        Objetivo: Maximizar F1 (binary) con TimeSeriesSplit (o StratifiedKFold) + SMOTE.

        Returns:
            dict con los mejores hiperparametros encontrados.

        Raises:
            ImportError: Si LightGBM no esta instalado.
        """
        if not LIGHTGBM_AVAILABLE:
            raise ImportError(
                "LightGBM no esta instalado. "
                "Instalar con: pip install lightgbm>=4.0"
            )

        logger.info("=== Optimizando LightGBM ===")

        def objective(trial: optuna.Trial) -> float:
            """Funcion objetivo para Optuna: evalua una config de LightGBM."""
            params = {
                "num_leaves": trial.suggest_int("num_leaves", 15, 63),
                "max_depth": trial.suggest_int("max_depth", 3, 10),
                "learning_rate": trial.suggest_float(
                    "learning_rate", 0.01, 0.3, log=True
                ),
                "n_estimators": trial.suggest_int("n_estimators", 100, 800),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 30),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float(
                    "colsample_bytree", 0.6, 1.0
                ),
                "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 1.0),
                "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 3.0),
                "is_unbalance": True,
                "random_state": self.random_seed,
                "verbosity": -1,  # Silenciar LightGBM
            }

            model = LGBMClassifier(**params)
            return self._cv_score_with_smote(model, self.X_train, self.y_train)

        # Crear y ejecutar estudio
        sampler = optuna.samplers.TPESampler(seed=self.random_seed)
        study = optuna.create_study(
            direction="maximize",
            sampler=sampler,
            study_name="lightgbm_tuning",
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            study.optimize(objective, n_trials=self.n_trials, show_progress_bar=False)

        # Extraer mejores parametros y agregar fijos
        best = study.best_params.copy()
        best["is_unbalance"] = True
        best["random_state"] = self.random_seed

        self.best_params["lightgbm"] = best
        self.studies["lightgbm"] = study

        logger.info(
            f"LGBM mejor F1 (CV): {study.best_value:.4f} | "
            f"Params: {best}"
        )

        return best

    # ============================================================
    # TUNING: Todos los modelos
    # ============================================================

    def tune_all(self) -> dict:
        """
        Optimiza hiperparametros para todos los modelos disponibles.

        Ejecuta tune_random_forest(), tune_xgboost() y, si LightGBM esta
        instalado, tune_lightgbm(). Retorna un diccionario con los mejores
        parametros de cada modelo.

        Returns:
            dict con estructura:
            {
                "random_forest": {params...},
                "xgboost": {params...},
                "lightgbm": {params...}  # solo si LightGBM disponible
            }
        """
        logger.info("=== Optimizando TODOS los modelos ===")

        results = {}

        # Random Forest
        results["random_forest"] = self.tune_random_forest()

        # XGBoost
        results["xgboost"] = self.tune_xgboost()

        # LightGBM (opcional)
        if LIGHTGBM_AVAILABLE:
            results["lightgbm"] = self.tune_lightgbm()
        else:
            logger.info(
                "LightGBM no disponible, saltando. "
                "Instalar con: pip install lightgbm>=4.0"
            )

        # Resumen
        logger.info("=== Resumen de tuning ===")
        for model_name, study in self.studies.items():
            logger.info(
                f"  {model_name}: mejor F1 (CV) = {study.best_value:.4f}"
            )

        return results

    # ============================================================
    # GUARDAR RESULTADOS
    # ============================================================

    def save_results(self, filepath: str):
        """
        Guarda los resultados de tuning en un archivo JSON.

        Incluye mejores parametros, mejor F1, y numero de trials
        para cada modelo optimizado.

        Args:
            filepath: Ruta del archivo JSON de salida.
        """
        cv_strategy = "TimeSeriesSplit" if self.temporal_cv else "StratifiedKFold"
        output = {}
        for model_name, params in self.best_params.items():
            study = self.studies.get(model_name)
            output[model_name] = {
                "best_params": _serialize_params(params),
                "best_f1_cv": float(study.best_value) if study else None,
                "n_trials": self.n_trials,
                "cv_folds": self.cv_folds,
                "cv_strategy": cv_strategy,
                "random_seed": self.random_seed,
            }

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"Resultados de tuning guardados en: {filepath}")


# ============================================================
# FUNCIONES AUXILIARES (privadas)
# ============================================================

def _clone_model(model):
    """
    Crea una copia del modelo con los mismos hiperparametros pero sin entrenar.

    Usa sklearn.base.clone si disponible, si no crea una instancia nueva
    con get_params().

    Args:
        model: Modelo sklearn-compatible.

    Returns:
        Clon del modelo sin entrenar.
    """
    from sklearn.base import clone
    return clone(model)


def _serialize_params(params: dict) -> dict:
    """
    Convierte parametros a tipos JSON-serializables.

    numpy int64/float64 no son serializables por defecto.

    Args:
        params: Diccionario de hiperparametros.

    Returns:
        Diccionario con tipos nativos de Python.
    """
    serialized = {}
    for key, value in params.items():
        if isinstance(value, (np.integer,)):
            serialized[key] = int(value)
        elif isinstance(value, (np.floating,)):
            serialized[key] = float(value)
        elif isinstance(value, np.bool_):
            serialized[key] = bool(value)
        else:
            serialized[key] = value
    return serialized
