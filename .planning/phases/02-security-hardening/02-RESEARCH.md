# Phase 2: Security Hardening - Research

**Researched:** 2026-03-20
**Domain:** FastAPI security hardening, Angular JWT/cookie auth migration, Redis session storage, Python exception handling
**Confidence:** HIGH (all findings based on direct codebase inspection; no speculative library claims)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Token auth flow (SEC-02)**
- Access token: Stored in Angular service memory only (`BehaviorSubject<string | null>` in `AuthService`). Not in localStorage. Lost on page refresh — recovered via silent refresh.
- Refresh token: Moved to httpOnly + Secure + SameSite=Lax cookie. Backend sets `Set-Cookie` header on login response. Frontend no longer reads or stores the refresh token in JS.
- Page refresh recovery: On app startup (APP_INITIALIZER or auth guard), Angular calls `/auth/refresh` — the browser sends the httpOnly cookie automatically. If it succeeds, user stays logged in with new access token in memory. If it fails (no cookie / expired), user is redirected to login.
- 401 interceptor: HTTP interceptor catches 401 responses, calls `/auth/refresh` (cookie-only, no body token), gets a new access token, then replays the original failed request transparently. User never sees the 401.
- Refresh token rotation: `/auth/refresh` issues a new httpOnly cookie and invalidates the previous refresh token (by updating its record in Redis or DB). One-use tokens — stolen refresh token is detected on next use.
- Cookie-only refresh: `/auth/refresh` reads the refresh token solely from the httpOnly cookie. No request body token accepted. This prevents XSS from extracting the refresh token via JS.
- Logout: Backend clears the httpOnly cookie by setting it with `Max-Age=0`. Frontend clears the in-memory access token. Both actions required.

**Error response contract (QUAL-03)**
- Standard shape: Keep FastAPI's native `{"detail": "message"}` format across all endpoints. Most endpoints already use this via `HTTPException`. Fix outliers that return `{"error": "..."}` to use `{"detail": "..."}` instead.
- 204 for side-effect operations: DELETE endpoints and logout that currently return `{"detail": "App deleted"}` or `{"detail": "Logged out"}` on HTTP 200 should change to HTTP 204 No Content with no response body. Frontend checks status code, not body.
- Structured logging: Replace bare `except Exception` with `logger.error("description: %s", e, exc_info=True)` — standard Python logging with full stack trace. No new dependency.

**Exception handling scope (QUAL-01)**
- Scope: All files — API endpoints AND background services (scheduler, sync services). Full sweep of all `except Exception` blocks outside of `main.py` startup helpers.
- `main.py` startup helpers: Leave `_run_migrations` and `_migrate_static_urls_to_objects` broad catches as-is. These are intentionally fire-and-forget non-fatal startup paths. Already commented `(non-fatal)`.
- Replacement pattern: Catch the specific exception types actually raised in that context (e.g., `httpx.HTTPError`, `SQLAlchemyError`, `ValueError`, `aioredis.RedisError`). Log at ERROR level with `exc_info=True`. In scheduler/sync loops, continue processing remaining jobs after catching.
- Anti-pattern to avoid: Do NOT replace `except Exception` with `except Exception as e: logger.error(e)` — that's the same thing with logging. The catch must target the specific exception types the called code can raise.

**Frontend TypeScript scope (QUAL-02)**
- Scope: API response interfaces only. Type every interface that represents a response from a backend HTTP call (`HttpClient` calls in services and components).
- Not in scope: Request body `any` params in `api.service.ts` generic wrapper methods, internal NgRx action payloads, utility helper types, Angular internal types.
- Priority files: `auth.service.ts` (`register` returns `Observable<any>`), `platforms.component.ts` (OAuth session and DV360 lookup responses), `dashboard.component.ts` and `asset-detail-dialog.component.ts` (assets/stats/asset-detail responses).
- Interface naming: Use suffix `Response` for backend responses (e.g., `OAuthSessionResponse`, `DashboardAssetsResponse`, `AssetDetailResponse`).

