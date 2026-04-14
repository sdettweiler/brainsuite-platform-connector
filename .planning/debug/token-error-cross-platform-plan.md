# Plan: Unified Token Error Handling (All Platforms)

**Status:** Blocked on Meta verification
**Created:** 2026-04-10

---

## Goal

Every platform sync must behave identically on token expiry:
1. Stop all operations immediately (no partial data, no retries)
2. Write `sync_status = "EXPIRED"` to the DB
3. Fire a `TOKEN_EXPIRED` notification → toast + bell

---

## Step 1 — Verify Meta (gate for all other work)

The root-cause fix was in `scheduler.py:452` — `if not is_dv360 and _token_err is None:` — which prevents a `NameError` crash on `sync_result` when `MetaTokenError` is caught, allowing the fresh-session handler at line 582 to actually run.

**To verify:**
1. `docker-compose up -d`
2. Revoke the Meta access token (in Meta for Developers → Apps → your app → Revoke access, or use an intentionally wrong token in the DB)
3. Trigger a manual resync from the UI
4. Check:
   - Connection chip changes to "Token Expired" (not "Syncing" stuck)
   - A toast notification appears
   - Bell icon shows the notification
   - `sync_status = 'EXPIRED'` in DB: `SELECT sync_status FROM platform_connections WHERE platform = 'META';`

---

## Step 2 — Implement for TikTok, Google Ads, DV360

### Pattern (copy from Meta)

**In each sync service:**
- Add `class <Platform>TokenError(Exception): pass`
- Detect 401/403 HTTP status and known auth error codes → raise `<Platform>TokenError` immediately (stop all loops)

**In `scheduler.py` — for each of the 3 scheduler functions** (`run_daily_sync`, `run_full_resync`, `run_initial_sync`):
- Add `except <Platform>TokenError` handler (same as `except MetaTokenError`)
- Write `sync_status = "EXPIRED"` via fresh session
- Fire `TOKEN_EXPIRED` notification

### TikTok
- **File:** `backend/app/services/sync/tiktok_sync.py`
- **Where to detect:** `sync_date_range` → inner HTTP call loops — check `response.status_code in (401, 403)` and TikTok API error codes for auth failures
- **Exception class:** `TikTokTokenError`

### Google Ads
- **File:** `backend/app/services/sync/google_ads_sync.py`
- **Where to detect:** `_fetch_video_ad_performance` → HTTP response check (line ~193) — `status_code in (401, 403)` → raise immediately
- **Exception class:** `GoogleAdsTokenError`

### DV360
- **File:** `backend/app/services/sync/dv360_sync.py`
- **Where to detect:** existing 401 detection in polling loop (line ~809) — if `_refresh_token_standalone` fails, raise `DV360TokenError` instead of logging and continuing
- **Exception class:** `DV360TokenError`

---

## Scheduler changes needed (per function × 3 platforms)

Each of the 3 scheduler functions needs a new `except` block added after the existing `except MetaTokenError`:

```python
except TikTokTokenError as e:
    # same pattern as MetaTokenError handler
except GoogleAdsTokenError as e:
    # same pattern
except DV360TokenError as e:
    # same pattern
```

Or alternatively, introduce a shared `TokenExpiredError` base class that all platform errors inherit from, reducing the scheduler to one handler.

---

## Files to touch

| File | Change |
|------|--------|
| `backend/app/services/sync/tiktok_sync.py` | Add `TikTokTokenError`, detect 401/403, raise immediately |
| `backend/app/services/sync/google_ads_sync.py` | Add `GoogleAdsTokenError`, detect 401/403, raise immediately |
| `backend/app/services/sync/dv360_sync.py` | Add `DV360TokenError`, if refresh fails raise immediately |
| `backend/app/services/sync/scheduler.py` | Add except handlers for all 3 new error types in all 3 sync functions |

---

## Already done

- `MetaTokenError` root-cause fixed: `scheduler.py:452` guarded with `and _token_err is None`
