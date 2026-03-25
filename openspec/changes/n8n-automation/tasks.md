# SDD Tasks: n8n-automation (Phase 2B)

**Status**: APPROVED | **Created**: 2026-03-25
**Depends on**: proposal.md, spec.md, design.md

---

## Phase 1: Database + Scoring Pipeline (Python side)

These tasks create the `scores` table and integrate scoring into the daily collection pipeline.
All n8n workflows depend on this phase being complete.

---

### Task 1.1: Create `scores` table in Supabase

**Complexity**: S
**Requirements**: REQ-S1
**Action**: Create (Supabase migration)
**Dependencies**: None

**Description**: Apply SQL migration to create the `scores` table with all columns, constraints, and indexes defined in the spec.

**SQL**:
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

**Verification**: `SELECT * FROM scores LIMIT 1;` executes without error. Table appears in `stats()`.

---

### Task 1.2: Add `upsert_scores()` method to SupabaseStorage

**Complexity**: M
**Requirements**: REQ-S1
**Action**: Modify
**Files**:
- `src/data/supabase_storage.py` — Add `upsert_scores(df)` method
**Dependencies**: Task 1.1

**Description**: Add a batch upsert method to `SupabaseStorage` that takes a DataFrame with columns `[token_id, probability, signal, prediction, model_name, model_version, scored_at]` and upserts to the `scores` table using `_batch_upsert` with `on_conflict="token_id"`. Also add `scores` to the `stats()` method's table list.

**Implementation notes**:
- Use existing `_batch_upsert()` pattern (already handles batching)
- Validate that `signal` is in `('STRONG','MEDIUM','WEAK','NONE')`
- Include `model_version` (read from `latest_version.txt` or passed as param)
- Add `"scores"` to the `tables` list in `stats()`

**Verification**: Unit test that mocks Supabase client and verifies upsert call shape.

---

### Task 1.3: Add `save_scores()` integration to GemScorer

**Complexity**: M
**Requirements**: REQ-S1
**Action**: Modify
**Files**:
- `src/models/scorer.py` — Add `score_and_save()` method
**Dependencies**: Task 1.2

**Description**: Add a convenience method `score_and_save()` to `GemScorer` that:
1. Calls `score_all_new()` to get scored tokens
2. Adds `model_version` column (read from `latest_version.txt`)
3. Calls `storage.upsert_scores(df)` to persist to `scores` table
4. Returns the DataFrame + count of saved scores

This method will be called from the GitHub Actions scoring step.

**Implementation notes**:
- Read model version from `self._models_dir / "latest_version.txt"` (already loaded in `__init__`)
- Reuse the existing `score_all_new()` (no duplication)
- Log count of scored tokens at INFO level

**Verification**: Unit test with mock storage that verifies `upsert_scores` is called with correct DataFrame shape.

---

### Task 1.4: Add scoring step to `daily-collect.yml`

**Complexity**: M
**Requirements**: REQ-S1
**Action**: Modify
**Files**:
- `.github/workflows/daily-collect.yml` — Add step after "Run daily collection"
**Dependencies**: Task 1.3

**Description**: Add a GitHub Actions step that downloads models from Supabase Storage (reusing `scripts/download_models.py`), runs `GemScorer.score_and_save()`, and logs results.

**New step** (insert between "Run daily collection" and "Show DB stats"):
```yaml
- name: Download models for scoring
  run: python scripts/download_models.py

- name: Score new tokens
  run: |
    python -c "
    from src.models.scorer import GemScorer
    scorer = GemScorer()
    df = scorer.score_and_save()
    print(f'Scored and saved {len(df)} tokens')
    "
```

**Implementation notes**:
- `download_models.py` already exists and downloads from Supabase Storage
- If scoring fails (no models, no tokens), it should NOT fail the workflow — use `continue-on-error: true`
- The "Show DB stats" step already exists and will now show `scores` count too (after Task 1.2 adds it to `stats()`)

**Verification**: Manual `workflow_dispatch`, verify scores appear in Supabase `scores` table.

---

### Task 1.5: Tests for scoring pipeline

