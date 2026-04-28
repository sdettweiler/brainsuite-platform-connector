---
phase: 14-youtube-cookies-admin-ui
plan: "03"
subsystem: frontend-admin-ui
tags: [angular, superadmin, route-guard, admin-ui, notifications, youtube-cookies]
dependency_graph:
  requires: [14-01]
  provides: [AdminComponent, IsSuperAdminGuard, admin route, COOKIE_FAILED notification routing]
  affects:
    - frontend/src/app/core/services/auth.service.ts
    - frontend/src/app/core/guards/is-superadmin.guard.ts
    - frontend/src/app/features/configuration/configuration-shell.component.ts
    - frontend/src/app/features/configuration/configuration.routes.ts
    - frontend/src/app/features/configuration/pages/admin.component.ts
    - frontend/src/app/core/layout/header/header.component.ts
tech_stack:
  added: []
  patterns: [standalone Angular component with inline template, route guard CanActivate pattern, cookie slot state machine (masked/replace/missing)]
key_files:
  created:
    - frontend/src/app/core/guards/is-superadmin.guard.ts
    - frontend/src/app/features/configuration/pages/admin.component.ts
  modified:
    - frontend/src/app/core/services/auth.service.ts
    - frontend/src/app/features/configuration/configuration-shell.component.ts
    - frontend/src/app/features/configuration/configuration.routes.ts
    - frontend/src/app/core/layout/header/header.component.ts
decisions:
  - "Admin nav item computed once in ngOnInit (not reactive to authService.currentUser$ changes) — sufficient since user cannot change is_superuser within a session"
  - "IsSuperAdminGuard uses synchronous canActivate (not CanActivateFn) matching existing auth.guard.ts functional pattern divergence intentionally — class-based for consistency with plan spec"
  - "Cookie slot state machine uses three mutually exclusive *ngIf blocks per slot (missing/masked/editing) rather than switch-case for readability"
metrics:
  duration_minutes: 10
  completed_date: "2026-04-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 4
---

# Phase 14 Plan 03: Angular Admin UI Summary

**One-liner:** Angular AdminComponent with three sections (YouTube Cookies health/replace, SuperAdmin Management, Organization List), IsSuperAdminGuard route protection, conditional sidebar nav, and COOKIE_FAILED bell notification routing to /configuration/admin.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Auth model extension + route guard + shell nav + routes | c8659f0 | auth.service.ts, is-superadmin.guard.ts (new), configuration-shell.component.ts, configuration.routes.ts |
| 2 | AdminComponent with three sections + notification routing | e3f6a47 | admin.component.ts (new), header.component.ts |

## What Was Built

### CurrentUser Interface Extension (auth.service.ts)
- Added `is_superuser?: boolean` to `CurrentUser` interface
- Backend `/users/me` already returns this field from Plan 14-01 UserResponse schema change — no additional endpoint changes needed

### IsSuperAdminGuard (frontend/src/app/core/guards/is-superadmin.guard.ts)
- Class-based `CanActivate` guard checking `authService.currentUser?.is_superuser`
- Redirects to `/` (home) on failure
- Injectable with `providedIn: 'root'` — no module registration needed

### Configuration Shell Nav Gating (configuration-shell.component.ts)
- Added `AuthService` injection and `OnInit` implementation
- `ngOnInit` builds `navItems` from `baseNavItems`, then conditionally appends `{ path: 'admin', label: 'Admin', icon: 'shield-lock' }` when `is_superuser` is true
- Existing four nav items (organization, metadata, platforms, brainsuite-apps) unchanged

### Admin Route (configuration.routes.ts)
- Added `/admin` child route under the configuration shell
- `canActivate: [IsSuperAdminGuard]` prevents direct URL access by non-SuperAdmins
- Lazy-loaded: `loadComponent: () => import('./pages/admin.component').then(m => m.AdminComponent)`

