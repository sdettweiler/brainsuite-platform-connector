---
phase: quick
plan: 260407-lxk
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/alembic/versions/q8r9s0t1u2v3_add_width_height_to_creative_assets.py
  - backend/app/models/creative.py
  - backend/app/services/sync/harmonizer.py
  - backend/app/services/sync/dv360_sync.py
  - backend/app/services/sync/scoring_job.py
  - backend/app/api/v1/endpoints/scoring.py
  - backend/app/schemas/creative.py
  - backend/app/api/v1/endpoints/dashboard.py
  - frontend/src/app/features/dashboard/dashboard.component.ts
  - frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts
autonomous: true
requirements: []
must_haves:
  truths:
    - "CreativeAsset has width and height columns in the database"
    - "New assets imported from Meta get width, height, and video_duration from raw performance data"
    - "New assets imported from TikTok get video_duration from raw performance data"
    - "New assets imported from Google Ads get video_duration (converted from millis)"
    - "New assets imported from DV360 get width and height from API dimensions"
    - "Existing assets can be backfilled for width/height via admin endpoint"
    - "Dashboard asset detail dialog shows width, height, and duration"
  artifacts:
    - path: "backend/alembic/versions/q8r9s0t1u2v3_add_width_height_to_creative_assets.py"
      provides: "Alembic migration adding width/height Integer columns"
    - path: "backend/app/models/creative.py"
      provides: "width and height Mapped fields on CreativeAsset"
    - path: "backend/app/services/sync/harmonizer.py"
      provides: "width/height/video_duration forwarding in all 4 platform harmonizers"
  key_links:
    - from: "harmonizer._harmonize_meta()"
      to: "harmonizer._ensure_asset()"
      via: "width=raw.creative_width_px, height=raw.creative_height_px, video_duration=raw.video_length_sec"
    - from: "scoring.py admin endpoint"
      to: "scoring_job.run_media_metrics_backfill()"
      via: "BackgroundTasks"
---

<objective>
Add missing width and height columns to CreativeAsset, wire dimension/duration extraction through all 4 platform harmonizers using already-available raw data, add a backfill admin endpoint, and expose the fields in the dashboard UI.

Purpose: Asset media dimensions are needed for BrainSuite scoring context, dashboard filtering, and creative analysis.
Output: Migration, model update, harmonizer wiring, backfill endpoint, frontend display.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/quick/260407-lxk-fix-missing-asset-media-metrics-add-dura/260407-lxk-RESEARCH.md

@backend/app/models/creative.py
@backend/app/models/performance.py
@backend/app/services/sync/harmonizer.py
@backend/app/services/sync/dv360_sync.py
@backend/app/services/sync/scoring_job.py
@backend/app/api/v1/endpoints/scoring.py
@backend/app/schemas/creative.py
@backend/app/api/v1/endpoints/dashboard.py
@frontend/src/app/features/dashboard/dashboard.component.ts
@frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts
</context>

<tasks>

<task type="auto">
  <name>Task 1: Migration + model + harmonizer wiring for all 4 platforms</name>
  <files>
    backend/alembic/versions/q8r9s0t1u2v3_add_width_height_to_creative_assets.py
    backend/app/models/creative.py
    backend/app/services/sync/harmonizer.py
    backend/app/services/sync/dv360_sync.py
  </files>
  <action>
1. **Alembic migration** (`q8r9s0t1u2v3_add_width_height_to_creative_assets.py`):
   - `down_revision = "p7q8r9s0t1u2"`
   - `upgrade()`: `op.add_column("creative_assets", sa.Column("width", sa.Integer(), nullable=True))` and same for `"height"`
   - `downgrade()`: drop both columns

2. **CreativeAsset model** (`backend/app/models/creative.py`):
   - Add after `video_duration` (line 51):
     ```python
     width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
     height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
     ```

3. **harmonizer._ensure_asset()** (line ~870 in new-asset block, line ~918 in update block):
   - New asset block: add `width=kwargs.get("width"), height=kwargs.get("height"),` after `video_duration=kwargs.get("video_duration"),`
   - Update block (after the `asset_format` update ~line 924): add:
     ```python
     if kwargs.get("width") and not asset.width:
         asset.width = kwargs["width"]
     if kwargs.get("height") and not asset.height:
         asset.height = kwargs["height"]
     if kwargs.get("video_duration") and not asset.video_duration:
         asset.video_duration = kwargs["video_duration"]
     ```

