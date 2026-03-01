#!/bin/bash
#
# test_system.sh - Script de verificacion completa del sistema.
#
# Verifica que todos los componentes esten correctamente instalados
# y configurados:
#   - Entorno virtual
#   - Dependencias Python
#   - Base de datos
#   - APIs
#   - Scripts ejecutables
#   - Configuracion launchd
#
# Uso:
#   ./scripts/test_system.sh

set -e  # Exit on error

# ============================================================
# CONFIGURACION
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_ROOT/.venv"
DB_PATH="$PROJECT_ROOT/data/trading_memes.db"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Contadores
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# ============================================================
# FUNCIONES
# ============================================================

check_ok() {
    echo -e "${GREEN}✓${NC} $1"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

check_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    WARNING_CHECKS=$((WARNING_CHECKS + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

section_header() {
    echo ""
    echo "========================================"
    echo "$1"
    echo "========================================"
}

# ============================================================
# CHECKS
# ============================================================

section_header "1. ENTORNO VIRTUAL"

if [ -d "$VENV_PATH" ]; then
    check_ok "Entorno virtual existe en $VENV_PATH"
else
    check_fail "Entorno virtual NO encontrado en $VENV_PATH"
    exit 1
fi

# Activar entorno virtual
source "$VENV_PATH/bin/activate"

# Verificar que Python funciona
if python --version > /dev/null 2>&1; then
    PYTHON_VERSION=$(python --version)
    check_ok "Python funciona: $PYTHON_VERSION"
else
    check_fail "Python NO funciona en el entorno virtual"
fi

# ============================================================
section_header "2. DEPENDENCIAS PYTHON"

# Lista de paquetes criticos
REQUIRED_PACKAGES=(
    "pandas"
    "numpy"
    "scikit-learn"
    "xgboost"
    "shap"
    "streamlit"
    "requests"
    "python-dotenv"
)

for package in "${REQUIRED_PACKAGES[@]}"; do
    if python -c "import $package" 2>/dev/null; then
        check_ok "Paquete instalado: $package"
    else
        check_fail "Paquete FALTANTE: $package"
    fi
done

# ============================================================
section_header "3. BASE DE DATOS"

if [ -f "$DB_PATH" ]; then
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    check_ok "Base de datos existe: $DB_PATH ($DB_SIZE)"

    # Verificar integridad con SQLite
    if sqlite3 "$DB_PATH" "PRAGMA integrity_check;" > /dev/null 2>&1; then
        check_ok "Integridad de DB verificada"
    else
        check_fail "DB corrupta o inaccesible"
    fi

    # Obtener estadisticas
    cd "$PROJECT_ROOT"
    python -c "
from src.data.storage import Storage
stats = Storage().stats()
print(f'Tokens: {stats[\"tokens\"]}')
print(f'OHLCV: {stats[\"ohlcv\"]}')
print(f'Features: {stats[\"features\"]}')
" 2>/dev/null && check_ok "Estadisticas de DB obtenidas" || check_warning "No se pudieron obtener stats de DB"

else
    check_fail "Base de datos NO encontrada en $DB_PATH"
fi

# ============================================================
section_header "4. ARCHIVOS DE CONFIGURACION"

if [ -f "$PROJECT_ROOT/.env" ]; then
    check_ok "Archivo .env existe"

    # Verificar que tiene las keys principales
    if grep -q "HELIUS_API_KEY" "$PROJECT_ROOT/.env"; then
        check_ok "HELIUS_API_KEY configurada en .env"
    else
        check_warning "HELIUS_API_KEY no encontrada en .env (opcional)"
    fi

    if grep -q "ETHERSCAN_API_KEY" "$PROJECT_ROOT/.env"; then
        check_ok "ETHERSCAN_API_KEY configurada en .env"
    else
        check_warning "ETHERSCAN_API_KEY no encontrada en .env (opcional)"
    fi
else
    check_warning "Archivo .env NO encontrado (crear desde .env.example)"
fi

if [ -f "$PROJECT_ROOT/.env.example" ]; then
    check_ok "Archivo .env.example existe"
else
    check_warning ".env.example NO encontrado"
fi

# ============================================================
section_header "5. SCRIPTS EJECUTABLES"

SCRIPTS=(
    "health_check.sh"
    "backup_db.sh"
    "restore_from_backup.sh"
    "setup_monitoring.sh"
    "daily_collect.sh"
    "daily_signals.sh"
    "full_refresh.sh"
    "retrain.sh"
)

for script in "${SCRIPTS[@]}"; do
    SCRIPT_PATH="$SCRIPT_DIR/$script"
    if [ -f "$SCRIPT_PATH" ]; then
        if [ -x "$SCRIPT_PATH" ]; then
            check_ok "Script ejecutable: $script"
        else
            check_warning "Script existe pero NO es ejecutable: $script (ejecutar chmod +x)"
        fi
    else
        check_fail "Script NO encontrado: $script"
    fi
done

# ============================================================
section_header "6. LAUNCHD AGENTS"

if launchctl list | grep -q "com.tradingmemes.healthcheck"; then
    check_ok "Health check agent activo"
else
    check_warning "Health check agent NO activo (ejecutar ./scripts/setup_monitoring.sh)"
fi

if launchctl list | grep -q "com.tradingmemes.backup"; then
    check_ok "Backup agent activo"
else
    check_warning "Backup agent NO activo (ejecutar ./scripts/setup_monitoring.sh)"
fi

if launchctl list | grep -q "com.tradingmemes.dailycollect"; then
    check_ok "Daily collect agent activo"
else
    check_warning "Daily collect agent NO activo (configurado manualmente?)"
fi

# ============================================================
section_header "7. DIRECTORIOS NECESARIOS"

DIRECTORIES=(
    "data"
    "data/raw"
    "data/processed"
    "data/models"
    "data/backups"
    "logs"
    ".cache"
)

for dir in "${DIRECTORIES[@]}"; do
    DIR_PATH="$PROJECT_ROOT/$dir"
    if [ -d "$DIR_PATH" ]; then
        check_ok "Directorio existe: $dir"
    else
        check_warning "Directorio NO existe: $dir (se creara automaticamente)"
    fi
done

# ============================================================
section_header "8. MODULOS PYTHON"

cd "$PROJECT_ROOT"

# Verificar que los modulos principales se pueden importar
MODULES=(
    "src.data.storage"
    "src.api.coingecko_client"
    "src.features.builder"
    "src.models.trainer"
    "src.monitoring.health_monitor"
)

for module in "${MODULES[@]}"; do
    if python -c "import $module" 2>/dev/null; then
        check_ok "Modulo importable: $module"
    else
        check_fail "Modulo NO se puede importar: $module"
    fi
done

# ============================================================
section_header "9. HEALTH CHECK"

# Ejecutar un health check rapido
if python -m src.monitoring.health_monitor > /dev/null 2>&1; then
    check_ok "Health monitor ejecutado exitosamente"
else
    check_warning "Health monitor fallo (revisar logs)"
fi

# ============================================================
# RESUMEN FINAL
# ============================================================

echo ""
echo "========================================"
echo "RESUMEN"
echo "========================================"
echo -e "Total de verificaciones: $TOTAL_CHECKS"
echo -e "${GREEN}Pasaron: $PASSED_CHECKS${NC}"
echo -e "${YELLOW}Warnings: $WARNING_CHECKS${NC}"
echo -e "${RED}Fallaron: $FAILED_CHECKS${NC}"
echo ""

if [ $FAILED_CHECKS -eq 0 ]; then
    if [ $WARNING_CHECKS -eq 0 ]; then
        echo -e "${GREEN}✓ Sistema completamente funcional${NC}"
        exit 0
    else
        echo -e "${YELLOW}⚠ Sistema funcional con warnings menores${NC}"
        echo "Revisar warnings arriba para optimizacion"
        exit 0
    fi
else
    echo -e "${RED}✗ Sistema con problemas criticos${NC}"
    echo "Revisar errores arriba antes de continuar"
    exit 1
fi
