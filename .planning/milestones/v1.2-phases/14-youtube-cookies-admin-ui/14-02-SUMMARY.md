---
phase: 14-youtube-cookies-admin-ui
plan: "02"
subsystem: backend-api-notifications
tags: [superadmin, youtube-cookies, fastapi, notifications, dv360, fernet-encryption]
dependency_graph:
  requires: [14-01]
  provides: [SuperAdmin API endpoints, create_superadmin_notification, _get_cookies_from_db]
  affects:
    - backend/app/api/v1/endpoints/super_admin.py
    - backend/app/api/v1/__init__.py
    - backend/app/services/notifications.py
    - backend/app/services/sync/dv360_sync.py
tech_stack:
  added: []
  patterns:
    - session-per-operation for SuperAdmin notification fan-out
    - correlated scalar subquery for org user counts
    - lazy inline imports for DB models inside service methods
    - Fernet encrypt/decrypt for cookie storage (existing pattern)
key_files:
  created:
    - backend/app/api/v1/endpoints/super_admin.py
  modified:
    - backend/app/api/v1/__init__.py
    - backend/app/services/notifications.py
    - backend/app/services/sync/dv360_sync.py
decisions:
  - "Cookie health response uses Pydantic Literal type — schema enforcement prevents any string field leaking decrypted content (T-14-05)"
  - "_do_download_with_cookies refactored to accept cookie string directly instead of env var name to avoid any accidental os.environ logging path (T-14-10)"
  - "COOKIE_FAILED notification only fires when cookies list is non-empty — cookieless download failures are not notified (cookieless is normal fallback, not an error state)"
  - "_get_cookie_env_vars_to_try retained for backward compatibility; _check_youtube_cookies retained as it is still used at line 1617"
metrics:
  duration_minutes: 8
  completed_date: "2026-04-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 3
---

# Phase 14 Plan 02: SuperAdmin API + Notifications + dv360_sync Cookie DB Refactor Summary

**One-liner:** Five SuperAdmin REST endpoints with Fernet-encrypted cookie storage, system-wide notification fan-out function, and dv360_sync refactored to read cookies from SystemConfig DB with env var fallback.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | SuperAdmin API endpoints + router registration | cd8cb14 | backend/app/api/v1/endpoints/super_admin.py, backend/app/api/v1/__init__.py |
| 2 | SuperAdmin notification fan-out + dv360_sync cookie DB refactor | e2dddb9 | backend/app/services/notifications.py, backend/app/services/sync/dv360_sync.py |

## What Was Built

### SuperAdmin API Endpoints (backend/app/api/v1/endpoints/super_admin.py)

Five endpoints, all gated by `Depends(get_current_superadmin)`:

- `GET /api/v1/super-admin/youtube-cookies` — returns `CookieHealthResponse` with `primary` and `backup` slot health (`valid`/`expired`/`missing`). Decrypts from SystemConfig in-memory for health check only; never returns decrypted content (T-14-05 mitigated via Pydantic response model).
- `PUT /api/v1/super-admin/youtube-cookies` — accepts `UpdateCookiesRequest` with optional `primary`/`backup` fields (partial update). Encrypts via `encrypt_token()` before DB write. Returns fresh health status after commit. Never logs cookie values (T-14-06).
- `GET /api/v1/super-admin/users` — lists all active SuperAdmin users ordered by `created_at`.
- `POST /api/v1/super-admin/users/promote` — promotes user by email. Returns 404 if not found, 409 if already SuperAdmin (T-14-08 — only existing SuperAdmins can promote).
- `GET /api/v1/super-admin/organizations` — read-only org list with active user counts via correlated scalar subquery.

`_check_cookie_health()` standalone function replicates the Netscape cookie expiry parsing logic from `DV360SyncService._check_youtube_cookies` but accepts a cookie string directly (not an env var name).

### SuperAdmin Notification Fan-out (backend/app/services/notifications.py)

