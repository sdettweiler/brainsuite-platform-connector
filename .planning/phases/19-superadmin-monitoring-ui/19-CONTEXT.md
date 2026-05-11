# Phase 19: SuperAdmin Monitoring UI - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a new SuperAdmin-only route `/configuration/jobs` ("Job Monitor") that displays all background jobs in real time via SSE. The page shows jobs grouped by type in 4 tabs, with per-job progress bars, status filtering, bulk-clear actions, and a drill-in side panel for full job detail (Gemini output, download manifests, error tracebacks, per-asset scores).

This phase also builds the two REST endpoints Phase 18 deferred: `GET /api/v1/jobs` (list, paginated) and `GET /api/v1/jobs/{id}` (detail with output+error JSONB), plus `DELETE /api/v1/jobs` for the clear-completed/clear-failed actions.

This phase does NOT modify the existing `/configuration/admin` page (admin.component.ts). The job monitor is a separate sub-route.

</domain>

<decisions>
## Implementation Decisions

### Monitor Placement

- **D-01:** New sub-route `/configuration/jobs` — a separate page, NOT a 5th section on the existing admin.component.ts.
- **D-02:** Sidebar entry: label "Job Monitor", icon `bi-activity`. Added to `configuration-shell.component.ts` `baseNavItems` array but conditionally shown to SuperAdmins only (same as existing "Admin" entry — check `user?.is_superuser`).
- **D-03:** Route guarded by `IsSuperAdminGuard` in `configuration.routes.ts`. Consistent with the existing `admin` route pattern.

### Job List Layout

- **D-04:** Tab-based layout: 4 tabs (Sync / Download / Autofill / Scoring). Each tab shows a live count badge reflecting active/pending jobs for that type in the current view.
- **D-05:** Within each tab: 50 jobs per page, sorted newest first (by `started_at` DESC). Pagination controls below the table.
- **D-06:** Status filter within each tab — filter chips or dropdown for: All / Running / Completed / Failed. Filters apply client-side from the in-memory SSE-maintained job map.
- **D-07:** "Clear completed" and "Clear failed" action buttons permanently DELETE matching records from the database for the active tab's job type. Requires new `DELETE /api/v1/jobs?job_type={type}&status={status}` backend endpoint.
- **D-08:** On SSE connect, the 24h bootstrap burst (Phase 18 D-07) pre-populates the job list. Subsequent SSE `job_update` events update the in-memory map and re-render affected rows without full reload.

### Drill-In Panel

- **D-09:** Side panel slides in from the right (same visual pattern as `field-mappings-panel.component.ts`). Clicking a job row opens the panel; clicking the overlay or a close button dismisses it.
- **D-10:** Panel header (all job types): `job_id` (monospace font, click-to-copy), `job_type` chip, status badge (PENDING/RUNNING/COMPLETE/FAILED), `started_at` / `ended_at` / calculated duration. Satisfies MON-07 (internal job ID always visible).
- **D-11:** External job IDs (e.g., BrainSuite `brainsuite_job_id`, `sync_job_id`) displayed in the panel header or a "References" row when present in the job's `metadata_` JSONB.
- **D-12:** Error traceback (MON-05): scrollable monospace `<pre>` block, content truncated at 10 KB for display. "Copy traceback" button copies full text via `navigator.clipboard.writeText()`.
- **D-13:** Autofill drill-in (MON-03): renders `output.fields[]` as a table (field name / value / source: gemini|whisper). Shows `whisper_transcript` and `language` below if present.
- **D-14:** Download drill-in (MON-04): renders `output.downloaded[]` as a list of asset IDs + MinIO URLs (each URL is a link). Shows `output.failed[]` as a collapsible error list.
- **D-15:** Scoring drill-in (MON-06): renders per-asset score outcome from `output` (score value, endpoint_type, brainsuite_job_id). Failures shown with error message inline.
- **D-16:** Sync drill-in: shows `output.platform`, `output.sync_job_id`, `output.records_fetched`, `output.records_processed`. `sync_job_id` is a reference to the existing `SyncJob` table (display only — no deep-link in this phase).

### SSE Connection Status

- **D-17:** Visible badge in the page header area: green dot + "Live" when `EventSource.readyState === OPEN`, spinner + "Reconnecting…" when `readyState === CONNECTING`, red dot + "Disconnected" if the `onerror` handler fires after 3 reconnect attempts.
- **D-18:** Rely on browser `EventSource` built-in auto-reconnect — no custom retry loop needed. The Angular service listens to `onerror` to track reconnect attempts and update the badge state.

### Claude's Discretion

- Angular service name: `JobMonitorService` in `frontend/src/app/core/services/job-monitor.service.ts`. Holds the in-memory job map (keyed by `job_id`), reconnect-attempt counter, and SSE connection status.
- SSE token passing: read `access_token` from `localStorage` (same approach used by other ApiService calls), append as `?token=<jwt>` per Phase 18 D-04.
- Progress bar component: Angular Material `MatProgressBar` (determinate for jobs with `progress_total > 0`, indeterminate for RUNNING jobs with no total).
- REST endpoint for job list: `GET /api/v1/jobs?job_type={type}&status={status}&limit=50&offset={N}`. Returns `BackgroundJob` rows as a Pydantic schema (no output/error JSONB in list response — only in `GET /jobs/{id}`).
- New Pydantic schemas in `backend/app/schemas/jobs.py`: `JobListItem` (no output/error) and `JobDetail` (full output+error JSONB).
- `DELETE /api/v1/jobs`: accepts `job_type` + `status` query params; deletes all matching rows for the requesting SuperAdmin session (no org filter — global firehose matches Phase 18 D-05).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — MON-01 through MON-07 (full requirement text + acceptance criteria)
- `.planning/ROADMAP.md` §Phase 19 — Success criteria (7 criteria)

