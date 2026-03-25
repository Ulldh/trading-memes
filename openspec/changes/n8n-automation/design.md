# Design: n8n-automation (Phase 2B)

## Technical Approach

3 standalone n8n Cloud workflows (Schedule → HTTP Request → Code → Telegram) following the Scheduled Tasks pattern. Each workflow queries Supabase via REST/RPC, builds a report in a Code node, and sends a single Telegram message. A new `scores` table is populated by a scoring step added to the existing `daily-collect.yml` GitHub Action, so n8n only reads pre-computed scores.

## Architecture Decisions

### AD-1: Standalone vs Sub-workflows

**Choice**: 3 independent standalone workflows — no shared sub-workflows.
**Alternatives**: Shared Telegram-send sub-workflow; monolithic single workflow with Switch.
**Rationale**: Each workflow has different schedules, credentials are trivially shared via n8n credential store, and sub-workflow invocation adds latency + debugging complexity. With only 3 simple workflows (~6-8 nodes each), duplication of the Telegram send node is negligible.

### AD-2: Supabase RPC `exec_query` vs PostgREST direct

**Choice**: HTTP Request nodes calling `POST /rest/v1/rpc/exec_query` with raw SQL.
**Alternatives**: PostgREST query params (`GET /rest/v1/tokens?select=...&first_seen=gte.{date}`); n8n built-in Supabase node.
**Rationale**: Health Monitor needs `COUNT(*)`, `UNION ALL`, and JOINs that PostgREST cannot express. Signal Notifier needs a JOIN (`scores` + `tokens`). RPC unifies all queries into one pattern. The n8n Supabase node uses PostgREST under the hood with the same limitations. Supabase Storage reads use direct GET — no RPC needed.

### AD-3: Telegram parse_mode

**Choice**: HTML parse_mode.
**Alternatives**: MarkdownV2, plain text.
**Rationale**: HTML is simpler to construct in JavaScript (no escaping of `.`, `-`, `(`, `)` that MarkdownV2 requires). Supports `<b>`, `<code>`, `<pre>`, `<a href="">` — sufficient for our reports. The existing `check-retrain.yml` uses Markdown, but that is shell `curl` where escaping is simpler; in n8n Code nodes, HTML is safer.

### AD-4: Scores table populated by GitHub Actions, not n8n

**Choice**: Add scoring step to `daily-collect.yml` that upserts to `scores` table. n8n only reads.
**Alternatives**: n8n runs scoring (too heavy — needs ML models); n8n queries features and applies heuristic thresholds.
**Rationale**: `GemScorer` requires joblib models + pandas + numpy — cannot run in n8n Code nodes. The scorer already exists in Python and integrates with `FeatureBuilder`. Adding one step to the existing GitHub Action is minimal effort and keeps ML in Python.

### AD-5: Error handling — per-node `continueOnFail`

**Choice**: Set `continueOnFail: true` on each HTTP Request node. Code node checks for errors and renders "N/A" for failed metrics.
**Alternatives**: Workflow-level Error Trigger node; try/catch in a single Code node using `$helpers.httpRequest`.
**Rationale**: Per-node `continueOnFail` is the n8n-native pattern and keeps the visual workflow debuggable. The Code node aggregates all inputs and gracefully handles missing data. A workflow-level Error Trigger would abort on first failure — spec REQ-C2 requires partial results.

### AD-6: Idempotency on re-runs

**Choice**: All queries use `::date = CURRENT_DATE` or compare versions — naturally idempotent. Telegram messages may duplicate on re-run (acceptable for monitoring). Retrain Notifier uses `$getWorkflowStaticData()` to store last-seen version, updated only after successful comparison.
**Alternatives**: Deduplication table in Supabase; message_id tracking.
**Rationale**: These are monitoring/alerting workflows, not transactional. A duplicate Telegram message on manual re-run is harmless and simpler than building dedup infrastructure.

### AD-7: Credential setup

**Choice**: Two n8n credentials: (1) "Header Auth" with `apikey` and `Authorization: Bearer` headers for Supabase, (2) "Telegram API" credential with bot token. Chat ID is a workflow variable.
**Alternatives**: Hardcoded headers per node; n8n environment variables.
**Rationale**: n8n credential store encrypts secrets at rest. Header Auth allows reuse across all HTTP Request nodes targeting Supabase. Telegram node has built-in credential type.

## Data Flow

### Health Monitor (07:00 UTC)

