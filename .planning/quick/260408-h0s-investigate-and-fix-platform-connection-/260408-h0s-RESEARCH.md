# Quick Task: Platform Connection Issues - Research

**Researched:** 2026-04-08
**Domain:** OAuth token management, platform sync pipeline
**Confidence:** HIGH

## Summary

Investigation of platform connection issues -- sync failures and expired tokens -- across all four platforms (Meta, Google Ads, DV360, TikTok). The codebase has several concrete issues in token lifecycle management that cause false "token expired" UI states and prevent proper error recovery.

**Primary finding:** The token_expiry field is set with naive datetimes at connection time but compared against timezone-aware datetimes during sync, creating a timezone mismatch. Additionally, the frontend shows "Token expired" based on client-side token_expiry comparison even when the backend can successfully refresh tokens. The "EXPIRED" sync status is documented but never actually set by any backend code.

**DV360 live mode:** DV360 uses standard Google OAuth with refresh tokens (same as Google Ads). There is no "dev mode vs live mode" distinction in the token mechanism itself -- both use the same `access_type=offline` flow with 1-hour access tokens and indefinite refresh tokens. The DV360 credential routing issue (DEV_ prefix) was already diagnosed and fixed in the debug session.

## Findings

### Finding 1: Naive vs Aware Datetime Mismatch in Token Expiry

**Severity:** HIGH
**Confidence:** HIGH [VERIFIED: codebase inspection]

**The bug:** When connections are created in `platforms.py:connect_accounts()`, `token_expiry` is set using `datetime.utcnow()` (naive, no timezone info):

```python
# platforms.py line 403 and 419
token_expiry=datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
```

But when the sync service checks token validity, it uses `datetime.now(timezone.utc)` (timezone-aware):

```python
# dv360_sync.py line 201, google_ads_sync.py line 109
now = datetime.now(timezone.utc)
if connection.token_expiry and connection.token_expiry > now:
```

The `PlatformConnection.token_expiry` column is `DateTime(timezone=True)`. PostgreSQL stores naive datetimes by assuming UTC when the column is `timestamptz`, so the backend comparison likely works in practice. However, the frontend receives this value and compares it client-side:

```typescript
// platforms.component.ts line 1080
if (conn.token_expiry && new Date(conn.token_expiry) < now) {
  return 'token_expired';
}
```

If the backend serializes a naive datetime without the `Z` suffix, `new Date()` will interpret it as local time, causing the expiry to appear hours early/late depending on the user's timezone. This is the most likely cause of premature "Token expired" badges.

**Fix:** Use `datetime.now(timezone.utc)` consistently everywhere, or ensure the Pydantic serializer always emits ISO 8601 with `Z`/`+00:00`.

### Finding 2: Frontend Token Expiry Check is Misleading

**Severity:** MEDIUM
**Confidence:** HIGH [VERIFIED: codebase inspection]

The frontend `getHealthState()` checks `token_expiry` first and shows "Token expired" even if the backend can and will refresh the token automatically. For Google Ads and DV360, the access token expires every ~3600 seconds, but the refresh token is indefinite. The backend's `_get_valid_token()` handles this transparently.

The frontend check at line 1080 means every Google Ads/DV360 connection will show "Token expired" after 1 hour, even though the next sync will refresh successfully.

**Token lifetimes by platform:**
| Platform | Access Token | Refresh Token | Backend Auto-Refresh |
|----------|-------------|---------------|---------------------|
| Meta | 60 days (long-lived) | None (not needed) | No -- must reconnect after 60 days |
| TikTok | ~24 hours | ~365 days | No `_get_valid_token` -- uses raw decrypt |
| Google Ads | ~1 hour | Indefinite | Yes -- `_get_valid_token()` |
| DV360 | ~1 hour | Indefinite | Yes -- `_get_valid_token()` + standalone refresh during polling |

**The problem:** For Google Ads and DV360, the `token_expiry` stored in DB represents the *access token* expiry (1 hour), not the refresh token expiry (indefinite). The frontend interprets expired access token as "connection broken" when it is not.

**Fix options:**
1. Remove client-side token_expiry check entirely; rely on backend sync_status for health state
2. Only check token_expiry for Meta (which has no refresh token), not for platforms with refresh tokens
3. Update token_expiry in the DB after each successful refresh (already done in `_get_valid_token`) and ensure frontend polls recent data

### Finding 3: TikTok and Meta Have No Token Refresh in Sync Path

