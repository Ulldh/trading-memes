# 🏥 Health Checks & Backups - Guía Rápida

Sistema de monitoreo y respaldos automáticos implementado y listo para usar.

---

## 🎯 ¿Qué se implementó?

### ✅ Health Monitor (Python)
- **Archivo**: `src/monitoring/health_monitor.py`
- **Función**: Verifica estado del sistema (APIs, DB, disco, última recolección)
- **Tests**: ✓ Funciona correctamente

### ✅ Scripts Automáticos (Bash)
1. **`scripts/health_check.sh`** - Health check cada 6h
2. **`scripts/backup_db.sh`** - Backup diario a las 04:00
3. **`scripts/restore_from_backup.sh`** - Restauración de backups
4. **`scripts/setup_monitoring.sh`** - Instalador automático

### ✅ Configuración launchd (macOS)
- **`com.tradingmemes.healthcheck.plist`** - Ejecuta health check cada 6h
- **`com.tradingmemes.backup.plist`** - Ejecuta backup diario a las 04:00

### ✅ Documentación
- **`docs/MONITORING.md`** - Documentación completa del sistema

---

## 🚀 Instalación en 3 Pasos

### Paso 1: Instalar el sistema

```bash
./scripts/setup_monitoring.sh
```

Esto configurará automáticamente:
- ✅ Directorios necesarios
- ✅ launchd agents
- ✅ Verificación de instalación

### Paso 2: Configurar alertas (opcional)

Edita tu archivo `.env`:

```bash
# Para alertas por email
NOTIFICATION_EMAIL=tu-email@gmail.com

# Para alertas por Telegram
TELEGRAM_BOT_TOKEN=tu_bot_token
TELEGRAM_CHAT_ID=tu_chat_id
```

### Paso 3: Verificar que funciona

```bash
# Ver servicios activos
launchctl list | grep tradingmemes

# Ejecutar health check manual
./scripts/health_check.sh

# Ejecutar backup manual
./scripts/backup_db.sh
```

---

## 📊 ¿Qué hace automáticamente?

### Health Checks (Cada 6 horas)

```
✓ APIs: Verifica que GeckoTerminal, DexScreener, Solana RPC, Etherscan respondan
✓ DB: Verifica que la base de datos esté creciendo (OHLCV recientes)
✓ Disco: Verifica que haya >1GB libre
✓ Recolección: Verifica que la última recolección fue <26h atrás
```

**Si detecta problemas**: Envía alertas por email/Telegram.

### Backups (Diario a las 04:00)

```
1. Copia trading_memes.db → data/backups/YYYY-MM-DD/
2. Exporta todas las tablas a Parquet
3. Genera metadata.json con estadísticas
4. Limpia backups de >30 días
```

**Resultado**: Backups completos listos para restaurar en cualquier momento.

---

## 🛠️ Uso Diario

### Ver Logs

```bash
# Health checks
tail -f logs/health_check.log

# Backups
tail -f logs/backup.log

# Estado actual (JSON)
cat logs/health_status.json
```

### Ejecutar Manualmente

```bash
# Health check
./scripts/health_check.sh

# Backup
./scripts/backup_db.sh

# Restaurar backup más reciente
./scripts/restore_from_backup.sh

# Restaurar backup específico
./scripts/restore_from_backup.sh 2026-02-26
```

### Ver Estado del Sistema

```bash
# Servicios activos
launchctl list | grep tradingmemes

# Backups disponibles
ls -lh data/backups/

# Tamaño de backups
du -sh data/backups/*
```

---

## 📈 Ejemplo de Health Check

### Estado Saludable

```
==================================================
HEALTH CHECK - Trading Memes
==================================================
Timestamp: 2026-02-27T10:36:57.735982+00:00
Estado: ✓ SALUDABLE

DETALLES:
  ✓ apis: Todas las APIs respondiendo correctamente
  ✓ database: Base de datos saludable (190 tokens, 155 OHLCV recientes)
  ✓ disk: Espacio en disco suficiente: 200.79 GB libres
  ✓ collection: Recoleccion reciente (hace 12.3 horas)
==================================================
```

### Estado con Problemas