`create_superadmin_notification(type, title, message, data)` added after existing `create_org_notification`:
- Queries all users with `is_superuser=True` and `is_active=True`
- Uses session-per-operation pattern (`get_session_factory()()`) — no caller session accepted
- Bulk inserts one `Notification` row per active SuperAdmin
- Returns count of rows inserted (0 if no active SuperAdmins)

### dv360_sync Cookie DB Refactor (backend/app/services/sync/dv360_sync.py)

`_get_cookies_from_db(self)` async method added after `_get_cookie_env_vars_to_try`:
- Opens its own session via `get_session_factory()()` — session-per-operation
- Queries `SystemConfig.limit(1)` for primary and backup encrypted slots
- Decrypts each slot with `decrypt_token()`; logs only "Failed to decrypt" warning without cipher text (T-14-10)
- Falls back to `os.environ.get("YOUTUBE_COOKIES")` and `YOUTUBE_COOKIES_BACKUP` when DB is empty (D-11 graceful migration)
- Returns list of cookie strings in preference order

`_download_video_asset` refactored:
- Calls `await self._get_cookies_from_db()` instead of `self._get_cookie_env_vars_to_try()`
- Inner `_do_download_with_cookies` now accepts `cookie_data: str` directly (was `env_var_name: str`) — eliminates `os.environ.get()` call inside the download function
- Attempt loop iterates over cookie strings: `attempts = cookies if cookies else [""]`
- After all attempts exhausted, fires `COOKIE_FAILED` notification via `create_superadmin_notification` with `deeplink: "/configuration/admin"` — only if `cookies` list was non-empty (D-12, D-13)

`_check_youtube_cookies` and `_get_cookie_env_vars_to_try` are preserved (still used at line 1617 for health reporting in the broader sync flow).

## Decisions Made

1. **Pydantic Literal for health status fields:** `CookieSlotHealth.status: Literal["valid","expired","missing"]` makes it structurally impossible for a string field leaking decrypted cookie content to pass schema validation (T-14-05 defense in depth).
2. **_do_download_with_cookies accepts string, not env var name:** Eliminates the `os.environ.get(env_var_name)` call inside the executor, preventing any accidental logging path that could expose cookie content (T-14-10).
3. **COOKIE_FAILED only when cookies list non-empty:** Cookieless download attempts (empty `cookies` list) are a normal fallback and are not notified. Notification fires only when DB/env cookies existed but all failed.
4. **Retained _get_cookie_env_vars_to_try and _check_youtube_cookies:** `_check_youtube_cookies` is still called at line 1617 in the broader sync health-reporting path. Removing it would break that logic. `_get_cookie_env_vars_to_try` retained for backward compatibility with no callers.

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria met on first implementation pass.

## Known Stubs

None — all endpoints are fully wired to DB queries. Cookie health is computed from live SystemConfig data.

## Threat Surface Scan

No new trust boundaries beyond those documented in the plan's threat model (T-14-05 through T-14-10). All mitigations applied:
- T-14-05: `CookieHealthResponse` Pydantic model enforces schema — no string field for cookie content
- T-14-06: Cookie values logged only as "updated (content not logged)" at INFO level
- T-14-08: `POST /users/promote` gated by `Depends(get_current_superadmin)`
- T-14-10: `_get_cookies_from_db` and `_do_download_with_cookies` never log decrypted content

## Self-Check

- [x] backend/app/api/v1/endpoints/super_admin.py exists with 5 routes
- [x] backend/app/api/v1/__init__.py contains `super_admin.router` import and registration
- [x] backend/app/services/notifications.py contains `create_superadmin_notification`
- [x] backend/app/services/sync/dv360_sync.py contains `_get_cookies_from_db`
- [x] backend/app/services/sync/dv360_sync.py contains `COOKIE_FAILED` notification dispatch
- [x] backend/app/services/sync/dv360_sync.py still contains `_check_youtube_cookies`
- [x] Commit cd8cb14 exists
- [x] Commit e2dddb9 exists
