# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

Memecoin Gem Detector - Data Science project that collects data from thousands of memecoins (Solana, Ethereum, Base), extracts differentiating features, and trains ML models to find correlations between "gems" (10x+) and tokens that go to zero.

## Build & Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run daily data collection
python -m src.data.collector

# Run tests
pytest tests/ -v

# Launch dashboard
streamlit run dashboard/app.py

# Execute notebooks in order (01 through 08)
jupyter notebook notebooks/
```

## Architecture

```
Trading Memes/
├── config.py                   # Central config (API keys, rate limits, thresholds)
├── src/
│   ├── api/                    # API clients (GeckoTerminal, DexScreener, Solana RPC, Etherscan)
│   │   ├── base_client.py      # Base class: rate limiting, retries, cache
│   │   ├── coingecko_client.py # GeckoTerminal + CoinGecko Demo
│   │   ├── dexscreener_client.py
│   │   ├── blockchain_rpc.py   # SolanaRPC + EtherscanClient
│   │   └── rate_limiter.py     # Token bucket rate limiter
│   ├── data/
│   │   ├── collector.py        # Daily collection orchestrator
│   │   ├── storage.py          # SQLite helpers (7 tables)
│   │   └── cache.py            # Disk cache for API responses
│   ├── features/               # Feature engineering (~35 features)
│   │   ├── tokenomics.py       # Holder concentration, supply
│   │   ├── liquidity.py        # LP depth, growth
│   │   ├── price_action.py     # Returns, volatility, volume trends
│   │   ├── social.py           # Buyer/seller ratios
│   │   ├── contract.py         # Verification, ownership
│   │   ├── market_context.py   # BTC/ETH/SOL trends, timing
│   │   └── builder.py          # Orchestrates all feature modules
│   ├── models/
│   │   ├── labeler.py          # 5-class + binary classification logic
│   │   ├── trainer.py          # RF + XGBoost with SMOTE
│   │   ├── evaluator.py        # Metrics, confusion matrix, ROC/PR curves
│   │   └── explainer.py        # SHAP analysis
│   └── utils/
│       ├── helpers.py          # safe_divide, pct_change, etc.
│       └── logger.py           # Centralized logging
├── notebooks/                  # Execute in order 01-08
├── dashboard/                  # Streamlit app (5 pages)
├── data/                       # SQLite DB, raw JSON, processed Parquet, models
└── tests/
```

## Key Conventions

- All code comments in Spanish (target audience: Python beginners)
- APIs: GeckoTerminal (principal), DexScreener (buyers/sellers), Helius RPC (Solana holders), Etherscan (contract verification), CoinGecko Demo (market context)
- Storage: SQLite + Parquet files
- ML: Random Forest baseline, XGBoost precision, SHAP explainability
- All API responses cached locally to avoid data loss
- Feature modules return flat dicts, builder combines into DataFrame
