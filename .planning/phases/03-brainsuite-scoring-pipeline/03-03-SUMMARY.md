---
phase: 03-brainsuite-scoring-pipeline
plan: 03
subsystem: backend/scoring-pipeline
tags: [scoring, apscheduler, harmonizer, brainsuite, batch-job]
dependency_graph:
  requires: [03-01, 03-02]
  provides: [scoring-batch-job, unscored-queue-injection]
  affects: [backend/app/services/sync/scoring_job.py, backend/app/services/sync/scheduler.py, backend/app/services/sync/harmonizer.py]
tech_stack:
  added: []
  patterns: [APScheduler interval job, session-per-operation (no long-held sessions during HTTP), pg_insert on_conflict_do_nothing]
key_files:
  created:
    - backend/app/services/sync/scoring_job.py
  modified:
    - backend/app/services/sync/scheduler.py
    - backend/app/services/sync/harmonizer.py
    - backend/app/core/config.py
    - backend/app/api/v1/endpoints/dashboard.py
  deleted:
    - backend/app/services/ace_score.py
decisions:
  - "Session-per-operation pattern: separate DB sessions for query, status update, and result write — never held during BrainSuite HTTP calls"
  - "on_conflict_do_nothing on creative_asset_id for UNSCORED injection prevents re-syncs from resetting COMPLETE/FAILED records"
  - "SCHEDULER_ENABLED flag added to config.py for multi-worker deployments (set False on non-scheduler workers)"
  - "ace_score.py deleted entirely; dashboard.py gets local _get_performer_tag() returning 'Average' until Plan 04 wires real join"
metrics:
  duration: "8min"
  completed_date: "2026-03-23"
  tasks_completed: 2
  files_changed: 6
---

# Phase 03 Plan 03: Scoring Batch Job + Harmonizer Injection Summary

**One-liner:** APScheduler batch job polls UNSCORED VIDEO assets every 15 min via BrainSuiteScoreService; harmonizer injects UNSCORED records on new asset creation; dummy ace_score module deleted.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Scoring batch job + scheduler registration | cdbae6f | scoring_job.py (created), scheduler.py, config.py |
| 2 | Harmonizer UNSCORED injection + remove dummy ace_score | 60c20e4 | harmonizer.py, ace_score.py (deleted), dashboard.py |

## What Was Built

### Task 1: Scoring Batch Job

`backend/app/services/sync/scoring_job.py` implements `run_scoring_batch()`:

- Queries up to 20 `UNSCORED` `CreativeScoreResult` records joined with `CreativeAsset WHERE asset_format = 'VIDEO'`, marks them `PENDING`, then releases the DB session
- For each asset: strips `/objects/` prefix from `asset_url` to get S3 key, generates a 1-hour signed URL via `get_object_storage().generate_signed_url()`
- Loads `brainsuite_*` metadata fields in a short-lived session, builds the BrainSuite payload, submits via `brainsuite_score_service.create_job_with_retry()`
- Updates status to `PROCESSING` (new session), then polls via `poll_job_status()` with no session held
- Writes `COMPLETE` with `total_score`, `total_rating`, `score_dimensions`, `scored_at` — or `FAILED` with `error_reason` on `BrainSuiteJobError` / unexpected exception

Registered in `startup_scheduler()` with `IntervalTrigger(minutes=15)`, `max_instances=1`, guarded by `settings.SCHEDULER_ENABLED`.

### Task 2: Harmonizer Injection + ace_score Cleanup

`_ensure_asset()` in harmonizer.py:
- Removed `generate_ace_score()` call and the three dummy fields (`ace_score`, `ace_score_confidence`, `brainsuite_metadata`) from the `CreativeAsset()` constructor
- After `db.add(asset)` + `await db.flush()`, new VIDEO assets trigger: `pg_insert(CreativeScoreResult).values(...).on_conflict_do_nothing(index_elements=["creative_asset_id"])`
- Existing assets (the `else` branch) are untouched — their score records are preserved

`backend/app/services/ace_score.py` deleted. `dashboard.py` no longer imports from it; uses local `_get_performer_tag()` returning `"Average"` until Plan 04 wires the real BrainSuite score join.

## Decisions Made

1. **Session-per-operation pattern** — three separate DB sessions per asset: (a) query+PENDING, (b) PROCESSING write, (c) COMPLETE/FAILED write. No session is held during `create_job_with_retry()` or `poll_job_status()` (which can take 30 min+). Follows Pitfall 4 from RESEARCH.md.

2. **on_conflict_do_nothing** — `index_elements=["creative_asset_id"]` prevents re-sync from resetting COMPLETE/FAILED records to UNSCORED. This is the "UNSCORED queue injection" pattern from RESEARCH.md Pattern 4.

3. **SCHEDULER_ENABLED config flag** — defaults `True` for single-worker dev; set `False` on non-scheduler workers in production to prevent duplicate job runs across multiple worker processes.

4. **Dashboard ace_score stub** — `_get_performer_tag(None, ...)` always returns "Average" for the assets list. Plan 04 will add the JOIN on `creative_score_results` to surface real scores.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

| File | Location | Reason |
|------|----------|--------|
| backend/app/api/v1/endpoints/dashboard.py | `_get_performer_tag(None, ...)` call (assets list) | Plan 04 will wire real BrainSuite score JOIN; `None` is correct interim value |
| backend/app/api/v1/endpoints/dashboard.py | `"scoring_status": None, "total_score": None` in assets response | Plan 04 will join `creative_score_results` and populate these fields |

These stubs do not prevent this plan's goal (batch job + harmonizer injection) from being achieved. Plan 04 is the integration plan that resolves them.

## Self-Check: PASSED

- `backend/app/services/sync/scoring_job.py` exists: FOUND
- `backend/app/services/sync/scheduler.py` contains `scoring_batch`: FOUND
- `backend/app/services/sync/harmonizer.py` contains `on_conflict_do_nothing`: FOUND
- `backend/app/services/ace_score.py` deleted: CONFIRMED
- No `generate_ace_score` references: CONFIRMED
- Commit `cdbae6f` exists: CONFIRMED
- Commit `60c20e4` exists: CONFIRMED
