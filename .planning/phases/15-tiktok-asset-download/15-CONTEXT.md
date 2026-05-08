# Phase 15: TikTok Asset Download - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Download TikTok video and image creative files to MinIO/S3 during sync, populating `asset_url` on `TikTokRawPerformance` so AI autofill (Gemini vision/Whisper audio) and BrainSuite scoring can process TikTok assets. The `scoring_enabled` gate is already in `scoring_job.py:66` and applies automatically — no new gate code needed.

</domain>

<decisions>
## Implementation Decisions

### Video Download Method
- **D-01:** Use TikTok API `/file/video/ad/` endpoint (authenticated, no anti-scraping risk, consistent with existing `/file/image/ad/` thumbnail pattern). Do NOT use yt-dlp for standard video ads.

### Spark Ad Handling
- **D-02:** Do NOT use yt-dlp for Spark ads (yt-dlp does not reliably work for TikTok). Investigate TikTok API endpoint for Spark ad creative access — the `tiktok_creator_auth_code` field already exists on `TikTokRawPerformance` and is likely the key. Planner/researcher must identify the correct API endpoint before coding. If no API solution exists, skip silently and leave `asset_url` null for Spark ads.

### Image-Only Ads
- **D-03:** For ads with `image_ids` but no `video_id`: download the full-resolution image via `/file/image/ad/` and store it in `asset_url`. This is a separate download from `thumbnail_url` — same API call, different target field. Semantically cleaner: `thumbnail_url` = cover/thumbnail, `asset_url` = scoring/autofill input.

### Download Timing
- **D-04:** Inline during `_enrich_from_ad_get` (consistent with existing thumbnail pattern and Meta's `_download_asset` pattern). Sync takes slightly longer but assets are immediately available. Download failures must not abort sync — log warning and continue.

### Auto-Scoring Gate
- **D-05:** `SystemConfig.scoring_enabled` gate is already checked in `scoring_job.py:66` for ALL platforms. Phase 15 just needs to ensure TikTok assets reach `UNSCORED` status in the harmonizer — the gate applies automatically. Verify all 4 platforms (Meta, TikTok, Google Ads, DV360) honour this same gate as part of Phase 15 acceptance criteria.

### Storage Target Fields
- **D-06:** Populate `asset_url` on `TikTokRawPerformance` (the field the harmonizer reads for BrainSuite scoring input). Also populate `video_source_url` for videos if the API returns it. `thumbnail_url` remains the cover/preview image and is already handled.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### TikTok Sync (primary file)
- `backend/app/services/sync/tiktok_sync.py` — Full sync service; `_enrich_from_ad_get` is where downloads are added; `_download_tiktok_thumbnail` is the pattern to follow for video/image download; `_fetch_cover_image_url` shows `/file/image/ad/` usage

### Data Models
- `backend/app/models/performance.py` line 155+ — `TikTokRawPerformance` model; `asset_url` (line 189), `video_source_url` (line 193), `thumbnail_url` (line 188), `video_id` (line 185), `image_ids` (line 186), `is_spark_ad` (line 181), `tiktok_creator_auth_code` (line 197)

### Scoring Gate
- `backend/app/services/sync/scoring_job.py` line 66 — `scoring_enabled` check; verify TikTok assets reach UNSCORED state

### Pattern Reference (Meta download)
- `backend/app/services/sync/meta_sync.py` — `_download_asset()` pattern (line ~985) and `_fetch_creatives()` (line ~727) — follow this pattern for TikTok video download

### Object Storage
- `backend/app/services/object_storage.py` — `upload_bytes()`, `file_exists()`, `served_url()` — same interface used by thumbnail download

### Requirements
- `.planning/REQUIREMENTS.md` — TKTOK-01, TKTOK-02

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_download_tiktok_thumbnail()` in `tiktok_sync.py` — exact pattern to replicate for video/image download (httpx download → `upload_bytes()` → return served URL)
- `_fetch_cover_image_url()` in `tiktok_sync.py` — pattern for calling `/file/image/ad/`; replicate for `/file/video/ad/`
- `obj_storage.upload_bytes()` — already used for thumbnails, works for any bytes

### Established Patterns
- Download failures are non-fatal: log warning, return None, continue sync (see `_download_tiktok_thumbnail` try/except)
- File existence check before download: `obj_storage.file_exists(relative_path)` prevents re-downloading on re-sync
- Storage path convention: `creatives/{org_id}/{filename}` — follow same convention
- Session-per-operation: no DB session held during HTTP download calls

### Integration Points
- `_enrich_from_ad_get()` — add video/image download calls here, after ad info is fetched, before `db.execute(update(...))`
- `update(TikTokRawPerformance).values(...)` call — add `asset_url=asset_url` to the values dict
- Harmonizer reads `asset_url` from raw performance to populate `CreativeAsset` — no harmonizer changes needed if `asset_url` is populated

</code_context>

<specifics>
## Specific Ideas

- TikTok API endpoint for video download: `/file/video/ad/` (investigate exact params — likely `advertiser_id` + `video_ids` list, mirroring `/file/image/ad/` structure)
- Spark ad API endpoint: investigate TikTok Business API for Spark ad creative access using `tiktok_creator_auth_code` — this field exists on the model suggesting it was planned for this purpose
- Storage path for videos: `creatives/{org_id}/video_tiktok_{ad_id}.mp4` (following `thumb_tiktok_{ad_id}.jpg` convention)
- Storage path for images: `creatives/{org_id}/image_tiktok_{ad_id}.jpg`

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-TikTok Asset Download*
*Context gathered: 2026-05-08*
