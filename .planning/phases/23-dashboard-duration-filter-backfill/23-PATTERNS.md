# Phase 23: Dashboard Duration Filter + Backfill - Pattern Map

**Mapped:** 2026-05-18  
**Files analyzed:** 9 (3 new, 6 modified)  
**Analogs found:** 9 / 9 (100% coverage)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/api/v1/endpoints/dashboard.py` | controller | request-response, CRUD | `backend/app/api/v1/endpoints/dashboard.py` (existing) | exact |
| `backend/app/services/sync/video_utils.py` | utility | file-I/O | `backend/app/services/sync/dv360_sync.py` | extract-method |
| `backend/app/services/sync/backfill_job.py` | service | batch, async | `backend/app/services/sync/scoring_job.py` | role-match |
| `backend/app/services/sync/dv360_sync.py` | service | request-response | `backend/app/services/sync/dv360_sync.py` (existing) | exact |
| `backend/app/services/sync/google_ads_sync.py` | service | request-response | `backend/app/services/sync/google_ads_sync.py` (existing) | exact |
| `backend/app/services/sync/meta_sync.py` | service | request-response | `backend/app/services/sync/meta_sync.py` (existing) | exact |
| `backend/app/services/sync/tiktok_sync.py` | service | request-response | `backend/app/services/sync/tiktok_sync.py` (existing) | exact |
| `backend/tests/test_dashboard_duration.py` | test | request-response, CRUD | `backend/tests/test_dashboard_filters.py` | role-match |
| `frontend/src/app/features/dashboard/dashboard.component.ts` | component | request-response | `frontend/src/app/features/dashboard/dashboard.component.ts` (existing) | exact |

---

## Pattern Assignments

### `backend/app/api/v1/endpoints/dashboard.py` (controller, request-response, CRUD)

**Analog:** `backend/app/api/v1/endpoints/dashboard.py` (lines 1–520)

**Imports pattern** (lines 1–27):
```python
from datetime import date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text, case, nullslast, cast, distinct
from sqlalchemy.orm import selectinload, aliased
import uuid

from app.db.base import get_db
from app.models.user import User
from app.models.creative import CreativeAsset, AssetMetadataValue, AssetProjectMapping
from app.models.metadata import MetadataField
from app.models.performance import HarmonizedPerformance
from app.schemas.creative import DashboardFilterParams, DashboardStats, CreativeAssetResponse
from app.api.v1.deps import get_current_user

router = APIRouter()
```

**Org-scoped WHERE clause pattern** (lines 89–92):
```python
.where(
    CreativeAsset.organization_id == current_user.organization_id,
    HarmonizedPerformance.report_date >= df,
    HarmonizedPerformance.report_date <= dt,
)
```

**Metadata filter JOIN pattern with aliased fields** (lines 421–437):
```python
filters_by_field: dict[str, list[str]] = {}
for meta_filter_str in (metadata_filter or []):
    if ":" not in meta_filter_str:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metadata_filter format; expected field_name:value (got: {meta_filter_str})",
        )
    field_name, filter_value = meta_filter_str.split(":", 1)
    filters_by_field.setdefault(field_name, []).append(filter_value)
for i, (field_name, filter_values) in enumerate(filters_by_field.items()):
    amv = aliased(AssetMetadataValue, name=f"amv_{i}")
    mf = aliased(MetadataField, name=f"mf_{i}")
    query = query.join(
        amv,
        and_(
            amv.asset_id == CreativeAsset.id,
            amv.value.in_(filter_values),
        ),
    ).join(
        mf,
        and_(
            mf.id == amv.field_id,
            mf.name == field_name,
            mf.organization_id == current_user.organization_id,
        ),
    )
```

**Conditional filter application pattern** (lines 439–445):
```python
if score_min is not None:
    query = query.where(CreativeScoreResult.total_score >= score_min)
if score_max is not None:
    query = query.where(CreativeScoreResult.total_score <= score_max)

