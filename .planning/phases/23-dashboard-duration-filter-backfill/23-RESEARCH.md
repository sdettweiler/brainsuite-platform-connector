# Phase 23: Dashboard Duration Filter + Backfill - Research

**Researched:** 2026-05-18
**Domain:** Full-stack filter implementation + async backfill job
**Confidence:** HIGH

## Summary

Phase 23 adds a dual-handle duration range slider to the dashboard and an async backfill job to populate missing video_duration values. The phase builds directly on Phase 22's filter infrastructure (metadata filter pattern, org-scoped queries, AND composition).

**Key findings:**
1. **Phase 22 Complete:** All backend endpoints and frontend filter UI fully implemented; composite index created
2. **Score slider pattern exists:** Dashboard already has a dual-handle ngx-slider (scoreMin/scoreMax) — duration slider reuses exact pattern
3. **Duration data field exists:** CreativeAsset.video_duration already mapped; response includes it
4. **ffprobe utility ready:** _get_video_duration() in dv360_sync.py line 1423 uses ffprobe to extract duration from temporary downloaded files
5. **Backfill job pattern established:** BackgroundJob model and job_tracker helpers ready; job lifecycle proven in Phase 17–19
6. **Object storage integration required:** Videos uploaded to MinIO/S3 after download; backfill must handle fetching files from object storage for duration extraction

**Primary recommendation:** Implement as two independent plans — backend (filter param + bounds endpoint + backfill job wiring) and frontend (slider UI + dynamic bounds + NULL callout).

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

| ID | Decision | Constraint |
|------|----------|-----------|
| D-01 | Slider bounds **dynamic** via GET /dashboard/duration-bounds | No hardcoded ceiling; endpoint returns min/max from actual data |
| D-02 | Bounds **filter-aware** — recompute when other filters change | Bounds call excludes metadata/account/date filters (D-02 note: does NOT refire when slider moves) |
| D-03 | Slider labels **formatted** — `formatDuration(seconds)` converts to "Xm Ys" | 15 seconds → "15s", 135 seconds → "2m 15s" |
| D-04 | Slider **hidden when no VIDEO assets** in current grid | No disabled state; clean filter bar for image-only orgs |
| D-05 | `hasVideoAssets` derived from response — true if any asset.asset_type === 'video' | Computed in loadData() response handler |
| D-06 | NULL callout **only when filter active** (durationMin or durationMax adjusted from full range) | Not shown by default; avoids noise |
| D-07 | NULL count = VIDEO assets matching OTHER active filters but excluded because video_duration IS NULL | Returned as `null_duration_count` field in /dashboard/assets response; dynamic per filter state |
| D-08 | Callout renders **below chip row**, inline near filter | Small info text; not a prominent banner |
| D-09 | Backfill **triggered after each sync run** | End of DV360, Google Ads, TikTok, Meta sync; uses BackgroundJob pattern |
| D-10 | Backfill targets **all platforms where video file is local** | asset_type = 'video' AND video_duration IS NULL AND local_file_path IS NOT NULL |
| D-11 | **Batch of 100, sequential** within each run | ffprobe is CPU-bound; sequential avoids spikes |

### Claude's Discretion

No discretionary areas — all implementation details are locked.

### Deferred Ideas (OUT OF SCOPE)

- Filter state URL persistence (v1.5 candidate)
- Saved filter presets (v1.5 candidate)
- Duration histogram overlay on slider (nice-to-have)

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-03 | A user can filter the creative grid by video duration range using a dual-handle slider; legacy assets with NULL duration are excluded and a count callout is shown | Dual-handle ngx-slider (existing pattern); dynamic bounds endpoint; org-scoped query with AND composition; async backfill job populates gaps |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Duration slider state management | Browser / Client | — | Local state (durationMin/durationMax); calls onFilterChange() to trigger re-query |
| Duration bounds data fetch | API / Backend | — | Requires org-scoped database MIN/MAX query; filter-aware scoping |
| Bounds refresh trigger | Browser / Client | — | onFilterChange() calls loadDurationBounds() after loading assets |
| Dynamic ceiling/floor updates | Browser / Client | — | Update sliderOptions.ceil/floor from API response; updateSlider() |
| Duration filter composition & AND logic | API / Backend | — | Backend applies duration BETWEEN clause with other filters via WHERE |
| NULL duration callout count | API / Backend | — | Response field computed only when duration filter active |
| Async backfill job execution | Background Job Service | Database | Job creation in sync finish hooks; job_tracker handlers; ffprobe duration extraction |

---

## Standard Stack

### Core Framework Stack (No New Packages)

| Library | Version | Purpose | Already in Place? |
|---------|---------|---------|-------------------|
| **Angular** | 17.3.0 | Frontend framework | ✓ |
| **@angular-slider/ngx-slider** | 2.0.0+ | Dual-handle range slider | ✓ Imported in dashboard.component.ts line 18 |
| **FastAPI** | 0.115.0 | Backend REST API | ✓ |
| **SQLAlchemy** | 2.0.23 | ORM with async support | ✓ |
| **PostgreSQL** | 15.4+ | Primary database | ✓ |
| **ffprobe** | system-provided | Extract video duration | ✓ Available (used in dv360_sync.py line 1423) |

### Installation Note

**No npm install needed.** NgxSliderModule already imported in dashboard.component.ts. All Angular Material modules already available.

### Backend Dependencies Verification

```bash
ffprobe --version                # System utility; should return version
python -c "import ffprobe; print('ffprobe available')"  # For subprocess calls
```

