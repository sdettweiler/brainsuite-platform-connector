---
phase: 03-brainsuite-scoring-pipeline
plan: 04
subsystem: api
tags: [fastapi, sqlalchemy, postgresql, scoring, dashboard]

requires:
  - phase: 03-01
    provides: CreativeScoreResult model with scoring_status, total_score, score_dimensions
  - phase: 03-03
    provides: Dashboard _get_performer_tag updated; ace_score removed from model

provides:
  - POST /api/v1/scoring/{asset_id}/rescore — resets scoring_status to UNSCORED
  - GET /api/v1/scoring/status?asset_ids=... — batch status polling endpoint
  - GET /api/v1/scoring/{asset_id} — full score detail including score_dimensions
  - Dashboard /assets endpoint joined with CreativeScoreResult returning real scoring_status + total_score

affects:
  - 03-05 (frontend scoring display — consumes these API endpoints)
  - 04 (dashboard UX polish — sort by score now works)

tech-stack:
  added: []
  patterns:
    - Outerjoin CreativeScoreResult in paginated query for zero-N+1 score data
    - Batch asset status endpoint using comma-separated UUID string (limit 100)
    - Rescore creates score record if absent; resets if present

key-files:
  created:
    - backend/app/api/v1/endpoints/scoring.py
  modified:
    - backend/app/api/v1/__init__.py
    - backend/app/api/v1/endpoints/dashboard.py
    - backend/app/schemas/creative.py

key-decisions:
  - "Scoring router GET /status uses comma-separated query param (not repeated params) limited to 100 IDs for simple frontend polling"
  - "Dashboard outerjoin returns scoring_status=UNSCORED when no score record exists (defaulted in Python, not SQL COALESCE)"
  - "ace_score/ace_score_confidence references in asset_detail, comparison, widget endpoints replaced with None stubs — full wiring deferred to future plan"

patterns-established:
  - "outerjoin pattern: select(Model, subq, JoinedModel.col1, JoinedModel.col2).outerjoin(...) then access row.col1 by name"

requirements-completed: [SCORE-06, SCORE-08]

duration: 15min
completed: 2026-03-23
---

# Phase 03 Plan 04: Scoring API Router + Dashboard Score Join Summary

**Scoring API router (rescore/status/detail) + dashboard assets endpoint joined with CreativeScoreResult returning real scoring_status and total_score**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-23T19:10:00Z
- **Completed:** 2026-03-23T19:25:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `scoring.py` with three endpoints: `POST /{asset_id}/rescore`, `GET /status`, `GET /{asset_id}` covering SCORE-06 and SCORE-08 requirements
- Registered scoring router at `/api/v1/scoring` prefix in `__init__.py`
- Updated `get_dashboard_assets()` to outerjoin CreativeScoreResult and return real `scoring_status` + `total_score` + `total_rating` (replacing stubs)
- Removed all `ace_score`/`ace_score_confidence` references from schemas and endpoint responses; replaced with `scoring_status`/`total_score`/`total_rating`

## Task Commits

1. **Task 1: Scoring API router** - `73b637b` (feat)
2. **Task 2: Dashboard assets endpoint + schemas** - `a9d646a` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `backend/app/api/v1/endpoints/scoring.py` - New scoring router with rescore, status, and detail endpoints
- `backend/app/api/v1/__init__.py` - Added scoring.router registration
- `backend/app/api/v1/endpoints/dashboard.py` - Added CreativeScoreResult import + outerjoin; replaced ace_score stubs with real joined values; fixed ace_score refs in asset_detail/comparison/widget
- `backend/app/schemas/creative.py` - CreativeAssetSummary: replaced ace_score fields with scoring_status/total_score/total_rating; DashboardFilterParams: replaced ace_score_min/max with score_min/score_max

## Decisions Made

- GET /status uses comma-separated query param (not repeated params) limited to 100 IDs — simpler for Angular HTTP client to construct as a single string parameter
- Dashboard outerjoin defaults scoring_status to "UNSCORED" in Python when row.scoring_status is None — consistent with scoring.py behavior
- ace_score/ace_score_confidence in asset_detail, comparison, and widget endpoints replaced with None stubs rather than full joins — those endpoints are outside Plan 04 scope; flagged as known stubs

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed ace_score references from asset_detail, widget, and comparison endpoints**
- **Found during:** Task 2 (dashboard.py edits)
- **Issue:** Three other response builders in dashboard.py referenced `asset.ace_score` and `asset.ace_score_confidence` which no longer exist on the CreativeAsset model (removed in Plan 03). These would cause AttributeError at runtime.
- **Fix:** Replaced all three occurrences with None stubs (`scoring_status: None`, `total_score: None`, `total_rating: None`) to prevent runtime crashes
- **Files modified:** backend/app/api/v1/endpoints/dashboard.py
- **Verification:** `grep -n "ace_score" dashboard.py` returns no matches
- **Committed in:** a9d646a (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** Auto-fix was necessary to prevent runtime AttributeErrors. The fix uses None stubs which is consistent with the existing pattern established in Plan 03.

## Known Stubs

- `backend/app/api/v1/endpoints/dashboard.py` line ~479: `get_asset_detail` returns `scoring_status: None, total_score: None, total_rating: None` — not joined to CreativeScoreResult
- `backend/app/api/v1/endpoints/dashboard.py` line ~590: top-performers widget returns `total_score: None`
- `backend/app/api/v1/endpoints/dashboard.py` line ~728: comparison endpoint returns `total_score: None`

These stubs do not block Plan 04's goal (dashboard list and polling are fully wired). Detail/comparison/widget score wiring can be addressed in Phase 04 Dashboard UX polish.

## Issues Encountered

None — plan executed cleanly with one auto-fix deviation.

## Next Phase Readiness

- Frontend can now call `POST /scoring/{id}/rescore`, `GET /scoring/status`, `GET /scoring/{id}` for all scoring UI interactions
- Dashboard /assets list now returns live scoring data — score column and performer tag work end-to-end
- Plan 05 (frontend scoring display) has all required backend endpoints available
- Blocker note: asset_detail, comparison, widget score data are still stubbed — if Phase 04 or 05 needs them, those joins need to be added

---
*Phase: 03-brainsuite-scoring-pipeline*
*Completed: 2026-03-23*
