---
phase: 17-service-instrumentation
plan: "05"
subsystem: api
tags: [sqlalchemy, asyncio, postgresql, background-jobs, scoring, job-tracker, pytest]

requires:
  - phase: 17-service-instrumentation
    plan: "01"
    provides: create_background_job/update_background_job helpers in job_tracker.py

provides:
  - _process_asset() in scoring_job.py creates one BackgroundJob per scored asset (D-07)
  - D-08 output dict (score, endpoint_type, brainsuite_job_id, dimensions) on COMPLETE
  - D-09 metadata dict (asset_id, creative_score_result_id) on BackgroundJob creation
  - D-13 error schema: BrainSuiteJobError uses empty traceback; general Exception truncates at 10KB

affects:
  - 17-06 (Wave 3 test implementation — test_scoring_output_schema fills in assertions)
  - Phase 19 MON-06 (renders per-asset scores by reading BackgroundJob.output)
  - Phase 19 MON-07 (shows brainsuite_job_id from BackgroundJob.metadata_)

tech-stack:
  added: []
  patterns:
    - "bg_job_id = None declared before try block — accessible in all except handlers even when create_background_job not yet called (guard path pattern)"
    - "Guard paths (_mark_unscored returns) leave bg_job_id = None — no BackgroundJob for skipped assets (not scoring runs)"
    - "BackgroundJob creation placed after both guards inside try — only scoreable assets get a BackgroundJob record"
    - "D-13 dual-traceback pattern: BrainSuiteJobError uses empty string; general Exception uses traceback.format_exc()[:10000]"

key-files:
  created: []
  modified:
    - backend/app/services/sync/scoring_job.py

key-decisions:
  - "bg_job_id declared before try (not inside) so except handlers can use if bg_job_id is not None: safely — no NameError risk"
  - "BackgroundJob creation placed AFTER both guard paths (config guard + mandatory fields guard) — skipped assets are not scoring runs per INSTR-04 scope; creating a job for them would pollute the monitoring dashboard"
  - "module-level import traceback at top of file alongside other imports — avoids per-except-block import; consistent with project import style"

metrics:
  duration: 20min
  completed: 2026-05-11T08:07:55Z
  tasks: 1
  files_modified: 1
---

# Phase 17 Plan 05: Scoring Job BackgroundJob Instrumentation Summary

**Per-asset BackgroundJob tracking wired into _process_asset() with D-08 output (score, endpoint_type, brainsuite_job_id, dimensions) and D-09 metadata (asset_id, creative_score_result_id), satisfying INSTR-04 and INSTR-05**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-11T07:47:00Z
- **Completed:** 2026-05-11T08:07:55Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- `scoring_job.py` imports `create_background_job` and `update_background_job` from `job_tracker`
- `traceback` stdlib module imported at module level for D-13 error schema
- `bg_job_id = None` declared before the outer `try` block so except handlers can safely reference it
- `create_background_job(job_type="scoring", ...)` called inside the `try` block AFTER both guard paths — skipped assets (no config, missing mandatory fields) return early without creating a BackgroundJob
- `update_background_job(status="RUNNING", progress_total=1, progress_current=0)` called immediately after create
- On successful score poll and COMPLETE DB write: `update_background_job(status="COMPLETE", progress_current=1, output=D-08 dict)` — captures score, endpoint_type, brainsuite_job_id, dimensions
- `BrainSuiteJobError` except block: `update_background_job(status="FAILED", error={"type": "BrainSuiteJobError", "message": ..., "traceback": ""})` — empty traceback string per D-13
- General `Exception` except block: `update_background_job(status="FAILED", error={"type": ..., "message": ..., "traceback": traceback.format_exc()[:10000]})` — 10 KB cap per D-13
- All `CreativeScoreResult` writes (total_score, total_rating, score_dimensions, scoring_status, scored_at, updated_at) remain completely unchanged

## Task Commits

1. **Task 1: Add BackgroundJob instrumentation to _process_asset in scoring_job.py** - `6b61bcc` (feat)

## Files Created/Modified

- `backend/app/services/sync/scoring_job.py` — `_process_asset()` now creates one BackgroundJob per scored asset with D-08 output and D-09 metadata; guard paths unchanged; existing CreativeScoreResult writes unchanged

## Decisions Made

- **Guard path placement decision:** The plan's behavior section says "Guard paths do NOT create BackgroundJobs" and "BackgroundJob created BEFORE the try block." These are contradictory since guards are inside the try. Resolved by: `bg_job_id = None` declared before the try, `create_background_job()` called inside the try but AFTER both guards. This satisfies both constraints: guards return with bg_job_id=None (no BackgroundJob created), and except handlers can safely check `if bg_job_id is not None:`.
- **Module-level traceback import:** Added `import traceback` at module level alongside other stdlib imports rather than using `import traceback as _tb` inside the except block. Consistent with existing import style and avoids confusion about the `_tb` alias.

## Deviations from Plan

### Auto-applied Clarifications

**1. [Clarification] bg_job_id placement inside try vs before try**
- **Found during:** Task 1 implementation
- **Issue:** Plan's `<behavior>` said "BackgroundJob created BEFORE the try block" while also saying "Guard paths do NOT create BackgroundJobs." These are contradictory since guards are inside the try.
- **Fix:** `bg_job_id = None` declared before try (as plan action instructed); `create_background_job()` placed inside the try after both guard paths. This satisfies both stated behaviors.
- **Files modified:** `backend/app/services/sync/scoring_job.py`
- **Commit:** `6b61bcc`

## Verification Results

- Python syntax check: PASSED (`python3 -c "import ast; ast.parse(...)"`)
- Import check: PASSED (`from app.services.sync.job_tracker import create_background_job, update_background_job` present at line 39)
- `pytest tests/services/ -x -q` inside Docker container: 3 passed, 7 skipped, 0 failures
- Module import check: PASSED (`from app.services.sync.scoring_job import _process_asset` in container)

## Known Stubs

None — all instrumentation is fully wired. The 7 test stubs in `test_instrumentation.py` (including `test_scoring_output_schema`) are Wave 0 scaffolds from plan 17-01; they will be filled in by plan 17-06 (Wave 3).

## Threat Flags

No new security surface introduced. The scoring instrumentation adds JSONB output fields sourced exclusively from BrainSuite API responses and internal asset UUIDs — no user-controlled fields reach BackgroundJob.output. Traceback truncation at 10000 chars (D-13) satisfies T-17-14.

---

## Self-Check

- `backend/app/services/sync/scoring_job.py` — FOUND and verified
- Commit `6b61bcc` — FOUND (`git log --oneline` confirms)
- Import line present at line 39 — VERIFIED
- `job_type="scoring"` at line 406 — VERIFIED
- `"creative_score_result_id": str(score_id)` at line 411 — VERIFIED
- `"brainsuite_job_id": str(job_id)` at line 561 — VERIFIED
- `"dimensions": score_data["score_dimensions"]` at line 562 — VERIFIED
- `traceback.format_exc()[:10000]` at line 605 — VERIFIED

## Self-Check: PASSED

---
*Phase: 17-service-instrumentation*
*Completed: 2026-05-11*
