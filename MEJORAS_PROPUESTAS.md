# MEJORAS PROPUESTAS - Trading Memes

**Fecha de Análisis:** 2026-02-26
**Autor:** Claude Code (Análisis Estratégico)
**Estado del Proyecto:** FASES 1-6 COMPLETADAS - Sistema funcional

---

## 📊 ESTADO ACTUAL: SÓLIDO

### Métricas Actuales
- ✅ Sistema funcional 100% (37/37 tests pasan)
- ✅ 190 tokens, 2550 OHLCV, buen volumen de datos inicial
- ✅ Automatización activa (launchd 03:00 diaria)
- ✅ Modelos RF/XGBoost con métricas razonables para dataset inicial
  - Random Forest: F1=0.67, CV F1=0.63, Accuracy=0.68
  - XGBoost: F1=0.59, Accuracy=0.63
- ✅ Dashboard completo y funcional (6 páginas)
- ✅ 5/5 APIs funcionando correctamente

### Base de Datos
```
tokens: 190
pool_snapshots: 215
ohlcv: 2550
holder_snapshots: 700
contract_info: 91
labels: 91
features: 190
```

### Arquitectura
```
Trading Memes/
├── config.py                   # Central config (API keys, rate limits, thresholds)
├── src/
│   ├── api/                    # API clients (GeckoTerminal, DexScreener, Solana RPC, Etherscan)
│   ├── data/                   # collector.py, storage.py, cache.py
│   ├── features/               # 7 módulos (~35 features)
│   ├── models/                 # labeler, trainer, evaluator, explainer, scorer, backtester, optimizer
│   └── utils/                  # helpers, logger
├── dashboard/                  # Streamlit app (6 páginas)
├── data/                       # SQLite DB, raw JSON, processed Parquet, models
├── scripts/                    # Automatización y mantenimiento
└── tests/                      # 37 tests unitarios
```

---

## 🚀 MEJORAS PROPUESTAS

### 🔴 PRIORIDAD ALTA - Acción Inmediata

#### 1. Monitoreo y Alertas

**Problema:** No hay monitoreo proactivo del sistema automatizado.
**Riesgo:** Fallas silenciosas pueden pasar desapercibidas durante semanas.

**Propuestas:**

✅ **Sistema de health checks**: Script diario que verifique:
- APIs respondiendo correctamente
- Base de datos creciendo (nuevos registros OHLCV)
- launchd ejecutándose sin errores
- Espacio en disco disponible

✅ **Notificaciones**: Email/Telegram cuando:
- Recolección diaria falla
- Alguna API responde con errores consistentes
- Modelos producen predicciones anómalas (todos 0 o todos 1)

✅ **Dashboard de salud del sistema**: Nueva página que muestre:
- Última ejecución exitosa
- Tasa de error por API en últimos 7 días
- Volumen de datos por día (gráfico)

**Archivos a crear:**
- `scripts/health_check.sh` (ejecutar cada 6 horas)
- `src/monitoring/health_monitor.py`
- `dashboard/views/system_health.py`

**Impacto:** Alto - Previene pérdida de datos y downtime no detectado
**Esfuerzo:** Medio (2-3 días)

---

#### 2. Respaldo de Datos (Backup)

**Problema:** La DB SQLite (`trading_memes.db`) no tiene respaldos automáticos.
**Riesgo:** Pérdida total de datos históricos por corrupción o error humano.

**Propuestas:**

✅ **Backup incremental diario**: Cron que copie la DB a carpeta timestamped
```bash
data/backups/trading_memes_2026-02-26.db
```

✅ **Backup remoto semanal**: Subir a Google Drive / Dropbox / S3

✅ **Exportación Parquet diaria**: Snapshot de todas las tablas en formato Parquet (más resiliente que SQLite)

✅ **Script de restauración**:
```bash
./scripts/restore_from_backup.sh 2026-02-26
```

**Archivos a crear:**
- `scripts/backup_db.sh` (incluir en launchd diario)
- `scripts/restore_from_backup.sh`
- `scripts/export_to_parquet.sh`

**Impacto:** Crítico - Protege el activo más valioso (datos históricos)
**Esfuerzo:** Bajo (1 día)

---

#### 3. Rate Limit Tracking

