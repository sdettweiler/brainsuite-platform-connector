---
phase: 19-superadmin-monitoring-ui
reviewed: 2026-05-11T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - backend/app/schemas/jobs.py
  - backend/tests/test_jobs_api.py
  - backend/app/api/v1/endpoints/jobs.py
  - frontend/src/app/core/services/job-monitor.service.ts
  - frontend/src/app/features/configuration/configuration.routes.ts
  - frontend/src/app/features/configuration/configuration-shell.component.ts
  - frontend/src/app/features/configuration/pages/job-monitor/job-monitor.component.ts
  - frontend/src/app/features/configuration/pages/job-monitor/job-monitor.component.html
  - frontend/src/app/features/configuration/pages/job-monitor/job-monitor.component.scss
  - frontend/src/app/features/configuration/pages/job-monitor/job-detail-panel/job-detail-panel.component.ts
  - frontend/src/app/features/configuration/pages/job-monitor/job-detail-panel/job-detail-panel.component.html
findings:
  critical: 4
  warning: 6
  info: 3
  total: 13
status: issues_found
---

# Phase 19: Code Review Report

**Reviewed:** 2026-05-11
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 19 delivers the SuperAdmin Job Monitoring UI: three backend REST endpoints (list, detail, bulk delete) and a full frontend implementation (SSE service, 4-tab job table, slide-panel detail view). The architecture is sound and the overall structure is clean. However, there are four blockers that must be addressed before this ships: a JWT token leaked into the URL (visible in server logs and browser history), an EventSource leak on every clear-jobs action, an unbounded bulk delete with no status guard, and a test that bypasses the actual endpoint under test for its 403 assertion.

---

## Critical Issues

### CR-01: JWT access token exposed in plain-text URL

**File:** `frontend/src/app/core/services/job-monitor.service.ts:39`

**Issue:** The SSE connection is opened with the access token appended as a query parameter (`?token=<access_jwt>`). `EventSource` cannot send custom headers, so this is an acknowledged design constraint (D-04). The problem is that `getAccessToken()` returns `string | null` (see `auth.service.ts:57`), and the value is interpolated directly with no null check:

```typescript
const token = this.authService.getAccessToken();
const url = `/api/v1/jobs/stream?token=${token}`;
this.eventSource = new EventSource(url);
```

If `token` is `null` (user session expired, race on first render), the literal string `"null"` is sent as the token value. The backend will then reject the request with a 401/403, but the EventSource will silently loop through reconnect attempts with an invalid `token=null` URL, incrementing `reconnectAttempts` and eventually locking the UI in "Disconnected" state permanently — even when the user's session is valid again. The `reconnectAttempts` counter is never reset after a disconnect, so a recovery is impossible without a page reload.

Secondary concern: Query-string tokens appear in server access logs and browser history. This is a known trade-off for SSE, but the `null` case is a distinct correctness bug on top of it.

**Fix:**
```typescript
connect(): void {
  const token = this.authService.getAccessToken();
  if (!token) {
    this.statusSubject.next('disconnected');
    return;
  }
  // close any existing connection before opening a new one (see CR-02)
  this.disconnect();
  const url = `/api/v1/jobs/stream?token=${encodeURIComponent(token)}`;
  this.eventSource = new EventSource(url);
  // ... rest unchanged
}
```

Also reset `reconnectAttempts = 0` inside `disconnect()` so a manual reconnect can recover.

---

### CR-02: EventSource leak — `connect()` called without closing the existing connection

**File:** `frontend/src/app/core/services/job-monitor.service.ts:37-58` and `frontend/src/app/features/configuration/pages/job-monitor/job-monitor.component.ts:158`

**Issue:** `connect()` unconditionally assigns `this.eventSource = new EventSource(url)` without closing the old one. `clearJobs()` in the component calls `this.jobMonitorService.connect()` after a successful delete, while `ngOnInit` also calls `connect()`. If `clearJobs` is triggered while an existing connection is open, the old `EventSource` object is leaked — it stays connected server-side, holds the previous token, and its callbacks still fire against the now-replaced subject reference. Every clear action adds one leaked connection for the lifetime of the page.

```typescript
// job-monitor.component.ts:154-159
next: () => {
  this.snackBar.open(...);
  this.jobMonitorService.clearJobMap();
  this.jobMonitorService.connect();  // <-- leaks previous EventSource
},
```

