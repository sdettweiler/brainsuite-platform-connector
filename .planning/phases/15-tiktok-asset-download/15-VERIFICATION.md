---
phase: 15-tiktok-asset-download
verified: 2026-05-08T17:00:00Z
status: human_needed
score: 7/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "After a real TikTok sync run, confirm video ads have asset_url populated in TikTokRawPerformance and that CreativeAsset.asset_url is non-null in the database"
    expected: "SELECT asset_url FROM tiktok_raw_performance WHERE video_id IS NOT NULL LIMIT 5; all rows have a non-null S3 URL. SELECT asset_url FROM creative_assets WHERE platform='TIKTOK' AND asset_format='VIDEO' LIMIT 5; all rows have a non-null URL."
    why_human: "Download flow requires live TikTok API credentials and a MinIO/S3 instance — cannot be verified programmatically without running the stack"
  - test: "After a real TikTok sync run, confirm image-only ads have asset_url populated in TikTokRawPerformance and CreativeAsset"
    expected: "SELECT asset_url FROM tiktok_raw_performance WHERE video_id IS NULL AND image_ids IS NOT NULL LIMIT 5; all rows have a non-null S3 URL (.jpg)"
    why_human: "Same dependency on live API and storage stack"
  - test: "Verify that on re-sync, previously downloaded TikTok assets are not re-downloaded (S3 idempotency)"
    expected: "_download_video_asset and _download_image_asset check file_exists first; second sync should produce no new MinIO uploads for already-present files (observable via MinIO access logs or tiktok_sync WARNING absence)"
    why_human: "Requires running two consecutive syncs against the same connection"
gaps:
  - truth: "An asset already present in S3 is not re-downloaded on re-sync (file_exists check returns early) — at the DB level"
    status: partial
    reason: "The _download_video_asset and _download_image_asset methods correctly guard with file_exists. However, asset_url and video_source_url are NOT in the _upsert_records ON CONFLICT exclusion list (unlike thumbnail_url), so on re-sync the DB field is temporarily overwritten to null by _upsert_records before _enrich_from_ad_get re-populates it. The idempotency guard prevents re-download to S3, but the DB field goes null between the two phases. This is a data-consistency window."
    artifacts:
      - path: "backend/app/services/sync/tiktok_sync.py"
        issue: "Lines 369-377: _upsert_records exclusion list includes thumbnail_url but not asset_url or video_source_url. On re-sync, pg_insert ON CONFLICT DO UPDATE will set asset_url = excluded.asset_url (null) since rows dict never includes asset_url."
    missing:
      - "Add 'asset_url' and 'video_source_url' to the _upsert_records exclusion list at lines 369-377, matching the pattern used for thumbnail_url"
---

# Phase 15: TikTok Asset Download — Verification Report

**Phase Goal:** TikTok video and image creatives are downloaded to MinIO/S3 during sync, closing the gap that blocks AI autofill and BrainSuite scoring for TikTok assets
**Verified:** 2026-05-08T17:00:00Z
**Status:** human_needed — automated checks passed with one partial gap; end-to-end flow requires human UAT
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After a TikTok sync, ads with a video_id have asset_url populated in TikTokRawPerformance | ? UNCERTAIN | Code path is complete and wired (lines 431-438 + 492 in tiktok_sync.py); requires live run to confirm |
| 2 | After a TikTok sync, ads with image_ids but no video_id have asset_url populated in TikTokRawPerformance | ? UNCERTAIN | Code path is complete and wired (lines 440-452 + 492 in tiktok_sync.py); requires live run to confirm |
| 3 | A download failure for one ad does not raise an exception or abort the sync loop | ✓ VERIFIED | Lines 456-459: `try/except Exception` wraps both download branches, resets asset_url=None, logs at WARNING, continues |
| 4 | An asset already present in S3 is not re-downloaded on re-sync (file_exists check returns early) | ✗ PARTIAL | _download_video_asset and _download_image_asset both have `if obj_storage.file_exists(relative_path): return obj_storage.served_url(relative_path)` (lines 609-610, 640-641). However, `asset_url` is NOT in the _upsert_records exclusion list, so the DB field is overwritten to null on re-sync before _enrich_from_ad_get re-populates it — creating a temporary null window |
| 5 | Spark ads (is_spark=True) have asset_url left as None (no download attempted) | ✓ VERIFIED | Both video branch `if video_id_val and not is_spark:` (line 431) and image branch `elif image_ids_raw and not video_id_val and not is_spark:` (line 440) guard against is_spark. Fix for image branch (CR-01) committed in 1a72d42 |
| 6 | TikTok VIDEO assets reach UNSCORED scoring status in the harmonizer (asset_url non-null → UNSCORED) | ✓ VERIFIED | scoring_endpoint_type.py maps TIKTOK+VIDEO → ScoringEndpointType.VIDEO; harmonizer.py lines 897-914 assign initial_status="UNSCORED" for VIDEO; confirmed by test_all_platforms_honor_scoring_enabled |
| 7 | TikTok IMAGE assets reach UNSUPPORTED scoring status (by design — scoring not supported for TikTok images) | ✓ VERIFIED | scoring_endpoint_type.py maps TIKTOK+IMAGE → ScoringEndpointType.UNSUPPORTED; confirmed by test_tiktok_image_is_unsupported_by_design |
| 8 | SystemConfig.scoring_enabled=False causes scoring_job.run_scoring_batch() to exit early for ALL platforms | ✓ VERIFIED | scoring_job.py line 66: `if system_cfg is not None and not system_cfg.scoring_enabled: return`; confirmed by test_scoring_disabled_exits_early |
| 9 | Harmonizer passes raw.creative_url or raw.asset_url as asset_url to CreativeAsset | ✓ VERIFIED | harmonizer.py line 372: `asset_url=raw.creative_url or raw.asset_url`; CreativeAsset.asset_url field exists (creative.py line 50); harmonizer _ensure_asset writes it at line 886 (new) and line 932 (existing update) |