### Phase 18 Locked Decisions (SSE Transport)
- `.planning/phases/18-sse-transport/18-CONTEXT.md` — D-04 (token via query param), D-05 (global firehose), D-06 (event payload schema), D-07 (24h bootstrap burst) — MUST read before implementing the Angular SSE service

### Backend Models & Schemas
- `backend/app/models/jobs.py` — `BackgroundJob` model: all columns, JSONB field shapes, indexes
- `backend/app/api/v1/endpoints/jobs.py` — Phase 18 SSE endpoint already built; Phase 19 adds `GET /jobs`, `GET /jobs/{id}`, `DELETE /jobs` to the same file
- `backend/app/api/v1/deps.py` — `get_current_superadmin` dependency (use for new REST endpoints)

### Phase 17 Output JSONB Schemas (for drill-in rendering)
- `.planning/phases/17-service-instrumentation/17-CONTEXT.md` — D-08 to D-13 define exact JSONB schemas for autofill, download, scoring, sync, error outputs

### Frontend Integration Points
- `frontend/src/app/features/configuration/configuration.routes.ts` — Add `/jobs` route + `IsSuperAdminGuard`
- `frontend/src/app/features/configuration/configuration-shell.component.ts` — Add "Job Monitor" sidebar entry (conditional on `is_superuser`)
- `frontend/src/app/features/configuration/pages/field-mappings-panel.component.ts` — Side panel pattern to replicate for the drill-in panel
- `frontend/src/app/core/services/api.service.ts` — HTTP service; `JobMonitorService` is a new peer service
- `frontend/src/app/features/configuration/pages/admin.component.ts` — DO NOT modify; job monitor is a separate route

### Auth Pattern
- `frontend/src/app/core/guards/is-superadmin.guard.ts` — Apply to new `/jobs` route

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `field-mappings-panel.component.ts` (828 lines) — slide-in panel pattern: `@Input() open: boolean`, overlay backdrop, CSS `transform: translateX` animation. Copy this pattern for the job detail panel.
- `admin.component.ts` — `config-section` + `section-header` + `section-body` CSS classes; `badge`, `badge-valid/expired/missing` badge styles; `skeleton-block` pulse animation. Reuse these tokens in the job monitor page.
- `ApiService` — `get<T>()`, `post<T>()`, `delete<T>()` methods; use for REST job endpoints.
- `IsSuperAdminGuard` at `frontend/src/app/core/guards/is-superadmin.guard.ts` — import directly into new route config.
- Angular Material `MatProgressBar`, `MatTabsModule`, `MatChipsModule` — available in the project; use for tabs + progress + status filters.

### Established Patterns
- **SSE via native `EventSource`**: Browser API, not Angular HttpClient. `const source = new EventSource(url)`. Manage lifecycle in `ngOnDestroy()` via `source.close()`.
- **Standalone components**: All components are standalone (no NgModules). Declare all imports inline in `imports: []`.
- **BehaviorSubject for live state**: Expose reactive state as `Observable` from a `BehaviorSubject` in the service — components `async` pipe or subscribe.
- **OnPush change detection**: Default Angular schematic config. Ensure `ChangeDetectorRef.markForCheck()` is called when SSE events update the job map outside Angular's zone (or use `NgZone.run()`).
- **Subscription cleanup**: Store subscriptions and call `unsubscribe()` in `ngOnDestroy()`. Use `takeUntil(this.destroy$)` pattern.

### Integration Points
- `configuration.routes.ts` — add child route `{ path: 'jobs', loadComponent: ..., canActivate: [IsSuperAdminGuard] }`
- `configuration-shell.component.ts` `ngOnInit()` — add Job Monitor nav item conditionally in the existing `user?.is_superuser` check (or add a second subscribe block)
- `backend/app/api/v1/endpoints/jobs.py` — existing SSE endpoint; add `GET /jobs`, `GET /jobs/{id}`, `DELETE /jobs` here
- `backend/app/api/v1/__init__.py` — jobs router already registered (Phase 18); no change needed

</code_context>

<specifics>
## Specific Ideas

- The job list component maintains an in-memory `Map<string, JobSnapshot>` keyed by `job_id`. SSE `job_update` events upsert into the map; the rendered list derives from this map filtered/sorted/paginated.
- Tab count badges show `jobs.filter(j => j.status === 'RUNNING' || j.status === 'PENDING').length` for the tab's job type — "active" count only, not total.
- "Clear completed" / "Clear failed" should show a brief confirmation snackbar after success (matching admin.component.ts style), e.g. "23 completed sync jobs cleared."
- The `job_id` in the detail panel header uses a monospace font and a small copy icon (matching the `slug-code` pattern in admin.component.ts). On click: `navigator.clipboard.writeText(job.job_id)` + snackbar "Job ID copied".
- For jobs still RUNNING when the panel is open, the panel should live-update as SSE events arrive (the same map upsert propagates to the open panel).

</specifics>

<deferred>
## Deferred Ideas

- **SSE-03 scaling**: Full pub/sub backend upgrade for 50+ concurrent SuperAdmin connections — future requirement, already noted in Phase 18 deferred.
- **Deep-link to SyncJob records**: Sync drill-in shows `sync_job_id` as reference only; a clickable link to a sync run detail view would be a future enhancement.
- **Export job history**: CSV/JSON export of the job list — not in scope for v1.3.

</deferred>

---

*Phase: 19-superadmin-monitoring-ui*
*Context gathered: 2026-05-11*