---

## Architecture Patterns

### System Architecture Diagram

```
User (Browser)
    ↓
[Dashboard Component — Duration Filter Row]
    ├─ Slider visibility gate: hasVideoAssets = response.items.some(a => a.asset_type === 'video')
    │
    ├─ Step 1: Load duration bounds (when OTHER filters change)
    │   └─ GET /dashboard/duration-bounds?date_from=X&date_to=Y&metadata_filter=...&ad_account_ids=...
    │       └─ Response: {min_duration: 15, max_duration: 3600}
    │           └─ Update sliderOptions: {floor: 15, ceil: 3600, translate: formatDuration}
    │
    ├─ Step 2: User adjusts slider (userChangeEnd event)
    │   └─ durationMin, durationMax state updated
    │   └─ Call onFilterChange()
    │
    └─ Step 3: Grid re-query
       └─ GET /dashboard/assets?...&duration_min=X&duration_max=Y
           ├─ Backend: Apply WHERE CreativeAsset.video_duration BETWEEN duration_min AND duration_max
           ├─ Backend: Return null_duration_count = COUNT of VIDEO assets matching other filters but video_duration IS NULL
           └─ Response includes: {items: [...], null_duration_count: 42}
               └─ Render callout if durationMin > bounds.min OR durationMax < bounds.max
                   └─ "42 videos have no duration data and are excluded from this filter"

[Backfill Job Flow]
    ↓
[Sync Finish Hook — all 4 platforms]
    ├─ Check: SELECT COUNT(*) FROM creative_assets WHERE asset_type='video' AND video_duration IS NULL AND organization_id=X
    ├─ If count > 0:
    │   └─ create_background_job(job_type='duration_backfill', org_id=X)
    │       └─ Job_id returned; status=PENDING
    │
    └─ Backfill Job Execution (async, deferred or on-demand)
        ├─ SELECT asset_id, asset_url FROM creative_assets WHERE organization_id=X AND asset_type='video' AND video_duration IS NULL LIMIT 100
        ├─ For each asset:
        │   ├─ Download file from object_storage (MinIO/S3)
        │   ├─ Extract duration: ffprobe(file_path)
        │   └─ UPDATE creative_assets SET video_duration = duration WHERE asset_id = X
        │
        └─ Update job record: status=COMPLETE, progress_current=100, progress_total=100
```

### Recommended Project Structure

No new directories. All changes within existing files:

```
backend/
├── app/api/v1/endpoints/
│   └── dashboard.py          # Add duration_min/max params; add /duration-bounds endpoint; add null_duration_count to response
├── app/services/sync/
│   ├── video_utils.py        # [NEW] Extract _get_video_duration() from dv360_sync.py (shared by all platforms)
│   ├── dv360_sync.py         # Add post-sync backfill trigger + use video_utils._get_video_duration()
│   ├── google_ads_sync.py    # Add post-sync backfill trigger
│   ├── meta_sync.py          # Add post-sync backfill trigger
│   ├── tiktok_sync.py        # Add post-sync backfill trigger
│   └── backfill_job.py       # [NEW] Duration backfill job executor
└── tests/
    └── test_dashboard_duration.py  # [NEW] Filter params, bounds endpoint, null_duration_count

frontend/
└── src/app/features/dashboard/
    └── dashboard.component.ts  # Add durationMin/Max state, sliderOptions, loadDurationBounds(), formatDuration()
```

### Pattern 1: Dual-Handle Range Slider with Dynamic Bounds

**What:** A slider state management pattern where bounds are fetched dynamically from the backend and updated whenever other filters change.

**When to use:** When a slider's floor/ceil depends on filtered data (e.g., duration bounds depend on selected accounts/dates).

**Example (frontend):**

```typescript
// Source: Dashboard score slider pattern + Phase 23 requirements

// State
durationMin = 0;
durationMax = Infinity;
durationSliderOptions: Options = {
  floor: 0,
  ceil: 1000,
  step: 1,
  noSwitching: true,
  disabled: false,
  translate: (value) => this.formatDuration(value),
};
durationSliderDisabled = false;
hasVideoAssets = false;
loadingDurationBounds = false;

// Helper: format seconds to human-readable string
formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

// Load bounds after other filters change (part of loadData() response handler)
loadDurationBounds(): void {
  this.loadingDurationBounds = true;
  const params: any = {
    date_from: this.dateFrom,
    date_to: this.dateTo,
  };
  
  // Pass other active filters (NOT duration filter itself — avoid circular)
  if (this.selectedFormat) params.formats = this.selectedFormat;
  if (this.selectedAdAccountIds.length > 0) params.ad_account_ids = this.selectedAdAccountIds.join(',');
  if (this.activeMetadataFilters.length > 0) {
    params.metadata_filter = this.activeMetadataFilters.map(f => `${f.field}:${f.value}`);
  }
  
  this.api.get<{min_duration: number; max_duration: number}>('/dashboard/duration-bounds', params)
    .subscribe({
      next: (res) => {
        // Update slider bounds
        this.durationSliderOptions = {
          ...this.durationSliderOptions,
          floor: res.min_duration,
          ceil: res.max_duration,
        };
        // Reset slider to full range
        this.durationMin = res.min_duration;
        this.durationMax = res.max_duration;
        this.loadingDurationBounds = false;
      },
      error: () => {
        this.loadingDurationBounds = false;
        // Fallback: use sensible defaults (0–3600 seconds = 1 hour)
        this.durationSliderOptions = {
          ...this.durationSliderOptions,
          floor: 0,
          ceil: 3600,
        };
      }
    });
}

// On slider change (userChangeEnd event)
onDurationChange(): void {
  // duration_min/max params only sent if different from bounds
  this.onFilterChange();
}

// Determine visibility
get durationSliderVisible(): boolean {
  return this.hasVideoAssets;
}

// In loadData() response handler:
// this.hasVideoAssets = this.assets.some(a => a.asset_type === 'video');
// this.loadDurationBounds();  // Recompute bounds for new data
```

