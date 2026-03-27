# Phase 6: Historical Backfill + Score History Schema - Research

**Researched:** 2026-03-27
**Domain:** FastAPI BackgroundTasks, admin endpoint pattern, cross-tenant DB query
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Queue **UNSCORED assets only** — `scoring_status = 'UNSCORED'` AND `endpoint_type != 'UNSUPPORTED'`. FAILED assets excluded; re-scored individually via existing `POST /scoring/{asset_id}/rescore`.
- **D-02:** Backfill is **cross-tenant** — queries all organizations in a single admin call. One-time platform migration, not a per-tenant action.
- **D-03:** UNSUPPORTED assets never queued — excluded by `endpoint_type != 'UNSUPPORTED'` (same exclusion logic already in `run_scoring_batch()`).
- **D-04:** Background task calls **`score_asset_now(score_id)`** for each UNSCORED asset. Uses the existing per-asset scoring function directly — no new scoring logic.
- **D-05:** Background task fetches all UNSCORED score IDs in a single DB query (single session, then released), then iterates and calls `score_asset_now()` per asset. Session-per-operation pattern maintained.
- **D-06:** Use **`get_current_admin` dependency** from `app.api.v1.deps` for admin-only guard.
- **D-07:** Endpoint returns **HTTP 202 + count of assets queued** immediately: `{"status": "backfill_started", "assets_queued": N}`.
- **D-08:** Endpoint path: `POST /api/v1/scoring/admin/backfill` (under existing scoring router). Alternatively a new `/admin` router — Claude's discretion.
- **D-09:** `creative_score_history` table is **NOT created in Phase 6**. TREND-01, TREND-02, TREND-03 dropped from v1.1 milestone.

### Claude's Discretion

- Whether to mount the backfill endpoint under the existing scoring router or a new `/admin` prefix router
- Exact Alembic migration needed (if any — Phase 5 already created `creative_score_results` with `endpoint_type`; backfill may require no schema changes)
- Concurrency strategy inside the background task (sequential `await score_asset_now()` calls vs. `asyncio.gather` with a semaphore to limit parallelism)
- Error handling in the background loop: per-asset failure should log and continue, not abort the backfill

### Deferred Ideas (OUT OF SCOPE)

**Score History + Trend Chart (TREND-01/02/03) — dropped from v1.1**

Originally scoped as Phase 6 (schema) and Phase 7 (chart). Dropped because BrainSuite scores are static — an asset is scored once and the score does not change. A trend chart would have at most one data point per asset. Revisit only if a future BrainSuite integration enables periodic re-scoring with meaningful score drift.

Requirements affected: TREND-01, TREND-02, TREND-03.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BACK-01 | Admin API endpoint `POST /admin/backfill-scoring` queues all pre-v1.1 assets (both IMAGE and VIDEO) without scores for the live scoring pipeline | Endpoint pattern confirmed from `scoring.py` rescore endpoint + `get_current_admin` dep in `deps.py` |
| BACK-02 | Backfill uses BackgroundTasks — not APScheduler — so it does not conflict with the live 15-minute scorer | BackgroundTasks usage already established in `scoring.py`; `score_asset_now()` already designed for this pattern |
</phase_requirements>

---

## Summary

Phase 6 is a narrow, additive feature: add one admin-only endpoint that reads all UNSCORED (non-UNSUPPORTED) rows from `creative_score_results` cross-tenant and enqueues them via FastAPI `BackgroundTasks` → `score_asset_now()`. No new schema, no new scoring logic, no new infrastructure. The entire implementation assembles existing pieces.

The key implementation insight is that `score_asset_now(score_id)` in `scoring_job.py` already handles the full per-asset lifecycle: it loads the row, marks it PENDING, calls `_process_asset()`, handles errors, and marks FAILED on exception. The backfill task only needs to query IDs and call this function per ID. The session-per-operation pattern is already established — a single session fetches the ID list, releases, then per-asset sessions are created inside `score_asset_now()`.

There are no schema changes required for this phase. `creative_score_results` already has all needed columns (`scoring_status`, `endpoint_type`) from Phase 5 migrations. The only file changes are: a new `run_backfill_task()` function in `scoring_job.py` and a new `POST /scoring/admin/backfill` endpoint in `scoring.py`.

