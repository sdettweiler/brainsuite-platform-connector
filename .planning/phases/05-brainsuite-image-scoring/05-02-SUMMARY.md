---
phase: 05-brainsuite-image-scoring
plan: 02
subsystem: api
tags: [brainsuite, scoring, static-api, image-scoring, harmonizer, python, tdd]

requires:
  - phase: 05-brainsuite-image-scoring
    plan: 01
    provides: "ScoringEndpointType enum, endpoint_type column on creative_score_results, 20-test scaffold in test_scoring_image.py"

provides:
  - "BrainSuiteStaticScoreService — async client for ACE_STATIC_SOCIAL_STATIC_API with announce→upload→start→poll flow"
  - "build_static_scoring_payload() — Static API announce payload with channel, legs[], iconicColorScheme, optional intendedMessages; no AOI, no brandValues"
  - "map_static_channel() — META+Instagram -> Instagram, all others -> Facebook"
  - "scoring_job.py updated with endpoint_type branching: VIDEO -> video service, STATIC_IMAGE -> static service"
  - "harmonizer.py updated: creates score rows for both VIDEO and IMAGE assets with correct endpoint_type and UNSCORED/UNSUPPORTED status"
  - "Rescore endpoint guards against UNSUPPORTED assets (HTTP 422)"

affects:
  - "05-03: scheduler — static service and payload builders now available for batch integration"
  - "harmonizer.py: IMAGE assets now get score rows at sync time; VIDEO rows gain endpoint_type column"

tech-stack:
  added: []
  patterns:
    - "Static API divergence: announce payload carries all briefing data; start body is empty {} (D-04)"
    - "endpoint_type branching in scoring_job.py: if/elif per endpoint_type, shared post-job flow"
    - "Channel mapping for images: Instagram detection by 'instagram' substring in placement (case-insensitive)"

key-files:
  created:
    - backend/app/services/brainsuite_static_score.py
  modified:
    - backend/app/services/sync/harmonizer.py
    - backend/app/services/sync/scoring_job.py
    - backend/app/api/v1/endpoints/scoring.py
    - backend/tests/test_scoring_image.py

key-decisions:
  - "Static API channel mapping uses substring match on placement ('instagram' in placement_lower) — simpler than exact set for images vs. video's exact set"
  - "Rescore endpoint returns 422 (Unprocessable Entity) for UNSUPPORTED assets — communicates 'valid request, unsupported operation' more precisely than 400"
  - "Polling loop branches on endpoint_type (two separate if/elif blocks for submit and poll) — keeps each service self-contained and avoids shared state"

duration: 5min
completed: 2026-03-26
---

# Phase 05 Plan 02: BrainSuiteStaticScoreService + Pipeline Wiring Summary

**BrainSuiteStaticScoreService mirroring the video service for ACE_STATIC_SOCIAL_STATIC_API; harmonizer populates endpoint_type at sync time for IMAGE+VIDEO assets; scoring_job.py branches on endpoint_type to route VIDEO vs. STATIC_IMAGE to their respective services**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-26T09:05:03Z
- **Completed:** 2026-03-26T09:10:11Z
- **Tasks:** 2
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments

