# Pitfalls Research

**Domain:** Multi-tenant ad platform connector with async creative scoring (FastAPI + Angular + GCS)
**Researched:** 2026-03-20
**Confidence:** HIGH (most pitfalls grounded in specific known issues in the existing codebase + verified external sources)

---

## Critical Pitfalls

### Pitfall 1: In-Memory OAuth Sessions Silently Break Under Autoscale

**What goes wrong:**
The `_oauth_sessions` dict lives in one worker's memory. Under Replit Autoscale, the OAuth callback may land on a different worker than initiated the flow — the session is not found, the user gets a cryptic error, and the platform connection silently fails. There is also no TTL, so abandoned OAuth attempts accumulate indefinitely, eating memory.

**Why it happens:**
OAuth state stored in-memory is the "obvious" quick solution during development on a single-process dev server. The problem is invisible until the second worker instance spins up under load.

**How to avoid:**
Replace `_oauth_sessions` with Redis using a short TTL (10–15 minutes). Use the already-configured `REDIS_URL` env var. Key the session by a cryptographically random `state` parameter, not user ID. Delete the key immediately on successful callback. Verify that `SETEX` (set-with-expiry) is used — not `SET` followed by `EXPIRE` — to avoid the race where the key exists with no TTL between those two calls.

**Warning signs:**
- OAuth connection works locally but fails inconsistently in production
- Users report "connection failed" after approving the platform consent screen
- Memory on the backend process grows over time with no corresponding user activity

**Phase to address:**
Security Hardening phase (before any external users onboard). This is a hard blocker for production.

---

### Pitfall 2: OAuth Redirect URI Constructed from Request Headers

**What goes wrong:**
The redirect URI is built from `x-forwarded-host` without validating the header value. A malicious actor sends a crafted request with a different host header during an OAuth initiation, causing the platform's callback to redirect tokens to an attacker-controlled domain. This is a classic OAuth redirect URI injection.

**Why it happens:**
Trusting forwarded headers is common when sitting behind a reverse proxy, but the assumption is that the proxy has already validated and locked down those headers. Replit's Autoscale environment does not guarantee this.

**How to avoid:**
Define the redirect URI as a hardcoded configuration value (env var `META_REDIRECT_URI`, `TIKTOK_REDIRECT_URI`, etc.) and compare the inbound `x-forwarded-host` against an allowlist. Never construct the redirect URI dynamically from request headers in production. The env vars for redirect URIs already exist in the codebase — use them exclusively.

**Warning signs:**
- Redirect URI in OAuth init is constructed with string interpolation rather than read from config
- No validation of `x-forwarded-host` against a known list of domains
- OAuth consent screen shows a domain that does not match your configured app domain

**Phase to address:**
Security Hardening phase. Exploitable in production — fix before external users.

---

### Pitfall 3: JWT in localStorage Exposes All User Tokens on XSS

**What goes wrong:**
A single XSS vector anywhere in the Angular app — including third-party ad preview iframes or injected creative metadata — allows an attacker to `localStorage.getItem('access_token')` and exfiltrate all of the user's ad platform tokens. Because those tokens are encrypted with Fernet and stored server-side against the user account, a stolen JWT grants access to the user's entire Meta/TikTok/Google/DV360 connection.

**Why it happens:**
localStorage is the default recommendation in most Angular tutorial code. The XSS risk is abstract until a creative asset with crafted metadata is imported and rendered.

**How to avoid:**
Switch to the hybrid pattern: access token in memory only (Angular service property, not persisted storage), refresh token in an `httpOnly; Secure; SameSite=Strict` cookie. Add a `POST /api/v1/auth/refresh` endpoint that accepts the httpOnly cookie, validates, and returns a new in-memory access token. Remove all `localStorage.setItem` calls in `auth.service.ts` and `auth.effects.ts`. Add a `Content-Security-Policy` header that disallows inline scripts and restricts `frame-src` to known ad platform preview domains.

**Warning signs:**
- `localStorage.setItem` used in `auth.service.ts` or any NgRx effect
- No `Content-Security-Policy` header on API responses or the Angular shell
- Creative metadata is rendered with `innerHTML` or `[innerHTML]` without sanitization