**Severity:** HIGH
**Confidence:** HIGH [VERIFIED: codebase inspection]

Meta and TikTok sync services call `decrypt_token(connection.access_token_encrypted)` directly without any expiry check or refresh attempt:

```python
# meta_sync.py line 111
access_token = decrypt_token(connection.access_token_encrypted)

# tiktok_sync.py line 128
access_token = decrypt_token(connection.access_token_encrypted)
```

Both platforms have refresh capabilities:
- **Meta:** Long-lived token (60 days) cannot be refreshed after expiry -- must re-authorize
- **TikTok:** Has `refresh_access_token()` method in `tiktok_oauth.py` but it is never called from the sync path

When TikTok access tokens expire (~24 hours), every sync attempt fails and sets `sync_status = "ERROR"`. There is no automatic recovery. The user must manually reconnect.

**Fix:** Add `_get_valid_token()` pattern to TikTok sync (check expiry, refresh if needed). For Meta, detect expired long-lived token and set sync_status to "EXPIRED" (with a reconnect prompt) instead of generic "ERROR".

### Finding 4: "EXPIRED" Sync Status Never Used

**Severity:** LOW
**Confidence:** HIGH [VERIFIED: codebase grep]

The model comment documents `EXPIRED` as a valid `sync_status` value:
```python
sync_status: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE, EXPIRED, ERROR, PENDING
```

The frontend has filter and display support for `EXPIRED`. But no backend code ever sets `sync_status = "EXPIRED"`. All failures go to `"ERROR"`, making it impossible for the UI to distinguish between "token needs reconnect" and "transient API error".

**Fix:** Set `sync_status = "EXPIRED"` when a sync fails specifically due to a 401/403 token error (after refresh attempt fails), instead of generic "ERROR".

### Finding 5: DV360 Credential Routing (Previously Diagnosed)

**Severity:** RESOLVED
**Confidence:** HIGH [VERIFIED: debug file]

The `.planning/debug/dv360-connection-not-opening.md` documents that DV360 credentials were missing the `DEV_` prefix in `.env`, causing the OAuth flow to fail with a 503. This has been fixed (status: awaiting_human_verify).

The docker-compose.yml now correctly passes both production and dev credentials:
- Production: `DV360_CLIENT_ID: ${DV360_CLIENT_ID:-}` (line not present -- uses config.py default)
- Dev: `DEV_DV360_CLIENT_ID: ${DEV_DV360_CLIENT_ID:-}` (line 131)

Note: The docker-compose.yml also passes production-level `GOOGLE_CLIENT_ID` directly (line 103), while the dev flow uses `DEV_GOOGLE_CLIENT_ID`. Both paths work because `apply_env_credentials` only promotes DEV_ values when `CURRENT_ENV=development`.

### Finding 6: No Distinction Between Transient and Fatal Sync Errors

**Severity:** MEDIUM
**Confidence:** HIGH [VERIFIED: codebase inspection]

The scheduler's error handling catches all exceptions uniformly:
```python
except Exception as e:
    connection.sync_status = "ERROR"
```

