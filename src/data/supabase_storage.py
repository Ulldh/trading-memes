"""
supabase_storage.py - Almacenamiento en Supabase via REST API.

Misma interfaz publica que Storage (SQLite), para que el resto del
proyecto pueda usar cualquiera de los dos backends sin cambios.

Usa supabase-py con service_role key para:
- Bypass completo de RLS (acceso total desde scripts y GitHub Actions)
- Operaciones CRUD via PostgREST (tabla API nativa)
- Consultas SQL via funciones RPC (exec_query/exec_sql) con validacion

Seguridad:
- SQL allowlist: solo SELECT/INSERT/UPDATE/DELETE/WITH permitidos
- Patrones peligrosos bloqueados (DROP, ALTER, TRUNCATE, etc.)
- Parametros escapados con proteccion contra inyeccion SQL
- PostgREST preferido sobre RPC cuando es posible

No requiere psycopg2 ni conexion directa a PostgreSQL.
Funciona desde cualquier red via HTTPS.

Uso:
    from src.data.supabase_storage import get_storage
    storage = get_storage()  # Retorna SupabaseStorage si STORAGE_BACKEND=supabase
    storage.upsert_token({...})
    df = storage.query("SELECT * FROM tokens WHERE chain = ?", ("solana",))
"""

import math
import json
import re
from typing import Optional

import pandas as pd

from src.utils.logger import get_logger

try:
    from config import (
        SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY,
    )
except ImportError:
    import os
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

logger = get_logger(__name__)

# Tamano de pagina para consultas paginadas via PostgREST
_PAGE_SIZE = 1000
# Tamano de batch para inserciones masivas
_BATCH_SIZE = 500


def _create_client():
    """
    Crea cliente supabase-py con service_role key (bypass RLS).

    Prioriza service_role sobre anon para acceso completo a todas las
    tablas sin restricciones de Row Level Security.
    """
    if not SUPABASE_URL:
        raise ValueError("SUPABASE_URL no configurada en .env")

    key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
    if not key:
        raise ValueError(
            "SUPABASE_SERVICE_ROLE_KEY o SUPABASE_ANON_KEY necesaria en .env. "
            "Obtener en: Dashboard Supabase > Settings > API"
        )

    from supabase import create_client
    return create_client(SUPABASE_URL, key)


