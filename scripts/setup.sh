#!/bin/bash
# setup.sh - Script maestro que automatiza TODA la configuracion del proyecto.
#
# Ejecuta de principio a fin:
#   FASE 1: Procesa seed dataset (91 tokens) -> recopila datos + labels + features + modelos
#   FASE 2: Valida APIs disponibles
#   FASE 3: Instala automatizacion diaria (launchd)
#   FASE 6: Genera primera ronda de senales (si hay modelo)
#
# Uso:
#   ./scripts/setup.sh              # Ejecutar todo desde cero
#   ./scripts/setup.sh --resume     # Continuar (solo tokens nuevos)
#
# Tiempo estimado: ~5-10 min (depende de rate limits de APIs)

set -uo pipefail  # No usamos -e porque queremos manejar errores manualmente

# ============================================================
# CONFIGURACION
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/logs"
SIGNALS_DIR="${PROJECT_DIR}/signals"
VENV_DIR="${PROJECT_DIR}/.venv"

mkdir -p "${LOG_DIR}" "${SIGNALS_DIR}"

DATE_STAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/setup_${DATE_STAMP}.log"

# Colores (solo si la terminal los soporta)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN='' YELLOW='' RED='' CYAN='' BOLD='' NC=''
fi

# Flag --resume
RESUME=false
for arg in "$@"; do
    if [ "$arg" = "--resume" ]; then
        RESUME=true
    fi
done

# ============================================================
# FUNCIONES
# ============================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "${LOG_FILE}"
    echo -e "$1"
}

header() {
    echo ""
    log "${BOLD}${CYAN}========================================${NC}"
    log "${BOLD}${CYAN}  $1${NC}"
    log "${BOLD}${CYAN}========================================${NC}"
}

success() {
    log "${GREEN}  OK: $1${NC}"
}

warn() {
    log "${YELLOW}  AVISO: $1${NC}"
}

fail() {
    log "${RED}  ERROR: $1${NC}"
}

# ============================================================
# VERIFICACION PREVIA
# ============================================================

header "SETUP COMPLETO - Memecoin Gem Detector"
log "Proyecto: ${PROJECT_DIR}"
log "Log: ${LOG_FILE}"
log "Modo: $(if $RESUME; then echo 'RESUME (solo tokens nuevos)'; else echo 'COMPLETO'; fi)"

# 1. Verificar entorno virtual
if [ ! -d "${VENV_DIR}" ]; then
    fail "Entorno virtual no encontrado en ${VENV_DIR}"
    log "Ejecuta: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

source "${VENV_DIR}/bin/activate"
success "Entorno virtual activado: $(python --version)"

# 2. Verificar dependencias criticas
python -c "import pandas, sklearn, xgboost, streamlit, shap, plotly" 2>/dev/null
if [ $? -ne 0 ]; then
    fail "Faltan dependencias. Instalando..."
    pip install -r "${PROJECT_DIR}/requirements.txt" 2>&1 | tee -a "${LOG_FILE}"
fi
success "Dependencias verificadas"

cd "${PROJECT_DIR}"

# 3. Crear .env si no existe
if [ ! -f "${PROJECT_DIR}/.env" ]; then
    cp "${PROJECT_DIR}/.env.example" "${PROJECT_DIR}/.env"
    success ".env creado desde .env.example"
else
    success ".env ya existe"
fi

# ============================================================
# FASE 1: EXPANSION DEL SEED DATASET
# ============================================================

header "FASE 1/5: Procesando Seed Dataset (91 tokens)"

if $RESUME; then
    log "Modo resume: solo tokens que no estan en la DB"
    python scripts/expand_seed.py --skip-existing 2>&1 | tee -a "${LOG_FILE}"
else
    python scripts/expand_seed.py 2>&1 | tee -a "${LOG_FILE}"
fi

SEED_EXIT=$?
if [ $SEED_EXIT -eq 0 ]; then
    success "Seed dataset procesado"
else
    warn "Seed dataset completo con algunos errores (normal si hay tokens sin liquidez)"
fi

# ============================================================
# FASE 2: VALIDACION DE APIs
# ============================================================

header "FASE 2/5: Validando APIs"

python scripts/validate_apis.py 2>&1 | tee -a "${LOG_FILE}"
# No salimos si falla - GeckoTerminal y DexScreener no necesitan keys
success "Validacion de APIs completada (ver detalle arriba)"

# ============================================================
# FASE 3: AUTOMATIZACION DIARIA
# ============================================================

header "FASE 3/5: Instalando automatizacion diaria"

PLIST_SRC="${PROJECT_DIR}/scripts/com.tradingmemes.dailycollect.plist"
PLIST_DST="${HOME}/Library/LaunchAgents/com.tradingmemes.dailycollect.plist"

# Descargar si ya existe (para actualizaciones limpias)
if launchctl list 2>/dev/null | grep -q "com.tradingmemes.dailycollect"; then
    launchctl unload "${PLIST_DST}" 2>/dev/null || true
    success "Job anterior descargado"
