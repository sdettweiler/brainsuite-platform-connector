# Brainsuite Platform Connector

## Overview
A platform connector tool that integrates with Meta, TikTok, and YouTube/Google advertising platforms. Built with a FastAPI backend and Angular 17 frontend, using PostgreSQL for data storage.

## Architecture
- **Backend**: Python 3.12 + FastAPI (served via uvicorn on port 5000)
- **Frontend**: Angular 17 (production build served as static files by FastAPI)
- **Database**: PostgreSQL (Replit-managed)
- **Charts**: ngx-echarts (Apache ECharts for Angular)
- **ORM**: SQLAlchemy 2.0 (async with asyncpg)
- **Migrations**: Alembic

## Project Structure
```
backend/
  app/
    api/v1/          # REST API endpoints
    core/            # Config, security
    db/              # Database session/base
    models/          # SQLAlchemy models
    schemas/         # Pydantic schemas
    services/        # Business logic, sync scheduler
  alembic/           # Database migrations
  requirements.txt   # Python dependencies
frontend/
  src/               # Angular source
  angular.json       # Angular CLI config
  package.json       # Node dependencies
replit_start.sh      # Startup script (installs deps, runs migrations, starts server)
```

## Key Configuration
- The startup script (`replit_start.sh`) handles dependency installation, database migrations, and launching the server
- FastAPI serves both the API (`/api/v1/`) and the Angular SPA (static files)
- Database URL is auto-configured from Replit's `DATABASE_URL` environment variable
- CORS is auto-configured for the Replit domain
- **Deployment**: `deploymentTarget = "autoscale"`, `build.sh` builds frontend only, `replit_start.sh` handles everything at runtime. Do NOT change to `vm` or move runtime setup into `build.sh` — the original config works and has been tested.
- **bcrypt**: Must stay pinned to 4.0.1

