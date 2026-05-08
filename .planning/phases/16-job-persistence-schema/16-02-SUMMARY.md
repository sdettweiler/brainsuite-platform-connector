---
phase: 16-job-persistence-schema
plan: "02"
subsystem: backend/alembic
tags: [migration, postgresql, background-jobs, autovacuum, wave-2]
dependency_graph:
  requires:
    - Phase 16 Plan 01 (BackgroundJob model and Wave-0 test scaffolds)
  provides:
    - background_jobs PostgreSQL table (migration d2e3f4a5b6c7)
    - Autovacuum tuning stored in pg_class.reloptions
    - 2 composite indexes on background_jobs
  affects:
    - backend/alembic/versions/ (new migration file)
    - backend/tests/migrations/test_phase16_migration.py (path fix)
    - Phase 17 (writes all 4 job types against this table)
    - Phase 18 (reads job status for SSE events)
    - Phase 19 (reads job status for UI dashboard)
tech_stack:
  added: []
  patterns:
    - Alembic op.create_table() with postgresql.UUID and postgresql.JSONB
    - Autovacuum tuning via op.execute("ALTER TABLE ... SET (...)") after create
    - FK constraints in op.create_table() via sa.ForeignKey()
    - Composite indexes via op.create_index()
key_files:
  created:
    - backend/alembic/versions/d2e3f4a5b6c7_background_jobs_schema.py
  modified:
    - backend/tests/migrations/test_phase16_migration.py
decisions:
  - Revision ID changed from a1b2c3d4e5f6 to d2e3f4a5b6c7 — collision with existing migration (rename_youtube_to_google_ads uses a1b2c3d4e5f6)
  - down_revision updated from z8a9b1c2d3e5 to c1d2e3f4a5b6 — actual DB head was 3 migrations ahead of plan spec
  - postgresql_with replaced by ALTER TABLE SET — postgresql_with kwarg not accepted by this SQLAlchemy/Alembic version
  - JSONB columns use postgresql.JSONB() not sa.JSONB() — JSONB is dialect-specific
metrics:
  duration_minutes: 15
  completed_date: "2026-05-08"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 16 Plan 02: Alembic Migration — background_jobs Table Summary

## One-Liner

Alembic migration d2e3f4a5b6c7 creates background_jobs table with 13 columns, FK constraints, 2 composite indexes, and autovacuum tuned to 5%/2% via ALTER TABLE SET; applied cleanly to running DB and verified by human review.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create Alembic migration for background_jobs table | b75c57a | backend/alembic/versions/d2e3f4a5b6c7_background_jobs_schema.py, backend/tests/migrations/test_phase16_migration.py |
| 2 | [BLOCKING] Verify migration on existing schema | approved | All 5 checks passed — human verified |

## What Was Built

### Task 1: Migration File

`backend/alembic/versions/d2e3f4a5b6c7_background_jobs_schema.py` creates the `background_jobs` table with:

- **13 data columns** per D-04: `id` (UUID PK), `job_type` (VARCHAR 50), `org_id` (UUID FK → organizations.id, non-nullable), `platform_connection_id` (UUID FK → platform_connections.id, nullable), `status` (VARCHAR 50, default PENDING), `progress_current` (Integer, default 0), `progress_total` (Integer nullable), `output` (JSONB, default `{}`), `metadata` (JSONB, default `{}`), `error` (JSONB nullable), `started_at` (DateTime TZ nullable), `ended_at` (DateTime TZ nullable), `created_at` (DateTime TZ, default now())
- **Autovacuum tuning** per D-06/D-07 via `ALTER TABLE background_jobs SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_analyze_scale_factor = 0.02)` — stored in `pg_class.reloptions`
- **2 composite indexes** per D-05: `ix_background_jobs_org_status(org_id, status)` and `ix_background_jobs_org_type_started(org_id, job_type, started_at)`
- **Full downgrade**: drops both indexes then drops table

### Task 2: DB Verification (Blocking Checkpoint — APPROVED)

All 5 checkpoint verification steps passed and human-approved:

