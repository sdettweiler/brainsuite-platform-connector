# Brainsuite Platform Connector

## Overview
A platform connector tool that integrates with Meta, TikTok, and YouTube/Google advertising platforms. Built with a FastAPI backend and Angular 16 frontend, using PostgreSQL for data storage.

## Architecture
- **Backend**: Python 3.12 + FastAPI (served via uvicorn on port 5000)
- **Frontend**: Angular 16 (production build served as static files by FastAPI)
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
- **CSS Variables**: All colors use CSS custom properties defined in `styles.scss` (--accent, --bg-primary, etc.)
- **Logo Assets**: Located in `frontend/src/assets/images/` (orange, white, black, orange-white, signet variants)

## Recent Changes
- 2026-02-23: Connections page rebuild — replaced flat card list with server-side paginated table view. Backend: GET /connections now returns `{items, total, page, page_size, status_summary}` with search (name/ID), platform filter (comma-separated), status filter, sort_by/sort_order, pagination params. Added POST /connections/bulk-action for resync/disconnect/assign_image_app/assign_video_app on multiple connections. Frontend: compact table with checkboxes, platform badges, inline app mapping dropdowns, status chips, search bar with debounce, platform filter chips, status dropdown, sort controls, pagination bar (25/50/100 per page), bulk action bar (resync/disconnect/assign app), status summary bar. Styles extracted to platforms.component.scss.
- 2026-02-20: Field reference v4 migration — major expansion of all 4 performance models. Meta +45 cols (creative metadata from /adcreatives enrichment, publisher_platform/platform_position breakdowns, quality/engagement/conversion rankings, app install/offline/messaging/on-facebook conversion metrics, unique outbound clicks, video 3-sec views). TikTok +44 cols (campaign/adgroup status, creative asset details, interactive add-on metrics, app/page/onsite/live commerce metrics, secondary goals, gross impressions, 7-day frequency, CTA/VTA attribution). YouTube +8 cols (ad network/format types, impression share, video 30s views, earned views). Harmonized +21 cols (app installs, in-app purchases, subscribe, offline, messaging, ad recall, quality rankings, unique clicks, video 3/30 sec watched). Removed deprecated TikTok paid_* metrics from sync (paid_likes/comments/shares/follows deprecated in API v1.3 Aug 2023). Meta sync now fetches creative metadata via Graph API field expansion on /ads endpoint. Migration: e6f7g8h9i0j1.
- 2026-02-19: Field reference v3 migration — expanded all 4 performance models (Meta +44 cols, TikTok +56 cols, YouTube +38 cols, Harmonized +26 cols). Updated Meta sync to fetch ~60 fields including individual conversion breakdowns (purchase/lead/subscribe), video quartiles, engagement metrics. Updated TikTok sync with expanded metrics + /ad/get/ call for creative/dimension fields. Updated harmonizer for all 3 platforms with new field mappings including YouTube quartile rate→count conversion. Made db/base.py engine creation lazy to fix Alembic migration compatibility. Migration: d5e6f7g8h9i0.
- 2026-02-19: Multi-step signup flow with Organization create/join, join request approval workflow, in-app notifications with badge, pending users section on org page
- 2026-02-19: Complete UI rework — brand colors (Juicy Orange + Dusky Blue), Nunito Sans typography, actual brand logos, comprehensive Material Design overrides for inputs/dropdowns/dialogs
- 2026-02-19: Imported project to Replit, fixed Angular build errors, configured for port 5000, fixed database connectivity

## User Preferences
- Brand-first design: All UI elements must use the Brainsuite design system colors and typography
- bcrypt must stay pinned to version 4.0.1 due to passlib compatibility
