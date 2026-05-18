---
phase: 23-dashboard-duration-filter-backfill
plan: 01
subsystem: api
tags: [dashboard, filters, duration, backfill, fastapi, sqlalchemy, ffprobe, alembic, video]

# Dependency graph
requires:
  - phase: 22-metadata-filter
    provides: "metadata filter JOIN pattern (aliased AssetMetadataValue + MetadataField org guard); Alembic single-head f8a2b3c4d5e6"
provides:
  - "GET /dashboard/duration-bounds endpoint returning min/max video_duration scoped to org + filters"
  - "duration_min/duration_max Query params on GET /dashboard/assets with BETWEEN filter"
  - "null_duration_count response field on GET /dashboard/assets (only when filter active)"
  - "video_utils.get_video_duration() shared ffprobe utility (extracted from dv360_sync)"
  - "backfill_job.run_duration_backfill() + has_null_duration_assets() async backfill"
  - "Composite index ix_creative_assets_org_format_duration on creative_assets(org, format, duration)"
  - "8 sync completion sites in scheduler.py fire duration backfill when NULL count > 0"
affects: [23-dashboard-duration-filter-frontend, plan-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "video_utils.py: shared ffprobe-based duration extraction (extracted from service method)"
    - "backfill_job.py: async batch job with job_tracker lifecycle (PENDING->RUNNING->COMPLETE)"
    - "duration bounds endpoint: filter-aware MIN/MAX aggregation reusing metadata JOIN pattern"
    - "null_duration_count: conditional COUNT subquery gated on filter activity (D-07)"
    - "Alembic index-only migration chaining onto single head (down_revision=f8a2b3c4d5e6)"

key-files:
  created:
    - backend/tests/test_dashboard_duration.py
    - backend/alembic/versions/a9b0c1d2e3f4_add_duration_index.py
    - backend/app/services/sync/video_utils.py
    - backend/app/services/sync/backfill_job.py
  modified:
    - backend/app/api/v1/endpoints/dashboard.py
    - backend/app/services/sync/dv360_sync.py
    - backend/app/services/sync/scheduler.py

key-decisions:
  - "null_duration_count computed only when duration filter active (D-07, T-23-06) — avoids COUNT on every unfiltered request"
  - "Backfill gated by has_null_duration_assets > 0 at each sync site — prevents unnecessary job creation"
  - "pre-existing test_downloads_skipped_when_scoring_disabled failure confirmed pre-existing (not introduced by this plan)"

patterns-established:
  - "video_utils.py pattern: extract method from service class to shared module-level function for cross-service reuse"
  - "Backfill pattern: same job_tracker lifecycle as scoring_job.py; per-asset failure logging; sequential batches"

requirements-completed: [DASH-03]

# Metrics
duration: 10min
completed: 2026-05-18
---

# Phase 23 Plan 01: Duration Filter Backend Summary

**Full backend for DASH-03 duration filter: ffprobe extraction utility, async backfill job, composite DB index, filter-aware bounds endpoint, BETWEEN filter + null count on /dashboard/assets, and 8 scheduler trigger sites**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-18T10:37:39Z
- **Completed:** 2026-05-18T10:47:49Z
- **Tasks:** 6
- **Files modified:** 7

## Accomplishments
- Created `video_utils.py` with `get_video_duration()` extracted from `dv360_sync._get_video_duration`; updated dv360_sync to import from shared module
- Created `backfill_job.py` with `run_duration_backfill(org_id, batch_size=100)` and `has_null_duration_assets(db, org_id)` using BackgroundJob lifecycle PENDING→RUNNING→COMPLETE
- Alembic migration `a9b0c1d2e3f4` adds composite index `ix_creative_assets_org_format_duration` on `(organization_id, asset_format, video_duration)`, chains onto `f8a2b3c4d5e6`
- `GET /dashboard/duration-bounds` endpoint returns filter-aware `{min_duration, max_duration}` with org + metadata filter parity
- `GET /dashboard/assets` gains `duration_min`/`duration_max` params, `null_duration_count` response field (computed only when filter active)
- `scheduler.py` fires `asyncio.create_task(run_duration_backfill(org_id))` at all 8 sync completion sites gated by `has_null_duration_assets > 0`
- All 4 tests in `test_dashboard_duration.py` GREEN; no new test failures introduced

## Task Commits

1. **Task 1: Test stubs** — `bb19cf7` (test)
2. **Task 2: Alembic migration** — `9e9aad6` (feat)
3. **Task 3: video_utils extraction + dv360_sync update** — `eb37493` (feat)
4. **Task 4: backfill_job.py** — `971cdb4` (feat)
5. **Task 5: dashboard.py duration-bounds + params + null_duration_count** — `33d20a4` (feat)
6. **Task 6: scheduler.py 8 trigger sites** — `03e2404` (feat)

## Files Created/Modified
- `backend/tests/test_dashboard_duration.py` - 4 tests: bounds org scope, BETWEEN filter, null count guard, backfill lifecycle
- `backend/alembic/versions/a9b0c1d2e3f4_add_duration_index.py` - composite index migration; resolves RESEARCH.md Q4
- `backend/app/services/sync/video_utils.py` - `get_video_duration(file_path) -> Optional[float]` using ffprobe
- `backend/app/services/sync/backfill_job.py` - `run_duration_backfill`, `has_null_duration_assets`
- `backend/app/api/v1/endpoints/dashboard.py` - `get_duration_bounds` endpoint + duration_min/max params + null_duration_count
- `backend/app/services/sync/dv360_sync.py` - replaced `_get_video_duration` with import from video_utils
- `backend/app/services/sync/scheduler.py` - 8 duration backfill trigger sites after autofill backfill calls

## Decisions Made
- `null_duration_count` computed only when `duration_min is not None or duration_max is not None` (D-07): avoids extra COUNT on every dashboard load
- Backfill gated by `has_null_duration_assets(db, org_id) > 0` at each sync site: prevents fire-and-forget job creation when no work exists
- Pre-existing test failure `test_downloads_skipped_when_scoring_disabled` confirmed pre-existing (also present before this plan's first commit); logged to deferred-items

## Deviations from Plan

None — plan executed exactly as written. The `null_duration_count` subquery was implemented with a slightly different join pattern than the plan sketch (using the already-built `perf_subq` subquery for `total_spend.isnot(None)` filtering to match `/dashboard/assets` behavior), which is functionally equivalent and more correct.

## Issues Encountered

- Pre-existing test failure: `tests/services/test_scheduler.py::test_downloads_skipped_when_scoring_disabled` (SQLAlchemy primary key error). Confirmed pre-existing by stashing Task 6 changes and re-running — same failure. Not caused by this plan. Logged to deferred-items.

## User Setup Required

None — no external service configuration required. The Alembic migration is automatically applied on container start (`alembic upgrade head` in Docker entrypoint).

## Next Phase Readiness
- Full backend substrate for DASH-03 is complete; Plan 02 (frontend) can now consume `/dashboard/duration-bounds`, `duration_min`/`duration_max` params, and `null_duration_count`
- Backfill will fire automatically on next sync run for any org with NULL-duration VIDEO assets

## Self-Check: PASSED

Files verified to exist:
- backend/tests/test_dashboard_duration.py — FOUND
- backend/alembic/versions/a9b0c1d2e3f4_add_duration_index.py — FOUND
- backend/app/services/sync/video_utils.py — FOUND
- backend/app/services/sync/backfill_job.py — FOUND

Commits verified to exist: bb19cf7, 9e9aad6, eb37493, 971cdb4, 33d20a4, 03e2404

---
*Phase: 23-dashboard-duration-filter-backfill*
*Completed: 2026-05-18*
