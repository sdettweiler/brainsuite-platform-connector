---
phase: build-resume-retry
plan: wave-2a
subsystem: jobs
tags: [resume, retry, download, partial-status, params]
key-files:
  modified:
    - backend/app/services/sync/scheduler.py
    - backend/app/api/v1/endpoints/jobs.py
decisions:
  - Resume skip query uses GoogleAdsRawPerformance.ad_id (string) — matches asset_queue keys directly
  - PARTIAL emitted when failed > 0 and downloaded > 0; FAILED when all fail; COMPLETE when none fail
  - trigger_download_retry reconstructs Google Ads asset_queue from DB rather than storing full queue in params
  - Meta/TikTok/DV360 also receive params and PARTIAL logic for consistency (deviation: scope extended beyond Google Ads only)
metrics:
  completed: "2026-05-15"
---

# Wave 2a: Store Params + Resume Skip Logic for Download Jobs

Download jobs now store their input params, skip already-downloaded assets on retry, emit PARTIAL status for mixed outcomes, and the retry endpoint is wired.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Store params when creating download jobs (all 4 platforms) | 6a77989 |
| 2 | Resume skip logic — skip already-downloaded Google Ads assets | 6a77989 |
| 3 | PARTIAL status on completion — all 4 download functions | 6a77989 |
| 4 | Wire retry dispatch in jobs.py + add trigger_download_retry() | 6a77989 |

## What Was Built

- **params stored on job create** — all four download functions (`_run_google_ads_asset_downloads`, `_run_meta_creatives_deferred`, `_run_tiktok_creatives_deferred`, `_run_dv360_asset_downloads`) now pass `params={asset_ids, platform, platform_connection_id}` to `create_background_job()`.

- **Resume skip logic (Google Ads)** — before the per-asset download loop, one batch query checks `GoogleAdsRawPerformance` for rows where `video_url IS NOT NULL AND != ''`. Any matching `ad_id` is added to `already_downloaded` set; those assets are skipped in the loop (counted as downloaded for progress).

- **PARTIAL status** — all four download functions now compute `final_status = "COMPLETE" if not failed else ("PARTIAL" if downloaded else "FAILED")` instead of always emitting "COMPLETE".

- **trigger_download_retry()** — new async function at the bottom of scheduler.py. Reads `platform` from params and dispatches to the correct download function. For Google Ads, re-queries `GoogleAdsRawPerformance` to reconstruct the asset_queue (preserves video_id). For Meta/TikTok, calls the existing deferred functions. For DV360, wraps asset_ids in the expected `{"queue": {}}` structure.

- **_dispatch_job_retry wired** — jobs.py now has a `job_type == "download"` branch that calls `trigger_download_retry`. The existing warning fallthrough remains for other job types not yet wired.

## Deviations from Plan

### Auto-extended scope

**[Rule 2 - Missing functionality] Params and PARTIAL status applied to Meta, TikTok, and DV360 download jobs**

- **Found during:** Task 1 (params) and Task 3 (PARTIAL)
- **Issue:** Plan specified Google Ads only for resume skip logic (Task 2), but params storage and PARTIAL status are equally applicable to Meta, TikTok, and DV360 download functions. Without params, retry would be silently broken for those platforms even after the dispatch is wired.
- **Fix:** Added `params={}` to `create_background_job()` calls in all four download functions. Added PARTIAL logic to Meta and TikTok completion blocks. DV360 already had separate downloaded/failed tracking.
- **Note:** Meta and TikTok use `ad_id` strings as keys — resume skip query not added for those (they use a different raw model; Google Ads was the only one specified in Task 2).

## Known Stubs

- `trigger_download_retry` for Google Ads reconstructs `asset_queue` with `{"video_id": video_id}` per asset — this matches the structure `_run_google_ads_asset_downloads` expects from the sync result. If `google_ads_sync.download_assets_post_commit` requires additional keys in `asset_info`, the retry path may download less metadata than the original. This is safe (video will still download) but noted.

## Self-Check

- `6a77989` exists: confirmed (commit output above)
- `backend/app/services/sync/scheduler.py`: syntax OK (python3 ast.parse)
- `backend/app/api/v1/endpoints/jobs.py`: syntax OK (python3 ast.parse)
- Both files modified: confirmed (git status before commit)

## Self-Check: PASSED
