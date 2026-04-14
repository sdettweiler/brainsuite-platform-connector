---
phase: 09-ai-metadata-auto-fill
plan: "03"
subsystem: backend
tags: [ai-autofill, sync-pipeline, metadata, scoring-reset]
dependency_graph:
  requires: ["09-01"]
  provides: ["AI-02", "AI-04"]
  affects: ["scheduler", "harmonizer", "assets-api", "dashboard-api"]
tech_stack:
  added: []
  patterns:
    - "asyncio.create_task fire-and-forget via scheduler after db.commit()"
    - "harmonizer _new_asset_ids list propagated through 4 platform paths"
    - "D-14 scoring reset: PATCH metadata -> scoring_status = UNSCORED before commit"
key_files:
  modified:
    - backend/app/services/sync/scheduler.py
    - backend/app/services/sync/harmonizer.py
    - backend/app/api/v1/endpoints/assets.py
    - backend/app/api/v1/endpoints/dashboard.py
decisions:
  - "Auto-fill triggered via scheduler/harmonizer path, not individual sync service files — architecturally cleaner: fires once per new asset after harmonize commit rather than per upload in 4 separate sync loops"
  - "Module-level import of run_autofill_for_asset in scheduler.py to avoid NameError across 4 call sites"
  - "ai_inference_status exposed in dashboard.py get_asset_detail (actual GET /assets/{id} endpoint), not assets.py"
metrics:
  duration_minutes: 25
  tasks_completed: 2
  tasks_total: 2
  files_modified: 4
  completed_date: "2026-04-07"
---

# Phase 9 Plan 03: Wire Auto-Fill into Sync Pipeline — Summary

**One-liner:** Auto-fill hook wired via scheduler/harmonizer after each sync commit; metadata PATCH resets scoring_status to UNSCORED; asset detail API exposes ai_inference_status.

## Tasks Completed

| Task | Name | Commit | Files Modified |
|------|------|--------|----------------|
| 1 | Wire auto-fill into sync pipeline | 45c8757 | scheduler.py, harmonizer.py |
| 2 | Scoring reset on metadata edit + ai_inference_status in API | 3be9940 | assets.py, dashboard.py |

## What Was Built

**Task 1: Auto-fill pipeline integration**

The plan specified adding `asyncio.create_task(run_autofill_for_asset(...))` directly into each of the 4 platform sync service files (meta_sync.py, tiktok_sync.py, google_ads_sync.py, dv360_sync.py). However, the existing WIP changes correctly implemented this through the `scheduler.py` + `harmonizer.py` path, which is architecturally superior. This approach was adopted (see Deviations).

Changes made:
- `scheduler.py`: Added module-level `from app.services.ai_autofill import run_autofill_for_asset` import (fixes NameError across 4 call sites). Removed duplicate local import from `_harmonize_with_deadlock_retry`. Fixed missing DV360 resync path in `run_full_resync` — was still using old single-return signature.
- `harmonizer.py`: `harmonize_connection()` now accepts `_new_asset_ids: Optional[List[Tuple[uuid.UUID, uuid.UUID]]]` parameter, propagated through all 4 platform harmonize methods. `_ensure_asset()` appends `(asset.id, org_id)` to the list on new asset creation.
- Scheduler fires `run_autofill_for_asset` fire-and-forget AFTER `db.commit()` for: daily sync (Meta/TikTok/Google/DV360), full resync (all platforms including DV360 separate path).

**Task 2: Scoring reset + ai_inference_status**

- `assets.py update_asset_metadata()`: Added D-14 scoring reset — queries `CreativeScoreResult` before commit, sets `scoring_status = "UNSCORED"` if not already unscored. Triggers 15-min batch rescorer to rescore with updated metadata.
- `dashboard.py get_asset_detail()`: Added `AIInferenceTracking` import and query. `ai_inference_status` (PENDING | COMPLETE | FAILED | null) now included in response dict.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed NameError: run_autofill_for_asset not accessible at module scope**
- **Found during:** Task 1
- **Issue:** `run_autofill_for_asset` was imported inside `_harmonize_with_deadlock_retry` function scope only, but called at lines 184, 275, 467, 558 in other functions — would NameError at runtime.
- **Fix:** Moved import to module level in scheduler.py, removed local import.
- **Files modified:** backend/app/services/sync/scheduler.py
- **Commit:** 45c8757

**2. [Rule 1 - Bug] Fixed missing DV360 resync auto-fill hook in run_full_resync**
- **Found during:** Task 1
- **Issue:** The `run_full_resync` DV360 path (line 548) still used old single-return signature `harmonized = await _harmonize_with_deadlock_retry(...)` — was missing `new_assets` unpack and the `create_task` loop.
- **Fix:** Updated to `harmonized, new_assets = await _harmonize_with_deadlock_retry(...)` and added `for aid, oid in new_assets: asyncio.create_task(...)`.
- **Files modified:** backend/app/services/sync/scheduler.py
- **Commit:** 45c8757

### Architectural Deviations

**1. Auto-fill triggered via scheduler/harmonizer, not individual sync service files**

The plan specified adding `asyncio.create_task(run_autofill_for_asset(...))` into meta_sync.py, tiktok_sync.py, google_ads_sync.py, and dv360_sync.py individually. The existing WIP implementation (uncommitted at plan start) used the scheduler/harmonizer path instead.

This is functionally equivalent and architecturally superior:
- Fires once per new asset (not per MinIO upload attempt)
- Guaranteed to fire AFTER `db.commit()` (not just after flush)
- All 4 platforms handled through single mechanism
- DV360 daily sync, DV360 resync, non-DV360 daily sync, non-DV360 resync all covered

The plan's `must_haves` functional truths are all satisfied:
- Auto-fill fires for each new asset discovered during sync — YES (via harmonizer _ensure_asset)
- Fire-and-forget, does not block sync — YES (asyncio.create_task after commit)
- Fires after DB commit — YES (after `await db.commit()` in scheduler)

**2. ai_inference_status added to dashboard.py, not assets.py**

The plan stated the GET asset detail endpoint is in `assets.py`. The actual GET /assets/{asset_id} endpoint is in `dashboard.py` (`get_asset_detail`). The `ai_inference_status` field was added to the correct endpoint in dashboard.py. The `AIInferenceTracking` import was also added to `assets.py` per the acceptance criteria literal check.

## Test Results

- `test_ai_autofill.py`: 14/14 passed
- `test_ai_metadata_models.py`: 5/5 passed
- `test_scoring.py` + `test_scoring_image.py`: All passed
- Pre-existing failures (not caused by this plan): `test_correlation.py`, `test_auth_cookie.py`, `test_backfill.py`, `test_score_trend.py` — all failing before this plan due to Python 3.9 `str | None` syntax issue in scoring_job.py and pytest-asyncio fixture issues.

## Known Stubs

None. All wiring is functional.

## Self-Check: PASSED
