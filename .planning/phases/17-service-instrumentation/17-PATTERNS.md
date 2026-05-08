# Phase 17: Service Instrumentation - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 5 (new + modified)
**Analogs found:** 5/5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/services/sync/job_tracker.py` | utility/helper | request-response | `backend/app/db/base.py` | role-match |
| `backend/app/services/sync/scheduler.py` | service | CRUD + event-driven | `backend/app/services/sync/scheduler.py` (existing) | self-match |
| `backend/app/services/sync/scoring_job.py` | service | CRUD + batch | `backend/app/services/sync/scoring_job.py` (existing) | self-match |
| `backend/app/services/ai_autofill.py` | service | CRUD + request-response | `backend/app/services/ai_autofill.py` (existing) | self-match |
| `backend/tests/services/test_instrumentation.py` | test | CRUD | `backend/tests/services/test_scheduler.py` | role-match |

---

## Pattern Assignments

### `backend/app/services/sync/job_tracker.py` (utility/helper, request-response)

**Analog:** `backend/app/db/base.py` (for session factory pattern), `backend/app/services/sync/scheduler.py` (for SyncJob creation pattern)

**Imports pattern** (scheduler.py lines 1–19, db/base.py lines 1–6):
```python
import logging
import uuid
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base import get_session_factory
from app.models.jobs import BackgroundJob

logger = logging.getLogger(__name__)
```

**Session-per-operation pattern** (db/base.py lines 20–26, scheduler.py lines 135–162):
```python
# Pattern: open session, perform single operation, close session before external calls
async with get_session_factory()() as db:
    job = BackgroundJob(
        job_type=job_type,
        org_id=org_id,
        platform_connection_id=platform_connection_id,
        status="PENDING",
        started_at=datetime.utcnow(),
        metadata_=metadata or {},
    )
    db.add(job)
    await db.flush()
    job_id = job.id
    await db.commit()
return job_id
```

**Error handling pattern** (scheduler.py lines 198–223):
```python
# Pattern: use try/except, capture exception type/message, format traceback
import traceback
try:
    # ... operation ...
except Exception as e:
    logger.error(f"Operation failed: {type(e).__name__}: {e}")
    tb_str = traceback.format_exc()[:10000]  # D-13: truncate at 10KB
    error_dict = {
        "type": type(e).__name__,
        "message": str(e),
        "traceback": tb_str,
    }
    # Update job with error
```

**Core update pattern** (scheduler.py lines 206–221):
```python
# Pattern: use fresh session for updates, get row, modify fields, commit
async with get_session_factory()() as db:
    job = await db.get(BackgroundJob, job_id)
    if not job:
        logger.warning(f"BackgroundJob {job_id} not found")
        return
    
    job.status = status
    if progress_current is not None:
        job.progress_current = progress_current
    if progress_total is not None:
        job.progress_total = progress_total
    if output is not None:
        job.output = output
    if error is not None:
        job.error = error
    
    if status in ("COMPLETE", "FAILED"):
        job.ended_at = datetime.utcnow()
    
    db.add(job)
    await db.commit()
```

---

### `backend/app/services/sync/scheduler.py` (service, CRUD + event-driven)

**Analog:** `backend/app/services/sync/scheduler.py` (self-match for existing patterns)

**SyncJob creation pattern** (lines 151–161):
```python
# Template for parallel BackgroundJob creation — same location, same session
job = SyncJob(
    platform_connection_id=connection.id,
    job_type="DAILY",
    status="RUNNING",
    started_at=datetime.utcnow(),
    date_from=date_from,
    date_to=date_to,
)
db.add(job)
await db.flush()
job_id = str(job.id)
```

**Entry points for BackgroundJob instrumentation:**
- `run_daily_sync()` — L112: After connection fetch, before `meta_sync.sync_date_range()` call
- `run_full_resync()` — L427: After connection fetch (inspect via grep)
- `run_initial_sync()` — L707: After connection fetch (inspect via grep)
- `run_historical_sync()` — L938: After connection fetch (inspect via grep)
- `_run_google_ads_asset_downloads()` — L362: At function entry, before download loop
- `_run_dv360_asset_downloads()` — L399: At function entry, before download loop

**Download progress pattern** (lines 362–387, 399–435):
```python
# Pattern: session-per-operation for downloads
async with get_session_factory()() as db:
    result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.id == uuid.UUID(connection_id)
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        return
    
    # Spawn background download task
    await google_ads_sync.download_assets_post_commit(db, connection, asset_queue)
