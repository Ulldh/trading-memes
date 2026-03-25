# SDD Proposal: n8n-automation (Phase 2B)

**Status**: PROPOSED
**Created**: 2026-03-25
**Author**: SDD Proposal Agent

---

## 1. Intent

Automatizar el monitoreo, las alertas de senales gem, y las notificaciones de re-entrenamiento del proyecto Memecoin Gem Detector mediante 3 workflows en n8n Cloud. Estos workflows cierran el bucle operativo del sistema: el usuario recibe notificaciones proactivas en Telegram sobre la salud del sistema, nuevos candidatos gem, y cambios en los modelos ML, sin necesidad de revisar dashboards manualmente.

**Problema que resuelve**: Actualmente, el daily collector corre en GitHub Actions (06:00 UTC) y envia alerta por Telegram solo si FALLA. No hay notificacion proactiva de:
- Si la coleccion fue exitosa y cuantos datos nuevos se recopilaron
- Si hay tokens nuevos con alta probabilidad de ser gems
- Si el modelo fue re-entrenado y como cambiaron las metricas

**Por que n8n Cloud y no GitHub Actions**: n8n proporciona un editor visual, manejo nativo de credenciales, nodos HTTP/Telegram preconstruidos, logica condicional sin YAML, y separacion de concerns (CI/CD en Actions, orquestacion/alertas en n8n). Ademas, n8n puede encadenar workflows y reaccionar a eventos de forma mas flexible.

---

## 2. Scope

### 2.1 Dentro del alcance (IN)

**Workflow 1 - Health Monitor** (Cron: 07:00 UTC diario)
- Consultar Supabase REST API para verificar:
  - Tokens insertados hoy (`SELECT COUNT(*) FROM tokens WHERE first_seen >= today`)
  - OHLCV recientes (`SELECT COUNT(*) FROM ohlcv WHERE timestamp >= today`)
  - Conteos totales de todas las tablas (via `stats()` equivalente)
  - Timestamp de ultimo insert en cada tabla principal
- Verificar frescura del modelo: consultar Supabase Storage `latest_version.txt`
- Enviar resumen diario por Telegram (siempre, no solo en fallo):
  - Estado general: OK / WARNING / ERROR
  - Tokens nuevos hoy, OHLCV nuevos, totales
  - Dias desde ultimo re-entrenamiento
  - Problemas detectados (si los hay)

**Workflow 2 - Signal Notifier** (Cron: 07:30 UTC diario)
- Consultar Supabase: tokens recientes con features calculados
- Consultar tabla `features` + `tokens` para obtener datos de tokens con menos de 14 dias
- Ejecutar logica de scoring simplificada en n8n (HTTP POST a Supabase RPC o query directa):
  - Opcion A: Query features ya calculados, aplicar threshold (si el scorer corre como parte del collector)
  - Opcion B: Consultar una tabla/vista `scores` si se crea en la DB
- Filtrar candidatos con probabilidad > 0.65 (MEDIUM o superior)
- Para cada candidato, formatear mensaje Telegram con:
  - Nombre, simbolo, chain
  - Probabilidad y nivel de senal (STRONG/MEDIUM)
  - Metricas clave: liquidez, volumen 24h, edad
  - Links a DexScreener (`https://dexscreener.com/{chain}/{token_id}`)
  - Links a GeckoTerminal (`https://www.geckoterminal.com/{chain_id}/pools/{pool_address}`)
- Si no hay candidatos, enviar breve mensaje "Sin senales hoy"

**Workflow 3 - Retrain Notifier** (Cron: 09:00 UTC lunes, despues del check-retrain de 08:00)
- Consultar Supabase Storage: descargar `latest_version.txt` y `{version}/metadata.json`
- Comparar version actual con la version guardada en n8n (variable estatica o Supabase KV)
- Si hay nueva version:
  - Extraer metricas: RF val_f1, XGB val_f1, train_size, n_features
  - Comparar con metricas anteriores (guardadas en la ejecucion previa)
  - Enviar Telegram con tabla comparativa: old vs new
  - Indicar si hubo mejora o degradacion