**Complexity**: M
**Requirements**: REQ-S1
**Action**: Modify
**Files**:
- `tests/test_scorer.py` — Add tests for `score_and_save()`
- `tests/test_supabase_storage.py` (or equivalent) — Add tests for `upsert_scores()`
**Dependencies**: Task 1.2, Task 1.3

**Description**: Add unit tests covering:
1. `upsert_scores()` — correct batch upsert call to Supabase with expected columns
2. `upsert_scores()` — empty DataFrame does nothing
3. `upsert_scores()` — invalid signal value is rejected
4. `score_and_save()` — calls `score_all_new` + `upsert_scores` with model_version
5. `score_and_save()` — empty results returns empty DataFrame without error

**Verification**: `pytest tests/test_scorer.py tests/test_supabase_storage.py -v` all pass.

---

## Phase 2: n8n Workflows

These tasks create the 3 n8n Cloud workflows. Each is independent of the others but all depend on Phase 1 being complete (for Signal Notifier to have data).

**Pre-requisite for all Phase 2 tasks**: n8n Cloud credentials configured (Supabase HTTP Header Auth + Telegram Bot API). This is a manual step done once.

---

### Task 2.0: Configure n8n Cloud credentials

**Complexity**: S
**Requirements**: REQ-C1
**Action**: Manual configuration
**Dependencies**: None (can be done in parallel with Phase 1)

**Description**: In n8n Cloud:
1. Create credential "Supabase API" (type: Header Auth):
   - Header Name 1: `apikey`, Value: `{service_role_key}`
   - Header Name 2: `Authorization`, Value: `Bearer {service_role_key}`
2. Create credential "Telegram Bot" (type: Telegram API):
   - Bot Token: `8317359629:AAFT_knnE98NZtKeDrVN1Qh73wbWSba-czA`
3. Verify both by testing an HTTP Request node to Supabase and a Telegram send to chat_id `1558705287`.

**Verification**: Test nodes succeed in n8n.

---

### Task 2.1: Create Health Monitor workflow (n8n)

**Complexity**: L
**Requirements**: REQ-H1, REQ-H2, REQ-C1, REQ-C2
**Action**: Create (n8n workflow)
**Dependencies**: Task 2.0

**Description**: Create n8n workflow "Health Monitor" with the following nodes:

| # | Node | Type | Config |
|---|------|------|--------|
| 1 | Schedule Trigger | Cron | 07:00 UTC daily |
| 2 | Tokens Today | HTTP Request | POST `exec_query`: `SELECT COUNT(*) as cnt FROM tokens WHERE first_seen::date=CURRENT_DATE` |
| 3 | OHLCV Today | HTTP Request | POST `exec_query`: `SELECT COUNT(*) as cnt FROM ohlcv WHERE timestamp::date=CURRENT_DATE` |
| 4 | Table Totals | HTTP Request | POST `exec_query`: UNION ALL counts for tokens/ohlcv/labels/features/scores |
| 5 | Latest Version | HTTP Request | GET `storage/v1/object/public/ml-models/latest_version.txt` |
| 6 | Metadata | HTTP Request | GET `storage/v1/object/public/ml-models/{version}/metadata.json` |
| 7 | Build Report | Code | JavaScript: aggregate all inputs, determine OK/WARNING/ERROR, build HTML message |
| 8 | Send Telegram | Telegram | chat_id: `1558705287`, parse_mode: HTML |

**Key logic in Code node**:
- `continueOnFail: true` on all HTTP Request nodes
- Status = OK if tokens_today > 0 AND ohlcv_today > 0 AND model_age <= 30 days
- Status = WARNING if any zero or stale
- Status = ERROR if HTTP failure
- Failed metrics render as "N/A"
- HTML format per REQ-H2

**Verification**: Manual trigger in n8n, verify Telegram message arrives with correct format and data.

---

### Task 2.2: Create Signal Notifier workflow (n8n)

**Complexity**: L
**Requirements**: REQ-SN1, REQ-SN2, REQ-C1, REQ-C2, REQ-C3
**Action**: Create (n8n workflow)
**Dependencies**: Task 2.0, Task 1.1 (scores table must exist)

**Description**: Create n8n workflow "Signal Notifier" with the following nodes:

