#!/bin/bash
#
# setup_monitoring.sh - Configura monitoreo y backups automaticos.
#
# Este script:
#   1. Crea los directorios necesarios
#   2. Instala los launchd agents para health checks y backups
#   3. Verifica la configuracion
#
# Uso:
#   ./scripts/setup_monitoring.sh

set -e  # Exit on error

# ============================================================
# CONFIGURACION
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"

# ============================================================
# FUNCIONES
# ============================================================

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

create_directories() {
    log "Creando directorios necesarios..."

    # Directorios para logs
    mkdir -p "$PROJECT_ROOT/logs"

    # Directorios para backups
    mkdir -p "$PROJECT_ROOT/data/backups"

    log "✓ Directorios creados"
}

install_launchd_agents() {
    log "Instalando launchd agents..."

    # Asegurar que el directorio LaunchAgents existe
    mkdir -p "$LAUNCHD_DIR"

    # Copiar plist files
    cp "$SCRIPT_DIR/com.tradingmemes.healthcheck.plist" "$LAUNCHD_DIR/"
    cp "$SCRIPT_DIR/com.tradingmemes.backup.plist" "$LAUNCHD_DIR/"

    log "✓ Archivos .plist copiados a $LAUNCHD_DIR"

    # Descargar agents si ya estaban cargados
    launchctl unload "$LAUNCHD_DIR/com.tradingmemes.healthcheck.plist" 2>/dev/null || true
    launchctl unload "$LAUNCHD_DIR/com.tradingmemes.backup.plist" 2>/dev/null || true

    # Cargar los nuevos agents
    launchctl load "$LAUNCHD_DIR/com.tradingmemes.healthcheck.plist"
    launchctl load "$LAUNCHD_DIR/com.tradingmemes.backup.plist"

    log "✓ Launchd agents cargados"
}

verify_installation() {
    log "Verificando instalacion..."

    # Verificar que los agents estan cargados
    if launchctl list | grep -q "com.tradingmemes.healthcheck"; then
        log "✓ Health check agent activo"
    else
        log "✗ ERROR: Health check agent no esta activo"
        return 1
    fi

    if launchctl list | grep -q "com.tradingmemes.backup"; then
        log "✓ Backup agent activo"
    else
        log "✗ ERROR: Backup agent no esta activo"
        return 1
    fi

    log "✓ Verificacion completada"
}

show_status() {
    log ""
    log "=========================================="
    log "CONFIGURACION DE MONITOREO COMPLETADA"
    log "=========================================="
    log ""
    log "Servicios activos:"
    log "  - Health Check: Cada 6 horas"
    log "  - Backup DB: Diario a las 04:00"
    log ""
    log "Comandos utiles:"
    log "  - Ver logs de health check:"
    log "    tail -f $PROJECT_ROOT/logs/health_check.log"
    log ""
    log "  - Ver logs de backup:"
    log "    tail -f $PROJECT_ROOT/logs/backup.log"
    log ""
    log "  - Ejecutar health check manualmente:"
    log "    $SCRIPT_DIR/health_check.sh"
    log ""
    log "  - Ejecutar backup manualmente:"
    log "    $SCRIPT_DIR/backup_db.sh"
    log ""
    log "  - Ver status de launchd:"
    log "    launchctl list | grep tradingmemes"
    log ""
    log "  - Desinstalar (si es necesario):"
    log "    launchctl unload ~/Library/LaunchAgents/com.tradingmemes.*.plist"
    log ""
    log "=========================================="
}

# ============================================================
# MAIN
# ============================================================

log "=========================================="
log "Configurando Monitoreo y Backups"
log "=========================================="

# Crear directorios
create_directories

# Instalar launchd agents
install_launchd_agents

# Verificar instalacion
verify_installation

# Mostrar status
show_status

exit 0
