# Codebase Concerns

**Analysis Date:** 2026-03-20

## Tech Debt

**In-Memory OAuth Session Storage:**
- Issue: OAuth session state is stored in-memory dict `_oauth_sessions` instead of persistent storage
- Files: `backend/app/api/v1/endpoints/platforms.py` (lines 28-29)
- Impact: Sessions lost on server restart; state not shared across multiple instances; no cleanup/expiry mechanism for abandoned sessions
- Fix approach: Replace with Redis-backed session store with TTL; implement session cleanup task; add session expiry after 10-15 minutes

**Broad Exception Handling:**
- Issue: Multiple `except Exception` blocks without specific error type handling
- Files: `backend/app/core/security.py` (line 21), `backend/app/main.py` (lines 33, 64, 87, 100), `backend/app/services/sync/meta_sync.py` (lines 233, 296, 325), `backend/app/api/v1/endpoints/platforms.py` (lines 244, 490)
- Impact: Silent failures mask bugs; difficult to diagnose root causes; poor error observability
- Fix approach: Replace with specific exception types (ValueError, HTTPException, etc.); add proper logging with context; implement structured exception handling per domain (auth, sync, API)

**Hardcoded Database Credentials in Config:**
- Issue: Default database URL contains hardcoded `password` string
- Files: `backend/app/core/config.py` (lines 29-30)
- Impact: Security risk if config is committed; misleading for deployment setup
- Fix approach: Require environment variables for all credentials; add validation to reject hardcoded defaults; document required env vars

**Type Safety Issues:**
- Issue: Excessive use of `any` type in frontend code (69 instances)
- Files: `frontend/src/app/core/services/api.service.ts` (lines 24, 28, 36, 40, 44), `frontend/src/app/core/services/auth.service.ts` (line 57), `frontend/src/app/features/dashboard/dashboard.component.ts` (lines 312, 332, 345), and 15+ other component files
- Impact: Loss of type safety; potential runtime errors; difficult refactoring
- Fix approach: Define specific interfaces for API responses; create typed DTOs for each endpoint; use generic constraints instead of `any`

**Tokens Stored in localStorage:**
- Issue: JWT tokens stored in browser localStorage without encryption
- Files: `frontend/src/app/core/services/auth.service.ts` (lines 44, 48, 86-87, 91-92), `frontend/src/app/core/store/auth/auth.effects.ts` (lines 15-16, 28-29, 41-42)
- Impact: XSS attacks can steal tokens; tokens persist across sessions unnecessarily
- Fix approach: Use httpOnly cookies with secure flag for token storage; implement CSRF protection; add Content Security Policy headers

**Dynamic File Path Construction:**
- Issue: File paths constructed dynamically without validation in asset serving
- Files: `backend/app/main.py` (lines 135, 155-161)
- Impact: Potential path traversal vulnerability if object_path contains `..` or other path traversal sequences
- Fix approach: Validate and sanitize object_path; use pathlib for safe path operations; whitelist allowed directories

## Known Bugs

**Fernet Token Encryption Fallback Issue:**
- Symptoms: If TOKEN_ENCRYPTION_KEY is invalid format, fallback generates new key silently
- Files: `backend/app/core/security.py` (lines 13-23)
- Trigger: Invalid base64 in TOKEN_ENCRYPTION_KEY environment variable
- Workaround: Ensure TOKEN_ENCRYPTION_KEY is valid base64-encoded Fernet key; use `Fernet.generate_key()` to create valid key

**OAuth Redirect URI Header Injection:**
- Symptoms: Redirect URI constructed from request headers without validation
- Files: `backend/app/core/config.py` (lines 84-90)
- Trigger: Malicious x-forwarded-host header in request
- Workaround: Ensure reverse proxy validates and sets x-forwarded-host to known good values

## Security Considerations

**Exposed OAuth Session State:**
- Risk: OAuth tokens and account lists stored in-memory with weak authorization check (only user_id comparison)
- Files: `backend/app/api/v1/endpoints/platforms.py` (lines 247-249, 264-275)
- Current mitigation: User ID check in get_oauth_session endpoint
- Recommendations: Move to Redis with encryption; implement state parameter validation per OAuth2 spec; add PKCE for code exchange; add rate limiting on session polling

**Token Encryption Key Management:**
- Risk: If TOKEN_ENCRYPTION_KEY not set, system generates new key on each startup, making old encrypted tokens unreadable
- Files: `backend/app/core/security.py` (lines 14-23)
- Current mitigation: Fernet fallback generates new key
- Recommendations: Require TOKEN_ENCRYPTION_KEY in production; validate key format at startup; add key rotation strategy; test key recovery scenario

**CORS Configuration Too Permissive:**
- Risk: `allow_methods=["*"]` and `allow_headers=["*"]` in CORS config
- Files: `backend/app/main.py` (lines 111-117)
- Current mitigation: Origins are restricted to `BACKEND_CORS_ORIGINS`
- Recommendations: Explicitly list allowed methods (GET, POST, PATCH, DELETE); explicitly list allowed headers; add CSRF token validation