1. `alembic upgrade head` — exited 0: `Running upgrade c1d2e3f4a5b6 -> d2e3f4a5b6c7`
2. `\d background_jobs` — all 13 columns confirmed with correct types and nullability
3. `pg_class.reloptions` — `{autovacuum_vacuum_scale_factor=0.05,autovacuum_analyze_scale_factor=0.02}`
4. `pg_indexes` — both `ix_background_jobs_org_status` and `ix_background_jobs_org_type_started` present
5. `pytest tests/migrations/test_phase16_migration.py` — `1 passed in 0.05s`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Revision ID collision**
- **Found during:** Task 1 — pre-run `alembic history` check
- **Issue:** Plan specified revision `a1b2c3d4e5f6`, but that ID was already used by `a1b2c3d4e5f6_rename_youtube_to_google_ads.py`. Alembic would fail with a duplicate revision error.
- **Fix:** Changed revision to `d2e3f4a5b6c7`. Migration file named `d2e3f4a5b6c7_background_jobs_schema.py`.
- **Files modified:** backend/alembic/versions/d2e3f4a5b6c7_background_jobs_schema.py
- **Commit:** b75c57a

**2. [Rule 1 - Bug] Stale down_revision**
- **Found during:** Task 1 — `alembic current` showed DB head as `c1d2e3f4a5b6`, not `z8a9b1c2d3e5`
- **Issue:** Plan specified `down_revision = "z8a9b1c2d3e5"` but the actual DB head was 3 migrations ahead. Would have created a branch fork.
- **Fix:** Updated `down_revision = "c1d2e3f4a5b6"` to chain from the actual head.
- **Files modified:** backend/alembic/versions/d2e3f4a5b6c7_background_jobs_schema.py
- **Commit:** b75c57a

**3. [Rule 1 - Bug] postgresql_with not supported**
- **Found during:** Task 1 — first `alembic upgrade head` attempt failed with `ArgumentError: Argument 'postgresql_with' is not accepted`
- **Issue:** `postgresql_with={...}` is not a valid kwarg for `op.create_table()` in this SQLAlchemy version.
- **Fix:** Replaced with `op.execute("ALTER TABLE background_jobs SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_analyze_scale_factor = 0.02)")` after `create_table`. Autovacuum settings still land in `pg_class.reloptions` (verified in Step 3).
- **Files modified:** backend/alembic/versions/d2e3f4a5b6c7_background_jobs_schema.py
- **Commit:** b75c57a

**4. [Rule 1 - Bug] sa.JSONB() AttributeError**
- **Found during:** Task 1 — second `alembic upgrade head` attempt failed with `AttributeError: module 'sqlalchemy' has no attribute 'JSONB'`
- **Issue:** JSONB is a PostgreSQL dialect type; must be imported from `sqlalchemy.dialects.postgresql`.
- **Fix:** Changed `sa.JSONB()` → `postgresql.JSONB()` for all 3 JSONB columns.
- **Files modified:** backend/alembic/versions/d2e3f4a5b6c7_background_jobs_schema.py
- **Commit:** b75c57a

**5. [Rule 1 - Bug] Test path wrong (../../../ vs ../../)**
- **Found during:** pytest run — test computed versions path as `/alembic/versions` instead of `/app/alembic/versions`
- **Issue:** Wave-0 scaffold in Plan 01 used `../../../alembic/versions` from `tests/migrations/` which goes one level too far up.
- **Fix:** Updated `test_phase16_migration.py` path traversal from `../../../` to `../../`.
- **Files modified:** backend/tests/migrations/test_phase16_migration.py
- **Commit:** b75c57a

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. The migration executes DDL under DB admin credentials during deploy — covered by T-16-05 (migration chain integrity, mitigated by hardcoded down_revision). T-16-07 (org_id FK tenant isolation) is implemented via `sa.ForeignKey("organizations.id")` with `nullable=False`.

## Known Stubs

None — migration is complete DDL with no placeholder values.

## Self-Check: PASSED

- backend/alembic/versions/d2e3f4a5b6c7_background_jobs_schema.py: EXISTS
- backend/tests/migrations/test_phase16_migration.py: MODIFIED (path fix)
- Commit b75c57a: EXISTS
- background_jobs table in DB: VERIFIED
- autovacuum reloptions: VERIFIED
- Both indexes: VERIFIED
- pytest: 1 PASSED
- Task 2 checkpoint: APPROVED by human
