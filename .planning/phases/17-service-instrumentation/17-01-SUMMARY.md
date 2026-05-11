---
phase: 17-service-instrumentation
plan: "01"
subsystem: api
tags: [sqlalchemy, asyncio, postgresql, background-jobs, job-tracker, pytest]

requires:
  - phase: 16-job-persistence-schema
    provides: BackgroundJob SQLAlchemy model (jobs.py), background_jobs table migration

provides:
  - create_background_job() async helper — inserts PENDING BackgroundJob row, returns UUID
  - update_background_job() async helper — updates status/progress/output/error, auto-sets ended_at
  - test_instrumentation.py — 7 skip-only Wave 0 stub tests covering INSTR-01 through INSTR-05

affects:
  - 17-02 (sync instrumentation — imports job_tracker helpers)
  - 17-03 (download instrumentation — imports job_tracker helpers)
  - 17-04 (autofill instrumentation — imports job_tracker helpers)
  - 17-05 (scoring instrumentation — imports job_tracker helpers)
  - 17-06 (Wave 3 test implementation — fills in test_instrumentation.py stubs)

tech-stack:
  added: []
  patterns:
    - "Session-per-operation for job updates: async with get_session_factory()() as db — opens/commits/closes before any HTTP call"
    - "ended_at auto-set: update_background_job sets ended_at=datetime.utcnow() automatically on COMPLETE or FAILED"
    - "Wave 0 stub pattern: test functions contain only pytest.skip() to keep test suite green during multi-wave execution"

key-files:
  created:
    - backend/app/services/sync/job_tracker.py
    - backend/tests/services/test_instrumentation.py
  modified: []

key-decisions:
  - "D-16: Centralised helpers in job_tracker.py — all four service types call the same two async functions to avoid duplication of session lifecycle and error-schema logic"
  - "Flush+commit in create_background_job before returning job_id — prevents race condition when background tasks use the returned ID immediately (RESEARCH.md Pitfall 1)"
  - "Wave 0 stub tests skip (not xfail) — skips keep the suite green without false positives; Wave 3 plan 17-06 replaces with assertions once all Wave 2 production code is complete"

patterns-established:
  - "job_tracker helpers: two thin async functions that handle session lifecycle internally — callers only pass in semantic parameters"
  - "update_background_job guards ended_at: if status in ('COMPLETE', 'FAILED') — centralised enforcement prevents NULL ended_at regressions"

requirements-completed:
  - INSTR-01
  - INSTR-02
  - INSTR-03
  - INSTR-04
  - INSTR-05

duration: 15min
completed: 2026-05-11
---

# Phase 17 Plan 01: Service Instrumentation Foundation Summary

**job_tracker.py helper module with create_background_job/update_background_job async functions and 7 Wave 0 pytest skip stubs establishing the Nyquist test scaffold for all four job types**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-11T07:28:00Z
- **Completed:** 2026-05-11T07:43:06Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `create_background_job()` inserts a BackgroundJob row with status=PENDING, flushes+commits, and returns the UUID — session closes before any external HTTP call can occur (D-14, D-16)
- `update_background_job()` updates status/progress/output/error on an existing BackgroundJob row and automatically sets `ended_at=datetime.utcnow()` when status transitions to COMPLETE or FAILED (Pitfall 3 guard)
- `test_instrumentation.py` provides 7 named stub functions (pytest.skip() only) covering INSTR-01 through INSTR-05 plus D-16 helper contracts — all 7 skip cleanly, no failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Create job_tracker.py with create/update BackgroundJob helpers** - `a343430` (feat)
2. **Task 2: Add test_instrumentation.py with 7 skip-only Wave 0 stubs** - `4bb853c` (test)

**Plan metadata:** (final doc commit — see below)

## Files Created/Modified

- `backend/app/services/sync/job_tracker.py` — two async helper functions centralising BackgroundJob create/update logic with session-per-operation pattern (D-16)
- `backend/tests/services/test_instrumentation.py` — 7 Wave 0 skip stubs; Wave 3 plan 17-06 fills in assertions after all Wave 2 production code is complete

## Decisions Made

- Followed D-16 exactly as specified — no deviations needed. Helpers are thin wrappers; session lifecycle handled internally via `async with get_session_factory()() as db:`.
- `ended_at` auto-set in `update_background_job` when `status in ("COMPLETE", "FAILED")` — mirrors the RESEARCH.md Pitfall 3 guard. This is the single enforcement point; no callers need to remember to set it.
- Stub tests use `pytest.skip()` (not `pytest.mark.xfail`) — clean skip is preferable to expected-fail during multi-wave execution where Wave 2 plans run in parallel.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `pytest` not installed in the host environment (project uses Docker Compose exclusively). Used `docker cp` + `docker exec brainsuite_backend python -m pytest` to run the acceptance verification inside the live backend container. Results: 7 skipped, 0 failures; full services suite 3 passed + 7 skipped, 0 failures.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `job_tracker.py` is on the worktree branch and available for import by all Wave 2 plans (17-02 through 17-05) immediately
- `test_instrumentation.py` stubs are ready; Wave 2 plans do not touch this file — Wave 3 plan 17-06 fills in all 7 assertions in a single pass after Wave 2 completes
- No blockers: BackgroundJob model (Phase 16) verified importable at `from app.models.jobs import BackgroundJob`

---

## Self-Check: PASSED

- `backend/app/services/sync/job_tracker.py` — FOUND (verified via syntax check + grep)
- `backend/tests/services/test_instrumentation.py` — FOUND (verified via pytest run: 7 skipped)
- Commit `a343430` — FOUND (`git log --oneline` confirms)
- Commit `4bb853c` — FOUND (`git log --oneline` confirms)

---
*Phase: 17-service-instrumentation*
*Completed: 2026-05-11*
