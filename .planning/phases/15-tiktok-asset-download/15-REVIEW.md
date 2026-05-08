---
phase: 15-tiktok-asset-download
reviewed: 2026-05-08T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - backend/app/services/sync/tiktok_sync.py
  - backend/tests/test_tiktok_sync.py
  - backend/tests/test_scoring_gate.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 15: Code Review Report

**Reviewed:** 2026-05-08
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 15 adds full-resolution video and image asset download to the TikTok sync pipeline, a deferred creative enrichment flow (`enrich_creatives_deferred`), and two new storage methods (`_download_video_asset`, `_download_image_asset`). The scoring gate toggle (`scoring_enabled`) and endpoint-type routing (`scoring_endpoint_type.py`) are covered by `test_scoring_gate.py`. The non-fatal download resilience pattern is sound.

One blocker is present: the Spark ad skip rule (Decision D-02) is only enforced for the video branch, not the image-only branch. A Spark image ad will have its content downloaded in violation of D-02. Beyond that, five warnings cover data fidelity (zero-valued metrics stored as NULL), incomplete Spark detection (missing `TT_USER`), missing rate-limit handling in `_fetch_ad_info`, and an unconditional asset download that ignores the `scoring_enabled` toggle.

---

## Critical Issues

### CR-01: Spark image ad download violates D-02 — `is_spark` guard missing from image branch

**File:** `backend/app/services/sync/tiktok_sync.py:431-452`

**Issue:** Decision D-02 mandates that Spark ads must not have their creative downloaded (`asset_url` stays `None`). The `is_spark` guard is applied only in the first `if` branch (video ads). The second `elif` branch — which fires when `image_ids_raw` is truthy **and** `video_id_val` is falsy — contains no `is_spark` check. A Spark ad that has image creatives and no `video_id` (e.g. a Spark image-format ad) will satisfy the `elif` condition (`image_ids_raw` truthy, `video_id_val` None) and proceed to download the image. The in-code comment at line 454 is incorrect: it states `is_spark=True` is handled implicitly, but for this case it is not.

```python
# Current (buggy):
if video_id_val and not is_spark:
    ...  # video download — Spark blocked correctly
elif image_ids_raw and not video_id_val:
    ...  # image download — is_spark NOT checked here
```

**Fix:**
```python
if video_id_val and not is_spark:
    ...  # video download
elif image_ids_raw and not video_id_val and not is_spark:
    ...  # image download — Spark blocked
# Spark ads: both branches blocked, asset_url stays None (D-02)
```

---

## Warnings

### WR-01: `video_completion_rate` is `None` when `video_p100 == 0` — valid metric stored as NULL

**File:** `backend/app/services/sync/tiktok_sync.py:266`

**Issue:** The guard `if video_p100 and video_views` uses Python truthiness. `video_p100 = 0` is falsy, so a campaign with genuinely zero 100% completions out of thousands of views stores `NULL` instead of `0.0`. Downstream analytics that distinguish `NULL` (missing data) from `0` (observed zero) will treat real zero-completion campaigns as having no data.

```python
# Current: zero completions treated as missing
video_completion_rate = (video_p100 / video_views * 100) if video_p100 and video_views else None
```

**Fix:**
```python
video_completion_rate = (
    (video_p100 / video_views * 100)
    if video_views is not None and video_views > 0 and video_p100 is not None
    else None
)
```

---

### WR-02: `focused_view_rate` is `None` when `focused_view_6s == 0` — valid metric stored as NULL

**File:** `backend/app/services/sync/tiktok_sync.py:272`

**Issue:** Same truthiness guard problem as WR-01. `focused_view_6s = 0` (no focused views from impressions) produces `NULL` rather than `0.0`. The same issue also silently affects `cost_per_focused_view` at line 273 — `focused_view_6s = 0` blocks calculation even when `spend > 0`, which would be a real (infinite cost) case worth surfacing.

```python
# Current: zero focused views treated as missing
focused_view_rate = (focused_view_6s / impressions * 100) if focused_view_6s and impressions else None
```

**Fix:**
```python
focused_view_rate = (
    (focused_view_6s / impressions * 100)
    if impressions is not None and impressions > 0 and focused_view_6s is not None
    else None
)
```

---

### WR-03: Incomplete Spark ad detection — `TT_USER` identity type not in the `is_spark` check

**File:** `backend/app/services/sync/tiktok_sync.py:414`

**Issue:** TikTok's Business API defines three `identity_type` values that indicate Spark ad usage: `CUSTOMIZED_USER`, `AUTH_CODE`, and `TT_USER`. The current check only tests for the first two. An ad with `identity_type = "TT_USER"` will be treated as a non-Spark ad, and the CR-01 gap compounds this: its image download would also proceed.

```python
# Current — misses TT_USER
is_spark = ad.get("identity_type") in ("CUSTOMIZED_USER", "AUTH_CODE")
```

**Fix:**
```python
is_spark = ad.get("identity_type") in ("CUSTOMIZED_USER", "AUTH_CODE", "TT_USER")
```

---

### WR-04: `_fetch_ad_info` has no rate-limit (HTTP 429) back-off unlike `_fetch_ad_reports`

