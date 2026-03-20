# External Integrations

**Analysis Date:** 2026-03-20

## APIs & External Services

**Advertising Platforms:**
- Meta Ads API - Social media ad management
  - SDK/Client: httpx (async HTTP)
  - Auth: OAuth 2.0 via Facebook Login
  - Env vars: `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI`
  - Endpoint: `/api/v1/platforms/oauth/callback/meta`
  - Implementation: `backend/app/services/platform/meta_oauth.py`

- TikTok Ads API - Short-form video ad management
  - SDK/Client: httpx (async HTTP)
  - Auth: OAuth 2.0 via TikTok
  - Env vars: `TIKTOK_APP_ID`, `TIKTOK_APP_SECRET`, `TIKTOK_REDIRECT_URI`
  - Endpoint: `/api/v1/platforms/oauth/callback/tiktok`
  - Implementation: `backend/app/services/platform/tiktok_oauth.py`

- Google Ads API - Search and shopping ads
  - SDK/Client: httpx (async HTTP)
  - Auth: OAuth 2.0 via Google
  - Env vars: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_DEVELOPER_TOKEN`, `GOOGLE_REDIRECT_URI`
  - Endpoint: `/api/v1/platforms/oauth/callback/google`
  - Implementation: `backend/app/services/platform/google_ads_oauth.py`
  - Requires: Google Ads API v15+ developer token from ads.google.com

- DV360 (Display & Video 360) API - Programmatic display advertising
  - SDK/Client: httpx (async HTTP)
  - Auth: OAuth 2.0 via Google
  - Env vars: `DV360_CLIENT_ID`, `DV360_CLIENT_SECRET`
  - Implementation: `backend/app/services/platform/dv360_oauth.py`
  - Uses: Display & Video 360 API v4, Bid Manager API v2

**Currency Conversion:**
- ExchangeRate-API - Primary currency conversion service
  - Service: https://v6.exchangerate-api.com/v6
  - Auth: API key in headers
  - Env var: `EXCHANGERATE_API_KEY`
  - Fallback enabled with rate limiting (429 detection)
  - Implementation: `backend/app/services/currency.py`

- Frankfurter API - Free fallback currency conversion
  - Service: https://api.frankfurter.dev/v1
  - Auth: None required
  - Always tried first; ExchangeRate-API used only if key is configured
  - Implementation: `backend/app/services/currency.py`

**Video/Media:**
- yt-dlp - YouTube video metadata and download
  - Used for: Video asset retrieval
  - Package: `yt-dlp` (no specific version constraint)

## Data Storage

**Databases:**
- PostgreSQL 16
  - Connection (async): `postgresql+asyncpg://[user]:[pass]@[host]/[db]`
  - Connection (sync): `postgresql://[user]:[pass]@[host]/[db]` (for migrations)
  - ORM: SQLAlchemy 2.0 with asyncpg driver
  - Env vars: `DATABASE_URL`, `SYNC_DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
  - Container: `postgres:16-alpine` in Docker Compose
  - Migrations: Alembic (`backend/alembic/`)

**File Storage:**
- Google Cloud Storage - Primary file storage for creatives and assets
  - SDK: `google-cloud-storage >= 2.14.0`
  - Auth: External account credentials via Replit sidecar (`http://127.0.0.1:1106`)
  - Bucket config: `DEFAULT_OBJECT_STORAGE_BUCKET_ID` env var
  - Implementation: `backend/app/services/object_storage.py`
  - Operations: Upload, download, delete, list, generate signed URLs
  - Replit integration: Uses Replit identity pool for credential exchange

**Caching:**
- Redis - Configured but not actively observed in code
  - Connection: `REDIS_URL` env var (default: `redis://localhost:6379/0`)
  - Status: Referenced in config, no active usage in observed service code

## Authentication & Identity

**OAuth 2.0 Providers:**
- Meta (Facebook) - Multi-platform identity provider
  - Portal: https://developers.facebook.com/apps/
  - Required permissions: ads_read, ads_management, business_management, read_insights, pages_read_engagement
  - Redirect: Configured in Facebook App Settings

- TikTok - Advertiser authentication
  - Portal: https://ads.tiktok.com/marketing_api/apps/
  - Required scopes: ad.read, campaign.read, report.read
  - Redirect: Configured in TikTok App Settings

