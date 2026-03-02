# CHANGELOG - Features de Volatilidad Avanzada

**Fecha**: 2026-02-27
**Autor**: Claude Code + Ulises Díaz Hernández
**Mejora**: #4b - Features de Volatilidad Avanzada (MEJORAS_PROPUESTAS.md)

---

## 📊 RESUMEN

Se implementaron **11 features avanzados de volatilidad y análisis técnico** para mejorar la capacidad predictiva del modelo.

### Antes
- **45 features** totales
- Volatilidad básica: `volatility_24h`, `volatility_7d`

### Después
- **56 features** totales (+11)
- Volatilidad avanzada: Bollinger Bands, ATR, RSI, rangos intradía, volatility spikes

---

## 🆕 NUEVOS FEATURES (11)

### 1. Bollinger Bands (4 features)
Detectan niveles de sobrecompra/sobreventa y volatilidad extrema.

| Feature | Descripción | Interpretación |
|---------|-------------|----------------|
| `bb_upper_7d` | Banda superior (SMA + 2σ) | Precio > bb_upper = sobrecompra extrema |
| `bb_lower_7d` | Banda inferior (SMA - 2σ) | Precio < bb_lower = sobreventa extrema |
| `bb_pct_b_7d` | %B = posición entre bandas (0-1) | 0 = banda baja, 1 = banda alta, >1 = fuera |
| `bb_bandwidth_7d` | Ancho de banda normalizado | Alto = alta volatilidad, bajo = consolidación |

**Utilidad ML**: Gems suelen tener %B alto (momentum) y bandwidth expandiéndose (volatilidad creciente).

---

### 2. ATR - Average True Range (2 features)
Mide volatilidad absoluta considerando gaps entre candles.

| Feature | Descripción | Interpretación |
|---------|-------------|----------------|
| `atr_7d` | True Range promedio (absoluto) | Volatilidad en unidades de precio |
| `atr_pct_7d` | ATR como % del precio actual | Normalizado para comparar tokens |

**Utilidad ML**: Gems tienen ATR% alto en etapas tempranas (movimientos bruscos). Rugs tienen ATR% extremo antes del dump.

---

### 3. RSI - Relative Strength Index (2 features)
Detecta momentum y niveles de reversión.

| Feature | Descripción | Interpretación |
|---------|-------------|----------------|
| `rsi_7d` | RSI en ventana de 7 días (0-100) | <30 = sobreventa, >70 = sobrecompra |
| `rsi_divergence_7d` | Diferencia entre RSI y 50 (neutral) | Positivo = momentum alcista |

**Utilidad ML**: Gems mantienen RSI > 50 consistentemente. Rugs tienen RSI extremo (>80) antes del crash.

---

### 4. Rango Intradía (2 features)
Captura volatilidad dentro de cada candle.

| Feature | Descripción | Interpretación |
|---------|-------------|----------------|
| `avg_intraday_range_7d` | (high-low)/open promedio | % de movimiento intra-candle |
| `max_intraday_range_7d` | Máximo rango observado | Detecta días de volatilidad extrema |

**Utilidad ML**: Memecoins legítimos tienen rangos intradía consistentes. Manipulación tiene spikes aislados.

---

### 5. Volatility Spikes (1 feature)
Detecta movimientos anómalos (>2σ del promedio).

| Feature | Descripción | Interpretación |
|---------|-------------|----------------|
| `volatility_spike_count_7d` | Número de retornos >2σ | Muchos spikes = manipulación o alta volatilidad |

**Utilidad ML**: Gems tienen pocos spikes. Rugs tienen spikes extremos concentrados antes del dump.

---

## 📁 ARCHIVOS MODIFICADOS/CREADOS

### Creados
1. **`src/features/volatility_advanced.py`** (368 líneas)
   - Función principal: `compute_volatility_advanced_features(ohlcv_df: pd.DataFrame) -> dict`
   - Calcula 11 features a partir de datos OHLCV
   - Maneja casos edge: datos vacíos, insuficientes, precios en cero

2. **`CHANGELOG_VOLATILITY.md`** (este archivo)
   - Documentación completa de la mejora