- Created `BrainSuiteStaticScoreService` with `_get_token()`, `_api_post_with_retry()`, `_announce_job(announce_payload)`, `_announce_asset()`, `_upload_to_brainsuite_s3()`, `_start_job()` (empty body), `submit_job_with_upload()`, `poll_job_status()` — all targeting ACE_STATIC_SOCIAL_STATIC_API endpoints
- `build_static_scoring_payload()` produces correct Static API announce payload: channel via `map_static_channel()`, projectName, assetLanguage, iconicColorScheme, legs[] with staticImage reference, optional intendedMessages; no AOI, no brandValues
- `map_static_channel()` maps META+Instagram placement to "Instagram", all others to "Facebook"
- Module-level singleton `brainsuite_static_score_service = BrainSuiteStaticScoreService()` exported
- Updated `harmonizer._upsert_asset()`: calls `get_endpoint_type(connection.platform, asset_fmt)` for both VIDEO and IMAGE assets; creates score rows with `endpoint_type=endpoint_type.value` and `scoring_status=UNSCORED` (or `UNSUPPORTED` for non-META images)
- Updated `scoring_job.run_scoring_batch()`: batch query now filters on `endpoint_type.in_(["VIDEO", "STATIC_IMAGE"])` instead of `asset_format == "VIDEO"`; captures `endpoint_type` in batch dict; branches to correct service for submit and poll
- Added UNSUPPORTED guard to rescore endpoint: HTTP 422 returned if `score_record.endpoint_type == "UNSUPPORTED"`
- 8 new tests added; all 28 image scoring tests pass; full suite 73 passed, 24 skipped, 0 failures

## Task Commits

Each task was committed atomically:

1. **Task 1: BrainSuiteStaticScoreService + harmonizer endpoint_type wiring** - `7379ed7` (feat)
2. **Task 2 [RED→GREEN]: payload/channel tests + scoring_job.py branching** - `f30e457` (test), `9aebfde` (feat)

_Note: TDD task has separate test commit (RED/GREEN combined — functions were available from Task 1) and implementation commit_

## Files Created/Modified

- `backend/app/services/brainsuite_static_score.py` (created) — BrainSuiteStaticScoreService with full announce→upload→start→poll flow; build_static_scoring_payload(); map_static_channel(); singleton
- `backend/app/services/sync/harmonizer.py` (modified) — adds `get_endpoint_type` import, replaces VIDEO-only score row creation with VIDEO+IMAGE routing including endpoint_type and UNSCORED/UNSUPPORTED status
- `backend/app/services/sync/scoring_job.py` (modified) — adds static service import, replaces asset_format filter with endpoint_type.in_(), adds endpoint_type to batch dict, branches submit and poll on endpoint_type
- `backend/app/api/v1/endpoints/scoring.py` (modified) — adds UNSUPPORTED guard to rescore endpoint
- `backend/tests/test_scoring_image.py` (modified) — adds 8 tests for build_static_scoring_payload and map_static_channel

## Decisions Made

- Static API channel mapping uses `"instagram" in placement_lower` substring match — more robust than exact set for images where placement variations are less constrained than video
- Rescore endpoint returns HTTP 422 (not 400) for UNSUPPORTED assets — communicates "valid request, unsupported operation" more precisely
- Polling branches on endpoint_type with two separate if/elif blocks (for submit and poll) — keeps each service self-contained

## Deviations from Plan

None — plan executed exactly as written. The plan noted `connection.platform_name` might need verification; confirmed attribute is `connection.platform` (consistent with the rest of harmonizer.py).

## Known Stubs

None — all wiring is complete. The BrainSuiteStaticScoreService requires `BRAINSUITE_CLIENT_ID` and `BRAINSUITE_CLIENT_SECRET` environment variables (same as video service, per D-15). This is a production credential requirement documented in PRODUCTION_CHECKLIST.md (PROD-01), not a code stub.

## Next Phase Readiness

- Plan 03 (scheduler integration) can proceed: `brainsuite_static_score_service` and `build_static_scoring_payload` are available for import
- All truths from must_haves verified: Image assets from Meta get STATIC_IMAGE endpoint_type and UNSCORED status; non-Meta images get UNSUPPORTED; batch query picks up STATIC_IMAGE assets; payload is correct structure
- PROD-01 spike (live API credentials) still blocked on credential availability — does not block Plan 03

---
*Phase: 05-brainsuite-image-scoring*
*Completed: 2026-03-26*

## Self-Check: PASSED

- brainsuite_static_score.py: FOUND
- 05-02-SUMMARY.md: FOUND
- Commit 7379ed7 (Task 1): FOUND
- Commit f30e457 (Task 2 tests): FOUND
- Commit 9aebfde (Task 2 impl): FOUND
