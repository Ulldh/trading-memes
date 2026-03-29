"""
retrain_panel.py - Panel de control de retrain para modelos ML.

Muestra:
- Informacion del modelo actual (version, métricas, fecha)
- Historial de versiones con comparativa
- Estadísticas de datos de entrenamiento
- Acciones de retrain (comandos manuales)
- Reporte de seleccion de features

Los retrains se ejecutan via GitHub Actions (manual-retrain.yml)
o mediante el pipeline local (scripts/retrain_pipeline.py).
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
import plotly.graph_objects as go
from pathlib import Path


# ============================================================
# CARGA DE DATOS
# ============================================================

@st.cache_data(ttl=300)
def _load_metadata(version_dir: Path) -> dict | None:
    """
    Carga metadata.json de una version de modelo.

    Retorna None si el archivo no existe o no se puede leer.
    """
    meta_path = version_dir / "metadata.json"
    if not meta_path.exists():
        return None
    try:
        with open(meta_path, "r") as f:
            return json.load(f)
    except Exception:
        return None


@st.cache_data(ttl=300)
def _load_all_versions() -> list[dict]:
    """
    Carga metadata de todas las versiones de modelo disponibles en disco.

    Busca directorios v* en MODELS_DIR y lee metadata.json de cada uno.
    Retorna lista de dicts ordenada por version descendente.
    """
    try:
        from config import MODELS_DIR
    except ImportError:
        return []

    versions = []
    for version_dir in sorted(MODELS_DIR.iterdir(), reverse=True):
        if version_dir.is_dir() and version_dir.name.startswith("v"):
            meta = _load_metadata(version_dir)
            if meta:
                meta["_dir"] = str(version_dir)
                versions.append(meta)

    return versions


@st.cache_data(ttl=300)
def _get_latest_version() -> str:
    """Lee la version mas reciente desde latest_version.txt."""
    try:
        from config import MODELS_DIR
        version_file = MODELS_DIR / "latest_version.txt"
        if version_file.exists():
            return version_file.read_text().strip()
    except Exception:
        pass
    return "v12"  # Fallback


@st.cache_data(ttl=120)
def _load_training_stats() -> dict:
    """
    Carga estadisticas de entrenamiento desde Supabase.

    Consulta conteos de tokens, labels, features y distribución de clases.
    """
    stats = {
        "total_tokens": 0,
        "total_labels": 0,
        "total_features": 0,
        "gems": 0,
        "non_gems": 0,
    }
    try:
        from src.data.supabase_storage import get_storage
        storage = get_storage()

        # Conteo de tokens
        df = storage.query("SELECT COUNT(*) as cnt FROM tokens")
        if not df.empty:
            stats["total_tokens"] = int(df.iloc[0]["cnt"])

        # Conteo de labels y distribucion
        df = storage.query(
            "SELECT label_binary, COUNT(*) as cnt FROM labels GROUP BY label_binary"
        )
        if not df.empty:
            for _, row in df.iterrows():
                label = row.get("label_binary")
                cnt = int(row.get("cnt", 0))
                stats["total_labels"] += cnt
                if label == 1 or label == "1":
                    stats["gems"] = cnt
                elif label == 0 or label == "0":
                    stats["non_gems"] = cnt

        # Conteo de features
        df = storage.query("SELECT COUNT(*) as cnt FROM features")
        if not df.empty:
            stats["total_features"] = int(df.iloc[0]["cnt"])

    except Exception as e:
        st.warning(f"No se pudieron cargar estadisticas de Supabase: {e}")

    return stats


@st.cache_data(ttl=300)
def _load_feature_columns() -> dict | None:
    """Carga feature_columns.json con información de seleccion de features."""
    try:
        from config import MODELS_DIR
        path = MODELS_DIR / "feature_columns.json"
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return None


# ============================================================
# RENDER PRINCIPAL
# ============================================================

def render():
    """Panel de control de retrain — ver versiones, comparar, ejecutar."""
    st.header("Control de Retrain")

    st.info(
        "**¿Qué es esto?** Este panel permite monitorear las versiones del modelo, "
        "comparar métricas entre versiones, ver estadisticas de los datos de "
        "entrenamiento y ejecutar retrains manuales via GitHub Actions."
    )

    # ------------------------------------------------------------------
    # 1. Informacion del modelo actual
    # ------------------------------------------------------------------
    st.subheader("Modelo actual")

    latest_version = _get_latest_version()
    all_versions = _load_all_versions()

    # Buscar metadata de la version actual
    current_meta = None
    for v in all_versions:
        if v.get("version") == latest_version:
            current_meta = v
            break

    if current_meta is None:
        st.warning(
            f"No se encontro metadata.json para {latest_version}. "
            "Ejecuta el pipeline de entrenamiento primero."
        )
    else:
        _render_model_card(current_meta, is_current=True)

    st.divider()

    # ------------------------------------------------------------------
    # 2. Historial de versiones
    # ------------------------------------------------------------------
    st.subheader("Historial de versiones")

    st.caption(
        "Todas las versiones de modelo disponibles en disco. "
        "La version activa se marca con asterisco (*)."
    )

    if all_versions:
        rows = []
        for meta in all_versions:
            version = meta.get("version", "?")
            trained_at = meta.get("trained_at", "N/A")
            results = meta.get("results", {})

            # Extraer metricas de cada modelo
            rf = results.get("random_forest", {})
            xgb = results.get("xgboost", {})
            lgb = results.get("lightgbm", {})

            # Formatear fecha
            if trained_at and trained_at != "N/A":
                try:
                    dt = pd.to_datetime(trained_at)
                    trained_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    trained_str = str(trained_at)[:16]
            else:
                trained_str = "N/A"

            is_active = version == latest_version

            row = {
                "Version": f"{version} *" if is_active else version,
                "Fecha": trained_str,
                "RF CV F1": f"{rf.get('cv_f1_mean', 0):.3f}" if rf.get("cv_f1_mean") else "N/A",
                "RF Val F1": f"{rf.get('val_f1', 0):.3f}" if rf.get("val_f1") else "N/A",
                "XGB CV F1": f"{xgb.get('cv_f1_mean', 0):.3f}" if xgb.get("cv_f1_mean") else "N/A",
                "XGB Val F1": f"{xgb.get('val_f1', 0):.3f}" if xgb.get("val_f1") else "N/A",
                "Features": meta.get("num_features", "N/A"),
            }

            # Agregar LightGBM si existe
            if lgb:
                row["LGB CV F1"] = f"{lgb.get('cv_f1_mean', 0):.3f}" if lgb.get("cv_f1_mean") else "N/A"
                row["LGB Val F1"] = f"{lgb.get('val_f1', 0):.3f}" if lgb.get("val_f1") else "N/A"

            rows.append(row)

        df_versions = pd.DataFrame(rows)
        st.dataframe(df_versions, use_container_width=True, hide_index=True)

        # Grafico comparativo de F1 scores entre versiones
        _render_version_comparison_chart(all_versions)
    else:
        st.warning("No se encontraron versiones de modelo en disco.")

    st.divider()

    # ------------------------------------------------------------------
    # 3. Estadisticas de datos de entrenamiento
    # ------------------------------------------------------------------
    st.subheader("Datos de entrenamiento")

    st.caption(
        "Estadísticas actuales de los datos disponibles en Supabase. "
        "Estos datos se usan para entrenar nuevas versiones del modelo."
    )

    stats = _load_training_stats()

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Tokens totales", f"{stats['total_tokens']:,}")
    col2.metric("Labels", f"{stats['total_labels']:,}")
    col3.metric("Gems (1)", f"{stats['gems']:,}")
    col4.metric("No-gems (0)", f"{stats['non_gems']:,}")
    col5.metric("Features", f"{stats['total_features']:,}")

    # Balance de clases
    if stats["total_labels"] > 0:
        gem_pct = stats["gems"] / stats["total_labels"] * 100
        st.caption(
            f"Balance de clases: {gem_pct:.1f}% gems vs "
            f"{100 - gem_pct:.1f}% no-gems "
            f"(ratio 1:{stats['non_gems'] // max(stats['gems'], 1)})"
        )

    # Comparar con datos usados en el modelo actual
    if current_meta:
        data_info = current_meta.get("results", {}).get("data_info", {})
        train_samples = data_info.get("total_samples", 0)
        new_since_train = stats["total_labels"] - train_samples
        if new_since_train > 0:
            st.info(
                f"Hay **{new_since_train}** labels nuevos desde el ultimo "
                f"entrenamiento ({train_samples} usados en {latest_version})."
            )

    st.divider()

    # ------------------------------------------------------------------
    # 4. Acciones de retrain
    # ------------------------------------------------------------------
    st.subheader("Acciones de retrain")

    st.caption(
        "Los retrains se ejecutan via GitHub Actions. Abajo estan los "
        "comandos para ejecutarlos desde la terminal."
    )

    # Ejecutar Retrain
    st.markdown("**Ejecutar Retrain completo**")
    st.markdown(
        "Re-entrena los modelos con todos los datos etiquetados actuales. "
        "Genera una nueva version y sube artefactos a Supabase Storage."
    )
    st.code(
        "gh workflow run manual-retrain.yml --ref main",
        language="bash",
    )
    st.caption(
        "Opciones adicionales: `-f skip_labels=true` (no recalcular labels), "
        "`-f skip_features=true` (no recalcular features)."
    )

    st.markdown("---")

    # Ejecutar Drift Check
    st.markdown("**Ejecutar Drift Check**")
    st.markdown(
        "Verifica si hay drift en los datos actuales respecto al modelo. "
        "Si detecta drift, marca el reporte como 'necesita re-entrenamiento'."
    )
    st.code(
        "gh workflow run check-retrain.yml --ref main",
        language="bash",
    )

    st.markdown("---")

    # Retrain local (pipeline directo)
    st.markdown("**Retrain local (pipeline directo)**")
    st.markdown(
        "Para ejecutar el retrain directamente en tu maquina local:"
    )
    st.code(
        "python scripts/retrain_pipeline.py --skip-labels --skip-features",
        language="bash",
    )
    st.caption(
        "Flags: `--skip-labels` (usa labels existentes), "
        "`--skip-features` (usa features existentes), "
        "`--version vN` (especificar número de version)."
    )

    st.markdown("---")

    # Rollback
    st.markdown("**Rollback a version anterior**")
    st.markdown(
        "Para usar una version anterior del modelo, actualiza "
        "`data/models/latest_version.txt` con el nombre de la version deseada."
    )
    if all_versions:
        version_names = [v.get("version", "?") for v in all_versions]
        st.code(
            f"echo '{version_names[1] if len(version_names) > 1 else 'vN'}' > data/models/latest_version.txt",
            language="bash",
        )
        st.caption(
            f"Versiones disponibles: {', '.join(version_names)}"
        )

    st.divider()

    # ------------------------------------------------------------------
    # 5. Reporte de seleccion de features
    # ------------------------------------------------------------------
    st.subheader("Seleccion de features")

    st.caption(
        "Features utilizadas en el modelo actual. Se muestran las features "
        "originales, las seleccionadas por el pipeline y las descartadas."
    )

    if current_meta:
        feature_names = current_meta.get("feature_names", [])
        num_features = current_meta.get("num_features", len(feature_names))

        st.metric("Features en el modelo", num_features)

        # Mostrar lista de features en un expander
        if feature_names:
            with st.expander(f"Ver las {num_features} features ({', '.join(feature_names[:3])}...)"):
                # Agrupar features por categoria (basado en prefijo)
                categories = _categorize_features(feature_names)
                for cat_name, features in categories.items():
                    st.markdown(f"**{cat_name}** ({len(features)})")
                    st.markdown(", ".join([f"`{f}`" for f in features]))

        # Intentar cargar feature_columns.json para info de seleccion
        feat_cols = _load_feature_columns()
        if feat_cols:
            original = feat_cols.get("original", [])
            selected = feat_cols.get("selected", [])
            removed = feat_cols.get("removed", [])

            if original and selected:
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Features originales", len(original))
                col_b.metric("Features seleccionadas", len(selected))
                col_c.metric("Features descartadas", len(removed) if removed else len(original) - len(selected))

                if removed:
                    with st.expander("Features descartadas"):
                        st.markdown(", ".join([f"`{f}`" for f in removed]))
    else:
        st.info("No hay metadata del modelo para mostrar features.")


# ============================================================
# COMPONENTES AUXILIARES
# ============================================================

def _render_model_card(meta: dict, is_current: bool = False):
    """
    Renderiza una tarjeta con información de un modelo.

    Muestra version, fecha, métricas principales de RF y XGB,
    y número de features.
    """
    version = meta.get("version", "?")
    trained_at = meta.get("trained_at", "N/A")
    results = meta.get("results", {})
    num_features = meta.get("num_features", "?")

    # Formatear fecha
    if trained_at and trained_at != "N/A":
        try:
            dt = pd.to_datetime(trained_at)
            trained_str = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            trained_str = str(trained_at)[:19]
    else:
        trained_str = "N/A"

    # Extraer metricas
    rf = results.get("random_forest", {})
    xgb = results.get("xgboost", {})
    data_info = results.get("data_info", {})

    # Fila de version e info
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Version",
        version,
        delta="activa" if is_current else None,
    )
    col2.metric("Entrenado", trained_str)
    col3.metric("Features", num_features)

    # Metricas de modelos
    st.markdown("**Métricas de validación:**")
    col_rf, col_xgb = st.columns(2)

    with col_rf:
        st.markdown("**Random Forest**")
        sub1, sub2, sub3 = st.columns(3)
        sub1.metric("CV F1", f"{rf.get('cv_f1_mean', 0):.3f}")
        sub2.metric("Val F1", f"{rf.get('val_f1', 0):.3f}")
        sub3.metric(
            "Threshold",
            f"{rf.get('optimal_threshold', 0.5):.2f}",
        )

    with col_xgb:
        st.markdown("**XGBoost**")
        sub1, sub2, sub3 = st.columns(3)
        sub1.metric("CV F1", f"{xgb.get('cv_f1_mean', 0):.3f}")
        sub2.metric("Val F1", f"{xgb.get('val_f1', 0):.3f}")
        sub3.metric(
            "Threshold",
            f"{xgb.get('optimal_threshold', 0.5):.2f}",
        )

    # Info de datos si disponible
    if data_info:
        st.caption(
            f"Datos: {data_info.get('total_samples', '?')} muestras "
            f"({data_info.get('train_samples', '?')} train, "
            f"{data_info.get('test_samples', '?')} test), "
            f"{data_info.get('n_features', '?')} features"
        )


def _render_version_comparison_chart(all_versions: list[dict]):
    """
    Renderiza un grafico de barras comparando F1 scores entre versiones.

    Muestra RF y XGB F1 de validación para las ultimas 10 versiones.
    """
    # Tomar solo las ultimas 10 versiones (las mas recientes)
    recent = all_versions[:10]

    if len(recent) < 2:
        return

    # Preparar datos
    versions = []
    rf_f1s = []
    xgb_f1s = []

    for meta in reversed(recent):  # Orden cronologico
        v = meta.get("version", "?")
        results = meta.get("results", {})
        rf = results.get("random_forest", {})
        xgb = results.get("xgboost", {})

        versions.append(v)
        rf_f1s.append(rf.get("val_f1", 0))
        xgb_f1s.append(xgb.get("val_f1", 0))

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=versions,
        y=rf_f1s,
        name="RF Val F1",
        marker_color="#2ecc71",
    ))

    fig.add_trace(go.Bar(
        x=versions,
        y=xgb_f1s,
        name="XGB Val F1",
        marker_color="#e67e22",
    ))

    fig.update_layout(
        title="Comparacion de F1 Score por version",
        xaxis_title="Version",
        yaxis_title="F1 Score (validación)",
        barmode="group",
        height=400,
        yaxis=dict(range=[0, 1]),
    )

    st.plotly_chart(fig, use_container_width=True)


def _categorize_features(feature_names: list[str]) -> dict[str, list[str]]:
    """
    Agrupa features por categoria basandose en su nombre/prefijo.

    Categorias:
    - Holders: top1_, top5_, holder_, whale_, new_whale_
    - Liquidez: liquidity_, liq_, initial_liquidity_
    - Precio: return_, drawdown_, volatility_, first_hour_
    - Volumen: volume_, green_candle_, up_days_
    - Social: buyers_, sellers_, avg_tx_, buyer_, seller_
    - Contrato: contract_, is_, has_
    - Tecnico: bb_, atr_, rsi_
    - Market Context: launch_
    - Otros: resto
    """
    categories = {
        "Holders / Tokenomics": [],
        "Liquidez": [],
        "Precio / Returns": [],
        "Volumen": [],
        "Social / Trading": [],
        "Contrato": [],
        "Indicadores Tecnicos": [],
        "Contexto de Mercado": [],
        "Otros": [],
    }

    for feat in feature_names:
        f = feat.lower()
        if any(f.startswith(p) for p in ["top1", "top5", "holder", "whale", "new_whale"]):
            categories["Holders / Tokenomics"].append(feat)
        elif any(f.startswith(p) for p in ["liquidity", "liq_", "initial_liquidity"]):
            categories["Liquidez"].append(feat)
        elif any(f.startswith(p) for p in ["return_", "drawdown", "volatility", "first_hour", "close_max"]):
            categories["Precio / Returns"].append(feat)
        elif any(f.startswith(p) for p in ["volume", "green_candle", "up_days"]):
            categories["Volumen"].append(feat)
        elif any(f.startswith(p) for p in ["buyers", "sellers", "avg_tx", "buyer_", "seller_", "tx_"]):
            categories["Social / Trading"].append(feat)
        elif any(f.startswith(p) for p in ["contract", "is_", "has_"]):
            categories["Contrato"].append(feat)
        elif any(f.startswith(p) for p in ["bb_", "atr_", "rsi_"]):
            categories["Indicadores Tecnicos"].append(feat)
        elif any(f.startswith(p) for p in ["launch_"]):
            categories["Contexto de Mercado"].append(feat)
        else:
            categories["Otros"].append(feat)

    # Filtrar categorias vacias
    return {k: v for k, v in categories.items() if v}