### Claude's Discretion
- Redis key naming convention for OAuth sessions (e.g., `oauth_session:{session_id}`) and TTL value
- Exact `SameSite` and `Secure` cookie attribute handling for local dev (where HTTPS may not be running) — researcher should find the right pattern
- Which specific exception types to use in each sync service (researcher reads the sync services and identifies what httpx, SQLAlchemy, and platform SDK code can raise)
- Token rotation storage: whether to use Redis or the existing DB `refresh_tokens` table pattern

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SEC-01 | OAuth session state stored in Redis with TTL (replace in-memory `_oauth_sessions` dict) | Redis client library (`redis[asyncio]`) must be added to requirements.txt; `platforms.py` line 29 `_oauth_sessions: dict = {}` is the only change site; key naming and TTL decided below |
| SEC-02 | JWT access token in Angular memory only; refresh token in httpOnly cookie | `auth.py` login/refresh/logout endpoints, `deps.py` `get_current_user`, `auth.service.ts`, `auth.effects.ts`, `auth.reducer.ts` all need coordinated changes; interceptor needs cookie-only refresh call |
| SEC-03 | Fernet key validated at startup — fail fast if TOKEN_ENCRYPTION_KEY missing or invalid | `security.py` `get_fernet()` silent fallback at lines 14-23 replaced with startup-time `ValueError` raise; `config.py` validator added |
| SEC-04 | Asset endpoint path traversal fixed (pathlib validation on `object_path` in `main.py`) | `main.py` `serve_object()` at line 132; `pathlib.Path` resolve + `is_relative_to` check before using the path |
| SEC-05 | OAuth redirect URI hardened — not constructable from untrusted request headers | `config.py` `get_redirect_uri_from_request()` reads `x-forwarded-host` without allowlist; fix: compare against `settings.ALLOWED_HOSTS` or fall back to `settings.BASE_URL` |
| SEC-06 | CORS origins locked to explicit allowlist (no wildcard in production) | `main.py` CORSMiddleware already uses `settings.BACKEND_CORS_ORIGINS`; `config.py` default is `["http://localhost:4200", "http://localhost:3000"]`; `.env.example` must document production requirement |
| QUAL-01 | All broad `except Exception` blocks replaced with specific exception types and structured logging | 75 broad catches across 13 files (see canonical_refs); primary exception types: `httpx.HTTPError`, `httpx.TimeoutException`, `sqlalchemy.exc.SQLAlchemyError`, `ValueError`, `redis.RedisError` |
| QUAL-02 | Frontend `any` types eliminated — typed interfaces for all API response DTOs | 4 priority files; `register` in `auth.service.ts`, OAuth session/DV360 lookup in `platforms.component.ts`, assets/stats in `dashboard.component.ts`, asset detail in `asset-detail-dialog.component.ts` |
| QUAL-03 | Backend error responses consistent structure across all endpoints | Outlier: `main.py` line 166 returns `{"error": "..."}` (SPA fallback — acceptable); `platforms.py` DELETE `{"detail": "App deleted"}` → HTTP 204; `auth.py` logout → HTTP 204 |
| QUAL-04 | All identified bugs fixed: Fernet silent fallback, OAuth session cleanup, token refresh failure handling | `security.py` Fernet fallback (SEC-03 overlap); `platforms.py` no TTL/cleanup on in-memory sessions; Angular interceptor calls `auth.logout()` on refresh failure but guard doesn't do startup refresh |
</phase_requirements>

---

## Summary

This phase has no new feature work — it is a targeted hardening pass across 10 specific vulnerabilities and quality issues. All change sites are precisely identified in CONTEXT.md and confirmed by direct code inspection. The biggest coordination challenge is SEC-02 (JWT/cookie migration): it touches backend endpoints, a Pydantic schema, a FastAPI dependency, and four Angular files simultaneously — these must land together atomically or the app will be broken in between.

The second significant finding is that `redis` (Python async client) is **not in `requirements.txt`**. The `REDIS_URL` setting exists and Redis runs in Docker Compose, but no code currently imports any Redis client. This must be added before SEC-01 can be implemented.

For SEC-02, the Angular auth layer has a dual-storage problem: `AuthService` writes to `localStorage`, AND `AuthEffects` writes to `localStorage` independently in `persistLogin$` and `persistRefresh$`. Both must be changed together — removing storage from effects and from the service, replacing with an in-memory `BehaviorSubject<string | null>` for the access token. The `auth.reducer.ts` initializes `accessToken` and `refreshToken` from `localStorage` directly — this initial state hydration must be removed too.

**Primary recommendation:** Implement in this order per SEC-01 → SEC-02 (backend) → SEC-02 (frontend, coordinated deploy) → SEC-03 → SEC-04 → SEC-05 → SEC-06 → QUAL-01 → QUAL-02 → QUAL-03/QUAL-04 (cleanup pass). SEC-02 backend and frontend changes must be deployed together.

---

## Standard Stack

