"""
storage.py - Almacenamiento en SQLite para datos de tokens.

SQLite es una base de datos que vive en un solo archivo (.db).
No necesita servidor, es rapida para nuestro volumen de datos,
y Python la soporta nativamente.

Tablas:
    - tokens: Informacion basica de cada token
    - pool_snapshots: Snapshots periodicos de cada pool (precio, vol, liq)
    - ohlcv: Datos OHLCV (Open, High, Low, Close, Volume)
    - holder_snapshots: Top holders en cada momento
    - contract_info: Datos de contrato (verificacion, ownership)
    - labels: Clasificacion de cada token (gem, failure, etc.)
    - features: Matriz de features calculados
"""

import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

import pandas as pd

from src.utils.logger import get_logger

try:
    from config import DB_PATH
except ImportError:
    DB_PATH = Path("data/trading_memes.db")

logger = get_logger(__name__)

# ============================================================
# Schema SQL - Definicion de todas las tablas
# ============================================================
SCHEMA_SQL = """
-- Tabla principal: un registro por token
CREATE TABLE IF NOT EXISTS tokens (
    token_id        TEXT PRIMARY KEY,           -- contract address
    chain           TEXT NOT NULL,              -- solana, ethereum, base
    name            TEXT,
    symbol          TEXT,
    pool_address    TEXT,                       -- pool principal (el de mayor liq)
    dex             TEXT,                       -- raydium, uniswap, etc.
    created_at      TEXT,                       -- timestamp ISO del primer trade
    first_seen      TEXT DEFAULT CURRENT_TIMESTAMP,  -- cuando lo descubrimos
    total_supply    REAL,
    decimals        INTEGER,
    UNIQUE(token_id, chain)
);

-- Snapshots periodicos de cada pool
CREATE TABLE IF NOT EXISTS pool_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id        TEXT NOT NULL,
    chain           TEXT NOT NULL,
    snapshot_time   TEXT NOT NULL,              -- timestamp ISO
    price_usd       REAL,
    volume_24h      REAL,
    liquidity_usd   REAL,
    market_cap      REAL,
    fdv             REAL,
    buyers_24h      INTEGER,
    sellers_24h     INTEGER,
    makers_24h      INTEGER,
    tx_count_24h    INTEGER,
    source          TEXT DEFAULT 'geckoterminal',
    FOREIGN KEY (token_id) REFERENCES tokens(token_id)
);

-- Datos OHLCV (velas de precio)
CREATE TABLE IF NOT EXISTS ohlcv (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id        TEXT NOT NULL,
    chain           TEXT NOT NULL,
    pool_address    TEXT NOT NULL,
    timeframe       TEXT NOT NULL,              -- 'day', 'hour', 'minute'
    timestamp       TEXT NOT NULL,              -- timestamp ISO de la vela
    open            REAL,
    high            REAL,
    low             REAL,
    close           REAL,
    volume          REAL,
    FOREIGN KEY (token_id) REFERENCES tokens(token_id),
    UNIQUE(pool_address, timeframe, timestamp)
);

-- Snapshots de holders (solo Solana por ahora)
CREATE TABLE IF NOT EXISTS holder_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id        TEXT NOT NULL,
    chain           TEXT NOT NULL,
    snapshot_time   TEXT NOT NULL,
    rank            INTEGER NOT NULL,           -- 1 = holder mas grande
    holder_address  TEXT,
    amount          REAL,
    pct_of_supply   REAL,                       -- porcentaje del supply total
    FOREIGN KEY (token_id) REFERENCES tokens(token_id)
);

-- Informacion de contrato
CREATE TABLE IF NOT EXISTS contract_info (
    token_id        TEXT PRIMARY KEY,
    chain           TEXT NOT NULL,
    is_verified     BOOLEAN,                    -- source code verificado
    is_renounced    BOOLEAN,                    -- ownership renunciado
    has_mint_authority BOOLEAN,                 -- puede crear mas tokens
    deploy_timestamp TEXT,                      -- cuando se desplego
    checked_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (token_id) REFERENCES tokens(token_id)
);

-- Labels (clasificacion)
CREATE TABLE IF NOT EXISTS labels (
    token_id        TEXT PRIMARY KEY,
    label_multi     TEXT,                       -- gem, moderate_success, neutral, failure, rug, pump_and_dump
    label_binary    INTEGER,                    -- 1=success, 0=failure
    max_multiple    REAL,                       -- maximo multiple alcanzado
    final_multiple  REAL,                       -- multiple al dia 30
    return_7d       REAL,                       -- close_day7 / close_day1
    tier            TEXT,                       -- mega_gem, standard_gem, mini_gem, micro_gem, neutral, failure, rug
    tier_numeric    INTEGER,                    -- 6=mega_gem, 5=standard, 4=mini, 3=micro, 2=neutral, 1=failure, 0=rug
    labeled_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    notes           TEXT,
    FOREIGN KEY (token_id) REFERENCES tokens(token_id)
);

-- Features calculados (1 fila por token)
CREATE TABLE IF NOT EXISTS features (
    token_id        TEXT PRIMARY KEY,
    -- Se agregan columnas dinamicamente segun los features calculados
    computed_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (token_id) REFERENCES tokens(token_id)
);

-- API Usage tracking (para monitorear rate limits)
CREATE TABLE IF NOT EXISTS api_usage (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT DEFAULT CURRENT_TIMESTAMP,
    api_name        TEXT NOT NULL,              -- geckoterminal, dexscreener, helius, etherscan, coingecko
    endpoint        TEXT,                       -- /pools, /tokens, etc.
    status_code     INTEGER,                    -- 200, 404, 429, etc.
    response_time_ms INTEGER,                   -- tiempo de respuesta en ms
    error_message   TEXT                        -- mensaje de error si fallo
);

-- Watchlist: tokens que el usuario quiere monitorear
CREATE TABLE IF NOT EXISTS watchlist (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id        TEXT NOT NULL,
    chain           TEXT NOT NULL,
    added_at        TEXT DEFAULT CURRENT_TIMESTAMP,
    notes           TEXT,
    FOREIGN KEY (token_id) REFERENCES tokens(token_id),
    UNIQUE(token_id)
);

-- Indices para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_tokens_chain ON tokens(chain);
CREATE INDEX IF NOT EXISTS idx_pool_snapshots_token ON pool_snapshots(token_id);
CREATE INDEX IF NOT EXISTS idx_pool_snapshots_time ON pool_snapshots(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_ohlcv_pool ON ohlcv(pool_address, timeframe);
CREATE INDEX IF NOT EXISTS idx_ohlcv_token ON ohlcv(token_id, timeframe);
CREATE INDEX IF NOT EXISTS idx_holders_token ON holder_snapshots(token_id);
CREATE INDEX IF NOT EXISTS idx_labels_multi ON labels(label_multi);
CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp);
CREATE INDEX IF NOT EXISTS idx_api_usage_api_name ON api_usage(api_name);
CREATE INDEX IF NOT EXISTS idx_ohlcv_token_timeframe_ts ON ohlcv(token_id, timeframe, timestamp);
"""


