---
phase: 10
plan: "01"
subsystem: backend-notifications
tags: [notifications, backend, fan-out, scheduler, scoring]
dependency_graph:
  requires: []
  provides: [create_org_notification, _notify_connection_status, SCORING_BATCH_COMPLETE]
  affects: [scheduler.py, scoring_job.py, notifications.py]
tech_stack:
  added: []
  patterns:
    - session-per-operation (notifications helper opens own DB session)
    - fire-and-forget via asyncio.create_task
    - status-change guard (deduplication before emitting ERROR/EXPIRED notifications)
    - bulk INSERT via sqlalchemy.dialects.postgresql.insert().values([...])
key_files:
  created:
    - backend/app/services/notifications.py
    - backend/tests/test_notifications.py
  modified:
    - backend/app/services/sync/scheduler.py
    - backend/app/services/sync/scoring_job.py
decisions:
  - id: D-01
    summary: "Session-per-operation: create_org_notification opens its own DB session, never accepts a caller session — avoids session reuse across async boundaries"
  - id: D-05
    summary: "SYNC_COMPLETE emitted only on initial_sync_completed=True transition (not on every success), preventing repeat notifications for recurring syncs"
  - id: D-06
    summary: "_notify_connection_status guards against duplicate ERROR/EXPIRED notifications by checking connection.sync_status before emitting"
  - id: D-07
    summary: "SCORING_BATCH_COMPLETE aggregated per-org via Counter before emitting — one notification per org per batch run with correct scored_count"
metrics:
  duration_minutes: 45
  completed_at: "2026-04-09T13:01:34Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 2
---

# Phase 10 Plan 01: Notification Emission Backend Summary

**One-liner:** Session-per-operation fan-out helper (`create_org_notification`) with status-change guards wired into 4 event emission points (SYNC_COMPLETE, SYNC_FAILED, TOKEN_EXPIRED, SCORING_BATCH_COMPLETE).

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Implement create_org_notification() helper | e5197dc | backend/app/services/notifications.py |
| 2 | Wire emission into scheduler.py and scoring_job.py | cf459a4 | backend/app/services/sync/scheduler.py, backend/app/services/sync/scoring_job.py |

## What Was Built

### Task 1: create_org_notification() helper (`notifications.py`)

- Opens its own DB session (session-per-operation pattern)
- Queries active users in org via `User.is_active == True` filter
- Bulk-inserts one `Notification` row per user via `insert(Notification).values([...])`
- Returns count of rows inserted (0 if no active users)
- No `db` parameter — avoids caller session reuse across async boundaries

### Task 2: Emission wiring

**scheduler.py:**
- Added module-level `PLATFORM_DISPLAY` dict for human-readable platform names
- Added `_notify_connection_status(connection, new_status)` guard helper:
  - Fires `SYNC_FAILED` only when transitioning INTO ERROR (not on repeated failures)
  - Fires `TOKEN_EXPIRED` only when transitioning INTO EXPIRED
  - Uses `asyncio.create_task` for fire-and-forget emission
- Added `await _notify_connection_status(conn, "ERROR")` before all `sync_status = "ERROR"` assignments (10 call sites)
- Added `asyncio.create_task(create_org_notification(..., type="SYNC_COMPLETE"))` at both `initial_sync_completed = True` sites

**scoring_job.py:**
- Added Phase 3.5 block after batch processing loop
- Aggregates scored counts per org via `Counter`
- Emits `SCORING_BATCH_COMPLETE` per org via `asyncio.create_task(create_org_notification(...))`
- Message includes correct count: "N creatives scored in this batch." (singular handled)

## Test Coverage

10 tests, all passing:
- `test_create_org_notification_fan_out` — 3 active users → 3 rows inserted
- `test_create_org_notification_empty_org` — 0 users → 0 rows, no commit
- `test_create_org_notification_inactive_users_excluded` — filter at DB query level
- `test_create_org_notification_session_isolation` — no `db` param in signature
- `test_sync_failed_guard_prevents_duplicate` — ERROR→ERROR: no create_task call
- `test_sync_failed_guard_fires_on_transition` — ACTIVE→ERROR: create_task called once
- `test_token_expired_guard_fires_on_transition` — ACTIVE→EXPIRED: create_task called once
- `test_token_expired_guard_prevents_duplicate` — EXPIRED→EXPIRED: no create_task call
- `test_sync_complete_initial_only` — verifies helper accepts `type` param
- `test_scoring_batch_per_org_notification` — 3 items across 2 orgs → 2 create_task calls

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Python 3.9 `dict | None` union syntax not supported**
- **Found during:** Task 1 implementation
- **Issue:** `data: dict | None = None` fails on Python 3.9 (union syntax requires 3.10+)
- **Fix:** Imported `Optional` from `typing` and used `data: Optional[dict] = None`
- **Files modified:** backend/app/services/notifications.py

**2. [Rule 3 - Blocking] apscheduler not installed in test Python environment**
- **Found during:** Task 2 test run
- **Issue:** `scheduler.py` imports `apscheduler` which was not installed in the Python 3.9 test environment
- **Fix:** Installed `apscheduler==3.10.4` into the Python 3.9 site-packages via `python3 -m pip install apscheduler`
- **Files modified:** None (environment fix only)

## Deferred Issues

**Pre-existing test failure: test_exception_audit.py::test_no_broad_except_exception**
- `run_backfill_task` in `scoring_job.py` has an allowed-but-unlisted `except Exception` that was present before Phase 10
- `dv360_sync.py:1177`, `dv360_sync.py:1695`, `google_ads_sync.py:349` also have pre-existing violations
- These were present in commit 2a1b420 (Phase 10 base) — not introduced by this plan
- Action needed: Add `run_backfill_task` to `ALLOWED_FUNCTIONS` in `test_exception_audit.py` and resolve the dv360/google_ads violations in a future plan

## Known Stubs

None. All notification emission points are fully wired to real DB inserts.

## Self-Check: PASSED

- backend/app/services/notifications.py: FOUND
- backend/tests/test_notifications.py: FOUND
- Commit e5197dc: FOUND
- Commit cf459a4: FOUND
- All 10 tests passing: CONFIRMED (117 passed, 0 failed excluding pre-existing exception audit)
