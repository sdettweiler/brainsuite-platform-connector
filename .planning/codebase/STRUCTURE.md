# Codebase Structure

**Analysis Date:** 2026-03-20

## Directory Layout

```
brainsuite-platform-connector/
├── frontend/                       # Angular standalone SPA
│   ├── src/
│   │   ├── app/
│   │   │   ├── core/               # Shared services, guards, interceptors, state
│   │   │   ├── features/           # Lazy-loaded feature modules (auth, dashboard, etc.)
│   │   │   ├── shared/             # Reusable components
│   │   │   ├── app.routes.ts       # Root routing configuration
│   │   │   ├── app.config.ts       # Dependency injection setup
│   │   │   └── app.component.ts    # Root component
│   │   ├── main.ts                 # Entry point
│   │   ├── environments/           # Environment-specific config
│   │   └── assets/                 # Static images
│   ├── angular.json                # Angular build config
│   ├── tsconfig.json               # TypeScript config
│   ├── package.json                # npm dependencies
│   └── proxy.conf.json             # Dev server proxy to backend
│
├── backend/                        # Python FastAPI application
│   ├── app/
│   │   ├── main.py                 # FastAPI app initialization, routes, lifespan
│   │   ├── core/
│   │   │   ├── config.py           # Settings singleton (env variables)
│   │   │   └── security.py         # JWT, password hashing, token encryption
│   │   ├── db/
│   │   │   └── base.py             # SQLAlchemy engine, session factory
│   │   ├── models/                 # ORM domain models
│   │   │   ├── user.py             # User, Organization, OrganizationRole
│   │   │   ├── platform.py         # PlatformConnection, BrainsuiteApp
│   │   │   ├── creative.py         # CreativeAsset, AssetMetadataValue
│   │   │   ├── performance.py       # HarmonizedPerformance, SyncJob, Raw platform tables
│   │   │   └── metadata.py         # MetadataField, other config models
│   │   ├── schemas/                # Pydantic request/response models
│   │   │   ├── user.py             # Login, Register, User responses
│   │   │   ├── platform.py         # Connection, OAuth requests/responses
│   │   │   └── creative.py         # Asset, Dashboard responses
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── __init__.py      # Router composition
│   │   │       ├── deps.py          # Dependency injection (get_current_user, etc.)
│   │   │       └── endpoints/       # Endpoint route handlers
│   │   │           ├── auth.py      # Register, login, token refresh
│   │   │           ├── platforms.py # OAuth init/callback, connection management
│   │   │           ├── dashboard.py # Performance stats, aggregations
│   │   │           ├── assets.py    # Creative asset CRUD, search
│   │   │           └── users.py     # User profile, settings
│   │   └── services/                # Business logic layer
│   │       ├── object_storage.py    # Google Cloud Storage integration
│   │       ├── currency.py          # Exchange rate conversion
│   │       ├── export_service.py    # CSV/PDF export logic
│   │       ├── connection_purge.py  # Token refresh, connection cleanup
│   │       ├── ace_score.py         # ACE scoring logic
│   │       ├── platform/            # OAuth and API client management
│   │       │   ├── meta_oauth.py
│   │       │   ├── tiktok_oauth.py
│   │       │   ├── google_ads_oauth.py
│   │       │   └── dv360_oauth.py
│   │       └── sync/                # Data synchronization
│   │           ├── scheduler.py     # APScheduler job registration
│   │           ├── harmonizer.py    # Metric normalization & aggregation
│   │           ├── meta_sync.py     # Meta platform data pull
│   │           ├── tiktok_sync.py   # TikTok platform data pull
│   │           ├── google_ads_sync.py # Google Ads data pull
│   │           └── dv360_sync.py    # Display & Video 360 data pull
│   ├── alembic/                    # Database migration management
│   │   ├── env.py                  # Migration execution config
│   │   ├── alembic.ini             # Alembic settings
│   │   └── versions/               # Migration scripts
│   └── requirements.txt            # Python dependencies
│
├── docker/                         # Container configs
│   └── (Dockerfile, docker-compose files)
│
├── .planning/                      # GSD planning artifacts
│   └── codebase/                  # This directory; contains ARCHITECTURE.md, STRUCTURE.md, etc.
│
└── README.md, package.json, docker-compose.yml, etc.
```

## Directory Purposes

**`frontend/src/app/core/`:**
- Purpose: Shared infrastructure for all features
- Contains:
  - `interceptors/`: HTTP interceptor for token attachment
  - `layout/`: Shell component (header, sidebar), shared layout
  - `guards/`: auth.guard prevents route access without token
  - `services/`: api.service (HTTP client wrapper), auth.service, theme.service
  - `store/`: NgRx auth reducer, actions, effects, selectors
  - `dialogs/`: Edit profile, reusable modal components
