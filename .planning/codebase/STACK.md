# Technology Stack

**Analysis Date:** 2026-03-20

## Languages

**Primary:**
- Python 3.12+ - Backend API, services, migrations
- TypeScript 5.2 - Frontend application (Angular)
- HTML/CSS - Frontend markup and styles

**Secondary:**
- JavaScript - Node.js tooling and build scripts
- Bash - Deployment and startup scripts

## Runtime

**Environment:**
- Python 3.12+ (backend)
- Node.js 18+ (frontend build tooling)
- Docker (containerization)

**Package Manager:**
- pip (Python) - Backend dependencies
- npm (Node.js) - Frontend dependencies
- Lockfile: `package-lock.json` present, `requirements.txt` for Python

## Frameworks

**Core:**
- FastAPI 0.115.0 - Async REST API framework
- Angular 17.3.0 - Frontend framework
- SQLAlchemy 2.0.23 - ORM for database access

**Web Server:**
- Uvicorn 0.24.0 - ASGI server for FastAPI
- Nginx - Reverse proxy (production frontend serving)

**Build/Dev:**
- Angular CLI 17.3.0 - Angular development and build tool
- Alembic 1.12.1 - Database schema migrations
- APScheduler 3.10.4 - Background job scheduling

**Testing:**
- Angular testing framework built-in
- No explicit Python test framework configured

## Key Dependencies

**Critical:**
- asyncpg 0.29.0 - Async PostgreSQL driver
- pydantic 2.5.0 - Data validation and settings
- pydantic-settings 2.1.0 - Configuration management
- SQLAlchemy 2.0.23 - Database ORM with async support

**Authentication & Security:**
- python-jose[cryptography] 3.4.0 - JWT token handling
- passlib[bcrypt] 1.7.4 - Password hashing
- bcrypt 4.0.1 - Cryptographic hashing
- cryptography 42.0.4 - Encryption/decryption utilities

**HTTP & Async:**
- httpx 0.25.2 - Async HTTP client for external APIs
- aiohttp 3.9.4 - Alternative async HTTP client
- aiofiles 23.2.1 - Async file I/O

**Data Processing:**
- openpyxl 3.1.2 - Excel file generation/reading
- reportlab 4.0.7 - PDF generation
- imageio-ffmpeg >= 0.5.1 - Video/image processing

**Cloud Storage:**
- google-cloud-storage >= 2.14.0 - Google Cloud Storage client
- google-auth-library 10.6.1 - Google authentication

**Frontend UI:**
- @angular/material 17.3.0 - Material Design UI components
- @angular/cdk 17.3.0 - Component Development Kit
- @ngrx/store 17.2.0 - State management (Redux-like)
- @ngrx/effects 17.2.0 - Side effects for store
- echarts 5.6.0 - Charting library
- ngx-echarts 17.2.0 - Angular wrapper for ECharts
- bootstrap-icons 1.13.1 - Icon library

**File Upload:**
- @uppy/core 5.2.0 - File upload framework core
- @uppy/dashboard 5.1.1 - File upload UI
- @uppy/react 5.2.0 - React integration for Uppy
- @uppy/aws-s3 5.1.0 - AWS S3 upload plugin

**Utilities:**
- date-fns 2.30.0 - Date manipulation
- ngx-skeleton-loader 9.0.0 - Skeleton loading states
- pyotp 2.9.0 - One-time password generation (2FA)
- email-validator 2.1.0 - Email validation
- python-multipart 0.0.7 - Multipart form data handling
- pytz 2023.3 - Timezone support
- python-dotenv 1.0.0 - Environment variable loading
- yt-dlp - YouTube video downloading/metadata

## Configuration

**Environment:**
- `.env` file required - Contains database, API keys, OAuth credentials
- Example: `.env.example` provided with all required variables
- Settings class: `backend/app/core/config.py` manages all config via Pydantic

**Key Environment Variables:**
- Database: `DATABASE_URL`, `SYNC_DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- Security: `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`
- OAuth: `META_APP_ID`, `META_APP_SECRET`, `TIKTOK_APP_ID`, `TIKTOK_APP_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_DEVELOPER_TOKEN`, `DV360_CLIENT_ID`, `DV360_CLIENT_SECRET`
- Currency: `EXCHANGERATE_API_KEY`
- Storage: `DEFAULT_OBJECT_STORAGE_BUCKET_ID`, `PUBLIC_OBJECT_SEARCH_PATHS`
- CORS: `BACKEND_CORS_ORIGINS`

**Build:**
- Frontend: `angular.json` - Angular build configuration
- Backend: Alembic migrations in `backend/alembic/`
- Docker: `docker-compose.yml`, `docker-compose.dev.yml`

## Database

**Primary:**
- PostgreSQL 16 (Alpine) - Main relational database
- Connection: Async via asyncpg, sync via psycopg2
- Migrations: Alembic handles schema evolution

**Optional Cache:**
- Redis - Referenced in config (`REDIS_URL`) but not actively used in observed code

## Platform Requirements

**Development:**
- Python 3.12+
- Node.js 18+ with npm
- Docker and Docker Compose
- Git

**Production:**
- Deployment target: Replit (autoscale)
- Docker containerization for both backend and frontend
- Replit object storage integration (Google Cloud Storage with custom auth)

## Build & Deployment

**Frontend Build:**
```bash
npm run build                    # Production build
npm run build:dev               # Development build
npm run build:replit            # Replit-optimized build
```

**Backend:**
- Runs via Uvicorn in Docker
- Alembic migrations run on startup
- Static file serving from frontend dist

**Container Images:**
- Backend: Alpine Python 3.12 base with FastAPI
- Frontend: Node.js 18 Alpine for building, Nginx for serving
- Database: PostgreSQL 16 Alpine

---

*Stack analysis: 2026-03-20*
