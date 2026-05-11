---
phase: 19-superadmin-monitoring-ui
plan: "04"
subsystem: frontend-routing
tags: [angular, routing, navigation, superadmin, job-monitor]
dependency_graph:
  requires: []
  provides:
    - /configuration/jobs route guarded by IsSuperAdminGuard
    - Job Monitor sidebar nav item (superadmin only)
  affects:
    - frontend/src/app/features/configuration/configuration.routes.ts
    - frontend/src/app/features/configuration/configuration-shell.component.ts
tech_stack:
  added: []
  patterns:
    - Angular lazy loadComponent route
    - canActivate guard on child route
    - Conditional navItems push in ngOnInit subscriber
key_files:
  modified:
    - frontend/src/app/features/configuration/configuration.routes.ts
    - frontend/src/app/features/configuration/configuration-shell.component.ts
decisions:
  - IsSuperAdminGuard reused from existing admin route — no new imports required
  - icon value 'activity' (without bi- prefix) to match template convention 'bi-' + item.icon
metrics:
  duration: "< 5 minutes"
  completed: "2026-05-11T21:11:54Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 19 Plan 04: Route + Nav Wiring for Job Monitor Summary

## One-liner

Added `/configuration/jobs` child route with `IsSuperAdminGuard` and "Job Monitor" sidebar nav item visible only to superadmin users.

## What Was Built

Two minimal, targeted additions to wire the Job Monitor page into the Angular app shell before Plan 05 creates the actual component.

**Task 1 — /jobs route in configuration.routes.ts (commit c01368c):**
- Added 5-line child route object after the existing `admin` route
- `canActivate: [IsSuperAdminGuard]` — consistent with admin route guard pattern
- Lazy `loadComponent` pointing to `./pages/job-monitor/job-monitor.component` (component created by Plan 05)

**Task 2 — Job Monitor nav item in configuration-shell.component.ts (commit f7b03ae):**
- Added single `this.navItems.push(...)` inside existing `is_superuser` block
- `{ path: 'jobs', label: 'Job Monitor', icon: 'activity' }` — icon without `bi-` prefix per template convention
- Superadmin sees: Organization & Users, Metadata Fields, Platform Connections, Brainsuite Apps, Admin, Job Monitor

## Threat Model Coverage

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-19-04-01 | `IsSuperAdminGuard` on the `/jobs` route — client-side gate; backend enforces independently |
| T-19-04-02 | Nav item push is inside `if (user?.is_superuser)` — non-superusers never see "Job Monitor" |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `frontend/src/app/features/configuration/configuration.routes.ts` — modified, committed c01368c
- [x] `frontend/src/app/features/configuration/configuration-shell.component.ts` — modified, committed f7b03ae
- [x] `path: 'jobs'` present in routes.ts
- [x] `canActivate: [IsSuperAdminGuard]` appears twice (admin + jobs)
- [x] `Job Monitor` present in shell component
- [x] `icon: 'activity'` (no bi- prefix)
- [x] All existing routes and nav items unchanged

## Self-Check: PASSED
