---
phase: quick
plan: 260407-lxk
subsystem: sync-pipeline / creative-assets / dashboard
tags: [migration, harmonizer, backfill, dimensions, media-metrics]
dependency_graph:
  requires: []
  provides: [width-height-on-creative-assets, media-metrics-backfill-endpoint]
  affects: [dashboard-asset-detail, scoring-pipeline, platform-harmonizers]
tech_stack:
  added: []
  patterns: [Pillow image dimension extraction, imageio_ffmpeg video metadata, BackgroundTasks backfill pattern]
key_files:
  created:
    - backend/alembic/versions/q8r9s0t1u2v3_add_width_height_to_creative_assets.py
  modified:
    - backend/app/models/creative.py
    - backend/app/services/sync/harmonizer.py
    - backend/app/services/sync/dv360_sync.py
    - backend/app/services/sync/scoring_job.py
    - backend/app/api/v1/endpoints/scoring.py
    - backend/app/schemas/creative.py
    - backend/app/api/v1/endpoints/dashboard.py
    - frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts
decisions:
  - "DV360 width/height derived from existing asset_format string (e.g. '640x480') in harmonizer — avoids raw model migration"
  - "Backfill skips external CDN URLs heuristically (checks for '://' in URL or non-creatives/ path) — expired Meta/TikTok tokens would 404"
  - "TikTok: video_duration_sec forwarded; no width/height in raw model — skip dimensions for TikTok (no file download path)"
  - "Google Ads: video_duration already passed as raw.video_duration; no width/height available from API"
metrics:
  duration: ~25 minutes
  completed_at: "2026-04-07T14:03:33Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 8
  files_created: 1
---

# Quick Task 260407-lxk: Fix Missing Asset Media Metrics — Add Duration + Dimensions Summary

**One-liner:** Added width/height Integer columns to creative_assets via Alembic, wired dimension/duration extraction through all 4 platform harmonizers using already-available raw data, added admin backfill endpoint using BackgroundTasks, and exposed fields in dashboard asset detail dialog.

## Tasks Completed

| Task | Name | Commit | Status |
|------|------|--------|--------|
| 1 | Migration + model + harmonizer wiring for all 4 platforms | 7ca21ae | Done |
| 2 | Backfill endpoint + API/frontend exposure | f07b9ba | Done |

## What Was Built

### Task 1 — Migration + Model + Harmonizer

- **Alembic migration** `q8r9s0t1u2v3`: adds `width INTEGER NULL` and `height INTEGER NULL` to `creative_assets` table. Down revision from `p7q8r9s0t1u2`. Migration confirmed run clean.
- **CreativeAsset model**: `width: Mapped[Optional[int]]` and `height: Mapped[Optional[int]]` added after `video_duration`.
- **`_ensure_asset()` new-asset block**: passes `width=kwargs.get("width"), height=kwargs.get("height")` to the constructor.
- **`_ensure_asset()` update block**: backfills `width`, `height`, and `video_duration` on existing assets that lack them (no-overwrite pattern).
- **`_harmonize_meta()`**: now forwards `width=raw.creative_width_px, height=raw.creative_height_px, video_duration=raw.video_length_sec` — these were already available in `MetaRawPerformance` but not forwarded.
- **`_harmonize_tiktok()`**: now forwards `video_duration=raw.video_duration_sec` — no width/height available in TikTok raw model.
- **Google Ads**: `video_duration=raw.video_duration` was already passed at line 536 — no change needed.
- **`_harmonize_dv360()`**: parses `width`/`height` from `row.asset_format` string (e.g. `"640x480"`) using a try/except `split("x", 1)`. No raw model migration required.
- **`dv360_sync._fetch_creatives()`**: added `width_pixels` and `height_pixels` to the creative dict (for future use via `entity_maps.creatives`).

### Task 2 — Backfill + API + Frontend

- **`run_media_metrics_backfill()`** in `scoring_job.py`:
  - Queries `creative_assets WHERE width IS NULL OR height IS NULL`.
  - Downloads files from internal S3/MinIO storage using `get_object_storage().download_blob()`.
  - Skips assets with no `asset_url` or external CDN URLs (heuristic: `://` in URL without `creatives/` key).
  - Extracts image dimensions via `PIL.Image.open(io.BytesIO(bytes)).size`.
  - Extracts video dimensions + duration via `imageio_ffmpeg.read_frames(tmp_path)` with proper `reader.close()` in `finally`.
  - Commits every 50 assets, logs summary on completion.
- **`POST /scoring/admin/backfill-media-metrics`**: admin-only endpoint, returns 202 immediately, queues backfill as `BackgroundTask`.
- **`CreativeAssetResponse` schema**: `width: Optional[int] = None` and `height: Optional[int] = None` added after `video_duration`.
- **`dashboard.py get_asset_detail()`**: `"width": asset.width, "height": asset.height` added to response dict.
- **Frontend dialog**: `width?: number | null` and `height?: number | null` added to `AssetDetailResponse` interface; `<span class="perf-dimension" *ngIf="detail?.width && detail?.height">` renders e.g. `"1920x1080"` with same styling as `.perf-duration`.

## Deviations from Plan

### Auto-fixed / Adjusted

**1. [Rule 2 - Missing Functionality] DV360 width/height derived from asset_format string rather than raw model**
- **Found during:** Task 1 investigation
- **Issue:** The plan said to add `width_pixels`/`height_pixels` to the DV360 raw dict in `_upsert_records`, but `entity_maps.creatives` is never accessed in `_upsert_records` — the creatives dict is stored in `EntityMaps` but unused in the data pipeline. Adding new columns to `Dv360RawPerformance` would require another migration.
- **Fix:** Parse existing `row.asset_format` string ("640x480") in the DV360 harmonizer path — zero migration cost, no raw model change needed.
- **Files modified:** `harmonizer.py` only

**2. [Observation] Google Ads video_duration already passed; no width/height available**
- **Found during:** Task 1
- **Issue:** `GoogleAdsRawPerformance.video_duration` exists and is already passed at harmonizer line 536. The Google Ads sync never populates it (no matching field in the sync's row dict), so it remains NULL for all assets. No width/height is available from the API.
- **Fix:** No change needed — the existing pass-through handles the field correctly. Noted for reference.

## Known Stubs

None — all fields are fully wired. Dimensions will be NULL for existing assets until the backfill endpoint is called, and for TikTok/Google Ads going forward (no dimension data available in those platform APIs).

## Verification Results

1. **Migration**: ran clean — `alembic upgrade head` output confirmed `p7q8r9s0t1u2 -> q8r9s0t1u2v3`.
2. **Model columns**: `'width' in CreativeAsset.__table__.columns` → `True`.
3. **Schema**: `CreativeAssetResponse.model_fields` contains `width` and `height` with `None` defaults.
4. **Frontend build**: `ng build --configuration=production` succeeded with no errors (pre-existing warnings only).

## Self-Check: PASSED

All key files confirmed present. Both commits (7ca21ae, f07b9ba) confirmed in git log.
