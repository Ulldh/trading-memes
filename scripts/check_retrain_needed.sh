#!/bin/bash
# check_retrain_needed.sh - Verifica si los modelos necesitan re-entrenamiento.
#
# Este script usa DriftDetector para verificar 4 condiciones:
#   1. Data Drift: Cambio en distribucion de features (KS test)
#   2. Concept Drift: F1 score bajo en tokens nuevos
#   3. Volume Drift: +50 tokens nuevos etiquetados
#   4. Time Drift: 30+ dias desde ultimo entrenamiento
#
# Si alguna condicion se cumple, imprime recomendacion de re-entrenar
# y opcionalmente ejecuta el re-entrenamiento automaticamente.
#
# Uso:
#   ./scripts/check_retrain_needed.sh              # Solo verifica
#   ./scripts/check_retrain_needed.sh --auto       # Re-entrena si es necesario

set -euo pipefail

# ============================================================
# CONFIGURACION
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"

DATE_STAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/check_retrain_${DATE_STAMP}.log"

VENV_DIR="${PROJECT_DIR}/.venv"

# Flag: auto re-train si es necesario
AUTO_RETRAIN=false
if [[ "${1:-}" == "--auto" ]]; then
    AUTO_RETRAIN=true
fi

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
log "VERIFICACION DE RE-ENTRENAMIENTO"
log "=========================================="

# Activar entorno virtual
if [ -d "${VENV_DIR}" ]; then
    source "${VENV_DIR}/bin/activate"
else
    log "ERROR: Entorno virtual no encontrado en ${VENV_DIR}"
    exit 1
fi

cd "${PROJECT_DIR}"

# ============================================================
# VERIFICAR DRIFT
# ============================================================

log "Verificando drift en modelos..."

# Ejecutar script Python que usa DriftDetector
DRIFT_RESULT=$(python -c "
import sys
import json
import pandas as pd
from pathlib import Path

from src.data.storage import Storage
from src.models.drift_detector import DriftDetector
from src.models.trainer import ModelTrainer

# ============================================================
# 1. CARGAR DATOS
# ============================================================

storage = Storage()

# Features actuales (usados en entrenamiento)
try:
    features_df = storage.get_features_df()
    if features_df.empty:
        print('ERROR: No hay features en DB')
        sys.exit(1)
except Exception as e:
    print(f'ERROR al cargar features: {e}')
    sys.exit(1)

# Labels actuales
labels_df = storage.query('SELECT * FROM labels')
if labels_df.empty:
    print('ERROR: No hay labels en DB')
    sys.exit(1)

# ============================================================
# 2. CARGAR METADATA DE ULTIMO ENTRENAMIENTO
# ============================================================

models_dir = Path('data/models')
trainer = ModelTrainer()

try:
    latest_version = trainer.get_latest_version()
    if latest_version:
        metadata = trainer.load_models_versioned(latest_version)
        train_date = metadata.get('trained_at')
        train_features = metadata.get('feature_names', [])
        train_size = metadata.get('results', {}).get('data_info', {}).get('n_train', 0)

        # Cargar modelo para concept drift
        model = trainer.models.get('random_forest')
    else:
        print('WARNING: No hay versiones previas. Recomendando re-entrenar.')
        result = {
            'needs_retraining': True,
            'reasons': ['No hay modelos previos entrenados']
        }
        print(json.dumps(result))
        sys.exit(0)

except Exception as e:
    print(f'WARNING: Error cargando metadata: {e}')
    train_date = None
    train_features = []
    train_size = 0
    model = None

# ============================================================
# 3. IDENTIFICAR DATOS NUEVOS
# ============================================================

# Merge features y labels
merged_df = features_df.merge(
    labels_df[['token_id', 'label_binary']],
    left_index=True,
    right_on='token_id',
    how='inner'
)

# Separar en train (usados antes) y new (disponibles ahora)
# Simplificacion: usar todos los datos actuales como 'new'
# (idealmente, deberiamos rastrear que tokens se usaron en entrenamiento)
new_data = merged_df.drop(columns=['token_id', 'label_binary'])
y_new = merged_df['label_binary']

new_size = len(merged_df)

# ============================================================
# 4. EJECUTAR DRIFT DETECTOR
# ============================================================

detector = DriftDetector(
    ks_threshold=0.05,
    f1_threshold=0.5,
    volume_threshold=50,
    days_threshold=30,
)

drift_report = detector.detect_all_drift(
    train_data=None,  # No tenemos los datos de entrenamiento originales
    new_data=None,    # Saltamos data drift por ahora
    model=model,
    y_new=y_new if model else None,
    train_size=train_size,
    new_size=new_size,
    last_train_date=train_date,
)

# ============================================================
# 5. DEVOLVER RESULTADO
# ============================================================

# Serializar a JSON
result = {
    'needs_retraining': drift_report['needs_retraining'],
    'reasons': drift_report['reasons'],
    'concept_drift': drift_report.get('concept_drift', {}),
    'volume_drift': drift_report.get('volume_drift', {}),
    'time_drift': drift_report.get('time_drift', {}),
    'current_tokens': new_size,
    'latest_version': latest_version if 'latest_version' in dir() else None,
}

print(json.dumps(result, default=str))
" 2>&1)

# Verificar si el comando fallo
if [[ $? -ne 0 ]]; then
    log "ERROR: Fallo la verificacion de drift"
    log "${DRIFT_RESULT}"
    exit 1
fi

# Parsear resultado JSON
NEEDS_RETRAIN=$(echo "${DRIFT_RESULT}" | grep -o '"needs_retraining": *[^,}]*' | sed 's/.*: *//')
REASONS=$(echo "${DRIFT_RESULT}" | grep -o '"reasons": *\[[^\]]*\]' | sed 's/.*: *//')

log "Resultado de drift detection:"
echo "${DRIFT_RESULT}" | python -m json.tool 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# DECISION: ¿RE-ENTRENAR?
# ============================================================

if [[ "${NEEDS_RETRAIN}" == "true" ]]; then
    log ""
    log "⚠️  RE-ENTRENAMIENTO RECOMENDADO"
    log "Razones: ${REASONS}"

    if [[ "${AUTO_RETRAIN}" == "true" ]]; then
        log ""
        log "Ejecutando re-entrenamiento automatico..."
        "${PROJECT_DIR}/scripts/retrain.sh" 2>&1 | tee -a "${LOG_FILE}"

        if [[ $? -eq 0 ]]; then
            log "✅ Re-entrenamiento completado exitosamente"
        else
            log "❌ Re-entrenamiento fallo"
            exit 1
        fi
    else
        log ""
        log "Para re-entrenar manualmente:"
        log "  ./scripts/retrain.sh"
        log ""
        log "O ejecutar con --auto para re-entrenar automaticamente:"
        log "  ./scripts/check_retrain_needed.sh --auto"
    fi
else
    log ""
    log "✅ No se necesita re-entrenamiento"
    log "Los modelos actuales son adecuados."
fi

log "=========================================="
log "VERIFICACION COMPLETADA"
log "Log guardado en: ${LOG_FILE}"
log "=========================================="
