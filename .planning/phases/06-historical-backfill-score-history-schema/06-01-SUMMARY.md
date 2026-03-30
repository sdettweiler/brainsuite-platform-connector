---
phase: 06-historical-backfill-score-history-schema
plan: 01
subsystem: api
tags: [fastapi, backfill, backgroundtasks, scoring, pytest]

# Dependency graph
requires:
  - phase: 05-brainsuite-image-scoring
    provides: score_asset_now(), scoring_job.py, CreativeScoreResult model, endpoint_type field
provides:
  - POST /api/v1/scoring/admin/backfill endpoint (admin-only, returns 202)
  - run_backfill_task() background task in scoring_job.py
  - 7-test suite covering backfill task and endpoint in test_backfill.py
affects: [07-notifications, prod-deployment]

# Tech tracking
tech-stack:
  added: []
  patterns: [FastAPI BackgroundTasks for admin one-shot jobs, session-per-ID-fetch then release before iteration]

key-files:
  created:
    - backend/tests/test_backfill.py
  modified:
    - backend/app/services/sync/scoring_job.py
    - backend/app/api/v1/endpoints/scoring.py
    - backend/app/core/config.py

key-decisions:
  - "TREND-01 (creative_score_history table) intentionally NOT created — scores are static per D-09"
  - "BackgroundTasks used for backfill, not APScheduler, to avoid competing with 15-min batch on same UNSCORED queue"
  - "Single DB session to fetch all UNSCORED IDs, then released; per-asset calls iterate without holding connection"
  - "Route /admin/backfill registered BEFORE /{asset_id}/rescore to prevent FastAPI treating 'admin' as UUID param"

patterns-established:
  - "admin-only endpoints use Depends(get_current_admin) from app.api.v1.deps"
  - "backfill/batch task pattern: fetch IDs in one session, release, iterate calling score_asset_now per ID"

requirements-completed: [BACK-01, BACK-02, TREND-01]

# Metrics
duration: 18min
completed: 2026-03-30
---

# Phase 06 Plan 01: Historical Backfill Endpoint Summary

**Admin-only POST /api/v1/scoring/admin/backfill endpoint queuing all UNSCORED VIDEO/STATIC_IMAGE assets cross-tenant via FastAPI BackgroundTasks with per-asset error isolation**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-03-30T07:45:00Z
- **Completed:** 2026-03-30T08:03:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `run_backfill_task()` added to `scoring_job.py`: queries UNSCORED+VIDEO/STATIC_IMAGE rows in one DB session, releases connection, then calls `score_asset_now(score_id)` per asset with per-asset try/except error isolation
- `POST /admin/backfill` endpoint added to `scoring.py` BEFORE `/{asset_id}` routes (critical ordering): requires admin auth, returns 202 `{"status": "backfill_started", "assets_queued": N}`, delegates to BackgroundTasks
- 7-test suite covering all behavioral requirements: query filtering, FAILED exclusion, error isolation, score_asset_now delegation, empty batch, 202 response, 403 for non-admin

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test file and implement run_backfill_task()** - `4ffb72f` (feat)
2. **Task 2: Add admin backfill endpoint with tests** - `9f192fc` (feat)

**Plan metadata:** (created in final docs commit)

_Note: TDD tasks with RED/GREEN cycle — tests written first, then implementation_

## Files Created/Modified
- `backend/tests/test_backfill.py` - 7 unit tests: 5 for run_backfill_task(), 2 for POST /admin/backfill
- `backend/app/services/sync/scoring_job.py` - Added run_backfill_task() function at end of file
- `backend/app/api/v1/endpoints/scoring.py` - Added /admin/backfill endpoint + imports (func, get_current_admin, run_backfill_task)
- `backend/app/core/config.py` - Added `extra = "ignore"` to Settings.Config (deviation fix)

## Decisions Made
- TREND-01 (creative_score_history table) intentionally NOT created per D-09: BrainSuite scores are static, time-series history has no analytical value
- BackgroundTasks chosen over second APScheduler job per D-05/BACK-02 to avoid queue competition
- /admin/backfill route placed before /{asset_id} routes — critical: FastAPI would match "admin" as UUID param otherwise

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `extra = "ignore"` to Pydantic Settings.Config**
- **Found during:** Task 1 (test file creation, RED phase)
- **Issue:** `.env` file contains legacy keys (`BRAINSUITE_API_KEY`, `BRAINSUITE_API_SECRET`, `BRAINSUITE_API_BASE`, `EXCHANGE_RATE_API_KEY`, `POSTGRES_USER`, etc.) not defined in the Settings model. Pydantic v2 settings default to `extra = "forbid"`, causing `ValidationError` on test collection whenever any test imports from `app.services.sync.scoring_job` (which transitively imports Settings)
- **Fix:** Added `extra = "ignore"` to the `class Config` in `backend/app/core/config.py`. This is safe — extra env vars are silently dropped rather than raising
- **Files modified:** `backend/app/core/config.py`
- **Verification:** All 7 backfill tests pass; existing 28 tests still pass
- **Committed in:** `4ffb72f` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking import error)
**Impact on plan:** Fix was necessary to allow any test importing app modules to run. No scope creep — only `extra = "ignore"` added, which is the standard pydantic-settings pattern for .env files with extra keys.

## Issues Encountered
- Legacy `.env` keys causing `pydantic_core.ValidationError: extra_forbidden` on test collection — resolved via `extra = "ignore"` in Settings.Config (see deviations above)

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backfill endpoint ready for admin use after deploying v1.1
- TREND-01 deferred indefinitely per D-09 (no creative_score_history table needed)
- All 7 backfill tests pass; existing 51 tests (28 pass + 23 skipped stubs) unbroken

## Self-Check: PASSED

- FOUND: backend/tests/test_backfill.py
- FOUND: backend/app/services/sync/scoring_job.py
- FOUND: backend/app/api/v1/endpoints/scoring.py
- FOUND commit: 4ffb72f
- FOUND commit: 9f192fc
- FOUND: run_backfill_task in scoring_job.py
- FOUND: /admin/backfill in scoring.py

---
*Phase: 06-historical-backfill-score-history-schema*
*Completed: 2026-03-30*