- Si no hay nueva version: enviar breve confirmacion

### 2.2 Fuera del alcance (OUT)
- Ejecutar scoring ML dentro de n8n (demasiado pesado; el scoring debe correr en GitHub Actions o Render)
- Modificar el collector o el pipeline de retrain existentes
- Crear nuevas tablas en Supabase (se usan las existentes)
- Webhook para eventos en tiempo real (fase futura)
- Alertas de X/Twitter (requiere API key de $100/mes, descartado)

### 2.3 Componentes impactados
- **n8n Cloud**: 3 workflows nuevos (no existe nada previo)
- **Supabase**: Solo lectura (queries REST API a tablas existentes + Storage read)
- **Telegram Bot**: Envio de mensajes (bot ya configurado y verificado)
- **Codigo Python**: Posible adicion de una vista/query SQL para facilitar el scoring query

---

## 3. Approach

### 3.1 Arquitectura general

```
                    n8n Cloud
                    =========
  07:00 UTC         07:30 UTC          09:00 UTC (Lun)
  +-----------+     +-----------+      +-----------+
  | Health    |     | Signal    |      | Retrain   |
  | Monitor   |     | Notifier  |      | Notifier  |
  +-----------+     +-----------+      +-----------+
       |                 |                   |
       v                 v                   v
  +----------+     +----------+      +---------------+
  | Supabase |     | Supabase |      | Supabase      |
  | REST API |     | REST API |      | REST + Storage|
  | (DB)     |     | (DB)     |      | API           |
  +----------+     +----------+      +---------------+
       |                 |                   |
       v                 v                   v
  +----------+     +----------+      +----------+
  | Telegram |     | Telegram |      | Telegram |
  | Bot API  |     | Bot API  |      | Bot API  |
  +----------+     +----------+      +----------+
```

### 3.2 Credenciales n8n

Se configuraran las siguientes credenciales en n8n Cloud:

| Credencial | Tipo | Uso |
|------------|------|-----|
| Supabase API | HTTP Header Auth | `Authorization: Bearer {service_role_key}`, `apikey: {service_role_key}` |
| Telegram Bot | Telegram API | Token: `8317359629:AAFT...` + Chat ID: `1558705287` |

### 3.3 Workflow 1 - Health Monitor (detalle de nodos)

```
[Cron Trigger 07:00 UTC]
    |
[HTTP Request: Supabase - Count tokens today]
    POST https://xayfwuqbbqtyerxzjbec.supabase.co/rest/v1/rpc/exec_query
    Body: { "q": "SELECT COUNT(*) as cnt FROM tokens WHERE first_seen::date = CURRENT_DATE" }
    |
[HTTP Request: Supabase - Count OHLCV today]
    POST .../rpc/exec_query
    Body: { "q": "SELECT COUNT(*) as cnt FROM ohlcv WHERE timestamp::date = CURRENT_DATE" }
    |
[HTTP Request: Supabase - Table stats]
    POST .../rpc/exec_query
    Body: { "q": "SELECT 'tokens' as t, COUNT(*) as c FROM tokens UNION ALL SELECT 'ohlcv', COUNT(*) FROM ohlcv UNION ALL SELECT 'labels', COUNT(*) FROM labels UNION ALL SELECT 'features', COUNT(*) FROM features" }
    |
[HTTP Request: Supabase Storage - latest_version.txt]
    GET .../storage/v1/object/public/ml-models/latest_version.txt
    |
[HTTP Request: Supabase Storage - metadata.json]
    GET .../storage/v1/object/public/ml-models/{version}/metadata.json
    |
[Code Node: Build health report]
    - Evaluar si tokens_today > 0 (OK) o == 0 (WARNING)
    - Calcular dias desde ultimo retrain (from metadata.trained_at)
    - Construir mensaje Markdown para Telegram
    |
[IF: Has issues?]
    |-- Yes --> [Telegram: Send alert message (con emoji rojo)]
    |-- No  --> [Telegram: Send daily summary (con emoji verde)]
```

