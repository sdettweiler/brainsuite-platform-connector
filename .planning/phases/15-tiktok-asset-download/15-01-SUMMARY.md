---
phase: 15-tiktok-asset-download
plan: "01"
subsystem: tiktok-sync
tags:
  - tiktok
  - asset-download
  - s3
  - sync-pipeline
  - tdd
dependency_graph:
  requires:
    - "backend/app/services/object_storage.py (upload_bytes, file_exists, served_url)"
    - "backend/app/services/sync/tiktok_sync.py (_fetch_cover_image_url, _download_tiktok_thumbnail patterns)"
    - "backend/app/models/performance.py (TikTokRawPerformance.asset_url, video_source_url)"
  provides:
    - "_fetch_video_download_url() — fetches TikTok video download URL via /file/video/ad/"
    - "_download_video_asset() — downloads video bytes to S3 at creatives/{org_id}/video_tiktok_{ad_id}.mp4"
    - "_download_image_asset() — downloads full-res image bytes to S3 at creatives/{org_id}/image_tiktok_{ad_id}.jpg"
    - "_enrich_from_ad_get() extended — populates asset_url + video_source_url on TikTokRawPerformance"
  affects:
    - "TikTok sync pipeline — asset_url now populated after each ad enrichment"
    - "AI autofill (Gemini/Whisper) — now has TikTok asset_url to process"
    - "BrainSuite scoring — TikTok assets now reach UNSCORED status"
tech_stack:
  added: []
  patterns:
    - "Non-fatal download with try/except (httpx.RequestError, httpx.HTTPStatusError, OSError) pattern"
    - "File existence check before download (file_exists idempotency guard)"
    - "Conditional values dict (**(dict) if value else {}) for SQLAlchemy update"
    - "TDD RED/GREEN cycle with 11 unit tests"
key_files:
  created:
    - path: backend/tests/test_tiktok_sync.py
      description: "11 unit tests covering _fetch_video_download_url, _download_video_asset, _download_image_asset, and _enrich_from_ad_get resilience"
  modified:
    - path: backend/app/services/sync/tiktok_sync.py
      description: "Added three new async methods and extended _enrich_from_ad_get to populate asset_url and video_source_url"
decisions:
  - "D-01: Use TikTok API /file/video/ad/ for video download — consistent with existing /file/image/ad/ pattern, no anti-scraping risk"
  - "D-02: Spark ads (identity_type CUSTOMIZED_USER or AUTH_CODE) skip download, asset_url stays None"
  - "D-03: Image-only ads (image_ids without video_id) download full-res image to asset_url via _download_image_asset"
  - "D-04: Inline download during _enrich_from_ad_get; failures are non-fatal, logged at WARNING"
  - "D-06: asset_url = S3 served URL for scoring/autofill input; video_source_url = raw TikTok CDN URL"
metrics:
  duration: "271 seconds (4 minutes)"
  completed_date: "2026-05-08"
  tasks_completed: 2
  files_modified: 2
---

# Phase 15 Plan 01: TikTok Asset Download — Implementation Summary

**One-liner:** Three new async download methods on TikTokSyncService plus _enrich_from_ad_get extension that populates asset_url and video_source_url on TikTokRawPerformance using the TikTok /file/video/ad/ API and S3 upload.

## What Was Built

Closed the TikTok asset gap that blocked AI autofill (Gemini/Whisper) and BrainSuite scoring. TikTok sync was leaving `asset_url` null on `TikTokRawPerformance`; after this plan, video ads populate `asset_url` with an S3-served `.mp4` URL and image-only ads populate it with an S3-served `.jpg` URL.

### New Methods on TikTokSyncService

1. **`_fetch_video_download_url(access_token, advertiser_id, video_ids)`**
   - GET `https://business-api.tiktok.com/open_api/v1.3/file/video/ad/`
   - Returns `data.list[0].video_url` or None on API error (code != 0) or HTTP error
   - Pattern: exact replica of existing `_fetch_cover_image_url` for `/file/image/ad/`

2. **`_download_video_asset(url, org_id, ad_id)`**
   - Storage path: `creatives/{org_id}/video_tiktok_{ad_id}.mp4`
   - File existence check prevents re-download on re-sync
   - httpx timeout=60s, follow_redirects=True (CDN redirect handling)
   - Non-fatal: catches `(httpx.RequestError, httpx.HTTPStatusError, OSError)` → log + return None

3. **`_download_image_asset(image_url, org_id, ad_id)`**
   - Storage path: `creatives/{org_id}/image_tiktok_{ad_id}.jpg`
   - 100-byte minimum size check prevents storing broken responses
   - httpx timeout=30s, follow_redirects=True
   - Non-fatal: same exception handling as video download

### `_enrich_from_ad_get` Extension

After the thumbnail block, new asset download block:
- Video ads (`video_id_val` present, `is_spark=False`): fetch URL → download → set `asset_url` + `video_source_url`
- Image-only ads (`image_ids_raw` present, no `video_id`): fetch cover URL → download → set `asset_url`
- Spark ads: skip both branches (asset_url stays None — D-02)
- Entire block wrapped in `try/except Exception` — per-ad failure cannot abort the sync loop
- `asset_url` and `video_source_url` added to `update(TikTokRawPerformance).values(...)` using conditional dict pattern

## TDD Gate Compliance

- RED commit `4c357d2`: `test(15-01)` — 11 failing tests (AttributeError: methods don't exist)
- GREEN commit `89a5aa3`: `feat(15-01)` — all 11 tests pass

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 (RED) | `4c357d2` | `test(15-01): add failing test scaffold for TikTok asset download` |
| 2 (GREEN) | `89a5aa3` | `feat(15-01): implement TikTok video and image asset download` |

## Test Results

- `backend/tests/test_tiktok_sync.py`: **11/11 passed**
- No regressions introduced in the tests relevant to our changes
- Pre-existing failures noted: `test_openai_api_key_defaults_to_none` (real API key in container env), `test_refresh_reads_cookie_only` (MagicMock JSON serialization), `test_backfill_query_filters` (async decorator). None related to this plan.

## Deviations from Plan

None — plan executed exactly as written. All three methods implemented with the exact signatures and behavior specified in the plan. `_enrich_from_ad_get` extended per the pattern map. All 11 tests pass.

## Known Stubs

None — all new methods are fully wired. `asset_url` flows from TikTok API → S3 → `TikTokRawPerformance.asset_url` → harmonizer (downstream, handled by existing code).

## Threat Flags

No new threat surface introduced beyond what the plan's `<threat_model>` covers:
- T-15-01 mitigated: `code == 0` check before reading `video_url`; null-check on `videos` list
- T-15-02 mitigated: 60s timeout on video download
- T-15-03 mitigated: `access_token` in header only (not URL params)
- T-15-04 accepted: `org_id` is UUID from `connection.organization_id` — not user-controlled
- T-15-05 accepted: Spark ad bypass leaves `asset_url=None` — safe default

## Self-Check

Files created/modified:
- `backend/tests/test_tiktok_sync.py` — exists (committed in 4c357d2)
- `backend/app/services/sync/tiktok_sync.py` — modified (committed in 89a5aa3)

Commits verified:
- 4c357d2: test(15-01) — RED phase
- 89a5aa3: feat(15-01) — GREEN phase

## Self-Check: PASSED
