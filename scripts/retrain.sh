#!/bin/bash
# retrain.sh - Re-entrenamiento manual de modelos ML.
#
# Ejecuta el pipeline completo de ML:
#   1. Muestra stats ANTES
#   2. Re-calcula features para TODOS los tokens
#   3. Re-etiqueta tokens con suficientes datos OHLCV
#   4. Re-entrena Random Forest + XGBoost
#   5. Genera SHAP analysis
#   6. Muestra stats DESPUES + comparacion
#
# Uso: ./scripts/retrain.sh

set -euo pipefail

# ============================================================
# CONFIGURACION
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"

DATE_STAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/retrain_${DATE_STAMP}.log"

VENV_DIR="${PROJECT_DIR}/.venv"

# ============================================================
# FUNCIONES
# ============================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# ============================================================
# INICIO
# ============================================================

log "=========================================="
log "RE-ENTRENAMIENTO DE MODELOS INICIADO"
log "=========================================="

# Activar entorno virtual
if [ -d "${VENV_DIR}" ]; then
    source "${VENV_DIR}/bin/activate"
    log "Entorno virtual activado: $(python --version)"
else
    log "ERROR: Entorno virtual no encontrado en ${VENV_DIR}"
    exit 1
fi

cd "${PROJECT_DIR}"

# ============================================================
# PASO 1: Stats ANTES
# ============================================================
log "--- ESTADISTICAS ANTES ---"
python -c "
from src.data.storage import Storage
s = Storage()
stats = s.stats()
for k, v in stats.items():
    print(f'  {k}: {v}')
" 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 2: Re-calcular features para TODOS los tokens
# ============================================================
log "Calculando features para todos los tokens..."
python -c "
from src.data.storage import Storage
from src.features.builder import FeatureBuilder

storage = Storage()
builder = FeatureBuilder(storage)

# Calcular features para todos
features_df = builder.build_all_features()
print(f'Features calculados: {features_df.shape[0]} tokens x {features_df.shape[1]} features')

# Guardar en storage y parquet
storage.save_features_df(features_df)
features_df.to_parquet('data/processed/features.parquet')
print('Features guardados en DB y parquet')
" 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 3: Re-etiquetar tokens
# ============================================================
log "Re-etiquetando tokens con datos suficientes..."
python -c "
from src.data.storage import Storage
from src.models.labeler import Labeler

storage = Storage()
labeler = Labeler(storage)

labels_df = labeler.label_all_tokens()
print(f'Tokens etiquetados: {len(labels_df)}')
if not labels_df.empty:
    print(labels_df['label_multi'].value_counts().to_string())
" 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 4: Re-entrenar modelos
# ============================================================
log "Re-entrenando Random Forest + XGBoost..."
python -c "
import json
import pandas as pd
from pathlib import Path
from src.data.storage import Storage
from src.models.trainer import ModelTrainer

storage = Storage()

# Cargar features y labels
features_df = storage.get_features_df()
labels_df = storage.query('SELECT * FROM labels')

if features_df.empty or labels_df.empty:
    print('ERROR: No hay suficientes datos para entrenar')
    exit(1)

print(f'Features: {features_df.shape}, Labels: {labels_df.shape}')

# Entrenar
trainer = ModelTrainer()
results = trainer.train_all(features_df, labels_df, target='label_binary')

# Validar F1 minimo antes de guardar
rf_results = results.get('random_forest', {})
xgb_results = results.get('xgboost', {})
rf_f1 = rf_results.get('cv_f1', rf_results.get('val_f1', 0))
xgb_f1 = xgb_results.get('cv_f1', xgb_results.get('val_f1', 0))
best_f1 = max(rf_f1, xgb_f1)
print(f'Mejor F1: {best_f1:.3f} (RF={rf_f1:.3f}, XGB={xgb_f1:.3f})')
if best_f1 < 0.10:
    print(f'ERROR: F1 demasiado bajo ({best_f1:.3f}). Abortando guardado.')
    exit(1)

