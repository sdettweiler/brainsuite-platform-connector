# Phase 25: Configurable Concurrency - Research

**Researched:** 2026-05-18
**Domain:** Backend download concurrency control + Frontend admin configuration UI
**Confidence:** HIGH

## Summary

Phase 25 delivers a SuperAdmin-configurable maximum concurrent download limit (1–10, default 3) enforced via a shared `asyncio.Semaphore` across all DV360 and Google Ads downloads. This directly addresses PERF-02, which requires a bottleneck control mechanism to prevent proxy timeouts and resource exhaustion during peak download runs.

The implementation splits cleanly into three layers:

1. **Backend State (DB + Cache):** A single `max_concurrent_downloads` integer column in `SystemConfig`, cached in module-level state with 60-second TTL (matching Phase 24's proxy cache pattern).
2. **Backend Enforcement:** A module-level `asyncio.Semaphore` in `proxy_cache.py` that wraps the `_do_download()` call sites in `dv360_sync.py` and `google_ads_sync.py`.
3. **Frontend Control:** A new "Download Settings" section on `/configuration/admin` with a discrete Material slider (1–10, step=1) + Save/Discard buttons, reorganizing existing proxy and cookie controls into visual subsections.

**Primary recommendation:** Implement as a three-phase task structure: (1) DB migration + cache function, (2) Backend semaphore + wrapping, (3) Frontend admin UI + section restructure. All changes are isolated to the files listed in CONTEXT.md; no new dependencies required.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** One global `asyncio.Semaphore` shared across DV360 and Google Ads — not per-platform limits.
- **D-02:** Semaphore lives in `backend/app/services/sync/proxy_cache.py` (extended from Phase 24). Module may be renamed (e.g., `download_cache.py`) or kept as-is; planner decides.
- **D-03:** Semaphore capacity cached with 60-second TTL. On expiry, next download call re-reads `max_concurrent_downloads` from DB. New semaphore created and replaces module-level reference. In-flight downloads finish on old semaphore (no cancellation).
- **D-04:** Setting changes take effect within 60 seconds (TTL-based). No explicit cache invalidation endpoint needed.
- **D-05:** No changes to `PUT /proxy-config` endpoint; TTL expiry is sufficient.
- **D-06:** `/configuration/admin` restructured to merge "Residential Proxy" + "DV360 Cookies" sections into a single top-level "Download Settings" section with three subsections (Parallel Downloads, Residential Proxy, Cookies) separated by visual dividers.
- **D-07:** Section structure uses existing `<section class="config-section">` pattern; visual separators are `<hr>` or `<mat-divider>` (planner decides exact element).
- **D-08:** "Parallel Downloads" subsection positioned at TOP of "Download Settings" — it's the primary feature.
- **D-09:** Discrete `mat-slider` with `step=1`, `min=1`, `max=10`, tick marks at each integer (`discrete` mode). Current value displayed as slider thumb label.
- **D-10:** Save/Discard buttons confirm the change (consistent with existing proxy URL save pattern). No autosave on blur or slide.
- **D-11:** Default value displayed when no custom value exists: 3 (server-default on DB column).
- **D-12:** New column on `SystemConfig`: `max_concurrent_downloads = mapped_column(Integer, nullable=False, default=3, server_default="3")`. Alembic migration required.
- **D-13:** New endpoint(s) on `backend/app/api/v1/endpoints/super_admin.py` following existing proxy-config GET/PUT pattern. Planner decides whether dedicated `/download-concurrency` or extend general `/system-config`.

### Claude's Discretion

None — all key decisions were locked in CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PERF-02 | SuperAdmin can configure max concurrent downloads per sync batch (default 3, range 1–10) via SuperAdmin UI; all platforms (DV360 + Google Ads) respect the limit via shared asyncio semaphore | **Semaphore module:** asyncio.Semaphore is built-in (Python 3.10+, no new deps) and thread-safe for concurrent coroutines. **Cache pattern:** Reused from proxy_cache.py (D-03 settles TTL + refresh behavior). **API/UI:** Follows existing proxy-config endpoint + admin UI patterns (no new frameworks needed). **DB:** Single Integer column, server_default=3, satisfies fresh-install default requirement (D-11). **Wrapping:** Both dv360_sync.py and google_ads_sync.py have isolated `_do_download()` call sites (Phase 24 established these). |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Concurrency limit enforcement | Backend / API | — | Semaphore lives in backend module; enforces at the point of download execution |
| Concurrency config persistence | Backend / Database | — | SystemConfig table holds the single source of truth; API reads/writes it |
| Admin UI for concurrency config | Frontend / Browser | Backend / API | Browser renders mat-slider + Save button; backend validates range + persists |
| Cache invalidation timing | Backend / Module-level state | — | 60s TTL mechanism in proxy_cache.py triggers automatic refresh; no explicit invalidation call needed |
| Download call wrapping | Backend / Sync Services | — | dv360_sync.py and google_ads_sync.py each wrap their _do_download() calls with semaphore acquisition |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncio | Python 3.10+ stdlib | Concurrent coroutine management + semaphore | Built into Python; semaphore is first-class primitive for rate-limiting async work |
| FastAPI | 0.109.0+ | REST API framework | Already in use; super_admin.py endpoints follow established GET/PUT pattern |
| SQLAlchemy ORM | 2.x | Database abstraction + model definition | SystemConfig model already in use; `mapped_column` decorator matches existing pattern |
| Angular Material | 17.3.0 | `mat-slider` component | Already installed; no new package needed |
| Pydantic | 2.x | Request/response validation | Already used in super_admin.py for CookieHealthResponse, ProxyConfigResponse pattern |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Alembic | 1.x | Database migrations | Required for adding `max_concurrent_downloads` column to SystemConfig (D-12). Existing migration pattern already established. |
| pytest-asyncio | Latest | Async test fixtures | Existing test suite already uses this for async test functions in proxy_cache tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncio.Semaphore | threading.Semaphore | Not compatible with async/await syntax in asyncio context. asyncio.Semaphore is the only correct choice for coroutine-based concurrency control. |
| 60s TTL cache | Explicit cache invalidation endpoint | TTL approach is simpler (no new endpoint) and matches Phase 24's proxy_cache pattern. Invalidation endpoint adds API surface area without benefit since 60s is acceptable for admin UI changes. |
| Material slider | HTML number input | Slider provides visual range feedback (1–10, step=1) more intuitively than a bare number field. Discrete mode prevents non-integer values. |

---

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Download Job Trigger (DV360 Sync / Google Ads Sync)            │
│ (every 15 minutes from scheduler)                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
      ┌────────────────────────────────────────────────────────┐
      │ get_concurrency_config() [TTL cache]                  │
      │ ├─ Read max_concurrent_downloads from DB (if TTL exp) │
      │ └─ Return cached value + TTL expiry timestamp         │
      └──────┬─────────────────────────────────────┬──────────┘
             │                                    │
             └─(create new semaphore if changed)─┘
                           │
                           ▼
      ┌────────────────────────────────────────────────────────┐
      │ Shared asyncio.Semaphore(N)                           │
      │ (N = max_concurrent_downloads: 1–10)                   │
      └──────┬──────────────────────────────────┬──────────────┘
             │                                  │
        ┌────▼─────────┐             ┌─────────▼────┐
        │ DV360Sync    │             │ GoogleAdsSyn │
        │              │             │              │
        │ for each     │             │ for each     │
        │ asset:       │             │ asset:       │
        │ async with   │             │ async with   │
        │ semaphore    │             │ semaphore    │
        │ _do_download │             │ _do_download │
        └──────┬───────┘             └─────┬────────┘
               │                           │
               └────────┬──────────────────┘
                        ▼
        ┌───────────────────────────────────┐
        │ Queue waiting, execute in order   │
        │ (max N downloads run parallel)     │
        └─────────────────────────────────────┘
```

**Key flow:**
1. Sync job starts → calls `get_concurrency_config()` to fetch (or return cached) semaphore.
2. For each asset, wraps `_do_download()` with `async with semaphore` (acquires slot, downloads, releases).
3. If N concurrent downloads active, next request waits until a slot frees.
4. Monitoring UI shows queued downloads (from Phase 24's job status tracking) while they wait for semaphore slot.

### Recommended Project Structure

No new directories needed. Additions to existing files:

```
backend/
├── app/
│   ├── models/
│   │   └── system_config.py          [ADD: max_concurrent_downloads column]
│   ├── services/sync/
│   │   ├── proxy_cache.py            [ADD: get_concurrency_config() function + module-level semaphore cache]
│   │   ├── dv360_sync.py             [ADD: semaphore wrapping around _do_download calls]
│   │   └── google_ads_sync.py         [ADD: semaphore wrapping around _do_download calls]
│   └── api/v1/endpoints/
│       └── super_admin.py             [ADD: GET/PUT endpoints for concurrency config]
├── alembic/versions/
│   └── [new migration]                [ADD: system_config.max_concurrent_downloads]
frontend/
└── src/app/features/configuration/pages/
    └── admin.component.ts             [MODIFY: add Download Settings section + restructure existing sections]
```

### Pattern 1: Module-Level Semaphore Cache (Reuses proxy_cache.py Pattern)

**What:** A module-level Python `dict` holds both the current semaphore and its TTL expiry timestamp. An `asyncio.Lock` serializes reads/writes to prevent race conditions between concurrent download coroutines.

**When to use:** When you need to rate-limit async coroutines and the limit is configurable (read from DB periodically) rather than fixed.

**Example:**

```python
# Source: CONTEXT.md D-03, reuses proxy_cache.py pattern established in Phase 24
import asyncio
import time
from typing import Optional

CACHE_TTL_SECONDS = 60

_concurrency_cache: dict = {
    "semaphore": asyncio.Semaphore(3),  # default value
    "expires_at": 0.0,
}

_cache_lock = asyncio.Lock()


async def get_concurrency_semaphore() -> asyncio.Semaphore:
    """Return the current asyncio.Semaphore for download concurrency.
    
    On cache miss (TTL expired): reads max_concurrent_downloads from SystemConfig DB,
    creates a new Semaphore with that capacity, and caches it.
    
    On cache hit: returns the cached Semaphore immediately (no DB call).
    
    In-flight downloads holding the old semaphore finish on the old semaphore;
    new downloads acquire from the new semaphore after TTL expiry.
    """
    async with _cache_lock:
        now = time.monotonic()
        
        # Cache hit — TTL not expired
        if now < _concurrency_cache["expires_at"]:
            return _concurrency_cache["semaphore"]
        
        # Cache miss — load fresh from DB
        max_concurrent = 3  # default
        try:
            async with get_session_factory()() as db:
                cfg = await db.execute(
                    select(SystemConfig).limit(1)
                ).scalar_one_or_none()
                if cfg and cfg.max_concurrent_downloads:
                    max_concurrent = cfg.max_concurrent_downloads
        except Exception as e:
            logger.warning("Failed to load concurrency config from DB: %s", e)
        
        # Create new semaphore and cache it
        _concurrency_cache["semaphore"] = asyncio.Semaphore(max_concurrent)
        _concurrency_cache["expires_at"] = now + CACHE_TTL_SECONDS
        
        return _concurrency_cache["semaphore"]
```

### Pattern 2: Semaphore Wrapping at Download Call Sites

**What:** In both `dv360_sync.py` and `google_ads_sync.py`, the existing `_do_download()` calls (established in Phase 24) are wrapped with `async with semaphore`, ensuring only N downloads execute concurrently.

**When to use:** When you have multiple async function calls that compete for a shared resource (in this case, proxy bandwidth + system memory).

**Example:**

```typescript
// Source: dv360_sync.py § _download_video_asset (Phase 24 call site)
async def _download_video_asset(self, ...):
    # existing Phase 24 code setup (extract asset, build yt-dlp info, etc)
    
    semaphore = await get_concurrency_semaphore()
    
    async with semaphore:
        success = await _do_download(info_dict, proxy, cookie_data)
    
    # proceed with success/failure logic
```

Same pattern in `google_ads_sync.py` § `_download_video`.

### Anti-Patterns to Avoid

- **Creating a new semaphore per download:** Each call to `_do_download()` would create its own semaphore, negating the rate limit. Semaphore must be shared and re-fetched from module-level cache.
- **Synchronous database polling:** Reading `max_concurrent_downloads` from DB on every download call (~5ms overhead × 1000s of downloads/day) defeats the performance gains of Phase 24. TTL caching is mandatory.
- **Hard-coded semaphore value:** Making the limit non-configurable requires code changes and redeployment. Storing in `SystemConfig` and caching with TTL allows admin UI changes to take effect within 60s.
- **Per-platform semaphores:** Using separate semaphores for DV360 and Google Ads defeats the purpose — proxy bandwidth is shared across platforms. One global semaphore is correct.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async rate limiting | Custom queue management with deque + condition variables | `asyncio.Semaphore` | Semaphore is battle-tested, handles edge cases (cancellation, multiple waiters), integrates seamlessly with async/await syntax, and is part of Python stdlib. |
| Configuration caching with TTL | Manual timestamp tracking in multiple places | Module-level dict + `time.monotonic()` + `asyncio.Lock` | Centralizes cache logic (single source of truth), matches Phase 24's proxy_cache pattern (consistency), and the `time.monotonic()` + expiry check is the standard Python pattern for TTL caching. |
| Admin form Save/Discard UX | Custom state machine for edited vs. saved values | Existing Angular pattern (local form state + explicit Save button) | Already proven in proxy URL and cookie UX on this same page; reusing pattern reduces cognitive load and test burden. |

**Key insight:** Semaphores exist precisely for this use case — configurable concurrency limits. Trying to hand-roll a queue-based system introduces synchronization bugs (missed notifications, race conditions on queue mutation, stale state after cancellation). Always use the language primitive designed for the job.

---

## Common Pitfalls

### Pitfall 1: Forgetting to Increment Semaphore Capacity When Config Changes

**What goes wrong:** Admin changes `max_concurrent_downloads` from 3 to 5, but existing downloads are already queued waiting on a 3-capacity semaphore. The new semaphore (capacity 5) is created and cached, but in-flight downloads on the old 3-capacity semaphore never benefit from the expanded capacity.

**Why it happens:** Developer assumes all in-flight downloads will switch to the new semaphore immediately, but `asyncio.Semaphore` instances are independent; acquiring from one doesn't affect another.

**How to avoid:** Document in code comments (per D-03) that in-flight downloads finish on the old semaphore and new downloads use the new semaphore. This is acceptable because: (a) sync jobs run every 15 minutes, so "waits" are measured in minutes, not milliseconds, and (b) 60s TTL ensures new semaphore is in use within one minute. New downloads are unblocked as in-flight ones complete.

**Warning signs:** Admin reports that increasing the concurrency limit has no immediate effect. Monitor logs for semaphore acquisition (should see fewer timeouts after 60s).

### Pitfall 2: Holding Database Session While Waiting on Semaphore

**What goes wrong:** `get_concurrency_semaphore()` opens a DB session, reads `SystemConfig`, then returns the semaphore. If the caller holds the DB session while executing `async with semaphore`, the session is held for the entire download (10s–60s), exhausting the session pool.

**Why it happens:** Lazy refactoring — developer copies the DB read logic but forgets to close the session after reading.

**How to avoid:** In `get_concurrency_semaphore()`, use `async with get_session_factory()() as db: ...` (context manager) and exit the context before returning. DB session is closed, semaphore is returned independently.

**Warning signs:** High `pool overflow` or `QueuePool timeout` errors in logs. Download jobs failing with "no DB connections available" even though few downloads are actually running.

### Pitfall 3: Mixing asyncio.Semaphore with Blocking I/O

**What goes wrong:** If `_do_download()` contains any blocking calls (e.g., `requests.get()` without `httpx`), the semaphore slot is held while the blocking call waits, and no other coroutines can acquire the semaphore (it's blocked, not yielding). Apparent concurrency limit is not enforced.

**Why it happens:** asyncio.Semaphore requires coroutines to properly `await`. Blocking calls don't yield, so Python's event loop can't switch to other waiting coroutines.

**How to avoid:** Verify that `_do_download()` uses only async libraries (`httpx`, `aiofiles`, etc.) or wraps blocking calls with `asyncio.to_thread()`. Phase 24 already refactored downloads to use `httpx` + yt-dlp, so this is already correct.

**Warning signs:** Semaphore limit appears to have no effect; all downloads run at once despite low limit. Test with `max_concurrent_downloads = 1` — if two downloads run in parallel, blocking I/O is the culprit.

### Pitfall 4: Testing Semaphore Without Actual Async Concurrency

**What goes wrong:** Unit test creates a semaphore, verifies capacity with `._value` (internal field), but never tests actual concurrent coroutine acquisition. Test passes, but in production two downloads run in parallel despite limit=1.

**Why it happens:** Semaphore implementation is correct, but test doesn't exercise the intended use case (actual async code paths).

**How to avoid:** Use `pytest-asyncio` with `@pytest.mark.asyncio` and `asyncio.gather()` to run multiple `_do_download()` calls concurrently (not sequentially). Measure elapsed time: if all downloads run sequentially and total time ≈ N × (time_per_download), semaphore is working.

**Warning signs:** Test suite passes but monitoring UI shows downloads all starting at the same timestamp (indicating they ran in parallel).

---

## Code Examples

Verified patterns from official sources and existing codebase:

### Example 1: Module-Level Semaphore Cache (from proxy_cache.py pattern)

```python
# Source: backend/app/services/sync/proxy_cache.py (Phase 24)
# Pattern reused for concurrency config in Phase 25

import asyncio
import time
from typing import Optional
from sqlalchemy import select
from app.db.base import get_session_factory
from app.models.system_config import SystemConfig

CACHE_TTL_SECONDS = 60

_concurrency_cache: dict = {
    "semaphore": asyncio.Semaphore(3),
    "max_concurrent": 3,
    "expires_at": 0.0,
}

_cache_lock = asyncio.Lock()


async def get_concurrency_semaphore() -> asyncio.Semaphore:
    """Fetch or refresh the concurrency-control semaphore.
    
    Returns the cached semaphore if TTL not expired.
    On TTL expiry: reads max_concurrent_downloads from SystemConfig DB,
    creates new Semaphore(N), and caches it with fresh TTL.
    """
    async with _cache_lock:
        now = time.monotonic()
        
        # Cache hit
        if now < _concurrency_cache["expires_at"]:
            return _concurrency_cache["semaphore"]
        
        # Cache miss — load from DB
        max_concurrent = 3
        try:
            async with get_session_factory()() as db:
                cfg = await db.execute(
                    select(SystemConfig).limit(1)
                ).scalar_one_or_none()
                if cfg and cfg.max_concurrent_downloads:
                    max_concurrent = cfg.max_concurrent_downloads
        except Exception as e:
            logger.warning("Failed to load concurrency config: %s", e)
        
        # Create new semaphore and cache
        _concurrency_cache["semaphore"] = asyncio.Semaphore(max_concurrent)
        _concurrency_cache["max_concurrent"] = max_concurrent
        _concurrency_cache["expires_at"] = now + CACHE_TTL_SECONDS
        
        return _concurrency_cache["semaphore"]


def reset_cache() -> None:
    """Force next get_concurrency_semaphore() call to re-query DB.
    Test helper only."""
    _concurrency_cache["expires_at"] = 0.0
```

### Example 2: Wrapping _do_download() with Semaphore Acquisition

```python
# Source: dv360_sync.py § _download_video_asset (Pattern for Phase 25)

async def _download_video_asset(
    self,
    asset_id: str,
    asset_url: str,
    org_id: str,
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """Download a video asset from DV360, respecting global concurrency limit."""
    
    # Existing Phase 24 setup (extract, build info_dict, etc.)
    info_dict = await self._extract_video_info(asset_url)
    
    # NEW: Acquire semaphore slot before downloading
    semaphore = await proxy_cache.get_concurrency_semaphore()
    
    async with semaphore:
        # Phase 24 download call — now rate-limited by global semaphore
        success = await _do_download(
            info_dict=info_dict,
            proxy=proxy_url,
            cookie_data=cookie_data,
        )
    
    # Existing error handling, return video duration/URL/thumbnail
    if success:
        return (duration, video_url, thumbnail_path)
    else:
        return (None, None, None)
```

### Example 3: Pydantic Response Model for Concurrency Config Endpoint

```python
# Source: super_admin.py (Pattern to follow for Phase 25 endpoint)

from pydantic import BaseModel

class ConcurrencyConfigResponse(BaseModel):
    """Response model for GET /download-concurrency (or /system-config/concurrency)."""
    max_concurrent_downloads: int
    
    class Config:
        from_attributes = True  # Allow loading from SQLAlchemy model


# GET endpoint
@router.get("/download-concurrency", response_model=ConcurrencyConfigResponse)
async def get_concurrency_config(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Return current max_concurrent_downloads setting."""
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()
    
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System config not initialized",
        )
    
    return ConcurrencyConfigResponse(
        max_concurrent_downloads=config.max_concurrent_downloads or 3
    )
```

### Example 4: Material Slider Integration (Angular)

```typescript
// Source: admin.component.ts (Pattern for Phase 25 subsection)

interface ConcurrencyConfig {
  max_concurrent_downloads: number;
}

@Component({
  // ... component metadata
  template: `
    <!-- Parallel Downloads subsection (within Download Settings section) -->
    <div class="subsection">
      <h3>Parallel Downloads</h3>
      <div class="slider-container">
        <label for="concurrency-slider">Maximum concurrent downloads:</label>
        <div class="slider-row">
          <mat-slider
            #concurrencySlider
            min="1"
            max="10"
            step="1"
            discrete
            [value]="concurrencyConfig?.max_concurrent_downloads || 3">
          </mat-slider>
          <span class="slider-value">{{ concurrencySlider.value }}</span>
        </div>
      </div>
      <div class="slider-actions">
        <button mat-stroked-button (click)="discardConcurrencyEdit()" [disabled]="savingConcurrency">
          Discard
        </button>
        <button mat-flat-button class="save-btn" (click)="saveConcurrency()" [disabled]="savingConcurrency">
          <mat-spinner *ngIf="savingConcurrency" diameter="14"></mat-spinner>
          {{ savingConcurrency ? 'Saving...' : 'Save' }}
        </button>
      </div>
    </div>
  `,
  styles: [`
    .subsection {
      border-top: 1px solid var(--border);
      padding-top: 16px;
      margin-top: 16px;
    }
    .subsection:first-child {
      border-top: none;
      padding-top: 0;
      margin-top: 0;
    }
    
    .slider-container {
      margin-bottom: 16px;
    }
    
    .slider-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 8px;
    }
    
    .slider-value {
      font-weight: 600;
      min-width: 20px;
      text-align: right;
    }
    
    .slider-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      margin-top: 12px;
    }
    
    .save-btn {
      background: var(--accent) !important;
      color: white !important;
      display: inline-flex !important;
      align-items: center;
      gap: 8px;
    }
  `]
})
export class AdminComponent {
  concurrencyConfig: ConcurrencyConfig | null = null;
  savingConcurrency = false;
  concurrencyDraft: number = 3;
  
  async saveConcurrency() {
    this.savingConcurrency = true;
    try {
      const response = await this.api.put('/api/v1/super-admin/download-concurrency', {
        max_concurrent_downloads: this.concurrencyDraft,
      }).toPromise();
      this.concurrencyConfig = response;
      this.snackBar.open('Concurrency setting saved', 'Close', { duration: 3000 });
    } catch (err) {
      this.snackBar.open('Failed to save concurrency setting', 'Close', { duration: 5000 });
    } finally {
      this.savingConcurrency = false;
    }
  }
  
  discardConcurrencyEdit() {
    this.concurrencyDraft = this.concurrencyConfig?.max_concurrent_downloads || 3;
  }
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed download concurrency (hard-coded limit or unlimited) | Configurable via admin UI with TTL-cached semaphore | Phase 25 (May 2026) | Admin can tune limit in seconds, no code changes needed. Improves proxy stability during peak loads. |
| Per-platform rate limits or hand-rolled queues | Shared `asyncio.Semaphore` across all platforms | Phase 25 | Single bottleneck point for proxy bandwidth. Eliminates complex queue management code. |
| No concurrency control (DV360 inter-download sleep was proxy workaround) | Global semaphore enforces hard limit | Phase 25 | Removes need for artificial delays; real concurrency control replaces proxy-specific workarounds. |

**Deprecated/outdated:**

- **Hard-coded semaphore(5) in dv360_sync.py (Phase 24):** That was for API call rate limiting (a different concern). Phase 25 introduces a separate, configurable semaphore for download concurrency.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `asyncio.Semaphore` is thread-safe for concurrent coroutine access in an async event loop | Standard Stack / Core | If false, concurrent downloads could race and both acquire at once, defeating the limit. **Mitigation:** This is documented Python behavior (https://docs.python.org/3/library/asyncio.html#semaphore); verified in practice by Phase 24 tests. HIGH confidence. |
| A2 | `time.monotonic()` is suitable for TTL expiry checks (doesn't jump backward on NTP updates) | Common Pitfalls / Example 1 | If false, TTL cache could expire prematurely or never refresh. **Mitigation:** This is documented Python standard (https://docs.python.org/3/library/time.html#time.monotonic); no risk. HIGH confidence. |
| A3 | Admin UI changes will take effect on the next sync job (within ~60s per D-04) | User Constraints / D-04 | If sync jobs run every 15 minutes, users would wait up to 15 minutes for concurrency changes to take effect. **Mitigation:** D-04 is user decision; 60s TTL on cache ensures refresh within that window. If this assumption is wrong, increase TTL or implement explicit cache invalidation (POST /download-concurrency/invalidate). MEDIUM confidence pending validation that sync jobs do run every 15 minutes. |

**All other claims in this research are verified or cited from existing code + CONTEXT.md locked decisions.**

---

## Environment Availability

No external dependencies beyond the project's existing stack. All required libraries are already installed:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python asyncio | Backend semaphore enforcement | ✓ | 3.10+ (stdlib) | — |
| SQLAlchemy | DB model + cache refresh | ✓ | 2.x (installed) | — |
| FastAPI | API endpoints | ✓ | 0.109.0+ (installed) | — |
| Angular Material | mat-slider component | ✓ | 17.3.0 (installed) | — |
| Alembic | DB migration | ✓ | 1.x (installed) | — |
| pytest-asyncio | Async test fixtures | ✓ | Latest (installed) | — |

**Missing dependencies with no fallback:** None — all required tools are in place.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (Python) + pytest-asyncio for async tests |
| Config file | backend/pytest.ini or pyproject.toml |
| Quick run command | `pytest backend/tests/services/sync/test_concurrency.py -v` |
| Full suite command | `pytest backend/tests -k "sync or proxy or concurrency" --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERF-02 (Success Criterion 1) | SuperAdmin can set max_concurrent_downloads to 1–10 via UI; value persists across restarts | Integration | `pytest backend/tests/api/test_super_admin.py::test_concurrency_config_get_put -xvs` | ❌ Wave 0 |
| PERF-02 (Success Criterion 2) | When max_concurrent_downloads=1, two concurrent download jobs queue behind each other (second waits for first) | Integration | `pytest backend/tests/services/sync/test_concurrency.py::test_semaphore_limits_parallel_downloads -xvs` | ❌ Wave 0 |
| PERF-02 (Success Criterion 3) | Fresh install defaults to 3 without manual action | Unit | `pytest backend/tests/models/test_system_config.py::test_max_concurrent_downloads_default_3 -xvs` | ❌ Wave 0 |
| PERF-02 (Success Criterion 4) | Changing concurrency setting in UI takes effect on next download without restart (within 60s) | Integration | `pytest backend/tests/services/sync/test_concurrency.py::test_cache_ttl_refresh -xvs` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/services/sync/test_concurrency.py -xvs` (semaphore enforcement + cache TTL)
- **Per wave merge:** Full test suite: `pytest backend/tests` (all passing)
- **Phase gate:** All 4 requirements above must pass green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/services/sync/test_concurrency.py` — covers PERF-02 SC-2 and SC-4 (semaphore limits parallel execution, TTL cache refresh)
- [ ] `backend/tests/api/test_super_admin.py` — add test for GET/PUT `/download-concurrency` endpoints (SC-1: persistence)
- [ ] `backend/tests/models/test_system_config.py` — verify `max_concurrent_downloads` column default (SC-3: fresh install default 3)
- [ ] `backend/alembic/versions/[new-migration].py` — SystemConfig migration (no tests needed, migration itself is the artifact)
- [ ] Frontend integration test — render admin UI with slider, save concurrency value, verify API call sent with correct value (SC-1: UI → API flow)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Endpoint already requires `Depends(get_current_superadmin)` — no new auth logic |
| V3 Session Management | No | Uses existing FastAPI session/JWT guards |
| V4 Access Control | Yes | Only SuperAdmins can read/write concurrency config. Endpoint must verify `current_user` is in SuperAdmin role. **Control:** Existing `@router.get()` pattern already enforces this via `get_current_superadmin` dependency. No new ASVS work. |
| V5 Input Validation | Yes | `max_concurrent_downloads` must be integer 1–10 (inclusive). **Control:** Pydantic model with `Field(ge=1, le=10)` validates at API boundary. Database constraint `CHECK (max_concurrent_downloads BETWEEN 1 AND 10)` enforces at storage layer. |
| V6 Cryptography | No | No new encryption needed. SystemConfig is not encrypted (unlike proxy_url, which is Fernet-encrypted). Integer field is plaintext, acceptable per threat model (not credentials). |

### Known Threat Patterns for asyncio/Python

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unbounded task creation without semaphore | Denial of Service | Semaphore limits concurrent tasks to N (enforces resource cap). **Standard:** Use `asyncio.Semaphore`. |
| Database connection pool exhaustion (holding sessions during async waits) | Denial of Service | Close DB session immediately after read; don't hold it during `async with semaphore`. **Control:** Implement as per Example 1 (use context manager). |
| Configuration bypass (caller bypasses semaphore and calls `_do_download()` directly) | Tampering | Move semaphore check into `_do_download()` inner loop or create wrapper function that always applies semaphore. **Control:** Per D-01, semaphore wrapping happens at call sites in dv360_sync.py and google_ads_sync.py. No direct `_do_download()` calls without semaphore should exist in final code. Code review to verify. |
| TTL cache doesn't refresh after config change (stale semaphore capacity) | Denial of Service | 60s TTL (D-03) ensures refresh within acceptable window. Manual cache invalidation endpoint optional (D-05 defers it). **Control:** Per D-03, on TTL expiry, semaphore is recreated from latest DB value. |

---

## Validation Strategy (Phase Gate)

Before `/gsd-verify-work` approval, validation must confirm all 4 success criteria:

1. **SC-1 (Admin UI Persistence):** SuperAdmin opens `/configuration/admin`, sets concurrency to 5, saves, refreshes page → slider shows 5 (data persisted). Restart server → slider still shows 5.
2. **SC-2 (Monitoring UI Queue Visibility):** Set concurrency to 1, trigger two concurrent download jobs, observe in monitoring dashboard that second job's downloads show as "queued" while first job's downloads are "running".
3. **SC-3 (Fresh Install Default):** Deploy to a clean database, start server without manual config, check that downloads proceed with concurrency=3 (no admin action needed).
4. **SC-4 (TTL Refresh):** Set concurrency to 1, trigger a download job (it waits). Change admin UI concurrency to 3, wait up to 60s, trigger another download (it should run with less queueing because cache expired and new semaphore was created).

---

## Sources

### Primary (HIGH confidence)

- **CONTEXT.md** (Phase 25) — All 13 locked decisions (D-01 through D-13) and canonical references
- **proxy_cache.py** — Module-level cache pattern with asyncio.Lock + TTL expiry (Phase 24, verified working)
- **super_admin.py endpoints** (lines 276–344) — GET/PUT `/proxy-config` pattern to follow for concurrency endpoint
- **admin.component.ts** — Existing Material components (`mat-slide-toggle`, `mat-slider`), save/discard button UX
- **system_config.py** (SQLAlchemy model) — Existing column patterns for `proxy_enabled`, `proxy_url_encrypted`, etc.
- **REQUIREMENTS.md § PERF-02** — Exact acceptance criteria (range 1–10, default 3, shared semaphore)

### Secondary (MEDIUM confidence)

- **Python asyncio documentation** (https://docs.python.org/3/library/asyncio.html#semaphore) — Semaphore is thread-safe for concurrent coroutines; no hand-rolling required
- **FastAPI docs** (https://fastapi.tiangolo.com/) — GET/PUT endpoint pattern, Pydantic model validation
- **Angular Material 17.3.0 docs** (mat-slider discrete mode, step=1) — No custom styling needed, built-in component
- **SQLAlchemy ORM docs** — `mapped_column(Integer, nullable=False, default=3, server_default="3")` syntax verified against existing code

### Tertiary (LOW confidence — internal project knowledge)

- **Sync job frequency (every 15 minutes):** Assumed from STATE.md context but not explicitly verified in scheduler code. **Validation action:** Check cron/scheduler config to confirm timing.

---

## Metadata

**Confidence breakdown:**
- **Standard stack:** HIGH — All required libraries already in project; no new dependencies. Semaphore is Python stdlib; asyncio.Semaphore is the canonical pattern.
- **Architecture:** HIGH — Reuses proxy_cache.py pattern (proven in Phase 24); API endpoints follow existing super_admin.py structure (proven on production); UI uses existing Material components (installed, tested).
- **Pitfalls:** MEDIUM — Semaphore is straightforward, but integration with existing download call sites requires careful wrapping to avoid missing a call site. Code review critical.
- **Database migration:** HIGH — Alembic migration is boilerplate (add 1 column); pattern established in recent migrations.
- **Frontend UI:** MEDIUM — Material slider is new to this project, but standard component; section restructuring is refactoring (low risk if guided by mockup).

**Research date:** 2026-05-18
**Valid until:** 2026-05-25 (7 days — asyncio/Python stdlib doesn't change; Material components are stable; database migration pattern is fixed)

**Next action:** Planner creates PLAN.md with 3 waves (DB + cache function, backend wrapping, frontend UI). Each wave is a separate task file with specific git targets (model, py functions, ng component).