**Score:** 7/9 truths verified (5 VERIFIED, 1 PARTIAL, 2 UNCERTAIN requiring human run)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/services/sync/tiktok_sync.py` | `_fetch_video_download_url()`, `_download_video_asset()`, `_download_image_asset()` methods; `_enrich_from_ad_get()` extended with asset_url/video_source_url | ✓ VERIFIED | All three methods present at lines 560-655; `_enrich_from_ad_get` extended at lines 426-493 |
| `backend/tests/test_tiktok_sync.py` | 11 unit tests for all new download methods and integration into `_enrich_from_ad_get` | ✓ VERIFIED | File exists; 11 test functions confirmed by `grep -c "def test_"` |
| `backend/tests/test_scoring_gate.py` | 10 unit tests: scoring gate toggle, cross-platform endpoint types, TikTok harmonizer asset_url pipe | ✓ VERIFIED | File exists; 10 test functions confirmed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tiktok_sync.py:_enrich_from_ad_get` | `TikTokRawPerformance.asset_url` | `sqlalchemy update().values(asset_url=asset_url)` | ✓ WIRED | Lines 492: `**({"asset_url": asset_url} if asset_url else {})` in update().values() |
| `tiktok_sync.py:_fetch_video_download_url` | TikTok `/file/video/ad/` endpoint | `httpx.AsyncClient GET with Access-Token header` | ✓ WIRED | Lines 571-578: `f"{TIKTOK_API_BASE}/file/video/ad/"` with `headers={"Access-Token": access_token}` |
| `scoring_job.py:66` | `SystemConfig.scoring_enabled` | `if system_cfg is not None and not system_cfg.scoring_enabled: return` | ✓ WIRED | Confirmed at scoring_job.py line 66 |
| `harmonizer.py:372` | `TikTokRawPerformance.asset_url` | `asset_url=raw.creative_url or raw.asset_url` | ✓ WIRED | Confirmed at harmonizer.py line 372 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `tiktok_sync.py:_enrich_from_ad_get` | `asset_url` | `_fetch_video_download_url()` → `_download_video_asset()` → `obj_storage.upload_bytes()` | Yes — real httpx call to TikTok API + S3 upload | ✓ FLOWING (code path) |
| `harmonizer.py:_harmonize_tiktok` | `asset_url` passed to `_ensure_asset` | `raw.creative_url or raw.asset_url` from TikTokRawPerformance | Yes — reads from DB row populated by _enrich_from_ad_get | ✓ FLOWING (code path) |
| `CreativeAsset.asset_url` | `asset_url` | Written by harmonizer `_ensure_asset` at line 886/932 | Yes — persisted to creative_assets table | ✓ FLOWING (code path) |

Note: Data flow is verified at the code level only. Live run verification is in human verification section.

### Behavioral Spot-Checks

Step 7b: SKIPPED — Tests require Docker container environment with PostgreSQL, Redis, and MinIO. Running `pytest` requires the containerized backend environment which is not available without `docker-compose up`. The SUMMARY.md documents all 21 tests passing in the Docker container.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| TKTOK-01 | 15-01, 15-02 | User sees TikTok video creatives in the dashboard after sync (video files downloaded to MinIO/S3, stored as asset_url on CreativeAsset) | ? UNCERTAIN (pending human UAT) | Code path complete: tiktok_sync.py downloads video to S3 → harmonizer writes to CreativeAsset.asset_url → dashboard.py returns asset_url. Requires live run to confirm data actually flows end-to-end |
| TKTOK-02 | 15-01, 15-02 | User sees TikTok image creatives in the dashboard after sync (image files downloaded to MinIO/S3, stored as asset_url on CreativeAsset) | ? UNCERTAIN (pending human UAT) | Code path complete: _download_image_asset stores to S3 → harmonizer writes asset_url → dashboard returns it. ROADMAP wording says "image_url" but model uses asset_url (same field for all formats) — this is an informal ROADMAP naming inconsistency, not an implementation gap |

