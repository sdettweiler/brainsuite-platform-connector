# Phase 10: In-App Notifications - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 10-in-app-notifications
**Areas discussed:** Notification scoping, Toast trigger mechanism, Event granularity

---

## Notification Scoping

| Option | Description | Selected |
|--------|-------------|----------|
| Fan-out per user | One Notification row per org member; keeps user_id model intact; no migration needed; read status is per-user | ✓ |
| Add org_id, single row | One row per event with org_id; all users share the same row; requires Alembic migration | |
| Admin-only delivery | Notify only org admin users (is_admin=True); simpler fan-out | |

**User's choice:** Fan-out per user

---

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone util function | `create_org_notification(db, org_id, type, title, message, data)` in `backend/app/services/notifications.py` | ✓ |
| Inline in scheduler/scoring_job | Duplicate fan-out logic at each emission point | |

**User's choice:** Standalone util function

---

## Toast Trigger Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Track last-check timestamp | `lastToastCheckAt` in component state; filter notifications by `created_at > lastToastCheckAt` AND high-priority type on each poll | ✓ |
| Dedicated high-priority endpoint | New backend endpoint `GET /notifications/unread?priority=high&since=...` | |
| Compare previous notification list | Diff full notification list on count increase | |

**User's choice:** Track last-check timestamp

---

| Option | Description | Selected |
|--------|-------------|----------|
| Title + action button | Shows title with 'View' action, opens bell menu; 8-second duration | ✓ |
| Message only, auto-dismiss | No action button, 5-second auto-dismiss | |
| One toast per batch | Summary toast for multiple simultaneous alerts | |

**User's choice:** Title + action button (8s, 'View' opens bell menu)

---

## Event Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Initial sync only | SYNC_COMPLETE only when `initial_sync_completed` transitions False → True | ✓ |
| Every sync completion | Every daily/initial/full resync; high noise | |
| Full resync only | Only admin-triggered full resync | |

**User's choice:** Initial sync only

---

| Option | Description | Selected |
|--------|-------------|----------|
| Once per connection per status change | SYNC_FAILED once per ERROR transition; TOKEN_EXPIRED once per EXPIRED transition | ✓ |
| Every failure occurrence | New notification every failed sync attempt | |
| Once per 24h per connection | Deduplicate within 24h window | |

**User's choice:** Once per connection per status change

---

| Option | Description | Selected |
|--------|-------------|----------|
| Only when assets were scored | SCORING_BATCH_COMPLETE fires if `scored_count >= 1` | ✓ |
| Every batch run | Every 15-min execution regardless of results; 96/day | |
| Only on backfill completion | Only admin backfill job | |

**User's choice:** Only when assets were scored (`scored_count >= 1`)

---

## Claude's Discretion

- Notification message copy for each event type
- Bootstrap Icons for new notification types
- Bulk insert vs per-user `db.add()` in helper
- MatMenu programmatic open API for 'View' toast action

## Deferred Ideas

- Email/Slack delivery (NOTIF-v2-01)
- SSE/WebSocket real-time delivery (NOTIF-v2-02)
- Per-tenant notification preferences
- Notification auto-pruning job
