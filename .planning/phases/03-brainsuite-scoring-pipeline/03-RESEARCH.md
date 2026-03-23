# Phase 3: BrainSuite Scoring Pipeline - Research

**Researched:** 2026-03-23
**Domain:** BrainSuite API integration, async scoring pipeline, APScheduler, SQLAlchemy migrations, Angular polling
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**BrainSuite API — Auth & Endpoints**
- Auth: OAuth 2.0 Client Credentials flow
  - Token endpoint: `https://auth.brainsuite.ai/oauth2/token`
  - Encode `client_id:client_secret` as Base64, send as Basic auth with `grant_type=client_credentials`
  - Returns `{"token_type": "Bearer", "access_token": "..."}` — only one active token per client at a time
- Video scoring endpoint: `POST https://api.brainsuite.ai/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/create`
- Workflow: Create-Job (URL-based) — send a signed S3 URL per SCORE-03
- Status polling: `GET https://api.brainsuite.ai/v1/jobs/{jobId}` until status `Succeeded` or `Failed`
  - Status values: `Scheduled` → `Created` → `Started` → `Succeeded` | `Failed` | `Stale`
  - Poll every ~30 seconds while `Scheduled` or `Created`
- Staging base URL: `https://api.staging.brainsuite.ai` (dev/test)
- Production base URL: `https://api.brainsuite.ai`

**BrainSuite API — Request Payload**
- `assets` array: one asset per job with `assetId: "video"`, `name`, `url` (fresh signed S3 URL)
- `input` object: `channel`, `assetLanguage`, `brandNames[]`, `projectName`, `assetName`, `assetStage`, `voiceOver` (optional), `voiceOverLanguage` (required if voiceOver set)

**BrainSuite API — Channel Mapping**
- META + facebook_feed → `facebook_feed`; META + facebook_story → `facebook_story`; META + instagram_feed → `instagram_feed`; META + instagram_story → `instagram_story`; META + instagram_reels/instagram_reel → `instagram_reel`; META + audience_network_* or unknown → `facebook_feed`
- TIKTOK + any → `tiktok`
- GOOGLE_ADS + any → `youtube`
- DV360 + any → `youtube`

**BrainSuite API — Metadata-Driven Fields**
- Required: `brainsuite_brand_names` → `brandNames`, `brainsuite_asset_language` → `assetLanguage`
- Optional: `brainsuite_project_name`, `brainsuite_asset_name`, `brainsuite_asset_stage`, `brainsuite_voice_over`, `brainsuite_voice_over_language`
- Seeded as `MetadataField` entries per org; new orgs get them on first setup
- Channel is overridable via metadata field if set

**BrainSuite API — Response / Score Shape**
- `output.legResults[].executiveSummary.rawTotalScore` → `total_score`
- `output.legResults[].executiveSummary.totalRating` → `total_rating` (positive/medium/negative)
- `output.legResults[].categories[]` → named categories with scores and ratings
- `output.legResults[].kpis{}` → named KPI objects with score and rating
- Do NOT store visualization URLs (expire after 1 hour)
- Store full `output` blob (minus visualizations) as JSONB `score_dimensions`

**Rate Limiting**
- `x-ratelimit-reset` ISO 8601 UTC header for 429 backoff
- 429 → wait until `x-ratelimit-reset` timestamp
- 5xx → short exponential backoff (tenacity)
- 4xx (except 429) → no retry, mark FAILED with error reason

**Data Model**
- New table: `creative_score_results` — UNSCORED → PENDING → PROCESSING → COMPLETE | FAILED
- Fields: `creative_asset_id` (FK), `organization_id`, `scoring_status`, `brainsuite_job_id` (nullable), `total_score` (Float, nullable), `total_rating` (String, nullable), `score_dimensions` (JSONB), `error_reason` (Text, nullable), `scored_at` (DateTime, nullable), `created_at`, `updated_at`
- One record per creative asset (upsert on re-score)
- Indexed on `scoring_status` and `creative_asset_id`
- Drop from `creative_assets`: `ace_score`, `ace_score_confidence`, `brainsuite_metadata`

**Scoring Job Architecture**
- APScheduler `IntervalTrigger(minutes=15)`, batch up to 20 UNSCORED VIDEO assets
- Job flow: query UNSCORED → generate signed S3 URL → build payload → POST create → set PENDING + store job ID → poll until Succeeded/Failed → store results
- Auto-queue: after harmonizer inserts new `CreativeAsset` records, upsert `creative_score_results` UNSCORED for VIDEO assets
- Manual re-score: `POST /api/v1/scoring/{asset_id}/rescore` → reset to UNSCORED