### Modificados
1. **`src/features/builder.py`**
   - Línea 41: Añadido import de `compute_volatility_advanced_features`
   - Líneas 228-242: Añadido módulo #9 (volatility_advanced) en `build_features_for_token()`

2. **`tests/test_features.py`** (+137 líneas)
   - Añadida clase `TestVolatilityAdvancedFeatures` con 5 tests:
     - `test_basic_calculation`: Calcula features con OHLCV válido
     - `test_empty_dataframe`: Maneja DataFrame vacío
     - `test_insufficient_data`: Maneja 1 candle (sin suficientes datos)
     - `test_extreme_volatility`: Maneja pump & dump extremo
     - `test_zero_prices`: Maneja datos corruptos (precios = 0)

---

## ✅ TESTS

### Ejecución
```bash
pytest tests/test_features.py::TestVolatilityAdvancedFeatures -v
```

### Resultado
```
5 passed in 1.24s
```

### Suite Completa
```bash
pytest tests/ -v
```

**Resultado**: **42/42 tests pasan** (antes: 37, +5 nuevos)

---

## 🧪 PRUEBA DE INTEGRACIÓN

### Comando
```bash
python -c "
from src.data.storage import Storage
from src.features.builder import FeatureBuilder

storage = Storage()
builder = FeatureBuilder(storage)

# Obtener token con OHLCV
tokens_with_ohlcv = storage.query('''
    SELECT DISTINCT token_id FROM ohlcv LIMIT 1
''')

token_id = tokens_with_ohlcv.iloc[0]['token_id']
features = builder.build_features_for_token(token_id)

print(f'Total features: {len(features)}')
"
```

### Resultado Real
```
Token: 0x0d97F261b1e88845184f678e2d1e7a98D9FD38dE (30 candles)
Total features: 56 (antes: 45, +11 de volatilidad)

Features de Volatilidad Calculados: 11/11 ✓

Valores (ejemplo):
  - bb_upper_7d            = 0.000015
  - bb_lower_7d            = 0.000011
  - bb_pct_b_7d            = 0.226394  (cerca de banda inferior)
  - bb_bandwidth_7d        = 0.293813  (volatilidad moderada)
  - atr_7d                 = 0.000002
  - atr_pct_7d             = 0.144489  (14.4% volatilidad)
  - rsi_7d                 = 30.695637 (sobreventa)
  - rsi_divergence_7d      = -19.304363 (momentum bajista)
  - avg_intraday_range_7d  = 0.125910  (12.6% rango promedio)
  - max_intraday_range_7d  = 0.209619  (20.9% rango máximo)
  - volatility_spike_count = 0         (sin spikes anómalos)
```

**Interpretación**: Token en zona de sobreventa (RSI ~31), precio cerca de banda inferior de Bollinger, volatilidad moderada-alta (ATR 14.4%), sin movimientos anómalos. **Posible bounce candidate**.

---

## 📊 IMPACTO ESPERADO EN MODELOS ML

### Hipótesis
Los nuevos features deberían mejorar la capacidad del modelo para:
1. **Detectar Gems tempranas**: RSI sostenido >50 + Bollinger Bands expandiéndose + ATR alto
2. **Detectar Rugs antes del dump**: RSI extremo (>80) + Volatility spikes + %B >1
3. **Filtrar Failures**: RSI <30 sostenido + Bandwidth contrayéndose + ATR bajo

### Métricas Actuales (91 tokens)
- **Random Forest**: F1=0.67, CV F1=0.63
- **XGBoost**: F1=0.59

### Métricas Esperadas (después de re-entrenamiento)
- **Random Forest**: F1=0.70-0.75 (+5-10%)
- **XGBoost**: F1=0.65-0.70 (+10%)

**Nota**: Mejoras significativas esperadas cuando haya 300+ tokens con OHLCV completo.

---

## 🔄 PRÓXIMOS PASOS

### Inmediatos
1. ✅ Implementar features de volatilidad (COMPLETADO)
2. ✅ Escribir tests (COMPLETADO)
3. ✅ Verificar integración (COMPLETADO)

