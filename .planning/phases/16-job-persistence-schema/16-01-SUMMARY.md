---
phase: 16-job-persistence-schema
plan: "01"
subsystem: backend/models
tags: [schema, sqlalchemy, background-jobs, wave-1]
dependency_graph:
  requires: []
  provides:
    - BackgroundJob SQLAlchemy model (backend/app/models/jobs.py)
    - BackgroundJob export from app.models
    - Wave-0 test scaffolds for model, migration, maintenance, scheduler
  affects:
    - backend/alembic/env.py (auto-discovers BackgroundJob via Base.metadata)
    - Phase 16 Plan 02 (migration reads the model)
    - Phase 16 Plan 03 (maintenance service depends on model)
tech_stack:
  added: []
  patterns:
    - SQLAlchemy 2.0 Mapped/mapped_column style (consistent with SyncJob in performance.py)
    - JSONB default=dict pattern (not default={})
    - Python attribute alias (metadata_ → "metadata" DB column) matching SyncJob.job_metadata pattern
    - Two composite indexes in __table_args__ tuple
key_files:
  created:
    - backend/app/models/jobs.py
    - backend/tests/models/__init__.py
    - backend/tests/models/test_jobs.py
    - backend/tests/services/__init__.py
    - backend/tests/services/test_maintenance.py
    - backend/tests/services/test_scheduler.py
    - backend/tests/migrations/__init__.py
    - backend/tests/migrations/test_phase16_migration.py
  modified:
    - backend/app/models/__init__.py
decisions:
  - BackgroundJob in separate jobs.py (not performance.py) per D-10; SyncJob preserved for backward compatibility
  - metadata_ python attribute aliased to "metadata" DB column, consistent with SyncJob.job_metadata alias pattern
  - Wave-0 test scaffolds written before migration/service code (test-first contract)
metrics:
  duration_minutes: 5
  completed_date: "2026-05-08"
  tasks_completed: 2
  tasks_total: 2
  files_created: 8
  files_modified: 1
---

# Phase 16 Plan 01: BackgroundJob Model and Wave-0 Test Scaffolds Summary

## One-Liner

BackgroundJob SQLAlchemy model with 14 columns, 2 composite indexes, FK constraints, exported from app.models; Wave-0 pytest scaffolds for model/migration/maintenance/scheduler.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create BackgroundJob model (jobs.py) and export from __init__.py | 572cd8e | backend/app/models/jobs.py, backend/app/models/__init__.py |
| 2 | Scaffold Wave-0 test files (models, migrations, maintenance, scheduler) | 70635b1 | 7 new files across tests/models/, tests/services/, tests/migrations/ |

## What Was Built

### Task 1: BackgroundJob Model

`backend/app/models/jobs.py` defines the `BackgroundJob` SQLAlchemy ORM model with:

- **14 columns** per D-04: `id` (UUID PK), `job_type` (VARCHAR 50), `org_id` (UUID FK non-nullable), `platform_connection_id` (UUID FK nullable), `status` (VARCHAR 50, default PENDING), `progress_current` (Integer, default 0), `progress_total` (Integer nullable), `output` (JSONB, default dict), `metadata_`/`"metadata"` (JSONB, default dict), `error` (JSONB nullable), `started_at` (DateTime TZ nullable), `ended_at` (DateTime TZ nullable), `created_at` (DateTime TZ, default utcnow)
- **2 composite indexes** per D-05: `ix_background_jobs_org_status(org_id, status)` and `ix_background_jobs_org_type_started(org_id, job_type, started_at)`
- `metadata_` Python attribute aliased to `"metadata"` DB column — avoids conflict with SQLAlchemy's internal `metadata` attribute, consistent with SyncJob's `job_metadata` alias pattern

`backend/app/models/__init__.py` updated with:
- `from app.models.jobs import BackgroundJob`
- `"BackgroundJob"` added to `__all__`

### Task 2: Wave-0 Test Scaffolds

Four test files created to establish the test contract before implementation:

- **`tests/models/test_jobs.py`**: 3 tests — `test_background_job_model_columns` (all 13 non-id columns), `test_background_job_model_indexes` (both composite indexes), `test_background_job_model_fk_constraints` (org_id non-nullable → organizations, platform_connection_id nullable → platform_connections)
- **`tests/services/test_maintenance.py`**: 2 async tests — `test_cleanup_old_background_jobs_deletes_old_records` (mocked session, verifies execute+commit), `test_cleanup_old_background_jobs_rollback_on_error` (verifies rollback+reraise)
- **`tests/services/test_scheduler.py`**: 1 test — `test_cleanup_job_registration` (mocks scheduler, verifies `cleanup_background_jobs` id + CronTrigger(hour=3, minute=0))
- **`tests/migrations/test_phase16_migration.py`**: 1 test — `test_phase16_migration_file_exists` (verifies migration file exists, contains autovacuum config, has down_revision)

## Verification

- All 4 test files pass Python AST parse (syntactically valid)
- Acceptance criteria grep checks pass: both index names (1 each), BackgroundJob import (1), "BackgroundJob" in __all__ (1)
- Model follows exact SyncJob pattern from performance.py:625-641 for SQLAlchemy 2.0 compatibility
- BackgroundJob is auto-discoverable by Alembic via Base.metadata once imported in __init__.py

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes at trust boundaries were introduced in this plan. The BackgroundJob model is a pure ORM definition with no write paths — T-16-01 (job_type validation) and T-16-02 (org_id tenant isolation) mitigations are deferred to Phase 17 service instrumentation as specified.

## Known Stubs

None — this plan creates the data contract layer only. No data flows to UI rendering.

## Self-Check: PASSED

- backend/app/models/jobs.py: EXISTS
- backend/app/models/__init__.py: MODIFIED (BackgroundJob added)
- backend/tests/models/test_jobs.py: EXISTS
- backend/tests/services/test_maintenance.py: EXISTS
- backend/tests/services/test_scheduler.py: EXISTS
- backend/tests/migrations/test_phase16_migration.py: EXISTS
- Commit 572cd8e: EXISTS (Task 1)
- Commit 70635b1: EXISTS (Task 2)
