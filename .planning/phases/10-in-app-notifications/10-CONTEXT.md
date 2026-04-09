# Phase 10: In-App Notifications - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire notification emission from sync/scoring events into the existing bell icon infrastructure. The `Notification` model, all backend endpoints, and the full frontend bell UI are already implemented (for JOIN_APPROVED/REJECTED events). This phase adds new event types (SYNC_COMPLETE, SYNC_FAILED, SCORING_BATCH_COMPLETE, TOKEN_EXPIRED), a standalone notification helper for background services, and MatSnackBar toast behavior for high-priority events.

This phase does NOT add SSE, WebSockets, or email/Slack delivery. In-app polling only (30s interval already implemented).

</domain>

<decisions>
## Implementation Decisions

### Notification Scoping

- **D-01:** Fan-out per user — when an org-level event occurs, one `Notification` row is created per active user in the org. The existing `user_id`-scoped model is kept intact. No Alembic migration needed. Read status is per-user (each user independently marks their own copy as read). This is consistent with the existing JOIN_APPROVED/REJECTED pattern.
- **D-02:** A standalone helper function `create_org_notification(db, org_id, type, title, message, data)` is added at `backend/app/services/notifications.py`. It fetches all active users for the org and bulk-inserts one `Notification` row per user. Scheduler and scoring_job import and await it directly, using the same session-per-operation pattern established in prior phases.

### Toast Trigger

- **D-03:** The `HeaderComponent` tracks a `lastToastCheckAt: Date` in component state (set to `ngOnInit` time). On each 30s `loadUnreadCount()` poll: if `unreadCount` increased, fetch recent notifications and filter for any with `created_at > lastToastCheckAt` AND `type` in `['SYNC_FAILED', 'TOKEN_EXPIRED']`. Show a toast for each matched notification. Update `lastToastCheckAt` after each check regardless of whether the count increased (prevents timestamp drift).
- **D-04:** Toast style: `MatSnackBar` with `{ message: n.title, action: 'View', duration: 8000 }`. Clicking 'View' programmatically opens the `#notifMenu` MatMenu. One toast per matched notification — no batching.

### Event Granularity

- **D-05: SYNC_COMPLETE** — fires **only when `initial_sync_completed` transitions from `False` to `True`** for a connection. Daily background syncs and full resyncs are silent. Prevents 4+ notifications per day per platform.
- **D-06: SYNC_FAILED / TOKEN_EXPIRED** — fire **once per connection per status change**: `SYNC_FAILED` when `connection.sync_status` transitions to `"ERROR"`, `TOKEN_EXPIRED` when it transitions to `"EXPIRED"`. No notification if the connection is already in that status from a prior sync cycle. Both are high-priority types — will trigger toast per D-03.
- **D-07: SCORING_BATCH_COMPLETE** — fires **only when `scored_count >= 1`** in the batch run. Silent if the batch found nothing to score. Runs every 15 min but most runs will be silent.

### Claude's Discretion

- Notification message copy (e.g. "Meta sync complete — 142 creatives imported") — planner/researcher decides based on available data in scheduler context.
- Icons for new notification types in `getNotifIcon()` / `getNotifIconClass()` — researcher picks appropriate Bootstrap Icons (`bi-*`) consistent with existing set.
- Whether `create_org_notification` uses a single `db.execute(insert(Notification).values([...]))` bulk insert or per-user `db.add()` — planner decides based on expected org size.
- MatMenu programmatic open on 'View' toast action — researcher confirms the correct Angular Material API for opening a `MatMenuTrigger` from outside the template.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing notification infrastructure
- `backend/app/models/user.py` — `Notification` model (`id`, `user_id`, `type`, `title`, `message`, `data` JSONB, `is_read`, `created_at`); also `User.organization_id` for fan-out query
- `backend/app/api/v1/endpoints/users.py` — existing notification endpoints (`/notifications`, `/notifications/unread-count`, `/notifications/{id}/read`, `/notifications/read-all`); pattern to follow for any new endpoints
- `frontend/src/app/core/layout/header/header.component.ts` — full bell UI implementation; `loadNotifications()`, `loadUnreadCount()`, `pollInterval`, `markRead()`, `markAllRead()`, `getNotifIcon()`, `getNotifIconClass()`; toast logic (D-03, D-04) goes here

