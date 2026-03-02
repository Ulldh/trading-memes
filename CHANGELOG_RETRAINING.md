# CHANGELOG - Pipeline de Re-Entrenamiento Automático

**Fecha**: 2026-02-27
**Autor**: Claude Code + Ulises Díaz Hernández
**Mejora**: #6 - Pipeline de Re-Entrenamiento Automático (MEJORAS_PROPUESTAS.md)

---

## 📊 RESUMEN

Se implementó un sistema completo de re-entrenamiento automático que:
1. **Detecta drift** (cambios en datos que degradan modelos)
2. **Versiona modelos** automáticamente (v1, v2, v3...)
3. **Recomienda re-entrenar** cuando es necesario
4. **Permite rollback** a versiones anteriores

### Antes
- Re-entrenamiento manual sin criterios claros
- Modelos sin versionado (sobrescribían archivos)
- No había forma de saber si los modelos estaban obsoletos
- Imposible hacer rollback a versiones previas

### Después
- **Detección automática** de 4 tipos de drift
- **Versionado automático** (v1, v2, v3...) con metadata JSON
- **Script de verificación** que recomienda cuándo re-entrenar
- **Rollback fácil** a cualquier versión anterior

---

## 🆕 COMPONENTES IMPLEMENTADOS (4)

### 1. Drift Detector (`src/models/drift_detector.py`)
Detecta cuando los modelos necesitan re-entrenamiento debido a cambios en los datos.

#### Tipos de Drift Detectados

| Tipo | Método | Umbral | Descripción |
|------|--------|--------|-------------|
| **Data Drift** | KS test | p<0.05 | Cambio en distribución de features |
| **Concept Drift** | F1 score | <0.5 | Modelo predice mal en datos nuevos |
| **Volume Drift** | Conteo | +50 tokens | Acumulación de nuevos datos etiquetados |
| **Time Drift** | Días | 30+ días | Tiempo desde último entrenamiento |

#### Clase Principal: `DriftDetector`

```python
from src.models.drift_detector import DriftDetector

detector = DriftDetector(
    ks_threshold=0.05,       # p-value para KS test
    f1_threshold=0.5,        # F1 mínimo aceptable
    volume_threshold=50,     # Tokens nuevos mínimos
    days_threshold=30,       # Días máximos sin re-entrenar
)

# Detectar drift
report = detector.detect_all_drift(
    train_data=X_train,
    new_data=X_new,
    model=model,
    y_new=y_new,
    train_size=100,
    new_size=60,
    last_train_date="2026-01-01T00:00:00Z"
)

if report["needs_retraining"]:
    print(f"Razones: {report['reasons']}")
    # ['Volume drift (60 nuevos tokens)', 'Time drift (57 dias)']
```

#### Métodos Disponibles

- `detect_data_drift()`: KS test para cada feature
- `detect_concept_drift()`: Evalúa modelo en datos nuevos
- `detect_volume_drift()`: Compara tamaño de datasets
- `detect_time_drift()`: Calcula días desde último entrenamiento
- `detect_all_drift()`: Ejecuta todos y devuelve reporte

---

### 2. Versionado de Modelos (`src/models/trainer.py`)
Guarda modelos con versionado automático y metadata completa.

#### Estructura de Versiones

```
data/models/
├── v1/
│   ├── random_forest.joblib
│   ├── xgboost.joblib
│   └── metadata.json           # Metadata completa de v1
├── v2/
│   ├── random_forest.joblib
│   ├── xgboost.joblib
│   └── metadata.json
├── random_forest.joblib  -> v2/random_forest.joblib (symlink)
├── xgboost.joblib        -> v2/xgboost.joblib       (symlink)
└── latest_version.txt    # Contiene "v2"
```

#### Metadata JSON

Cada versión incluye un archivo `metadata.json` con información completa:

```json
{
  "version": "v2",
  "trained_at": "2026-02-27T16:30:00Z",
  "feature_names": ["top1_holder_pct", "return_24h", ...],
  "num_features": 56,
  "results": {
    "random_forest": {
      "cv_f1_mean": 0.63,
      "cv_f1_std": 0.05,
      "val_f1": 0.67,
      "val_accuracy": 0.68
    },
    "xgboost": {
      "val_f1": 0.59,
      "val_accuracy": 0.63
    }
  },
  "hyperparameters": {
    "random_forest": {
      "n_estimators": 300,
      "max_depth": 15,
      ...
    },
    "xgboost": {
      "n_estimators": 500,
      "max_depth": 6,
      ...
    }
  }
}
```

