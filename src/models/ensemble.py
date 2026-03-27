"""
ensemble.py - Modelos ensemble combinando RF, XGBoost y LightGBM.

Este modulo construye y evalua modelos ensemble que combinan las predicciones
de multiples modelos base (Random Forest, XGBoost, LightGBM) para obtener
predicciones mas robustas y precisas.

Estrategias disponibles:
- Soft Voting: Promedio simple de probabilidades de todos los modelos.
- Weighted Voting: Promedio ponderado (pesos basados en F1 de validacion).
- Stacking: Meta-learner (Logistic Regression) entrenado sobre predicciones base.

Clases:
    EnsembleBuilder: Construye y evalua modelos ensemble.

Dependencias:
    - scikit-learn: Para Logistic Regression (stacking) y metricas.
    - lightgbm (opcional): Para el modelo LightGBM.
    - numpy: Para operaciones con arrays.
"""

from typing import Optional

import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    accuracy_score,
    roc_auc_score,
)

from src.utils.logger import get_logger

# Importar LightGBM de forma segura (puede no estar instalado)
try:
    import lightgbm as lgb

    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

logger = get_logger(__name__)


class EnsembleBuilder:
    """
    Construye y evalua modelos ensemble combinando RF, XGB, y LightGBM.

    Un ensemble combina las predicciones de multiples modelos para obtener
    una prediccion final mas robusta. La idea es que los errores de un modelo
    pueden ser compensados por los aciertos de otros.

    Estrategias:
    - soft_voting: Promedia las probabilidades de todos los modelos.
      Simple y efectivo. Funciona bien cuando los modelos son diversos.
    - weighted_voting: Igual que soft_voting pero cada modelo tiene un peso
      proporcional a su rendimiento individual (F1 en validacion).
    - stacking: Entrena un meta-learner (Logistic Regression) que aprende
      la mejor forma de combinar las predicciones base. Mas potente pero
      requiere datos de validacion para entrenar el meta-learner.

    Atributos:
        models: Dict con los modelos base {nombre: modelo}.
        val_scores: Dict con F1 de validacion por modelo {nombre: f1}.
        meta_learner: Modelo de stacking (Logistic Regression) si se entreno.
        evaluation_results: Dict con metricas de cada estrategia.
        best_method_name: Nombre del mejor metodo segun F1 de validacion.

    Ejemplo:
        # Crear con modelos ya entrenados
        models = {
            "random_forest": rf_model,
            "xgboost": xgb_model,
        }
        ensemble = EnsembleBuilder(models)

        # Entrenar LightGBM y agregarlo
        lgb_model = ensemble.train_lightgbm(X_train, y_train, X_val, y_val)

        # Evaluar todas las estrategias
        results = ensemble.evaluate_ensemble(X_val, y_val)
        print(f"Mejor metodo: {ensemble.get_best_method()}")

        # Predecir con el mejor metodo
        proba = ensemble.soft_voting(X_test)
    """

    def __init__(self, models: dict[str, object]):
        """
        Inicializa el ensemble con modelos base ya entrenados.

        Args:
            models: Diccionario {nombre: modelo_entrenado}.
                    Ejemplo: {"random_forest": rf_model, "xgboost": xgb_model}
                    Los modelos deben tener metodos predict() y predict_proba().
        """
        if not models:
            raise ValueError(
                "Se necesita al menos un modelo base para el ensemble. "
                "Pasa un diccionario con al menos un modelo entrenado."
            )

        self.models = dict(models)  # Copia para no mutar el original
        self.val_scores: dict[str, float] = {}  # nombre -> F1 en validacion
        self.meta_learner: Optional[LogisticRegression] = None
        self.evaluation_results: dict = {}
        self.best_method_name: Optional[str] = None

        logger.info(
            f"EnsembleBuilder inicializado con {len(self.models)} modelo(s): "
            f"{list(self.models.keys())}"
        )

    # ============================================================
    # EXTRACCION DE ESTIMADOR BASE
    # ============================================================

    def _extract_estimator(self, model):
        """
        Extrae el estimador base de un Pipeline/ImbPipeline.

        RF se almacena como ImbPipeline([("smote", SMOTE), ("rf", RFC)]).
        Si llamamos predict_proba() sobre el pipeline, SMOTE se aplica
        a los datos de validacion y corrompe las predicciones (F1=0.0).

        Esta funcion extrae el clasificador final del pipeline para
        llamar predict/predict_proba directamente sobre el, sin pasar
        por SMOTE ni otros transformadores.

        CalibratedClassifierCV y modelos sueltos (XGB, LGB) se retornan
        tal cual porque su predict_proba() funciona correctamente.

        Args:
            model: Modelo que puede ser Pipeline, ImbPipeline,
                   CalibratedClassifierCV o estimador directo.

        Returns:
            Estimador listo para predict/predict_proba sin SMOTE.
        """
        # Pipeline / ImbPipeline: tienen atributo 'steps' (lista de tuplas)
        if hasattr(model, "steps"):
            estimator = model.steps[-1][1]
            logger.debug(
                f"Estimador extraido de pipeline: {type(estimator).__name__}"
            )
            return estimator
        # named_steps (alternativa menos comun)
        if hasattr(model, "named_steps"):
            estimator = list(model.named_steps.values())[-1]
            logger.debug(
                f"Estimador extraido de named_steps: {type(estimator).__name__}"
            )
            return estimator
        # CalibratedClassifierCV o modelo directo: retornar tal cual
        return model

    # ============================================================
    # ENTRENAMIENTO DE LIGHTGBM
    # ============================================================

    def train_lightgbm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        random_seed: int = 42,
    ) -> object:
        """
        Entrena un modelo LightGBM y lo agrega al ensemble.

        LightGBM es un framework de gradient boosting que usa arboles de decision
        basados en histogramas. Es mas rapido que XGBoost y maneja bien datasets
        pequenos con el parametro is_unbalance para clases desbalanceadas.

        Parametros optimizados para:
        - Dataset pequeno (~4000 tokens): num_leaves=31, max_depth=6.
        - Clases desbalanceadas: is_unbalance=True.
        - Evitar overfitting: learning_rate=0.05, early_stopping_rounds=50.

        Args:
            X_train: Features de entrenamiento.
            y_train: Labels de entrenamiento (0/1).
            X_val: Features de validacion (para early stopping).
            y_val: Labels de validacion (para early stopping).
            random_seed: Semilla para reproducibilidad.

        Returns:
            Modelo LightGBM entrenado (LGBMClassifier).

        Raises:
            ImportError: Si lightgbm no esta instalado.
        """
        if not LIGHTGBM_AVAILABLE:
            raise ImportError(
                "LightGBM no esta instalado. "
                "Instala con: pip install lightgbm>=4.0"
            )

        logger.info("Entrenando LightGBM...")

        # Calcular scale_pos_weight para manejar desbalance de clases
        # Mas efectivo que is_unbalance para datasets pequenos con minoria extrema
        n_neg = int((y_train == 0).sum())
        n_pos = int((y_train == 1).sum())
        spw = n_neg / n_pos if n_pos > 0 else 1.0
        logger.info(f"  Clase positiva: {n_pos}/{len(y_train)} ({100*n_pos/len(y_train):.1f}%), scale_pos_weight={spw:.1f}")

        # Parametros optimizados para dataset pequeno + clasificacion binaria
        params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "num_leaves": 31,       # Complejidad del arbol (2^max_depth = 64 > 31, evita overfitting)
            "max_depth": 6,         # Profundidad maxima (limita complejidad)
            "learning_rate": 0.05,  # Tasa de aprendizaje baja para convergencia suave
            "n_estimators": 500,    # Maximo de arboles (early stopping lo controla)
            "scale_pos_weight": spw,  # Peso explicito para clase minoritaria (mejor que is_unbalance)
            "min_child_samples": 5, # Minimo de muestras por hoja (default=20 es mucho para ~4000 muestras)
            "subsample": 0.8,       # Fraccion de datos por arbol (reduce overfitting)
            "colsample_bytree": 0.8,  # Fraccion de features por arbol
            "reg_alpha": 0.1,       # Regularizacion L1
            "reg_lambda": 0.1,      # Regularizacion L2
            "random_state": random_seed,
            "verbose": -1,          # Silenciar logs de LightGBM
            "n_jobs": -1,           # Usar todos los cores
        }

        model = lgb.LGBMClassifier(**params)

        # Entrenar con o sin early stopping
        if X_val is not None and y_val is not None:
            logger.info("  Usando early stopping con set de validacion")
            model.fit(
                X_train,
                y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[
                    lgb.early_stopping(stopping_rounds=50, verbose=False),
                    lgb.log_evaluation(period=0),  # Silenciar logs de iteracion
                ],
            )
            # Garantizar minimo 50 iteraciones para evitar underfitting
            # Con datasets pequenos y desbalanceados, early stopping puede parar
            # muy pronto (ej: 15 iteraciones) porque logloss converge rapido
            # prediciendo todo como clase mayoritaria.
            min_iterations = 50
            if model.best_iteration_ < min_iterations:
                logger.warning(
                    f"  LightGBM paro en {model.best_iteration_} iteraciones (< {min_iterations} minimo). "
                    f"Re-entrenando con n_estimators={min_iterations} sin early stopping..."
                )
                params_retry = dict(params)
                params_retry["n_estimators"] = min_iterations
                model = lgb.LGBMClassifier(**params_retry)
                model.fit(X_train, y_train)
                logger.info(f"  LightGBM re-entrenado con {min_iterations} iteraciones fijas")
            else:
                logger.info(
                    f"  LightGBM entrenado con {model.best_iteration_} iteraciones "
                    f"(de {params['n_estimators']} max)"
                )
        else:
            logger.info("  Sin set de validacion, entrenando sin early stopping")
            model.fit(X_train, y_train)

        # Agregar al ensemble
        self.models["lightgbm"] = model
        logger.info("  LightGBM agregado al ensemble")

        return model

    # ============================================================
    # PREDICCION: SOFT VOTING
    # ============================================================

    def soft_voting(self, X: pd.DataFrame) -> np.ndarray:
        """
        Prediccion por votacion suave (promedio de probabilidades).

        Cada modelo genera sus probabilidades (predict_proba) y se promedian.
        El resultado es la probabilidad promedio de ser clase positiva (gem).

        Ejemplo: Si RF dice 0.8, XGB dice 0.6, y LGB dice 0.7,
        el soft voting da (0.8 + 0.6 + 0.7) / 3 = 0.7.

        Args:
            X: Features para predecir.

        Returns:
            Array de probabilidades promediadas (clase positiva).
        """
        all_probs = self._collect_probabilities(X)

        # Promediar las probabilidades de todos los modelos
        avg_probs = np.mean(all_probs, axis=0)

        logger.info(
            f"Soft voting con {len(all_probs)} modelos. "
            f"Prob media: {avg_probs.mean():.4f}"
        )

        return avg_probs

    # ============================================================
    # PREDICCION: WEIGHTED VOTING
    # ============================================================

    def weighted_voting(
        self,
        X: pd.DataFrame,
        weights: Optional[dict[str, float]] = None,
    ) -> np.ndarray:
        """
        Prediccion por votacion ponderada.

        Igual que soft_voting pero cada modelo tiene un peso diferente.
        Por defecto, los pesos se basan en el F1 de validacion de cada modelo.
        Modelos con mejor F1 tienen mas influencia en la prediccion final.

        Si no se proporcionan pesos y no hay val_scores, usa pesos iguales
        (equivalente a soft_voting).

        Args:
            X: Features para predecir.
            weights: Dict {nombre_modelo: peso}. Si None, usa val_scores (F1).

        Returns:
            Array de probabilidades ponderadas (clase positiva).
        """
        # Determinar pesos
        if weights is not None:
            model_weights = weights
        elif self.val_scores:
            # Usar F1 de validacion como pesos
            model_weights = self.val_scores
        else:
            # Sin pesos disponibles, usar pesos iguales (= soft voting)
            logger.warning(
                "No hay pesos ni val_scores disponibles. "
                "Usando pesos iguales (equivalente a soft voting). "
                "Ejecuta evaluate_ensemble() primero para calcular val_scores."
            )
            model_weights = {name: 1.0 for name in self.models}

        # Recolectar probabilidades y sus pesos
        all_probs = []
        all_weights = []

        for name, model in self.models.items():
            try:
                # Extraer estimador base para evitar que SMOTE corrompa datos
                estimator = self._extract_estimator(model)
                proba = estimator.predict_proba(X)
                # Tomar probabilidad de clase positiva
                if proba.ndim == 2 and proba.shape[1] >= 2:
                    prob_positive = proba[:, 1]
                else:
                    prob_positive = proba[:, 0]

                weight = model_weights.get(name, 1.0)
                all_probs.append(prob_positive)
                all_weights.append(weight)
            except Exception as e:
                logger.warning(f"Error obteniendo probabilidades de '{name}': {e}")

        if not all_probs:
            raise ValueError(
                "Ningun modelo pudo generar probabilidades. "
                "Verifica que los modelos tengan predict_proba()."
            )

        # Normalizar pesos para que sumen 1
        total_weight = sum(all_weights)
        norm_weights = [w / total_weight for w in all_weights]

        # Promedio ponderado
        weighted_probs = np.zeros_like(all_probs[0])
        for prob, weight in zip(all_probs, norm_weights):
            weighted_probs += prob * weight

        logger.info(
            f"Weighted voting con {len(all_probs)} modelos. "
            f"Pesos normalizados: {dict(zip(self.models.keys(), norm_weights))}"
        )

        return weighted_probs

    # ============================================================
    # PREDICCION: STACKING
    # ============================================================

    def stacking(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ) -> LogisticRegression:
        """
        Meta-learner (Logistic Regression) sobre predicciones base.

        El stacking entrena un modelo de segundo nivel que aprende a combinar
        las predicciones de los modelos base de forma optima.

        Paso 1: Cada modelo base genera sus probabilidades para X_train.
        Paso 2: Esas probabilidades se usan como features para entrenar
                 una Logistic Regression (el meta-learner).
        Paso 3: Para predecir, los modelos base generan probabilidades
                 y el meta-learner las combina.

        Args:
            X_train: Features de entrenamiento (para generar meta-features).
            y_train: Labels de entrenamiento (para entrenar meta-learner).
            X_val: Features de validacion (para evaluar el stacking).
            y_val: Labels de validacion (para evaluar el stacking).

        Returns:
            Meta-learner entrenado (LogisticRegression).
        """
        logger.info("Entrenando meta-learner (stacking)...")

        # Paso 1: Generar meta-features (probabilidades de modelos base)
        meta_train = self._build_meta_features(X_train)
        meta_val = self._build_meta_features(X_val)

        logger.info(
            f"  Meta-features generadas: {meta_train.shape[1]} columnas "
            f"(una por modelo base)"
        )

        # Paso 2: Entrenar Logistic Regression como meta-learner
        # C=1.0 regularizacion por defecto, max_iter alto para convergencia
        self.meta_learner = LogisticRegression(
            C=1.0,
            max_iter=1000,
            random_state=42,
            solver="lbfgs",
        )
        self.meta_learner.fit(meta_train, y_train)

        # Evaluar en validacion
        y_pred_val = self.meta_learner.predict(meta_val)
        f1_val = f1_score(y_val, y_pred_val, zero_division=0)

        logger.info(f"  Meta-learner entrenado. F1 en validacion: {f1_val:.4f}")

        # Mostrar coeficientes del meta-learner (importancia de cada modelo base)
        model_names = list(self.models.keys())
        coefs = self.meta_learner.coef_[0]
        for name, coef in zip(model_names, coefs):
            logger.info(f"    Coeficiente de '{name}': {coef:.4f}")

        return self.meta_learner

    def predict_stacking(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predice usando el meta-learner de stacking.

        Genera meta-features (probabilidades de modelos base) y las pasa
        al meta-learner para obtener la prediccion final.

        Args:
            X: Features para predecir.

        Returns:
            Array de probabilidades (clase positiva) del meta-learner.

        Raises:
            ValueError: Si el meta-learner no ha sido entrenado.
        """
        if self.meta_learner is None:
            raise ValueError(
                "El meta-learner no ha sido entrenado. "
                "Ejecuta stacking(X_train, y_train, X_val, y_val) primero."
            )

        meta_features = self._build_meta_features(X)
        proba = self.meta_learner.predict_proba(meta_features)

        # Probabilidad de clase positiva
        if proba.ndim == 2 and proba.shape[1] >= 2:
            return proba[:, 1]
        return proba[:, 0]

    # ============================================================
    # EVALUACION DEL ENSEMBLE
    # ============================================================

    def evaluate_ensemble(
        self,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        X_train: Optional[pd.DataFrame] = None,
        y_train: Optional[pd.Series] = None,
    ) -> dict:
        """
        Compara: cada modelo individual vs soft_voting vs weighted_voting vs stacking.

        Calcula F1, Precision, Recall, Accuracy y ROC-AUC para cada estrategia.
        Guarda los resultados en self.evaluation_results y determina el mejor metodo.

        Si X_train y y_train se proporcionan, tambien entrena y evalua stacking.
        Si no, stacking se omite.

        Args:
            X_val: Features de validacion.
            y_val: Labels de validacion (0/1).
            X_train: Features de entrenamiento (necesario para stacking).
            y_train: Labels de entrenamiento (necesario para stacking).

        Returns:
            Dict con metricas por metodo:
            {
                "random_forest": {"f1": 0.65, "precision": 0.70, ...},
                "xgboost": {"f1": 0.72, ...},
                "lightgbm": {"f1": 0.68, ...},
                "soft_voting": {"f1": 0.74, ...},
                "weighted_voting": {"f1": 0.75, ...},
                "stacking": {"f1": 0.76, ...},  # Solo si se dieron X_train/y_train
            }
        """
        logger.info("=" * 60)
        logger.info("EVALUACION DE ENSEMBLE")
        logger.info("=" * 60)

        results = {}

        # --- 1. Evaluar cada modelo individual ---
        for name, model in self.models.items():
            logger.info(f"\nEvaluando modelo individual: {name}")
            # Extraer estimador base para evitar que SMOTE corrompa datos
            estimator = self._extract_estimator(model)
            metrics = self._evaluate_model_predictions(
                y_val,
                estimator.predict(X_val),
                estimator.predict_proba(X_val),
            )
            results[name] = metrics
            self.val_scores[name] = metrics["f1"]
            logger.info(
                f"  {name}: F1={metrics['f1']:.4f}, "
                f"P={metrics['precision']:.4f}, R={metrics['recall']:.4f}"
            )

        # --- 2. Soft Voting ---
        logger.info("\nEvaluando soft voting...")
        soft_probs = self.soft_voting(X_val)
        soft_preds = (soft_probs >= 0.5).astype(int)
        results["soft_voting"] = self._evaluate_model_predictions(
            y_val, soft_preds, soft_probs
        )
        logger.info(
            f"  soft_voting: F1={results['soft_voting']['f1']:.4f}, "
            f"P={results['soft_voting']['precision']:.4f}, "
            f"R={results['soft_voting']['recall']:.4f}"
        )

        # --- 3. Weighted Voting (pesos basados en F1 individual) ---
        logger.info("\nEvaluando weighted voting...")
        weighted_probs = self.weighted_voting(X_val)
        weighted_preds = (weighted_probs >= 0.5).astype(int)
        results["weighted_voting"] = self._evaluate_model_predictions(
            y_val, weighted_preds, weighted_probs
        )
        logger.info(
            f"  weighted_voting: F1={results['weighted_voting']['f1']:.4f}, "
            f"P={results['weighted_voting']['precision']:.4f}, "
            f"R={results['weighted_voting']['recall']:.4f}"
        )

        # --- 4. Stacking (solo si hay datos de entrenamiento) ---
        if X_train is not None and y_train is not None:
            logger.info("\nEvaluando stacking...")
            self.stacking(X_train, y_train, X_val, y_val)
            stacking_probs = self.predict_stacking(X_val)
            stacking_preds = (stacking_probs >= 0.5).astype(int)
            results["stacking"] = self._evaluate_model_predictions(
                y_val, stacking_preds, stacking_probs
            )
            logger.info(
                f"  stacking: F1={results['stacking']['f1']:.4f}, "
                f"P={results['stacking']['precision']:.4f}, "
                f"R={results['stacking']['recall']:.4f}"
            )
        else:
            logger.info(
                "\nStacking omitido (necesita X_train y y_train). "
                "Pasa estos parametros para incluir stacking en la evaluacion."
            )

        # --- Guardar resultados y determinar mejor metodo ---
        self.evaluation_results = results
        self.best_method_name = max(
            results, key=lambda k: results[k]["f1"]
        )

        # --- Resumen ---
        logger.info("\n" + "=" * 60)
        logger.info("RESUMEN DE ENSEMBLE")
        logger.info("=" * 60)
        for method, metrics in sorted(
            results.items(), key=lambda x: -x[1]["f1"]
        ):
            marker = " <-- MEJOR" if method == self.best_method_name else ""
            logger.info(
                f"  {method:20s}: F1={metrics['f1']:.4f}, "
                f"P={metrics['precision']:.4f}, "
                f"R={metrics['recall']:.4f}, "
                f"AUC={metrics.get('roc_auc', 'N/A')}{marker}"
            )

        return results

    def get_best_method(self) -> str:
        """
        Retorna el nombre del mejor metodo segun F1 de validacion.

        Returns:
            Nombre del metodo (ej: "weighted_voting", "stacking", "xgboost").

        Raises:
            ValueError: Si no se ha ejecutado evaluate_ensemble() aun.
        """
        if self.best_method_name is None:
            raise ValueError(
                "No se ha evaluado el ensemble todavia. "
                "Ejecuta evaluate_ensemble(X_val, y_val) primero."
            )
        return self.best_method_name

    # ============================================================
    # METODOS AUXILIARES (PRIVADOS)
    # ============================================================

    def _collect_probabilities(self, X: pd.DataFrame) -> list[np.ndarray]:
        """
        Recolecta probabilidades de clase positiva de todos los modelos.

        Args:
            X: Features para predecir.

        Returns:
            Lista de arrays, uno por modelo, con probabilidades de clase 1.
        """
        all_probs = []

        for name, model in self.models.items():
            try:
                # Extraer estimador base para evitar que SMOTE corrompa datos
                estimator = self._extract_estimator(model)
                proba = estimator.predict_proba(X)
                # Tomar probabilidad de clase positiva (columna 1)
                if proba.ndim == 2 and proba.shape[1] >= 2:
                    prob_positive = proba[:, 1]
                else:
                    prob_positive = proba[:, 0]
                all_probs.append(prob_positive)
            except Exception as e:
                logger.warning(
                    f"Error obteniendo probabilidades de '{name}': {e}. "
                    "Este modelo sera excluido del ensemble."
                )

        if not all_probs:
            raise ValueError(
                "Ningun modelo pudo generar probabilidades. "
                "Verifica que los modelos tengan predict_proba()."
            )

        return all_probs

    def _build_meta_features(self, X: pd.DataFrame) -> np.ndarray:
        """
        Construye meta-features para stacking (probabilidades de modelos base).

        Cada modelo base genera su probabilidad de clase positiva, y estas
        se concatenan en una matriz donde cada columna es un modelo.

        Args:
            X: Features originales.

        Returns:
            Array (n_samples, n_modelos) con probabilidades de cada modelo.
        """
        probs = self._collect_probabilities(X)
        # Apilar como columnas: cada modelo es una feature para el meta-learner
        return np.column_stack(probs)

    def _evaluate_model_predictions(
        self,
        y_true: pd.Series,
        y_pred: np.ndarray,
        y_prob: np.ndarray,
    ) -> dict:
        """
        Calcula metricas de clasificacion binaria.

        Args:
            y_true: Labels verdaderos (0/1).
            y_pred: Labels predichos (0/1).
            y_prob: Probabilidades predichas (puede ser array 1D o 2D).

        Returns:
            Dict con: accuracy, precision, recall, f1, roc_auc.
        """
        # Asegurar que y_prob sea 1D (probabilidad de clase positiva)
        if isinstance(y_prob, np.ndarray) and y_prob.ndim == 2:
            if y_prob.shape[1] >= 2:
                prob_positive = y_prob[:, 1]
            else:
                prob_positive = y_prob[:, 0]
        else:
            prob_positive = y_prob

        metrics = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        }

        # ROC-AUC solo si hay 2 clases
        try:
            if len(np.unique(y_true)) >= 2:
                metrics["roc_auc"] = float(roc_auc_score(y_true, prob_positive))
            else:
                metrics["roc_auc"] = None
        except ValueError:
            metrics["roc_auc"] = None

        return metrics
