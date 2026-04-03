"""
labeler.py - Clasificacion automatica de tokens segun su historial de precios.

Este modulo analiza los datos OHLCV de cada token y le asigna una etiqueta
(label) que indica si fue un "gem", un "rug pull", un "fracaso", etc.

Clases:
    Labeler: Clasifica tokens en categorias multiclase y binaria.

Dependencias:
    - pandas: Para manipulacion de datos tabulares.
    - config: Para umbrales de clasificacion (LABELS_MULTI, etc.).
    - Storage: Para leer datos OHLCV y guardar labels.
"""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from src.data.storage import Storage
from src.data.supabase_storage import get_storage
from src.utils.logger import get_logger
from src.utils.helpers import safe_divide, safe_float

# Importar configuracion del proyecto
try:
    from config import (
        LABELS_MULTI,
        LABEL_BINARY_THRESHOLD,
        LABEL_BINARY_MODE,
        LABEL_RETURN_7D_THRESHOLD,
        LABEL_WINDOW_DAYS,
        MIN_DAYS_REQUIRED,
        TIER_THRESHOLDS,
    )
except ImportError:
    # Valores por defecto si no se puede importar config
    LABEL_WINDOW_DAYS = 30
    LABEL_BINARY_THRESHOLD = 5.0
    LABEL_BINARY_MODE = "return_7d"
    LABEL_RETURN_7D_THRESHOLD = 2.0
    MIN_DAYS_REQUIRED = 3
    LABELS_MULTI = {
        "gem": {"min_multiple": 10.0, "sustain_multiple": 5.0, "sustain_days": 7},
        "moderate_success": {"min_multiple": 3.0, "sustain_multiple": 2.0, "sustain_days": 3},
        "neutral": {"min_multiple": 0.3, "max_multiple": 3.0},
        "failure": {"max_multiple": 0.1},
        "rug": {"max_multiple": 0.01, "time_hours": 72, "liquidity_drop_pct": 0.9},
    }
    TIER_THRESHOLDS = {
        "mega_gem": 10.0,
        "standard_gem": 4.0,
        "mini_gem": 2.0,
        "micro_gem": 1.5,
        "neutral_upper": 1.5,
        "neutral_lower": 0.5,
        "failure": 0.5,
        "rug_drop_pct": 0.90,
        "rug_max_hours": 72,
    }

logger = get_logger(__name__)


