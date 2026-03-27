"""
model_results.py - Pagina de resultados de los modelos de Machine Learning.

Muestra:
- Tabla comparativa de metricas (RF vs XGBoost)
- Matrices de confusion (heatmap)
- Curvas ROC y Precision-Recall
- Reporte de clasificacion completo
"""
# Guard de acceso — solo admin
try:
    from dashboard.auth import require_admin
    require_admin()
except ImportError:
    pass  # Fallback: sin auth module, acceso libre (desarrollo)

import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from config import MODELS_DIR

# Colores para cada modelo
MODEL_COLORS = {
    "RandomForest": "#2ecc71",
    "XGBoost": "#e67e22",
}


@st.cache_data(ttl=300)
def load_evaluation_results():
    """Carga los resultados de evaluacion guardados."""
    results_path = MODELS_DIR / "evaluation_results.json"
    if not results_path.exists():
        return None
    try:
        with open(results_path, "r") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error al cargar resultados: {e}")
        return None


def render():
    """Renderiza la pagina de Resultados del Modelo."""
    st.title("Resultados del Modelo")

    st.info(
        "**Que es esto?** Aqui evaluamos que tan bien predicen nuestros modelos de "
        "Machine Learning. Entrenamos dos modelos diferentes (Random Forest y XGBoost) "
        "y los comparamos para ver cual detecta mejor las 'gems' (memecoins exitosos).\n\n"
        "**Importante**: Los resultados dependen de la cantidad de datos etiquetados. "
        "Con mas tokens las metricas seran mas estables y representativas."
    )

    results = load_evaluation_results()

    if results is None:
        st.warning(
            f"No se encontraron resultados en `{MODELS_DIR}/evaluation_results.json`."
        )
        st.info("Ejecuta el pipeline de entrenamiento para generar los resultados.")
        return

    models_data = results.get("models", results)
    if not models_data:
        st.warning("El archivo de resultados esta vacio.")
        return

    model_names = list(models_data.keys())

    st.divider()

    # ------------------------------------------------------------------
    # 1. Tabla comparativa de metricas
    # ------------------------------------------------------------------
    st.subheader("Comparacion de metricas")

    st.caption(
        "Cada metrica mide algo diferente sobre el rendimiento del modelo:"
    )

    # Explicar metricas
    with st.expander("Que significa cada metrica? (click para expandir)"):
        st.markdown("""
- **Accuracy** (Exactitud): % de predicciones correctas en total. Puede ser enganosa si hay muchos mas gems que failures.
- **Precision**: Cuando el modelo dice "esto es un gem", que % de las veces acierta. Alta precision = pocas falsas alarmas.
- **Recall**: De todos los gems reales, que % detecta el modelo. Alto recall = no se le escapan muchos gems.
- **F1-Score**: Combina Precision y Recall en un solo numero (media armonica). Ideal para datos desbalanceados.
- **ROC-AUC**: Mide la capacidad general de distinguir gems de no-gems. 1.0 = perfecto, 0.5 = aleatorio.
- **PR-AUC**: Similar a ROC-AUC pero mas fiable cuando hay pocas muestras de una clase.
        """)

    metric_keys = ["accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc"]
    metric_labels = {
        "accuracy": "Accuracy (Exactitud)",
        "precision": "Precision",
        "recall": "Recall (Sensibilidad)",
        "f1": "F1-Score",
        "roc_auc": "ROC-AUC",
        "pr_auc": "PR-AUC",
    }

    rows = []
    for metric_key in metric_keys:
        row = {"Metrica": metric_labels.get(metric_key, metric_key)}
        for model_name in model_names:
            value = models_data[model_name].get(metric_key, None)
            row[model_name] = f"{value:.3f}" if value is not None else "N/A"
        rows.append(row)

    df_metrics = pd.DataFrame(rows)
    st.dataframe(df_metrics, use_container_width=True, hide_index=True)

    # Metricas destacadas
    cols = st.columns(len(model_names))
    for i, model_name in enumerate(model_names):
        with cols[i]:
            st.markdown(f"**{model_name}**")
            model_info = models_data[model_name]
            sub_cols = st.columns(3)
            sub_cols[0].metric("Accuracy", f"{model_info.get('accuracy', 0):.0%}")
            sub_cols[1].metric("F1-Score", f"{model_info.get('f1', 0):.0%}")
            sub_cols[2].metric("ROC-AUC", f"{model_info.get('roc_auc', 0):.2f}")

    st.divider()

    # ------------------------------------------------------------------
    # 2. Matrices de confusion
    # ------------------------------------------------------------------
    st.subheader("Matrices de confusion")

    st.caption(
        "La matriz de confusion muestra cuantas predicciones fueron correctas "
        "y cuantas no. Filas = lo que realmente es, Columnas = lo que predijo "
        "el modelo. Los numeros en la diagonal (esquina superior-izquierda e "
        "inferior-derecha) son los aciertos."
    )

    cols_cm = st.columns(len(model_names))
    for i, model_name in enumerate(model_names):
        with cols_cm[i]:
            cm = models_data[model_name].get("confusion_matrix", None)
            if cm is None:
                st.info(f"No hay matriz para {model_name}.")
                continue

            cm_array = np.array(cm)
            labels_cm = ["No-gem", "Gem"]

            fig_cm = px.imshow(
                cm_array,
                title=f"{model_name}",
                x=labels_cm, y=labels_cm,
                color_continuous_scale="Blues",
                text_auto=True,
                aspect="auto",
            )
            fig_cm.update_layout(
                xaxis_title="Prediccion del modelo",
                yaxis_title="Valor real",
            )
            st.plotly_chart(fig_cm, use_container_width=True)

    with st.expander("Como leer la matriz de confusion?"):
        st.markdown("""
| | Predijo No-gem | Predijo Gem |
|---|---|---|
| **Realmente No-gem** | Verdadero Negativo (bien) | Falso Positivo (falsa alarma) |
| **Realmente Gem** | Falso Negativo (gem perdido!) | Verdadero Positivo (acierto!) |

- **Verdadero Positivo (VP)**: El modelo dijo "gem" y realmente era gem. Lo que queremos maximizar.
- **Falso Positivo (FP)**: El modelo dijo "gem" pero no lo era. Perdemos tiempo investigando.
- **Falso Negativo (FN)**: Era un gem pero el modelo no lo detecto. Oportunidad perdida.
- **Verdadero Negativo (VN)**: El modelo dijo "no es gem" y realmente no lo era. Bien.
        """)

    st.divider()

    # ------------------------------------------------------------------
    # 3. Curva ROC
    # ------------------------------------------------------------------
    st.subheader("Curva ROC")

    st.caption(
        "La curva ROC muestra la relacion entre aciertos (TPR) y falsas alarmas (FPR) "
        "a diferentes umbrales de decision. Cuanto mas arriba y a la izquierda este "
        "la curva, mejor es el modelo. La linea gris punteada es un modelo aleatorio."
    )

    fig_roc = go.Figure()
    fig_roc.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1],
        mode="lines",
        line=dict(dash="dash", color="gray"),
        name="Aleatorio (AUC=0.5)",
    ))

    has_roc = False
    for model_name in model_names:
        roc_data = models_data[model_name].get("roc_curve", None)
        roc_auc = models_data[model_name].get("roc_auc", None)
        if roc_data is None:
            continue
        has_roc = True
        auc_label = f" (AUC={roc_auc:.3f})" if roc_auc else ""
        fig_roc.add_trace(go.Scatter(
            x=roc_data["fpr"], y=roc_data["tpr"],
            mode="lines",
            name=f"{model_name}{auc_label}",
            line=dict(color=MODEL_COLORS.get(model_name), width=2),
        ))

    fig_roc.update_layout(
        title="Curva ROC - Comparacion de modelos",
        xaxis_title="Tasa de Falsas Alarmas (FPR)",
        yaxis_title="Tasa de Deteccion (TPR)",
        legend=dict(x=0.55, y=0.1),
        height=500,
    )

    if has_roc:
        st.plotly_chart(fig_roc, use_container_width=True)
    else:
        st.info("No hay datos de curva ROC disponibles.")

    st.divider()

    # ------------------------------------------------------------------
    # 4. Curva Precision-Recall
    # ------------------------------------------------------------------
    st.subheader("Curva Precision-Recall")

    st.caption(
        "Muestra el balance entre Precision (no dar falsas alarmas) y Recall "
        "(no perder gems reales). Lo ideal seria tener ambas en 1.0, pero "
        "normalmente mejorar una empeora la otra. El area bajo la curva (AUC) "
        "resume el rendimiento general."
    )

    fig_pr = go.Figure()
    has_pr = False
    for model_name in model_names:
        pr_data = models_data[model_name].get("pr_curve", None)
        pr_auc = models_data[model_name].get("pr_auc", None)
        if pr_data is None:
            continue
        has_pr = True
        auc_label = f" (AUC={pr_auc:.3f})" if pr_auc else ""
        fig_pr.add_trace(go.Scatter(
            x=pr_data["recall"], y=pr_data["precision"],
            mode="lines",
            name=f"{model_name}{auc_label}",
            line=dict(color=MODEL_COLORS.get(model_name), width=2),
        ))

    fig_pr.update_layout(
        title="Curva Precision-Recall",
        xaxis_title="Recall (que % de gems detecta)",
        yaxis_title="Precision (que % de los que dice 'gem' son reales)",
        legend=dict(x=0.1, y=0.1),
        height=500,
    )

    if has_pr:
        st.plotly_chart(fig_pr, use_container_width=True)
    else:
        st.info("No hay datos de curva Precision-Recall disponibles.")

    st.divider()

    # ------------------------------------------------------------------
    # 5. Reporte de clasificacion
    # ------------------------------------------------------------------
    st.subheader("Reporte de clasificacion detallado")

    st.caption(
        "Tabla detallada con precision, recall y f1-score para cada clase "
        "(gem y no-gem) y el promedio general."
    )

    for model_name in model_names:
        report = models_data[model_name].get("classification_report", None)
        if report:
            st.markdown(f"**{model_name}**")
            st.code(report, language="text")
        else:
            st.info(f"No hay reporte para {model_name}.")

    st.divider()

    # ------------------------------------------------------------------
    # 6. Threshold optimo
    # ------------------------------------------------------------------
    st.subheader("Threshold Optimo")

    st.caption(
        "El modelo predice una probabilidad (0 a 1). El 'threshold' (umbral) es el "
        "punto de corte: si la probabilidad supera el umbral, se clasifica como gem. "
        "Optimizar el threshold maximiza el F1-Score, que balancea precision y recall."
    )

    # Buscar threshold optimo en los resultados
    optimal_threshold = results.get("optimal_threshold")
    if optimal_threshold is None:
        # Intentar leerlo de cada modelo
        for model_name in model_names:
            t = models_data[model_name].get("optimal_threshold")
            if t is not None:
                optimal_threshold = t
                break

    if optimal_threshold is not None:
        col_t1, col_t2, col_t3 = st.columns(3)
        col_t1.metric(
            "Threshold Optimo",
            f"{optimal_threshold:.2f}",
            help="Umbral de probabilidad que maximiza F1-Score.",
        )
        col_t2.metric(
            "Threshold Default",
            "0.50",
            help="El umbral por defecto (50%).",
        )
        diff = optimal_threshold - 0.5
        col_t3.metric(
            "Diferencia",
            f"{diff:+.2f}",
            help="Diferencia entre el optimo y el default.",
        )

        with st.expander("Que significa el threshold?"):
            st.markdown("""
- **Threshold alto** (ej: 0.7): El modelo es mas exigente. Menos falsas alarmas, pero puede perder gems reales.
- **Threshold bajo** (ej: 0.3): El modelo es mas permisivo. Detecta mas gems, pero tambien mas falsas alarmas.
- **El optimo** balancea ambos extremos para maximizar el F1-Score.
            """)
    else:
        st.info("No hay threshold optimo disponible. Ejecuta el pipeline de entrenamiento v2.")

    st.divider()

    # ------------------------------------------------------------------
    # 7. Curva de calibracion
    # ------------------------------------------------------------------
    st.subheader("Curva de Calibracion")

    st.caption(
        "Verifica si las probabilidades del modelo son confiables. "
        "Si el modelo dice 70% de probabilidad de ser gem, deberia acertar "
        "en ~70% de los casos. La linea punteada es calibracion perfecta."
    )

    # Intentar cargar curva de calibracion desde archivo procesado
    from pathlib import Path
    cal_plot_path = Path("data/processed/calibration_curve.png")
    if cal_plot_path.exists():
        st.image(str(cal_plot_path), caption="Curva de calibracion (generada en notebook 09)")
    else:
        # Verificar si hay datos para generar on-the-fly
        has_cal_data = False
        for model_name in model_names:
            cal_data = models_data[model_name].get("calibration_curve")
            if cal_data:
                has_cal_data = True
                break

        if has_cal_data:
            fig_cal = go.Figure()
            fig_cal.add_trace(go.Scatter(
                x=[0, 1], y=[0, 1],
                mode="lines",
                line=dict(dash="dash", color="gray"),
                name="Calibracion perfecta",
            ))

            for model_name in model_names:
                cal_data = models_data[model_name].get("calibration_curve")
                if cal_data:
                    fig_cal.add_trace(go.Scatter(
                        x=cal_data["prob_pred"],
                        y=cal_data["prob_true"],
                        mode="lines+markers",
                        name=model_name,
                        line=dict(color=MODEL_COLORS.get(model_name), width=2),
                    ))

            fig_cal.update_layout(
                title="Curva de Calibracion",
                xaxis_title="Probabilidad predicha",
                yaxis_title="Fraccion de positivos reales",
                height=500,
            )
            st.plotly_chart(fig_cal, use_container_width=True)
        else:
            st.info(
                "No hay datos de calibracion. Ejecuta el notebook "
                "`09_ml_pipeline_v2.ipynb` para generarlos."
            )