# Guardar modelos con versionado
version_dir = trainer.save_models_versioned(
    metadata={
        'script': 'retrain.sh',
        'trigger': 'manual',
    }
)
print(f'Modelos guardados en {version_dir}')

# Guardar resultados de evaluacion
eval_results = {}
for name, metrics in results.items():
    if isinstance(metrics, dict):
        # Filtrar valores no serializables
        eval_results[name] = {k: v for k, v in metrics.items()
                               if isinstance(v, (int, float, str, list, dict, type(None)))}

eval_path = Path('data/models/evaluation_results.json')
with open(eval_path, 'w') as f:
    json.dump(eval_results, f, indent=2, default=str)
print(f'Resultados guardados en {eval_path}')

# Guardar X_train y y_train para SHAP
if hasattr(trainer, '_X_train'):
    trainer._X_train.to_csv('data/processed/X_train.csv', index=False)
    trainer._y_train.to_csv('data/processed/y_train.csv', index=False)
    print('X_train y y_train guardados')

# Guardar feature columns
feature_cols_path = Path('data/models/feature_columns.json')
with open(feature_cols_path, 'w') as f:
    json.dump(trainer.feature_names, f)
print(f'Feature columns guardados en {feature_cols_path}')
" 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 5: Sensitivity analysis del labeler
# ============================================================
log "Ejecutando sensitivity analysis del labeler..."
python -c "
from src.data.storage import Storage
from src.models.labeler import Labeler
import pandas as pd

storage = Storage()
labeler = Labeler(storage)

# Ejecutar sensitivity analysis si el metodo existe
if hasattr(labeler, 'sensitivity_analysis'):
    sa_df = labeler.sensitivity_analysis()
    if sa_df is not None and not sa_df.empty:
        sa_df.to_csv('data/processed/sensitivity_analysis.csv', index=False)
        print(f'Sensitivity analysis completado: {len(sa_df)} variaciones')
        print(sa_df.to_string(index=False))
    else:
        print('Sensitivity analysis devolvio datos vacios')
else:
    print('Labeler no tiene metodo sensitivity_analysis (skipping)')

# Mostrar threshold optimo si existe
from config import ML_CONFIG
threshold = ML_CONFIG.get('optimal_threshold')
if threshold:
    print(f'Threshold optimo configurado: {threshold}')
else:
    print('Threshold optimo: no configurado (usando default 0.5)')
" 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 6: SHAP analysis
# ============================================================
log "Generando analisis SHAP..."
python -c "
import pandas as pd
import joblib
import matplotlib
matplotlib.use('Agg')  # Backend sin GUI para scripts
import matplotlib.pyplot as plt
from pathlib import Path

# Cargar modelo y datos
models_dir = Path('data/models')
processed_dir = Path('data/processed')

try:
    rf_model = joblib.load(models_dir / 'random_forest.joblib')
    X_train = pd.read_csv(processed_dir / 'X_train.csv')

    from src.models.explainer import SHAPExplainer
    explainer = SHAPExplainer(rf_model, X_train)

    # Top features
    top_features = explainer.get_top_features(X_train, n=15)
    top_features.to_csv(processed_dir / 'shap_feature_importance.csv', index=False)
    print('SHAP feature importance guardado')

    # Summary plot
    shap_values = explainer.get_shap_values(X_train)
    import shap
    plt.figure(figsize=(12, 8))
    shap.summary_plot(shap_values, X_train, max_display=15, show=False)
    plt.tight_layout()
    plt.savefig(processed_dir / 'shap_summary_plot.png', dpi=150, bbox_inches='tight')
    plt.close()
    print('SHAP summary plot guardado')

except Exception as e:
    print(f'SHAP analysis fallo (no critico): {e}')
" 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 7: Stats DESPUES
# ============================================================
log "--- ESTADISTICAS DESPUES ---"
python -c "
from src.data.storage import Storage
s = Storage()
stats = s.stats()
for k, v in stats.items():
    print(f'  {k}: {v}')
" 2>&1 | tee -a "${LOG_FILE}"

log "=========================================="
log "RE-ENTRENAMIENTO COMPLETADO"
log "Log guardado en: ${LOG_FILE}"
log "=========================================="