This means a transient network timeout gets the same treatment as a permanently revoked token. There is no retry logic at the scheduler level (only within DV360's report polling), and no error classification.

## Token Lifecycle Summary

### Connection Time (platforms.py:connect_accounts)
1. OAuth callback returns tokens (access_token, refresh_token, expires_in)
2. Both tokens encrypted with Fernet and stored in PlatformConnection
3. `token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)` -- naive datetime stored in timestamptz column

### Sync Time (scheduler.py -> *_sync.py)
1. **Google Ads / DV360:** `_get_valid_token()` checks `token_expiry > now(UTC)`, refreshes if expired, updates DB
2. **Meta / TikTok:** Directly decrypts access_token with no expiry check or refresh
3. Any exception -> sync_status = "ERROR", no error classification

### Frontend Display (platforms.component.ts)
1. `getHealthState()` checks `token_expiry` client-side first (priority over all other states)
2. Then checks `is_syncing`, `last_synced_at`, `sync_status === 'ERROR'`, and staleness (>48h)
3. Problem: For Google/DV360, token_expiry fires after 1 hour but backend auto-refreshes

## Recommended Fixes (Priority Order)

### Fix 1: Remove Frontend Token Expiry Health Check (Quick Win)
Remove the client-side `token_expiry` check from `getHealthState()`. The backend already handles token refresh for Google/DV360, and the frontend should rely on `sync_status` as the source of truth for connection health.

### Fix 2: Add TikTok Token Refresh to Sync Path
Add a `_get_valid_token()` method to `tiktok_sync.py` mirroring the Google/DV360 pattern. TikTok has a `refresh_access_token()` method already implemented in `tiktok_oauth.py` but unused.

### Fix 3: Use "EXPIRED" Status for Token Failures
When a sync fails due to 401/403 after refresh attempt fails, set `sync_status = "EXPIRED"` instead of "ERROR". This lets the frontend show "Reconnect" prompts specifically for auth failures.

### Fix 4: Fix Naive Datetime in Token Expiry
Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` in `platforms.py:connect_accounts()` for token_expiry calculation. This ensures consistency with the sync services that use aware datetimes.

### Fix 5: Classify Sync Errors
Wrap the scheduler's error handling to detect HTTP 401/403 specifically and set EXPIRED vs ERROR accordingly. Add a retry mechanism for transient failures (network timeouts, 5xx responses).

## DV360 Live Mode Specifics

There is no fundamental difference between DV360 "dev mode" and "live mode" in terms of token handling. Both use the same Google OAuth 2.0 flow with:
- `access_type=offline` (gets refresh token)
- `prompt=consent` (forces consent screen, ensures refresh token is returned)
- Access tokens expire in ~3600 seconds
- Refresh tokens are indefinite (unless user revokes or app is de-authorized)

"Live mode" (published OAuth consent screen) simply means:
- More than 100 users can authorize
- No test user restrictions
- Tokens don't expire after 7 days (which they do for "Testing" consent screen status)

**Critical note:** If the Google Cloud project's OAuth consent screen is still in "Testing" status, refresh tokens expire after 7 days. This would cause DV360 (and Google Ads, which shares the same GCP project) connections to fail after 1 week with no recovery. This aligns with the reported symptom of "expired tokens".

**Verification needed:** Check the Google Cloud Console > APIs & Services > OAuth consent screen to confirm the publishing status. If it shows "Testing", that is the root cause for both DV360 and Google Ads token expiry. [ASSUMED -- cannot verify Google Cloud Console status from code]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Google OAuth consent screen in "Testing" mode causes refresh token expiry after 7 days | DV360 Live Mode Specifics | HIGH -- if consent screen is already published, this is not the root cause |
| A2 | PostgreSQL interprets naive datetimes as UTC for timestamptz columns | Finding 1 | LOW -- this is standard PostgreSQL behavior |
| A3 | Frontend Date() constructor interprets timestamps without timezone as local time | Finding 1 | LOW -- this is standard JavaScript behavior |

## Open Questions

1. **Is the Google Cloud OAuth consent screen in "Testing" or "Published" status?**
   - This is the single most important question. "Testing" status = refresh tokens expire after 7 days, which would explain all Google/DV360 sync failures.
   - How to check: Google Cloud Console > APIs & Services > OAuth consent screen
   - Recommendation: If "Testing", publish immediately. This is already flagged in STATE.md as PROD-02.

2. **Are Meta long-lived tokens actually expiring?**
   - Meta long-lived tokens last 60 days. If the platform was set up >60 days ago, Meta tokens will have expired with no automatic recovery path.
   - Meta does NOT have refresh tokens -- must re-authorize after 60 days.

3. **What specific error messages appear in backend logs during sync failures?**
   - The scheduler logs `f"{type(e).__name__}: {e}"` on failure. Checking these logs would immediately reveal whether failures are 401 (token) or something else.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `backend/app/services/platform/dv360_oauth.py` -- DV360 OAuth flow, token refresh
- Codebase inspection: `backend/app/services/sync/dv360_sync.py` -- `_get_valid_token()`, standalone refresh
- Codebase inspection: `backend/app/services/sync/scheduler.py` -- sync orchestration, error handling
- Codebase inspection: `backend/app/api/v1/endpoints/platforms.py` -- OAuth connect flow, token storage
- Codebase inspection: `frontend/src/app/features/configuration/pages/platforms.component.ts` -- health state logic
- Codebase inspection: `backend/app/models/platform.py` -- PlatformConnection model
- Debug file: `.planning/debug/dv360-connection-not-opening.md` -- DV360 credential routing fix

### Secondary (MEDIUM confidence)
- Google OAuth documentation: Testing mode refresh token 7-day expiry [ASSUMED from training knowledge]
- Meta OAuth documentation: 60-day long-lived token lifetime [ASSUMED from training knowledge]