**Queries Supabase clave**:
```sql
-- Tokens descubiertos hoy
SELECT COUNT(*) as cnt FROM tokens WHERE first_seen::date = CURRENT_DATE;

-- OHLCV insertados hoy
SELECT COUNT(*) as cnt FROM ohlcv WHERE timestamp::date = CURRENT_DATE;

-- Ultimo snapshot (para saber si collector corrio)
SELECT MAX(snapshot_time) as last_snapshot FROM pool_snapshots;

-- Totales por tabla
SELECT 'tokens' as tabla, COUNT(*) as total FROM tokens
UNION ALL SELECT 'ohlcv', COUNT(*) FROM ohlcv
UNION ALL SELECT 'labels', COUNT(*) FROM labels
UNION ALL SELECT 'features', COUNT(*) FROM features;
```

### 3.4 Workflow 2 - Signal Notifier (detalle de nodos)

**Prerequisito**: El daily collector (06:00 UTC) ya calcula features para tokens nuevos y los guarda en la tabla `features`. Para el scoring, se necesita una de estas opciones:

- **Opcion A (recomendada)**: Agregar un paso al daily-collect GitHub Action que ejecute el scorer y guarde resultados en una tabla `scores` en Supabase. n8n solo consulta `scores`.
- **Opcion B (fallback)**: n8n consulta `features` directamente y aplica un threshold simple sobre features clave (sin modelo ML completo, heuristica basada en SHAP top features).

```
[Cron Trigger 07:30 UTC]
    |
[HTTP Request: Supabase - Get recent high-score tokens]
    -- Opcion A: si tabla scores existe --
    POST .../rpc/exec_query
    Body: { "q": "SELECT s.*, t.name, t.symbol, t.chain, t.pool_address
                   FROM scores s JOIN tokens t ON s.token_id = t.token_id
                   WHERE s.scored_at::date = CURRENT_DATE
                   AND s.probability >= 0.65
                   ORDER BY s.probability DESC LIMIT 20" }
    |
[IF: Has candidates?]
    |-- No  --> [Telegram: "Sin senales gem hoy"]
    |-- Yes --> [Split In Batches: process each token]
                    |
                [Code Node: Format token message]
                    - Nombre: {{symbol}} ({{chain}})
                    - Probabilidad: {{probability}}%
                    - Senal: {{signal}}
                    - Link DexScreener: https://dexscreener.com/{{chain}}/{{token_id}}
                    |
                [Telegram: Send formatted message per candidate]
```

**Formato del mensaje Telegram**:
```
=== GEM CANDIDATES ===

1. PEPE (solana)
   Probabilidad: 82.3% | Senal: STRONG
   Liquidez: $45.2K | Vol 24h: $12.8K
   DexScreener: https://dexscreener.com/solana/abc123...

2. DOGE2 (base)
   Probabilidad: 71.5% | Senal: MEDIUM
   ...

Total: 2 candidatos | Fecha: 2026-03-25
```

### 3.5 Workflow 3 - Retrain Notifier (detalle de nodos)

