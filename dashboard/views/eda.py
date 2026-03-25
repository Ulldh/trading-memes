"""
eda.py - Pagina de Analisis Exploratorio de Datos (EDA).

Permite explorar visualmente los features calculados:
- Scatter plot de 2 features cualesquiera (coloreado por label)
- Histogramas de distribucion por label
- Mapa de correlaciones (heatmap)
- Box plots comparativos por categoria de label
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from src.data.supabase_storage import get_storage as _get_storage
from config import PROCESSED_DIR

# Colores consistentes para las labels
LABEL_COLORS = {
    "gem": "#2ecc71",
    "moderate_success": "#3498db",
    "neutral": "#95a5a6",
    "failure": "#e74c3c",
    "rug": "#1a1a1a",
    "sin_label": "#bdc3c7",
}


@st.cache_resource
def get_storage():
    return _get_storage()


@st.cache_data(ttl=300)
def load_features_and_labels():
    """Carga features y labels y los combina."""
    storage = get_storage()

    try:
        df_features = storage.get_features_df()
    except Exception:
        df_features = pd.DataFrame()

    # Fallback: cargar desde parquet si SQLite esta vacio
    if df_features.empty:
        parquet_path = PROCESSED_DIR / "features.parquet"
        if parquet_path.exists():
            try:
                df_features = pd.read_parquet(parquet_path)
            except Exception:
                pass

    try:
        df_labels = storage.query("SELECT token_id, label_multi FROM labels")
    except Exception:
        df_labels = pd.DataFrame()

    try:
        df_tokens = storage.query("SELECT token_id, chain, symbol FROM tokens")
    except Exception:
        df_tokens = pd.DataFrame()

    if df_features.empty:
        return pd.DataFrame()

    df = df_features.copy()

    # Asegurar que token_id es columna (puede venir como index)
    if "token_id" not in df.columns and df.index.name == "token_id":
        df = df.reset_index()

    if not df_labels.empty:
        df = df.merge(df_labels, on="token_id", how="left")
    else:
        df["label_multi"] = "sin_label"

    # Solo mergear columnas de tokens que NO existan ya en features
    # (features puede tener 'chain' y 'dex' propios, lo que causa conflicto)
    if not df_tokens.empty:
        cols_to_add = [c for c in df_tokens.columns if c not in df.columns or c == "token_id"]
        df = df.merge(df_tokens[cols_to_add], on="token_id", how="left")

    # Asegurar que existan las columnas esperadas
    if "chain" not in df.columns:
        df["chain"] = "desconocido"
    if "symbol" not in df.columns:
        df["symbol"] = ""

    # Rellenar labels faltantes
    df["label_multi"] = df["label_multi"].fillna("sin_label")

    return df


def get_numeric_columns(df):
    """Devuelve las columnas numericas del DataFrame, excluyendo IDs."""
    exclude = {
        "token_id", "label_multi", "label_binary", "chain", "computed_at",
        "index", "symbol", "dex",
    }
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    return [c for c in numeric_cols if c not in exclude]


# Descripciones de features para tooltips
FEATURE_DESCRIPTIONS = {
    "initial_liquidity_usd": "Liquidez inicial en USD del pool cuando se creo",
    "liquidity_growth_24h": "Cuanto crecio (%) la liquidez en las primeras 24 horas",
    "liquidity_growth_7d": "Cuanto crecio (%) la liquidez en 7 dias",
    "liq_to_mcap_ratio": "Liquidez / Market Cap. Ratio alto = pool saludable",
    "volume_to_liq_ratio_24h": "Volumen 24h / Liquidez. Que tan activamente se tradea",
    "return_24h": "Retorno del precio en 24 horas (1.0 = +100%)",
    "return_48h": "Retorno del precio en 48 horas",
    "return_7d": "Retorno del precio en 7 dias",
    "return_30d": "Retorno del precio en 30 dias",
    "max_return_7d": "Maximo retorno alcanzado en 7 dias (el pico)",
    "drawdown_from_peak_7d": "Caida desde el maximo en 7 dias (negativo = perdida)",
    "volatility_7d": "Volatilidad (variabilidad) del precio en 7 dias",
    "volume_spike_ratio": "Pico de volumen vs promedio. Alto = momentos de FOMO",
    "green_candle_ratio_24h": "% de velas verdes (precio subio) en 24h",
    "volume_trend_slope": "Tendencia del volumen. Positivo = volumen creciendo",
    "buyers_24h": "Compradores unicos en 24 horas",
    "sellers_24h": "Vendedores unicos en 24 horas",
    "buyer_seller_ratio_24h": "Compradores / Vendedores. >1 = presion compradora",
    "makers_24h": "Market makers activos en 24h (proveedores de liquidez)",
    "tx_count_24h": "Total de transacciones en 24 horas",
    "avg_tx_size_usd": "Tamano promedio de transaccion en USD",
    "is_boosted": "Si el token pago para aparecer destacado en DexScreener",
    "is_verified": "Si el contrato tiene su codigo fuente verificado",
    "contract_age_hours": "Horas entre el deploy del contrato y el primer trade",
    "launch_day_of_week": "Dia de la semana del lanzamiento (0=Lunes, 6=Domingo)",
    "launch_hour_utc": "Hora UTC del lanzamiento (0-23)",
    "has_mint_authority": "Si el creador puede generar mas tokens (riesgo de inflacion)",
}


def render():
    """Renderiza la pagina de Analisis Exploratorio."""
    st.title("Analisis Exploratorio (EDA)")

    st.info(
        "**Que es EDA?** El Analisis Exploratorio de Datos es como \"mirar los datos "
        "antes de modelar\". Aqui puedes comparar visualmente las caracteristicas "
        "(features) de los tokens que fueron gems vs los que fracasaron, buscando "
        "patrones que distingan a unos de otros."
    )

    df = load_features_and_labels()

    if df.empty:
        st.warning(
            "No hay features calculados todavia. "
            "Ejecuta primero el pipeline de feature engineering."
        )
        return

    numeric_cols = get_numeric_columns(df)

    if not numeric_cols:
        st.warning("No se encontraron columnas numericas en los features.")
        return

    # ------------------------------------------------------------------
    # Filtros en la barra lateral
    # ------------------------------------------------------------------
    st.sidebar.subheader("Filtros EDA")

    chains_disponibles = ["Todas"] + sorted(df["chain"].dropna().unique().tolist())
    chain_seleccionada = st.sidebar.selectbox("Cadena", chains_disponibles)

    labels_disponibles = ["Todas"] + sorted(df["label_multi"].dropna().unique().tolist())
    label_seleccionada = st.sidebar.selectbox("Label", labels_disponibles)

    df_filtrado = df.copy()
    if chain_seleccionada != "Todas":
        df_filtrado = df_filtrado[df_filtrado["chain"] == chain_seleccionada]
    if label_seleccionada != "Todas":
        df_filtrado = df_filtrado[df_filtrado["label_multi"] == label_seleccionada]

    st.caption(f"Mostrando {len(df_filtrado)} tokens de {len(df)} totales.")

    if df_filtrado.empty:
        st.warning("No hay datos con los filtros seleccionados.")
        return

    st.divider()

    # ------------------------------------------------------------------
    # 1. Scatter plot: dos features cualesquiera
    # ------------------------------------------------------------------
    st.subheader("Scatter Plot: comparar dos features")

    st.caption(
        "Selecciona dos caracteristicas y mira como se distribuyen los tokens. "
        "Cada punto es un token, coloreado segun su clasificacion. "
        "Si los colores se agrupan en zonas distintas, significa que esa "
        "combinacion de features ayuda a distinguir gems de failures."
    )

    col_scatter1, col_scatter2 = st.columns(2)
    with col_scatter1:
        feature_x = st.selectbox(
            "Feature eje X", numeric_cols, index=0, key="scatter_x",
            help=FEATURE_DESCRIPTIONS.get(numeric_cols[0], ""),
        )
    with col_scatter2:
        default_y = min(1, len(numeric_cols) - 1)
        feature_y = st.selectbox(
            "Feature eje Y", numeric_cols, index=default_y, key="scatter_y",
            help=FEATURE_DESCRIPTIONS.get(numeric_cols[default_y], ""),
        )

    # Tooltip con el nombre del token
    hover_cols = []
    if "symbol" in df_filtrado.columns:
        hover_cols.append("symbol")
    if "token_id" in df_filtrado.columns:
        hover_cols.append("token_id")

    fig_scatter = px.scatter(
        df_filtrado,
        x=feature_x,
        y=feature_y,
        color="label_multi",
        color_discrete_map=LABEL_COLORS,
        title=f"{feature_x} vs {feature_y}",
        opacity=0.7,
        hover_data=hover_cols if hover_cols else None,
    )
    fig_scatter.update_layout(legend_title_text="Clasificacion")
    st.plotly_chart(fig_scatter, use_container_width=True)

    # Descripcion de los features seleccionados
    desc_x = FEATURE_DESCRIPTIONS.get(feature_x, "")
    desc_y = FEATURE_DESCRIPTIONS.get(feature_y, "")
    if desc_x or desc_y:
        with st.expander("Que significan estos features?"):
            if desc_x:
                st.markdown(f"- **{feature_x}**: {desc_x}")
            if desc_y:
                st.markdown(f"- **{feature_y}**: {desc_y}")

    st.divider()

    # ------------------------------------------------------------------
    # 2. Histograma: distribucion de un feature por label
    # ------------------------------------------------------------------
    st.subheader("Histograma: distribucion por clasificacion")

    st.caption(
        "Muestra como se distribuye un feature para cada tipo de token. "
        "Si las barras de 'gem' (verde) estan en una zona diferente a las de "
        "'failure' (rojo), ese feature es util para la prediccion."
    )

    feature_hist = st.selectbox(
        "Feature para histograma", numeric_cols, index=0, key="hist_feat",
    )

    fig_hist = px.histogram(
        df_filtrado,
        x=feature_hist,
        color="label_multi",
        color_discrete_map=LABEL_COLORS,
        title=f"Distribucion de {feature_hist}",
        barmode="overlay",
        opacity=0.7,
        nbins=30,
    )
    fig_hist.update_layout(legend_title_text="Clasificacion")
    st.plotly_chart(fig_hist, use_container_width=True)

    desc = FEATURE_DESCRIPTIONS.get(feature_hist, "")
    if desc:
        st.caption(f"**{feature_hist}**: {desc}")

    st.divider()

    # ------------------------------------------------------------------
    # 3. Mapa de correlaciones
    # ------------------------------------------------------------------
    st.subheader("Mapa de correlaciones")

    st.caption(
        "Muestra que tan relacionados estan los features entre si. "
        "Valores cercanos a **+1** (rojo) = se mueven juntos. "
        "Valores cercanos a **-1** (azul) = se mueven en direccion opuesta. "
        "Valores cercanos a **0** (blanco) = no hay relacion. "
        "Features muy correlacionados son redundantes (dan la misma info)."
    )

    top_n = min(15, len(numeric_cols))
    variances = df_filtrado[numeric_cols].var().sort_values(ascending=False)
    top_features = variances.head(top_n).index.tolist()

    corr_matrix = df_filtrado[top_features].corr()

    fig_corr = px.imshow(
        corr_matrix,
        title=f"Correlacion entre top {top_n} features",
        color_continuous_scale="RdBu_r",
        zmin=-1, zmax=1,
        aspect="auto",
        text_auto=".2f",
    )
    fig_corr.update_layout(width=800, height=800, xaxis_tickangle=-45)
    st.plotly_chart(fig_corr, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------------
    # 4. Box plots
    # ------------------------------------------------------------------
    st.subheader("Box Plot: comparar por clasificacion")

    st.caption(
        "Un box plot muestra el rango de valores de un feature para cada grupo. "
        "La caja contiene el 50% central de los datos, la linea del medio es la "
        "mediana (valor tipico), y los puntos fuera son valores atipicos (outliers)."
    )

    feature_box = st.selectbox(
        "Feature para box plot", numeric_cols, index=0, key="box_feat",
    )

    fig_box = px.box(
        df_filtrado,
        x="label_multi",
        y=feature_box,
        color="label_multi",
        color_discrete_map=LABEL_COLORS,
        title=f"Distribucion de {feature_box} por clasificacion",
        points="outliers",
    )
    fig_box.update_layout(
        xaxis_title="Clasificacion",
        yaxis_title=feature_box,
        showlegend=False,
    )
    st.plotly_chart(fig_box, use_container_width=True)

    desc = FEATURE_DESCRIPTIONS.get(feature_box, "")
    if desc:
        st.caption(f"**{feature_box}**: {desc}")