```

**Error handling in sync** (lines 198–223):
```python
# Pattern: fresh DB session for error updates, then notify
except Exception as e:
    logger.error(f"Daily sync fetch failed: {type(e).__name__}: {e}")
    try:
        await db.rollback()
    except Exception:
        pass
    async with get_session_factory()() as fresh_db:
        await fresh_db.execute(
            update(SyncJob).where(SyncJob.id == job.id).values(
                status="FAILED",
                error_message=f"{type(e).__name__}: {e}"[:4000],
                completed_at=datetime.utcnow()
            )
        )
        await fresh_db.commit()
```

---

### `backend/app/services/sync/scoring_job.py` (service, CRUD + batch)

**Analog:** `backend/app/services/sync/scoring_job.py` (self-match for existing patterns)

**Batch query pattern** (lines 74–89):
```python
# Pattern: single DB session for batch query, mark status, release before HTTP
async with get_session_factory()() as db:
    result = await db.execute(
        select(CreativeScoreResult, CreativeAsset)
        .join(CreativeAsset, CreativeAsset.id == CreativeScoreResult.creative_asset_id)
        .where(
            CreativeScoreResult.scoring_status == "UNSCORED",
            CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"]),
        )
        .order_by(CreativeScoreResult.created_at.asc())
        .limit(BATCH_SIZE)
    )
    rows = result.all()
    if not rows:
        logger.info("Scoring batch: no UNSCORED assets found")
        return
```

**Per-asset processing pattern** (lines 304–544, per-asset loop):
```python
# Pattern: _process_asset() called per row; each asset gets its own BackgroundJob (D-07)
for score_row, asset_row in rows:
    org_id = asset_row.organization_id
    # ... quota/field checks ...
    asyncio.create_task(_process_asset(score_id, asset_row, endpoint_type))
```

**Per-asset session management** (lines 318–324):
```python
# Pattern: fresh session per asset for config lookup
async with get_session_factory()() as db:
    config_result = await db.execute(
        select(OrgBrainsuiteConfig).where(
            OrgBrainsuiteConfig.organization_id == asset.organization_id
        )
    )
    org_config = config_result.scalar_one_or_none()
    # Close session here before HTTP call to BrainSuite API
