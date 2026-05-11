---
phase: 17-service-instrumentation
plan: "04"
subsystem: api
tags: [sqlalchemy, asyncio, postgresql, background-jobs, job-tracker, ai-autofill, gemini, whisper]

requires:
  - phase: 17-service-instrumentation
    plan: "01"
    provides: create_background_job/update_background_job helpers in job_tracker.py

provides:
  - run_autofill_for_asset() creates BackgroundJob (job_type="autofill") per invocation
  - _autofill() returns D-10 output dict: fields list, whisper_transcript, language
  - FAILED path captures D-13 error dict with traceback truncated at 10000 chars

affects:
  - 17-06 (Wave 3 test implementation — test_autofill_output_schema fills in assertions for run_autofill_for_asset)
  - 19 (SuperAdmin Monitoring UI — MON-03 drill-in reads fields/whisper_transcript/language from BackgroundJob.output)

tech-stack:
  added: []
  patterns:
    - "D-10 autofill output JSONB: fields list with name/value/source/confidence per field, plus whisper_transcript and language at top level"
    - "field_data 4-tuple: (id, auto_fill_type, default_value, name) — name preserved in tuple for output construction after session closes"
    - "Early-return paths return None; run_autofill_for_asset provides empty D-10 default via `autofill_output or {...}`"

key-files:
  created: []
  modified:
    - backend/app/services/ai_autofill.py

key-decisions:
  - "Extend field_data tuple to 4 elements (adds name) rather than doing a second DB query after session closes — name is already loaded in Phase 1 query"
  - "Import create_background_job/update_background_job at module level (not inside function) — cleaner than local import, no circular dependency risk"
  - "Early-return paths (COMPLETE guard, no-fields guard) continue to return None implicitly — run_autofill_for_asset guards with `autofill_output or {...}` to ensure valid D-10 output always reaches BackgroundJob"

patterns-established:
  - "D-10 source map: gemini fields (language, brand_names), whisper fields (vo_transcript, vo_language), sync fields (campaign_name, ad_name), fixed_value fields → fixed"

requirements-completed:
  - INSTR-03

duration: ~2min
completed: 2026-05-11
---

# Phase 17 Plan 04: Autofill Instrumentation Summary

**run_autofill_for_asset() wired to BackgroundJob tracking with D-10 structured output (fields/source/whisper_transcript/language) for MON-03 drill-in**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-11T07:59:29Z
- **Completed:** 2026-05-11T08:01:07Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- `run_autofill_for_asset()` creates a BackgroundJob (job_type="autofill", D-06) at function entry before any inference begins, then updates to RUNNING (progress_total=1) immediately after
- `_autofill()` now returns a D-10 output dict (`{"fields": [...], "whisper_transcript": ..., "language": ...}`) built from `field_data` + `values_to_write` at completion of the happy path
- FAILED path captures D-13 error dict (type/message/traceback truncated at 10000 chars) and calls `_set_status(asset_id, "FAILED")` as before
- `field_data` tuple extended from 3 to 4 elements to include `f.name`, enabling output field list construction without a second DB query

## Task Commits

Each task was committed atomically:

1. **Task 1: Instrument run_autofill_for_asset and refactor _autofill to return D-10 output dict** - `5c0da9c` (feat)

**Plan metadata:** (final doc commit — see below)

## Files Created/Modified

- `backend/app/services/ai_autofill.py` — run_autofill_for_asset instrumented with BackgroundJob create/update; _autofill returns D-10 dict; field_data 4-tuple with name field

## Decisions Made

- Followed the plan action exactly as specified — no deviations needed.
- Module-level import used (not local import inside function body) for consistency with other imports in the file.
- Early-return paths in `_autofill` (COMPLETE guard, no-fields guard) remain unchanged — they still return None implicitly. The fallback `autofill_output or {"fields": [], "whisper_transcript": None, "language": None}` in `run_autofill_for_asset` ensures the BackgroundJob always receives a valid D-10 dict.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Worktree was behind `main` at execution start (job_tracker.py from plan 17-01 was committed on main but not merged into this worktree). Resolved via `git merge main` (fast-forward). No conflicts.
- `python` not available at host; used `python3` for syntax check. Docker exec still used for test run.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `ai_autofill.py` now emits BackgroundJob records per autofill run; plan 17-05 (scoring instrumentation) is the final Wave 2 plan
- `test_instrumentation.py::test_autofill_output_schema` stub is ready for Wave 3 (plan 17-06) to fill in assertions
- No blockers

---

## Self-Check

- `backend/app/services/ai_autofill.py` contains `from app.services.sync.job_tracker import create_background_job, update_background_job` — VERIFIED (line 30)
- `backend/app/services/ai_autofill.py` contains `job_type="autofill"` — VERIFIED (line 127)
- `backend/app/services/ai_autofill.py` contains `progress_total=1` — VERIFIED (line 134)
- `backend/app/services/ai_autofill.py` contains `"whisper_transcript":` in D-10 return — VERIFIED (line 336)
- `backend/app/services/ai_autofill.py` contains `"fields": fields_output` — VERIFIED (line 335)
- `backend/app/services/ai_autofill.py` uses 4-element unpacking — VERIFIED (lines 282, 325)
- Python syntax check: PASSED
- `pytest tests/services/ -x -q`: 3 passed, 7 skipped, 0 failures — PASSED
- Commit `5c0da9c` — FOUND

## Self-Check: PASSED

---
*Phase: 17-service-instrumentation*
*Completed: 2026-05-11*