- Key files: `auth.interceptor.ts`, `auth.guard.ts`, `api.service.ts`, `auth.service.ts`

**`frontend/src/app/features/`:**
- Purpose: Feature-specific components and routes
- Contains lazy-loaded modules:
  - `auth/`: login, register routes (public)
  - `home/`: Dashboard welcome page
  - `dashboard/`: Performance data, metrics, asset list (protected)
  - `comparison/`: Period-over-period comparison view
  - `configuration/`: Organization settings, platform connections, metadata fields, Brainsuite apps
- Key files: Feature routes (`*.routes.ts`), page components, dialogs

**`frontend/src/app/shared/`:**
- Purpose: Reusable UI components used across features
- Contains: date-range-picker, other generic components
- Pattern: Standalone components for easy import into features

**`backend/app/core/`:**
- Purpose: Application-wide configuration and security
- `config.py`: Settings loaded from environment (database URL, API keys, CORS origins, etc.)
- `security.py`: Token creation/validation, password hashing, encryption utilities

**`backend/app/db/`:**
- Purpose: Database connectivity and session management
- `base.py`: Defines Base class (SQLAlchemy DeclarativeBase), async engine factory, session factory
- Pattern: Singleton engine; new sessions created per request via dependency

**`backend/app/models/`:**
- Purpose: Domain models mapped to PostgreSQL tables
- `user.py`: User, Organization, OrganizationRole, RefreshToken, Notification, OrganizationJoinRequest
- `platform.py`: PlatformConnection, BrainsuiteApp
- `creative.py`: CreativeAsset, AssetMetadataValue, AssetProjectMapping, Project
- `performance.py`: HarmonizedPerformance, SyncJob, and raw platform tables (MetaRawPerformance, TikTokRawPerformance, etc.)
- `metadata.py`: MetadataField configuration per organization

**`backend/app/schemas/`:**
- Purpose: Pydantic validation models for API requests/responses
- `user.py`: LoginRequest, UserCreate, UserResponse, RefreshRequest
- `platform.py`: Connection requests, OAuth responses
- `creative.py`: Asset details, Dashboard filters, comparison requests

**`backend/app/api/v1/endpoints/`:**
- Purpose: HTTP route handlers
- `auth.py`: Register, login, token refresh, slug checking (registration flow)
- `platforms.py`: OAuth initialization, callback handling, connection CRUD, app management
- `dashboard.py`: Aggregated stats (spend, impressions, ROAS), asset counts, period comparisons
- `assets.py`: Asset search, detail retrieval, metadata assignment
- `users.py`: Profile updates, settings

**`backend/app/services/platform/`:**
- Purpose: Platform-specific OAuth and API client management
- `meta_oauth.py`: Meta (Facebook) OAuth flow, API client initialization
- `tiktok_oauth.py`: TikTok OAuth flow, API client
- `google_ads_oauth.py`: Google Ads OAuth, client setup
- `dv360_oauth.py`: Display & Video 360 OAuth, client setup
- Pattern: Each module handles auth init URL generation, callback token exchange, API client creation

**`backend/app/services/sync/`:**
- Purpose: Background data synchronization
- `scheduler.py`: APScheduler initialization, job registration, cron triggers at 00:10 per timezone
- `meta_sync.py`: Pulls performance data from Meta API, inserts into `meta_raw_performance` table
- `tiktok_sync.py`: TikTok data pull and storage
- `google_ads_sync.py`: Google Ads data pull (uses google-ads-api library)
- `dv360_sync.py`: DV360 data pull via Google Ads API
- `harmonizer.py`: Normalizes raw data into `HarmonizedPerformance` table (currency conversion, metric mapping)

**`backend/alembic/`:**
- Purpose: Database schema versioning
- Contains migration scripts in `versions/` directory
- `env.py`: SQLAlchemy async context configuration
- Run: `alembic upgrade head` on server startup (called in main.py)

## Key File Locations

**Entry Points:**

- `backend/app/main.py`: FastAPI app initialization, middleware, router registration, lifespan
- `frontend/src/main.ts`: Angular bootstrap entry point
- `frontend/src/app/app.routes.ts`: Root routing tree, lazy-loaded feature routes
- `frontend/src/app/app.component.ts`: Root component (`<router-outlet>`)

**Configuration:**

- `backend/app/core/config.py`: Environment settings (DATABASE_URL, API_KEY, CORS_ORIGINS, etc.)
- `frontend/src/environments/environment.ts`: Frontend config (API_URL, production flag)
- `frontend/angular.json`: Build, serve, test config
- `backend/requirements.txt`: Python package versions

**Core Logic:**

- `backend/app/models/`: Domain entities
- `backend/app/services/sync/harmonizer.py`: Data transformation logic
- `backend/app/services/sync/scheduler.py`: Job scheduling
- `frontend/src/app/core/services/api.service.ts`: HTTP communication
- `frontend/src/app/core/store/auth/`: Authentication state