**Phase to address:**
Security Hardening phase. The 69 `any` type instances in the frontend increase this risk because untyped API responses may silently carry unexpected HTML/script content.

---

### Pitfall 4: Platform Token Refresh Failures Are Swallowed Silently

**What goes wrong:**
Background sync jobs refresh platform access tokens. If token refresh fails — expired refresh token, revoked app access, Google Cloud project still in "Testing" status, or TikTok 24-hour access token not rotated — the sync service falls into `except Exception` blocks that log an error and move on. The user never sees a notification. They see stale metrics indefinitely, with no indication their connection is broken.

**Why it happens:**
Broad exception handling (`except Exception`) in `meta_sync.py`, `scheduler.py`, and `platforms.py` suppresses the failure signal. The scheduler continues scheduling the job. The connection record is never updated to a "disconnected" state.

**How to avoid:**
Model platform connection state explicitly: `connected`, `token_refresh_failed`, `disconnected`. When a token refresh fails after N retries, update the connection record's status and surface a visible error in the dashboard ("Your Meta connection needs to be reconnected"). Add a dedicated exception type for `PlatformTokenExpiredError` that sync services raise, and catch it specifically in the scheduler to trigger the state transition.

**Warning signs:**
- `except Exception` in any sync service without a state transition on the platform connection record
- No `status` or `health` field on `PlatformConnection` model
- Dashboard shows metrics from 3+ days ago without any error indicator

**Phase to address:**
Platform Reliability phase (sync hardening). Also requires a UI indicator in the Dashboard Polish phase.

---

### Pitfall 5: BrainSuite Scoring Creates N+1 Asset Submissions

**What goes wrong:**
When the BrainSuite integration is built, the naive implementation submits each creative individually as it is synced. With large accounts (hundreds to thousands of creatives), this creates hundreds of sequential HTTP calls to the BrainSuite API. If the BrainSuite API has per-minute rate limits, this immediately starts returning 429s. If not rate-limited, it creates a latency cascade during sync that delays the entire job.

**Why it happens:**
The sync services already download/store assets one at a time. Appending a BrainSuite API call after each asset store is the path of least resistance, but does not account for API rate limits or failure handling.

**How to avoid:**
Queue creative IDs for scoring separately from the sync pipeline. After a sync completes, enqueue all unscored creatives into a scoring task. The scoring task processes with a configurable rate limit (e.g., 5 per second). Store score status on the creative record (`pending`, `scoring`, `scored`, `failed`). Use existing Redis as the queue backing. This decouples sync reliability from scoring reliability.

**Warning signs:**
- BrainSuite API call made inline inside the asset download/store loop
- No `score_status` field on the creative record
- No backoff or retry logic around BrainSuite API calls

**Phase to address:**
BrainSuite Integration phase. Architecture decision must be made before the first line of scoring code is written.

---

### Pitfall 6: Fernet Key Rotation Silently Invalidates All Stored Platform Tokens

**What goes wrong:**
If `TOKEN_ENCRYPTION_KEY` is not set in production (or is set incorrectly), the application generates a new Fernet key on each startup. All platform OAuth tokens stored in the database were encrypted with the previous key. Every sync job fails immediately with decryption errors. Users must reconnect all their ad accounts. The failure mode is indistinguishable at the surface from "connection expired."

**Why it happens:**
The fallback to generate a new key was intended as a development convenience. It becomes catastrophic in a stateless deploy (e.g., Replit container restart) where environment variables may not persist.

**How to avoid:**
Add a startup validation that asserts `TOKEN_ENCRYPTION_KEY` is set and is a valid Fernet key format before accepting any traffic. Fail fast with a descriptive error rather than silently continuing. Store the key in Replit's secret store, not as a `.env` file that may not survive a container rebuild. Document key rotation procedure: generate new key, re-encrypt all tokens in a migration, update the secret.

**Warning signs:**
- `security.py` has a `try/except` around Fernet key parsing with silent fallback
- `TOKEN_ENCRYPTION_KEY` not listed in deployment runbook as required
- Sync errors spiking immediately after a deployment

**Phase to address:**
Security Hardening phase. Startup validation should be implemented before production traffic.

---