**Frontend — Score Display**
- Score badge in table: dash for UNSCORED/FAILED, spinner chip for PENDING/PROCESSING, colored number badge for COMPLETE
- Colors by `totalRating`: positive=green, medium=amber, negative=red
- Polling endpoint: `/api/v1/scoring/status?asset_ids=...` — only while PENDING/PROCESSING visible, stops when none remain
- "Creative Effectiveness" tab in existing `asset-detail-dialog` — populate with `totalScore` + `categories[]`
- Right-click context menu: "Score now" → `POST /api/v1/scoring/{asset_id}/rescore`

### Claude's Discretion
- Tenacity retry configuration (backoff multiplier, max attempts for 5xx)
- Token caching strategy for BrainSuite Bearer token (cache until expiry vs. re-fetch per job run)
- Exact polling interval and max poll attempts before marking job as FAILED/STALE
- Score badge color thresholds (using totalRating enum from API: positive/medium/negative)
- `score_dimensions` JSONB schema (exact fields stored — determined from spike)

### Deferred Ideas (OUT OF SCOPE)
- Image scoring (ACE_STATIC_SOCIAL_STATIC_API) — future phase
- Score-to-ROAS correlation view — DASH-v2-01
- Score trend over time per creative — DASH-v2-03
- Backfill scoring for historical assets — SCORE-v2-01
- YouTube Shorts channel mapping (videos under 60s → `youtube_shorts`)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SCORE-01 | `creative_score_results` table with scoring state machine (UNSCORED → PENDING → PROCESSING → COMPLETE | FAILED) | Alembic migration pattern confirmed; pg_insert upsert pattern available from harmonizer |
| SCORE-02 | `BrainSuiteScoreService` — async httpx client with tenacity retry (429=long backoff, 5xx=short backoff, 4xx=no retry) | currency.py httpx pattern directly applicable; tenacity in requirements.txt NOT present — must be added |
| SCORE-03 | Fresh GCS/S3 signed URLs generated per scoring request | `object_storage.generate_signed_url(relative_path, ttl_sec)` confirmed; call immediately before POSTing |
| SCORE-04 | APScheduler scoring job runs every 15 minutes, batches up to 20 UNSCORED assets, respects rate limits | `IntervalTrigger` already used in scheduler.py; `startup_scheduler()` is the registration point |
| SCORE-05 | New assets automatically queued as UNSCORED after platform sync completes | `harmonizer._ensure_asset()` is the injection point — called for every new asset across all platforms |
| SCORE-06 | Manual re-score trigger via UI and API endpoint | New router at `/api/v1/scoring`; registered in `api/v1/__init__.py` alongside existing routers |
| SCORE-07 | Score dimensions stored and retrievable per creative (confirmed via API discovery spike at phase start) | JSONB column `score_dimensions` in `creative_score_results`; new GET endpoint needed |
| SCORE-08 | Scoring status endpoint (`/scoring/status`) for frontend polling | New endpoint returning status + score per requested asset_ids list |
</phase_requirements>

---

## Summary

Phase 3 wires the BrainSuite API into a fully async scoring pipeline. The existing codebase provides all the building blocks: httpx async client pattern (currency.py), APScheduler job registration (scheduler.py), signed S3 URL generation (object_storage.py), metadata field values (models/metadata.py), and upsert patterns (harmonizer.py using `pg_insert`). The main net-new work is the `creative_score_results` table, a `BrainSuiteScoreService`, a scoring router, and frontend additions to the dashboard table and asset detail dialog.

The most important pre-implementation constraint is the **API discovery spike**: the exact set of `categories` and `kpis` keys returned by BrainSuite must be captured from a real API response before the "Creative Effectiveness" tab layout can be finalized. The CONTEXT.md explicitly gates the frontend dimension display on this spike.

One key finding: `tenacity` is referenced in CONTEXT.md as the retry library but is **not currently in `backend/requirements.txt`**. It must be added. The existing currency.py uses manual try/except with logging rather than tenacity decorators, so the tenacity integration for BrainSuiteScoreService will be new territory for this codebase.

**Primary recommendation:** Implement in waves — (1) Alembic migration + model, (2) BrainSuiteScoreService with auth + retry, (3) scoring job + harmonizer integration, (4) scoring API router, (5) frontend badge + polling, (6) asset detail tab.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.25.2 (pinned) | Async HTTP client for BrainSuite API | Already in use throughout codebase; async-native |
| tenacity | must add (~8.x) | Retry logic with exponential backoff | Best-in-class Python retry library; handles 429 wait-until patterns |
| APScheduler | 3.10.4 (pinned) | Scoring job scheduler | Already used for sync jobs; `AsyncIOScheduler` + `IntervalTrigger` |
| SQLAlchemy | 2.0.23 (pinned) | ORM + async session | Already used; `JSONB` type for `score_dimensions` |
| Alembic | 1.12.1 (pinned) | DB migration for new table | Existing migration chain to extend |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| boto3 | >=1.42.0 (pinned) | Generate fresh S3 signed URLs | Already wired in `ObjectStorageService.generate_signed_url()` |
| pydantic | 2.5.0 (pinned) | DTO validation for scoring endpoints | Consistent with all existing endpoints |
| Angular + RxJS | (existing) | Frontend polling with interval | Use `interval()` + `takeUntil()` for smart polling |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tenacity decorators | Manual asyncio retry loop | Tenacity is cleaner and testable; manual loop is what currency.py does but harder to reason about backoff |
| In-memory token cache | Redis token cache | In-memory is sufficient for single-worker; Redis would be needed for multi-worker — SCHEDULER_ENABLED guard already prevents multi-worker scheduler |
| APScheduler interval job for polling | Celery beat | APScheduler is already the project standard; Celery adds overhead with no benefit here |

