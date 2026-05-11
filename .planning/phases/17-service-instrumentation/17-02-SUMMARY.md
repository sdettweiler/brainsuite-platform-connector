---
phase: 17-service-instrumentation
plan: "02"
subsystem: api
tags: [sqlalchemy, asyncio, postgresql, background-jobs, sync, instrumentation, scheduler]

requires:
  - phase: 17-service-instrumentation
    plan: "01"
    provides: create_background_job / update_background_job helpers in job_tracker.py

provides:
  - run_daily_sync() creates a sync_daily BackgroundJob in parallel with SyncJob
  - run_full_resync() creates a sync_full BackgroundJob in parallel with SyncJob
  - run_initial_sync() creates a sync_initial BackgroundJob in parallel with SyncJob
  - run_historical_sync() creates a sync_historical BackgroundJob in parallel with SyncJob
  - All 4 entry points transition BackgroundJob through RUNNING -> COMPLETE/FAILED (D-12/D-13)

affects:
  - 17-06 (Wave 3 test implementation — test_instrumentation.py stubs cover INSTR-01 sync behaviour)
  - 19 (SuperAdmin Monitoring UI — reads sync BackgroundJob rows built here)

tech-stack:
  added: []
  patterns:
    - "bg_job_id = None before async-with block — makes variable accessible to DV360 second-phase blocks outside the with scope (Python scoping workaround)"
    - "None-guard on all update_background_job calls — safe no-op if create_background_job is skipped due to early return"
    - "import traceback as _tb inline in except blocks — avoids top-level import conflict with existing inline 'import traceback' statements in the file"
    - "MetaTokenError FAILED with empty traceback string — token errors lack a meaningful stack trace at capture time"

key-files:
  created: []
  modified:
    - backend/app/services/sync/scheduler.py

key-decisions:
  - "bg_job_id = None sentinel before first async-with block in every entry point — handles DV360 two-phase path where bg_job_id is set inside the first block but consumed in second-phase exception handlers outside the block"
  - "SyncJob code left completely unchanged (D-01) — all BackgroundJob writes are purely additive lines; no existing lines were removed or altered"
  - "DV360 MetaTokenError in run_full_resync stores empty traceback string — MetaTokenError is caught without re-raising, so format_exc() would return 'NoneType: None'; empty string is cleaner and passes the D-13 schema"
  - "None-guard (if bg_job_id is not None) on every update call — prevents AttributeError in the theoretical edge case where create_background_job raises before assignment"

requirements-completed:
  - INSTR-01
  - INSTR-05

duration: 23min
completed: 2026-05-11
---

# Phase 17 Plan 02: Sync Entry Point Instrumentation Summary

**All four scheduler.py sync entry points (run_daily_sync, run_full_resync, run_initial_sync, run_historical_sync) now create a BackgroundJob record in parallel with the existing SyncJob, tracking RUNNING/COMPLETE/FAILED status with D-12 output schema and D-13 error schema throughout all code paths including the DV360 two-phase path**

## Performance

- **Duration:** ~23 min
- **Started:** 2026-05-11T07:28:00Z
- **Completed:** 2026-05-11T07:51:44Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `from app.services.sync.job_tracker import create_background_job, update_background_job` import to scheduler.py
- Instrumented `run_daily_sync` with `job_type="sync_daily"` BackgroundJob: creates after `await db.flush()` on SyncJob, updates RUNNING immediately, COMPLETE with D-12 output on harmonization success, FAILED with D-13 on MetaTokenError / general exception / harmonization failure — DV360 second-phase success/failure paths also handled
- Instrumented `run_full_resync` with `job_type="sync_full"` BackgroundJob: same lifecycle pattern; MetaTokenError path stores FAILED with empty traceback (token errors captured via `_token_err` variable, not a live exception context); DV360 two-phase success/failure handled
- Instrumented `run_initial_sync` with `job_type="sync_initial"` BackgroundJob: same lifecycle; DV360 upsert-failure and harmonize-failure paths covered
- Instrumented `run_historical_sync` with `job_type="sync_historical"` BackgroundJob: same lifecycle; all DV360 second-phase paths covered
- metadata_ dict contains `{"sync_job_id": job_id, "platform": connection.platform}` on every create call (INSTR-05)
- D-12 output schema: `{"platform": platform.lower(), "sync_job_id": job_id, "records_fetched": int, "records_processed": int}`
- D-13 error schema: `{"type": ExceptionClassName, "message": str, "traceback": str[:10000]}`
- All SyncJob column writes, status values, and completed_at logic unchanged (D-01)

## Task Commits

1. **Task 1: Add BackgroundJob instrumentation to all 4 sync entry points** — `4d25d85` (feat)

## Files Created/Modified

- `backend/app/services/sync/scheduler.py` — 371 lines inserted (4 entry points x ~90 lines each); zero lines removed from existing SyncJob logic

## Decisions Made

- `bg_job_id = None` sentinel placed before first `async with` block in all four functions — required for DV360 two-phase functions where the variable is set inside the first block but referenced in second-phase exception handlers outside it
- Inline `import traceback as _tb` in each except block — matches the pre-existing inline `import traceback` style already present in the file; avoids top-level import that would shadow those
- MetaTokenError in `run_full_resync` writes `"traceback": ""` — the exception is stored to `_token_err` and processed outside the except block, so `format_exc()` would return `NoneType: None`; empty string is accurate and schema-valid

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all four entry points write real BackgroundJob rows with real status/output data.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes beyond what is in the plan's threat model.

---

## Self-Check: PASSED

- `backend/app/services/sync/scheduler.py` — FOUND (modified in place; worktree confirmed)
- Import `from app.services.sync.job_tracker import create_background_job, update_background_job` — FOUND (1 occurrence)
- `create_background_job(` — FOUND (4 occurrences, one per entry point)
- `job_type="sync_daily"` — FOUND
- `job_type="sync_full"` — FOUND
- `job_type="sync_initial"` — FOUND
- `job_type="sync_historical"` — FOUND
- `job = SyncJob(` — FOUND (4 occurrences, D-01 confirmed)
- `"sync_job_id": job_id` — FOUND (8 occurrences — create + output per entry point)
- Python syntax check: PASSED
- pytest tests/services/test_scheduler.py: 1 passed, 0 failures
- Commit `4d25d85` — FOUND

---
*Phase: 17-service-instrumentation*
*Completed: 2026-05-11*
