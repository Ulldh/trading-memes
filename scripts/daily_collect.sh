#!/bin/bash
# daily_collect.sh - Recopilacion diaria automatica de datos.
#
# Ejecuta el pipeline completo de recopilacion:
#   1. Descubre pools nuevos en Solana, Ethereum, Base
#   2. Enriquece con DexScreener (buyers/sellers)
#   3. Obtiene OHLCV historico
#   4. Obtiene holders (si hay key de Helius)
#   5. Verifica contratos (si hay key de Etherscan)
#   6. Recopila contexto de mercado (BTC, ETH, SOL)
#
# Uso manual:   ./scripts/daily_collect.sh
# Automatizado:  launchd plist (ver scripts/com.tradingmemes.dailycollect.plist)

set -euo pipefail

# ============================================================
# CONFIGURACION
# ============================================================

# Directorio raiz del proyecto (relativo a este script)
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Directorio de logs
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"

# Archivo de log con fecha
DATE_STAMP=$(date +%Y%m%d)
LOG_FILE="${LOG_DIR}/daily_${DATE_STAMP}.log"

# Entorno virtual de Python
VENV_DIR="${PROJECT_DIR}/.venv"

# ============================================================
# FUNCIONES
# ============================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

cleanup_old_logs() {
    # Eliminar logs con mas de 30 dias
    find "${LOG_DIR}" -name "daily_*.log" -mtime +30 -delete 2>/dev/null || true
    find "${LOG_DIR}" -name "launchd_*.log" -mtime +30 -delete 2>/dev/null || true
    log "Logs antiguos (>30 dias) limpiados"
}

# ============================================================
# INICIO
# ============================================================

log "=========================================="
log "RECOPILACION DIARIA INICIADA"
log "=========================================="
log "Proyecto: ${PROJECT_DIR}"

# Activar entorno virtual
if [ -d "${VENV_DIR}" ]; then
    source "${VENV_DIR}/bin/activate"
    log "Entorno virtual activado: $(python --version)"
else
    log "ERROR: Entorno virtual no encontrado en ${VENV_DIR}"
    exit 1
fi

# Cambiar al directorio del proyecto (necesario para imports)
cd "${PROJECT_DIR}"

# ============================================================
# PASO 1: Recopilacion diaria (discover + enrich + OHLCV + holders + contracts)
# ============================================================
log "Ejecutando recopilacion diaria..."
python -m src.data.collector 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 2: Contexto de mercado (ya se ejecuta dentro de collector.__main__)
# Pero lo dejamos explicito por si se cambia en el futuro
# ============================================================
log "Verificando contexto de mercado..."
python -c "
from src.data.collector import DataCollector
collector = DataCollector()
collector.collect_market_context(days=90)
print('Contexto de mercado actualizado')
" 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 3: Mostrar estadisticas
# ============================================================
log "Estadisticas de la base de datos:"
python -c "
from src.data.storage import Storage
s = Storage()
stats = s.stats()
for k, v in stats.items():
    print(f'  {k}: {v}')
" 2>&1 | tee -a "${LOG_FILE}"

# ============================================================
# PASO 4: Generar senales (si hay modelo entrenado)
# ============================================================
if [ -f "${PROJECT_DIR}/data/models/random_forest.joblib" ] || [ -f "${PROJECT_DIR}/data/models/random_forest_v1.joblib" ]; then
    log "Generando senales diarias..."
    bash "${PROJECT_DIR}/scripts/daily_signals.sh" 2>&1 | tee -a "${LOG_FILE}"
else
    log "Sin modelo entrenado, saltando generacion de senales"
fi

# ============================================================
# LIMPIEZA
# ============================================================
cleanup_old_logs

log "=========================================="
log "RECOPILACION DIARIA COMPLETADA"
log "=========================================="