#### Métodos Nuevos en ModelTrainer

```python
from src.models.trainer import ModelTrainer

trainer = ModelTrainer()

# Entrenar modelos
trainer.train_all(features_df, labels_df)

# Guardar con versionado automático
version_dir = trainer.save_models_versioned()
print(f"Guardado en: {version_dir}")
# Guardado en: data/models/v3

# Cargar versión específica
metadata = trainer.load_models_versioned("v2")
print(f"Cargados: {metadata['trained_at']}")

# Cargar última versión
trainer.load_models_versioned()  # None = última

# Obtener última versión
latest = trainer.get_latest_version()
print(f"Última: {latest}")  # "v3"
```

---

### 3. Script de Verificación (`scripts/check_retrain_needed.sh`)
Script que verifica si es necesario re-entrenar y opcionalmente lo ejecuta.

#### Uso

```bash
# Solo verificar (recomendación)
./scripts/check_retrain_needed.sh

# Verificar y re-entrenar automáticamente si es necesario
./scripts/check_retrain_needed.sh --auto
```

#### Salida de Ejemplo

```
[2026-02-27 16:30:00] ==========================================
[2026-02-27 16:30:00] VERIFICACION DE RE-ENTRENAMIENTO
[2026-02-27 16:30:00] ==========================================
[2026-02-27 16:30:00] Verificando drift en modelos...
[2026-02-27 16:30:05] Resultado de drift detection:
{
  "needs_retraining": true,
  "reasons": [
    "Volume drift (60 nuevos tokens)",
    "Time drift (35 dias)"
  ],
  "volume_drift": {
    "has_drift": true,
    "new_tokens": 60,
    "threshold": 50
  },
  "time_drift": {
    "has_drift": true,
    "days_since_training": 35,
    "threshold": 30
  }
}

[2026-02-27 16:30:05]
[2026-02-27 16:30:05] ⚠️  RE-ENTRENAMIENTO RECOMENDADO
[2026-02-27 16:30:05] Razones: ["Volume drift (60 nuevos tokens)", "Time drift (35 dias)"]
[2026-02-27 16:30:05]
[2026-02-27 16:30:05] Para re-entrenar manualmente:
[2026-02-27 16:30:05]   ./scripts/retrain.sh
[2026-02-27 16:30:05]
[2026-02-27 16:30:05] ==========================================
```

---

### 4. Integración en `retrain.sh`
El script de re-entrenamiento ahora usa `save_models_versioned()` automáticamente.

#### Cambio en retrain.sh

```bash
# ANTES
trainer.save_models()
print('Modelos guardados en data/models/')

# DESPUÉS
version_dir = trainer.save_models_versioned(
    metadata={
        'script': 'retrain.sh',
        'trigger': 'manual',
    }
)
print(f'Modelos guardados en {version_dir}')
```

---

## 📁 ARCHIVOS CREADOS/MODIFICADOS

### Creados
1. **`src/models/drift_detector.py`** (540 líneas)
   - Clase `DriftDetector` con 4 tipos de detección
   - Métodos: `detect_data_drift()`, `detect_concept_drift()`, `detect_volume_drift()`, `detect_time_drift()`, `detect_all_drift()`

2. **`scripts/check_retrain_needed.sh`** (230 líneas)
   - Script bash que usa DriftDetector para verificar drift
   - Soporte para `--auto` (re-entrenar automáticamente)
   - Log detallado en `logs/check_retrain_*.log`

3. **`tests/test_drift_and_versioning.py`** (16 tests)
   - Tests para DriftDetector (11 tests)
   - Tests para versionado de modelos (5 tests)

4. **`CHANGELOG_RETRAINING.md`** (este archivo)
   - Documentación completa de la mejora

### Modificados
1. **`src/models/trainer.py`** (+250 líneas)
   - Añadidos imports: `json`, `datetime`, `os`
   - Método `_get_next_version()`: Encuentra siguiente versión
   - Método `save_models_versioned()`: Guarda con versionado
   - Método `get_latest_version()`: Obtiene última versión
   - Método `load_models_versioned()`: Carga versión específica

2. **`scripts/retrain.sh`** (1 línea modificada)
   - Cambio de `save_models()` a `save_models_versioned()`

---

## ✅ TESTS

### Nuevos Tests (16)
```bash
pytest tests/test_drift_and_versioning.py -v
```