**Fix:** Guard `connect()` so it always closes the existing connection first:

```typescript
connect(): void {
  this.disconnect();                // close old connection unconditionally
  const token = this.authService.getAccessToken();
  if (!token) { this.statusSubject.next('disconnected'); return; }
  this.eventSource = new EventSource(...);
  // ...
}
```

---

### CR-03: Bulk delete has no RUNNING/PENDING status guard — active jobs can be silently deleted

**File:** `backend/app/api/v1/endpoints/jobs.py:214-229`

**Issue:** `DELETE /jobs?job_type=...&status=...` accepts any arbitrary `status` string without validation. A caller can pass `status=RUNNING` or `status=PENDING` and the endpoint will execute the delete without any check. There is no ORM-level or constraint preventing this. Per project memory, resetting/deleting PROCESSING (RUNNING) assets is explicitly forbidden ("PROCESSING assets have live BrainSuite job IDs; never reset them"). The same principle applies here: deleting a RUNNING job row while the worker is mid-flight leaves the worker with a dangling record reference and no way to write its completion status.

The frontend `clearJobs` button is disabled for RUNNING/PENDING (only COMPLETE and FAILED are exposed), but the API itself has no guard. The UI restriction is bypassable via direct API call or developer tools.

```python
@router.delete("", status_code=204, response_class=Response)
async def delete_jobs(
    job_type: str = Query(...),
    status: str = Query(...),
    ...
) -> Response:
    await db.execute(
        delete(BackgroundJob).where(
            BackgroundJob.job_type == job_type,
            BackgroundJob.status == status,
        )
    )
```

**Fix:** Add an explicit server-side guard:

```python
PROTECTED_STATUSES = {"RUNNING", "PENDING"}

@router.delete("", status_code=204, response_class=Response)
async def delete_jobs(
    job_type: str = Query(...),
    status: str = Query(...),
    ...
) -> Response:
    if status in PROTECTED_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot bulk-delete jobs with status '{status}'. Only COMPLETE and FAILED are permitted."
        )
    # ... rest unchanged
```

---

### CR-04: 403 tests do not test the endpoints under review — they test the dependency directly

**File:** `backend/tests/test_jobs_api.py:133-152`

**Issue:** Both `test_get_jobs_403_non_superadmin` and `test_delete_jobs_403_non_superadmin` call `get_current_superadmin` directly instead of going through `list_jobs` or `delete_jobs`:

```python
# test_get_jobs_403_non_superadmin (line 139)
await get_current_superadmin(current_user=mock_user)

# test_delete_jobs_403_non_superadmin (line 151) — identical body
await get_current_superadmin(current_user=mock_user)
```

Both tests are identical in body and test the same thing: the shared dependency function. They do not verify that `list_jobs` or `delete_jobs` actually wire `get_current_superadmin` as a dependency. If either endpoint ever changed its `Depends(...)` annotation (e.g., switched to a weaker check or removed the guard entirely), these tests would still pass. The 403 coverage for the endpoints themselves is illusory.

**Fix:** Call the endpoint functions with a non-superadmin user injected directly:

```python
@pytest.mark.asyncio
async def test_list_jobs_403_non_superadmin():
    from fastapi import HTTPException
    mock_db = AsyncMock()
    mock_user = _make_superuser(is_superuser=False)
    with pytest.raises(HTTPException) as exc_info:
        await list_jobs(db=mock_db, current_user=mock_user)
    assert exc_info.value.status_code == 403

@pytest.mark.asyncio
async def test_delete_jobs_403_non_superadmin():
    from fastapi import HTTPException
    mock_db = AsyncMock()
    mock_user = _make_superuser(is_superuser=False)
    with pytest.raises(HTTPException) as exc_info:
        await delete_jobs(job_type="sync_daily", status="COMPLETE", db=mock_db, current_user=mock_user)
    assert exc_info.value.status_code == 403
```

Note: This approach only works if the endpoint raises the exception itself rather than delegating entirely to FastAPI's DI resolver. Adjust to a full integration test with `TestClient` if direct injection does not trigger the guard.

---

## Warnings

### WR-01: `JobDetailPanelComponent` missing `ChangeDetectionStrategy.OnPush` — live updates will silently fail

**File:** `frontend/src/app/features/configuration/pages/job-monitor/job-detail-panel/job-detail-panel.component.ts:110`