### Core (all already in requirements.txt or package.json)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | 0.115.0 | HTTP framework | Already in use |
| `cryptography` | 42.0.4 | Fernet key validation (`InvalidKey`) | Already in use |
| `python-jose` | 3.4.0 | JWT encode/decode | Already in use |
| `redis[asyncio]` | **MISSING — must add** | Async Redis client for OAuth session storage | `aioredis` merged into `redis>=4.2`; use `redis.asyncio` module |
| Angular 17 | 17.3.x | Frontend framework | Already in use |
| `@ngrx/store` | 17.2.x | State management | Already in use |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pathlib` (stdlib) | stdlib | Path traversal validation | SEC-04 only; no new install |
| `pydantic-settings` | 2.1.0 | `@validator` on `TOKEN_ENCRYPTION_KEY` at startup | Already in use |

### New Dependency Required

**`redis[asyncio]`** must be added to `backend/requirements.txt`:

```
redis[asyncio]>=5.0.0
```

The `redis>=4.2` package includes `redis.asyncio` as the async interface. No separate `aioredis` package needed (it was deprecated and merged into `redis` in v4.2). The `[asyncio]` extra installs `async-timeout`.

**Version verification:** As of March 2026 the `redis` package on PyPI is at `5.x`. Use `redis[asyncio]>=5.0.0`.

---

## Architecture Patterns

### SEC-01: Redis OAuth Session Storage

**Pattern:** Create a thin async helper in `app/core/redis.py` that exposes a lazy-initialized `redis.asyncio.Redis` client. OAuth endpoints in `platforms.py` call `get_redis()` and use `setex`/`get`/`delete`.

**Redis key naming (Claude's Discretion — decided here):**
```
oauth_session:{session_id}
```

**TTL (Claude's Discretion — decided here):**
- 15 minutes (`900` seconds). OAuth flows should complete within this window; longer TTL creates a session fixation risk.

**Session data format:** JSON-serialized dict (same fields as current `_oauth_sessions` value).

**Pattern:**
```python
# app/core/redis.py
import redis.asyncio as aioredis
from app.core.config import settings

_redis_client: aioredis.Redis | None = None

def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client
```

**In `platforms.py`:**
```python
import json
from app.core.redis import get_redis

OAUTH_SESSION_TTL = 900  # 15 minutes

# Store
redis = get_redis()
await redis.setex(f"oauth_session:{session_id}", OAUTH_SESSION_TTL, json.dumps(session_data))

# Retrieve
raw = await redis.get(f"oauth_session:{session_id}")
session = json.loads(raw) if raw else None

# Delete after use (on successful account connect)
await redis.delete(f"oauth_session:{session_id}")
```

**Remove:** `_oauth_sessions: dict = {}` at `platforms.py` line 29 and all 12 direct dict accesses at the lines listed in CONTEXT.md.

---

### SEC-02: httpOnly Cookie Refresh Token Migration

**Backend changes (coordinated):**

1. **`auth.py` `/auth/login`** — stop returning `refresh_token` in JSON body; set httpOnly cookie instead:
```python
from fastapi import Response

@router.post("/login")
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    # ... existing token creation ...
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,   # False in dev (no HTTPS), True in prod
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",         # scope cookie to auth endpoints only
    )
    return {"access_token": access_token, "token_type": "bearer"}
```

2. **`auth.py` `/auth/refresh`** — read from cookie, not request body:
```python
from fastapi import Cookie

@router.post("/refresh")
async def refresh_token(
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    # ... existing validation logic (unchanged) ...
    # Set new cookie on response
    response.set_cookie(...)
    return {"access_token": new_access, "token_type": "bearer"}
```

3. **`auth.py` `/auth/logout`** — read refresh token from cookie for revocation, clear cookie:
```python
@router.post("/logout", status_code=204)
async def logout(
    refresh_token: str | None = Cookie(default=None),
    response: Response = ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token:
        # revoke in DB ...
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    # 204 No Content — no return body
```

4. **`schemas/user.py` `TokenResponse`** — remove `refresh_token` field; change to `{"access_token": str, "token_type": str}`.

5. **`deps.py` `get_current_user`** — no change needed (already reads `Authorization: Bearer` header for access token).

**Cookie attribute decision for local dev (Claude's Discretion — decided here):**
- Use `secure=not settings.DEBUG`. In `DEBUG=True` mode (local dev over HTTP), `Secure` is omitted so the cookie works without HTTPS. In production `DEBUG=False`, `Secure=True` is enforced.
- `SameSite=Lax` works for same-origin requests. For the OAuth popup callback pattern, the redirect lands on the same origin so `Lax` is safe.
- Set `path="/api/v1/auth"` so the cookie is only sent to auth endpoints, not every API call.

**Frontend changes (coordinated with backend):**

Angular must use `withCredentials: true` on the `/auth/refresh` call so the browser sends the httpOnly cookie cross-origin (dev: 4200→8000):

```typescript
// auth.service.ts
private accessToken$ = new BehaviorSubject<string | null>(null);

getAccessToken(): string | null {
  return this.accessToken$.value;
}

login(email: string, password: string): Observable<LoginResponse> {
  return this.http.post<LoginResponse>(
    `${environment.apiUrl}/auth/login`,
    { email, password },
    { withCredentials: true }   // browser stores the httpOnly Set-Cookie
  ).pipe(
    tap(res => this.accessToken$.next(res.access_token))
  );
}

refreshTokens(): Observable<LoginResponse> {
  return this.http.post<LoginResponse>(
    `${environment.apiUrl}/auth/refresh`,
    {},
    { withCredentials: true }   // sends httpOnly cookie automatically
  ).pipe(
    tap(res => this.accessToken$.next(res.access_token))
  );
}

logout(): void {
  this.http.post(`${environment.apiUrl}/auth/logout`, {}, { withCredentials: true }).subscribe();
  this.accessToken$.next(null);
  this.user$.next(null);
  this.router.navigate(['/auth/login']);
}
```

**Remove from `auth.service.ts`:** `ACCESS_KEY`, `REFRESH_KEY` constants, `storeTokens()`, `clearTokens()`, `localStorage.getItem` calls, `getRefreshToken()`.

**`auth.effects.ts` changes:**
- Remove `persistLogin$` (deletes the two `localStorage.setItem` calls)
- Remove `persistRefresh$` (deletes the two `localStorage.setItem` calls)
- Keep `logout$` but remove `localStorage.removeItem` calls (service clears in-memory token)

**`auth.reducer.ts` changes:**
- Remove `refreshToken` from `AuthState` entirely
- Change `accessToken` initial state from `localStorage.getItem('bs_access')` to `null`
- Remove `isAuthenticated: !!localStorage.getItem('bs_access')` — derive from `accessToken !== null`
- Remove `refreshToken` from `tokenRefreshed` action payload (action dispatch + action definition both need update)

**`auth.actions.ts` changes:**
- Remove `refreshToken` from `loginSuccess` and `tokenRefreshed` props

**`auth.guard.ts` changes:**
- Current guard only checks `auth.isAuthenticated` (memory-based after change). On page refresh, `isAuthenticated` will be false. Guard must attempt silent refresh before redirecting:
```typescript
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.isAuthenticated) return true;

  return auth.refreshTokens().pipe(
    map(() => true),
    catchError(() => of(router.createUrlTree(['/auth/login'])))
  );
};
```

**`auth.interceptor.ts` changes:**
- `refreshTokens()` call already exists. Add `{ withCredentials: true }` is handled inside `AuthService`. The interceptor itself needs no body changes — it just calls `auth.refreshTokens()`.

---

### SEC-03: Fernet Key Startup Validation

**Current bug:** `get_fernet()` silently generates a throwaway key if `TOKEN_ENCRYPTION_KEY` is missing or malformed. Any tokens encrypted with the ephemeral key are permanently unrecoverable on next restart.

**Fix pattern:** Add a Pydantic validator on `Settings` and raise at import time:

```python
# config.py
from cryptography.fernet import InvalidToken
import base64

