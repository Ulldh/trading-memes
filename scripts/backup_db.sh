#!/bin/bash
#
# backup_db.sh - Script de respaldo de la base de datos.
#
# Este script crea un backup de la base de datos SQLite con timestamp.
# Tambien exporta todas las tablas a formato Parquet como backup adicional.
# Opcionalmente puede subir a Google Drive o almacenamiento remoto.
#
# Uso:
#   ./scripts/backup_db.sh
#
# El script crea:
#   - data/backups/YYYY-MM-DD/trading_memes.db (copia SQLite)
#   - data/backups/YYYY-MM-DD/parquet/*.parquet (export Parquet)
#   - data/backups/YYYY-MM-DD/metadata.json (info del backup)
#
# Retention: Mantiene backups de los ultimos 30 dias, borra mas antiguos.

set -e  # Exit on error

# ============================================================
# CONFIGURACION
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_ROOT/.venv"
DB_PATH="$PROJECT_ROOT/data/trading_memes.db"
BACKUP_DIR="$PROJECT_ROOT/data/backups"
LOG_FILE="$PROJECT_ROOT/logs/backup.log"

# Retention en dias
RETENTION_DAYS=30

# Timestamp para este backup
BACKUP_DATE=$(date +'%Y-%m-%d')
BACKUP_TIMESTAMP=$(date +'%Y-%m-%d_%H-%M-%S')
BACKUP_PATH="$BACKUP_DIR/$BACKUP_DATE"

# ============================================================
# FUNCIONES
# ============================================================

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

create_backup_dir() {
    if [ ! -d "$BACKUP_PATH" ]; then
        mkdir -p "$BACKUP_PATH"
        mkdir -p "$BACKUP_PATH/parquet"
        log "Directorio de backup creado: $BACKUP_PATH"
    fi
}

backup_sqlite() {
    log "Respaldando base de datos SQLite..."

    if [ ! -f "$DB_PATH" ]; then
        log "ERROR: Base de datos no encontrada en $DB_PATH"
        return 1
    fi

    # Usar cp para copiar (SQLite soporta hot backup)
    cp "$DB_PATH" "$BACKUP_PATH/trading_memes_$BACKUP_TIMESTAMP.db"

    # Crear symlink a ultimo backup
    ln -sf "$BACKUP_PATH/trading_memes_$BACKUP_TIMESTAMP.db" "$BACKUP_PATH/trading_memes.db"

    # Calcular tamaño
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    log "✓ SQLite backup completado ($DB_SIZE)"
}

export_to_parquet() {
    log "Exportando tablas a Parquet..."

    # Activar entorno virtual
    source "$VENV_PATH/bin/activate"

    cd "$PROJECT_ROOT"

    # Script Python para exportar a Parquet
    python -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')

from pathlib import Path
from src.data.storage import Storage
import pandas as pd

storage = Storage()
backup_path = Path('$BACKUP_PATH/parquet')

# Tablas a exportar
tables = [
    'tokens',
    'pool_snapshots',
    'ohlcv',
    'holder_snapshots',
    'contract_info',
    'labels',
    'features'
]

for table in tables:
    try:
        # Leer tabla completa usando context manager
        query = f'SELECT * FROM {table}'
        with storage._connect() as conn:
            df = pd.read_sql_query(query, conn)

        # Guardar a Parquet
        output_file = backup_path / f'{table}.parquet'
        df.to_parquet(output_file, compression='snappy', index=False)

        print(f'✓ {table}: {len(df)} filas exportadas')
    except Exception as e:
        print(f'✗ Error exportando {table}: {e}')

print('Export a Parquet completado')
" 2>&1 | tee -a "$LOG_FILE"

    log "✓ Export a Parquet completado"
}

create_metadata() {
    log "Generando metadata del backup..."

    # Activar entorno virtual
    source "$VENV_PATH/bin/activate"

    cd "$PROJECT_ROOT"

    # Generar metadata JSON
    python -c "
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, '$PROJECT_ROOT')

from src.data.storage import Storage

storage = Storage()
stats = storage.stats()

metadata = {
    'backup_date': '$BACKUP_DATE',
    'backup_timestamp': '$BACKUP_TIMESTAMP',
    'db_stats': stats,
    'db_size_bytes': Path('$DB_PATH').stat().st_size,
    'created_at': datetime.now(timezone.utc).isoformat(),
}

with open('$BACKUP_PATH/metadata.json', 'w') as f:
    json.dump(metadata, f, indent=2)

print('Metadata generado')
" 2>&1 | tee -a "$LOG_FILE"

    log "✓ Metadata generado"
}

cleanup_old_backups() {
    log "Limpiando backups antiguos (retention: $RETENTION_DAYS dias)..."

    # Buscar directorios de backup mas antiguos que RETENTION_DAYS
    find "$BACKUP_DIR" -maxdepth 1 -type d -mtime +$RETENTION_DAYS -exec rm -rf {} \;

    # Contar backups restantes
    BACKUP_COUNT=$(find "$BACKUP_DIR" -maxdepth 1 -type d | wc -l | tr -d ' ')
    log "✓ Cleanup completado ($BACKUP_COUNT backups restantes)"
}

# ============================================================
# MAIN
# ============================================================

log "=========================================="
log "Iniciando Backup"
log "=========================================="

# Verificar que el entorno virtual existe
if [ ! -d "$VENV_PATH" ]; then
    log "ERROR: Entorno virtual no encontrado en $VENV_PATH"
    exit 1
fi

# Verificar que la DB existe
if [ ! -f "$DB_PATH" ]; then
    log "ERROR: Base de datos no encontrada en $DB_PATH"
    exit 1
fi

# Crear directorio de backup
create_backup_dir

# Ejecutar backups
backup_sqlite
export_to_parquet
create_metadata

# Cleanup de backups antiguos
cleanup_old_backups

log "=========================================="
log "Backup completado exitosamente"
log "Backup location: $BACKUP_PATH"
log "=========================================="

exit 0