**Object Storage Path Traversal:**
- Risk: Malicious object_path parameter could traverse outside intended directory
- Files: `backend/app/main.py` (lines 131-148)
- Current mitigation: Path is prefixed with "creatives/" directory
- Recommendations: Use `os.path.normpath()` and validate path doesn't escape base directory; implement whitelist of allowed object patterns; add request signing for sensitive URLs

**Plaintext Temporary Passwords:**
- Risk: Temporary passwords set to hardcoded defaults and sent via unencrypted channels
- Files: `backend/app/api/v1/endpoints/users.py` (line 170)
- Current mitigation: User must change on first login
- Recommendations: Use cryptographically random temporary passwords; require secure password change flow; audit password change endpoint; implement passwordless auth option

## Performance Bottlenecks

**Large Component Files:**
- Problem: Several frontend components exceed 700 lines causing slow rendering and testing
- Files: `frontend/src/app/features/configuration/pages/platforms.component.ts` (1024 lines), `frontend/src/app/features/dashboard/dashboard.component.ts` (785 lines), `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` (693 lines)
- Cause: Single-responsibility principle violated; multiple concerns bundled in one component
- Improvement path: Extract template into smaller sub-components; separate data loading logic into services; use smart/dumb component pattern

**Synchronous Database Migrations at Startup:**
- Problem: Database migrations run synchronously in lifespan, blocking server startup
- Files: `backend/app/main.py` (lines 75-79, 21-34)
- Cause: Alembic upgrade runs in executor, but 15s wait added for production deployments
- Improvement path: Run migrations in separate init container before app startup; implement health checks that wait for migration completion; add migration status endpoint

**DV360 Report Polling with Long Wait:**
- Problem: DV360 reports can take up to 2 hours, with polling thread blocking during wait
- Files: `backend/app/services/sync/dv360_sync.py` (lines 1-37)
- Cause: Adaptive polling (30s→60s→120s) extends wall-clock time for large datasets
- Improvement path: Implement webhook callbacks for report completion; use exponential backoff with jitter; persist poll state and resume on restart; run DV360 syncs in separate background worker

**Missing Database Indexes:**
- Problem: Frequent queries on non-indexed columns could cause full table scans
- Files: `backend/app/models/performance.py` (performance tables lack indexes on common query columns like report_date, platform_connection_id, ad_account_id)
- Cause: Schema designed for correctness, not query optimization
- Improvement path: Add composite indexes for common query patterns; profile slow queries with `EXPLAIN ANALYZE`; add index hints for complex queries

## Fragile Areas

**Platform OAuth Flow State Machine:**
- Files: `backend/app/api/v1/endpoints/platforms.py` (lines 115-275)
- Why fragile: Complex multi-step flow with in-memory state; no transaction boundaries; race conditions possible if user retries
- Safe modification: Add state machine class; use database for persistent state; implement idempotent endpoints; add comprehensive logging at each step
- Test coverage: No unit tests for OAuth flows; happy path only tested in integration; error cases untested

**Sync Job Failure Recovery:**
- Files: `backend/app/services/sync/scheduler.py` (lines 40-160)
- Why fragile: Deadlock retry logic uses string matching "deadlock" (case-sensitive); generic exception handling masks real issues
- Safe modification: Catch specific SQLAlchemy `IntegrityError` with deadlock code check; log full exception context; implement per-platform retry strategies; add sync job status persistence
- Test coverage: No unit tests; scheduler behavior only testable in integration environment

**Creative Asset Download and Storage:**
- Files: `backend/app/services/sync/dv360_sync.py` (lines 1090-1234), `backend/app/services/object_storage.py`
- Why fragile: Multiple async operations with partial failure (download thumb but not video); yt-dlp subprocess calls without timeout context; no validation of downloaded file integrity
- Safe modification: Implement transactional asset download (all or nothing); wrap subprocess in timeout handler; validate MIME types and file sizes; add checksum verification; implement cleanup on failure
- Test coverage: No unit tests for asset operations; only integration tested

**Metadata Field Validation:**
- Files: `frontend/src/app/features/configuration/pages/metadata.component.ts` (395 lines)
- Why fragile: Dynamic form generation from API response; validation rules not co-located with schema; field changes not reflected in downstream components
- Safe modification: Generate forms from strongly-typed schema; implement real-time validation with debounce; add schema change detection; propagate updates via RxJS Subject
- Test coverage: No unit tests for form validation

## Scaling Limits

**In-Memory Session Storage:**
- Current capacity: Limited by server RAM; typically ~1000 sessions before memory issues
- Limit: Single server deployment; scales to ~10k concurrent users with session memory
- Scaling path: Implement Redis session store; distribute sessions across cluster; implement session cleanup; monitor session memory growth

