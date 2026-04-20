---
phase: 13-field-mapping-editor-mandatory-field-enforcement
plan: "03"
subsystem: backend-pipeline
tags: [scoring-pipeline, field-mappings, sqlalchemy, notifications, mandatory-fields]

dependency_graph:
  requires:
    - phase: 13-01
      provides: OrgBrainsuiteFieldMapping model with brainsuite_app_id FK and is_mandatory column
    - phase: 13-02
      provides: GET/PUT field-mapping endpoints writing mandatory field config to DB
  provides:
    - _check_mandatory_fields helper in scoring_job.py
    - FMAP-07 guard blocking assets with missing mandatory field values
    - PIPE-02 guard documented on existing config check
    - MANDATORY_FIELD_MISSING notification dispatch via asyncio.create_task
  affects: [phase-13-04-frontend, phase-13-verification]

tech-stack:
  added: []
  patterns:
    - session-per-operation for _check_mandatory_fields (matches existing pattern)
    - asyncio.create_task for fire-and-forget notification dispatch (matches SCORING_BATCH_COMPLETE)
    - module-level service import instead of inline function-level import

key-files:
  created: []
  modified:
    - backend/app/services/sync/scoring_job.py

key-decisions:
  - "_check_mandatory_fields opens its own DB session (session-per-operation) — never holds session during guard check in _process_asset"
  - "PIPE-02 guard was already implemented by the existing PIPE-01 config check; plan only added the clarifying comment"
  - "create_org_notification moved from inline import inside run_scoring_batch to module-level import for shared access"
  - "MANDATORY_FIELD_MISSING notification uses asyncio.create_task (fire-and-forget) — notification failure must not block asset scoring"

patterns-established:
  - "Pipeline guards follow read-from-DB pattern: _check_mandatory_fields queries org_brainsuite_field_mappings directly, independent of UI state (T-13-09 mitigation)"
  - "Guard ordering: PIPE-02 (config check) -> FMAP-07 (field check) -> scoring logic. Earlier guards are cheaper."

requirements-completed: [FMAP-07, PIPE-02]

duration: ~15min
completed: 2026-04-20
---

# Phase 13 Plan 03: Pipeline Enforcement Guards Summary

**FMAP-07 mandatory field guard added to scoring_job.py: _check_mandatory_fields queries DB for missing mandatory field values and fires MANDATORY_FIELD_MISSING notification via asyncio.create_task before skipping asset.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-20T19:09:00Z
- **Completed:** 2026-04-20T19:15:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `_check_mandatory_fields(asset_id, app_id, organization_id)` helper that queries `org_brainsuite_field_mappings` for mandatory mappings and checks `AssetMetadataValue.field_id` for each — returning `(is_valid, missing_field_names)`
- Added FMAP-07 guard block in `_process_asset` after the existing config guard: skips asset scoring, fires `MANDATORY_FIELD_MISSING` notification with asset name and field names, then calls `_mark_unscored`
- Documented PIPE-02 on the existing incomplete-config guard (behavior was already correct per plan analysis)
- Moved `create_org_notification` from inline import inside `run_scoring_batch` to module-level import so both the batch notification block and the new FMAP-07 guard can use it

## Task Commits

1. **Task 1: Add FMAP-07 mandatory field check to scoring pipeline** - `78e3f96` (feat)

## Files Created/Modified

- `backend/app/services/sync/scoring_job.py` — Added `OrgBrainsuiteFieldMapping` import, module-level `create_org_notification` import, `_check_mandatory_fields` helper function, FMAP-07 guard block in `_process_asset`, PIPE-02 comment on existing config guard

## Decisions Made

- `_check_mandatory_fields` opens its own session (session-per-operation pattern) rather than reusing the config-load session, consistent with all other helpers in this file
- `MANDATORY_FIELD_MISSING` notification is fire-and-forget via `asyncio.create_task()` — matches the existing `SCORING_BATCH_COMPLETE` pattern; notification failure must not prevent `_mark_unscored` from running
- PIPE-02 requirement was already satisfied by the existing PIPE-01 config guard; this plan added only the clarifying comment (confirmed by plan spec)

## Deviations from Plan

None — plan executed exactly as written. The plan correctly noted that PIPE-02 was already implemented; only the FMAP-07 guard and `_check_mandatory_fields` required new code.

## Issues Encountered

- The Edit tool initially modified the main repo path instead of the worktree path. Detected via `git status` showing worktree clean. Resolved by reading the worktree file and using Write tool with the correct absolute worktree path. No data was lost.

## User Setup Required

None — no external service configuration required.

## Known Stubs

None — the guard reads directly from DB and all logic is fully wired.

## Threat Mitigations Applied

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-13-09 | `_check_mandatory_fields` queries `org_brainsuite_field_mappings` directly from DB — pipeline cannot be bypassed via frontend state |
| T-13-10 | `MANDATORY_FIELD_MISSING` notification reveals only field names (not values) and asset name/ID to the org's own admins |
| T-13-11 | One notification per asset per scoring run; volume bounded by BATCH_SIZE=20 |

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary crossings introduced. The new code path reads from an existing DB table and calls an existing notification service.

## Next Phase Readiness

- PIPE-02 and FMAP-07 pipeline enforcement is complete
- Phase 13-04 (frontend field mapping editor UI) can proceed independently
- All 18 static analysis tests pass (including `test_scoring_job_has_mandatory_field_check`)

## Self-Check: PASSED

- `backend/app/services/sync/scoring_job.py` — modified, contains `_check_mandatory_fields`, `MANDATORY_FIELD_MISSING`, `OrgBrainsuiteFieldMapping`, `PIPE-02`, `FMAP-07`
- Commit `78e3f96` confirmed in worktree git log
- 18/18 tests pass: `docker-compose exec backend pytest /app/tests/test_phase13_field_mappings.py`

---
*Phase: 13-field-mapping-editor-mandatory-field-enforcement*
*Completed: 2026-04-20*