**Installation:**
```bash
# Add to backend/requirements.txt:
tenacity>=8.2.0
```

**Version verification:** Run `npm view tenacity version` is not applicable (Python). Check PyPI:
```bash
pip index versions tenacity 2>/dev/null | head -1
# Current stable: 9.0.0 (as of 2026-03)
```
Use `tenacity>=8.2.0` to allow patch/minor upgrades while ensuring `wait_exponential_jitter` is available.

---

## Architecture Patterns

### Recommended Project Structure

New files to create:
```
backend/
├── app/
│   ├── models/
│   │   └── scoring.py                     # CreativeScoreResult model
│   ├── services/
│   │   └── brainsuite_score.py            # BrainSuiteScoreService
│   ├── api/v1/endpoints/
│   │   └── scoring.py                     # /scoring router
│   └── (modify)
│       ├── services/sync/harmonizer.py    # add UNSCORED queue after _ensure_asset
│       ├── services/sync/scheduler.py     # register scoring job in startup_scheduler
│       ├── core/config.py                 # add BRAINSUITE_* env vars
│       └── api/v1/__init__.py             # include scoring router
├── alembic/versions/
│   └── {hash}_add_creative_score_results.py
frontend/src/app/features/dashboard/
├── dashboard.component.ts                 # add score badge column + polling
└── dialogs/asset-detail-dialog.component.ts  # populate "Creative Effectiveness" tab
```

### Pattern 1: BrainSuiteScoreService — Auth Token Management

**What:** Cache Bearer token in-memory with expiry timestamp; re-fetch only on expiry or 401.
**When to use:** Single-scheduler-worker deployment (SCHEDULER_ENABLED guard prevents multiple workers running scheduler).

```python
# Source: BrainSuite API Docs General.txt + currency.py pattern
import httpx
import base64
from datetime import datetime, timedelta
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

class BrainSuiteScoreService:
    def __init__(self):
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    async def _get_token(self) -> str:
        now = datetime.utcnow()
        if self._token and self._token_expires_at and now < self._token_expires_at:
            return self._token
        credentials = base64.b64encode(
            f"{settings.BRAINSUITE_CLIENT_ID}:{settings.BRAINSUITE_CLIENT_SECRET}".encode()
        ).decode()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://auth.brainsuite.ai/oauth2/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )
            resp.raise_for_status()
            data = resp.json()
        self._token = data["access_token"]
        # BrainSuite docs: only one token active at a time; conservative 50-min expiry
        self._token_expires_at = now + timedelta(minutes=50)
        return self._token
```

### Pattern 2: BrainSuiteScoreService — Create Job with Tenacity Retry

**What:** POST to create-job endpoint; handle 429 (wait until x-ratelimit-reset), 5xx (exponential backoff), 4xx (no retry).
**When to use:** Every scoring submission.

```python
# Source: BrainSuite API Docs General.txt + CONTEXT.md rate limit spec
import asyncio
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

class BrainSuiteRateLimitError(Exception):
    def __init__(self, reset_at: datetime):
        self.reset_at = reset_at

class BrainSuite5xxError(Exception):
    pass

async def _create_job_raw(self, token: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/create",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code == 429:
            reset_str = resp.headers.get("x-ratelimit-reset")
            reset_at = datetime.fromisoformat(reset_str.replace("Z", "+00:00")) if reset_str else (
                datetime.now(timezone.utc) + timedelta(minutes=15)
            )
            raise BrainSuiteRateLimitError(reset_at)
        if resp.status_code >= 500:
            raise BrainSuite5xxError(f"BrainSuite {resp.status_code}: {resp.text}")
        if resp.status_code >= 400:
            # 4xx (not 429): no retry, propagate as fatal
            raise ValueError(f"BrainSuite 4xx {resp.status_code}: {resp.text}")
        return resp.json()
```

