# Architecture

**Analysis Date:** 2026-03-20

## Pattern Overview

**Overall:** Full-stack multi-tenant SaaS application with decoupled frontend (Angular) and backend (FastAPI). Features event-driven data synchronization, OAuth platform integrations, and state management via NgRx. The system synchronizes ad platform data (Meta, TikTok, Google Ads, DV360) into a unified PostgreSQL database, harmonizes performance metrics, and exposes data through REST API.

**Key Characteristics:**
- Async/await throughout backend (FastAPI + SQLAlchemy async)
- Multi-tenancy enforced at organization level with role-based access control
- Scheduled background synchronization (APScheduler) for daily data pulls from ad platforms
- Encrypted token storage for platform OAuth credentials
- Data harmonization layer that normalizes metrics across platforms
- Standalone frontend (Angular Standalone Components) with lazy-loaded feature modules
- Store-based state management (NgRx) for auth state only; feature data via HTTP

## Layers

**API Layer (FastAPI):**
- Purpose: HTTP REST endpoints, request validation, response marshaling
- Location: `backend/app/api/v1/endpoints/`
- Contains: Router definitions for auth, platforms, dashboard, assets, users
- Depends on: Database, security middleware, service layer
- Used by: Frontend applications, OAuth callback handlers

**Service Layer:**
- Purpose: Business logic, platform integrations, data transformation
- Location: `backend/app/services/`
- Contains: OAuth handlers (`platform/`), sync orchestration (`sync/`), object storage, currency conversion, ACE scoring
- Depends on: Database, external APIs (Google Cloud Storage, platform SDKs, exchange rate APIs)
- Used by: API endpoints, scheduler

**Synchronization & Scheduling Layer:**
- Purpose: Background job execution, data pulls, harmonization
- Location: `backend/app/services/sync/`
- Contains: Platform-specific sync modules (`meta_sync.py`, `tiktok_sync.py`, `google_ads_sync.py`, `dv360_sync.py`), harmonizer, scheduler
- Depends on: Database, platform APIs, external SDKs
- Used by: Startup lifecycle, cron triggers

**Data Layer (Models & ORM):**
- Purpose: Domain entities, database schema, relationships
- Location: `backend/app/models/`
- Contains: User, Organization, PlatformConnection, CreativeAsset, HarmonizedPerformance, etc.
- Depends on: SQLAlchemy ORM, PostgreSQL dialect
- Used by: Service layer, endpoints, database migrations

**Database:**
- Type: PostgreSQL with async adapter (asyncpg)
- Session management: `backend/app/db/base.py` provides singleton engine and session factory
- Migrations: Alembic in `backend/alembic/` for schema versioning

**Frontend Layer (Angular):**
- Purpose: UI presentation, user interactions, state management
- Location: `frontend/src/app/`
- Contains: Components (auth, features, shared), services, guards, interceptors, store
- Depends on: Angular core, Material (implied by dialogs), HTTP client
- Used by: End users via browser

**Security Layer:**
- Purpose: Token generation/validation, password hashing, OAuth flow orchestration
- Location: `backend/app/core/security.py`
- Contains: JWT token creation/decoding, password verification, encryption utilities
- Depends on: JWT library, bcrypt, Fernet for token encryption
- Used by: API endpoints, OAuth handlers

## Data Flow

**Authentication Flow:**

1. User registers/logs in via `frontend/src/app/features/auth/`
2. Frontend POST to `/api/v1/auth/register` or `/api/v1/auth/login`
3. Backend endpoint (`backend/app/api/v1/endpoints/auth.py`) validates credentials, creates JWT tokens
4. Frontend stores access token and refresh token locally
5. All subsequent requests include bearer token via `authInterceptor` (`frontend/src/app/core/interceptors/auth.interceptor.ts`)
6. Backend validates token in dependency `get_current_user()` from `backend/app/api/v1/deps.py`

**Platform Connection Flow:**

1. User initiates OAuth from `Configuration` feature (`frontend/src/app/features/configuration/pages/platforms.component.ts`)
2. Frontend calls `/api/v1/platforms/oauth/init` with platform name
3. Backend endpoint generates OAuth authorization URL and stores session state
4. User redirected to platform (Meta, TikTok, Google Ads, DV360) login
5. Platform calls backend at `/api/v1/platforms/oauth/callback/{platform}`
6. Backend exchanges authorization code for access token via platform SDK
7. Backend encrypts and stores tokens in `PlatformConnection` model
8. Initial sync triggered to populate historical data

**Daily Synchronization Flow:**

1. APScheduler triggers `run_daily_sync()` at 00:10 in connection's timezone (`backend/app/services/sync/scheduler.py`)
2. Sync job created in database with status RUNNING
3. Platform-specific sync module (e.g., `backend/app/services/sync/meta_sync.py`) fetches data from platform API
4. Raw performance data inserted into platform-specific table (e.g., `meta_raw_performance`)
5. Harmonizer (`backend/app/services/sync/harmonizer.py`) normalizes metrics across platforms:
   - Standardizes field names (impressions, clicks, spend, conversions, conversion_value)
   - Converts currency using exchange rate service
   - Inserts into `HarmonizedPerformance` table
6. Sync job marked complete with statistics
7. Assets linked to performances via `CreativeAsset` model

**Dashboard Data Flow:**