**File:** `backend/app/services/sync/tiktok_sync.py:699-728`

**Issue:** `_fetch_ad_reports` handles HTTP 429 with a 60-second sleep and retry (lines 205-207). `_fetch_ad_info` checks `resp.status_code != 200` and immediately breaks the pagination loop on any non-200 response, including 429. Because `_fetch_ad_info` is called once per 100-ad batch inside `_enrich_from_ad_get`, a transient rate-limit during creative enrichment will silently discard all remaining un-fetched ad metadata rather than retrying. No exception is raised, so the caller's `except (httpx.RequestError, httpx.HTTPStatusError)` guard does not fire either.

**Fix:** Add 429 detection and a sleep-and-retry loop to `_fetch_ad_info`, matching the pattern in `_fetch_ad_reports`:
```python
if resp.status_code == 429:
    logger.warning("TikTok /ad/get/ rate limit, backing off 60s")
    await asyncio.sleep(60)
    continue  # retry same page
elif resp.status_code != 200:
    logger.error(f"TikTok /ad/get/ HTTP {resp.status_code}")
    break
```

---

### WR-05: Asset download runs unconditionally regardless of `scoring_enabled` toggle

**File:** `backend/app/services/sync/tiktok_sync.py:430-461`

**Issue:** The project memory note explicitly states: "must respect auto-scoring toggle for all platforms." The `scoring_enabled` flag is checked in `run_scoring_batch()` before submitting assets to BrainSuite, but asset download (video/image bytes to S3) proceeds unconditionally during `_enrich_from_ad_get` even when `scoring_enabled=False`. When a superadmin disables auto-scoring to pause the pipeline, TikTok assets continue to be downloaded and stored, consuming storage and bandwidth. Other platforms' asset download paths (Google Ads, Meta) were not observed to check this toggle either, so this may be a systemic gap, but it is explicitly required for Phase 15.

**Fix:** In `enrich_creatives_deferred`, read `SystemConfig.scoring_enabled` before calling `_enrich_from_ad_get`, and skip the download when disabled:
```python
cfg_result = await db.execute(select(SystemConfig).limit(1))
system_cfg = cfg_result.scalar_one_or_none()
if system_cfg is not None and not system_cfg.scoring_enabled:
    logger.info("TikTok deferred enrichment: scoring disabled, skipping asset download")
    # Optionally still run creative metadata enrichment without asset download
    return
```

---

## Info

### IN-01: No test for Spark ad skip behavior in `_enrich_from_ad_get`

**File:** `backend/tests/test_tiktok_sync.py`

**Issue:** `test_download_failure_resilience` only tests the failure-resilience path with `identity_type="STANDARD"` ads. There is no test verifying that `identity_type="CUSTOMIZED_USER"` or `"AUTH_CODE"` ads skip both the video and image download branches and result in `asset_url=None`. This is the primary acceptance criterion for D-02 and is untested.

**Fix:** Add a test that passes a Spark ad (`identity_type="CUSTOMIZED_USER"`, `video_id` set) to `_enrich_from_ad_get` and asserts `_download_video_asset` and `_download_image_asset` are never called.

---

### IN-02: No test for image-only ad download path in `_enrich_from_ad_get`

**File:** `backend/tests/test_tiktok_sync.py`

**Issue:** `test_download_image_asset_*` tests verify the storage method in isolation but do not verify that `_enrich_from_ad_get` correctly triggers `_download_image_asset` for an ad with `image_ids_raw` set and `video_id=None`. The branch logic (including the `image_ids_list` coercion for comma-separated strings) is exercised only by integration.

**Fix:** Add a test that passes an image-only ad to `_enrich_from_ad_get` via a mocked `_fetch_ad_info` and asserts `_download_image_asset` is called with the correct arguments.

---

### IN-03: `test_download_failure_resilience` asserts call count, not asset_url value

**File:** `backend/tests/test_tiktok_sync.py:249`

**Issue:** The resilience test asserts `db.execute.call_count >= 2`, which only confirms that the DB update was attempted for each ad. It does not verify the argument passed to `db.execute` — specifically that the `update().values()` call was made with `asset_url=None` (or that the `asset_url` key was absent). A future change that passes an incorrect `asset_url` on failure would not be caught.

**Fix:** Capture `db.execute.call_args_list` and assert that neither call includes a non-None `asset_url` in the update values.

---

### IN-04: `enrich_creatives_deferred` logs token expiry warning but still proceeds

**File:** `backend/app/services/sync/tiktok_sync.py:523-524`

**Issue:** When `conn.token_expiry < datetime.now(timezone.utc)`, a warning is logged but `_enrich_from_ad_get` is called anyway. The call will likely produce 401 errors from TikTok's API for every batch, generating noise in logs. The outer `except Exception` swallows these silently (line 529-530). This pattern causes unnecessary API calls and log noise when the token is known to be expired.

**Fix:** Return early when token is expired, or escalate to an error-level notification:
```python
if conn.token_expiry and conn.token_expiry < datetime.now(timezone.utc):
    logger.error("TikTok deferred enrichment skipped: token expired for connection %s", connection_id)
    return
```

---

_Reviewed: 2026-05-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
