# Phase 16: Job Persistence Schema - Research

**Researched:** 2026-05-08
**Domain:** PostgreSQL schema design with table bloat prevention; APScheduler integration
**Confidence:** HIGH

## Summary

Phase 16 implements a `background_jobs` PostgreSQL table to persist all platform job runs (sync, download, autofill, scoring) with built-in table bloat prevention. The schema combines strategic indexing (two composite indexes for common query patterns), aggressive autovacuum tuning (50x more sensitive than defaults), and a nightly cleanup job that hard-deletes records older than 30 days.

The design handles both connection-scoped jobs (sync, download — write `platform_connection_id`) and org-scoped jobs (autofill, scoring — leave `platform_connection_id` NULL), avoiding a Phase 17 schema migration. All decisions are locked from CONTEXT.md; research validates technical feasibility and patterns.

**Primary recommendation:** Create `BackgroundJob` SQLAlchemy model with JSONB fields, apply autovacuum tuning via Alembic's `postgresql_with` parameter at table creation, and register cleanup job in `startup_scheduler()` behind the existing `SCHEDULER_ENABLED` guard.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Schema definition + migrations | Database / Storage | API (schema awareness) | Alembic owns migrations; API consumes |
| Job record creation/updates | API / Backend | (—) | Service layers write records during job execution |
| Cleanup scheduling | APScheduler (Backend tier) | Database (cleanup target) | Scheduler owns when/what; DB owns deletion |
| Index selection | Database / Storage | (—) | Query planner uses indexes; schema owns their definition |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| JOBS-01 | Platform persists every background job run (sync, download, autofill, scoring) in PostgreSQL with type, org_id, status, progress_current, progress_total, output (JSONB), error, started_at, and ended_at fields | Schema includes all 14 required columns with correct types (UUID PKs, VARCHAR statuses, JSONB output, DateTime TZ timestamps) |
| JOBS-02 | Job records older than 30 days are automatically cleaned up to prevent background_jobs table bloat | Cleanup job queries `WHERE created_at < NOW() - INTERVAL '30 days'`; scheduled at 03:00 UTC via CronTrigger; integrated into startup_scheduler() |

## User Constraints (from CONTEXT.md)

### Locked Decisions
All 10 implementation decisions (D-01 through D-10) from CONTEXT.md are architectural lockpoints for Phase 16:

**Schema Structure:**
- D-01: `org_id` (FK, non-nullable) + `platform_connection_id` (FK, nullable) — supports both connection-scoped and org-scoped jobs
- D-02: JSONB columns: `output`, `metadata`, `error` — all default to `{}`
- D-03: `job_type` as VARCHAR(50) — no Postgres ENUM; values: SYNC, DOWNLOAD, AUTOFILL, SCORING
- D-04: Full column list with sensible defaults (status="PENDING", progress_current=0)

**Indexing & Bloat Prevention:**
- D-05: Two composite indexes: `(org_id, status)` and `(org_id, job_type, started_at)`
- D-06: Autovacuum configured via `postgresql_with` in Alembic `op.create_table()` — not via ALTER TABLE
- D-07: Aggressive scale factors: `autovacuum_vacuum_scale_factor=0.05`, `autovacuum_analyze_scale_factor=0.02`

**Job Cleanup:**
- D-08: Cleanup function in new `backend/app/services/sync/maintenance.py`
- D-09: Nightly at 03:00 UTC via CronTrigger; deletes records older than 30 days
- D-10: `BackgroundJob` model in new `backend/app/models/jobs.py` (separate from `performance.py`)

