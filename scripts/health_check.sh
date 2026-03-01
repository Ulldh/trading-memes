#!/bin/bash
#
# health_check.sh - Script de verificacion de salud del sistema.
#
# Este script ejecuta el HealthMonitor y envia alertas si hay problemas.
# Diseñado para ejecutarse cada 6 horas via launchd.
#
# Uso:
#   ./scripts/health_check.sh
#
# Variables de entorno necesarias:
#   NOTIFICATION_EMAIL (opcional) - Email para recibir alertas
#   TELEGRAM_BOT_TOKEN (opcional) - Token del bot de Telegram
#   TELEGRAM_CHAT_ID (opcional) - Chat ID para enviar mensajes

set -e  # Exit on error

# ============================================================
# CONFIGURACION
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_ROOT/.venv"
LOG_FILE="$PROJECT_ROOT/logs/health_check.log"
STATUS_FILE="$PROJECT_ROOT/logs/health_status.json"

# Cargar variables de entorno
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

# ============================================================
# FUNCIONES
# ============================================================

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_email_alert() {
    local subject="$1"
    local body="$2"

    if [ -z "$NOTIFICATION_EMAIL" ]; then
        log "NOTIFICATION_EMAIL no configurado, saltando email"
        return
    fi

    # Usar sendmail o mail command
    if command -v mail &> /dev/null; then
        echo "$body" | mail -s "$subject" "$NOTIFICATION_EMAIL"
        log "Email enviado a $NOTIFICATION_EMAIL"
    else
        log "Comando 'mail' no disponible, no se pudo enviar email"
    fi
}

send_telegram_alert() {
    local message="$1"

    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
        log "Telegram no configurado, saltando notificacion"
        return
    fi

    # Enviar mensaje via Telegram Bot API
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d text="$message" \
        -d parse_mode="Markdown" \
        > /dev/null

    log "Mensaje enviado a Telegram (chat_id: $TELEGRAM_CHAT_ID)"
}

# ============================================================
# MAIN
# ============================================================

log "=========================================="
log "Iniciando Health Check"
log "=========================================="

# Verificar que el entorno virtual existe
if [ ! -d "$VENV_PATH" ]; then
    log "ERROR: Entorno virtual no encontrado en $VENV_PATH"
    exit 1
fi

# Activar entorno virtual
source "$VENV_PATH/bin/activate"

# Cambiar al directorio del proyecto
cd "$PROJECT_ROOT"

# Ejecutar health monitor y guardar resultado en JSON
log "Ejecutando HealthMonitor..."
python -c "
import sys
import json
sys.path.insert(0, '$PROJECT_ROOT')

from src.monitoring import HealthMonitor

monitor = HealthMonitor()
status = monitor.check_all()

# Guardar status en archivo JSON
with open('$STATUS_FILE', 'w') as f:
    json.dump(status, f, indent=2)

# Imprimir resumen
print(monitor.get_summary())

# Exit code: 0 si healthy, 1 si hay problemas
sys.exit(0 if status['healthy'] else 1)
" 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=$?

# Leer el status JSON para enviar alertas
if [ -f "$STATUS_FILE" ]; then
    HEALTHY=$(python -c "import json; print(json.load(open('$STATUS_FILE'))['healthy'])" 2>/dev/null || echo "false")
    ISSUES=$(python -c "import json; print(len(json.load(open('$STATUS_FILE'))['issues']))" 2>/dev/null || echo "0")
    WARNINGS=$(python -c "import json; print(len(json.load(open('$STATUS_FILE'))['warnings']))" 2>/dev/null || echo "0")

    if [ "$HEALTHY" = "False" ] || [ "$EXIT_CODE" -ne 0 ]; then
        log "⚠️  Sistema con problemas detectados: $ISSUES errores, $WARNINGS warnings"

        # Generar resumen para alertas
        SUMMARY=$(python -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from src.monitoring import HealthMonitor
monitor = HealthMonitor()
print(monitor.get_summary())
" 2>/dev/null || echo "Error generando resumen")

        # Enviar alertas
        send_email_alert "🚨 Trading Memes - Health Check FAILED" "$SUMMARY"
        send_telegram_alert "🚨 *Trading Memes - ALERTA*

Sistema con problemas:
- Errores: $ISSUES
- Warnings: $WARNINGS

Ejecuta: \`./scripts/health_check.sh\` para mas detalles"

    else
        log "✓ Sistema saludable"
    fi
else
    log "ERROR: No se pudo generar archivo de status"
    send_email_alert "🚨 Trading Memes - Health Check ERROR" "No se pudo ejecutar el health check correctamente."
    send_telegram_alert "🚨 *Trading Memes - ERROR*

Health check no se pudo ejecutar."
fi

log "Health Check completado (exit code: $EXIT_CODE)"
log "=========================================="

exit $EXIT_CODE