```
==================================================
HEALTH CHECK - Trading Memes
==================================================
Timestamp: 2026-02-27T10:36:57.735982+00:00
Estado: ✗ PROBLEMAS DETECTADOS

ERRORES:
  ✗ collection: Ultima recoleccion hace 34.6 horas (>26h)

WARNINGS:
  ⚠ apis: 1/4 APIs con problemas

DETALLES:
  ⚠ apis: 1/4 APIs con problemas
  ✓ database: Base de datos saludable (190 tokens, 155 OHLCV recientes)
  ✓ disk: Espacio en disco suficiente: 200.79 GB libres
  ✗ collection: Ultima recoleccion hace 34.6 horas (>26h)
==================================================
```

---

## 📦 Ejemplo de Backup

### Estructura Generada

```
data/backups/2026-02-27/
├── trading_memes_2026-02-27_04-00-00.db  (Copia SQLite)
├── trading_memes.db -> trading_memes_2026-02-27_04-00-00.db
├── metadata.json
└── parquet/
    ├── tokens.parquet
    ├── pool_snapshots.parquet
    ├── ohlcv.parquet
    ├── holder_snapshots.parquet
    ├── contract_info.parquet
    ├── labels.parquet
    └── features.parquet
```

### Metadata JSON

```json
{
  "backup_date": "2026-02-27",
  "backup_timestamp": "2026-02-27_04-00-00",
  "db_stats": {
    "tokens": 190,
    "pool_snapshots": 215,
    "ohlcv": 2550,
    "holder_snapshots": 700,
    "contract_info": 91,
    "labels": 91,
    "features": 190
  },
  "db_size_bytes": 1572864,
  "created_at": "2026-02-27T04:00:05+00:00"
}
```

---

## ⚠️ Troubleshooting Rápido

### Problema: Health check no se ejecuta

```bash
# Verificar que el agent esté cargado
launchctl list | grep healthcheck

# Si no aparece, reinstalar
./scripts/setup_monitoring.sh
```

### Problema: Backup falla

```bash
# Ver logs detallados
tail -50 logs/backup.log

# Verificar permisos
chmod +x scripts/backup_db.sh

# Ejecutar manualmente para ver error
./scripts/backup_db.sh
```

### Problema: Quiero desinstalar todo

```bash
# Descargar agents
launchctl unload ~/Library/LaunchAgents/com.tradingmemes.healthcheck.plist
launchctl unload ~/Library/LaunchAgents/com.tradingmemes.backup.plist

# Eliminar archivos
rm ~/Library/LaunchAgents/com.tradingmemes.*.plist

# (Opcional) Eliminar backups
rm -rf data/backups/
```

---

## 🔔 Configurar Telegram Bot (Paso a Paso)

### 1. Crear Bot

1. Habla con [@BotFather](https://t.me/botfather) en Telegram
2. Envía `/newbot`
3. Sigue las instrucciones (nombre y username)
4. Guarda el **TOKEN** que te da

### 2. Obtener Chat ID

1. Envía un mensaje a [@userinfobot](https://t.me/userinfobot)
2. Te responderá con tu **Chat ID**

### 3. Configurar en .env

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

### 4. Probar

```bash
# Ejecutar health check (simulará alerta si hay problemas)
./scripts/health_check.sh
```

---

## 📚 Documentación Completa

Para más detalles, ver: [`docs/MONITORING.md`](docs/MONITORING.md)

---

## ✅ Checklist de Verificación

Después de instalar, verifica que todo funcione:

- [ ] `launchctl list | grep tradingmemes` muestra 2 servicios
- [ ] `./scripts/health_check.sh` se ejecuta sin errores
- [ ] `./scripts/backup_db.sh` crea backup en `data/backups/`
- [ ] `ls data/backups/` muestra carpeta con fecha de hoy
- [ ] `cat logs/health_status.json` muestra JSON válido
- [ ] (Opcional) Alertas por email/Telegram funcionan

---

## 🎉 ¡Listo!

Tu sistema ahora tiene:
- ✅ Monitoreo automático cada 6 horas
- ✅ Backups diarios a las 04:00
- ✅ Alertas cuando hay problemas
- ✅ Restauración fácil de cualquier backup

**Próximo paso**: Esperar a que el sistema funcione automáticamente. Si detecta problemas, recibirás una notificación.

---

**Creado**: 2026-02-27
**Versión**: 1.0