```
[Cron Trigger 09:00 UTC Monday]
    |
[HTTP Request: Supabase Storage - latest_version.txt]
    GET .../storage/v1/object/public/ml-models/latest_version.txt
    |
[Code Node: Compare with stored version]
    - Leer version previa de n8n static data (o Supabase KV table)
    - Si es la misma: saltar
    |
[IF: New version detected?]
    |-- No  --> [Telegram: "Modelo sin cambios. Version actual: v12"]
    |-- Yes --> [HTTP Request: Supabase Storage - new metadata.json]
                    GET .../storage/v1/object/public/ml-models/{new_version}/metadata.json
                    |
                [HTTP Request: Supabase Storage - old metadata.json]
                    GET .../storage/v1/object/public/ml-models/{old_version}/metadata.json
                    |
                [Code Node: Compare metrics]
                    - RF val_f1: old vs new (+ delta %)
                    - XGB val_f1: old vs new (+ delta %)
                    - Train size: old vs new
                    - Determinar: mejora / degradacion / lateral
                    |
                [Code Node: Update stored version]
                    - Guardar nueva version en n8n static data
                    |
                [Telegram: Send comparison report]
```

**Formato del mensaje Telegram**:
```
=== MODELO RE-ENTRENADO ===

Version: v12 -> v13
Fecha: 2026-03-25

             v12    v13    Delta
RF Val F1:   0.667  0.701  +5.1%
XGB Val F1:  0.595  0.623  +4.7%
Train size:  1467   1650   +183

Resultado: MEJORA

Artefactos en Supabase Storage OK
```

### 3.6 Dependencia clave: tabla `scores`

Para que el Signal Notifier funcione con datos reales del modelo ML, se recomienda:

1. Crear tabla `scores` en Supabase:
```sql
CREATE TABLE scores (
    token_id    TEXT PRIMARY KEY REFERENCES tokens(token_id),
    probability REAL NOT NULL,
    signal      TEXT NOT NULL,       -- STRONG, MEDIUM, WEAK, NONE
    prediction  INTEGER NOT NULL,    -- 1=gem, 0=no-gem
    model_name  TEXT DEFAULT 'random_forest',
    scored_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_scores_probability ON scores(probability DESC);
CREATE INDEX idx_scores_scored_at ON scores(scored_at);
```

2. Agregar paso de scoring al workflow `daily-collect.yml` (despues del collector):
```yaml
- name: Score new tokens
  run: |
    python -c "
    from src.models.scorer import GemScorer
    scorer = GemScorer()
    results = scorer.score_all_new()
    if not results.empty:
        from src.data.supabase_storage import get_storage
        storage = get_storage()
        # Upsert scores to DB
        for _, row in results.iterrows():
            storage.upsert('scores', row.to_dict(), conflict_column='token_id')
    "
```

**Alternativa sin tabla scores**: El Signal Notifier puede funcionar con una query heuristica sobre `features` usando los top SHAP features (ej: `initial_liquidity_usd > 5000 AND volume_1h > 1000 AND volatility_24h < 5`), pero sera menos preciso que el modelo completo.

---

## 4. Risks

| # | Riesgo | Impacto | Probabilidad | Mitigacion |
|---|--------|---------|--------------|------------|
| R1 | Supabase RPC (`exec_query`) requiere service_role key; si se compromete, acceso total a DB | Alto | Baja | Usar credenciales seguras en n8n; exec_query es solo SELECT en estos workflows; considerar crear funciones SQL especificas read-only |
| R2 | n8n Cloud free tier tiene limite de ejecuciones (puede no ser suficiente) | Medio | Media | 3 workflows * ~30 ejecuciones/mes = ~90 ejecuciones. Free tier de n8n Cloud da ~300/mes. Monitorear uso |
| R3 | Supabase Storage URLs publicas exponen archivos del bucket ml-models | Bajo | Baja | Los modelos ML no son secretos; metadata.json no contiene datos sensibles. Si preocupa, usar signed URLs |
| R4 | El Signal Notifier sin tabla `scores` no puede usar el modelo ML real | Alto | Media | Implementar la tabla scores (recomendado) O aceptar heuristica de features como v1 temporal |
| R5 | Telegram rate limiting si hay muchos candidatos (>30 por dia) | Bajo | Baja | Agrupar candidatos en un solo mensaje (no un mensaje por token). Limite: 30 mensajes/segundo |
| R6 | Desfase temporal: si el collector tarda >1h, Health Monitor a las 07:00 no vera datos de hoy | Medio | Baja | Ajustar cron del Health Monitor a 08:00 UTC si se observa desfase; el collector actual tarda ~20min |
| R7 | El formato de metadata.json puede cambiar entre versiones de modelo | Bajo | Baja | Validar campos en Code Node con fallbacks; el formato es estable desde v10 |