| # | Node | Type | Config |
|---|------|------|--------|
| 1 | Schedule Trigger | Cron | 07:30 UTC daily |
| 2 | Query Scores | HTTP Request | POST `exec_query`: `SELECT s.*, t.name, t.symbol, t.chain, t.pool_address FROM scores s JOIN tokens t ON s.token_id=t.token_id WHERE s.scored_at::date=CURRENT_DATE AND s.probability>=0.65 ORDER BY s.probability DESC LIMIT 20` |
| 3 | Format Report | Code | JavaScript: format candidates or "Sin senales" message |
| 4 | Send Telegram | Telegram | chat_id: `1558705287`, parse_mode: HTML |

**Key logic in Code node**:
- `continueOnFail: true` on HTTP Request
- If HTTP error → send warning "No hay scores hoy. Verificar daily-collect."
- If empty array → send "Sin senales gem hoy ({date})"
- If candidates → format each per REQ-SN2 with DexScreener link
- Cap at 20, show "+{n} mas" if overflow
- Configurable: `SCORE_THRESHOLD = 0.65`, `MAX_CANDIDATES = 20` as workflow variables (REQ-C3)

**Verification**: Manual trigger in n8n with and without scores data, verify correct Telegram messages.

---

### Task 2.3: Create Retrain Notifier workflow (n8n)

**Complexity**: L
**Requirements**: REQ-R1, REQ-R2, REQ-C1, REQ-C2
**Action**: Create (n8n workflow)
**Dependencies**: Task 2.0

**Description**: Create n8n workflow "Retrain Notifier" with the following nodes:

| # | Node | Type | Config |
|---|------|------|--------|
| 1 | Schedule Trigger | Cron | 09:00 UTC Mondays |
| 2 | Latest Version | HTTP Request | GET `storage/v1/object/public/ml-models/latest_version.txt` |
| 3 | Compare Version | Code | Read `$getWorkflowStaticData().lastVersion`, compare |
| 4 | IF | Condition | `newVersionDetected == true` |
| 5a | No Change | Telegram | "Modelo sin cambios. Version: {v}" |
| 5b | New Metadata | HTTP Request | GET `metadata.json` for new version |
| 6 | Old Metadata | HTTP Request | GET `metadata.json` for old version |
| 7 | Compare Metrics | Code | Build comparison table, update static data |
| 8 | Send Comparison | Telegram | Formatted comparison report |

**Key logic**:
- `continueOnFail: true` on HTTP Request nodes
- `$getWorkflowStaticData()` stores `lastVersion` between runs
- First run: initialize static data, send "Retrain Notifier inicializado"
- Storage unreachable: send ERROR, do NOT update static data
- Comparison: MEJORA = both F1 up, DEGRADACION = either F1 dropped > 2%, LATERAL = otherwise
- HTML format per REQ-R2

**Verification**: Manual trigger, test with current version. Then change static data to simulate version difference.

---

## Phase 3: Integration Testing + Activation

---

### Task 3.1: End-to-end integration test

**Complexity**: M
**Requirements**: All (REQ-S1, REQ-H1, REQ-H2, REQ-SN1, REQ-SN2, REQ-R1, REQ-R2, REQ-C1, REQ-C2, REQ-C3)
**Action**: Verify
**Dependencies**: All Phase 1 + Phase 2 tasks

**Description**: Run the complete daily pipeline end-to-end and verify all three workflows:

1. **Trigger daily-collect.yml** via `workflow_dispatch` — verify:
   - Collector runs successfully
   - Scoring step downloads models, scores tokens, upserts to `scores` table
   - `scores` table has rows with correct schema

2. **Trigger Health Monitor** manually in n8n — verify:
   - Telegram message arrives with OK/WARNING status
   - All metrics present (tokens today, OHLCV today, totals, model info)
   - Format matches REQ-H2

3. **Trigger Signal Notifier** manually in n8n — verify:
   - If scores exist with prob >= 0.65: candidates message with correct format
   - If no qualifying scores: "Sin senales gem hoy" message
   - DexScreener links are valid

4. **Trigger Retrain Notifier** manually in n8n — verify:
   - First run: "Retrain Notifier inicializado" message
   - Second run (same version): "Modelo sin cambios" message
   - Static data persists between runs

