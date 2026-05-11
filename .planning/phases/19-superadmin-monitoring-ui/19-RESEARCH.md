# Phase 19: SuperAdmin Monitoring UI — Research

**Confidence:** HIGH
**Date:** 2026-05-11

---

## Summary

Phase 19 builds a new `/configuration/jobs` Angular page for SuperAdmins to monitor background jobs in real time via SSE. All dependencies are verified, patterns are established, and no new packages are needed. Three implementation tiers: backend REST endpoints → Angular service (SSE + state) → UI components (list + drill-in panel).

---

## Architecture Responsibility Map

| Capability | File | Notes |
|---|---|---|
| Job list REST endpoint | `backend/app/api/v1/endpoints/jobs.py` | Add GET /jobs, GET /jobs/{id}, DELETE /jobs |
| Pydantic schemas | `backend/app/schemas/jobs.py` (new) | JobListItem + JobDetail |
| Angular SSE service | `frontend/src/app/core/services/job-monitor.service.ts` (new) | EventSource lifecycle, in-memory Map, BehaviorSubject |
| Job monitor page | `frontend/src/app/features/configuration/pages/job-monitor/` (new) | Tab layout, status filter, job list table |
| Drill-in panel | `frontend/src/app/features/configuration/pages/job-monitor/job-detail-panel/` (new) | Replicates field-mappings-panel pattern |
| Route registration | `frontend/src/app/features/configuration/configuration.routes.ts` | Add `{ path: 'jobs', ... canActivate: [IsSuperAdminGuard] }` |
| Sidebar nav | `frontend/src/app/features/configuration/configuration-shell.component.ts` | Add "Job Monitor" nav item, conditioned on `user?.is_superuser` |

---

## Backend: Existing SSE Endpoint (Phase 18)

The SSE endpoint is already built in `backend/app/api/v1/endpoints/jobs.py`:
- Route: `GET /api/v1/jobs/stream` (protected by `get_current_superadmin_sse`)
- On connect: emits 24h bootstrap burst of recent jobs
- Heartbeat: keeps proxy connections alive
- Event payload (Phase 18 D-06): `{ job_id, job_type, status, progress_current, progress_total, started_at, ended_at, metadata_ }`

Phase 19 adds to the same file:
```python
# GET /api/v1/jobs
@router.get("/jobs", response_model=list[JobListItem])
async def list_jobs(job_type: str | None, status: str | None, limit: int = 50, offset: int = 0, ...)

# GET /api/v1/jobs/{job_id}
@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(job_id: str, ...)

# DELETE /api/v1/jobs
@router.delete("/jobs", status_code=204)
async def delete_jobs(job_type: str, status: str, ...)
```

All three use `get_current_superadmin` from `backend/app/api/v1/deps.py` (no org filter — global firehose, matches Phase 18 D-05).

---

## Backend: BackgroundJob Model (Phase 16)

Key columns from `backend/app/models/jobs.py`:
- `id` (UUID PK)
- `job_type` (str: "sync" | "download" | "autofill" | "scoring")
- `org_id` (UUID FK)
- `status` (str: "PENDING" | "RUNNING" | "COMPLETE" | "FAILED")
- `progress_current` (int)
- `progress_total` (int)
- `output` (JSONB)
- `error` (JSONB: `{ traceback, message }`)
- `metadata_` (JSONB: external job IDs like `brainsuite_job_id`, `sync_job_id`)
- `started_at`, `ended_at` (datetime)

---

## Backend: JSONB Output Schemas (Phase 17)

From `17-CONTEXT.md` D-08 to D-13:

**Autofill output:**
```json
{ "fields": [{ "field_name": "...", "value": "...", "source": "gemini|whisper" }], "whisper_transcript": "...", "language": "en_US" }
```

**Download output:**
```json
{ "downloaded": [{ "asset_id": "...", "url": "..." }], "failed": [{ "asset_id": "...", "error": "..." }] }
```

**Scoring output:**
```json
{ "assets": [{ "asset_id": "...", "score": 0.87, "endpoint_type": "...", "brainsuite_job_id": "..." }] }
```

**Sync output:**
```json
{ "platform": "...", "sync_job_id": "...", "records_fetched": 0, "records_processed": 0 }
```

**Error output** (all types):
```json
{ "traceback": "...", "message": "..." }
```

---

## Pydantic Schema Patterns

Existing schemas in `backend/app/schemas/` use:
- `class Config: from_attributes = True` (or `model_config = ConfigDict(from_attributes=True)` in Pydantic v2)
- Field aliasing via `Field(alias=...)` if needed
- `Optional[dict]` for JSONB fields

New schemas:
```python
class JobListItem(BaseModel):
    id: UUID
    job_type: str
    status: str
    progress_current: int
    progress_total: int
    started_at: datetime
    ended_at: datetime | None
    metadata_: dict | None

class JobDetail(JobListItem):
    output: dict | None
    error: dict | None
```

---

## Angular: EventSource + NgZone Pattern

**Critical gotcha:** EventSource callbacks run outside Angular's zone. Must wrap state updates with `NgZone.run()` to trigger change detection on OnPush components.