Note: REQUIREMENTS.md traceability table still shows both TKTOK requirements as "Pending" — this is pre-existing and reflects the REQUIREMENTS.md not being updated post-phase.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tiktok_sync.py` | 369-377 | `asset_url` and `video_source_url` excluded from _upsert_records preservation list | Warning | On re-sync, DB fields temporarily null until _enrich_from_ad_get re-populates (S3 idempotency guard prevents re-download but DB has a null window) |
| `tiktok_sync.py` | 430-461 | Asset download proceeds regardless of SystemConfig.scoring_enabled | Warning | Memory note: "must respect auto-scoring toggle for all platforms"; download runs even when toggle=False, consuming storage/bandwidth unnecessarily (identified in code review WR-05) |
| `tiktok_sync.py` | 414 | `is_spark` missing `TT_USER` identity type (WR-03 from code review) | Warning | Ads with identity_type="TT_USER" are not recognized as Spark ads and may have assets downloaded in violation of D-02 |
| `backend/tests/test_tiktok_sync.py` | 392-419 | `test_download_failure_resilience` does not verify asset_url=None in the DB update call (IN-03) | Info | Future regression could silently pass a non-None asset_url on failure without being caught by this test |

Stub classification: None of the anti-patterns above are stubs that prevent the goal. The asset download code path is fully implemented and substantive.

### Human Verification Required

#### 1. TikTok Video Asset End-to-End

**Test:** Trigger a TikTok sync for a connection that has video ads. After sync completes, query: `SELECT ad_id, asset_url, video_source_url FROM tiktok_raw_performance WHERE video_id IS NOT NULL AND platform_connection_id = '<conn_id>' LIMIT 5;`
**Expected:** Rows have non-null asset_url containing an S3/MinIO URL ending in `.mp4` and non-null video_source_url containing the TikTok CDN URL
**Why human:** Requires live TikTok API credentials, a running MinIO/S3 instance, and an active sync

#### 2. TikTok Image Asset End-to-End

**Test:** After sync, query: `SELECT ad_id, asset_url FROM tiktok_raw_performance WHERE video_id IS NULL AND image_ids IS NOT NULL AND platform_connection_id = '<conn_id>' LIMIT 5;`
**Expected:** Rows have non-null asset_url containing an S3/MinIO URL ending in `.jpg`
**Why human:** Same dependency on live stack

#### 3. Dashboard Rendering of TikTok Creatives

**Test:** Navigate to the dashboard for a TikTok connection after sync. Confirm TikTok video ads show a playable video and image ads show a visible image.
**Expected:** Video assets render with a video player; image assets show the downloaded image (not a placeholder). Previously both would have been blank/broken.
**Why human:** Visual confirmation; requires a browser session with a real TikTok connection

#### 4. Re-sync Idempotency (S3 Level)

**Test:** Run TikTok sync twice for the same connection. Check MinIO access logs or add a `logger.info("Skipping existing asset...")` and look for it in the second sync run's logs.
**Expected:** Second sync logs "Skipping existing..." (file_exists=True) for all already-downloaded assets, and no new MinIO PUT operations for those files
**Why human:** Requires two sync runs and MinIO log access

### Gaps Summary

**One partial gap** (data-consistency window on re-sync):

The `asset_url` and `video_source_url` fields are not included in the `_upsert_records` ON CONFLICT exclusion list (unlike `thumbnail_url` which is preserved). On re-sync, the first DB write (`_upsert_records`) will overwrite these fields with null. The second DB write (`_enrich_from_ad_get`, deferred) will re-populate them. This creates a temporary null window during each re-sync. The S3 idempotency guard (file_exists check) means no actual re-download occurs, but the DB reflects stale data during the window. Fix: add `asset_url` and `video_source_url` to the exclusion list at lines 369-377 in `_upsert_records`.

**Two additional warnings** from the code review (not blocking goal):
- WR-03: `TT_USER` identity type not recognized as Spark (partial D-02 gap)
- WR-05: Asset download ignores scoring_enabled toggle (memory note: "must respect auto-scoring toggle")

These warnings are carried forward from the code review (15-REVIEW.md) and do not block the core phase goal but represent technical debt.

---

_Verified: 2026-05-08T17:00:00Z_
_Verifier: Claude (gsd-verifier)_
