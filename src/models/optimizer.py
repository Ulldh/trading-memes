"""
optimizer.py - Optimizacion de features y modelos ML.

Este modulo proporciona herramientas para mejorar los modelos una vez
que se tiene un dataset de 300+ tokens etiquetados:

1. Eliminacion de features correlacionados (reducir redundancia).
2. GridSearchCV para Random Forest (buscar mejores hiperparametros).
3. GridSearchCV para XGBoost (buscar mejores hiperparametros).
4. Ensemble VotingClassifier (combinar RF + XGB para mejor rendimiento).

Clase:
    ModelOptimizer: Interfaz para optimizacion de modelos.

Dependencias:
    - scikit-learn: Para GridSearchCV, VotingClassifier, metricas.
    - xgboost: Para XGBClassifier.
    - numpy/pandas: Para manipulacion de datos.
    - joblib: Para guardar modelos optimizados.

Uso:
    from src.models.optimizer import ModelOptimizer

    optimizer = ModelOptimizer()

    # 1. Eliminar features correlacionados
    X_clean = optimizer.remove_correlated_features(X_train, threshold=0.95)

    # 2. Optimizar RF
    best_rf = optimizer.tune_random_forest(X_train, y_train)

    # 3. Optimizar XGBoost
    best_xgb = optimizer.tune_xgboost(X_train, y_train)

    # 4. Crear ensemble
    ensemble = optimizer.create_ensemble(X_train, y_train)
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.metrics import f1_score, make_scorer

from xgboost import XGBClassifier

from src.utils.logger import get_logger

try:
    from config import ML_CONFIG, MODELS_DIR
except ImportError:
    ML_CONFIG = {"random_seed": 42, "cv_folds": 5}
    MODELS_DIR = Path("data/models")

logger = get_logger(__name__)


class ModelOptimizer:
    """
    Optimizacion de features y modelos de clasificacion.

    Diseñado para usarse cuando el dataset tiene 300+ tokens etiquetados,
    lo cual permite GridSearchCV con cross-validation confiable.

    Args:
        random_seed: Semilla para reproducibilidad.
        cv_folds: Numero de folds para cross-validation.

    Atributos:
        best_models: Dict con los mejores modelos encontrados.
        best_params: Dict con los mejores hiperparametros.
        cv_results: Dict con resultados detallados de GridSearchCV.
    """

    def __init__(self, random_seed: int = 42, cv_folds: int = 5):
        self.random_seed = random_seed
        self.cv_folds = cv_folds
        self.best_models: dict = {}
        self.best_params: dict = {}
        self.cv_results: dict = {}
        self.removed_features: list = []

    # ============================================================
    # 1. ELIMINACION DE FEATURES CORRELACIONADOS
    # ============================================================

    def remove_correlated_features(
        self,
        X: pd.DataFrame,
        threshold: float = 0.95,
    ) -> pd.DataFrame:
        """
        Elimina features con correlacion de Pearson > threshold.

        Cuando dos features estan muy correlacionados (ej: >0.95),
        aportan informacion redundante al modelo. Eliminar uno de
        los dos simplifica el modelo sin perder poder predictivo.

        Para cada par correlacionado, se elimina el que tiene menor
        correlacion promedio con el target (si esta disponible) o
        simplemente el segundo feature del par.

        Args:
            X: DataFrame con features.
            threshold: Umbral de correlacion (0.0 - 1.0).
                       Features con correlacion > threshold se eliminan.

        Returns:
            DataFrame con features filtrados (sin los correlacionados).
        """
        logger.info(f"Buscando features correlacionados (threshold={threshold})...")
        logger.info(f"Features iniciales: {X.shape[1]}")

        # Calcular matriz de correlacion (valor absoluto)
        corr_matrix = X.corr().abs()

        # Obtener triangulo superior (evitar pares duplicados)
        upper_triangle = corr_matrix.where(
            np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
        )

        # Encontrar features a eliminar
        to_drop = set()
        correlated_pairs = []

        for col in upper_triangle.columns:
            # Features con correlacion > threshold con este feature
            highly_correlated = upper_triangle.index[
                upper_triangle[col] > threshold
            ].tolist()

            for corr_feature in highly_correlated:
                correlated_pairs.append(
                    (col, corr_feature, corr_matrix.loc[col, corr_feature])
                )
                # Eliminar el que tiene menor varianza (menos informativo)
                if X[col].var() >= X[corr_feature].var():
                    to_drop.add(corr_feature)
                else:
                    to_drop.add(col)

        # Reportar pares encontrados
        if correlated_pairs:
            logger.info(f"Pares altamente correlacionados ({len(correlated_pairs)}):")
            for f1, f2, corr in sorted(correlated_pairs, key=lambda x: -x[2])[:10]:
                logger.info(f"  {f1} <-> {f2}: {corr:.4f}")

        # Eliminar features
        self.removed_features = list(to_drop)
        X_clean = X.drop(columns=list(to_drop))

        logger.info(
            f"Features eliminados: {len(to_drop)} "
            f"({X.shape[1]} -> {X_clean.shape[1]})"
        )

        return X_clean

    # ============================================================
    # 2. OPTIMIZACION DE RANDOM FOREST
    # ============================================================

    def tune_random_forest(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> RandomForestClassifier:
        """
        GridSearchCV para encontrar los mejores hiperparametros de RF.

        Busca combinaciones de:
        - n_estimators: 100, 300, 500
        - max_depth: 5, 10, 15, None
        - min_samples_split: 2, 5, 10
        - min_samples_leaf: 1, 3, 5

        La metrica de optimizacion es F1 (la mas relevante para
        datos desbalanceados como los nuestros).

        Args:
            X_train: Features de entrenamiento.
            y_train: Labels de entrenamiento.

        Returns:
            Mejor modelo RandomForestClassifier encontrado.
        """
        logger.info("=" * 60)
        logger.info("OPTIMIZANDO RANDOM FOREST (GridSearchCV)")
        logger.info("=" * 60)

        # Espacio de busqueda (reducido para eficiencia)
        param_grid = {
            "n_estimators": [100, 300, 500],
            "max_depth": [5, 10, 15, None],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 3, 5],
        }

        # Modelo base
        rf = RandomForestClassifier(
            class_weight="balanced",
            random_state=self.random_seed,
            n_jobs=-1,
        )

        # Cross-validation estratificada
        cv = StratifiedKFold(
            n_splits=self.cv_folds,
            shuffle=True,
            random_state=self.random_seed,
        )

        # Scorer: F1 binario
        scorer = make_scorer(f1_score, zero_division=0)

        # GridSearchCV
        total_combinaciones = 1
        for v in param_grid.values():
            total_combinaciones *= len(v)
        logger.info(
            f"Probando {total_combinaciones} combinaciones "
            f"x {self.cv_folds} folds = {total_combinaciones * self.cv_folds} fits"
        )

        grid_search = GridSearchCV(
            rf, param_grid,
            cv=cv,
            scoring=scorer,
            n_jobs=-1,
            verbose=1,
            refit=True,
        )

        grid_search.fit(X_train, y_train)

        # Resultados
        best_model = grid_search.best_estimator_
        best_params = grid_search.best_params_
        best_score = grid_search.best_score_

        logger.info(f"Mejor F1 (CV): {best_score:.4f}")
        logger.info(f"Mejores parametros: {best_params}")

        # Guardar resultados
        self.best_models["random_forest_v2"] = best_model
        self.best_params["random_forest_v2"] = best_params
        self.cv_results["random_forest_v2"] = {
            "best_f1_cv": float(best_score),
            "best_params": best_params,
        }

        return best_model

    # ============================================================
    # 3. OPTIMIZACION DE XGBOOST
    # ============================================================

    def tune_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> XGBClassifier:
        """
        GridSearchCV para encontrar los mejores hiperparametros de XGBoost.

        Busca combinaciones de:
        - learning_rate: 0.01, 0.05, 0.1
        - n_estimators: 100, 300, 500
        - max_depth: 3, 5, 7
        - subsample: 0.7, 0.8, 0.9

        Args:
            X_train: Features de entrenamiento.
            y_train: Labels de entrenamiento.

        Returns:
            Mejor modelo XGBClassifier encontrado.
        """
        logger.info("=" * 60)
        logger.info("OPTIMIZANDO XGBOOST (GridSearchCV)")
        logger.info("=" * 60)

        # Calcular scale_pos_weight
        n_neg = int((y_train == 0).sum())
        n_pos = int((y_train == 1).sum())
        scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

        # Espacio de busqueda
        param_grid = {
            "learning_rate": [0.01, 0.05, 0.1],
            "n_estimators": [100, 300, 500],
            "max_depth": [3, 5, 7],
            "subsample": [0.7, 0.8, 0.9],
        }

        # Modelo base
        xgb = XGBClassifier(
            scale_pos_weight=scale_pos_weight,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=self.random_seed,
        )

        # Cross-validation
        cv = StratifiedKFold(
            n_splits=self.cv_folds,
            shuffle=True,
            random_state=self.random_seed,
        )

        scorer = make_scorer(f1_score, zero_division=0)

        total_combinaciones = 1
        for v in param_grid.values():
            total_combinaciones *= len(v)
        logger.info(
            f"Probando {total_combinaciones} combinaciones "
            f"x {self.cv_folds} folds = {total_combinaciones * self.cv_folds} fits"
        )

        grid_search = GridSearchCV(
            xgb, param_grid,
            cv=cv,
            scoring=scorer,
            n_jobs=-1,
            verbose=1,
            refit=True,
        )

        grid_search.fit(X_train, y_train)

        # Resultados
        best_model = grid_search.best_estimator_
        best_params = grid_search.best_params_
        best_score = grid_search.best_score_

        logger.info(f"Mejor F1 (CV): {best_score:.4f}")
        logger.info(f"Mejores parametros: {best_params}")

        self.best_models["xgboost_v2"] = best_model
        self.best_params["xgboost_v2"] = best_params
        self.cv_results["xgboost_v2"] = {
            "best_f1_cv": float(best_score),
            "best_params": best_params,
        }

        return best_model

    # ============================================================
    # 4. ENSEMBLE (VotingClassifier)
    # ============================================================

    def create_ensemble(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        rf_model: Optional[RandomForestClassifier] = None,
        xgb_model: Optional[XGBClassifier] = None,
    ) -> VotingClassifier:
        """
        Crea un VotingClassifier soft con RF + XGBoost.

        Soft voting: promedia las probabilidades de ambos modelos.
        Es mejor que hard voting cuando los modelos estan calibrados.

        Args:
            X_train: Features de entrenamiento.
            y_train: Labels de entrenamiento.
            rf_model: Modelo RF optimizado (si None, usa el de best_models).
            xgb_model: Modelo XGB optimizado (si None, usa el de best_models).

        Returns:
            VotingClassifier entrenado.
        """
        logger.info("=" * 60)
        logger.info("CREANDO ENSEMBLE (VotingClassifier)")
        logger.info("=" * 60)

        # Usar modelos optimizados o los que se pasen
        rf = rf_model or self.best_models.get("random_forest_v2")
        xgb = xgb_model or self.best_models.get("xgboost_v2")

        if rf is None or xgb is None:
            raise ValueError(
                "Se necesitan modelos RF y XGB. "
                "Ejecuta tune_random_forest() y tune_xgboost() primero."
            )

        # Crear ensemble con soft voting
        ensemble = VotingClassifier(
            estimators=[
                ("rf", rf),
                ("xgb", xgb),
            ],
            voting="soft",
            # Pesos: dar un poco mas de peso al modelo con mejor F1
            weights=[1.0, 1.0],  # Se ajustan despues de ver resultados
        )

        logger.info("Entrenando ensemble...")
        ensemble.fit(X_train, y_train)

        # Cross-validation del ensemble
        cv = StratifiedKFold(
            n_splits=self.cv_folds,
            shuffle=True,
            random_state=self.random_seed,
        )
        scorer = make_scorer(f1_score, zero_division=0)

        from sklearn.model_selection import cross_val_score
        cv_scores = cross_val_score(
            ensemble, X_train, y_train,
            cv=cv, scoring=scorer, n_jobs=-1,
        )

        logger.info(
            f"Ensemble CV F1: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})"
        )

        self.best_models["ensemble_v1"] = ensemble
        self.cv_results["ensemble_v1"] = {
            "best_f1_cv": float(cv_scores.mean()),
            "f1_std": float(cv_scores.std()),
        }

        return ensemble

    # ============================================================
    # GUARDAR MODELOS OPTIMIZADOS
    # ============================================================

    def save_optimized_models(self, path: Optional[Path] = None):
        """
        Guarda los modelos optimizados en disco.

        Args:
            path: Directorio de destino. Por defecto usa MODELS_DIR.
        """
        save_dir = Path(path) if path else MODELS_DIR
        save_dir.mkdir(parents=True, exist_ok=True)

        for name, model in self.best_models.items():
            filepath = save_dir / f"{name}.joblib"
            joblib.dump(model, filepath)
            logger.info(f"Modelo '{name}' guardado en: {filepath}")

        # Guardar metadata de optimizacion
        metadata = {
            "best_params": self.best_params,
            "cv_results": self.cv_results,
            "removed_features": self.removed_features,
        }
        metadata_path = save_dir / "optimization_metadata.joblib"
        joblib.dump(metadata, metadata_path)
        logger.info(f"Metadata de optimizacion guardada en: {metadata_path}")

    # ============================================================
    # RESUMEN DE OPTIMIZACION
    # ============================================================

    def summary(self) -> pd.DataFrame:
        """
        Devuelve un DataFrame con el resumen de todos los modelos optimizados.

        Returns:
            DataFrame con columnas: modelo, f1_cv, parametros.
        """
        rows = []
        for name, results in self.cv_results.items():
            rows.append({
                "modelo": name,
                "f1_cv": results.get("best_f1_cv", 0.0),
                "parametros": str(results.get("best_params", {})),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("f1_cv", ascending=False).reset_index(drop=True)

        return df
