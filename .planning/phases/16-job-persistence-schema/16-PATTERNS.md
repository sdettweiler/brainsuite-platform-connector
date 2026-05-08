# Phase 16: Job Persistence Schema - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 5 (1 new model, 1 new migration, 1 new service, 2 modified)
**Analogs found:** 5/5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/models/jobs.py` | model | CRUD | `backend/app/models/performance.py` (SyncJob) | exact |
| `backend/app/models/__init__.py` | config | CRUD | `backend/app/models/__init__.py` (existing) | exact |
| `backend/alembic/versions/{new_revision}.py` | migration | CRUD | `backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py` | exact |
| `backend/app/services/sync/maintenance.py` | service | CRUD | `backend/app/services/sync/scheduler.py` (purge_read_notifications) | exact |
| `backend/app/services/sync/scheduler.py` | service | CRUD | `backend/app/services/sync/scheduler.py` (startup_scheduler) | exact |

## Pattern Assignments

### `backend/app/models/jobs.py` (model, CRUD)

**Analog:** `backend/app/models/performance.py` (SyncJob class, lines 625–641)

**Imports pattern** (lines 1–8):
```python
import uuid
from datetime import datetime, date
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Date, Text, Integer, Float, Numeric, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base
```

**Model structure with SQLAlchemy 2.0 mapped_column API** (lines 625–641):
```python
class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    platform_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_connections.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=True)
    output: Mapped[dict] = mapped_column(JSONB, default=dict)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[dict] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_background_jobs_org_status", "org_id", "status"),
        Index("ix_background_jobs_org_type_started", "org_id", "job_type", "started_at"),
    )
```

**Key patterns to copy:**
- UUID PK with `UUID(as_uuid=True), primary_key=True, default=uuid.uuid4`
- String columns with `String(size)`, nullable specified
- FK references with `ForeignKey("table.column")` and explicit nullable
- JSONB columns with `JSONB, default=dict`
- DateTime with `DateTime(timezone=True)` for all timestamps
- Default values via `default=` or `server_default=` (see migration for server_default)
- Composite indexes via `__table_args__` tuple with Index objects

---

### `backend/app/models/__init__.py` (config, CRUD)

**Analog:** `backend/app/models/__init__.py` (existing file, lines 1–32)

**Current exports pattern** (lines 1–32):
```python
from app.models.user import User, Organization, OrganizationRole, RefreshToken
from app.models.platform import PlatformConnection, BrainsuiteApp
from app.models.creative import CreativeAsset, Project, AssetProjectMapping, AssetMetadataValue
from app.models.metadata import MetadataField, MetadataFieldValue
from app.models.performance import (
    MetaRawPerformance,
    TikTokRawPerformance,
    GoogleAdsRawPerformance,
    Dv360RawPerformance,
    HarmonizedPerformance,
    CurrencyRate,
    SyncJob,
)
from app.models.scoring import CreativeScoreResult
from app.models.ai_inference import AIInferenceTracking
from app.models.brainsuite_config import OrgBrainsuiteConfig, OrgBrainsuiteFieldMapping
from app.models.system_config import SystemConfig

