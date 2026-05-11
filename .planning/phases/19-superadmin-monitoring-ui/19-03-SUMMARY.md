---
phase: 19-superadmin-monitoring-ui
plan: "03"
subsystem: frontend-service
tags: [angular, sse, eventsource, ngrx-zone, job-monitoring, rxjs]
dependency_graph:
  requires:
    - "Phase 18 SSE endpoint (/api/v1/jobs/stream)"
    - "frontend/src/app/core/services/auth.service.ts (getAccessToken)"
    - "frontend/src/app/core/services/api.service.ts (get, delete)"
  provides:
    - "JobMonitorService — shared SSE state layer for Plans 05 and 06"
    - "SseStatus type: live | reconnecting | disconnected"
    - "JobSnapshot interface matching Phase 18 D-06 SSE payload"
  affects:
    - "frontend/src/app/features/configuration/pages/job-monitor/ (Plans 05, 06)"
tech_stack:
  added: []
  patterns:
    - "NgZone.run() wrapping for EventSource callbacks (OnPush change detection)"
    - "BehaviorSubject pair: jobs$ + connectionStatus$"
    - "In-memory Map keyed by job_id for O(1) upserts"
    - "3-attempt threshold for disconnected state"
key_files:
  created:
    - frontend/src/app/core/services/job-monitor.service.ts
  modified: []
decisions:
  - "Inject AuthService.getAccessToken() instead of localStorage — AuthService stores token in-memory only (no localStorage key)"
  - "Use path-embedded query params for REST helpers — ApiService.delete() does not accept HttpParams"
  - "clearJobMap() provided to prevent unbounded growth (T-19-03-03 mitigation)"
metrics:
  duration: "< 5 minutes"
  completed: "2026-05-11T21:12:09Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 19 Plan 03: JobMonitorService Summary

**One-liner:** Angular SSE service connecting to `/api/v1/jobs/stream?token=` with NgZone-wrapped EventSource, in-memory job Map, reactive observables, and REST helpers for job list/detail/delete.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create JobMonitorService with SSE connection lifecycle and REST helpers | 2044e1f | frontend/src/app/core/services/job-monitor.service.ts |

## What Was Built

`JobMonitorService` is an Angular injectable service (provided in root) that:

1. **SSE connection lifecycle** — `connect()` builds the URL `/api/v1/jobs/stream?token=<jwt>` using `AuthService.getAccessToken()`, creates an `EventSource`, and registers three callbacks all wrapped in `NgZone.run()`:
   - `job_update` custom event: parses JSON, upserts into `jobMap`, emits updated array
   - `onopen`: resets `reconnectAttempts` to 0, emits `'live'`
   - `onerror`: increments `reconnectAttempts`, emits `'reconnecting'` (< 3) or `'disconnected'` (>= 3)

2. **In-memory store** — `Map<string, JobSnapshot>` keyed by `job_id` for O(1) upserts; `BehaviorSubject<JobSnapshot[]>` exposes `jobs$`

3. **Connection status** — `BehaviorSubject<SseStatus>` exposes `connectionStatus$` with three states: `live`, `reconnecting`, `disconnected`

4. **REST helpers** — `getJobs()`, `getJobDetail()`, `clearJobs()` using `ApiService.get<T>()` / `ApiService.delete<T>()`

5. **Lifecycle** — `disconnect()` closes EventSource, `clearJobMap()` resets Map + emits empty, `ngOnDestroy()` calls `disconnect()`

## Acceptance Criteria Results

| Check | Result |
|-------|--------|
| `grep -c "class JobMonitorService"` | 1 |
| `grep -c "ngZone.run"` | 3 (one per EventSource callback) |
| URL contains `?token=` | Yes — `/api/v1/jobs/stream?token=${token}` |
| `getAccessToken()` usage | Yes — `this.authService.getAccessToken()` |
| `reconnectAttempts >= 3` gate | Yes |
| connect/disconnect/clearJobMap exist | Yes (all 3) |
| getJobs/getJobDetail/clearJobs exist | Yes (all 3) |
| TypeScript compilation errors | None |

## Deviations from Plan

None — plan executed exactly as written. The PATTERNS.md implementation was used as the authoritative base, with the REST helpers from the task action added on top.

## Threat Surface Scan

No new network endpoints introduced in this plan (frontend service only). The service connects to the existing Phase 18 SSE endpoint. No new trust boundaries created beyond those in the plan's threat model.

## Known Stubs

None — this service contains no hardcoded empty values or placeholder data. REST helpers delegate to ApiService with real paths.

## Self-Check

- [x] `frontend/src/app/core/services/job-monitor.service.ts` exists
- [x] Commit `2044e1f` exists (`feat(19-03): create JobMonitorService with SSE lifecycle and REST helpers`)
- [x] TypeScript compilation clean for this file
- [x] All 3 NgZone.run() wrappings present

## Self-Check: PASSED
