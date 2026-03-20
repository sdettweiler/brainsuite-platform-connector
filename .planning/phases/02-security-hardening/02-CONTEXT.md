# Phase 2: Security Hardening - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix all critical production security vulnerabilities and establish a minimum code quality baseline so external users can safely onboard. No new features — purely hardening existing functionality. Covers: OAuth session Redis migration (SEC-01), JWT httpOnly cookie migration (SEC-02), Fernet key startup validation (SEC-03), path traversal fix (SEC-04), OAuth redirect URI hardening (SEC-05), CORS lockdown (SEC-06), exception handling quality (QUAL-01), frontend TypeScript DTO typing (QUAL-02), backend error response consistency (QUAL-03), and identified bug fixes (QUAL-04).

</domain>

<decisions>
## Implementation Decisions

### Token auth flow (SEC-02)

- **Access token**: Stored in Angular service memory only (`BehaviorSubject<string | null>` in `AuthService`). Not in localStorage. Lost on page refresh — recovered via silent refresh.
- **Refresh token**: Moved to httpOnly + Secure + SameSite=Lax cookie. Backend sets `Set-Cookie` header on login response. Frontend no longer reads or stores the refresh token in JS.
- **Page refresh recovery**: On app startup (APP_INITIALIZER or auth guard), Angular calls `/auth/refresh` — the browser sends the httpOnly cookie automatically. If it succeeds, user stays logged in with new access token in memory. If it fails (no cookie / expired), user is redirected to login.
- **401 interceptor**: HTTP interceptor catches 401 responses, calls `/auth/refresh` (cookie-only, no body token), gets a new access token, then replays the original failed request transparently. User never sees the 401.
- **Refresh token rotation**: `/auth/refresh` issues a new httpOnly cookie and invalidates the previous refresh token (by updating its record in Redis or DB). One-use tokens — stolen refresh token is detected on next use.
- **Cookie-only refresh**: `/auth/refresh` reads the refresh token solely from the httpOnly cookie. No request body token accepted. This prevents XSS from extracting the refresh token via JS.
- **Logout**: Backend clears the httpOnly cookie by setting it with `Max-Age=0`. Frontend clears the in-memory access token. Both actions required.

### Error response contract (QUAL-03)

- **Standard shape**: Keep FastAPI's native `{"detail": "message"}` format across all endpoints. Most endpoints already use this via `HTTPException`. Fix outliers that return `{"error": "..."}` to use `{"detail": "..."}` instead.
- **204 for side-effect operations**: DELETE endpoints and logout that currently return `{"detail": "App deleted"}` or `{"detail": "Logged out"}` on HTTP 200 should change to HTTP 204 No Content with no response body. Frontend checks status code, not body.
- **Structured logging**: Replace bare `except Exception` with `logger.error("description: %s", e, exc_info=True)` — standard Python logging with full stack trace. No new dependency.

### Exception handling scope (QUAL-01)

- **Scope**: All files — API endpoints AND background services (scheduler, sync services). Full sweep of all `except Exception` blocks outside of `main.py` startup helpers.
- **`main.py` startup helpers**: Leave `_run_migrations` and `_migrate_static_urls_to_objects` broad catches as-is. These are intentionally fire-and-forget non-fatal startup paths. Already commented `(non-fatal)`.
- **Replacement pattern**: Catch the specific exception types actually raised in that context (e.g., `httpx.HTTPError`, `SQLAlchemyError`, `ValueError`, `aioredis.RedisError`). Log at ERROR level with `exc_info=True`. In scheduler/sync loops, continue processing remaining jobs after catching.
- **Anti-pattern to avoid**: Do NOT replace `except Exception` with `except Exception as e: logger.error(e)` — that's the same thing with logging. The catch must target the specific exception types the called code can raise.

### Frontend TypeScript scope (QUAL-02)

- **Scope**: API response interfaces only. Type every interface that represents a response from a backend HTTP call (`HttpClient` calls in services and components).
- **Not in scope**: Request body `any` params in `api.service.ts` generic wrapper methods, internal NgRx action payloads, utility helper types, Angular internal types.
- **Priority files**: `auth.service.ts` (`register` returns `Observable<any>`), `platforms.component.ts` (OAuth session and DV360 lookup responses), `dashboard.component.ts` and `asset-detail-dialog.component.ts` (assets/stats/asset-detail responses).
- **Interface naming**: Use suffix `Response` for backend responses (e.g., `OAuthSessionResponse`, `DashboardAssetsResponse`, `AssetDetailResponse`).

### Claude's Discretion

- Redis key naming convention for OAuth sessions (e.g., `oauth_session:{session_id}`) and TTL value
- Exact `SameSite` and `Secure` cookie attribute handling for local dev (where HTTPS may not be running) — researcher should find the right pattern
- Which specific exception types to use in each sync service (researcher reads the sync services and identifies what httpx, SQLAlchemy, and platform SDK code can raise)
- Token rotation storage: whether to use Redis or the existing DB `refresh_tokens` table pattern

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements
- `.planning/REQUIREMENTS.md` §Security & Code Quality — SEC-01 through SEC-06, QUAL-01 through QUAL-04: full requirement list for this phase
- `.planning/ROADMAP.md` §Phase 2 — Success criteria (5 items) that define done