**Testing:**

- No dedicated test files present in current structure
- Tests would be in `backend/tests/`, `frontend/src/app/**/*.spec.ts` (Angular convention)

## Naming Conventions

**Files:**

- **Backend Python**: `snake_case.py` (e.g., `meta_sync.py`, `get_user_role`)
- **Frontend TypeScript**: `kebab-case.component.ts` (e.g., `dashboard.component.ts`), `service.ts`, `*.routes.ts`
- **Models**: `CamelCase` class names (e.g., `PlatformConnection`, `HarmonizedPerformance`)
- **Services**: `*Service.ts` or `*_service.py`

**Directories:**

- **Backend**: `snake_case` (e.g., `platform`, `sync`, `object_storage`)
- **Frontend**: `kebab-case` for feature folders (e.g., `configuration`, `dashboard`); singular or plural per context
- **Models directory**: `models/` (all domain models)
- **Schemas directory**: `schemas/` (Pydantic validation)
- **Endpoints directory**: `endpoints/` (API route handlers)

**Functions/Methods:**

- **Backend**: `async def snake_case_function(...)`
- **Frontend**: `camelCaseMethod()` in classes, `camelCaseFunction()` standalone
- **TypeScript classes**: `CamelCase`, methods are `camelCase`

**Variables:**

- **Backend**: `snake_case` (Python convention)
- **Frontend**: `camelCase` (TypeScript convention)
- **Constants**: `UPPER_SNAKE_CASE` (both languages)

**API Endpoints:**

- **Pattern**: `/api/v1/{resource}/{action}`
- Examples:
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `GET /api/v1/platforms/oauth/session/{session_id}`
  - `POST /api/v1/platforms/oauth/callback/{platform}`
  - `GET /api/v1/dashboard/stats`
  - `GET /api/v1/assets/search`

## Where to Add New Code

**New API Endpoint:**
1. Create/update schema in `backend/app/schemas/` (e.g., `resource.py`)
2. Add route handler in `backend/app/api/v1/endpoints/` (e.g., `@router.get()`)
3. Add dependency in `backend/app/api/v1/deps.py` if needed (e.g., permission checks)
4. Register router in `backend/app/api/v1/__init__.py` if new resource
5. Add corresponding request in `frontend/src/app/services/` or call via `ApiService`

**New Database Model:**
1. Define class in `backend/app/models/{area}.py` (e.g., `models/performance.py`)
2. Create Alembic migration: `alembic revision --autogenerate -m "Add new model"`
3. Review and update migration script in `backend/alembic/versions/`
4. Create Pydantic schema in `backend/app/schemas/` if exposing via API
5. Update relationships in related models

**New Feature (Frontend):**
1. Create feature directory: `frontend/src/app/features/{feature}/`
2. Define routes: `frontend/src/app/features/{feature}/{feature}.routes.ts`
3. Create page component: `frontend/src/app/features/{feature}/pages/{page}.component.ts`
4. Add feature routes to root router in `frontend/src/app/app.routes.ts`
5. Create feature-specific service in feature directory or `frontend/src/app/core/services/`
6. Create reusable components in `frontend/src/app/features/{feature}/components/`

**New Service/Integration:**
- **OAuth Platform**: Create file in `backend/app/services/platform/{platform}_oauth.py` following existing pattern
- **Data Sync**: Create sync module in `backend/app/services/sync/{platform}_sync.py`; register in scheduler
- **Utility Service**: Create in `backend/app/services/{service_name}.py` (e.g., `currency.py`, `object_storage.py`)

**Tests:**
- **Backend**: Create test files in `backend/tests/` mirroring app structure
- **Frontend**: Co-locate spec files: `feature.component.spec.ts` alongside `feature.component.ts`

## Special Directories

**`backend/static/creatives/`:**
- Purpose: Local storage of creative assets (images, videos)
- Generated: Yes (created on first run if missing)
- Committed: No; `.gitignore` excludes
- Mounted at: `/static/creatives` on backend server
- Superseded by: Google Cloud Storage at `/objects/` endpoint (migration path)

**`backend/alembic/`:**
- Purpose: Database migration management
- Generated: No; migrations are authored
- Committed: Yes; schema changes are versioned
- Run on: Server startup via `alembic upgrade head`

**`frontend/dist/brainsuite/`:**
- Purpose: Built frontend assets
- Generated: Yes; output of `npm run build`
- Committed: No; rebuilt on deploy
- Served by: FastAPI catch-all route in `main.py` for SPA routing

**`.planning/codebase/`:**
- Purpose: GSD planning documents (this directory)
- Generated: By GSD agents via `/gsd:map-codebase`
- Committed: Yes; reference documents for orchestration
- Consumed by: `/gsd:plan-phase` and `/gsd:execute-phase`

---

*Structure analysis: 2026-03-20*
