---
phase: 02-security-hardening
plan: 04
subsystem: auth
tags: [angular, ngrx, jwt, httponly-cookie, behaviorsubject, token-refresh, interceptor]

# Dependency graph
requires:
  - phase: 02-security-hardening plan 03
    provides: Backend httpOnly cookie Set-Cookie on login/refresh, refresh_token removed from TokenResponse body

provides:
  - In-memory access token storage via BehaviorSubject<string|null> (no localStorage)
  - Silent token refresh on page load via auth guard and APP_INITIALIZER
  - Cookie-based 401 retry in auth interceptor via AuthService.refreshTokens()
  - NgRx auth state without localStorage hydration

affects: [03-brainsuite-integration, 04-dashboard-reliability]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Access token stored in BehaviorSubject (memory only), never localStorage"
    - "Silent refresh via httpOnly cookie: withCredentials: true on all auth calls"
    - "Auth guard attempts refreshTokens() before redirecting to /auth/login"
    - "APP_INITIALIZER attempts silent refresh on app startup for better UX"

key-files:
  created: []
  modified:
    - frontend/src/app/core/services/auth.service.ts
    - frontend/src/app/core/store/auth/auth.actions.ts
    - frontend/src/app/core/store/auth/auth.effects.ts
    - frontend/src/app/core/store/auth/auth.reducer.ts
    - frontend/src/app/core/guards/auth.guard.ts
    - frontend/src/app/core/interceptors/auth.interceptor.ts
    - frontend/src/app/app.config.ts

key-decisions:
  - "APP_INITIALIZER added to attempt silent refresh on app startup — prevents flash of login page when user refreshes browser with valid httpOnly cookie"
  - "auth.effects.ts logout$ effect retains router navigation — AuthService already clears in-memory token, effect handles redirect"
  - "localStorage references in theme.service.ts are intentional (UI preferences, not tokens) — left untouched"

patterns-established:
  - "Angular auth: BehaviorSubject<string|null> as single source of truth for access token"
  - "All /auth/login, /auth/refresh, /auth/logout calls use withCredentials: true"
  - "Auth guard pattern: check isAuthenticated -> attempt refreshTokens() -> catchError -> redirect"

requirements-completed: [SEC-02, QUAL-04]

# Metrics
duration: 15min
completed: 2026-03-23
---

# Phase 02 Plan 04: Frontend In-Memory Auth + Cookie Refresh Summary

**Angular auth migrated from localStorage to in-memory BehaviorSubject with httpOnly cookie refresh, guard silent-refresh, and APP_INITIALIZER session recovery**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-23T08:34:05Z
- **Completed:** 2026-03-23T08:49:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Removed all localStorage token persistence from NgRx auth store (effects, reducer, actions)
- Access token now lives exclusively in AuthService BehaviorSubject — never touches disk
- Auth guard attempts silent httpOnly cookie refresh before redirecting to login (QUAL-04 fix)
- APP_INITIALIZER pre-warms access token on app startup for seamless page reload UX
- TypeScript compiles cleanly with zero errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite auth store for in-memory access token + cookie refresh** - `82c56d1` (feat)
2. **Task 2: Harden auth guard with silent refresh and add APP_INITIALIZER** - `6f83cdd` (feat)

**Plan metadata:** (see final docs commit)

## Files Created/Modified
- `frontend/src/app/core/services/auth.service.ts` - Already correct from prior work; BehaviorSubject, withCredentials on all three auth calls
- `frontend/src/app/core/store/auth/auth.actions.ts` - Already correct; no refreshToken in action props
- `frontend/src/app/core/store/auth/auth.effects.ts` - Removed persistLogin$, persistRefresh$ effects and all localStorage calls; kept redirect-only logout$
- `frontend/src/app/core/store/auth/auth.reducer.ts` - Removed refreshToken from AuthState, removed localStorage.getItem() from initialState
- `frontend/src/app/core/guards/auth.guard.ts` - Added silent refreshTokens() call with catchError redirect (QUAL-04 fix)
- `frontend/src/app/core/interceptors/auth.interceptor.ts` - Already correct; no changes needed
- `frontend/src/app/app.config.ts` - Added APP_INITIALIZER to pre-warm access token on startup

## Decisions Made
- APP_INITIALIZER added for better UX: without it the guard handles recovery but the user briefly sees the login page before being redirected back. The initializer silently refreshes before routing starts.
- auth.effects.ts logout$ effect kept with only router navigation since AuthService.logout() already clears the BehaviorSubject and calls logout backend endpoint.
- theme.service.ts localStorage references are intentional (UI theme preference, not security tokens) and were left untouched per scope boundary rules.

## Deviations from Plan

None - plan executed exactly as written. auth.service.ts and auth.actions.ts were already in the correct state from prior work; the plan accounted for this possibility. APP_INITIALIZER was described as "optional but provides better UX" in the plan and was implemented as it was straightforward with the standalone app config.

## Issues Encountered
- npm dependencies were not installed in the frontend directory. Ran `npm install` before TypeScript compilation check. No code changes required.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full SEC-02 implementation complete: backend sets httpOnly cookie (Plan 03), frontend uses it (Plan 04)
- QUAL-04 silent refresh bug fixed — auth guard now recovers sessions on page reload
- Auth layer is ready for Phase 03 BrainSuite integration (authenticated API calls will use access token from memory)

---
*Phase: 02-security-hardening*
*Completed: 2026-03-23*
