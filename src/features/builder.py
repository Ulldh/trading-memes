"""
builder.py - Orquestador principal de feature engineering.

FeatureBuilder es la clase que coordina todos los modulos de features.
Para cada token en la base de datos:
    1. Obtiene los datos necesarios de Storage (holders, OHLCV, etc.)
    2. Llama a cada modulo de features (tokenomics, liquidity, etc.)
    3. Combina todos los features en un solo diccionario (una fila)
    4. Al final, devuelve un DataFrame con todos los tokens y sus features

Esto es lo que se usa para alimentar los modelos de Machine Learning.

Uso:
    from src.data.storage import Storage
    from src.features.builder import FeatureBuilder

    storage = Storage()
    builder = FeatureBuilder(storage)

    # Features para un solo token
    features = builder.build_features_for_token("abc123...")

    # Features para todos los tokens
    features_df = builder.build_all_features()
"""

import pandas as pd
from typing import Optional

from src.data.storage import Storage
from src.utils.logger import get_logger

# Importar todos los modulos de features
from src.features.tokenomics import compute_tokenomics_features, compute_whale_movement_features
from src.features.liquidity import compute_liquidity_features
from src.features.price_action import compute_price_action_features
from src.features.social import compute_social_features, compute_temporal_social_features
from src.features.contract import compute_contract_features, compute_contract_risk_features
from src.features.market_context import compute_market_context_features
from src.features.temporal import extract_temporal_features
from src.features.volatility_advanced import compute_volatility_advanced_features
from src.features.sentiment import compute_sentiment_features

logger = get_logger(__name__)


