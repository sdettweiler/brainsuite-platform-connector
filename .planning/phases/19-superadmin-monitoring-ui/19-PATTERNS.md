# Phase 19: SuperAdmin Monitoring UI - Pattern Map

**Mapped:** 2026-05-11
**Files analyzed:** 9
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/schemas/jobs.py` | schema | transform | `backend/app/schemas/user.py` | exact |
| `backend/app/api/v1/endpoints/jobs.py` (MODIFY) | controller | CRUD + request-response | `backend/app/api/v1/endpoints/assets.py` | exact |
| `frontend/src/app/core/services/job-monitor.service.ts` | service | event-driven + pub-sub | `frontend/src/app/core/services/auth.service.ts` | role-match |
| `frontend/src/app/features/configuration/pages/job-monitor/job-monitor.component.ts` | component | event-driven | `frontend/src/app/features/configuration/pages/admin.component.ts` | role-match |
| `frontend/src/app/features/configuration/pages/job-monitor/job-monitor.component.html` | component | event-driven | `frontend/src/app/features/configuration/pages/admin.component.ts` (inline template) | role-match |
| `frontend/src/app/features/configuration/pages/job-monitor/job-monitor.component.scss` | config | — | `frontend/src/app/features/configuration/pages/field-mappings-panel.component.ts` (inline styles) | role-match |
| `frontend/src/app/features/configuration/pages/job-monitor/job-detail-panel/job-detail-panel.component.ts` | component | request-response | `frontend/src/app/features/configuration/pages/field-mappings-panel.component.ts` | exact |
| `frontend/src/app/features/configuration/configuration.routes.ts` (MODIFY) | config | — | self (existing `admin` route pattern) | exact |
| `frontend/src/app/features/configuration/configuration-shell.component.ts` (MODIFY) | component | — | self (existing `is_superuser` nav pattern) | exact |

---

## Pattern Assignments

### `backend/app/schemas/jobs.py` (schema, transform)

**Analog:** `backend/app/schemas/user.py`

**Imports pattern** (user.py lines 1-6):
```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
```

**Core schema pattern** (user.py lines 56-67):
```python
class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    is_superuser: bool = False
    organization_id: Optional[uuid.UUID]
    last_login: Optional[datetime]
    created_at: datetime
    full_name: str

    class Config:
        from_attributes = True
```

**Inheritance pattern for detail schema** (user.py lines 69-71):
```python
class UserWithRole(UserResponse):
    role: Optional[str] = None
```

**Apply to new schemas:**
```python
# backend/app/schemas/jobs.py — copy Config pattern exactly
class JobListItem(BaseModel):
    id: uuid.UUID
    job_type: str
    status: str
    progress_current: int
    progress_total: Optional[int]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    metadata_: Optional[dict]

    class Config:
        from_attributes = True

class JobDetail(JobListItem):
    output: Optional[dict]
    error: Optional[dict]
```

---

### `backend/app/api/v1/endpoints/jobs.py` — MODIFY (controller, CRUD + request-response)

**Analog:** `backend/app/api/v1/endpoints/assets.py`

**Imports pattern** (assets.py lines 1-27):
```python
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.base import get_db
from app.models.user import User
from app.api.v1.deps import get_current_user, get_current_admin
```

**New import additions for jobs.py** (add to existing imports):
```python
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import uuid

from app.db.base import get_db
from app.models.jobs import BackgroundJob
from app.api.v1.deps import get_current_superadmin
from app.schemas.jobs import JobListItem, JobDetail
```

**GET list endpoint pattern** (assets.py lines 35-60):
```python
@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(
            Project.organization_id == current_user.organization_id,
            Project.is_active == True,
        )
    )
    projects = result.scalars().all()
    return [...]