### AdminComponent (frontend/src/app/features/configuration/pages/admin.component.ts)
Three sections following 14-UI-SPEC.md design contract:

**Section 1 — YouTube Cookies:**
- Loads GET `/super-admin/youtube-cookies` on init to get `{ primary: { status }, backup: { status } }` health response
- Each slot has three states: MISSING (Add Cookie button), masked display (Replace button), editing (textarea + Save/Discard)
- Skeleton loading block during fetch; error message on failure
- PUT `/super-admin/youtube-cookies` with `{ primary?: string }` or `{ backup?: string }` payload; updates health display on success
- `discardEdit(slot)` resets textarea content and closes edit mode

**Section 2 — SuperAdmin Management:**
- Loads GET `/super-admin/users` on init; shows table with email, name, joined date
- Promote input: email text field + "Promote to SuperAdmin" button
- POST `/super-admin/users/promote` with `{ email }` body
- Error handling for `"User not found"` (→ "No user found with that email address.") and `"User is already a SuperAdmin"` (→ "This user is already a SuperAdmin.") detail strings

**Section 3 — Organizations (read-only):**
- Loads GET `/super-admin/organizations` on init
- Table: name, slug (monospace code), user count (right-aligned), created date

### COOKIE_FAILED Notification Routing (header.component.ts)
Five changes:
1. `loadUnreadCount` highPriority filter: added `'COOKIE_FAILED'` to the type array → triggers toast popup
2. `showToastForNotification` actionLabel: `COOKIE_FAILED` now shows "Fix Now" (same as TOKEN_EXPIRED)
3. `showToastForNotification` action handler: added `else if (n.type === 'COOKIE_FAILED')` → `router.navigate(['/configuration/admin'])`
4. `getNotifIcon`: added `case 'COOKIE_FAILED': return 'bi-key'`
5. `getNotifIconClass`: added `case 'COOKIE_FAILED': return 'icon-rejected'`
6. `markRead`: added `if (n.type === 'COOKIE_FAILED')` → `router.navigate(['/configuration/admin'])`

## Decisions Made

1. **ngOnInit nav computation (not reactive):** The Admin nav item is computed once when the shell loads. Since `is_superuser` cannot change during a session (user would need to log out and back in), a one-time check in `ngOnInit` is sufficient and avoids subscription management overhead.
2. **Class-based guard over functional:** The plan spec uses `CanActivate` class pattern. The existing `auth.guard.ts` uses the functional `CanActivateFn` style. Class-based was chosen to match the plan spec exactly.
3. **Cookie state machine with *ngIf blocks:** Three separate `*ngIf` conditional blocks per slot (missing / masked / editing) rather than a single switch expression — improves template readability and matches the UI-SPEC state diagram.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All three API endpoints (youtube-cookies, users, organizations) are called with real HTTP calls. The UI renders actual API data. No hardcoded placeholder values flow to the rendered output.

## Threat Surface Scan

No new trust boundaries beyond those documented in the plan's threat model:
- T-14-11: IsSuperAdminGuard implemented — client-side gate only (server-side 403 is the real enforcement, per plan)
- T-14-12: Cookie content never sent to frontend — GET returns health status only; masked display uses hardcoded bullet characters
- T-14-13: `is_superuser` read from `/users/me` API response via `loadCurrentUser()`, not from JWT decode on client

## Self-Check: PASSED

- [x] frontend/src/app/core/guards/is-superadmin.guard.ts exists
- [x] frontend/src/app/features/configuration/pages/admin.component.ts exists
- [x] auth.service.ts contains `is_superuser?: boolean`
- [x] configuration-shell.component.ts pushes Admin nav item conditionally
- [x] configuration.routes.ts contains admin route with IsSuperAdminGuard
- [x] header.component.ts contains COOKIE_FAILED in markRead, showToast, getNotifIcon, getNotifIconClass, highPriority filter
- [x] Commit c8659f0 exists (Task 1)
- [x] Commit e3f6a47 exists (Task 2)