class Settings(BaseSettings):
    TOKEN_ENCRYPTION_KEY: str  # remove Optional — required field

    @validator("TOKEN_ENCRYPTION_KEY")
    def validate_fernet_key(cls, v: str) -> str:
        try:
            from cryptography.fernet import Fernet
            Fernet(v.encode() if isinstance(v, str) else v)
        except Exception as exc:
            raise ValueError(
                f"TOKEN_ENCRYPTION_KEY is invalid (must be 32 url-safe base64 bytes): {exc}"
            ) from exc
        return v
```

**`security.py` change:** Remove the entire `get_fernet()` function fallback logic. The module-level `fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())` can be inlined directly since validation already ran. The `except Exception:` catch at line 21 must be removed.

**Effect:** App raises `ValidationError` at process startup if key is absent or malformed — `uvicorn` exits with a clear error message before accepting requests.

---

### SEC-04: Path Traversal Fix

**Current code** (`main.py` line 132-148): `object_path` is used directly in `f"creatives/{object_path}"` with no validation.

**Fix:**
```python
from pathlib import Path

_CREATIVES_BASE = Path("/app/static/creatives").resolve()  # or compute dynamically

@app.get("/objects/{object_path:path}", include_in_schema=False)
async def serve_object(object_path: str):
    # Validate: resolved path must stay under creatives base
    try:
        resolved = (_CREATIVES_BASE / object_path).resolve()
        resolved.relative_to(_CREATIVES_BASE)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset path")

    relative = f"creatives/{object_path}" if not object_path.startswith("creatives/") else object_path
    # ... rest of function unchanged ...
```

`Path.resolve()` expands `..` components. `relative_to()` raises `ValueError` if the resolved path escapes the base. This covers `../../etc/passwd` and null-byte variants.

---

### SEC-05: OAuth Redirect URI Hardening

**Current bug** (`config.py` line 84): `host = request.headers.get("x-forwarded-host") or ...` — attacker can set `x-forwarded-host: evil.com` to redirect OAuth callback to their domain.

**Fix — compare against allowlist from `BASE_URL`:**
```python
@staticmethod
def get_redirect_uri_from_request(request, platform: str) -> str:
    platform_keys = {...}
    key = platform_keys.get(platform, platform.lower())

    # Use only the configured BASE_URL scheme+host — never trust x-forwarded-host
    from urllib.parse import urlparse
    parsed = urlparse(settings.BASE_URL)
    safe_base = f"{parsed.scheme}://{parsed.netloc}"
    return f"{safe_base}/api/v1/platforms/oauth/callback/{key}"
```

This removes the `x-forwarded-host` branch entirely. The `BASE_URL` env var is already operator-controlled and used throughout the app. Production deploys set `BASE_URL=https://your-domain.com`. The function signature doesn't change (still accepts `request` parameter for interface compatibility).