**429 handling pattern** — wait until `x-ratelimit-reset`, not a fixed sleep:
```python
async def create_job_with_retry(self, payload: dict) -> dict:
    for attempt in range(5):
        token = await self._get_token()
        try:
            return await self._create_job_raw(token, payload)
        except BrainSuiteRateLimitError as e:
            wait_secs = max(0, (e.reset_at - datetime.now(timezone.utc)).total_seconds()) + 2
            logger.warning(f"BrainSuite 429 — waiting {wait_secs:.0f}s until {e.reset_at}")
            await asyncio.sleep(wait_secs)
        except BrainSuite5xxError as e:
            if attempt >= 4:
                raise
            wait = min(2 ** attempt * 5, 120)
            logger.warning(f"BrainSuite 5xx — backoff {wait}s: {e}")
            await asyncio.sleep(wait)
    raise RuntimeError("BrainSuite create_job exhausted retries")
```

### Pattern 3: Scoring Job Registration

**What:** Add `IntervalTrigger(minutes=15)` job to `startup_scheduler()`, wrapped in try/except for per-asset isolation.

```python
# Source: scheduler.py startup_scheduler() pattern
# In startup_scheduler():
scheduler.add_job(
    run_scoring_batch,
    trigger=IntervalTrigger(minutes=15),
    id="scoring_batch",
    replace_existing=True,
    max_instances=1,
)
```

Key: `max_instances=1` prevents overlapping runs if a batch takes longer than 15 minutes.

### Pattern 4: UNSCORED Queue Injection in Harmonizer

**What:** After `_ensure_asset()` creates a new VIDEO asset, upsert a `creative_score_results` row with `UNSCORED`.

```python
# Source: harmonizer.py _ensure_asset() + pg_insert upsert pattern
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.scoring import CreativeScoreResult

# Called after db.flush() on new asset
if asset_format and asset_format.upper() == "VIDEO":
    stmt = pg_insert(CreativeScoreResult).values(
        creative_asset_id=asset.id,
        organization_id=asset.organization_id,
        scoring_status="UNSCORED",
    ).on_conflict_do_nothing(index_elements=["creative_asset_id"])
    await db.execute(stmt)
```

**Critical:** Use `on_conflict_do_nothing` not `on_conflict_do_update` — do NOT reset a COMPLETE/FAILED asset back to UNSCORED on re-sync.

### Pattern 5: Asset URL for Signing

**What:** `creative_asset.asset_url` stores the relative S3 path (not a full URL). Pass to `object_storage.generate_signed_url(relative_path, ttl_sec=3600)`.

From `object_storage.py`:
```python
def generate_signed_url(self, relative_path: str, ttl_sec: int = 3600) -> Optional[str]:
    # Returns full presigned URL with public URL rewrite for MinIO dev
```

Use `ttl_sec=3600` (1 hour) — longer than the BrainSuite job processing time. Generate immediately before POSTing.

### Pattern 6: Frontend Polling — Smart Stop

**What:** Poll `/api/v1/scoring/status?asset_ids=...` only while PENDING/PROCESSING assets are visible; stop when all are COMPLETE/FAILED.

```typescript
// Source: Angular RxJS interval + takeUntil pattern
import { interval, Subject } from 'rxjs';
import { takeUntil, switchMap } from 'rxjs/operators';

private stopPolling$ = new Subject<void>();

startPolling(pendingIds: string[]) {
  interval(10000).pipe(
    takeUntil(this.stopPolling$),
    switchMap(() => this.api.getScoringStatus(pendingIds))
  ).subscribe(statuses => {
    this.updateScoreBadges(statuses);
    const stillPending = statuses.filter(
      s => s.scoring_status === 'PENDING' || s.scoring_status === 'PROCESSING'
    );
    if (stillPending.length === 0) {
      this.stopPolling$.next();
    }
  });
}
```

### Anti-Patterns to Avoid

- **Storing visualization URLs in `score_dimensions`**: BrainSuite visualizations expire after 1 hour. Strip all `visualizations` keys before persisting to JSONB.
- **Using `on_conflict_do_update` in harmonizer upsert**: Would reset scoring status to UNSCORED on every sync, destroying COMPLETE records.
- **Re-fetching token on every API call**: BrainSuite only allows one active token per client. Cache with expiry.
- **Fixed sleep on 429**: Must read `x-ratelimit-reset` header and wait until that timestamp.
- **Polling BrainSuite job status inside the same DB transaction**: Hold no DB session during long-running HTTP polling loops (follows DV360 pattern in scheduler.py — "polling reports with no DB session held").
- **Running scoring job on startup with no `max_instances=1` guard**: Without this, overlapping scheduler fires can cause duplicate job submissions.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retry with exponential backoff | Custom asyncio retry loop | `tenacity` | Handles jitter, max attempts, condition-based retry; battle-tested |
| Signed S3 URLs | Call boto3 directly | `object_storage.generate_signed_url()` | Already handles MinIO/AWS endpoint distinction and public URL rewrite |
| DB session management in scheduler | Raw engine access | `get_session_factory()()` context manager | Handles async session lifecycle and commit/rollback as per existing scheduler pattern |
| Per-org metadata field seeding | Runtime check-and-create | Alembic data migration (or startup seed function) | Ensures consistent org setup; same approach used for other seed data |
| JSONB upsert | Manual SELECT then INSERT or UPDATE | `pg_insert(...).on_conflict_do_nothing()` | Atomic, avoids race conditions in concurrent scheduler runs |

