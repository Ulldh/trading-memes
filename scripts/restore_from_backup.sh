#!/bin/bash
#
# restore_from_backup.sh - Script de restauracion de backup.
#
# Restaura la base de datos desde un backup especifico.
# CUIDADO: Esto sobrescribe la base de datos actual.
#
# Uso:
#   ./scripts/restore_from_backup.sh [FECHA]
#
# Ejemplos:
#   ./scripts/restore_from_backup.sh 2026-02-26
#   ./scripts/restore_from_backup.sh latest
#
# Si no se especifica fecha, usa el backup mas reciente.

set -e  # Exit on error

# ============================================================
# CONFIGURACION
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DB_PATH="$PROJECT_ROOT/data/trading_memes.db"
BACKUP_DIR="$PROJECT_ROOT/data/backups"
LOG_FILE="$PROJECT_ROOT/logs/restore.log"

# Fecha del backup a restaurar (argumento o "latest")
BACKUP_DATE="${1:-latest}"

# ============================================================
# FUNCIONES
# ============================================================

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

find_backup_path() {
    if [ "$BACKUP_DATE" = "latest" ]; then
        # Buscar el backup mas reciente
        LATEST_BACKUP=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name "20*" | sort -r | head -n 1)

        if [ -z "$LATEST_BACKUP" ]; then
            log "ERROR: No se encontraron backups en $BACKUP_DIR"
            exit 1
        fi

        BACKUP_PATH="$LATEST_BACKUP"
        BACKUP_DATE=$(basename "$BACKUP_PATH")
        log "Backup mas reciente encontrado: $BACKUP_DATE"
    else
        BACKUP_PATH="$BACKUP_DIR/$BACKUP_DATE"

        if [ ! -d "$BACKUP_PATH" ]; then
            log "ERROR: Backup no encontrado: $BACKUP_PATH"
            log "Backups disponibles:"
            ls -1 "$BACKUP_DIR" | grep "^20"
            exit 1
        fi
    fi
}

verify_backup() {
    log "Verificando backup..."

    # Verificar que existe el archivo DB
    BACKUP_DB=$(find "$BACKUP_PATH" -name "trading_memes*.db" -type f | head -n 1)

    if [ -z "$BACKUP_DB" ]; then
        log "ERROR: No se encontro archivo de base de datos en $BACKUP_PATH"
        exit 1
    fi

    # Verificar integridad del backup
    sqlite3 "$BACKUP_DB" "PRAGMA integrity_check;" > /dev/null 2>&1

    if [ $? -ne 0 ]; then
        log "ERROR: Backup corrupto: $BACKUP_DB"
        exit 1
    fi

    log "✓ Backup verificado: $BACKUP_DB"
}

create_current_backup() {
    log "Creando backup de seguridad de la DB actual..."

    if [ -f "$DB_PATH" ]; then
        SAFETY_BACKUP="$DB_PATH.before_restore_$(date +'%Y%m%d_%H%M%S')"
        cp "$DB_PATH" "$SAFETY_BACKUP"
        log "✓ Backup de seguridad creado: $SAFETY_BACKUP"
    else
        log "No existe DB actual, no se crea backup de seguridad"
    fi
}

restore_database() {
    log "Restaurando base de datos desde backup..."

    # Copiar backup a la ubicacion de la DB
    cp "$BACKUP_DB" "$DB_PATH"

    # Verificar que se restauro correctamente
    sqlite3 "$DB_PATH" "PRAGMA integrity_check;" > /dev/null 2>&1

    if [ $? -ne 0 ]; then
        log "ERROR: Restauracion fallida, DB corrupta"
        exit 1
    fi

    # Obtener estadisticas de la DB restaurada
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)

    log "✓ Base de datos restaurada exitosamente"
    log "  Tamaño: $DB_SIZE"
}

show_stats() {
    log "Obteniendo estadisticas de la DB restaurada..."

    # Activar entorno virtual si existe
    if [ -d "$PROJECT_ROOT/.venv" ]; then
        source "$PROJECT_ROOT/.venv/bin/activate"

        cd "$PROJECT_ROOT"

        python -c "
import sys
import json
sys.path.insert(0, '$PROJECT_ROOT')

from src.data.storage import Storage

storage = Storage()
stats = storage.stats()

print('Estadisticas de la DB restaurada:')
for key, value in stats.items():
    print(f'  {key}: {value}')
" 2>&1 | tee -a "$LOG_FILE"
    fi
}

# ============================================================
# MAIN
# ============================================================

log "=========================================="
log "Iniciando Restauracion de Backup"
log "=========================================="

# Confirmar con el usuario
echo ""
echo "⚠️  ADVERTENCIA: Esta operacion sobrescribira la base de datos actual."
echo ""
echo "Backup a restaurar: $BACKUP_DATE"
echo "Base de datos actual: $DB_PATH"
echo ""
read -p "¿Estas seguro de continuar? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    log "Restauracion cancelada por el usuario"
    exit 0
fi

# Buscar el backup
find_backup_path

# Verificar el backup
verify_backup

# Crear backup de seguridad de la DB actual
create_current_backup

# Restaurar la base de datos
restore_database

# Mostrar estadisticas
show_stats

log "=========================================="
log "Restauracion completada exitosamente"
log "Backup restaurado: $BACKUP_DATE"
log "=========================================="

exit 0
