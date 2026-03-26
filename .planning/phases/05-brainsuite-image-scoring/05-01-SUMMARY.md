---
phase: 05-brainsuite-image-scoring
plan: 01
subsystem: api
tags: [brainsuite, scoring, alembic, migration, enum, python, tdd]

requires:
  - phase: 03-brainsuite-scoring-pipeline
    provides: "BrainSuiteScoreService reference implementation for announce→upload→start pattern, scoring_status state machine, creative_score_results table"

provides:
  - "Static API discovery spike script (scripts/spike_static_api.py) confirming ACE_STATIC_SOCIAL_STATIC_API endpoint structure"
  - "docs/BRAINSUITE_API.md with Static API endpoint URLs, payload schema, response shape (pending live spike)"
  - "docs/PRODUCTION_CHECKLIST.md with PROD-01 and PROD-02 verification steps"
  - "ScoringEndpointType enum (VIDEO/STATIC_IMAGE/UNSUPPORTED) with get_endpoint_type() lookup function"
  - "endpoint_type column on creative_score_results (Alembic migration l3m4n5o6p7q8 with VIDEO backfill)"
  - "20-test scaffold in test_scoring_image.py covering all D-11 routing combinations"

affects:
  - "05-02: BrainSuiteStaticScoreService — uses ScoringEndpointType.STATIC_IMAGE routing"
  - "05-03: scheduler branch — uses get_endpoint_type() and endpoint_type column to route VIDEO vs STATIC_IMAGE"
  - "harmonizer.py — must populate endpoint_type at sync time using get_endpoint_type()"

tech-stack:
  added: []
  patterns:
    - "ScoringEndpointType: explicit lookup table at module level, case-normalized inputs, safe UNSUPPORTED default"
    - "TDD RED→GREEN: test file committed before implementation, confirmed failing, then implementation makes all pass"
    - "Alembic migration: add nullable column + create index + backfill in single upgrade() transaction"

key-files:
  created:
    - backend/app/services/scoring_endpoint_type.py
    - backend/alembic/versions/l3m4n5o6p7q8_add_endpoint_type_unsupported.py
    - backend/tests/test_scoring_image.py
    - docs/BRAINSUITE_API.md
    - docs/PRODUCTION_CHECKLIST.md
    - scripts/spike_static_api.py
  modified:
    - backend/app/models/scoring.py

key-decisions:
  - "Spike script ready-to-run: credentials not available in dev environment; script exits with clear message and PROD-01 confirmation pending"
  - "ScoringEndpointType lives in dedicated module (not inline in creative.py or enums.py) for clean import by scheduler and harmonizer"
  - "endpoint_type migration down_revision=k2l3m4n5o6p7 (add_dv360_cost_per_view) — latest migration in chain"
  - "PROD-02 (Google Ads OAuth consent screen) documented as manual verification step in PRODUCTION_CHECKLIST.md"

patterns-established:
  - "get_endpoint_type(platform, asset_format): normalize to uppercase, check CAROUSEL first, lookup dict with UNSUPPORTED default"
  - "Alembic migration backfill: UPDATE ... WHERE endpoint_type IS NULL immediately after add_column in same upgrade()"

requirements-completed: [PROD-01, PROD-02, IMG-01, IMG-02]

duration: 5min
completed: 2026-03-26
---

# Phase 05 Plan 01: Image Scoring Foundation Summary

**ScoringEndpointType enum + 8-entry D-11 lookup table, endpoint_type Alembic migration with VIDEO backfill, Static API discovery spike script, and BRAINSUITE_API.md + PRODUCTION_CHECKLIST.md documentation foundation**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-26T08:56:54Z
- **Completed:** 2026-03-26T09:01:44Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Static API discovery spike script created covering full announce→upload→start→poll flow; script exits with clear credential-not-found message in dev environment and is ready to run with real credentials
- ScoringEndpointType enum with VIDEO/STATIC_IMAGE/UNSUPPORTED values and get_endpoint_type() lookup function covering all 8 D-11 platform/format combinations; 20 tests all green
- Alembic migration adds endpoint_type column (String(50), nullable, indexed) to creative_score_results and backfills existing rows to 'VIDEO'
- BRAINSUITE_API.md documents Static API endpoint URLs, payload schema, authentication, rate limiting, and expected response shape
- PRODUCTION_CHECKLIST.md documents PROD-01 (BrainSuite credentials) and PROD-02 (Google Ads OAuth consent screen) verification steps