**Key insight:** The BrainSuite 429 rate limit reset timestamp must be respected exactly — sleeping for a fixed duration would either undersleep (triggering another 429) or oversleep (wasting time). Read `x-ratelimit-reset` ISO 8601 UTC, parse to datetime, compute `max(0, reset_at - now) + 2s` buffer.

---

## Common Pitfalls

### Pitfall 1: Asset URL vs Served URL Confusion
**What goes wrong:** `creative_asset.asset_url` stores `/objects/path/to/file.mp4` (the served proxy path), not the raw S3 key. Passing this directly to `generate_signed_url()` would fail.
**Why it happens:** `object_storage.served_url()` prepends `/objects/` as a proxy prefix; `_object_name()` returns the relative path unchanged.
**How to avoid:** Inspect `asset_url` and strip the `/objects/` prefix before passing to `generate_signed_url()`. Or store and retrieve `asset_url` as the raw relative S3 key. Confirm what format is stored at Phase 3 start.
**Warning signs:** Signed URL generation returns `None` or 404 on presigned URL access.

### Pitfall 2: `ace_score` Column Migration — Foreign Key Safety
**What goes wrong:** Dropping `ace_score`, `ace_score_confidence`, `brainsuite_metadata` from `creative_assets` breaks any code that references those columns before the new `creative_score_results` table is ready.
**Why it happens:** The harmonizer currently writes to `ace_score` on every `_ensure_asset()` call. If the migration drops the column before the service code is updated, the app crashes.
**How to avoid:** In the same Alembic migration: (1) create `creative_score_results`, (2) then drop old columns. Deploy service code changes atomically with migration. The `generate_ace_score` import in `harmonizer.py` must be removed at the same time.
**Warning signs:** `sqlalchemy.exc.ProgrammingError: column "ace_score" of relation "creative_assets" does not exist`

### Pitfall 3: STALE Status Handling
**What goes wrong:** BrainSuite jobs can reach `Stale` status (not started). If the scoring service only handles `Succeeded`/`Failed`, `Stale` jobs block the asset indefinitely.
**Why it happens:** The BrainSuite status machine has `Stale` as a terminal non-success state — documented in API docs.
**How to avoid:** Treat `Stale` the same as `Failed`: set `scoring_status=FAILED`, `error_reason="BrainSuite job stale"`.
**Warning signs:** Assets stuck in `PROCESSING` indefinitely.

### Pitfall 4: Poll Loop Holds DB Session
**What goes wrong:** Polling BrainSuite job status (30-second intervals, multiple polls) while holding a live SQLAlchemy async session causes session timeout or connection exhaustion.
**Why it happens:** SQLAlchemy async connections have idle timeouts; long-running polling ties up a connection from the pool.
**How to avoid:** Follow the existing DV360 pattern in scheduler.py — "polling reports with no DB session held". Open a new session only when writing results after polling completes.
**Warning signs:** `asyncpg.exceptions.IdleInTransactionSessionTimeoutError` or connection pool exhaustion.

### Pitfall 5: Missing `SCHEDULER_ENABLED` Guard on Scoring Job
**What goes wrong:** In multi-worker deploys, every worker registers and runs the scoring job, causing duplicate BrainSuite API submissions and wasted rate-limit budget.
**Why it happens:** The existing `startup_scheduler()` already has this guard pattern; a new scoring job must also check it.
**How to avoid:** The `SCHEDULER_ENABLED` env var check is in main.py's `_background_startup()` — `startup_scheduler()` is only called on the designated worker. Scoring job registration inside `startup_scheduler()` is inherently protected. Verify no separate scoring job registration path exists outside `startup_scheduler()`.
**Warning signs:** BrainSuite rate limit hit faster than expected; duplicate `brainsuite_job_id` entries.

### Pitfall 6: Brainsuite Token Reuse Across Scoring Batch
**What goes wrong:** BrainSuite API docs state "only one bearer token may exist outstanding for a customer client, and repeated requests to this method will yield the same already-existent token until it has been invalidated." Requesting a new token while the old one is valid returns the same token — this is not an error but confirms caching is safe.
**Why it happens:** Misreading this as "always re-request token per job" wastes an API call but doesn't break anything.
**How to avoid:** Cache token in-memory on the service singleton with a conservative 50-minute expiry (shorter than actual expiry to handle clock skew).