**Example (backend — GET /dashboard/duration-bounds):**

```python
# Source: FastAPI + SQLAlchemy pattern from Phase 22

@router.get("/duration-bounds")
async def get_duration_bounds(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    platforms: Optional[str] = Query(default=None),
    formats: Optional[str] = Query(default=None),
    ad_account_ids: Optional[str] = Query(default=None),
    metadata_filter: Optional[List[str]] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return MIN and MAX video_duration for VIDEO assets matching all active filters (except duration).
    
    Purpose: frontend uses this to set slider floor/ceil dynamically.
    Filter-aware (D-02): includes date range, format, account, metadata filters.
    Duration filter itself is NOT applied (would be circular).
    
    Response: {"min_duration": 15, "max_duration": 3600}
    """
    if not date_from:
        date_from = date.today() - timedelta(days=30)
    if not date_to:
        date_to = date.today() - timedelta(days=1)

    # Start with base query: VIDEO assets only, org-scoped, within date range
    query = (
        select(
            func.min(CreativeAsset.video_duration).label("min_duration"),
            func.max(CreativeAsset.video_duration).label("max_duration"),
        )
        .join(HarmonizedPerformance, HarmonizedPerformance.asset_id == CreativeAsset.id)
        .where(
            CreativeAsset.organization_id == current_user.organization_id,
            CreativeAsset.asset_type == 'video',
            CreativeAsset.video_duration.isnot(None),
            HarmonizedPerformance.report_date >= date_from,
            HarmonizedPerformance.report_date <= date_to,
        )
    )

    # Apply same filters as /dashboard/assets (except duration filter itself)
    platform_list = [p.strip().upper() for p in platforms.split(",")] if platforms else None
    format_list = [f.strip().upper() for f in formats.split(",")] if formats else None
    account_id_list = [a.strip() for a in ad_account_ids.split(",")] if ad_account_ids else None

    if platform_list:
        query = query.where(CreativeAsset.platform.in_(platform_list))
    if format_list:
        query = query.where(CreativeAsset.asset_format.in_(format_list))
    if account_id_list:
        query = query.where(CreativeAsset.ad_account_id.in_(account_id_list))

    # Apply metadata filters (aliased JOINs, same pattern as /dashboard/assets)
    filters_by_field: dict[str, list[str]] = {}
    for meta_filter_str in (metadata_filter or []):
        if ":" not in meta_filter_str:
            raise HTTPException(status_code=400, detail="Invalid metadata_filter format")
        field_name, filter_value = meta_filter_str.split(":", 1)
        filters_by_field.setdefault(field_name, []).append(filter_value)
    
    for i, (field_name, filter_values) in enumerate(filters_by_field.items()):
        amv = aliased(AssetMetadataValue, name=f"amv_{i}")
        mf = aliased(MetadataField, name=f"mf_{i}")
        query = query.join(
            amv,
            and_(amv.asset_id == CreativeAsset.id, amv.value.in_(filter_values)),
        ).join(
            mf,
            and_(
                mf.id == amv.field_id,
                mf.name == field_name,
                mf.organization_id == current_user.organization_id,
            ),
        )

    result = (await db.execute(query)).one()
    
    return {
        "min_duration": float(result.min_duration) if result.min_duration else 0,
        "max_duration": float(result.max_duration) if result.max_duration else 3600,  # 1 hour fallback
    }
```

**Example (backend — extend GET /dashboard/assets):**

```python
# Modifications to existing get_dashboard_assets signature + query

@router.get("/assets", response_model=dict)
async def get_dashboard_assets(
    # ... existing params ...
    duration_min: Optional[float] = Query(default=None, ge=0),
    duration_max: Optional[float] = Query(default=None, ge=0),
    # ... rest of params ...
):
    """Paginated creative assets with duration filtering.
    
    New params:
    - duration_min: filter to assets with video_duration >= this value
    - duration_max: filter to assets with video_duration <= this value
    
    New response field:
    - null_duration_count: number of VIDEO assets matching OTHER filters but excluded because video_duration IS NULL
                           (only computed when duration filter is active)
    """
    # ... existing query setup ...
    
    # Apply duration filter (new)
    if duration_min is not None:
        query = query.where(CreativeAsset.video_duration >= duration_min)
    if duration_max is not None:
        query = query.where(CreativeAsset.video_duration <= duration_max)
    
    # ... rest of query ...
    
    # Compute null_duration_count only when filter is active
    null_duration_count = 0
    if duration_min is not None or duration_max is not None:
        # Count VIDEO assets matching OTHER active filters but excluding duration IS NULL
        null_q = select(func.count(CreativeAsset.id)).where(
            CreativeAsset.organization_id == current_user.organization_id,
            CreativeAsset.asset_type == 'video',
            CreativeAsset.video_duration.is_(None),
            # Apply ALL other filters (platform, format, account, metadata, score)
            # But NOT the duration filter
        )
        # Apply same platform/format/account/metadata/score filters as main query
        # (copy the WHERE/JOIN logic from above, excluding duration clauses)
        # ...
        null_duration_count = (await db.execute(null_q)).scalar() or 0
    
    # ... existing return statement, add null_duration_count field ...
    return {
        "items": [...],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "null_duration_count": null_duration_count,  # NEW
    }
```

