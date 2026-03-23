---
phase: 02-security-hardening
verified: 2026-03-23T12:00:00Z
status: passed
score: 10/10 requirements verified
re_verification: false
human_verification:
  - test: "Login flow with real browser — confirm Set-Cookie header arrives with httpOnly flag"
    expected: "Browser devtools > Application > Cookies shows refresh_token with HttpOnly checked"
    why_human: "Cookie flags cannot be inspected programmatically from test client; only real browser renders Set-Cookie flags visibly"
  - test: "Page refresh on a protected route when a valid httpOnly cookie exists"
    expected: "User stays on the protected route without being sent to /auth/login — APP_INITIALIZER silent refresh succeeded"
    why_human: "Auth guard + APP_INITIALIZER behaviour requires a running Angular app in a browser with a real HTTP cookie jar"
---

# Phase 2: Security Hardening Verification Report

**Phase Goal:** Harden the platform connector against the six identified security vulnerabilities and four code quality issues found during Phase 1 audit. All backend and frontend changes must be covered by automated tests so regressions are caught in CI.
**Verified:** 2026-03-23
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | OAuth sessions stored in Redis with TTL, not in-memory dict | VERIFIED | `_oauth_sessions` dict gone from platforms.py; `get_redis()` + `OAUTH_SESSION_TTL=900` + `oauth_session:{id}` key pattern confirmed at lines 30, 35, 201-439 |
| 2  | App refuses to start if TOKEN_ENCRYPTION_KEY is missing or invalid | VERIFIED | `config.py` line 61: `TOKEN_ENCRYPTION_KEY: str` (required); `field_validator` at line 63 raises ValueError on empty or non-Fernet key |
| 3  | Refresh token delivered via httpOnly cookie, not JSON body | VERIFIED | `auth.py` lines 203-213: `response.set_cookie(httponly=True, samesite="lax", path="/api/v1/auth")`; `TokenResponse` schema has no `refresh_token` field |
| 4  | `/auth/refresh` reads from cookie only, rejects body token | VERIFIED | `auth.py` line 219: `Cookie(default=None)` parameter; endpoint raises 401 when cookie absent |
| 5  | Path traversal on asset endpoint blocked | VERIFIED | `main.py` lines 136-140: `PurePosixPath` check on both raw and URL-decoded `object_path`; raises `HTTPException(400, "Invalid asset path")` |
| 6  | OAuth redirect URI ignores x-forwarded-host | VERIFIED | `config.py` lines 91-107: `get_redirect_uri_from_request` uses `urlparse(settings.BASE_URL)` only; comment explicitly documents the removed header-injection attack |
| 7  | CORS origins documented with no-wildcard warning | VERIFIED | `.env.example` line 21-22: `BACKEND_CORS_ORIGINS=["http://localhost:4200","http://localhost:3000"]` with "Never use ["*"] in production" comment |
| 8  | No broad `except Exception` outside allowed list | VERIFIED | `test_exception_audit.py` AST scanner passes (part of 38-test green suite); grep of `backend/app/` confirms zero violations outside `main.py`, `base.py`, and allowed `scheduler.py` functions |
| 9  | Frontend API response types use named interfaces, not `any` | VERIFIED | Zero `Observable<any>` / `http.get<any>` in all 4 target files; `RegisterResponse`, `OAuthSessionResponse`, `DashboardAssetsResponse`, `StatsResponse`, `AssetDetailResponse` interfaces confirmed |
| 10 | All tests green; regressions caught in CI | VERIFIED | `38 passed, 1 skipped` — 1 skip is an intentional stub (`test_platforms_uses_redis_not_dict`) that is functionally superseded by the 4 passing OAuth session tests |