### Pitfall 7: Frontend DashboardAsset Interface Still Has `ace_score`
**What goes wrong:** `dashboard.component.ts` has `ace_score: number | null` in `DashboardAsset`. After Phase 3 the backend no longer returns `ace_score` from `creative_assets`. If the interface isn't updated, the TypeScript compiler or runtime fails.
**Why it happens:** The field is removed from the SQLAlchemy model but the Angular interface may lag.
**How to avoid:** Replace `ace_score` with `scoring_status: string | null` and `total_score: number | null` in the `DashboardAsset` interface. Update the dashboard endpoint to join with `creative_score_results`.

---

## Code Examples

### BrainSuite Create-Job Payload Construction

```python
# Source: CONTEXT.md decisions + brainsuite_api/API Docs General.txt
def _build_payload(asset: CreativeAsset, metadata: dict[str, str], signed_url: str) -> dict:
    channel = _map_channel(asset.platform, asset.placement, metadata)
    return {
        "assets": [
            {
                "assetId": "video",
                "name": asset.ad_name or f"{asset.id}.mp4",
                "url": signed_url,
            }
        ],
        "input": {
            "channel": channel,
            "assetLanguage": metadata.get("brainsuite_asset_language", "en"),
            "brandNames": [
                b.strip()
                for b in (metadata.get("brainsuite_brand_names") or "").replace("\n", ",").split(",")
                if b.strip()
            ],
            "projectName": metadata.get("brainsuite_project_name") or "Spring Campaign 2026",
            "assetName": metadata.get("brainsuite_asset_name") or "asset_name",
            "assetStage": metadata.get("brainsuite_asset_stage") or "finalVersion",
            **(
                {
                    "voiceOver": metadata["brainsuite_voice_over"],
                    "voiceOverLanguage": metadata.get("brainsuite_voice_over_language", "en"),
                }
                if metadata.get("brainsuite_voice_over")
                else {}
            ),
        },
    }

def _map_channel(platform: str, placement: str | None, metadata: dict) -> str:
    # Channel override from metadata takes priority
    if metadata.get("brainsuite_channel"):
        return metadata["brainsuite_channel"]
    p = (placement or "").lower().strip()
    p = p.replace("reels", "reel")  # instagram_reels -> instagram_reel
    if platform == "META":
        if p in ("facebook_feed", "facebook_story", "instagram_feed", "instagram_story", "instagram_reel"):
            return p
        return "facebook_feed"  # fallback for audience_network_* or unknown
    if platform == "TIKTOK":
        return "tiktok"
    if platform in ("GOOGLE_ADS", "DV360"):
        return "youtube"
    return "facebook_feed"  # safe default
```

### Alembic Migration Structure

```python
# Source: existing migration pattern, e.g. alembic/versions/41dcacc7071c_initial.py
def upgrade() -> None:
    # 1. Create creative_score_results
    op.create_table(
        "creative_score_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("creative_asset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("creative_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("scoring_status", sa.String(50), nullable=False, default="UNSCORED"),
        sa.Column("brainsuite_job_id", sa.String(255), nullable=True),
        sa.Column("total_score", sa.Float, nullable=True),
        sa.Column("total_rating", sa.String(50), nullable=True),
        sa.Column("score_dimensions", postgresql.JSONB, nullable=True),
        sa.Column("error_reason", sa.Text, nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("creative_asset_id", name="uq_score_per_asset"),
    )
    op.create_index("ix_score_results_status", "creative_score_results", ["scoring_status"])
    op.create_index("ix_score_results_asset", "creative_score_results", ["creative_asset_id"])

    # 2. Drop old dummy score columns from creative_assets
    op.drop_column("creative_assets", "ace_score")
    op.drop_column("creative_assets", "ace_score_confidence")
    op.drop_column("creative_assets", "brainsuite_metadata")
```

### Scoring Batch Job Skeleton

```python
# Source: scheduler.py run_daily_sync() pattern
async def run_scoring_batch() -> None:
    """APScheduler job: score up to 20 UNSCORED VIDEO assets."""
    from sqlalchemy import select
    from app.models.creative import CreativeAsset
    from app.models.scoring import CreativeScoreResult

    async with get_session_factory()() as db:
        result = await db.execute(
            select(CreativeScoreResult)
            .join(CreativeAsset, CreativeAsset.id == CreativeScoreResult.creative_asset_id)
            .where(
                CreativeScoreResult.scoring_status == "UNSCORED",
                CreativeAsset.asset_format == "VIDEO",
            )
            .limit(20)
        )
        batch = result.scalars().all()

        for score_record in batch:
            try:
                await _score_single_asset(db, score_record)
            except Exception as e:
                logger.error(
                    "Scoring failed for asset %s: %s: %s",
                    score_record.creative_asset_id, type(e).__name__, e
                )
                score_record.scoring_status = "FAILED"
                score_record.error_reason = f"{type(e).__name__}: {str(e)[:500]}"
                score_record.updated_at = datetime.utcnow()
                db.add(score_record)
        await db.commit()
```

