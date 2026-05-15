---
phase: build-resume-retry
plan: wave-1
subsystem: jobs
tags: [jobs, retry, interrupted, partial, alembic, migration, cloud-run]
tech-stack:
  added: []
  patterns: [startup-hook, shutdown-hook, sigterm-cleanup, job-retry]
key-files:
  created:
    - backend/alembic/versions/f8a2b3c4d5e6_add_job_params.py
  modified:
    - backend/app/models/jobs.py
    - backend/app/services/sync/job_tracker.py
    - backend/app/main.py
    - backend/app/api/v1/endpoints/jobs.py
decisions:
  - Retry endpoint is SuperAdmin-only (matches all other job management endpoints)
  - _dispatch_job_retry is a no-op stub in Wave 1; Wave 2 wires real routing per job_type
  - Startup and shutdown cleanup are non-fatal (wrapped in try/except) to avoid blocking server boot
  - Migration merges all three current heads (a9b1c2d3e5f6, d3e4f5g6h7i8, e8f9a0b1c2d3) into f8a2b3c4d5e6
metrics:
  duration: ~15 minutes
  completed: 2026-05-15
---

# Phase build-resume-retry Wave 1 Summary

## What was built

Job resume/retry infrastructure for Cloud Run autoscaling resilience. Three commits:

### Commit 1 — `4e7e383`: Migration + model + job_tracker

**New migration `f8a2b3c4d5e6_add_job_params.py`**
- Merges all three alembic heads (`a9b1c2d3e5f6`, `d3e4f5g6h7i8`, `e8f9a0b1c2d3`) into a single new head
- Adds `params JSONB nullable` column to `background_jobs`
- Migration applied cleanly via `docker-compose exec -T backend alembic upgrade head`

**`backend/app/models/jobs.py`**
- Added `params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)` field
- Added `from typing import Optional` import (was missing)

**`backend/app/services/sync/job_tracker.py`**
- `create_background_job()` gains `params: Optional[dict] = None` kwarg, stored on row
- `update_background_job()` now sets `ended_at` for `INTERRUPTED` and `PARTIAL` in addition to `COMPLETE` and `FAILED`

### Commit 2 — `7660d0c`: Startup/shutdown hooks

**`backend/app/main.py`**
- Startup (before `yield`): bulk-UPDATE `RUNNING` → `INTERRUPTED` to recover from Cloud Run instance replacement
- Shutdown (after `yield`, before scheduler shutdown): same cleanup on SIGTERM
- Both operations are non-fatal (wrapped in try/except with warning log)
- Uses `get_session_factory()()` async context manager — same pattern as job_tracker.py

### Commit 3 — `4823b6f`: Retry endpoint

**`backend/app/api/v1/endpoints/jobs.py`**
- `POST /api/v1/jobs/{job_id}/retry` (SuperAdmin only, returns 202)
  - Validates job exists
  - Validates status is `INTERRUPTED`, `FAILED`, or `PARTIAL`
  - Validates `params` is non-null (jobs created before Wave 1 have no params)
  - Creates new `BackgroundJob` row via `create_background_job()` with original params
  - Calls `_dispatch_job_retry()` stub (logs warning, does not start job)
  - Returns `{"job_id": "<new-uuid>", "status": "queued"}`
- `_dispatch_job_retry()` stub — Wave 2 replaces with real routing
- Bulk-delete error message updated to mention `INTERRUPTED` and `PARTIAL` as deletable

## New migration revision ID

`f8a2b3c4d5e6`

File: `backend/alembic/versions/f8a2b3c4d5e6_add_job_params.py`

## job_type values to wire up in Wave 2

Scanned all `BackgroundJob` instantiation call sites. These are the `job_type` strings in active use:

| job_type | Description |
|---|---|
| `sync_daily` | Daily incremental sync for a platform connection |
| `sync_full` | Full re-sync of all data for a platform connection |
| `sync_initial` | First-time sync on connection setup |
| `sync_historical` | Historical backfill sync |
| `download` | Asset download job (Meta, DV360, Google Ads, TikTok) |
| `autofill` | AI autofill job for creative assets |
| `scoring` | Creative scoring job (BrainSuite API) |

Wave 2 must add a branch per `job_type` in `_dispatch_job_retry()` that:
1. Reconstructs the service call arguments from `job.params`
2. Enqueues the task via the appropriate trigger function
3. Updates the new job's status to `RUNNING`

Note: `sync_*` types also need their params stored at job creation time (Wave 2 call sites must pass `params=` to `create_background_job()`). Currently no call site passes params — the retry endpoint will return 400 for any job created before this wave.

## Deviations from plan

None — plan executed exactly as written, with one minor decision: the retry endpoint uses `get_current_superadmin` (not `get_current_user`) because the endpoint fetches any org's job by ID without an org filter, consistent with all other SuperAdmin job management endpoints.

## Known Stubs

- `_dispatch_job_retry()` in `backend/app/api/v1/endpoints/jobs.py` — logs a warning and does nothing. Wave 2 must implement per-`job_type` dispatch before retry is operationally useful.
- No call site currently passes `params=` to `create_background_job()` — Wave 2 must add this at each trigger point so new jobs have stored params.