__all__ = [
    "User", "Organization", "OrganizationRole", "RefreshToken",
    "PlatformConnection", "BrainsuiteApp",
    "CreativeAsset", "Project", "AssetProjectMapping", "AssetMetadataValue",
    "MetadataField", "MetadataFieldValue",
    "MetaRawPerformance", "TikTokRawPerformance", "GoogleAdsRawPerformance",
    "Dv360RawPerformance",
    "HarmonizedPerformance", "CurrencyRate", "SyncJob",
    "CreativeScoreResult",
    "AIInferenceTracking",
    "OrgBrainsuiteConfig",
    "OrgBrainsuiteFieldMapping",
    "SystemConfig",
]
```

**Action:** Add import line:
```python
from app.models.jobs import BackgroundJob
```

Then add `"BackgroundJob"` to `__all__` list (alphabetically or grouped with other job models).

---

### `backend/alembic/versions/{new_revision}.py` (migration, CRUD)

**Analog:** `backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py` (lines 1–81)

**Migration header and setup** (lines 1–14):
```python
"""Phase 16: background_jobs table with autovacuum tuning

Revision ID: {next_hex_id}
Revises: c1d2e3f4a5b6
Create Date: 2026-05-08

Creates background_jobs table with org_id FK, platform_connection_id FK (nullable),
and JSONB columns for output/metadata/error. Composite indexes on (org_id, status)
and (org_id, job_type, started_at). Autovacuum tuned to 50x default sensitivity.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "{next_hex_id}"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None
```

**Create table pattern with postgresql_with for autovacuum tuning** (lines 17–60):
```python
def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("platform_connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("platform_connections.id"), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("progress_current", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer(), nullable=True),
        sa.Column("output", sa.JSONB(), nullable=False, server_default="{}"),
        sa.Column("metadata", sa.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error", sa.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # PostgreSQL-specific table options for aggressive autovacuum tuning
        postgresql_with={
            "autovacuum_vacuum_scale_factor": "0.05",
            "autovacuum_analyze_scale_factor": "0.02",
        },
    )
    
    # Composite indexes (matching composite index pattern from line 63–67 of s0t1u2v3w4x5)
    op.create_index("ix_background_jobs_org_status", "background_jobs", ["org_id", "status"])
    op.create_index("ix_background_jobs_org_type_started", "background_jobs", ["org_id", "job_type", "started_at"])
```

**Downgrade pattern** (lines 70–81 of s0t1u2v3w4x5):
```python
def downgrade() -> None:
    op.drop_index("ix_background_jobs_org_type_started", table_name="background_jobs")
    op.drop_index("ix_background_jobs_org_status", table_name="background_jobs")
    op.drop_table("background_jobs")
```

**Key patterns:**
- Use `postgresql.UUID(as_uuid=True)` for UUID columns (matches codebase pattern)
- Use `server_default=` for JSONB defaults: `server_default="{}"`
- Use `sa.func.now()` for timestamp server defaults
- Add `postgresql_with={...}` dict as final positional argument to `op.create_table()` for autovacuum settings
- Create indexes in separate `op.create_index()` calls after table creation
- Downgrade drops indexes before dropping table (reverse order)

---

### `backend/app/services/sync/maintenance.py` (service, CRUD)

**Analog:** `backend/app/services/sync/scheduler.py` (purge_read_notifications function, lines 1184–1199)

**Imports pattern** (from scheduler.py lines 1–19, 1184–1186):
```python
"""Maintenance jobs for background task cleanup."""
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, delete

from app.db.base import get_session_factory
from app.models.jobs import BackgroundJob

logger = logging.getLogger(__name__)
```

**Cleanup function pattern** (lines 1184–1199 of scheduler.py, adapted for BackgroundJob):
```python
async def cleanup_old_background_jobs() -> None:
    """Delete background job records older than 30 days."""
    from sqlalchemy import delete
    
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    async with get_session_factory()() as db:
        try:
            # Execute delete with parameterized query
            result = await db.execute(
                delete(BackgroundJob).where(BackgroundJob.created_at < cutoff_date)
            )
            deleted_count = result.rowcount
            
            await db.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} background job records older than 30 days")
            else:
                logger.debug("No background job records to clean up")
                
        except Exception as e:
            logger.error(f"Failed to clean up background jobs: {type(e).__name__}: {e}")
            await db.rollback()
            raise
```

**Key patterns to copy:**
- Use `async def` with no return type annotation (or `-> None`)
- Get DB session via `async with get_session_factory()() as db:`
- Use `delete(Model).where(...)` from SQLAlchemy ORM
- Call `await db.execute(...)` and check `result.rowcount`
- Call `await db.commit()` on success, `await db.rollback()` on exception
- Log at INFO level when rows deleted, DEBUG when zero rows
- Log exceptions at ERROR level with `type(e).__name__` for exception type

---

### `backend/app/services/sync/scheduler.py` (service, CRUD)

**Analog:** `backend/app/services/sync/scheduler.py` (startup_scheduler function and scheduler.add_job pattern, lines 1202–1243)

**Location for cleanup job registration** (lines 1225–1240):
```python
async def startup_scheduler(db_session=None) -> None:
    """Load all active connections and schedule their daily syncs.
    Also triggers initial sync for any connections that missed it."""
    from sqlalchemy import select
    from app.models.platform import PlatformConnection

    # ... existing code to load connections and schedule syncs ...

    from app.core.config import settings as _settings
    from app.services.sync.scoring_job import run_scoring_batch

    if _settings.SCHEDULER_ENABLED:
        scheduler.add_job(
            run_scoring_batch,
            trigger=IntervalTrigger(minutes=15),
            id="scoring_batch",
            replace_existing=True,
            max_instances=10,
        )
        logger.info("Registered scoring_batch job (every 15 minutes)")
        
        # ADD CLEANUP JOB HERE (after scoring_batch, same pattern)
        from app.services.sync.maintenance import cleanup_old_background_jobs
        
        scheduler.add_job(
            cleanup_old_background_jobs,
            trigger=CronTrigger(hour=3, minute=0),
            id="cleanup_background_jobs",
            replace_existing=True,
        )
        logger.info("Registered cleanup_background_jobs job (daily at 03:00 UTC)")
        
        # ... remaining purge_read_notifications registration ...
        scheduler.add_job(
            purge_read_notifications,
            trigger=CronTrigger(hour=3, minute=0),
            id="purge_read_notifications",
            replace_existing=True,
        )
        logger.info("Registered purge_read_notifications job (daily at 03:00 UTC)")
    else:
        logger.info("SCHEDULER_ENABLED=False — skipping scheduling")

    scheduler.start()
```

**Key patterns:**
- Import cleanup function inside the `if _settings.SCHEDULER_ENABLED:` block
- Use `scheduler.add_job(coroutine, trigger=CronTrigger(...), id="job_id", replace_existing=True)`
- CronTrigger syntax: `CronTrigger(hour=3, minute=0)` for 03:00 UTC
- Log registration with job name and schedule in human-readable format
- No `max_instances` parameter needed for cleanup job (runs once per day, no concurrency risk)

---

## Shared Patterns

### DateTime and Timezone Handling
**Source:** `backend/app/models/performance.py` (SyncJob model, line 632–633, 640)
**Apply to:** All models with timestamps in Phase 16 and beyond
```python
# In model definition:
started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

# In migration:
sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
```

All timestamp columns in this codebase use `DateTime(timezone=True)` to ensure UTC consistency across the backend and database.

### UUID Primary Keys and Foreign Keys
**Source:** `backend/app/models/performance.py` (SyncJob, lines 628–629) and `backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py` (lines 20–26)
**Apply to:** All new models and migrations in Phase 16+
```python
# In model:
id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

# In migration:
sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
```

### JSONB Default to Empty Dict
**Source:** `backend/app/models/performance.py` (SyncJob, line 639: `job_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)`)
**Apply to:** All JSONB columns (Phase 16 output/metadata/error)
```python
# In model (note: default=dict, not default={})
output: Mapped[dict] = mapped_column(JSONB, default=dict)
metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

# In migration (note: server_default as JSON string)
sa.Column("output", sa.JSONB(), nullable=False, server_default="{}"),
sa.Column("metadata", sa.JSONB(), nullable=False, server_default="{}"),
```

### Async Database Session Pattern
**Source:** `backend/app/services/sync/scheduler.py` (lines 1189–1199, 1210–1214)
**Apply to:** All service functions that read/write to the database
```python
async with get_session_factory()() as db:
    try:
        result = await db.execute(
            delete(Model).where(Model.field < value)
        )
        deleted = result.rowcount
        await db.commit()
    except Exception as e:
        logger.error(f"Error: {type(e).__name__}: {e}")
        await db.rollback()
        raise
```

Always:
- Use `async with get_session_factory()() as db:` to open a session
- Wrap operations in try/except to rollback on error
- Use `await db.commit()` after successful mutations
- Use `await db.rollback()` in exception handler
- Log exceptions with `type(e).__name__` for exception type

### APScheduler Job Registration Pattern
**Source:** `backend/app/services/sync/scheduler.py` (lines 1226–1233, 1234–1240)
**Apply to:** All new scheduled jobs in Phase 16+
```python
if _settings.SCHEDULER_ENABLED:
    scheduler.add_job(
        async_function,
        trigger=CronTrigger(hour=3, minute=0),  # or IntervalTrigger(minutes=15)
        id="unique_job_id",
        replace_existing=True,
    )
    logger.info("Registered {job_name} job (schedule description)")
```

Key points:
- Wrap all job registrations in `if _settings.SCHEDULER_ENABLED:` guard
- Use `replace_existing=True` to allow multiple deployments without duplicate jobs
- Pass async coroutine directly (scheduler handles `await`)
- Use descriptive ID strings
- Log after registration with human-readable schedule

---

## No Analog Found

All files have close matches in the codebase. No files require fallback to RESEARCH.md patterns.

## Metadata

**Analog search scope:** 
- `backend/app/models/` — model patterns
- `backend/app/services/sync/` — scheduler and maintenance patterns
- `backend/alembic/versions/` — migration patterns (UUID, JSONB, indexes, foreign keys)

**Files scanned:** 12 migrations, 5 model files, 1 scheduler file

**Pattern extraction date:** 2026-05-08

**Key confidence notes:**
- SyncJob model is exact analog for BackgroundJob (same SQLAlchemy version, same FK/JSONB patterns)
- purge_read_notifications function exactly matches cleanup_old_background_jobs requirements (async, delete with WHERE, commit/rollback)
- Alembic migration pattern verified across 5+ recent migrations in codebase; `postgresql_with` parameter is standard for table-level options
- APScheduler CronTrigger pattern is already in use for purge_read_notifications (same time, same guard)
- All imports and session management follow established async patterns in this codebase