**Primary recommendation:** Add the backfill endpoint under the existing scoring router at `POST /api/v1/scoring/admin/backfill`. Keep the background task sequential by default; if runtime shows it is too slow for large datasets, revisit with a semaphore-bounded `asyncio.gather`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.115.0 | Router, BackgroundTasks, Depends | Already used throughout the project |
| sqlalchemy (async) | 2.0.23 | Async query for UNSCORED IDs | Already used; session-per-operation pattern established |
| Python asyncio | stdlib | Optional semaphore-bounded concurrency | Built-in; no new dependency |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest + pytest-asyncio | >=7.4.0 / >=0.23.0 | Unit tests for backfill logic | All test coverage in this phase |

**No new packages required.** All dependencies are already in `requirements.txt`.

---

## Architecture Patterns

### Recommended Project Structure (additions only)

```
backend/app/
├── services/sync/
│   └── scoring_job.py          # ADD: run_backfill_task() function
└── api/v1/endpoints/
    └── scoring.py              # ADD: POST /admin/backfill endpoint
```

No new files. No new modules. Two additions to existing files.

### Pattern 1: BackgroundTasks Endpoint (established pattern)

**What:** Endpoint validates auth, does synchronous pre-work (query count), registers background function, returns 202 immediately.
**When to use:** All async operations that must not block the HTTP response.

```python
# Source: backend/app/api/v1/endpoints/scoring.py (rescore endpoint)
@router.post("/{asset_id}/rescore")
async def rescore_asset(
    asset_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ... validation ...
    background_tasks.add_task(score_asset_now, score_id)
    return {"status": "scoring_started", "asset_id": str(asset_id)}
```

The backfill endpoint follows the same shape — replace per-asset lookup with cross-tenant count query, return `assets_queued`, register `run_backfill_task`.

### Pattern 2: Session-Per-Operation (established pattern)

**What:** Fetch IDs in one `async with get_session_factory()() as db:` block, release, then call per-asset functions that each open their own sessions.
**When to use:** Any batch operation where sessions must not be held during HTTP calls.

```python
# Source: backend/app/services/sync/scoring_job.py (run_scoring_batch)
async def run_backfill_task() -> None:
    score_ids = []
    async with get_session_factory()() as db:
        result = await db.execute(
            select(CreativeScoreResult.id)
            .where(
                CreativeScoreResult.scoring_status == "UNSCORED",
                CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"]),
            )
        )
        score_ids = result.scalars().all()
    # Session released — iterate without holding DB connection
    for score_id in score_ids:
        try:
            await score_asset_now(score_id)
        except Exception as exc:
            logger.error("Backfill: error scoring score_id=%s: %s", score_id, exc, exc_info=True)
```

Note: The filter `endpoint_type.in_(["VIDEO", "STATIC_IMAGE"])` is more explicit than `!= 'UNSUPPORTED'` and handles future unknown values safely.

### Pattern 3: Admin Guard (established pattern)

**What:** `get_current_admin` from `deps.py` checks `OrganizationRole.role == 'ADMIN'` or `user.is_superuser`. Already tested and used in `platforms.py`.

```python
# Source: backend/app/api/v1/deps.py
async def get_current_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(
        select(OrganizationRole).where(
            OrganizationRole.user_id == current_user.id,
            OrganizationRole.organization_id == current_user.organization_id,
            OrganizationRole.role == "ADMIN",
        )
    )
    role = result.scalar_one_or_none()
    if not role and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user
```

### Endpoint Mounting Decision

The scoring router is mounted at `/api/v1/scoring` in `backend/app/api/v1/__init__.py`. Adding `POST /admin/backfill` to the scoring router yields the path `POST /api/v1/scoring/admin/backfill`.

**Recommendation:** Mount under the existing scoring router. Reason: this endpoint is operationally a scoring operation (it triggers scoring). Adding a new `/admin` top-level router adds a file and a router registration for a single endpoint. That overhead is not justified for one endpoint in this phase.