class SupabaseStorage:
    """
    Interfaz de almacenamiento usando Supabase REST API (PostgREST).

    Mismos metodos publicos que Storage (SQLite) para intercambiabilidad.
    Usa supabase-py con service_role key para bypass de RLS.
    No necesita psycopg2 ni conexion directa a PostgreSQL.

    Args:
        client: Cliente supabase-py (opcional, se crea automaticamente).
    """

    def __init__(self, client=None):
        self._client = client or _create_client()
        # Verificar conexion con una consulta simple
        try:
            resp = self._client.table("tokens").select(
                "token_id", count="exact", head=True
            ).execute()
            logger.info(f"SupabaseStorage: conexion verificada ({resp.count} tokens)")
        except Exception as e:
            logger.error(f"SupabaseStorage: error de conexion: {e}")
            raise

    # ============================================================
    # SEGURIDAD: Validacion SQL y escapado de parametros
    # ============================================================

    # Prefijos SQL permitidos (operaciones CRUD + CTEs)
    _ALLOWED_SQL_PREFIXES = ("SELECT", "INSERT", "UPDATE", "DELETE", "WITH")

    # Regex con word boundaries para DDL peligroso (evita falsos positivos)
    _DANGEROUS_SQL = re.compile(
        r'\b(DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY)\b',
        re.IGNORECASE,
    )

    # Patrones bloqueados adicionales — acceso a metadatos, comentarios
    _BLOCKED_PATTERNS = [
        "pg_", "information_schema",
        "--",       # Comentarios SQL de linea
        "/*",       # Comentarios SQL de bloque (apertura)
        "*/",       # Comentarios SQL de bloque (cierre)
        "\\\\",     # Backslash escapes
    ]

    # Regex precompilado para detectar patrones bloqueados (case-insensitive)
    _BLOCKED_RE = re.compile(
        "|".join(re.escape(p) for p in _BLOCKED_PATTERNS),
        re.IGNORECASE,
    )

    def _validate_sql(self, sql: str):
        """
        Valida que el SQL solo contenga operaciones permitidas.

        Defensa en profundidad: bloquea DDL, acceso a catalogo del sistema,
        comentarios SQL (usados frecuentemente en inyecciones), semicolons
        (multi-statement injection) y otros patrones peligrosos ANTES de
        enviar al RPC.

        Raises:
            ValueError: Si el SQL contiene operaciones no permitidas.
        """
        sql_stripped = sql.strip()
        sql_upper = sql_stripped.upper()

        # Verificar prefijo permitido (SELECT, INSERT, UPDATE, DELETE, WITH)
        if not any(sql_upper.startswith(prefix) for prefix in self._ALLOWED_SQL_PREFIXES):
            raise ValueError(
                f"SQL no permitido: debe empezar con "
                f"{'/'.join(self._ALLOWED_SQL_PREFIXES)}. "
                f"Recibido: {sql_stripped[:50]}..."
            )

        # Bloquear semicolons para prevenir multi-statement injection
        if ";" in sql_stripped:
            raise ValueError(
                "SQL contiene ';' — multi-statement no permitido: "
                f"{sql_stripped[:80]}..."
            )

        # Buscar DDL peligroso con word boundaries
        match_ddl = self._DANGEROUS_SQL.search(sql_stripped)
        if match_ddl:
            raise ValueError(
                f"SQL contiene operacion DDL bloqueada: '{match_ddl.group()}' "
                f"en consulta: {sql_stripped[:80]}..."
            )

        # Buscar patrones bloqueados adicionales
        match = self._BLOCKED_RE.search(sql_stripped)
        if match:
            raise ValueError(
                f"SQL contiene patron bloqueado: '{match.group()}' "
                f"en consulta: {sql_stripped[:80]}..."
            )

    # ============================================================
    # OPERACIONES GENERICAS (compatibilidad con Storage SQLite)
    # ============================================================

    @staticmethod
    def _format_param(param) -> str:
        """
        Formatea un parametro Python a literal SQL de PostgreSQL.

        Protecciones aplicadas:
        - None → NULL
        - bool → TRUE/FALSE (antes de int, porque bool es subclase de int)
        - int/float → str directo (con validacion de NaN/Inf)
        - str → escapado de backslashes, comillas simples, null bytes
        """
        if param is None:
            return "NULL"
        if isinstance(param, bool):
            return "TRUE" if param else "FALSE"
        if isinstance(param, (int, float)):
            # Proteger contra NaN/Inf que podrian causar errores en PG
            if isinstance(param, float) and (math.isnan(param) or math.isinf(param)):
                return "NULL"
            return str(param)
        # Strings: escapar backslashes, comillas simples y null bytes
        val = str(param)
        val = val.replace("\\", "\\\\")   # Escapar backslashes primero
        val = val.replace("'", "''")       # Escapar comillas simples
        val = val.replace("\x00", "")      # Eliminar null bytes
        return f"'{val}'"

    def _substitute_params(self, sql: str, params: tuple) -> str:
        """
        Sustituye placeholders (? o %s) con valores reales.

        Soporta tanto ? (SQLite style) como %s (PostgreSQL style)
        para compatibilidad con todo el codebase.
        """
        if not params:
            return sql
        result = sql
        for param in params:
            val = self._format_param(param)
            if "?" in result:
                result = result.replace("?", val, 1)
            elif "%s" in result:
                result = result.replace("%s", val, 1)
        return result

    def _rpc_query(self, sql: str) -> list:
        """
        Ejecuta SQL via RPC exec_query y retorna lista de dicts.

        Valida el SQL contra el allowlist antes de enviar al RPC.
        """
        self._validate_sql(sql)
        resp = self._client.rpc("exec_query", {"query_text": sql}).execute()
        data = resp.data
        if isinstance(data, str):
            data = json.loads(data)
        return data or []

    def query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        """
        Ejecuta una consulta SQL (SELECT) y devuelve un DataFrame.

        Usa la funcion RPC exec_query() con validacion de seguridad.
        Soporta placeholders ? (SQLite) y %s (PostgreSQL).

        Args:
            sql: Consulta SQL (SELECT).
            params: Parametros para placeholders.

        Returns:
            DataFrame con los resultados.
        """
        final_sql = self._substitute_params(sql, params)
        data = self._rpc_query(final_sql)
        return pd.DataFrame(data) if data else pd.DataFrame()

    def execute(self, sql: str, params: tuple = ()):
        """
        Ejecuta una sentencia SQL (INSERT, UPDATE, DELETE) via RPC.

        Valida el SQL contra el allowlist antes de enviar al RPC.
        """
        final_sql = self._substitute_params(sql, params)
        self._validate_sql(final_sql)
        self._client.rpc("exec_sql", {"query_text": final_sql}).execute()

    def execute_many(self, sql: str, params_list: list):
        """Ejecuta una sentencia SQL para multiples filas."""
        for params in params_list:
            self.execute(sql, params)

    # ============================================================
    # HELPERS INTERNOS
    # ============================================================

    def _select_all(self, table: str, columns: str = "*",
                    filters: dict = None, order: str = None) -> pd.DataFrame:
        """
        SELECT con paginacion automatica para tablas grandes.

        Usa PostgREST table API (mas eficiente que exec_query para
        consultas simples sin JOINs ni aggregaciones).
        """
        all_data = []
        offset = 0
        while True:
            q = self._client.table(table).select(columns)
            if filters:
                for col, val in filters.items():
                    q = q.eq(col, val)
            if order:
                q = q.order(order)
            resp = q.range(offset, offset + _PAGE_SIZE - 1).execute()
            batch = resp.data or []
            all_data.extend(batch)
            if len(batch) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
        return pd.DataFrame(all_data) if all_data else pd.DataFrame()

    def _batch_upsert(self, table: str, rows: list[dict],
                      on_conflict: str = None):
        """Upsert en batches para evitar limites de PostgREST."""
        for i in range(0, len(rows), _BATCH_SIZE):
            batch = rows[i:i + _BATCH_SIZE]
            if on_conflict:
                self._client.table(table).upsert(
                    batch, on_conflict=on_conflict
                ).execute()
            else:
                self._client.table(table).upsert(batch).execute()

    def _batch_insert(self, table: str, rows: list[dict]):
        """Insert en batches (tolera duplicados)."""
        for i in range(0, len(rows), _BATCH_SIZE):
            batch = rows[i:i + _BATCH_SIZE]
            try:
                self._client.table(table).insert(batch).execute()
            except Exception as e:
                if "duplicate" in str(e).lower() or "23505" in str(e):
                    logger.warning(
                        f"Duplicados en {table} batch {i}: {str(e)[:100]}"
                    )
                else:
                    raise

    # ============================================================
    # TOKENS
    # ============================================================

    def upsert_token(self, token: dict):
        """Inserta o actualiza un token."""
        row = {
            "token_id": token.get("token_id"),
            "chain": token.get("chain"),
            "name": token.get("name"),
            "symbol": token.get("symbol"),
            "pool_address": token.get("pool_address"),
            "dex": token.get("dex"),
            "created_at": token.get("created_at"),
            "total_supply": token.get("total_supply"),
            "decimals": token.get("decimals"),
        }
        # Filtrar None para preservar valores existentes en ON CONFLICT
        row = {k: v for k, v in row.items() if v is not None}
        self._client.table("tokens").upsert(
            row, on_conflict="token_id"
        ).execute()

    def get_all_tokens(self, chain: Optional[str] = None) -> pd.DataFrame:
        """Devuelve todos los tokens, opcionalmente filtrados por cadena."""
        filters = {"chain": chain} if chain else None
        return self._select_all("tokens", filters=filters)

    # ============================================================
    # POOL SNAPSHOTS
    # ============================================================

    def insert_pool_snapshot(self, snapshot: dict):
        """Inserta un snapshot de pool."""
        row = {
            "token_id": snapshot.get("token_id"),
            "chain": snapshot.get("chain"),
            "snapshot_time": snapshot.get("snapshot_time"),
            "price_usd": snapshot.get("price_usd"),
            "volume_24h": snapshot.get("volume_24h"),
            "liquidity_usd": snapshot.get("liquidity_usd"),
            "market_cap": snapshot.get("market_cap"),
            "fdv": snapshot.get("fdv"),
            "buyers_24h": snapshot.get("buyers_24h"),
            "sellers_24h": snapshot.get("sellers_24h"),
            "makers_24h": snapshot.get("makers_24h"),
            "tx_count_24h": snapshot.get("tx_count_24h"),
            "source": snapshot.get("source", "geckoterminal"),
        }
        self._client.table("pool_snapshots").insert(row).execute()

    # ============================================================
    # OHLCV
    # ============================================================

    def insert_ohlcv_batch(self, rows: list[dict]):
        """Inserta multiples filas de OHLCV con validacion."""
        valid_rows = []
        skipped = 0
        for r in rows:
            o, h, l, c = (
                r.get("open"), r.get("high"), r.get("low"), r.get("close")
            )
            if any(v is not None and v < 0 for v in [o, h, l, c]):
                skipped += 1
                continue
            if h is not None and l is not None and h < l:
                skipped += 1
                continue
            if c is not None and c == 0 and o is not None and o > 0:
                skipped += 1
                continue
            valid_rows.append({
                "token_id": r.get("token_id"),
                "chain": r.get("chain"),
                "pool_address": r.get("pool_address"),
                "timeframe": r.get("timeframe"),
                "timestamp": r.get("timestamp"),
                "open": r.get("open"),
                "high": r.get("high"),
                "low": r.get("low"),
                "close": r.get("close"),
                "volume": r.get("volume"),
            })

        if skipped > 0:
            logger.warning(f"OHLCV: {skipped} filas descartadas por validacion")

        # Deduplicar por (pool_address, timeframe, timestamp) para evitar
        # "ON CONFLICT DO UPDATE cannot affect row a second time" en PG
        seen = set()
        deduped = []
        for r in valid_rows:
            key = (r["pool_address"], r["timeframe"], r["timestamp"])
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        if len(deduped) < len(valid_rows):
            logger.warning(
                f"OHLCV: {len(valid_rows) - len(deduped)} duplicados "
                f"eliminados del batch"
            )

        if deduped:
            self._batch_upsert(
                "ohlcv", deduped,
                on_conflict="pool_address,timeframe,timestamp",
            )

    def get_ohlcv(self, token_id: str, timeframe: str = "day") -> pd.DataFrame:
        """Devuelve datos OHLCV para un token."""
        return self._select_all(
            "ohlcv",
            filters={"token_id": token_id, "timeframe": timeframe},
            order="timestamp",
        )

    # ============================================================
    # HOLDER SNAPSHOTS
    # ============================================================

    def insert_holder_snapshot(self, rows: list[dict]):
        """Inserta datos de holders para un token."""
        data = [
            {
                "token_id": r.get("token_id"),
                "chain": r.get("chain"),
                "snapshot_time": r.get("snapshot_time"),
                "rank": r.get("rank"),
                "holder_address": r.get("holder_address"),
                "amount": r.get("amount"),
                "pct_of_supply": r.get("pct_of_supply"),
            }
            for r in rows
        ]
        if data:
            self._batch_insert("holder_snapshots", data)

    # ============================================================
    # CONTRACT INFO
    # ============================================================

    def upsert_contract_info(self, info: dict):
        """Inserta o actualiza informacion de contrato."""
        row = {
            "token_id": info.get("token_id"),
            "chain": info.get("chain"),
            "is_verified": info.get("is_verified"),
            "is_renounced": info.get("is_renounced"),
            "has_mint_authority": info.get("has_mint_authority"),
            "deploy_timestamp": info.get("deploy_timestamp"),
        }
        self._client.table("contract_info").upsert(
            row, on_conflict="token_id"
        ).execute()

    # ============================================================
    # LABELS
    # ============================================================

    def upsert_label(self, label: dict):
        """
        Inserta o actualiza un label para un token.

        Soporta campos nuevos de tier (M2): tier y tier_numeric.
        Los campos None se filtran para no sobreescribir valores existentes
        en un upsert parcial (ej: actualizar solo tier sin borrar label_multi).
        """
        row = {
            "token_id": label.get("token_id"),
            "label_multi": label.get("label_multi"),
            "label_binary": label.get("label_binary"),
            "max_multiple": label.get("max_multiple"),
            "final_multiple": label.get("final_multiple"),
            "return_7d": label.get("return_7d"),
            "notes": label.get("notes"),
            # Campos de tier (M2) — se agregan si existen en el dict
            "tier": label.get("tier"),
            "tier_numeric": label.get("tier_numeric"),
        }
        # Filtrar None para preservar valores existentes en ON CONFLICT
        # (permite upserts parciales: solo tier, o solo label_multi, etc.)
        row = {k: v for k, v in row.items() if v is not None}
        self._client.table("labels").upsert(
            row, on_conflict="token_id"
        ).execute()

    # ============================================================
    # FEATURES (JSONB)
    # ============================================================

    def save_features_df(self, df: pd.DataFrame):
        """
        Guarda un DataFrame de features en la tabla features (JSONB).

        El DataFrame debe tener 'token_id' como indice o columna.
        Cada fila se convierte a un dict JSONB.
        """
        if df.empty:
            logger.warning("save_features_df: DataFrame vacio, nada que guardar")
            return

        # Asegurar que token_id es columna
        if df.index.name == "token_id":
            df = df.reset_index()

        if "token_id" not in df.columns:
            logger.error("save_features_df: DataFrame no tiene columna token_id")
            return

        feature_cols = [c for c in df.columns if c not in ("token_id", "computed_at")]
        rows = []
        for _, row in df.iterrows():
            data = {}
            for col in feature_cols:
                val = row[col]
                if pd.isna(val):
                    data[col] = None
                else:
                    data[col] = (
                        float(val) if isinstance(val, (int, float)) else str(val)
                    )
            rows.append({
                "token_id": row["token_id"],
                "data": data,
            })

        self._batch_upsert("features", rows, on_conflict="token_id")
        logger.info(f"Features guardados en Supabase: {len(rows)} tokens")

    def get_features_df(self) -> pd.DataFrame:
        """
        Devuelve la tabla de features como DataFrame (desempaqueta JSONB).

        Reconstruye el DataFrame con columnas planas desde el JSONB,
        compatible con el formato que espera el resto del pipeline.
        """
        df = self._select_all("features", columns="token_id, data")
        if df.empty:
            return df

        # Desempaquetar JSONB a columnas planas
        features_expanded = pd.json_normalize(df["data"])
        features_expanded.insert(0, "token_id", df["token_id"].values)
        return features_expanded

    # ============================================================
    # API USAGE TRACKING
    # ============================================================

    def log_api_call(
        self,
        api_name: str,
        endpoint: str = None,
        status_code: int = None,
        response_time_ms: int = None,
        error_message: str = None,
    ):
        """Registra una llamada a API para tracking."""
        row = {"api_name": api_name}
        if endpoint is not None:
            row["endpoint"] = endpoint
        if status_code is not None:
            row["status_code"] = status_code
        if response_time_ms is not None:
            row["response_time_ms"] = response_time_ms
        if error_message is not None:
            row["error_message"] = error_message
        self._client.table("api_usage").insert(row).execute()

    def get_api_usage_stats(self, days: int = 30) -> pd.DataFrame:
        """Obtiene estadisticas de uso de APIs en los ultimos N dias."""
        # Validar days: debe ser entero positivo, maximo 365
        days_safe = max(1, min(int(days), 365))
        sql = f"""
            SELECT
                api_name,
                COUNT(*) as total_calls,
                SUM(CASE WHEN status_code >= 200 AND status_code < 300
                    THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate,
                AVG(response_time_ms) as avg_response_time_ms,
                SUM(CASE WHEN status_code = 429
                    THEN 1 ELSE 0 END) as rate_limit_hits
            FROM api_usage
            WHERE timestamp >= NOW() - INTERVAL '{days_safe} days'
            GROUP BY api_name
            ORDER BY COUNT(*) DESC
        """
        data = self._rpc_query(sql)
        return pd.DataFrame(data) if data else pd.DataFrame()

    def get_api_usage_by_day(self, days: int = 30) -> pd.DataFrame:
        """Obtiene uso de APIs agrupado por dia."""
        # Validar days: debe ser entero positivo, maximo 365
        days_safe = max(1, min(int(days), 365))
        sql = f"""
            SELECT
                DATE(timestamp) as date,
                api_name,
                COUNT(*) as calls
            FROM api_usage
            WHERE timestamp >= NOW() - INTERVAL '{days_safe} days'
            GROUP BY DATE(timestamp), api_name
            ORDER BY DATE(timestamp) DESC, api_name
        """
        data = self._rpc_query(sql)
        return pd.DataFrame(data) if data else pd.DataFrame()

    # ============================================================
    # WATCHLIST
    # ============================================================

    def add_to_watchlist(self, token_id: str, chain: str,
                         notes: str = "", user_id: str = None,
                         added_price: float = None):
        """Agrega un token a la watchlist de un usuario.

        Args:
            token_id: Identificador unico del token.
            chain: Blockchain del token (solana, ethereum, base).
            notes: Notas opcionales del usuario.
            user_id: UUID del usuario autenticado.
            added_price: Precio en USD en el momento de agregar el token.
                         Se usa para calcular el % de cambio desde que se agrego.
        """
        row = {"token_id": token_id, "chain": chain, "notes": notes}
        if user_id:
            row["user_id"] = user_id
        if added_price is not None:
            row["added_price"] = float(added_price)
        self._client.table("watchlist").upsert(
            row,
            on_conflict="token_id,user_id",
        ).execute()

    def remove_from_watchlist(self, token_id: str, user_id: str = None):
        """Elimina un token de la watchlist de un usuario."""
        q = self._client.table("watchlist").delete().eq(
            "token_id", token_id
        )
        if user_id:
            q = q.eq("user_id", user_id)
        q.execute()

    def get_watchlist(self, user_id: str = None) -> pd.DataFrame:
        """Devuelve la watchlist con datos del token, filtrada por usuario."""
        user_filter = ""
        if user_id:
            safe_uid = self._format_param(user_id)
            user_filter = f"WHERE w.user_id = {safe_uid}"

        sql = f"""
            SELECT w.token_id, w.chain, w.added_at, w.notes, w.added_price,
                   t.name, t.symbol,
                   ps.price_usd, ps.volume_24h, ps.liquidity_usd,
                   l.label_multi, l.label_binary
            FROM watchlist w
            LEFT JOIN tokens t ON w.token_id = t.token_id
            LEFT JOIN LATERAL (
                SELECT price_usd, volume_24h, liquidity_usd
                FROM pool_snapshots
                WHERE token_id = w.token_id
                ORDER BY snapshot_time DESC
                LIMIT 1
            ) ps ON true
            LEFT JOIN labels l ON w.token_id = l.token_id
            {user_filter}
            ORDER BY w.added_at DESC
        """
        data = self._rpc_query(sql)
        return pd.DataFrame(data) if data else pd.DataFrame()

    def is_in_watchlist(self, token_id: str, user_id: str = None) -> bool:
        """Verifica si un token esta en la watchlist de un usuario."""
        q = (
            self._client.table("watchlist")
            .select("token_id")
            .eq("token_id", token_id)
        )
        if user_id:
            q = q.eq("user_id", user_id)
        resp = q.execute()
        return len(resp.data or []) > 0

    # ============================================================
    # MODEL VERSIONS (nueva tabla)
    # ============================================================

    def save_model_version(self, version: str, metrics: dict = None,
                           model_url: str = None, features_used: list = None,
                           samples_count: int = None, notes: str = None):
        """Registra una version de modelo entrenado."""
        row = {
            "version": version,
            "metrics": metrics or {},
            "model_url": model_url,
            "features_used": features_used or [],
            "samples_count": samples_count,
            "notes": notes,
        }
        self._client.table("model_versions").upsert(
            row, on_conflict="version"
        ).execute()

    def get_latest_model_version(self) -> Optional[dict]:
        """Devuelve la version mas reciente del modelo."""
        resp = (
            self._client.table("model_versions")
            .select("*")
            .order("trained_at", desc=True)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        return resp.data[0]

    # ============================================================
    # SCORES (predicciones ML)
    # ============================================================

    def upsert_scores(self, scores: list[dict]):
        """
        Inserta o actualiza scores de prediccion ML en la tabla scores.

        Cada dict debe contener: token_id, probability, signal, prediction,
        model_name, model_version. scored_at se asigna automaticamente
        si no se proporciona (DEFAULT NOW() en Supabase).

        Usa ON CONFLICT (token_id) para idempotencia: si ya existe un
        score para ese token, se actualiza con los nuevos valores.

        Args:
            scores: Lista de dicts con los scores a insertar/actualizar.
                Campos requeridos: token_id, probability, signal, prediction,
                model_name, model_version.
                Campo opcional: scored_at (TIMESTAMPTZ, default NOW()).

        Ejemplo:
            storage.upsert_scores([{
                "token_id": "abc123",
                "probability": 0.85,
                "signal": "STRONG",
                "prediction": 1,
                "model_name": "random_forest",
                "model_version": "v12",
            }])
        """
        if not scores:
            logger.warning("upsert_scores: lista vacia, nada que guardar")
            return

        # Validar y normalizar cada score antes de insertar
        valid_rows = []
        for s in scores:
            if not s.get("token_id"):
                logger.warning("upsert_scores: score sin token_id, saltando")
                continue

            row = {
                "token_id": s["token_id"],
                "probability": float(s.get("probability", 0.0)),
                "signal": s.get("signal", "NONE"),
                "prediction": int(s.get("prediction", 0)),
                "model_name": s.get("model_name", "random_forest"),
                "model_version": s.get("model_version", "unknown"),
            }
            # scored_at es opcional — si no se pasa, Supabase usa DEFAULT NOW()
            if s.get("scored_at"):
                row["scored_at"] = s["scored_at"]

            valid_rows.append(row)

        if not valid_rows:
            logger.warning("upsert_scores: ningun score valido")
            return

        # Usar _batch_upsert con on_conflict="token_id" (PK de la tabla)
        self._batch_upsert("scores", valid_rows, on_conflict="token_id")
        logger.info(f"Scores upserted en Supabase: {len(valid_rows)} tokens")

    def get_scores(self, min_probability: float = 0.0,
                   scored_today: bool = False) -> pd.DataFrame:
        """
        Obtiene scores de la tabla scores con filtros opcionales.

        Args:
            min_probability: Probabilidad minima para filtrar (default 0.0 = todos).
            scored_today: Si True, solo devuelve scores de hoy.

        Returns:
            DataFrame con scores + datos del token (JOIN con tokens).
        """
        # Validar que min_probability es un numero finito
        prob = float(min_probability)
        if math.isnan(prob) or math.isinf(prob):
            prob = 0.0

        sql = """
            SELECT s.*, t.name, t.symbol, t.chain, t.pool_address,
                   ps.market_cap, ps.fdv, ps.price_usd
            FROM scores s
            JOIN tokens t ON s.token_id = t.token_id
            LEFT JOIN LATERAL (
                SELECT market_cap, fdv, price_usd
                FROM pool_snapshots
                WHERE token_id = s.token_id
                ORDER BY snapshot_time DESC
                LIMIT 1
            ) ps ON true
            WHERE s.probability >= ?
        """

        if scored_today:
            sql += " AND s.scored_at::date = CURRENT_DATE"

        sql += " ORDER BY s.probability DESC"

        return self.query(sql, (prob,))

    # ============================================================
    # DRIFT REPORTS
    # ============================================================

    def save_drift_report(self, report: dict):
        """
        Guarda un reporte de drift detection en la tabla drift_reports.

        Args:
            report: Dict con los resultados del drift check.
                Campos requeridos: model_version.
                Campos opcionales: needs_retraining, reasons,
                time_drift_days, time_drift_triggered,
                volume_drift_new_labels, volume_drift_triggered,
                feature_drift_count, feature_drift_total,
                feature_drift_triggered, feature_drift_details,
                overall_score, report_json.

        Ejemplo:
            storage.save_drift_report({
                "model_version": "v12",
                "needs_retraining": True,
                "reasons": ["time_drift", "feature_drift"],
                "overall_score": 0.75,
                "time_drift_days": 45,
                "time_drift_triggered": True,
            })
        """
        if not report.get("model_version"):
            logger.error("save_drift_report: model_version es requerido")
            return

        row = {
            "model_version": report["model_version"],
            "needs_retraining": report.get("needs_retraining", False),
            "reasons": report.get("reasons", []),
            "time_drift_days": report.get("time_drift_days"),
            "time_drift_triggered": report.get("time_drift_triggered", False),
            "volume_drift_new_labels": report.get("volume_drift_new_labels"),
            "volume_drift_triggered": report.get("volume_drift_triggered", False),
            "feature_drift_count": report.get("feature_drift_count", 0),
            "feature_drift_total": report.get("feature_drift_total", 0),
            "feature_drift_triggered": report.get("feature_drift_triggered", False),
            "feature_drift_details": report.get("feature_drift_details", {}),
            "overall_score": report.get("overall_score", 0.0),
            "report_json": report.get("report_json", {}),
        }

        # Filtrar None para que Supabase use los DEFAULT de la tabla
        row = {k: v for k, v in row.items() if v is not None}

        try:
            self._client.table("drift_reports").insert(row).execute()
            logger.info(
                f"Drift report guardado: {report['model_version']} "
                f"(needs_retraining={report.get('needs_retraining', False)})"
            )
        except Exception as e:
            logger.error(f"Error guardando drift report: {e}")
            raise

    def get_drift_reports(self, model_version: str = None,
                          limit: int = 50) -> pd.DataFrame:
        """
        Obtiene reportes de drift, opcionalmente filtrados por version.

        Args:
            model_version: Filtrar por version de modelo (opcional).
            limit: Numero maximo de reportes a devolver (default 50).

        Returns:
            DataFrame con los reportes ordenados por checked_at DESC.
        """
        q = (
            self._client.table("drift_reports")
            .select("*")
            .order("checked_at", desc=True)
            .limit(limit)
        )
        if model_version:
            q = q.eq("model_version", model_version)

        resp = q.execute()
        data = resp.data or []
        return pd.DataFrame(data) if data else pd.DataFrame()

    # ============================================================
    # ALERT PREFERENCES
    # ============================================================

    def get_alert_preferences(self, user_id: str) -> Optional[dict]:
        """
        Obtiene las preferencias de alerta de un usuario.

        Args:
            user_id: UUID del usuario en auth.users.

        Returns:
            Dict con las preferencias o None si no existen.
        """
        try:
            resp = (
                self._client.table("alert_preferences")
                .select("*")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            data = resp.data or []
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Error obteniendo alert_preferences para {user_id}: {e}")
            return None

    def upsert_alert_preferences(self, user_id: str, preferences: dict) -> bool:
        """
        Crea o actualiza las preferencias de alerta de un usuario.

        Args:
            user_id: UUID del usuario en auth.users.
            preferences: Dict con claves opcionales:
                - telegram_chat_id (str)
                - min_signal (str): 'STRONG', 'MEDIUM' o 'WEAK'
                - chains (list): lista de cadenas, e.g. ["solana", "ethereum"]
                - min_probability (float): threshold de score, e.g. 0.6
                - enabled (bool): si las alertas estan activas
                - quiet_hours_start (int): hora de inicio de silencio (0-23)
                - quiet_hours_end (int): hora de fin de silencio (0-23)

        Returns:
            True si se guardo correctamente, False en caso de error.
        """
        try:
            row = {"user_id": user_id, "updated_at": "now()"}

            allowed_keys = {
                "telegram_chat_id", "min_signal", "chains",
                "min_probability", "enabled",
                "quiet_hours_start", "quiet_hours_end",
            }
            for key in allowed_keys:
                if key in preferences:
                    val = preferences[key]
                    # Serializar listas a JSON para columna jsonb
                    if key == "chains" and isinstance(val, list):
                        import json as _json
                        val = _json.dumps([c.lower() for c in val])
                    row[key] = val

            self._client.table("alert_preferences").upsert(
                row, on_conflict="user_id"
            ).execute()
            logger.info(f"alert_preferences guardadas para user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error guardando alert_preferences para {user_id}: {e}")
            return False

    # ============================================================
    # PORTFOLIO DE USUARIO
    # ============================================================

    def get_portfolio(self, user_id: str) -> pd.DataFrame:
        """
        Devuelve todas las posiciones abiertas del portfolio de un usuario.

        Args:
            user_id: UUID del usuario autenticado.

        Returns:
            DataFrame con las posiciones abiertas ordenadas por fecha de creacion.
        """
        resp = (
            self._client.table("user_portfolio")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "open")
            .order("created_at", desc=False)
            .execute()
        )
        data = resp.data or []
        return pd.DataFrame(data) if data else pd.DataFrame()

    def add_portfolio_position(
        self,
        user_id: str,
        token_id: str,
        symbol: str,
        name: str,
        chain: str,
        entry_price: float,
        quantity: float,
        notes: str = "",
    ) -> dict:
        """
        Agrega una nueva posicion al portfolio del usuario.

        Args:
            user_id: UUID del usuario autenticado.
            token_id: Direccion del contrato del token.
            symbol: Simbolo del token (ej: SOL).
            name: Nombre del token.
            chain: Blockchain (solana, ethereum, base).
            entry_price: Precio de entrada en USD.
            quantity: Cantidad de tokens comprados.
            notes: Notas opcionales del usuario.

        Returns:
            Dict con la posicion creada (incluye id generado).
        """
        row = {
            "user_id": user_id,
            "token_id": token_id,
            "token_symbol": symbol or "",
            "token_name": name or "",
            "chain": chain or "",
            "entry_price": float(entry_price),
            "quantity": float(quantity),
            "notes": notes or "",
            "status": "open",
        }
        resp = self._client.table("user_portfolio").insert(row).execute()
        return resp.data[0] if resp.data else {}

    def close_portfolio_position(
        self,
        position_id: str,
        user_id: str,
        closed_price: float,
    ):
        """
        Cierra una posicion del portfolio (status -> 'closed').

        Args:
            position_id: UUID de la posicion a cerrar.
            user_id: UUID del usuario (para verificar propiedad).
            closed_price: Precio de cierre en USD.
        """
        self._client.table("user_portfolio").update({
            "status": "closed",
            "closed_price": float(closed_price),
            "closed_at": "now()",
            "updated_at": "now()",
        }).eq("id", position_id).eq("user_id", user_id).execute()

    def delete_portfolio_position(self, position_id: str, user_id: str):
        """
        Elimina permanentemente una posicion del portfolio.

        Args:
            position_id: UUID de la posicion a eliminar.
            user_id: UUID del usuario (para verificar propiedad).
        """
        self._client.table("user_portfolio").delete().eq(
            "id", position_id
        ).eq("user_id", user_id).execute()

    # ============================================================
    # ESTADISTICAS
    # ============================================================

    def stats(self) -> dict:
        """Devuelve conteos de cada tabla."""
        tables = [
            "tokens", "pool_snapshots", "ohlcv",
            "holder_snapshots", "contract_info", "labels", "features",
            "scores", "drift_reports",
        ]
        counts = {}
        for table in tables:
            try:
                resp = (
                    self._client.table(table)
                    .select("*", count="exact", head=True)
                    .execute()
                )
                counts[table] = resp.count or 0
            except Exception as e:
                logger.warning(f"Error consultando tabla '{table}': {e}")
                counts[table] = 0
        return counts


# ============================================================
# FACTORY: Obtener el storage adecuado segun configuracion
# ============================================================

def get_storage():
    """
    Factory que devuelve Storage (SQLite) o SupabaseStorage segun config.

    Lee STORAGE_BACKEND de config.py / .env:
    - "sqlite" (default): retorna Storage() local
    - "supabase": retorna SupabaseStorage() cloud

    Ejemplo:
        from src.data.supabase_storage import get_storage
        storage = get_storage()
        storage.upsert_token({...})  # Funciona igual con ambos backends
    """
    try:
        from config import STORAGE_BACKEND
    except ImportError:
        import os
        STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "sqlite")

    if STORAGE_BACKEND == "supabase":
        logger.info("Usando SupabaseStorage (cloud)")
        return SupabaseStorage()
    else:
        from src.data.storage import Storage
        logger.info("Usando Storage (SQLite local)")
        return Storage()