**Issue:** The parent `JobMonitorComponent` is declared with `ChangeDetectionStrategy.OnPush`. The child `JobDetailPanelComponent` has no `changeDetection` annotation, defaulting to `ChangeDetectionStrategy.Default`. When `jobs$` emits an SSE update and `ngOnInit`'s subscription calls `loadJobDetail()`, the `loading` and `jobDetail` assignments happen inside a plain `subscribe` callback — not inside `NgZone`. With the parent on `OnPush`, Angular may not run change detection on the child after these assignments, meaning the panel can show stale data (old status, old progress) even after a live update arrives. The `JobMonitorService` wraps SSE callbacks in `ngZone.run()`, but the HTTP observable in `loadJobDetail()` has no such wrapping.

**Fix:** Add `ChangeDetectionStrategy.OnPush` to the panel and inject `ChangeDetectorRef`, then call `cdr.markForCheck()` in both the `next` and `error` callbacks of `loadJobDetail()`.

---

### WR-02: `clearJobs` forkJoin fires even when tab type list has no matching jobs of that status

**File:** `frontend/src/app/features/configuration/pages/job-monitor/job-monitor.component.ts:142-163`

**Issue:** `clearJobs()` dispatches `forkJoin(calls)` where `calls` is built from `this.TAB_TYPES[this.activeTab]` — always 4 calls for the Sync tab (`sync_daily`, `sync_full`, `sync_initial`, `sync_historical`). All 4 DELETE requests are fired unconditionally even if only 1 of those types has any COMPLETE/FAILED jobs. Empty DELETEs are harmless to correctness, but they make the snackbar message misleading:

```typescript
const count = allJobs.filter(j => types.includes(j.job_type) && j.status === statusToClear).length;
// count is from the in-memory map (SSE burst, possibly stale)
this.snackBar.open(`${count} ${statusLabel} ${label} jobs cleared.`, ...);
```

The `count` is taken from the client-side SSE snapshot, which only contains the last 24h of jobs. If the DB has older completed jobs (not in the SSE burst), `count` will under-report, and the message will be wrong. This is not a crash, but it creates operator confusion during an incident review.

**Fix:** Either (a) return a deleted-count from the backend and use that for the message, or (b) document clearly that count is an estimate from the live view, not the actual deleted count.

---

### WR-03: `reconnectAttempts` counter never resets after "Disconnected" — permanent lock-out

**File:** `frontend/src/app/core/services/job-monitor.service.ts:55-58`

**Issue:** After 3 errors, `statusSubject` emits `'disconnected'` and the UI shows "Disconnected". There is no automatic recovery: the counter stays at 3+, `onerror` keeps incrementing it, and every subsequent `onopen` resets it to 0 — but only if `onopen` fires, which it won't if the browser has stopped trying. `EventSource` will keep retrying indefinitely at the browser's default interval, but once `reconnectAttempts >= 3` every error just keeps emitting `'disconnected'` with no state change. If the user navigates away and back, `ngOnInit` calls `connect()` again but doesn't reset the counter, so the new connection starts with `reconnectAttempts >= 3` and will immediately show "Disconnected" on first error.

**Fix:** Reset `this.reconnectAttempts = 0` at the start of `connect()` (or inside `disconnect()`):

```typescript
connect(): void {
  this.disconnect();
  this.reconnectAttempts = 0;
  // ...
}
```

---

### WR-04: `list_jobs` returns `None`-started jobs at unpredictable position in sort order

**File:** `backend/app/api/v1/endpoints/jobs.py:191`

**Issue:** The query sorts by `BackgroundJob.started_at.desc()`. Jobs where `started_at IS NULL` (PENDING jobs that have never started) sort at the end in PostgreSQL's default `NULLS LAST` for `DESC`. This is usually correct, but PENDING jobs are time-sensitive items that operators want to see. Depending on the monitoring use case, these may need to appear first. More importantly, the frontend `getFilteredJobs()` re-sorts by `started_at` client-side with nulls going to position 0 (timestamp 0 = 1970), so PENDING jobs sort to the bottom on the client even if the server put them first. The two sort orderings are inconsistent, which means when paging, the "next page" offset is applied to server-order results, but the displayed slice is client-re-sorted — items can appear on both pages or on neither.

