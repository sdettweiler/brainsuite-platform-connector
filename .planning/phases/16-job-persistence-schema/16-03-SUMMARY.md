---
phase: 16-job-persistence-schema
plan: "03"
subsystem: backend/services/sync
tags: [maintenance, scheduler, apscheduler, background-jobs, wave-2]
dependency_graph:
  requires:
    - "16-01 (BackgroundJob model in app.models.jobs)"
  provides:
    - cleanup_old_background_jobs() async function (backend/app/services/sync/maintenance.py)
    - cleanup_background_jobs APScheduler job registered in startup_scheduler()
  affects:
    - backend/app/services/sync/scheduler.py (startup_scheduler updated)
    - background_jobs table (nightly DELETE of records older than 30 days)
tech_stack:
  added: []
  patterns:
    - purge_read_notifications() pattern from scheduler.py (async with get_session_factory)
    - SQLAlchemy bulk DELETE via delete(Model).where()
    - try/except with explicit commit on success, rollback on error and re-raise
    - Lazy import inside SCHEDULER_ENABLED guard (consistent with run_scoring_batch pattern)
key_files:
  created:
    - backend/app/services/sync/maintenance.py
  modified:
    - backend/app/services/sync/scheduler.py
decisions:
  - Import of cleanup_old_background_jobs placed inside SCHEDULER_ENABLED block (not at module level) — consistent with run_scoring_batch pattern; prevents import cost when scheduler is disabled
  - cleanup job inserted between scoring_batch and purge_read_notifications — logical grouping of maintenance jobs, no functional dependency on order
  - replace_existing=True included on cleanup job — satisfies T-16-10 (prevents duplicate registration on hot reload)
metrics:
  duration_minutes: 10
  completed_date: "2026-05-08"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 16 Plan 03: Nightly Cleanup Service Summary

## One-Liner

Async cleanup_old_background_jobs() deletes BackgroundJob records older than 30 days with commit/rollback semantics, registered as a CronTrigger(hour=3) APScheduler job inside the SCHEDULER_ENABLED guard.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create maintenance.py with cleanup_old_background_jobs() | 5674480 | backend/app/services/sync/maintenance.py |
| 2 | Register cleanup job in startup_scheduler() inside SCHEDULER_ENABLED guard | 9a17495 | backend/app/services/sync/scheduler.py |

## What Was Built

### Task 1: maintenance.py

`backend/app/services/sync/maintenance.py` — new file containing `cleanup_old_background_jobs()`:

- Calculates `cutoff_date = datetime.utcnow() - timedelta(days=30)`
- Opens async DB session via `get_session_factory()()`
- Executes `delete(BackgroundJob).where(BackgroundJob.created_at < cutoff_date)` via SQLAlchemy ORM
- On success: calls `await db.commit()`, logs INFO with deleted count (or DEBUG if zero)
- On exception: logs ERROR, calls `await db.rollback()`, re-raises
- Follows exact pattern of `purge_read_notifications()` in scheduler.py:1184-1199

### Task 2: scheduler.py

`startup_scheduler()` updated inside `if _settings.SCHEDULER_ENABLED:` block:

- Lazy import: `from app.services.sync.maintenance import cleanup_old_background_jobs`
- `scheduler.add_job(cleanup_old_background_jobs, trigger=CronTrigger(hour=3, minute=0), id="cleanup_background_jobs", replace_existing=True)`
- Inserted after scoring_batch (line 1233) and before purge_read_notifications (line 1243)
- Satisfies T-16-09 (guard) and T-16-10 (replace_existing=True)

## Verification

- `grep -c "async def cleanup_old_background_jobs" maintenance.py` → 1
- `grep -c "from app.models.jobs import BackgroundJob" maintenance.py` → 1
- `grep -c "timedelta(days=30)" maintenance.py` → 1
- `grep -c "await db.rollback()" maintenance.py` → 1
- `grep -c "await db.commit()" maintenance.py` → 1
- `grep -c "cleanup_old_background_jobs" scheduler.py` → 2 (import + add_job arg)
- `grep -c "cleanup_background_jobs" scheduler.py` → 2 (id= + logger.info)
- `grep -c "CronTrigger(hour=3, minute=0)" scheduler.py` → 2 (cleanup + purge_read)
- cleanup job at line 1238, after scoring_batch (1229), before purge_read_notifications (1243): CONFIRMED
- Both files pass AST syntax check: PASSED

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. Threat mitigations confirmed:
- T-16-08: cutoff_date uses parameterized SQLAlchemy ORM (not string interpolation)
- T-16-09: import and add_job are inside `if _settings.SCHEDULER_ENABLED:` block
- T-16-10: `replace_existing=True` present on cleanup job registration

## Known Stubs

None — maintenance function and scheduler registration are fully wired.

## Self-Check: PASSED

- backend/app/services/sync/maintenance.py: EXISTS (created in Task 1)
- backend/app/services/sync/scheduler.py: MODIFIED (cleanup job registered in Task 2)
- Commit 5674480: EXISTS (Task 1 — maintenance.py)
- Commit 9a17495: EXISTS (Task 2 — scheduler.py)
