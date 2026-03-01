# Sistema de Monitoreo y Backups

Este documento explica el sistema de monitoreo y respaldos automáticos del proyecto Trading Memes.

## 📋 Tabla de Contenidos

1. [Resumen](#resumen)
2. [Health Checks](#health-checks)
3. [Backups Automáticos](#backups-automáticos)
4. [Instalación](#instalación)
5. [Configuración de Alertas](#configuración-de-alertas)
6. [Uso Manual](#uso-manual)
7. [Troubleshooting](#troubleshooting)

---

## Resumen

El sistema de monitoreo consta de dos componentes principales:

### 1. Health Checks (Cada 6 horas)
- ✅ Verifica que las APIs estén respondiendo
- ✅ Verifica que la base de datos esté creciendo
- ✅ Verifica espacio en disco
- ✅ Verifica que la recolección diaria se ejecute

### 2. Backups Automáticos (Diario a las 04:00)
- ✅ Copia la base de datos SQLite
- ✅ Exporta todas las tablas a formato Parquet
- ✅ Mantiene backups de los últimos 30 días
- ✅ Genera metadata JSON de cada backup

---

## Health Checks

### ¿Qué verifica?

El health monitor ejecuta 4 verificaciones:

#### 1. APIs
Prueba cada API con una llamada simple:
- **GeckoTerminal**: `get_trending_pools()`
- **DexScreener**: `get_token_profile()`
- **Solana RPC**: `get_token_holders()`
- **Etherscan**: `get_contract_source()`

**Estado OK**: Todas las APIs responden correctamente
**Warning**: 1-2 APIs con problemas
**Error**: 3+ APIs fallando

#### 2. Base de Datos
- Verifica que el archivo `trading_memes.db` existe
- Cuenta registros OHLCV de las últimas 48h
- Obtiene estadísticas generales (tokens, snapshots, etc.)

**Estado OK**: DB accesible y creciendo (nuevos OHLCV en 48h)
**Warning**: DB accesible pero sin crecimiento reciente
**Error**: DB no accesible o vacía

#### 3. Espacio en Disco
- Verifica espacio libre en el disco del proyecto
- Threshold por defecto: 1 GB mínimo

**Estado OK**: > 2 GB libres
**Warning**: Entre 1-2 GB libres
**Error**: < 1 GB libre

#### 4. Última Recolección
- Busca el timestamp más reciente en tabla `ohlcv`
- Threshold: 26 horas (24h + 2h de margen)

**Estado OK**: Recolección en últimas 24h
**Warning**: Entre 24-26h desde última recolección
**Error**: > 26h sin recolección

### Frecuencia

El health check se ejecuta automáticamente cada **6 horas** via launchd.

### Logs

Todos los checks se registran en:
```
logs/health_check.log
logs/health_status.json (último estado en JSON)
```

### Alertas

Si el sistema detecta problemas, envía alertas por:
- ✉️ **Email** (si `NOTIFICATION_EMAIL` configurado)
- 📱 **Telegram** (si `TELEGRAM_BOT_TOKEN` configurado)

---

## Backups Automáticos

### ¿Qué respalda?

Cada backup incluye:

1. **Copia SQLite**: `trading_memes_YYYY-MM-DD_HH-MM-SS.db`
2. **Export Parquet**: Una carpeta `parquet/` con:
   - `tokens.parquet`
   - `pool_snapshots.parquet`
   - `ohlcv.parquet`
   - `holder_snapshots.parquet`
   - `contract_info.parquet`
   - `labels.parquet`
   - `features.parquet`
3. **Metadata**: `metadata.json` con estadísticas del backup

### Estructura de Backups

```
data/backups/
├── 2026-02-26/
│   ├── trading_memes_2026-02-26_04-00-00.db
│   ├── trading_memes.db -> trading_memes_2026-02-26_04-00-00.db (symlink)
│   ├── metadata.json
│   └── parquet/
│       ├── tokens.parquet
│       ├── pool_snapshots.parquet
│       ├── ohlcv.parquet
│       └── ...
├── 2026-02-27/
│   └── ...
└── 2026-02-28/
    └── ...
```

### Retention Policy

- **Automático**: Backups de más de 30 días se eliminan automáticamente
- **Manual**: Puedes ajustar `RETENTION_DAYS` en `backup_db.sh`

### Frecuencia

El backup se ejecuta automáticamente **diario a las 04:00** via launchd.

> **Nota**: El backup se ejecuta 1 hora después de la recolección diaria (03:00) para asegurar que capture los datos más recientes.

### Logs

```
logs/backup.log
```

---

## Instalación

### 1. Ejecutar Script de Setup

```bash
./scripts/setup_monitoring.sh
```

Este script:
- ✅ Crea directorios necesarios (`logs/`, `data/backups/`)
- ✅ Instala los launchd agents
- ✅ Verifica la instalación

### 2. Verificar Estado

```bash
launchctl list | grep tradingmemes
```

Deberías ver:
```
com.tradingmemes.healthcheck
com.tradingmemes.backup
```

### 3. Ver Logs

```bash
# Health checks
tail -f logs/health_check.log

# Backups
tail -f logs/backup.log
```

---

## Configuración de Alertas

### Email (Gmail SMTP)

Añade a tu archivo `.env`:

```bash
NOTIFICATION_EMAIL=tu-email@gmail.com
```

> **Nota**: Para usar Gmail SMTP necesitas configurar una App Password en tu cuenta de Google.

### Telegram Bot

1. Crea un bot con [@BotFather](https://t.me/botfather)
2. Obtén el `BOT_TOKEN`
3. Obtén tu `CHAT_ID` (envia un mensaje a [@userinfobot](https://t.me/userinfobot))

Añade a tu `.env`:

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

### Probar Alertas

```bash
# Simular un health check con problemas
./scripts/health_check.sh
```

Si hay problemas detectados, deberías recibir una notificación.

---

## Uso Manual

### Health Check Manual

```bash
./scripts/health_check.sh
```

Salida ejemplo:
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

### Backup Manual

```bash
./scripts/backup_db.sh
```

Salida ejemplo:
```
[2026-02-27 10:00:00] Iniciando Backup
[2026-02-27 10:00:01] ✓ SQLite backup completado (1.5M)
[2026-02-27 10:00:05] ✓ Export a Parquet completado
[2026-02-27 10:00:06] ✓ Metadata generado
[2026-02-27 10:00:07] Backup completado exitosamente
Backup location: /path/to/data/backups/2026-02-27
```

### Restaurar desde Backup

#### Restaurar el backup más reciente:

```bash
./scripts/restore_from_backup.sh
```

#### Restaurar un backup específico:

```bash
./scripts/restore_from_backup.sh 2026-02-26
```

**⚠️ ADVERTENCIA**: La restauración sobrescribe la base de datos actual. Se crea un backup de seguridad automáticamente antes de restaurar.

### Listar Backups Disponibles

```bash
ls -lh data/backups/
```

---

## Troubleshooting

### Problema: "Health check agent no está activo"

**Solución**:
```bash
# Descargar agent
launchctl unload ~/Library/LaunchAgents/com.tradingmemes.healthcheck.plist

# Recargar agent
launchctl load ~/Library/LaunchAgents/com.tradingmemes.healthcheck.plist

# Verificar
launchctl list | grep healthcheck
```

### Problema: "Backup falla con Permission Denied"

**Solución**:
```bash
# Verificar permisos del script
chmod +x scripts/backup_db.sh

# Verificar permisos del directorio
chmod 755 data/backups/
```

### Problema: "APIs fallando en health check"

**Causas comunes**:
1. **Internet desconectado**: Verifica tu conexión
2. **Rate limit excedido**: Espera unos minutos y reintenta
3. **API temporalmente caída**: Normal, el próximo check debería pasar

**Solución**:
```bash
# Ejecutar health check manual para ver detalle
./scripts/health_check.sh

# Ver logs de APIs
grep "ERROR" logs/health_check.log | tail -20
```

### Problema: "DB no ha crecido en 48h"

**Solución**:
```bash
# Verificar que la recolección diaria esté activa
launchctl list | grep dailycollect

# Ejecutar recolección manualmente
./scripts/daily_collect.sh

# Verificar logs
tail -50 logs/daily_collect.log
```

### Problema: "Espacio en disco bajo"

**Solución**:
```bash
# Ver uso de disco del proyecto
du -h -d 1 .

# Limpiar backups viejos manualmente
rm -rf data/backups/2026-01-*

# Limpiar cache
rm -rf .cache/*

# Limpiar logs antiguos
find logs/ -name "*.log" -mtime +30 -delete
```

### Problema: "Restauración falló, DB corrupta"

**Solución**:
```bash
# El script crea un backup de seguridad automáticamente
# Buscar el backup de seguridad
ls -lh data/*.db.before_restore_*

# Restaurar el backup de seguridad
cp data/trading_memes.db.before_restore_YYYYMMDD_HHMMSS data/trading_memes.db

# Intentar con otro backup
./scripts/restore_from_backup.sh 2026-02-25
```

---

## Comandos Útiles

### Ver estado de todos los servicios

```bash
launchctl list | grep tradingmemes
```

### Ver logs en tiempo real

```bash
# Health checks
tail -f logs/health_check.log

# Backups
tail -f logs/backup.log

# Launchd output
tail -f logs/launchd_healthcheck_out.log
tail -f logs/launchd_backup_out.log
```

### Forzar ejecución de un job

```bash
# Health check
launchctl start com.tradingmemes.healthcheck

# Backup
launchctl start com.tradingmemes.backup
```

### Desinstalar monitoreo

```bash
# Descargar agents
launchctl unload ~/Library/LaunchAgents/com.tradingmemes.healthcheck.plist
launchctl unload ~/Library/LaunchAgents/com.tradingmemes.backup.plist

# Eliminar archivos
rm ~/Library/LaunchAgents/com.tradingmemes.*.plist
```

### Ver tamaño de backups

```bash
du -sh data/backups/*
```

### Comprimir backups antiguos

```bash
# Comprimir backups de más de 14 días
find data/backups/ -type d -name "20*" -mtime +14 -exec tar -czf {}.tar.gz {} \; -exec rm -rf {} \;
```

---

## Mejoras Futuras

- [ ] Subir backups a Google Drive / Dropbox / S3
- [ ] Dashboard web para visualizar health status
- [ ] Alertas por SMS (Twilio)
- [ ] Integración con Grafana para métricas
- [ ] Backup incremental (solo cambios)
- [ ] Compresión automática de backups antiguos
- [ ] Health check de modelos ML (drift detection)

---

**Última actualización**: 2026-02-27