### Metadata Field Seeding Migration

```python
# Source: CONTEXT.md metadata-driven fields spec
BRAINSUITE_METADATA_FIELDS = [
    {"name": "brainsuite_brand_names", "label": "Brand Names", "field_type": "TEXT", "is_required": True, "sort_order": 0},
    {"name": "brainsuite_asset_language", "label": "Asset Language", "field_type": "SELECT", "is_required": True, "sort_order": 1},
    {"name": "brainsuite_project_name", "label": "Project Name", "field_type": "TEXT", "is_required": False, "sort_order": 2, "default_value": "Spring Campaign 2026"},
    {"name": "brainsuite_asset_name", "label": "Asset Name", "field_type": "TEXT", "is_required": False, "sort_order": 3, "default_value": "asset_name"},
    {"name": "brainsuite_asset_stage", "label": "Asset Stage", "field_type": "SELECT", "is_required": False, "sort_order": 4, "default_value": "finalVersion"},
    {"name": "brainsuite_voice_over", "label": "Voice Over", "field_type": "TEXT", "is_required": False, "sort_order": 5},
    {"name": "brainsuite_voice_over_language", "label": "Voice Over Language", "field_type": "SELECT", "is_required": False, "sort_order": 6},
]
# Insert for each existing organization in an Alembic data migration
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Dummy `generate_ace_score()` in harmonizer | Real `BrainSuiteScoreService` via APScheduler | Phase 3 | Remove `ace_score.py` import from harmonizer; remove ace_score columns |
| `ace_score` / `brainsuite_metadata` on `creative_assets` | Separate `creative_score_results` table with state machine | Phase 3 | Enables async retry, partial failure, per-asset scoring lifecycle |
| No tenacity in requirements.txt | Add `tenacity>=8.2.0` | Phase 3 | New dependency; enables declarative retry with correct 429 handling |
| Frontend `DashboardAsset.ace_score: number \| null` | `scoring_status: string`, `total_score: number \| null` | Phase 3 | Interface update required alongside backend endpoint change |

**Deprecated/outdated after Phase 3:**
- `backend/app/services/ace_score.py`: entire file — remove after wiring real service
- `creative_assets.ace_score`, `ace_score_confidence`, `brainsuite_metadata` columns: dropped in migration
- Dashboard endpoint `ace_score` field in response: replaced with `scoring_status` + `total_score`
- `harmonizer._ensure_asset()` ace score call: removed, replaced with UNSCORED queue injection

---

## Open Questions

1. **Asset URL format stored in `creative_assets.asset_url`**
   - What we know: `object_storage.served_url()` returns `/objects/{relative_path}`. `_ensure_asset()` stores the raw URL from platform sync (`raw.asset_url`, `raw.creative_url`). Platform sync stores whatever URL the platform provides — may be an external URL, not an S3 path.
   - What's unclear: For assets that have been downloaded to S3 (DV360 download pipeline), `asset_url` is the relative S3 key. For META/TikTok assets, it may be the CDN URL or may be blank. Which assets have a valid S3 key to sign?
   - Recommendation: At Phase 3 start, query a sample of VIDEO assets and inspect `asset_url` values. Only assets with an S3 key can be submitted to BrainSuite. Assets without a local S3 URL should be skipped (left UNSCORED) and flagged for investigation.

2. **BrainSuite job response exact schema (API spike required)**
   - What we know: Response contains `output.legResults[].executiveSummary`, `categories[]`, `kpis{}`. Specific `categories` and `kpis` names are undocumented until first real response.
   - What's unclear: Number of categories, exact `kpi` keys, whether `kpis` is always present, whether `legResults` always has exactly one entry for single-asset jobs.
   - Recommendation: Wave 0 task — submit one real video to BrainSuite staging, capture full JSON, document the schema. Gate `score_dimensions` JSONB column definition and "Creative Effectiveness" tab layout on this spike output.

3. **BrainSuite token expiry duration**
   - What we know: Docs say "only one bearer token may exist outstanding per client." No explicit expiry duration stated.
   - What's unclear: How long the token is valid before it expires and needs renewal.
   - Recommendation: Use conservative 50-minute in-memory cache. If a 401 is received, invalidate cache and re-fetch immediately. Add 401 handling to the service.

---

## Validation Architecture

> `nyquist_validation` is `true` in `.planning/config.json` — section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4.0+ with pytest-asyncio 0.23.0+ |
| Config file | `pyproject.toml` at project root (`testpaths = ["backend/tests"]`, `asyncio_mode = "auto"`) |
| Quick run command | `pytest backend/tests/test_scoring.py -x` |
| Full suite command | `pytest backend/tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCORE-01 | `creative_score_results` model fields and state machine transitions | unit | `pytest backend/tests/test_scoring.py::test_score_result_model -x` | ❌ Wave 0 |
| SCORE-02 | `BrainSuiteScoreService._get_token()` caches token and re-fetches on expiry | unit | `pytest backend/tests/test_scoring.py::test_token_caching -x` | ❌ Wave 0 |
| SCORE-02 | 429 → waits until x-ratelimit-reset; 5xx → exponential retry; 4xx → raises immediately | unit | `pytest backend/tests/test_scoring.py::test_retry_logic -x` | ❌ Wave 0 |
| SCORE-03 | Fresh signed URL generated per scoring request (not cached/stored URL) | unit | `pytest backend/tests/test_scoring.py::test_signed_url_generation -x` | ❌ Wave 0 |
| SCORE-04 | Scoring batch processes at most 20 UNSCORED VIDEO assets per run | unit | `pytest backend/tests/test_scoring.py::test_batch_size_limit -x` | ❌ Wave 0 |
| SCORE-05 | New VIDEO asset inserted by harmonizer creates UNSCORED score record; existing COMPLETE not reset | unit | `pytest backend/tests/test_scoring.py::test_unscored_queue_injection -x` | ❌ Wave 0 |
| SCORE-06 | `POST /api/v1/scoring/{asset_id}/rescore` resets status to UNSCORED | unit | `pytest backend/tests/test_scoring.py::test_rescore_endpoint -x` | ❌ Wave 0 |
| SCORE-07 | `score_dimensions` stores output blob without visualization URLs | unit | `pytest backend/tests/test_scoring.py::test_score_dimensions_no_viz_urls -x` | ❌ Wave 0 |
| SCORE-08 | `/scoring/status?asset_ids=...` returns current status for requested assets | unit | `pytest backend/tests/test_scoring.py::test_scoring_status_endpoint -x` | ❌ Wave 0 |
| SCORE-08 | Channel mapping covers all platform/placement combinations including fallbacks | unit | `pytest backend/tests/test_scoring.py::test_channel_mapping -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/test_scoring.py -x`
- **Per wave merge:** `pytest backend/tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_scoring.py` — covers all SCORE-01 through SCORE-08 test cases above
- [ ] No new conftest.py needed — existing `backend/tests/conftest.py` has fixtures (mock_settings, async_client, mock_redis) that can be extended
- [ ] Framework install: `pip install tenacity>=8.2.0` — add to `backend/requirements.txt`