### Pitfall 7: APScheduler Multi-Worker Duplicate Job Execution

**What goes wrong:**
APScheduler uses an in-memory job store by default. Under Replit Autoscale with multiple workers, each worker runs its own scheduler instance. Every worker fires the same sync job at the same scheduled time. This causes simultaneous duplicate syncs: duplicate API calls to ad platforms (may hit rate limits or trigger platform abuse detection), duplicate database writes that cause constraint violations or inflated metrics, and database deadlocks on upsert operations.

**Why it happens:**
APScheduler is well-suited for single-process deployments. The existing deadlock retry logic (`string matching "deadlock"` in `scheduler.py`) is the evidence this has already been observed — it's a symptom of this exact problem.

**How to avoid:**
Configure APScheduler with a database-backed job store (PostgreSQL or Redis) that enforces single-instance execution via distributed locking. Alternatively, use a dedicated lightweight worker approach: run the scheduler only in a designated worker (check a `SCHEDULER_ENABLED` env var) and disable it in other workers. For the scale of this application, the env-var approach is simpler and sufficient.

**Warning signs:**
- APScheduler initialized in `main.py` lifespan without a distributed job store
- `string.find("deadlock")` error-detection pattern already present in scheduler
- Metrics showing double-counted spend/impressions after a sync

**Phase to address:**
Platform Reliability phase. Also relevant when adding BrainSuite scoring queue — scoring jobs must not be executed twice for the same creative.

---

### Pitfall 8: Path Traversal in Asset Serving Endpoint

**What goes wrong:**
The asset serving endpoint in `main.py` constructs a GCS object path by concatenating a user-supplied `object_path` parameter with the `creatives/` prefix. A crafted value like `../secrets/SERVICE_ACCOUNT_KEY.json` may traverse outside the intended directory. Even if GCS rejects directory traversal in object names, the endpoint could be used to probe for the existence of objects in other GCS paths, or future refactoring could introduce a local filesystem serving variant where this becomes fully exploitable.

**Why it happens:**
The existing mitigation (prefix with `creatives/`) is insufficient. A path like `creatives/../other-tenant/asset.jpg` normalizes to `other-tenant/asset.jpg` after GCS path resolution, potentially exposing another organization's assets.

**How to avoid:**
Use `pathlib.PurePosixPath` to normalize the path and assert the resolved path starts with `creatives/`. Also assert the path matches a pattern consistent with GCS object naming (`^creatives/[a-zA-Z0-9_\-./]+$`). Switch from serving via proxy to generating short-lived GCS signed URLs (15-minute expiry) — this is already supported by `object_storage.py` — and redirecting the client directly. This eliminates the proxy surface entirely.

**Warning signs:**
- Object path built with string concatenation rather than `pathlib`
- No regex validation on `object_path` parameter
- Asset endpoint returns binary content directly rather than a redirect to a signed URL