**Verification**: All 4 Telegram messages received with correct format and data.

---

### Task 3.2: Activate workflows + final configuration

**Complexity**: S
**Requirements**: REQ-C3
**Action**: Configure
**Dependencies**: Task 3.1

**Description**: After successful integration tests:
1. Activate all 3 workflows in n8n Cloud (set to "Active")
2. Verify cron schedules: Health 07:00 UTC, Signal 07:30 UTC, Retrain 09:00 UTC Mon
3. Document workflow IDs and activation status
4. Update project MEMORY.md with:
   - n8n workflow IDs
   - Phase 2B completion status
   - Next pending phases

**Verification**: Wait for next scheduled run (or manually trigger at scheduled time) and verify automatic execution.

---

## Dependency Graph

```
Phase 1 (Python)                    Phase 2 (n8n)
================                    =============

1.1 scores table ----+              2.0 credentials ---+
        |            |                    |             |
        v            |                    v             |
1.2 upsert_scores    |              2.1 Health Monitor  |
        |            |                    |             |
        v            |              2.2 Signal Notifier |
1.3 score_and_save   |                    |             |
        |            |              2.3 Retrain Notifier|
        v            |                    |             |
1.4 daily-collect.yml|                    |             |
        |            |                    |             |
        v            |                    |             |
1.5 tests -----------+--------------------+             |
                     |                                  |
                     v                                  |
              3.1 Integration test <--------------------+
                     |
                     v
              3.2 Activate workflows
```

**Parallel execution opportunities**:
- Phase 1 (1.1 → 1.2 → 1.3 → 1.4 → 1.5) runs sequentially
- Task 2.0 runs in parallel with Phase 1
- Tasks 2.1, 2.2, 2.3 can run in parallel after 2.0
- Task 2.1 and 2.3 do NOT depend on Phase 1 (they read existing tables)
- Task 2.2 depends on Task 1.1 (needs `scores` table)

---

## Summary Table

| Task | Phase | Complexity | Requirements | Files Changed |
|------|-------|------------|-------------|---------------|
| 1.1 | DB | S | REQ-S1 | Supabase migration |
| 1.2 | Python | M | REQ-S1 | `src/data/supabase_storage.py` |
| 1.3 | Python | M | REQ-S1 | `src/models/scorer.py` |
| 1.4 | CI | M | REQ-S1 | `.github/workflows/daily-collect.yml` |
| 1.5 | Test | M | REQ-S1 | `tests/test_scorer.py`, `tests/test_supabase_storage.py` |
| 2.0 | Config | S | REQ-C1 | n8n Cloud (manual) |
| 2.1 | n8n | L | REQ-H1, REQ-H2, REQ-C1, REQ-C2 | n8n workflow JSON |
| 2.2 | n8n | L | REQ-SN1, REQ-SN2, REQ-C1, REQ-C2, REQ-C3 | n8n workflow JSON |
| 2.3 | n8n | L | REQ-R1, REQ-R2, REQ-C1, REQ-C2 | n8n workflow JSON |
| 3.1 | Test | M | All | None (verification only) |
| 3.2 | Config | S | REQ-C3 | n8n Cloud + MEMORY.md |

**Total**: 11 tasks (2 S, 5 M, 3 L, 1 verify)
**Estimated effort**: 6-9 hours (aligned with proposal estimate)

---

## Requirement Coverage Matrix

| Requirement | Tasks |
|-------------|-------|
| REQ-S1 | 1.1, 1.2, 1.3, 1.4, 1.5 |
| REQ-H1 | 2.1, 3.1 |
| REQ-H2 | 2.1, 3.1 |
| REQ-SN1 | 2.2, 3.1 |
| REQ-SN2 | 2.2, 3.1 |
| REQ-R1 | 2.3, 3.1 |
| REQ-R2 | 2.3, 3.1 |
| REQ-C1 | 2.0, 2.1, 2.2, 2.3 |
| REQ-C2 | 2.1, 2.2, 2.3, 3.1 |
| REQ-C3 | 2.2, 3.2 |

All 10 requirements are covered by at least 2 tasks (implementation + verification).
