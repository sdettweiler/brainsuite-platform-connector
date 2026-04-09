# Phase 10: In-App Notifications - Research

**Researched:** 2026-04-09
**Domain:** Angular 17 / FastAPI / PostgreSQL notification plumbing
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Fan-out per user — one `Notification` row per active user in the org when an org-level event occurs. `user_id`-scoped model intact. No Alembic migration needed. Read status is per-user.
- **D-02:** Standalone helper `create_org_notification(db, org_id, type, title, message, data)` at `backend/app/services/notifications.py`. Fetches active users for the org and bulk-inserts one row per user. Scheduler and scoring_job import and await it directly, using session-per-operation pattern.
- **D-03:** `HeaderComponent` tracks `lastToastCheckAt: Date` set at `ngOnInit`. On each 30s `loadUnreadCount()` poll: if `unreadCount` increased, fetch recent notifications, filter for `created_at > lastToastCheckAt` AND `type` in `['SYNC_FAILED', 'TOKEN_EXPIRED']`. Show a toast for each matched notification. Update `lastToastCheckAt` after each check regardless.
- **D-04:** Toast: `MatSnackBar.open(n.title, 'View', { duration: 8000 })`. Clicking 'View' programmatically opens the `#notifMenu` MatMenu via `MatMenuTrigger`. One toast per matched notification.
- **D-05:** `SYNC_COMPLETE` fires only when `initial_sync_completed` transitions from `False` to `True` for a connection. Daily syncs and full resyncs are silent.
- **D-06:** `SYNC_FAILED` / `TOKEN_EXPIRED` fire once per connection per status change: only if the connection was NOT already in `"ERROR"` / `"EXPIRED"` status from a prior cycle.
- **D-07:** `SCORING_BATCH_COMPLETE` fires only when `scored_count >= 1` in the batch run. Silent if batch found nothing to score.

### Claude's Discretion

- Notification message copy (planner/researcher decides based on available data in scheduler context)
- Icons for new notification types in `getNotifIcon()` / `getNotifIconClass()`
- Whether `create_org_notification` uses single bulk `db.execute(insert(Notification).values([...]))` or per-user `db.add()` calls
- MatMenu programmatic open on 'View' toast action — researcher confirms correct Angular Material API

### Deferred Ideas (OUT OF SCOPE)

- Email/Slack notification delivery
- SSE/WebSocket real-time delivery
- Per-tenant notification preferences
- Notification auto-pruning (30-day retention job)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NOTIF-01 | `notifications` table with `(id, org_id, type, payload JSONB, read, created_at)` indexed for efficient polling | Table already exists as `(id, user_id, type, title, message, data JSONB, is_read, created_at)` — D-01 confirms no migration needed; polling index analysis below |
| NOTIF-02 | Notifications created for: sync complete, sync failed, scoring batch complete, platform token expired | `create_org_notification()` helper + 4 emission points documented below |
| NOTIF-03 | Frontend polls `GET /notifications/unread` every 30 seconds — no SSE or WebSockets | Already implemented as `/users/notifications/unread-count` — see `HeaderComponent.loadUnreadCount()` |
| NOTIF-04 | Bell icon with unread badge; click opens `MatMenu`; individual and bulk mark-as-read | Fully implemented in `HeaderComponent` — only icon/class additions needed |
| NOTIF-05 | `MatSnackBar` toast for high-priority events (sync failed, token expired) when user is active | D-03/D-04 pattern — `MatMenuTrigger.openMenu()` for 'View' action |
</phase_requirements>

---

## Summary

Phase 10 is almost entirely additive wiring. The notification infrastructure (model, all API endpoints, full bell UI with polling and mark-read) was shipped as part of the JOIN_APPROVED/REJECTED flow in a prior phase. This phase adds four new event types on the backend and toast behavior on the frontend.

The critical insight is that `run_scoring_batch()` currently returns **remaining** UNSCORED asset count (not `scored_count`). D-07 says "fires only when `scored_count >= 1`" — but this data is not directly available from the current return value. The planner must either (a) change `run_scoring_batch()` to also return a `scored_count` tuple, or (b) infer it from `batch_size > 0` (if any batch was started, at least some assets were attempted). The safest approach is to make `run_scoring_batch()` return a `(scored_count, remaining)` tuple, or pass `len(batch)` into the wrapper.