class Storage:
    """
    Interfaz para la base de datos SQLite del proyecto.

    Maneja la creacion de tablas, insercion y consulta de datos.
    Usa context managers para manejar conexiones de forma segura.

    Args:
        db_path: Ruta al archivo .db (por defecto usa config.DB_PATH).

    Ejemplo:
        storage = Storage()

        # Insertar un token
        storage.upsert_token({
            "token_id": "abc123...",
            "chain": "solana",
            "name": "MiToken",
            "symbol": "MT",
        })

        # Consultar tokens de Solana
        df = storage.query("SELECT * FROM tokens WHERE chain = 'solana'")
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or DB_PATH)
        self._init_db()
        logger.info(f"Storage inicializado: {self.db_path}")

    def _init_db(self):
        """Crea las tablas si no existen y activa WAL mode."""
        with self._connect() as conn:
            # WAL mode permite lecturas concurrentes mientras se escribe
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA_SQL)
            # Migracion: agregar columnas tier si no existen en tablas antiguas
            self._migrate_labels_tier(conn)

    def _migrate_labels_tier(self, conn):
        """Agrega columnas tier y tier_numeric a labels si no existen (M2)."""
        try:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(labels)").fetchall()]
            if "tier" not in cols:
                conn.execute("ALTER TABLE labels ADD COLUMN tier TEXT")
                logger.info("Migracion: columna 'tier' agregada a labels")
            if "tier_numeric" not in cols:
                conn.execute("ALTER TABLE labels ADD COLUMN tier_numeric INTEGER")
                logger.info("Migracion: columna 'tier_numeric' agregada a labels")
        except Exception as e:
            logger.debug(f"Migracion tier ya aplicada o error menor: {e}")

    @contextmanager
    def _connect(self):
        """
        Context manager para conexiones SQLite.

        Uso:
            with self._connect() as conn:
                conn.execute("INSERT INTO ...")
            # Se hace commit automatico, o rollback si hay error
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Permite acceder columnas por nombre
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ============================================================
    # OPERACIONES GENERICAS
    # ============================================================

    def query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        """
        Ejecuta una consulta SQL y devuelve un DataFrame.

        Args:
            sql: Consulta SQL (SELECT).
            params: Parametros para placeholders (?).

        Returns:
            DataFrame con los resultados.

        Ejemplo:
            df = storage.query(
                "SELECT * FROM tokens WHERE chain = ?",
                ("solana",)
            )
        """
        with self._connect() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def execute(self, sql: str, params: tuple = ()):
        """Ejecuta una sentencia SQL (INSERT, UPDATE, DELETE)."""
        with self._connect() as conn:
            conn.execute(sql, params)

    def execute_many(self, sql: str, params_list: list):
        """Ejecuta una sentencia SQL para multiples filas."""
        with self._connect() as conn:
            conn.executemany(sql, params_list)

    # ============================================================
    # TOKENS
    # ============================================================

    def upsert_token(self, token: dict):
        """
        Inserta o actualiza un token.

        Args:
            token: Dict con al menos 'token_id' y 'chain'.
        """
        sql = """
            INSERT INTO tokens (token_id, chain, name, symbol, pool_address,
                                dex, created_at, total_supply, decimals)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(token_id) DO UPDATE SET
                name = COALESCE(excluded.name, tokens.name),
                symbol = COALESCE(excluded.symbol, tokens.symbol),
                pool_address = COALESCE(excluded.pool_address, tokens.pool_address),
                dex = COALESCE(excluded.dex, tokens.dex),
                created_at = COALESCE(excluded.created_at, tokens.created_at),
                total_supply = COALESCE(excluded.total_supply, tokens.total_supply),
                decimals = COALESCE(excluded.decimals, tokens.decimals)
        """
        self.execute(sql, (
            token.get("token_id"),
            token.get("chain"),
            token.get("name"),
            token.get("symbol"),
            token.get("pool_address"),
            token.get("dex"),
            token.get("created_at"),
            token.get("total_supply"),
            token.get("decimals"),
        ))

    def get_all_tokens(self, chain: Optional[str] = None) -> pd.DataFrame:
        """Devuelve todos los tokens, opcionalmente filtrados por cadena."""
        if chain:
            return self.query("SELECT * FROM tokens WHERE chain = ?", (chain,))
        return self.query("SELECT * FROM tokens")

    # ============================================================
    # POOL SNAPSHOTS
    # ============================================================

    def insert_pool_snapshot(self, snapshot: dict):
        """Inserta un snapshot de pool."""
        sql = """
            INSERT INTO pool_snapshots
                (token_id, chain, snapshot_time, price_usd, volume_24h,
                 liquidity_usd, market_cap, fdv, buyers_24h, sellers_24h,
                 makers_24h, tx_count_24h, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.execute(sql, (
            snapshot.get("token_id"),
            snapshot.get("chain"),
            snapshot.get("snapshot_time"),
            snapshot.get("price_usd"),
            snapshot.get("volume_24h"),
            snapshot.get("liquidity_usd"),
            snapshot.get("market_cap"),
            snapshot.get("fdv"),
            snapshot.get("buyers_24h"),
            snapshot.get("sellers_24h"),
            snapshot.get("makers_24h"),
            snapshot.get("tx_count_24h"),
            snapshot.get("source", "geckoterminal"),
        ))

    # ============================================================
    # OHLCV
    # ============================================================

    def insert_ohlcv_batch(self, rows: list[dict]):
        """
        Inserta multiples filas de OHLCV de una vez, con validacion.

        Descarta filas con precios negativos, high < low, o close = 0.

        Args:
            rows: Lista de dicts con keys: token_id, chain, pool_address,
                  timeframe, timestamp, open, high, low, close, volume.
        """
        sql = """
            INSERT OR IGNORE INTO ohlcv
                (token_id, chain, pool_address, timeframe, timestamp,
                 open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        valid_rows = []
        skipped = 0
        for r in rows:
            o, h, l, c = r.get("open"), r.get("high"), r.get("low"), r.get("close")
            # Validar: precios deben ser positivos, high >= low, close != 0
            if any(v is not None and v < 0 for v in [o, h, l, c]):
                skipped += 1
                continue
            if h is not None and l is not None and h < l:
                skipped += 1
                continue
            if c is not None and c == 0 and o is not None and o > 0:
                skipped += 1
                continue
            valid_rows.append(r)

        if skipped > 0:
            logger.warning(f"OHLCV: {skipped} filas descartadas por validacion")

        params = [
            (
                r.get("token_id"), r.get("chain"), r.get("pool_address"),
                r.get("timeframe"), r.get("timestamp"),
                r.get("open"), r.get("high"), r.get("low"),
                r.get("close"), r.get("volume"),
            )
            for r in valid_rows
        ]
        self.execute_many(sql, params)

    def get_ohlcv(
        self,
        token_id: str,
        timeframe: str = "day",
    ) -> pd.DataFrame:
        """Devuelve datos OHLCV para un token."""
        return self.query(
            """SELECT * FROM ohlcv
               WHERE token_id = ? AND timeframe = ?
               ORDER BY timestamp""",
            (token_id, timeframe),
        )

    # ============================================================
    # HOLDER SNAPSHOTS
    # ============================================================

    def insert_holder_snapshot(self, rows: list[dict]):
        """Inserta datos de holders para un token."""
        sql = """
            INSERT INTO holder_snapshots
                (token_id, chain, snapshot_time, rank, holder_address,
                 amount, pct_of_supply)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = [
            (
                r.get("token_id"), r.get("chain"), r.get("snapshot_time"),
                r.get("rank"), r.get("holder_address"),
                r.get("amount"), r.get("pct_of_supply"),
            )
            for r in rows
        ]
        self.execute_many(sql, params)

    # ============================================================
    # CONTRACT INFO
    # ============================================================

    def upsert_contract_info(self, info: dict):
        """Inserta o actualiza informacion de contrato."""
        sql = """
            INSERT INTO contract_info
                (token_id, chain, is_verified, is_renounced,
                 has_mint_authority, deploy_timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(token_id) DO UPDATE SET
                is_verified = excluded.is_verified,
                is_renounced = excluded.is_renounced,
                has_mint_authority = excluded.has_mint_authority,
                deploy_timestamp = excluded.deploy_timestamp,
                checked_at = CURRENT_TIMESTAMP
        """
        self.execute(sql, (
            info.get("token_id"),
            info.get("chain"),
            info.get("is_verified"),
            info.get("is_renounced"),
            info.get("has_mint_authority"),
            info.get("deploy_timestamp"),
        ))

    # ============================================================
    # LABELS
    # ============================================================

    def upsert_label(self, label: dict):
        """
        Inserta o actualiza un label para un token.

        Soporta campos nuevos de tier (M2): tier y tier_numeric.
        Usa COALESCE para no sobreescribir campos existentes con NULL
        en upserts parciales (ej: actualizar solo tier sin borrar label_multi).
        """
        sql = """
            INSERT INTO labels
                (token_id, label_multi, label_binary, max_multiple,
                 final_multiple, return_7d, notes, tier, tier_numeric)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(token_id) DO UPDATE SET
                label_multi = COALESCE(excluded.label_multi, labels.label_multi),
                label_binary = COALESCE(excluded.label_binary, labels.label_binary),
                max_multiple = COALESCE(excluded.max_multiple, labels.max_multiple),
                final_multiple = COALESCE(excluded.final_multiple, labels.final_multiple),
                return_7d = COALESCE(excluded.return_7d, labels.return_7d),
                notes = COALESCE(excluded.notes, labels.notes),
                tier = COALESCE(excluded.tier, labels.tier),
                tier_numeric = COALESCE(excluded.tier_numeric, labels.tier_numeric),
                labeled_at = CURRENT_TIMESTAMP
        """
        self.execute(sql, (
            label.get("token_id"),
            label.get("label_multi"),
            label.get("label_binary"),
            label.get("max_multiple"),
            label.get("final_multiple"),
            label.get("return_7d"),
            label.get("notes"),
            label.get("tier"),
            label.get("tier_numeric"),
        ))

    # ============================================================
    # FEATURES
    # ============================================================

    def save_features_df(self, df: pd.DataFrame):
        """
        Guarda un DataFrame de features en la tabla features.

        El DataFrame debe tener 'token_id' como indice o columna.
        Se reemplaza la tabla completa cada vez.
        """
        with self._connect() as conn:
            df.to_sql("features", conn, if_exists="replace", index=True)
        logger.info(f"Features guardados: {len(df)} tokens")

    def get_features_df(self) -> pd.DataFrame:
        """Devuelve la tabla de features como DataFrame."""
        return self.query("SELECT * FROM features")

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
        """
        Registra una llamada a API para tracking de rate limits.

        Args:
            api_name: Nombre de la API (geckoterminal, dexscreener, etc.)
            endpoint: Endpoint llamado (/pools, /tokens, etc.)
            status_code: Codigo HTTP de respuesta (200, 404, 429, etc.)
            response_time_ms: Tiempo de respuesta en milisegundos
            error_message: Mensaje de error si fallo
        """
        sql = """
            INSERT INTO api_usage
                (api_name, endpoint, status_code, response_time_ms, error_message)
            VALUES (?, ?, ?, ?, ?)
        """
        self.execute(sql, (api_name, endpoint, status_code, response_time_ms, error_message))

    def get_api_usage_stats(self, days: int = 30) -> pd.DataFrame:
        """
        Obtiene estadisticas de uso de APIs en los ultimos N dias.

        Args:
            days: Numero de dias a consultar (default: 30)

        Returns:
            DataFrame con columnas: api_name, total_calls, success_rate, avg_response_time_ms
        """
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        sql = """
            SELECT
                api_name,
                COUNT(*) as total_calls,
                SUM(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate,
                AVG(response_time_ms) as avg_response_time_ms,
                SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) as rate_limit_hits
            FROM api_usage
            WHERE timestamp >= ?
            GROUP BY api_name
            ORDER BY total_calls DESC
        """
        return self.query(sql, (cutoff_str,))

    def get_api_usage_by_day(self, days: int = 30) -> pd.DataFrame:
        """
        Obtiene uso de APIs agrupado por dia.

        Args:
            days: Numero de dias a consultar (default: 30)

        Returns:
            DataFrame con columnas: date, api_name, calls
        """
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        sql = """
            SELECT
                DATE(timestamp) as date,
                api_name,
                COUNT(*) as calls
            FROM api_usage
            WHERE timestamp >= ?
            GROUP BY DATE(timestamp), api_name
            ORDER BY date DESC, api_name
        """
        return self.query(sql, (cutoff_str,))

    # ============================================================
    # WATCHLIST
    # ============================================================

    def add_to_watchlist(self, token_id: str, chain: str, notes: str = ""):
        """Agrega un token a la watchlist."""
        sql = """
            INSERT OR IGNORE INTO watchlist (token_id, chain, notes)
            VALUES (?, ?, ?)
        """
        self.execute(sql, (token_id, chain, notes))

    def remove_from_watchlist(self, token_id: str):
        """Elimina un token de la watchlist."""
        self.execute("DELETE FROM watchlist WHERE token_id = ?", (token_id,))

    def get_watchlist(self) -> pd.DataFrame:
        """Devuelve la watchlist con datos del token."""
        return self.query("""
            SELECT w.token_id, w.chain, w.added_at, w.notes,
                   t.name, t.symbol,
                   ps.price_usd, ps.volume_24h, ps.liquidity_usd,
                   l.label_multi, l.label_binary
            FROM watchlist w
            LEFT JOIN tokens t ON w.token_id = t.token_id
            LEFT JOIN (
                SELECT token_id, price_usd, volume_24h, liquidity_usd,
                       ROW_NUMBER() OVER (PARTITION BY token_id ORDER BY snapshot_time DESC) as rn
                FROM pool_snapshots
            ) ps ON w.token_id = ps.token_id AND ps.rn = 1
            LEFT JOIN labels l ON w.token_id = l.token_id
            ORDER BY w.added_at DESC
        """)

    def is_in_watchlist(self, token_id: str) -> bool:
        """Verifica si un token esta en la watchlist."""
        df = self.query(
            "SELECT 1 FROM watchlist WHERE token_id = ?",
            (token_id,)
        )
        return not df.empty

    # ============================================================
    # ESTADISTICAS
    # ============================================================

    def stats(self) -> dict:
        """Devuelve conteos de cada tabla."""
        tables = [
            "tokens", "pool_snapshots", "ohlcv",
            "holder_snapshots", "contract_info", "labels", "features",
        ]
        counts = {}
        for table in tables:
            try:
                df = self.query(f"SELECT COUNT(*) as n FROM {table}")
                counts[table] = int(df["n"].iloc[0])
            except Exception as e:
                error_msg = str(e)
                if "no such table" in error_msg:
                    # Tabla no existe todavia, es normal (count=0)
                    counts[table] = 0
                else:
                    # Error real de SQLite (permisos, corrupcion, etc.)
                    logger.warning(f"Error consultando tabla '{table}': {e}")
                    counts[table] = 0
        return counts