#### DriftDetector (11 tests)
- ✅ `test_init`: Inicialización con parámetros default
- ✅ `test_init_custom_thresholds`: Inicialización con parámetros custom
- ✅ `test_detect_data_drift_no_drift`: No detecta drift con distribuciones similares
- ✅ `test_detect_data_drift_with_drift`: Detecta drift con distribuciones diferentes
- ✅ `test_detect_concept_drift`: Detecta concept drift con F1 bajo
- ✅ `test_detect_volume_drift_yes`: Detecta volume drift (+50 tokens)
- ✅ `test_detect_volume_drift_no`: No detecta volume drift (<50 tokens)
- ✅ `test_detect_time_drift_yes`: Detecta time drift (>30 días)
- ✅ `test_detect_time_drift_no`: No detecta time drift (<30 días)
- ✅ `test_detect_time_drift_no_date`: Asume drift si no hay fecha
- ✅ `test_detect_all_drift`: Ejecuta detección completa

#### ModelVersioning (5 tests)
- ✅ `test_get_next_version_empty_dir`: Devuelve v1 en directorio vacío
- ✅ `test_get_next_version_existing`: Devuelve v3 si existen v1 y v2
- ✅ `test_save_models_versioned`: Guarda modelos con versionado correcto
- ✅ `test_get_latest_version`: Obtiene última versión correctamente
- ✅ `test_load_models_versioned`: Carga versión específica correctamente

### Suite Completa
```bash
pytest tests/ -v
```

**Resultado**: **58/58 tests pasan** (antes: 42, +16 nuevos = 58 total)

---

## 🧪 PRUEBA DE INTEGRACIÓN

### Flujo Completo

```bash
# 1. Verificar si se necesita re-entrenar
./scripts/check_retrain_needed.sh

# Si recomienda re-entrenar:
# 2. Re-entrenar (crea v3 automáticamente)
./scripts/retrain.sh

# 3. Verificar que se creó v3
ls -la data/models/v3/
# random_forest.joblib  xgboost.joblib  metadata.json

# 4. Ver metadata de v3
cat data/models/v3/metadata.json | jq .

# 5. Ver última versión
cat data/models/latest_version.txt
# v3

# 6. Si v3 tiene problemas, hacer rollback a v2
python -c "
from src.models.trainer import ModelTrainer
trainer = ModelTrainer()
trainer.load_models_versioned('v2')
print('Modelos v2 cargados')
"
```

---

## 📊 IMPACTO

### Beneficios Clave

| Beneficio | Antes | Después |
|-----------|-------|---------|
| **Detección de obsolescencia** | Manual | Automática (4 tipos de drift) |
| **Versionado** | No existía | Automático (v1, v2, v3...) |
| **Metadata** | Mínima | Completa (features, métricas, hiperparámetros) |
| **Rollback** | Imposible | Fácil (cualquier versión) |
| **Recomendación** | Subjetiva | Objetiva (drift detector) |
| **Auditoría** | Difícil | Fácil (metadata.json por versión) |

### Casos de Uso

1. **Re-entrenamiento programado**: Ejecutar `check_retrain_needed.sh --auto` diariamente via launchd
2. **Auditoría de modelos**: Revisar `metadata.json` para ver evolución de métricas
3. **Rollback rápido**: Si v3 tiene problemas, cargar v2 inmediatamente
4. **Comparación de versiones**: Comparar F1 score entre v1, v2, v3
5. **Investigación de drift**: Analizar qué features cambiaron entre versiones

---

## 🔄 FLUJO RECOMENDADO

### Setup Inicial (Una vez)

```bash
# 1. Re-entrenar una vez para crear v1
./scripts/retrain.sh

# 2. Configurar verificación diaria (opcional)
# Añadir a launchd:
# ./scripts/check_retrain_needed.sh >> logs/drift_check.log 2>&1
```

### Operación Normal

```bash
# Cada semana (o cuando se acumulen tokens nuevos):
./scripts/check_retrain_needed.sh

# Si recomienda re-entrenar:
./scripts/retrain.sh

# Verificar mejora en métricas:
python -c "
import json
from pathlib import Path

# Cargar v2 y v3
v2_meta = json.load(open('data/models/v2/metadata.json'))
v3_meta = json.load(open('data/models/v3/metadata.json'))

# Comparar F1
f1_v2 = v2_meta['results']['random_forest']['val_f1']
f1_v3 = v3_meta['results']['random_forest']['val_f1']

print(f'v2 F1: {f1_v2:.4f}')
print(f'v3 F1: {f1_v3:.4f}')
print(f'Mejora: {f1_v3 - f1_v2:+.4f}')
"
```

---

## 🧠 CONCEPTOS TÉCNICOS (Para Neófitos)

### ¿Qué es Drift?
**Drift** = Cambio en los datos que hace que un modelo entrenado se vuelva menos preciso con el tiempo.

