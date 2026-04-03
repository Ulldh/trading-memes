"""
config.py - Configuracion central del proyecto Memecoin Gem Detector.

Aqui se definen:
- API keys (cargadas desde .env)
- Rate limits por API
- Umbrales para clasificacion de tokens
- Rutas de archivos
- Parametros de features y modelos
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# ============================================================
# RUTAS DEL PROYECTO
# ============================================================
# Path.resolve() convierte la ruta relativa a absoluta
PROJECT_ROOT = Path(__file__).parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = DATA_DIR / "models"
DB_PATH = DATA_DIR / "trading_memes.db"
CACHE_DIR = PROJECT_ROOT / ".cache"

# Crear directorios si no existen
for d in [RAW_DIR, PROCESSED_DIR, MODELS_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================
# API KEYS
# ============================================================
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
BASESCAN_API_KEY = os.getenv("BASESCAN_API_KEY", "")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")

# ============================================================
# RATE LIMITS (calls por minuto)
# ============================================================
RATE_LIMITS = {
    "geckoterminal": 30,    # 30 calls/min, sin limite mensual documentado
    "coingecko": 30,        # 30 calls/min, 10K calls/mes (demo)
    "dexscreener": 300,     # 300 calls/min, sin limite mensual
    "helius": 1000,         # Free tier: 50 rps = 3000/min. Usamos 1000 (headroom)
    "etherscan": 5 * 60,    # 5 calls/seg = 300/min
    "basescan": 5 * 60,     # Mismo que Etherscan
    "twitter": 30,          # 450 calls/15min = ~30/min (Basic tier)
    "pumpfun": 30,          # API no oficial, conservador
    "birdeye": 900,         # Lite tier ($39/m): 15 rps = 900/min
    "jupiter": 60,          # JSON estatico, sin rate limit documentado
    "raydium": 60,          # JSON estatico, sin rate limit documentado
    "goplus": 60,           # ~100 req/min fair use, conservador a 60
    "rugcheck": 60,         # ~60 req/min fair use
}

# ============================================================
# URLs BASE DE LAS APIs
# ============================================================
API_URLS = {
    "geckoterminal": "https://api.geckoterminal.com/api/v2",
    "coingecko": "https://api.coingecko.com/api/v3",
    "dexscreener": "https://api.dexscreener.com",
    # Si hay key de Helius, usarla. Si no, usar RPC publico de Solana (mas lento).
    "helius": (
        f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
        if HELIUS_API_KEY
        else "https://api.mainnet-beta.solana.com"
    ),
    # Etherscan V2 API - URL unificada para todas las cadenas EVM
    "etherscan": "https://api.etherscan.io/v2/api",
    # X (Twitter) API v2
    "twitter": "https://api.twitter.com/2",
    # Fuentes de descubrimiento adicionales
    "pumpfun": "https://frontend-api-v3.pump.fun",
    "jupiter": "https://lite-api.jup.ag/tokens/v1",
    "raydium": "https://api-v3.raydium.io",
    "birdeye": "https://public-api.birdeye.so",
}

# Chain IDs para Etherscan V2 API
ETHERSCAN_CHAIN_IDS = {
    "ethereum": 1,
    "base": 8453,
    "bsc": 56,
    "arbitrum": 42161,
}

# ============================================================
# CADENAS SOPORTADAS
# ============================================================
SUPPORTED_CHAINS = {
    "solana": {
        "geckoterminal_id": "solana",
        "dexscreener_id": "solana",
        "native_token": "SOL",
    },
    "ethereum": {
        "geckoterminal_id": "eth",
        "dexscreener_id": "ethereum",
        "native_token": "ETH",
    },
    "base": {
        "geckoterminal_id": "base",
        "dexscreener_id": "base",
        "native_token": "ETH",
    },
    "bsc": {
        "geckoterminal_id": "bsc",
        "dexscreener_id": "bsc",
        "native_token": "BNB",
    },
    "arbitrum": {
        "geckoterminal_id": "arbitrum",
        "dexscreener_id": "arbitrum",
        "native_token": "ETH",
    },
}

# ============================================================
# BIRDEYE CU BUDGET (control de costes)
# ============================================================
# Birdeye Lite: 1.5M CU/mes ≈ 50K CU/dia
# Presupuesto conservador: 30K CU/dia para no exceder el limite
BIRDEYE_DAILY_CU_BUDGET = 30_000

# Costes estimados por endpoint en CU (Birdeye Lite tier)
# Fuente: https://docs.birdeye.so/docs/credit-usage
BIRDEYE_CU_COSTS = {
    "ohlcv": 5,              # GET /defi/ohlcv
    "token_overview": 10,    # GET /defi/token_overview
    "token_security": 5,     # GET /defi/token_security
    "token_creation_info": 5,  # GET /defi/token_creation_info
    "token_holder": 10,      # GET /defi/v3/token/holder
    "new_listing": 5,        # GET /defi/v2/tokens-new_listing
    "meme_list": 5,          # GET /defi/v3/token/meme-list
    "trade_data": 5,         # GET /defi/v3/token/trade-data-single
}

# ============================================================
# UMBRALES DE CLASIFICACION (Labels)
# ============================================================
# Ventana de observacion: 30 dias desde lanzamiento
LABEL_WINDOW_DAYS = 30

# Clasificacion de 5 categorias
LABELS_MULTI = {
    "gem": {
        "min_multiple": 10.0,       # Alcanzo 10x
        "sustain_multiple": 5.0,    # Se mantuvo >5x
        "sustain_days": 7,          # Por al menos 7 dias
    },
    "moderate_success": {
        "min_multiple": 3.0,        # Alcanzo 3x
        "sustain_multiple": 2.0,    # Se mantuvo >2x
        "sustain_days": 3,          # Por al menos 3 dias
    },
    "neutral": {
        "min_multiple": 0.3,        # Precio entre 0.3x y 3x
        "max_multiple": 3.0,
    },
    "failure": {
        "max_multiple": 0.1,        # Perdio 90%+
    },
    "rug": {
        "max_multiple": 0.01,       # Perdio 99%+ en 72h
        "time_hours": 72,
        "liquidity_drop_pct": 0.9,  # O liquidez cayo 90%+
    },
}

# Minimo de dias de datos OHLCV para clasificar (reducido de 7 a 3 para capturar rugs tempranos)
MIN_DAYS_REQUIRED = 3

# Umbrales para clasificacion por tiers (granular, complementa binaria)
TIER_THRESHOLDS = {
    "mega_gem": 10.0,        # max return >= 10x (1000%)
    "standard_gem": 4.0,     # max return >= 4x (300%)
    "mini_gem": 2.0,         # max return >= 2x (100%)
    "micro_gem": 1.5,        # max return >= 1.5x (50%)
    "neutral_upper": 1.5,    # max return < 1.5x
    "neutral_lower": 0.5,    # max return >= 0.5x
    "failure": 0.5,          # max return < 0.5x (perdio 50%+)
    "rug_drop_pct": 0.90,    # caida de 90%+ en primeras 72h
    "rug_max_hours": 72,     # ventana de deteccion de rug
}

# Umbrales de senal para scoring (unica fuente de verdad)
# Ajustados para modelos con pocos positivos (<200 gems):
# Las probabilidades se distribuyen en rango bajo (0.10-0.50),
# no llegan a 0.80+ porque el modelo es conservador.
SIGNAL_THRESHOLDS = {
    "STRONG": 0.60,    # >= 60% probabilidad de gem
    "MEDIUM": 0.40,    # >= 40%
    "WEAK": 0.30,      # >= 30% (alineado con threshold por defecto)
}

# Clasificacion binaria simplificada
LABEL_BINARY_THRESHOLD = 5.0  # success = alcanzo 5x en 30 dias

# Modo de label binario: "max_multiple" (v1-v4) o "return_7d" (v5+)
LABEL_BINARY_MODE = "return_7d"
LABEL_RETURN_7D_THRESHOLD = 1.2  # close_day7 / close_day1 >= 1.2 (+20% en 7d)

# Features excluidos del entrenamiento
EXCLUDED_FEATURES = [
    # Target leakage: return_7d ES el target (close_day7/close_day1)
    "return_7d",
    # Quasi-leakage: usan datos de la ventana de 7 dias (misma que el target)
    "max_return_7d",           # usa max(high) de ventana 7d
    "max_return_30d",          # usa max(high) de ventana 30d
    "close_to_high_ratio_7d",  # usa last close de ventana 7d
    "price_recovery_ratio",    # usa last close de ventana 7d
    # Leakage temporal: cambia con datetime.now(), no reproducible
    "days_since_launch",
    # Duplicado: tx_count_24h == makers_24h == buyers + sellers
    "tx_count_24h",
    # Colineal: makers_24h == buyers + sellers (r=1.0)
    "makers_24h",
    # Categoricos no numericos (is_numeric_dtype los filtra, pero por seguridad)
    "launch_hour_category",    # string categorico
    "chain",                   # string categorico
    "dex",                     # string categorico
    # Holder data: solo Solana+Helius, <5% de tokens tienen datos
    "top10_holder_pct",
    "top20_holder_pct",
    # Contract info: Etherscan solo, <5% cobertura
    "is_verified",
    "is_renounced",
    # Market context: requiere precios BTC/ETH/SOL que no estan en SQLite
    "btc_return_7d_at_launch",
    "eth_return_7d_at_launch",
    "sol_return_7d_at_launch",
    "market_fear_greed",
    # Social/DexScreener: buyers/sellers solo en snapshots, no en OHLCV
    "buyer_seller_ratio_24h",
    # Data leakage: columnas de labels que codifican directamente el resultado
    "tier_numeric",            # codifica directamente el outcome (1-5 tiers)
    "tier",                    # string pero red de seguridad contra leakage
    "close_max_multiple",      # metrica de resultado (max close / close inicial)
]

# ============================================================
# PARAMETROS DE FEATURES
# ============================================================
# Ventanas de tiempo para price action (en horas)
PRICE_WINDOWS = {
    "1h": 1,
    "6h": 6,
    "24h": 24,
    "48h": 48,
    "7d": 24 * 7,
    "14d": 24 * 14,
    "30d": 24 * 30,
}

# Ventanas para OHLCV
OHLCV_TIMEFRAMES = ["day", "hour"]  # GeckoTerminal soporta: day, hour, minute

# ============================================================
# PARAMETROS DE MODELOS ML
# ============================================================
ML_CONFIG = {
    "random_seed": 42,
    "test_size": 0.2,           # 20% para test
    "cv_folds": 5,              # 5-fold cross validation
    "smote_sampling": 0.5,      # Ratio de sobremuestreo para clase minoritaria
    "rf_params": {
        "n_estimators": 300,
        "max_depth": 15,
        "min_samples_leaf": 5,
        "class_weight": "balanced",
        "random_state": 42,
        "n_jobs": -1,
    },
    "xgb_params": {
        "n_estimators": 500,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42,
        "eval_metric": "logloss",
        "early_stopping_rounds": 50,
    },
    "optimal_threshold": None,  # Se sobreescribe tras entrenamiento con threshold optimizado
    "use_ensemble": False,      # Activar ensemble VotingClassifier (RF+XGB)
    "remove_correlated": True,  # Eliminar features con correlacion > 0.95
}

# ============================================================
# STORAGE BACKEND
# ============================================================
# "sqlite" (local, default) o "supabase" (cloud)
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "sqlite")

# Supabase config (solo necesario si STORAGE_BACKEND == "supabase")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# ============================================================
# CACHE
# ============================================================
CACHE_TTL_HOURS = 24  # Tiempo de vida del cache en horas
CACHE_ENABLED = True

# ============================================================
# LOGGING
# ============================================================
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