## Design System
- **Typography**: Nunito Sans (web fallback for Avenir Next) — Headlines: Demi Bold, Sub Headlines: Medium, Body: Regular
- **Primary Colors**: True White (#FFFFFF), Asphalt Black (#1B1B1B), Dusky Blue (#04093A)
- **Secondary Colors**: Deep Blue (#0009BC), Juicy Orange (#FF7700)
- **Brand Gradient**: 45deg from #DF4742 → #EC7235 → #F38A2E
- **Icons**: Bootstrap Icons (via `bootstrap-icons` npm package, CSS imported in `styles.scss`). All icons use `<i class="bi bi-xxx"></i>` syntax. Material Icons (`MatIconModule`) fully removed — no `<mat-icon>` elements remain. Note: `mat-icon-button` directives are still used for Angular Material button styling.
- **CSS Variables**: All colors use CSS custom properties defined in `styles.scss` (--accent, --bg-primary, etc.)
- **Logo Assets**: Located in `frontend/src/assets/images/` (orange, white, black, orange-white, signet variants)

## OAuth Redirect URIs
- Redirect URIs are now derived dynamically from the incoming HTTP request's `Host` header at runtime
- `settings.get_redirect_uri_from_request(request, platform)` builds the URI from the request origin
- OAuth handlers (`meta_oauth`, `tiktok_oauth`, `google_ads_oauth`, `dv360_oauth`) accept `redirect_uri` as an optional parameter
- The redirect URI is stored in the in-memory OAuth session so the callback handler uses the same URI that was sent during init
- Pattern: `https://{request_host}/api/v1/platforms/oauth/callback/{meta|tiktok|google|dv360}`
- `_get_base_url()` in `config.py` detects deployment vs dev via `REPLIT_DEPLOYMENT` env var

## DV360 Dual-API Architecture
The DV360 integration uses two separate Google APIs with a **two-report YOUTUBE architecture**:
- **DV360 API v4** (`displayvideo.googleapis.com/v4`): OAuth advertiser listing + entity metadata (campaigns, insertion orders, line items, creatives, **ad groups, ad group ads**, **advertiser timezone**). Provides creative thumbnails/assets, campaign hierarchy fallback, YouTube video ID retrieval via adGroupAds chain, and **dimension backfill** for all fields removed from the Bid Manager report.
- **Bid Manager API v2** (`doubleclickbidmanager.googleapis.com/v2`): Single YOUTUBE-type performance report:
  - **11 confirmed-working metrics** (YOUTUBE + FILTER_YOUTUBE_AD_VIDEO_ID):
    - **Core**: `METRIC_IMPRESSIONS`, `METRIC_CLICKS`, `METRIC_CTR`
    - **Spend/Cost**: `METRIC_MEDIA_COST_ADVERTISER`, `METRIC_MEDIA_COST_ECPM_ADVERTISER`, `METRIC_MEDIA_COST_ECPC_ADVERTISER`, `METRIC_REVENUE_ADVERTISER`
    - **Video**: `METRIC_TRUEVIEW_VIEWS`, `METRIC_TRUEVIEW_VIEW_RATE`, `METRIC_VIDEO_COMPLETION_RATE`, `METRIC_TRUEVIEW_CPV_ADVERTISER`
  - **Confirmed INCOMPATIBLE metrics** (all rejected by API with YOUTUBE + FILTER_YOUTUBE_AD_VIDEO_ID):
    - `METRIC_CLICK_RATE` (use `METRIC_CTR` instead)
    - `METRIC_VIDEO_COMPLETE_IMPRESSIONS`, `METRIC_VIDEO_FIRST/MIDPOINT/THIRD_QUARTILE_IMPRESSIONS`, `METRIC_VIDEO_SKIPS`
    - `METRIC_ACTIVE_VIEW_MEASURABLE_IMPRESSIONS`, `METRIC_ACTIVE_VIEW_VIEWABLE_IMPRESSIONS`, `METRIC_ACTIVE_VIEW_PERCENT_VIEWABLE_IMPRESSIONS`
    - `METRIC_VIDEO_COMPANION_IMPRESSIONS`, `METRIC_VIDEO_COMPANION_CLICKS`
    - `METRIC_BILLABLE_IMPRESSIONS`, `METRIC_ENGAGEMENTS`
    - ALL conversion metrics: `METRIC_TOTAL_CONVERSIONS`, `METRIC_POST_CLICK_CONVERSIONS`, `METRIC_POST_VIEW_CONVERSIONS`, `METRIC_REVENUE_CONVERSION_COST_ADVERTISER`
  - Conversion report disabled (returns []) — no conversion metrics work with this report type.
  - Uses 8 groupBys: `FILTER_DATE`, `FILTER_ADVERTISER`, `FILTER_ADVERTISER_NAME`, `FILTER_ADVERTISER_CURRENCY`, `FILTER_INSERTION_ORDER`, `FILTER_LINE_ITEM`, `FILTER_LINE_ITEM_TYPE`, `FILTER_YOUTUBE_AD_VIDEO_ID`.
- **Asset format**: DV360 YouTube assets use `asset_format = "VIDEO"` (set when `youtube_ad_video_id` is present). Frontend shows `<video>` player for VIDEO format in detail view.
- **Dimension backfill from v4 API**: advertiser_timezone → `advertisers/{id}` generalConfig.timeZone; campaign_id/name → IO.campaignId + campaigns map; io_goal_type → IO.performanceGoal; creative_type → adGroupAd format (In-Stream/Bumper/Video Performance/etc); media_type → derived from line_item_type; ad_type → adGroupAd format label; creative_source → "YouTube" for all video ads.
- **YouTube Video ID retrieval**: Primary source is the Bid Manager CSV column `Video ID` (from `FILTER_YOUTUBE_AD_VIDEO_ID`). Fallback via adGroupAds chain: `_fetch_ad_groups()` maps adGroupId→lineItemId, `_fetch_ad_group_ads()` extracts YouTube video IDs.
- **YouTube oEmbed metadata**: `_fetch_youtube_metadata()` calls `youtube.com/oembed?url=...&format=json` (no auth required) for each unique video ID to get video title and builds maxresdefault thumbnail URL from YouTube CDN.
- **Cookie validation**: `_check_youtube_cookies(env_var)` validates cookie env vars before yt-dlp attempts: checks Netscape cookie format expiry timestamps, returns valid/expired/missing. Expired/missing cookies skip video downloads but still download thumbnails.
- **Dual-cookie fallback**: `YOUTUBE_COOKIES` (primary) and `YOUTUBE_COOKIES_BACKUP` (backup) env vars. `_get_cookie_env_vars_to_try()` returns ordered list of valid cookie sets. `_download_video_asset()` tries primary cookies first, falls back to backup on failure ("no longer valid" / "Sign in"). If both expired, only thumbnails are downloaded.
- **Post-commit asset downloads**: Asset downloads (yt-dlp videos, YouTube thumbnails, images) happen AFTER DB upsert+commit via `download_assets_post_commit()`. `_upsert_records()` returns `(count, asset_queue)` tuple; scheduler commits data first, then runs asset downloads as a separate non-fatal step. This prevents DB connection timeouts from slow yt-dlp retries causing data loss.
- **Asset-level aggregation**: `ad_id` = YouTube video ID (matching Meta/TikTok pattern where ad_id = platform creative identifier). Multiple line items sharing the same video aggregate metrics (sum additive, recalculate derived) into one row per video per date. Additive fields: spend, impressions, clicks, trueview_views, video_views, total_media_cost.
- **Fields**: `cost_per_view` (from `METRIC_TRUEVIEW_CPV_ADVERTISER`), `total_media_cost` (from `METRIC_REVENUE_ADVERTISER`), `video_plays` intentionally `None` (no YouTube "starts" metric). Video quartiles, skips, active_view, companion, billable, engagements all set to None (metrics incompatible with YOUTUBE + FILTER_YOUTUBE_AD_VIDEO_ID).
- Sync flow: fetch v4 entity maps → run Report 1 (performance) → run Report 2 (conversion, non-fatal) → fetch YouTube oEmbed metadata → parse CSV + backfill from v4 → upsert performance rows → merge conversion rows → download creative assets.
- Key files: `dv360_oauth.py` (OAuth + advertiser listing via v4), `dv360_sync.py` (entity metadata via v4 + reporting via Bid Manager v2 + oEmbed + asset downloading).

## Production Resilience
- **Non-blocking startup**: Migrations + scheduler run as a background `asyncio.create_task()` in the lifespan. Uvicorn starts and responds to health checks immediately. Migrations run via `run_in_executor` (sync Alembic in thread), then URL migration runs, then scheduler starts.
- **Build-time pip install**: `build.sh` installs Python dependencies during the build phase so they're baked into the deployment artifact. `replit_start.sh` skips pip install at runtime via marker file.
- **Object Storage**: Creative assets (thumbnails, videos) stored in Replit Object Storage (GCS bucket) for persistence across autoscale containers. `backend/app/services/object_storage.py` handles upload/download via `google.auth.identity_pool` credentials through the Replit sidecar (`127.0.0.1:1106`). Assets served via `/objects/creatives/{org_id}/{filename}` route in `main.py`. DV360 sync downloads files locally (temp), uploads to object storage, then cleans up local files. Startup runs a one-time URL migration replacing `/static/creatives/` with `/objects/creatives/` in all raw performance and creative_assets tables.
- **Deadlock retry**: All harmonization calls wrapped in `_harmonize_with_deadlock_retry()` — retries up to 3x with exponential backoff on `DeadlockDetectedError` (scheduler.py)
- **YouTube download throttling**: 4s delay between consecutive yt-dlp downloads to avoid bot detection / cookie invalidation from datacenter IPs (dv360_sync.py)
- **Error message format**: All exception logs use `{type(e).__name__}: {e}` pattern (not bare `{e}`) to avoid empty messages from httpx/asyncpg exceptions. Full tracebacks logged in sync error handlers.

## Recent Changes
- 2026-03-03: DV360 sync stability + currency fix — (1) Split DV360 sync into poll phase (no DB session) + upsert phase (fresh DB session). All 4 scheduler paths (daily, initial, historical, full_resync) now: open session → get token → close session → poll Bid Manager API (up to 2h, no DB held) → open fresh session → upsert + harmonize. `_refresh_token_standalone()` uses its own lightweight session for mid-poll token refresh, preventing `InterfaceError: connection is closed`. (2) Currency service: switched primary from exchangerate-api.com to frankfurter.dev (`https://api.frankfurter.dev/v1/`), 0.3s delay between API calls, exchangerate-api.com disabled after 429 via class-level flag `_exchangerate_api_disabled`. (3) Removed iOS player client from yt-dlp config (incompatible with cookies, only `web` kept).
- 2026-03-03: DV360 asset download fix — (1) `download_assets_post_commit()` restructured to two-pass: thumbnails first (with immediate DB commit), then videos. Ensures thumbnails always persist even when video downloads fail/timeout. (2) yt-dlp: `remote_components: {"ejs:github"}` added to auto-download YouTube's JS challenge solver (fixes "n challenge solving failed" without needing deno); format `bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b` with merge_output_format mp4; `extractor_args` with `ios`+`web` player clients as additional bypass; socket_timeout 15s; `imageio-ffmpeg` pip package added for production ffmpeg binary (yt-dlp `ffmpeg_location` set automatically). (3) Format-not-available errors now break immediately instead of retrying with backup cookies (same root cause, not a cookie issue).
- 2026-03-03: DV360 deployment stability fixes — (1) Asset downloads in separate DB session: `_run_dv360_asset_downloads()` opens a fresh session for yt-dlp downloads, preventing connection pool exhaustion during concurrent syncs. Main sync session is closed before downloads begin. (2) Alembic migration startup made idempotent: checks `alembic current` first, stamps head if DB exists but has no version tracking, falls back gracefully on DuplicateTable. (3) Upsert batch size reduced from 100→25 rows to lower parameter count and reduce DB connection hold time.
- 2026-03-03: DV360 stability fixes — (1) Moved asset downloads (yt-dlp videos, thumbnails) to post-DB-commit phase: `_upsert_records` returns `(count, asset_queue)` tuple, scheduler commits data first, then runs `download_assets_post_commit()` as non-fatal step. Prevents DB connection timeouts from slow downloads causing data loss. (2) Dual YouTube cookie fallback: `_check_youtube_cookies(env_var)` now parameterized, `_get_cookie_env_vars_to_try()` returns valid cookie sets in priority order, `_download_video_asset()` tries primary then backup cookies. (3) When both cookie sets expired, skips all yt-dlp calls but still downloads thumbnails via CDN. All 4 sync paths (daily, initial, historical, full resync) updated with post-commit asset handling.
- 2026-03-02: DV360 metric revert — Confirmed that VIDEO_COMPLETE_IMPRESSIONS, quartiles, SKIPS, ACTIVE_VIEW_*, COMPANION_*, BILLABLE_IMPRESSIONS, ENGAGEMENTS, and ALL conversion metrics are incompatible with YOUTUBE + FILTER_YOUTUBE_AD_VIDEO_ID. Reverted to original 11 confirmed-working metrics. Conversion report disabled (returns []). Kept: asset_format VIDEO fix, safe_float % stripping, /static proxy route, expanded CSV column name fallbacks.
- 2026-02-27: Two-report YOUTUBE architecture attempt — Discovered most VIDEO_*, ACTIVE_VIEW_*, COMPANION_*, ENGAGEMENTS, BILLABLE_*, and all conversion metrics are incompatible with YOUTUBE + FILTER_YOUTUBE_AD_VIDEO_ID. Reverted to single 11-metric report. Added `cost_per_view` column (migration k2l3m4n5o6p7) and `video_skips` column (migration j1k2l3m4n5o6). Adaptive polling (30s→60s→120s intervals, 2-hour max wait) with automatic OAuth token refresh handles long-running YouTube reports.
- 2026-02-27: FILTER_YOUTUBE_AD_VIDEO_ID restored + metric slimming — Added FILTER_YOUTUBE_AD_VIDEO_ID back to Bid Manager groupBys (now 8 total). Removed 14 incompatible metrics (total_media_cost, total_conversions, post-click/view conversions, all rich_media video quartile/completion/play metrics, all active_view metrics, billable_impressions, eCPA). Report now has 11 metrics. CSV video ID is primary ad_id source (fallback to adGroupAds). `line_item_videos` stores ALL video IDs per line item. `video_metadata` flat dict for ad_type_label lookup. Fresh YouTube cookies stored cleanly.
- 2026-02-27: Slimmed Bid Manager report + v4 backfill architecture — Removed 10 groupBys from Bid Manager report (timezone, ad position/type, IO goal type, creative ID/type/source, media plan/name, media type) that were incompatible with YouTube Video ID. Report now uses 7 groupBys only. All removed dimensions backfilled from DV360 v4 API entity metadata: advertiser timezone via advertisers endpoint, campaign ID/name via IO→campaign chain, IO goal type from performanceGoal, creative type from adGroupAd format, media type derived from line item type. Added YouTube oEmbed metadata fetching for video titles and hi-res thumbnails. Fixed videoPerformanceAd parsing to handle `videos[]` array format. Added yt-dlp cookie expiry validation (check before download, skip gracefully if expired/missing). EntityMaps expanded with advertiser_timezone and youtube_metadata fields.
- 2026-02-26: Removed channel_id, channel_type, channel_name from DV360 — dropped FILTER_CHANNEL_ID/TYPE/NAME from Bid Manager query (20→17 groupBys), removed columns from Dv360RawPerformance model, removed from CSV parsing and ON CONFLICT upsert, removed from harmonizer platform_extras. Updated publisher_platform to use media_type only. Migration: i0j1k2l3m4n5.
- 2026-02-26: DV360 YouTube video ID retrieval via adGroupAds — Since FILTER_YOUTUBE_AD_VIDEO_ID is incompatible with Bid Manager API and DV360 v4 creatives returns 0 results for YouTube & Partners campaigns, implemented alternative retrieval via DV360 v4 `adGroupAds` endpoint chain. New methods: `_fetch_ad_groups()` (maps adGroupId→lineItemId), `_fetch_ad_group_ads()` (extracts video IDs from inStreamAd/bumperAd/nonSkippableAd/etc). Added `line_item_videos` field to `EntityMaps` NamedTuple. During CSV parsing, lineItemId is used to look up video IDs from entity maps when not present in CSV. Result: 12 line items mapped to 6 unique YouTube video IDs, 137 records populated with video IDs, 6 thumbnails downloaded. Video downloads require YouTube OAuth cookies (private ad creatives).
- 2026-02-26: DV360 harmonization fix — Root cause: CurrencyConverterService._cache_rate() called db.rollback() on duplicate key, which corrupted the outer SAVEPOINT and caused cascading InFailedSQLTransactionError for all subsequent records. Fix: wrapped cache insert in begin_nested() instead of raw rollback. Added in-memory rate cache to avoid repeated API/DB calls (1617 records now harmonize in <60s instead of 30+ min). Also widened harmonized_performance.publisher_platform/platform_position columns from varchar(100) to varchar(500) — DV360 channel names can be very long. Migration: h9i0j1k2l3m4. Result: 1617 raw → 1616 harmonized (1 dupe asset skip), 70 creative assets created.
- 2026-02-26: DV360 Bid Manager query validated — Systematically tested all filters/metrics against live API. Removed 3 API-incompatible items: FILTER_YOUTUBE_AD_VIDEO_ID, METRIC_AVERAGE_IMPRESSION_FREQUENCY_PER_USER, METRIC_BILLABLE_COST_ADVERTISER (all cause "invalid combination" errors even in isolation). Final validated query: 20 groupBys + 25 metrics, confirmed working via API query creation. DB columns retained for potential v4 metadata population.
- 2026-02-26: DV360 comprehensive expansion — Added 14 new Bid Manager groupBys (FILTER_ADVERTISER_NAME/TIMEZONE, AD_POSITION/TYPE, CHANNEL_ID/TYPE/NAME, IO_GOAL_TYPE, MEDIA_PLAN/NAME, LINE_ITEM_TYPE, CREATIVE_TYPE/SOURCE, MEDIA_TYPE) and 4 new metrics (BILLABLE_IMPRESSIONS, TRUEVIEW_VIEW_RATE, MEDIA_COST_ECPA). Added 11 new DB columns (ad_position, advertiser_timezone, channel_id/type/name, io_goal_type, youtube_ad_video_id, media_type, video_url, billable_cost, average_impression_frequency). Removed deprecated `exchange` and `rich_media_interactions` columns. Implemented creative asset downloading: images via httpx, YouTube videos via yt-dlp, video duration via ffprobe. Updated CSV→DB mapping to use dimensions directly from Bid Manager CSV. Updated harmonizer: publisher_platform from channel_name/media_type, platform_position from ad_position, expanded platform_extras JSONB. Migration: g8h9i0j1k2l3.
- 2026-02-26: DV360 sync fixes — Fixed date parsing (CSV YYYY/MM/DD strings now parsed to Python date objects before DB insert). Batched upserts in groups of 100 rows to avoid exceeding PostgreSQL parameter limits. Removed unnecessary 30-day chunking (single Bid Manager report for full date range). Normalized ad_id fallback to use ISO date format.
- 2026-02-26: DV360 API v4 entity metadata integration — sync now fetches campaigns, insertion orders, line items, and creatives from DV360 API v4 to enrich Bid Manager report records with proper names, types, creative details, and campaign hierarchy (campaign→IO→LI). Upsert now updates metadata fields on conflict. Restored `campaign_id` field via IO→campaign lookup since Bid Manager v2 removed `FILTER_CAMPAIGN_ID`.
- 2026-02-25: Added YouTube cookie authentication for yt-dlp video downloads. `YOUTUBE_COOKIES` env var (Netscape cookie format) is written to a temp file at runtime and passed to yt-dlp via `cookiefile` option. Cookies expire periodically and need manual refresh. yt-dlp requires `deno` system dependency (installed via Nix) as JavaScript runtime for YouTube extraction.
- 2026-02-25: Fixed OAuth redirect URIs for deployment — removed static `META_REDIRECT_URI`/`TIKTOK_REDIRECT_URI`/`GOOGLE_REDIRECT_URI`/`DV360_REDIRECT_URI` config fields. Redirect URIs are now computed at request time from the HTTP Host header, ensuring they match the actual domain (dev or production) the user is accessing. OAuth handlers accept `redirect_uri` parameter; `init_oauth` endpoint derives URI from request and stores in session for callback use.
- 2026-02-25: Security dependency updates — Backend: aiohttp 3.9.1→3.9.4, cryptography 41.0.7→42.0.4, fastapi 0.104.1→0.115.0, python-jose 3.3.0→3.4.0, python-multipart 0.0.6→0.0.7. Frontend: Angular 16→17 (all @angular/* and @ngrx/* packages), zone.js 0.13→0.14, typescript 5.1→5.2, ngx-skeleton-loader 7→9. npm overrides applied for minimatch→10.2.3 and tar→7.5.9 (transitive build-tool deps).
- 2026-02-23: Bootstrap Icons migration complete — replaced all Material Icons (`<mat-icon>`) with Bootstrap Icons (`<i class="bi bi-xxx">`) across all 15 component files (sidebar, header, home, dashboard, comparison, 4 dialogs, 4 config pages, date-range-picker). Removed all `MatIconModule` imports. Icon CSS loaded via `styles.scss`. Key mappings: home→house, bar_chart→bar-chart, compare→arrow-left-right, settings→gear, close→x-lg, add→plus-lg, etc.
- 2026-02-23: Connections page rebuild — replaced flat card list with server-side paginated table view. Backend: GET /connections now returns `{items, total, page, page_size, status_summary}` with search (name/ID), platform filter (comma-separated), status filter, sort_by/sort_order, pagination params. Added POST /connections/bulk-action for resync/disconnect/assign_image_app/assign_video_app on multiple connections. Frontend: compact table with checkboxes, platform badges, inline app mapping dropdowns, status chips, search bar with debounce, platform filter chips, status dropdown, sort controls, pagination bar (25/50/100 per page), bulk action bar (resync/disconnect/assign app), status summary bar. Styles extracted to platforms.component.scss.
- 2026-02-20: Field reference v4 migration — major expansion of all 4 performance models. Meta +45 cols (creative metadata from /adcreatives enrichment, publisher_platform/platform_position breakdowns, quality/engagement/conversion rankings, app install/offline/messaging/on-facebook conversion metrics, unique outbound clicks, video 3-sec views). TikTok +44 cols (campaign/adgroup status, creative asset details, interactive add-on metrics, app/page/onsite/live commerce metrics, secondary goals, gross impressions, 7-day frequency, CTA/VTA attribution). YouTube +8 cols (ad network/format types, impression share, video 30s views, earned views). Harmonized +21 cols (app installs, in-app purchases, subscribe, offline, messaging, ad recall, quality rankings, unique clicks, video 3/30 sec watched). Removed deprecated TikTok paid_* metrics from sync (paid_likes/comments/shares/follows deprecated in API v1.3 Aug 2023). Meta sync now fetches creative metadata via Graph API field expansion on /ads endpoint. Migration: e6f7g8h9i0j1.
- 2026-02-19: Field reference v3 migration — expanded all 4 performance models (Meta +44 cols, TikTok +56 cols, YouTube +38 cols, Harmonized +26 cols). Updated Meta sync to fetch ~60 fields including individual conversion breakdowns (purchase/lead/subscribe), video quartiles, engagement metrics. Updated TikTok sync with expanded metrics + /ad/get/ call for creative/dimension fields. Updated harmonizer for all 3 platforms with new field mappings including YouTube quartile rate→count conversion. Made db/base.py engine creation lazy to fix Alembic migration compatibility. Migration: d5e6f7g8h9i0.
- 2026-02-19: Multi-step signup flow with Organization create/join, join request approval workflow, in-app notifications with badge, pending users section on org page
- 2026-02-19: Complete UI rework — brand colors (Juicy Orange + Dusky Blue), Nunito Sans typography, actual brand logos, comprehensive Material Design overrides for inputs/dropdowns/dialogs
- 2026-02-19: Imported project to Replit, fixed Angular build errors, configured for port 5000, fixed database connectivity

## User Preferences
- Brand-first design: All UI elements must use the Brainsuite design system colors and typography
- bcrypt must stay pinned to version 4.0.1 due to passlib compatibility
