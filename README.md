# 💎 Trading Memes - Memecoin Gem Detector

Sistema de Machine Learning que detecta "gems" (tokens con potencial de 10x+) en miles de memecoins de Solana, Ethereum y Base.

[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 ¿Qué hace este proyecto?

**Trading Memes** recopila datos de miles de memecoins, extrae features diferenciadores, y entrena modelos de Machine Learning para predecir cuáles tienen alta probabilidad de éxito (10x o más).

### Características principales:

- 📊 **Recopilación automatizada** de datos (precio, volumen, liquidez, holders, contratos)
- 🤖 **5 APIs integradas**: GeckoTerminal, DexScreener, Helius RPC, Etherscan, CoinGecko
- 🧠 **35+ features** extraídos (tokenomics, liquidez, price action, social, contrato, timing)
- 🎓 **2 modelos ML**: Random Forest + XGBoost con SHAP explainability
- 📈 **Dashboard interactivo** con Streamlit (6 páginas + Señales)
- ⚡ **Sistema automático**: Recopilación diaria, backups, health checks
- 🔔 **Alertas proactivas**: Email y Telegram cuando hay problemas

---

## 🚀 Quick Start

### Requisitos Previos

- **Python 3.14+**
- **macOS** (Linux compatible con modificaciones menores)
- **10GB espacio en disco**
- **(Opcional) API keys**: Helius, Etherscan, Basescan

### Instalación en 5 minutos

```bash
# 1. Clonar repositorio
cd "Tu/Ruta/Proyectos"

# 2. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno (opcional)
cp .env.example .env
# Editar .env con tus API keys

# 5. Ejecutar setup inicial
./scripts/setup.sh
```

### Uso Básico

```bash
# Ver estadísticas rápidas
./scripts/quick_stats.sh

# Ejecutar dashboard
streamlit run dashboard/app.py

# Ejecutar recopilación manual
python -m src.data.collector

# Ver health check
./scripts/health_check.sh
```

---

## 📊 Estado Actual del Proyecto

```
Tokens:            190
OHLCV:             2,550
Pool Snapshots:    215
Holders:           700
Features:          190

Modelos:           RF (F1=0.67), XGBoost (F1=0.59)
Scorer:            Gems ~80% prob, Failures ~27% prob
Automatización:    ✓ Activa (launchd)
```

---

## 🏗️ Arquitectura

```
Trading Memes/
├── config.py                    # Configuración central
├── src/
│   ├── api/                     # Clientes de APIs (5)
│   │   ├── base_client.py       # Base con rate limiting + cache
│   │   ├── coingecko_client.py  # GeckoTerminal + CoinGecko
│   │   ├── dexscreener_client.py
│   │   └── blockchain_rpc.py    # Solana RPC + Etherscan V2
│   ├── data/
│   │   ├── collector.py         # Orquestador de recopilación
│   │   ├── storage.py           # SQLite (8 tablas)
│   │   └── cache.py             # Cache en disco
│   ├── features/                # Feature engineering (8 módulos)
│   │   ├── tokenomics.py        # Distribución de holders
│   │   ├── liquidity.py         # LP depth, growth
│   │   ├── price_action.py      # Returns, volatility
│   │   ├── social.py            # Buyers/sellers ratios
│   │   ├── contract.py          # Verification, ownership
│   │   ├── market_context.py    # BTC/ETH/SOL trends
│   │   ├── temporal.py          # Timing del lanzamiento 🆕
│   │   └── builder.py           # Orquestador
│   ├── models/
│   │   ├── labeler.py           # Clasificación 5-class + binary
│   │   ├── trainer.py           # RF + XGBoost con SMOTE
│   │   ├── evaluator.py         # Métricas, ROC, PR curves
│   │   ├── explainer.py         # SHAP analysis
│   │   ├── scorer.py            # Scoring de tokens nuevos
│   │   ├── backtester.py        # Simulación histórica
│   │   └── optimizer.py         # Hyperparameter tuning
│   ├── monitoring/              # Sistema de monitoreo 🆕
│   │   └── health_monitor.py    # Health checks + API usage tracking
│   └── utils/
│       ├── helpers.py           # safe_divide, pct_change, etc.
│       └── logger.py            # Logging centralizado
├── dashboard/                   # Streamlit app (7 páginas)
│   ├── app.py
│   └── views/
│       ├── overview.py
│       ├── eda.py
│       ├── model_results.py
│       ├── feature_importance.py
│       ├── token_lookup.py
│       ├── signals.py
│       └── system_health.py     # 🆕
├── data/
│   ├── trading_memes.db         # SQLite database
│   ├── raw/                     # JSON responses crudos
│   ├── processed/               # Parquet, features, train data
│   ├── models/                  # .joblib, metrics, SHAP
│   └── backups/                 # Backups automáticos 🆕
├── scripts/
│   ├── daily_collect.sh         # Recopilación diaria
│   ├── daily_signals.sh         # Generación de señales
│   ├── retrain.sh               # Re-entrenamiento
│   ├── full_refresh.sh          # Refresh completo
│   ├── health_check.sh          # 🆕 Health checks
│   ├── backup_db.sh             # 🆕 Backups automáticos
│   ├── restore_from_backup.sh   # 🆕 Restauración
│   ├── setup_monitoring.sh      # 🆕 Setup de monitoreo
│   ├── test_system.sh           # 🆕 Test completo
│   └── quick_stats.sh           # 🆕 Stats rápidos
├── notebooks/                   # Jupyter notebooks (01-08)
└── tests/                       # Tests unitarios (37 tests)
```

---

## 🔑 Características Detalladas

### 1. Recopilación de Datos

**APIs Integradas:**
- 🟢 **GeckoTerminal**: OHLCV, pools, trending (30 calls/min)
- 🟢 **DexScreener**: Buyers/sellers, boosts, precio (300 calls/min)
- 🟢 **Helius RPC**: Holders de Solana (free tier)
- 🟢 **Etherscan V2**: Contratos Ethereum/Base (5 calls/sec)
- 🟢 **CoinGecko**: Precios BTC/ETH/SOL (10K calls/mes)

**Base de Datos (SQLite):**
- `tokens` - Info básica de cada token
- `pool_snapshots` - Snapshots periódicos (precio, volumen, liquidez)
- `ohlcv` - Datos OHLCV históricos
- `holder_snapshots` - Top 20 holders por token
- `contract_info` - Verificación, ownership
- `labels` - Clasificación (gem, failure, etc.)
- `features` - Matriz de features calculados
- `api_usage` - 🆕 Tracking de rate limits

### 2. Feature Engineering (40+ Features)

**Tokenomics** (distribuciónde holders):
- Concentración top 1, 5, 10 holders
- Gini coefficient
- Número de holders únicos

**Liquidez**:
- LP depth (USD)
- Crecimiento de LP en 24h/7d
- LP/Market Cap ratio

**Price Action**:
- Returns en 1h, 6h, 24h, 48h, 7d
- Volatilidad (std dev)
- Volume trends
- Max return en 7d

**Social**:
- Buyer/seller ratios
- Tx count
- Makers count

**Contrato**:
- Is verified
- Is renounced
- Has mint authority
- Days since deployment

**Market Context**:
- BTC/ETH/SOL trends en 7d
- Chain (Solana/Ethereum/Base)
- DEX (Raydium/Uniswap/etc)

**Temporal** (🆕):
- Día de la semana de lanzamiento
- Hora del día (UTC)
- Es fin de semana
- Días desde lanzamiento
- Categoría horaria

### 3. Machine Learning

**Modelos Entrenados:**
- **Random Forest**: F1=0.67, CV F1=0.63 (baseline robusto)
- **XGBoost**: F1=0.59 (precisión en clase positiva)

**Técnicas:**
- SMOTE para balancear clases
- 5-fold cross-validation
- SHAP values para explainability
- Versionado de modelos

**Top 5 Features (SHAP):**
1. `return_24h` - Return en 24h
2. `return_48h` - Return en 48h
3. `volume_trend_slope` - Pendiente de volumen
4. `max_return_7d` - Máximo return en 7d
5. `volume_spike_ratio` - Ratio de spikes de volumen

### 4. Dashboard Interactivo

**7 Páginas:**
1. **Overview**: Stats generales, resumen de datos
2. **Análisis Exploratorio**: Gráficos interactivos de features
3. **Resultados del Modelo**: Métricas, confusion matrix, ROC/PR curves
4. **Importancia de Features**: SHAP waterfall, summary, dependence
5. **Buscar Token**: Predicción individual por contract address
6. **Señales**: 🆕 Alertas diarias, histórico, backtesting interactivo
7. **System Health**: 🆕 Estado del sistema, API usage, health checks

**Acceso:**
```bash
streamlit run dashboard/app.py
# Abre automáticamente en http://localhost:8501
```

### 5. Sistema de Monitoreo 🆕

**Health Checks (cada 6 horas):**
- ✅ APIs respondiendo correctamente
- ✅ Base de datos creciendo
- ✅ Espacio en disco suficiente
- ✅ Última recolección <26h
- ✅ API usage dentro de límites

**Backups Automáticos (diario 04:00):**
- Copia SQLite completa
- Export a Parquet (7 tablas)
- Metadata JSON
- Retention de 30 días

**Alertas:**
- Email (Gmail SMTP)
- Telegram Bot
- Logs estructurados

**Comandos:**
```bash
# Health check manual
./scripts/health_check.sh

# Backup manual
./scripts/backup_db.sh

# Restaurar backup
./scripts/restore_from_backup.sh 2026-02-26

# Ver logs
tail -f logs/health_check.log
tail -f logs/backup.log
```

---

## 📈 Flujo de Trabajo

### Flujo Diario Automatizado

```
03:00 → Daily Collect  (recopila datos de APIs)
04:00 → Backup DB      (respaldo completo)
06:00 → Health Check   (verifica sistema)
12:00 → Health Check   (verifica sistema)
18:00 → Health Check   (verifica sistema)
00:00 → Health Check   (verifica sistema)
```

### Flujo Manual (TDD - Test-Driven Data Science)

```bash
# 1. Recopilar más datos
python -m src.data.collector

# 2. Feature engineering
python -m src.features.builder

# 3. Entrenar modelos
python -m src.models.trainer

# 4. Evaluar modelos
python -m src.models.evaluator

# 5. Generar SHAP
python -m src.models.explainer

# 6. Dashboard
streamlit run dashboard/app.py
```

---

## 🛠️ Comandos Útiles

### Desarrollo

```bash
# Ver estado rápido
./scripts/quick_stats.sh

# Test completo del sistema
./scripts/test_system.sh

# Ejecutar tests unitarios
pytest tests/ -v

# Ejecutar notebooks
jupyter notebook notebooks/
```

### Mantenimiento

```bash
# Refresh completo (cuando haya 300+ tokens)
./scripts/full_refresh.sh

# Re-entrenar modelos
./scripts/retrain.sh

# Limpiar cache
rm -rf .cache/*

# Ver logs
tail -f logs/*.log
```

### Monitoreo

```bash
# Ver servicios activos
launchctl list | grep tradingmemes

# Ver backups disponibles
ls -lh data/backups/

# Ver último health check
cat logs/health_status.json | jq .
```

---

## 🧪 Testing

```bash
# Ejecutar todos los tests
pytest tests/ -v

# Tests con cobertura
pytest tests/ --cov=src --cov-report=html

# Test específico
pytest tests/test_features.py -v

# Tests actualmente pasando: 37/37 ✓
```

---

## 📚 Documentación Adicional

- **[HEALTH_BACKUPS_README.md](HEALTH_BACKUPS_README.md)** - Guía rápida de monitoreo
- **[docs/MONITORING.md](docs/MONITORING.md)** - Documentación completa de monitoreo
- **[MEJORAS_PROPUESTAS.md](MEJORAS_PROPUESTAS.md)** - Roadmap de mejoras
- **[CLAUDE.md](CLAUDE.md)** - Instrucciones para Claude Code

---

## 🎯 Roadmap

### ✅ Completado (Fases 1-6)

- [x] Feature engineering (40+ features)
- [x] Modelos ML (RF + XGBoost)
- [x] Dashboard interactivo (7 páginas)
- [x] Automatización diaria (launchd)
- [x] Health checks + Backups
- [x] Rate limit tracking
- [x] Features temporales

### 🔄 En Progreso

- [ ] Acumulación de datos (objetivo: 300+ tokens)
- [ ] Dashboard de System Health
- [ ] Optimización de modelos

### 📅 Futuro (3-6 meses)

- [ ] Features de sentimiento social (Twitter/Telegram)
- [ ] Multi-chain expansion (Polygon, Arbitrum, BSC)
- [ ] Paper trading
- [ ] Trading automático

---

## ⚠️ Disclaimer

**IMPORTANTE:** Este proyecto es para fines educativos y de investigación. NO es asesoría financiera.

- Los memecoins son extremadamente volátiles y riesgosos
- Puedes perder el 100% de tu inversión
- Los modelos ML tienen precisión limitada (~67% F1)
- Siempre haz tu propia investigación (DYOR)
- Nunca inviertas más de lo que puedes perder

---

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

---

## 👤 Autor

**Ulises Díaz Hernández**
- Proyecto: Trading Memes - Memecoin Gem Detector
- Versión: 1.0
- Última actualización: 2026-02-27

---

## 🙏 Agradecimientos

- **APIs utilizadas**: GeckoTerminal, DexScreener, Helius, Etherscan, CoinGecko
- **Librerías**: scikit-learn, XGBoost, SHAP, Streamlit, Plotly
- **Comunidad**: Crypto research community

---

**¿Necesitas ayuda?** Revisa la documentación en `docs/` o ejecuta `./scripts/test_system.sh` para diagnóstico.
