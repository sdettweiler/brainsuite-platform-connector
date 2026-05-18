---
phase: 25-configurable-concurrency
plan: 02
subsystem: download-concurrency
tags: [asyncio, semaphore, fastapi, pydantic, superadmin, ratelimit, dv360, google-ads]

# Dependency graph
requires:
  - plan: 25-01
    provides: get_concurrency_semaphore() in proxy_cache.py; max_concurrent_downloads column in SystemConfig
provides:
  - semaphore-guarded download call sites in dv360_sync.py _download_video_asset (acquire-once-outside-retry-loop)
  - semaphore-guarded download call sites in google_ads_sync.py _download_video (acquire-once-outside-retry-loop)
  - GET /api/v1/super-admin/download-concurrency endpoint + ConcurrencyConfigResponse model
  - PUT /api/v1/super-admin/download-concurrency endpoint + ConcurrencyConfigRequest model with Field(ge=1, le=10)
  - 8 endpoint tests in test_super_admin_proxy.py
affects:
  - 25-03 (Angular admin UI slider calls GET/PUT /download-concurrency)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Acquire-once-outside-retry-loop: semaphore = await get_concurrency_semaphore() called once per asset, before the for-loop; async with semaphore: wraps the entire retry loop so all retry attempts share one slot and no other asset can cut the line mid-retry"
    - "SuperAdmin endpoint pair (GET/PUT) with Pydantic Field(ge=1, le=10) range validation — rejects out-of-range integers before handler body, DB never reached"

key-files:
  created: []
  modified:
    - backend/app/services/sync/dv360_sync.py
    - backend/app/services/sync/google_ads_sync.py
    - backend/app/api/v1/endpoints/super_admin.py
    - backend/tests/test_super_admin_proxy.py

key-decisions:
  - "Semaphore acquired ONCE per asset, outside the retry loop — ensures all retry attempts share one slot, preventing other assets from cutting the line between retry attempts (D-01)"
  - "No reset_concurrency_cache() call in PUT endpoint — D-04/D-05: 60s TTL deferred refresh is sufficient; explicit invalidation would couple the API to the cache module unnecessarily"
  - "Google Ads uses inline import (from app.services.sync.proxy_cache import get_concurrency_semaphore) inside _download_video rather than top-level; DV360 uses top-level import — both patterns valid, no normalization needed for this phase"

requirements-completed:
  - PERF-02

# Metrics
duration: 25min
completed: 2026-05-18
---

# Phase 25 Plan 02: Configurable Concurrency — Semaphore Enforcement + API Summary

**DV360 and Google Ads download paths now acquire a single asyncio.Semaphore slot per asset (outside the retry loop); SuperAdmin GET/PUT /download-concurrency endpoints expose the max_concurrent_downloads setting with Pydantic range validation (1-10)**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-18T18:32:00Z
- **Completed:** 2026-05-18T18:58:53Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Wrapped `_download_video_asset` (DV360) and `_download_video` (Google Ads) retry loops in `async with semaphore:` using the acquire-once-outside-retry-loop pattern; all retry attempts for a single asset share one semaphore slot
- Added `ConcurrencyConfigResponse` and `ConcurrencyConfigRequest` Pydantic models to `super_admin.py`; `ConcurrencyConfigRequest` uses `Field(ge=1, le=10)` to reject out-of-range values before the handler body executes
- Implemented `GET /api/v1/super-admin/download-concurrency` and `PUT /api/v1/super-admin/download-concurrency` endpoints, both guarded by `Depends(get_current_superadmin)`, with audit log line matching existing proxy-config pattern
- Added 8 new tests to `test_super_admin_proxy.py`; all 16 tests (8 existing + 8 new) pass

## Task Commits

1. **Task 1: Wrap DV360 and Google Ads _do_download call sites with semaphore** - `d1cf041` (feat)
2. **Task 2: Add GET/PUT /download-concurrency endpoints + Pydantic models** - `fc0f41b` (feat)
3. **Task 3: Endpoint tests — GET default, PUT happy path, PUT 422, 403 non-SuperAdmin** - `36bed3d` (test)

## Files Created/Modified

- `backend/app/services/sync/dv360_sync.py` - Import get_concurrency_semaphore; semaphore acquire + async with wrap around retry loop in _download_video_asset
- `backend/app/services/sync/google_ads_sync.py` - Inline import get_concurrency_semaphore; semaphore acquire + async with wrap around retry loop in _download_video
- `backend/app/api/v1/endpoints/super_admin.py` - Add Field to pydantic import; add ConcurrencyConfigResponse + ConcurrencyConfigRequest models; add GET/PUT /download-concurrency endpoints
- `backend/tests/test_super_admin_proxy.py` - Add _make_system_config_concurrency helper + 8 new /download-concurrency tests

## Decisions Made

- Semaphore acquired ONCE per asset, outside the retry loop (D-01 compliance) — if acquired inside the loop, each retry attempt would release and re-acquire, allowing other assets to cut the line between retries
- No `reset_concurrency_cache()` call in the PUT endpoint — D-04/D-05 explicitly defer to 60s TTL refresh; coupling the API to the cache module's internals would make the endpoint harder to test and violates the separation of concerns
- DV360 uses a top-level import (`from app.services.sync.proxy_cache import get_proxy_config, get_concurrency_semaphore`); Google Ads uses an inline import inside `_download_video`. Both are correct; the Google Ads inline import follows the existing pattern in that file for `get_proxy_config`

## Deviations from Plan

### Pre-existing Test Failures (not introduced by this plan)

**3 tests were already failing on main branch before Plan 25-02 execution:**

- `test_dv360_sync.py::test_remote_components_present_in_both_phases`
- `test_google_ads_sync.py::test_remote_components_present_in_both_phases`
- `test_google_ads_sync.py::test_download_video_with_proxy`

All 3 assert `remote_components == "ejs:github"` (string) but production code uses `["ejs:github"]` (list). Verified pre-existing by running against main branch code in container. Documented in `deferred-items.md`. No regressions introduced by this plan — 12 of the 15 non-concurrency tests pass (3 pre-existing failures excluded).

## Known Stubs

None — all endpoints wire directly to SystemConfig DB column.

## Threat Surface Scan

No new trust-boundary surface added beyond what the threat model covers:

| Threat ID | Status |
|-----------|--------|
| T-25-06 | Mitigated — Pydantic Field(ge=1, le=10) rejects 0/11/-1 with HTTP 422; tested explicitly |
| T-25-07 | Mitigated — Depends(get_current_superadmin) on both endpoints; tested in test_download_concurrency_endpoints_reject_non_superadmin |
| T-25-10 | Mitigated — _do_download is a closure; grep confirms no module-level import possible |

## Self-Check

Files created/modified:
- `backend/app/services/sync/dv360_sync.py` — FOUND
- `backend/app/services/sync/google_ads_sync.py` — FOUND
- `backend/app/api/v1/endpoints/super_admin.py` — FOUND
- `backend/tests/test_super_admin_proxy.py` — FOUND

Commits:
- d1cf041 — FOUND
- fc0f41b — FOUND
- 36bed3d — FOUND

## Self-Check: PASSED

---
*Phase: 25-configurable-concurrency*
*Completed: 2026-05-18*
