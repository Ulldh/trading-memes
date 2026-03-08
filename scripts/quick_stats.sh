#!/bin/bash
#
# quick_stats.sh - Muestra estadisticas rapidas del sistema.
#
# Uso:
#   ./scripts/quick_stats.sh

set -e  # Exit on error

# ============================================================
# CONFIGURACION
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_ROOT/.venv"
DB_PATH="$PROJECT_ROOT/data/trading_memes.db"

# ============================================================
# FUNCIONES
# ============================================================

print_header() {
    echo "=========================================="
    echo "  TRADING MEMES - QUICK STATS"
    echo "=========================================="
    echo ""
}

print_section() {
    echo "----------------------------------------"
    echo "$1"
    echo "----------------------------------------"
}

# ============================================================
# MAIN
# ============================================================

print_header

# Activar entorno virtual
if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
else
    echo "❌ Entorno virtual no encontrado"
    exit 1
fi

cd "$PROJECT_ROOT"

# ============================================================
# BASE DE DATOS
# ============================================================
print_section "📊 BASE DE DATOS"

if [ -f "$DB_PATH" ]; then
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    echo "Tamaño: $DB_SIZE"
    echo ""

    python -c "
from src.data.storage import Storage
from datetime import datetime

storage = Storage()
stats = storage.stats()

print('Estadísticas:')
for key, value in stats.items():
    print(f'  {key:20} {value:>6}')
" 2>/dev/null || echo "Error obteniendo stats de DB"

else
    echo "❌ Base de datos no encontrada"
fi

echo ""

# ============================================================
# ULTIMA RECOLECCION
# ============================================================
print_section "⏰ ULTIMA RECOLECCION"

python -c "
from src.data.storage import Storage
from datetime import datetime, timezone

storage = Storage()

# Query para timestamp mas reciente
query = 'SELECT MAX(timestamp) as last_timestamp FROM ohlcv'
result_df = storage.query(query)

if not result_df.empty and result_df.iloc[0]['last_timestamp']:
    last_timestamp_str = result_df.iloc[0]['last_timestamp']
    last_timestamp = datetime.fromisoformat(last_timestamp_str.replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    hours_since = (now - last_timestamp).total_seconds() / 3600

    print(f'Última recolección: {last_timestamp.strftime(\"%Y-%m-%d %H:%M UTC\")}')
    print(f'Hace: {hours_since:.1f} horas')

    if hours_since < 24:
        print('Estado: ✓ Reciente')
    elif hours_since < 48:
        print('Estado: ⚠ Atrasada (>24h)')
    else:
        print('Estado: ❌ Muy atrasada (>48h)')
else:
    print('No hay datos OHLCV en la base de datos')
" 2>/dev/null || echo "Error verificando última recolección"

echo ""

# ============================================================
# ESPACIO EN DISCO
# ============================================================
print_section "💾 ESPACIO EN DISCO"

DISK_USAGE=$(df -h "$PROJECT_ROOT" | tail -1)
DISK_AVAIL=$(echo $DISK_USAGE | awk '{print $4}')
DISK_USED=$(echo $DISK_USAGE | awk '{print $5}')

echo "Disponible: $DISK_AVAIL"
echo "Uso del disco: $DISK_USED"

# Tamaño del proyecto
PROJECT_SIZE=$(du -sh "$PROJECT_ROOT" | cut -f1)
echo "Tamaño del proyecto: $PROJECT_SIZE"

echo ""

# ============================================================
# MODELOS
# ============================================================
print_section "🤖 MODELOS ML"

MODELS_DIR="$PROJECT_ROOT/data/models"

if [ -d "$MODELS_DIR" ]; then
    if [ -f "$MODELS_DIR/random_forest.joblib" ]; then
        RF_SIZE=$(du -h "$MODELS_DIR/random_forest.joblib" | cut -f1)
        echo "✓ Random Forest ($RF_SIZE)"
    else
        echo "❌ Random Forest no encontrado"
    fi

    if [ -f "$MODELS_DIR/xgboost.joblib" ]; then
        XGB_SIZE=$(du -h "$MODELS_DIR/xgboost.joblib" | cut -f1)
        echo "✓ XGBoost ($XGB_SIZE)"
    else
        echo "❌ XGBoost no encontrado"
    fi

    if [ -f "$MODELS_DIR/evaluation_results.json" ]; then
        echo ""
        echo "Métricas de entrenamiento:"
        python -c "
import json
with open('$MODELS_DIR/evaluation_results.json', 'r') as f:
    results = json.load(f)
    rf = results.get('random_forest', {})
    xgb = results.get('xgboost', {})
    print(f'  Random Forest F1: {rf.get(\"val_f1\", rf.get(\"f1_score\", rf.get(\"f1\", 0))):.3f}')
    print(f'  XGBoost F1:       {xgb.get(\"val_f1\", xgb.get(\"f1_score\", xgb.get(\"f1\", 0))):.3f}')
" 2>/dev/null || echo "  Error leyendo métricas"
    fi
else
    echo "❌ Directorio de modelos no encontrado"
fi

echo ""

# ============================================================
# BACKUPS
# ============================================================
print_section "💾 BACKUPS"

BACKUP_DIR="$PROJECT_ROOT/data/backups"

if [ -d "$BACKUP_DIR" ]; then
    BACKUP_COUNT=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name "20*" | wc -l | tr -d ' ')
    echo "Backups disponibles: $BACKUP_COUNT"

    if [ $BACKUP_COUNT -gt 0 ]; then
        LATEST_BACKUP=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name "20*" | sort -r | head -n 1)
        LATEST_DATE=$(basename "$LATEST_BACKUP")
        LATEST_SIZE=$(du -sh "$LATEST_BACKUP" | cut -f1)
        echo "Último backup: $LATEST_DATE ($LATEST_SIZE)"
    fi
else
    echo "❌ Directorio de backups no encontrado"
fi

echo ""

# ============================================================
# SERVICIOS LAUNCHD
# ============================================================
print_section "⚙️  SERVICIOS ACTIVOS"

if launchctl list | grep -q "com.tradingmemes.healthcheck"; then
    echo "✓ Health Check (cada 6h)"
else
    echo "❌ Health Check (inactivo)"
fi

if launchctl list | grep -q "com.tradingmemes.backup"; then
    echo "✓ Backup (diario 04:00)"
else
    echo "❌ Backup (inactivo)"
fi

if launchctl list | grep -q "com.tradingmemes.dailycollect"; then
    echo "✓ Daily Collect (diario 03:00)"
else
    echo "⚠  Daily Collect (revisar configuración)"
fi

echo ""
echo "=========================================="
echo "Para más detalles:"
echo "  Health check: ./scripts/health_check.sh"
echo "  Test completo: ./scripts/test_system.sh"
echo "=========================================="
