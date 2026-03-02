"""
explainer.py - Explicabilidad de modelos con SHAP.

SHAP (SHapley Additive exPlanations) es una tecnica de interpretabilidad
basada en teoria de juegos que explica las predicciones de modelos ML.

Para cada prediccion, SHAP calcula la "contribucion" de cada feature:
- SHAP positivo: El feature empuja la prediccion hacia la clase positiva (gem).
- SHAP negativo: El feature empuja la prediccion hacia la clase negativa (no gem).

Esto permite entender:
- A nivel global: Que features son los mas importantes en general.
- A nivel local: Por que el modelo clasifico un token especifico de cierta forma.

Clases:
    SHAPExplainer: Interfaz de alto nivel para analisis SHAP.

Dependencias:
    - shap: Para calcular valores SHAP y generar graficas.
    - numpy/pandas: Para manipulacion de datos.
    - matplotlib: Para graficas personalizadas.
"""

from typing import Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import shap

from src.utils.logger import get_logger

logger = get_logger(__name__)


class SHAPExplainer:
    """
    Analisis de explicabilidad de modelos basados en arboles con SHAP.

    Usa shap.TreeExplainer, que es optimizado para modelos de arboles
    (Random Forest, XGBoost, LightGBM, etc.) y es mucho mas rapido
    que el KernelExplainer generico.

    Funcionalidades principales:
    - Importancia global de features (summary plot).
    - Explicacion individual de predicciones (force plot).
    - Analisis de dependencia de un feature especifico.
    - Ranking de features mas importantes.
    - Explicacion detallada de tokens individuales.

    Args:
        model: Modelo de arboles entrenado (RF, XGBoost, etc.).
        X_train: DataFrame de features de entrenamiento (para calcular expected value).

    Ejemplo:
        # Crear el explainer despues de entrenar un modelo
        explainer = SHAPExplainer(model=rf_model, X_train=X_train)

        # Ver features mas importantes globalmente
        explainer.plot_summary(X_test)

        # Entender por que un token fue clasificado como "gem"
        explanation = explainer.explain_single_token(X_test, idx=0)
        print(explanation)
    """

    def __init__(self, model, X_train: pd.DataFrame):
        """
        Inicializa el explainer SHAP con TreeExplainer.

        TreeExplainer calcula valores SHAP exactos para modelos de arboles,
        usando un algoritmo optimizado de O(TLD^2) donde T=arboles,
        L=hojas, D=profundidad.

        Args:
            model: Modelo de arboles entrenado (debe ser compatible con
                   shap.TreeExplainer: sklearn RF, XGBoost, LightGBM, etc.).
            X_train: DataFrame usado para entrenamiento. TreeExplainer lo
                     usa internamente para calcular el "expected value" (baseline).
        """
        self.model = model
        self.X_train = X_train

        # Si el modelo es CalibratedClassifierCV, extraer el estimador base
        # porque TreeExplainer no soporta wrappers de calibracion
        from sklearn.calibration import CalibratedClassifierCV
        if isinstance(model, CalibratedClassifierCV):
            base_model = model.calibrated_classifiers_[0].estimator
            logger.info(
                f"Modelo es CalibratedClassifierCV, extrayendo base: "
                f"{type(base_model).__name__}"
            )
        else:
            base_model = model

        logger.info("Inicializando SHAP TreeExplainer...")
        try:
            self.explainer = shap.TreeExplainer(base_model, X_train)
            logger.info("TreeExplainer inicializado correctamente")
        except Exception as e:
            logger.error(
                f"Error al inicializar TreeExplainer: {e}. "
                "Asegurate de que el modelo sea compatible (RF, XGBoost, etc.)."
            )
            raise

    # ============================================================
    # CALCULAR VALORES SHAP
    # ============================================================

    def get_shap_values(self, X: pd.DataFrame) -> np.ndarray:
        """
        Calcula los valores SHAP para un conjunto de muestras.

        Los valores SHAP tienen la misma forma que X:
        - Cada fila corresponde a una muestra (token).
        - Cada columna corresponde a un feature.
        - El valor indica cuanto contribuye ese feature a la prediccion.

        Para clasificacion binaria, devolvemos los SHAP values de la clase positiva.

        Args:
            X: DataFrame con features para los cuales calcular SHAP.

        Returns:
            np.ndarray de shape (n_muestras, n_features) con valores SHAP.
        """
        logger.info(f"Calculando valores SHAP para {len(X)} muestras...")

        shap_values = self.explainer.shap_values(X)

        # Para clasificacion binaria, shap_values puede ser:
        # - Una lista [clase_0, clase_1] (SHAP antiguo)
        # - Un ndarray 3D de shape (n_samples, n_features, n_classes) (SHAP nuevo)
        # Nos interesa la clase positiva (clase 1 = "gem")
        if isinstance(shap_values, list):
            if len(shap_values) == 2:
                shap_values = shap_values[1]
                logger.info(
                    "Usando SHAP values de la clase positiva (gem)"
                )
            else:
                logger.info(
                    f"SHAP values multiclase: {len(shap_values)} clases"
                )
        elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
            # ndarray 3D: (n_samples, n_features, n_classes)
            if shap_values.shape[2] == 2:
                shap_values = shap_values[:, :, 1]
                logger.info(
                    "Usando SHAP values de la clase positiva (gem) [ndarray 3D]"
                )
            else:
                logger.info(
                    f"SHAP values multiclase: {shap_values.shape[2]} clases"
                )

        logger.info(f"Forma de SHAP values: {np.array(shap_values).shape}")
        return np.array(shap_values)

    # ============================================================
    # GRAFICAS: Summary Plot (Importancia Global)
    # ============================================================

    def plot_summary(self, X: pd.DataFrame, max_display: int = 15):
        """
        Genera el summary plot de SHAP (importancia global de features).

        Este grafico muestra:
        - Eje Y: Features ordenados por importancia (|SHAP| medio).
        - Eje X: Valor SHAP (contribucion a la prediccion).
        - Color: Valor real del feature (rojo = alto, azul = bajo).

        Es la grafica mas informativa de SHAP porque muestra no solo
        QUE features son importantes, sino COMO afectan la prediccion.

        Args:
            X: DataFrame con features para el analisis.
            max_display: Numero maximo de features a mostrar (default 15).
        """
        logger.info(f"Generando SHAP summary plot (top {max_display} features)...")

        shap_values = self.get_shap_values(X)

        plt.figure(figsize=(12, 8))
        shap.summary_plot(
            shap_values,
            X,
            max_display=max_display,
            show=False,
        )
        plt.title("SHAP Summary Plot - Importancia Global de Features", fontsize=14, pad=15)
        plt.tight_layout()
        plt.show()

    # ============================================================
    # GRAFICAS: Force Plot (Explicacion Individual)
    # ============================================================

    def plot_force(self, X: pd.DataFrame, idx: int):
        """
        Genera un force plot para una prediccion individual.

        El force plot muestra como cada feature "empuja" la prediccion
        desde el valor base (expected value) hacia la prediccion final.

        - Features en rojo: Empujan hacia la prediccion positiva (gem).
        - Features en azul: Empujan hacia la prediccion negativa (no gem).

        Args:
            X: DataFrame con features.
            idx: Indice de la fila/muestra a explicar.
        """
        if idx < 0 or idx >= len(X):
            logger.error(f"Indice {idx} fuera de rango (0-{len(X)-1})")
            return

        logger.info(f"Generando force plot para muestra {idx}...")

        shap_values = self.get_shap_values(X)

        # Obtener el expected value (valor base del modelo)
        expected_value = self.explainer.expected_value
        # Para binario, puede ser una lista [ev_clase0, ev_clase1]
        if isinstance(expected_value, (list, np.ndarray)):
            if len(expected_value) == 2:
                expected_value = expected_value[1]  # Clase positiva
            else:
                expected_value = expected_value[0]

        # Generar force plot
        # shap.initjs() es necesario para notebooks; en scripts se usa matplotlib
        try:
            shap.force_plot(
                expected_value,
                shap_values[idx],
                X.iloc[idx],
                matplotlib=True,  # Usar matplotlib en lugar de JS
                show=True,
            )
        except Exception as e:
            logger.warning(f"Force plot con matplotlib fallo: {e}. Intentando texto...")
            # Fallback: mostrar los top features como texto
            self._print_force_explanation(
                shap_values[idx], X.iloc[idx], X.columns, expected_value
            )

    def _print_force_explanation(
        self,
        shap_vals: np.ndarray,
        feature_vals: pd.Series,
        feature_names: pd.Index,
        expected_value: float,
    ):
        """
        Muestra la explicacion force como texto formateado (fallback).

        Args:
            shap_vals: Valores SHAP para una muestra.
            feature_vals: Valores reales de los features.
            feature_names: Nombres de los features.
            expected_value: Valor base del modelo.
        """
        # Crear DataFrame con features, valores y SHAP
        explanation_df = pd.DataFrame({
            "feature": feature_names,
            "valor": feature_vals.values,
            "shap": shap_vals,
        })
        explanation_df = explanation_df.sort_values("shap", key=abs, ascending=False)

        print(f"\nValor base (expected value): {expected_value:.4f}")
        print(f"Prediccion: {expected_value + shap_vals.sum():.4f}")
        print("\nTop 10 features que influyen en la prediccion:")
        print("-" * 55)
        for _, row in explanation_df.head(10).iterrows():
            signo = "+" if row["shap"] > 0 else ""
            print(f"  {row['feature']:30s}  valor={row['valor']:.4f}  SHAP={signo}{row['shap']:.4f}")

    # ============================================================
    # GRAFICAS: Dependence Plot
    # ============================================================

    def plot_dependence(self, X: pd.DataFrame, feature: str):
        """
        Genera un dependence plot para un feature especifico.

        Muestra la relacion entre el valor de un feature y su efecto SHAP.
        El color indica la interaccion con otro feature (auto-detectado).

        Util para entender:
        - Si la relacion es lineal, no lineal, o tiene umbrales.
        - Que otro feature interactua con este.

        Args:
            X: DataFrame con features.
            feature: Nombre del feature a analizar.
        """
        if feature not in X.columns:
            logger.error(
                f"Feature '{feature}' no encontrado. "
                f"Features disponibles: {list(X.columns)}"
            )
            return

        logger.info(f"Generando dependence plot para: {feature}")

        shap_values = self.get_shap_values(X)

        plt.figure(figsize=(10, 6))
        shap.dependence_plot(
            feature,
            shap_values,
            X,
            show=False,
        )
        plt.title(f"SHAP Dependence Plot - {feature}", fontsize=14, pad=15)
        plt.tight_layout()
        plt.show()

    # ============================================================
    # RANKING DE FEATURES
    # ============================================================

    def get_top_features(self, X: pd.DataFrame, n: int = 15) -> pd.DataFrame:
        """
        Devuelve los top N features por importancia SHAP (mean |SHAP value|).

        La importancia SHAP es el promedio del valor absoluto de SHAP
        para cada feature a traves de todas las muestras. Es una medida
        mas precisa que la importancia basada en impureza de los arboles.

        Args:
            X: DataFrame con features para calcular SHAP.
            n: Numero de top features a devolver (default 15).

        Returns:
            DataFrame con columnas: feature, mean_abs_shap, ordenado descendente.
        """
        logger.info(f"Calculando top {n} features por importancia SHAP...")

        shap_values = self.get_shap_values(X)

        # Si SHAP values tiene 3 dimensiones (samples, features, classes),
        # tomamos la clase positiva (indice 1) para calcular importancia
        if shap_values.ndim == 3:
            shap_values = shap_values[:, :, 1]

        # Calcular la media del valor absoluto de SHAP por feature
        mean_abs_shap = np.abs(shap_values).mean(axis=0)

        # Crear DataFrame con nombres y valores
        importance_df = pd.DataFrame({
            "feature": X.columns.tolist(),
            "mean_abs_shap": mean_abs_shap,
        })

        # Ordenar por importancia descendente y tomar top N
        importance_df = importance_df.sort_values(
            "mean_abs_shap", ascending=False
        ).head(n).reset_index(drop=True)

        # Agregar ranking (1-indexed)
        importance_df.insert(0, "rank", range(1, len(importance_df) + 1))

        logger.info(f"Top {n} features:")
        for _, row in importance_df.iterrows():
            logger.info(f"  #{row['rank']:2d}  {row['feature']:30s}  SHAP={row['mean_abs_shap']:.6f}")

        return importance_df

    # ============================================================
    # EXPLICACION DE UN TOKEN INDIVIDUAL
    # ============================================================

    def explain_single_token(self, X: pd.DataFrame, idx: int) -> dict:
        """
        Explica la prediccion para un token individual.

        Devuelve las features que mas contribuyeron positiva y negativamente
        a la prediccion de ese token. Util para entender por que el modelo
        clasifico un token como "gem" o "no gem".

        Args:
            X: DataFrame con features.
            idx: Indice de la fila del token a explicar.

        Returns:
            Diccionario con:
            {
                "idx": int,
                "expected_value": float (valor base del modelo),
                "prediction": float (prediccion final),
                "top_positive": DataFrame (features que empujan hacia "gem"),
                "top_negative": DataFrame (features que empujan hacia "no gem"),
                "all_contributions": DataFrame (todos los features ordenados),
            }
        """
        if idx < 0 or idx >= len(X):
            logger.error(f"Indice {idx} fuera de rango (0-{len(X)-1})")
            return {}

        logger.info(f"Explicando prediccion para token en indice {idx}...")

        shap_values = self.get_shap_values(X)

        # Obtener expected value
        expected_value = self.explainer.expected_value
        if isinstance(expected_value, (list, np.ndarray)):
            if len(expected_value) == 2:
                expected_value = float(expected_value[1])
            else:
                expected_value = float(expected_value[0])
        else:
            expected_value = float(expected_value)

        # Si SHAP values tiene 3 dimensiones (samples, features, classes),
        # tomamos la clase positiva (indice 1)
        if shap_values.ndim == 3:
            shap_values = shap_values[:, :, 1]

        # SHAP values y feature values para este token
        token_shap = shap_values[idx]
        token_features = X.iloc[idx]

        # Prediccion = expected_value + suma de SHAP values
        prediction = expected_value + token_shap.sum()

        # Crear DataFrame con todas las contribuciones
        contributions_df = pd.DataFrame({
            "feature": X.columns.tolist(),
            "valor_feature": token_features.values,
            "shap_value": token_shap,
            "abs_shap": np.abs(token_shap),
        })
        contributions_df = contributions_df.sort_values("abs_shap", ascending=False)

        # Separar contribuciones positivas (hacia "gem") y negativas
        top_positive = contributions_df[contributions_df["shap_value"] > 0].head(10).copy()
        top_negative = contributions_df[contributions_df["shap_value"] < 0].head(10).copy()

        # Logging
        logger.info(f"  Expected value (base): {expected_value:.4f}")
        logger.info(f"  Prediccion final:      {prediction:.4f}")
        logger.info(f"  Top features POSITIVOS (empujan hacia gem):")
        for _, row in top_positive.head(5).iterrows():
            logger.info(
                f"    {row['feature']:30s}  valor={row['valor_feature']:.4f}  "
                f"SHAP=+{row['shap_value']:.4f}"
            )
        logger.info(f"  Top features NEGATIVOS (empujan contra gem):")
        for _, row in top_negative.head(5).iterrows():
            logger.info(
                f"    {row['feature']:30s}  valor={row['valor_feature']:.4f}  "
                f"SHAP={row['shap_value']:.4f}"
            )

        return {
            "idx": idx,
            "expected_value": expected_value,
            "prediction": prediction,
            "top_positive": top_positive.reset_index(drop=True),
            "top_negative": top_negative.reset_index(drop=True),
            "all_contributions": contributions_df.reset_index(drop=True),
        }