### Event emission points (scheduler)
- `backend/app/services/sync/scheduler.py` — SYNC_COMPLETE hook: `initial_sync_completed` transition (search for `initial_sync_completed = True`); SYNC_FAILED hook: `connection.sync_status = "ERROR"` transition; TOKEN_EXPIRED hook: `connection.sync_status = "EXPIRED"` transition (line ~169)
- `backend/app/services/sync/scoring_job.py` — SCORING_BATCH_COMPLETE hook: after `run_scoring_batch()` returns, if `scored_count >= 1` (see line ~238 "Scoring batch complete" log)

### Alembic migration reference (no migration needed for D-01)
- `backend/alembic/versions/b3c4d5e6f7g8_add_join_requests_notifications.py` — existing migration that created the `notifications` table; confirms current schema

### Phase requirements
- `.planning/REQUIREMENTS.md` §NOTIF-01 through §NOTIF-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Notification` model in `user.py` — already has all needed columns; no migration required
- `/users/notifications` endpoints in `users.py` — already implemented and wired to frontend; no changes needed for list/read endpoints
- `HeaderComponent` bell UI — fully implemented with polling, badge, MatMenu, mark-read; only `getNotifIcon()`, `getNotifIconClass()`, and toast logic need additions
- `ApiService.get()` / `ApiService.post()` — existing HTTP client used by header for notification calls

### Established Patterns
- `asyncio.create_task` / direct await for fire-and-forget from background services (Phase 9 pattern)
- Session-per-operation: open new `AsyncSession` per notification write, never reuse a scheduler session
- `on_conflict_do_nothing` for idempotent inserts where relevant
- UPPERCASE string values for `type` field (e.g. `SYNC_FAILED`, `TOKEN_EXPIRED`)
- `data: JSONB` column already present on `Notification` — use for event-specific context (platform, connection_id, scored_count, etc.)

### Integration Points
- `scheduler.py` sync completion/failure paths → call `create_org_notification()`
- `scoring_job.py` batch completion → call `create_org_notification()` if `scored_count >= 1`
- `header.component.ts` → add toast logic to existing `loadUnreadCount()` method
- `header.component.ts` → extend `getNotifIcon()` and `getNotifIconClass()` for new types

</code_context>

<specifics>
## Specific Ideas

- **Status-change guard for SYNC_FAILED/TOKEN_EXPIRED**: Check `connection.sync_status` BEFORE updating it. Only emit a notification if the previous status was NOT already "ERROR"/"EXPIRED". This prevents duplicate notifications on repeated daily sync failures.
- **`lastToastCheckAt` initialization**: Set to `new Date()` in `ngOnInit` so the component doesn't toast on existing unread notifications that predate the current session.
- **`data` JSONB usage**: Store useful context in each notification's `data` field — e.g. `{ platform: "meta", connection_id: "...", scored_count: 42 }`. Frontend can use this for richer display if needed later.

</specifics>

<deferred>
## Deferred Ideas

- Email/Slack notification delivery — listed as future requirement NOTIF-v2-01 in REQUIREMENTS.md; not in scope
- SSE/WebSocket real-time delivery (NOTIF-v2-02) — polling is sufficient for v1.1 event frequency
- Per-tenant notification preferences (opt-in/out per event type) — v1.2+
- Notification auto-pruning (delete rows older than 30 days) — could be a background job; deferred

</deferred>

---

*Phase: 10-in-app-notifications*
*Context gathered: 2026-04-09*