The only non-trivial frontend piece is opening the `#notifMenu` MatMenu programmatically when the user clicks 'View' on a toast. Angular Material 17 exposes this via `MatMenuTrigger.openMenu()` after getting a `@ViewChild(MatMenuTrigger)` reference.

**Primary recommendation:** Backend: add `notifications.py` service + 4 emission points in scheduler/scoring_job. Frontend: add `MatSnackBarModule` + `MatMenuTrigger` ViewChild to `HeaderComponent`; extend `getNotifIcon()`/`getNotifIconClass()`.

---

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| `@angular/material` | 17.3.x | MatSnackBar toast + MatMenu + MatMenuTrigger | Already imported in project [VERIFIED: frontend/package.json] |
| `sqlalchemy` (asyncio) | — | Bulk insert via `insert(Notification).values([...])` | Already in use throughout project [VERIFIED: codebase] |
| `apscheduler` | — | Scoring batch job and sync scheduler | Already used [VERIFIED: codebase] |

### No new dependencies required

All libraries needed are already installed. [VERIFIED: frontend/package.json, backend/requirements.txt patterns]

---

## Architecture Patterns

### Recommended Project Structure (additions only)

```
backend/app/services/
└── notifications.py          # NEW — create_org_notification() helper

backend/app/services/sync/
├── scheduler.py              # MODIFY — add 4 emission call sites
└── scoring_job.py            # MODIFY — change return type + add emission

frontend/src/app/core/layout/header/
└── header.component.ts       # MODIFY — toast logic + MatMenuTrigger
```

### Pattern 1: `create_org_notification()` helper

**What:** Standalone async function that opens its own DB session, queries active users for the org, and bulk-inserts one `Notification` row per user. Never reuses a caller's session.

**When to use:** Called from `scheduler.py` and `scoring_job.py` at event emission points.

```python
# backend/app/services/notifications.py
# Source: D-02 + session-per-operation pattern established in ai_autofill.py

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.db.base import get_session_factory
from app.models.user import User, Notification

async def create_org_notification(
    org_id: str,
    type: str,
    title: str,
    message: str,
    data: dict | None = None,
) -> int:
    """Create one Notification row per active user in the org.

    Returns the number of rows inserted.
    Session-per-operation — never call with a caller's session.
    """
    async with get_session_factory()() as db:
        result = await db.execute(
            select(User).where(
                User.organization_id == org_id,
                User.is_active == True,
            )
        )
        users = result.scalars().all()
        if not users:
            return 0

        rows = [
            {
                "user_id": user.id,
                "type": type,
                "title": title,
                "message": message,
                "data": data or {},
            }
            for user in users
        ]
        await db.execute(
            pg_insert(Notification).values(rows).on_conflict_do_nothing()
        )
        await db.commit()
        return len(rows)
```

**Implementation note on bulk vs. per-row:** For typical org sizes (< 20 users), both approaches work. Use the single `pg_insert(...).values(rows)` bulk pattern — same as AI autofill's `pg_insert` usage [VERIFIED: ai_autofill.py line 19]. The `on_conflict_do_nothing()` provides idempotency if the helper is accidentally called twice.

### Pattern 2: Event emission in `scheduler.py` — status-change guard

**What:** Check the connection's current `sync_status` BEFORE overwriting it. Only emit if transitioning INTO the error state.

```python
# backend/app/services/sync/scheduler.py
# Source: D-06 specifics + CONTEXT.md status-change guard note

from app.services.notifications import create_org_notification
import asyncio

# At SYNC_FAILED emission point — BEFORE: connection.sync_status = "ERROR"
if connection.sync_status != "ERROR":
    asyncio.create_task(create_org_notification(
        org_id=str(connection.organization_id),
        type="SYNC_FAILED",
        title="Sync Failed",
        message=f"{connection.platform.title()} sync failed. Please check your connection.",
        data={"platform": connection.platform, "connection_id": str(connection.id)},
    ))
connection.sync_status = "ERROR"

# At TOKEN_EXPIRED emission point — BEFORE: connection.sync_status = "EXPIRED"
if connection.sync_status != "EXPIRED":
    asyncio.create_task(create_org_notification(
        org_id=str(connection.organization_id),
        type="TOKEN_EXPIRED",
        title="Platform Token Expired",
        message=f"Your {connection.platform.title()} access token has expired. Reconnect to resume syncing.",
        data={"platform": connection.platform, "connection_id": str(connection.id)},
    ))
connection.sync_status = "EXPIRED"

# At SYNC_COMPLETE emission point (initial sync only)
# AFTER: connection.initial_sync_completed = True
asyncio.create_task(create_org_notification(
    org_id=str(connection.organization_id),
    type="SYNC_COMPLETE",
    title="Sync Complete",
    message=f"{connection.platform.title()} initial sync complete.",
    data={"platform": connection.platform, "connection_id": str(connection.id)},
))
```

