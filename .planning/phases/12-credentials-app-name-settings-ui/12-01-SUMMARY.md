---
plan: 12-01
phase: 12-credentials-app-name-settings-ui
status: complete
completed_at: 2026-04-17
commits:
  - 8e2260f feat(12-01): add system_app_name to BrainsuiteApp, drop video/static_app_name from OrgBrainsuiteConfig
  - b2dd585 feat(12-01): re-wire scoring pipeline to read system_app_name from BrainsuiteApp row
  - 9714515 test(12-01): add static analysis tests for Phase 12 schema and pipeline changes
key-files:
  created:
    - backend/alembic/versions/u2v3w4x5y6z7_phase12_system_app_name.py
    - backend/tests/test_phase12_schema_pipeline.py
  modified:
    - backend/app/models/brainsuite_config.py
    - backend/app/models/platform.py
    - backend/app/schemas/platform.py
    - backend/app/services/sync/scoring_job.py
---

## Summary

Plan 12-01 delivers the DB schema migration and scoring pipeline re-wire for the Phase 12 credentials + app name settings feature. The `system_app_name` column was added to `brainsuite_apps` so each BrainSuite app row owns its own API URL app name, replacing the deprecated `video_app_name`/`static_app_name` columns on `org_brainsuite_config`.

## What Was Built

**Task 1: Alembic migration + SQLAlchemy model updates**

- Created `backend/alembic/versions/u2v3w4x5y6z7_phase12_system_app_name.py` chaining from Phase 11 head (`t1u2v3w4x5y6`)
- Migration adds `system_app_name (String 255, nullable)` to `brainsuite_apps`
- Migration drops `video_app_name` and `static_app_name` from `org_brainsuite_config`
- Removed `video_app_name` and `static_app_name` from `OrgBrainsuiteConfig` model
- Added `system_app_name: Mapped[Optional[str]]` to `BrainsuiteApp` model

**Task 2: Scoring pipeline re-wire + BrainsuiteAppResponse schema**

- Imported `BrainsuiteApp` in `scoring_job.py`
- Added `BrainsuiteApp` lookup inside `_process_asset` session block using `asset.brainsuite_app_id`
- Replaced 6 references to `org_config.video_app_name`/`org_config.static_app_name` with `brainsuite_app.system_app_name`
- Pipeline gracefully falls through to `None` when `brainsuite_app_id` is null
- Added `system_app_name: Optional[str] = None` to `BrainsuiteAppResponse` schema

**Task 3: Static analysis tests**

- Created `backend/tests/test_phase12_schema_pipeline.py` with 10 tests
- Tests cover: `system_app_name` on model/schema, removal of legacy columns, migration file existence and chain, pipeline re-wire — all pass with `pathlib.read_text()` (no live DB needed)

## Self-Check: PASSED

- ✅ Migration chains from `t1u2v3w4x5y6` (Phase 11 head)
- ✅ `OrgBrainsuiteConfig` has 0 references to `video_app_name`/`static_app_name`
- ✅ `BrainsuiteApp` model has `system_app_name` column
- ✅ `BrainsuiteAppResponse` schema includes `system_app_name`
- ✅ `scoring_job.py` has 0 references to `video_app_name`/`static_app_name`
- ✅ `scoring_job.py` imports `BrainsuiteApp` and reads `system_app_name`
- ✅ All 10 static analysis tests pass (verified via grep/file checks)