```typescript
// job-monitor.service.ts
@Injectable({ providedIn: 'root' })
export class JobMonitorService implements OnDestroy {
  private jobMap = new Map<string, JobSnapshot>();
  private jobsSubject = new BehaviorSubject<JobSnapshot[]>([]);
  jobs$ = this.jobsSubject.asObservable();
  
  private connectionStatus$ = new BehaviorSubject<'live' | 'reconnecting' | 'disconnected'>('reconnecting');
  private eventSource: EventSource | null = null;
  private reconnectAttempts = 0;

  constructor(private ngZone: NgZone) {}

  connect(): void {
    const token = localStorage.getItem('access_token');
    const url = `/api/v1/jobs/stream?token=${token}`;
    this.eventSource = new EventSource(url);
    
    this.eventSource.addEventListener('job_update', (event) => {
      this.ngZone.run(() => {
        const job = JSON.parse(event.data);
        this.jobMap.set(job.job_id, job);
        this.jobsSubject.next(Array.from(this.jobMap.values()));
      });
    });

    this.eventSource.onopen = () => this.ngZone.run(() => {
      this.reconnectAttempts = 0;
      this.connectionStatus$.next('live');
    });

    this.eventSource.onerror = () => this.ngZone.run(() => {
      this.reconnectAttempts++;
      this.connectionStatus$.next(this.reconnectAttempts >= 3 ? 'disconnected' : 'reconnecting');
    });
  }

  ngOnDestroy(): void {
    this.eventSource?.close();
  }
}
```

---

## Angular: Slide-In Panel Pattern (field-mappings-panel.component.ts)

The existing panel uses:
- `@Input() open: boolean` — controls visibility
- `@Output() closed = new EventEmitter()` — parent dismisses on close
- Overlay backdrop `<div class="panel-overlay">` + `.panel-content` with CSS `transform: translateX(100%)` → `translateX(0)` transition
- `(click)` on overlay emits `closed`

Job detail panel replicates this exactly. Parent component manages `selectedJobId: string | null`; passes `[open]="selectedJobId !== null"` and `[jobId]="selectedJobId"`.

---

## Angular: Tab + Filter Architecture

```
job-monitor.component.ts
  → tabs: MatTabsModule (4 tabs: Sync / Download / Autofill / Scoring)
  → Each tab: filter chips (All / Running / Completed / Failed) — client-side
  → Job table (50 rows, sorted by started_at DESC)
  → Progress bar: MatProgressBar [mode]="job.progress_total > 0 ? 'determinate' : 'indeterminate'"
  → Click row → open job-detail-panel
job-detail-panel.component.ts (slide-in, replicate field-mappings-panel pattern)
  → On input job_id change: fetch GET /jobs/{id} for full output/error
  → Type-specific drill-in sections
```

---

## Angular: Route Registration

```typescript
// configuration.routes.ts — add to existing children array:
{
  path: 'jobs',
  loadComponent: () => import('./pages/job-monitor/job-monitor.component').then(m => m.JobMonitorComponent),
  canActivate: [IsSuperAdminGuard]
}
```

---

## Angular: Sidebar Nav Item

```typescript
// configuration-shell.component.ts — inside existing is_superuser conditional:
if (user?.is_superuser) {
  this.baseNavItems.push({ label: 'Job Monitor', icon: 'bi-activity', route: '/configuration/jobs' });
}
```

---

## Validation Architecture

### Unit / Integration Tests
1. GET /jobs returns 200 with JobListItem list (no output/error fields)
2. GET /jobs?job_type=sync filters correctly
3. GET /jobs?status=FAILED filters correctly
4. GET /jobs/{id} returns 200 with JobDetail including output+error JSONB
5. DELETE /jobs?job_type=sync&status=COMPLETE deletes matching rows (204)
6. Non-SuperAdmin token → GET /jobs returns 403
7. Non-SuperAdmin token → DELETE /jobs returns 403
8. GET /jobs/{id} for non-existent job → 404

### E2E / Manual UAT
- MON-01: /configuration/jobs page loads, tabs visible, jobs appear, update without refresh
- MON-02: RUNNING download job shows progress bar advancing
- MON-03: Autofill drill-in shows fields table
- MON-04: Download drill-in shows asset list with URLs
- MON-05: Failed job drill-in shows copyable traceback
- MON-06: Scoring drill-in shows per-asset scores
- MON-07: All drill-in panels show job_id and external IDs

---

## Security Analysis

- All 3 new endpoints guarded by `get_current_superadmin` (JWT + is_superuser claim) — ASVS L1
- DELETE endpoint accepts `job_type` + `status` query params; no org filter (global SuperAdmin scope matches Phase 18 D-05); safe since only SuperAdmins can reach it
- JSONB output rendered in `<pre>` or table — no HTML injection risk (Angular templates escape by default)
- SSE token via query param (Phase 18 D-04 decision) — acceptable for v1.3 scale

---

## Environment Audit

| Dependency | Version | Status |
|---|---|---|
| Angular Material | 17.x | ✓ In project |
| MatTabsModule | included | ✓ |
| MatProgressBarModule | included | ✓ |
| MatChipsModule | included | ✓ |
| MatSnackBarModule | included | ✓ |
| RxJS | 7.8 | ✓ |
| sse-starlette | 3.4.2 | ✓ Phase 18 |
| Bootstrap Icons | included | ✓ bi-activity |

No new packages required.

---

## Pitfalls & Prevention

1. **EventSource + OnPush**: Wrap all SSE callbacks in `NgZone.run()` — otherwise BehaviorSubject updates won't trigger change detection
2. **MatProgressBar mode switching**: Set `[mode]` dynamically based on `progress_total > 0`; don't toggle `[value]` without also setting `mode="determinate"`
3. **Panel lifecycle**: Close EventSource in `ngOnDestroy()` of JobMonitorService; unsubscribe all observables with `takeUntil(this.destroy$)`
4. **Large traceback display**: Truncate at 10KB for display; store full string separately for clipboard write
5. **Stale SSE data on reconnect**: On reconnect, re-fetch the bootstrap burst (Phase 18 D-07 auto-handles this); clear jobMap on reconnect to avoid stale entries
6. **DELETE confirmation**: No modal required per CONTEXT.md; use Angular Material snackbar for post-action confirmation only

---

*RESEARCH COMPLETE — Phase 19 SuperAdmin Monitoring UI is fully researched and ready to plan.*