---

### SEC-06: CORS Lockdown

**Current state:** `config.py` default `BACKEND_CORS_ORIGINS = ["http://localhost:4200", "http://localhost:3000"]` — no wildcard. `main.py` already uses this setting. The CORSMiddleware is already parameterized.

**Work required:**
- Verify `.env.example` documents `BACKEND_CORS_ORIGINS` with a comment explaining that production must set explicit origins (no `*`).
- Add `BACKEND_CORS_ORIGINS` to the setup script's documented variables.
- No code change needed to `main.py` or `config.py` unless a wildcard was introduced somewhere (inspect `.env.example` to confirm).

**This is primarily a documentation/environment check, not a code change.**

---

### QUAL-01: Exception Handling Pattern

**Replacement matrix by module:**

| Module | Typical exceptions to catch |
|--------|----------------------------|
| `dv360_sync.py`, `meta_sync.py`, `google_ads_sync.py`, `tiktok_sync.py` | `httpx.HTTPStatusError`, `httpx.RequestError`, `httpx.TimeoutException` for HTTP calls; `sqlalchemy.exc.SQLAlchemyError` for DB ops; `ValueError` for data parse failures |
| `scheduler.py` | `Exception` in the per-job wrapper is acceptable **at the job dispatch level** — APScheduler already isolates jobs; narrow catches INSIDE each job runner |
| `harmonizer.py` | `sqlalchemy.exc.SQLAlchemyError`, `sqlalchemy.exc.IntegrityError` |
| `currency.py` | `httpx.RequestError`, `httpx.HTTPStatusError` |
| `connection_purge.py` | `sqlalchemy.exc.SQLAlchemyError` |
| `db/base.py` line 52 | This is `get_db()` rollback handler — the `except Exception` is intentional and correct; rollback-and-reraise pattern must NOT be narrowed |
| `google_ads_oauth.py` | `httpx.HTTPStatusError` |
| `platforms.py` (2 catches) | `httpx.HTTPStatusError` around OAuth token exchange |
| `users.py` (1 catch) | Inspect to determine; likely `sqlalchemy.exc.SQLAlchemyError` |
| `security.py` (1 catch) | Remove entirely after SEC-03 fix |

**Logging pattern:**
```python
except httpx.HTTPStatusError as exc:
    logger.error("DV360 report fetch failed: %s", exc, exc_info=True)
    raise HTTPException(status_code=502, detail="Platform API error")
```

**Exception in `db/base.py` line 52:** The `except Exception: await session.rollback(); raise` is a standard SQLAlchemy session manager pattern — it is correct to keep it broad because it must catch any exception type to guarantee rollback. Do NOT narrow this catch.

**The `_harmonize_with_deadlock_retry` function in `scheduler.py`** at lines 25-37 already uses `except Exception` intentionally to detect deadlock by string match. This is a legitimate use. Leave it as-is or add a comment; it should not be narrowed.

---

### QUAL-02: TypeScript DTO Typing

**Interfaces to create (by file):**

`auth.service.ts`:
```typescript
export interface RegisterResponse {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string;
  is_active: boolean;
  organization_id: string;
  created_at: string;
}
// register(): Observable<RegisterResponse>
```

`platforms.component.ts` — need OAuthSessionResponse and DV360LookupResponse. The existing `ConnectionsResponse` and `PlatformConnection` interfaces at lines 19-42 are already typed — only the two `any` HTTP call returns need typing.

`dashboard.component.ts` and `asset-detail-dialog.component.ts` — inspect the API response shapes from `backend/app/schemas/` (or from existing component property usage) to write `DashboardAssetsResponse`, `AssetDetailResponse`, `StatsResponse` interfaces.

**Convention:** Define interfaces in the same file as the component (not a shared types file) unless they span multiple files.

---

### QUAL-03: Error Response Consistency

**Remaining outliers (confirmed by code inspection):**

1. `main.py` line 166: `{"error": "Frontend not built..."}` — this is the SPA fallback, not an API endpoint. Acceptable to leave as-is since it's a developer diagnostic message, not part of the API contract.

2. `platforms.py` DELETE `/apps/{app_id}` returns `{"detail": "App deleted"}` on HTTP 200 — change to HTTP 204 with no body.

3. `auth.py` POST `/logout` returns `{"detail": "Logged out"}` on HTTP 200 — change to HTTP 204 with no body. (Also: the `/logout` endpoint currently requires `RefreshRequest` body. After SEC-02, logout reads from cookie — the request body schema changes too.)

**FastAPI 204 pattern:**
```python
from fastapi import Response

@router.delete("/apps/{app_id}", status_code=204)
async def delete_brainsuite_app(...) -> Response:
    # ... existing logic ...
    return Response(status_code=204)
```

---

### QUAL-04: Identified Bugs

1. **Fernet silent fallback** — overlaps SEC-03. Fixed by removing the fallback in `security.py` and adding Pydantic validation in `config.py`.