### Existing auth code to change
- `backend/app/core/security.py` — `get_fernet()` silent fallback bug (SEC-03 target), JWT creation functions
- `backend/app/api/v1/endpoints/auth.py` — login, refresh, logout endpoints; where `Set-Cookie` and `clear-cookie` changes happen
- `backend/app/api/v1/deps.py` — `get_current_user` dependency; where access token reading changes
- `frontend/src/app/core/services/auth.service.ts` — localStorage token storage to remove; in-memory access token + cookie-based refresh to implement
- `frontend/src/app/core/store/auth/auth.effects.ts` — NgRx effects that call auth actions; may need update for new token flow
- `frontend/src/app/core/store/auth/auth.reducer.ts` — NgRx state for auth; may hold token state

### OAuth session code to migrate (SEC-01)
- `backend/app/api/v1/endpoints/platforms.py` — `_oauth_sessions: dict = {}` at line 29; all usages at lines 188, 222, 248, 249, 259, 264, 292, 330, 414, 460, 486, 487

### Path traversal target (SEC-04)
- `backend/app/main.py` — `serve_object(object_path: str)` endpoint; `object_path` needs pathlib validation before use

### OAuth redirect URI target (SEC-05)
- `backend/app/core/config.py` — `get_redirect_uri_from_request()` reads `x-forwarded-host` without allowlist check

### CORS target (SEC-06)
- `backend/app/main.py` — `CORSMiddleware` configuration reads `settings.BACKEND_CORS_ORIGINS`
- `backend/app/core/config.py` — `BACKEND_CORS_ORIGINS` field; needs to be env-configured, not hardcoded

### Exception handling targets (QUAL-01)
- `backend/app/api/v1/endpoints/platforms.py` — 2 broad catches
- `backend/app/api/v1/endpoints/users.py` — 1 broad catch
- `backend/app/services/sync/scheduler.py` — 23 broad catches
- `backend/app/services/sync/dv360_sync.py` — 21 broad catches
- `backend/app/services/sync/meta_sync.py` — 10 broad catches
- `backend/app/services/sync/harmonizer.py` — 6 broad catches
- `backend/app/services/currency.py` — 3 broad catches
- `backend/app/services/connection_purge.py` — 5 broad catches
- `backend/app/services/sync/google_ads_sync.py` — 2 broad catches
- `backend/app/services/sync/tiktok_sync.py` — 2 broad catches
- `backend/app/services/platform/google_ads_oauth.py` — 1 broad catch
- `backend/app/core/security.py` — 1 broad catch (the Fernet fallback)
- `backend/app/db/base.py` — 1 broad catch

### TypeScript DTO targets (QUAL-02)
- `frontend/src/app/core/services/auth.service.ts` — `register` returns `Observable<any>`
- `frontend/src/app/features/configuration/pages/platforms.component.ts` — OAuth session and DV360 lookup `any` responses
- `frontend/src/app/features/dashboard/dashboard.component.ts` — assets and stats `any` responses
- `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` — asset detail `any` response
- `frontend/src/app/core/services/api.service.ts` — generic service wrapper (request body `any` stays, response types need callers to pass proper generics)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/core/config.py` `Settings.REDIS_URL`: Already configured (`redis://localhost:6379/0`). Redis service running from Phase 1. OAuth session migration has infrastructure ready — just needs the Redis client wired up in `platforms.py`.
- `frontend/src/app/core/services/auth.service.ts`: `AuthService` already has `storeTokens()`, `clearTokens()`, `getAccessToken()`, `getRefreshToken()` — these are the methods to rewrite, not the class structure.
- Existing `BehaviorSubject<CurrentUser | null>` pattern in `AuthService` — access token can use the same pattern (`BehaviorSubject<string | null>`).

### Established Patterns
- `CORSMiddleware` with `settings.BACKEND_CORS_ORIGINS` list: Middleware is already parameterized — just need to ensure `BACKEND_CORS_ORIGINS` in `.env.example` documents the production lockdown requirement (no wildcard).
- `HTTPException(status_code=..., detail="...")`: This is the established error pattern in all endpoint files. The outlier `{"error": "..."}` returns are exceptions, not the rule.
- `APScheduler` job executor wraps each job run — unhandled exceptions from jobs are logged by APScheduler itself. The broad catches in sync services currently suppress those logs; removing them (replacing with specific types) lets APScheduler also log job failures at its level.

### Integration Points
- `/auth/login` response → currently returns `{access_token, refresh_token}` JSON body → changes to `{access_token}` JSON + `Set-Cookie: refresh_token=...` header
- `/auth/refresh` endpoint → currently reads `refresh_token` from request body → changes to read from httpOnly cookie
- HTTP interceptor in Angular → needs creation or modification to handle 401 + retry
- APP_INITIALIZER or root guard → needs to call `/auth/refresh` on startup to restore session

</code_context>

<specifics>
## Specific Ideas

No specific product references or "I want it like X" moments — this phase is purely fixing known vulnerabilities to production-standard patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-security-hardening*
*Context gathered: 2026-03-20*
