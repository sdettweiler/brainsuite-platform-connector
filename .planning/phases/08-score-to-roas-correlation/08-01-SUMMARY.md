---
phase: 08-score-to-roas-correlation
plan: "01"
subsystem: api
tags: [fastapi, sqlalchemy, pytest, tdd, dashboard, correlation, roas]

# Dependency graph
requires:
  - phase: 03-brainsuite-scoring-pipeline
    provides: CreativeScoreResult model with scoring_status and total_score fields
  - phase: 04-dashboard-polish-reliability
    provides: HarmonizedPerformance model and perf_subq aggregation pattern
provides:
  - GET /dashboard/correlation-data endpoint returning unpaginated scored asset list
  - _serialize_correlation_asset() helper with correct is-not-None ROAS handling
  - TDD test coverage for correlation serialization and endpoint existence
affects:
  - 08-02 (scatter chart frontend will consume this endpoint)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Use `row.roas is not None` (not `if row.roas`) to preserve zero-value ROAS in serialization"
    - "Unpaginated endpoint pattern for full-dataset scatter chart queries"

key-files:
  created:
    - backend/tests/test_correlation.py
  modified:
    - backend/app/api/v1/endpoints/dashboard.py

key-decisions:
  - "Use `row.roas is not None` guard in _serialize_correlation_asset — falsy `if row.roas` coerces 0.0 to None (existing bug in get_dashboard_assets line 228)"
  - "No pagination on /correlation-data — scatter chart needs full dataset for accurate median and quadrant framing"
  - "outerjoin to perf_subq — assets with no perf data in period get roas=null, frontend excludes them"

patterns-established:
  - "_serialize_correlation_asset: extract row serialization to named helper for unit testability"
  - "TDD: test helper functions directly (import module, call function) rather than via HTTP client for serialization tests"

requirements-completed:
  - CORR-01
  - CORR-02

# Metrics
duration: 12min
completed: 2026-03-31
---

# Phase 08 Plan 01: Correlation Data Endpoint Summary

**Unpaginated GET /dashboard/correlation-data endpoint with zero-ROAS preservation fix, backed by 8 TDD tests covering serialization edge cases**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-31T00:00:00Z
- **Completed:** 2026-03-31T00:12:00Z
- **Tasks:** 2 (RED + GREEN TDD cycle)
- **Files modified:** 2

## Accomplishments

- TDD RED: 8 failing tests covering endpoint existence, ROAS serialization (zero/null/positive), key set validation, no-pagination assertion
- TDD GREEN: `_serialize_correlation_asset()` helper + `GET /correlation-data` endpoint using `outerjoin` perf_subq pattern, filtered to COMPLETE-scored assets only
- Fixed zero-ROAS falsy bug — `row.roas is not None` instead of `if row.roas` which coerces `0.0` to `None`
- Full test suite passes: 46 passed, 24 skipped

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — Write failing tests for correlation-data endpoint** - `a1ac275` (test)
2. **Task 2: GREEN — Implement correlation-data endpoint passing all tests** - `9e3dd25` (feat)

_Note: TDD tasks have separate test and implementation commits_

## Files Created/Modified

- `backend/tests/test_correlation.py` - 8 unit tests for correlation serialization and endpoint existence
- `backend/app/api/v1/endpoints/dashboard.py` - Added `CreativeScoreResult` import, `_serialize_correlation_asset()` helper, and `GET /correlation-data` endpoint

## Decisions Made

- Used `row.roas is not None` (not falsy `if row.roas`) to preserve 0.0 ROAS — this fixes an existing pattern bug visible in get_dashboard_assets line 228
- No pagination — the scatter chart needs the full dataset for accurate median computation and quadrant framing
- `outerjoin` to perf_subq so assets with no performance data in the period get `roas=null`; frontend handles exclusion

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Backend endpoint ready for Phase 08 Plan 02 (Angular scatter chart component)
- Endpoint returns `[{id, ad_name, platform, thumbnail_url, total_score, roas, spend}]` — matches the Angular CorrelationDataPoint interface spec
- Zero-ROAS preservation tested and verified

---
*Phase: 08-score-to-roas-correlation*
*Completed: 2026-03-31*