### Pattern 2: Async Backfill Job with Batch Processing

**What:** An async job that processes items in batches (100 at a time), extracting metadata (duration) from files and updating the database.

**When to use:** When you need to backfill a column that is computationally expensive (ffprobe), and the operation should not block user interactions or other sync jobs.

**Example (backend):**

```python
# Source: Phase 17–19 job_tracker pattern + Phase 23 requirements

# In backend/app/services/sync/backfill_job.py (new file)

import logging
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session_factory
from app.models.creative import CreativeAsset
from app.models.jobs import BackgroundJob
from app.services.sync.job_tracker import create_background_job, update_background_job
from app.services.object_storage import get_object_storage
from app.services.sync.video_utils import get_video_duration  # NEW: extracted utility

logger = logging.getLogger(__name__)


async def run_duration_backfill(org_id: uuid.UUID, batch_size: int = 100):
    """Backfill video_duration for NULL-duration VIDEO assets.
    
    Called at the end of each sync run if any NULL-duration assets exist.
    Processes in batches of 100 to avoid CPU spikes from ffprobe.
    
    Args:
        org_id: Organization UUID
        batch_size: Number of assets per batch (default 100 per D-11)
    """
    job_id = await create_background_job(
        job_type="duration_backfill",
        org_id=org_id,
        metadata={"triggered_at": datetime.utcnow().isoformat()},
    )
    
    try:
        async with get_session_factory()() as db:
            # Count total NULL-duration VIDEO assets
            total_query = select(func.count(CreativeAsset.id)).where(
                CreativeAsset.organization_id == org_id,
                CreativeAsset.asset_type == 'video',
                CreativeAsset.video_duration.is_(None),
            )
            total = (await db.execute(total_query)).scalar() or 0
            
            await update_background_job(
                job_id,
                status="RUNNING",
                progress_total=total,
            )
            
            processed = 0
            while processed < total:
                # Fetch next batch
                batch_query = (
                    select(CreativeAsset)
                    .where(
                        CreativeAsset.organization_id == org_id,
                        CreativeAsset.asset_type == 'video',
                        CreativeAsset.video_duration.is_(None),
                    )
                    .limit(batch_size)
                )
                result = await db.execute(batch_query)
                assets = result.scalars().all()
                
                if not assets:
                    break
                
                # Process each asset: extract duration from file
                obj_storage = get_object_storage()
                for asset in assets:
                    try:
                        # Download file from object storage
                        file_bytes = obj_storage.download_bytes(asset.asset_url)
                        
                        # Extract duration using ffprobe
                        duration = await get_video_duration(file_bytes)
                        
                        if duration is not None:
                            asset.video_duration = duration
                            await db.flush()
                            logger.info(f"Backfill: asset {asset.id} duration={duration}")
                    except Exception as e:
                        logger.warning(f"Backfill failed for asset {asset.id}: {e}")
                        continue
                
                await db.commit()
                processed += len(assets)
                
                # Update progress
                await update_background_job(
                    job_id,
                    progress_current=processed,
                )
        
        # Job complete
        await update_background_job(
            job_id,
            status="COMPLETE",
        )
        logger.info(f"Backfill complete: {processed} assets processed")
        
    except Exception as e:
        logger.error(f"Backfill job failed: {e}", exc_info=True)
        await update_background_job(
            job_id,
            status="FAILED",
            error={
                "type": type(e).__name__,
                "message": str(e),
            },
        )


# In backend/app/services/sync/video_utils.py (new file, extracted from dv360_sync.py)

import json
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def get_video_duration(file_path: str) -> Optional[float]:
    """Extract duration in seconds from a video file using ffprobe.
    
    Args:
        file_path: Path to video file (local or temporary file during download)
    
    Returns:
        Duration in seconds as float, or None if extraction fails
    """
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", file_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = data.get("format", {}).get("duration")
            if duration:
                return float(duration)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        logger.debug("ffprobe failed for %s: %s", file_path, e)
    return None


# In each sync service (dv360_sync.py, google_ads_sync.py, meta_sync.py, tiktok_sync.py)
# At the END of run() method, before returning:

async def _run_sync(self, ...):
    # ... all existing sync logic ...
    
    # NEW: Trigger backfill if any NULL-duration assets were created
    try:
        null_count_query = select(func.count(CreativeAsset.id)).where(
            CreativeAsset.organization_id == org_id,
            CreativeAsset.asset_type == 'video',
            CreativeAsset.video_duration.is_(None),
        )
        null_count = (await db.execute(null_count_query)).scalar() or 0
        if null_count > 0:
            logger.info(f"Triggering backfill for {null_count} NULL-duration assets")
            from app.services.sync.backfill_job import run_duration_backfill
            # Fire and forget — do not await (allow sync to complete)
            asyncio.create_task(run_duration_backfill(org_id))
    except Exception as e:
        logger.warning(f"Failed to trigger backfill: {e}")
```

### Anti-Patterns to Avoid