```
Schedule Trigger
    |
    v
[HTTP: tokens_today] --continueOnFail--> [HTTP: ohlcv_today] --> [HTTP: table_totals]
    |                                          |                       |
    +------------------------------------------+-----------------------+
    |
    v
[HTTP: Storage latest_version.txt] --> [HTTP: Storage metadata.json]
    |                                       |
    +---------------------------------------+
    |
    v
[Code: Build health report]
    - Reads all 5 HTTP outputs via $node["NodeName"].json
    - Determines status: OK / WARNING / ERROR
    - Formats HTML message
    |
    v
[Telegram: Send message]
    - chat_id: 1558705287
    - parse_mode: HTML
    - text: from Code node output
```

### Signal Notifier (07:30 UTC)

```
Schedule Trigger
    |
    v
[HTTP: Query scores+tokens JOIN]  --continueOnFail-->
    |
    v
[Code: Format signal report]
    - If error or empty -> "Sin senales gem hoy"
    - If no scores for today -> "No hay scores hoy. Verificar daily-collect."
    - If candidates -> format each with symbol, chain, prob, signal, DexScreener link
    - Cap at 20, note overflow
    |
    v
[Telegram: Send message]
```

### Retrain Notifier (09:00 UTC Mon)

```
Schedule Trigger
    |
    v
[HTTP: GET latest_version.txt]  --continueOnFail-->
    |
    v
[Code: Compare with static data]
    - $getWorkflowStaticData().lastVersion
    - If same or first run -> simple message, update static
    - If different -> set newVersion + oldVersion for next nodes
    |
    v
[IF: new version detected?]
    |-- false --> [Telegram: "Modelo sin cambios"]
    |-- true  --> [HTTP: GET new metadata.json] --> [HTTP: GET old metadata.json]
                       |                                |
                       +--------------------------------+
                       |
                       v
                  [Code: Compare metrics + update static data]
                       |
                       v
                  [Telegram: Send comparison report]
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| Supabase migration (via MCP) | Create | `scores` table with indexes per REQ-S1 |
| `.github/workflows/daily-collect.yml` | Modify | Add scoring step after collection using `GemScorer.score_all_new()` + upsert to `scores` table |
| `src/data/supabase_storage.py` | Modify | Add `upsert_scores(df)` method for batch upsert to `scores` table |
| n8n workflow: Health Monitor | Create | Via n8n MCP or manual — 7 nodes |
| n8n workflow: Signal Notifier | Create | Via n8n MCP or manual — 4 nodes |
| n8n workflow: Retrain Notifier | Create | Via n8n MCP or manual — 8 nodes |

## Interfaces / Contracts

### Scores table schema (SQL)

```sql
CREATE TABLE scores (
    token_id      TEXT PRIMARY KEY REFERENCES tokens(token_id),
    probability   REAL NOT NULL,
    signal        TEXT NOT NULL CHECK (signal IN ('STRONG','MEDIUM','WEAK','NONE')),
    prediction    INTEGER NOT NULL,
    model_name    TEXT DEFAULT 'random_forest',
    model_version TEXT NOT NULL,
    scored_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_scores_probability ON scores(probability DESC);
CREATE INDEX idx_scores_scored_at ON scores(scored_at);
```

### n8n Supabase HTTP Request pattern

All Supabase RPC calls use this configuration:

```javascript
// Node: HTTP Request
{
  method: "POST",
  url: "https://xayfwuqbbqtyerxzjbec.supabase.co/rest/v1/rpc/exec_query",
  authentication: "predefinedCredentialType",
  nodeCredentialType: "httpHeaderAuth",
  sendBody: true,
  body: {
    contentType: "json",
    content: { "q": "<SQL_QUERY>" }
  }
}
```

Headers via credential: `apikey: {service_role_key}`, `Authorization: Bearer {service_role_key}`.

### n8n Supabase Storage GET pattern

```javascript
// Node: HTTP Request (GET)
{
  method: "GET",
  url: "https://xayfwuqbbqtyerxzjbec.supabase.co/storage/v1/object/public/ml-models/{path}",
  authentication: "predefinedCredentialType",
  nodeCredentialType: "httpHeaderAuth"
}
```

### Health Monitor Code node (pseudocode)

```javascript
const tokensToday = $node["Tokens Today"].json?.[0]?.cnt ?? "N/A";
const ohlcvToday  = $node["OHLCV Today"].json?.[0]?.cnt ?? "N/A";
const totals      = $node["Table Totals"].json ?? [];
const version     = $node["Latest Version"].json; // plain text "v12"
const metadata    = $node["Metadata"].json ?? {};

const trainedAt = metadata.trained_at ? DateTime.fromISO(metadata.trained_at) : null;
const modelAgeDays = trainedAt ? Math.floor(DateTime.now().diff(trainedAt, 'days').days) : "N/A";

let status = "OK", emoji = "\u2705";
const warnings = [];
if (tokensToday === 0 || tokensToday === "N/A") { warnings.push("Tokens hoy: 0"); }
if (ohlcvToday === 0 || ohlcvToday === "N/A") { warnings.push("OHLCV hoy: 0"); }
if (typeof modelAgeDays === "number" && modelAgeDays > 30) { warnings.push(`Modelo stale: ${modelAgeDays}d`); }
if (warnings.length > 0) { status = "WARNING"; emoji = "\u26a0\ufe0f"; }
// Any HTTP error detected -> ERROR
// ... build HTML message, return [{json: {text, chat_id}}]
```

### Signal Notifier Code node (pseudocode)

```javascript
const data = $input.first().json;
const candidates = Array.isArray(data) ? data : [];
const today = DateTime.now().toFormat('yyyy-MM-dd');

if (candidates.length === 0) {
  return [{json: {text: `Sin senales gem hoy (${today})`}}];
}

let msg = `<b>\u{1f48e} GEM CANDIDATES - ${today}</b>\n\n`;
const show = candidates.slice(0, 20);
show.forEach((c, i) => {
  const link = `https://dexscreener.com/${c.chain}/${c.pool_address}`;
  msg += `<b>${i+1}. ${c.symbol}</b> (${c.chain}) | Prob: ${(c.probability*100).toFixed(1)}% | ${c.signal}\n`;
  msg += `<a href="${link}">DexScreener</a>\n\n`;
});
if (candidates.length > 20) msg += `+${candidates.length - 20} mas\n`;
msg += `Total: ${candidates.length} candidatos`;

return [{json: {text: msg}}];
```

### daily-collect.yml scoring step

```yaml
- name: Score new tokens
  run: |
    python -c "
    from src.models.scorer import GemScorer
    from src.data.supabase_storage import get_storage
    import json

    storage = get_storage()
    scorer = GemScorer(storage=storage)
    df = scorer.score_all_new()

    if df.empty:
        print('No tokens to score')
    else:
        # Read current model version
        version = open('data/models/latest_version.txt').read().strip() \
            if __import__('pathlib').Path('data/models/latest_version.txt').exists() \
            else 'unknown'

        for _, row in df.iterrows():
            storage.query(
                \"\"\"INSERT INTO scores (token_id, probability, signal, prediction, model_name, model_version)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (token_id)
                   DO UPDATE SET probability=EXCLUDED.probability, signal=EXCLUDED.signal,
                                 prediction=EXCLUDED.prediction, model_version=EXCLUDED.model_version,
                                 scored_at=NOW()\"\"\",
                (row['token_id'], float(row['probability']), row['signal'],
                 int(row['prediction']), 'random_forest', version)
            )
        print(f'Scored {len(df)} tokens, version={version}')
    "
```

Note: `storage.query()` supports `%s` placeholders and routes them to `exec_sql` for writes.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `upsert_scores` method in supabase_storage.py | pytest mock against Supabase RPC |
| Integration | Scoring step in daily-collect.yml | Manual workflow_dispatch, verify rows in `scores` table |
| E2E | Each n8n workflow | Manually trigger each in n8n Cloud, verify Telegram messages arrive |
| Edge cases | Empty scores, Storage unreachable, first run of Retrain Notifier | Simulate by clearing table / using bad URL / clearing static data |

## Migration / Rollout

1. **Phase A — DB migration**: Create `scores` table via Supabase MCP `apply_migration`
2. **Phase B — Python changes**: Add `upsert_scores` to storage, add scoring step to `daily-collect.yml`
3. **Phase C — n8n workflows**: Create and configure 3 workflows in n8n Cloud, activate after testing
4. **Rollback**: Deactivate workflows in n8n (instant). Scoring step in GH Action is independent and harmless. `scores` table can remain (no destructive changes).

## Open Questions

- [x] Scores table schema — resolved in spec REQ-S1
- [x] HTML vs Markdown — resolved: HTML
- [ ] n8n Cloud free tier execution limits: verify ~90 executions/month fits within quota
- [ ] Supabase Storage bucket `ml-models` public vs private: currently public, acceptable for non-sensitive model metadata