4. **_harmonize_meta()** (line ~136, the `_ensure_asset` call):
   - Add kwargs: `width=raw.creative_width_px, height=raw.creative_height_px, video_duration=raw.video_length_sec,`
   - Meta raw already has `creative_width_px`, `creative_height_px`, `video_length_sec` populated from API. No file download needed.

5. **_harmonize_tiktok()** (line ~358, the `_ensure_asset` call):
   - Add kwarg: `video_duration=raw.video_duration_sec,`
   - TikTok has no width/height in raw model and no creative download — skip dimensions (correct per research).

6. **_harmonize_google_ads()** (line ~521, the `_ensure_asset` call):
   - Google Ads raw has `video_duration` (Integer) which is already passed at line 536 as `video_duration=raw.video_duration`. The research says `video_duration_millis` but the actual model field at performance.py line 344 is `video_duration: Mapped[int]`. Check the value range — if the raw values are in milliseconds (>1000 for any video), convert: `video_duration=(raw.video_duration / 1000.0) if raw.video_duration else None`. If already in seconds, leave as-is. Either way, ensure it is passed (it already is at line 536 — just verify correctness).
   - No width/height available for Google Ads — skip.

7. **DV360 sync** (`dv360_sync.py` lines 515-527):
   - In `_fetch_creatives()`, the `creatives[str(cr_id)]` dict at line 520 already builds `asset_format = f"{w}x{h}"` but discards `w` and `h`. Add `"width_pixels": int(w) if w else None` and `"height_pixels": int(h) if h else None` to the dict.

8. **DV360 harmonizer wiring:**
   - In `_harmonize_dv360()`, the creative dict is looked up and merged into the raw row. Find where `asset_format` from the creative dict flows into the `_ensure_asset` call (line ~686). Add `width=` and `height=` kwargs sourced from the creative dict's `width_pixels`/`height_pixels`. The DV360 `_ensure_asset` call needs these added alongside the existing `video_duration=row.video_duration_seconds`.

Run migration: `cd backend && alembic upgrade head`
  </action>
  <verify>
    <automated>cd /Users/sebastian.dettweiler/Claude\ Code/platform-connector/brainsuite-platform-connector/backend && alembic upgrade head && python -c "from app.models.creative import CreativeAsset; print('width' in [c.name for c in CreativeAsset.__table__.columns] and 'height' in [c.name for c in CreativeAsset.__table__.columns])"</automated>
  </verify>
  <done>
    - Migration runs clean, width/height columns exist on creative_assets table
    - CreativeAsset model has width, height Mapped fields
    - All 4 harmonize methods pass available dimensions/duration to _ensure_asset
    - _ensure_asset sets width/height on new assets and backfills on existing assets that lack them
  </done>
</task>

<task type="auto">
  <name>Task 2: Backfill endpoint + API/frontend exposure</name>
  <files>
    backend/app/services/sync/scoring_job.py
    backend/app/api/v1/endpoints/scoring.py
    backend/app/schemas/creative.py
    backend/app/api/v1/endpoints/dashboard.py
    frontend/src/app/features/dashboard/dashboard.component.ts
    frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts
  </files>
  <action>
1. **Backfill function** (`scoring_job.py`):
   - Add `async def run_media_metrics_backfill() -> None:` following the `run_backfill_task` pattern (line 406).
   - Query `creative_assets` where `width IS NULL OR height IS NULL`, fetch in batches of 100.
   - For each asset:
     - If `asset_url` is None or empty, skip.
     - Try to download bytes from object storage. Use the object storage service if the URL is an internal MinIO/S3 path. If external CDN URL, attempt fetch but catch 403/404 and skip gracefully.
     - Detect format from `asset_format` column: if `"IMAGE"`, use `PIL.Image.open(io.BytesIO(bytes)).size` to get `(width, height)`. If `"VIDEO"`, write bytes to a temp file, use `imageio_ffmpeg.read_frames(tmp_path)`, call `meta = next(reader)`, extract `meta["size"]` for `(width, height)` and `meta.get("duration")` for duration. Close reader in try/finally.
     - Update asset row: `asset.width = w`, `asset.height = h`, and if duration found and `asset.video_duration` is None, set it.
     - Commit every 50 assets.
   - Log summary: `"Media metrics backfill complete: {updated}/{total} assets updated"`
   - Import: `from PIL import Image`, `import imageio_ffmpeg`, `import io`, `import tempfile`