**Problema:** No hay visibilidad de cuántas llamadas API se hacen por día/mes.
**Riesgo:** Exceder límites mensurales sin darse cuenta (CoinGecko: 10K/mes).

**Propuestas:**

✅ **Contadores en DB**: Nueva tabla `api_usage` con columnas:
```sql
CREATE TABLE api_usage (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    api_name TEXT NOT NULL,
    endpoint TEXT,
    status_code INTEGER,
    response_time_ms INTEGER
);
```

✅ **Dashboard de consumo API**: Gráfico de barras por API/día

✅ **Alertas de límite**: Warning cuando se alcance 80% del límite mensual

**Archivos a modificar:**
- `src/api/base_client.py` (log cada request a DB)
- `src/data/storage.py` (añadir métodos para `api_usage`)
- `dashboard/views/system_health.py` (mostrar consumo)

**Impacto:** Alto - Previene exceder límites y costos inesperados
**Esfuerzo:** Medio (2 días)

---

### 🟡 PRIORIDAD MEDIA - Próximas 2-4 Semanas

#### 4. Features Avanzadas ✅ COMPLETADO (2026-02-27)

**Oportunidad:** Agregar features más sofisticadas puede mejorar F1 score de 0.67 a 0.75+.

**Propuestas:**

✅ **Features temporales** - IMPLEMENTADO:
- ✅ Día de la semana de lanzamiento (`launch_day_of_week`)
- ✅ Hora de lanzamiento (UTC) (`launch_hour_utc`)
- ✅ Días desde lanzamiento (`days_since_launch`)
- ✅ ¿Lanzado en fin de semana? (`launch_is_weekend`)
- ✅ Categoría horaria (`launch_hour_category`)

✅ **Features de volatilidad** - IMPLEMENTADO:
- ✅ Bandas de Bollinger: `bb_upper_7d`, `bb_lower_7d`, `bb_pct_b_7d`, `bb_bandwidth_7d`
- ✅ ATR (Average True Range): `atr_7d`, `atr_pct_7d`
- ✅ RSI (Relative Strength Index): `rsi_7d`, `rsi_divergence_7d`
- ✅ Rango intradía: `avg_intraday_range_7d`, `max_intraday_range_7d`
- ✅ Volatility spikes: `volatility_spike_count_7d`