class FeatureBuilder:
    """
    Orquestador de feature engineering.

    Coordina la extraccion de features de todos los modulos y
    los combina en un DataFrame listo para ML.

    Args:
        storage: Instancia de Storage para acceder a la base de datos.

    Atributos:
        storage: Referencia a la instancia de Storage.

    Ejemplo:
        >>> storage = Storage()
        >>> builder = FeatureBuilder(storage)
        >>> df = builder.build_all_features()
        >>> print(df.shape)
        (100, 35)  # 100 tokens, 35 features
    """

    def __init__(self, storage: Storage):
        """
        Inicializa el FeatureBuilder con una conexion a Storage.

        Args:
            storage: Instancia de Storage con la base de datos del proyecto.
        """
        self.storage = storage

    def build_features_for_token(self, token_id: str) -> dict:
        """
        Calcula todos los features para un token especifico.

        Flujo:
            1. Obtener informacion basica del token (chain, dex, created_at, etc.)
            2. Obtener datos de holders -> calcular features de tokenomics
            3. Obtener pool snapshots -> calcular features de liquidez
            4. Obtener OHLCV -> calcular features de price action
            5. Obtener ultimo snapshot -> calcular features sociales
            6. Obtener contract_info -> calcular features de contrato
            7. Obtener precios de BTC/ETH/SOL -> calcular contexto de mercado
            8. Combinar todo en un solo dict

        Args:
            token_id: ID del token (contract address).

        Returns:
            Dict con TODOS los features del token combinados.
            Incluye 'token_id' como identificador.

        Ejemplo:
            >>> features = builder.build_features_for_token("abc123...")
            >>> features["top1_holder_pct"]
            15.3
        """
        logger.info(f"Calculando features para token: {token_id}")

        # Diccionario donde acumulamos todos los features
        all_features = {"token_id": token_id}

        # Contadores de modulos exitosos/fallidos
        modules_ok = 0
        modules_fail = 0

        # ============================================================
        # 1. OBTENER INFORMACION BASICA DEL TOKEN
        # ============================================================
        token_df = self.storage.query(
            "SELECT * FROM tokens WHERE token_id = ?",
            (token_id,)
        )

        if token_df.empty:
            logger.warning(f"Token no encontrado: {token_id}")
            return all_features

        token_info = token_df.iloc[0].to_dict()
        chain = token_info.get("chain", "")
        dex = token_info.get("dex", "")
        created_at = token_info.get("created_at", "")

        # ============================================================
        # 2. FEATURES DE TOKENOMICS (distribucion de holders)
        # ============================================================
        try:
            # Obtener datos de holders (ultimo snapshot)
            holders_df = self._get_latest_holders(token_id)

            # Obtener informacion del contrato
            contract_info = self._get_contract_info(token_id)

            # Agregar total_supply al contract_info para el calculo
            if contract_info is not None:
                contract_info["total_supply"] = token_info.get("total_supply")

            tokenomics = compute_tokenomics_features(holders_df, contract_info)
            all_features.update(tokenomics)
            modules_ok += 1
        except Exception as e:
            logger.error(f"Error en tokenomics para {token_id}: {e}")
            modules_fail += 1

        # ============================================================
        # 2b. FEATURES DE MOVIMIENTO DE BALLENAS
        # ============================================================
        try:
            all_holders_df = self._get_all_holder_snapshots(token_id)
            whale_features = compute_whale_movement_features(all_holders_df)
            all_features.update(whale_features)
            modules_ok += 1
        except Exception as e:
            logger.error(f"Error en whale_movement para {token_id}: {e}")
            modules_fail += 1

        # ============================================================
        # 3. FEATURES DE LIQUIDEZ
        # ============================================================
        # Inicializar snapshots_df antes del try/except para que esté
        # disponible en el paso 5b (temporal_social) aunque liquidez falle
        snapshots_df = pd.DataFrame()
        try:
            # Obtener todos los pool snapshots ordenados por tiempo
            snapshots_df = self.storage.query(
                """SELECT * FROM pool_snapshots
                   WHERE token_id = ?
                   ORDER BY snapshot_time""",
                (token_id,)
            )

            liquidity = compute_liquidity_features(snapshots_df)
            all_features.update(liquidity)
            modules_ok += 1
        except Exception as e:
            logger.error(f"Error en liquidity para {token_id}: {e}")
            modules_fail += 1

        # ============================================================
        # 4. FEATURES DE PRICE ACTION (OHLCV)
        # ============================================================
        try:
            # Obtener datos OHLCV (velas horarias para mas detalle)
            ohlcv_df = self.storage.get_ohlcv(token_id, timeframe="hour")

            # Si no hay datos horarios, intentar con datos diarios
            if ohlcv_df.empty:
                ohlcv_df = self.storage.get_ohlcv(token_id, timeframe="day")

            price_action = compute_price_action_features(ohlcv_df)
            all_features.update(price_action)
            modules_ok += 1
        except Exception as e:
            logger.error(f"Error en price_action para {token_id}: {e}")
            modules_fail += 1

        # ============================================================
        # 5. FEATURES SOCIALES (buyers, sellers, txs)
        # ============================================================
        try:
            # Usar el snapshot mas reciente para datos sociales
            latest_snapshot = self._get_latest_snapshot(token_id)
            social = compute_social_features(latest_snapshot)
            all_features.update(social)
            modules_ok += 1
        except Exception as e:
            logger.error(f"Error en social para {token_id}: {e}")
            modules_fail += 1

        # ============================================================
        # 5b. FEATURES SOCIALES TEMPORALES (tendencias en snapshots)
        # ============================================================
        try:
            # Reutilizamos snapshots_df del paso 3 (liquidez)
            temporal_social = compute_temporal_social_features(snapshots_df)
            all_features.update(temporal_social)
            modules_ok += 1
        except Exception as e:
            logger.error(f"Error en temporal_social para {token_id}: {e}")
            modules_fail += 1

        # ============================================================
        # 6. FEATURES DE CONTRATO
        # ============================================================
        try:
            contract_info = self._get_contract_info(token_id)
            contract = compute_contract_features(
                contract_info, created_at, created_at
            )
            all_features.update(contract)
            modules_ok += 1
        except Exception as e:
            logger.error(f"Error en contract para {token_id}: {e}")
            modules_fail += 1

        # ============================================================
        # 6b. FEATURES DE RIESGO DEL CONTRATO (solo EVM con source verificado)
        # ============================================================
        try:
            if chain in ("ethereum", "base"):
                contract_source = self._get_contract_source(token_id)
                if contract_source:
                    risk_features = compute_contract_risk_features(contract_source)
                    all_features.update(risk_features)
                    modules_ok += 1
        except Exception as e:
            logger.error(f"Error en contract_risk para {token_id}: {e}")
            modules_fail += 1

        # ============================================================
        # 7. FEATURES DE CONTEXTO DE MERCADO
        # ============================================================
        try:
            # Obtener precios de BTC, ETH, SOL
            btc_prices = self._get_asset_prices("btc")
            eth_prices = self._get_asset_prices("eth")
            sol_prices = self._get_asset_prices("sol")

            market = compute_market_context_features(
                launch_time=created_at,
                btc_prices=btc_prices,
                eth_prices=eth_prices,
                sol_prices=sol_prices,
                chain=chain,
                dex=dex
            )
            all_features.update(market)
            modules_ok += 1
        except Exception as e:
            logger.error(f"Error en market_context para {token_id}: {e}")
            modules_fail += 1

        # ============================================================
        # 8. FEATURES TEMPORALES (timing del lanzamiento)
        # ============================================================
        try:
            temporal = extract_temporal_features(token_info)
            all_features.update(temporal)
            modules_ok += 1
        except Exception as e:
            logger.error(f"Error en temporal para {token_id}: {e}")
            modules_fail += 1

        # ============================================================
        # 9. FEATURES DE VOLATILIDAD AVANZADA
        # ============================================================
        try:
            # Obtener datos OHLCV (reutilizamos los mismos datos que price_action)
            ohlcv_df = self.storage.get_ohlcv(token_id, timeframe="hour")

            # Si no hay datos horarios, intentar con datos diarios
            if ohlcv_df.empty:
                ohlcv_df = self.storage.get_ohlcv(token_id, timeframe="day")

            volatility = compute_volatility_advanced_features(ohlcv_df)
            all_features.update(volatility)
            modules_ok += 1
        except Exception as e:
            logger.error(f"Error en volatility_advanced para {token_id}: {e}")
            modules_fail += 1

        # ============================================================
        # 10. FEATURES DE SENTIMIENTO SOCIAL (X / Twitter)
        # ============================================================
        try:
            mention_data = self._get_twitter_mentions(token_info)
            if mention_data:
                sentiment = compute_sentiment_features(mention_data)
                all_features.update(sentiment)
                modules_ok += 1
        except Exception as e:
            logger.error(f"Error en sentiment para {token_id}: {e}")
            modules_fail += 1

        # Reportar si hubo modulos fallidos
        if modules_fail > 0:
            logger.warning(
                f"Token {token_id}: {modules_fail} modulos fallaron, "
                f"{modules_ok} exitosos"
            )

        logger.info(
            f"Features calculados para {token_id}: {len(all_features)} columnas "
            f"({modules_ok} ok, {modules_fail} fail)"
        )
        return all_features

    def build_all_features(self) -> pd.DataFrame:
        """
        Calcula features para TODOS los tokens en la base de datos.

        Itera sobre cada token, calcula sus features, y los combina
        en un DataFrame donde cada fila es un token y cada columna
        es un feature.

        Returns:
            DataFrame con token_id como indice y todos los features
            como columnas. Si no hay tokens, devuelve DataFrame vacio.

        Ejemplo:
            >>> df = builder.build_all_features()
            >>> print(df.columns.tolist())
            ['top1_holder_pct', 'top5_holder_pct', ...]
        """
        # Obtener la lista de todos los tokens
        tokens_df = self.storage.get_all_tokens()

        if tokens_df.empty:
            logger.warning("No hay tokens en la base de datos.")
            return pd.DataFrame()

        logger.info(f"Calculando features para {len(tokens_df)} tokens...")

        # Lista para acumular los features de cada token
        all_rows = []

        # Iterar sobre cada token
        for idx, token_row in tokens_df.iterrows():
            token_id = token_row["token_id"]

            try:
                # Calcular features para este token
                features = self.build_features_for_token(token_id)
                all_rows.append(features)
            except Exception as e:
                logger.error(
                    f"Error procesando token {token_id}: {e}"
                )
                # Agregar fila con solo el token_id (features seran NaN)
                all_rows.append({"token_id": token_id})

        # Convertir lista de dicts a DataFrame
        features_df = pd.DataFrame(all_rows)

        # Establecer token_id como indice
        if "token_id" in features_df.columns:
            features_df = features_df.set_index("token_id")

        logger.info(
            f"Feature matrix: {features_df.shape[0]} tokens x "
            f"{features_df.shape[1]} features"
        )

        # Loguear features con <50% cobertura (muchos NaN = feature poco util)
        if not features_df.empty:
            total_tokens = len(features_df)
            coverage = features_df.notna().sum() / total_tokens
            low_coverage = coverage[coverage < 0.5]
            if not low_coverage.empty:
                logger.warning(
                    f"Features con <50% cobertura ({len(low_coverage)}):\n"
                    + "\n".join(
                        f"  {col}: {pct:.1%}"
                        for col, pct in low_coverage.sort_values().items()
                    )
                )

        return features_df

    # ============================================================
    # METODOS AUXILIARES (privados)
    # ============================================================
    # Estos metodos obtienen datos especificos de Storage
    # y los preparan para los modulos de features

    def _get_latest_holders(self, token_id: str) -> pd.DataFrame:
        """
        Obtiene el snapshot mas reciente de holders para un token.

        Args:
            token_id: ID del token.

        Returns:
            DataFrame con los holders del ultimo snapshot.
        """
        # Obtener el timestamp del snapshot mas reciente
        latest_time_df = self.storage.query(
            """SELECT MAX(snapshot_time) as max_time
               FROM holder_snapshots
               WHERE token_id = ?""",
            (token_id,)
        )

        if latest_time_df.empty or latest_time_df["max_time"].iloc[0] is None:
            return pd.DataFrame()

        max_time = latest_time_df["max_time"].iloc[0]

        # Obtener todos los holders de ese snapshot
        return self.storage.query(
            """SELECT rank, holder_address, amount, pct_of_supply
               FROM holder_snapshots
               WHERE token_id = ? AND snapshot_time = ?
               ORDER BY rank""",
            (token_id, max_time)
        )

    def _get_contract_info(self, token_id: str) -> Optional[dict]:
        """
        Obtiene la informacion del contrato de un token.

        Args:
            token_id: ID del token.

        Returns:
            Dict con la info del contrato, o None si no existe.
        """
        df = self.storage.query(
            "SELECT * FROM contract_info WHERE token_id = ?",
            (token_id,)
        )

        if df.empty:
            return None

        return df.iloc[0].to_dict()

    def _get_latest_snapshot(self, token_id: str) -> Optional[dict]:
        """
        Obtiene el pool snapshot mas reciente de un token.

        Args:
            token_id: ID del token.

        Returns:
            Dict con los datos del snapshot, o None si no existe.
        """
        df = self.storage.query(
            """SELECT * FROM pool_snapshots
               WHERE token_id = ?
               ORDER BY snapshot_time DESC
               LIMIT 1""",
            (token_id,)
        )

        if df.empty:
            return None

        return df.iloc[0].to_dict()

    def _get_asset_prices(self, asset: str) -> pd.DataFrame:
        """
        Obtiene los precios historicos de un activo (BTC, ETH, SOL).

        Busca en la tabla ohlcv usando un token_id especial para
        los activos de referencia (ej: "__btc__", "__eth__", "__sol__").

        Si los datos no estan disponibles, devuelve un DataFrame vacio.

        Args:
            asset: Identificador del activo ("btc", "eth", "sol").

        Returns:
            DataFrame con columnas [timestamp, price].
        """
        # Los precios de referencia se almacenan con IDs especiales
        asset_token_id = f"__{asset}__"

        df = self.storage.query(
            """SELECT timestamp, close as price
               FROM ohlcv
               WHERE token_id = ? AND timeframe = 'day'
               ORDER BY timestamp""",
            (asset_token_id,)
        )

        return df

    def _get_all_holder_snapshots(self, token_id: str) -> pd.DataFrame:
        """
        Obtiene TODOS los snapshots de holders para un token.

        A diferencia de _get_latest_holders, este metodo devuelve
        todos los snapshots historicos para detectar movimientos de whales.

        Args:
            token_id: ID del token.

        Returns:
            DataFrame con todos los holder snapshots ordenados por tiempo.
        """
        return self.storage.query(
            """SELECT snapshot_time, rank, holder_address, pct_of_supply
               FROM holder_snapshots
               WHERE token_id = ?
               ORDER BY snapshot_time, rank""",
            (token_id,)
        )

    def _get_contract_source(self, token_id: str) -> Optional[dict]:
        """
        Obtiene el source code/ABI del contrato para risk analysis.

        Busca en contract_info si hay source_code almacenado.
        Solo disponible para contratos EVM verificados.

        Args:
            token_id: ID del token.

        Returns:
            Dict con source_code y abi, o None.
        """
        df = self.storage.query(
            "SELECT * FROM contract_info WHERE token_id = ?",
            (token_id,)
        )

        if df.empty:
            return None

        info = df.iloc[0].to_dict()
        # Solo retornar si hay datos utiles para risk analysis
        if info.get("is_verified"):
            return info
        return None

    def _get_twitter_mentions(self, token_info: dict) -> Optional[dict]:
        """
        Obtiene datos de menciones en X (Twitter) para un token.

        Usa TwitterClient para buscar menciones del simbolo del token.
        Si X API no esta configurado, retorna None silenciosamente.

        Args:
            token_info: Dict con informacion del token (necesita 'symbol', 'name').

        Returns:
            Dict con metricas de menciones, o None si no disponible.
        """
        try:
            from src.api.twitter_client import TwitterClient
        except ImportError:
            return None

        symbol = token_info.get("symbol", "")
        name = token_info.get("name", "")

        if not symbol:
            return None

        try:
            client = TwitterClient()
            if not client.is_configured:
                return None
            return client.get_mention_count(symbol, name)
        except Exception as e:
            logger.debug(f"Error obteniendo menciones de X: {e}")
            return None