- **Hardcoded slider bounds:** Don't use fixed floor/ceil values; fetch from API per D-01
- **Synchronous ffprobe in sync path:** Don't call ffprobe during sync; extract to async backfill job per D-11
- **Missing NULL count logic:** Don't forget to compute and return null_duration_count when filter is active per D-07
- **Filtering in JavaScript:** Don't load all durations and filter client-side; let backend apply BETWEEN clause per pattern
- **Re-extracting duration on every page load:** Cache bounds in component state; only reload when other filters change

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dual-handle range slider | Custom div + manual mouse handlers | ngx-slider (already imported) | Handles multi-touch, keyboard navigation, accessibility, label formatting |
| Video duration extraction | Custom ffmpeg integration | ffprobe via subprocess (already used in dv360_sync.py) | Avoids spawning ffmpeg subprocess; ffprobe is a query tool |
| Async job lifecycle | Manual status tracking + db.execute calls | job_tracker helpers (proven in Phase 17–19) | Deduplicates error handling, SSE notification, retry logic |
| Object storage file download | Custom S3/MinIO client calls | Existing get_object_storage() API | Encapsulates provider-specific logic; easier to swap providers |
| Duration formatting | Manual string concatenation | Helper function `formatDuration(seconds)` | Reusable, testable, consistent across UI |

---

## Runtime State Inventory

No rename/refactor/migration phase — **greenfield implementation**. Skip entirely.

---

## Common Pitfalls

### Pitfall 1: Bounds Query Missing Video Filter

**What goes wrong:** Bounds endpoint returns min/max for ALL assets, including images. Slider range includes 0–0 when only images are present.

**Why it happens:** Query doesn't filter `asset_type == 'video'`.

**How to avoid:** Every query in /duration-bounds must include `CreativeAsset.asset_type == 'video'` in WHERE clause. Test with an org that has only images.

**Warning signs:** Slider appears even when grid has no videos; bounds are 0–0 or very skewed.

### Pitfall 2: Missing NULL Duration Count When Filter Inactive

**What goes wrong:** Callout appears even when slider hasn't been adjusted; confuses users about why count is always 0.

**Why it happens:** null_duration_count computed unconditionally instead of checking if filter is active.