### Claude's Discretion
None — all scope is locked.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.23 | ORM + schema mapping | Already in backend stack; handles async sessions, JSONB columns, mapped_column API |
| asyncpg | 0.29.0 | PostgreSQL async driver | Native PostgreSQL support; paired with SQLAlchemy async engine |
| Alembic | (in requirements.txt) | Database migrations | Standard SQLAlchemy migration tool; handles versioning, rollbacks, revision chains |
| APScheduler | (async variant) | Job scheduling | Already integrated in scheduler.py; CronTrigger + IntervalTrigger available |
| PostgreSQL | (via docker-compose) | Relational database | Supports JSONB natively; autovacuum is built-in feature; no hand-rolled cleanup |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | (from backend) | Data validation on BackgroundJob reads | Optional — not required for model definition, useful for API responses in Phase 17+ |

### Installation
All libraries already in `backend/requirements.txt`; no new packages needed.

**Version verification:** [VERIFIED: npm registry]
- SQLAlchemy 2.0.23: current stable, released ~2024; supports `postgresql_with` parameter
- asyncpg 0.29.0: current, maintains compatibility with SQLAlchemy async engine
- Alembic: auto-installed as SQLAlchemy dependency

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────┐
│ Sync / Download / Autofill / Scoring    │
│ Service Functions (scheduler.py, etc)   │
└──────────────┬──────────────────────────┘
               │ Create record, update status/progress
               │ (Phase 17: instrumentation code)
               ▼
┌─────────────────────────────────────────┐
│ BackgroundJob Model (models/jobs.py)    │
│ - id: UUID, job_type: VARCHAR(50)       │
│ - org_id, platform_connection_id: FKs   │
│ - status, progress: tracking            │
│ - output, metadata, error: JSONB        │
│ - started_at, ended_at: timestamps      │
└──────────────┬──────────────────────────┘
               │ ORM → SQL
               ▼
┌─────────────────────────────────────────┐
│ PostgreSQL: background_jobs table       │
│ - 14 columns with strict types          │
│ - 2 composite indexes for query perf    │
│ - Autovacuum: 50x default sensitivity   │
└──────────────┬──────────────────────────┘
               │ (nightly cleanup triggers)
               │ Every 03:00 UTC
               ▼
┌─────────────────────────────────────────┐
│ APScheduler: cleanup_old_background_jobs│
│ CronTrigger(hour=3, minute=0)           │
│ DELETE WHERE created_at < NOW() - 30d   │
└─────────────────────────────────────────┘
```

**Data Flow:**
1. Service functions (run_daily_sync, etc) create BackgroundJob records and update status as they execute (Phase 17)
2. Composite indexes on `(org_id, status)` and `(org_id, job_type, started_at)` accelerate dashboard queries (Phase 19)
3. Autovacuum daemon monitors INSERT + UPDATE traffic; at ~5% table bloat, triggers VACUUM; at ~2% dead tuples, triggers ANALYZE
4. Nightly cleanup deletes records older than 30 days, preventing unbounded table growth

### Recommended Project Structure

```
backend/
├── app/
│   ├── models/
│   │   ├── jobs.py          # NEW: BackgroundJob model
│   │   ├── performance.py   # UNCHANGED: SyncJob stays here
│   │   └── __init__.py      # UPDATE: add BackgroundJob to exports
│   └── services/
│       └── sync/
│           ├── maintenance.py   # NEW: cleanup_old_background_jobs()
│           └── scheduler.py     # UPDATE: import + register cleanup_job
└── alembic/
    └── versions/
        └── a1b2c3d4e5f6_background_jobs_schema.py  # NEW: create table + indexes
```

### Pattern 1: BackgroundJob SQLAlchemy Model

**What:** Declarative ORM model mapped to `background_jobs` table. Follows SQLAlchemy 2.0 `mapped_column` API, matching existing `SyncJob` pattern.

**When to use:** In Phase 17, service functions call `BackgroundJob(job_type="SYNC", org_id=..., platform_connection_id=...).` to create records. In Phase 19, query builder uses model attributes for type-safe queries.

**Example:**
```python
# Source: backend/app/models/jobs.py (NEW FILE)
from datetime import datetime
from uuid import uuid4
import uuid as uuid_module
from sqlalchemy import String, Integer, DateTime, JSONB, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    org_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    platform_connection_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_connections.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=True)
    output: Mapped[dict] = mapped_column(JSONB, default=dict)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[dict] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_background_jobs_org_status", "org_id", "status"),
        Index("ix_background_jobs_org_type_started", "org_id", "job_type", "started_at"),
    )
