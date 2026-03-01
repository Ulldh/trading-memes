"""
evaluator.py - Evaluacion integral de modelos de clasificacion.

Este modulo proporciona herramientas para evaluar modelos entrenados:
- Metricas de clasificacion (precision, recall, F1, AUC).
- Matriz de confusion.
- Curva ROC (Receiver Operating Characteristic).
- Curva Precision-Recall (mas informativa para datos desbalanceados).
- Comparacion lado a lado de multiples modelos.

Clases:
    ModelEvaluator: Evalua y compara modelos de clasificacion.

Dependencias:
    - scikit-learn: Para metricas de clasificacion.
    - matplotlib: Para graficas.
    - numpy: Para operaciones numericas.
    - pandas: Para tablas de comparacion.
"""

from typing import Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Metricas de clasificacion
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    roc_curve,
    average_precision_score,
    precision_recall_curve,
    ConfusionMatrixDisplay,
)

from sklearn.calibration import calibration_curve

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ModelEvaluator:
    """
    Evaluacion integral de modelos de clasificacion binaria.

    Genera metricas detalladas, matrices de confusion, curvas ROC y
    curvas Precision-Recall para cada modelo. Tambien permite comparar
    multiples modelos lado a lado.

    Para datos desbalanceados (como nuestro caso de memecoins, donde
    los "gems" son raros), la curva Precision-Recall y el PR-AUC son
    mas informativos que la curva ROC y el ROC-AUC.

    Ejemplo:
        evaluator = ModelEvaluator()

        # Evaluar un modelo individual
        metrics = evaluator.evaluate(rf_model, X_test, y_test, model_name="Random Forest")
        print(f"F1: {metrics['f1']:.4f}, ROC-AUC: {metrics['roc_auc']:.4f}")

        # Comparar varios modelos
        all_results = {
            "Random Forest": rf_metrics,
            "XGBoost": xgb_metrics,
        }
        comparison_df = evaluator.compare_models(all_results)
        print(comparison_df)

        # Generar graficas
        evaluator.plot_confusion_matrix(y_test, metrics["y_pred"], "Random Forest")
        evaluator.plot_roc_curve(y_test, metrics["y_prob"], "Random Forest")
        evaluator.plot_precision_recall_curve(y_test, metrics["y_prob"], "Random Forest")
    """

    def __init__(self):
        """Inicializa el evaluador. No requiere parametros."""
        pass

    # ============================================================
    # EVALUACION PRINCIPAL
    # ============================================================

    def evaluate(
        self,
        model,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        model_name: str = "model",
    ) -> dict:
        """
        Evaluacion completa de un modelo de clasificacion.

        Genera todas las metricas relevantes para clasificacion binaria:
        - Accuracy: Porcentaje de predicciones correctas (engañoso con datos desbalanceados).
        - Precision: De los que predijo positivos, cuantos realmente lo eran.
        - Recall: De los que realmente eran positivos, cuantos detecto.
        - F1: Media armonica de precision y recall.
        - ROC-AUC: Area bajo la curva ROC (bueno para ranking general).
        - PR-AUC: Area bajo la curva Precision-Recall (mejor para datos desbalanceados).

        Args:
            model: Modelo sklearn/xgboost con metodos predict() y predict_proba().
            X_test: Features del set de test.
            y_test: Labels verdaderos del set de test.
            model_name: Nombre descriptivo del modelo (para logs).

        Returns:
            Diccionario con todas las metricas y predicciones:
            {
                "accuracy": float,
                "precision": float,
                "recall": float,
                "f1": float,
                "roc_auc": float,
                "pr_auc": float,
                "confusion_matrix": list[list[int]],
                "classification_report": str,
                "y_pred": np.ndarray,
                "y_prob": np.ndarray o None,
            }
        """
        logger.info(f"Evaluando modelo: {model_name}")

        # --- Predicciones ---
        y_pred = model.predict(X_test)

        # Intentar obtener probabilidades (necesarias para ROC y PR)
        # predict_proba devuelve [[prob_clase0, prob_clase1], ...] para binario
        y_prob = None
        try:
            y_prob_full = model.predict_proba(X_test)
            # Tomar la probabilidad de la clase positiva (columna 1)
            if y_prob_full.shape[1] == 2:
                y_prob = y_prob_full[:, 1]
            else:
                y_prob = y_prob_full[:, 1] if y_prob_full.shape[1] > 1 else y_prob_full[:, 0]
        except AttributeError:
            logger.warning(
                f"Modelo '{model_name}' no soporta predict_proba(). "
                "ROC-AUC y PR-AUC no estaran disponibles."
            )

        # --- Metricas basicas ---
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        # --- Metricas basadas en probabilidades ---
        roc_auc = None
        pr_auc = None

        if y_prob is not None:
            # Verificar que hay al menos 2 clases en y_test
            unique_classes = np.unique(y_test)
            if len(unique_classes) >= 2:
                try:
                    roc_auc = roc_auc_score(y_test, y_prob)
                except ValueError as e:
                    logger.warning(f"No se pudo calcular ROC-AUC: {e}")

                try:
                    pr_auc = average_precision_score(y_test, y_prob)
                except ValueError as e:
                    logger.warning(f"No se pudo calcular PR-AUC: {e}")
            else:
                logger.warning(
                    f"Solo hay {len(unique_classes)} clase(s) en y_test. "
                    "ROC-AUC y PR-AUC requieren al menos 2 clases."
                )

        # --- Matriz de confusion ---
        cm = confusion_matrix(y_test, y_pred)

        # --- Reporte de clasificacion (texto formateado) ---
        report = classification_report(y_test, y_pred, zero_division=0)

        # --- Logging ---
        logger.info(f"  Accuracy:  {accuracy:.4f}")
        logger.info(f"  Precision: {precision:.4f}")
        logger.info(f"  Recall:    {recall:.4f}")
        logger.info(f"  F1:        {f1:.4f}")
        if roc_auc is not None:
            logger.info(f"  ROC-AUC:   {roc_auc:.4f}")
        if pr_auc is not None:
            logger.info(f"  PR-AUC:    {pr_auc:.4f}")

        # --- Construir diccionario de resultados ---
        results = {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "roc_auc": float(roc_auc) if roc_auc is not None else None,
            "pr_auc": float(pr_auc) if pr_auc is not None else None,
            "confusion_matrix": cm.tolist(),  # Convertir a lista para serializacion
            "classification_report": report,
            "y_pred": y_pred,
            "y_prob": y_prob,
        }

        # --- Buscar threshold optimo si hay probabilidades ---
        if y_prob is not None and len(np.unique(y_test)) >= 2:
            try:
                threshold_results = self.find_optimal_threshold(y_test, y_prob)
                results["optimal_threshold"] = threshold_results
                logger.info(
                    f"  Threshold optimo: {threshold_results['best_threshold']:.2f} "
                    f"(F1={threshold_results['best_f1']:.4f})"
                )
            except Exception as e:
                logger.warning(f"No se pudo calcular threshold optimo: {e}")

        return results

    # ============================================================
    # COMPARACION DE MODELOS
    # ============================================================

    def compare_models(self, results: dict) -> pd.DataFrame:
        """
        Compara multiples modelos lado a lado en una tabla.

        Crea un DataFrame donde cada fila es un modelo y las columnas
        son las metricas principales (accuracy, precision, recall, f1,
        roc_auc, pr_auc).

        Args:
            results: Diccionario {nombre_modelo: dict_metricas}.
                     Cada dict_metricas debe tener las keys generadas
                     por el metodo evaluate().

        Returns:
            DataFrame con la comparacion de modelos, ordenado por F1 descendente.

        Ejemplo:
            all_results = {
                "Random Forest": evaluator.evaluate(rf_model, X_test, y_test),
                "XGBoost": evaluator.evaluate(xgb_model, X_test, y_test),
            }
            comparison = evaluator.compare_models(all_results)
            print(comparison)
        """
        logger.info(f"Comparando {len(results)} modelos...")

        # Metricas que queremos comparar
        metric_names = ["accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc"]

        rows = []
        for model_name, metrics in results.items():
            # Saltar entradas que no son metricas de modelos
            if not isinstance(metrics, dict) or "f1" not in metrics:
                continue

            row = {"modelo": model_name}
            for metric in metric_names:
                valor = metrics.get(metric)
                # Formatear a 4 decimales si tiene valor
                row[metric] = round(valor, 4) if valor is not None else None
            rows.append(row)

        if not rows:
            logger.warning("No hay modelos validos para comparar.")
            return pd.DataFrame()

        # Crear DataFrame y ordenar por F1 descendente
        df = pd.DataFrame(rows)
        df = df.sort_values("f1", ascending=False).reset_index(drop=True)

        # Marcar el mejor modelo
        if len(df) > 0:
            mejor = df.iloc[0]
            logger.info(
                f"Mejor modelo: {mejor['modelo']} "
                f"(F1={mejor['f1']}, PR-AUC={mejor.get('pr_auc', 'N/A')})"
            )

        return df

    # ============================================================
    # GRAFICAS: Matriz de Confusion
    # ============================================================

    def plot_confusion_matrix(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        model_name: str = "model",
        figsize: tuple = (8, 6),
    ):
        """
        Genera una grafica de la matriz de confusion.

        La matriz de confusion muestra:
        - True Negatives (TN): Correctamente clasificados como negativos.
        - False Positives (FP): Negativos clasificados como positivos (error tipo I).
        - False Negatives (FN): Positivos clasificados como negativos (error tipo II).
        - True Positives (TP): Correctamente clasificados como positivos.

        Para nuestro caso:
        - FN es peor que FP (perdernos un "gem" es peor que investigar uno falso).
        - Queremos minimizar FN, es decir, maximizar Recall.

        Args:
            y_true: Labels verdaderos.
            y_pred: Labels predichos.
            model_name: Nombre del modelo (para el titulo).
            figsize: Tamaño de la figura (ancho, alto).
        """
        logger.info(f"Generando matriz de confusion para: {model_name}")

        cm = confusion_matrix(y_true, y_pred)

        fig, ax = plt.subplots(figsize=figsize)

        # Usar ConfusionMatrixDisplay de sklearn para una grafica limpia
        disp = ConfusionMatrixDisplay(
            confusion_matrix=cm,
            display_labels=["No Gem (0)", "Gem (1)"],
        )
        disp.plot(ax=ax, cmap="Blues", values_format="d")

        ax.set_title(f"Matriz de Confusion - {model_name}", fontsize=14, pad=15)
        ax.set_xlabel("Prediccion", fontsize=12)
        ax.set_ylabel("Valor Real", fontsize=12)

        plt.tight_layout()
        plt.show()

    # ============================================================
    # GRAFICAS: Curva ROC
    # ============================================================

    def plot_roc_curve(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        model_name: str = "model",
        figsize: tuple = (8, 6),
    ):
        """
        Genera la curva ROC (Receiver Operating Characteristic).

        La curva ROC grafica la tasa de verdaderos positivos (TPR/Recall)
        contra la tasa de falsos positivos (FPR) a diferentes umbrales.

        Un modelo perfecto tiene AUC = 1.0.
        Un modelo aleatorio tiene AUC = 0.5 (linea diagonal).

        Nota: Para datos muy desbalanceados, la curva Precision-Recall
        es mas informativa que la curva ROC.

        Args:
            y_true: Labels verdaderos.
            y_prob: Probabilidades predichas para la clase positiva.
            model_name: Nombre del modelo (para el titulo).
            figsize: Tamaño de la figura.
        """
        if y_prob is None:
            logger.warning(
                f"No hay probabilidades disponibles para {model_name}. "
                "No se puede generar la curva ROC."
            )
            return

        logger.info(f"Generando curva ROC para: {model_name}")

        # Calcular la curva ROC
        fpr, tpr, thresholds = roc_curve(y_true, y_prob)
        auc_score = roc_auc_score(y_true, y_prob)

        fig, ax = plt.subplots(figsize=figsize)

        # Curva ROC del modelo
        ax.plot(
            fpr, tpr,
            color="darkorange",
            lw=2,
            label=f"{model_name} (AUC = {auc_score:.4f})",
        )

        # Linea diagonal (modelo aleatorio)
        ax.plot(
            [0, 1], [0, 1],
            color="gray",
            lw=1,
            linestyle="--",
            label="Aleatorio (AUC = 0.50)",
        )

        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel("Tasa de Falsos Positivos (FPR)", fontsize=12)
        ax.set_ylabel("Tasa de Verdaderos Positivos (TPR / Recall)", fontsize=12)
        ax.set_title(f"Curva ROC - {model_name}", fontsize=14, pad=15)
        ax.legend(loc="lower right", fontsize=11)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    # ============================================================
    # GRAFICAS: Curva Precision-Recall
    # ============================================================

    def plot_precision_recall_curve(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        model_name: str = "model",
        figsize: tuple = (8, 6),
    ):
        """
        Genera la curva Precision-Recall.

        MAS IMPORTANTE QUE LA CURVA ROC para datos desbalanceados.

        La curva P-R grafica Precision vs Recall a diferentes umbrales.
        - Precision alta = pocos falsos positivos (alertas falsas).
        - Recall alto = detectamos la mayoria de los gems reales.

        El PR-AUC (area bajo esta curva) es la metrica mas relevante
        cuando la clase positiva es rara (como los memecoins "gem").

        Un modelo perfecto tiene PR-AUC = 1.0.
        Un modelo aleatorio tiene PR-AUC ~ proporcion de la clase positiva.

        Args:
            y_true: Labels verdaderos.
            y_prob: Probabilidades predichas para la clase positiva.
            model_name: Nombre del modelo (para el titulo).
            figsize: Tamaño de la figura.
        """
        if y_prob is None:
            logger.warning(
                f"No hay probabilidades disponibles para {model_name}. "
                "No se puede generar la curva Precision-Recall."
            )
            return

        logger.info(f"Generando curva Precision-Recall para: {model_name}")

        # Calcular la curva Precision-Recall
        precision_vals, recall_vals, thresholds = precision_recall_curve(y_true, y_prob)
        pr_auc = average_precision_score(y_true, y_prob)

        # Linea base: proporcion de positivos (modelo aleatorio)
        baseline = np.mean(y_true)

        fig, ax = plt.subplots(figsize=figsize)

        # Curva P-R del modelo
        ax.plot(
            recall_vals, precision_vals,
            color="darkorange",
            lw=2,
            label=f"{model_name} (PR-AUC = {pr_auc:.4f})",
        )

        # Linea base (clasificador aleatorio)
        ax.axhline(
            y=baseline,
            color="gray",
            lw=1,
            linestyle="--",
            label=f"Aleatorio (baseline = {baseline:.4f})",
        )

        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel("Recall (Sensibilidad)", fontsize=12)
        ax.set_ylabel("Precision", fontsize=12)
        ax.set_title(f"Curva Precision-Recall - {model_name}", fontsize=14, pad=15)
        ax.legend(loc="upper right", fontsize=11)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    # ============================================================
    # THRESHOLD OPTIMIZATION
    # ============================================================

    def find_optimal_threshold(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        metric: str = "f1",
        thresholds: Optional[np.ndarray] = None,
    ) -> dict:
        """
        Busca el threshold optimo para clasificacion binaria.

        En lugar de usar 0.5 como umbral de decision, prueba multiples
        thresholds y encuentra el que maximiza la metrica elegida (F1).

        Esto es especialmente importante para datos desbalanceados donde
        el threshold optimo suele ser diferente de 0.5.

        Args:
            y_true: Labels verdaderos.
            y_prob: Probabilidades predichas para la clase positiva.
            metric: Metrica a optimizar ("f1" por defecto).
            thresholds: Array de thresholds a probar. Por defecto np.arange(0.1, 0.91, 0.05).

        Returns:
            Dict con:
            - best_threshold: float (threshold optimo)
            - best_f1: float (mejor F1 encontrado)
            - all_results: list[dict] con {threshold, f1, precision, recall} para cada threshold
        """
        if thresholds is None:
            thresholds = np.arange(0.1, 0.91, 0.05)

        all_results = []
        for t in thresholds:
            y_pred_t = (y_prob >= t).astype(int)
            f1_t = f1_score(y_true, y_pred_t, zero_division=0)
            prec_t = precision_score(y_true, y_pred_t, zero_division=0)
            rec_t = recall_score(y_true, y_pred_t, zero_division=0)
            all_results.append({
                "threshold": round(float(t), 2),
                "f1": float(f1_t),
                "precision": float(prec_t),
                "recall": float(rec_t),
            })

        # Encontrar el mejor threshold
        best = max(all_results, key=lambda x: x["f1"])

        # Loggear top 5
        sorted_results = sorted(all_results, key=lambda x: -x["f1"])[:5]
        logger.info("Top 5 thresholds por F1:")
        for r in sorted_results:
            logger.info(
                f"  threshold={r['threshold']:.2f}: "
                f"F1={r['f1']:.4f}, P={r['precision']:.4f}, R={r['recall']:.4f}"
            )

        return {
            "best_threshold": best["threshold"],
            "best_f1": best["f1"],
            "all_results": all_results,
        }

    def plot_threshold_analysis(
        self,
        results: dict,
        figsize: tuple = (10, 6),
    ):
        """
        Grafica F1, Precision y Recall vs threshold.

        Muestra como varian las metricas al cambiar el umbral de decision,
        y marca el threshold optimo con una linea vertical.

        Args:
            results: Output de find_optimal_threshold().
            figsize: Tamaño de la figura.
        """
        all_results = results["all_results"]
        best_t = results["best_threshold"]

        thresholds = [r["threshold"] for r in all_results]
        f1s = [r["f1"] for r in all_results]
        precs = [r["precision"] for r in all_results]
        recs = [r["recall"] for r in all_results]

        fig, ax = plt.subplots(figsize=figsize)

        ax.plot(thresholds, f1s, "b-o", label="F1", markersize=4)
        ax.plot(thresholds, precs, "g--s", label="Precision", markersize=4)
        ax.plot(thresholds, recs, "r--^", label="Recall", markersize=4)

        # Marcar el optimo
        ax.axvline(x=best_t, color="black", linestyle=":", lw=2,
                    label=f"Optimo (t={best_t:.2f})")

        ax.set_xlabel("Threshold", fontsize=12)
        ax.set_ylabel("Score", fontsize=12)
        ax.set_title("Analisis de Threshold: F1 / Precision / Recall", fontsize=14, pad=15)
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.set_xlim([0.05, 0.95])
        ax.set_ylim([0.0, 1.05])

        plt.tight_layout()
        plt.show()

    # ============================================================
    # CALIBRATION CURVE
    # ============================================================

    def plot_calibration_curve(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        model_name: str = "model",
        n_bins: int = 10,
        figsize: tuple = (8, 6),
    ):
        """
        Genera la curva de calibracion del modelo.

        La curva de calibracion muestra si las probabilidades del modelo
        son realistas. Un modelo bien calibrado tiene una curva cercana
        a la diagonal: cuando predice 80%, realmente acierta ~80%.

        Args:
            y_true: Labels verdaderos.
            y_prob: Probabilidades predichas para la clase positiva.
            model_name: Nombre del modelo (para el titulo).
            n_bins: Numero de bins para la curva.
            figsize: Tamaño de la figura.
        """
        if y_prob is None:
            logger.warning(f"No hay probabilidades para curva de calibracion de {model_name}")
            return

        logger.info(f"Generando curva de calibracion para: {model_name}")

        fraction_pos, mean_predicted = calibration_curve(
            y_true, y_prob, n_bins=n_bins, strategy="uniform"
        )

        fig, ax = plt.subplots(figsize=figsize)

        # Curva de calibracion del modelo
        ax.plot(
            mean_predicted, fraction_pos,
            "s-", color="darkorange", lw=2,
            label=f"{model_name}",
        )

        # Diagonal = calibracion perfecta
        ax.plot(
            [0, 1], [0, 1],
            "k--", lw=1,
            label="Calibracion perfecta",
        )

        ax.set_xlabel("Probabilidad predicha (media)", fontsize=12)
        ax.set_ylabel("Fraccion de positivos reales", fontsize=12)
        ax.set_title(f"Curva de Calibracion - {model_name}", fontsize=14, pad=15)
        ax.legend(loc="lower right", fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])

        plt.tight_layout()
        plt.show()
