---
phase: 04-dashboard-polish-reliability
plan: 03
subsystem: frontend/configuration
tags: [health-badges, reconnect, relative-time, reliability]
dependency_graph:
  requires: [04-01]
  provides: [platform-health-ui, reconnect-flow]
  affects: [frontend/src/app/features/configuration/pages/platforms.component.ts]
tech_stack:
  added: [date-fns/formatDistanceToNow]
  patterns: [health-state-derivation, badge-display, oauth-reuse]
key_files:
  created: []
  modified:
    - frontend/src/app/features/configuration/pages/platforms.component.ts
    - frontend/src/app/features/configuration/pages/platforms.component.scss
decisions:
  - HealthState derived from token_expiry and last_synced_at (48h threshold) — not from sync_status enum, which is a backend state that may lag behind real expiry
  - reconnect() reuses startOAuth(conn.platform) — no new OAuth flow needed
  - Reconnect button added inline in col-actions — avoids adding a new table column
metrics:
  duration: 10min
  completed_date: "2026-03-25"
  tasks_completed: 2
  files_changed: 2
---

# Phase 4 Plan 03: Platform Health Badges and Reconnect Prompts Summary

Platform connections table now surfaces sync health per row: green Connected badge, amber Token expired badge, red Sync failed badge. Unhealthy rows show a Reconnect Account button that triggers the existing OAuth re-auth flow. Last sync time is displayed as relative text ("2 hours ago") with absolute datetime tooltip.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | Health badge, relative time, reconnect button | cba7359 | Done |
| 2 | Verify DASH-03 (CE tab) and REL-03 (scheduler guard) | — | Verified (no code change) |

## What Was Built

**Task 1 — Health badges, relative time, and reconnect button:**

- Added `HealthState` type alias: `'connected' | 'token_expired' | 'sync_failed'`
- Added `token_expiry?: string` to `PlatformConnection` interface
- Added `import { formatDistanceToNow } from 'date-fns'`
- Added methods: `getHealthState()`, `getHealthLabel()`, `getHealthBadgeClass()`, `getRelativeTime()`, `needsReconnect()`, `reconnect()`
- Replaced Status column header with Health column in table `<thead>`
- Replaced `<td class="col-status">` with `<td class="col-health">` using badge display
- Replaced absolute date pipe with `getRelativeTime()` and `matTooltip` for absolute fallback
- Added Reconnect Account button in `col-actions` (guarded by `*ngIf="needsReconnect(conn)"`)
- Added CSS classes: `.badge`, `.badge-success`, `.badge-warning`, `.badge-error`, `.reconnect-btn`

**Health state logic:**
1. Token expired: `conn.token_expiry` is in the past
2. Sync failed: no `last_synced_at`, or last sync was over 48 hours ago
3. Connected: token valid and synced within 48 hours

**Task 2 — Verification:**

- DASH-03 confirmed: `asset-detail-dialog.component.ts` line 138 has `<mat-tab label="Creative Effectiveness">` — CE tab with dimension breakdown is present and accessible per creative
- REL-03 confirmed: `backend/app/services/sync/scheduler.py` (main branch, added in Phase 3 Plan 03 merge) contains `SCHEDULER_ENABLED` guard at line 935 preventing scoring batch job registration in multi-worker deployments. Note: this worktree was branched before Phase 3 merge; the guard exists on main and will be present in the final merge.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| 48-hour threshold for sync_failed | CONTEXT.md "Claude's Discretion" — reasonable window for background sync jobs that run every 24h |
| Reconnect button in col-actions | Avoids adding a new table column; keeps layout clean |
| HealthState derived independently of sync_status | Backend sync_status can lag; token_expiry is more precise for auth failures |

## Deviations from Plan

None - plan executed exactly as written. TypeScript auto-fix applied (Rule 1): the `date` pipe returns `string | null` in strict mode, so the matTooltip binding was updated from `(conn.last_synced_at | date:'...')` to `((conn.last_synced_at | date:'...') || '')` to satisfy the `string` type constraint.

## Known Stubs

None — all methods are fully implemented. `getHealthState()` uses real `token_expiry` and `last_synced_at` fields from the live API response.

## Self-Check: PASSED
