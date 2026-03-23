---
phase: 02-security-hardening
plan: 06
subsystem: frontend-types, backend-api
tags: [typescript, api-contracts, error-shapes, tdd, qual-02, qual-03, qual-04]
dependency_graph:
  requires: [02-01, 02-03, 02-04]
  provides: [typed-api-interfaces, consistent-204-responses, error-shape-tests]
  affects: [frontend-compilation, backend-api-contract, test-suite]
tech_stack:
  added: []
  patterns: [TypeScript interface typing for HTTP responses, TDD red-green cycle, FastAPI Response(status_code=204)]
key_files:
  created:
    - backend/tests/test_error_shapes.py
  modified:
    - frontend/src/app/core/services/auth.service.ts
    - frontend/src/app/features/configuration/pages/platforms.component.ts
    - frontend/src/app/features/dashboard/dashboard.component.ts
    - frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts
    - backend/app/api/v1/endpoints/platforms.py
    - backend/app/core/redis.py
decisions:
  - "snake_case field names in TypeScript interfaces match the JSON wire format from FastAPI"
  - "AssetDetailResponse defined locally in dialog component (not shared) to stay minimal — no shared types library yet"
  - "DashboardAsset typed locally in dashboard component — matches actual API response fields from dashboard.py"
  - "Deleted both /apps/{app_id} AND /brainsuite-apps/{app_id} alias to return 204 consistently"
metrics:
  duration_minutes: 25
  tasks_completed: 2
  files_modified: 6
  completed_date: "2026-03-23"
---

# Phase 02 Plan 06: API Response Typing and Error Shape Consistency Summary

Eliminated all `Observable<any>` / `http.get<any>` API response types from 4 priority frontend files (QUAL-02) and fixed DELETE endpoints to return 204 with no body, with full test coverage for error shapes (QUAL-03).

## Tasks Completed

### Task 1: Add typed interfaces for all API response DTOs in frontend

Added named TypeScript interfaces for all API response DTOs across 4 priority files:

**auth.service.ts** — `RegisterResponse` already added by a prior plan (verified in place).

**platforms.component.ts:**
- Added `OAuthAccount`, `OAuthSessionResponse`, `DV360LookupResponse` interfaces
- Replaced `get<any>` in `checkOAuthSession()` with `get<OAuthSessionResponse>`
- Replaced `post<any>` in `lookupDv360Advertiser()` with `post<DV360LookupResponse>`
- Typed `pendingAccounts: any[]` as `OAuthAccount[]`

**dashboard.component.ts:**
- Added `AssetPerformance`, `DashboardAsset`, `DashboardAssetsResponse`, `StatsResponse` interfaces
- Replaced `get<any>('/dashboard/assets', ...)` with `get<DashboardAssetsResponse>`
- Replaced `get<any>('/dashboard/stats', ...)` with `get<StatsResponse>`
- Typed `assets`, `stats`, `contextMenu.asset`, `assetDetailCache` class properties
- Typed all asset method parameters (`selectAsset`, `onRightClick`, `openAssetDetail`, etc.)
- Fixed `pctChange()` and `changeClass()` to accept `number | null` (required by nullable backend fields)

**asset-detail-dialog.component.ts:**
- Added `AssetPerformanceDetail`, `AssetTimeseriesPoint`, `AssetBrainsuiteMetadata`, `AssetDetailResponse` interfaces
- Replaced `get<any>('/dashboard/assets/${assetId}', ...)` with `get<AssetDetailResponse>`
- Typed `asset` and `detail` class properties as `AssetDetailResponse | null`
- Typed `data.preloaded` dialog input as `AssetDetailResponse | null`
- Used non-null assertion `this.detail!.timeseries!` with explicit null-check guard above

**Verification:** `cd frontend && npx tsc --noEmit` exits 0.

### Task 2: Fix error response consistency (QUAL-03) and implement error shape tests (TDD)

**RED phase:** Implemented 3 tests in `test_error_shapes.py` (replaced all `pytest.mark.skip` stubs):
- `test_error_response_has_detail_key`: POST `/auth/login` with bad credentials → 401 → `{"detail": "..."}` shape confirmed, no `"error"` key
- `test_delete_returns_204`: DELETE `/platforms/apps/{id}` → expected 204, got 200 (FAILED as expected)
- `test_logout_returns_204`: POST `/auth/logout` → 204 confirmed (PASSED, already fixed in plan 02-03)

**GREEN phase:** Fixed `platforms.py` DELETE endpoints:
- `DELETE /apps/{app_id}`: Changed from `return {"detail": "App deleted"}` (HTTP 200) to `return Response(status_code=204)` with `status_code=204` decorator
- `DELETE /brainsuite-apps/{app_id}` (alias route): Same fix applied
- Added `Response` import from fastapi

All 3 tests now pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Python 3.9 incompatible type annotation in redis.py**
- **Found during:** Task 2 RED phase (test execution)
- **Issue:** `_redis_client: aioredis.Redis | None = None` uses Python 3.10+ union syntax (`X | Y`) which fails on Python 3.9 (test environment). All tests using the `app` fixture (which imports main.py → api_router → platforms.py → redis.py) were failing at collection time.
- **Fix:** Changed to `Optional[aioredis.Redis]` from `typing` module — compatible with Python 3.9+
- **Files modified:** `backend/app/core/redis.py`
- **Commit:** 6f667a9

## Verification Results

- `cd frontend && npx tsc --noEmit` — zero errors
- `cd backend && python3 -m pytest tests/test_error_shapes.py -v` — 3/3 tests pass
- `cd backend && python3 -m pytest tests/ -x -q` — 37 passed, 2 skipped
- `grep -rn "Observable<any>" [4 priority files]` — returns empty

## Self-Check: PASSED

All key files confirmed present. All 3 task commits confirmed in git log.
- frontend/src/app/features/configuration/pages/platforms.component.ts: FOUND
- backend/tests/test_error_shapes.py: FOUND
- Commit 75b8e3b (Task 1 typed interfaces): FOUND
- Commit 6f667a9 (Task 2 RED failing tests + redis.py fix): FOUND
- Commit 8a96e91 (Task 2 GREEN DELETE 204 fix): FOUND