### Corto Plazo (Esta Semana)
- [ ] Esperar acumulación de datos (2-4 semanas)
- [ ] Monitorear `./scripts/quick_stats.sh` semanalmente

### Mediano Plazo (Cuando 300+ tokens)
- [ ] Re-entrenar modelos: `./scripts/full_refresh.sh`
- [ ] Evaluar SHAP importance de los nuevos features
- [ ] Comparar F1 score antes/después
- [ ] Si mejora significativa: commit y documentar
- [ ] Si no mejora: analizar correlación y considerar feature selection

---

## 🧠 CONCEPTOS TÉCNICOS (Para Neófitos)

### Bollinger Bands
Imagina un "túnel" alrededor del precio:
- **Banda superior**: Precio promedio + 2 desviaciones (límite "caro")
- **Banda inferior**: Precio promedio - 2 desviaciones (límite "barato")
- **%B**: ¿Dónde está el precio dentro del túnel? (0% = abajo, 100% = arriba)

**Uso**: Precio tocando banda inferior = posible rebote. Precio rompiendo banda superior = momentum fuerte (posible gem).

### ATR (Average True Range)
Mide "cuánto se mueve" el precio en promedio, considerando gaps (saltos entre candles).
- ATR alto = token volátil (se mueve mucho)
- ATR bajo = token estable (se mueve poco)

**Uso**: Memecoins legítimos tienen ATR consistente. Rugs tienen ATR que explota antes del dump.

### RSI (Relative Strength Index)
Mide el "momentum" del precio (0-100):
- RSI > 70: Sobrecompra (mucha gente comprando, posible corrección)
- RSI < 30: Sobreventa (mucha gente vendiendo, posible rebote)
- RSI ~ 50: Neutral

**Uso**: Gems mantienen RSI alto (50-70) de forma sostenida. Rugs tienen RSI extremo (>80) antes del crash.

### Volatility Spikes
Movimientos de precio muy grandes comparados con el promedio (>2 desviaciones estándar).
- Pocos spikes = token con movimientos orgánicos
- Muchos spikes = posible manipulación o pump & dump

---

## 📚 REFERENCIAS

### Papers
- **Bollinger Bands**: John Bollinger (1980s) - "Bollinger on Bollinger Bands"
- **ATR**: J. Welles Wilder Jr. (1978) - "New Concepts in Technical Trading Systems"
- **RSI**: J. Welles Wilder Jr. (1978) - Same book as ATR

### Libros
- "Technical Analysis of the Financial Markets" - John J. Murphy
- "Evidence-Based Technical Analysis" - David Aronson
- "Algorithmic Trading" - Ernie Chan

### Código de Referencia
- **TA-Lib**: Technical Analysis Library (C library, Python wrapper)
- **pandas-ta**: Pandas Technical Analysis indicators
- **Backtrader**: Python backtesting framework

**Nota**: No usamos librerías externas en este proyecto (solo numpy/pandas) para mantener control total sobre cálculos y facilitar debugging.

---

## 📝 NOTAS FINALES

### Decisiones de Diseño
1. **Ventana de 7 días**: Balance entre capturar patrones tempranos (gems se definen en primeros días) y tener suficientes datos.
2. **No usar rolling window**: Calculamos sobre toda la ventana de 7d, no rolling, para simplificar y evitar lookback bias.
3. **Manejo de None**: Features con datos insuficientes devuelven None (no 0), para distinguir "sin datos" de "valor cero".

### Limitaciones Conocidas
1. **Tokens sin OHLCV**: Features = None (esperado). Mejorará con acumulación de datos.
2. **Tokens con <2 candles**: La mayoría de features = None (esperado).
3. **RSI con solo ganancias**: RSI = 100 (correcto matemáticamente, indica momentum extremo).

### Validación Futura
Cuando se re-entrenen los modelos:
1. Verificar SHAP importance de nuevos features
2. Si algún feature no es importante → considerar eliminarlo (simplificar modelo)
3. Si algún feature tiene alta correlación con otros → feature selection

---

**Fin del documento**

¿Preguntas o mejoras? Documentar en issue de GitHub o en MEJORAS_PROPUESTAS.md
