# Phase 15: TikTok Asset Download - Research

**Researched:** 2026-05-08
**Domain:** TikTok creative asset download (video and image files)
**Confidence:** HIGH

## Summary

Phase 15 closes the TikTok asset download gap by downloading video and image creatives to MinIO/S3 during sync, enabling AI autofill (Gemini vision, Whisper audio) and BrainSuite scoring to process TikTok assets. The codebase provides a complete reference pattern in `meta_sync.py` for video/image download, and an existing thumbnail download pattern in `tiktok_sync.py` that demonstrates the mechanics for TikTok-specific workflows.

**Primary recommendation:** Inline video/image download during `_enrich_from_ad_get()` using the existing `/file/video/ad/` and `/file/image/ad/` API endpoints, following the Meta download pattern for error resilience and the TikTok thumbnail pattern for TikTok API integration. Investigate Spark ad video API endpoint before implementation. Auto-scoring gate (`SystemConfig.scoring_enabled`) is already in place at `scoring_job.py:66` — Phase 15 only needs to ensure TikTok assets reach `UNSCORED` state.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use TikTok API `/file/video/ad/` endpoint (authenticated, no anti-scraping risk, consistent with existing `/file/image/ad/` thumbnail pattern). Do NOT use yt-dlp for standard video ads.
- **D-02:** Do NOT use yt-dlp for Spark ads. Investigate TikTok API endpoint for Spark ad creative access using `tiktok_creator_auth_code` field. If no API solution exists, skip silently and leave `asset_url` null for Spark ads.
- **D-03:** For ads with `image_ids` but no `video_id`: download the full-resolution image via `/file/image/ad/` and store in `asset_url` (separate from `thumbnail_url` which remains cover/preview).
- **D-04:** Inline during `_enrich_from_ad_get()` (consistent with existing thumbnail pattern and Meta's `_download_asset` pattern). Download failures must not abort sync — log warning and continue.
- **D-05:** `SystemConfig.scoring_enabled` gate is already checked at `scoring_job.py:66` for ALL platforms. Phase 15 must verify all 4 platforms (Meta, TikTok, Google Ads, DV360) honour this gate as acceptance criteria.
- **D-06:** Populate `asset_url` on `TikTokRawPerformance` (field the harmonizer reads for BrainSuite scoring input). Also populate `video_source_url` for videos if the API returns it.

### Claude's Discretion
None — all major decisions were locked during discussion phase.

### Deferred Ideas
None — discussion stayed within phase scope.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TKTOK-01 | User sees TikTok video creatives in dashboard after sync (video files downloaded to MinIO/S3, stored as video_url on CreativeAsset) | `asset_url` field on TikTokRawPerformance; `/file/video/ad/` endpoint documented in canonical refs; existing download pattern in `_download_tiktok_thumbnail()`; harmonizer reads `asset_url` for CreativeAsset population |
| TKTOK-02 | User sees TikTok image creatives in dashboard after sync (image files downloaded to MinIO/S3, stored as image_url on CreativeAsset) | `asset_url` field on TikTokRawPerformance; `/file/image/ad/` endpoint already used for thumbnails; image_ids parsing in `_enrich_from_ad_get()` line 409–410; harmonizer reads `asset_url` for CreativeAsset population |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Video/image file download | API / Backend | — | TikTok API endpoints are called server-side; files are downloaded and uploaded to S3 before being served to frontend |
| Asset URL storage | Database | API / Backend | Raw performance model stores URLs; API reads and serves them; harmonizer populates CreativeAsset table |
| Harmonization (raw → harmonized) | Database | API / Backend | Harmonizer already reads `asset_url` field and populates CreativeAsset table; no new logic needed |
| Auto-scoring gate enforcement | API / Backend | Database | `SystemConfig.scoring_enabled` checked at `scoring_job.py:66`; already applies to all platforms |
| Frontend display | Browser / Client | — | Dashboard uses CreativeAsset table (which gets populated from harmonizer); UI reads image_url/video_url fields |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.25+ [VERIFIED: codebase] | Async HTTP client for TikTok API calls | Same async client used throughout sync services (Meta, DV360, TikTok reports) |
| sqlalchemy | 2.0+ [VERIFIED: codebase] | ORM for database updates | Project standard; used for all data models |
| asyncio | Python 3.11+ [VERIFIED: codebase] | Async runtime | Project standard; all sync services are async |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| boto3/S3 | 1.26+ [VERIFIED: codebase] | Object storage client | Already used for all creative asset uploads; MinIO compatible |
| pillow (PIL) | 10+ [VERIFIED: meta_sync.py] | Image processing (optional for thumbnails) | Only needed if generating thumbnails from downloaded images; Meta already does this for videos |

## Architecture Patterns

### System Architecture Diagram

```
TikTok Sync Flow:
==================================================

[Sync Start]
    ↓
[Fetch Ad Reports] → TikTokRawPerformance (populated with performance metrics)
    ↓
[_enrich_from_ad_get()]
    ├→ [Call /ad/get/ endpoint] → Get ad metadata (creative_type, video_id, image_ids, etc.)
    ├→ [Call /file/image/ad/ for thumbnails] → Download cover image
    │  └→ [_download_tiktok_thumbnail()] → Upload to MinIO → Update thumbnail_url
    │
    ├→ [NEW: Call /file/video/ad/] → Get video download URL (for video_id ads)
    │  └→ [_download_video_asset()] → Download video bytes → Upload to MinIO → Update asset_url
    │
    └→ [NEW: Call /file/image/ad/ for full resolution] → Get full image (for image_ids ads)
       └→ [_download_image_asset()] → Download image bytes → Upload to MinIO → Update asset_url
    ↓
[Post-Commit]
    ↓
[Harmonizer Reads asset_url] → Populates CreativeAsset table (image_url/video_url fields)
    ↓
[Scoring Gate Check]
    └→ [SystemConfig.scoring_enabled = true?]
       ├→ YES: Mark as UNSCORED → Scoring batch picks up
       └→ NO: Skip scoring
    ↓
[Dashboard Display]
```

### Recommended Project Structure

TikTok asset download does not require new files or directories. All changes are within existing `backend/app/services/sync/tiktok_sync.py`:

```
backend/app/services/sync/
├── tiktok_sync.py         # Add _download_video_asset() and _download_image_asset() methods
├── meta_sync.py           # (Reference pattern only)
└── object_storage.py      # (Existing, no changes needed)
```

### Pattern 1: Non-Fatal Download Failures

**What:** Download failures during sync do not abort the entire sync run. Failures are logged as warnings and the sync continues.

**When to use:** Any large-scale data fetch where network/API errors are expected and one failure shouldn't block progress.

**Example:**
```python
# Source: tiktok_sync.py:_download_tiktok_thumbnail (line 522–550)
async def _download_tiktok_thumbnail(
    self,
    image_url: str,
    org_id: str,
    ad_id: str,
) -> Optional[str]:
    """Download a TikTok cover image and upload to S3. Returns served URL or None."""
    from app.services.object_storage import get_object_storage
    obj_storage = get_object_storage()

    filename = f"thumb_tiktok_{ad_id}.jpg"
    relative_path = f"creatives/{org_id}/{filename}"

    if obj_storage.file_exists(relative_path):
        return obj_storage.served_url(relative_path)

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
        if len(resp.content) < 100:
            logger.warning("TikTok thumbnail for ad %s too small (%d bytes), skipping", ad_id, len(resp.content))
            return None
        served_url = obj_storage.upload_bytes(resp.content, relative_path, content_type="image/jpeg")
        logger.info("Downloaded TikTok thumbnail for ad %s: %s (%d bytes)", ad_id, filename, len(resp.content))
        return served_url
    except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
        logger.warning("Failed to download TikTok thumbnail for ad %s: %s", ad_id, e, exc_info=True)
        return None
```

### Pattern 2: Conditional Asset Update (Skip If Already Exists)

**What:** Before downloading, check if the asset already exists in S3. If it does, return the served URL and skip download.

**When to use:** Any asset that should persist across re-syncs (avoid re-downloading unchanged assets).

**Example:**
```python
# Source: tiktok_sync.py:_download_tiktok_thumbnail (line 535–536)
if obj_storage.file_exists(relative_path):
    return obj_storage.served_url(relative_path)
```

### Pattern 3: Update Raw Performance Records Inline

**What:** Download assets and update raw performance records within the same `_enrich_from_ad_get()` loop, then batch-flush to database.

**When to use:** When download results need to be persisted and you're already iterating through records.

**Example:**
```python
# Source: tiktok_sync.py:_enrich_from_ad_get (line 426–456)
await db.execute(
    update(TikTokRawPerformance)
    .where(
        TikTokRawPerformance.ad_id == ad_id,
        TikTokRawPerformance.platform_connection_id == connection.id,
    )
    .values(
        # ... other fields ...
        thumbnail_url=thumbnail_url,
        # NEW: Add asset_url here
        asset_url=asset_url,
    )
)
```

### Anti-Patterns to Avoid

- **Holding DB session during HTTP download:** The sync session should not be held during the 10-30 second HTTP download window. Meta and TikTok both use post-commit async tasks to release the session. Phase 15 uses inline download (D-04), so the session IS held — this is acceptable for performance vs. schema complexity tradeoff, but monitor sync duration.
- **Mixing thumbnail_url and asset_url semantics:** `thumbnail_url` is cover/preview (for dashboard display). `asset_url` is the full-resolution asset (for AI autofill/scoring input). Never populate one with the other.
- **Silently dropping download failures:** Always log download failures with warning level and ad_id. This helps diagnose API/network issues during sync audits.
- **Re-downloading unchanged assets:** Always check `obj_storage.file_exists()` before downloading. Reduces redundant downloads and S3 egress costs.
- **Using yt-dlp for standard TikTok video ads:** The `/file/video/ad/` API endpoint is authenticated and reliable. yt-dlp is anti-scraping risk and not required.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP downloads | Custom urllib3/requests wrapper | httpx.AsyncClient (already used throughout) | Already integrated; timeout/redirect handling; matches project async/await pattern |
| File type detection | Manual regex parsing of URLs | mimetypes library + Content-Type header parsing (see meta_sync.py:1043–1048) | Handles edge cases (redirects, query params, content negotiation) |
| S3/MinIO uploads | Direct boto3 calls | ObjectStorageService.upload_bytes() (wrapper already exists) | Handles bucket configuration, presigned URLs, content type inference, error handling |
| Video download URL retrieval from TikTok API | Parsing undocumented response fields | Call `/file/video/ad/` endpoint (authenticated, stable API) | Official endpoint; no anti-scraping risk; matches existing `/file/image/ad/` pattern |
| Image resolution fallback chains | Multiple conditional API calls | Meta's pattern: hash → adimages API → story_spec URL → image_url (see meta_sync.py:796–801) | TikTok pattern: image_ids → /file/image/ad/ → fallback to null |

**Key insight:** The biggest pitfall in this domain is choosing the wrong download source (yt-dlp vs. API). The `/file/video/ad/` endpoint is official, authenticated, and requires no anti-scraping workarounds. Use it directly.

## Common Pitfalls

### Pitfall 1: Spark Ad Video Download Method Unclear

**What goes wrong:** Spark ads (identity_type = "CUSTOMIZED_USER" or "AUTH_CODE") may require a different API endpoint or authentication method than standard video ads. Using `/file/video/ad/` without verifying may fail silently or return null URLs.

**Why it happens:** TikTok has two creator identity types: standard (anonymous) and Spark (creator-linked). Spark ads reference creator-owned content, which may require different API authorization.

**How to avoid:** Investigate TikTok Business API documentation or test endpoints with a Spark ad sample before writing the download logic. The field `tiktok_creator_auth_code` exists on the model (line 197, `performance.py`), suggesting it was planned for Spark ad auth. Verify if this field is required for `/file/video/ad/` calls on Spark ads.

**Warning signs:** 
- `/file/video/ad/` returns null `video_url` for Spark ads
- API returns 403 Forbidden or 401 Unauthorized for Spark ad video fetch
- `tiktok_creator_auth_code` is populated but not used in download call

### Pitfall 2: Confusing thumbnail_url and asset_url Semantics

**What goes wrong:** Thumbnail downloaded to `asset_url` instead of `thumbnail_url`, or vice versa. This causes BrainSuite to attempt scoring on a cover image (too small, wrong aspect ratio) instead of the full-resolution video/image.

**Why it happens:** Both fields exist and both are URLs. It's easy to mix them up if the distinction isn't clear.

**How to avoid:** 
- `thumbnail_url` = cover/preview image (used for dashboard thumbnail display)
- `asset_url` = full-resolution asset (video file or full-resolution image, used for AI autofill and scoring)

Enforce this in code comments and never assign thumbnail data to `asset_url`.

**Warning signs:**
- BrainSuite scoring fails with "image too small" or dimension errors
- Dashboard shows correct thumbnails but AI autofill produces junk results
- Scoring endpoint_type is STATIC_IMAGE but asset is actually a video

### Pitfall 3: Sync Duration Increases Significantly

**What goes wrong:** Inline video download (D-04) adds 10-30 seconds per video to sync time. If there are 1000 ads with videos, sync takes 3-8 hours instead of 10 minutes.

**Why it happens:** HTTP downloads are I/O-bound and sequential in the current `_enrich_from_ad_get()` loop structure.

**How to avoid:** 
- Use asyncio task batching if downloads take > 5 minutes per 100 ads (consider post-commit deferred task pattern like Meta uses)
- Monitor sync duration during UAT; if > 30 minutes for typical account, escalate to deferred download strategy
- Log download time per asset for performance diagnostics

**Warning signs:**
- Sync duration increases 10x+ after this phase
- Timeouts during large account syncs
- Connection timeout errors in logs

### Pitfall 4: Image_ids Array Parsing Error

**What goes wrong:** `image_ids` is returned from `/ad/get/` as either a list or a comma-separated string (depending on API version). Parsing it incorrectly results in malformed `/file/image/ad/` calls.

**Why it happens:** API response formats vary across TikTok API versions. Line 409–410 of `tiktok_sync.py` already handles this for thumbnail, but the new image download method must replicate the same logic.

**How to avoid:** Replicate the existing thumbnail pattern exactly:
```python
image_ids_raw = ad.get("image_ids")
image_ids_list = image_ids_raw if isinstance(image_ids_raw, list) else (image_ids_raw.split(",") if image_ids_raw else [])
```

**Warning signs:**
- `/file/image/ad/` API returns 400 Bad Request
- image_ids parameter is formatted as a list instead of JSON array
- No images downloaded for image-only ads

### Pitfall 5: Auto-Scoring Gate Not Checked For All Platforms

**What goes wrong:** Phase 15 implements TikTok asset download, but the auto-scoring gate check (D-05) is not verified for Meta, Google Ads, and DV360. Assets appear in dashboard but scoring does not run even when `scoring_enabled=true`.

**Why it happens:** The gate exists at `scoring_job.py:66`, but if it's not applied consistently across all platform sync pipelines, some platforms' assets will remain UNSCORED forever.

**How to avoid:** As part of Phase 15 acceptance criteria, verify that:
1. `SystemConfig.scoring_enabled` is checked in `scoring_job.py:66` (already implemented)
2. All platform raw performance models have asset URLs populated (Meta ✓, TikTok ✓ after Phase 15, Google Ads ?, DV360 ?)
3. Harmonizer reads `asset_url` from all platform tables and populates CreativeAsset (verify)

Run test sync on all 4 platforms with `scoring_enabled=true` and `scoring_enabled=false` to confirm gate behavior.

**Warning signs:**
- TikTok assets in dashboard but not scored
- Meta assets are scored but TikTok assets remain UNSCORED
- Toggling `scoring_enabled` has no effect on TikTok assets

## Code Examples

Verified patterns from official sources:

### Video Download from TikTok API

```python
# Source: tiktok_sync.py:_fetch_cover_image_url (line 493–520, pattern to replicate)
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
                # Verify response structure matches /file/image/ad/ pattern
                return videos[0].get("video_url")  # [ASSUMED] field name from API
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.warning("Failed to fetch TikTok video URL: %s", e)
    return None
```

### Asset Download and Upload to S3

```python
# Source: meta_sync.py:_download_asset (line 1012–1060, pattern to adapt)
async def _download_video_asset(
    self,
    url: str,
    org_id,
    ad_id: str,
) -> Optional[str]:
    """Download a video from URL, upload to S3. Returns served_url or None."""
    try:
        from app.services.object_storage import get_object_storage
        obj_storage = get_object_storage()

        filename = f"video_tiktok_{ad_id}.mp4"
        relative_path = f"creatives/{org_id}/{filename}"

        if obj_storage.file_exists(relative_path):
            return obj_storage.served_url(relative_path)

        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            served_url = obj_storage.upload_bytes(resp.content, relative_path, content_type="video/mp4")
            logger.info(f"Downloaded TikTok video for ad {ad_id}: {filename} ({len(resp.content)} bytes)")
            return served_url

    except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
        logger.warning("Failed to download TikTok video for ad %s: %s", ad_id, e, exc_info=True)
        return None
```

### Integration into _enrich_from_ad_get()

```python
# Source: tiktok_sync.py:_enrich_from_ad_get (line 386–462, integration point)
# Within the ad loop, after thumbnail download:

video_id_val = ad.get("video_id")
asset_url = None
video_source_url = None

# NEW: Download video for video ads
if video_id_val:
    video_url = await self._fetch_video_download_url(access_token, advertiser_id, [str(video_id_val)])
    if video_url:
        asset_url = await self._download_video_asset(video_url, org_id, ad_id)
        video_source_url = video_url  # Optional: store API URL for reference

# NEW: Download full-res image for image-only ads
image_ids_raw = ad.get("image_ids")
if image_ids_raw and not video_id_val:
    image_ids_list = image_ids_raw if isinstance(image_ids_raw, list) else (image_ids_raw.split(",") if image_ids_raw else [])
    if image_ids_list:
        image_url = await self._fetch_cover_image_url(access_token, advertiser_id, image_ids_list[:1])
        if image_url:
            asset_url = await self._download_image_asset(image_url, org_id, ad_id)

# Add to update statement:
await db.execute(
    update(TikTokRawPerformance)
    .where(
        TikTokRawPerformance.ad_id == ad_id,
        TikTokRawPerformance.platform_connection_id == connection.id,
    )
    .values(
        # ... existing fields ...
        thumbnail_url=thumbnail_url,
        asset_url=asset_url,  # NEW
        video_source_url=video_source_url,  # NEW (optional)
    )
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-rolled async download loops | httpx.AsyncClient with timeout handling | Project inception | Simplified error handling, consistent across all sync services |
| Storing raw download URLs | Downloading to S3 and storing served URLs | Phase 14 (Meta implementation) | Enables offline viewing, reduces external API dependency, works with AI autofill |
| Separate download service post-commit | Inline download during sync | Meta Phase (v1.2) | Simpler state management, consistent asset availability, acceptable performance for typical account sizes |

**Deprecated/outdated:**
- yt-dlp for TikTok video: TikTok Business API `/file/video/ad/` endpoint is now the standard. yt-dlp is used only for organic video scraping and has monthly breakage due to anti-scraping measures. Do not use for ads.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | TikTok API `/file/video/ad/` endpoint exists and returns video_url field | Code Examples | Download logic would fail; fallback: investigate Spark ad endpoint or switch to yt-dlp with monthly maintenance burden |
| A2 | `image_ids` from `/ad/get/` can be parsed as list or comma-separated string | Common Pitfalls (Pitfall 4) | Image-only ads would not be downloaded; detected during UAT |
| A3 | `/file/image/ad/` returns full-resolution image URLs (not just thumbnails) | Code Examples | Image-only ads would show thumbnail instead of full asset to scoring; verify by testing image_ids with multiple sizes |
| A4 | `tiktok_creator_auth_code` field is required for Spark ad video download | Pitfalls (Pitfall 1) | Spark ad videos would not download; escalate to TikTok support or implement retry with auth_code |
| A5 | Harmonizer already reads `asset_url` from TikTokRawPerformance and populates CreativeAsset.image_url/video_url | Requirements | CreativeAsset would remain unpopulated; verify harmonizer logic |

**User confirmation needed:** Assumptions A1, A2, A3, A4 before implementation begins. Recommendation: validate `/file/video/ad/` and `/file/image/ad/` endpoints against TikTok sandbox before coding Phase 15.

## Open Questions

1. **Spark Ad Video Download Endpoint**
   - What we know: `tiktok_creator_auth_code` field exists and is populated for Spark ads
   - What's unclear: Does `/file/video/ad/` work with Spark ads? Do we need to use a different endpoint or pass auth_code as a parameter?
   - Recommendation: Test `/file/video/ad/` with a known Spark ad in TikTok sandbox. If it fails, investigate TikTok Business API docs for creator-specific video endpoints.

2. **Image Resolution for Image-Only Ads**
   - What we know: `/file/image/ad/` returns image URLs for image_ids
   - What's unclear: Are these full-resolution images suitable for scoring, or are they thumbnail-sized (like the cover image)?
   - Recommendation: Download an image-only ad asset and inspect dimensions. If < 400x300px, escalate as limitation.

3. **Download Time Impact on Sync Duration**
   - What we know: Inline download adds HTTP latency to sync runtime (D-04 decision)
   - What's unclear: For accounts with 500+ video ads, how much does sync duration increase? Is it acceptable?
   - Recommendation: Monitor Phase 15 UAT on large accounts. If sync > 30 minutes, consider post-commit deferred task pattern (like Meta).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| TikTok Business API (OAuth token) | `/file/video/ad/` and `/file/image/ad/` endpoints | ✓ | v1.3 | — (no fallback; API access required) |
| httpx | Async HTTP requests for TikTok API | ✓ | 0.25+ | Use requests (sync only, not recommended) |
| boto3/S3 (MinIO compatible) | Asset upload to object storage | ✓ | 1.26+ | — (no fallback; S3 required) |
| ObjectStorageService wrapper | Simplified S3 calls | ✓ | Project-specific | — (project utility, no fallback) |

**Missing dependencies with no fallback:** None — all required dependencies are already available.

**Missing dependencies with fallback:** None identified.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing test infrastructure in backend/tests/) |
| Config file | pyproject.toml (pytest config) or pytest.ini (if exists) |
| Quick run command | `pytest backend/tests/test_tiktok_sync.py -x -v` |
| Full suite command | `pytest backend/tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TKTOK-01 | TikTok video creatives downloaded and stored in asset_url | unit | `pytest backend/tests/test_tiktok_sync.py::test_download_video_asset -xvs` | ❌ Wave 0 |
| TKTOK-01 | After sync, video_url populated on CreativeAsset | integration | `pytest backend/tests/test_tiktok_sync.py::test_video_asset_harmonization -xvs` | ❌ Wave 0 |
| TKTOK-02 | TikTok image creatives downloaded and stored in asset_url | unit | `pytest backend/tests/test_tiktok_sync.py::test_download_image_asset -xvs` | ❌ Wave 0 |
| TKTOK-02 | After sync, image_url populated on CreativeAsset | integration | `pytest backend/tests/test_tiktok_sync.py::test_image_asset_harmonization -xvs` | ❌ Wave 0 |
| TKTOK-01, TKTOK-02 | Download failure does not abort sync (non-fatal) | unit | `pytest backend/tests/test_tiktok_sync.py::test_download_failure_resilience -xvs` | ❌ Wave 0 |
| TKTOK-01, TKTOK-02 | Asset already in S3 skips re-download | unit | `pytest backend/tests/test_tiktok_sync.py::test_skip_existing_asset -xvs` | ❌ Wave 0 |
| (Success Criteria #5) | Scoring enabled toggle applies to TikTok (verify all 4 platforms) | integration | `pytest backend/tests/test_scoring_gate.py::test_all_platforms_honor_scoring_enabled -xvs` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/test_tiktok_sync.py::test_download_video_asset -x`
- **Per wave merge:** `pytest backend/tests/ -x --tb=short`
- **Phase gate:** Full suite green + manual verification on live TikTok account with video and image ads

### Wave 0 Gaps
- [ ] `backend/tests/test_tiktok_sync.py` — unit tests for `_download_video_asset()`, `_download_image_asset()`, `_fetch_video_download_url()`, resilience to download failures, skip-if-exists logic
- [ ] `backend/tests/test_tiktok_sync.py` — integration tests for video/image harmonization into CreativeAsset table
- [ ] `backend/tests/test_scoring_gate.py` — cross-platform scoring enabled gate verification (Meta, TikTok, Google Ads, DV360)
- [ ] Mock httpx responses for TikTok `/file/video/ad/` and `/file/image/ad/` endpoints in test fixtures
- [ ] Test data: sample TikTok ad with video_id and image_ids for round-trip testing

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | TikTok OAuth token already managed by PlatformConnection; no new auth added |
| V3 Session Management | No | HTTP client timeout (30-60s) prevents indefinite hangs; async context manager ensures cleanup |
| V4 Access Control | No | Downloads scoped to organization_id (org_id derived from connection.organization_id); no cross-org asset leakage |
| V5 Input Validation | Yes | API response validation: check for null/missing fields before accessing; validate image_ids array format |
| V6 Cryptography | No | All communication with TikTok API is HTTPS; S3 upload uses boto3 default encryption |

### Known Threat Patterns for {TikTok + S3 + Python async HTTP}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| URL validation (malicious CDN redirect in API response) | Tampering | Use httpx with `follow_redirects=True` and timeout (30-60s); never follow infinite redirects |
| DoS via large file downloads | Denial of Service | Set content-length limit before download; raise if > 500MB (reasonable for video); timeout connection if transfer takes > 60s |
| S3 bucket misconfiguration (public read) | Information Disclosure | Use boto3 S3 client with private ACL; verify S3_BUCKET_NAME and endpoint in CI/staging before production deploy |
| Race condition: file exists check → download → upload | Race Condition | `file_exists()` and `upload_bytes()` are atomic per S3 semantics; if concurrent sync jobs download same ad simultaneously, both upload and last-write-wins (acceptable) |
| Malicious API credentials in logs | Information Disclosure | Ensure access_token is never logged; use decrypt_token() only in function parameters; all httpx calls use headers (not in logs by default) |

**No new threats introduced by Phase 15.** Existing security posture (OAuth encryption, S3 private buckets, URL validation) is sufficient.

## Sources

### Primary (HIGH confidence)
- **Codebase inspection:**
  - `backend/app/services/sync/tiktok_sync.py` (lines 1–596) — Existing thumbnail download pattern, `/file/image/ad/` API usage
  - `backend/app/services/sync/meta_sync.py` (lines 700–1060) — Complete video/image download reference pattern
  - `backend/app/models/performance.py` (lines 155–250) — TikTokRawPerformance model structure; asset_url, video_source_url fields
  - `backend/app/services/object_storage.py` (lines 1–150) — ObjectStorageService.upload_bytes() interface
  - `backend/app/services/sync/scoring_job.py` (lines 44–68) — SystemConfig.scoring_enabled gate location and usage

### Secondary (MEDIUM confidence)
- **Decision document:** `.planning/phases/15-tiktok-asset-download/15-CONTEXT.md` (locked implementation decisions D-01 through D-06)
- **Requirements document:** `.planning/REQUIREMENTS.md` (TKTOK-01, TKTOK-02 definitions)

### Tertiary (LOW confidence)
- **TikTok API endpoint structure:** [ASSUMED] `/file/video/ad/` and `/file/image/ad/` response schema mirrors `/file/image/ad/` pattern; needs verification against TikTok Business API sandbox

## Metadata

**Confidence breakdown:**
- **Standard stack:** HIGH — httpx, sqlalchemy, asyncio all verified in use throughout codebase
- **Architecture:** HIGH — Meta download pattern is proven implementation; TikTok thumbnail pattern is proven for TikTok API calls
- **Pitfalls:** MEDIUM — Spark ad endpoint is [ASSUMED]; all others based on codebase inspection
- **Implementation roadmap:** HIGH — Clear integration point (`_enrich_from_ad_get()` line 386), clear data model fields (`asset_url`, `video_source_url`)

**Research date:** 2026-05-08
**Valid until:** 2026-05-22 (14 days — TikTok API is stable, but implementation assumptions should be validated against sandbox within 2 weeks)
