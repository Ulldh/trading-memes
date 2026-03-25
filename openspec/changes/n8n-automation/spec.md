# n8n-automation Specification

**Status**: APPROVED | **Created**: 2026-03-25

## Domain: Data Schema

### REQ-S1: Scores Table

MUST create `scores` table: `token_id TEXT PK FK, probability REAL NOT NULL, signal TEXT NOT NULL CHECK('STRONG','MEDIUM','WEAK','NONE'), prediction INT NOT NULL, model_name TEXT DEFAULT 'random_forest', model_version TEXT NOT NULL, scored_at TIMESTAMPTZ DEFAULT NOW()`. Indexes: `probability DESC`, `scored_at`.

- GIVEN daily collector completed
- WHEN scoring step runs in daily-collect.yml
- THEN unlabeled tokens with >=7d OHLCV MUST have upserted row with current model_version

- GIVEN scores table is empty
- WHEN Signal Notifier queries it
- THEN MUST send "Sin senales hoy" (not error)

## Domain: Health Monitor (07:00 UTC daily)

### REQ-H1: Daily Health Check

MUST query Supabase via RPC `exec_query` and send Telegram summary.

**Queries:** (1) `SELECT COUNT(*) FROM tokens WHERE first_seen::date=CURRENT_DATE` (2) `SELECT COUNT(*) FROM ohlcv WHERE timestamp::date=CURRENT_DATE` (3) Table totals UNION ALL for tokens/ohlcv/labels/features/scores (4) GET `ml-models/latest_version.txt` from Storage (5) GET `ml-models/{version}/metadata.json`

**Status:** OK = tokens_today>0 AND ohlcv_today>0 AND model_age<=30d. WARNING = any zero or stale. ERROR = HTTP failure.

- GIVEN collector inserted data today
- WHEN Health Monitor runs
- THEN MUST send OK with: new tokens, new OHLCV, totals, model version, days since retrain

- GIVEN tokens_today==0 AND ohlcv_today==0
- WHEN Health Monitor runs
- THEN MUST send WARNING indicating zero new data

- GIVEN Supabase returns non-2xx or timeout >30s
- WHEN Health Monitor runs
- THEN MUST send ERROR with failing endpoint; SHOULD continue remaining checks

### REQ-H2: Health Message Format

Template: `{emoji} HEALTH MONITOR - {STATUS}\n{date} | Model {ver}\nNuevos: Tokens {n} | OHLCV {n}\nTotales: Tokens/OHLCV/Labels/Features/Scores\nModelo: {ver} ({days}d)\n{warnings}`. Max 4096 chars. Failed metrics show "N/A".

## Domain: Signal Notifier (07:30 UTC daily)

### REQ-SN1: Daily Signal Detection

MUST query: `SELECT s.*, t.name, t.symbol, t.chain, t.pool_address FROM scores s JOIN tokens t ON s.token_id=t.token_id WHERE s.scored_at::date=CURRENT_DATE AND s.probability>=0.65 ORDER BY s.probability DESC LIMIT 20`.

- GIVEN 5 tokens scored with prob>=0.65
- WHEN Signal Notifier runs
- THEN MUST send ONE message, ordered by probability DESC, each with: symbol, chain, prob%, signal, DexScreener link

- GIVEN no tokens with prob>=0.65
- WHEN runs
- THEN MUST send "Sin senales gem hoy ({date})"

- GIVEN no scores for today
- WHEN runs
- THEN MUST send warning "No hay scores para hoy. Verificar daily-collect."

### REQ-SN2: Signal Message Format

Per candidate: `{n}. {symbol} ({chain}) | Prob: {prob}% | {signal}\nDexScreener: https://dexscreener.com/{chain}/{pool_address}`. If >20 qualify, show top 20 + "+{n} mas".

## Domain: Retrain Notifier (09:00 UTC Mondays)

### REQ-R1: Weekly Version Check

MUST GET `ml-models/latest_version.txt`, compare with n8n static data (`$getWorkflowStaticData()`).

- GIVEN latest=v13, static=v12
- WHEN runs
- THEN MUST download both metadata.json, send comparison table, update static to v13

- GIVEN latest==static version
- WHEN runs
- THEN MUST send "Modelo sin cambios. Version: {v}"

- GIVEN no static data (first run)
- WHEN runs
- THEN MUST store version, send "Retrain Notifier inicializado. Version: {v}"

- GIVEN Storage unreachable
- WHEN runs
- THEN MUST send ERROR, MUST NOT update static data

### REQ-R2: Retrain Message Format

Table: `{old}->{new} | RF Val F1: old/new/delta% | XGB Val F1: old/new/delta% | Train size: old/new/delta`. MEJORA=both F1 up. DEGRADACION=either F1 dropped >2%. LATERAL=otherwise.

## Domain: Cross-cutting

### REQ-C1: Credentials

All workflows MUST use n8n credential store. No hardcoded secrets. Credentials: Supabase HTTP Header Auth (service_role), Telegram Bot API.

### REQ-C2: Error Resilience

Individual query failures MUST NOT abort workflow. Failed metrics render as "N/A".

### REQ-C3: Configurable Parameters

| Param | Default | Workflow |
|-------|---------|---------|
| SCORE_THRESHOLD | 0.65 | Signal |
| MAX_CANDIDATES | 20 | Signal |
| MODEL_STALE_DAYS | 30 | Health |
