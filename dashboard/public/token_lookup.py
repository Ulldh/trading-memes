"""
token_lookup.py - Pagina de busqueda de tokens individuales.

Permite:
- Buscar un token por contract address y cadena
- Ver datos almacenados (nombre, simbolo, dex, etc.)
- Ver snapshot mas reciente (precio, volumen, liquidez)
- Ver grafico OHLCV de precio histórico
- Ver features calculados
- Obtener prediccion del modelo con explicacion
- Añadir nuevos tokens desde el dashboard
"""
# Las funciones premium requieren suscripcion Pro
# (por ahora acceso libre, se activara con Stripe)

import json
import sys
import time
from html import escape
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from src.data.supabase_storage import get_storage as _get_storage
from src.utils.helpers import detect_chain
from config import MODELS_DIR, SUPPORTED_CHAINS
from dashboard.constants import LABEL_COLORS


@st.cache_resource
def get_storage():
    return _get_storage()


@st.cache_resource
def load_model():
    """Carga el modelo entrenado desde data/models/."""
    try:
        import joblib
    except ImportError:
        return None, None

    model_files = [
        ("random_forest.joblib", "Random Forest"),
        ("xgboost.joblib", "XGBoost"),
        ("random_forest_v1.joblib", "Random Forest"),
        ("xgboost_v1.joblib", "XGBoost"),
        ("random_forest_model.joblib", "Random Forest"),
        ("xgboost_model.joblib", "XGBoost"),
        ("best_model.joblib", "Mejor Modelo"),
    ]

    for filename, model_name in model_files:
        path = MODELS_DIR / filename
        if path.exists():
            try:
                model = joblib.load(path)
                return model, model_name
            except Exception:
                continue

    return None, None


@st.cache_data(ttl=300)
def load_feature_columns():
    """Carga la lista de columnas que espera el modelo."""
    meta_path = MODELS_DIR / "feature_columns.json"
    if meta_path.exists():
        try:
            with open(meta_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def prepare_features_for_prediction(feature_row, chain, feature_cols):
    """
    Prepara un row de features crudos para que sea compatible con el modelo.

    El modelo espera columnas one-hot para chain (chain_solana, chain_ethereum,
    chain_base) pero la tabla features tiene 'chain' como texto.
    """
    # Crear un dict con todos los valores
    data = {}
    for col in feature_cols:
        if col.startswith("chain_"):
            # Columnas one-hot de cadena
            expected_chain = col.replace("chain_", "")
            data[col] = 1 if chain == expected_chain else 0
        elif col in feature_row.index:
            data[col] = feature_row[col]
        else:
            data[col] = 0  # Feature no disponible

    X = pd.DataFrame([data])[feature_cols]
    X = X.fillna(0)

    # Convertir a numerico por si hay algun tipo mixto
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0)

    return X