- Google - Multi-service identity provider
  - Portal: https://console.developers.google.com/
  - Required scopes: https://www.googleapis.com/auth/adwords, https://www.googleapis.com/auth/youtube.readonly
  - Required APIs: Google Ads API, YouTube Data API v3
  - Developer token: Required from https://ads.google.com/nav/selectaccount

**JWT Tokens:**
- Implementation: `backend/app/core/security.py`
- Algorithm: HS256
- Encryption: Fernet symmetric encryption for storing sensitive tokens
- Env var: `TOKEN_ENCRYPTION_KEY` (required for production)

**Session Management:**
- Access tokens: 30-minute expiry (configurable)
- Refresh tokens: 7-day expiry (configurable)
- In-memory OAuth session store: `backend/app/api/v1/endpoints/platforms.py` (replace with Redis in production)

## Monitoring & Observability

**Error Tracking:**
- Not detected - No explicit error tracking service (Sentry, etc.) configured

**Logs:**
- Python logging module - Standard Python logging
- Format: `%(levelname)s:%(name)s: %(message)s`
- Output: Console (suitable for Docker container logs)
- Uvicorn logs: HTTP access logs

## CI/CD & Deployment

**Hosting:**
- Replit - Primary deployment platform
  - Deployment target: Autoscale
  - Integrations: javascript_object_storage:2.0.0
  - Sidecar endpoint: `http://127.0.0.1:1106` (credentials and object storage)

**Build Process:**
- Build script: `bash build.sh`
- Run command: `bash replit_start.sh`
- Port binding: 5000 (backend), 4200 (frontend dev), 80 (frontend prod)

**CI Pipeline:**
- Not detected - No GitHub Actions, GitLab CI, or Jenkins configuration observed

## Environment Configuration

**Required env vars (critical):**
- `SECRET_KEY` - JWT signing key (generate: `openssl rand -hex 32`)
- `TOKEN_ENCRYPTION_KEY` - Token encryption (generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- `DATABASE_URL` - PostgreSQL async connection string
- `SYNC_DATABASE_URL` - PostgreSQL sync connection string (migrations)
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` - Database credentials

**Secrets location:**
- `.env` file (git-ignored, not committed)
- Example template: `.env.example` in root and `backend/.env.example`
- Production: Environment variables injected by Replit during deployment

## Webhooks & Callbacks

**Incoming:**
- `/api/v1/platforms/oauth/callback/meta` - Meta OAuth callback
- `/api/v1/platforms/oauth/callback/tiktok` - TikTok OAuth callback
- `/api/v1/platforms/oauth/callback/google` - Google OAuth callback
- `/api/v1/platforms/oauth/callback/dv360` - DV360 OAuth callback
- `/health` - Health check endpoint (for Docker container probes)

**Outgoing:**
- Not detected - No webhook subscription or outbound notifications configured

## API Rate Limiting & Handling

**Currency Conversion:**
- ExchangeRate-API: Detects 429 (Too Many Requests) and disables for process lifetime
- Frankfurter: Primary, always attempted first
- Fallback behavior: If both fail, returns 1.0 (no conversion)

**OAuth Session Store:**
- Current: In-memory dictionary (`_oauth_sessions`)
- Note: Must be replaced with Redis for production/multi-worker deployments
- Location: `backend/app/api/v1/endpoints/platforms.py`

## Data Integration Points

**Platform Connection Flow:**
1. OAuth initiation: User requests connection at `/api/v1/platforms/oauth/init`
2. Platform-specific handler: Generates authorization URL
3. Redirect: Browser redirected to platform OAuth provider
4. User consent: Platform OAuth provider handles authentication
5. Callback: Platform redirects to backend with authorization code
6. Token exchange: Backend exchanges code for access/refresh tokens
7. Account fetch: Backend queries platform API for accessible accounts
8. Account selection: User selects accounts to connect
9. Storage: Encrypted tokens stored in `PlatformConnection` model

**Data Sync:**
- Background scheduler: APScheduler for periodic syncs
- Sync services: `backend/app/services/sync/` directory
  - `meta_sync.py` - Meta Ads data sync
  - `tiktok_sync.py` - TikTok Ads data sync
  - `google_ads_sync.py` - Google Ads data sync
  - `dv360_sync.py` - DV360 data sync
  - `scheduler.py` - Background task coordination

---

*Integration audit: 2026-03-20*
