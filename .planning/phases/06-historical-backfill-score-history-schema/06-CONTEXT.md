# Phase 6: Historical Backfill + Score History Schema - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Queue all pre-v1.1 assets that have never been scored (both IMAGE and VIDEO, cross-tenant) into the live BrainSuite scoring pipeline via an admin-only endpoint. The backfill runs as a FastAPI BackgroundTask — not via APScheduler — so it does not compete with the 15-minute scheduler on the same UNSCORED queue.

**Scope reduction from original roadmap:** TREND-01 (score history schema), TREND-02 (write history after scoring), and TREND-03 (score trend chart) have been dropped. Scores are static — BrainSuite scores an asset once and the result does not change over time. A trend chart would almost never have more than one data point. These requirements are deferred indefinitely.

**Phase 6 requirements in scope:** BACK-01, BACK-02 only.

</domain>

<decisions>
## Implementation Decisions

### Backfill Scope

- **D-01:** Queue **UNSCORED assets only** — `scoring_status = 'UNSCORED'` AND `endpoint_type != 'UNSUPPORTED'`. FAILED assets are excluded; they can be re-scored individually via the existing `POST /scoring/{asset_id}/rescore` endpoint.
- **D-02:** Backfill is **cross-tenant** — queries all organizations in a single admin call. This is a one-time platform migration, not a per-tenant action.
- **D-03:** UNSUPPORTED assets are never queued — excluded by the `endpoint_type != 'UNSUPPORTED'` filter (same exclusion logic already in `run_scoring_batch()`).

### Backfill Execution Model

- **D-04:** The background task calls **`score_asset_now(score_id)`** for each UNSCORED asset. Assets are processed immediately, not waiting for the next 15-minute scheduler tick. Uses the existing per-asset scoring function directly — no new scoring logic required.
- **D-05:** The background task fetches all UNSCORED score IDs in a single DB query (single session, then released), then iterates and calls `score_asset_now()` per asset. Session-per-operation pattern maintained — no DB session held during HTTP calls.

### Admin Endpoint

- **D-06:** Use **`get_current_admin` dependency** from `app.api.v1.deps` — the established pattern for admin-only operations (already used in `platforms.py`). Checks `OrganizationRole.role == 'ADMIN'` or `user.is_superuser`.
- **D-07:** Endpoint returns **HTTP 202 + count of assets queued** immediately. Example: `{"status": "backfill_started", "assets_queued": 47}`. No polling endpoint needed — per-asset scoring progress is already visible in the dashboard.
- **D-08:** Endpoint path: `POST /api/v1/scoring/admin/backfill` (under the existing scoring router, guarded by `get_current_admin`). Alternatively a new `/admin` router — Claude's discretion on where to mount it.

### Deferred: Score History (TREND-01/02/03)

- **D-09:** `creative_score_history` table is **NOT created in Phase 6**. Scores are static — BrainSuite computes a score once per asset and it does not change. A trend chart would have at most one data point per asset. TREND-01, TREND-02, TREND-03 are dropped from the v1.1 milestone.

### Claude's Discretion

- Whether to mount the backfill endpoint under the existing scoring router or a new `/admin` prefix router
- Exact Alembic migration needed (if any — Phase 5 already created `creative_score_results` with `endpoint_type`; backfill may require no schema changes)
- Concurrency strategy inside the background task (sequential `await score_asset_now()` calls vs. asyncio.gather with a semaphore to limit parallelism)
- Error handling in the background loop: per-asset failure should log and continue, not abort the backfill

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements
- `.planning/REQUIREMENTS.md` §Historical Backfill — BACK-01, BACK-02: full requirement text
- `.planning/ROADMAP.md` §Phase 6 — Success criteria (items 1 and 2 apply; items 3 and 4 are dropped per D-09)

### Existing code to extend
- `backend/app/services/sync/scoring_job.py` — `score_asset_now(score_id)` is the per-asset entry point the backfill task calls; `run_scoring_batch()` shows the UNSCORED query and UNSUPPORTED exclusion pattern to mirror
- `backend/app/api/v1/deps.py` — `get_current_admin` dependency (admin auth guard to reuse)
- `backend/app/api/v1/endpoints/scoring.py` — existing BackgroundTasks usage pattern (rescore endpoint); mount backfill endpoint in this file or alongside it
- `backend/app/models/scoring.py` — `CreativeScoreResult` model; `scoring_status` and `endpoint_type` fields used in backfill query

### Prior phase context
- `.planning/phases/03-brainsuite-scoring-pipeline/03-CONTEXT.md` — scoring state machine, UNSCORED→PENDING flow, SCHEDULER_ENABLED guard
- `.planning/phases/05-brainsuite-image-scoring/05-CONTEXT.md` — UNSUPPORTED status, endpoint_type enum, cross-tenant scoring patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `score_asset_now(score_id)` in `scoring_job.py` — drop-in per-asset scoring entry point; backfill loop calls this directly for each UNSCORED score_id
- `get_current_admin` in `deps.py` — admin guard dep; already tested and used in platforms.py
- BackgroundTasks pattern in `scoring.py` rescore endpoint — exact pattern for the backfill endpoint to follow

### Established Patterns
- UNSCORED query with UNSUPPORTED exclusion: `WHERE scoring_status = 'UNSCORED' AND endpoint_type != 'UNSUPPORTED'` (from `run_scoring_batch()`)
- Session-per-operation: fetch batch in one session, release, then process per-asset without holding session
- Per-asset failure isolation: try/except per asset, log error, continue loop

### Integration Points
- New endpoint under `/api/v1/scoring/` (or `/api/v1/admin/`) → calls `run_backfill_task()` via `background_tasks.add_task()`
- `run_backfill_task()` queries `CreativeScoreResult` cross-tenant, iterates `score_asset_now()` per asset
- No schema changes expected — `creative_score_results` table already has all required columns from Phase 5

</code_context>

<specifics>
## Specific Ideas

- Response shape: `{"status": "backfill_started", "assets_queued": N}` — returned immediately before background task runs
- Query for backfill: `SELECT id FROM creative_score_results WHERE scoring_status = 'UNSCORED' AND endpoint_type != 'UNSUPPORTED'` — no org filter (cross-tenant)
- FAILED assets explicitly excluded: if an admin wants to re-queue failed assets, they use the existing per-asset rescore endpoint

</specifics>

<deferred>
## Deferred Ideas

### Score History + Trend Chart (TREND-01/02/03) — dropped from v1.1

Originally scoped as Phase 6 (schema) and Phase 7 (chart). Dropped because BrainSuite scores are static — an asset is scored once and the score does not change. A trend chart would have at most one data point per asset and provides no analytical value. Revisit only if a future BrainSuite integration enables periodic re-scoring with meaningful score drift.

Requirements affected: TREND-01, TREND-02, TREND-03.

</deferred>

---

*Phase: 06-historical-backfill-score-history-schema*
*Context gathered: 2026-03-27*
