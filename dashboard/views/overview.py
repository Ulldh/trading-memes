"""
overview.py - Pagina de resumen general del dataset.

Muestra estadisticas clave del proyecto:
- Conteo de tokens, snapshots, OHLCV y labels
- Distribucion de tokens por cadena (pie chart)
- Distribucion de labels (pie chart)
- Tokens descubiertos por semana (bar chart)
- Frescura de los datos (ultima actualizacion)
"""
import streamlit as st
import pandas as pd
import plotly.express as px

from src.data.supabase_storage import get_storage as _get_storage
from dashboard.constants import LABEL_COLORS, CHAIN_COLORS


@st.cache_resource
def get_storage():
    """Crea una instancia de Storage cacheada para no reconectar cada vez."""
    return _get_storage()


def render():
    """Renderiza la pagina de Overview."""
    st.title("Overview del Dataset")

    st.info(
        "**Que es esto?** Esta pagina muestra un resumen de todos los datos que hemos "
        "recopilado sobre memecoins. Piensa en ello como el \"inventario\" de nuestro "
        "proyecto: cuantos tokens tenemos, de que blockchains vienen, y como estan "
        "clasificados."
    )

    storage = get_storage()

    # ------------------------------------------------------------------
    # 1. Metricas principales (KPIs)
    # ------------------------------------------------------------------
    st.subheader("Metricas principales")

    st.caption(
        "Cada numero representa cuantos registros tenemos en la base de datos. "
        "Mas datos = modelos mas confiables."
    )

    try:
        stats = storage.stats()
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return

    # Mostrar conteos en columnas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Tokens",
        f"{stats.get('tokens', 0):,}",
        help="Numero total de memecoins que estamos rastreando.",
    )
    col2.metric(
        "Snapshots",
        f"{stats.get('pool_snapshots', 0):,}",
        help="Fotos del estado de cada token (precio, volumen, liquidez) tomadas en un momento dado.",
    )
    col3.metric(
        "Registros OHLCV",
        f"{stats.get('ohlcv', 0):,}",
        help="Velas de precio (Open-High-Low-Close-Volume). Cada vela es un dia de datos de precio.",
    )
    col4.metric(
        "Labels asignados",
        f"{stats.get('labels', 0):,}",
        help="Tokens que ya clasificamos como 'gem', 'failure', etc. Esto es lo que el modelo aprende.",
    )

    # Fila adicional
    col5, col6, col7, col8 = st.columns(4)
    col5.metric(
        "Holders snapshots",
        f"{stats.get('holder_snapshots', 0):,}",
        help="Datos de quienes poseen cada token (los 'holders'). Requiere API key de Helius.",
    )
    col6.metric(
        "Contratos analizados",
        f"{stats.get('contract_info', 0):,}",
        help="Tokens cuyo contrato inteligente verificamos (si es seguro, si puede crear mas tokens, etc.).",
    )
    col7.metric(
        "Features calculados",
        f"{stats.get('features', 0):,}",
        help="Tokens para los que ya calculamos las 'features' (caracteristicas numericas que el modelo usa para predecir).",
    )
    col8.metric(
        "Tablas en la DB",
        len(stats),
        help="Numero de tablas en la base de datos SQLite.",
    )

    st.divider()

    # ------------------------------------------------------------------
    # 2. Distribucion de tokens por cadena (pie chart)
    # ------------------------------------------------------------------
    st.subheader("Distribucion de tokens por cadena")

    st.caption(
        "Cada memecoin vive en una blockchain (Solana, Ethereum o Base). "
        "Este grafico muestra cuantos tokens tenemos de cada una. "
        "Solana es la mas popular para memecoins por sus transacciones rapidas y baratas."
    )

    try:
        df_tokens = storage.query("SELECT chain, COUNT(*) as count FROM tokens GROUP BY chain")
    except Exception:
        df_tokens = pd.DataFrame()

    if df_tokens.empty:
        st.info("No hay tokens en la base de datos todavia.")
    else:
        fig_chain = px.pie(
            df_tokens,
            names="chain",
            values="count",
            title="Tokens por blockchain",
            color="chain",
            color_discrete_map=CHAIN_COLORS,
            hole=0.4,
        )
        fig_chain.update_traces(textposition="inside", textinfo="percent+label+value")
        st.plotly_chart(fig_chain, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------------
    # 3. Distribucion de labels (pie chart)
    # ------------------------------------------------------------------
    st.subheader("Clasificaciones asignadas")

    st.caption(
        "Cada token del 'seed dataset' (nuestros ejemplos conocidos) esta clasificado "
        "segun su rendimiento historico:\n"
        "- **Gem**: Alcanzo 10x o mas y se mantuvo (las joyas que buscamos).\n"
        "- **Moderate success**: Subio entre 3x-10x pero no tanto como un gem.\n"
        "- **Failure**: Perdio 90%+ de su valor (la mayoria de memecoins acaban asi)."
    )

    try:
        df_labels = storage.query(
            "SELECT label_multi, COUNT(*) as count FROM labels GROUP BY label_multi"
        )
    except Exception:
        df_labels = pd.DataFrame()

    if df_labels.empty:
        st.info("No hay labels asignados todavia.")
    else:
        fig_labels = px.pie(
            df_labels,
            names="label_multi",
            values="count",
            title="Clasificacion de tokens conocidos",
            color="label_multi",
            color_discrete_map=LABEL_COLORS,
            hole=0.4,
        )
        fig_labels.update_traces(textposition="inside", textinfo="percent+label+value")
        st.plotly_chart(fig_labels, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------------
    # 4. Tokens descubiertos por semana (bar chart)
    # ------------------------------------------------------------------
    st.subheader("Tokens descubiertos por semana")

    st.caption(
        "Muestra cuando anadimos cada token a nuestra base de datos. "
        "A medida que recopilemos datos diariamente, este grafico crecera."
    )

    try:
        df_first_seen = storage.query("SELECT first_seen FROM tokens WHERE first_seen IS NOT NULL")
    except Exception:
        df_first_seen = pd.DataFrame()

    if df_first_seen.empty:
        st.info("No hay datos de fecha de descubrimiento.")
    else:
        df_first_seen["first_seen"] = pd.to_datetime(df_first_seen["first_seen"], errors="coerce")
        df_first_seen = df_first_seen.dropna(subset=["first_seen"])

        if not df_first_seen.empty:
            df_first_seen["week"] = df_first_seen["first_seen"].dt.to_period("W").apply(
                lambda r: r.start_time
            )
            df_weekly = df_first_seen.groupby("week").size().reset_index(name="tokens_nuevos")
            df_weekly = df_weekly.sort_values("week")

            fig_weekly = px.bar(
                df_weekly,
                x="week",
                y="tokens_nuevos",
                title="Nuevos tokens descubiertos por semana",
                labels={"week": "Semana", "tokens_nuevos": "Tokens nuevos"},
                color_discrete_sequence=["#9b59b6"],
            )
            fig_weekly.update_layout(xaxis_title="Semana", yaxis_title="Cantidad de tokens")
            st.plotly_chart(fig_weekly, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------------
    # 5. Frescura de los datos
    # ------------------------------------------------------------------
    st.subheader("Frescura de los datos")

    st.caption(
        "Indica cuando fue la ultima vez que recopilamos datos. "
        "Si la fecha es muy antigua, conviene ejecutar la recopilacion de nuevo."
    )

    col_fresh1, col_fresh2 = st.columns(2)

    try:
        df_last_snap = storage.query("SELECT MAX(snapshot_time) as last_time FROM pool_snapshots")
        last_snap = df_last_snap["last_time"].iloc[0] if not df_last_snap.empty else None
    except Exception:
        last_snap = None

    with col_fresh1:
        if last_snap:
            st.metric("Ultimo pool snapshot", str(last_snap)[:19])
        else:
            st.info("No hay snapshots todavia.")

    try:
        df_last_ohlcv = storage.query("SELECT MAX(timestamp) as last_time FROM ohlcv")
        last_ohlcv = df_last_ohlcv["last_time"].iloc[0] if not df_last_ohlcv.empty else None
    except Exception:
        last_ohlcv = None

    with col_fresh2:
        if last_ohlcv:
            st.metric("Ultimo registro OHLCV", str(last_ohlcv)[:19])
        else:
            st.info("No hay datos OHLCV todavia.")
