"""
feature_importance.py - Pagina de importancia de features (SHAP).

Muestra:
- Top 15 features por SHAP value medio absoluto
- Summary plot de SHAP
- Dependencia de features individuales
- Interpretacion de cada feature top
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from config import MODELS_DIR, PROCESSED_DIR

# Colores para SHAP
SHAP_COLOR_POSITIVE = "#e74c3c"  # rojo = empuja hacia gem
SHAP_COLOR_NEGATIVE = "#3498db"  # azul = empuja hacia no-gem


@st.cache_data(ttl=300)
def load_shap_values():
    """Carga los valores SHAP desde CSV o Parquet."""
    for base_dir in [PROCESSED_DIR, MODELS_DIR]:
        for ext in ["parquet", "csv"]:
            path = base_dir / f"shap_values.{ext}"
            if path.exists():
                try:
                    if ext == "parquet":
                        return pd.read_parquet(path)
                    else:
                        return pd.read_csv(path)
                except Exception:
                    pass
    return None


@st.cache_data(ttl=300)
def load_feature_values():
    """Carga los valores originales de features para graficos de dependencia."""
    filenames = ["X_train.csv", "X_test.csv", "X_train.parquet", "X_test.parquet"]
    for base_dir in [PROCESSED_DIR, MODELS_DIR]:
        for fn in filenames:
            path = base_dir / fn
            if path.exists():
                try:
                    if fn.endswith(".parquet"):
                        return pd.read_parquet(path)
                    else:
                        return pd.read_csv(path)
                except Exception:
                    continue
    return None


# Interpretaciones en lenguaje llano
FEATURE_INTERPRETATIONS = {
    "makers_24h": "Número de market makers (proveedores de liquidez) activos en 24h. "
                  "Mas makers = mas gente poniendo dinero para que se pueda tradear el token. "
                  "Es la senal mas fuerte de que un token tiene traccion real.",
    "buyers_24h": "Compradores unicos en las primeras 24 horas. "
                  "Muchos compradores indica que hay demanda organica, no solo un par de ballenas.",
    "tx_count_24h": "Total de transacciones en 24h. "
                    "Un token activo con muchas transacciones tiene una comunidad comprometida.",
    "sellers_24h": "Vendedores unicos en 24h. "
                   "Paradojicamente, tener vendedores es bueno: indica actividad real y liquidez. "
                   "Los tokens sin vendedores suelen ser iliquidos o de muy baja capitalización.",
    "liq_to_mcap_ratio": "Liquidez del pool dividida por el Market Cap. "
                         "Un ratio alto (ej. 0.1+) significa que hay suficiente liquidez "
                         "respecto al tamano del token = pool saludable.",
    "buyer_seller_ratio_24h": "Ratio compradores/vendedores. "
                              "Mayor que 1 = mas gente comprando que vendiendo (presion compradora). "
                              "Un ratio muy alto puede indicar FOMO.",
    "volume_trend_slope": "Tendencia del volumen en el tiempo. "
                          "Valor positivo = el volumen crece dia a dia (buena senal). "
                          "Negativo = el interes esta cayendo.",
    "volume_spike_ratio": "Maximo volumen en un momento / volumen promedio. "
                          "Un spike alto indica momentos de FOMO o noticias virales.",
    "volume_to_liq_ratio_24h": "Volumen de trading dividido por la liquidez. "
                                "Un ratio alto sugiere trading muy activo respecto a la liquidez disponible.",
    "return_24h": "Retorno del precio en las primeras 24 horas. "
                  "Un retorno positivo sugiere momentum inicial.",
    "return_7d": "Retorno del precio en 7 dias. Los gems suelen mantener subidas sostenidas.",
    "return_30d": "Retorno del precio en 30 dias. Es la ventana completa de evaluacion.",
    "max_return_7d": "Maximo retorno alcanzado en los primeros 7 dias. "
                     "Los gems tipicamente alcanzan picos altos temprano.",
    "drawdown_from_peak_7d": "Caida desde el pico maximo en 7 dias. "
                             "Valores cercanos a 0 = se mantuvo cerca del maximo. "
                             "Valores muy negativos = subio y luego se desplomo.",
    "volatility_7d": "Variabilidad del precio en 7 dias. "
                     "Alta volatilidad puede indicar manipulacion o bajo volumen.",
    "green_candle_ratio_24h": "Porcentaje de velas verdes (precio subio) en 24h. "
                              "Un ratio alto indica consistencia en la subida.",
    "initial_liquidity_usd": "Liquidez en USD cuando se creo el pool. "
                             "Pools con mas liquidez inicial suelen ser proyectos mas serios.",
    "liquidity_growth_24h": "Crecimiento de la liquidez en 24h. "
                            "Si la liquidez crece, mas gente esta depositando en el pool.",
    "liquidity_growth_7d": "Crecimiento de la liquidez en 7 dias.",
    "avg_tx_size_usd": "Tamano promedio de cada transaccion en USD. "
                       "Transacciones muy grandes = ballenas. Pequenas = retail (bueno para gems).",
    "is_boosted": "Si el token pago para aparecer destacado en DexScreener. "
                  "Los boosts no garantizan calidad, pero indican que alguien invirtio en marketing.",
    "is_verified": "Si el contrato tiene su codigo fuente publicado y verificado. "
                   "Verificado = mas transparencia = menos riesgo de estafa.",
    "has_mint_authority": "Si el creador puede generar mas tokens. "
                         "Si tiene mint authority, puede crear tokens nuevos e inflar el supply (riesgo!).",
    "contract_age_hours": "Horas entre que se desplegó el contrato y el primer trade. "
                          "Contratos muy nuevos son mas riesgosos.",
    "launch_day_of_week": "Dia de la semana del lanzamiento (0=Lunes). "
                          "Algunos estudios sugieren que ciertos dias tienen mas actividad.",
    "launch_hour_utc": "Hora UTC del lanzamiento. "
                       "Lanzamientos en horario de EE.UU. suelen tener mas traccion.",
}


def render():
    """Renderiza la pagina de Importancia de Features."""
    # Guard de acceso — solo admin
    try:
        from dashboard.auth import require_admin
        require_admin()
    except ImportError:
        pass

    st.title("Importancia de Features (SHAP)")

    st.info(
        "**¿Qué es SHAP?** SHAP (SHapley Additive exPlanations) es una tecnica que "
        "explica *por que* el modelo hace cada prediccion. Para cada token, SHAP "
        "calcula cuanto contribuye cada feature (caracteristica) a la prediccion "
        "final. Es como preguntar al modelo: \"¿Qué fue lo que te convencio de que "
        "este token es un gem?\"\n\n"
        "- **SHAP positivo** (rojo) = este feature empuja la prediccion hacia \"gem\".\n"
        "- **SHAP negativo** (azul) = este feature empuja la prediccion hacia \"no-gem\".\n"
        "- **SHAP cercano a 0** = este feature no influye mucho en la prediccion."
    )

    df_shap = load_shap_values()

    if df_shap is None:
        st.warning("No se encontraron valores SHAP.")
        st.info("Ejecuta el pipeline SHAP para generar los valores.")
        return

    # Excluir columnas que no son features
    exclude_cols = {"token_id", "index", "Unnamed: 0"}
    feature_names = [c for c in df_shap.columns if c not in exclude_cols]

    if not feature_names:
        st.warning("No se encontraron features en el archivo de SHAP.")
        return

    st.success(f"SHAP cargado: {len(df_shap)} tokens, {len(feature_names)} features.")

    st.divider()

    # ------------------------------------------------------------------
    # 1. Top 15 features mas importantes
    # ------------------------------------------------------------------
    st.subheader("Top 15 features mas importantes")

    st.caption(
        "Muestra cuales features tienen mayor impacto en las predicciones del modelo. "
        "Cuanto mas larga la barra, mas importante es ese feature para decidir "
        "si un token es gem o no."
    )

    mean_abs_shap = df_shap[feature_names].abs().mean().sort_values(ascending=False)
    top_15 = mean_abs_shap.head(15)

    df_top = pd.DataFrame({
        "Feature": top_15.index,
        "Impacto medio": top_15.values,
    })

    fig_bar = px.bar(
        df_top,
        x="Impacto medio",
        y="Feature",
        orientation="h",
        title="Top 15 Features por Impacto en Prediccion",
        color="Impacto medio",
        color_continuous_scale=["#3498db", "#e74c3c"],
    )
    fig_bar.update_layout(
        yaxis=dict(autorange="reversed"),
        height=500,
        showlegend=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------------
    # 2. SHAP Summary Plot
    # ------------------------------------------------------------------
    st.subheader("SHAP Summary Plot")

    df_features = load_feature_values()

    n_summary = st.slider(
        "Número de features a mostrar", min_value=5,
        max_value=min(25, len(feature_names)),
        value=min(12, len(feature_names)), key="summary_n",
    )
    top_summary_features = mean_abs_shap.head(n_summary).index.tolist()

    if df_features is not None and len(df_features) == len(df_shap):
        st.caption(
            "Cada punto es un token. La posicion horizontal indica si el feature "
            "empuja la prediccion hacia gem (derecha) o no-gem (izquierda). "
            "El color indica el valor real del feature: rojo = valor alto, azul = bajo."
        )

        fig_summary = go.Figure()

        for i, feat in enumerate(reversed(top_summary_features)):
            shap_vals = df_shap[feat].values
            if feat in df_features.columns:
                feat_vals = df_features[feat].values
                fmin, fmax = np.nanmin(feat_vals), np.nanmax(feat_vals)
                if fmax > fmin:
                    feat_norm = (feat_vals - fmin) / (fmax - fmin)
                else:
                    feat_norm = np.full_like(feat_vals, 0.5)
            else:
                feat_norm = np.full(len(shap_vals), 0.5)

            jitter = np.random.default_rng(42).normal(0, 0.12, len(shap_vals))

            fig_summary.add_trace(go.Scatter(
                x=shap_vals,
                y=np.full(len(shap_vals), i) + jitter,
                mode="markers",
                marker=dict(
                    size=6,
                    color=feat_norm,
                    colorscale=[[0, "#3498db"], [1, "#e74c3c"]],
                    opacity=0.7,
                    showscale=(i == 0),
                    colorbar=dict(
                        title="Valor del<br>feature",
                        len=0.5,
                        tickvals=[0, 1],
                        ticktext=["Bajo", "Alto"],
                    ) if i == 0 else None,
                ),
                name=feat,
                showlegend=False,
                hovertemplate=f"{feat}<br>SHAP: %{{x:.4f}}<extra></extra>",
            ))

        fig_summary.update_layout(
            title="SHAP Summary Plot",
            xaxis_title="SHAP Value (impacto en prediccion)",
            yaxis=dict(
                tickmode="array",
                tickvals=list(range(len(top_summary_features))),
                ticktext=list(reversed(top_summary_features)),
            ),
            height=max(400, n_summary * 35),
        )
        fig_summary.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
        st.plotly_chart(fig_summary, use_container_width=True)

    else:
        # Fallback: box plot
        st.caption(
            "Distribución de valores SHAP para cada feature. Valores a la derecha "
            "de la línea central (0) indican que el feature empuja hacia 'gem'."
        )
        shap_melted = df_shap[top_summary_features].melt(
            var_name="Feature", value_name="SHAP Value"
        )
        fig_box = px.box(
            shap_melted,
            x="SHAP Value", y="Feature", orientation="h",
            title="Distribución de SHAP Values por feature",
            color_discrete_sequence=["#3498db"],
        )
        fig_box.update_layout(height=max(400, n_summary * 30))
        fig_box.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
        st.plotly_chart(fig_box, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------------
    # 3. Dependencia de feature individual
    # ------------------------------------------------------------------
    st.subheader("Dependencia de Feature Individual")

    st.caption(
        "Selecciona un feature para ver como su valor afecta la prediccion. "
        "Si los puntos suben (SHAP positivo) cuando el valor del feature es alto, "
        "significa que valores altos de ese feature favorecen la prediccion de 'gem'."
    )

    selected_feature = st.selectbox(
        "Selecciona un feature",
        top_summary_features,
        index=0,
        key="dep_feature",
    )

    if df_features is not None and selected_feature in df_features.columns:
        dep_df = pd.DataFrame({
            "Valor del feature": df_features[selected_feature].values,
            "SHAP Value": df_shap[selected_feature].values,
        })

        fig_dep = px.scatter(
            dep_df,
            x="Valor del feature", y="SHAP Value",
            title=f"Dependencia: {selected_feature}",
            opacity=0.6,
            color="SHAP Value",
            color_continuous_scale=[[0, "#3498db"], [0.5, "#95a5a6"], [1, "#e74c3c"]],
        )
        fig_dep.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig_dep.update_layout(height=450)
        st.plotly_chart(fig_dep, use_container_width=True)
    else:
        fig_hist = px.histogram(
            df_shap, x=selected_feature, nbins=30,
            title=f"Distribución de SHAP para {selected_feature}",
            color_discrete_sequence=["#3498db"],
        )
        fig_hist.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
        st.plotly_chart(fig_hist, use_container_width=True)

    # Descripcion del feature seleccionado
    desc = FEATURE_INTERPRETATIONS.get(selected_feature, "")
    if desc:
        st.info(f"**{selected_feature}**: {desc}")

    st.divider()

    # ------------------------------------------------------------------
    # 4. Interpretacion de los top features
    # ------------------------------------------------------------------
    st.subheader("¿Qué nos dicen los top features?")

    st.caption(
        "Resumen en lenguaje llano de que significa cada feature importante "
        "para la deteccion de gems."
    )

    top_10_for_interp = mean_abs_shap.head(10).index.tolist()

    for rank, feat in enumerate(top_10_for_interp, 1):
        importance = mean_abs_shap[feat]
        interpretation = FEATURE_INTERPRETATIONS.get(feat, None)

        if interpretation:
            st.markdown(
                f"**{rank}. {feat}** (impacto: {importance:.4f})\n\n"
                f"> {interpretation}"
            )
        else:
            st.markdown(
                f"**{rank}. {feat}** (impacto: {importance:.4f})\n\n"
                f"> Feature personalizado. Revisa el modulo de features para su definicion."
            )

    st.divider()

    st.subheader("Conclusion")

    # Generar conclusion dinamica basada en las top features reales
    if top_10_for_interp:
        top_3_names = top_10_for_interp[:3]
        st.success(
            f"**Hallazgo principal**: Las features mas influyentes son: "
            f"**{', '.join(top_3_names)}**. "
            "Estas características tienen el mayor impacto en la prediccion del modelo. "
            "A medida que se reentrenan los modelos con mas datos, "
            "esta clasificacion puede cambiar."
        )
    else:
        st.info("No hay datos de importancia de features disponibles.")