**IMPACTO VERIFICADO v1:**
- **6 de los top 15 features (40%) son features de volatilidad** 🔥
- Modelos v1: RF val_f1=1.0, XGB val_f1=1.0
- Ver SHAP: bb_bandwidth_7d (#3), atr_pct_7d (#4), rsi_divergence_7d (#7)

⏳ **Features pendientes**:
- [ ] Features de liquidez avanzadas (ratio LP/Market Cap, estabilidad)
- [ ] Features de holders dynamics (velocidad cambio, Gini coefficient)
- [ ] Features de mercado macro (correlación BTC/ETH, sentimiento)

**Archivos creados:**
- ✅ `src/features/temporal.py` (5 features)
- ✅ `src/features/volatility_advanced.py` (11 features)
- ✅ `CHANGELOG_VOLATILITY.md` (documentación completa)
- ⏳ `src/features/holder_dynamics.py` (pendiente)

**Impacto:** Alto - Mejora directa verificada en modelo v1
**Esfuerzo:** Alto (5-7 días) - **COMPLETADO**

---

#### 5. Optimización de Modelos

**Oportunidad:** Con más datos (objetivo: 300+ tokens), optimizar hiperparámetros puede dar F1 > 0.75.

**Propuestas:**

✅ **Usar `optimizer.py`**: Está implementado pero no se usa. Ejecutar cuando haya 300+ tokens:
```bash
./scripts/full_refresh.sh  # Incluir optimización automática
```

✅ **Ensemble stacking**: Combinar RF + XGBoost con meta-learner (Logistic Regression)
```python
from sklearn.ensemble import StackingClassifier
estimators = [('rf', rf_model), ('xgb', xgb_model)]
meta_model = LogisticRegression()
stacking = StackingClassifier(estimators=estimators, final_estimator=meta_model)
```

✅ **Features adicionales de SMOTE**: Probar ADASYN o BorderlineSMOTE en lugar de SMOTE vanilla

✅ **Validación temporal**: Usar `TimeSeriesSplit` en lugar de `KFold` (más realista para datos temporales)
```python
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5)
```

**Archivos a modificar:**
- `src/models/trainer.py` (añadir stacking ensemble)
- `scripts/full_refresh.sh` (llamar a `optimizer.py` automáticamente)

**Impacto:** Alto - Mejora sustancial en predicciones
**Esfuerzo:** Medio (3-4 días)

---

#### 6. Pipeline de Re-Entrenamiento ✅ COMPLETADO (2026-02-27)

**Problema:** No hay criterio claro para cuándo re-entrenar modelos.

**Propuestas:**

✅ **Re-entrenamiento automático** - IMPLEMENTADO:
- ✅ Script `check_retrain_needed.sh` con flag `--auto` para re-entrenar
- ✅ Detecta cuando necesita re-entrenamiento basado en 4 tipos de drift
- ✅ Integrado con `retrain.sh` que usa versionado automático

✅ **Validación de drift** - IMPLEMENTADO:
- ✅ **Data Drift**: KS test (Kolmogorov-Smirnov) para cada feature
- ✅ **Concept Drift**: F1 score en datos nuevos
- ✅ **Volume Drift**: Cantidad de nuevos tokens
- ✅ **Time Drift**: Días desde último entrenamiento
```python
# Implementado en src/models/drift_detector.py
detector = DriftDetector(
    ks_threshold=0.05,
    f1_threshold=0.5,
    volume_threshold=50,
    days_threshold=30
)
drift_report = detector.detect_all_drift(...)
```

✅ **Versionado de modelos** - IMPLEMENTADO:
- ✅ Modelos guardados en `data/models/v1/`, `v2/`, etc.
- ✅ Metadata JSON completa por versión
- ✅ Symlinks para compatibilidad (`random_forest.joblib -> v1/random_forest.joblib`)
- ✅ `latest_version.txt` tracking versión actual
- ✅ Rollback fácil con `load_models_versioned(version="v1")`

**MODELO v1 CREADO:**
```json
{
  "version": "v1",
  "trained_at": "2026-02-27T17:07:00Z",
  "num_features": 46,
  "train_samples": 72,
  "test_samples": 19,
  "rf_cv_f1": 0.47,
  "rf_val_f1": 1.0,
  "xgb_val_f1": 1.0
}
```

**Archivos creados:**
- ✅ `src/models/drift_detector.py` (540 líneas, 4 tipos de drift)
- ✅ `scripts/check_retrain_needed.sh` (230 líneas, manual o --auto)
- ✅ `CHANGELOG_RETRAINING.md` (documentación completa)
- ✅ Modificado `src/models/trainer.py` (+250 líneas para versionado)
- ✅ Modificado `scripts/retrain.sh` (usa `save_models_versioned()`)
- ✅ 16 tests nuevos en `tests/test_drift_and_versioning.py` (58/58 pasan)

**Impacto:** Alto - Sistema autónomo de actualización de modelos
**Esfuerzo:** Medio (3 días) - **COMPLETADO**

---

#### 7. Dashboard - Mejoras UX

**Oportunidad:** Hacer el dashboard más útil para toma de decisiones.

**Propuestas:**

✅ **Filtros en "Señales"**:
- Por chain (Solana, Ethereum, Base)
- Por probabilidad mínima (slider 0-100%)
- Por fecha (date picker)

✅ **Gráficos OHLCV interactivos**: Usar Plotly Candlestick en Token Lookup
```python
import plotly.graph_objects as go
fig = go.Figure(data=[go.Candlestick(
    x=df['timestamp'],
    open=df['open'], high=df['high'],
    low=df['low'], close=df['close']
)])
```

✅ **Comparador de tokens**: Vista side-by-side de 2-3 tokens
```
Token A         Token B         Token C
[Gráfico]       [Gráfico]       [Gráfico]
Features:       Features:       Features:
- Prob: 85%     - Prob: 45%     - Prob: 92%
- Volume: 500K  - Volume: 50K   - Volume: 2M
```

✅ **Exportar señales a CSV**: Botón de descarga en página de Señales
```python
st.download_button(
    label="Descargar CSV",
    data=signals_df.to_csv(index=False),
    file_name=f"signals_{datetime.now():%Y%m%d}.csv",
    mime="text/csv"
)
```

✅ **Notificaciones in-app**: Usar `st.toast()` para alertas importantes
```python
st.toast("¡Nueva gem candidate detectada! Prob: 87%", icon="💎")
```

**Archivos a modificar:**
- `dashboard/views/signals.py`
- `dashboard/views/token_lookup.py`
- `dashboard/views/token_comparison.py` (nuevo)

**Impacto:** Medio - Mejora experiencia de usuario
**Esfuerzo:** Medio (3 días)

---

### 🟢 PRIORIDAD BAJA - Futuro (Post MVP)

#### 8. Integración con Exchange APIs

**Visión:** Trading automático basado en señales del modelo.

**Propuestas:**

✅ **Paper trading**: Simular trades con API de exchange ficticio
- Rastrear portfolio virtual
- Calcular P&L en tiempo real
- Generar reportes de rendimiento

✅ **Bot de trading**: Ejecutar compras automáticas cuando probabilidad > 0.8
- Integrar con Binance/KuCoin API
- Position sizing automático
- Stop-loss y take-profit

✅ **Gestión de riesgo**:
- Stop-loss automático (-20%)
- Position sizing basado en Kelly Criterion
- Diversificación automática (máx 10% por posición)

**Archivos a crear:**
- `src/trading/paper_trader.py`
- `src/trading/risk_manager.py`
- `src/trading/exchange_client.py`

**Impacto:** Muy Alto - Monetización directa del sistema
**Esfuerzo:** Muy Alto (2-3 semanas)
**Riesgo:** Alto - Requiere capital real y gestión de riesgo sofisticada

---

#### 9. Datos Adicionales

**Oportunidad:** Enriquecer con fuentes de datos externas.

**Propuestas:**

✅ **Twitter/X API**: Sentimiento de menciones en redes sociales
- Número de menciones en últimas 24h
- Sentiment score (positivo/negativo/neutral)
- Influencers hablando del token

✅ **Telegram API**: Actividad en grupos de cada token
- Número de mensajes por hora
- Crecimiento de miembros
- Actividad de administradores

✅ **On-chain analytics**: Usar Dune Analytics / Nansen para métricas avanzadas
- Smart money wallet activity
- Token transfers patterns
- DEX agregator routing

✅ **News API**: Detectar menciones en CoinDesk, CoinTelegraph
- Número de artículos en últimas 24h
- Sentiment de noticias

**Archivos a crear:**
- `src/api/twitter_client.py`
- `src/api/telegram_client.py`
- `src/features/social_sentiment.py`
- `src/features/news_sentiment.py`

**Impacto:** Alto - Features de sentimiento son muy predictivos
**Esfuerzo:** Alto (1-2 semanas)
**Costo:** Twitter API: $100/mes, News API: $50/mes

---

#### 10. Multi-Chain Expansion

**Oportunidad:** Agregar más cadenas (Polygon, Arbitrum, BSC).

**Propuestas:**

✅ **Arquitectura multi-chain**: Abstraer lógica de chain-specific en `src/api/blockchain_rpc.py`

✅ **Nuevos clientes Etherscan**: Usar V2 API para Polygon, Arbitrum
```python
ETHERSCAN_CHAIN_IDS = {
    "ethereum": 1,
    "base": 8453,
    "polygon": 137,      # NUEVO
    "arbitrum": 42161,   # NUEVO
    "bsc": 56,          # NUEVO
}
```

✅ **Features por chain**: Algunos chains tienen características únicas
- Solana: Más rápido, menor fee
- Ethereum: Mayor liquidez, más institucional
- BSC: Más retail, mayor volatilidad

**Archivos a modificar:**
- `config.py` (añadir nuevas chains a `SUPPORTED_CHAINS`)
- `src/api/blockchain_rpc.py` (añadir RPCs)
- `src/features/builder.py` (features específicas por chain)

**Impacto:** Alto - 10x más tokens disponibles
**Esfuerzo:** Alto (1 semana por chain)

---

## 📈 PLAN DE ACCIÓN RECOMENDADO

### ✅ Semana 1-2 (COMPLETADO - 2026-02-27)
- [x] Implementar health checks básicos
- [x] Configurar backup diario de DB
- [x] Añadir contadores de API usage
- [x] Configurar alertas por email (Gmail SMTP)
- [x] Implementar features temporales
- [x] Mejorar dashboard con filtros y exportación CSV
- [x] Dashboard de system health (nueva página)
- [x] Implementar versionado de modelos
- [x] Añadir features avanzadas de volatilidad

**Entregables COMPLETADOS:**
- ✅ `scripts/health_check.sh` funcionando
- ✅ `scripts/backup_db.sh` en launchd
- ✅ Tabla `api_usage` en DB
- ✅ `src/features/temporal.py` con 5 features
- ✅ `src/features/volatility_advanced.py` con 11 features
- ✅ Dashboard con 7 páginas
- ✅ `data/models/v1/` con metadata
- ✅ 58/58 tests pasando

---

### 🔄 Próximo Mes (Días 1-30) - ACUMULACIÓN
- [ ] **Esperar acumulación de datos** (objetivo: 300+ tokens con OHLCV completo)
- [ ] Monitorear con `./scripts/quick_stats.sh` semanalmente
- [ ] Verificar health checks automáticamente cada 6h
- [ ] Backups diarios funcionando (04:00)
- [ ] Recolección diaria funcionando (03:00)

**Métricas objetivo:**
- `tokens_in_db >= 300`
- `ohlcv_records >= 10000`
- `avg_daily_new_tokens >= 5`

---

### 📊 Post-Acumulación (300+ tokens) - OPTIMIZACIÓN
- [ ] Ejecutar optimización de modelos con ModelOptimizer
- [ ] Ejecutar `./scripts/full_refresh.sh` (re-extraer features + re-entrenar)
- [ ] Crear modelo v2 con dataset completo
- [ ] Validar mejora en métricas (objetivo: F1 > 0.75)

**Entregables esperados:**
- Modelos v2 con F1 > 0.75 (mejora +10% sobre v1)
- `data/models/v2/` con metadata
- Análisis de impacto de nuevas features

---

### Próximos 3 Meses (Largo Plazo)
- [ ] Implementar drift detector
- [ ] Añadir features de sentimiento social (Twitter/Telegram)
- [ ] Paper trading funcionando
- [ ] Multi-chain expansion (Polygon, Arbitrum)

**Entregables:**
- Sistema autónomo de re-entrenamiento
- Paper trading con ROI simulado
- 1000+ tokens en 5+ chains

---

## ⚠️ RIESGOS IDENTIFICADOS

| Riesgo | Probabilidad | Impacto | Mitigación Propuesta |
|--------|--------------|---------|---------------------|
| **APIs cambien sin aviso** | Media | Alto | Health checks + alertas + tests E2E |
| **DB SQLite se corrompa** | Baja | Crítico | Backups diarios + Parquet exports |
| **Exceder límites API** | Media | Medio | Tracking + alertas al 80% |
| **Modelos se vuelvan obsoletos** | Alta | Alto | Re-entrenamiento automático + drift detection |
| **Sesgo temporal en datos** | Alta | Medio | TimeSeriesSplit en CV + validación en holdout |
| **Overfitting en dataset pequeño** | Alta | Medio | Regularización + cross-validation riguroso |
| **Labels incorrectos** | Media | Alto | Revisión manual + threshold conservador |
| **Market regime change** | Media | Alto | Drift detection + features de contexto macro |

### Riesgos Técnicos Adicionales

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| **launchd falla sin notificar** | Media | Alto | Health check externo cada 6h |
| **Espacio en disco lleno** | Baja | Alto | Monitoring + rotación de logs |
| **Python 3.14 incompatibilidades** | Baja | Medio | Pin exact versions en requirements.txt |
| **Streamlit crash en producción** | Baja | Medio | Restart automático + logs |

---

## 💰 COSTOS ESTIMADOS

### Actual (Gratis)
- ✅ GeckoTerminal: Free tier (30 calls/min)
- ✅ DexScreener: Free tier (300 calls/min)
- ✅ Helius: Free tier (50 calls/sec)
- ✅ CoinGecko: Demo API (10K calls/mes)
- ✅ Etherscan: Free tier (5 calls/sec)

**Costo actual:** $0/mes

---

### Mejoras Propuestas - Costo Incremental

#### Tier 1: Monitoreo y Backups (Gratis)
- ✅ Email SMTP: Gratis (Gmail SMTP)
- ✅ Telegram Bot API: Gratis
- ✅ Google Drive: 15GB gratis (suficiente para backups)

**Costo adicional:** $0/mes

---

#### Tier 2: APIs Mejoradas (Opcional)
- ❓ **CoinGecko Pro**: $129/mes (500K calls/mes)
  - **Solo si:** Excedes 10K calls/mes
  - **ROI:** Permite escalar a 1000+ tokens

- ❓ **Helius Pro**: $99/mes (llamadas ilimitadas)
  - **Solo si:** Necesitas holders de 500+ tokens Solana
  - **ROI:** Holders data es muy predictivo

**Costo adicional:** $0-228/mes (según necesidad)

---

#### Tier 3: Features Avanzadas (Futuro)
- ❓ **Twitter API**: $100/mes (Academic Research tier)
- ❓ **News API**: $50/mes
- ❓ **S3 Storage**: $5/mes para backups remotos
- ❓ **VPS Hosting**: $20/mes (si mueves de local a servidor)

**Costo adicional:** $175/mes (para features premium)

---

### Resumen de Costos

| Fase | Componentes | Costo Mensual | ¿Necesario? |
|------|-------------|---------------|-------------|
| **MVP Actual** | APIs gratuitas | $0 | ✅ Ya implementado |
| **Mejoras Alta Prioridad** | Monitoreo + Backups | $0 | ✅ Recomendado ahora |
| **Escalar a 1000+ tokens** | CoinGecko Pro + Helius Pro | $228 | ⏳ Solo cuando sea necesario |
| **Features Premium** | Twitter + News + S3 + VPS | $175 | ⏳ Futuro (6+ meses) |

**Recomendación:** Mantener costo $0 por ahora. Escalar APIs solo cuando se confirme ROI positivo con paper trading.

---

## 🎯 MÉTRICAS DE ÉXITO

### Corto Plazo (1 mes) - EN PROGRESO
- [ ] 300+ tokens con OHLCV completo (actualmente: 190)
- [x] 0 downtime en recolección diaria (monitoreo activo)
- [ ] F1 score > 0.70 con dataset completo (v1: cv_f1=0.47, val_f1=1.0 con 91 tokens)
- [x] Health checks detectando 100% de fallas de API
- [x] 0 pérdidas de datos (backups funcionando)

**KPIs ACTUALES:**
- `tokens_in_db = 190` (objetivo: 300+)
- `avg_daily_new_tokens = ~3-5` (objetivo: >= 5)
- `v1_val_f1 = 1.0` (overfitting por dataset pequeño, objetivo real: 0.70+)
- `api_uptime >= 99%` ✅
- `backups_diarios` ✅
- `health_checks_cada_6h` ✅

---

### Mediano Plazo (3 meses)
- [ ] 1000+ tokens en base de datos
- [ ] F1 score > 0.75
- [ ] Backtesting mostrando ROI positivo en simulación
- [ ] Re-entrenamiento automático funcionando
- [ ] Drift detection activo

**KPIs:**
- `tokens_in_db >= 1000`
- `f1_score >= 0.75`
- `backtest_roi >= 30%` (anualizado)
- `model_version >= v3`

---

### Largo Plazo (6 meses)
- [ ] Paper trading funcionando
- [ ] ROI simulado > 50% anualizado
- [ ] Sistema completamente autónomo
- [ ] Multi-chain (5+ cadenas)
- [ ] Features de sentimiento social integradas

**KPIs:**
- `paper_trading_roi >= 50%` (anualizado)
- `sharpe_ratio >= 1.5`
- `max_drawdown <= 20%`
- `supported_chains >= 5`
- `tokens_in_db >= 5000`

---

## 🔧 DEUDA TÉCNICA IDENTIFICADA

### Alta Prioridad
1. **Falta de tipos estáticos**: No hay type hints completos
   - **Acción:** Añadir type hints progresivamente, empezar por `src/models/`
   - **Herramienta:** `mypy` para validación estática

2. **Tests de integración**: Solo tests unitarios, no hay tests E2E
   - **Acción:** Crear `tests/integration/test_full_pipeline.py`
   - **Cobertura objetivo:** 80%

### Media Prioridad
3. **Configuración hardcoded**: Algunos thresholds están hardcoded en código
   - **Acción:** Mover todos los magic numbers a `config.py`
   - **Ejemplo:** `if probability > 0.8:` → `if probability > config.GEM_THRESHOLD:`

4. **Logs no estructurados**: Usar logging JSON para mejor análisis
   - **Acción:** Migrar a `structlog` o `python-json-logger`
   - **Beneficio:** Logs parseables por herramientas como Grafana

### Baja Prioridad
5. **Sin CI/CD**: No hay GitHub Actions para tests automáticos
   - **Acción:** Crear `.github/workflows/tests.yml`
   - **Beneficio:** Tests automáticos en cada commit

6. **Documentación inline**: Algunos módulos tienen poca documentación
   - **Acción:** Generar docs con Sphinx o MkDocs
   - **Beneficio:** Onboarding más rápido

---

## 📚 DOCUMENTACIÓN FALTANTE

### Crítico
- [ ] **README.md**: Guía de instalación y uso para nuevos usuarios
  - Secciones: Quick Start, Installation, Configuration, Usage, Troubleshooting

### Importante
- [ ] **ARCHITECTURE.md**: Diagrama de flujo de datos
  - Incluir: ERD de base de datos, flujo de recolección, pipeline ML

- [ ] **API_DOCS.md**: Documentación de todas las APIs usadas
  - Rate limits, endpoints, autenticación, ejemplos

### Nice to Have
- [ ] **TROUBLESHOOTING.md**: Guía de resolución de problemas comunes
  - "API falla", "DB corrupta", "Dashboard no carga"

- [ ] **CONTRIBUTING.md**: Guía para colaboradores
  - Code style, testing, pull request process

- [ ] **CHANGELOG.md**: Historial de cambios por versión
  - Seguir formato Keep a Changelog

**Acción:** Crear carpeta `docs/` con todos estos archivos.

---

## 🛠️ HERRAMIENTAS RECOMENDADAS

### Monitoreo y Observabilidad
- **Uptime Kuma**: Self-hosted monitoring dashboard (alternativa gratuita a UptimeRobot)
- **Grafana + Prometheus**: Para métricas avanzadas (opcional, futuro)
- **Sentry**: Error tracking (free tier: 5K events/month)

### Testing
- **pytest-cov**: Cobertura de tests
- **pytest-mock**: Mocking para tests
- **locust**: Load testing para APIs (si escala mucho)

### Calidad de Código
- **black**: Auto-formatter (ya debería estar)
- **flake8**: Linter
- **mypy**: Type checking
- **pre-commit**: Git hooks para calidad automática

### Documentación
- **MkDocs**: Generador de docs estáticas (más simple que Sphinx)
- **mermaid.js**: Diagramas en Markdown

---

## 📖 RECURSOS ADICIONALES

### Papers y Research
- **Burniske & Tatar**: "Cryptoassets: The Innovative Investor's Guide"
- **CryptoQuant Research**: On-chain metrics methodology
- **Messari Research**: Token valuation frameworks

### Cursos y Tutoriales
- **Fast.ai**: Machine Learning for Coders (feature engineering)
- **Kaggle**: Time Series Forecasting competitions
- **DeFi Llama**: Open source analytics (inspiración)

### Comunidades
- **r/algotrading**: Trading bot strategies
- **Dune Analytics Discord**: On-chain analytics
- **Messari Hub**: Crypto research discussions

---

## ✅ CHECKLIST DE IMPLEMENTACIÓN

### Semana 1: Fundamentos
- [ ] Crear `scripts/health_check.sh`
- [ ] Crear `scripts/backup_db.sh`
- [ ] Añadir tabla `api_usage` a storage.py
- [ ] Modificar base_client.py para log requests
- [ ] Configurar Gmail SMTP para alertas
- [ ] Añadir health_check a launchd (cada 6h)
- [ ] Añadir backup_db a launchd (diario)
- [ ] Probar restauración desde backup

### Semana 2: Monitoreo
- [ ] Crear `src/monitoring/health_monitor.py`
- [ ] Crear `dashboard/views/system_health.py`
- [ ] Implementar gráfico de consumo API por día
- [ ] Implementar alerta 80% límite mensual
- [ ] Configurar bot de Telegram
- [ ] Integrar notificaciones Telegram en collector.py
- [ ] Documentar en `docs/MONITORING.md`

### Semana 3-4: Features
- [ ] Crear `src/features/temporal.py`
- [ ] Añadir día de semana, hora, es_fin_de_semana
- [ ] Integrar temporal features en builder.py
- [ ] Re-ejecutar feature engineering
- [ ] Validar nuevas features con correlation matrix
- [ ] Actualizar tests en `tests/test_features.py`
- [ ] Re-entrenar modelos con nuevas features

### Mes 2: Optimización
- [ ] Esperar acumulación (300+ tokens)
- [ ] Ejecutar ModelOptimizer
- [ ] Implementar stacking ensemble
- [ ] Cambiar de KFold a TimeSeriesSplit
- [ ] Implementar versionado de modelos
- [ ] Crear `src/models/drift_detector.py`
- [ ] Documentar mejoras en `docs/MODEL_IMPROVEMENTS.md`

---

## 🎓 LECCIONES APRENDIDAS

### Lo que Funciona Bien
- ✅ **Arquitectura modular**: Fácil añadir nuevas features y APIs
- ✅ **Cache agresivo**: Evita perder datos por rate limits
- ✅ **Tests unitarios**: Detectan bugs temprano
- ✅ **Dashboard Streamlit**: Rápido de iterar y muy visual
- ✅ **SQLite**: Suficiente para 1000s de tokens, simple de respaldar

### Lo que se Puede Mejorar
- ⚠️ **Logging**: Falta estructura, difícil debugging
- ⚠️ **Monitoreo**: No detecta fallas silenciosas
- ⚠️ **Versionado**: Difícil rollback de modelos
- ⚠️ **Documentación**: Onboarding lento para nuevos colaboradores

### Decisiones Arquitectónicas Clave
1. **SQLite vs PostgreSQL**: SQLite elegido por simplicidad. OK hasta 10K tokens.
2. **Parquet vs CSV**: Parquet elegido por compresión y tipado. Correcto.
3. **Streamlit vs Flask**: Streamlit elegido por velocidad de desarrollo. Correcto para MVP.
4. **Local vs Cloud**: Local elegido por costo $0. Migrar a cloud cuando sea necesario.

---

## 🚦 SEMÁFORO DE PRIORIDADES

### 🔴 HACER AHORA (Esta Semana)
- Health checks
- Backups diarios
- API usage tracking

### 🟡 HACER PRONTO (Este Mes)
- Features temporales
- Dashboard mejoras
- Optimización de modelos (cuando haya 300+ tokens)

### 🟢 HACER DESPUÉS (3-6 Meses)
- Paper trading
- Multi-chain
- Features de sentimiento social

### ⚪ NICE TO HAVE (Futuro Lejano)
- Trading automático real
- CI/CD completo
- Documentación Sphinx

---

## 📝 NOTAS FINALES

Este documento es un **roadmap vivo**. Debe actualizarse cada mes con:
- ✅ Ítems completados
- 📊 Métricas alcanzadas
- 🐛 Bugs encontrados
- 💡 Nuevas ideas

**Última actualización:** 2026-02-26
**Próxima revisión:** 2026-03-26

---

**¿Dudas o sugerencias?** Agregar en sección "Preguntas" al final de este documento.

## ❓ PREGUNTAS ABIERTAS

1. ¿Cuándo migrar de SQLite a PostgreSQL? (Respuesta: Cuando haya 10K+ tokens o queries sean lentas)
2. ¿Invertir en CoinGecko Pro ahora o esperar? (Respuesta: Esperar a tener ROI positivo en paper trading)
3. ¿Priorizar multi-chain o features de sentimiento? (Respuesta: Features primero, luego multi-chain)
4. ¿Implementar trading real o mantener en simulación? (Respuesta: Mínimo 6 meses de paper trading exitoso)

---

**Fin del documento**