fi

# Copiar plist actualizado
cp "${PLIST_SRC}" "${PLIST_DST}"

# Cargar el job
launchctl load "${PLIST_DST}" 2>&1
if [ $? -eq 0 ]; then
    success "launchd job instalado (ejecucion diaria 03:00)"
    log "  Verificar: launchctl list | grep tradingmemes"
else
    warn "No se pudo cargar el launchd job"
    log "  Puedes cargarlo manualmente: launchctl load ${PLIST_DST}"
fi

# ============================================================
# FASE 4: PRIMERA RONDA DE SENALES
# ============================================================

header "FASE 4/5: Generando senales iniciales"

# Solo si hay un modelo entrenado
if [ -f "${PROJECT_DIR}/data/models/random_forest.joblib" ] || [ -f "${PROJECT_DIR}/data/models/random_forest_v1.joblib" ]; then
    bash "${PROJECT_DIR}/scripts/daily_signals.sh" 2>&1 | tee -a "${LOG_FILE}"
    success "Senales generadas"
else
    warn "Sin modelo entrenado - las senales se generaran tras el re-entrenamiento"
fi

# ============================================================
# FASE 5: RESUMEN FINAL
# ============================================================

header "FASE 5/5: Resumen del sistema"

python -c "
from src.data.storage import Storage
import os
from pathlib import Path

s = Storage()
stats = s.stats()

print()
print('  BASE DE DATOS:')
for k, v in stats.items():
    print(f'    {k}: {v}')

print()
print('  MODELOS:')
models_dir = Path('data/models')
for f in sorted(models_dir.glob('*.joblib')):
    size_kb = f.stat().st_size / 1024
    print(f'    {f.name} ({size_kb:.0f} KB)')

eval_path = models_dir / 'evaluation_results.json'
if eval_path.exists():
    import json
    with open(eval_path) as ef:
        results = json.load(ef)
    for name, metrics in results.items():
        if isinstance(metrics, dict):
            f1 = metrics.get('val_f1', metrics.get('f1', 'N/A'))
            acc = metrics.get('val_accuracy', metrics.get('accuracy', 'N/A'))
            print(f'    {name}: F1={f1}, Accuracy={acc}')

print()
print('  SENALES:')
signals_dir = Path('signals')
csvs = sorted(signals_dir.glob('candidates_*.csv'))
if csvs:
    latest = csvs[-1]
    import pandas as pd
    df = pd.read_csv(latest)
    print(f'    Ultimo archivo: {latest.name}')
    print(f'    Candidatos: {len(df)}')
    for sig in ['STRONG', 'MEDIUM', 'WEAK']:
        count = (df.get('signal', pd.Series()) == sig).sum()
        if count > 0:
            print(f'      {sig}: {count}')
else:
    print('    Sin senales todavia (se generaran con datos suficientes)')

print()
print('  AUTOMATIZACION:')
" 2>&1 | tee -a "${LOG_FILE}"

# Verificar launchd
if launchctl list 2>/dev/null | grep -q "com.tradingmemes.dailycollect"; then
    success "launchd job ACTIVO (03:00 diario)"
else
    warn "launchd job NO activo"
fi

# Dashboard
success "Dashboard listo: streamlit run dashboard/app.py"

# ============================================================
# RESUMEN DE SIGUIENTE PASO
# ============================================================

header "SETUP COMPLETADO"

echo ""
echo -e "${BOLD}El sistema esta operativo. Estas son las acciones automaticas:${NC}"
echo ""
echo "  Diario 03:00 -> Descubre tokens nuevos + recopila datos + genera senales"
echo "  Manual        -> streamlit run dashboard/app.py  (ver resultados)"
echo ""
echo -e "${BOLD}Comandos utiles:${NC}"
echo ""
echo "  Ver estado de la DB:"
echo "    python -c \"from src.data.storage import Storage; [print(f'  {k}: {v}') for k,v in Storage().stats().items()]\""
echo ""
echo "  Ejecutar recopilacion manual:"
echo "    ./scripts/daily_collect.sh"
echo ""
echo "  Re-entrenar modelos (cuando haya 300+ tokens):"
echo "    ./scripts/retrain.sh"
echo ""
echo "  Full refresh (features + labels + modelos):"
echo "    ./scripts/full_refresh.sh"
echo ""
echo "  Ver logs:"
echo "    ls -la logs/"
echo ""
echo -e "${YELLOW}OPCIONAL: Para desbloquear datos de holders y verificacion de contratos:${NC}"
echo "  1. Registrate gratis en https://www.helius.dev/ y https://etherscan.io/apis"
echo "  2. Edita .env con tus keys"
echo "  3. Ejecuta: ./scripts/setup.sh --resume"
echo ""
log "Setup completado. Log en: ${LOG_FILE}"