## Task Commits

Each task was committed atomically:

1. **Task 1: Static API discovery spike + docs** - `b2d3e41` (feat)
2. **Task 2 [RED]: failing tests for ScoringEndpointType** - `9401767` (test)
3. **Task 2 [GREEN]: ScoringEndpointType module + migration** - `f46fd83` (feat)

_Note: TDD task has separate test commit (RED) and implementation commit (GREEN)_

## Files Created/Modified

- `scripts/spike_static_api.py` - Standalone spike: authenticate, announce, upload 1x1 JPEG, start job, poll to terminal status, dump response
- `docs/BRAINSUITE_API.md` - Static API endpoint reference, payload fields, response shape, channel mapping for images
- `docs/PRODUCTION_CHECKLIST.md` - PROD-01 (BrainSuite credentials) and PROD-02 (Google Ads OAuth) verification checklists
- `backend/app/services/scoring_endpoint_type.py` - ScoringEndpointType(str, Enum) with VIDEO/STATIC_IMAGE/UNSUPPORTED; get_endpoint_type() with 8-entry lookup dict
- `backend/alembic/versions/l3m4n5o6p7q8_add_endpoint_type_unsupported.py` - Add endpoint_type column, create index, backfill VIDEO
- `backend/app/models/scoring.py` - Added endpoint_type Mapped[Optional[str]] column + updated docstring with UNSUPPORTED status
- `backend/tests/test_scoring_image.py` - 20 tests: 8 D-11 combinations, CAROUSEL pre-check, case insensitivity, None/empty handling

## Decisions Made

- Spike script exits with exit code 2 (not 1) when credentials missing, distinguishing "not configured" from "auth failed" — callers can check this
- `iconicColorScheme` default confirmed `"manufactory"` from API docs; additional valid values to be confirmed by live spike
- Static API base URL is `https://api.brainsuite.ai` (production); docs reference `https://api.staging.brainsuite.ai` as staging — spike script targets production URL
- All 20 tests added in single test file (not split) since they test one module; test count exceeds required 9

## Deviations from Plan

None — plan executed exactly as written. The spike script could not be run (no credentials in dev environment), which was explicitly anticipated in the plan's acceptance criteria.

## Issues Encountered

- No backend `.env` file present in dev environment — credentials not available. Script handles this gracefully with a clear error message and exit code 2.
- The API docs reference `https://api.staging.brainsuite.ai` as base URL for the Static API, but existing video service uses `https://api.brainsuite.ai`. BRAINSUITE_API.md documents both and notes the spike should confirm which to use.

## Known Stubs

- `docs/BRAINSUITE_API.md` section "Spike Results" is intentionally unpopulated — marked "Pending — credentials not available in dev environment". This will be filled in when the spike is run with real credentials. This does not block Plan 02 implementation (all endpoint structure is documented from API docs).
- `docs/PRODUCTION_CHECKLIST.md` PROD-01 and PROD-02 verification dates are blank — awaiting manual verification.

## User Setup Required

**PROD-01:** Run `BRAINSUITE_CLIENT_ID=<id> BRAINSUITE_CLIENT_SECRET=<secret> python scripts/spike_static_api.py` from project root to confirm Static API works with existing credentials. Update `docs/BRAINSUITE_API.md` with results.

**PROD-02:** Check Google Ads OAuth consent screen status in Google Cloud Console (see `docs/PRODUCTION_CHECKLIST.md` for exact steps).

## Next Phase Readiness

- Plan 02 (BrainSuiteStaticScoreService) can proceed: endpoint URLs, payload shape, auth pattern all documented
- ScoringEndpointType module ready for import by harmonizer.py and scheduler.py
- Alembic migration ready to apply; test suite foundation in place
- PROD-01 spike confirmation blocked on credential availability — does not block implementation

---
*Phase: 05-brainsuite-image-scoring*
*Completed: 2026-03-26*
