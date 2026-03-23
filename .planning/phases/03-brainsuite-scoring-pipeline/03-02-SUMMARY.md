---
phase: 03-brainsuite-scoring-pipeline
plan: 02
subsystem: api
tags: [brainsuite, httpx, oauth, async, retry, scoring, channel-mapping]

# Dependency graph
requires:
  - phase: 03-brainsuite-scoring-pipeline plan 01
    provides: BRAINSUITE_* config vars in Settings (added as deviation in this plan)

provides:
  - BrainSuiteScoreService class with OAuth 2.0 Client Credentials token caching
  - create_job_with_retry: 429/5xx retry with correct backoff strategies
  - poll_job_status: async polling with terminal status handling
  - map_channel: full META/TIKTOK/GOOGLE_ADS/DV360 channel mapping
  - build_scoring_payload: metadata-driven BrainSuite CreateJobInput builder
  - extract_score_data: score extraction with recursive visualization URL stripping
  - brainsuite_score_service singleton

affects:
  - 03-brainsuite-scoring-pipeline plan 03 (scoring APScheduler job uses this service)
  - 03-brainsuite-scoring-pipeline plan 04 (scoring API endpoints use this service)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "OAuth 2.0 Client Credentials with in-memory token cache (50-min TTL, invalidate on 401)"
    - "429 backoff: wait until x-ratelimit-reset ISO 8601 header + 2s"
    - "5xx backoff: exponential min(2^attempt * 5, 120) seconds, max 5 attempts"
    - "Recursive visualization URL stripping before JSONB storage"

key-files:
  created:
    - backend/app/services/brainsuite_score.py
  modified:
    - backend/app/core/config.py

key-decisions:
  - "Token cached for 50 minutes (not per-request) to avoid unnecessary auth round-trips"
  - "429 backoff uses x-ratelimit-reset header + 2s safety buffer, not a fixed duration"
  - "5xx uses exponential backoff (5s, 10s, 20s... capped at 120s) with up to 5 attempts"
  - "visualizations stripped recursively via _strip_visualizations helper to avoid key-name assumptions"
  - "map_channel normalizes 'reels' → 'reel' before comparison to handle META instagram_reels placement"
  - "brainsuite_channel metadata override: if set, bypasses all platform/placement logic"

patterns-established:
  - "BrainSuite auth pattern: Basic auth header with base64 client_id:client_secret, cache token 50 min"
  - "Rate limit pattern: parse x-ratelimit-reset ISO 8601, sleep until that timestamp + 2s"
  - "Visualization strip pattern: recursive dict/list traversal excluding 'visualizations' key"

requirements-completed: [SCORE-02, SCORE-03, SCORE-07]

# Metrics
duration: 15min
completed: 2026-03-23
---

# Phase 03 Plan 02: BrainSuiteScoreService Summary

**Async httpx BrainSuite API client with OAuth token caching, 429/5xx retry, job polling, channel mapping for all platforms, metadata-driven payload builder, and recursive visualization URL stripping.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-23T19:50:00Z
- **Completed:** 2026-03-23T20:05:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- BrainSuiteScoreService class with OAuth 2.0 Client Credentials auth and 50-minute in-memory token cache
- create_job_with_retry handles 429 (wait until x-ratelimit-reset), 5xx (exponential backoff), 401 (token invalidate + retry), and exhausted retries (RuntimeError)
- poll_job_status polls up to 60 times with 30s intervals, handles Succeeded/Failed/Stale terminal statuses
- map_channel covers all platform/placement combos including META instagram_reels normalization and brainsuite_channel metadata override
- build_scoring_payload constructs full CreateJobInput with brand_names splitting (comma/newline), optional voiceOver fields, and all metadata-driven defaults
- extract_score_data navigates legResults[0].executiveSummary, strips all visualizations recursively
- Module-level singleton brainsuite_score_service exported

## Task Commits

1. **Task 1: BrainSuiteScoreService — auth, create-job, poll, channel mapping, payload builder** - `35cabcf` (feat)

## Files Created/Modified

- `backend/app/services/brainsuite_score.py` - Full BrainSuiteScoreService implementation + module-level functions + singleton
- `backend/app/core/config.py` - Added BRAINSUITE_CLIENT_ID, BRAINSUITE_CLIENT_SECRET, BRAINSUITE_BASE_URL, BRAINSUITE_AUTH_URL settings

## Decisions Made

- Token cached 50 minutes (shorter than typical 60-min OAuth token TTL to avoid edge cases where the token expires mid-request)
- x-ratelimit-reset parsing includes fallback to `now + 60s` if the header is missing or malformed
- _strip_visualizations is a module-level recursive function so it can be unit-tested independently
- map_channel uses `.replace("reels", "reel")` rather than an exact match to handle both "instagram_reels" and "instagram_reel" placement values

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added BRAINSUITE_* config vars to config.py**
- **Found during:** Task 1 (import verification)
- **Issue:** Plan 01 (which adds BRAINSUITE_* vars to Settings) has not been committed to this worktree yet — parallel wave execution. The service imports settings.BRAINSUITE_BASE_URL at module load, so without these vars the import would fail.
- **Fix:** Added the four BRAINSUITE_* settings directly to the worktree's config.py: BRAINSUITE_CLIENT_ID, BRAINSUITE_CLIENT_SECRET, BRAINSUITE_BASE_URL, BRAINSUITE_AUTH_URL — identical to what Plan 01 specifies.
- **Files modified:** backend/app/core/config.py
- **Verification:** `from app.services.brainsuite_score import BrainSuiteScoreService` imports cleanly
- **Committed in:** 35cabcf (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to make the service importable. Plan 01 adds these same vars; when both branches are merged there will be a trivial conflict that resolves in favor of either (they're identical).

## Issues Encountered

None — service implementation matched the plan specification exactly.

## Known Stubs

None — all functions are fully implemented. No hardcoded empty values or placeholders.

## Next Phase Readiness

- BrainSuiteScoreService is ready for use by the APScheduler scoring job (Plan 03)
- build_scoring_payload requires metadata dict from AssetMetadataValue records — caller (Plan 03) is responsible for querying those
- extract_score_data output shape (total_score, total_rating, score_dimensions) matches the CreativeScoreResult model fields from Plan 01
- No blockers for Plan 03 or Plan 04

---
*Phase: 03-brainsuite-scoring-pipeline*
*Completed: 2026-03-23*