1. User views Dashboard (`frontend/src/app/features/dashboard/dashboard.component.ts`)
2. Frontend calls `/api/v1/dashboard/stats` with date range filters
3. Backend aggregates `HarmonizedPerformance` records by organization
4. Calculates metrics: total_spend, impressions, ROAS, asset_count
5. Compares current period vs. prior period
6. Returns aggregated stats with period-over-period deltas
7. Frontend uses data to populate header cards and tables

**State Management:**

- **Authentication State:** NgRx store in `frontend/src/app/core/store/auth/`
  - Actions: login, logout, token refresh
  - State shape: `{ auth: { user, token, loading, error } }`
  - Persists to localStorage via effects

- **Feature Data:** Fetched on-demand via `ApiService` (no global store)
  - Components subscribe to HTTP observables
  - Templates use async pipe for reactive binding
  - No manual state management per feature (reduces complexity)

## Key Abstractions

**PlatformConnection:**
- Purpose: Represents a linked ad account with encrypted OAuth credentials
- Examples: `backend/app/models/platform.py`
- Pattern: One connection per ad account; stores platform name, account ID, access/refresh tokens, sync status
- Relationships: Belongs to Organization, created_by User, linked to BrainsuiteApp

**HarmonizedPerformance:**
- Purpose: Unified performance metrics regardless of platform source
- Examples: `backend/app/models/performance.py`
- Pattern: Normalized table populated by sync jobs; all values in organization's currency
- Fields: asset_id, platform, report_date, spend, impressions, clicks, conversions, conversion_value, ROAS

**CreativeAsset:**
- Purpose: Individual creative (image/video) tracked across platforms
- Examples: `backend/app/models/creative.py`
- Pattern: One record per asset; references thumbnails/videos stored in Google Cloud Storage
- Relationships: Multiple performances, multiple projects (via AssetProjectMapping)

**OAuth Service (Platform-specific):**
- Purpose: Encapsulates OAuth flow and API client initialization for each platform
- Examples: `backend/app/services/platform/meta_oauth.py`, `tiktok_oauth.py`, etc.
- Pattern: Init URL generation → callback handling → token exchange → client creation
- Uses: Platform SDKs (google-ads-api, tiktok_business_sdk, etc.)

**Harmonizer:**
- Purpose: Transforms raw platform data to unified schema
- Examples: `backend/app/services/sync/harmonizer.py`
- Pattern: Iterates HarmonizedPerformance records; applies currency conversion, metric mapping
- Dependency: Currency service for exchange rates

## Entry Points

**Backend:**
- Location: `backend/app/main.py`
- Triggers: Uvicorn server startup, lifespan events
- Responsibilities:
  - Middleware registration (CORS, TrustedHost)
  - Router registration
  - Lifespan context manager for scheduler initialization
  - Database migrations on startup
  - Frontend SPA serving

**Frontend:**
- Location: `frontend/src/main.ts`
- Triggers: Browser page load
- Responsibilities:
  - Bootstrap Angular application with config
  - Initialize HTTP client, router, store, animations
  - Render root AppComponent

**Scheduler:**
- Location: `backend/app/services/sync/scheduler.py::startup_scheduler()`
- Triggers: Called from main.py lifespan on startup
- Responsibilities:
  - Query all active connections
  - Register daily cron jobs per connection
  - Start AsyncIOScheduler
  - Register shutdown hook

## Error Handling

**Strategy:** Layered error responses with logging at service layer

**Patterns:**

1. **HTTP Error Responses:** FastAPI HTTPException with status code + detail message
   - 400: Invalid request (validation)
   - 401: Missing/invalid auth token
   - 403: Insufficient permissions
   - 404: Resource not found
   - 500: Unhandled server error

2. **Database Errors:** Caught in dependencies, logged, re-raised as HTTP 500
   - Deadlock handling in sync/scheduler.py with exponential backoff
   - Session rollback on transaction failure

3. **External API Errors:** Platform SDK exceptions caught in sync modules
   - Logged with platform name and connection ID
   - Sync job marked FAILED with error message
   - Non-fatal; next scheduled job retries

4. **OAuth Errors:** Handled in callback endpoint
   - User-friendly HTML response with error description
   - Session state validated to prevent CSRF
   - Token exchange failures logged

5. **Frontend Errors:** HTTP interceptor catches 401, triggers re-auth
   - Non-401 errors logged to console
   - Components handle errors in their own subscriptions

## Cross-Cutting Concerns

**Logging:**
- Backend: Standard Python logging to console (stdout)
- Frontend: Console.error for HTTP errors
- Scheduler: Detailed logs with timestamp, platform, connection ID

**Validation:**
- Backend: Pydantic schemas in `backend/app/schemas/` for request bodies
- Frontend: Angular form validation (reactive forms) in components
- Database: SQLAlchemy model constraints (ForeignKey, String length, Boolean defaults)

**Authentication:**
- Backend: JWT bearer tokens (HS256) with 30-minute access, 7-day refresh
- Frontend: Token stored in localStorage, attached via interceptor
- Token encryption: Optional via Fernet (if TOKEN_ENCRYPTION_KEY set)

**Authorization:**
- Role-based: ADMIN, READ_ONLY (stored in OrganizationRole)
- Organization isolation: All queries filter by current_user.organization_id
- User-level: is_superuser flag for system admins

**Multi-tenancy:**
- Enforced at model level: Every query includes `.where(organization_id == user_org_id)`
- Credential isolation: Tokens stored encrypted in PlatformConnection
- No cross-org data leakage: Cascading checks in dependencies

---

*Architecture analysis: 2026-03-20*
