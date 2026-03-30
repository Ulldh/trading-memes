"""
feature_selector.py - Seleccion automatica de features para reducir ruido y overfitting.

Este modulo proporciona herramientas para filtrar features que no aportan
valor predictivo o que introducen ruido/multicolinealidad:

1. Filtro por varianza: elimina features con varianza near-zero (constantes).
2. Filtro por correlacion: elimina features redundantes (correlacion alta).
3. Filtro por importancia: elimina features con importancia negligible.
4. Seleccion top-K: selecciona las K features mas importantes.
5. Pipeline automatico: ejecuta todos los filtros en secuencia.

El objetivo es reducir el numero de features de ~57 a ~25-30, eliminando
ruido que causa overfitting (especialmente en XGBoost, donde CV_F1=0.726
pero Val_F1=0.595).

Clases:
    FeatureSelector: Seleccion y filtrado de features.

Dependencias:
    - pandas: Para manipulacion de DataFrames.
    - numpy: Para calculos numericos.
    - scikit-learn: Para VarianceThreshold (opcional).
"""

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


class FeatureSelector:
    """
    Seleccion de features para reducir ruido y overfitting.

    Aplica una serie de filtros para eliminar features que:
    - Tienen varianza near-zero (no discriminan entre clases).
    - Son altamente correlacionadas entre si (informacion redundante).
    - Tienen importancia negligible segun el modelo (ruido).

    El pipeline completo (auto_select) ejecuta los tres filtros en orden:
    varianza -> correlacion -> importancia.

    Ejemplo:
        selector = FeatureSelector(X_train, y_train, feature_names)

        # Pipeline automatico
        X_filtered, selected = selector.auto_select(rf_model)
        print(f"Features: {len(feature_names)} -> {len(selected)}")

        # O filtros individuales
        low_var = selector.filter_by_variance(min_variance=0.01)
        high_corr = selector.filter_by_correlation(threshold=0.95)
        low_imp = selector.filter_by_importance(model, min_importance=0.01)

    Args:
        X_train: DataFrame con features de entrenamiento.
        y_train: Serie con labels de entrenamiento.
        feature_names: Lista con nombres de todas las features.
    """

    def __init__(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        feature_names: list[str],
    ):
        """
        Inicializa el selector con los datos de entrenamiento.

        Args:
            X_train: DataFrame con features de entrenamiento (filas=tokens, cols=features).
            y_train: Serie con labels de entrenamiento (0/1 para binario).
            feature_names: Lista con los nombres de las features (columnas de X_train).
        """
        self.X_train = X_train.copy()
        self.y_train = y_train.copy()
        self.feature_names = list(feature_names)

        # Registro de features eliminadas por cada filtro (para trazabilidad)
        self.removal_log: dict[str, list[str]] = {
            "variance": [],
            "correlation": [],
            "importance": [],
        }

        logger.info(
            f"FeatureSelector inicializado con {len(feature_names)} features, "
            f"{len(X_train)} muestras"
        )

    # ============================================================
    # FILTRO 1: VARIANZA NEAR-ZERO
    # ============================================================

    def filter_by_variance(
        self,
        min_variance: float = 0.001,
        min_remaining: int = 20,
    ) -> list[str]:
        """
        Identifica features con varianza menor al umbral (near-zero variance).

        Features con varianza muy baja son practicamente constantes y no
        aportan informacion discriminativa. Ejemplo: si el 99% de los tokens
        tienen el mismo valor en una feature, esa feature no ayuda al modelo.

        La varianza se calcula sobre los datos normalizados (0-1) para que
        sea comparable entre features con diferentes escalas.

        NOTA: En datos crypto, muchas features tienen baja varianza por diseño
        (flags booleanos como has_mint_authority, metricas de concentracion
        cercanas a 0, etc.) pero son altamente predictivas. Por eso el umbral
        default es conservador (0.001) y se garantiza un minimo de features.

        Args:
            min_variance: Umbral minimo de varianza (default 0.001).
                          Features con varianza < min_variance se eliminan.
            min_remaining: Numero minimo de features que deben quedar (default 20).
                           Si eliminar por varianza dejaria menos de min_remaining
                           features, se conservan las top-N por varianza en lugar
                           de eliminar todas las que estan bajo el umbral.

        Returns:
            Lista de nombres de features a eliminar (varianza near-zero).
        """
        logger.info(f"Filtro de varianza: umbral={min_variance}, min_remaining={min_remaining}")

        # Calcular varianza normalizada de cada feature
        variance_scores = {}
        features_to_remove = []

        for col in self.feature_names:
            if col not in self.X_train.columns:
                continue

            col_data = self.X_train[col]

            # Normalizar a 0-1 para comparar varianzas entre features
            col_range = col_data.max() - col_data.min()
            if col_range == 0:
                # Feature completamente constante
                variance_scores[col] = 0.0
                features_to_remove.append(col)
                logger.debug(f"  {col}: constante (varianza=0)")
                continue

            # Varianza normalizada (entre 0 y ~0.25 para distribuciones uniformes)
            normalized = (col_data - col_data.min()) / col_range
            variance = normalized.var()
            variance_scores[col] = variance

            if variance < min_variance:
                features_to_remove.append(col)
                logger.debug(f"  {col}: varianza normalizada={variance:.6f} < {min_variance}")

        # Proteccion: si eliminar dejaria menos de min_remaining features,
        # conservar las top-N por varianza en lugar de eliminar todas
        total_available = len([f for f in self.feature_names if f in self.X_train.columns])
        remaining_after = total_available - len(features_to_remove)

        if remaining_after < min_remaining and len(features_to_remove) > 0:
            logger.warning(
                f"Eliminar {len(features_to_remove)} features dejaria solo "
                f"{remaining_after} (minimo requerido: {min_remaining}). "
                f"Ajustando: solo se eliminan las de menor varianza."
            )
            # Ordenar candidatos a eliminar por varianza (menor primero)
            # Solo eliminar las que permitan mantener min_remaining
            max_to_remove = max(0, total_available - min_remaining)
            sorted_candidates = sorted(features_to_remove, key=lambda f: variance_scores.get(f, 0.0))
            features_to_remove = sorted_candidates[:max_to_remove]
            logger.info(
                f"  Ajustado: eliminando {len(features_to_remove)} de "
                f"{len(sorted_candidates)} candidatas (conservando min_remaining={min_remaining})"
            )

        self.removal_log["variance"] = features_to_remove
        logger.info(
            f"Varianza: {len(features_to_remove)} features a eliminar "
            f"de {len(self.feature_names)}"
        )
        if features_to_remove:
            logger.info(f"  Features eliminadas: {features_to_remove}")

        return features_to_remove

    # ============================================================
    # FILTRO 2: CORRELACION ALTA
    # ============================================================

    def filter_by_correlation(
        self,
        threshold: float = 0.95,
        importance_scores: dict[str, float] | None = None,
    ) -> list[str]:
        """
        Identifica features con correlacion > threshold (redundancia).

        Cuando dos features estan altamente correlacionadas, contienen
        informacion redundante. Mantener ambas:
        - Aumenta la dimensionalidad sin aportar informacion nueva.
        - Puede inflar la importancia de features correlacionadas.
        - Hace al modelo mas sensible a ruido.

        Para cada par correlacionado, se elimina la feature con menor
        importancia (si se proporcionan scores) o la segunda del par.

        Args:
            threshold: Umbral de correlacion absoluta (default 0.95).
                       Pares con |correlacion| > threshold se consideran redundantes.
            importance_scores: Diccionario {feature: importancia} para decidir
                               cual eliminar de cada par. Si None, se elimina
                               la segunda del par encontrado.

        Returns:
            Lista de nombres de features a eliminar (alta correlacion).
        """
        logger.info(f"Filtro de correlacion: umbral={threshold}")

        # Calcular matriz de correlacion (Pearson)
        # Solo usar features que existen en X_train
        available = [f for f in self.feature_names if f in self.X_train.columns]
        corr_matrix = self.X_train[available].corr().abs()

        # Mascara triangular superior (evitar contar pares dos veces)
        upper_triangle = np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)

        features_to_remove = set()
        corr_pairs = []

        # Recorrer pares con correlacion > threshold
        for i in range(len(available)):
            for j in range(i + 1, len(available)):
                if not upper_triangle[i, j]:
                    continue

                corr_value = corr_matrix.iloc[i, j]
                if corr_value > threshold:
                    feat_i = available[i]
                    feat_j = available[j]
                    corr_pairs.append((feat_i, feat_j, corr_value))

                    # Decidir cual eliminar
                    if importance_scores:
                        imp_i = importance_scores.get(feat_i, 0)
                        imp_j = importance_scores.get(feat_j, 0)
                        # Eliminar la menos importante
                        if imp_i >= imp_j:
                            features_to_remove.add(feat_j)
                        else:
                            features_to_remove.add(feat_i)
                    else:
                        # Sin scores de importancia, eliminar la segunda
                        features_to_remove.add(feat_j)

        features_to_remove = list(features_to_remove)
        self.removal_log["correlation"] = features_to_remove

        logger.info(
            f"Correlacion: {len(corr_pairs)} pares con |r|>{threshold}, "
            f"{len(features_to_remove)} features a eliminar"
        )
        for f1, f2, r in corr_pairs:
            logger.debug(f"  {f1} <-> {f2}: r={r:.4f}")
        if features_to_remove:
            logger.info(f"  Features eliminadas: {sorted(features_to_remove)}")

        return features_to_remove

    # ============================================================
    # FILTRO 3: IMPORTANCIA BAJA
    # ============================================================

    def filter_by_importance(
        self,
        model,
        min_importance: float = 0.01,
    ) -> list[str]:
        """
        Identifica features con importancia menor al umbral.

        Usa feature_importances_ del modelo (disponible en RF y XGBoost).
        Features con importancia < min_importance no contribuyen significativamente
        a las predicciones y solo agregan ruido.

        Nota: para modelos envueltos en ImbPipeline (SMOTE + clasificador),
        se accede al clasificador via model.named_steps['classifier'].

        Args:
            model: Modelo entrenado con atributo feature_importances_.
                   Puede ser un modelo directo (RF, XGB) o un ImbPipeline.
            min_importance: Umbral minimo de importancia normalizada (default 0.01).
                            Features con importancia < min_importance se eliminan.

        Returns:
            Lista de nombres de features a eliminar (baja importancia).
        """
        logger.info(f"Filtro de importancia: umbral={min_importance}")

        # Extraer importancias del modelo (manejar ImbPipeline)
        importances = self._get_feature_importances(model)

        if importances is None:
            logger.warning(
                "No se pudieron obtener feature_importances_. "
                "Retornando lista vacia."
            )
            return []

        # Crear DataFrame con nombre e importancia
        importance_df = pd.DataFrame({
            "feature": self.feature_names[:len(importances)],
            "importance": importances,
        }).sort_values("importance", ascending=False)

        # Features bajo el umbral
        features_to_remove = importance_df[
            importance_df["importance"] < min_importance
        ]["feature"].tolist()

        self.removal_log["importance"] = features_to_remove

        logger.info(
            f"Importancia: {len(features_to_remove)} features con "
            f"importancia < {min_importance}"
        )
        if features_to_remove:
            # Mostrar las features eliminadas con su importancia
            removed_info = importance_df[
                importance_df["feature"].isin(features_to_remove)
            ]
            for _, row in removed_info.iterrows():
                logger.debug(f"  {row['feature']}: {row['importance']:.6f}")
            logger.info(f"  Features eliminadas: {features_to_remove}")

        # Log top 10 features mas importantes (para referencia)
        logger.info("Top 10 features por importancia:")
        for _, row in importance_df.head(10).iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.4f}")

        return features_to_remove

    # ============================================================
    # SELECCION TOP-K
    # ============================================================

    def select_top_k(self, model, k: int = 25) -> list[str]:
        """
        Selecciona las top-K features por importancia del modelo.

        En lugar de eliminar features por debajo de un umbral, selecciona
        directamente las K mas importantes. Util cuando se quiere un numero
        fijo de features.

        Args:
            model: Modelo entrenado con atributo feature_importances_.
                   Puede ser un modelo directo (RF, XGB) o un ImbPipeline.
            k: Numero de features a seleccionar (default 25).

        Returns:
            Lista con los nombres de las top-K features (ordenadas por importancia).
        """
        logger.info(f"Seleccion top-K: k={k}")

        importances = self._get_feature_importances(model)

        if importances is None:
            logger.warning(
                "No se pudieron obtener feature_importances_. "
                "Retornando todas las features."
            )
            return self.feature_names

        # Crear DataFrame y ordenar
        importance_df = pd.DataFrame({
            "feature": self.feature_names[:len(importances)],
            "importance": importances,
        }).sort_values("importance", ascending=False)

        # Limitar k al numero de features disponibles
        k = min(k, len(importance_df))

        selected = importance_df.head(k)["feature"].tolist()

        logger.info(f"Top-{k} features seleccionadas:")
        for i, (_, row) in enumerate(importance_df.head(k).iterrows(), 1):
            logger.info(f"  {i:2d}. {row['feature']}: {row['importance']:.4f}")

        # Importancia acumulada del top-K
        total_importance = importance_df["importance"].sum()
        topk_importance = importance_df.head(k)["importance"].sum()
        logger.info(
            f"Importancia acumulada: {topk_importance:.4f} / {total_importance:.4f} "
            f"({topk_importance/total_importance*100:.1f}%)"
        )

        return selected

    # ============================================================
    # PIPELINE AUTOMATICO
    # ============================================================

    def auto_select(
        self,
        model,
        skip_variance: bool = True,
        min_variance: float = 0.001,
        corr_threshold: float = 0.95,
        min_importance: float = 0.01,
    ) -> tuple[pd.DataFrame, list[str]]:
        """
        Pipeline de seleccion: [varianza] -> correlacion -> importancia.

        Varianza se SALTA por defecto (skip_variance=True) porque en datos
        crypto muchas features son binarias o near-zero por diseño.

        Ejecuta los filtros en secuencia, eliminando features en cada paso.

        Args:
            model: Modelo entrenado (RF o XGB, puede ser ImbPipeline).
            min_variance: Umbral de varianza minima (default 0.01).
            corr_threshold: Umbral de correlacion para eliminar (default 0.95).
            min_importance: Umbral de importancia minima (default 0.01).

        Returns:
            Tupla de:
            - X_filtered: DataFrame filtrado con solo las features seleccionadas.
            - selected_features: Lista de nombres de features que sobrevivieron.
        """
        logger.info("=" * 60)
        logger.info("PIPELINE AUTOMATICO DE SELECCION DE FEATURES")
        logger.info(f"Features iniciales: {len(self.feature_names)}")
        logger.info("=" * 60)

        # Conjunto de features a eliminar (union de todos los filtros)
        all_to_remove = set()

        # --- Paso 1: Filtro de varianza (saltado por defecto en crypto) ---
        if skip_variance:
            logger.info("\n--- Paso 1/3: Filtro de varianza SALTADO (skip_variance=True) ---")
            logger.info("  Razon: features crypto son frecuentemente binarias/near-zero por diseño")
            low_var = []
        else:
            logger.info("\n--- Paso 1/3: Filtro de varianza ---")
            low_var = self.filter_by_variance(min_variance=min_variance)
            all_to_remove.update(low_var)

        # --- Paso 2: Filtro de correlacion ---
        logger.info("\n--- Paso 2/3: Filtro de correlacion ---")
        # Obtener importancias para desempatar pares correlacionados
        importances = self._get_feature_importances(model)
        importance_scores = None
        if importances is not None:
            importance_scores = dict(
                zip(self.feature_names[:len(importances)], importances)
            )
        high_corr = self.filter_by_correlation(
            threshold=corr_threshold,
            importance_scores=importance_scores,
        )
        all_to_remove.update(high_corr)

        # --- Paso 3: Filtro de importancia ---
        logger.info("\n--- Paso 3/3: Filtro de importancia ---")
        low_imp = self.filter_by_importance(model, min_importance=min_importance)
        all_to_remove.update(low_imp)

        # --- Aplicar filtros ---
        selected_features = [
            f for f in self.feature_names
            if f not in all_to_remove and f in self.X_train.columns
        ]

        X_filtered = self.X_train[selected_features].copy()

        # --- Resumen ---
        logger.info("\n" + "=" * 60)
        logger.info("RESUMEN DE SELECCION DE FEATURES")
        logger.info("=" * 60)
        logger.info(f"Features iniciales:  {len(self.feature_names)}")
        logger.info(f"Eliminadas (varianza):    {len(low_var)}")
        logger.info(f"Eliminadas (correlacion): {len(high_corr)}")
        logger.info(f"Eliminadas (importancia): {len(low_imp)}")
        logger.info(f"Total eliminadas (unicas): {len(all_to_remove)}")
        logger.info(f"Features seleccionadas:   {len(selected_features)}")
        logger.info(f"Reduccion: {len(self.feature_names)} -> {len(selected_features)} "
                     f"({(1 - len(selected_features)/len(self.feature_names))*100:.1f}% reduccion)")
        logger.info(f"\nFeatures seleccionadas: {selected_features}")

        return X_filtered, selected_features

    # ============================================================
    # UTILIDADES INTERNAS
    # ============================================================

    def _get_feature_importances(self, model) -> np.ndarray | None:
        """
        Extrae feature_importances_ de un modelo, manejando ImbPipeline.

        Los modelos RF y XGB tienen feature_importances_ directamente.
        Pero cuando se usan con ImbPipeline (SMOTE + clasificador),
        las importancias estan en el paso 'classifier' del pipeline.

        Args:
            model: Modelo entrenado (directo o ImbPipeline).

        Returns:
            Array de importancias (una por feature) o None si no disponible.
        """
        # Caso 1: modelo directo con feature_importances_
        if hasattr(model, "feature_importances_"):
            return model.feature_importances_

        # Caso 2: ImbPipeline (SMOTE + classifier)
        if hasattr(model, "named_steps"):
            classifier = model.named_steps.get("classifier")
            if classifier and hasattr(classifier, "feature_importances_"):
                return classifier.feature_importances_

        # Caso 3: Pipeline de sklearn generico
        if hasattr(model, "steps"):
            # El ultimo paso suele ser el estimador
            last_step = model.steps[-1][1]
            if hasattr(last_step, "feature_importances_"):
                return last_step.feature_importances_

        # Caso 4: CalibratedClassifierCV (wrapper de calibracion)
        if hasattr(model, "estimator"):
            return self._get_feature_importances(model.estimator)

        logger.warning(
            f"Modelo {type(model).__name__} no tiene feature_importances_. "
            "Intentar con un modelo RF o XGBoost."
        )
        return None

    def get_removal_report(self) -> dict:
        """
        Retorna un resumen de las features eliminadas por cada filtro.

        Util para logging, debugging y para incluir en metadata del modelo.

        Returns:
            Diccionario con:
            - "variance": lista de features eliminadas por varianza.
            - "correlation": lista de features eliminadas por correlacion.
            - "importance": lista de features eliminadas por importancia.
            - "total_removed": numero total de features unicas eliminadas.
            - "total_kept": numero de features que sobrevivieron.
        """
        all_removed = set()
        for removed_list in self.removal_log.values():
            all_removed.update(removed_list)

        return {
            "variance": self.removal_log["variance"],
            "correlation": self.removal_log["correlation"],
            "importance": self.removal_log["importance"],
            "total_removed": len(all_removed),
            "total_kept": len(self.feature_names) - len(all_removed),
        }