**Routing pitfall:** FastAPI matches routes in registration order. The scoring router already has `/{asset_id}/rescore` and `/{asset_id}/refetch` as dynamic path routes. A static path like `/admin/backfill` must be registered **before** dynamic `/{asset_id}` routes in the router, or FastAPI will match `admin` as an `asset_id` UUID (which will fail UUID parsing, returning 422 rather than 404, but still wrong). Register the static admin route first.

### Anti-Patterns to Avoid

- **Holding a DB session during the backfill loop:** Do not pass a session into `run_backfill_task()` from the endpoint handler. The endpoint's session closes when the request ends; the background task runs after. Use `get_session_factory()` inside the background task.
- **Re-queuing FAILED assets in the backfill:** D-01 is explicit — FAILED assets are excluded. The existing rescore endpoint handles those.
- **APScheduler for backfill:** D-04/BACK-02 explicitly prohibit this. The backfill is a one-time operation, not a recurring job.
- **Holding `assets_queued` count based on DB query outside the task:** Count the IDs returned from the initial query before handing off to `background_tasks.add_task()`. This gives an accurate immediate count for the 202 response.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-asset scoring | Custom scoring loop | `score_asset_now(score_id)` | Already handles PENDING marking, VIDEO/IMAGE routing, error handling, FAILED marking |
| Admin auth | Custom role check | `get_current_admin` dep | Already tested, handles superuser edge case |
| Background execution | Thread pool, Celery | FastAPI `BackgroundTasks` | Already used in rescore endpoint; no new infrastructure |
| Session management | Custom pool/context | `get_session_factory()` | Established pattern; handles async context correctly |

**Key insight:** This phase is assembly, not construction. Every primitive exists. The risk is over-engineering (adding concurrency management, a polling endpoint, a new router) when the simplest reading of the requirements needs neither.

---

## Common Pitfalls

### Pitfall 1: Static Route Shadowed by Dynamic Route

**What goes wrong:** `POST /api/v1/scoring/admin/backfill` returns 422 (invalid UUID) instead of hitting the backfill handler.
**Why it happens:** FastAPI registers routes in order. If `/{asset_id}/rescore` is registered first, "admin" is treated as the `asset_id` path parameter — UUID parsing fails.
**How to avoid:** Register `@router.post("/admin/backfill")` before any `@router.post("/{asset_id}/...")` routes in `scoring.py`.
**Warning signs:** 422 Unprocessable Entity with a "value is not a valid uuid" error detail.

### Pitfall 2: Session Outlives Request

**What goes wrong:** `run_backfill_task()` uses the `db: AsyncSession` from the endpoint's `Depends(get_db)` — the session is closed by the time the background task runs.
**Why it happens:** FastAPI closes dependency-injected sessions when the response is sent. Background tasks run after response.
**How to avoid:** Never inject `db` into a background task function. Open fresh sessions inside the task using `get_session_factory()`.
**Warning signs:** `sqlalchemy.exc.InvalidRequestError: This Session's transaction has been rolled back` in background task logs.

### Pitfall 3: Backfill Races with Live Scheduler

**What goes wrong:** Both the 15-minute APScheduler batch and the backfill task attempt to mark the same UNSCORED rows as PENDING simultaneously.
**Why it happens:** Both query `scoring_status = 'UNSCORED'` in overlapping time windows.
**How to avoid:** This is handled by the existing design — `score_asset_now()` marks the row PENDING before processing. If the batch job picks up a row and marks it PENDING first, `score_asset_now()` will still mark it PENDING again (idempotent), then process it. The unique constraint `uq_score_per_asset` prevents duplicate rows. No duplicate BrainSuite API calls result because `run_scoring_batch()` uses LIMIT 20 and the backfill calls `score_asset_now()` which marks PENDING before submitting. A row marked PENDING is excluded from the `scoring_status = 'UNSCORED'` batch query.
**Warning signs:** Two BrainSuite jobs created for the same asset. Check for duplicate `brainsuite_job_id` values in `creative_score_results`.

### Pitfall 4: Backfill Count Includes Already-PENDING/PROCESSING Assets

