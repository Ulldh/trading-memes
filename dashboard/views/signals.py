"""
signals.py - Pagina de señales y backtesting.

Muestra:
  Tab 1: Señales actuales - tokens con probabilidad alta de ser gem.
  Tab 2: Historico - señales pasadas y su resultado real.
  Tab 3: Backtesting - simulacion de rendimiento del modelo.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

from src.data.supabase_storage import get_storage as _get_storage
from dashboard.constants import SIGNAL_COLORS

try:
    from config import MODELS_DIR
except ImportError:
    MODELS_DIR = Path("data/models")

try:
    from src.models.scorer import SIGNAL_THRESHOLDS
except ImportError:
    SIGNAL_THRESHOLDS = {"STRONG": 0.80, "MEDIUM": 0.65, "WEAK": 0.50}

SIGNALS_DIR = Path("signals")


@st.cache_resource
def get_storage():
    return _get_storage()


def load_latest_signals() -> pd.DataFrame:
    """Carga el CSV de señales mas reciente de signals/."""
    if not SIGNALS_DIR.exists():
        return pd.DataFrame()

    csv_files = sorted(SIGNALS_DIR.glob("candidates_*.csv"), reverse=True)
    if not csv_files:
        return pd.DataFrame()

    try:
        return pd.read_csv(csv_files[0])
    except Exception:
        return pd.DataFrame()


def load_all_signals() -> pd.DataFrame:
    """Carga todos los CSVs de señales historicas."""
    if not SIGNALS_DIR.exists():
        return pd.DataFrame()

    csv_files = sorted(SIGNALS_DIR.glob("candidates_*.csv"))
    if not csv_files:
        return pd.DataFrame()

    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            # Extraer fecha del nombre del archivo
            date_str = f.stem.replace("candidates_", "")
            df["signal_date"] = date_str
            dfs.append(df)
        except Exception:
            continue

    if not dfs:
        return pd.DataFrame()

    return pd.concat(dfs, ignore_index=True)


def render():
    """Renderiza la pagina de Señales."""
    st.title("Señales de Gem")

    st.info(
        "**¿Qué es esto?** Esta pagina muestra los tokens que nuestro modelo de "
        "Machine Learning considera con mayor probabilidad de ser 'gems' (10x+). "
        "Las señales se generan automáticamente cada dia despues de la recopilacion.\n\n"
        "**Niveles de senal:**\n"
        f"- **STRONG** (>{SIGNAL_THRESHOLDS['STRONG']:.0%}): Alta confianza. El modelo esta muy seguro.\n"
        f"- **MEDIUM** (>{SIGNAL_THRESHOLDS['MEDIUM']:.0%}): Confianza moderada. Vale la pena investigar.\n"
        f"- **WEAK** (>{SIGNAL_THRESHOLDS['WEAK']:.0%}): Baja confianza. Monitorear pero no actuar.\n\n"
        "**IMPORTANTE**: Esto NO es consejo financiero. Los memecoins son "
        "extremadamente riesgosos. Nunca inviertas mas de lo que puedas perder."
    )

    # Tabs
    tab1, tab2, tab3 = st.tabs([
        "Señales Actuales",
        "Historico de Señales",
        "Backtesting",
    ])

    # ==========================================================
    # TAB 1: SENALES ACTUALES
    # ==========================================================
    with tab1:
        render_current_signals()

    # ==========================================================
    # TAB 2: HISTORICO
    # ==========================================================
    with tab2:
        render_signal_history()

    # ==========================================================
    # TAB 3: BACKTESTING
    # ==========================================================
    with tab3:
        render_backtesting()


def render_current_signals():
    """Muestra las señales mas recientes."""
    st.subheader("Señales del Ultimo Análisis")

    df = load_latest_signals()

    if df.empty:
        st.warning(
            "No hay señales generadas todavia. Las señales se crean "
            "automáticamente con el script diario, o puedes generarlas "
            "manualmente ejecutando:\n\n"
            "```bash\nbash scripts/daily_signals.sh\n```"
        )
        return

    # Filtros mejorados
    st.subheader("Filtros")
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        # Filtrar por nivel de senal
        signal_options = ["Todas", "STRONG", "MEDIUM", "WEAK"]
        selected_signal = st.selectbox("Filtrar por senal", signal_options)

    with col_f2:
        # Filtrar por cadena
        if "chain" in df.columns:
            chain_options = ["Todas"] + sorted(df["chain"].dropna().unique().tolist())
            selected_chain = st.selectbox("Filtrar por cadena", chain_options)
        else:
            selected_chain = "Todas"

    with col_f3:
        # Filtrar por probabilidad minima
        if "probability" in df.columns:
            min_prob = st.slider(
                "Probabilidad mínima",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                step=0.05,
                format="%.2f",
                help="Muestra solo tokens con probabilidad igual o mayor a este valor."
            )
        else:
            min_prob = 0.0

    # Aplicar filtros
    df_filtered = df.copy()
    if selected_signal != "Todas" and "signal" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["signal"] == selected_signal]
    if selected_chain != "Todas" and "chain" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["chain"] == selected_chain]
    if "probability" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["probability"] >= min_prob]

    if df_filtered.empty:
        st.info("No hay señales con los filtros seleccionados.")
        return

    # Metricas resumen
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Señales", len(df_filtered))
    if "signal" in df_filtered.columns:
        col2.metric("STRONG", (df_filtered["signal"] == "STRONG").sum())
        col3.metric("MEDIUM", (df_filtered["signal"] == "MEDIUM").sum())
        col4.metric("WEAK", (df_filtered["signal"] == "WEAK").sum())

    # Boton de exportacion CSV
    if not df_filtered.empty:
        csv = df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar CSV (filtrado)",
            data=csv,
            file_name=f"senales_filtradas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            help="Descarga las señales filtradas en formato CSV para análisis externo."
        )

    st.divider()

    # Tabla de senales con colores
    if "signal" in df_filtered.columns:
        # Ordenar por probabilidad descendente (si la columna existe)
        if "probability" in df_filtered.columns:
            df_display = df_filtered.sort_values("probability", ascending=False)
        else:
            df_display = df_filtered.copy()

        # Seleccionar columnas para mostrar
        display_cols = ["token_id", "chain", "symbol", "probability", "signal"]
        available_cols = [c for c in display_cols if c in df_display.columns]
        df_display = df_display[available_cols].copy()

        # Formatear probabilidad como porcentaje
        if "probability" in df_display.columns:
            df_display["probability"] = df_display["probability"].apply(
                lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
            )

        # Acortar token_id para legibilidad
        if "token_id" in df_display.columns:
            df_display["token_id"] = df_display["token_id"].apply(
                lambda x: f"{x[:8]}...{x[-6:]}" if isinstance(x, str) and len(x) > 14 else x
            )

        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df_filtered, use_container_width=True, hide_index=True)

    # Grafico de distribucion de probabilidades
    if "probability" in df.columns:
        st.subheader("Distribución de Probabilidades")
        st.caption(
            "Histograma de las probabilidades asignadas por el modelo. "
            "Tokens a la derecha (>0.65) son los candidatos mas fuertes."
        )
        fig = px.histogram(
            df, x="probability", nbins=20,
            title="Distribución de probabilidades de gem",
            labels={"probability": "Probabilidad de Gem", "count": "Cantidad de tokens"},
            color_discrete_sequence=["#3498db"],
        )
        # Agregar lineas verticales para los umbrales (dinamicos desde scorer)
        fig.add_vline(x=SIGNAL_THRESHOLDS["STRONG"], line_dash="dash", line_color="green",
                       annotation_text=f"STRONG ({SIGNAL_THRESHOLDS['STRONG']:.0%})")
        fig.add_vline(x=SIGNAL_THRESHOLDS["MEDIUM"], line_dash="dash", line_color="orange",
                       annotation_text=f"MEDIUM ({SIGNAL_THRESHOLDS['MEDIUM']:.0%})")
        fig.add_vline(x=SIGNAL_THRESHOLDS["WEAK"], line_dash="dash", line_color="blue",
                       annotation_text=f"WEAK ({SIGNAL_THRESHOLDS['WEAK']:.0%})")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    # Seccion de graficos OHLCV Candlestick
    render_ohlcv_section(df_filtered)

    # Seccion de comparador de tokens
    render_token_comparator()


def render_signal_history():
    """Muestra el histórico de señales pasadas."""
    st.subheader("Historico de Señales")
    st.caption(
        "Todas las señales generadas en dias anteriores. "
        "Puedes comparar cuantas señales se generaron cada dia."
    )

    df = load_all_signals()

    if df.empty:
        st.info("No hay histórico de señales. Se acumulara con el tiempo.")
        return

    # Filtros para historico
    if "signal_date" in df.columns:
        dates_available = sorted(df["signal_date"].unique().tolist())
        if len(dates_available) > 1:
            col_h1, col_h2 = st.columns(2)

            with col_h1:
                start_date = st.selectbox(
                    "Desde fecha",
                    options=["Todas"] + dates_available,
                    help="Filtra señales desde esta fecha."
                )

            with col_h2:
                end_date = st.selectbox(
                    "Hasta fecha",
                    options=["Todas"] + dates_available,
                    index=0,
                    help="Filtra señales hasta esta fecha."
                )

            # Aplicar filtros de fecha
            if start_date != "Todas":
                df = df[df["signal_date"] >= start_date]
            if end_date != "Todas":
                df = df[df["signal_date"] <= end_date]

            if df.empty:
                st.info("No hay señales en el rango de fechas seleccionado.")
                return

    # Boton de exportacion para historico
    if not df.empty:
        csv_historical = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Histórico CSV",
            data=csv_historical,
            file_name=f"senales_historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            help="Descarga todo el histórico de señales en formato CSV."
        )

    # Resumen por fecha
    if "signal_date" in df.columns and "signal" in df.columns:
        summary = df.groupby(["signal_date", "signal"]).size().reset_index(name="count")

        fig = px.bar(
            summary, x="signal_date", y="count", color="signal",
            title="Señales por dia y nivel",
            labels={"signal_date": "Fecha", "count": "Cantidad", "signal": "Nivel"},
            color_discrete_map=SIGNAL_COLORS,
            barmode="stack",
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    # Tabla detallada
    with st.expander("Ver tabla completa"):
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_backtesting():
    """Muestra resultados de backtesting interactivo."""
    st.subheader("Backtesting")
    st.caption(
        "El backtesting simula que hubiera pasado si hubieras seguido "
        "las señales del modelo en el pasado. Usa tokens con resultado "
        "conocido (gems y failures) para medir la precision real.\n\n"
        "**¿Cómo leer los resultados:**\n"
        "- **Precision**: De las señales que dio, cuantas eran gems reales.\n"
        "- **Recall**: De los gems que existian, cuantos detecto.\n"
        "- **F1**: Balance entre precision y recall (mas alto = mejor)."
    )

    storage = get_storage()

    # Verificar si hay datos suficientes
    labels_df = storage.query("SELECT * FROM labels")
    if labels_df.empty or len(labels_df) < 5:
        st.warning(
            f"Se necesitan al menos 5 tokens etiquetados para backtesting "
            f"(actual: {len(labels_df)}). Ejecuta retrain.sh primero."
        )
        return

    # Selector de threshold
    threshold = st.selectbox(
        "Nivel de senal para backtesting",
        ["MEDIUM (recomendado)", "STRONG", "WEAK"],
        help="El nivel minimo de senal que se consideraria como 'comprar'.",
    )
    threshold_key = threshold.split(" ")[0]

    # Boton para ejecutar backtesting
    if st.button("Ejecutar Backtesting", type="primary"):
        with st.spinner("Ejecutando backtesting..."):
            try:
                from src.models.backtester import Backtester
                bt = Backtester(storage=storage)
                results = bt.backtest_historical(signal_threshold=threshold_key)

                if "error" in results:
                    st.error(results["error"])
                    return

                # Metricas principales (acceso defensivo a claves del resultado)
                col1, col2, col3 = st.columns(3)
                col1.metric(
                    "Precision",
                    f"{results.get('precision', 0):.1%}",
                    help="De las señales, cuantas eran gems reales.",
                )
                col2.metric(
                    "Recall",
                    f"{results.get('recall', 0):.1%}",
                    help="De los gems, cuantos se detectaron.",
                )
                col3.metric(
                    "F1 Score",
                    f"{results.get('f1', 0):.4f}",
                    help="Balance entre precision y recall.",
                )

                col4, col5, col6 = st.columns(3)
                col4.metric("True Positives", results.get("true_positives", 0))
                col5.metric("False Positives", results.get("false_positives", 0))
                col6.metric("False Negatives", results.get("false_negatives", 0))

                # Resumen de rentabilidad
                if "avg_return" in results:
                    st.divider()
                    st.subheader("Rentabilidad Simulada")
                    col_r1, col_r2 = st.columns(2)
                    col_r1.metric(
                        "Retorno promedio (max multiple)",
                        f"{results.get('avg_return', 0):.2f}x",
                        help="Promedio del maximo retorno de tokens con senal.",
                    )
                    col_r2.metric(
                        "Retorno mediana",
                        f"{results.get('median_return', 0):.2f}x",
                        help="Mediana del maximo retorno (mas robusta que el promedio).",
                    )

                # Tabla detallada
                if "details" in results and not results["details"].empty:
                    st.divider()
                    st.subheader("Detalle por Token")

                    df_detail = results["details"].copy()
                    display_cols = [
                        "symbol", "chain", "probability", "signal",
                        "signaled", "label_real", "is_gem_real",
                        "max_multiple",
                    ]
                    available = [c for c in display_cols if c in df_detail.columns]
                    df_detail = df_detail[available]
                    if "probability" in df_detail.columns:
                        df_detail = df_detail.sort_values(
                            "probability", ascending=False
                        )

                    # Formatear
                    if "probability" in df_detail.columns:
                        df_detail["probability"] = df_detail["probability"].apply(
                            lambda x: f"{x:.1%}"
                        )
                    if "max_multiple" in df_detail.columns:
                        df_detail["max_multiple"] = df_detail["max_multiple"].apply(
                            lambda x: f"{x:.2f}x" if pd.notna(x) else "N/A"
                        )

                    st.dataframe(df_detail, use_container_width=True, hide_index=True)

            except ImportError:
                st.error(
                    "El modulo de backtesting no esta disponible. "
                    "Verifica que src/models/backtester.py existe."
                )
            except FileNotFoundError as e:
                st.error(f"Modelo no encontrado: {e}")
                st.info("Ejecuta retrain.sh para entrenar los modelos primero.")
            except Exception as e:
                st.error(f"Error en backtesting: {e}")


def render_ohlcv_section(df_signals: pd.DataFrame):
    """Renderiza la seccion de graficos OHLCV candlestick."""
    st.divider()
    st.subheader("📊 Análisis OHLCV - Candlestick Chart")
    st.caption(
        "Visualiza el comportamiento del precio de cualquier token con gráficos "
        "de velas japonesas (candlestick). Útil para identificar patrones y tendencias."
    )

    if df_signals.empty or "token_id" not in df_signals.columns:
        st.info("No hay tokens disponibles para graficar.")
        return

    # Selector de token
    token_options = []
    for _, row in df_signals.iterrows():
        token_id = row.get("token_id", "Unknown")
        symbol = row.get("symbol", "")
        chain = row.get("chain", "")
        prob = row.get("probability", 0)

        # Crear label descriptivo
        label = f"{symbol} ({chain}) - {prob:.1%} prob"
        if len(token_id) > 14:
            label += f" - {token_id[:8]}...{token_id[-6:]}"

        token_options.append((label, token_id))

    if not token_options:
        st.info("No hay tokens con datos completos para graficar.")
        return

    # Selectbox con labels descriptivos
    selected_label = st.selectbox(
        "Selecciona un token para ver su gráfico OHLCV",
        options=[label for label, _ in token_options],
        help="Elige un token de la lista de señales para visualizar su price action."
    )

    # Obtener token_id seleccionado
    selected_token_id = next(
        (tid for label, tid in token_options if label == selected_label),
        None
    )

    if not selected_token_id:
        return

    # Selector de timeframe
    col_tf1, col_tf2 = st.columns([3, 1])
    with col_tf1:
        timeframe = st.selectbox(
            "Timeframe",
            ["hour", "day"],
            format_func=lambda x: "Horario (1h)" if x == "hour" else "Diario (1d)",
            help="Granularidad de las velas: horarias o diarias."
        )

    with col_tf2:
        limit = st.number_input(
            "Velas",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            help="Número máximo de velas a mostrar."
        )

    # Cargar datos OHLCV
    storage = get_storage()
    ohlcv_df = storage.get_ohlcv(selected_token_id, timeframe=timeframe)

    if ohlcv_df.empty:
        st.warning(f"No hay datos OHLCV disponibles para este token en timeframe '{timeframe}'.")
        return

    # Verificar columnas requeridas para candlestick
    required_ohlcv_cols = {"timestamp", "open", "high", "low", "close", "volume"}
    missing_cols = required_ohlcv_cols - set(ohlcv_df.columns)
    if missing_cols:
        st.warning(f"Faltan columnas OHLCV: {', '.join(missing_cols)}")
        return

    # Limitar numero de velas
    if len(ohlcv_df) > limit:
        ohlcv_df = ohlcv_df.tail(limit)

    # Crear grafico candlestick
    fig = go.Figure(data=[go.Candlestick(
        x=ohlcv_df['timestamp'],
        open=ohlcv_df['open'],
        high=ohlcv_df['high'],
        low=ohlcv_df['low'],
        close=ohlcv_df['close'],
        name='OHLCV',
        increasing_line_color='#2ecc71',  # Verde
        decreasing_line_color='#e74c3c',  # Rojo
    )])

    # Añadir volumen como barras en subplot
    fig.add_trace(go.Bar(
        x=ohlcv_df['timestamp'],
        y=ohlcv_df['volume'],
        name='Volume',
        marker_color='rgba(100, 100, 255, 0.3)',
        yaxis='y2',
    ))

    # Layout
    fig.update_layout(
        title=f"Candlestick Chart - {selected_label}",
        xaxis_title="Fecha",
        yaxis_title="Precio (USD)",
        yaxis2=dict(
            title="Volumen",
            overlaying='y',
            side='right',
            showgrid=False,
        ),
        xaxis_rangeslider_visible=False,
        height=500,
        hovermode='x unified',
        template='plotly_white',
    )

    st.plotly_chart(fig, use_container_width=True)

    # Metricas adicionales
    if not ohlcv_df.empty:
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)

        latest = ohlcv_df.iloc[-1]
        first = ohlcv_df.iloc[0]

        price_change = ((latest['close'] - first['open']) / first['open']) * 100 if first['open'] > 0 else 0
        avg_volume = ohlcv_df['volume'].mean()
        max_high = ohlcv_df['high'].max()
        min_low = ohlcv_df['low'].min()

        col_m1.metric("Precio Actual", f"${latest['close']:.8f}")
        col_m2.metric("Cambio %", f"{price_change:+.2f}%", delta=f"{price_change:+.2f}%")
        col_m3.metric("Vol. Promedio", f"${avg_volume:,.0f}")
        col_m4.metric("Rango (Max/Min)", f"${max_high:.8f} / ${min_low:.8f}")


def render_token_comparator():
    """Renderiza el comparador lado a lado de 2 tokens."""
    st.divider()
    st.subheader("🔀 Comparador de Tokens")
    st.caption(
        "Compara 2 tokens lado a lado para ver cuál tiene mejores métricas. "
        "Útil para tomar decisiones entre múltiples señales."
    )

    storage = get_storage()

    # Obtener lista de tokens con features
    features_df = storage.get_features_df()

    if features_df.empty:
        st.info("No hay features calculados. Ejecuta `python -m src.features.builder` primero.")
        return

    # Obtener info basica de tokens
    tokens_df = storage.get_all_tokens()
    if tokens_df.empty:
        st.info("No hay tokens disponibles para comparar.")
        return

    # Merge para obtener symbols
    # Determinar la columna de token_id en features (puede ser index o columna)
    if 'token_id' in features_df.columns:
        feature_token_ids = features_df['token_id'].values
    else:
        feature_token_ids = features_df.index.values
    tokens_with_features = tokens_df[tokens_df['token_id'].isin(feature_token_ids)]

    if len(tokens_with_features) < 2:
        st.info("Se necesitan al menos 2 tokens con features para comparar.")
        return

    # Crear opciones para selectbox
    token_options = []
    for _, row in tokens_with_features.iterrows():
        token_id = row['token_id']
        symbol = row.get('symbol', 'Unknown')
        chain = row.get('chain', 'Unknown')
        label = f"{symbol} ({chain}) - {token_id[:8]}...{token_id[-6:]}"
        token_options.append((label, token_id))

    # Selectores para 2 tokens
    col_t1, col_t2 = st.columns(2)

    with col_t1:
        st.markdown("**Token A**")
        token_a_label = st.selectbox(
            "Selecciona Token A",
            options=[label for label, _ in token_options],
            key="token_a",
        )
        token_a_id = next((tid for label, tid in token_options if label == token_a_label), None)

    with col_t2:
        st.markdown("**Token B**")
        token_b_label = st.selectbox(
            "Selecciona Token B",
            options=[label for label, _ in token_options],
            key="token_b",
        )
        token_b_id = next((tid for label, tid in token_options if label == token_b_label), None)

    if not token_a_id or not token_b_id:
        return

    if token_a_id == token_b_id:
        st.warning("Selecciona 2 tokens diferentes para comparar.")
        return

    # Obtener features de ambos tokens (manejar token_id como columna o index)
    if 'token_id' in features_df.columns:
        row_a = features_df[features_df['token_id'] == token_a_id]
        row_b = features_df[features_df['token_id'] == token_b_id]
        features_a = row_a.iloc[0].to_dict() if not row_a.empty else {}
        features_b = row_b.iloc[0].to_dict() if not row_b.empty else {}
    else:
        features_a = features_df.loc[token_a_id].to_dict() if token_a_id in features_df.index else {}
        features_b = features_df.loc[token_b_id].to_dict() if token_b_id in features_df.index else {}

    if not features_a or not features_b:
        st.error("No se pudieron obtener features para uno o ambos tokens.")
        return

    # Features clave para comparar (solo features que realmente existen en la DB)
    key_features = [
        "initial_liquidity_usd",
        "liquidity_growth_7d",
        "return_24h",
        "return_48h",
        "volatility_7d",
        "volume_to_liq_ratio_24h",
        "volume_trend_slope",
        "green_candle_ratio_24h",
        "tx_count_24h",
        "contract_age_hours",
        "days_since_deployment",
    ]

    # Mostrar comparacion en tabla
    comparison_data = []
    for feature in key_features:
        val_a = features_a.get(feature, np.nan)
        val_b = features_b.get(feature, np.nan)

        # Determinar cual es mejor (simple heuristica)
        if pd.isna(val_a) or pd.isna(val_b):
            better = "N/A"
        elif feature in ["top1_holder_pct", "top5_holder_pct", "volatility"]:
            # Menor es mejor
            better = "A" if val_a < val_b else "B"
        else:
            # Mayor es mejor
            better = "A" if val_a > val_b else "B"

        comparison_data.append({
            "Feature": feature,
            "Token A": f"{val_a:.4f}" if isinstance(val_a, (int, float)) and not pd.isna(val_a) else str(val_a),
            "Token B": f"{val_b:.4f}" if isinstance(val_b, (int, float)) and not pd.isna(val_b) else str(val_b),
            "Mejor": better,
        })

    comparison_df = pd.DataFrame(comparison_data)
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)

    # Resumen de victoria
    wins_a = (comparison_df["Mejor"] == "A").sum()
    wins_b = (comparison_df["Mejor"] == "B").sum()

    st.divider()
    col_w1, col_w2, col_w3 = st.columns(3)
    col_w1.metric("Token A gana en", f"{wins_a} features")
    col_w2.metric("Token B gana en", f"{wins_b} features")
    col_w3.metric("Ganador", "Token A" if wins_a > wins_b else "Token B" if wins_b > wins_a else "Empate")

    st.caption(
        "**Nota:** Esta comparación usa heurísticas simples. "
        "Para decisiones reales, considera el análisis completo del modelo ML."
    )
