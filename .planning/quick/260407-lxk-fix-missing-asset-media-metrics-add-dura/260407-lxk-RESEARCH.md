# Quick Task: Fix Missing Asset Media Metrics — Research

**Researched:** 2026-04-07
**Domain:** SQLAlchemy/Alembic, asset sync pipeline, media extraction (Pillow, imageio-ffmpeg)
**Confidence:** HIGH

---

## Summary

`CreativeAsset` already has `video_duration` but is missing `width` and `height` columns. These two columns must be added via Alembic migration, populated during import in all four platform sync paths, and backfilled for existing assets via an admin endpoint (matching the established `POST /scoring/admin/backfill` pattern using `BackgroundTasks`).

Both extraction libraries are already installed and actively used in the codebase — no new dependencies required. The extraction path for images uses `PIL.Image.open()` and for videos uses `imageio_ffmpeg.read_frames()`, both already live in `ai_autofill.py`.

**Primary recommendation:** Add `width`/`height` Integer columns to `creative_assets` via Alembic; extract dimensions from the already-downloaded local bytes at import time; backfill via new admin endpoint with `BackgroundTasks`.

---

## Current State Inventory

### What already exists on `CreativeAsset` (creative.py)

| Column | Type | Notes |
|--------|------|-------|
| `video_duration` | `Float`, nullable | Already present — populated in harmonizer |
| `width` | — | **MISSING** — needs migration |
| `height` | — | **MISSING** — needs migration |

### Duration data already available in raw models

| Platform | Raw model field | Passed to harmonizer? |
|----------|---------------|-----------------------|
| Meta | `MetaRawPerformance.video_length_sec` | NO — not passed in `_ensure_asset` kwargs |
| TikTok | `TikTokRawPerformance.video_duration_sec` | NO — not passed in `_ensure_asset` kwargs |
| Google Ads | `GoogleAdsRawPerformance.video_duration_millis` | NO |
| DV360 | `Dv360RawPerformance.video_duration_seconds` | YES — via `raw.video_duration` |

Meta raw also has `creative_width_px` / `creative_height_px` already populated from API. These are also not forwarded to `CreativeAsset`. TikTok has no width/height in raw model.

### Key finding: Meta already has width/height in raw table

`MetaRawPerformance.creative_width_px` and `creative_height_px` are populated by the Meta Graph API (fields `url,url_128,width,height,name` are requested in `_get_full_image_url`). Harmonizer currently ignores them. For Meta, these fields can be forwarded directly from raw — no file download needed.

---

## Architecture Patterns

### Migration pattern (from recent migrations)

Latest head revision: `p7q8r9s0t1u2` (add pending_at/submitted_at to score results).

Pattern: `op.add_column` with `server_default=sa.null()` (nullable columns, no server default needed).

```python
# New migration: q8r9s0t1u2v3_add_width_height_to_creative_assets.py
revision = "q8r9s0t1u2v3"
down_revision = "p7q8r9s0t1u2"

def upgrade() -> None:
    op.add_column("creative_assets", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("creative_assets", sa.Column("height", sa.Integer(), nullable=True))

def downgrade() -> None:
    op.drop_column("creative_assets", "height")
    op.drop_column("creative_assets", "width")
```

No backfill inside the migration. The migration is additive/non-breaking — new columns default to NULL.

### Extraction approach

**Images — use Pillow (already in use in meta_sync.py line 1062):**
```python
from PIL import Image
img = Image.open(io.BytesIO(image_bytes))
width, height = img.size  # tuple (w, h)
```

**Videos — use imageio_ffmpeg (already in use in ai_autofill.py line 491):**
```python
import imageio_ffmpeg
reader = imageio_ffmpeg.read_frames(tmp_path)
meta = next(reader)  # first yield is metadata dict
width, height = meta["size"]   # (w, h) in pixels
duration = meta.get("duration")  # float, seconds
reader.close()
```

This is the exact pattern already used in `_extract_key_frames()` in `ai_autofill.py`. Reuse or extract a shared helper.

**DV360 already has `_get_video_duration()` using `ffprobe` subprocess** — but this calls system `ffprobe`, not `imageio_ffmpeg`. For consistency, prefer `imageio_ffmpeg.read_frames()` which is already bundled.

### Where to inject extraction

The canonical asset creation path is `harmonizer._ensure_asset()` (line 848). It accepts `**kwargs` and sets `video_duration=kwargs.get("video_duration")`. The two new columns must be added here:

```python
# in CreativeAsset constructor block:
width=kwargs.get("width"),
height=kwargs.get("height"),

# in update block (existing asset):
if kwargs.get("width") and not asset.width:
    asset.width = kwargs.get("width")
if kwargs.get("height") and not asset.height:
    asset.height = kwargs.get("height")
```

### Per-platform extraction points

**Meta** — Dimensions are already in `MetaRawPerformance.creative_width_px` / `creative_height_px` / `video_length_sec`. Harmonizer's `_harmonize_meta()` can forward these directly:
```python
asset = await self._ensure_asset(
    ...
    width=raw.creative_width_px,
    height=raw.creative_height_px,
    video_duration=raw.video_length_sec or raw_video_duration,  # fix existing gap
)
```

**TikTok** — No dimensions in raw model. File bytes are available at download time in TikTok sync (if a creative_url is present). Extract at download via Pillow/imageio_ffmpeg and store in raw model OR extract from `asset_url` bytes during harmonization. Simplest: extract after downloading during creative enrichment and write to `TikTokRawPerformance` or pass directly.

**Google Ads** — `GoogleAdsRawPerformance.video_duration_millis` exists; convert to seconds: `millis / 1000.0`. No width/height in raw model — extract from downloaded video file in `google_ads_sync._upsert_records()` (where `_download_video` already runs). Use `imageio_ffmpeg.read_frames()` on the local file before upload.

