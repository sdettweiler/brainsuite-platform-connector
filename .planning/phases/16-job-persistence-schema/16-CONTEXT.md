# Phase 16: Job Persistence Schema - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Create the `background_jobs` PostgreSQL table with all required columns, composite indexes, aggressive autovacuum tuning, a nightly APScheduler cleanup job, and an Alembic migration. No job instrumentation code (Phase 17), no SSE (Phase 18), no UI (Phase 19). The schema must be complete enough that Phase 17 can write all four job types (sync, download, autofill, scoring) without a second migration.

</domain>

<decisions>
## Implementation Decisions

### Schema Columns
- **D-01:** Include `org_id` (FK → organizations.id, non-nullable) AND `platform_connection_id` (FK → platform_connections.id, nullable). Sync and download jobs populate `platform_connection_id`; autofill and scoring leave it NULL. This avoids a Phase 17 schema migration.
- **D-02:** Three JSONB columns — `output` (job payload: Gemini fields, download manifest, per-asset scores), `metadata` (external IDs envelope: brainsuite_job_id, platform_run_id, etc.), `error` (structured: `{message, traceback, exception_type}`). All default to `{}`.
- **D-03:** `job_type` as `VARCHAR(50)` — consistent with existing `SyncJob.job_type = String(50)`. No Postgres ENUM. Values: SYNC, DOWNLOAD, AUTOFILL, SCORING.
- **D-04:** Required columns per JOBS-01: `id` (UUID PK), `job_type` (VARCHAR 50), `org_id` (UUID FK), `platform_connection_id` (UUID FK nullable), `status` (VARCHAR 50, default PENDING), `progress_current` (Integer, default 0), `progress_total` (Integer, nullable), `output` (JSONB, default {}), `metadata` (JSONB, default {}), `error` (JSONB, nullable), `started_at` (DateTime TZ nullable), `ended_at` (DateTime TZ nullable), `created_at` (DateTime TZ, default utcnow).

### Indexes
- **D-05:** Two composite indexes:
  - `ix_background_jobs_org_status` on `(org_id, status)` — covers "active jobs per org" queries
  - `ix_background_jobs_org_type_started` on `(org_id, job_type, started_at)` — covers "jobs grouped by type per org, ordered by time" queries

### Autovacuum Tuning
- **D-06:** Autovacuum configured via `postgresql_with` in the Alembic `op.create_table()` call — applied at table creation time, visible in pg_class, no separate ALTER TABLE needed.
- **D-07:** Scale factors: `autovacuum_vacuum_scale_factor=0.05`, `autovacuum_analyze_scale_factor=0.02`. More aggressive than PostgreSQL defaults (0.2/0.1) to handle the heavy INSERT + UPDATE (status-transition) traffic pattern.

### Cleanup Job
- **D-08:** Cleanup function lives in `backend/app/services/sync/maintenance.py` as `async def cleanup_old_background_jobs()`. New file — keeps `scheduler.py` (already ~1,170 lines) focused on sync orchestration.
- **D-09:** Registered in `startup_scheduler()` alongside `scoring_batch`, behind the `SCHEDULER_ENABLED` guard. Runs nightly at 03:00 UTC via `CronTrigger(hour=3, minute=0)`. Hard-deletes records where `created_at < now() - 30 days`.

### Model Location
- **D-10:** `BackgroundJob` model in a new `backend/app/models/jobs.py` — separate from `performance.py` which already hosts `SyncJob`. `SyncJob` stays in `performance.py` for backward compatibility (FK references from 4 tables).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Job Model (Pattern Reference)
- `backend/app/models/performance.py` lines 625–641 — `SyncJob` model definition; follow the same SQLAlchemy mapped_column patterns for `BackgroundJob`

### Scheduler (Integration Target)
- `backend/app/services/sync/scheduler.py` lines 1156–1169 — `startup_scheduler()` end section where `scoring_batch` is registered; cleanup job goes here
- `backend/app/services/sync/scheduler.py` lines 10–12 — `CronTrigger`, `IntervalTrigger` imports already in place

### Migration Pattern
- `backend/alembic/versions/z8a9b1c2d3e5_youtube_cookies_runtime_expired.py` — most recent migration; follow its revision/down_revision chain
- `backend/alembic/versions/x6y7z8a9b0c_phase14_system_config_and_superadmin.py` — example of a larger create_table migration for reference

### Requirements
- `.planning/REQUIREMENTS.md` — JOBS-01, JOBS-02 (column list, 30-day retention rule)

### Codebase Maps
- `.planning/codebase/ARCHITECTURE.md` — APScheduler/scheduler layer description; confirms startup_scheduler() as the entry point

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SyncJob` in `performance.py:625` — exact SQLAlchemy mapped_column style to replicate for `BackgroundJob` (UUID PK, String status, JSONB metadata, DateTime TZ fields)
- `CronTrigger` + `IntervalTrigger` — already imported in `scheduler.py:11–12`, available for the cleanup job registration
- `get_session_factory()` in `scheduler.py:1144` — pattern for opening a DB session inside an APScheduler job function (use in cleanup_old_background_jobs)

### Established Patterns
- Alembic migrations use a hex revision ID string (e.g., `z8a9b1c2d3e5`); the new migration must set `down_revision = "z8a9b1c2d3e5"` (current head)
- JSONB columns default to `dict` in SQLAlchemy: `mapped_column(JSONB, default=dict)`
- `DateTime(timezone=True)` is the standard for all timestamp columns in this codebase
- `scheduler.add_job(..., id="job_id", replace_existing=True)` is the pattern for non-connection jobs

### Integration Points
- `startup_scheduler()` in `scheduler.py:1137` — import and register `cleanup_old_background_jobs` here, inside the `SCHEDULER_ENABLED` guard
- `backend/app/models/__init__.py` — add `BackgroundJob` to the export list (line 12 area)
- `backend/alembic/env.py` — verify `target_metadata` includes the new model (Base is imported from models; adding to `__init__.py` is sufficient)

</code_context>

<specifics>
## Specific Ideas

- Cleanup DELETE query: `DELETE FROM background_jobs WHERE created_at < NOW() - INTERVAL '30 days'` — straightforward, no archiving
- Migration revision ID: pick the next in the hex sequence after `z8a9b1c2d3e5`
- `BackgroundJob` status values: PENDING, RUNNING, COMPLETE, FAILED (consistent with `SyncJob` convention)
- `maintenance.py` function signature: `async def cleanup_old_background_jobs() -> None` — logs rows deleted, no return value

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-Job Persistence Schema*
*Context gathered: 2026-05-08*