# Only assets with performance in period
query = query.where(perf_subq.c.total_spend.isnot(None))
```

**Response assembly pattern** (lines 477–520):
```python
assets_out = []
for row in rows:
    asset = row[0]
    perf = {
        "spend": row.total_spend,
        "impressions": row.total_impressions,
        # ... other perf fields ...
    }
    # ... compute additional fields ...
    assets_out.append({
        "id": str(asset.id),
        "platform": asset.platform,
        # ... other asset fields ...
        "performance": perf,
        # ... additional computed fields ...
    })

return {
    "items": assets_out,
    "total": total,
    "page": page,
    "page_size": page_size,
    "total_pages": (total + page_size - 1) // page_size,
}
```

**For Phase 23: ADD to this endpoint (new params + null_duration_count output):**
- Add `duration_min: Optional[float] = Query(default=None, ge=0)` and `duration_max: Optional[float] = Query(default=None, ge=0)` params
- Before returning, add conditional compute of `null_duration_count` (only if duration filter is active)
- Append `null_duration_count: int` to response dict

**For Phase 23: NEW endpoint `/dashboard/duration-bounds`:**
- Copy the entire filter-building logic (platform, format, account, metadata JOINs) from `get_dashboard_assets`
- Return `{"min_duration": float, "max_duration": float}` with sensible fallback (0, 3600)
- Ensure `CreativeAsset.asset_type == 'video'` and `CreativeAsset.video_duration.isnot(None)` in WHERE

---

### `backend/app/services/sync/video_utils.py` (utility, file-I/O)

**Analog:** `backend/app/services/sync/dv360_sync.py` lines 1423–1436

**Imports pattern**:
```python
import json
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)
```

**Core ffprobe extraction function** (extract from dv360_sync.py, lines 1423–1436):
```python
def get_video_duration(file_path: str) -> Optional[float]:
    """Extract duration in seconds from a video file using ffprobe.
    
    Args:
        file_path: Path to video file (local or temporary)
    
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
```

**For Phase 23:**
- Extract `_get_video_duration()` from dv360_sync.py as standalone `get_video_duration()`
- Update dv360_sync.py to import from video_utils: `from app.services.sync.video_utils import get_video_duration`
- Update dv360_sync.py line 1317 call from `self._get_video_duration()` to `get_video_duration()`

---

### `backend/app/services/sync/backfill_job.py` (service, batch, async)

**Analog:** `backend/app/services/sync/scoring_job.py` lines 46–92

**Imports pattern**:
```python
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session_factory
from app.models.creative import CreativeAsset
from app.models.jobs import BackgroundJob
from app.services.sync.job_tracker import create_background_job, update_background_job
from app.services.sync.video_utils import get_video_duration
from app.services.object_storage import get_object_storage

logger = logging.getLogger(__name__)
```

**Async job entry point pattern** (from scoring_job.py lines 46–60):
```python
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
```

**Batch fetch pattern** (model after scoring_job.py batch pattern):
```python
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
    for asset in assets:
        try:
            # Download file from object storage
            file_bytes = obj_storage.download_bytes(asset.asset_url)
            
            # Extract duration using ffprobe
            duration = get_video_duration(file_path)  # Pass file or bytes
            
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
```

**Job completion pattern** (from scoring_job.py and job_tracker.py):
```python
await update_background_job(
    job_id,
    status="COMPLETE",
)
logger.info(f"Backfill complete: {processed} assets processed")
```

**Error handling pattern**:
```python
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
```

---

### `backend/app/services/sync/dv360_sync.py` (service, request-response)

**Analog:** `backend/app/services/sync/dv360_sync.py` (existing)

**Post-sync backfill trigger pattern** (add at END of sync run):
```python
# Trigger backfill if any NULL-duration assets were created
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
        # Fire and forget — do not await
        asyncio.create_task(run_duration_backfill(org_id))
except Exception as e:
    logger.warning(f"Failed to trigger backfill: {e}")
```

**For Phase 23:**
- Replace internal `_get_video_duration()` method (line 1423) with import: `from app.services.sync.video_utils import get_video_duration`
- Update line 1317 call: change `self._get_video_duration(actual_path)` to `get_video_duration(actual_path)`
- Delete the `_get_video_duration()` method (lines 1423–1436)
- Add post-sync backfill trigger at the end of sync run

---

### `backend/app/services/sync/google_ads_sync.py` (service, request-response)

**Analog:** `backend/app/services/sync/google_ads_sync.py` (existing, same pattern as dv360_sync)

**For Phase 23:**
- Add post-sync backfill trigger (same pattern as dv360_sync) at the end of sync run
- Check if `google_ads_sync.py` has its own `_get_video_duration()` method; if so, update to use video_utils

---

### `backend/app/services/sync/meta_sync.py` (service, request-response)

**Analog:** `backend/app/services/sync/meta_sync.py` (existing)

**For Phase 23:**
- Add post-sync backfill trigger (same pattern as dv360_sync) at the end of sync run

---

### `backend/app/services/sync/tiktok_sync.py` (service, request-response)

**Analog:** `backend/app/services/sync/tiktok_sync.py` (existing)

**For Phase 23:**
- Add post-sync backfill trigger (same pattern as dv360_sync) at the end of sync run

---

### `backend/tests/test_dashboard_duration.py` (test, request-response, CRUD)

**Analog:** `backend/tests/test_dashboard_filters.py` lines 1–100

**Test imports pattern**:
```python
"""Phase 23 Plan 01 — Dashboard Duration Filter and Backfill Tests.

