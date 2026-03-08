#!/bin/bash
# full_refresh.sh - Refresh completo: features + labels + modelos.
#
# Usar despues de 2-4 semanas de recopilacion automatica (Fase 3),
# cuando haya 300+ tokens con OHLCV acumulado.
#
# Ejecuta:
#   1. Stats ANTES
#   2. build_all_features() para TODOS los tokens
#   3. Auto-label tokens con >= 7 dias OHLCV
#   4. Re-entrena modelos RF + XGBoost
#   5. SHAP analysis
#   6. Stats DESPUES + comparacion
#
# Uso: ./scripts/full_refresh.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"

DATE_STAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/full_refresh_${DATE_STAMP}.log"

VENV_DIR="${PROJECT_DIR}/.venv"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log "=========================================="
log "FULL REFRESH INICIADO"
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
log "--- ESTADISTICAS ANTES DEL REFRESH ---"
python -c "
from src.data.storage import Storage
s = Storage()
stats_antes = s.stats()
for k, v in stats_antes.items():
    print(f'  {k}: {v}')

# Guardar para comparacion posterior
import json
with open('logs/stats_before.json', 'w') as f:
    json.dump(stats_antes, f)
" 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 2: Re-calcular features para TODOS los tokens
# ============================================================
log "Calculando features para TODOS los tokens..."
python -c "
from src.data.storage import Storage
from src.features.builder import FeatureBuilder

storage = Storage()
builder = FeatureBuilder(storage)

# Calcular features para todos los tokens
features_df = builder.build_all_features()
print(f'Features calculados: {features_df.shape[0]} tokens x {features_df.shape[1]} features')

# Guardar en storage y parquet
storage.save_features_df(features_df)
features_df.to_parquet('data/processed/features.parquet')
print('Features guardados en DB y parquet')
" 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 3: Auto-label tokens
# ============================================================
log "Auto-etiquetando tokens..."
python -c "
from src.data.storage import Storage
from src.models.labeler import Labeler

storage = Storage()
labeler = Labeler(storage)

labels_df = labeler.label_all_tokens()
print(f'Tokens etiquetados: {len(labels_df)}')
if not labels_df.empty:
    print('Distribucion:')
    print(labels_df['label_multi'].value_counts().to_string())
    print()
    print(f'Binario: {(labels_df[\"label_binary\"]==1).sum()} gems, {(labels_df[\"label_binary\"]==0).sum()} no-gems')
" 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 4: Re-entrenar modelos (directamente, sin llamar retrain.sh
#          que repetiria features+labels)
# ============================================================
log "Re-entrenando modelos..."
python -c "
import json
import pandas as pd
from pathlib import Path
from src.data.storage import Storage
from src.models.trainer import ModelTrainer

storage = Storage()
features_df = storage.get_features_df()
labels_df = storage.query('SELECT * FROM labels')

if features_df.empty or labels_df.empty:
    print('ERROR: No hay suficientes datos para entrenar')
    exit(1)

print(f'Features: {features_df.shape}, Labels: {labels_df.shape}')

trainer = ModelTrainer()
results = trainer.train_all(features_df, labels_df, target='label_binary')

version_dir = trainer.save_models_versioned(
    metadata={'script': 'full_refresh.sh', 'trigger': 'manual'}
)
print(f'Modelos guardados en {version_dir}')

# Guardar resultados y feature columns
eval_results = {}
for name, metrics in results.items():
    if isinstance(metrics, dict):
        eval_results[name] = {k: v for k, v in metrics.items()
                               if isinstance(v, (int, float, str, list, dict, type(None)))}
eval_path = Path('data/models/evaluation_results.json')
with open(eval_path, 'w') as f:
    json.dump(eval_results, f, indent=2, default=str)

feature_cols_path = Path('data/models/feature_columns.json')
with open(feature_cols_path, 'w') as f:
    json.dump(trainer.feature_names, f)

if hasattr(trainer, '_X_train'):
    trainer._X_train.to_csv('data/processed/X_train.csv', index=False)
    trainer._y_train.to_csv('data/processed/y_train.csv', index=False)
print('Training completado')
" 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 5: Stats DESPUES + comparacion
# ============================================================
log "--- ESTADISTICAS DESPUES DEL REFRESH ---"
python -c "
import json
from src.data.storage import Storage

s = Storage()
stats_despues = s.stats()

# Cargar stats anteriores
try:
    with open('logs/stats_before.json', 'r') as f:
        stats_antes = json.load(f)
except FileNotFoundError:
    stats_antes = {}

print('Tabla               Antes  -> Despues  (Cambio)')
print('-' * 55)
for k, v_despues in stats_despues.items():
    v_antes = stats_antes.get(k, 0)
    cambio = v_despues - v_antes
    signo = '+' if cambio > 0 else ''
    print(f'  {k:20s} {v_antes:6d} -> {v_despues:6d}  ({signo}{cambio})')
" 2>&1 | tee -a "${LOG_FILE}"

log "=========================================="
log "FULL REFRESH COMPLETADO"
log "Log: ${LOG_FILE}"
log "=========================================="