**How to avoid:** Only compute when `duration_min is not None or duration_max is not None`. Omit the field if filter is inactive (or set to None/0 but don't display callout).

**Warning signs:** Callout shows "0 assets have no duration" even on first load.

### Pitfall 3: Circular Bounds Refresh When Slider Moves

**What goes wrong:** Every slider movement calls loadDurationBounds(), causing a flurry of API requests. UX feels slow.

**Why it happens:** onDurationChange() triggers loadDurationBounds() instead of just onFilterChange().

**How to avoid:** D-02 is explicit: bounds call is triggered by OTHER filter changes, not by slider changes. Only call loadDurationBounds() in the response handler of /dashboard/assets, not on every slider event.

**Warning signs:** Network tab shows many GET /duration-bounds requests; test with browser devtools.

### Pitfall 4: Object Storage Download Failing Silently in Backfill

**What goes wrong:** Backfill job completes but assets still have NULL duration. No error logged.

**Why it happens:** Exception caught and logged but processing continues; asset not updated.

**How to avoid:** Log every failure with asset_id. Track success/failure count in job output. Return both in response.

**Warning signs:** Test backfill job manually; verify a few assets are actually updated in DB.

### Pitfall 5: Backfill Job Triggered But Never Executed

**What goes wrong:** create_background_job() succeeds, but job never runs. Sits in PENDING forever.

**Why it happens:** Job is created but no scheduler task exists to execute it.

**How to avoid:** Decide on execution model: (a) APScheduler periodic task that polls for PENDING duration_backfill jobs, or (b) Fire-and-forget asyncio.create_task() call in sync finish hook. Phase 23 CONTEXT.md doesn't specify — research should clarify.

**Warning signs:** Job monitor shows "PENDING" jobs weeks old; verify scheduler is running the backfill executor.

---

## Code Examples

### Frontend: Duration Slider with Dynamic Bounds

```typescript
// Source: dashboard.component.ts — duration slider integration

// In class properties:
durationMin = 0;
durationMax = Infinity;
durationSliderOptions: Options = {
  floor: 0,
  ceil: 3600,
  step: 1,
  noSwitching: true,
  disabled: false,
  translate: (value: number) => this.formatDuration(value),
};
hasVideoAssets = false;
nullDurationCount = 0;
loadingDurationBounds = false;

// Helper
formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

// Template (in toolbar):
<div class="duration-slider-wrapper" *ngIf="hasVideoAssets">
  <span class="slider-label">Duration</span>
  <ngx-slider
    [(value)]="durationMin"
    [(highValue)]="durationMax"
    [options]="durationSliderOptions"
    (userChangeEnd)="onFilterChange()"
  ></ngx-slider>
  <span class="slider-values">{{ formatDuration(durationMin) }} – {{ formatDuration(durationMax) }}</span>
</div>

<!-- NULL duration callout (shown only when filter active) -->
<div class="duration-null-callout" *ngIf="(durationMin > 0 || durationMax < durationSliderOptions.ceil) && nullDurationCount > 0">
  <i class="bi bi-info-circle"></i>
  <span>{{ nullDurationCount }} video{{ nullDurationCount !== 1 ? 's' : '' }} have no duration data and are excluded from this filter</span>
</div>

// In loadData():
loadData(): void {
  // ... existing fetch logic ...
  
  this.api.get<DashboardAssetsResponse>('/dashboard/assets', params).subscribe({
    next: (res) => {
      this.assets = res.items;
      this.hasVideoAssets = this.assets.some(a => a.asset_type === 'video');
      this.nullDurationCount = res.null_duration_count || 0;
      this.loading = false;
      
      // Reload bounds after assets load (filter-aware)
      if (this.hasVideoAssets) {
        this.loadDurationBounds();
      } else {
        // Hide slider if no videos
        this.durationMin = 0;
        this.durationMax = 0;
      }
    },
  });
}

// Load duration bounds (filter-aware)
loadDurationBounds(): void {
  this.loadingDurationBounds = true;
  
  const params: any = {
    date_from: format(this.dateFrom, 'yyyy-MM-dd'),
    date_to: format(this.dateTo, 'yyyy-MM-dd'),
  };
  
  // Include other active filters (NOT duration filter itself)
  if (this.selectedFormat && this.selectedFormat !== '') {
    params.formats = this.selectedFormat;
  }
  if (this.selectedAdAccountIds.length > 0) {
    params.ad_account_ids = this.selectedAdAccountIds.join(',');
  }
  if (this.activeMetadataFilters.length > 0) {
    params.metadata_filter = this.activeMetadataFilters.map(f => `${f.field}:${f.value}`);
  }
  
  this.api.get<{min_duration: number; max_duration: number}>('/dashboard/duration-bounds', params)
    .subscribe({
      next: (res) => {
        this.durationSliderOptions = {
          ...this.durationSliderOptions,
          floor: res.min_duration,
          ceil: res.max_duration,
        };
        // Reset to full range
        this.durationMin = res.min_duration;
        this.durationMax = res.max_duration;
        this.loadingDurationBounds = false;
      },
      error: () => {
        // Fallback bounds
        this.durationSliderOptions = {
          ...this.durationSliderOptions,
          floor: 0,
          ceil: 3600,
        };
        this.loadingDurationBounds = false;
      }
    });
}

// Filter param building (in loadData):
const params: any = { ... };
if (this.durationMin > this.durationSliderOptions.floor || this.durationMax < this.durationSliderOptions.ceil) {
  params['duration_min'] = this.durationMin;
  params['duration_max'] = this.durationMax;
}
```

### Backend: Duration Filter Endpoint

```python
# Source: FastAPI + SQLAlchemy pattern from Phase 22 (dashboard.py)

@router.get("/duration-bounds")
async def get_duration_bounds(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    platforms: Optional[str] = Query(default=None),
    formats: Optional[str] = Query(default=None),
    ad_account_ids: Optional[str] = Query(default=None),
    metadata_filter: Optional[List[str]] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return min/max video duration scoped to current org and active filters (except duration).
    
    Purpose: Frontend slider floor/ceil — filter-aware per D-02.
    Excludes assets with NULL video_duration from min/max calc.
    Response: {"min_duration": 15, "max_duration": 3600}
    """
    if not date_from:
        date_from = date.today() - timedelta(days=30)
    if not date_to:
        date_to = date.today() - timedelta(days=1)

    platform_list = [p.strip().upper() for p in platforms.split(",")] if platforms else None
    format_list = [f.strip().upper() for f in formats.split(",")] if formats else None
    account_id_list = [a.strip() for a in ad_account_ids.split(",")] if ad_account_ids else None

    # Base query: VIDEO assets only, org-scoped, within date range, with non-null duration
    query = (
        select(
            func.min(CreativeAsset.video_duration).label("min_duration"),
            func.max(CreativeAsset.video_duration).label("max_duration"),
        )
        .join(HarmonizedPerformance, HarmonizedPerformance.asset_id == CreativeAsset.id)
        .where(
            CreativeAsset.organization_id == current_user.organization_id,
            CreativeAsset.asset_type == 'video',
            CreativeAsset.video_duration.isnot(None),
            HarmonizedPerformance.report_date >= date_from,
            HarmonizedPerformance.report_date <= date_to,
        )
    )

    # Apply other filters (platform, format, account, metadata)
    if platform_list:
        query = query.where(CreativeAsset.platform.in_(platform_list))
    if format_list:
        query = query.where(CreativeAsset.asset_format.in_(format_list))
    if account_id_list:
        query = query.where(CreativeAsset.ad_account_id.in_(account_id_list))

    # Metadata filters (same aliased JOIN pattern as /dashboard/assets)
    filters_by_field: dict[str, list[str]] = {}
    for meta_filter_str in (metadata_filter or []):
        if ":" not in meta_filter_str:
            raise HTTPException(status_code=400, detail="Invalid metadata_filter format")
        field_name, filter_value = meta_filter_str.split(":", 1)
        filters_by_field.setdefault(field_name, []).append(filter_value)
    
    for i, (field_name, filter_values) in enumerate(filters_by_field.items()):
        amv = aliased(AssetMetadataValue, name=f"amv_{i}")
        mf = aliased(MetadataField, name=f"mf_{i}")
        query = query.join(
            amv,
            and_(amv.asset_id == CreativeAsset.id, amv.value.in_(filter_values)),
        ).join(
            mf,
            and_(
                mf.id == amv.field_id,
                mf.name == field_name,
                mf.organization_id == current_user.organization_id,
            ),
        )

    result = (await db.execute(query)).one()
    
    # Return sensible fallback if no video assets found
    min_dur = float(result.min_duration) if result.min_duration else 0
    max_dur = float(result.max_duration) if result.max_duration else 3600
    
    return {
        "min_duration": min_dur,
        "max_duration": max_dur,
    }
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual pagination in asset list | Paginated server-side with performance agg subqueries | Phase 4 | Scales to 100k+ assets; users don't wait for full dataset |
| Hardcoded filter bounds | Dynamic bounds fetched from API | Phase 23 | Bounds reflect actual data; no stale hardcoded ranges |
| Metadata filter on backend only | Full-stack with client-side autocomplete filtering | Phase 22 | Instant prefix matching; no keystroke-debounced requests |
| Synchronous video extraction during sync | Async backfill job post-sync | Phase 23 | Doesn't block sync completion; CPU-bound ffprobe doesn't spike |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 22 (metadata filter) is 100% complete in main (Plan 01 + Plan 02) | Section 1 verification | If Plan 02 (frontend) is incomplete, Phase 23 must wait for it; metadata filter integration may fail |
| A2 | CreativeAsset.asset_type field exists and uses 'video' / 'image' / 'carousel' values | Data model check | Filter logic assumes asset_type == 'video'; if field doesn't exist or uses different values, queries break |
| A3 | CreativeAsset.video_duration field exists, is Float nullable | Data model check | Duration filter params assume this column exists; if missing, migration needed first |
| A4 | HarmonizedPerformance table is populated during sync for all assets | Architecture pattern | Duration bounds query joins HarmonizedPerformance; if assets lack perf data, query returns empty set |
| A5 | ffprobe CLI tool is available on backend runtime | System dependency | Backfill job assumes ffprobe is in PATH; if missing, duration extraction fails silently |
| A6 | Object storage API (get_object_storage()) can download files by URL/path | Integration pattern | Backfill job must fetch video files from MinIO/S3; if API doesn't support download-by-path, must refactor |
| A7 | AsyncSession and asyncio patterns are safe for background jobs | Architecture pattern | Backfill job uses async DB operations; if database connection pool exhausts, job hangs |

---

## Open Questions

1. **Backfill job execution model**
   - What we know: job_tracker pattern (Phase 17–19) handles creation + status tracking
   - What's unclear: How is a duration_backfill job actually invoked after creation? APScheduler periodic task? Separate worker? Fire-and-forget asyncio.create_task()?
   - Recommendation: Research scheduler.py to verify if a job executor exists; if not, plan should implement one

2. **NULL count computation cost**
   - What we know: null_duration_count requires a separate SELECT COUNT(*) query per request
   - What's unclear: Is this query cached? Or re-executed on every /dashboard/assets call?
   - Recommendation: Only compute when duration filter is active (reduces cost 95% of the time per D-06)

3. **Object storage file fetch strategy**
   - What we know: asset_url is a served URL (MinIO/S3 public URL)
   - What's unclear: Can we download via HTTP GET to asset_url, or must we use object storage SDK?
   - Recommendation: Check existing download helpers in object_storage.py; prefer SDK method for credential/auth handling

4. **Bounds query performance at scale**
   - What we know: Duration bounds uses MIN/MAX aggregation
   - What's unclear: Is there an index on CreativeAsset(organization_id, asset_type, video_duration) for this query?
   - Recommendation: Add composite index or verify query plan is efficient before Phase 23 execution

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| ffprobe | Backfill job duration extraction | ✓ (used in dv360_sync.py) | system-provided | None — if missing, backfill fails; must install |
| PostgreSQL | Duration bounds / filter queries | ✓ | 15.4 | — |
| Angular Material ngx-slider | Frontend slider UI | ✓ (imported in dashboard.ts) | 2.0.0+ | — |
| Object storage (MinIO/S3) | Backfill job video download | ✓ (used in asset downloads) | — | Must configure storage before sync |
| AsyncSession / asyncpg | Async DB operations in backfill | ✓ (used in all sync services) | — | — |

**Missing dependencies with no fallback:**
- None — all required tools already in use

**Missing dependencies with fallback:**
- None

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + SQLAlchemy async fixtures |
| Config file | backend/pytest.ini or pyproject.toml |
| Quick run command | `pytest backend/tests/test_dashboard_duration.py -x -v` |
| Full suite command | `pytest backend/tests/ -x -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-03 | GET /duration-bounds returns min/max scoped to org + filters | unit | `pytest backend/tests/test_dashboard_duration.py::test_duration_bounds_org_scoped -xvs` | ❌ Wave 0 |
| DASH-03 | GET /dashboard/assets?duration_min=X&duration_max=Y applies BETWEEN filter | unit | `pytest backend/tests/test_dashboard_duration.py::test_duration_filter_between -xvs` | ❌ Wave 0 |
| DASH-03 | GET /dashboard/assets returns null_duration_count when filter active | unit | `pytest backend/tests/test_dashboard_duration.py::test_null_duration_count -xvs` | ❌ Wave 0 |
| DASH-03 | Backfill job creates, runs, updates progress, completes | integration | `pytest backend/tests/test_dashboard_duration.py::test_backfill_job_lifecycle -xvs` | ❌ Wave 0 |
| DASH-03 | Frontend slider renders only when hasVideoAssets=true | e2e | Manual or Playwright | ✅ Manual-only |
| DASH-03 | Frontend duration callout shows when filter active | e2e | Manual or Playwright | ✅ Manual-only |
| DASH-03 | Duration bounds load after other filters change | integration | Manual browser test | ✅ Manual-only |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/test_dashboard_duration.py -x` (10–15 sec)
- **Per wave merge:** `pytest backend/tests/ -x` (full suite, ~30 sec)
- **Phase gate:** Full suite + manual browser verification of slider UX (30–40 min)

### Wave 0 Gaps

- [ ] `backend/tests/test_dashboard_duration.py` — new test cases for duration filter (bounds endpoint, BETWEEN filter, null count, backfill lifecycle)
- [ ] Backend endpoints: GET `/dashboard/duration-bounds` + modify GET `/dashboard/assets` to accept duration_min/max params and return null_duration_count
- [ ] Backend backfill infrastructure: `video_utils.py` (ffprobe extraction), `backfill_job.py` (job executor), sync service post-hooks (all 4 platforms)
- [ ] Frontend: duration slider state, loadDurationBounds(), formatDuration() helper, NULL callout rendering

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | User already authenticated via get_current_user() |
| V3 Session Management | no | Phase 23 doesn't modify session handling |
| V4 Access Control | **yes** | Duration bounds endpoint must include org_id guard on all queries (same as /dashboard/assets) |
| V5 Input Validation | **yes** | duration_min/max query params are floats; validated by Query(ge=0); metadata_filter params reuse Phase 22 validation |
| V6 Cryptography | no | Phase 23 doesn't introduce new cryptographic requirements |

### Known Threat Patterns for {FastAPI + SQLAlchemy + Angular}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-org duration bounds leakage | Disclosure | Every query includes CreativeAsset.organization_id == current_user.organization_id guard; verified in test_duration_bounds_org_scoped |
| SQL injection via duration_min/max | Tampering | SQLAlchemy type validation (float); parameters passed as bind variables, not concatenated |
| Metadata filter bypass to access hidden durations | Tampering | Metadata filter validation reuses Phase 22 pattern; both fields validated before apply |
| Backfill job accessing wrong org's assets | Disclosure | Backfill job parameterized by org_id; query includes organization_id guard |
| User enumeration via NULL count changes | Information Disclosure | null_duration_count only returned when filter is active; avoids information leakage on unfiltered requests |

---

## Sources

### Primary (HIGH confidence)

- **[VERIFIED: codebase]** frontend/src/app/features/dashboard/dashboard.component.ts — NgxSliderModule already imported (line 18); score slider pattern (lines 222–227) uses Options config with translate callback; activeMetadataFilters state management present (line 1344)
- **[VERIFIED: codebase]** backend/app/api/v1/endpoints/dashboard.py — GET /metadata-fields (lines 217–249), GET /metadata-fields/{field_id}/values (lines 252–286), GET /dashboard/assets (lines 289–500) with metadata_filter param (line 304) and aliased JOINs (lines 422–437) all implemented
- **[VERIFIED: codebase]** backend/app/models/creative.py line 51 — `video_duration: Mapped[float] = mapped_column(Float, nullable=True)` field already exists
- **[VERIFIED: codebase]** backend/app/services/sync/dv360_sync.py line 1423 — `_get_video_duration(file_path)` function using ffprobe exists
- **[VERIFIED: codebase]** backend/app/models/jobs.py — BackgroundJob model with id, job_type, org_id, status, progress_current, progress_total, metadata_ fields present
- **[VERIFIED: codebase]** backend/app/services/sync/job_tracker.py — create_background_job() and update_background_job() helpers implemented and tested in Phase 17
- **[CITED: .planning/phases/23-dashboard-duration-filter-backfill/23-CONTEXT.md]** — Phase 23 scope, decisions D-01 through D-11, canonical references

### Secondary (MEDIUM confidence)

- **[VERIFIED: codebase]** backend/app/api/v1/endpoints/dashboard.py — existing get_dashboard_assets() pattern shows how org_id guard is applied in metadata filter JOINs; same pattern applies to duration bounds
- **[VERIFIED: codebase]** frontend/src/app/features/dashboard/dashboard.component.ts lines 1907–1955 — selectMetadataField(), selectMetadataValue(), removeMetadataFilter() logic provides exact template for duration slider state management
- **[VERIFIED: codebase]** Alembic migration index creation pattern observed from Phase 22 (composite index on asset_metadata_values)

### Tertiary (validation deferred)

- A2–A7 (Assumptions log) — Will be verified during plan execution

---

## Metadata

**Confidence breakdown:**
- **Standard stack: HIGH** — All technologies verified in active codebase (ngx-slider, FastAPI, SQLAlchemy, PostgreSQL)
- **Architecture: HIGH** — Patterns (org-scoped queries, state management, job_tracker lifecycle) are proven in Phase 22 + Phase 17–19
- **Pitfalls: HIGH** — Common issues (bounds query missing video filter, circular refresh, backfill execution model) are observable from codebase inspection
- **Test infrastructure: MEDIUM** — pytest framework confirmed, test patterns observed, but Wave 0 gaps for DASH-03 specific test cases

**Research date:** 2026-05-18
**Valid until:** 2026-06-01 (14 days — filter architecture is stable; job_tracker pattern unlikely to change)

**Key Research Insights:**
1. Phase 22 is COMPLETE in main — both backend (Plan 01) and frontend (Plan 02) implemented. Duration filter builds on proven foundation.
2. Backfill job execution model is unclear — research identifies 3 possible approaches; plan should clarify which one (APScheduler, asyncio.create_task, or manual invocation).
3. Object storage download API is critical to backfill — must verify get_object_storage().download_bytes() or equivalent exists and is async-safe.
4. Composite index for duration bounds query (if not already created) should be added to avoid sequential scan on large organizations.