**What goes wrong:** The 202 response claims N assets queued, but some of those assets are already PENDING or PROCESSING from the live scheduler.
**Why it happens:** If the backfill query includes PENDING or PROCESSING rows, the count is inflated.
**How to avoid:** Query is `scoring_status = 'UNSCORED'` (D-01 is explicit). PENDING/PROCESSING rows are not UNSCORED — they are excluded by the query naturally.

### Pitfall 5: Large Backfill Blocking Event Loop

**What goes wrong:** A sequential loop calling `await score_asset_now()` for 500+ assets occupies the event loop for the duration of all BrainSuite API calls (announce + upload + poll per asset), blocking other requests.
**Why it happens:** FastAPI background tasks run in the same event loop as request handlers. Very long-running tasks with blocking IO can starve other requests.
**How to avoid (pragmatic):** `score_asset_now()` uses `httpx.AsyncClient` under the hood (via BrainSuite service), which yields control on each await. For typical tenant sizes (< 200 assets) this is acceptable. For very large datasets, an `asyncio.Semaphore` bounding concurrent calls to 5–10 provides throughput without starvation. This is Claude's discretion per D-04.

---

## Code Examples

### Backfill Task Function (scoring_job.py addition)

```python
# Follows session-per-operation pattern from run_scoring_batch()
async def run_backfill_task() -> None:
    """Queue all UNSCORED VIDEO and STATIC_IMAGE assets cross-tenant via score_asset_now().

    Designed to run as a FastAPI BackgroundTask.
    Fetches all UNSCORED score IDs in a single session (then releases),
    then iterates without holding a DB connection during HTTP calls.
    """
    logger.info("Backfill task started")

    score_ids: list[uuid.UUID] = []
    async with get_session_factory()() as db:
        result = await db.execute(
            select(CreativeScoreResult.id)
            .where(
                CreativeScoreResult.scoring_status == "UNSCORED",
                CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"]),
            )
            .order_by(CreativeScoreResult.created_at.asc())
        )
        score_ids = list(result.scalars().all())

    logger.info("Backfill task: found %d UNSCORED assets to score", len(score_ids))

    for score_id in score_ids:
        try:
            await score_asset_now(score_id)
        except Exception as exc:
            logger.error(
                "Backfill: unexpected error for score_id=%s: %s",
                score_id,
                exc,
                exc_info=True,
            )

    logger.info("Backfill task complete: processed %d assets", len(score_ids))
```

### Backfill Endpoint (scoring.py addition — register BEFORE /{asset_id} routes)

```python
# Source: follows pattern from rescore_asset() in scoring.py
@router.post("/admin/backfill", status_code=202)
async def admin_backfill_scoring(
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin),
):
    """Queue all UNSCORED assets (cross-tenant) for the live scoring pipeline.

    Returns immediately with a count of assets queued.
    Progress is visible per-asset in the dashboard.
    """
    # Count UNSCORED assets (same filter as run_backfill_task uses)
    async with get_session_factory()() as db:
        result = await db.execute(
            select(func.count(CreativeScoreResult.id))
            .where(
                CreativeScoreResult.scoring_status == "UNSCORED",
                CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"]),
            )
        )
        assets_queued = result.scalar_one()

    background_tasks.add_task(run_backfill_task)
    logger.info(
        "admin_backfill_scoring: queuing %d UNSCORED assets (requested by user %s)",
        assets_queued,
        current_admin.id,
    )
    return {"status": "backfill_started", "assets_queued": assets_queued}
```

Note: `func` requires `from sqlalchemy import func` — add to imports.

### Import additions for scoring.py

