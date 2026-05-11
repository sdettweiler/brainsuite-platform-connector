---
phase: 19-superadmin-monitoring-ui
plan: 01
subsystem: api
tags: [pydantic, fastapi, testing, jobs, monitoring]

# Dependency graph
requires:
  - phase: 16-job-persistence-schema
    provides: BackgroundJob SQLAlchemy model with all column names and types
provides:
  - Pydantic schemas JobListItem (9 fields, no JSONB body) and JobDetail (11 fields, with output+error) in backend/app/schemas/jobs.py
  - 9 test stubs in backend/tests/test_jobs_api.py covering all REST endpoint contract scenarios
affects: [19-02-plan, 19-03-plan]

# Tech tracking
tech-stack:
  added: []
  patterns: [JobListItem omits JSONB fields for list endpoint; JobDetail inherits and adds them for detail endpoint]

key-files:
  created:
    - backend/app/schemas/jobs.py
    - backend/tests/test_jobs_api.py
  modified: []

key-decisions:
  - "JobDetail inherits JobListItem; both declare explicit Config with from_attributes = True (Pydantic v2 ORM serialisation)"
  - "Test stubs all use pytest.skip so Wave 2 can flip them to real assertions without restructuring"

patterns-established:
  - "List schema omits JSONB blob fields (output/error); detail schema adds them — pattern established for future bulk-vs-detail endpoints"

requirements-completed: [MON-01, MON-02, MON-03, MON-04, MON-05, MON-06, MON-07]

# Metrics
duration: 15min
completed: 2026-05-11
---

# Phase 19 Plan 01: SuperAdmin Monitoring UI — Schemas + Test Stubs Summary

**JobListItem/JobDetail Pydantic schemas (ORM-ready, JSONB split) and 9 test stubs establishing the Wave 2 REST API contract**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-11T21:00:00Z
- **Completed:** 2026-05-11T21:13:29Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `JobListItem` schema with 9 fields (id, job_type, org_id, status, progress_current, progress_total, started_at, ended_at, metadata_) — intentionally omits output/error JSONB to keep list response lightweight
- `JobDetail` inherits `JobListItem` and adds `output` and `error` Optional[dict] fields; both have `from_attributes = True` for SQLAlchemy ORM serialisation
- 9 test stubs covering all REST scenarios: list (200, filter_by_type, filter_by_status, pagination), detail (200, 404), delete (204), and 403 for non-superadmin on both GET and DELETE

## Task Commits

Each task was committed atomically:

1. **Task 1: Create JobListItem and JobDetail Pydantic schemas** - `1c7307d` (feat)
2. **Task 2: Write 9 REST API test stubs in test_jobs_api.py** - `66ec898` (test)

## Files Created/Modified
- `backend/app/schemas/jobs.py` — JobListItem (9 fields) and JobDetail (11 fields) Pydantic schemas with ORM Config
- `backend/tests/test_jobs_api.py` — 9 stubs with _make_superuser() and _make_job() helpers; all skip cleanly

## Decisions Made
- Both JobListItem and JobDetail have explicit `class Config: from_attributes = True` rather than relying on Pydantic v2 inheritance alone — matches existing schema conventions in user.py and satisfies acceptance criteria
- 9 stubs written (behaviour list had 9 items including pagination) — matches plan's acceptance criteria count

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- File was initially written to the main repo path instead of the worktree path — detected via `git status` showing no changes; corrected by writing to the worktree-relative absolute path. The miswrite to the main repo was cleaned up immediately before staging.

## Known Stubs

All stubs in `backend/tests/test_jobs_api.py` are intentional scaffolding per the plan design. They will be wired to real assertions in Wave 2 (Plan 02) once the REST endpoints exist.

## Next Phase Readiness
- Wave 2 (Plan 02) can immediately implement REST endpoints and flip the 9 stubs to real assertions without restructuring the test file
- Schema contract is locked: list returns no JSONB body; detail returns full JSONB — Plan 02 must respect this split

---
*Phase: 19-superadmin-monitoring-ui*
*Completed: 2026-05-11*