**Phase to address:**
Security Hardening phase. Also: switching to signed URL redirects is the correct long-term architecture regardless of the security fix.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `any` type in Angular API service | Fast iteration on untyped API responses | Runtime errors when API shape changes; refactoring requires guessing; BrainSuite score fields typed as `any` fail silently in templates | Only during initial prototype; never in production frontend |
| `except Exception` in sync services | Prevents crashes on unexpected errors | Swallows signal that tokens are expired; makes root cause analysis require log diving; masks data corruption | Never in a system with financial data (ad spend metrics) |
| In-memory OAuth session dict | No Redis dependency in dev | Sessions lost on restart; impossible to scale horizontally; no TTL means memory growth | Only acceptable in local development with single process |
| APScheduler without distributed lock | No queue infrastructure needed | Duplicate sync on multi-worker deploy; race conditions on upsert; deadlocks | Only acceptable when guaranteed single-process (local dev, single Replit deployment) |
| Synchronous Alembic migration at startup | Simple deployment | Blocks startup for up to 15s; fails if migration takes longer than health check timeout; migrations run on every worker restart | Only for MVP/prototype; unacceptable before autoscale |
| Hardcoded `password` in default DATABASE_URL | Easy local setup | Developers accidentally use default in production; security incident risk | Never in a committed config file; use env var with no default |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Google Ads OAuth | Using "Testing" OAuth app status causes refresh tokens to expire after 7 days, even in production deployments | Verify Google Cloud project OAuth consent screen is published ("In production"), not testing status |
| TikTok Ads API | Treating TikTok access tokens as long-lived; they expire in 24 hours | Schedule background rotation of TikTok access tokens; store both access and refresh token with explicit expiry timestamps |
| Meta Ads API | Requesting `ads_management` scope when only `ads_read` is needed; triggers more aggressive review | Request minimum required scopes; `ads_management` only if write operations are planned |
| BrainSuite API | Sending GCS object paths directly without verifying URL is publicly accessible or signed | Verify the URL passed to BrainSuite is a publicly accessible HTTPS URL or a long-lived signed URL (BrainSuite likely fetches the asset server-side) |
| GCS Signed URLs | Generating signed URLs with the default 7-day maximum expiry for dashboard display | Use short expiry (15–60 min) for signed URLs; regenerate on each dashboard load; never store signed URLs in the database |
| DV360 Report API | Treating report polling as a single-request operation; large reports can take up to 2 hours | Persist poll state to database; resume on scheduler restart; set a maximum wait before marking sync as "partial" |
| ExchangeRate-API | Silently returning 1.0 (no conversion) when both currency services fail | Log the failure with the target currency and amount; surface "currency data unavailable" state in the UI rather than silently passing through unconverted values |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Scoring all creatives inline during sync | Sync jobs take 10x longer; platform API rate limits hit during score submission | Decouple scoring from sync; queue creatives for scoring post-sync | First account with >100 creatives |
| N+1 queries when rendering dashboard with unindexed columns | Dashboard load time degrades linearly with data volume | Add composite indexes on `(platform_connection_id, report_date)`, `(ad_account_id, report_date)` | ~5000 performance records per account |
| APScheduler running sync jobs in single thread | Syncs for all platforms queue behind one another; 4-platform sync takes 4x as long as 1 platform | Use async job execution; configure thread pool for concurrent platform syncs | 2+ connected platforms with large datasets |
| Fetching all creatives to find unscored ones | Full table scan on creative table; slow as library grows | Add `score_status` column with index; query `WHERE score_status = 'pending'` | ~1000 creatives |
| Loading full creative asset binary through FastAPI proxy | API server saturates on asset-heavy dashboard loads | Generate GCS signed URL, return redirect; let GCS serve the binary | ~10 concurrent dashboard users |
| Default asyncpg pool size (20) under multi-worker autoscale | Connection pool exhaustion; 500 errors under moderate load | Set `POSTGRES_POOL_SIZE` per worker to `floor(max_connections / worker_count)`; monitor pool wait time | 3+ Replit Autoscale workers + any background jobs |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing ad platform OAuth tokens without verifying they are bound to the requesting organization | Token from one tenant usable by another if user ID check is bypassed | Add `organization_id` filter on all `PlatformConnection` queries; never rely solely on `user_id` for multi-tenant isolation |
| Using organization/account IDs directly in API URLs without authorization check | Attacker enumerates numeric IDs to access other tenants' data | Validate ownership on every read/write; use opaque UUIDs for public-facing resource IDs |
| Returning full platform API error messages to the frontend | Meta/Google error messages may include internal account structure, developer token partial values | Sanitize external API errors before returning; map to user-facing messages |
| CORS configured with `allow_methods=["*"]` and `allow_headers=["*"]` | Allows unexpected HTTP methods and headers; weakens CORS as a defense layer | Explicitly enumerate: `["GET", "POST", "PUT", "DELETE", "OPTIONS"]` and required headers only |
| Plaintext temporary passwords sent to users | Interceptable in transit; user may never change them | Generate cryptographically random temporary passwords; force change on first login; log and alert if password not changed within 24 hours |
| No rate limiting on OAuth initiation endpoints | Platform OAuth initiation can be abused to flood callback logs or probe for valid redirect URIs | Add sliding-window rate limiting per IP on `/oauth/init` and `/oauth/callback` endpoints |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing creative performance metrics without a score status indicator | Users see empty score columns and assume BrainSuite is broken or the integration is incomplete | Show "Scoring..." spinner or "Score pending" badge while `score_status = 'pending'`; show "Score unavailable" if scoring failed |
| Silent sync failures — dashboard shows stale data with no indication | Users make budget decisions on 3-day-old metrics without knowing they are stale | Show "Last synced: 3 days ago — reconnect your Meta account" warning on dashboards when sync age exceeds threshold |
| Treating all 4 platforms as if they sync on the same cadence | DV360 reports take hours; users expect immediate data after connecting | Per-platform sync status; DV360 progress indication; "Initial sync may take up to 2 hours for DV360" onboarding message |
| Displaying BrainSuite dimension scores without explanation | Users see "Attention: 72" and "Memory: 45" with no context for what constitutes a good score | Add score range indicators (color-coded), tooltips explaining each dimension, and contextual comparison (above/below account average) |
| Requiring full page reload to see updated connection status after OAuth | User completes OAuth, returns to app, still sees "Not connected" until they refresh | Poll connection status for 30 seconds after OAuth callback; update NgRx store reactively |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **OAuth connection flow:** Shows "Connected" in UI — verify the stored token has been successfully used to make at least one API call; OAuth consent does not guarantee working API access (scopes may be wrong, developer token may be missing for Google Ads)
- [ ] **BrainSuite scoring:** Score appears in dashboard — verify the score was persisted to the database and is not just held in component state; verify failed scores are retried, not silently dropped
- [ ] **Asset serving:** Images display in dashboard — verify the serving path has been hardened against traversal; verify GCS permissions prevent unauthenticated direct access to the bucket
- [ ] **Token refresh:** Sync runs without error — verify token refresh failure increments a failure counter and eventually transitions platform connection to `disconnected` state; a single refresh failure should not permanently break sync silently
- [ ] **Multi-tenant isolation:** User only sees their own data — verify every database query for creatives, metrics, and platform connections filters on `organization_id`, not just `user_id`; run a cross-tenant access test
- [ ] **Redis session store:** OAuth sessions persist across restarts — verify sessions are not being written to both Redis and the old in-memory dict; verify the TTL is actually being set (check with `TTL session:xyz` in Redis CLI)
- [ ] **Production key management:** App starts successfully — verify `TOKEN_ENCRYPTION_KEY` and `SECRET_KEY` are set as Replit secrets, not in a `.env` file that may be ephemeral; verify startup validation rejects missing keys

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Fernet key rotation invalidates all platform tokens | HIGH | 1. Restore previous key value from backup/secret history. 2. If key is unrecoverable: notify users, prompt re-connection of all platform accounts. 3. Add startup key validation to prevent recurrence. |
| In-memory session loss after deploy | LOW | Users retry OAuth flow; no data lost. Reduce user impact by shortening OAuth session TTL and displaying a friendlier "session expired, please reconnect" error. |
| APScheduler duplicate sync creates double-counted metrics | MEDIUM | Identify affected date ranges from sync job logs. Run deduplication query on performance table keyed by `(platform, account_id, creative_id, date)`. Add `UNIQUE` constraint on that combination to prevent future duplication. |
| JWT localStorage tokens stolen via XSS | HIGH | 1. Rotate `SECRET_KEY` to invalidate all existing JWTs. 2. Force re-login for all users. 3. Audit logs for suspicious API activity. 4. Patch XSS vector. 5. Migrate to httpOnly cookies before re-opening to users. |
| BrainSuite scoring backlog (thousands of unscored creatives) | LOW | Add `score_status = 'pending'` index. Run batch scoring job with rate limiting during off-peak hours. Use `LIMIT 100` chunks with exponential backoff. |
| Path traversal exploit on asset endpoint | MEDIUM-HIGH | 1. Take asset endpoint offline immediately. 2. Audit GCS access logs for anomalous object path requests. 3. Implement pathlib validation + signed URL redirect. 4. Re-enable only after hardening is verified. |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| In-memory OAuth sessions (Pitfall 1) | Security Hardening | Redis session TTL set; OAuth flow works after simulated worker restart; no `_oauth_sessions` dict in code |
| OAuth redirect URI header injection (Pitfall 2) | Security Hardening | Redirect URIs read exclusively from env vars; `x-forwarded-host` validated against allowlist |
| JWT in localStorage (Pitfall 3) | Security Hardening | No `localStorage.setItem` in Angular auth code; access token lives in service memory; `Set-Cookie: httpOnly; Secure` header on login response |
| Silent platform token refresh failure (Pitfall 4) | Platform Reliability | `PlatformConnection.status` field exists; dashboard shows reconnect prompt when `status = 'token_refresh_failed'` |
| BrainSuite N+1 scoring calls (Pitfall 5) | BrainSuite Integration | Scoring decoupled from sync; `score_status` field on creative; rate-limited queue confirmed with >50 creative test |
| Fernet key rotation catastrophe (Pitfall 6) | Security Hardening | Startup fails with descriptive error when `TOKEN_ENCRYPTION_KEY` not set; key stored in Replit secrets |
| APScheduler duplicate job execution (Pitfall 7) | Platform Reliability | Scheduler disabled in secondary workers via env var; no duplicate metric rows after simulated multi-worker sync |
| Path traversal in asset serving (Pitfall 8) | Security Hardening | `pathlib` normalization + regex validation in asset endpoint; or endpoint replaced with signed URL redirect |