Tests for:
- GET /dashboard/duration-bounds returns min/max scoped to org + active filters
- GET /dashboard/assets?duration_min=X&duration_max=Y applies BETWEEN filter
- GET /dashboard/assets returns null_duration_count when filter active
- Backfill job creates, runs, processes batch, updates progress, completes
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
```

**Helper fixture pattern** (from test_dashboard_filters.py lines 21–40):
```python
def _make_asset_row(asset_id: uuid.UUID, video_duration: Optional[float], spend: float = 100.0):
    """Return a dict matching the dashboard /assets response item shape."""
    return {
        "id": str(asset_id),
        "platform": "META",
        "ad_id": f"ad_{asset_id.hex[:8]}",
        "ad_name": f"Ad {asset_id.hex[:8]}",
        "campaign_name": "Test Campaign",
        "campaign_objective": "AWARENESS",
        "asset_format": "VIDEO",
        "asset_type": "video",
        "video_duration": video_duration,
        "thumbnail_url": None,
        "asset_url": None,
        "scoring_status": "COMPLETE",
        "total_score": 75.0,
        "is_active": True,
        "performance": {"spend": spend},
        "performer_tag": "Average",
    }
```

**Test structure pattern** (from test_dashboard_filters.py):
```python
@pytest.fixture
def mock_db():
    """Async DB session mock."""
    return AsyncMock()

@pytest.fixture
def mock_user():
    """Minimal user mock."""
    user = MagicMock()
    user.organization_id = uuid.uuid4()
    return user

def test_duration_bounds_org_scoped():
    """GET /duration-bounds returns min/max scoped to current org only."""
    # Implementation: mock db.execute(), verify WHERE clause includes org_id guard
    pass

def test_duration_filter_between():
    """GET /dashboard/assets?duration_min=15&duration_max=120 applies BETWEEN filter."""
    # Implementation: verify CreativeAsset.video_duration.between() in WHERE
    pass

def test_null_duration_count_when_active():
    """GET /dashboard/assets?duration_min=15 returns null_duration_count > 0."""
    # Implementation: verify response includes null_duration_count field
    pass

def test_null_duration_count_when_inactive():
    """GET /dashboard/assets with no duration filter returns null_duration_count=0 or omitted."""
    # Implementation: verify field is 0 or absent when filter is inactive
    pass

def test_backfill_job_lifecycle():
    """Backfill job creates, runs, processes batch, completes."""
    # Implementation: mock job_tracker, run_duration_backfill(), verify progress updates
    pass
