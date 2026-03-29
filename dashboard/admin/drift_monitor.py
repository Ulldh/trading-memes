"""
drift_monitor.py - Monitor de drift para modelos de Machine Learning.

Muestra:
- Ultimo reporte de drift (score, estado, razones)
- Desglose por tipo de drift (tiempo, volumen, features)
- Tabla de detalle de feature drift
- Historico de scores de drift (grafico de línea)
- Tabla de reportes recientes (ultimos 20)

Los reportes se generan automáticamente los lunes a las 08:00 UTC
via GitHub Actions (check-retrain.yml).
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timezone


# ============================================================
# CARGA DE DATOS
# ============================================================

@st.cache_data(ttl=120)
def _load_drift_reports(limit: int = 50) -> pd.DataFrame:
    """
    Carga reportes de drift desde Supabase.

    Retorna DataFrame vacio si no hay conexion o no hay reportes.
    TTL de 2 minutos para no saturar la API.
    """
    try:
        from src.data.supabase_storage import get_storage
        storage = get_storage()
        return storage.get_drift_reports(limit=limit)
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        return pd.DataFrame()


# ============================================================
# RENDER PRINCIPAL
# ============================================================

def render():
    """Monitor de drift — visualizacion de reportes de drift detection."""
    # Guard de acceso — solo admin
    try:
        from dashboard.auth import require_admin
        require_admin()
    except ImportError:
        pass

    st.header("Drift Monitor")

    st.info(
        "**¿Qué es esto?** El drift detection verifica si los datos actuales "
        "han cambiado lo suficiente respecto a los datos de entrenamiento como "
        "para que el modelo pierda efectividad. Se revisan tres tipos de drift: "
        "tiempo (dias sin re-entrenar), volumen (tokens nuevos) y features "
        "(cambio en distribución de variables)."
    )

    # Cargar reportes
    df_reports = _load_drift_reports()

    if df_reports.empty:
        st.warning(
            "No hay reportes de drift. El primer check se ejecuta los lunes "
            "a las 08:00 UTC via GitHub Actions (`check-retrain.yml`)."
        )
        st.caption(
            "Tambien puedes ejecutar un check manual con: "
            "`gh workflow run check-retrain.yml --ref main`"
        )
        return

    # ------------------------------------------------------------------
    # 1. Ultimo reporte de drift (tarjeta resumen)
    # ------------------------------------------------------------------
    st.subheader("Ultimo reporte")

    latest = df_reports.iloc[0]

    # Extraer campos del ultimo reporte
    score = latest.get("overall_score", 0.0) or 0.0
    needs_retrain = latest.get("needs_retraining", False)
    reasons = latest.get("reasons", [])
    checked_at = latest.get("checked_at", "N/A")
    model_version = latest.get("model_version", "N/A")

    # Si reasons es string (JSON serializado), convertir a lista
    if isinstance(reasons, str):
        try:
            import json
            reasons = json.loads(reasons)
        except (json.JSONDecodeError, TypeError):
            reasons = [reasons] if reasons else []

    # Tarjeta de estado
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Gauge visual del score (0-1)
        _render_score_gauge(score)

    with col2:
        if needs_retrain:
            st.metric("Estado", "RE-ENTRENAR")
            st.error("El modelo necesita re-entrenamiento")
        else:
            st.metric("Estado", "OK")
            st.success("El modelo esta actualizado")

    with col3:
        st.metric("Version", model_version)

    with col4:
        # Formatear fecha de checked_at
        if checked_at and checked_at != "N/A":
            try:
                dt = pd.to_datetime(checked_at)
                st.metric("Ultimo check", dt.strftime("%Y-%m-%d %H:%M"))
            except Exception:
                st.metric("Ultimo check", str(checked_at)[:16])
        else:
            st.metric("Ultimo check", "N/A")

    # Razones de re-entrenamiento
    if reasons:
        st.markdown("**Razones para re-entrenar:**")
        for reason in reasons:
            st.markdown(f"- {reason}")

    st.divider()

    # ------------------------------------------------------------------
    # 2. Desglose por tipo de drift
    # ------------------------------------------------------------------
    st.subheader("Desglose por tipo de drift")

    col_time, col_vol, col_feat = st.columns(3)

    # Time Drift
    with col_time:
        st.markdown("**Time Drift**")
        time_days = latest.get("time_drift_days")
        time_triggered = latest.get("time_drift_triggered", False)
        threshold_days = 30  # Umbral por defecto del DriftDetector

        if time_days is not None:
            st.metric(
                "Dias desde entrenamiento",
                f"{time_days}",
                delta=f"umbral: {threshold_days}",
                delta_color="inverse",
            )
        else:
            st.metric("Dias desde entrenamiento", "N/A")

        if time_triggered:
            st.error("DRIFT: Modelo desactualizado")
        else:
            st.success("OK: Dentro del umbral")

    # Volume Drift
    with col_vol:
        st.markdown("**Volume Drift**")
        new_labels = latest.get("volume_drift_new_labels")
        vol_triggered = latest.get("volume_drift_triggered", False)
        threshold_vol = 50  # Umbral por defecto

        if new_labels is not None:
            st.metric(
                "Labels nuevos",
                f"{new_labels}",
                delta=f"umbral: {threshold_vol}",
                delta_color="inverse",
            )
        else:
            st.metric("Labels nuevos", "N/A")

        if vol_triggered:
            st.error("DRIFT: Suficientes datos nuevos")
        else:
            st.success("OK: Pocos datos nuevos")

    # Feature Drift
    with col_feat:
        st.markdown("**Feature Drift**")
        feat_count = latest.get("feature_drift_count", 0) or 0
        feat_total = latest.get("feature_drift_total", 0) or 0
        feat_triggered = latest.get("feature_drift_triggered", False)

        if feat_total > 0:
            pct = feat_count / feat_total * 100
            st.metric(
                "Features con drift",
                f"{feat_count}/{feat_total}",
                delta=f"{pct:.1f}%",
                delta_color="inverse",
            )
        else:
            st.metric("Features con drift", "N/A")

        if feat_triggered:
            st.error("DRIFT: Distribución cambiada")
        else:
            st.success("OK: Distribución estable")

    st.divider()

    # ------------------------------------------------------------------
    # 3. Detalle de feature drift (tabla)
    # ------------------------------------------------------------------
    st.subheader("Detalle de feature drift")

    st.caption(
        "Features cuya mediana actual difiere significativamente de la mediana "
        "de entrenamiento. Shift % = cambio relativo respecto al valor de "
        "entrenamiento. Solo se muestran las top 10 con mayor shift."
    )

    feature_details = latest.get("feature_drift_details", {})

    # Si viene como string JSON, parsear
    if isinstance(feature_details, str):
        try:
            import json
            feature_details = json.loads(feature_details)
        except (json.JSONDecodeError, TypeError):
            feature_details = {}

    if feature_details:
        # Construir tabla de detalle
        rows = []
        for feat_name, detail in feature_details.items():
            train_val = detail.get("train", 0)
            current_val = detail.get("current", 0)
            shift_pct = detail.get("shift_pct", 0)
            # Estado: DRIFT si shift > 50%, WARNING si > 25%, OK si < 25%
            if shift_pct > 0.5:
                status = "DRIFT"
            elif shift_pct > 0.25:
                status = "WARNING"
            else:
                status = "OK"
            rows.append({
                "Feature": feat_name,
                "Mediana Train": f"{train_val:.4f}" if isinstance(train_val, (int, float)) else str(train_val),
                "Mediana Actual": f"{current_val:.4f}" if isinstance(current_val, (int, float)) else str(current_val),
                "Shift %": f"{shift_pct * 100:.1f}%",
                "Estado": status,
            })

        df_details = pd.DataFrame(rows)
        # Ordenar por shift descendente
        df_details = df_details.sort_values(
            "Shift %",
            key=lambda x: x.str.rstrip("%").astype(float),
            ascending=False,
        )
        st.dataframe(df_details, use_container_width=True, hide_index=True)
    else:
        st.info("No hay detalles de feature drift disponibles en este reporte.")

    st.divider()

    # ------------------------------------------------------------------
    # 4. Historico de drift scores (grafico de linea)
    # ------------------------------------------------------------------
    st.subheader("Historico de drift scores")

    st.caption(
        "Evolucion del score de drift en el tiempo. Score 0 = sin drift, "
        "Score 1 = drift maximo. La línea roja punteada marca el umbral "
        "donde se recomienda re-entrenar."
    )

    if len(df_reports) >= 2:
        # Preparar datos para el grafico
        df_chart = df_reports[["checked_at", "overall_score", "needs_retraining"]].copy()
        df_chart["checked_at"] = pd.to_datetime(df_chart["checked_at"])
        df_chart = df_chart.sort_values("checked_at")

        fig = go.Figure()

        # Linea de score
        fig.add_trace(go.Scatter(
            x=df_chart["checked_at"],
            y=df_chart["overall_score"],
            mode="lines+markers",
            name="Drift Score",
            line=dict(color="#3498db", width=2),
            marker=dict(
                size=8,
                color=["#e74c3c" if r else "#2ecc71"
                       for r in df_chart["needs_retraining"]],
            ),
        ))

        # Linea de umbral (cualquier componente > 0 dispara retrain,
        # pero mostramos 0.5 como referencia visual)
        fig.add_hline(
            y=0.5,
            line_dash="dash",
            line_color="red",
            annotation_text="Umbral de referencia",
        )

        fig.update_layout(
            xaxis_title="Fecha del check",
            yaxis_title="Score de drift (0-1)",
            yaxis=dict(range=[0, 1.05]),
            height=400,
            showlegend=True,
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(
            "Se necesitan al menos 2 reportes para mostrar el histórico. "
            "Actualmente hay solo 1 reporte."
        )

    st.divider()

    # ------------------------------------------------------------------
    # 5. Tabla de reportes recientes (ultimos 20)
    # ------------------------------------------------------------------
    st.subheader("Reportes recientes")

    st.caption("Ultimos 20 reportes de drift detection, ordenados por fecha.")

    # Preparar tabla resumida
    df_table = df_reports.head(20).copy()

    # Seleccionar columnas relevantes
    display_cols = []
    col_mapping = {
        "checked_at": "Fecha",
        "model_version": "Version",
        "overall_score": "Score",
        "needs_retraining": "Re-entrenar?",
        "time_drift_triggered": "Time Drift",
        "volume_drift_triggered": "Volume Drift",
        "feature_drift_triggered": "Feature Drift",
        "time_drift_days": "Dias",
        "volume_drift_new_labels": "Labels nuevos",
        "feature_drift_count": "Features drift",
    }

    for col, label in col_mapping.items():
        if col in df_table.columns:
            display_cols.append(col)

    if display_cols:
        df_display = df_table[display_cols].copy()
        df_display.columns = [col_mapping[c] for c in display_cols]

        # Formatear fecha
        if "Fecha" in df_display.columns:
            df_display["Fecha"] = pd.to_datetime(
                df_display["Fecha"]
            ).dt.strftime("%Y-%m-%d %H:%M")

        # Formatear booleanos
        for bool_col in ["Re-entrenar?", "Time Drift", "Volume Drift", "Feature Drift"]:
            if bool_col in df_display.columns:
                df_display[bool_col] = df_display[bool_col].map(
                    {True: "Si", False: "No"}
                ).fillna("N/A")

        # Formatear score
        if "Score" in df_display.columns:
            df_display["Score"] = df_display["Score"].apply(
                lambda x: f"{x:.3f}" if pd.notna(x) else "N/A"
            )

        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df_table, use_container_width=True, hide_index=True)


# ============================================================
# COMPONENTES AUXILIARES
# ============================================================

def _render_score_gauge(score: float):
    """
    Renderiza un gauge visual para el score de drift (0-1).

    Colores: verde (0-0.3), amarillo (0.3-0.6), rojo (0.6-1.0).
    Usa plotly.graph_objects.Indicator.
    """
    # Determinar color segun nivel de score
    if score < 0.3:
        bar_color = "#2ecc71"  # Verde
    elif score < 0.6:
        bar_color = "#f39c12"  # Amarillo
    else:
        bar_color = "#e74c3c"  # Rojo

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": "", "font": {"size": 28}},
        title={"text": "Drift Score", "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, 1], "tickwidth": 1},
            "bar": {"color": bar_color},
            "bgcolor": "white",
            "steps": [
                {"range": [0, 0.3], "color": "#eafaf1"},
                {"range": [0.3, 0.6], "color": "#fef9e7"},
                {"range": [0.6, 1], "color": "#fdedec"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 2},
                "thickness": 0.75,
                "value": 0.5,
            },
        },
    ))

    fig.update_layout(
        height=200,
        margin=dict(l=20, r=20, t=40, b=10),
    )

    st.plotly_chart(fig, use_container_width=True)
