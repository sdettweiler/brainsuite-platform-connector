---
phase: quick-260408-h0s
plan: 01
subsystem: platform-auth
tags: [oauth, token-lifecycle, tiktok, scheduler, frontend]
dependency_graph:
  requires: []
  provides: [reliable-token-lifecycle, tiktok-auto-refresh, expired-status-classification, accurate-health-badges]
  affects: [platform-connections, sync-pipeline, dashboard-health-display]
tech_stack:
  added: []
  patterns: [timezone-aware-datetimes, token-refresh-guard, error-classification, backend-driven-ui-state]
key_files:
  created: []
  modified:
    - backend/app/api/v1/endpoints/platforms.py
    - backend/app/services/sync/tiktok_sync.py
    - backend/app/services/sync/scheduler.py
    - frontend/src/app/features/configuration/pages/platforms.component.ts
decisions:
  - "Use sync_status === 'PENDING' as syncing indicator (is_syncing field does not exist in backend schema)"
  - "Auth error classification uses string-match heuristic on error message (acceptable: worst case misclassified badge, not a security issue)"
  - "Harmonization failures keep ERROR status (not EXPIRED) -- they succeed after auth and are transient DB issues"
metrics:
  duration: "~25 minutes"
  completed: "2026-04-08"
  tasks_completed: 3
  files_modified: 4
---

# Quick Task 260408-h0s: Platform Connection Fix Summary

**One-liner:** Timezone-aware token_expiry, TikTok auto-refresh via _get_valid_token(), EXPIRED status classification for auth failures, and frontend health badges driven by backend sync_status instead of client-side token_expiry.

## What Was Done

### Task 1: Backend token lifecycle fixes

**platforms.py** — Both `datetime.utcnow()` calls in `connect_accounts()` replaced with `datetime.now(timezone.utc)`. Added `timezone` to import. Eliminates potential timezone offset if backend serializer omits the `Z` suffix on naive datetimes.

**tiktok_sync.py** — Added `_get_valid_token()` method to `TikTokSyncService`, mirroring the `google_ads_sync.py` pattern:
- Checks `token_expiry > now(UTC)` — returns decrypted token if still valid
- Calls `tiktok_oauth.TikTokOAuthHandler().refresh_access_token()` if expired
- Updates `access_token_encrypted`, `token_expiry`, and optionally `refresh_token_encrypted` if TikTok rotated it
- Flushes to DB before returning the new token
- `sync_date_range()` now calls `await self._get_valid_token(db, connection)` instead of `decrypt_token()` directly

**scheduler.py** — All `datetime.utcnow()` calls replaced with `datetime.now(timezone.utc)` across all three sync functions (`run_daily_sync`, `run_full_resync`, `run_initial_sync`). Auth error classification added to the main sync fetch `except` block and the DV360-specific error handlers in `run_daily_sync`:

```python
err_str = str(e).lower()
is_auth_failure = (
    "401" in err_str
    or "403" in err_str
    or ("token" in err_str and ("expired" in err_str or "invalid" in err_str or "revoked" in err_str))
    or "unauthorized" in err_str
    or "authentication" in err_str
    or (isinstance(e, ValueError) and "refresh" in err_str)
)
connection.sync_status = "EXPIRED" if is_auth_failure else "ERROR"
```

### Task 2: Frontend health state rewrite

**platforms.component.ts:**
- `HealthState` type extended with `'expired'` and `'initial_sync'`
- `getHealthState()` rewrote: removed client-side `token_expiry` check that caused false "Token expired" after 1 hour for Google Ads/DV360. New logic: check `sync_status === 'PENDING'` for active syncing, then `last_synced_at` for never-synced, then `sync_status === 'EXPIRED'` for auth failures, then `sync_status === 'ERROR'` for other failures, then 48h staleness check
- `getHealthLabel()` and `getHealthBadgeClass()` extended with `'expired'` → `'Reconnect needed'` / `badge-warning` and `'initial_sync'` → `'Syncing…'` / `badge-info`
- `needsReconnect()` updated to include `state === 'expired'`

### Task 3: Build verification

- Python3 AST syntax check: all 3 backend files parse cleanly
- Angular production build: succeeded with no TypeScript errors

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] is_syncing property does not exist in PlatformConnection interface**
- **Found during:** Task 3 (Angular build)
- **Issue:** Plan's `getHealthState()` referenced `conn.is_syncing` but this field is not in the backend schema, does not exist in the TS interface, and would not compile
- **Fix:** Replaced `if (conn.is_syncing)` with `if (conn.sync_status === 'PENDING')` — this is the actual backend indicator for syncing state (consistent with the original code's pattern)
- **Files modified:** `frontend/src/app/features/configuration/pages/platforms.component.ts`
- **Commit:** 375e208

## MANUAL ACTION REQUIRED

**Check Google Cloud Console > APIs and Services > OAuth consent screen.**

If status is "Testing", publish to production immediately.

"Testing" mode causes Google/DV360 refresh tokens to expire after 7 days, which is the most likely root cause of recurring token expiry across Google platforms. This is already tracked as PROD-02 in STATE.md.

The code fixes in this task prevent *false* expired badges and enable TikTok auto-refresh, but if the GCP consent screen is in Testing mode, DV360 and Google Ads tokens genuinely will expire every 7 days and require reconnection — no code fix can address that.

## Known Stubs

None — all changes are functional fixes, no placeholder data.

## Self-Check: PASSED

- FOUND: backend/app/api/v1/endpoints/platforms.py
- FOUND: backend/app/services/sync/tiktok_sync.py
- FOUND: backend/app/services/sync/scheduler.py
- FOUND: frontend/src/app/features/configuration/pages/platforms.component.ts
- FOUND commit: f64211b (Task 1 backend)
- FOUND commit: 20d15bc (Task 2 frontend)
- FOUND commit: 375e208 (deviation fix)
