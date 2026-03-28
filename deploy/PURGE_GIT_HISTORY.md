# Purga de Secretos del Historial Git

## Estado de los secretos

| Secreto | Estado | Riesgo actual |
|---------|--------|---------------|
| Telegram Bot Token (`AAFT_...`) | REVOCADO y rotado | Ninguno (token invalido) |
| Supabase JWT (service_role) | ROTADO | Ninguno (JWT antiguo invalido) |
| Telegram Chat ID (`1558705287`) | No es secreto | Bajo (es un ID de usuario publico) |

**Todos los secretos expuestos han sido revocados/rotados.** Esta purga es una limpieza preventiva, no una respuesta a una vulnerabilidad activa.

## Requisitos previos

```bash
# Instalar BFG Repo-Cleaner
brew install bfg
```

## Pasos para purgar el historial

### 1. Hacer backup del repositorio

```bash
# Clonar una copia de seguridad ANTES de purgar
cd ~/Desktop
git clone --mirror https://github.com/Ulldh/trading-memes.git trading-memes-backup.git
```

### 2. Clonar mirror fresco para la purga

```bash
# BFG requiere un clone --mirror
git clone --mirror https://github.com/Ulldh/trading-memes.git trading-memes-purge.git
cd trading-memes-purge.git
```

### 3. Ejecutar BFG con el archivo de patrones

```bash
# El archivo secrets_to_purge.txt esta en deploy/ del repo original
# Copiarlo a una ubicacion accesible
cp "/ruta/al/repo/deploy/secrets_to_purge.txt" /tmp/secrets_to_purge.txt

# Ejecutar BFG para reemplazar los secretos con ***REMOVED***
bfg --replace-text /tmp/secrets_to_purge.txt trading-memes-purge.git
```

### 4. Limpiar los objetos git

```bash
cd trading-memes-purge.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### 5. Force push al remoto

```bash
# ATENCION: Esto reescribe TODO el historial del repositorio
# Todos los colaboradores deberan re-clonar despues de esto
git push --force
```

### 6. Verificar la purga

```bash
# Clonar de nuevo y verificar que los secretos no aparecen
cd ~/Desktop
git clone https://github.com/Ulldh/trading-memes.git trading-memes-verify
cd trading-memes-verify

# Buscar en todo el historial
git log --all -p | grep -c "AAFT_"
# Debe devolver 0

git log --all -p | grep -c "eyJhbGciOiJIUzI1NiI"
# Debe devolver 0
```

### 7. Limpiar archivos temporales

```bash
# Borrar el backup mirror y el archivo de secretos
rm -rf ~/Desktop/trading-memes-backup.git
rm -rf ~/Desktop/trading-memes-purge.git
rm -rf ~/Desktop/trading-memes-verify
rm /tmp/secrets_to_purge.txt

# Borrar este archivo y secrets_to_purge.txt del repo (ya no son necesarios)
# O mantenerlos como documentacion sin los valores reales
```

## Post-purga

- [ ] Todos los colaboradores deben re-clonar el repositorio (el historial cambio)
- [ ] Verificar que GitHub Actions sigue funcionando (los workflows no se ven afectados)
- [ ] Eliminar `deploy/secrets_to_purge.txt` del repo (contiene los secretos a purgar)

## Notas importantes

1. **BFG no modifica el commit HEAD actual**, solo el historial anterior. Como los secretos ya fueron eliminados del HEAD en el commit `5fb50c7`, esto es exactamente lo que queremos.
2. **El Chat ID de Telegram (`1558705287`)** aparece 33 veces en el historial pero NO se incluye en la purga porque no es un secreto (es un ID de usuario publico de la API de Telegram). Si se desea purgar por privacidad, agregarlo a `secrets_to_purge.txt`.
3. **No se encontraron** claves de Stripe (`sk_live_`), webhooks (`whsec_`), ni otros secretos de produccion en el historial git.