```

---

### `frontend/src/app/features/dashboard/dashboard.component.ts` (component, request-response)

**Analog:** `frontend/src/app/features/dashboard/dashboard.component.ts` (existing, lines 1–2000)

**Imports pattern** (lines 1–31):
```typescript
import { Component, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, FormGroup, ReactiveFormsModule, FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
// ... other Material imports ...
import { NgxSliderModule, Options } from '@angular-slider/ngx-slider';
import { Subject, debounceTime, takeUntil, forkJoin, interval, switchMap, take, takeWhile } from 'rxjs';
// ... other imports ...
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
```

**Interface patterns** (lines 33–98):
```typescript
interface DashboardAsset {
  id: string;
  platform: string;
  asset_format: string | null;
  asset_type: string | null;     // NEW for Phase 23
  video_duration: number | null;  // NEW for Phase 23
  // ... other fields ...
}

interface DashboardAssetsResponse {
  items: DashboardAsset[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  null_duration_count?: number;   // NEW for Phase 23
}
```

**Score slider state pattern** (lines 1405–1416, MODEL for duration slider):
```typescript
scoreMin = 0;
scoreMax = 100;
sliderOptions: Options = {
  floor: 0,
  ceil: 100,
  step: 1,
  noSwitching: true,
  disabled: true,
};
sliderDisabled = true;
private scoreChange$ = new Subject<void>();
```

**For Phase 23: ADD duration slider state** (mirror score slider):
```typescript
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
private durationChange$ = new Subject<void>();
```

**Helper method pattern** (NEW for Phase 23):
```typescript
formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}
```

**Load bounds method** (NEW for Phase 23):
```typescript
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
```

**Template slider pattern** (NEW for Phase 23, mirror score slider from lines 220–229):
```html
<!-- Duration range filter (per D-01, D-02, D-04) -->
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
<div class="duration-null-callout" *ngIf="(durationMin > durationSliderOptions.floor || durationMax < durationSliderOptions.ceil) && nullDurationCount > 0">
  <i class="bi bi-info-circle"></i>
  <span>{{ nullDurationCount }} video{{ nullDurationCount !== 1 ? 's' : '' }} have no duration data and are excluded from this filter</span>
</div>
```

**Filter param building pattern** (NEW for Phase 23, add to loadData near lines 1765–1766):
```typescript
const params: any = { ... };
if (this.durationMin > this.durationSliderOptions.floor || this.durationMax < this.durationSliderOptions.ceil) {
  params['duration_min'] = this.durationMin;
  params['duration_max'] = this.durationMax;
}
```

**In loadData() response handler** (NEW for Phase 23):
```typescript
next: (res) => {
  this.assets = res.items;
  this.hasVideoAssets = this.assets.some(a => a.asset_type === 'video');
  this.nullDurationCount = res.null_duration_count || 0;
  this.loading = false;
  
  // Reload bounds after assets load (filter-aware)
  if (this.hasVideoAssets) {
    this.loadDurationBounds();
  }
},
```

---

## Shared Patterns

### Org-Scoped Query Guard
**Source:** `backend/app/api/v1/endpoints/dashboard.py` line 90  
**Apply to:** All new backend endpoints and queries

```python
CreativeAsset.organization_id == current_user.organization_id
```

Every single query must include this WHERE clause to prevent cross-org data leakage.

---

### Job Tracker Pattern
**Source:** `backend/app/services/sync/job_tracker.py` lines 24–71

**Apply to:** `backend/app/services/sync/backfill_job.py`

```python
from app.services.sync.job_tracker import create_background_job, update_background_job

# Create job (commits before returning)
job_id = await create_background_job(
    job_type="duration_backfill",
    org_id=org_id,
    metadata={"triggered_at": datetime.utcnow().isoformat()},
)

# Update status + progress (auto-sets ended_at on COMPLETE/FAILED)
await update_background_job(
    job_id,
    status="RUNNING",
    progress_total=total,
)

# ... later, update progress ...
await update_background_job(job_id, progress_current=processed)

# Complete
await update_background_job(job_id, status="COMPLETE")
```

---

### Conditional Filter Application
**Source:** `backend/app/api/v1/endpoints/dashboard.py` lines 439–442

**Apply to:** Duration filter in `/dashboard/assets` endpoint

```python
if duration_min is not None:
    query = query.where(CreativeAsset.video_duration >= duration_min)
if duration_max is not None:
    query = query.where(CreativeAsset.video_duration <= duration_max)
```

Only apply filter clauses when the param is actually set (not None). This allows the backend to distinguish "filter not active" from "filter active with these bounds."

---

### Metadata Filter Aliased JOIN Pattern
**Source:** `backend/app/api/v1/endpoints/dashboard.py` lines 421–437

**Apply to:** `/dashboard/duration-bounds` endpoint (same metadata filter logic as `/dashboard/assets`)

Reuse the exact same logic to ensure consistent behavior between bounds and asset queries:
- Parse `metadata_filter` array
- Build `filters_by_field` dict
- For each field, create aliased `AssetMetadataValue` and `MetadataField`
- JOIN with `AND` conditions
- Include `mf.organization_id == current_user.organization_id` guard on MetadataField JOIN

---

### Batch Processing Pattern
**Source:** `backend/app/services/sync/scoring_job.py` lines 74–92

**Apply to:** `backend/app/services/sync/backfill_job.py` batch loop

```python
processed = 0
while processed < total:
    result = await db.execute(query.limit(batch_size))
    batch = result.scalars().all()
    
    if not batch:
        break
    
    # Process each item
    for item in batch:
        try:
            # ... operation ...
        except Exception as e:
            logger.warning(f"Item failed: {e}")
            continue
    
    await db.commit()
    processed += len(batch)
    await update_background_job(job_id, progress_current=processed)
```

Key pattern: fetch batch, process sequentially within batch, commit after batch, update progress, loop until done.

---

### Angular Slider State & Template Pattern
**Source:** `frontend/src/app/features/dashboard/dashboard.component.ts` lines 1405–1414, 220–229

**Apply to:** Duration slider (exactly mirror score slider)

- State: `durationMin`, `durationMax`, `durationSliderOptions: Options`
- Options config: `floor`, `ceil`, `step`, `noSwitching`, `translate` callback
- Template: `ngx-slider` with `[(value)]`, `[(highValue)]`, `[options]`, `(userChangeEnd)` handler
- Helper: `formatDuration(seconds)` returns human-readable string

---

## No Analog Found

None. All files have verified analogs in the codebase.

---

## Metadata

**Analog search scope:**
- `backend/app/api/v1/endpoints/dashboard.py` (full endpoint file)
- `backend/app/services/sync/dv360_sync.py` (ffprobe utility extraction)
- `backend/app/services/sync/scoring_job.py` (async batch job pattern)
- `backend/app/services/sync/job_tracker.py` (job lifecycle)
- `backend/tests/test_dashboard_filters.py` (test structure)
- `frontend/src/app/features/dashboard/dashboard.component.ts` (slider state + template)

**Files scanned:** 6 primary analogs + 3 secondary (Google Ads, Meta, TikTok sync services)

**Pattern extraction date:** 2026-05-18

**Confidence:**
- Backend API patterns: **EXACT** — all endpoints exist; duration filter is additive change only
- Backfill job pattern: **STRONG MATCH** — scoring_job.py uses identical job_tracker lifecycle, batch loop, error handling
- Frontend slider pattern: **EXACT** — score slider is 1:1 template for duration slider; options config identical
- Utility extraction: **EXACT** — ffprobe logic already exists in dv360_sync.py, just move to shared file

---

## Key Pattern Takeaways

1. **Org-scoped queries are non-negotiable** — every WHERE clause must include `CreativeAsset.organization_id == current_user.organization_id` guard.

2. **Metadata filter reuse** — `/dashboard/duration-bounds` must apply the exact same filter logic as `/dashboard/assets` to ensure bounds are "filter-aware" per D-02. Copy the aliased JOIN logic wholesale.

3. **Conditional param application** — Only apply duration BETWEEN clauses when `duration_min` or `duration_max` is not None. Same pattern as score filter (lines 439–442).

4. **Batch + progress** — Backfill job follows scoring_job.py pattern: fetch batch, process sequentially, commit, update progress, loop. Use job_tracker helpers for lifecycle.

5. **Angular slider is plug-and-play** — Copy score slider state (durationMin, durationMax, sliderOptions: Options) and template exactly. Only difference: `translate` callback to format seconds as "Xm Ys".

6. **Post-sync hook pattern** — At the end of each sync run (dv360, google_ads, meta, tiktok), fire a background task `asyncio.create_task(run_duration_backfill(org_id))` if NULL-duration assets exist. Don't await it.