---

## 5. Dependencies

### 5.1 Infraestructura existente (ya configurada)
- **Supabase**: Proyecto `xayfwuqbbqtyerxzjbec` con DB poblada (4028 tokens, 86728 OHLCV, 1467 labels, 4028 features) y Storage bucket `ml-models` con modelos v12
- **Telegram Bot**: Token `8317359629:AAFT_knnE98NZtKeDrVN1Qh73wbWSba-czA`, Chat ID `1558705287`, verificado y funcionando
- **GitHub Actions**: 4 workflows existentes (ci, daily-collect, check-retrain, manual-retrain) con secrets configurados
- **Supabase RPC functions**: `exec_query(text)` y `exec_sql(text)` disponibles con service_role key

### 5.2 Dependencias nuevas (por crear)
- **n8n Cloud account**: Se necesita crear cuenta y configurar credenciales
- **Tabla `scores` en Supabase** (recomendada para Workflow 2): Migracion SQL para crear tabla + indice
- **Paso de scoring en daily-collect.yml** (recomendado): Agregar step que ejecute GemScorer despues de la recoleccion
- **n8n MCP**: Ya configurado en `~/.claude/.mcp.json` con API key; requiere reiniciar Claude Code para cargar

### 5.3 Dependencias entre workflows
- Workflow 1 (Health) es independiente
- Workflow 2 (Signal) depende de que exista la tabla `scores` O acepta heuristica temporal
- Workflow 3 (Retrain) es independiente (lee directamente de Supabase Storage)
- Los 3 workflows dependen de credenciales Supabase + Telegram configuradas en n8n

---

## 6. Estimation

| Componente | Esfuerzo estimado |
|------------|-------------------|
| Configurar credenciales n8n Cloud | 15 min |
| Workflow 1 - Health Monitor | 1-2 horas |
| Workflow 2 - Signal Notifier | 2-3 horas |
| Workflow 3 - Retrain Notifier | 1-2 horas |
| Tabla `scores` + migracion SQL | 30 min |
| Scoring step en daily-collect.yml | 30 min |
| Testing y ajustes de formato Telegram | 1 hora |
| **Total estimado** | **6-9 horas** |

---

## 7. Next Recommended Steps

1. **sdd-spec**: Especificar contratos de cada workflow (inputs, outputs, formatos de mensaje, queries SQL exactas)
2. **sdd-design**: Disenar nodos n8n detallados, manejo de errores, y formato de mensajes Telegram
3. **sdd-tasks**: Desglosar en tareas implementables (crear credenciales, crear cada workflow, crear tabla scores, modificar daily-collect, testing)

---

## 8. Decision Log

| # | Decision | Razon |
|---|----------|-------|
| D1 | Usar Supabase RPC `exec_query` en lugar de PostgREST directo | Queries complejas (JOINs, UNION ALL, aggregates) no se pueden expresar facilmente en PostgREST |
| D2 | Recomendar tabla `scores` vs query de features en n8n | El modelo ML completo no se puede ejecutar en n8n; guardar scores pre-calculados es mas preciso y mas rapido |
| D3 | Cron timings: 07:00 / 07:30 / 09:00 | Health despues del collector (06:00), Signal 30min despues de health, Retrain 1h despues del check (08:00 lunes) |
| D4 | Un mensaje agrupado vs mensaje por token | Evita spam en Telegram; mas legible; respeta rate limits |
| D5 | n8n static data para guardar version previa del modelo | Evita crear tabla auxiliar en Supabase; n8n tiene KV store nativo por workflow |
