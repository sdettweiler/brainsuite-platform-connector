---
phase: 07-score-trend-performer-highlights-performance-tab
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, window-functions, percent-rank, postgresql, pytest]

# Dependency graph
requires:
  - phase: 03-brainsuite-scoring-pipeline
    provides: CreativeScoreResult model with total_score, scored_at, scoring_status fields
  - phase: 04-dashboard-ux-polish
    provides: dashboard.py with get_dashboard_assets() and get_asset_detail() endpoints
provides:
  - GET /dashboard/score-trend endpoint returning daily avg BrainSuite scores
  - _compute_performer_tag(pct_rank, total_scored) pure function with PERCENT_RANK logic
  - PERCENT_RANK() window function subquery in get_dashboard_assets()
  - 10-asset minimum guard for performer tagging
  - ad_account_id field in asset detail response
  - test_score_trend.py and test_performer_tag.py test coverage
affects:
  - 07-02 (frontend score trend panel needs /score-trend endpoint)
  - 07-03 (frontend performer badges need pct_rank-based tagging)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - PERCENT_RANK() window function via SQLAlchemy func.percent_rank().over(order_by=...)
    - Pure function _compute_performer_tag(pct_rank, total_scored) extracted for direct unit testing
    - cast(DateTime, Date) for daily grouping in trend queries

key-files:
  created:
    - backend/tests/test_score_trend.py
    - backend/tests/test_performer_tag.py
  modified:
    - backend/app/api/v1/endpoints/dashboard.py

key-decisions:
  - "PERCENT_RANK() replaces fixed-threshold performer tagging — relative ranking adapts to any org's score distribution"
  - "10-asset minimum guard: fewer than 10 COMPLETE scored assets = all null tags (not enough data for relative ranking)"
  - "Score trend endpoint date defaults: 30 days ago to yesterday — consistent with existing stats endpoint convention"
  - "data_points threshold (< 2 = empty state) is a frontend concern; backend returns single-point results as-is"
  - "ad_account_id already existed in CreativeAsset and CreativeAssetResponse schema; only detail response return dict needed updating"

patterns-established:
  - "Pattern: PERCENT_RANK subquery joined via outerjoin to main asset query — pct_rank=None for unscored assets"
  - "Pattern: _compute_performer_tag is a pure function taking (pct_rank, total_scored) — directly unit-testable without DB"

requirements-completed: [TREND-02, PERF-01]

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 07 Plan 01: Score Trend Endpoint + PERCENT_RANK Performer Tagging Summary

**GET /dashboard/score-trend endpoint and PERCENT_RANK() window function performer tagging with 10-asset minimum guard and ad_account_id in asset detail response**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T12:54:39Z
- **Completed:** 2026-03-30T12:57:00Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments

- New `GET /dashboard/score-trend` endpoint returns `{trend: [{date, avg_score}], data_points: N}` for an org's COMPLETE-scored assets grouped by day
- `_compute_performer_tag(pct_rank, total_scored)` pure function replaces the old fixed-threshold `_get_performer_tag()` — relative PERCENT_RANK() approach adapts to any org's score distribution
- PERCENT_RANK() window function subquery added to `get_dashboard_assets()` so every asset row now carries `pct_rank` and `total_scored` from its org's scored set
- 10-asset minimum guard: when `total_scored < 10`, all performer tags are `None` — prevents misleading rankings in small orgs
- `ad_account_id` added to `get_asset_detail()` return dict (field already existed in model and schema)
- 23 new tests pass; 102 pre-existing tests still pass (0 regressions)

## Task Commits

1. **Task 1: Score trend endpoint + PERCENT_RANK performer tagging with tests** - `5a1858e` (feat)

## Files Created/Modified

- `backend/app/api/v1/endpoints/dashboard.py` - Added get_score_trend(), replaced _get_performer_tag() with _compute_performer_tag(), added PERCENT_RANK subquery, added ad_account_id to detail response
- `backend/tests/test_score_trend.py` - Structural + contract tests for score trend endpoint (11 tests)
- `backend/tests/test_performer_tag.py` - Unit tests for _compute_performer_tag() pure function + structural checks (12 tests)

## Decisions Made

- PERCENT_RANK() replaces fixed thresholds (>=70 Top, >=45 Average, else Below Average). Fixed thresholds produce unstable tags when BrainSuite rescores assets or changes score distributions — relative ranking is more meaningful.
- 10-asset minimum guard chosen over a smaller number to prevent single assets dominating percentile bands.
- Score trend date defaults (30 days ago to yesterday) align with the existing stats endpoint convention at line 54-56 of dashboard.py.
- `data_points < 2` threshold for empty-state is a frontend concern; the backend returns single-point results and lets the UI decide display behavior.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing failing test `test_exception_audit.py::test_no_broad_except_exception` found in `scoring_job.py:299` — unrelated to this plan's changes. Confirmed pre-existing by stashing changes and re-running. Logged to deferred items.

## Known Stubs

None - all data fields are wired to real DB queries.

## Next Phase Readiness

- `GET /dashboard/score-trend` is ready for the frontend score trend panel (Phase 07 Plan 02)
- Performer tagging via PERCENT_RANK is ready for the frontend performer badge rendering (Phase 07 Plan 03)
- `ad_account_id` is now in the asset detail response for any UI that needs platform-level routing

---
*Phase: 07-score-trend-performer-highlights-performance-tab*
*Completed: 2026-03-30*
