#!/bin/bash
# daily_signals.sh - Genera senales diarias post-recopilacion.
#
# Ejecutar DESPUES de daily_collect.sh.
# Califica todos los tokens nuevos (sin label) que tengan
# al menos 7 dias de datos OHLCV.
#
# Output: signals/candidates_YYYYMMDD.csv
#
# Uso manual: ./scripts/daily_signals.sh
# Automatizado: Llamar desde daily_collect.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"

DATE_STAMP=$(date +%Y%m%d)
LOG_FILE="${LOG_DIR}/signals_${DATE_STAMP}.log"

VENV_DIR="${PROJECT_DIR}/.venv"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log "=========================================="
log "GENERACION DE SENALES INICIADA"
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

# Verificar que hay un modelo entrenado
if [ ! -f "data/models/random_forest.joblib" ] && [ ! -f "data/models/random_forest_v1.joblib" ]; then
    log "ERROR: No hay modelo entrenado. Ejecuta retrain.sh primero."
    exit 1
fi

# Generar senales
log "Scoring tokens nuevos..."
python -c "
from src.models.scorer import GemScorer

scorer = GemScorer()

# Calificar todos los tokens nuevos con >= 7 dias OHLCV
candidates = scorer.score_all_new(min_ohlcv_days=7)

if candidates.empty:
    print('No hay tokens nuevos para calificar')
else:
    # Guardar CSV
    output_path = scorer.save_signals(candidates)
    print(f'Senales guardadas: {output_path}')

    # Resumen
    print(f'Total candidatos: {len(candidates)}')
    for signal in ['STRONG', 'MEDIUM', 'WEAK']:
        count = (candidates['signal'] == signal).sum()
        if count > 0:
            print(f'  {signal}: {count} tokens')

    # Top 5 candidatos
    top5 = candidates.head(5)
    if not top5.empty:
        print()
        print('Top 5 candidatos:')
        for _, row in top5.iterrows():
            symbol = row.get('symbol', 'N/A')
            chain = row.get('chain', 'N/A')
            prob = row.get('probability', 0)
            signal = row.get('signal', 'NONE')
            print(f'  {symbol} ({chain}): {prob:.1%} [{signal}]')
" 2>&1 | tee -a "${LOG_FILE}"

log "=========================================="
log "GENERACION DE SENALES COMPLETADA"
log "=========================================="
