# Architecture Research

**Domain:** Async AI/ML scoring pipeline integration for ad creative assets
**Researched:** 2026-03-20
**Confidence:** HIGH (grounded in existing codebase analysis + verified patterns)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Angular Frontend                            │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │  Dashboard   │  │ Asset Table  │  │  Score Badge / Dimension  │  │
│  │  (existing)  │  │  (existing)  │  │  Breakdown Panel (new)    │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬──────────────┘  │
│         │                 │                        │                 │
│         └─────────────────┴────────────────────────┘                │
│                           │ HTTP + polling                           │
└───────────────────────────┼─────────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────────┐
│                     FastAPI REST Layer                               │
│  ┌───────────────┐  ┌────────────────┐  ┌──────────────────────┐   │
│  │ /dashboard/*  │  │  /assets/*     │  │  /scoring/*  (new)   │   │
│  │  (existing)   │  │  (existing)    │  │  trigger, status     │   │
│  └───────────────┘  └────────────────┘  └──────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────────┐
│                       Service Layer                                  │
│  ┌───────────────────┐   ┌────────────────────────────────────────┐  │
│  │   APScheduler     │   │     BrainSuiteScoreService (new)       │  │
│  │   (existing)      │   │  - submit_asset_for_scoring()          │  │
│  │  + scoring job    │   │  - fetch_scoring_result()              │  │
│  │    registered     │   │  - bulk_score_unscored()               │  │
│  └───────────────────┘   └────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────────┐
│                       Data Layer                                     │
│  ┌────────────────────┐  ┌──────────────────────────────────────┐   │
│  │  creative_assets   │  │  creative_score_results (new table)  │   │
│  │  (existing)        │  │  - asset_id FK                       │   │
│  │  ace_score,        │  │  - scoring_status (enum)             │   │
│  │  brainsuite_       │  │  - overall_score, dimensions (JSONB) │   │
│  │  metadata columns  │  │  - scored_at, error_message          │   │
│  └────────────────────┘  └──────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │              PostgreSQL + Google Cloud Storage                 │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴──────────────┐
              │     BrainSuite API         │
              │  (external, HTTP POST)     │
              └────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation Location |
|-----------|----------------|------------------------|
| BrainSuiteScoreService | Submit assets to BrainSuite API, handle response, write results | `backend/app/services/brainsuite_score.py` (new) |
| Scoring APScheduler job | Periodically scan for unscored assets, trigger scoring | Registered in `scheduler.py` alongside existing sync jobs |
| `creative_score_results` table | Authoritative store for scoring status + results per asset | New Alembic migration |
| Scoring API endpoints | Expose trigger, status check, and retry endpoints | `backend/app/api/v1/endpoints/scoring.py` (new) |
| Score display (frontend) | Show score badge + dimension breakdown in asset table/detail | New Angular component, wired into existing dashboard table |
| `ace_score` / `brainsuite_metadata` columns | Denormalized cache on `creative_assets` for fast dashboard queries | Already exist — populate from score results |

## Recommended Project Structure

```
backend/app/
├── services/
│   ├── brainsuite_score.py       # BrainSuite API client + scoring logic (new)
│   └── sync/
│       └── scheduler.py          # Add scoring job registration here
├── api/v1/endpoints/
│   └── scoring.py                # POST /scoring/trigger, GET /scoring/status (new)
├── models/
│   └── scoring.py                # CreativeScoringResult model (new)
└── alembic/versions/
    └── xxxx_add_scoring_results.py   # Migration (new)

frontend/src/app/
├── features/
│   └── dashboard/
│       └── components/
│           ├── score-badge/          # Reusable score display chip (new)
│           └── score-breakdown/      # Dimension detail panel (new)
└── services/
    └── scoring.service.ts            # HTTP calls to /scoring/* (new)
```

### Structure Rationale

- **`brainsuite_score.py` as dedicated service:** Mirrors the existing platform OAuth service pattern (`meta_oauth.py`, etc.). Keeps API client logic separate from scheduler/endpoint code.
- **`scoring.py` endpoint:** Keeps scoring control plane separate from asset CRUD (`assets.py`). Allows adding retry/force-rescore without touching dashboard logic.
- **`scoring.py` model:** Separate table (not just columns on `creative_assets`) for scoring status tracking — enables querying "what needs scoring" without full table scan on `creative_assets`.
- **Score badge as standalone component:** Score display appears in multiple contexts (dashboard table row, asset detail drawer, export). Encapsulating it prevents duplication.

## Architectural Patterns

### Pattern 1: Sync-Trigger, Async-Execute

**What:** An API endpoint accepts a user request to score an asset (or all unscored assets), returns immediately with a job acknowledgment, and the actual BrainSuite API call happens in a background coroutine via FastAPI `BackgroundTasks` or the existing APScheduler.

**When to use:** Always — BrainSuite API calls are external HTTP requests that may take seconds. Never block the request thread waiting for a scoring result.

**Trade-offs:** Simple, no new infrastructure. Downside: if the worker process restarts between trigger and execution, the in-flight score request is lost. Acceptable here because the scheduler will pick up un-scored assets on its next run.

**Example:**
```python
# endpoint
@router.post("/scoring/trigger")
async def trigger_scoring(
    asset_ids: list[uuid.UUID],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Mark assets as PENDING in scoring table
    await score_service.mark_pending(db, asset_ids, current_user.organization_id)
    # Kick off background work — returns immediately
    background_tasks.add_task(score_service.run_scoring_batch, asset_ids)
    return {"queued": len(asset_ids)}
```

### Pattern 2: Scoring Status as Database State Machine

**What:** Each asset has a scoring status tracked in `creative_score_results`: `UNSCORED → PENDING → PROCESSING → COMPLETE | FAILED`. The scheduler queries `WHERE status IN ('UNSCORED', 'FAILED')` to find work. The frontend polls a status endpoint.

**When to use:** Required for bulk historical scoring. Prevents duplicate work (idempotent — scheduler skips COMPLETE assets). Enables user-visible progress and retry of failed assets.

**Trade-offs:** Slightly more schema complexity than pure columns on `creative_assets`, but enables clean query patterns and avoids scanning the entire assets table. Alembic migration required.

**State transitions:**
```
New asset synced         → UNSCORED  (set by sync service on INSERT)
Scheduler picks up       → PENDING   (set on batch selection)
BrainSuite call started  → PROCESSING
BrainSuite call returned → COMPLETE  (write score + dimensions)
BrainSuite call errored  → FAILED    (write error_message, retry eligible)
```

### Pattern 3: Denormalize Score to Asset Table for Dashboard Queries

**What:** After writing the authoritative result to `creative_score_results`, also update `ace_score`, `ace_score_confidence`, and `brainsuite_metadata` columns directly on `creative_assets` (these columns already exist).

**When to use:** Always — the dashboard joins `creative_assets` with `HarmonizedPerformance`. Keeping score on the asset record avoids an additional join to `creative_score_results` on every dashboard page load.

**Trade-offs:** Slight denormalization. Acceptable because scores rarely change once set. The score results table remains the source of truth; the asset columns are a read cache.

### Pattern 4: Scheduled Backfill for Historical Assets

**What:** Register a scoring scan job in APScheduler (alongside existing daily sync jobs) that runs on a separate interval (e.g., every 15 minutes). The job queries for assets with `scoring_status = 'UNSCORED'` or `'FAILED'`, processes them in batches of N, respecting BrainSuite API rate limits.

**When to use:** Required — there are existing `creative_assets` rows with no scores that must be backfilled. New assets arrive via daily sync and also need scoring.

**Trade-offs:** APScheduler already handles the async event loop in this app. No Redis/Celery needed. Batch size should be conservative (10–20 assets per run) to avoid hammering BrainSuite API. Assets that were scored by the dummy `ace_score.py` implementation should be re-scored by the real API — use `brainsuite_metadata.is_dummy = true` as the detection condition.

## Data Flow

### New Asset Scoring Flow

```
Platform Sync (daily)
    ↓
CreativeAsset inserted/updated
    ↓
Sync service sets scoring_status = 'UNSCORED' on creative_score_results
    ↓
APScheduler scoring job runs (every 15 min)
    ↓
Queries: creative_score_results WHERE status = 'UNSCORED' LIMIT 20
    ↓
Sets status = 'PROCESSING', calls BrainSuiteScoreService.score_asset(asset)
    ↓
BrainSuite API call: POST {asset_url, metadata} → {score, dimensions}
    ↓
On success:
  - Write result to creative_score_results (status = COMPLETE, dimensions JSON)
  - Update creative_assets.ace_score, brainsuite_metadata (denormalize)
On failure:
  - Write error to creative_score_results (status = FAILED, error_message)
  - Retry eligible on next scheduler run
```

### Historical Backfill Flow

```
App startup (or admin trigger via POST /scoring/trigger)
    ↓
Query: creative_assets WHERE ace_score IS NULL
       OR brainsuite_metadata->>'is_dummy' = 'true'
    ↓
For each: upsert creative_score_results with status = 'UNSCORED'
    ↓
Scoring scheduler picks up on next interval (same path as new assets above)
```

### Dashboard Score Display Flow

```
User loads Dashboard
    ↓
GET /api/v1/dashboard/creatives
    ↓
Query: SELECT creative_assets.*, ace_score, brainsuite_metadata
       (score already denormalized on asset row — no extra join)
    ↓
Response includes: ace_score, scoring_status, dimension breakdown
    ↓
Frontend score-badge component:
  - COMPLETE → render score chip with color (green/amber/red)
  - PENDING/PROCESSING → render "Scoring..." spinner
  - UNSCORED → render "Not scored" neutral badge
  - FAILED → render "Score unavailable" with retry option
```

### Scoring Status Polling Flow

```
Frontend mounts dashboard with any PENDING/PROCESSING assets
    ↓
Angular interval (30s) calls GET /api/v1/scoring/status?asset_ids=[...]
    ↓
Backend returns {asset_id: status} map
    ↓
Angular updates score badge reactively when status transitions to COMPLETE
    ↓
Poll stops when all visible assets reach terminal state (COMPLETE or FAILED)
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Current (< 10k assets/org) | APScheduler batch job is sufficient. No queue needed. |
| 10k–100k assets | Increase batch size, add concurrency semaphore to limit parallel BrainSuite calls. Redis already configured — could use it for job deduplication if needed. |
| 100k+ assets | Consider moving scoring worker to separate process (Celery + Redis). Not needed for v1. |

### Scaling Priorities

1. **First bottleneck:** BrainSuite API rate limits. Fix by adding a semaphore and configurable batch size in `BrainSuiteScoreService`. Start at 5 concurrent requests per scheduler run.
2. **Second bottleneck:** Dashboard query joins asset + scoring status. Fix by ensuring the score columns remain denormalized on `creative_assets` (Pattern 3 above) and that `ace_score` is indexed.

## Anti-Patterns

### Anti-Pattern 1: Synchronous BrainSuite API Call in Request Handler

**What people do:** Call the BrainSuite API directly in the POST handler and wait for the response before returning to the user.

**Why it's wrong:** BrainSuite calls take 1–10 seconds. Blocks the request thread, causes timeouts for bulk operations, and degrades dashboard responsiveness.

**Do this instead:** Accept the trigger, set status to PENDING, fire the actual API call as a BackgroundTask or let the scheduler handle it. Return 202 Accepted immediately.

### Anti-Pattern 2: Storing Dimensions Only in JSONB Without Denormalization

**What people do:** Store the entire BrainSuite response JSONB in `brainsuite_metadata` and require the dashboard to unpack it client-side for display.

**Why it's wrong:** The existing export endpoint already reads individual dimension keys (`attention_score`, `brand_score`, etc.) from `brainsuite_metadata`. Relying on JSONB key lookups in ORDER BY or WHERE clauses is slow and non-indexable.

**Do this instead:** The `creative_score_results` table stores the full JSONB response. The dashboard uses the denormalized top-level `ace_score` float column for sorting/filtering. Dimension breakdown (detail view only) unpacks from JSONB on demand.

### Anti-Pattern 3: Re-scoring Already Scored Assets on Every Sync

**What people do:** Trigger a BrainSuite API call every time a daily sync touches an asset record (even if the creative hasn't changed).

**Why it's wrong:** Wastes BrainSuite API quota. Scores are stable unless the creative changes. Platform syncs update performance metrics daily but the creative asset file itself is static.

**Do this instead:** Check `scoring_status = 'COMPLETE'` before queuing. Only re-score if the asset URL changes or if an admin explicitly requests a rescore.

### Anti-Pattern 4: Polling for Score on Every Page Render

**What people do:** Call a score status endpoint on every component initialization, regardless of whether assets have pending scores.

**Why it's wrong:** Unnecessary load. Most assets will be COMPLETE once backfill runs.

**Do this instead:** Only start the poll interval if the current page view contains assets with `PENDING` or `PROCESSING` status. Stop polling when all visible assets reach terminal state.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| BrainSuite API | HTTP POST from `BrainSuiteScoreService` (async httpx) | Asset URL must be publicly accessible or signed. GCS signed URLs expire — generate fresh signed URL per scoring request, not stored URL. |
| Google Cloud Storage | Already integrated via `object_storage.py` | Use `generate_signed_url()` to produce time-limited URL to pass to BrainSuite |
| APScheduler | Add scoring scan job via `scheduler.add_job()` in `startup_scheduler()` | Use `IntervalTrigger(minutes=15)`, not cron — avoids timezone alignment issues for a catch-up process |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Sync services → Scoring | Sync inserts `creative_score_results` row with `UNSCORED` status after asset upsert | Sync service is not responsible for calling BrainSuite — only marking intent |
| Scheduler → BrainSuiteScoreService | Direct async function call within same process | APScheduler runs in the same asyncio event loop; keep calls fully async |
| BrainSuiteScoreService → creative_assets | Write denormalized score columns after successful API response | One write path — service owns both the results table and the denormalized columns |
| API endpoints → BrainSuiteScoreService | Endpoints call service methods; do not call BrainSuite API directly | Same service layer pattern as existing OAuth/sync services |
| Frontend → scoring endpoints | HTTP polling every 30s while PENDING/PROCESSING assets are visible | Not WebSocket — simplicity wins; polling is sufficient given 15-min scheduler cadence |

## Build Order

Based on component dependencies, the recommended build sequence is:

1. **Schema + model** (`creative_score_results` table, Alembic migration) — everything else reads/writes this table
2. **BrainSuiteScoreService** — the core API client; can be tested in isolation with mock responses
3. **Scheduler integration** — register scoring scan job; depends on service and model
4. **Backfill trigger** — at startup or via admin endpoint, mark existing un-scored assets as UNSCORED; depends on model
5. **Scoring API endpoints** — expose status and manual trigger; depends on service and model
6. **Score denormalization** — write `ace_score` / `brainsuite_metadata` back to `creative_assets`; part of step 2 (service handles this)
7. **Frontend score badge** — display component; depends on API returning status field
8. **Frontend dimension breakdown** — detail panel; depends on score badge existing and confirmed schema for dimension keys
9. **Frontend polling** — activate only when badge detects PENDING/PROCESSING status; final wiring step

## Sources

- [FastAPI Background Tasks official docs](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Managing Background Tasks in FastAPI — Leapcell](https://leapcell.io/blog/managing-background-tasks-and-long-running-operations-in-fastapi)
- [Managing Asynchronous Workflows with REST API — AWS Architecture Blog](https://aws.amazon.com/blogs/architecture/managing-asynchronous-workflows-with-a-rest-api/)
- [APScheduler with FastAPI — Medium/rajansahu](https://rajansahu713.medium.com/implementing-background-job-scheduling-in-fastapi-with-apscheduler-6f5fdabf3186)
- [PostgreSQL Task Queue Design — Medium/huimin](https://medium.com/@huimin.hacker/task-queue-design-with-postgres-b57146d741dc)
- Existing codebase analysis: `backend/app/services/sync/scheduler.py`, `backend/app/models/creative.py`, `backend/app/services/ace_score.py`

---
*Architecture research for: BrainSuite creative scoring pipeline integration*
*Researched: 2026-03-20*