# Descripciones breves de features para la tabla
def add_new_token(token_address: str, chain: str):
    """
    Añade un nuevo token a la base de datos ejecutando el collector.

    Args:
        token_address: Contract address del token
        chain: Blockchain del token (solana, ethereum, base)
    """
    try:
        # Importar módulos necesarios
        st.toast("🔧 Paso 1: Importando módulos...", icon="🔧")
        from src.data.collector import DataCollector
        from src.features.builder import FeatureBuilder

        # Crear collector
        st.toast("🔧 Paso 2: Inicializando collector...", icon="🔧")
        collector = DataCollector()

        # Recopilar datos del token
        st.toast(f"🔧 Paso 3: Recopilando datos de {token_address[:12]}...", icon="🔍")
        with st.spinner(f"🔍 Buscando {token_address[:12]}... en {chain}"):
            result = collector.collect_single_token(token_address, chain)

        st.toast(f"🔧 Paso 4: Datos recibidos. Verificando...", icon="✅")

        if not result or result.get("error"):
            error_msg = result.get("error", "Error desconocido") if result else "No se pudo recopilar datos"
            st.error(f"❌ {error_msg}")
            st.caption("Verifica que el contract address sea correcto y que el token tenga liquidez.")
            return

        # Calcular features
        st.toast("🔧 Paso 5: Calculando features...", icon="🧮")
        with st.spinner("🧮 Calculando features..."):
            try:
                feat_storage = _get_storage()
                builder = FeatureBuilder(feat_storage)
                features_dict = builder.build_features_for_token(token_address)

                if features_dict:
                    new_row = pd.DataFrame([features_dict])
                    if "token_id" in new_row.columns:
                        new_row = new_row.set_index("token_id")
                    existing_df = feat_storage.get_features_df()
                    if not existing_df.empty:
                        if "token_id" in existing_df.columns:
                            existing_df = existing_df.set_index("token_id")
                        existing_df = existing_df[existing_df.index != token_address]
                        combined = pd.concat([existing_df, new_row])
                    else:
                        combined = new_row
                    feat_storage.save_features_df(combined)
                    has_features = True
                else:
                    has_features = False
                st.toast("🔧 Features calculadas correctamente", icon="✅")
            except Exception as e:
                st.warning(f"⚠️ Features se calcularán en el próximo ciclo: {e}")
                has_features = False

        st.toast("🔧 Paso 6: Preparando resultado final...", icon="🎉")
        success = True

        if success:
            # Mensaje de éxito visual
            st.balloons()
            st.success("### 🎉 ¡Token añadido exitosamente!")

            # Mostrar resumen de lo que se recopiló
            storage = _get_storage()
            try:
                # Verificar datos recopilados
                df_token = storage.query(
                    "SELECT * FROM tokens WHERE token_id = ? AND chain = ?",
                    (token_address, chain)
                )

                if not df_token.empty:
                    token_info = df_token.iloc[0]

                    col_success1, col_success2, col_success3 = st.columns(3)
                    with col_success1:
                        st.metric("Nombre", token_info.get("name", "N/A") or "N/A")
                    with col_success2:
                        st.metric("Símbolo", token_info.get("symbol", "N/A") or "N/A")
                    with col_success3:
                        st.metric("Chain", chain.title())

                    # Verificar si hay OHLCV
                    df_ohlcv = storage.get_ohlcv(token_address)
                    ohlcv_count = len(df_ohlcv) if not df_ohlcv.empty else 0

                    # Verificar si hay features
                    df_features = storage.query(
                        "SELECT * FROM features WHERE token_id = ?",
                        (token_address,)
                    )
                    has_features = not df_features.empty

                    st.info(f"📊 **Datos recopilados:** {ohlcv_count} velas OHLCV, "
                           f"{'✅ Features calculados' if has_features else '⏳ Calculando features...'}")

            except Exception as e:
                st.caption(f"Info: {e}")

            # Botón para ver la predicción
            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
            with col_btn2:
                if st.button("🔮 Ver Predicción del Token", type="primary", use_container_width=True):
                    # Guardar en session state para que se muestre al recargar
                    st.session_state["search_token"] = token_address
                    st.session_state["search_chain"] = chain
                    st.rerun()
        else:
            st.error("❌ Error al recopilar datos del token")
            st.caption("Revisa los logs para más detalles.")

    except Exception as e:
        st.error(f"❌ Error al añadir el token: {str(e)}")
        st.caption("Es posible que el token no exista o no tenga liquidez suficiente.")
        import traceback
        with st.expander("Ver detalles técnicos"):
            st.code(traceback.format_exc())


FEATURE_DESCRIPTIONS = {
    "initial_liquidity_usd": "Liquidez inicial del pool (USD)",
    "liquidity_growth_24h": "Cambio de liquidez en 24h (%)",
    "liquidity_growth_7d": "Cambio de liquidez en 7 dias (%)",
    "liq_to_mcap_ratio": "Liquidez / Market Cap (salud del pool)",
    "volume_to_liq_ratio_24h": "Volumen 24h / Liquidez",
    "return_24h": "Retorno de precio en 24h",
    "return_48h": "Retorno de precio en 48h",
    "return_7d": "Retorno de precio en 7 dias",
    "return_30d": "Retorno de precio en 30 dias",
    "max_return_7d": "Maximo retorno en 7 dias",
    "drawdown_from_peak_7d": "Caida desde el pico en 7 dias",
    "volatility_7d": "Variabilidad del precio en 7 dias",
    "volume_spike_ratio": "Pico de volumen / volumen medio",
    "green_candle_ratio_24h": "% de velas verdes en 24h",
    "volume_trend_slope": "Tendencia del volumen (positivo = crece)",
    "buyers_24h": "Compradores unicos en 24h",
    "sellers_24h": "Vendedores unicos en 24h",
    "buyer_seller_ratio_24h": "Ratio compradores/vendedores",
    "makers_24h": "Market makers activos en 24h",
    "tx_count_24h": "Transacciones totales en 24h",
    "avg_tx_size_usd": "Tamano promedio de transaccion (USD)",
    "is_boosted": "Destacado en DexScreener (pagado)",
    "is_verified": "Contrato verificado",
    "has_mint_authority": "Puede crear mas tokens (riesgo!)",
    "contract_age_hours": "Edad del contrato (horas)",
    "launch_day_of_week": "Dia de lanzamiento (0=Lun, 6=Dom)",
    "launch_hour_utc": "Hora de lanzamiento (UTC)",
}