**DV360** — `video_duration_seconds` already forwarded. Width/height: the DV360 sync already reads `widthPixels`/`heightPixels` from the API response (lines 515–518) but only uses them to build an `asset_format` string like `"640x480"`. Parse this string or forward the raw pixel values to the raw model and then to harmonizer.

### Backfill approach

Follow the existing pattern from `POST /scoring/admin/backfill`:
- New endpoint: `POST /scoring/admin/backfill-media-metrics`
- Uses `Depends(get_current_admin)` guard
- Queues a `BackgroundTasks` function, returns 202
- Background function: iterate `creative_assets` where `width IS NULL OR height IS NULL`, fetch bytes from `asset_url` (S3 presigned URL), extract dimensions, update row

**Critical pitfall for backfill:** Assets may have `asset_url` pointing to S3/MinIO (served URL) or a remote platform CDN URL. Platform CDN URLs expire — Meta/TikTok CDN URLs typically have short-lived tokens. For backfill, prefer reading from object storage (MinIO/S3) where the file was already saved. Use `get_object_storage().get_file_bytes(key)` if the asset was uploaded, else skip with `None`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Image dimensions | PIL parsing | `PIL.Image.open(bytes).size` | Already in meta_sync.py |
| Video dimensions + duration | Custom ffmpeg subprocess | `imageio_ffmpeg.read_frames(path)` — `meta["size"]`, `meta["duration"]` | Already used in ai_autofill.py |
| Video duration via ffprobe subprocess | Custom subprocess | `imageio_ffmpeg.read_frames()` | Avoids system ffprobe dependency; bundled binary |

---

## Common Pitfalls

### Pitfall 1: Expired remote URLs during backfill
**What goes wrong:** `asset_url` for Meta/TikTok creatives contains CDN URLs with embedded expiry tokens. Fetching these during backfill returns 403/404.
**How to avoid:** Check whether the URL is an internal S3/MinIO URL first (`asset_url.startswith(settings.MINIO_ENDPOINT)` or object storage domain). If internal, download via boto3 `get_object`. If external/expired, skip and log — do not fail the entire backfill.

### Pitfall 2: imageio_ffmpeg reader not closed
**What goes wrong:** `read_frames()` returns a generator; if you only `next()` the metadata frame and abandon the generator, the underlying process may leak.
**How to avoid:** Call `reader.close()` explicitly in a try/finally block after reading the metadata frame, or use: `meta = next(reader); reader.close()`.

### Pitfall 3: DV360 format string parsing
**What goes wrong:** DV360 already builds `asset_format = f"{w}x{h}"` but this is not stored in raw model — it's computed inline and only used as a string for `asset_format`. Width/height ints are discarded.
**How to avoid:** Store `w` and `h` in the DV360 raw dict (add `width_pixels`/`height_pixels` fields to the raw row dict passed through `_upsert_records`) before they're discarded.

### Pitfall 4: video_duration not forwarded for Meta/TikTok/Google Ads
**What goes wrong:** Meta raw has `video_length_sec`, TikTok has `video_duration_sec`, Google Ads has `video_duration_millis` — but harmonizer does not pass these to `_ensure_asset`. So `CreativeAsset.video_duration` is NULL for 3 of 4 platforms.
**How to avoid:** Fix these gaps in the same task, since the same harmonizer `_ensure_asset` call needs to be updated anyway.

---

## Implementation Checklist (for planner)

1. Alembic migration: add `width Integer nullable`, `height Integer nullable` to `creative_assets`
2. `CreativeAsset` model: add `width` and `height` `Mapped[Optional[int]]` fields
3. `harmonizer._ensure_asset()`: accept `width`/`height` kwargs, set on new asset and update on existing
4. `_harmonize_meta()`: forward `raw.creative_width_px`, `raw.creative_height_px`, `raw.video_length_sec`
5. `_harmonize_tiktok()`: extract dimensions from downloaded bytes (at TikTok creative fetch time) and forward
6. `_harmonize_google_ads()`: convert `video_duration_millis` → seconds; extract W/H from downloaded video
7. DV360 sync: store `widthPixels`/`heightPixels` in raw dict instead of discarding them
8. New admin endpoint `POST /scoring/admin/backfill-media-metrics` + `BackgroundTasks` function
9. Backfill function: skip assets with no `asset_url`; handle S3 vs expired CDN URLs; use imageio_ffmpeg for video, Pillow for image

---

## Sources

### Primary (HIGH confidence)
- Codebase direct read: `backend/app/models/creative.py` — confirmed `video_duration` exists, `width`/`height` absent
- Codebase direct read: `backend/app/models/performance.py` — confirmed `MetaRawPerformance.creative_width_px/height/video_length_sec`; `TikTokRawPerformance.video_duration_sec`; `GoogleAdsRawPerformance.video_duration_millis`; `Dv360RawPerformance.video_duration_seconds`
- Codebase direct read: `backend/app/services/ai_autofill.py` — confirmed `imageio_ffmpeg.read_frames()` usage with `meta["size"]` (lines 491–494)
- Codebase direct read: `backend/app/services/sync/harmonizer.py` — confirmed `_ensure_asset()` pattern and kwarg forwarding; confirmed DV360 is the only platform forwarding `video_duration`
- Codebase direct read: `backend/requirements.txt` — confirmed `imageio-ffmpeg>=0.5.1` and `Pillow>=10.0.0` installed
- Codebase direct read: last migration `p7q8r9s0t1u2` — confirmed `down_revision` is the current head

**Research date:** 2026-04-07
**Valid until:** 2026-05-07 (stable codebase)
