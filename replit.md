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
The DV360 integration uses two separate Google APIs:
- **DV360 API v4** (`displayvideo.googleapis.com/v4`): OAuth advertiser listing + entity metadata (campaigns, insertion orders, line items, creatives). Provides creative thumbnails/assets and campaign hierarchy fallback.
- **Bid Manager API v2** (`doubleclickbidmanager.googleapis.com/v2`): Reporting queries with 20 groupBys (date, advertiser name/currency/timezone, ad position/type, IO/IO goal type, LI/LI type, creative ID/type/source, channel ID/type/name, media plan/name, media type) and 25 metrics (impressions, clicks, CTR, spend, eCPM, eCPC, eCPA, conversions, post-click/view conversions, revenue, TrueView views/view rate, video quartiles/completions/plays, viewability, engagements, billable impressions). **API-incompatible** (removed): FILTER_YOUTUBE_AD_VIDEO_ID, METRIC_AVERAGE_IMPRESSION_FREQUENCY_PER_USER, METRIC_BILLABLE_COST_ADVERTISER — these cause "invalid combination" errors even individually or in minimal queries.
- Sync flow: fetch v4 entity maps → run Bid Manager report → parse CSV (dimensions now come directly from CSV) → download creative assets (images via httpx, videos via yt-dlp) → upsert into `dv360_raw_performance`.
- Asset downloading: YouTube videos downloaded via yt-dlp (using `youtube_ad_video_id` from CSV), thumbnails from YouTube CDN, DV360 image creatives via httpx. Assets stored in `static/creatives/{org_id}/`. Video duration extracted via ffprobe.
- Key files: `dv360_oauth.py` (OAuth + advertiser listing via v4), `dv360_sync.py` (entity metadata via v4 + reporting via Bid Manager v2 + asset downloading).

## Recent Changes
- 2026-02-26: DV360 harmonization fix — Root cause: CurrencyConverterService._cache_rate() called db.rollback() on duplicate key, which corrupted the outer SAVEPOINT and caused cascading InFailedSQLTransactionError for all subsequent records. Fix: wrapped cache insert in begin_nested() instead of raw rollback. Added in-memory rate cache to avoid repeated API/DB calls (1617 records now harmonize in <60s instead of 30+ min). Also widened harmonized_performance.publisher_platform/platform_position columns from varchar(100) to varchar(500) — DV360 channel names can be very long. Migration: h9i0j1k2l3m4. Result: 1617 raw → 1616 harmonized (1 dupe asset skip), 70 creative assets created.
- 2026-02-26: DV360 Bid Manager query validated — Systematically tested all filters/metrics against live API. Removed 3 API-incompatible items: FILTER_YOUTUBE_AD_VIDEO_ID, METRIC_AVERAGE_IMPRESSION_FREQUENCY_PER_USER, METRIC_BILLABLE_COST_ADVERTISER (all cause "invalid combination" errors even in isolation). Final validated query: 20 groupBys + 25 metrics, confirmed working via API query creation. DB columns retained for potential v4 metadata population.
- 2026-02-26: DV360 comprehensive expansion — Added 14 new Bid Manager groupBys (FILTER_ADVERTISER_NAME/TIMEZONE, AD_POSITION/TYPE, CHANNEL_ID/TYPE/NAME, IO_GOAL_TYPE, MEDIA_PLAN/NAME, LINE_ITEM_TYPE, CREATIVE_TYPE/SOURCE, MEDIA_TYPE) and 4 new metrics (BILLABLE_IMPRESSIONS, TRUEVIEW_VIEW_RATE, MEDIA_COST_ECPA). Added 11 new DB columns (ad_position, advertiser_timezone, channel_id/type/name, io_goal_type, youtube_ad_video_id, media_type, video_url, billable_cost, average_impression_frequency). Removed deprecated `exchange` and `rich_media_interactions` columns. Implemented creative asset downloading: images via httpx, YouTube videos via yt-dlp, video duration via ffprobe. Updated CSV→DB mapping to use dimensions directly from Bid Manager CSV. Updated harmonizer: publisher_platform from channel_name/media_type, platform_position from ad_position, expanded platform_extras JSONB. Migration: g8h9i0j1k2l3.
- 2026-02-26: DV360 sync fixes — Fixed date parsing (CSV YYYY/MM/DD strings now parsed to Python date objects before DB insert). Batched upserts in groups of 100 rows to avoid exceeding PostgreSQL parameter limits. Removed unnecessary 30-day chunking (single Bid Manager report for full date range). Normalized ad_id fallback to use ISO date format.
- 2026-02-26: DV360 API v4 entity metadata integration — sync now fetches campaigns, insertion orders, line items, and creatives from DV360 API v4 to enrich Bid Manager report records with proper names, types, creative details, and campaign hierarchy (campaign→IO→LI). Upsert now updates metadata fields on conflict. Restored `campaign_id` field via IO→campaign lookup since Bid Manager v2 removed `FILTER_CAMPAIGN_ID`.
- 2026-02-25: Added YouTube cookie authentication for yt-dlp video downloads. `YOUTUBE_COOKIES` env var (Netscape cookie format) is written to a temp file at runtime and passed to yt-dlp via `cookiefile` option. Cookies expire periodically and need manual refresh.
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