def render():
    """Renderiza la pagina de Busqueda de Token."""
    st.title("Buscar Token")

    st.info(
        "**¿Qué es esto?** Busca cualquier memecoin por su contract address para ver "
        "todos los datos que tenemos, el grafico de precio, y la prediccion del modelo "
        "de Machine Learning sobre si podria ser un 'gem' o no.\n\n"
        "**Contract address** es el identificador unico de un token en la blockchain. "
        "Lo puedes encontrar en DexScreener, CoinGecko o copiandolo de la URL del token."
    )

    storage = get_storage()

    # ------------------------------------------------------------------
    # Formulario de busqueda
    # ------------------------------------------------------------------
    # Verificar si hay un token en session_state (desde botón "Ver Predicción")
    default_address = st.session_state.get("search_token", "")
    default_chain = st.session_state.get("search_chain", "solana")

    # Limpiar session_state después de usarlo
    if "search_token" in st.session_state:
        del st.session_state["search_token"]
    if "search_chain" in st.session_state:
        del st.session_state["search_chain"]

    col_input1, col_input2 = st.columns([3, 1])

    with col_input1:
        contract_address = st.text_input(
            "Contract Address",
            value=default_address,
            placeholder="Ej: DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            help="La dirección del contrato del token. Puedes copiarla de DexScreener.",
            key="token_address_input",
        )

    # Auto-detectar blockchain por formato de la direccion
    detected = detect_chain(contract_address.strip()) if contract_address.strip() else None

    with col_input2:
        chain_options = list(SUPPORTED_CHAINS.keys())
        if detected and detected in chain_options:
            default_index = chain_options.index(detected)
        elif default_chain in chain_options:
            default_index = chain_options.index(default_chain)
        else:
            default_index = 0
        selected_chain = st.selectbox(
            "Cadena",
            chain_options,
            index=default_index,
            help="Se detecta automáticamente por el formato de la dirección (0x = EVM, base58 = Solana).",
            key="chain_select_input",
        )
    if detected:
        st.caption(f"Blockchain detectada automáticamente: **{detected.title()}**")

    buscar = st.button("Buscar", type="primary", use_container_width=True)

    # Auto-buscar si viene desde el botón "Ver Predicción"
    auto_search = bool(default_address)

    # Persistir estado de busqueda: cuando "Buscar" se pulsa, guardamos
    # en session_state para que reruns posteriores (ej: boton "Añadir")
    # no se bloqueen en la condicion de abajo.
    if buscar and contract_address.strip():
        st.session_state["active_search"] = True

    active_search = st.session_state.get("active_search", False)
    is_processing = st.session_state.get("processing_new_token", False)

    if not (buscar or auto_search or active_search or is_processing) or not contract_address.strip():
        # Sin direccion, limpiar estado de busqueda
        st.session_state.pop("active_search", None)
        # Mostrar tokens de ejemplo
        st.caption("**Tokens de ejemplo para probar:**")
        col_ex1, col_ex2, col_ex3 = st.columns(3)
        col_ex1.code("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263")
        col_ex1.caption("BONK (Solana) - Gem")
        col_ex2.code("0x6982508145454Ce325dDbE47a25d4ec3d2311933")
        col_ex2.caption("PEPE (Ethereum) - Gem")
        col_ex3.code("0x3301Ee63Fb29F863f2333Bd4466acb46CD8323E6")
        col_ex3.caption("AKITA (Ethereum) - Failure")
        return

    contract_address = contract_address.strip()
    st.divider()

    # ------------------------------------------------------------------
    # 1. Buscar token en la base de datos
    # ------------------------------------------------------------------
    try:
        df_token = storage.query(
            "SELECT * FROM tokens WHERE token_id = ? AND chain = ?",
            (contract_address, selected_chain),
        )
    except Exception as e:
        st.error(f"Error al consultar la base de datos: {e}")
        return

    if df_token.empty:
        try:
            df_token_any = storage.query(
                "SELECT * FROM tokens WHERE token_id = ?",
                (contract_address,),
            )
        except Exception:
            df_token_any = pd.DataFrame()

        if not df_token_any.empty:
            actual_chain = df_token_any["chain"].iloc[0]
            st.warning(
                f"Token no encontrado en '{selected_chain}', "
                f"pero existe en: **{actual_chain}**. Mostrando esos datos."
            )
            df_token = df_token_any.head(1)
            selected_chain = actual_chain
        else:
            st.warning(f"Token `{contract_address[:12]}...` no esta en nuestra base de datos.")
            st.info(
                "Este token aun no ha sido recopilado. Puedes añadirlo ahora mismo "
                "haciendo clic en el boton de abajo."
            )

            # Botón para marcar que se quiere añadir el token
            col_add1, col_add2, col_add3 = st.columns([1, 2, 1])
            with col_add2:
                if st.button("🔄 Añadir este token", type="primary", use_container_width=True, key="btn_add_token"):
                    # Guardar en session_state para procesarlo después
                    st.session_state["add_token_address"] = contract_address
                    st.session_state["add_token_chain"] = selected_chain
                    st.session_state["processing_new_token"] = True

            # Procesar el token FUERA del botón si el flag está activo
            if st.session_state.get("processing_new_token"):
                token_to_add = st.session_state.get("add_token_address")
                chain_to_add = st.session_state.get("add_token_chain")

                st.write("---")
                st.write(f"### 🔄 Procesando token: `{token_to_add[:12]}...` en {chain_to_add}")

                try:
                    from src.data.collector import DataCollector
                    from src.features.builder import FeatureBuilder

                    collector = DataCollector()

                    with st.spinner(f"🔍 Recopilando datos del token..."):
                        result = collector.collect_single_token(token_to_add, chain_to_add)

                    if not result or result.get("error"):
                        error_msg = result.get("error", "Error desconocido") if result else "No se pudo recopilar datos"
                        st.error(f"❌ {error_msg}")
                        st.caption("Verifica que el contract address sea correcto y que el token tenga liquidez.")
                        # Limpiar flag
                        st.session_state["processing_new_token"] = False
                    else:
                        with st.spinner("🧮 Calculando features..."):
                            try:
                                feat_storage = _get_storage()
                                builder = FeatureBuilder(feat_storage)
                                features_dict = builder.build_features_for_token(token_to_add)

                                if features_dict:
                                    # Guardar features: merge con existentes
                                    new_row = pd.DataFrame([features_dict])
                                    if "token_id" in new_row.columns:
                                        new_row = new_row.set_index("token_id")
                                    existing_df = feat_storage.get_features_df()
                                    if not existing_df.empty:
                                        if "token_id" in existing_df.columns:
                                            existing_df = existing_df.set_index("token_id")
                                        existing_df = existing_df[existing_df.index != token_to_add]
                                        combined = pd.concat([existing_df, new_row])
                                    else:
                                        combined = new_row
                                    feat_storage.save_features_df(combined)
                                    has_features = True
                                else:
                                    has_features = False
                            except Exception as e:
                                st.warning(f"⚠️ Features se calcularán en el próximo ciclo: {e}")
                                has_features = False

                        # Mostrar éxito
                        st.balloons()
                        st.success("### 🎉 ¡Token añadido exitosamente!")

                        # Mostrar resumen
                        storage = _get_storage()
                        df_token_new = storage.query(
                            "SELECT * FROM tokens WHERE token_id = ? AND chain = ?",
                            (token_to_add, chain_to_add)
                        )

                        if not df_token_new.empty:
                            token_info = df_token_new.iloc[0]

                            col_s1, col_s2, col_s3 = st.columns(3)
                            with col_s1:
                                st.metric("Nombre", token_info.get("name", "N/A") or "N/A")
                            with col_s2:
                                st.metric("Símbolo", token_info.get("symbol", "N/A") or "N/A")
                            with col_s3:
                                st.metric("Chain", chain_to_add.title())

                            df_ohlcv = storage.get_ohlcv(token_to_add)
                            ohlcv_count = len(df_ohlcv) if not df_ohlcv.empty else 0

                            st.info(f"📊 **Datos recopilados:** {ohlcv_count} velas OHLCV")

                        # Botón para ver predicción
                        st.markdown("---")
                        col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
                        with col_b2:
                            if st.button("🔮 Ver Predicción del Token", type="primary", use_container_width=True, key="btn_ver_pred"):
                                st.session_state["search_token"] = token_to_add
                                st.session_state["search_chain"] = chain_to_add
                                st.session_state["processing_new_token"] = False
                                st.session_state.pop("active_search", None)
                                st.rerun()

                        # Limpiar flag después de mostrar todo
                        if st.button("✅ Continuar", key="btn_continue"):
                            st.session_state["processing_new_token"] = False
                            st.session_state.pop("active_search", None)
                            st.rerun()

                except Exception as e:
                    st.error(f"❌ Error al añadir el token: {str(e)}")
                    import traceback
                    with st.expander("Ver detalles técnicos"):
                        st.code(traceback.format_exc())
                    # Limpiar flags
                    st.session_state["processing_new_token"] = False
                    st.session_state.pop("active_search", None)

            return

    # ------------------------------------------------------------------
    # 2. Informacion basica del token
    # ------------------------------------------------------------------
    st.subheader("Informacion del Token")
    st.caption("Datos basicos del token extraidos de DexScreener y GeckoTerminal.")

    token_info = df_token.iloc[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("Nombre", token_info.get("name", "N/A") or "N/A")
    col2.metric("Simbolo", token_info.get("symbol", "N/A") or "N/A")
    col3.metric(
        "Cadena", token_info.get("chain", "N/A") or "N/A",
        help="La blockchain donde vive este token.",
    )

    col4, col5, col6 = st.columns(3)
    col4.metric(
        "DEX", token_info.get("dex", "N/A") or "N/A",
        help="Exchange descentralizado donde se tradea (Raydium, Uniswap, etc.).",
    )
    col5.metric("Creado", str(token_info.get("created_at", "N/A") or "N/A")[:19])
    col6.metric("Descubierto", str(token_info.get("first_seen", "N/A") or "N/A")[:19])

    # Boton de watchlist
    in_watchlist = storage.is_in_watchlist(contract_address)
    col_wl1, col_wl2, col_wl3 = st.columns([1, 2, 1])
    with col_wl2:
        if in_watchlist:
            if st.button("Quitar de Watchlist", key="btn_remove_watchlist", use_container_width=True):
                storage.remove_from_watchlist(contract_address)
                st.rerun()
        else:
            if st.button("Agregar a Watchlist", key="btn_add_watchlist", type="primary", use_container_width=True):
                storage.add_to_watchlist(contract_address, selected_chain)
                st.toast("Token agregado a tu Watchlist")
                st.rerun()

    # Mostrar label si existe
    try:
        df_label = storage.query(
            "SELECT * FROM labels WHERE token_id = ?",
            (contract_address,),
        )
    except Exception:
        df_label = pd.DataFrame()

    if not df_label.empty:
        label_info = df_label.iloc[0]
        label_multi = label_info.get("label_multi", "N/A")
        safe_label_multi = escape(str(label_multi))
        label_color = LABEL_COLORS.get(label_multi, "#95a5a6")

        st.markdown(
            f"**Clasificacion conocida:** "
            f"<span style='color: {label_color}; font-weight: bold; font-size: 1.2em;'>"
            f"{safe_label_multi.upper()}</span>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ------------------------------------------------------------------
    # 3. Ultimo snapshot del pool
    # ------------------------------------------------------------------
    st.subheader("Ultimo Snapshot del Pool")
    st.caption(
        "Datos del ultimo momento en que capturamos información de este token. "
        "Incluye precio, volumen de trading, liquidez y actividad de compradores/vendedores."
    )

    try:
        df_snap = storage.query(
            """SELECT * FROM pool_snapshots
               WHERE token_id = ?
               ORDER BY snapshot_time DESC LIMIT 1""",
            (contract_address,),
        )
    except Exception:
        df_snap = pd.DataFrame()

    if df_snap.empty:
        st.info("No hay snapshots para este token.")
    else:
        snap = df_snap.iloc[0]

        col_s1, col_s2, col_s3, col_s4 = st.columns(4)

        price = snap.get("price_usd", None)
        if price is not None:
            if price < 0.01:
                price_str = f"${price:.8f}"
            elif price < 1:
                price_str = f"${price:.4f}"
            else:
                price_str = f"${price:,.2f}"
        else:
            price_str = "N/A"

        col_s1.metric("Precio USD", price_str, help="Precio actual del token en dolares.")
        volume = snap.get("volume_24h", None)
        col_s2.metric(
            "Volumen 24h",
            f"${volume:,.0f}" if volume else "N/A",
            help="Total de dolares tradeados en las ultimas 24 horas.",
        )
        liquidity = snap.get("liquidity_usd", None)
        col_s3.metric(
            "Liquidez USD",
            f"${liquidity:,.0f}" if liquidity else "N/A",
            help="Dinero depositado en el pool de liquidez. Mas liquidez = mas facil comprar/vender.",
        )
        mcap = snap.get("market_cap", None)
        col_s4.metric(
            "Market Cap",
            f"${mcap:,.0f}" if mcap else "N/A",
            help="Valor total del token (precio x supply circulante).",
        )

        col_s5, col_s6, col_s7, col_s8 = st.columns(4)
        col_s5.metric(
            "Compradores 24h",
            snap.get("buyers_24h", "N/A"),
            help="Wallets unicas que compraron en 24h.",
        )
        col_s6.metric(
            "Vendedores 24h",
            snap.get("sellers_24h", "N/A"),
            help="Wallets unicas que vendieron en 24h.",
        )
        col_s7.metric(
            "Transacciones 24h",
            snap.get("tx_count_24h", "N/A"),
            help="Número total de transacciones (compras + ventas) en 24h.",
        )
        col_s8.metric("Snapshot", str(snap.get("snapshot_time", "N/A"))[:19])

    st.divider()

    # ------------------------------------------------------------------
    # 4. Grafico OHLCV
    # ------------------------------------------------------------------
    st.subheader("Gráfico de Precio")
    st.caption(
        "Gráfico de velas (candlestick) del precio histórico. "
        "Cada vela representa un dia: si cierra verde (arriba), el precio subio; "
        "si cierra roja (abajo), bajo. Las barras de abajo muestran el volumen."
    )

    try:
        df_ohlcv = storage.get_ohlcv(contract_address, timeframe="day")
    except Exception:
        df_ohlcv = pd.DataFrame()

    if df_ohlcv.empty:
        try:
            df_ohlcv = storage.get_ohlcv(contract_address, timeframe="hour")
        except Exception:
            df_ohlcv = pd.DataFrame()

    if df_ohlcv.empty:
        st.info("No hay datos de precio (OHLCV) para este token.")
    else:
        df_ohlcv["timestamp"] = pd.to_datetime(df_ohlcv["timestamp"], errors="coerce")
        df_ohlcv = df_ohlcv.dropna(subset=["timestamp"]).sort_values("timestamp")

        has_ohlc = all(
            col in df_ohlcv.columns and df_ohlcv[col].notna().any()
            for col in ["open", "high", "low", "close"]
        )

        if has_ohlc:
            fig_price = go.Figure(data=[go.Candlestick(
                x=df_ohlcv["timestamp"],
                open=df_ohlcv["open"],
                high=df_ohlcv["high"],
                low=df_ohlcv["low"],
                close=df_ohlcv["close"],
                name="Precio",
            )])
            fig_price.update_layout(
                title="Precio histórico (velas diarias)",
                xaxis_title="Fecha",
                yaxis_title="Precio (USD)",
                xaxis_rangeslider_visible=False,
                height=450,
            )
        else:
            fig_price = px.line(
                df_ohlcv, x="timestamp", y="close",
                title="Precio de cierre en el tiempo",
                labels={"timestamp": "Fecha", "close": "Precio (USD)"},
            )
            fig_price.update_layout(height=450)

        st.plotly_chart(fig_price, use_container_width=True)

        if "volume" in df_ohlcv.columns and df_ohlcv["volume"].notna().any():
            fig_vol = px.bar(
                df_ohlcv, x="timestamp", y="volume",
                title="Volumen de trading diario",
                labels={"timestamp": "Fecha", "volume": "Volumen (USD)"},
                color_discrete_sequence=["#3498db"],
            )
            fig_vol.update_layout(height=200)
            st.plotly_chart(fig_vol, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------------
    # 5. Features calculados
    # ------------------------------------------------------------------
    st.subheader("Features Calculados")
    st.caption(
        "Estas son las características numericas que el modelo usa para hacer "
        "su prediccion. Cada feature captura un aspecto diferente del token "
        "(liquidez, actividad, precio, contrato, etc.)."
    )

    try:
        df_features = storage.query(
            "SELECT * FROM features WHERE token_id = ?",
            (contract_address,),
        )
    except Exception:
        df_features = pd.DataFrame()

    if df_features.empty:
        st.info(
            "No hay features calculados para este token. "
            "Ejecuta el pipeline de feature engineering."
        )
    else:
        feature_row = df_features.iloc[0]
        exclude = {"token_id", "index", "computed_at"}
        feature_dict = {}
        for k, v in feature_row.items():
            if k not in exclude and v is not None and not (isinstance(v, float) and np.isnan(v)):
                feature_dict[k] = v

        if feature_dict:
            rows = []
            for k, v in feature_dict.items():
                desc = FEATURE_DESCRIPTIONS.get(k, "")
                try:
                    val = f"{v:.6f}" if isinstance(v, float) else str(v)
                except (ValueError, TypeError):
                    val = str(v)
                rows.append({"Feature": k, "Valor": val, "Descripcion": desc})

            df_display = pd.DataFrame(rows)
            st.dataframe(df_display, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # 5b. Radar chart comparativo
    # ------------------------------------------------------------------
    if not df_features.empty:
        st.subheader("Radar de Perfil del Token")
        st.caption(
            "Gráfico radar que muestra las dimensiones clave del token, "
            "normalizadas de 0 a 1. Puedes comparar con otro token de la base "
            "de datos para ver diferencias de perfil."
        )

        # Dimensiones clave para el radar (subconjunto legible)
        RADAR_FEATURES = {
            "liquidity_growth_7d": "Liquidez 7d",
            "return_24h": "Retorno 24h",
            "volatility_7d": "Volatilidad 7d",
            "buyer_seller_ratio_24h": "Ratio B/S",
            "volume_to_liq_ratio_24h": "Vol/Liq",
            "tx_count_24h": "Transacciones",
            "green_candle_ratio_24h": "Velas Verdes",
            "contract_age_hours": "Edad Contrato",
        }

        # Filtrar features disponibles (acceso defensivo a feature_row)
        available_radar = {}
        for k, v in RADAR_FEATURES.items():
            if k in feature_row.index:
                val = feature_row[k]
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    available_radar[k] = v

        if len(available_radar) >= 3:
            # Obtener valores del token actual
            current_vals = [float(feature_row[k]) for k in available_radar]
            labels_radar = list(available_radar.values())

            # Normalizar con min-max global (de la tabla features)
            all_features_df = storage.get_features_df()
            norm_current = []
            norm_compare = None

            for k, raw_val in zip(available_radar.keys(), current_vals):
                if k in all_features_df.columns:
                    col_data = pd.to_numeric(all_features_df[k], errors="coerce").dropna()
                    if len(col_data) > 0:
                        vmin, vmax = col_data.min(), col_data.max()
                        if vmax > vmin:
                            norm_current.append((raw_val - vmin) / (vmax - vmin))
                        else:
                            norm_current.append(0.5)
                    else:
                        norm_current.append(0.5)
                else:
                    norm_current.append(0.5)

            # Comparar con otro token (opcional)
            compare_address = st.text_input(
                "Comparar con otro token (contract address, opcional):",
                key="radar_compare",
                placeholder="Pega otra dirección para comparar",
            )

            fig_radar = go.Figure()

            # Token actual
            fig_radar.add_trace(go.Scatterpolar(
                r=norm_current + [norm_current[0]],
                theta=labels_radar + [labels_radar[0]],
                fill="toself",
                name=f"{token_info.get('symbol', 'Token')}",
                opacity=0.6,
            ))

            # Token de comparacion
            if compare_address and compare_address.strip():
                try:
                    df_compare = storage.query(
                        "SELECT * FROM features WHERE token_id = ?",
                        (compare_address.strip(),)
                    )
                    if not df_compare.empty:
                        compare_row = df_compare.iloc[0]
                        norm_compare = []
                        for k in available_radar:
                            raw_val = compare_row.get(k, None)
                            if raw_val is None or (isinstance(raw_val, float) and np.isnan(raw_val)):
                                norm_compare.append(0)
                                continue
                            raw_val = float(raw_val)
                            if k in all_features_df.columns:
                                col_data = pd.to_numeric(all_features_df[k], errors="coerce").dropna()
                                if len(col_data) > 0:
                                    vmin, vmax = col_data.min(), col_data.max()
                                    if vmax > vmin:
                                        norm_compare.append((raw_val - vmin) / (vmax - vmin))
                                    else:
                                        norm_compare.append(0.5)
                                else:
                                    norm_compare.append(0.5)
                            else:
                                norm_compare.append(0.5)

                        # Obtener nombre del token de comparacion
                        df_comp_token = storage.query(
                            "SELECT symbol FROM tokens WHERE token_id = ?",
                            (compare_address.strip(),)
                        )
                        comp_symbol = df_comp_token["symbol"].iloc[0] if not df_comp_token.empty else "Comparado"

                        fig_radar.add_trace(go.Scatterpolar(
                            r=norm_compare + [norm_compare[0]],
                            theta=labels_radar + [labels_radar[0]],
                            fill="toself",
                            name=comp_symbol,
                            opacity=0.6,
                        ))
                    else:
                        st.caption("Token de comparacion no encontrado en la base de datos.")
                except Exception:
                    st.caption("Error al cargar token de comparacion.")

            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                showlegend=True,
                height=400,
                title="Perfil normalizado (0 = minimo global, 1 = maximo global)",
            )
            st.plotly_chart(fig_radar, use_container_width=True)
        else:
            st.info("No hay suficientes features para generar el radar (minimo 3).")

    st.divider()

    # ------------------------------------------------------------------
    # 6. Prediccion del modelo
    # ------------------------------------------------------------------
    st.subheader("Prediccion del Modelo")
    st.caption(
        "El modelo de Machine Learning analiza los features del token y predice "
        "si tiene características similares a los 'gems' conocidos."
    )

    model, model_name = load_model()

    if model is None:
        st.info("No hay modelo entrenado disponible.")
        return

    if df_features.empty:
        st.warning("No se puede hacer prediccion sin features calculados.")
        return

    try:
        feature_row = df_features.iloc[0]

        # Obtener la cadena del token
        token_chain = token_info.get("chain", selected_chain)

        # Usar feature_names_in_ del modelo como fuente de verdad,
        # con fallback a feature_columns.json
        if hasattr(model, "feature_names_in_"):
            feature_cols = list(model.feature_names_in_)
        else:
            feature_cols = load_feature_columns()

        if feature_cols:
            X = prepare_features_for_prediction(feature_row, token_chain, feature_cols)
        else:
            exclude = {"token_id", "index", "computed_at", "chain", "dex", "symbol"}
            numeric_data = {
                k: v for k, v in feature_row.items() if k not in exclude
            }
            X = pd.DataFrame([numeric_data]).select_dtypes(include=[np.number])
            X = X.fillna(0)

        if X.empty:
            st.warning("No se pudieron preparar los features para la prediccion.")
            return

        # Hacer prediccion
        prediction = model.predict(X)[0]

        # Probabilidades
        proba = None
        max_proba = None
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X)[0]
            max_proba = max(proba)

        st.markdown(f"**Modelo utilizado:** {model_name}")

        # Interpretar resultado
        if isinstance(prediction, (int, np.integer)):
            if prediction == 1:
                pred_label = "POTENCIAL GEM"
                pred_color = "#2ecc71"
                pred_emoji = "**+**"
            else:
                pred_label = "NO ES GEM"
                pred_color = "#e74c3c"
                pred_emoji = "**-**"
        else:
            pred_label = str(prediction)
            pred_color = LABEL_COLORS.get(pred_label, "#95a5a6")
            pred_emoji = ""

        safe_prediction = escape(str(pred_label))

        st.markdown(
            f"### Prediccion: "
            f"<span style='color: {pred_color}; font-weight: bold;'>"
            f"{safe_prediction}</span>",
            unsafe_allow_html=True,
        )

        if proba is not None and len(proba) >= 2:
            col_p1, col_p2 = st.columns(2)
            col_p1.metric(
                "Probabilidad de Gem",
                f"{proba[1]:.0%}",
                help="¿Qué tan seguro esta el modelo de que es un gem (0-100%).",
            )
            col_p2.metric(
                "Probabilidad de No-Gem",
                f"{proba[0]:.0%}",
                help="¿Qué tan seguro esta el modelo de que NO es un gem.",
            )

            # Barra visual
            st.progress(float(proba[1]))

        # Advertencia de limitaciones
        # Obtener numero de labels para advertencia dinamica
        try:
            n_labels = len(storage.query("SELECT COUNT(*) as n FROM labels"))
            n_labels = storage.query("SELECT COUNT(*) as n FROM labels").iloc[0]["n"]
        except Exception:
            n_labels = 0
        st.warning(
            f"**Ojo**: Esta prediccion se basa en {n_labels} tokens etiquetados. "
            "Usalo como referencia, no como consejo financiero. "
            "Nunca inviertas mas de lo que puedas perder."
        )

    except Exception as e:
        st.error(f"Error al hacer prediccion: {e}")
        st.info(
            "Esto puede ocurrir si las columnas de features no coinciden con "
            "las que espera el modelo."
        )