**Score:** 10/10 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/tests/conftest.py` | Shared pytest fixtures | VERIFIED | Contains `async_client`, `mock_redis`, `mock_settings` fixtures |
| `backend/tests/test_oauth_session.py` | SEC-01 Redis session tests | VERIFIED | 4 tests pass; 1 legacy stub skipped (non-blocking) |
| `backend/tests/test_auth_cookie.py` | SEC-02 cookie tests | VERIFIED | 5 tests pass, zero skips |
| `backend/tests/test_startup_validation.py` | SEC-03 Fernet validation tests | VERIFIED | 3 tests pass, zero skips |
| `backend/tests/test_path_traversal.py` | SEC-04 path traversal tests | VERIFIED | 3 tests pass, zero skips |
| `backend/tests/test_redirect_uri.py` | SEC-05 redirect URI tests | VERIFIED | 2 tests pass, zero skips |
| `backend/tests/test_error_shapes.py` | QUAL-03 error shape tests | VERIFIED | 3 tests pass, zero skips |
| `backend/tests/test_exception_audit.py` | QUAL-01 AST audit test | VERIFIED | 1 test passes; uses function-name allowlist for scheduler.py intentional broad catches |
| `backend/app/core/config.py` | Fernet validation + redirect URI hardening | VERIFIED | `field_validator("TOKEN_ENCRYPTION_KEY")` present; `get_redirect_uri_from_request` uses `settings.BASE_URL` only |
| `backend/app/core/security.py` | Fernet silent fallback removed | VERIFIED | Module-level `fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())` — no `except Exception` fallback present |
| `backend/app/core/redis.py` | Async Redis singleton | VERIFIED | `get_redis()` with `settings.REDIS_URL` and `decode_responses=True` |
| `backend/app/api/v1/endpoints/platforms.py` | Redis OAuth sessions | VERIFIED | Zero `_oauth_sessions` dict references; full Redis setex/get/delete lifecycle with `OAUTH_SESSION_TTL=900` |
| `backend/app/api/v1/endpoints/auth.py` | httpOnly cookie auth endpoints | VERIFIED | Login/refresh/logout all use `response.set_cookie` / `Cookie(default=None)` / `delete_cookie` |
| `backend/app/schemas/user.py` | TokenResponse without refresh_token | VERIFIED | `TokenResponse` has only `access_token` + `token_type`; `RefreshRequest` schema retained but unused in endpoint signatures (dead import — minor smell, not a security gap) |
| `backend/.env.example` | CORS documentation | VERIFIED | Key present with no-wildcard production comment |
| `frontend/src/app/core/services/auth.service.ts` | In-memory BehaviorSubject, no localStorage | VERIFIED | `BehaviorSubject<string \| null>(null)` at line 41; zero `localStorage` references; `withCredentials: true` on all 3 auth calls |
| `frontend/src/app/core/store/auth/auth.reducer.ts` | No localStorage hydration | VERIFIED | `accessToken: null` initial state; no localStorage references |
| `frontend/src/app/core/store/auth/auth.effects.ts` | No localStorage persistence | VERIFIED | Zero localStorage references |
| `frontend/src/app/core/store/auth/auth.actions.ts` | No refreshToken in action props | VERIFIED | Zero `refreshToken` references in action definitions |
| `frontend/src/app/core/guards/auth.guard.ts` | Silent refresh on page load | VERIFIED | `auth.refreshTokens()` with `catchError(() => router.createUrlTree(['/auth/login']))` |
| `frontend/src/app/features/configuration/pages/platforms.component.ts` | OAuthSessionResponse interface | VERIFIED | `interface OAuthSessionResponse` at line 27; HTTP calls typed |
| `frontend/src/app/features/dashboard/dashboard.component.ts` | DashboardAssetsResponse/StatsResponse | VERIFIED | Both interfaces present at lines 48, 56; `http.get<T>` calls typed |
| `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` | AssetDetailResponse interface | VERIFIED | Interface at line 90; used in `api.get<AssetDetailResponse>` at line 491 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `config.py field_validator` | `security.py Fernet init` | TOKEN_ENCRYPTION_KEY validated before module uses it | VERIFIED | `security.py` module-level `Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())` — validation at config load means invalid key never reaches security module |
| `main.py serve_object` | Path validation | `PurePosixPath` + `".." in parts` check | VERIFIED | Both raw and URL-decoded paths checked before use |
| `platforms.py` | `redis.py get_redis()` | `from app.core.redis import get_redis` + session operations | VERIFIED | Import confirmed; setex/get/delete operations on `oauth_session:{id}` key throughout file |
| `redis.py` | `config.py settings.REDIS_URL` | `aioredis.from_url(settings.REDIS_URL)` | VERIFIED | Pattern confirmed in redis.py |
| `auth.py login` | httpOnly cookie | `response.set_cookie(httponly=True)` | VERIFIED | Cookie set on login (line 203) and refresh (line 262); deleted on logout (line 294) |
| `auth.py refresh` | Cookie parameter | `Cookie(default=None)` | VERIFIED | Lines 219, 278 — body token rejected; 401 on missing cookie |
| `auth.service.ts refreshTokens()` | `/api/v1/auth/refresh` | `http.post` with `withCredentials: true` | VERIFIED | Line 78 in auth.service.ts |
| `auth.guard.ts` | `auth.service.ts refreshTokens()` | Call on guard activation before redirect | VERIFIED | Line 16 in auth.guard.ts |
| `test_exception_audit.py` | All `backend/app/*.py` files | `ast.parse` + ExceptHandler scan with function-name allowlist | VERIFIED | Test uses `pathlib.Path(__file__).parent.parent / "app"` to scan all files |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SEC-01 | 02-02 | OAuth session state in Redis with TTL | SATISFIED | `_oauth_sessions` dict removed; Redis setex/900s TTL + explicit delete after account connection |
| SEC-02 | 02-03, 02-04 | Refresh token in httpOnly cookie; access token in memory | SATISFIED | Backend: `set_cookie(httponly=True)` + `Cookie(default=None)`. Frontend: `BehaviorSubject`, no localStorage, `withCredentials: true` |
| SEC-03 | 02-01 | Fernet key startup validation | SATISFIED | `field_validator("TOKEN_ENCRYPTION_KEY")` raises ValidationError on missing/invalid key |
| SEC-04 | 02-01 | Path traversal prevention on asset endpoint | SATISFIED | `PurePosixPath` double-check (raw + URL-decoded) in `serve_object` |
| SEC-05 | 02-01 | OAuth redirect URI uses BASE_URL only | SATISFIED | `x-forwarded-host` branch removed; only `urlparse(settings.BASE_URL)` used |
| SEC-06 | 02-01 | CORS origins documented with no-wildcard warning | SATISFIED | `.env.example` has key + production warning comment |
| QUAL-01 | 02-05 | Broad `except Exception` replaced with specific types | SATISFIED | AST audit test green; grep confirms zero violations outside allowed files/functions |
| QUAL-02 | 02-06 | Frontend `any` types eliminated for API response DTOs | SATISFIED | TypeScript compiles clean; zero `<any>` on HTTP response calls in 4 target files |
| QUAL-03 | 02-06 | Consistent error response structure + 204 on DELETE/logout | SATISFIED | DELETE `/apps/{app_id}` returns 204; `/auth/logout` returns 204; error shape tests green |
| QUAL-04 | 02-01, 02-02, 02-03, 02-04 | Fernet fallback, OAuth cleanup, token refresh bugs fixed | SATISFIED | Fernet fallback removed from security.py; `redis.delete()` after session use (line 439); auth guard silent refresh; APP_INITIALIZER added |

All 10 requirements satisfied. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/schemas/user.py` | 87-88 | `RefreshRequest` class retained; imported but unused in `auth.py` | Info | Dead code, not a security issue. Refresh endpoint uses `Cookie(default=None)` — the class cannot be used to bypass the cookie requirement. No test impact. |
| `backend/tests/test_oauth_session.py` | 161 | `test_platforms_uses_redis_not_dict` still marked `pytest.mark.skip` | Info | Was pre-written for plan 02-02 but the 4 functional Redis tests already verify the same property. The skip note says "stub - implementation in plan 02-02" — the implementation happened but this convenience test was not unskipped. Does not affect CI coverage. |

No blocker or warning-level anti-patterns found.

---

### Human Verification Required

#### 1. httpOnly Cookie Flag in Browser

**Test:** Log in via the Angular frontend in a real browser (Chrome/Firefox). Open DevTools > Application > Cookies > `localhost`.
**Expected:** A cookie named `refresh_token` exists, with the `HttpOnly` column checked and `Path` set to `/api/v1/auth`.
**Why human:** Test client (`httpx.AsyncClient`) in pytest confirms `set-cookie` header is present, but the HttpOnly attribute rendering in actual browser storage requires manual inspection.

#### 2. Silent Refresh on Page Reload

**Test:** Log in, then hard-reload the page (Cmd+Shift+R / Ctrl+Shift+R) while on a protected route (e.g., `/dashboard`).
**Expected:** User remains on `/dashboard` — APP_INITIALIZER fires `refreshTokens()` which succeeds via the httpOnly cookie, restoring the in-memory access token before the auth guard runs.
**Why human:** Requires a running Angular + FastAPI stack with a live database and Redis instance; the httpOnly cookie must survive the page reload in a real browser cookie jar.

---

### Minor Issues (Non-blocking)

1. **Dead import in auth.py**: `RefreshRequest` is imported from schemas but never used in any endpoint signature after SEC-02 implementation. The refresh endpoint correctly uses `Cookie(default=None)`. Safe to remove in a future cleanup pass.

2. **Skipped stub in test_oauth_session.py**: `test_platforms_uses_redis_not_dict` (line 161) remains skipped. The plan summary notes this was "prematurely written" before Redis migration was complete and the 4 functional OAuth session tests provide stronger coverage of the same invariant.

---

## Summary

All 10 security and quality requirements (SEC-01 through SEC-06, QUAL-01 through QUAL-04) are implemented and verified. The backend test suite runs 38 tests green with 1 intentional skip. Frontend TypeScript compiles without errors. All key security links — Fernet validation chain, Redis session lifecycle, httpOnly cookie delivery, path traversal guard, redirect URI hardening, and exception specificity enforcement — are substantively wired and not stubs.

The phase goal is **achieved**.

---

_Verified: 2026-03-23_
_Verifier: Claude (gsd-verifier)_