```

**Apply as GET /jobs:**
```python
@router.get("", response_model=List[JobListItem])
async def list_jobs(
    job_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    q = select(BackgroundJob).order_by(BackgroundJob.started_at.desc())
    if job_type:
        q = q.where(BackgroundJob.job_type == job_type)
    if status:
        q = q.where(BackgroundJob.status == status)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()
```

**GET by ID with 404 pattern** (assets.py lines 99-111):
```python
@router.delete("/projects/{project_id}")
async def delete_project(...):
    project = await db.get(Project, project_id)
    if not project or project.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Project not found")
```

**Apply as GET /jobs/{job_id}:**
```python
@router.get("/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(BackgroundJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
```

**DELETE with Query params and 204 pattern** (assets.py lines 262-274):
```python
@router.delete("/metadata-fields/{field_id}")
async def delete_metadata_field(
    field_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    field = await db.get(MetadataField, field_id)
    if not field or field.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Field not found")
    ...
    await db.commit()
    return {"detail": "Field deleted"}
```

**Apply as DELETE /jobs** (bulk delete with SQLAlchemy `delete()`):
```python
@router.delete("", status_code=204, response_class=Response)
async def delete_jobs(
    job_type: str = Query(...),
    status: str = Query(...),
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(BackgroundJob).where(
            BackgroundJob.job_type == job_type,
            BackgroundJob.status == status,
        )
    )
    await db.commit()
    return Response(status_code=204)
```

**NOTE:** The existing `jobs.py` file contains only the SSE `/stream` route and its helpers. All three new routes are appended to the same `router` object.

---

### `frontend/src/app/core/services/job-monitor.service.ts` (service, event-driven)

**Analog:** `frontend/src/app/core/services/auth.service.ts`

**Injectable + BehaviorSubject pattern** (auth.service.ts lines 40-46):
```typescript
@Injectable({ providedIn: 'root' })
export class AuthService {
  private accessToken$ = new BehaviorSubject<string | null>(null);
  private user$ = new BehaviorSubject<CurrentUser | null>(null);
  currentUser$ = this.user$.asObservable();
  constructor(private http: HttpClient, private router: Router) {}
```

**Token read pattern** (auth.service.ts lines 57-59):
```typescript
getAccessToken(): string | null {
  return this.accessToken$.value;
}
```

**Note on token source:** The CONTEXT.md specifies reading `access_token` from `localStorage`. The existing `AuthService` stores the token only in memory (`BehaviorSubject`), not in localStorage. Verify actual localStorage key at runtime (auth interceptor or login tap). If no localStorage key is found, inject `AuthService` and call `getAccessToken()` instead.

**Apply pattern for JobMonitorService:**
```typescript
import { Injectable, NgZone, OnDestroy } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { AuthService } from './auth.service';

export type SseStatus = 'live' | 'reconnecting' | 'disconnected';

export interface JobSnapshot {
  job_id: string;
  job_type: string;
  org_id: string;
  status: string;
  progress_current: number;
  progress_total: number;
  started_at: string | null;
  ended_at: string | null;
}

@Injectable({ providedIn: 'root' })
export class JobMonitorService implements OnDestroy {
  private jobMap = new Map<string, JobSnapshot>();
  private jobsSubject = new BehaviorSubject<JobSnapshot[]>([]);
  jobs$ = this.jobsSubject.asObservable();

  private statusSubject = new BehaviorSubject<SseStatus>('reconnecting');
  connectionStatus$ = this.statusSubject.asObservable();

  private eventSource: EventSource | null = null;
  private reconnectAttempts = 0;

  constructor(private ngZone: NgZone, private authService: AuthService) {}

  connect(): void {
    const token = this.authService.getAccessToken();
    const url = `/api/v1/jobs/stream?token=${token}`;
    this.eventSource = new EventSource(url);

    this.eventSource.addEventListener('job_update', (event: MessageEvent) => {
      this.ngZone.run(() => {
        const job: JobSnapshot = JSON.parse(event.data);
        this.jobMap.set(job.job_id, job);
        this.jobsSubject.next(Array.from(this.jobMap.values()));
      });
    });

    this.eventSource.onopen = () => this.ngZone.run(() => {
      this.reconnectAttempts = 0;
      this.statusSubject.next('live');
    });

    this.eventSource.onerror = () => this.ngZone.run(() => {
      this.reconnectAttempts++;
      this.statusSubject.next(this.reconnectAttempts >= 3 ? 'disconnected' : 'reconnecting');
    });
  }

  disconnect(): void {
    this.eventSource?.close();
    this.eventSource = null;
  }

  clearJobMap(): void {
    this.jobMap.clear();
    this.jobsSubject.next([]);
  }

  ngOnDestroy(): void {
    this.disconnect();
  }
}
```

---

### `frontend/src/app/features/configuration/pages/job-monitor/job-monitor.component.ts` (component, event-driven)

**Analog:** `frontend/src/app/features/configuration/pages/admin.component.ts`

**Standalone component + imports pattern** (admin.component.ts lines 53-57):
```typescript
@Component({
  standalone: true,
  selector: 'app-admin',
  imports: [CommonModule, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule,
            MatProgressSpinnerModule, MatSlideToggleModule, MatSnackBarModule],
```

**Apply for job-monitor.component.ts** (additional Material modules needed):
```typescript
import { Component, OnInit, OnDestroy, ChangeDetectionStrategy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { MatTabsModule } from '@angular/material/tabs';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatChipsModule } from '@angular/material/chips';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { JobMonitorService, JobSnapshot, SseStatus } from '../../../../core/services/job-monitor.service';
import { ApiService } from '../../../../core/services/api.service';
import { JobDetailPanelComponent } from './job-detail-panel/job-detail-panel.component';

@Component({
  standalone: true,
  selector: 'app-job-monitor',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CommonModule,
    MatTabsModule,
    MatProgressBarModule,
    MatChipsModule,
    MatButtonModule,
    MatSnackBarModule,
    JobDetailPanelComponent,
  ],
  templateUrl: './job-monitor.component.html',
  styleUrls: ['./job-monitor.component.scss'],
})
export class JobMonitorComponent implements OnInit, OnDestroy {
  private destroy$ = new Subject<void>();
```

**takeUntil + destroy$ cleanup pattern** (field-mappings-panel.component.ts lines 621-624, 670-673):
```typescript
// In ngOnInit:
this.someObservable$.pipe(takeUntil(this.destroy$)).subscribe(...)

// In ngOnDestroy:
ngOnDestroy(): void {
  this.destroy$.next();
  this.destroy$.complete();
}
```

**snackBar confirmation pattern** (field-mappings-panel.component.ts lines 800-803):
```typescript
this.snackBar.open('Field mappings saved', '', { duration: 3000 });
// error variant:
this.snackBar.open('Failed to save — please try again.', 'Close', { duration: 4000, panelClass: ['snack-error'] });
```

**CSS class tokens to reuse** (admin.component.ts template lines 61-70):
```html
<div class="page-container">
  <section class="config-section">
    <div class="section-header">...</div>
    <div class="section-body">
      <div *ngIf="loading" class="skeleton-block"></div>
      <span class="badge badge-valid">VALID</span>
      <span class="badge badge-expired">EXPIRED</span>
      <span class="badge badge-missing">MISSING</span>
    </div>
  </section>
</div>
```

---

### `frontend/src/app/features/configuration/pages/job-monitor/job-detail-panel/job-detail-panel.component.ts` (component, request-response)

**Analog:** `frontend/src/app/features/configuration/pages/field-mappings-panel.component.ts` — exact copy of structural pattern.

**Panel Input/Output contract** (field-mappings-panel.component.ts lines 609-619):
```typescript
export class FieldMappingsPanelComponent implements OnInit, OnChanges, OnDestroy {
  @Input() app: BrainsuiteApp | null = null;
  @Input() isOpen = false;

  @Output() closed = new EventEmitter<void>();
  @Output() saved = new EventEmitter<void>();
```

**Apply for job-detail-panel.component.ts:**
```typescript
export class JobDetailPanelComponent implements OnChanges, OnDestroy {
  @Input() jobId: string | null = null;
  @Input() isOpen = false;

  @Output() closed = new EventEmitter<void>();
```

**Backdrop + slide animation pattern** (field-mappings-panel.component.ts lines 99-108):
```html
<!-- Backdrop -->
<div
  class="slide-panel-backdrop"
  [class.active]="isOpen"
  (click)="onBackdropClick()"
></div>

<!-- Slide Panel -->
<div class="slide-panel" [class.open]="isOpen" role="dialog" aria-modal="true">
```

**CSS for backdrop + slide** (field-mappings-panel.component.ts lines 313-347):
```scss
.slide-panel-backdrop {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  opacity: 0;
  transition: opacity 0.3s ease;
  z-index: 999;
  pointer-events: none;
}
.slide-panel-backdrop.active {
  opacity: 1;
  pointer-events: auto;
}
.slide-panel {
  position: fixed;
  top: 0; right: 0;
  width: 600px;
  max-width: 90vw;
  height: 100vh;
  background: var(--bg-card);
  border-left: 1px solid var(--border);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.18);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-panel.open {
  transform: translateX(0);
}
```

**Header layout pattern** (field-mappings-panel.component.ts lines 110-130):
```html
<div class="panel-header">
  <div class="header-title">
    <div class="header-title-row">
      <span class="app-title">{{ app?.name }}</span>
      <span class="app-type-badge" [class]="'type-' + (app?.app_type?.toLowerCase() ?? '')">{{ app?.app_type }}</span>
    </div>
    <p class="panel-subtitle">Map metadata fields to BrainSuite API fields</p>
  </div>
  <button mat-icon-button class="close-btn" type="button" aria-label="Close panel" (click)="cancel()">
    <i class="bi bi-x-lg"></i>
  </button>
</div>
```

**onChanges data-fetch pattern** (field-mappings-panel.component.ts lines 657-668):
```typescript
ngOnChanges(changes: SimpleChanges): void {
  const isOpenChange = changes['isOpen'];
  if (isOpenChange && this.isOpen && this.app) {
    this.loadFieldMappings();
  }
  const appChange = changes['app'];
  if (appChange && this.isOpen && this.app) {
    this.loadFieldMappings();
  }
}
```

**Apply for job-detail-panel.component.ts** — fetch `GET /jobs/{jobId}` when `isOpen` becomes `true` or `jobId` changes:
```typescript
ngOnChanges(changes: SimpleChanges): void {
  const openChange = changes['isOpen'];
  const idChange = changes['jobId'];
  if ((openChange?.currentValue || idChange) && this.isOpen && this.jobId) {
    this.loadJobDetail();
  }
}

private loadJobDetail(): void {
  this.loading = true;
  this.jobDetail = null;
  this.api.get<JobDetail>(`/jobs/${this.jobId}`).pipe(
    takeUntil(this.destroy$),
  ).subscribe({
    next: (detail) => { this.jobDetail = detail; this.loading = false; },
    error: () => { this.loading = false; },
  });
}
```

**ApiService usage pattern** (field-mappings-panel.component.ts lines 634-655):
```typescript
this.loadRequest$.pipe(
  switchMap(appId => this.api.get<FieldMappingApiResponse>(
    `/brainsuite-config/apps/${appId}/field-mappings`
  )),
  takeUntil(this.destroy$),
).subscribe({ next: ..., error: ... });
```

---

### `frontend/src/app/features/configuration/configuration.routes.ts` — MODIFY (config)

**Analog:** self — existing `admin` route at lines 27-30.

**Existing superadmin-guarded route pattern** (configuration.routes.ts lines 27-30):
```typescript
{
  path: 'admin',
  loadComponent: () => import('./pages/admin.component').then(m => m.AdminComponent),
  canActivate: [IsSuperAdminGuard],
},
```

**Add after `admin` entry:**
```typescript
{
  path: 'jobs',
  loadComponent: () => import('./pages/job-monitor/job-monitor.component').then(m => m.JobMonitorComponent),
  canActivate: [IsSuperAdminGuard],
},
```

No new imports needed — `IsSuperAdminGuard` is already imported at line 2.

---

### `frontend/src/app/features/configuration/configuration-shell.component.ts` — MODIFY (component)

**Analog:** self — existing superadmin nav-push pattern at lines 73-79.

**Existing conditional nav pattern** (configuration-shell.component.ts lines 73-79):
```typescript
ngOnInit(): void {
  this.authService.currentUser$.subscribe(user => {
    this.navItems = [...this.baseNavItems];
    if (user?.is_superuser) {
      this.navItems.push({ path: 'admin', label: 'Admin', icon: 'shield-lock' });
    }
  });
}
```

**Apply — push Job Monitor item inside the same `is_superuser` block:**
```typescript
if (user?.is_superuser) {
  this.navItems.push({ path: 'admin', label: 'Admin', icon: 'shield-lock' });
  this.navItems.push({ path: 'jobs', label: 'Job Monitor', icon: 'activity' });
}
```

Note: Bootstrap Icons class is `bi-activity`; the `icon` field in `ConfigNav` is used as `'bi-' + item.icon` (shell template line 26), so pass `'activity'` (without `bi-` prefix).

---

## Shared Patterns

### SuperAdmin Authentication (backend)
**Source:** `backend/app/api/v1/deps.py` lines 67-80
**Apply to:** All three new REST endpoints in `jobs.py`
```python
async def get_current_superadmin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SuperAdmin privileges required",
        )
    return current_user
```
Use as `current_user: User = Depends(get_current_superadmin)` — no `db` session needed for the auth check itself, but add `db: AsyncSession = Depends(get_db)` for DB queries.

### IsSuperAdminGuard (frontend routes)
**Source:** `frontend/src/app/core/guards/is-superadmin.guard.ts` lines 1-31
**Apply to:** `/jobs` route in `configuration.routes.ts` via `canActivate: [IsSuperAdminGuard]`

### NgZone + OnPush
**Source:** Documented in RESEARCH.md; no existing EventSource service in codebase.
**Apply to:** `JobMonitorService.connect()` — wrap all EventSource callbacks in `this.ngZone.run(() => { ... })`.
**Apply to:** `JobMonitorComponent` — declare `changeDetection: ChangeDetectionStrategy.OnPush` and inject `ChangeDetectorRef`; call `this.cdr.markForCheck()` after state mutations if `async` pipe is not used.

### takeUntil + destroy$ Subscription Cleanup
**Source:** `frontend/src/app/features/configuration/pages/field-mappings-panel.component.ts` lines 621-624, 670-673
**Apply to:** All new Angular components and services that hold subscriptions.
```typescript
private destroy$ = new Subject<void>();

ngOnDestroy(): void {
  this.destroy$.next();
  this.destroy$.complete();
}

// In subscriptions:
someObservable$.pipe(takeUntil(this.destroy$)).subscribe(...)
```

### Snackbar Confirmation
**Source:** `frontend/src/app/features/configuration/pages/field-mappings-panel.component.ts` lines 800-806
**Apply to:** `JobMonitorComponent` clear-completed / clear-failed actions.
```typescript
// Success:
this.snackBar.open('23 completed sync jobs cleared.', '', { duration: 3000 });
// Error:
this.snackBar.open('Failed to clear jobs — please try again.', 'Close', { duration: 4000, panelClass: ['snack-error'] });
```

### ApiService Generic HTTP
**Source:** `frontend/src/app/core/services/api.service.ts` lines 42-74
**Apply to:** `JobDetailPanelComponent.loadJobDetail()` and `JobMonitorComponent` delete actions.
```typescript
// GET:
this.api.get<T>(path, params?): Observable<T>
// DELETE:
this.api.delete<T>(path): Observable<T>
```
Note: `ApiService.delete()` accepts only a path string. For DELETE with query params (`?job_type=sync&status=COMPLETE`), append params to the path string directly (no HttpParams helper on the `delete()` method).

### Pydantic `class Config` / `from_attributes`
**Source:** `backend/app/schemas/user.py` lines 66-67 (and all schemas in `backend/app/schemas/`)
**Apply to:** Both `JobListItem` and `JobDetail` in `backend/app/schemas/jobs.py`.
```python
class Config:
    from_attributes = True
```

---

## No Analog Found

All files have close analogs in the codebase. The EventSource + NgZone pattern has no direct code analog (no existing SSE client service), but the RESEARCH.md provides a complete authoritative implementation at lines 130-174.

---

## Metadata

**Analog search scope:** `backend/app/schemas/`, `backend/app/api/v1/endpoints/`, `backend/app/api/v1/deps.py`, `backend/app/models/jobs.py`, `frontend/src/app/core/services/`, `frontend/src/app/core/guards/`, `frontend/src/app/features/configuration/`
**Files scanned:** 13
**Pattern extraction date:** 2026-05-11