**Fix:** Either eliminate the client-side re-sort and trust server ordering, or make them consistent. If client-side sort is intentional (for live SSE updates), remove the `ORDER BY` from the server query and document that the REST endpoint is unordered.

---

### WR-05: `getJobDetail` uses `Observable<any>` — no type safety at the service boundary

**File:** `frontend/src/app/core/services/job-monitor.service.ts:78-80`

**Issue:** `getJobDetail` returns `Observable<any>`, bypassing TypeScript's type system at exactly the point where a `JobDetail` interface is defined in the consumer (`job-detail-panel.component.ts:14`). Template bindings like `jobDetail.output['platform']` and `detail.error?.traceback` have no compile-time verification. A backend field rename would produce a silent runtime failure with no TS error.

**Fix:**

```typescript
// In job-monitor.service.ts — import or re-export JobDetail, or use a shared type
getJobDetail(jobId: string): Observable<JobDetail> {
  return this.api.get<JobDetail>(`/jobs/${jobId}`);
}
```

The `JobDetail` interface in the panel component should be moved to the service (or a shared types file) so both sides use the same type.

---

### WR-06: `ConfigurationShellComponent.ngOnInit` subscription is never unsubscribed — memory leak

**File:** `frontend/src/app/features/configuration/configuration-shell.component.ts:74`

**Issue:** `this.authService.currentUser$.subscribe(...)` in `ngOnInit` has no `takeUntil`, `take(1)`, or stored `Subscription` to unsubscribe in `ngOnDestroy`. The component implements `OnInit` but not `OnDestroy`. Since `currentUser$` is a long-lived `BehaviorSubject`, the subscription persists after the component is destroyed. In a single-page app where the user navigates in and out of Configuration repeatedly, each navigation creates a new subscription. Over time this accumulates multiple active subscriptions updating `navItems` on a destroyed component reference.

**Fix:** Implement `OnDestroy` and use `takeUntilDestroyed` (Angular 16+) or a `destroy$` subject:

```typescript
export class ConfigurationShellComponent implements OnInit, OnDestroy {
  private destroy$ = new Subject<void>();

  ngOnInit(): void {
    this.authService.currentUser$
      .pipe(takeUntil(this.destroy$))
      .subscribe(user => { ... });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
```

---

## Info

### IN-01: `schemas/jobs.py` — `metadata_` field naming mismatch may surprise Pydantic serialization

**File:** `backend/app/schemas/jobs.py:16`

**Issue:** The schema field is named `metadata_` (with trailing underscore, matching the ORM column attribute name). When serialized to JSON by FastAPI, Pydantic v2 with `from_attributes = True` will output the key as `"metadata_"`, not `"metadata"`. The frontend `JobDetail` interface (panel component line 24) declares `metadata_: Record<string, unknown> | null`, so the naming matches. However, any external consumer of this API (curl, Postman, other services) will see `metadata_` as the key name, which is unusual and could be confused with a Python naming artifact. Consider adding `Field(alias="metadata")` or using a Pydantic `model_serializer` to output `"metadata"` on the wire.

---

### IN-02: `delete_jobs` test does not assert `db.execute` was called — the core behavior is untested

**File:** `backend/tests/test_jobs_api.py:122-130`

**Issue:** `test_delete_jobs_204` asserts `result.status_code == 204` and `mock_db.commit.assert_awaited_once()`, but never asserts that `db.execute` was called. If the implementation were changed to skip the DELETE and just commit, the test would still pass. Adding `mock_db.execute.assert_awaited_once()` would make the test more meaningful.

---

### IN-03: `job-detail-panel` — `aria-labelledby` missing on `role="dialog"`

**File:** `frontend/src/app/features/configuration/pages/job-monitor/job-detail-panel/job-detail-panel.component.html:5`

**Issue:** The panel uses `role="dialog" aria-modal="true"` but has no `aria-labelledby` or `aria-label` attribute. Screen readers will announce an unlabelled dialog, which is a WCAG 2.1 Level AA failure (4.1.2 Name, Role, Value). The job-type chip or panel header would serve as a natural label.

**Fix:**

```html
<div class="slide-panel" [class.open]="isOpen" role="dialog" aria-modal="true"
     aria-labelledby="panel-job-type-label">
```

And add `id="panel-job-type-label"` to the job-type chip element.

---

_Reviewed: 2026-05-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