**Sync Job Queue Processing:**
- Current capacity: Single scheduler instance processes jobs sequentially
- Limit: Max 24 daily syncs per day; if sync takes >1 hour, queue backs up
- Scaling path: Implement distributed task queue (Celery/Bull); use dedicated worker pool for each platform; add job priority/backoff logic; monitor queue depth

**Database Connection Pool:**
- Current capacity: Default AsyncPG pool (~20 connections)
- Limit: ~100 concurrent users before connection pool exhaustion
- Scaling path: Increase pool size; use connection pooler (PgBouncer); implement connection timeout handling; monitor pool utilization

**File Storage:**
- Current capacity: Filesystem storage with `/static/creatives/` mount
- Limit: Single disk I/O bottleneck; no redundancy; storage cost scales linearly
- Scaling path: Move to GCS object storage (already partially implemented); implement CDN caching; clean up old assets; implement S3-compatible backup

## Dependencies at Risk

**yt-dlp (Unmaintained Alternative):**
- Risk: yt-dlp is maintained by community, not YouTube; future API changes may break
- Impact: DV360 video sync fails if YouTube changes API or yt-dlp falls behind
- Migration plan: Implement fallback to ffmpeg/HLS extraction; store YouTube CDN URLs directly; implement URL expiry handling; monitor YouTube API changes

**APScheduler (Synchronous Scheduler in Async App):**
- Risk: APScheduler runs sync code in executor; can cause thread starvation if many jobs scheduled
- Impact: Delayed job execution under high load; scheduler thread may block event loop
- Migration plan: Replace with dedicated task queue (Celery); use async-native scheduler; implement proper async context handling

**google-cloud-storage Dependency Chain:**
- Risk: Google Cloud SDK has large dependency tree (20+ packages); updates may introduce breaking changes
- Impact: Deployment failures if version constraints not properly specified
- Migration plan: Pin major versions; implement version compatibility testing; prepare fallback to alternative storage (AWS S3)

**passlib/bcrypt Version Mismatch:**
- Risk: passlib==1.7.4 is old; bcrypt==4.0.1 may have version compatibility issues
- Impact: Potential security issues in bcrypt; password hashing may fail
- Migration plan: Update to passlib 1.7.4+ if available; test bcrypt upgrade; implement password migration strategy

## Missing Critical Features

**Authentication Audit Logging:**
- Problem: No audit trail for login/logout/token refresh events
- Blocks: Compliance audits; security incident investigation; suspicious activity detection
- Recommendation: Implement audit table; log all auth events with IP, user agent, timestamp

**Rate Limiting:**
- Problem: No rate limiting on OAuth endpoints or API operations
- Blocks: Protection against brute force attacks; API abuse protection
- Recommendation: Implement sliding window rate limiter; different limits per endpoint; IP-based and user-based limits

**Request/Response Logging:**
- Problem: No structured logging of API requests; difficult to debug or audit
- Blocks: Performance analysis; security investigation; error tracking
- Recommendation: Implement request/response middleware; log URL, method, status, duration; exclude sensitive headers

**Graceful Shutdown:**
- Problem: No graceful shutdown of background tasks on server stop
- Blocks: In-flight syncs may be killed; jobs may leave database in inconsistent state
- Recommendation: Implement shutdown signal handler; wait for active jobs; drain job queue; implement job restart on next startup

## Test Coverage Gaps

**Zero Unit Test Coverage:**
- What's not tested: All backend services, API endpoints, sync logic, authentication
- Files: `backend/app/**/*.py` - no .test.py or .spec.py files found
- Risk: Changes may introduce regressions undetected; refactoring is risky; debugging difficult
- Priority: High - Implement pytest tests for core services (auth, sync, export)

**Frontend Component Tests:**
- What's not tested: Angular components (no .spec.ts files found)
- Files: `frontend/src/app/**/*.ts` - no test files
- Risk: UI regressions; form validation failures; data binding issues
- Priority: High - Add Jasmine tests for critical components (auth, dashboard filters)

**OAuth Flow Integration Tests:**
- What's not tested: Multi-step OAuth flows; token refresh; session recovery
- Files: `backend/app/api/v1/endpoints/platforms.py` (OAuth endpoints)
- Risk: Token expiry handling bugs; redirect URI mismatches; account linking issues
- Priority: Medium - Implement integration tests with mock OAuth providers

**Sync Job Error Cases:**
- What's not tested: Network failures; malformed API responses; partial data loss recovery
- Files: `backend/app/services/sync/**/*.py` (1000+ lines of sync logic)
- Risk: Silent failures; data inconsistency; customer data loss
- Priority: High - Implement error injection tests for each platform

**Database Migration Tests:**
- What's not tested: Alembic migrations; data transformations; schema rollback
- Files: `backend/alembic/versions/`
- Risk: Production migration failures; data loss; downtime
- Priority: Medium - Create migration test suite with test database

---

*Concerns audit: 2026-03-20*
