# Phase 15: TikTok Asset Download - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 1 (modified)
**Analogs found:** 2 / 1 (TikTok thumbnail + Meta video download)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/services/sync/tiktok_sync.py` | service | CRUD + file-I/O | `backend/app/services/sync/meta_sync.py` (video download) + `backend/app/services/sync/tiktok_sync.py` (thumbnail pattern) | exact |

## Pattern Assignments

### `backend/app/services/sync/tiktok_sync.py` (service, CRUD + file-I/O)

**Primary Analog:** `backend/app/services/sync/tiktok_sync.py` (existing thumbnail pattern)
**Secondary Analog:** `backend/app/services/sync/meta_sync.py` (video/image download reference)

#### Imports Pattern (lines 1-17)

The file already has all necessary imports. No new imports required:

```python
import asyncio
import httpx
import logging
import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import TikTokRawPerformance
from app.core.security import decrypt_token

logger = logging.getLogger(__name__)
```

#### Method 1: Fetch Video Download URL Pattern (NEW METHOD)

**Analog:** `backend/app/services/sync/tiktok_sync.py` lines 493-520 (`_fetch_cover_image_url` pattern)

**Core Pattern** — Replicate for `/file/video/ad/` endpoint:

```python
async def _fetch_video_download_url(
    self,
    access_token: str,
    advertiser_id: str,
    video_ids: List[str],
) -> Optional[str]:
    """Fetch the video download URL for given video ID via /file/video/ad/."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{TIKTOK_API_BASE}/file/video/ad/",
                params={
                    "advertiser_id": advertiser_id,
                    "video_ids": json.dumps([str(vid) for vid in video_ids]),
                },
                headers={"Access-Token": access_token},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                logger.warning("TikTok /file/video/ad/ error: %s", data.get("message"))
                return None
            videos = data.get("data", {}).get("list", [])
            if videos:
                return videos[0].get("video_url")
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.warning("Failed to fetch TikTok video URL: %s", e)
    return None
```

**Key deviations from thumbnail pattern:**
- HTTP timeout: 30s (same as image fetch)
- Params: `video_ids` instead of `image_ids` (API consistency)
- Response field: `video_url` instead of `image_url` (assumed)
- Error handling: Non-fatal, returns None on any failure

#### Method 2: Download Video Asset Pattern (NEW METHOD)

**Analog:** `backend/app/services/sync/meta_sync.py` lines 1012-1060 (`_download_asset` pattern)

**Core Pattern** — Download bytes and upload to S3:

```python
async def _download_video_asset(
    self,
    url: str,
    org_id: str,
    ad_id: str,
) -> Optional[str]:
    """Download a TikTok video from URL, upload to S3. Returns served URL or None."""
    from app.services.object_storage import get_object_storage
    obj_storage = get_object_storage()

    filename = f"video_tiktok_{ad_id}.mp4"
    relative_path = f"creatives/{org_id}/{filename}"

    if obj_storage.file_exists(relative_path):
        return obj_storage.served_url(relative_path)

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        served_url = obj_storage.upload_bytes(resp.content, relative_path, content_type="video/mp4")
        logger.info("Downloaded TikTok video for ad %s: %s (%d bytes)", ad_id, filename, len(resp.content))
        return served_url

    except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
        logger.warning("Failed to download TikTok video for ad %s: %s", ad_id, e, exc_info=True)
        return None
```

**Key design decisions:**
- **File existence check first** (line 535-536 from `_download_tiktok_thumbnail`): Prevents re-downloading on re-sync
- **HTTP timeout: 60s** (meta_sync.py line 1038): Longer than image/thumbnail (30s) to allow video transfer
- **follow_redirects=True** (meta_sync.py line 1038): Handle CDN redirects for video URLs
- **Non-fatal errors** (meta_sync.py lines 1058-1060): Log warning and return None; do NOT abort sync
- **Content-type header** (meta_sync.py line 1053-1054): Use `video/mp4` for consistency; could be inferred from response headers if needed
- **Storage path convention** (line 534): `creatives/{org_id}/video_tiktok_{ad_id}.mp4` (matches `thumb_tiktok_{ad_id}.jpg` pattern)

#### Method 3: Download Image Asset Pattern (NEW METHOD)

**Analog:** `backend/app/services/sync/tiktok_sync.py` lines 522-549 (`_download_tiktok_thumbnail` pattern)

**Core Pattern** — Reuse for full-resolution images:

```python
async def _download_image_asset(
    self,
    image_url: str,
    org_id: str,
    ad_id: str,
) -> Optional[str]:
    """Download a TikTok full-resolution image and upload to S3. Returns served URL or None."""
    from app.services.object_storage import get_object_storage
    obj_storage = get_object_storage()

    filename = f"image_tiktok_{ad_id}.jpg"
    relative_path = f"creatives/{org_id}/{filename}"

    if obj_storage.file_exists(relative_path):
        return obj_storage.served_url(relative_path)

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
        if len(resp.content) < 100:
            logger.warning("TikTok image for ad %s too small (%d bytes), skipping", ad_id, len(resp.content))
            return None
        served_url = obj_storage.upload_bytes(resp.content, relative_path, content_type="image/jpeg")
        logger.info("Downloaded TikTok image for ad %s: %s (%d bytes)", ad_id, filename, len(resp.content))
        return served_url
    except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
        logger.warning("Failed to download TikTok image for ad %s: %s", ad_id, e, exc_info=True)
        return None
```

**Key deviations from `_download_tiktok_thumbnail`:**
- Filename: `image_tiktok_{ad_id}.jpg` (distinguish from thumbnail which is `thumb_tiktok_{ad_id}.jpg`)
- Purpose: Full-resolution image for AI autofill/scoring (not just dashboard preview)
- Minimal size check (100 bytes): Prevent storing broken/corrupt images
- Content-type: `image/jpeg` (matches thumbnail); could be content-type header negotiation if needed

#### Integration into `_enrich_from_ad_get()` (MODIFIED METHOD)

**Analog:** `backend/app/services/sync/tiktok_sync.py` lines 386-462 (integration point)

**Current code structure** (lines 420-456):

```python
# EXISTING THUMBNAIL LOGIC (lines 420-424)
thumbnail_url: Optional[str] = None
if isinstance(image_ids_raw, list) and image_ids_raw:
    cover_url = await self._fetch_cover_image_url(access_token, advertiser_id, image_ids_raw[:1])
    if cover_url:
        thumbnail_url = await self._download_tiktok_thumbnail(cover_url, org_id, ad_id)

# EXISTING UPDATE STATEMENT (lines 426-457)
await db.execute(
    update(TikTokRawPerformance)
    .where(
        TikTokRawPerformance.ad_id == ad_id,
        TikTokRawPerformance.platform_connection_id == connection.id,
    )
    .values(
        # ... other fields (campaign_id, ad_name, etc.) ...
        **({"thumbnail_url": thumbnail_url} if thumbnail_url else {}),
    )
)
```

**Insertion point** (after thumbnail logic, before update statement):

```python
# NEW: Download video asset for video ads
asset_url: Optional[str] = None
video_source_url: Optional[str] = None

if video_id_val and not is_spark:  # Skip Spark ads for now (D-02)
    video_url = await self._fetch_video_download_url(access_token, advertiser_id, [str(video_id_val)])
    if video_url:
        asset_url = await self._download_video_asset(video_url, org_id, ad_id)
        video_source_url = video_url  # Optional: store API URL for reference

# NEW: Download full-res image for image-only ads (no video)
if image_ids_raw and not video_id_val:
    image_ids_list = image_ids_raw if isinstance(image_ids_raw, list) else (image_ids_raw.split(",") if image_ids_raw else [])
    if image_ids_list:
        # Use first image_id, same pattern as thumbnail
        image_url = await self._fetch_cover_image_url(access_token, advertiser_id, image_ids_list[:1])
        if image_url:
            asset_url = await self._download_image_asset(image_url, org_id, ad_id)

# MODIFIED UPDATE STATEMENT: add asset_url and video_source_url
await db.execute(
    update(TikTokRawPerformance)
    .where(
        TikTokRawPerformance.ad_id == ad_id,
        TikTokRawPerformance.platform_connection_id == connection.id,
    )
    .values(
        # ... existing fields unchanged ...
        **({"thumbnail_url": thumbnail_url} if thumbnail_url else {}),
        **({"asset_url": asset_url} if asset_url else {}),
        **({"video_source_url": video_source_url} if video_source_url else {}),
    )
)
```

**Key integration decisions:**
- **Add after thumbnail logic** (not mixed): Thumbnail remains thumbnail; asset is separate full-resolution asset
- **Respect is_spark flag** (D-02): Skip video download for Spark ads for now; `asset_url` remains None
- **Image-only ads fallback** (D-03): If ad has `image_ids` but no `video_id`, download full image via `/file/image/ad/` (not thumbnail)
- **image_ids parsing**: Replicate existing pattern (line 409-410): handle list or comma-separated string
- **Conditional update fields** (line 455): Only add asset_url/video_source_url if populated, matching existing thumbnail pattern

---

## Shared Patterns

### Non-Fatal Download Failures

**Source:** `backend/app/services/sync/tiktok_sync.py` lines 548-549; `backend/app/services/sync/meta_sync.py` lines 1058-1060

**Apply to:** Both `_download_video_asset()` and `_download_image_asset()`

```python
except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
    logger.warning("Failed to download TikTok [asset_type] for ad %s: %s", ad_id, e, exc_info=True)
    return None
```

**Rationale:** Download failures are expected in production (network flakes, API transients). Log and continue sync rather than failing entire sync run. Sync will succeed, but asset_url will be null for that ad — harmonizer will see null and skip scoring for that asset.

### File Existence Check Before Download

**Source:** `backend/app/services/sync/tiktok_sync.py` lines 535-536

**Apply to:** Both `_download_video_asset()` and `_download_image_asset()`

```python
if obj_storage.file_exists(relative_path):
    return obj_storage.served_url(relative_path)
```

**Rationale:** Avoid re-downloading on re-sync. Assets are immutable (ad creative doesn't change), so presence check is sufficient. Saves S3 egress costs and sync duration on large re-syncs.

### Storage Path Convention

**Source:** `backend/app/services/sync/tiktok_sync.py` line 533; `backend/app/services/sync/meta_sync.py` line 1033

**Apply to:** All new download methods

```
creatives/{org_id}/{asset_type}_{source}_{ad_id}.{ext}
```

**Examples:**
- `creatives/12345/thumb_tiktok_abc123.jpg` — thumbnail (existing)
- `creatives/12345/video_tiktok_abc123.mp4` — video asset (new)
- `creatives/12345/image_tiktok_abc123.jpg` — image asset (new)

**Rationale:** Flat namespace per org; descriptive prefix enables filtering/cleanup; ad_id ensures uniqueness.

### Object Storage Interface

**Source:** `backend/app/services/object_storage.py` lines 64-77, 79-80

**Apply to:** All new download methods

```python
from app.services.object_storage import get_object_storage
obj_storage = get_object_storage()

# Check existence
if obj_storage.file_exists(relative_path):
    return obj_storage.served_url(relative_path)

# Upload bytes
served_url = obj_storage.upload_bytes(resp.content, relative_path, content_type="video/mp4")

# Get served URL
return obj_storage.served_url(relative_path)
```

**Rationale:** `ObjectStorageService` is the project standard for S3/MinIO operations. Handles bucket config, presigned URLs, content-type inference. No direct boto3 calls needed.

### HTTP Client Configuration

**Source:** `backend/app/services/sync/tiktok_sync.py` lines 501-502, 539

**Apply to:** All new HTTP download calls

```python
async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
    resp = await client.get(url)
    resp.raise_for_status()
```

**Timeout guidance:**
- API calls (fetch URL from TikTok): 30s (`_fetch_cover_image_url` pattern)
- File downloads (HTTP transfer): 60s for videos, 30s for images (meta_sync.py line 1038)
- `follow_redirects=True`: Handles CDN redirects from TikTok API URLs

**Rationale:** `httpx.AsyncClient` with timeout prevents indefinite hangs. Async context manager ensures cleanup. Matches project-wide async pattern.

---

## No Analog Found

All required patterns exist in the codebase.

| Pattern | Why No Direct Match | Resolution |
|---------|-------------------|-----------|
| TikTok `/file/video/ad/` endpoint specification | API endpoint not yet implemented; only `/file/image/ad/` used for thumbnails | Research document (15-RESEARCH.md) provides assumed schema based on `/file/image/ad/` pattern; validate against TikTok sandbox before implementation |
| Spark ad video download | Spark ad support not yet coded | Decision D-02 defers; skip silently for now, return None; escalate to TikTok support if needed |

---

## Metadata

**Analog search scope:**
- `backend/app/services/sync/` — TikTok and Meta sync services
- `backend/app/models/` — Performance data models
- `backend/app/services/` — Object storage and utility services

**Files scanned:** 5
- `backend/app/services/sync/tiktok_sync.py` (596 lines) — primary source
- `backend/app/services/sync/meta_sync.py` (1500+ lines) — reference for video download pattern
- `backend/app/models/performance.py` (300+ lines) — model verification
- `backend/app/services/object_storage.py` (150+ lines) — S3 interface
- `backend/app/services/sync/scoring_job.py` (200+ lines) — scoring gate verification

**Pattern extraction date:** 2026-05-08
**Confidence:** HIGH — All patterns are direct quotes or minor adaptations of existing production code