---

## Sources

- BrainSuite Platform Connector codebase concern audit: `.planning/codebase/CONCERNS.md`
- TikTok Ads API access token management: https://developers.tiktok.com/doc/oauth-user-access-token-management
- Google Ads API refresh token expiry (Testing vs Production status): https://groups.google.com/g/adwords-api/c/6WNYZYBMF2c
- OAuth 2.0 production pitfalls (redirect URI injection, PKCE, token exposure): https://securityboulevard.com/2025/03/oauth-2-0-explained-a-complete-guide-to-secure-authorization/
- Third-party OAuth token supply chain risks: https://unit42.paloaltonetworks.com/third-party-supply-chain-token-management/
- JWT localStorage vs httpOnly cookies, Angular SPA: https://javascript.plainenglish.io/the-secure-way-to-handle-jwt-authentication-in-angular-stop-using-localstorage-96e7be0d9b8c
- JWT hybrid pattern (access in memory, refresh in httpOnly cookie): https://medium.com/lets-code-future/stop-using-localstorage-for-jwts-in-your-spa-heres-the-safer-smarter-alternative-in-2025-ece409045978
- FastAPI async SQLAlchemy production patterns: https://orchestrator.dev/blog/2025-1-30-fastapi-production-patterns/
- Sync SQLAlchemy in async FastAPI (event loop blocking): https://medium.com/@patrickduch93/the-hidden-trap-in-fastapi-projects-accidently-using-sync-sql-alchemy-in-an-async-app-245b0391a17d
- APScheduler multi-process duplicate execution: https://apscheduler.readthedocs.io/en/stable/faq.html
- APScheduler AsyncIOScheduler defaults to ThreadPoolExecutor (event loop risk): https://github.com/agronholm/apscheduler/issues/304
- Redis session race conditions and TTL pitfalls: https://fsck.sh/en/blog/redis-session-locking-pitfalls-symfony/
- Redis session management best practices: https://redis.io/tutorials/howtos/solutions/mobile-banking/session-management/
- Multi-tenant data isolation and cross-tenant leakage patterns: https://agnitestudio.com/blog/preventing-cross-tenant-leakage/
- Row-level security failures in multi-tenant SaaS: https://medium.com/@instatunnel/multi-tenant-leakage-when-row-level-security-fails-in-saas-da25f40c788c
- GCS signed URL best practices (short expiry, HTTPS only): https://medium.com/google-cloud/managing-signed-url-risks-in-google-cloud-4d256bd58735
- Async pipeline idempotency (duplicate execution, stuck jobs): https://dev.to/damikaanupama/designing-asynchronous-apis-with-a-pending-processing-and-done-workflow-4gpd
- Idempotent data pipeline patterns: https://medium.com/towards-data-engineering/building-idempotent-data-pipelines-a-practical-guide-to-reliability-at-scale-2afc1dcb7251

---
*Pitfalls research for: Multi-tenant ad platform connector with BrainSuite creative scoring (FastAPI + Angular + GCS)*
*Researched: 2026-03-20*