2. **Admin endpoint** (`scoring.py`):
   - Add after the existing `/admin/backfill` endpoint (~line 27):
     ```python
     @router.post("/admin/backfill-media-metrics", status_code=202)
     async def admin_backfill_media_metrics(
         background_tasks: BackgroundTasks,
         current_admin: User = Depends(get_current_admin),
     ):
         background_tasks.add_task(run_media_metrics_backfill)
         return {"status": "queued", "message": "Media metrics backfill started"}
     ```
   - Import `run_media_metrics_backfill` from `scoring_job`.

3. **Schema update** (`schemas/creative.py`):
   - Add to `CreativeAssetResponse` (after `video_duration` line 98):
     ```python
     width: Optional[int] = None
     height: Optional[int] = None
     ```

4. **Dashboard API** (`dashboard.py`):
   - In `get_asset_detail` response dict (~line 651), add after `"video_duration"`:
     ```python
     "width": asset.width,
     "height": asset.height,
     ```

5. **Frontend — asset detail dialog** (`asset-detail-dialog.component.ts`):
   - Add `width?: number | null;` and `height?: number | null;` to `AssetDetailResponse` interface (after `video_duration` ~line 109).
   - In the template, near the existing duration display (~line 228), add a dimensions display:
     ```html
     <span class="perf-dimension" *ngIf="detail?.width && detail?.height">
       {{ detail!.width }}x{{ detail!.height }}
     </span>
     ```
   - Style `.perf-dimension` to match `.perf-duration` styling.

6. **Frontend — dashboard tile** (`dashboard.component.ts`):
   - Optional: If the main tile grid shows `asset_format`, consider adding dimensions inline. But the main dashboard tiles do NOT currently show video_duration or dimensions in the grid — they only show in the detail dialog. Keep consistent: only show in detail dialog. No changes to dashboard.component.ts tile grid needed unless the format column already shows dimensions.
  </action>
  <verify>
    <automated>cd /Users/sebastian.dettweiler/Claude\ Code/platform-connector/brainsuite-platform-connector && python -c "from backend.app.schemas.creative import CreativeAssetResponse; r = CreativeAssetResponse(id='00000000-0000-0000-0000-000000000000', platform='META', ad_id='1', is_active=True, width=1920, height=1080); assert r.width == 1920 and r.height == 1080; print('Schema OK')" && cd frontend && npx ng build --configuration=production 2>&1 | tail -5</automated>
  </verify>
  <done>
    - POST /scoring/admin/backfill-media-metrics returns 202 and queues background task
    - Backfill function reads assets with NULL width/height, extracts from stored files, updates DB
    - API responses include width and height fields
    - Asset detail dialog shows dimensions (e.g., "1920x1080") when available
    - Frontend builds without errors
  </done>
</task>

</tasks>

<verification>
1. Migration: `alembic upgrade head` succeeds, `\d creative_assets` shows width/height INTEGER columns
2. Schema: `CreativeAssetResponse` includes width, height fields
3. Endpoint: `curl -X POST /scoring/admin/backfill-media-metrics` with admin auth returns 202
4. Frontend: `ng build --configuration=production` succeeds
5. Detail dialog: Open any asset detail — dimensions display when width/height are populated
</verification>

<success_criteria>
- width and height Integer columns exist on creative_assets table
- All 4 platform harmonizers forward available dimension/duration data to _ensure_asset
- Backfill admin endpoint exists and processes assets with missing metrics
- Asset detail API returns width, height, video_duration
- Frontend detail dialog renders dimensions when present
</success_criteria>

<output>
After completion, create `.planning/quick/260407-lxk-fix-missing-asset-media-metrics-add-dura/260407-lxk-SUMMARY.md`
</output>