2. **OAuth session cleanup** — in-memory `_oauth_sessions` never removes stale sessions (no TTL, no cleanup). Fixed by SEC-01 migration to Redis with `OAUTH_SESSION_TTL=900`. After token exchange completes successfully, `await redis.delete(f"oauth_session:{session_id}")` must be called in `oauth_callback` after storing tokens in the session AND in `select_ad_account` (wherever the session is consumed for final connection creation).

3. **Token refresh failure handling** — `auth.guard.ts` currently checks only `auth.isAuthenticated` (localStorage-backed). After SEC-02, this check will always be false on page refresh. The guard must do a silent refresh attempt. This is documented in the SEC-02 pattern above.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Path canonicalization for traversal prevention | Custom string stripping logic | `pathlib.Path.resolve()` + `relative_to()` | Handles `../`, `%2e%2e%2f`, symlinks, OS-specific separators |
| Redis async client | Custom socket/protocol code | `redis.asyncio` (from `redis[asyncio]>=5.0`) | Already the ecosystem standard; `aioredis` was merged into this package |
| Cookie-based httpOnly token management | Custom cookie parsing | FastAPI `Response.set_cookie()` + `Cookie()` parameter | FastAPI's cookie handling covers `Secure`, `SameSite`, `HttpOnly`, `Max-Age` correctly |
| Fernet key format validation | Custom base64 check | `Fernet(key)` constructor raises `ValueError` on invalid key | The constructor validates length, padding, and URL-safe base64 atomically |

**Key insight:** Every problem in this phase has an existing stdlib or already-installed solution. No new dependencies except `redis[asyncio]`.

---

## Common Pitfalls

### Pitfall 1: Coordinating SEC-02 Backend + Frontend
**What goes wrong:** Backend stops accepting `refresh_token` in request body; frontend still sends it. Or frontend stops sending it before backend reads from cookie. App breaks for all users.
**Why it happens:** The API contract changes in both directions simultaneously.
**How to avoid:** Deploy backend and frontend in the same release. Backend `/auth/refresh` must accept BOTH cookie and body token during a brief migration window if zero-downtime is needed, or deploy as an atomic breaking change during low-traffic.
**Warning signs:** All users see 401 loops after deploy.

### Pitfall 2: `withCredentials` Missing on Refresh Call
**What goes wrong:** Browser does not send the httpOnly cookie on the `/auth/refresh` POST because Angular's `HttpClient` does not attach credentials by default for cross-origin requests (dev: port 4200 → 8000).
**Why it happens:** Browsers block cross-origin cookie sending unless `withCredentials: true` is set on the request AND the backend sets `allow_credentials=True` in `CORSMiddleware`.
**How to avoid:** Set `{ withCredentials: true }` on every call that needs the cookie (`/auth/refresh`, `/auth/logout`). Confirm `CORSMiddleware(allow_credentials=True)` is set (it already is in `main.py`).
**Warning signs:** 401 on refresh in dev; cookie visible in browser devtools but not sent.

### Pitfall 3: `SameSite=Strict` Breaks OAuth Popup Callback
**What goes wrong:** OAuth provider redirects back to `/api/v1/platforms/oauth/callback/{platform}` from a different origin. With `SameSite=Strict`, the browser will not send the session cookie on that cross-site redirect.
**Why it happens:** The refresh token cookie is on `/api/v1/auth`, not the callback path. This pitfall is moot because the refresh token cookie is scoped to `path="/api/v1/auth"` — the OAuth callback endpoint is a different path.
**How to avoid:** Use `SameSite=Lax` (as decided) and scope cookie to `path="/api/v1/auth"`. The callback endpoint does not need the refresh token.

### Pitfall 4: Angular In-Memory Token Lost on Page Refresh
**What goes wrong:** User refreshes the browser. `accessToken$` BehaviorSubject resets to `null`. `isAuthenticated` returns false. All routes protected by `authGuard` redirect to login.
**Why it happens:** In-memory state does not survive page reload.
**How to avoid:** `authGuard` must attempt a silent `/auth/refresh` (cookie-sent automatically) before redirecting. This is the startup recovery flow decided in CONTEXT.md. See the guard pattern in Architecture Patterns above.
**Warning signs:** Users always have to log in again after any page refresh.

### Pitfall 5: `RefreshRequest` Schema Still in `/auth/refresh` After SEC-02
**What goes wrong:** FastAPI validation rejects the refresh request because it expects a `RefreshRequest` body but the new endpoint reads from cookie only.
**Why it happens:** The Pydantic schema and the endpoint signature must both change.
**How to avoid:** Remove `payload: RefreshRequest` from the refresh endpoint signature; replace with `refresh_token: str | None = Cookie(default=None)`. Also remove `RefreshRequest` from the logout endpoint signature.

