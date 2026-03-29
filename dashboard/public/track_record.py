"""
track_record.py - Historial de aciertos del modelo.

Pagina de "prueba social": demuestra a los suscriptores que el modelo
funciona con datos reales. Compara las predicciones pasadas con los
resultados reales para calcular hit rate, retorno promedio, etc.

Secciones:
  1. KPI cards: total predicciones, aciertos, hit rate, avg return
  2. Tabla mensual de rendimiento
  3. Top 10 gems detectados
  4. Gráfico de hit rate a lo largo del tiempo
  5. Resumen simplificado de la matriz de confusion

Fuente de datos: JOIN entre tablas scores (predicciones historicas)
y labels (resultados reales), ambas en Supabase.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from src.data.supabase_storage import get_storage as _get_storage
from dashboard.constants import LABEL_COLORS, CHAIN_COLORS, SIGNAL_COLORS


# ============================================================
# Helpers
# ============================================================

@st.cache_resource
def get_storage():
    """Instancia de Storage cacheada."""
    return _get_storage()


@st.cache_data(ttl=600)
def load_track_record_data() -> pd.DataFrame:
    """
    Carga datos para el track record: scores históricos cruzados con labels reales.

    Hace JOIN entre scores (predicciones) y labels (resultados reales)
    para poder comparar lo que el modelo predijo vs lo que realmente paso.

    Returns:
        DataFrame con columnas: token_id, probability, signal, prediction,
        scored_at, model_version, name, symbol, chain, pool_address,
        label_multi, label_binary, max_multiple, return_7d.
    """
    storage = get_storage()

    sql = """
        SELECT
            s.token_id,
            s.probability,
            s.signal,
            s.prediction,
            s.scored_at,
            s.model_version,
            t.name,
            t.symbol,
            t.chain,
            t.pool_address,
            l.label_multi,
            l.label_binary,
            l.max_multiple,
            l.return_7d
        FROM scores s
        JOIN tokens t ON s.token_id = t.token_id
        LEFT JOIN labels l ON s.token_id = l.token_id
        ORDER BY s.scored_at DESC
    """

    try:
        data = storage._rpc_query(sql)
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _dexscreener_url(chain: str, pool_address: str) -> str:
    """Construye la URL de DexScreener para un token."""
    chain_slug = {
        "solana": "solana",
        "ethereum": "ethereum",
        "base": "base",
    }.get(chain, chain)
    return f"https://dexscreener.com/{chain_slug}/{pool_address}"


def _chain_badge(chain: str) -> str:
    """Devuelve el nombre legible de la cadena."""
    badges = {
        "solana": "Solana",
        "ethereum": "Ethereum",
        "base": "Base",
    }
    return badges.get(chain, chain.capitalize() if chain else "Desconocida")


# ============================================================
# Render principal
# ============================================================

def render():
    """Historico de aciertos — prueba social del modelo."""

    st.header(":bar_chart: Track Record")
    st.caption(
        "Historial de detecciones del modelo y su rendimiento real. "
        "Comparamos lo que el modelo predijo con lo que realmente paso."
    )

    df = load_track_record_data()

    # --- Estado vacio ---
    if df.empty:
        st.info(
            ":hourglass_flowing_sand: **El modelo esta recopilando datos.**\n\n"
            "Los primeros resultados del track record estaran disponibles "
            "una vez que tengamos predicciones con resultados reales verificados. "
            "Esto suele tomar entre 1 y 2 semanas desde la primera ejecucion del modelo."
        )
        return

    # Separar tokens CON resultado conocido vs sin resultado
    df_with_labels = df[df["label_multi"].notna()].copy()
    df_pending = df[df["label_multi"].isna()].copy()

    # Si no hay tokens con label, mostrar mensaje pero igual las predicciones pendientes
    if df_with_labels.empty:
        st.info(
            ":hourglass_flowing_sand: **Todavia no hay resultados verificados.**\n\n"
            f"El modelo ha generado **{len(df)}** predicciones, pero aun no tenemos "
            "resultados reales para compararlas. Los primeros resultados estaran "
            "disponibles en aproximadamente 2 semanas."
        )

        if not df_pending.empty:
            st.divider()
            st.subheader("Predicciones pendientes de verificacion")
            st.caption(
                f"{len(df_pending)} tokens estan siendo monitoreados. "
                "Los resultados se verificaran automáticamente."
            )
            _render_pending_predictions(df_pending)
        return

    # Calcular campo de acierto: un "acierto" es un token predicho como gem
    # que resulto ser gem o moderate_success (label_binary=1 o max_multiple >= 3)
    df_with_labels["is_hit"] = (
        (df_with_labels["label_binary"] == 1) |
        (df_with_labels["label_multi"].isin(["gem", "moderate_success"]))
    )

    # Tokens que tuvieron senal (STRONG, MEDIUM o WEAK — no NONE)
    df_signaled = df_with_labels[
        df_with_labels["signal"].isin(["STRONG", "MEDIUM", "WEAK"])
    ].copy()

    # ======================================================
    # 1. KPI CARDS
    # ======================================================
    _render_kpis(df_with_labels, df_signaled)

    st.divider()

    # ======================================================
    # 2. TABLA MENSUAL
    # ======================================================
    _render_monthly_performance(df_signaled)

    st.divider()

    # ======================================================
    # 3. TOP GEMS DETECTADOS
    # ======================================================
    _render_top_gems(df_signaled)

    st.divider()

    # ======================================================
    # 4. GRAFICO DE HIT RATE EN EL TIEMPO
    # ======================================================
    _render_hit_rate_over_time(df_signaled)

    st.divider()

    # ======================================================
    # 5. RESUMEN DE CONFUSION SIMPLIFICADO
    # ======================================================
    _render_simplified_confusion(df_with_labels, df_signaled)

    st.divider()

    # Disclaimer
    st.warning(
        ":warning: **Rendimiento pasado no garantiza resultados futuros.** "
        "Estos datos muestran el track record histórico del modelo, que puede variar "
        "segun las condiciones del mercado. DYOR."
    )


# ============================================================
# Secciones individuales
# ============================================================

def _render_kpis(df_all: pd.DataFrame, df_signaled: pd.DataFrame):
    """Tarjetas KPI resumen del track record."""

    total_predictions = len(df_all)
    total_signaled = len(df_signaled)
    hits = df_signaled["is_hit"].sum() if not df_signaled.empty else 0
    hit_rate = (hits / total_signaled * 100) if total_signaled > 0 else 0.0

    # Retorno promedio de los gems detectados correctamente
    df_hits = df_signaled[df_signaled["is_hit"] == True]
    if not df_hits.empty and "max_multiple" in df_hits.columns:
        avg_return = df_hits["max_multiple"].dropna().mean()
    else:
        avg_return = 0.0

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total predicciones",
        f"{total_predictions:,}",
        help="Número total de tokens analizados por el modelo con resultado conocido.",
    )
    col2.metric(
        "Aciertos",
        f"{int(hits)}",
        help=(
            "Tokens que el modelo marco con senal (STRONG/MEDIUM/WEAK) "
            "y efectivamente subieron significativamente."
        ),
    )
    col3.metric(
        "Hit rate",
        f"{hit_rate:.1f}%",
        help="Porcentaje de aciertos sobre el total de señales emitidas.",
    )
    col4.metric(
        "Retorno prom. de aciertos",
        f"{avg_return:.1f}x" if avg_return > 0 else "N/A",
        help="Multiplicador promedio (max_multiple) de los gems detectados correctamente.",
    )


def _render_monthly_performance(df: pd.DataFrame):
    """Tabla de rendimiento mensual."""

    st.subheader("Rendimiento mensual")

    if df.empty or "scored_at" not in df.columns:
        st.info("No hay datos suficientes para el rendimiento mensual.")
        return

    # Parsear fecha
    df = df.copy()
    df["scored_at"] = pd.to_datetime(df["scored_at"], errors="coerce")
    df = df.dropna(subset=["scored_at"])

    if df.empty:
        st.info("No hay datos con fechas validas.")
        return

    df["mes"] = df["scored_at"].dt.to_period("M").astype(str)

    # Agrupar por mes
    monthly = df.groupby("mes").agg(
        predicciones=("token_id", "count"),
        aciertos=("is_hit", "sum"),
        avg_return=("max_multiple", lambda x: x.dropna().mean()),
    ).reset_index()

    monthly["hit_rate"] = (monthly["aciertos"] / monthly["predicciones"] * 100).round(1)
    monthly["avg_return"] = monthly["avg_return"].round(2)

    # Mejor gem de cada mes
    best_gems = []
    for mes in monthly["mes"]:
        month_df = df[df["mes"] == mes]
        if not month_df.empty and "max_multiple" in month_df.columns:
            best_row = month_df.loc[month_df["max_multiple"].idxmax()]
            best_label = f"{best_row.get('symbol', '?')} ({best_row.get('max_multiple', 0):.1f}x)"
        else:
            best_label = "N/A"
        best_gems.append(best_label)

    monthly["mejor_gem"] = best_gems

    # Renombrar para presentacion
    monthly_display = monthly.rename(columns={
        "mes": "Mes",
        "predicciones": "Predicciones",
        "aciertos": "Aciertos",
        "hit_rate": "Hit Rate (%)",
        "avg_return": "Retorno Prom. (x)",
        "mejor_gem": "Mejor Gem",
    })

    # Ordenar por mes descendente
    monthly_display = monthly_display.sort_values("Mes", ascending=False)

    st.dataframe(
        monthly_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Hit Rate (%)": st.column_config.ProgressColumn(
                "Hit Rate (%)",
                format="%.1f%%",
                min_value=0,
                max_value=100,
            ),
            "Retorno Prom. (x)": st.column_config.NumberColumn(
                "Retorno Prom. (x)",
                format="%.2fx",
            ),
        },
    )


def _render_top_gems(df: pd.DataFrame):
    """Top 10 gems detectados correctamente por el modelo."""

    st.subheader("Top 10 gems detectados")
    st.caption(
        "Los mejores tokens que el modelo identifico con senal y que "
        "efectivamente tuvieron un rendimiento sobresaliente."
    )

    if df.empty:
        st.info("No hay gems detectados todavia.")
        return

    # Filtrar solo aciertos con max_multiple
    df_hits = df[
        (df["is_hit"] == True) &
        (df["max_multiple"].notna()) &
        (df["max_multiple"] > 0)
    ].copy()

    if df_hits.empty:
        st.info("No hay gems con resultado verificado todavia.")
        return

    # Top 10 por max_multiple
    df_top = df_hits.nlargest(10, "max_multiple")

    # Preparar tabla de presentacion
    display_data = []
    for _, row in df_top.iterrows():
        name = row.get("name", "")
        symbol = row.get("symbol", "")
        token_label = f"{name} ({symbol})" if name and symbol else (symbol or name or "?")

        scored_at = row.get("scored_at", "")
        if pd.notna(scored_at):
            fecha = str(scored_at)[:10]
        else:
            fecha = "N/A"

        chain = row.get("chain", "")
        pool_addr = row.get("pool_address", "")
        link = _dexscreener_url(chain, pool_addr) if pool_addr and chain else ""

        display_data.append({
            "Token": token_label,
            "Fecha deteccion": fecha,
            "Score": row.get("probability", 0.0),
            "Retorno real": row.get("max_multiple", 0.0),
            "Chain": _chain_badge(chain),
            "DexScreener": link,
        })

    df_display = pd.DataFrame(display_data)

    st.dataframe(
        df_display,
        column_config={
            "Token": st.column_config.TextColumn("Token", width="medium"),
            "Fecha deteccion": st.column_config.TextColumn("Fecha", width="small"),
            "Score": st.column_config.ProgressColumn(
                "Score",
                format="%.0f%%",
                min_value=0.0,
                max_value=1.0,
            ),
            "Retorno real": st.column_config.NumberColumn(
                "Retorno real",
                format="%.1fx",
                help="Multiplicador maximo alcanzado por el token.",
            ),
            "Chain": st.column_config.TextColumn("Chain", width="small"),
            "DexScreener": st.column_config.LinkColumn(
                "DexScreener",
                display_text="Ver",
                width="small",
            ),
        },
        use_container_width=True,
        hide_index=True,
    )


def _render_hit_rate_over_time(df: pd.DataFrame):
    """Gráfico de línea: hit rate a lo largo del tiempo (por mes)."""

    st.subheader("Hit rate a lo largo del tiempo")
    st.caption(
        "Evolucion del porcentaje de aciertos del modelo por periodo. "
        "Una tendencia estable o ascendente indica que el modelo mantiene su calidad."
    )

    if df.empty or "scored_at" not in df.columns:
        st.info("No hay datos suficientes para el grafico de tendencia.")
        return

    df = df.copy()
    df["scored_at"] = pd.to_datetime(df["scored_at"], errors="coerce")
    df = df.dropna(subset=["scored_at"])

    if df.empty or len(df) < 3:
        st.info("Se necesitan al menos 3 predicciones con resultado para mostrar la tendencia.")
        return

    # Determinar granularidad: semanal si hay >= 4 semanas de datos, sino mensual
    date_range = (df["scored_at"].max() - df["scored_at"].min()).days
    if date_range >= 28:
        df["periodo"] = df["scored_at"].dt.to_period("W").apply(lambda r: r.start_time)
        periodo_label = "Semana"
    else:
        df["periodo"] = df["scored_at"].dt.to_period("M").apply(lambda r: r.start_time)
        periodo_label = "Mes"

    # Agrupar por periodo
    period_stats = df.groupby("periodo").agg(
        total=("token_id", "count"),
        aciertos=("is_hit", "sum"),
    ).reset_index()

    period_stats["hit_rate"] = (period_stats["aciertos"] / period_stats["total"] * 100).round(1)
    period_stats = period_stats.sort_values("periodo")

    fig = px.line(
        period_stats,
        x="periodo",
        y="hit_rate",
        markers=True,
        labels={"periodo": periodo_label, "hit_rate": "Hit Rate (%)"},
    )

    fig.update_traces(
        line_color=SIGNAL_COLORS.get("STRONG", "#2ecc71"),
        marker_size=8,
        line_width=3,
    )

    # Linea de referencia al 50%
    fig.add_hline(
        y=50,
        line_dash="dot",
        line_color="#95a5a6",
        annotation_text="50% (aleatorio)",
        annotation_position="bottom left",
    )

    fig.update_layout(
        height=400,
        margin=dict(t=20, b=40, l=40, r=20),
        yaxis_range=[0, 105],
        yaxis_title="Hit Rate (%)",
        xaxis_title=periodo_label,
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_simplified_confusion(df_all: pd.DataFrame, df_signaled: pd.DataFrame):
    """Resumen simplificado tipo 'prueba social' de la matriz de confusion."""

    st.subheader("Resumen de precision")
    st.caption(
        "Desglose sencillo de como se desempenan las señales del modelo."
    )

    if df_signaled.empty:
        st.info("No hay suficientes datos para calcular la precision.")
        return

    total_signaled = len(df_signaled)
    true_positives = df_signaled["is_hit"].sum()
    false_positives = total_signaled - true_positives

    # Gems reales que NO fueron detectados (false negatives)
    # Son tokens en df_all con label gem/moderate_success pero sin senal
    df_no_signal = df_all[~df_all["signal"].isin(["STRONG", "MEDIUM", "WEAK"])]
    false_negatives = (
        df_no_signal["label_multi"].isin(["gem", "moderate_success"]).sum()
        if not df_no_signal.empty else 0
    )

    # Precision y recall
    precision = (true_positives / total_signaled * 100) if total_signaled > 0 else 0
    recall = (
        true_positives / (true_positives + false_negatives) * 100
        if (true_positives + false_negatives) > 0 else 0
    )

    # Mostrar con lenguaje accesible
    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Precision",
            f"{precision:.1f}%",
            help="De las señales que dio el modelo, que porcentaje fueron aciertos reales.",
        )
        st.caption(
            f"De **{total_signaled}** tokens marcados con senal, "
            f"**{int(true_positives)}** efectivamente subieron."
        )

    with col2:
        st.metric(
            "Recall (cobertura)",
            f"{recall:.1f}%",
            help="De todos los gems reales, que porcentaje detecto el modelo.",
        )
        gems_total = int(true_positives + false_negatives)
        st.caption(
            f"De **{gems_total}** gems reales en el periodo, "
            f"el modelo detecto **{int(true_positives)}**."
        )

    # Detalle visual con barras apiladas
    confusion_data = pd.DataFrame({
        "Categoria": [
            "Aciertos (gems detectados)",
            "Falsos positivos (senal sin resultado)",
            "Gems no detectados",
        ],
        "Cantidad": [int(true_positives), int(false_positives), int(false_negatives)],
        "Color": ["#2ecc71", "#e74c3c", "#f39c12"],
    })

    fig = px.bar(
        confusion_data,
        y="Categoria",
        x="Cantidad",
        orientation="h",
        color="Categoria",
        color_discrete_map={
            "Aciertos (gems detectados)": "#2ecc71",
            "Falsos positivos (senal sin resultado)": "#e74c3c",
            "Gems no detectados": "#f39c12",
        },
        text="Cantidad",
    )

    fig.update_traces(textposition="outside", textfont_size=13)
    fig.update_layout(
        showlegend=False,
        height=250,
        margin=dict(t=10, b=20, l=20, r=40),
        xaxis_title="Número de tokens",
        yaxis_title="",
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_pending_predictions(df_pending: pd.DataFrame):
    """Muestra predicciones que aun no tienen resultado verificado."""

    if df_pending.empty:
        return

    # Ordenar por probabilidad descendente, mostrar top 20
    df_pending = df_pending.sort_values("probability", ascending=False).head(20)

    display_data = []
    for _, row in df_pending.iterrows():
        name = row.get("name", "")
        symbol = row.get("symbol", "")
        token_label = f"{name} ({symbol})" if name and symbol else (symbol or name or "?")

        scored_at = row.get("scored_at", "")
        fecha = str(scored_at)[:10] if pd.notna(scored_at) else "N/A"

        display_data.append({
            "Token": token_label,
            "Fecha": fecha,
            "Score": row.get("probability", 0.0),
            "Senal": row.get("signal", "NONE"),
            "Chain": _chain_badge(row.get("chain", "")),
        })

    df_display = pd.DataFrame(display_data)

    st.dataframe(
        df_display,
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score",
                format="%.0f%%",
                min_value=0.0,
                max_value=1.0,
            ),
        },
        use_container_width=True,
        hide_index=True,
    )
