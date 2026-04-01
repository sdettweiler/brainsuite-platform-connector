---
phase: 09-ai-metadata-auto-fill
plan: 01
subsystem: api
tags: [openai, gpt4o, whisper, sqlalchemy, alembic, pillow, imageio-ffmpeg, ai-inference, metadata]

# Dependency graph
requires:
  - phase: 05-brainsuite-image-scoring
    provides: MetadataField model, AssetMetadataValue model, asset binary download patterns
  - phase: 03-brainsuite-scoring-pipeline
    provides: session-per-operation pattern from scoring_job.py
provides:
  - AIInferenceTracking SQLAlchemy model with PENDING/COMPLETE/FAILED state machine
  - ai_autofill.py service routing 7 auto_fill_type values via GPT-4o Vision + Whisper
  - Alembic migration adding auto_fill_enabled/auto_fill_type to metadata_fields, widening value to Text, creating ai_inference_tracking table
  - OPENAI_API_KEY optional setting with graceful no-op fallback
  - 24 passing unit tests (10 model/schema + 14 service)
affects: [09-02, 09-03, sync-services, metadata-field-admin]

# Tech tracking
tech-stack:
  added: [openai>=2.0.0, Pillow>=10.0.0]
  patterns:
    - session-per-operation (Phase 1 read, Phase 2 download, Phase 3 OpenAI, Phase 4 write)
    - on_conflict_do_nothing for tracking row idempotency
    - FAILED→PENDING retry gate (D-12)
    - COMPLETE guard to prevent re-inference (AI-06)

key-files:
  created:
    - backend/app/models/ai_inference.py
    - backend/app/services/ai_autofill.py
    - backend/alembic/versions/o6p7q8r9s0t1_add_ai_autofill_columns.py
    - backend/tests/test_ai_autofill.py
    - backend/tests/test_ai_metadata_models.py
  modified:
    - backend/app/models/metadata.py
    - backend/app/models/__init__.py
    - backend/app/core/config.py
    - backend/app/schemas/creative.py
    - backend/app/api/v1/endpoints/assets.py
    - backend/requirements.txt

key-decisions:
  - "AsyncOpenAI at module-level import (not deferred) to allow patch() in tests"
  - "_set_status and _write_values are separate awaitable helpers so routing tests can patch them"
  - "get_object_storage imported at module level so it can be patched in tests"
  - "_make_db_session_mock helper in test file accounts for extra execute call for FAILED→PENDING update"

patterns-established:
  - "Pattern: _autofill 4-phase (read/download/infer/write) — no DB session held during OpenAI calls"
  - "Pattern: pg_insert on_conflict_do_nothing for idempotent tracking row insertion"
  - "Pattern: FAILED resets to PENDING via explicit UPDATE before proceeding (D-12)"

requirements-completed: [AI-01, AI-02, AI-03, AI-05, AI-06]

# Metrics
duration: 28min
completed: 2026-04-01
---

# Phase 09 Plan 01: AI Metadata Auto-Fill Backend Summary

**AIInferenceTracking model + ai_autofill.py service routing 7 auto_fill_type values via GPT-4o Vision and Whisper with session-per-operation pattern and 24 passing tests**

## Performance

- **Duration:** 28 min
- **Started:** 2026-04-01T18:00:42Z
- **Completed:** 2026-04-01T18:28:00Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Created AIInferenceTracking model (ai_inference_tracking table) with PENDING/COMPLETE/FAILED state machine, unique asset_id constraint, and status index
- Created ai_autofill.py with full 4-phase pattern: DB read (session closed), asset download, OpenAI inference (outside session), DB write (new session) — matching scoring_job.py established pattern
- Created Alembic migration o6p7q8r9s0t1 adding auto_fill_enabled + auto_fill_type to metadata_fields, widening asset_metadata_values.value to Text, and creating ai_inference_tracking table
- 24 unit tests passing: 10 model/schema tests (Task 1) + 14 service behavior tests (Task 2) covering all 7 routing paths, edge cases, and D-09/D-12 behaviors

## Task Commits

Each task was committed atomically:

1. **Task 1: Alembic migration + models + config + dependencies** - `0a62f86` (feat)
2. **Task 2: ai_autofill.py service + comprehensive test suite** - `963feb7` (feat)

## Files Created/Modified

- `backend/app/models/ai_inference.py` - AIInferenceTracking model with PENDING/COMPLETE/FAILED status and uq_ai_inference_asset unique constraint
- `backend/app/services/ai_autofill.py` - Full auto-fill orchestration: run_autofill_for_asset(), _autofill(), _run_vision(), _run_whisper(), _extract_audio_bytes(), _downsample_image(), _extract_first_frame(), _write_values(), _set_status()
- `backend/alembic/versions/o6p7q8r9s0t1_add_ai_autofill_columns.py` - Migration: 2 new columns, widened value column, new tracking table
- `backend/tests/test_ai_autofill.py` - 14 service tests covering all behaviors
- `backend/tests/test_ai_metadata_models.py` - 10 model/schema tests
- `backend/app/models/metadata.py` - Added auto_fill_enabled + auto_fill_type columns to MetadataField
- `backend/app/models/__init__.py` - Registered AIInferenceTracking
- `backend/app/core/config.py` - Added OPENAI_API_KEY: Optional[str] = None
- `backend/app/schemas/creative.py` - Added auto_fill_enabled + auto_fill_type to MetadataFieldCreate and MetadataFieldResponse
- `backend/app/api/v1/endpoints/assets.py` - Updated update_metadata_field_v2 allowed set and return statement
- `backend/requirements.txt` - Added openai>=2.0.0 and Pillow>=10.0.0

## Decisions Made

- AsyncOpenAI imported at module level (not deferred inside function) to allow `patch()` in unit tests — deferred import breaks `patch("app.services.ai_autofill.AsyncOpenAI")`
- `get_object_storage` imported at module level for same patchability reason
- `_set_status` and `_write_values` extracted as separate awaitable helpers so routing tests can patch them out and focus on value routing logic
- Test file uses `_make_db_session_mock()` helper that automatically injects an extra execute side_effect when tracking status is FAILED (accounts for the UPDATE FAILED→PENDING call in _autofill)

## Deviations from Plan

None - plan executed exactly as written.

The one deviation from initial implementation was fixing the `get_object_storage` import: originally placed inside the function body as in the RESEARCH skeleton, moved to module-level to support patching in tests. This is a test hygiene fix, not a functional deviation.

## Issues Encountered

- openai and Pillow packages not installed in local Python environment — installed with pip3 install before running tests. These are already added to requirements.txt for Docker deployment.
- Initial test runs for routing tests (3-11) failed because they called `_autofill` directly but only mocked 3 execute side_effects; the `_set_status` call at the end of `_autofill` opened a new session and triggered a 4th execute. Fixed by patching `_set_status` in all tests that call `_autofill` directly.

## User Setup Required

None - no external service configuration required for this plan.

`OPENAI_API_KEY` is optional — the service degrades gracefully to `default_value` fallback when absent.

## Next Phase Readiness

- AIInferenceTracking model and ai_autofill.py ready for Plan 02 (sync service integration)
- Alembic migration ready to apply — must be applied before sync services trigger auto-fill
- `run_autofill_for_asset(asset_id, org_id)` is the public API for sync service integration via `asyncio.create_task()`

---
*Phase: 09-ai-metadata-auto-fill*
*Completed: 2026-04-01*