### Pitfall 6: `redis.asyncio` vs `aioredis` Import Path
**What goes wrong:** Code imports `import aioredis` — `ModuleNotFoundError` because the standalone package was deprecated.
**Why it happens:** Older tutorials reference `aioredis` as a separate package.
**How to avoid:** Use `import redis.asyncio as aioredis` or `from redis import asyncio as aioredis`. The API is the same. Requires `redis[asyncio]>=4.2`.

### Pitfall 7: QUAL-01 Over-Narrowing the `db/base.py` Rollback Catch
**What goes wrong:** Developer narrows `except Exception` in `get_db()` to `except sqlalchemy.exc.SQLAlchemyError` — application errors (e.g., `ValueError` raised inside an endpoint) no longer trigger rollback.
**Why it happens:** Applying the QUAL-01 rule uniformly without reading the intent of each catch.
**How to avoid:** The `except Exception` in `db/base.py` is an intentional re-raise pattern (`except Exception: rollback; raise`). It must stay broad. Only catches that swallow exceptions need narrowing.

---

## Code Examples

### Redis async client initialization
```python
# Source: redis-py official docs (redis.readthedocs.io)
import redis.asyncio as aioredis

client = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
await client.setex("key", 900, "value")
value = await client.get("key")
await client.delete("key")
```

### FastAPI httpOnly cookie set/clear
```python
# Source: FastAPI docs (fastapi.tiangolo.com/tutorial/cookie-param-models/)
from fastapi import Response, Cookie

# Set cookie on login response
response.set_cookie(
    key="refresh_token",
    value=token_value,
    httponly=True,
    secure=True,         # omit or False in dev
    samesite="lax",
    max_age=604800,      # 7 days in seconds
    path="/api/v1/auth",
)

# Read cookie in endpoint
async def refresh(refresh_token: str | None = Cookie(default=None)):
    ...

# Clear cookie on logout
response.delete_cookie(key="refresh_token", path="/api/v1/auth")
```

### Path traversal prevention with pathlib
```python
# Source: Python docs (docs.python.org/3/library/pathlib.html)
from pathlib import Path

BASE = Path("/app/static/creatives").resolve()

def validate_asset_path(raw: str) -> Path:
    try:
        resolved = (BASE / raw).resolve()
        resolved.relative_to(BASE)   # raises ValueError if outside BASE
        return resolved
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset path")
```