### Pattern 3: Scoring batch emission — scored_count derivation

**What:** `run_scoring_batch()` currently returns `remaining` (UNSCORED count after batch). For D-07 we need to know how many assets were actually scored. The `len(batch)` variable inside the function captures how many assets were submitted.

**Recommendation:** Change `run_scoring_batch()` to return a tuple `(scored_count, remaining)` where `scored_count = len(batch)`. Update `run_scoring_batch_adaptive()` to unpack the tuple.

```python
# backend/app/services/sync/scoring_job.py — modified signature
async def run_scoring_batch() -> tuple[int, int]:
    """Returns (scored_count, remaining_unscored)."""
    ...
    scored_count = len(batch)  # batch was populated in Phase 1
    ...
    return scored_count, remaining

# In scheduler.py run_scoring_batch_adaptive():
from app.services.notifications import create_org_notification

async def run_scoring_batch_adaptive() -> None:
    scored_count, remaining = await run_scoring_batch()

    if scored_count >= 1:
        # Emit per org — need to gather distinct org_ids from the batch
        # Simplest approach: fire a generic platform-wide notification
        # (no org_id available here — see Open Question OQ-01)
        ...
```

**Critical gap:** `run_scoring_batch_adaptive()` in `scheduler.py` does not have access to org-specific context. The scoring batch is global (scores all orgs' assets). See Open Question OQ-01 below.

### Pattern 4: MatMenuTrigger programmatic open (Angular 17)

**What:** Get a `@ViewChild(MatMenuTrigger)` reference to the bell button's menu trigger, then call `.openMenu()` in the snackBar action callback.

```typescript
// frontend/src/app/core/layout/header/header.component.ts
// Source: Angular Material 17 docs — MatMenuTrigger.openMenu() [ASSUMED — see Assumptions Log]

import { ViewChild } from '@angular/core';
import { MatMenuTrigger } from '@angular/material/menu';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';

// In @Component imports array:
// MatSnackBarModule (add alongside MatMenuModule)

// In class:
@ViewChild(MatMenuTrigger) notifMenuTrigger!: MatMenuTrigger;

// Constructor:
constructor(
  private auth: AuthService,
  private theme: ThemeService,
  private dialog: MatDialog,
  private api: ApiService,
  private snackBar: MatSnackBar,
) {}

// Toast emission (called from loadUnreadCount):
private showToastForNotification(n: NotificationItem): void {
  const ref = this.snackBar.open(n.title, 'View', { duration: 8000 });
  ref.onAction().subscribe(() => {
    this.notifMenuTrigger?.openMenu();
    // Also reload so the list is fresh
    this.loadNotifications();
  });
}
```

**Caution on multiple MatMenuTrigger:** The template has two `[matMenuTriggerFor]` bindings (bell button + avatar button). `@ViewChild(MatMenuTrigger)` returns the first one in DOM order. Since the bell button appears first in the template, this will correctly resolve to the notif menu trigger. [VERIFIED: header.component.ts template order — bell button is first at line 34]

**Alternative if ViewChild resolves wrong trigger:** Use `@ViewChild('notifTrigger') notifMenuTrigger!: MatMenuTrigger` and add `#notifTrigger` template variable to the bell button alongside the existing `[matMenuTriggerFor]="notifMenu"`.

### Pattern 5: Toast firing logic in `loadUnreadCount()`

```typescript
// In HeaderComponent:
private lastToastCheckAt: Date = new Date(); // set in ngOnInit
private previousUnreadCount = 0;

ngOnInit(): void {
  this.auth.currentUser$.subscribe(u => {
    this.user = u;
    if (u) {
      this.loadNotifications();
      this.lastToastCheckAt = new Date();
      this.pollInterval = setInterval(() => this.loadUnreadCount(), 30000);
    }
  });
  this.theme.currentTheme$.subscribe(t => this.isDark = t === 'dark-theme');
}

loadUnreadCount(): void {
  const checkTime = new Date(); // capture before API call
  this.api.get<{count: number}>('/users/notifications/unread-count').subscribe({
    next: (res) => {
      const newCount = res.count;
      if (newCount > this.unreadCount) {
        // Count increased — fetch recent and check for high-priority
        this.api.get<NotificationItem[]>('/users/notifications').subscribe({
          next: (notifs) => {
            const threshold = this.lastToastCheckAt;
            const highPriority = notifs.filter(n =>
              !n.is_read &&
              ['SYNC_FAILED', 'TOKEN_EXPIRED'].includes(n.type) &&
              new Date(n.created_at) > threshold
            );
            highPriority.forEach(n => this.showToastForNotification(n));
            this.notifications = notifs;
          },
        });
      }
      this.unreadCount = newCount;
      this.lastToastCheckAt = checkTime; // update regardless
    },
  });
}
```

### Pattern 6: Icon/class additions for new notification types

```typescript
getNotifIcon(n: NotificationItem): string {
  switch (n.type) {
    case 'JOIN_REQUEST':   return 'bi-person-plus';
    case 'JOIN_APPROVED':  return 'bi-check-circle-fill';
    case 'JOIN_REJECTED':  return 'bi-slash-circle';
    case 'SYNC_COMPLETE':  return 'bi-check2-circle';
    case 'SYNC_FAILED':    return 'bi-exclamation-triangle-fill';
    case 'TOKEN_EXPIRED':  return 'bi-shield-exclamation';
    case 'SCORING_BATCH_COMPLETE': return 'bi-bar-chart-fill';
    default: return 'bi-bell';
  }
}

getNotifIconClass(n: NotificationItem): string {
  switch (n.type) {
    case 'JOIN_REQUEST':   return 'icon-join';
    case 'JOIN_APPROVED':  return 'icon-approved';
    case 'JOIN_REJECTED':  return 'icon-rejected';
    case 'SYNC_COMPLETE':  return 'icon-approved';     // reuse green
    case 'SYNC_FAILED':    return 'icon-rejected';     // reuse red
    case 'TOKEN_EXPIRED':  return 'icon-rejected';     // reuse red
    case 'SCORING_BATCH_COMPLETE': return 'icon-join'; // reuse accent
    default: return '';
  }
}
```

**Icon rationale (Claude's Discretion):** `bi-check2-circle` for sync complete (success, distinct from join approved), `bi-exclamation-triangle-fill` for sync failed (warning/error), `bi-shield-exclamation` for token expired (auth/security), `bi-bar-chart-fill` for scoring batch (data/analytics). All consistent with Bootstrap Icons used elsewhere. [ASSUMED — verify against Bootstrap Icons CDN version in use]

### Anti-Patterns to Avoid

- **Holding the scheduler DB session during notification write:** Never pass `db` from `run_daily_sync()` into `create_org_notification()`. Always open a new session. [VERIFIED: established pattern in ai_autofill.py and scoring_job.py]
- **Emitting `SYNC_FAILED`/`TOKEN_EXPIRED` without status-change guard:** Will produce one notification per daily sync cycle when the connection stays broken. Guard is mandatory (CONTEXT.md specifics section).
- **Setting `lastToastCheckAt` only when a toast fires:** Must update on every poll tick regardless, otherwise timestamp drifts and old notifications get re-toasted after a silent period.
- **Using `@ViewChild(MatMenuTrigger)` without `static: false`:** Default is `static: false` in Angular 14+ which is correct here (menu is in `*ngIf`-free template). No flag needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bulk insert with idempotency | Manual loop + exists check | `pg_insert(...).values([...]).on_conflict_do_nothing()` | Single round-trip, atomic, already used in codebase |
| Toast with action callback | Custom overlay component | `MatSnackBar.open().onAction().subscribe()` | Built into Angular Material, already imported in 5 other components |
| Programmatic menu open | DOM manipulation / custom event | `MatMenuTrigger.openMenu()` | Official Angular Material API |

---

## Critical Finding: `scored_count` vs. `run_scoring_batch()` return value

**This is the most important implementation detail for the planner.**

CONTEXT.md D-07 says "fires only when `scored_count >= 1`". However, `run_scoring_batch()` currently returns `remaining` (remaining UNSCORED count), not `scored_count`. [VERIFIED: scoring_job.py lines 137-238]

The `len(batch)` local variable in `run_scoring_batch()` captures exactly the number of assets that entered Phase 1 (BATCH_SIZE assets marked PENDING). This is the closest proxy for `scored_count`.

**Recommended change:** Modify `run_scoring_batch()` signature to return `tuple[int, int]` — `(scored_count, remaining)`. Update `run_scoring_batch_adaptive()` to unpack.

**Second critical finding:** `run_scoring_batch_adaptive()` runs across all orgs' assets. There is no per-org context available. See Open Question OQ-01.

---

## Critical Finding: Multiple `sync_status = "ERROR"` assignment sites

The status-change guard must be added at EVERY site that assigns `"ERROR"` or `"EXPIRED"`. Looking at the scheduler, there are at least **8 separate `connection.sync_status = "ERROR"` lines** across `run_daily_sync()` (for both non-DV360 and DV360 paths) and similar for `run_initial_sync()`. [VERIFIED: scheduler.py grep output]

The planner must enumerate all these sites. Approach options:

1. **Guard at each site individually** — verbose but explicit. Requires reading the current status from the DB before each assignment (connection object is already loaded, so `connection.sync_status` reflects current DB state if not yet modified).
2. **Centralise into a helper** `_set_connection_error_status(connection, status)` that checks and emits before assigning.

Approach 2 is cleaner. The planner should decide; both are valid.

---

## Common Pitfalls

### Pitfall 1: Duplicate `SYNC_FAILED` notifications on persistent errors

**What goes wrong:** Without the status-change guard, every daily sync attempt on a broken connection creates N new notifications (one per org user per run).
**Why it happens:** The scheduler runs daily for all connections regardless of current status.
**How to avoid:** Check `connection.sync_status != "ERROR"` BEFORE assigning. The `connection` object is freshly loaded from DB at the start of each `run_daily_sync()` call, so its `sync_status` reflects current state. [VERIFIED: scheduler.py line 88-99]
**Warning signs:** Notifications table growing rapidly with repeated `SYNC_FAILED` rows for the same connection.

### Pitfall 2: Scoring batch notification without per-org context

**What goes wrong:** `run_scoring_batch_adaptive()` has no org_id — it scores assets from all orgs in the queue.
**Why it happens:** The batch is a platform-wide job, not per-connection.
**How to avoid:** See Open Question OQ-01 for resolution strategies.
**Warning signs:** Trying to call `create_org_notification()` from `run_scoring_batch_adaptive()` without a valid org_id.

### Pitfall 3: Toast firing for pre-session notifications

**What goes wrong:** If `lastToastCheckAt` is not set before the first poll, toasts fire for all existing unread `SYNC_FAILED`/`TOKEN_EXPIRED` notifications from previous sessions.
**How to avoid:** Set `lastToastCheckAt = new Date()` in `ngOnInit` (D-03). The comparison `new Date(n.created_at) > lastToastCheckAt` will be false for all pre-existing notifications.

### Pitfall 4: Toast fires multiple times per notification

**What goes wrong:** Each 30s poll that still shows the count as elevated re-fetches notifications and may re-toast the same high-priority item.
**Why it happens:** Count stays high until user opens and reads the notification.
**How to avoid:** The `created_at > lastToastCheckAt` filter handles this correctly — update `lastToastCheckAt` on every poll tick, not just when a toast fires. After the first poll that toasts, `lastToastCheckAt` advances past the notification's timestamp, so subsequent polls won't re-match it.

### Pitfall 5: `MatMenuTrigger.openMenu()` called before view is initialized

**What goes wrong:** Calling `notifMenuTrigger.openMenu()` before `ngOnInit` completes or while user is null results in a null-reference error.
**How to avoid:** The toast action callback only fires on user interaction, by which point `ngOnInit` has run. Use optional chaining `notifMenuTrigger?.openMenu()` as a safety net.

---

## Notification Message Copy (Claude's Discretion)

Recommended message strings based on available data in scheduler context:

| Type | Title | Message template |
|------|-------|-----------------|
| `SYNC_COMPLETE` | `{PLATFORM} Sync Complete` | `Initial sync complete. Your {platform} creatives are now available.` |
| `SYNC_FAILED` | `{PLATFORM} Sync Failed` | `Sync failed for your {platform} account. Check your connection settings.` |
| `TOKEN_EXPIRED` | `{PLATFORM} Token Expired` | `Your {platform} access token has expired. Reconnect to resume syncing.` |
| `SCORING_BATCH_COMPLETE` | `Scoring Complete` | `{N} creative{s} scored in this batch.` |

The `data` JSONB field stores `{ platform, connection_id }` for sync events and `{ scored_count }` for scoring events. [VERIFIED: CONTEXT.md specifics section]

---

## Runtime State Inventory

Step 2.5: SKIPPED — this is a greenfield additive phase, not a rename/refactor/migration.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | notifications table | Yes | 16 (alpine) | — |
| FastAPI backend | notification endpoints | Yes | running (port 8000) | — |
| Angular frontend | MatSnackBar + MatMenuTrigger | Yes | 17.3.x | — |
| Redis | (not needed by this phase) | Yes | 7 (alpine) | — |

[VERIFIED: docker-compose ps output — all services healthy]

No missing dependencies. No environment blockers.

---

## Validation Architecture

nyquist_validation is enabled (config.json).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (async, unittest.mock pattern) |
| Config file | none — run from backend container |
| Quick run command | `docker-compose exec backend python -m pytest tests/test_notifications.py -x -q` |
| Full suite command | `docker-compose exec backend python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NOTIF-01 | notifications table schema correct (user_id, type, title, message, data, is_read, created_at) | unit (model inspection) | `pytest tests/test_notifications.py::test_notification_model -x` | Wave 0 |
| NOTIF-02a | `create_org_notification()` inserts one row per active user | unit | `pytest tests/test_notifications.py::test_create_org_notification_fan_out -x` | Wave 0 |
| NOTIF-02b | SYNC_FAILED guard prevents duplicate on repeated failure | unit | `pytest tests/test_notifications.py::test_sync_failed_no_duplicate -x` | Wave 0 |
| NOTIF-02c | TOKEN_EXPIRED guard prevents duplicate | unit | `pytest tests/test_notifications.py::test_token_expired_no_duplicate -x` | Wave 0 |
| NOTIF-02d | SYNC_COMPLETE fires only on initial_sync_completed transition | unit | `pytest tests/test_notifications.py::test_sync_complete_initial_only -x` | Wave 0 |
| NOTIF-02e | SCORING_BATCH_COMPLETE fires when scored_count >= 1, silent when 0 | unit | `pytest tests/test_notifications.py::test_scoring_batch_notification -x` | Wave 0 |
| NOTIF-03 | GET /users/notifications/unread-count endpoint returns correct count | unit | `pytest tests/test_notifications.py::test_unread_count_endpoint -x` | Wave 0 |
| NOTIF-04 | Mark individual notification as read | unit | `pytest tests/test_notifications.py::test_mark_read -x` | Wave 0 |
| NOTIF-04 | Mark all notifications as read | unit | `pytest tests/test_notifications.py::test_mark_all_read -x` | Wave 0 |
| NOTIF-05 | Frontend toast logic: filter by type and created_at — manual only (no Angular test harness in CI) | manual | open app, trigger SYNC_FAILED | N/A |

### Wave 0 Gaps

- [ ] `tests/test_notifications.py` — covers NOTIF-01 through NOTIF-04 (backend unit tests)
- [ ] Uses existing `conftest.py` fixtures (mock_settings, AsyncMock pattern established in test_ai_autofill.py)

---

## Open Questions

### OQ-01: Scoring batch notification — per-org or platform-wide?

**What we know:** `run_scoring_batch_adaptive()` processes assets from all orgs. There is no single `org_id` in scope. The batch scores up to 20 assets from the global UNSCORED queue.

**What's unclear:** Should SCORING_BATCH_COMPLETE be per-org (notifying each org whose assets were scored in this batch) or omitted from the scoring_job level entirely?

**Options:**
1. **Per-org approach:** In `run_scoring_batch()` (Phase 1 or Phase 2/3), collect `(org_id, count)` pairs from the batch. Pass them back via the return tuple. Emit per-org notifications in `run_scoring_batch_adaptive()`.
2. **Simplified approach:** Change `run_scoring_batch()` to return `(scored_count, remaining)` as one number, and emit a single global notification to... nobody (no single org). This doesn't work with the per-user model.
3. **Approach from scoring_job directly:** After Phase 2/3, derive per-org counts from the batch items (each `CreativeAsset` has `organization_id`). Emit per-org inside `run_scoring_batch()` itself.

**Recommendation:** Approach 3 — collect `(org_id → count)` dict from `batch` items after Phase 1 (each asset has `organization_id` via the JOIN). Emit per-org notifications inside `run_scoring_batch()` itself before returning. This keeps emission co-located with the data.

**Implication for codebase:** Requires joining `CreativeAsset.organization_id` in the Phase 1 query (or using the already-loaded `asset_row` from `(score_row, asset_row)` in the batch). The `asset_row` is already a `CreativeAsset` — confirm it has `organization_id`. [ASSUMED — need to verify CreativeAsset.organization_id field exists]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `MatMenuTrigger.openMenu()` is the correct Angular Material 17 API for programmatically opening a MatMenu | Pattern 4: MatMenuTrigger | Would need alternative approach (e.g. trigger click event on button) — LOW risk, this is a stable Material API |
| A2 | `@ViewChild(MatMenuTrigger)` without `static` resolves to the first trigger in DOM order (bell button) | Pattern 4 | If resolves to avatar menu trigger, use `@ViewChild('notifTrigger')` with explicit template variable instead |
| A3 | Bootstrap Icons used in `bi-check2-circle`, `bi-exclamation-triangle-fill`, `bi-shield-exclamation`, `bi-bar-chart-fill` are available in the Bootstrap Icons version loaded by this project | Pattern 6: icon names | Use `bi-check-circle`, `bi-exclamation-circle`, `bi-lock`, `bi-star` as fallbacks — same visual intent |
| A4 | `CreativeAsset` model has `organization_id` field — needed for per-org scoring batch notification (OQ-01 approach 3) | OQ-01 | If missing, requires join through `PlatformConnection` to reach org_id |

---

## Sources

### Primary (HIGH confidence)

- [VERIFIED: codebase] `backend/app/models/user.py` — `Notification` model confirmed schema
- [VERIFIED: codebase] `backend/app/api/v1/endpoints/users.py` — all 4 notification endpoints confirmed
- [VERIFIED: codebase] `frontend/src/app/core/layout/header/header.component.ts` — full bell UI with `loadUnreadCount()`, `loadNotifications()`, `getNotifIcon()`, `getNotifIconClass()`, polling at 30s
- [VERIFIED: codebase] `backend/app/services/sync/scheduler.py` — all `sync_status = "ERROR"/"EXPIRED"` and `initial_sync_completed = True` transition sites
- [VERIFIED: codebase] `backend/app/services/sync/scoring_job.py` — `run_scoring_batch()` return type confirmed as `int` (remaining count, not scored count)
- [VERIFIED: codebase] `backend/alembic/versions/b3c4d5e6f7g8` — `notifications` table schema, no migration needed
- [VERIFIED: frontend/package.json] `@angular/material ^17.3.0` — MatSnackBar, MatMenuTrigger available
- [VERIFIED: docker-compose ps] All runtime dependencies healthy

### Secondary (ASSUMED)

- Angular Material 17 `MatMenuTrigger.openMenu()` API — consistent with Angular Material docs pattern (A1)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all infrastructure verified in codebase, no new dependencies
- Architecture: HIGH — event emission points found and verified; helper pattern established from ai_autofill.py precedent
- Pitfalls: HIGH — derived from direct code inspection, not inference
- Scored_count derivation: HIGH — `run_scoring_batch()` return value confirmed by reading source
- MatMenuTrigger API: MEDIUM — assumed from Angular Material docs pattern (stable API, LOW risk if wrong)

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable codebase, no external API changes)
