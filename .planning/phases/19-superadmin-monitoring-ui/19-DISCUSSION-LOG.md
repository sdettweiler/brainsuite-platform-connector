# Phase 19: SuperAdmin Monitoring UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 19-superadmin-monitoring-ui
**Areas discussed:** Monitor placement, Job grouping layout, Drill-in panel, SSE status indicator

---

## Monitor Placement

| Option | Description | Selected |
|--------|-------------|----------|
| 5th section on existing admin page | Adds a Job Monitor section at top of admin.component.ts; single nav item, scroll-based | |
| New sub-route 'Job Monitor' | New sidebar entry at /configuration/jobs; own full-height canvas | ✓ |

**User's choice:** New sub-route 'Job Monitor'

| Option | Description | Selected |
|--------|-------------|----------|
| Job Monitor / bi-activity | Label: 'Job Monitor', icon: Bootstrap Icons bi-activity | ✓ |
| Jobs / bi-list-task | Shorter label, list-task icon | |
| You decide | Claude picks | |

**User's choice:** Job Monitor / bi-activity

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — SuperAdmin only | canActivate: IsSuperAdminGuard on /jobs route | ✓ |
| No — any authenticated user | Any logged-in user can view | |

**User's choice:** Yes — SuperAdmin only
**Notes:** Consistent with existing /admin route guard.

---

## Job Grouping Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Tabs with live count badges | 4 tabs (Sync/Download/Autofill/Scoring) with active job count badges | ✓ |
| Flat list with type filter chips | All jobs in one chronological list | |
| Accordion sections | 4 collapsible sections per type | |

**User's choice:** Tabs with live count badges

| Option | Description | Selected |
|--------|-------------|----------|
| All 24h jobs, newest first | No pagination, full 24h window | |
| Most recent 50, newest first | Cap at 50 per tab | |
| Active jobs first, then completed | Float RUNNING/PENDING to top | |

**User's choice (modified):** 50 jobs per page with pagination; status filter (completed/running/failed); "Clear completed" and "Clear failed" buttons that permanently delete from DB.
**Notes:** User selected option 1 but added pagination (50/page), status filter, and destructive clear buttons.

| Option | Description | Selected |
|--------|-------------|----------|
| Delete from database permanently | Backend DELETE endpoint removes records | ✓ |
| Hide from UI only (client-side) | Records stay in DB, just hidden | |
| You decide | Claude picks | |

**User's choice:** Delete from database permanently

---

## Drill-In Panel

| Option | Description | Selected |
|--------|-------------|----------|
| Side panel (slide from right) | field-mappings-panel.component.ts pattern; job list stays visible | ✓ |
| MatDialog overlay | Full-screen modal; disconnect-dialog.component.ts pattern | |
| Inline row expand | Expands row in-place; no separate component | |

**User's choice:** Side panel (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Job ID + type + status badge + timestamps | job_id (monospace, copyable) + type + status + timestamps; satisfies MON-07 | ✓ |
| Type + status + progress only | Minimal header; job ID below | |
| You decide | Claude picks | |

**User's choice:** Job ID + type + status badge + timestamps (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Monospace block + Copy traceback button | Scrollable pre, truncated at 10KB, Clipboard API copy | ✓ |
| Collapsed by default, expand to read | Exception type visible; expand for full | |
| You decide | Claude picks | |

**User's choice:** Monospace block, truncated with 'Copy traceback' button (Recommended)

---

## SSE Status Indicator

| Option | Description | Selected |
|--------|-------------|----------|
| Live badge in page header | Green dot/Live, spinner/Reconnecting..., red dot/Disconnected after 3 failures | ✓ |
| Subtle, in page footer only | Less prominent | |
| No — handle silently | Browser auto-reconnects quietly; no indicator | |

**User's choice:** Yes — live badge in page header (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Browser EventSource auto-reconnect | Built-in behavior; badge reflects readyState | ✓ |
| Manual reconnect after 3 failures | User clicks to re-establish | |
| You decide | Claude picks | |

**User's choice:** Browser EventSource auto-reconnect (Recommended)

---

## Claude's Discretion

- Angular service name and location: `JobMonitorService` at `frontend/src/app/core/services/job-monitor.service.ts`
- SSE token passing: `?token=<access_token>` from localStorage (per Phase 18 D-04)
- Progress bar: Angular Material `MatProgressBar` — determinate when `progress_total > 0`, indeterminate otherwise
- REST endpoint design: `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `DELETE /api/v1/jobs`
- New Pydantic schemas: `JobListItem` (no output/error) and `JobDetail` (full JSONB)

## Deferred Ideas

- SSE-03 scaling (already deferred from Phase 18)
- Deep-link from sync drill-in to SyncJob detail view
- CSV/JSON export of job history