### Angular APP_INITIALIZER silent refresh pattern
```typescript
// Source: Angular docs (angular.dev/guide/di/app-tokens#app_initializer)
import { APP_INITIALIZER } from '@angular/core';
import { AuthService } from './auth.service';
import { catchError, of } from 'rxjs';

export function initAuth(authService: AuthService) {
  return () => authService.refreshTokens().pipe(
    catchError(() => of(null))  // silent failure → guard handles redirect
  );
}

// In appConfig providers:
{
  provide: APP_INITIALIZER,
  useFactory: initAuth,
  deps: [AuthService],
  multi: true,
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `aioredis` (standalone package) | `redis.asyncio` (built into `redis>=4.2`) | redis-py v4.2 (2022) | Import path changes; API identical |
| Pydantic v1 `@validator` | Pydantic v2 `@field_validator` | Pydantic v2 (2023) | Project uses Pydantic v2 (see `pydantic==2.5.0`); use `@field_validator` not `@validator` |
| `localStorage` JWT storage | httpOnly cookie (refresh) + memory (access) | Security standard (2020+) | Eliminates XSS token theft |
| FastAPI `response_model` for 204 endpoints | Return `Response(status_code=204)` directly | FastAPI best practice | Avoids Pydantic serialization on no-body responses |

**Pydantic v2 validator note:** The project uses `pydantic==2.5.0`. The `@validator` decorator is deprecated in v2 — use `@field_validator` with `mode='before'` or `mode='after'`. However, `pydantic-settings` 2.x still supports `@validator` with a deprecation warning. Either works; `@field_validator` is preferred.

---

## Open Questions

1. **`select_ad_account` endpoint location**
   - What we know: `oauth_callback` stores tokens in the session; somewhere downstream the session is consumed to create a `PlatformConnection` DB record.
   - What's unclear: The full `platforms.py` was only read through line 330 during research. The session consumption point (where the session should be deleted from Redis) may be in the second half of the file.
   - Recommendation: Planner should read lines 280-520 of `platforms.py` to find `select_ad_account` or equivalent and identify the exact line where `_oauth_sessions[session_id]["tokens"]` is read for the last time — that is where `await redis.delete(...)` must be called.

2. **Frontend: existing API call that sends `refresh_token` in interceptor**
   - What we know: `auth.interceptor.ts` line 19 calls `auth.refreshTokens()`, which currently passes `{ refresh_token: this.getRefreshToken() }` in the body.
   - What's unclear: After SEC-02, `getRefreshToken()` will not exist. The interceptor calls `refreshTokens()` which will be rewritten to send an empty body. This should be transparent — but the `tokenRefreshed` NgRx action currently dispatches `{ accessToken, refreshToken }`. After SEC-02, there is no `refreshToken` to dispatch.
   - Recommendation: Remove `refreshToken` from `tokenRefreshed` action props (confirmed as in-scope per QUAL-04); update all dispatch sites.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (>=7.4.0, from requirements.txt) |
| Config file | None detected — see Wave 0 |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-01 | Redis OAuth session: store, retrieve, expiry, multi-worker isolation | unit (mock redis) | `pytest tests/test_oauth_session.py -x` | ❌ Wave 0 |
| SEC-02 | Login sets httpOnly cookie; /auth/refresh reads cookie only; logout clears cookie | unit (TestClient) | `pytest tests/test_auth_cookie.py -x` | ❌ Wave 0 |
| SEC-03 | App raises ValueError on startup when TOKEN_ENCRYPTION_KEY is missing or malformed | unit | `pytest tests/test_startup_validation.py -x` | ❌ Wave 0 |
| SEC-04 | `../../etc/passwd` path returns 400; valid path proxies normally | unit (mock obj storage) | `pytest tests/test_path_traversal.py -x` | ❌ Wave 0 |
| SEC-05 | `get_redirect_uri_from_request` ignores `x-forwarded-host`; always uses BASE_URL | unit | `pytest tests/test_redirect_uri.py -x` | ❌ Wave 0 |
| SEC-06 | `BACKEND_CORS_ORIGINS` env var documented; no wildcard default | manual / env check | inspect `.env.example` | N/A |
| QUAL-01 | No `except Exception` outside main.py startup helpers (static analysis) | static | `python -m pytest tests/test_exception_audit.py -x` | ❌ Wave 0 |
| QUAL-02 | No `any` types in API response interfaces (TypeScript compile check) | build | `cd frontend && npx tsc --noEmit --strict` | ❌ (tsc config check needed) |
| QUAL-03 | DELETE and logout return 204; all errors return `{"detail": ...}` | unit (TestClient) | `pytest tests/test_error_shapes.py -x` | ❌ Wave 0 |
| QUAL-04 | OAuth sessions are cleaned up after use; no stale sessions accumulate | unit (mock redis) | covered in SEC-01 test | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -v`
- **Phase gate:** Full pytest suite green + `cd frontend && npx tsc --noEmit` before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_oauth_session.py` — covers SEC-01, QUAL-04
- [ ] `backend/tests/test_auth_cookie.py` — covers SEC-02
- [ ] `backend/tests/test_startup_validation.py` — covers SEC-03
- [ ] `backend/tests/test_path_traversal.py` — covers SEC-04
- [ ] `backend/tests/test_redirect_uri.py` — covers SEC-05
- [ ] `backend/tests/test_error_shapes.py` — covers QUAL-03
- [ ] `backend/tests/test_exception_audit.py` — covers QUAL-01 (AST-based static check)
- [ ] `backend/tests/conftest.py` — shared fixtures (FastAPI TestClient, mock redis, mock settings)

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `backend/app/core/security.py` — Fernet fallback bug confirmed at lines 15-23
- Direct code inspection: `backend/app/api/v1/endpoints/auth.py` — `TokenResponse` returns both tokens in body; `RefreshRequest` schema used in body
- Direct code inspection: `backend/app/api/v1/endpoints/platforms.py` — `_oauth_sessions: dict = {}` confirmed at line 29
- Direct code inspection: `backend/app/main.py` — `serve_object` path traversal at lines 132-148; CORSMiddleware uses `settings.BACKEND_CORS_ORIGINS` at line 113
- Direct code inspection: `backend/app/core/config.py` — `get_redirect_uri_from_request` reads `x-forwarded-host` at line 84; `TOKEN_ENCRYPTION_KEY` is `Optional[str]`; Redis URL configured
- Direct code inspection: `frontend/src/app/core/services/auth.service.ts` — `localStorage.getItem` at lines 44, 48; `storeTokens` writes localStorage at lines 85-88
- Direct code inspection: `frontend/src/app/core/store/auth/auth.effects.ts` — `persistLogin$` and `persistRefresh$` write to localStorage
- Direct code inspection: `frontend/src/app/core/store/auth/auth.reducer.ts` — initializes from `localStorage.getItem` at lines 15-17
- Direct code inspection: `backend/requirements.txt` — no `redis` package present
- Direct code inspection: `docker-compose.yml` — redis:7-alpine running

### Secondary (MEDIUM confidence)
- FastAPI docs pattern for `Cookie()` parameter and `Response.set_cookie()` — standard FastAPI features, HIGH confidence
- `redis-py` v5 `redis.asyncio` API — verified as the current standard; `aioredis` deprecated since 2022

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed present (or confirmed absent) by direct requirements.txt inspection
- Architecture: HIGH — all change sites confirmed by code inspection; patterns are standard FastAPI/Angular
- Pitfalls: HIGH — derived from actual code structure (dual localStorage writes, cross-origin cookie mechanics)

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable stack; no fast-moving dependencies)