**Analogía**: Imagina que entrenas un modelo para predecir el clima en verano. Si lo usas en invierno, va a fallar porque los datos cambiaron (drift).

### Tipos de Drift

#### Data Drift
**¿Qué es?** La distribución de las features (X) cambia.

**Ejemplo**:
- Entrenamiento: Memecoins con market cap promedio $100K
- Ahora: Memecoins con market cap promedio $1M

**Cómo se detecta**: KS test (Kolmogorov-Smirnov test)
- Compara dos distribuciones
- p-value < 0.05 = distribuciones significativamente diferentes

#### Concept Drift
**¿Qué es?** La relación entre features y target (X → y) cambia.

**Ejemplo**:
- Antes: Tokens con alto volumen = gems
- Ahora: Tokens con alto volumen = rugs (manipulación)

**Cómo se detecta**: F1 score en datos nuevos
- Si F1 < 0.5 = modelo predice mal

#### Volume Drift
**¿Qué es?** Se acumulan muchos datos nuevos que no están en el modelo.

**Ejemplo**:
- Modelo entrenado con 100 tokens
- Ahora hay 160 tokens (+60 nuevos)

**Cómo se detecta**: Conteo simple
- Si nuevos tokens >= 50 = re-entrenar para incluirlos

#### Time Drift
**¿Qué es?** Ha pasado mucho tiempo desde el último entrenamiento.

**Ejemplo**:
- Último entrenamiento: hace 45 días
- Umbral: 30 días

**Cómo se detecta**: Diferencia de fechas
- Si días >= 30 = re-entrenar periódicamente

### ¿Por qué Versionado?
**Versionado** = Guardar cada modelo entrenado en una carpeta separada con metadata.

**Beneficios**:
1. **Auditoría**: Saber cuándo, cómo y con qué datos se entrenó cada versión
2. **Rollback**: Si v3 falla, volver a v2 inmediatamente
3. **Comparación**: Ver evolución de métricas (F1, accuracy) entre versiones
4. **Reproducibilidad**: Saber exactamente qué hiperparámetros usó cada versión

---

## 📚 REFERENCIAS

### Papers
- **Data Drift**: "Learning under Concept Drift" - Tsymbal (2004)
- **KS Test**: "On a Test of Whether one of Two Random Variables is Stochastically Larger than the Other" - Kolmogorov-Smirnov (1933)

### Libros
- **Model Monitoring**: "Reliable Machine Learning" - Todd Underwood et al. (O'Reilly, 2022)
- **MLOps**: "Introducing MLOps" - Mark Treveil et al. (O'Reilly, 2020)

### Herramientas Relacionadas
- **Evidently AI**: Open source drift detection library
- **Great Expectations**: Data validation framework
- **MLflow**: Model versioning and tracking

---

## 📝 NOTAS FINALES

### Decisiones de Diseño

1. **KS test en lugar de distribución**:
   - KS test es no-paramétrico (no asume distribución normal)
   - Funciona bien con cualquier tipo de feature

2. **F1 < 0.5 como umbral de concept drift**:
   - F1 = 0.5 es el mínimo aceptable (apenas mejor que azar)
   - Si cae por debajo, el modelo es inútil

3. **50 tokens como umbral de volume drift**:
   - ~50% del dataset original (91 tokens)
   - Suficientes datos nuevos para mejorar el modelo significativamente

4. **30 días como umbral de time drift**:
   - Compromiso entre no re-entrenar demasiado seguido y mantener modelo actualizado
   - Puede ajustarse según la velocidad de cambio del mercado crypto

### Limitaciones Conocidas

1. **Data drift simplificado**: No guardamos los datos de entrenamiento originales, por lo que el data drift detection está deshabilitado por ahora. Solución futura: guardar `X_train` en cada versión.

2. **Concept drift requiere labels nuevos**: Solo funciona si hay tokens nuevos con labels (requiere etiquetado manual).

3. **Symlinks en Windows**: Pueden fallar si no hay permisos de administrador. Solución: copiar archivos en lugar de symlinks.

### Próximas Mejoras

- [ ] Guardar `X_train` en cada versión para habilitar data drift detection completo
- [ ] Dashboard de versiones (comparar métricas visualmente)
- [ ] A/B testing entre versiones (v2 vs v3 en producción)
- [ ] Drift alerts vía Telegram cuando se detecte drift crítico

---

**Fin del documento**

¿Preguntas o mejoras? Documentar en issue de GitHub o en MEJORAS_PROPUESTAS.md
