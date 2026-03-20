---
phase: 02-security-hardening
plan: 03
subsystem: auth
tags: [jwt, refresh-token, httponly-cookie, fastapi, security, xss-prevention]

# Dependency graph
requires:
  - phase: 01-infra-portability
    provides: Working FastAPI backend with JWT auth endpoints

provides:
  - Cookie-based refresh token delivery (httpOnly, SameSite=lax, path-scoped)
  - Refresh endpoint reads from Cookie parameter only
  - Token rotation on each refresh call
  - Logout returns 204 and clears cookie via delete_cookie()
  - TokenResponse schema with no refresh_token field

affects:
  - 02-04-frontend-cookie (frontend must send credentials:include and remove manual refresh_token handling)
  - Any plan that calls /auth/login, /auth/refresh, or /auth/logout

# Tech tracking
tech-stack:
  added: []
  patterns:
    - httpOnly cookie delivery via FastAPI Response.set_cookie() injection
    - Cookie(default=None) FastAPI parameter for reading cookies
    - TDD with unittest.mock for async FastAPI endpoint testing (no DB required)

key-files:
  created:
    - backend/tests/test_auth_cookie.py
  modified:
    - backend/app/api/v1/endpoints/auth.py
    - backend/app/schemas/user.py

key-decisions:
  - "Refresh token removed from TokenResponse Pydantic schema — body never exposes it"
  - "Cookie path=/api/v1/auth limits scope to auth endpoints only, reducing attack surface"
  - "secure=not settings.DEBUG allows HTTP in local dev, enforces HTTPS in prod"
  - "logout uses response.delete_cookie() (not return Response(204)) so FastAPI merges the set-cookie header into the 204 response"
  - "Rotation test mocks create_refresh_token to guarantee distinct token value regardless of test execution speed"

patterns-established:
  - "FastAPI cookie injection: add Response parameter + call response.set_cookie() before returning JSON"
  - "TDD RED with stub skips, GREEN with mocked DB via dependency_overrides + unittest.mock"

requirements-completed: [SEC-02]

# Metrics
duration: 18min
completed: 2026-03-20
---

# Phase 02 Plan 03: httpOnly Cookie Refresh Token Summary

**Refresh token moved from JSON response body to httpOnly cookie using FastAPI Response injection; login/refresh/logout all updated; 5 TDD tests green**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-03-20T17:55:00Z
- **Completed:** 2026-03-20T18:13:50Z
- **Tasks:** 1 (TDD: RED commit + GREEN commit)
- **Files modified:** 3

## Accomplishments

- Login endpoint sets `refresh_token` httpOnly, SameSite=lax cookie scoped to `/api/v1/auth`; JSON body no longer includes `refresh_token`
- Refresh endpoint reads token exclusively from `Cookie(default=None)` parameter; returns 401 "No refresh token" when no cookie present
- Each refresh rotates the cookie (new token value stored in DB, old record revoked)
- Logout reads from cookie, revokes DB record, calls `response.delete_cookie()`, returns 204 No Content
- `TokenResponse` schema stripped of `refresh_token` field
- `main.py` already had `allow_credentials=True` on CORSMiddleware — no change needed
- 5 tests passing with zero `pytest.mark.skip` decorators

## Task Commits

1. **TDD RED: test_auth_cookie.py (failing tests)** - `bfe6fa9` (test)
2. **TDD GREEN: auth.py + user.py implementation** - `0a599fc` (feat)

## Files Created/Modified

- `backend/tests/test_auth_cookie.py` - 5 tests covering login cookie, refresh from cookie, reject body token, logout clears cookie, rotation
- `backend/app/api/v1/endpoints/auth.py` - Login/refresh/logout endpoints rewritten for cookie-based flow
- `backend/app/schemas/user.py` - `TokenResponse.refresh_token` field removed

## Decisions Made

- `secure=not settings.DEBUG` — allows HTTP in local dev (DEBUG=True), enforces HTTPS-only cookie in production
- `path="/api/v1/auth"` — limits cookie scope to auth endpoints only (not sent with ad data API calls)
- `response.delete_cookie()` without a separate `return Response(204)` — returning a new Response object would bypass FastAPI's header merging, dropping the set-cookie header
- Token rotation test uses `patch("app.api.v1.endpoints.auth.create_refresh_token")` to guarantee a distinct return value even when two JWTs are created within the same second

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- **Token rotation test timing**: JWT `exp` is second-precision; two tokens created within the same second have identical values, causing the rotation assertion to fail. Fixed by patching `create_refresh_token` in the auth module to return a known distinct value. This tests the correct behavior (cookie value is whatever `create_refresh_token` returns) without depending on wall-clock timing.
- **Response object conflict**: Initial implementation used `return Response(status_code=204)` inside the logout handler, which created a new Response object that did not carry the `delete_cookie()` call from the injected `response` parameter. Fixed by removing the explicit return — FastAPI uses the decorator's `status_code=204` and merges headers from the injected `response`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Backend is ready: `/auth/login`, `/auth/refresh`, `/auth/logout` all speak cookies
- **Plan 02-04 (frontend):** Angular auth service must be updated to:
  - Remove manual `refresh_token` storage from localStorage/sessionStorage
  - Add `withCredentials: true` to Angular HttpClient calls to auth endpoints so cookies are sent automatically
  - Remove any code that reads `refresh_token` from the login response body

---
*Phase: 02-security-hardening*
*Completed: 2026-03-20*
