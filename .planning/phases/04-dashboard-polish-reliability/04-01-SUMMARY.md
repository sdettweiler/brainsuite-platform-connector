---
phase: 04-dashboard-polish-reliability
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, pydantic, dashboard, filtering, sorting]

# Dependency graph
requires:
  - phase: 03-brainsuite-scoring-pipeline
    provides: CreativeScoreResult model with total_score field, scoring_status, creative_asset_id
provides:
  - score_min/score_max query params on GET /api/v1/dashboard/assets
  - nullslast() sort behavior for both ASC and DESC on all dashboard sort columns
  - total_score sort key alias (frontend compat for sort_by=total_score)
  - token_expiry field in PlatformConnectionResponse schema
affects: [04-02, 04-03, 04-04, frontend-dashboard, platform-health]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "nullslast() standalone function from sqlalchemy for both ASC/DESC — avoids deprecated column method"
    - "Optional filter params default=None with is-not-None guard for zero-overhead no-op when omitted"

key-files:
  created:
    - backend/tests/test_dashboard_filters.py
  modified:
    - backend/app/api/v1/endpoints/dashboard.py
    - backend/app/schemas/platform.py

key-decisions:
  - "Use standalone nullslast() function import from sqlalchemy (not deprecated .nullslast() column method) for both sort directions"
  - "score_min/score_max filter on CreativeScoreResult.total_score with ge=0, le=100 validation; NULL scores excluded when filter applied"
  - "total_score alias in sort_col_map points to same column as score — no logic duplication"
  - "token_expiry added as Optional[datetime]=None default — backward compatible, ORM mapping automatic via from_attributes=True"

patterns-established:
  - "Score filter: WHERE score IS NOT NULL AND score >= score_min (implicit NULL exclusion via comparison)"
  - "Nullslast pattern: nullslast(sort_col.desc()) and nullslast(sort_col.asc()) for consistent NULL-last behavior regardless of direction"

requirements-completed: [DASH-04, DASH-05, REL-01]

# Metrics
duration: 3min
completed: 2026-03-25
---

# Phase 4 Plan 01: Dashboard Score Filter and Sort Summary

**score_min/score_max filter params, nullslast sort fix for ASC direction, total_score sort key alias, and token_expiry schema field added to dashboard backend**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-25T09:20:09Z
- **Completed:** 2026-03-25T09:23:27Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Fixed broken score sort: ASC direction now uses `nullslast(sort_col.asc())` instead of `.nullsfirst()` — NULL scores appear after scored assets in both directions
- Added `score_min` and `score_max` query params to `get_dashboard_assets` with `ge=0, le=100` validation and conditional WHERE clauses
- Added `"total_score"` key to `sort_col_map` so frontend `sort_by=total_score` no longer falls back to spend sort
- Exposed `token_expiry: Optional[datetime]` in `PlatformConnectionResponse` so frontend can compute platform health state

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test scaffolds for score filter and sort fixes** - `db04686` (test)
2. **Task 2: Implement score filter params, sort fixes, and token_expiry schema** - `8fa2436` (feat)

_Note: TDD tasks have two commits (test RED → feat GREEN)_

## Files Created/Modified
- `backend/tests/test_dashboard_filters.py` - 7 tests covering nullslast behavior, score range filter params, and total_score sort key alias
- `backend/app/api/v1/endpoints/dashboard.py` - Added score_min/score_max params, filter WHERE clauses, total_score alias, fixed nullslast for both sort directions
- `backend/app/schemas/platform.py` - Added token_expiry Optional[datetime] to PlatformConnectionResponse

## Decisions Made
- Used standalone `nullslast()` function from sqlalchemy (not deprecated `.nullslast()` column method) — forward-compatible, works with both asc/desc in same pattern
- score_min/score_max filter implicitly excludes NULL scores via comparison semantics — no extra IS NOT NULL clause needed
- token_expiry defaults to `None` to remain backward compatible with existing API consumers

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

The worktree (agent-a64f1d66) was based at an older commit (99a5beb) and required a rebase onto main before the backend files were available. This was resolved by running `git rebase main` in the worktree before making changes.

## Known Stubs

None - all changes are concrete implementations. No placeholder values or TODO patterns introduced.

## Next Phase Readiness
- Backend score filter and sort are ready for 04-02 (frontend filter UI wiring)
- token_expiry in API response enables 04-03 (platform health status computation)
- Existing tests in test_dashboard_filters.py serve as regression guard for future score-related changes

---
*Phase: 04-dashboard-polish-reliability*
*Completed: 2026-03-25*