*(Existing test infrastructure covers pytest setup; only the scoring-specific test file is missing)*

---

## Sources

### Primary (HIGH confidence)
- `brainsuite_api/API Docs General.txt` — OAuth 2.0 auth flow, rate limiting headers, Create-Job workflow, polling, visualization expiry
- `backend/app/services/sync/scheduler.py` — APScheduler patterns, startup_scheduler(), IntervalTrigger, SCHEDULER_ENABLED usage
- `backend/app/services/currency.py` — httpx async client pattern, 429 handling, try/except structure to mirror
- `backend/app/services/object_storage.py` — `generate_signed_url()` method signature and return behavior
- `backend/app/models/creative.py` — current `ace_score`, `ace_score_confidence`, `brainsuite_metadata` columns to be dropped
- `backend/app/models/metadata.py` — `MetadataField.name` as key for payload mapping
- `backend/app/services/sync/harmonizer.py` — `_ensure_asset()` injection point, `pg_insert` upsert pattern
- `backend/app/api/v1/endpoints/dashboard.py` — current `ace_score` fields in response (to be replaced)
- `backend/requirements.txt` — confirmed `tenacity` absent; `httpx==0.25.2`, `apscheduler==3.10.4`, `pytest>=7.4.0`
- `pyproject.toml` — `asyncio_mode = "auto"`, `testpaths = ["backend/tests"]`
- `.planning/phases/03-brainsuite-scoring-pipeline/03-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)
- `brainsuite_api/SMV API Docs_compressed.txt` — OpenAPI spec for ACE_VIDEO_SMV_API (file too large to read in full; key decisions already captured in CONTEXT.md from prior session)

### Tertiary (LOW confidence)
- tenacity PyPI version: current stable is 9.0.0 as of early 2026 — verify exact version before pinning (`pip index versions tenacity`)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified in requirements.txt or CONTEXT.md
- Architecture: HIGH — all patterns derived from existing codebase code, not assumption
- Pitfalls: HIGH — each pitfall traced to a specific code artifact in the codebase
- API behavior: HIGH for auth/rate-limit/polling (from API docs); MEDIUM for exact score response shape (spike required)

**Research date:** 2026-03-23
**Valid until:** 2026-04-22 (stable API — 30-day validity; spike output may change the score_dimensions schema)