```python
from sqlalchemy import select, func
from app.api.v1.deps import get_current_user, get_current_admin
from app.services.sync.scoring_job import score_asset_now, run_backfill_task
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| APScheduler for one-off tasks | FastAPI BackgroundTasks for non-recurring admin ops | Decided Phase 6 context | BackgroundTasks do not compete with SCHEDULER_ENABLED guard or multi-worker deployments |
| Separate admin router | Endpoint under existing domain router | Phase 6 decision | Fewer files, simpler routing |

**Deprecated/outdated for this phase:**
- TREND-01 (creative_score_history schema): Dropped in D-09. Do not create this table.

---

## Open Questions

1. **Concurrency strategy for large datasets**
   - What we know: Sequential `await score_asset_now()` is correct and safe; it yields on each HTTP call.
   - What's unclear: Whether tenant asset counts are large enough that sequential processing causes noticeable event-loop latency for other users during backfill.
   - Recommendation: Start sequential. If logs show backfill taking > 30 minutes for any tenant, add a semaphore with limit 5: `sem = asyncio.Semaphore(5); async with sem: await score_asset_now(score_id)`.

2. **Race condition between count query and task execution**
   - What we know: The 202 response returns the count from a query at request time; the background task runs after and queries again. Between these two points, the live scheduler may mark some UNSCORED rows as PENDING.
   - What's unclear: Whether the user cares about count accuracy.
   - Recommendation: The count is "approximate queued" not "guaranteed processed" — the response message `"backfill_started"` with a count is informational. No fix needed; document in API response comment.

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies beyond the existing project stack — this phase adds no new tools, services, or runtimes).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.4+ with pytest-asyncio 0.23+ |
| Config file | None found (no pytest.ini / pyproject.toml) — pytest auto-discovers `tests/` |
| Quick run command | `cd backend && python -m pytest tests/test_backfill.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BACK-01 | Backfill endpoint returns 202 + `assets_queued` count | unit | `pytest tests/test_backfill.py::test_backfill_endpoint_returns_202 -x` | Wave 0 |
| BACK-01 | Backfill queries only UNSCORED + non-UNSUPPORTED rows (cross-tenant) | unit | `pytest tests/test_backfill.py::test_backfill_query_filters -x` | Wave 0 |
| BACK-01 | FAILED assets excluded from backfill | unit | `pytest tests/test_backfill.py::test_backfill_excludes_failed -x` | Wave 0 |
| BACK-01 | Non-admin user receives 403 | unit | `pytest tests/test_backfill.py::test_backfill_requires_admin -x` | Wave 0 |
| BACK-02 | `run_backfill_task` calls `score_asset_now` per asset, not APScheduler | unit | `pytest tests/test_backfill.py::test_backfill_uses_score_asset_now -x` | Wave 0 |
| BACK-02 | Per-asset failure logs and continues (does not abort loop) | unit | `pytest tests/test_backfill.py::test_backfill_error_isolation -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && python -m pytest tests/test_backfill.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_backfill.py` — covers BACK-01 and BACK-02 (6 tests above)

*(All tests are new; existing `tests/test_scoring.py` and `tests/test_scoring_image.py` are not modified by this phase.)*

---

## Sources

### Primary (HIGH confidence)

- `backend/app/services/sync/scoring_job.py` — `score_asset_now()`, `run_scoring_batch()` — direct code inspection
- `backend/app/api/v1/endpoints/scoring.py` — BackgroundTasks pattern, router shape — direct code inspection
- `backend/app/api/v1/deps.py` — `get_current_admin` implementation — direct code inspection
- `backend/app/models/scoring.py` — `CreativeScoreResult` model fields — direct code inspection
- `backend/app/api/v1/__init__.py` — router registration and prefix conventions — direct code inspection
- `backend/alembic/versions/n5o6p7q8r9s0_fix_endpoint_type_for_existing_images.py` — confirms Phase 5 schema is complete, no further migration needed — direct code inspection

### Secondary (MEDIUM confidence)

- FastAPI BackgroundTasks docs — BackgroundTasks run after response, in same event loop; session injection caveats — well-documented framework behavior
- SQLAlchemy async session-per-operation pattern — recommended for avoiding cross-coroutine session sharing — established in project codebase

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all libraries already in requirements.txt; no new dependencies
- Architecture: HIGH — all patterns are directly readable from existing code; no framework research uncertainty
- Pitfalls: HIGH — routing order and session lifetime pitfalls are verified FastAPI/SQLAlchemy behavior, observable in existing code
- Test map: HIGH — pytest + pytest-asyncio already in use; test file naming follows existing project convention

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable domain; no fast-moving dependencies)