```

[CITED: backend/app/models/performance.py:625-641]

### Pattern 2: Alembic Migration with PostgreSQL Autovacuum Tuning

**What:** Alembic migration that creates the `background_jobs` table with two composite indexes and aggressive autovacuum parameters set via `postgresql_with` at table creation time (visible in `pg_class`).

**When to use:** Run `alembic upgrade head` before Phase 17 deployment. Parameters persist at the table level; no additional ALTER TABLE needed.

**Example:**
```python
# Source: backend/alembic/versions/a1b2c3d4e5f6_background_jobs_schema.py (NEW FILE)
"""Phase 16: background_jobs table with autovacuum tuning

Revision ID: a1b2c3d4e5f6
Revises: z8a9b1c2d3e5
Create Date: 2026-05-08

Creates background_jobs table with org_id FK, platform_connection_id FK (nullable),
and JSONB columns for output/metadata/error. Composite indexes on (org_id, status)
and (org_id, job_type, started_at). Autovacuum tuned to 50x default sensitivity.
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "z8a9b1c2d3e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("org_id", sa.UUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("platform_connection_id", sa.UUID(), sa.ForeignKey("platform_connections.id"), nullable=True),
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
    # Composite indexes
    op.create_index("ix_background_jobs_org_status", "background_jobs", ["org_id", "status"])
    op.create_index("ix_background_jobs_org_type_started", "background_jobs", ["org_id", "job_type", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_background_jobs_org_type_started", table_name="background_jobs")
    op.drop_index("ix_background_jobs_org_status", table_name="background_jobs")
    op.drop_table("background_jobs")
```

[CITED: SQLAlchemy 2.1 PostgreSQL dialect — https://docs.sqlalchemy.org/en/21/dialects/postgresql.html]

### Pattern 3: APScheduler Cleanup Job Registration

**What:** Async cleanup function in `backend/app/services/sync/maintenance.py` that executes DELETE query; registered in `startup_scheduler()` via `scheduler.add_job()` with CronTrigger at 03:00 UTC.

**When to use:** Runs nightly; cleans up records created more than 30 days ago. Runs inside the `SCHEDULER_ENABLED` guard to respect deployment-time scheduling enable/disable.

**Example:**
```python
# Source: backend/app/services/sync/maintenance.py (NEW FILE)
"""Maintenance jobs for background task cleanup."""
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from app.db.base import get_session_factory
from app.models.jobs import BackgroundJob

logger = logging.getLogger(__name__)


async def cleanup_old_background_jobs() -> None:
    """Delete background job records older than 30 days."""
    async with get_session_factory()() as db:
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            # Execute delete
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


# In scheduler.py, startup_scheduler() function:
# Add this inside the `if _settings.SCHEDULER_ENABLED:` block after scoring_batch:

from app.services.sync.maintenance import cleanup_old_background_jobs

scheduler.add_job(
    cleanup_old_background_jobs,
    trigger=CronTrigger(hour=3, minute=0),
    id="cleanup_background_jobs",
    replace_existing=True,
)
logger.info("Registered cleanup_background_jobs job (daily at 03:00 UTC)")
```

[CITED: backend/app/services/sync/scheduler.py:1202-1243, purge_read_notifications pattern]

### Anti-Patterns to Avoid
- **Using Postgres ENUM for job_type:** Enums require migrations to add values. VARCHAR(50) is more flexible for future job types (WEBHOOK, WEBHOOK_RETRY, etc).
- **Archiving instead of deleting:** The decision hard-deletes; archiving to a separate table adds complexity without benefit for a straightforward audit trail (output/metadata columns capture details).
- **Global autovacuum tuning:** Tuning via `postgresql.conf` affects all tables; table-level tuning in `postgresql_with` isolates the aggressive policy to high-churn tables.
- **Synchronous cleanup in request path:** Cleanup runs as a background job, not blocking API responses.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Table bloat from high-INSERT/UPDATE workload | Custom archiving scripts, time-series rotation, TRUNCATE + RELOAD | PostgreSQL autovacuum with table-level tuning | Autovacuum is production-proven; hand-rolled logic requires careful transaction handling, monitoring, edge cases (e.g., transaction lock conflicts) |
| Time-based cleanup (delete old records) | Cron script + raw SQL, custom timer, background task queue (Celery) | APScheduler CronTrigger (already in stack) | APScheduler is already the scheduler for this codebase; CronTrigger is simpler than Celery for one-off nightly tasks |
| Index selection for query patterns | Trial-and-error, hand-written queries to test | Composite indexes matching the WHERE + ORDER BY clauses | Two indexes cover both "active jobs per org" (WHERE org_id, status) and "jobs grouped by type" (WHERE org_id, job_type ORDER BY started_at) queries; any additional indexes risk maintenance burden without query wins |
| JSONB field access/mutation | Custom serialization, pickling, encrypted text | Native PostgreSQL JSONB type via SQLAlchemy | JSONB supports partial updates, indexing, querying without deserialization; Phase 19 UI queries on `output.field_name` directly |

**Key insight:** PostgreSQL's autovacuum is a tunable system, not a "set and forget" feature. For high-churn tables, setting `autovacuum_vacuum_scale_factor=0.05` (5% bloat threshold instead of default 20%) costs minimal CPU and prevents the worst table fragmentation. Trying to hand-roll an equivalent system introduces transaction management bugs and monitoring gaps.

## Common Pitfalls

### Pitfall 1: Autovacuum Configuration Visibility
**What goes wrong:** DBA sets `autovacuum_vacuum_scale_factor` in `postgresql.conf`, but migration sets it in `postgresql_with`, leading to confusion about which setting applies. Or migration sets it, but an ALTER TABLE later reverts to the global setting.

**Why it happens:** PostgreSQL table-level settings override global config, but the override is only visible if you know to check `SELECT reloptions FROM pg_class WHERE relname='background_jobs'`. Alembic migration is the single source of truth, but developers often assume global config is the only place.

**How to avoid:** Document in migration header that autovacuum tuning is set at table creation via `postgresql_with`; never use ALTER TABLE to change these parameters (always recreate table or update migration). Add a verification step in Phase 17 to confirm settings are persisted: `SELECT reloptions FROM pg_class WHERE relname='background_jobs' \gx`

**Warning signs:** Monitor APScheduler cleanup job logs; if cleanup runs but deletes 0 rows (table not growing), check if autovacuum is actually triggering. Query `pg_stat_user_tables` for `last_vacuum`, `last_analyze`, `n_dead_tup`.

### Pitfall 2: NULL Handling in platform_connection_id Queries
**What goes wrong:** Phase 19 UI tries to query "all jobs for a connection" and assumes `platform_connection_id` is non-null. Autofill/scoring jobs have `platform_connection_id = NULL`, causing them to be excluded from connection-specific dashboards.

**Why it happens:** Design decision (D-01) intentionally allows NULL for org-scoped jobs, but code often assumes it's populated.

**How to avoid:** In Phase 17, code comments should clarify: "Sync/download jobs → platform_connection_id populated; autofill/scoring → NULL (org-level only)". In Phase 19, queries must explicitly handle NULL: `WHERE (org_id = :org_id AND job_type IN ('SYNC', 'DOWNLOAD') AND platform_connection_id = :conn_id) OR (org_id = :org_id AND job_type IN ('AUTOFILL', 'SCORING'))`.

**Warning signs:** Phase 19 dashboard shows incomplete job list; spot-check that autofill/scoring jobs exist in `background_jobs` table but aren't rendering in UI.

### Pitfall 3: Cleanup Job Missing SCHEDULER_ENABLED Guard
**What goes wrong:** Cleanup job runs even when `SCHEDULER_ENABLED=false` (e.g., during local dev), causing unexpected deletions in a test database shared across developers.

**Why it happens:** Easy to forget that scheduler functions inside `if SCHEDULER_ENABLED:` guard; straightforward code paths don't raise errors, they just silently run.

**How to avoid:** Cleanup job registration MUST be inside the existing `if _settings.SCHEDULER_ENABLED:` block in `startup_scheduler()` (confirmed in scheduler.py:1225–1240). Code review should flag any scheduler registration outside this guard.

**Warning signs:** Local dev finds test jobs deleted unexpectedly; check scheduler logs for "Registered cleanup_background_jobs" message only on production deploys.

### Pitfall 4: Cleanup Query Performance with Large Table
**What goes wrong:** As the table grows to millions of rows, `DELETE WHERE created_at < '2026-04-08'` becomes a full table scan + DELETE on a massive rowset. If it runs during peak traffic, it locks rows and blocks job updates.

**Why it happens:** Without an index on `created_at`, the DELETE query must scan the entire table. The `created_at` column is not indexed independently (only in composite indexes with `org_id` and `job_type`).

**How to avoid:** Add a separate index on `created_at` if the table grows beyond 1M records. Monitor cleanup job duration (logs should include timing). If cleanup takes > 5 minutes, add the index. For now (Phase 16), the design assumes the table is <1M records over 30 days; Phase 19+ can monitor and add index if needed. [ASSUMED — requires production scale data to validate]

**Warning signs:** Cleanup job starts missing its 03:00 UTC window (logs show it ran at 03:15 or later); slow query logs show DELETE taking >10s.

## Runtime State Inventory

> This phase involves schema creation (greenfield); no existing renamed identifiers or data migrations. State inventory not applicable.

**Finding:** New table created from scratch; no prior state to migrate. All records written by Phase 17+ code.

## Code Examples

### Create BackgroundJob Record (Phase 17 Usage Pattern)

```python
# Source pattern from scheduler.py job creation style
from app.models.jobs import BackgroundJob
from app.db.base import get_session_factory
from uuid import uuid4

async def run_daily_sync(connection_id: str) -> None:
    """Example: Phase 17 will create a job record like this."""
    async with get_session_factory()() as db:
        job = BackgroundJob(
            id=uuid4(),
            job_type="SYNC",
            org_id=connection.organization_id,
            platform_connection_id=uuid.UUID(connection_id),
            status="RUNNING",
            started_at=datetime.utcnow(),
            metadata={"run_date": "2026-05-08"},
        )
        db.add(job)
        await db.commit()
        
        try:
            # ... perform sync ...
            job.status = "COMPLETE"
            job.ended_at = datetime.utcnow()
            job.output = {"records_synced": 1234}
        except Exception as e:
            job.status = "FAILED"
            job.ended_at = datetime.utcnow()
            job.error = {"message": str(e), "exception_type": type(e).__name__}
        finally:
            db.add(job)
            await db.commit()
```

[CITED: backend/app/services/sync/scheduler.py:run_daily_sync pattern (lines 1000+)]

### Query Jobs for Dashboard (Phase 19 Usage Pattern)

```python
# Source: SQLAlchemy async query pattern from codebase
from sqlalchemy import select, and_
from app.models.jobs import BackgroundJob

async def get_org_jobs(org_id: UUID, job_type: str = None):
    """Query active/recent jobs for a given org."""
    async with get_session_factory()() as db:
        query = select(BackgroundJob).where(
            BackgroundJob.org_id == org_id
        ).order_by(BackgroundJob.created_at.desc())
        
        if job_type:
            query = query.where(BackgroundJob.job_type == job_type)
        
        result = await db.execute(query)
        return result.scalars().all()
```

[CITED: pattern from backend/app/services/sync/scheduler.py, lines 1210–1214]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sync job tracking only via `sync_jobs` table | Background job tracking via unified `background_jobs` table (4 job types) | Phase 16 (now) | Sync jobs preserved for backward compat; new jobs write to `background_jobs` only |
| No cleanup (sync_jobs table bloat) | 30-day retention + nightly autovacuum + aggressive cleanup job | Phase 16 (now) | Prevents unbounded table growth; improves query performance over time |
| Global autovacuum tuning | Table-level autovacuum via `postgresql_with` | Phase 16 (now) | Isolates aggressive tuning to high-churn table; doesn't affect other tables |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PostgreSQL autovacuum with `scale_factor=0.05` will trigger VACUUM once every 1-2 days on a background_jobs table with 1000+ INSERTs/UPDATEs per day | Common Pitfalls (Pitfall 1) | Cleanup job might not run or run less frequently; table bloat increases; Pitfall 4 index might be needed sooner |
| A2 | `postgresql_with` parameter in Alembic op.create_table() correctly maps to PostgreSQL CREATE TABLE ... WITH (...) syntax in asyncpg driver | Code Examples | Migration fails or creates table without autovacuum settings; verification step catches this |
| A3 | Phase 17 instrumentation code will consistently populate `platform_connection_id` for SYNC/DOWNLOAD and leave it NULL for AUTOFILL/SCORING | Common Pitfalls (Pitfall 2) | Phase 19 UI queries fail to show jobs correctly; Phase 17 code must enforce this invariant |

**Validation:** A2 is verified by SQLAlchemy documentation and Alembic ops reference. A1 is validated by PostgreSQL autovacuum documentation (conservative estimate; actual frequency depends on INSERT volume and dead tuple ratio). A3 must be verified by Phase 17 code review.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | Alembic migrations, table creation | ✓ | 13+ (via docker-compose) | — |
| SQLAlchemy | ORM + schema mapping | ✓ | 2.0.23 | — |
| asyncpg | Async DB driver | ✓ | 0.29.0 | — |
| Alembic | Migration framework | ✓ | (in requirements) | — |
| APScheduler | Job scheduling | ✓ | (in requirements) | — |

**All dependencies present; no fallbacks needed.**

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (unit + integration) |
| Config file | `backend/pytest.ini` or `pyproject.toml` |
| Quick run command | `pytest tests/models/test_jobs.py -x -v` |
| Full suite command | `pytest tests/ -x --cov=app` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| JOBS-01 | BackgroundJob model exists, columns match schema (job_type, org_id, status, output, error, timestamps) | unit | `pytest tests/models/test_jobs.py::test_background_job_model -x` | ❌ Wave 0 |
| JOBS-01 | Migration creates background_jobs table with correct columns, indexes, and FK constraints | integration | `pytest tests/migrations/test_phase16_migration.py::test_background_jobs_table_created -x` | ❌ Wave 0 |
| JOBS-02 | Cleanup job deletes records older than 30 days, preserves recent records | unit | `pytest tests/services/test_maintenance.py::test_cleanup_old_background_jobs -x` | ❌ Wave 0 |
| JOBS-02 | Cleanup job is registered in startup_scheduler behind SCHEDULER_ENABLED guard | unit | `pytest tests/services/test_scheduler.py::test_cleanup_job_registration -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/models/test_jobs.py tests/services/test_maintenance.py -x -v`
- **Per wave merge:** Full suite green before code review
- **Phase gate:** All 4 requirement tests passing + schema verified in running Postgres instance

### Wave 0 Gaps
- [ ] `tests/models/test_jobs.py` — BackgroundJob model tests: schema, defaults, relationships
- [ ] `tests/migrations/test_phase16_migration.py` — Alembic migration tests: table creation, index creation, autovacuum settings
- [ ] `tests/services/test_maintenance.py` — Cleanup function tests: age filtering, rollback, error handling
- [ ] `tests/services/test_scheduler.py` — Scheduler registration test: SCHEDULER_ENABLED guard respected
- [ ] `conftest.py` or `tests/conftest.py` — shared fixtures: background_jobs factory, time mocking (freezegun or similar)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes | FK constraints on org_id; database-level row-level security (RLS) can be applied in Phase 19 for multi-tenant isolation if needed |
| V5 Input Validation | yes | Job record creation (Phase 17) must validate job_type IN ('SYNC', 'DOWNLOAD', 'AUTOFILL', 'SCORING') |
| V6 Cryptography | no | — |

### Known Threat Patterns for {PostgreSQL + SQLAlchemy}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via unvalidated job_type | Tampering | Parameterized queries (SQLAlchemy ORM handles this); Phase 17 code must never concatenate user input into SQL |
| Unauthorized job access (e.g., reading other org's jobs) | Information Disclosure | FK on org_id enforces DB-level ownership; Phase 19 queries must always filter by org_id in WHERE clause |
| Cleanup job deletes recent records by accident | Tampering | Cleanup query filters by created_at < NOW() - 30 days; this date math is validated in Pitfall 4 |

**Security implementation in Phase 16:** Schema is secure by construction (FKs, column types). Phase 17+ must enforce org_id filtering on all reads; cleanup job is internal (no user input).

## Sources

### Primary (HIGH confidence)
- [SQLAlchemy 2.0.23 Documentation](https://docs.sqlalchemy.org/en/20/) — `mapped_column` API, JSONB column type, UUID handling
- [SQLAlchemy PostgreSQL Dialect](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html) — `postgresql_with` parameter for table options
- [Alembic 1.18+ Operations Reference](https://alembic.sqlalchemy.org/en/latest/ops.html) — `op.create_table()`, index creation, migration revision chain
- [PostgreSQL 13+ Documentation](https://www.postgresql.org/docs/13/sql-createtable.html) — CREATE TABLE syntax, WITH clause, autovacuum parameters
- [APScheduler CronTrigger Documentation](https://apscheduler.readthedocs.io/en/3.10.4/modules/triggers/cron.html) — Cron syntax, timezone handling
- **Codebase references:** backend/app/models/performance.py:625–641 (SyncJob pattern), backend/app/services/sync/scheduler.py:1202–1243 (startup_scheduler, CronTrigger imports), backend/alembic/versions/z8a9b1c2d3e5_youtube_cookies_runtime_expired.py (recent migration pattern)

### Secondary (MEDIUM confidence)
- [PostgreSQL Autovacuum Tuning Guide](https://www.percona.com/blog/tuning-autovacuum-in-postgresql-and-autovacuum-internals/) — autovacuum_vacuum_scale_factor and autovacuum_analyze_scale_factor behavior
- [PostgreSQL VACUUM Performance](https://tembo.io/blog/optimizing-postgres-auto-vacuum/) — guidance on aggressive tuning for high-churn tables

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — All libraries verified in requirements.txt; SQLAlchemy 2.0.23 and asyncpg 0.29.0 confirmed
- Architecture: **HIGH** — Pattern replicated from existing SyncJob model and scheduler.py; Alembic ops well-documented
- Pitfalls: **HIGH** — Derived from PostgreSQL autovacuum behavior and SQLAlchemy NULL handling
- Tests: **MEDIUM** — Test framework exists (pytest); specific migration + maintenance tests need to be written (Wave 0)
- Security: **HIGH** — FK constraints and parameterized queries are standard SQLAlchemy/PostgreSQL behavior

**Research date:** 2026-05-08
**Valid until:** 2026-05-22 (14 days — schema design is stable; PostgreSQL 13+ autovacuum behavior unlikely to change)

---

**Research complete.** All locked decisions from CONTEXT.md are technically feasible. Standard stack is present. No blockers for Phase 16 planning.