class Labeler:
    """
    Clasifica tokens basandose en su historial de precios OHLCV.

    Cada token recibe dos tipos de etiqueta:
    - label_multi: Categoria detallada (gem, moderate_success, neutral, failure, rug).
    - label_binary: Clasificacion simple (1 = exito, 0 = no exito).

    La clasificacion se basa en:
    - El multiplo maximo alcanzado (max(high) / precio_inicial).
    - El multiplo final (ultimo close / precio_inicial).
    - Si el precio se mantuvo por encima de ciertos umbrales durante dias consecutivos.
    - Si hubo una caida extrema en las primeras 72 horas (rug pull).

    Args:
        storage: Instancia de Storage para leer datos OHLCV y guardar labels.

    Ejemplo:
        storage = get_storage()
        labeler = Labeler(storage)

        # Clasificar un token individual
        resultado = labeler.label_token("0xABC123...")
        print(resultado)
        # {'token_id': '0xABC123...', 'label_multi': 'gem', 'label_binary': 1,
        #  'max_multiple': 15.2, 'final_multiple': 8.1, 'notes': '...'}

        # Clasificar todos los tokens con datos suficientes
        df_labels = labeler.label_all_tokens()
    """

    def __init__(self, storage: Storage):
        """
        Inicializa el Labeler con acceso a la base de datos.

        Args:
            storage: Instancia de Storage para consultas y escrituras.
        """
        self.storage = storage

    # ============================================================
    # METODO PRINCIPAL: Clasificar un token
    # ============================================================

    def label_token(
        self, token_id: str, liquidity_data: pd.DataFrame = None
    ) -> Optional[dict]:
        """
        Clasifica un solo token basandose en sus datos OHLCV diarios.

        Pasos:
        1. Obtiene datos OHLCV diarios del token desde la base de datos.
        2. Verifica que haya al menos MIN_DAYS_REQUIRED dias de datos.
        3. Calcula el precio inicial (close de la primera vela).
        4. Calcula max_multiple y final_multiple.
        5. Aplica las reglas de clasificacion multiclase.
        6. Aplica la clasificacion binaria.
        7. Guarda el resultado en la base de datos.

        Args:
            token_id: Identificador unico del token (contract address).
            liquidity_data: DataFrame con snapshots de liquidez pre-fetched
                para este token (None = consultar DB individualmente).

        Returns:
            Dict con: token_id, label_multi, label_binary, max_multiple,
            final_multiple, notes. Retorna None si no hay datos suficientes.
        """
        # --- Paso 1: Obtener datos OHLCV diarios ---
        ohlcv_df = self.storage.get_ohlcv(token_id, timeframe="day")

        # --- Paso 1.5: Deteccion temprana de rug (antes del check de MIN_DAYS) ---
        # Si el token tiene 2+ velas y el precio cae 90%+ desde la primera,
        # lo clasificamos como "rug" inmediatamente, sin esperar MIN_DAYS.
        if not ohlcv_df.empty and len(ohlcv_df) >= 2:
            early_rug_result = self.label_early_rug(ohlcv_df, token_id)
            if early_rug_result is not None:
                # Guardar en la base de datos y retornar
                self.storage.upsert_label(early_rug_result)
                logger.info(
                    f"Token {token_id}: early rug detectado | "
                    f"max={early_rug_result['max_multiple']:.4f}x, "
                    f"final={early_rug_result['final_multiple']:.4f}x"
                )
                return early_rug_result

        # --- Paso 2: Verificar datos minimos ---
        if ohlcv_df.empty or len(ohlcv_df) < MIN_DAYS_REQUIRED:
            logger.warning(
                f"Token {token_id}: datos insuficientes "
                f"({len(ohlcv_df)} dias, minimo {MIN_DAYS_REQUIRED})"
            )
            return None

        # --- Paso 3: Limitar a la ventana de observacion ---
        # Solo usamos los primeros LABEL_WINDOW_DAYS dias
        ohlcv_df = ohlcv_df.head(LABEL_WINDOW_DAYS).copy()

        # Convertir columnas numericas por seguridad
        for col in ["open", "high", "low", "close", "volume"]:
            ohlcv_df[col] = ohlcv_df[col].apply(safe_float)

        # --- Paso 4: Calcular precio inicial ---
        # El precio inicial es el close de la primera vela diaria
        initial_price = safe_float(ohlcv_df.iloc[0]["close"])

        if initial_price <= 0:
            logger.warning(f"Token {token_id}: precio inicial invalido ({initial_price})")
            return None

        # --- Paso 5: Calcular multiples ---
        # max_multiple = el pico mas alto relativo al precio inicial (usa high = wicks)
        max_high = ohlcv_df["high"].max()
        max_multiple = safe_divide(max_high, initial_price, default=0.0)

        # close_max_multiple = maximo close relativo al precio inicial
        # Complementa max_multiple: high captura wicks momentaneos,
        # close captura precios de cierre confirmados.
        max_close = ohlcv_df["close"].max()
        close_max_multiple = safe_divide(max_close, initial_price, default=0.0)

        # final_multiple = precio actual relativo al precio inicial
        final_close = safe_float(ohlcv_df.iloc[-1]["close"])
        final_multiple = safe_divide(final_close, initial_price, default=0.0)

        # --- Paso 5b: Calcular return_7d ---
        # close del dia 7 / close del dia 1
        # Validamos que el candle en iloc[6] realmente corresponda a ~7 dias
        # (tolerancia de +-2 dias para gaps en datos OHLCV)
        if len(ohlcv_df) >= 7:
            try:
                ts_0 = pd.to_datetime(ohlcv_df.iloc[0]["timestamp"])
                ts_6 = pd.to_datetime(ohlcv_df.iloc[6]["timestamp"])
                delta_days = (ts_6 - ts_0).days
                if delta_days >= 5:  # tolerancia: 7 dias - 2 = 5 minimo
                    close_day7 = safe_float(ohlcv_df.iloc[6]["close"])
                    return_7d = safe_divide(close_day7, initial_price, default=0.0)
                else:
                    # Gap demasiado corto, no es un return real de 7 dias
                    logger.debug(
                        f"Token {token_id}: iloc[6] solo cubre {delta_days} dias, "
                        f"usando final_multiple como fallback"
                    )
                    return_7d = final_multiple
            except Exception:
                close_day7 = safe_float(ohlcv_df.iloc[6]["close"])
                return_7d = safe_divide(close_day7, initial_price, default=0.0)
        else:
            return_7d = final_multiple  # fallback si no hay 7 dias exactos

        # --- Paso 6: Obtener closes diarios para checks de sustain ---
        daily_closes = ohlcv_df["close"].tolist()

        # --- Paso 7: Clasificacion multiclase (de mas especifico a mas general) ---
        # El orden importa: evaluamos "rug" primero, luego "gem", etc.
        notes_parts = []
        label_multi = self._classify_multiclass(
            ohlcv_df=ohlcv_df,
            initial_price=initial_price,
            max_multiple=max_multiple,
            final_multiple=final_multiple,
            daily_closes=daily_closes,
            notes_parts=notes_parts,
            liquidity_data=liquidity_data,
        )

        # --- Paso 8: Clasificacion binaria ---
        # Segun modo configurado: return_7d (v5+) o max_multiple (v1-v4)
        if LABEL_BINARY_MODE == "return_7d":
            label_binary = 1 if return_7d >= LABEL_RETURN_7D_THRESHOLD else 0
        else:
            label_binary = 1 if max_multiple >= LABEL_BINARY_THRESHOLD else 0

        # --- Paso 9: Construir resultado ---
        notes = "; ".join(notes_parts) if notes_parts else ""

        result = {
            "token_id": token_id,
            "label_multi": label_multi,
            "label_binary": label_binary,
            "max_multiple": round(max_multiple, 4),
            "close_max_multiple": round(close_max_multiple, 4),
            "final_multiple": round(final_multiple, 4),
            "return_7d": round(return_7d, 4),
            "notes": notes,
        }

        # --- Paso 10: Guardar en la base de datos ---
        self.storage.upsert_label(result)
        logger.info(
            f"Token {token_id}: {label_multi} | "
            f"max={max_multiple:.2f}x, final={final_multiple:.2f}x, "
            f"return_7d={return_7d:.2f}x, binario={label_binary}"
        )

        return result

    # ============================================================
    # CLASIFICAR TODOS LOS TOKENS
    # ============================================================

    def label_all_tokens(self) -> pd.DataFrame:
        """
        Clasifica todos los tokens que tengan suficientes datos OHLCV.

        Obtiene la lista de tokens desde la tabla 'tokens', intenta
        clasificar cada uno, y devuelve un DataFrame con todos los resultados.

        Optimizacion: pre-fetch de TODOS los snapshots de liquidez en una
        sola query (evita N+1 queries individuales por token en _is_rug).

        Returns:
            DataFrame con columnas: token_id, label_multi, label_binary,
            max_multiple, final_multiple, notes.
        """
        # Obtener todos los tokens registrados
        tokens_df = self.storage.get_all_tokens()

        if tokens_df.empty:
            logger.warning("No hay tokens en la base de datos para clasificar.")
            return pd.DataFrame()

        logger.info(f"Clasificando {len(tokens_df)} tokens...")

        # --- Pre-fetch de snapshots de liquidez para deteccion de rug ---
        # Una sola query en vez de una por token (evita N+1 queries)
        snapshots_by_token = {}
        try:
            all_snapshots = self.storage.query(
                "SELECT token_id, liquidity_usd, snapshot_time "
                "FROM pool_snapshots ORDER BY token_id, snapshot_time"
            )
            if not all_snapshots.empty:
                snapshots_by_token = {
                    tid: group_df.reset_index(drop=True)
                    for tid, group_df in all_snapshots.groupby("token_id")
                }
            logger.info(
                f"Pre-fetch liquidez: {len(snapshots_by_token)} tokens "
                f"con snapshots (total {len(all_snapshots)} filas)"
            )
        except Exception as e:
            logger.warning(f"No se pudo pre-fetch liquidez (se consultara por token): {e}")

        resultados = []
        exitos = 0
        fallos = 0

        for _, row in tokens_df.iterrows():
            token_id = row["token_id"]
            try:
                # Pasar snapshots pre-fetched (DataFrame vacio si no hay datos)
                liq_data = snapshots_by_token.get(token_id, pd.DataFrame())
                resultado = self.label_token(token_id, liquidity_data=liq_data)
                if resultado is not None:
                    resultados.append(resultado)
                    exitos += 1
                else:
                    fallos += 1
            except Exception as e:
                logger.error(f"Error clasificando token {token_id}: {e}")
                fallos += 1

        logger.info(
            f"Clasificacion completada: {exitos} exitos, {fallos} sin datos suficientes"
        )

        if not resultados:
            return pd.DataFrame()

        # Convertir la lista de dicts a DataFrame
        df = pd.DataFrame(resultados)

        # Mostrar resumen de distribucion de labels
        if not df.empty:
            distribucion = df["label_multi"].value_counts()
            logger.info(f"Distribucion de labels:\n{distribucion.to_string()}")

        return df

    # ============================================================
    # LOGICA INTERNA DE CLASIFICACION
    # ============================================================

    def _classify_multiclass(
        self,
        ohlcv_df: pd.DataFrame,
        initial_price: float,
        max_multiple: float,
        final_multiple: float,
        daily_closes: list,
        notes_parts: list,
        liquidity_data: pd.DataFrame = None,
    ) -> str:
        """
        Aplica las reglas de clasificacion multiclase.

        El orden de evaluacion es importante:
        1. Primero verificamos si es un "rug" (caida extrema temprana).
        2. Luego si es un "failure" (perdio 90%+).
        3. Luego si es un "gem" (alcanzo 10x y se mantuvo).
        4. Luego si es "moderate_success" (alcanzo 3x y se mantuvo).
        5. Si nada coincide, es "neutral".

        Args:
            ohlcv_df: DataFrame con datos OHLCV diarios.
            initial_price: Precio close de la primera vela.
            max_multiple: Maximo multiplo alcanzado.
            final_multiple: Multiplo final.
            daily_closes: Lista de precios close diarios.
            notes_parts: Lista mutable donde agregar notas explicativas.
            liquidity_data: DataFrame con snapshots de liquidez pre-fetched
                (None = consultar DB individualmente).

        Returns:
            String con la etiqueta: "rug", "failure", "gem",
            "moderate_success", o "neutral".
        """
        # --- CHECK 1: Rug Pull ---
        if self._is_rug(ohlcv_df, initial_price, notes_parts, liquidity_data=liquidity_data):
            return "rug"

        # --- CHECK 2: Failure (perdio 90%+) ---
        failure_config = LABELS_MULTI["failure"]
        if final_multiple < failure_config["max_multiple"]:
            notes_parts.append(
                f"Failure: precio final {final_multiple:.4f}x "
                f"(< {failure_config['max_multiple']}x)"
            )
            return "failure"

        # --- CHECK 2.5: Pump and Dump (subio 5x+ pero no mantuvo) ---
        if max_multiple >= 5.0 and final_multiple < 1.5:
            notes_parts.append(
                f"Pump&Dump: max {max_multiple:.2f}x pero final {final_multiple:.2f}x"
            )
            return "pump_and_dump"

        # --- CHECK 3: Gem (alcanzo 10x y se mantuvo >5x por 7+ dias) ---
        gem_config = LABELS_MULTI["gem"]
        if max_multiple >= gem_config["min_multiple"]:
            # Verificar que se mantuvo por encima del umbral de sustain
            consecutive = self._max_consecutive_days_above(
                daily_closes, initial_price, gem_config["sustain_multiple"]
            )
            if consecutive >= gem_config["sustain_days"]:
                notes_parts.append(
                    f"Gem: max {max_multiple:.2f}x, "
                    f"sostuvo >{gem_config['sustain_multiple']}x "
                    f"por {consecutive} dias consecutivos"
                )
                return "gem"

        # --- CHECK 4: Moderate Success (alcanzo 3x y se mantuvo >2x por 3+ dias) ---
        mod_config = LABELS_MULTI["moderate_success"]
        if max_multiple >= mod_config["min_multiple"]:
            consecutive = self._max_consecutive_days_above(
                daily_closes, initial_price, mod_config["sustain_multiple"]
            )
            if consecutive >= mod_config["sustain_days"]:
                notes_parts.append(
                    f"Exito moderado: max {max_multiple:.2f}x, "
                    f"sostuvo >{mod_config['sustain_multiple']}x "
                    f"por {consecutive} dias consecutivos"
                )
                return "moderate_success"

        # --- CHECK 5: Neutral (se mantuvo entre 0.3x y 3x) ---
        neutral_config = LABELS_MULTI["neutral"]
        if (
            final_multiple >= neutral_config["min_multiple"]
            and final_multiple <= neutral_config["max_multiple"]
        ):
            notes_parts.append(
                f"Neutral: final {final_multiple:.2f}x "
                f"(entre {neutral_config['min_multiple']}x y {neutral_config['max_multiple']}x)"
            )
            return "neutral"

        # --- Si el token no encaja en ninguna categoria definida claramente ---
        # Puede ser un token que subio mucho pero no sostuvo, o que bajo
        # pero no tanto como para ser "failure"
        notes_parts.append(
            f"Neutral (por defecto): max {max_multiple:.2f}x, final {final_multiple:.2f}x"
        )
        return "neutral"

    def _is_rug(
        self,
        ohlcv_df: pd.DataFrame,
        initial_price: float,
        notes_parts: list,
        liquidity_data: pd.DataFrame = None,
    ) -> bool:
        """
        Detecta si un token sufrio un rug pull.

        Un rug pull se identifica si:
        - El precio cayo por debajo de 0.01x en las primeras 72 horas (3 dias).
        - O si la liquidez cayo 90%+ (si hay datos de liquidez disponibles).

        Args:
            ohlcv_df: DataFrame con datos OHLCV.
            initial_price: Precio inicial del token.
            notes_parts: Lista donde agregar notas.
            liquidity_data: DataFrame con columnas liquidity_usd, snapshot_time
                para este token (pre-fetched). Si es None, consulta la DB.

        Returns:
            True si el token es un rug pull.
        """
        rug_config = LABELS_MULTI["rug"]
        rug_threshold = rug_config["max_multiple"]  # 0.01x
        rug_hours = rug_config["time_hours"]  # 72 horas

        # Calcular cuantos dias equivalen a las horas configuradas
        # (72h = 3 dias, redondeando hacia arriba)
        rug_days = max(1, rug_hours // 24)

        # Verificar los primeros 'rug_days' dias de datos
        early_data = ohlcv_df.head(rug_days)

        if early_data.empty:
            return False

        # Verificar si el low cayo por debajo del umbral
        min_low = early_data["low"].min()
        min_multiple = safe_divide(min_low, initial_price, default=1.0)

        if min_multiple <= rug_threshold:
            notes_parts.append(
                f"Rug pull: precio cayo a {min_multiple:.6f}x "
                f"en primeras {rug_hours}h"
            )
            return True

        # --- Verificar caida de liquidez (si hay datos de pool_snapshots) ---
        # Si se paso liquidity_data pre-fetched, usarlo directamente.
        # Si no, consultar la DB (caso de label_token individual).
        try:
            if liquidity_data is not None:
                liq_df = liquidity_data
            else:
                token_id = ohlcv_df.iloc[0]["token_id"]
                liq_df = self.storage.query(
                    """SELECT liquidity_usd, snapshot_time
                       FROM pool_snapshots
                       WHERE token_id = ?
                       ORDER BY snapshot_time""",
                    (token_id,),
                )

            if not liq_df.empty and len(liq_df) >= 2:
                # Comparar primera y minima liquidez
                first_liq = safe_float(liq_df.iloc[0]["liquidity_usd"])
                min_liq = safe_float(liq_df["liquidity_usd"].min())

                if first_liq > 0:
                    liq_drop = 1.0 - safe_divide(min_liq, first_liq, default=1.0)
                    if liq_drop >= rug_config["liquidity_drop_pct"]:
                        notes_parts.append(
                            f"Rug pull: liquidez cayo {liq_drop*100:.1f}% "
                            f"(de ${first_liq:,.0f} a ${min_liq:,.0f})"
                        )
                        return True
        except Exception as e:
            # Si no podemos consultar liquidez, no es un error critico
            logger.debug(f"No se pudo verificar liquidez para rug check: {e}")

        return False

    def _max_consecutive_days_above(
        self,
        daily_closes: list,
        initial_price: float,
        multiple_threshold: float,
    ) -> int:
        """
        Cuenta el maximo de dias CONSECUTIVOS donde el close estuvo
        por encima de un multiplo del precio inicial.

        Por ejemplo, si multiple_threshold=5.0 y initial_price=0.001,
        contamos los dias donde close >= 0.005.

        Args:
            daily_closes: Lista de precios close diarios.
            initial_price: Precio de referencia.
            multiple_threshold: Multiplo minimo requerido (ej: 5.0 = 5x).

        Returns:
            Numero maximo de dias consecutivos por encima del umbral.
        """
        if initial_price <= 0:
            return 0

        # Precio umbral = precio_inicial * multiplo
        price_threshold = initial_price * multiple_threshold

        # Recorrer los closes y contar racha maxima consecutiva
        max_consecutive = 0
        current_streak = 0

        for close_price in daily_closes:
            close_val = safe_float(close_price)
            if close_val >= price_threshold:
                current_streak += 1
                max_consecutive = max(max_consecutive, current_streak)
            else:
                # Se rompio la racha
                current_streak = 0

        return max_consecutive

    # ============================================================
    # DETECCION TEMPRANA DE RUG PULL (M1)
    # ============================================================

    def label_early_rug(self, ohlcv_df: pd.DataFrame, token_id: str = "") -> Optional[dict]:
        """
        Detecta rug pulls tempranos sin necesitar MIN_DAYS_REQUIRED dias de datos.

        Si un token tiene 2+ velas y el precio cae 90%+ desde el close de la
        primera vela, se clasifica inmediatamente como "rug". Esto captura
        tokens que hacen rug en 48-72h sin tener que esperar dias de datos.

        Args:
            ohlcv_df: DataFrame con datos OHLCV diarios (al menos 2 filas).
            token_id: Identificador del token (para el resultado).

        Returns:
            Dict con label "rug" si se detecta early rug, None si no aplica.
        """
        if ohlcv_df.empty or len(ohlcv_df) < 2:
            return None

        # Copiar para no modificar el original y convertir columnas numericas
        df = ohlcv_df.copy()
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = df[col].apply(safe_float)

        initial_price = safe_float(df.iloc[0]["close"])
        if initial_price <= 0:
            return None

        # Verificar si el precio cayo 90%+ desde el inicio
        # Usamos el low mas bajo para capturar la caida maxima
        min_low = df["low"].min()
        min_multiple = safe_divide(min_low, initial_price, default=1.0)

        # Umbral: caida de 90% = el precio quedo en 10% o menos del original
        rug_drop_threshold = 1.0 - TIER_THRESHOLDS.get("rug_drop_pct", 0.90)

        if min_multiple <= rug_drop_threshold:
            # Es un early rug — calcular metricas basicas
            max_high = df["high"].max()
            max_multiple = safe_divide(max_high, initial_price, default=0.0)
            final_close = safe_float(df.iloc[-1]["close"])
            final_multiple = safe_divide(final_close, initial_price, default=0.0)

            return {
                "token_id": token_id,
                "label_multi": "rug",
                "label_binary": 0,
                "max_multiple": round(max_multiple, 4),
                "close_max_multiple": round(
                    safe_divide(df["close"].max(), initial_price, default=0.0), 4
                ),
                "final_multiple": round(final_multiple, 4),
                "return_7d": round(final_multiple, 4),  # No hay 7d, usar final
                "notes": (
                    f"Early rug: precio cayo a {min_multiple:.6f}x "
                    f"({(1 - min_multiple) * 100:.1f}% caida) "
                    f"en {len(df)} velas"
                ),
            }

        return None

    # ============================================================
    # CLASIFICACION POR TIERS (M2) — Sistema granular adicional
    # ============================================================

    def label_tiered(self, ohlcv_df: pd.DataFrame, token_id: str = "") -> dict:
        """
        Etiquetado por tiers para clasificacion mas granular.

        Sistema de 7 niveles basado en el retorno maximo alcanzado dentro
        de la ventana de observacion. Complementa (NO reemplaza) el sistema
        binario y multiclase existente.

        Tiers (de mayor a menor rendimiento):
        - mega_gem (6): max return >= 10x (1000%)
        - standard_gem (5): max return >= 4x (300%)
        - mini_gem (4): max return >= 2x (100%)
        - micro_gem (3): max return >= 1.5x (50%)
        - neutral (2): max return entre 0.5x y 1.5x
        - failure (1): max return < 0.5x (perdio 50%+)
        - rug (0): precio cae 90%+ en primeras 72h

        Args:
            ohlcv_df: DataFrame con datos OHLCV diarios.
            token_id: Identificador del token (para el resultado).

        Returns:
            Dict con: tier, tier_numeric, max_return, details.
        """
        if ohlcv_df.empty or len(ohlcv_df) < 2:
            return {
                "tier": "unknown",
                "tier_numeric": -1,
                "max_return": 0.0,
                "details": "Datos insuficientes para clasificar tier",
            }

        # Copiar y convertir columnas numericas
        df = ohlcv_df.copy()
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = df[col].apply(safe_float)

        initial_price = safe_float(df.iloc[0]["close"])
        if initial_price <= 0:
            return {
                "tier": "unknown",
                "tier_numeric": -1,
                "max_return": 0.0,
                "details": "Precio inicial invalido",
            }

        # Calcular max return (usando high para capturar picos)
        max_high = df["high"].max()
        max_return = safe_divide(max_high, initial_price, default=0.0)

        # --- Check 1: Rug Pull (caida 90%+ en primeras 72h) ---
        rug_hours = TIER_THRESHOLDS.get("rug_max_hours", 72)
        rug_days = max(1, int(rug_hours // 24))
        early_data = df.head(rug_days)

        if not early_data.empty:
            min_low = early_data["low"].min()
            min_multiple = safe_divide(min_low, initial_price, default=1.0)
            rug_threshold = 1.0 - TIER_THRESHOLDS.get("rug_drop_pct", 0.90)

            if min_multiple <= rug_threshold:
                return {
                    "tier": "rug",
                    "tier_numeric": 0,
                    "max_return": round(max_return, 4),
                    "details": (
                        f"Rug: precio cayo a {min_multiple:.6f}x "
                        f"en primeras {rug_hours}h"
                    ),
                }

        # --- Check 2: Clasificar por max return ---
        if max_return >= TIER_THRESHOLDS["mega_gem"]:
            tier, tier_num = "mega_gem", 6
            details = f"Mega gem: max return {max_return:.2f}x (>= {TIER_THRESHOLDS['mega_gem']}x)"
        elif max_return >= TIER_THRESHOLDS["standard_gem"]:
            tier, tier_num = "standard_gem", 5
            details = f"Standard gem: max return {max_return:.2f}x (>= {TIER_THRESHOLDS['standard_gem']}x)"
        elif max_return >= TIER_THRESHOLDS["mini_gem"]:
            tier, tier_num = "mini_gem", 4
            details = f"Mini gem: max return {max_return:.2f}x (>= {TIER_THRESHOLDS['mini_gem']}x)"
        elif max_return >= TIER_THRESHOLDS["micro_gem"]:
            tier, tier_num = "micro_gem", 3
            details = f"Micro gem: max return {max_return:.2f}x (>= {TIER_THRESHOLDS['micro_gem']}x)"
        elif max_return >= TIER_THRESHOLDS["neutral_lower"]:
            tier, tier_num = "neutral", 2
            details = (
                f"Neutral: max return {max_return:.2f}x "
                f"(entre {TIER_THRESHOLDS['neutral_lower']}x y {TIER_THRESHOLDS['neutral_upper']}x)"
            )
        else:
            tier, tier_num = "failure", 1
            details = f"Failure: max return {max_return:.2f}x (< {TIER_THRESHOLDS['failure']}x)"

        return {
            "tier": tier,
            "tier_numeric": tier_num,
            "max_return": round(max_return, 4),
            "details": details,
        }

    def label_all_tokens_tiered(self) -> pd.DataFrame:
        """
        Clasifica todos los tokens con el sistema de tiers.

        Obtiene la lista de tokens desde la tabla 'tokens', aplica
        label_tiered() a cada uno, y guarda los campos tier y tier_numeric
        en la tabla labels (via upsert).

        Returns:
            DataFrame con columnas: token_id, tier, tier_numeric, max_return, details.
        """
        tokens_df = self.storage.get_all_tokens()

        if tokens_df.empty:
            logger.warning("No hay tokens para clasificar con tiers.")
            return pd.DataFrame()

        logger.info(f"Clasificando {len(tokens_df)} tokens con sistema de tiers...")

        resultados = []
        exitos = 0
        fallos = 0

        for _, row in tokens_df.iterrows():
            token_id = row["token_id"]
            try:
                ohlcv_df = self.storage.get_ohlcv(token_id, timeframe="day")
                if ohlcv_df.empty or len(ohlcv_df) < 2:
                    fallos += 1
                    continue

                # Limitar a ventana de observacion
                ohlcv_df = ohlcv_df.head(LABEL_WINDOW_DAYS).copy()

                tier_result = self.label_tiered(ohlcv_df, token_id)
                tier_result["token_id"] = token_id
                resultados.append(tier_result)

                # Actualizar la tabla labels con tier y tier_numeric
                # (upsert parcial: solo agrega/actualiza campos de tier)
                self.storage.upsert_label({
                    "token_id": token_id,
                    "tier": tier_result["tier"],
                    "tier_numeric": tier_result["tier_numeric"],
                })

                exitos += 1

            except Exception as e:
                logger.error(f"Error clasificando tier para token {token_id}: {e}")
                fallos += 1

        logger.info(
            f"Clasificacion por tiers completada: "
            f"{exitos} exitos, {fallos} sin datos suficientes"
        )

        if not resultados:
            return pd.DataFrame()

        df = pd.DataFrame(resultados)

        # Mostrar distribucion de tiers
        if not df.empty:
            distribucion = df["tier"].value_counts()
            logger.info(f"Distribucion de tiers:\n{distribucion.to_string()}")

        return df

    # ============================================================
    # SENSITIVITY ANALYSIS
    # ============================================================

    def sensitivity_analysis(self, storage=None) -> pd.DataFrame:
        """
        Analiza como cambian las distribuciones de labels al variar umbrales.

        Los umbrales de clasificacion (gem=10x, sustain=5x/7d, failure<0.1x)
        son arbitrarios. Este metodo testea combinaciones para verificar que
        pequenos cambios no producen distribuciones muy diferentes.

        Args:
            storage: Instancia de Storage (si None, usa self.storage).

        Returns:
            DataFrame con columnas: gem_min_multiple, gem_sustain_multiple,
            gem_sustain_days, binary_threshold, gem_count, moderate_count,
            neutral_count, failure_count, rug_count, y porcentajes.
        """
        st = storage or self.storage

        # Obtener todos los tokens con OHLCV suficiente
        tokens_df = st.get_all_tokens()
        if tokens_df.empty:
            logger.warning("No hay tokens para sensitivity analysis")
            return pd.DataFrame()

        # Pre-calcular datos OHLCV para todos los tokens
        token_data = {}
        for _, row in tokens_df.iterrows():
            token_id = row["token_id"]
            ohlcv_df = st.get_ohlcv(token_id, timeframe="day")
            if ohlcv_df.empty or len(ohlcv_df) < MIN_DAYS_REQUIRED:
                continue

            ohlcv_df = ohlcv_df.head(LABEL_WINDOW_DAYS).copy()
            for col in ["open", "high", "low", "close", "volume"]:
                ohlcv_df[col] = ohlcv_df[col].apply(safe_float)

            initial_price = safe_float(ohlcv_df.iloc[0]["close"])
            if initial_price <= 0:
                continue

            max_high = ohlcv_df["high"].max()
            max_multiple = safe_divide(max_high, initial_price, default=0.0)
            final_close = safe_float(ohlcv_df.iloc[-1]["close"])
            final_multiple = safe_divide(final_close, initial_price, default=0.0)
            daily_closes = ohlcv_df["close"].tolist()

            token_data[token_id] = {
                "max_multiple": max_multiple,
                "final_multiple": final_multiple,
                "daily_closes": daily_closes,
                "initial_price": initial_price,
            }

        if not token_data:
            logger.warning("No hay tokens con datos suficientes para sensitivity analysis")
            return pd.DataFrame()

        logger.info(f"Sensitivity analysis: {len(token_data)} tokens evaluables")

        # Combinaciones de parametros
        gem_min_multiples = [5, 7, 10, 15, 20]
        gem_sustain_multiples = [3, 5, 7]
        gem_sustain_days_list = [3, 5, 7, 14]
        binary_thresholds = [3, 5, 7, 10]

        rows = []
        total = len(token_data)

        for gmin in gem_min_multiples:
            for gsus in gem_sustain_multiples:
                for gdays in gem_sustain_days_list:
                    for bt in binary_thresholds:
                        counts = {"gem": 0, "moderate_success": 0, "neutral": 0,
                                  "failure": 0, "rug": 0}

                        for tid, td in token_data.items():
                            mm = td["max_multiple"]
                            fm = td["final_multiple"]

                            # Clasificar con parametros ajustados
                            if fm < 0.1:
                                label = "failure"
                            elif mm >= gmin:
                                consec = self._max_consecutive_days_above(
                                    td["daily_closes"], td["initial_price"], gsus
                                )
                                if consec >= gdays:
                                    label = "gem"
                                elif mm >= 3.0:
                                    label = "moderate_success"
                                else:
                                    label = "neutral"
                            elif mm >= 3.0:
                                label = "moderate_success"
                            else:
                                label = "neutral"

                            counts[label] += 1

                        row = {
                            "gem_min_multiple": gmin,
                            "gem_sustain_multiple": gsus,
                            "gem_sustain_days": gdays,
                            "binary_threshold": bt,
                        }
                        for cat, count in counts.items():
                            row[f"{cat}_count"] = count
                            row[f"{cat}_pct"] = round(count / total * 100, 1) if total > 0 else 0

                        rows.append(row)

        df = pd.DataFrame(rows)

        # Advertir sobre clases con <5% de tokens
        for _, row in df.iterrows():
            for cat in ["gem", "moderate_success", "neutral", "failure"]:
                pct = row[f"{cat}_pct"]
                if 0 < pct < 5:
                    logger.warning(
                        f"Clase '{cat}' tiene solo {pct}% con "
                        f"gem_min={row['gem_min_multiple']}, "
                        f"sustain={row['gem_sustain_multiple']}x/{row['gem_sustain_days']}d, "
                        f"binary_t={row['binary_threshold']}"
                    )

        logger.info(f"Sensitivity analysis completado: {len(df)} combinaciones evaluadas")
        return df

    def validate_label_window(
        self,
        storage=None,
        windows: Optional[list] = None,
    ) -> pd.DataFrame:
        """
        Verifica la estabilidad de las clasificaciones entre diferentes ventanas.

        Compara cuantos tokens cambian de clase al variar la ventana de
        observacion (14, 21, 30, 45, 60 dias).

        Args:
            storage: Instancia de Storage (si None, usa self.storage).
            windows: Lista de ventanas en dias. Por defecto [14, 21, 30, 45, 60].

        Returns:
            DataFrame con columnas: window, gem, moderate, neutral, failure, rug,
            flip_rate (porcentaje de tokens que cambiaron respecto a la ventana anterior).
        """
        if windows is None:
            windows = [14, 21, 30, 45, 60]

        st = storage or self.storage
        tokens_df = st.get_all_tokens()

        if tokens_df.empty:
            return pd.DataFrame()

        # Pre-cargar OHLCV (usamos la ventana mas grande)
        max_window = max(windows)
        token_data = {}
        for _, row in tokens_df.iterrows():
            token_id = row["token_id"]
            ohlcv_df = st.get_ohlcv(token_id, timeframe="day")
            if ohlcv_df.empty or len(ohlcv_df) < MIN_DAYS_REQUIRED:
                continue
            ohlcv_df = ohlcv_df.head(max_window).copy()
            for col in ["open", "high", "low", "close", "volume"]:
                ohlcv_df[col] = ohlcv_df[col].apply(safe_float)
            token_data[token_id] = ohlcv_df

        if not token_data:
            return pd.DataFrame()

        logger.info(f"Validate label window: {len(token_data)} tokens, {len(windows)} ventanas")

        # Clasificar cada token con cada ventana
        window_labels = {}  # {window: {token_id: label}}
        for w in windows:
            labels = {}
            for tid, full_ohlcv in token_data.items():
                ohlcv_w = full_ohlcv.head(w)
                if len(ohlcv_w) < MIN_DAYS_REQUIRED:
                    continue

                initial_price = safe_float(ohlcv_w.iloc[0]["close"])
                if initial_price <= 0:
                    continue

                max_high = ohlcv_w["high"].max()
                max_multiple = safe_divide(max_high, initial_price, default=0.0)
                final_close = safe_float(ohlcv_w.iloc[-1]["close"])
                final_multiple = safe_divide(final_close, initial_price, default=0.0)
                daily_closes = ohlcv_w["close"].tolist()

                notes_parts = []
                label = self._classify_multiclass(
                    ohlcv_df=ohlcv_w,
                    initial_price=initial_price,
                    max_multiple=max_multiple,
                    final_multiple=final_multiple,
                    daily_closes=daily_closes,
                    notes_parts=notes_parts,
                )
                labels[tid] = label

            window_labels[w] = labels

        # Calcular distribuciones y flip rates
        rows = []
        prev_labels = None
        for w in windows:
            labels = window_labels[w]
            dist = pd.Series(labels.values()).value_counts()

            row = {
                "window": w,
                "gem": int(dist.get("gem", 0)),
                "moderate_success": int(dist.get("moderate_success", 0)),
                "neutral": int(dist.get("neutral", 0)),
                "failure": int(dist.get("failure", 0)),
                "rug": int(dist.get("rug", 0)),
                "total": len(labels),
            }

            # Calcular flip_rate vs ventana anterior
            if prev_labels is not None:
                common_tokens = set(labels.keys()) & set(prev_labels.keys())
                if common_tokens:
                    flips = sum(1 for t in common_tokens if labels[t] != prev_labels[t])
                    row["flip_rate"] = round(flips / len(common_tokens) * 100, 1)
                else:
                    row["flip_rate"] = 0.0
            else:
                row["flip_rate"] = 0.0  # No hay ventana anterior

            rows.append(row)
            prev_labels = labels

        df = pd.DataFrame(rows)
        logger.info(f"Estabilidad de labels por ventana:\n{df.to_string(index=False)}")
        return df