```

**Score result format** (existing code at L484, for reference):
```python
# Pattern: store score result with brainsuite_job_id
# This becomes output JSONB (D-08):
# {
#     "score": score_data["total_score"],
#     "endpoint_type": endpoint_type,  # "VIDEO" or "STATIC_IMAGE"
#     "brainsuite_job_id": str(job_id),
#     "dimensions": score_data["score_dimensions"],
# }
```

---

### `backend/app/services/ai_autofill.py` (service, CRUD + request-response)

**Analog:** `backend/app/services/ai_autofill.py` (self-match for existing patterns)

**Entry point with exception wrapper** (lines 116–127):
```python
# Pattern: top-level try/except logs and marks FAILED if _autofill() throws
async def run_autofill_for_asset(asset_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """Entry point — called via asyncio.create_task() from sync services."""
    try:
        await _autofill(asset_id, org_id)
    except Exception as exc:
        logger.exception("auto-fill failed for asset_id=%s: %s", asset_id, exc)
        await _set_status(asset_id, "FAILED")
```

**Phase 1: DB read with session close** (lines 140–199):
```python
# Pattern: session-per-operation; close session before AI calls
async with get_session_factory()() as db:
    # Insert tracking row
    await db.execute(...)
    await db.commit()
    
    # Load field config
    fields = (await db.execute(...)).scalars().all()
    
    # Load asset
    asset = await db.get(CreativeAsset, asset_id)
    
    # Collect data before session closes
    field_data = [(f.id, f.auto_fill_type, f.default_value) for f in fields]
    asset_format = asset.asset_format or "IMAGE"
    # Session closes here (exits async with block)
```

**Output schema** (D-10, from RESEARCH.md, implemented in Phase 17):
```python
# Pattern: build output dict with structured fields before writing to DB
output = {
    "fields": [
        {
            "name": "<field_name>",
            "value": "<determined_value>",
            "source": "<gemini|whisper>",
            "confidence": "<str|null>",
        },
        # ... more fields ...
    ],
    "whisper_transcript": "<str|null>",
    "language": "<lang_code>",
}
# Then call: await update_background_job(bg_job_id, status="COMPLETE", output=output)
```

---

### `backend/tests/services/test_instrumentation.py` (test, CRUD)

**Analog:** `backend/tests/services/test_scheduler.py`

**Test imports and async pattern** (test_scheduler.py lines 1–12):
```python
import pytest
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, AsyncMock, patch

# Pre-import modules that depend on settings
import app.core.security  # noqa: F401
import app.services.sync.scoring_job  # noqa: F401
import app.services.sync.maintenance  # noqa: F401

@pytest.mark.asyncio
async def test_my_async_function():
    """Test description."""
    # Test implementation
```

**Mock DB pattern** (test_scheduler.py lines 25–42):
```python
# Pattern: mock execute() result and session factory
mock_execute_result = MagicMock()
mock_execute_result.scalars.return_value.all.return_value = []

mock_db = AsyncMock()
mock_db.execute.return_value = mock_execute_result

@asynccontextmanager
async def _mock_session():
    yield mock_db

def _mock_session_factory():
    return _mock_session()

mock_get_session_factory = MagicMock(return_value=_mock_session_factory)

with patch("app.core.config.settings", mock_settings), \
     patch("app.services.sync.scheduler.get_session_factory", mock_get_session_factory):
    # Import and run code under test
    from app.services.sync.scheduler import startup_scheduler
    await startup_scheduler()
```

**Test structure for instrumentation** (test_scheduler.py lines 15–63):
```python
# Pattern: verify mock was called with expected arguments
@pytest.mark.asyncio
async def test_background_job_created():
    """Verify BackgroundJob created during sync."""
    # Setup: create mock session, mock BackgroundJob model
    # Execute: call run_daily_sync()
    # Assert: verify db.add() was called with BackgroundJob instance
    # Assert: verify db.commit() was called
```

---

## Shared Patterns

### Session-Per-Operation (All Services)

**Source:** `backend/app/db/base.py`, used in all service files
**Apply to:** All four service files (scheduler, scoring_job, ai_autofill modifications)

```python
# Pattern: Always use async context manager to ensure session closes
async with get_session_factory()() as db:
    # ... do DB work ...
    await db.commit()
# Session automatically closed here; safe for external API calls
```

**Critical:** Never hold a session open during `await` calls to external APIs (BrainSuite, platform APIs, Gemini, Whisper). Open session → read/write → commit → close → THEN do HTTP calls.

### Error Handling with Traceback Truncation (All Services)

**Source:** `backend/app/services/sync/scheduler.py` lines 198–223
**Apply to:** All four service files

```python
import traceback

try:
    # ... operation ...
except Exception as e:
    logger.error(f"Operation failed: {type(e).__name__}: {e}")
    tb_str = traceback.format_exc()[:10000]  # D-13: truncate at 10KB for MON-05
    error_dict = {
        "type": type(e).__name__,
        "message": str(e),
        "traceback": tb_str,
    }
    # Pass to update_background_job(job_id, status="FAILED", error=error_dict)
```

### Timestamp Management (All Service Updates)

**Source:** `backend/app/models/jobs.py`, used in job_tracker helpers
**Apply to:** All BackgroundJob updates via job_tracker

```python
from datetime import datetime

# On job creation: started_at = datetime.utcnow()
job = BackgroundJob(
    ...,
    started_at=datetime.utcnow(),
)

# On job completion/failure: ended_at = datetime.utcnow()
job.status = "COMPLETE"  # or "FAILED"
job.ended_at = datetime.utcnow()
```

### JSONB Output Serialization (All Service Types)

**Source:** `backend/app/models/jobs.py` line 19 (JSONB column), `backend/app/services/sync/scoring_job.py` (score data format)
**Apply to:** All four service types before calling `update_background_job(..., output=dict)`

```python
# Pattern: SQLAlchemy JSONB column automatically serializes Python dict
output_dict = {
    "key1": "value1",
    "key2": 123,
    "key3": ["list", "of", "items"],
}
# Pass directly to update_background_job() — SQLAlchemy handles JSON conversion
await update_background_job(
    job_id=bg_job_id,
    status="COMPLETE",
    output=output_dict,
)
```

---

## No Analog Found

No files without analogs — all five files have clear existing patterns or templates.

---

## Pattern Reference by Decision ID

| Decision | Pattern Location | Key Code |
|----------|------------------|----------|
| D-01 (SyncJob + BackgroundJob parallel write) | `scheduler.py` L151–162 + job_tracker helper | Create both in same DB session, flush SyncJob, create BackgroundJob with link in metadata |
| D-02 (org_id sourcing) | `scheduler.py` L138–142 | `connection.organization_id` from PlatformConnection fetch |
| D-03 (job_type values) | RESEARCH.md list | `"sync_daily"`, `"sync_full"`, `"sync_initial"`, `"sync_historical"`, `"download"`, `"autofill"`, `"scoring"` |
| D-04–D-06 (progress tracking) | `scheduler.py` L362–387 (download loop example) | Set `progress_total` on RUNNING, increment `progress_current` per item |
| D-07 (per-asset scoring jobs) | `scoring_job.py` L304+ | One BackgroundJob per asset, created in _process_asset() |
| D-08 (Scoring output schema) | `scoring_job.py` L484 context | `{"score": float, "endpoint_type": str, "brainsuite_job_id": str, "dimensions": dict}` |
| D-09 (Scoring metadata) | CONTEXT.md | `{"asset_id": str, "creative_score_result_id": str}` in metadata_ JSONB |
| D-10 (Autofill output schema) | `ai_autofill.py` example in RESEARCH.md | `{"fields": [...], "whisper_transcript": str, "language": str}` |
| D-11 (Download output schema) | RESEARCH.md | `{"downloaded": [{"asset_id": str, "url": str}], "failed": [{"asset_id": str, "error": str}]}` |
| D-12 (Sync output schema) | RESEARCH.md | `{"platform": str, "sync_job_id": str, "records_fetched": int, "records_processed": int}` |
| D-13 (Error schema truncation) | `scheduler.py` L276 | `traceback.format_exc()[:10000]` in error_dict |
| D-14 (Session-per-operation) | `db/base.py` L20–26, all services | Always close session before external HTTP calls |
| D-15 (Progress increments use fresh session) | `scheduler.py` L362–387 | Each loop iteration opens/closes session for progress update |
| D-16 (job_tracker helpers) | job_tracker.py NEW | `create_background_job()` and `update_background_job()` functions |

---

## Metadata

**Analog search scope:** 
- `backend/app/services/sync/*.py` — scheduler, scoring_job, ai_autofill, maintenance
- `backend/app/db/base.py` — session factory pattern
- `backend/app/models/jobs.py` — BackgroundJob schema
- `backend/tests/services/test_*.py` — test patterns

**Files scanned:** 8

**Pattern extraction date:** 2026-05-08

**Key confidence notes:**
- Session-per-operation pattern: **HIGH** — established in all existing services
- Error handling: **HIGH** — template exists at scheduler.py L198–223
- JSONB serialization: **HIGH** — BackgroundJob model already uses JSONB columns
- Output schemas (D-08–D-12): **MEDIUM** — defined in CONTEXT.md; verification against Phase 19 UI deferred
- Per-asset vs. per-batch (D-07): **HIGH** — existing scoring_job.py L304+ shows per-asset pattern; new BackgroundJob follows same approach
