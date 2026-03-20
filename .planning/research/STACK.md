# Stack Research

**Domain:** Ad tech platform — third-party AI scoring API integration + production hardening
**Researched:** 2026-03-20
**Confidence:** MEDIUM-HIGH (existing stack verified; new additions verified via PyPI/GitHub; BrainSuite API schema unknown)

---

## Context: What This Research Covers

This is a brownfield project. The existing stack (FastAPI 0.115 + Angular 17 + PostgreSQL + APScheduler + httpx) is fixed. This research focuses exclusively on **new additions** needed for:

1. BrainSuite API integration — async HTTP calls with retry, job state tracking
2. Production security hardening — OAuth session store, JWT token storage
3. Platform data reliability — sync error surfacing, resilient background jobs

Do not re-evaluate Angular, FastAPI, SQLAlchemy, or PostgreSQL. They are not changing.

---

## Recommended Stack: New Additions Only

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| redis-py (asyncio) | 7.1.1 | Job state tracking, OAuth session store, scoring job queue | Redis is already configured (`REDIS_URL` env var exists, client just needs wiring). `redis.asyncio` is the unified async API since redis-py 4.2 — aioredis is abandoned. Native asyncio support means no bridge needed with FastAPI's async stack. |
| tenacity | 9.1.4 | Retry logic with exponential backoff for BrainSuite API calls | Already the Python ecosystem standard for retry logic. Supports `@retry` on async functions natively via `AsyncRetrying`. Handles retries on timeouts, 429s, and transient 5xx — exactly what a third-party AI API integration needs. Composable with `wait_exponential`, `stop_after_attempt`, `retry_if_exception_type`. |
| APScheduler 3.10.4 | 3.10.4 | Background scoring jobs triggered post-sync | Already in requirements.txt. Keep it — the existing sync jobs use it. Do not introduce a second task system for scoring jobs; route scoring through the same scheduler instead. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.28.1 | HTTP client for BrainSuite API calls | Already in requirements at 0.25.2; upgrade to 0.28.1 for bug fixes and modern SSL API. The project already uses httpx for all platform API calls — use it consistently for BrainSuite too. `httpx.AsyncClient` with tenacity wrapping is the pattern. |
| python-jose[cryptography] | 3.4.0 (existing) | JWT signing + verification | Already present. For the httpOnly cookie migration, no new JWT library is needed — the signing stays the same; only the transport mechanism (cookie vs Authorization header) changes. |
| fastapi (built-in Response) | 0.115.0 (existing) | Set httpOnly cookies on login response | FastAPI's `Response.set_cookie()` with `httponly=True`, `secure=True`, `samesite="lax"` is sufficient. No additional library needed. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest-asyncio | Async test support for scoring pipeline | The project has no Python test framework. Adding pytest + pytest-asyncio enables testing the BrainSuite client and retry logic before wiring to production. |
| pytest-httpx | Mock httpx calls in tests | Allows testing BrainSuite API client without live API calls. Pairs with pytest-asyncio. |

---

## Installation

```bash
# Backend: new additions to requirements.txt
pip install redis==7.1.1 tenacity==9.1.4

# Upgrade httpx from 0.25.2 to 0.28.1
pip install httpx==0.28.1

# Dev/test only
pip install pytest pytest-asyncio pytest-httpx
```

No frontend library additions are needed. The Angular scoring UI uses RxJS polling against a FastAPI job-status endpoint — RxJS is already bundled with Angular 17.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| redis-py asyncio (job state in Redis) | PostgreSQL job state table | Use PostgreSQL if Redis is unavailable or too costly. Adds row-level locking complexity; Redis is faster for ephemeral job state. PostgreSQL is the right store for final scored results, not job status. |
| tenacity | httpx-retries transport layer | Use httpx-retries if you want retry logic declaratively at the transport level rather than the function level. Tenacity is preferred here because retry behavior needs to vary by exception type (429 = long backoff; 5xx = short backoff; 4xx = no retry), which is easier to express with tenacity's composable retry conditions. |
| APScheduler (existing, extended) | taskiq / arq | Use taskiq if the project outgrows single-process scheduling and needs distributed workers. ARQ is explicitly in maintenance-only mode (GitHub issue #510) — do not introduce it. Taskiq is the async-native successor but adds significant setup overhead for what is a modest scoring workload. APScheduler with Redis-backed job state is sufficient for v1. |
| APScheduler (existing, extended) | Celery + Redis | Use Celery only if CPU-bound work or distributed workers across machines are required. Celery adds broker management overhead and is synchronous by default — bridging to FastAPI's async event loop requires extra configuration. Not warranted here. |
| FastAPI built-in cookies | fastapi-jwt-auth library | Use fastapi-jwt-auth only if you need token refresh rotation, CSRF double-submit pattern, or complex multi-token scenarios out of the box. For this project, manually setting `httponly=True` cookies in login/refresh endpoints is 10 lines of code and avoids a dependency. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| arq (Python task queue) | Officially in maintenance-only mode (GitHub issue #510, confirmed March 2025). No new features. PRs go unreviewed. | Extend APScheduler for job-triggered scoring; use taskiq if outgrowing APScheduler in v2. |
| aioredis | Abandoned — merged into redis-py 4.2 in 2022. PyPI package is archived. `import aioredis` will break on Python 3.12. | `import redis.asyncio as redis` from redis-py 7.x |
| httpx-retry | Abandoned as of April 2025 per maintainer. | tenacity wrapping httpx.AsyncClient, or httpx-retries if transport-level retry is preferred. |
| In-memory `_oauth_sessions` dict (existing) | Dies on process restart; breaks multi-worker Replit Autoscale deployments. OAuth state tokens become invalid when a request hits a different worker. | Redis key with TTL (e.g., 10-minute expiry on state param). This is the primary production blocker. |
| localStorage for JWT (existing) | XSS-vulnerable. Any injected script reads the token. Industry consensus since 2020: access tokens in memory, refresh token in httpOnly cookie. | httpOnly `Secure` cookie for refresh token; in-memory variable (Angular service) for short-lived access token. |
| Polling the BrainSuite API synchronously in the HTTP request path | Ties up a FastAPI worker thread/coroutine for the duration of the scoring call (potentially 10-30s for video). Causes request timeouts and blocks other users. | Enqueue a scoring job in APScheduler/Redis from the sync completion hook; poll job status from the frontend via a `/scoring/status/{job_id}` endpoint. |

---

## Scoring Pipeline Pattern

The correct async integration pattern for a third-party AI scoring API without known response time SLA:

```
[Sync completes] → [APScheduler fires score_creative job]
                         ↓
              [Fetch GCS signed URL for asset]
                         ↓
              [POST to BrainSuite API via httpx.AsyncClient]
              [tenacity: retry on 429/5xx, max 5 attempts, exponential backoff]
                         ↓
              [Store result in PostgreSQL creative_scores table]
              [Update job state in Redis: pending → complete/failed]
                         ↓
[Angular polls /api/v1/scoring/status/{job_id} every 5s]
[RxJS: timer(0, 5000).pipe(switchMap(...), takeUntil(complete$))]
                         ↓
              [Dashboard updates score display when complete]
```

**Why polling, not webhook:**
BrainSuite's API schema is unknown. Polling is safer to implement without knowing if BrainSuite supports webhooks. Once BrainSuite API docs are confirmed, webhooks can replace polling in v2 if latency matters.

**Why GCS signed URL, not re-upload:**
Assets are already in Google Cloud Storage. BrainSuite should receive a signed URL reference. This avoids bandwidth costs, upload latency, and duplication. Signed URLs can be short-lived (1-hour TTL is sufficient for a scoring job).

---

## Security Hardening Stack Decisions

### OAuth Session Store Migration

**Current:** `_oauth_sessions = {}` — in-memory dict in platforms.py
**Target:** Redis key with TTL

```python
# Key pattern: oauth_session:{state_token}
# TTL: 600 seconds (10 minutes — long enough for OAuth dance)
# Value: JSON blob with platform, redirect_uri, user_id
await redis_client.setex(f"oauth_session:{state}", 600, json.dumps(session_data))
```

Redis is already configured via `REDIS_URL`. This is a 1-day change, not a migration project.

### JWT Token Storage Migration

**Current:** localStorage in Angular
**Target:** Refresh token in httpOnly cookie; access token in memory only

FastAPI side: `response.set_cookie("refresh_token", token, httponly=True, secure=True, samesite="lax", max_age=604800)`

Angular side: Remove `localStorage.getItem("token")` calls. Store access token in an Angular service's private property (survives navigation, cleared on tab close). On page load, call `/api/v1/auth/refresh` with the httpOnly cookie to rehydrate the access token.

**Confidence:** HIGH — this is the documented production pattern for FastAPI + Angular SPA auth.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| redis 7.1.1 | Python 3.12+ | Requires Python 3.8+. redis-py 7.x dropped Python 3.7. Compatible with existing stack. |
| tenacity 9.1.4 | Python 3.10+ | Requires Python >=3.10. Existing stack is Python 3.12 — compatible. |
| httpx 0.28.1 | FastAPI 0.115 | FastAPI uses httpx internally for TestClient. 0.28.x is the current stable. The `proxies` argument was removed in 0.28 — verify no existing code passes `proxies=` to httpx. |
| APScheduler 3.10.4 (existing) | redis-py 7.x | APScheduler 3.x has a Redis jobstore (`apscheduler.jobstores.redis`) — not needed here, but compatible. Keep APScheduler at 3.10.4; version 4.x has breaking API changes. |

---

## Upstash Redis (Replit Constraint Note)

Replit Autoscale does not include a Redis sidecar. The existing `REDIS_URL=redis://localhost:6379/0` will fail in production autoscale because there is no local Redis process.

**Recommended:** Upstash Redis (serverless, HTTP-based Redis compatible with redis-py via `rediss://` URL). Upstash has explicit Replit integration documentation and is used in production on Replit. Free tier covers the OAuth session + job state volume of this project.

The `REDIS_URL` env var already in config.py is the right abstraction — changing from `redis://localhost:6379` to an Upstash `rediss://` URL requires no code change, only environment variable update.

**Confidence:** MEDIUM — verified Upstash + Replit integration exists; Replit's own Redis sidecar availability not confirmed from docs.

---

## Sources

- [python-arq/arq GitHub — Issue #510 (maintenance mode)](https://github.com/python-arq/arq/issues/437) — confirmed maintenance-only status
- [redis-py PyPI — version 7.1.1](https://pypi.org/project/redis/) — current version, asyncio unified API
- [tenacity PyPI — version 9.1.4](https://pypi.org/project/tenacity/) — current version, Python 3.10+ requirement
- [httpx GitHub releases — 0.28.1](https://github.com/encode/httpx/releases/tag/0.28.0) — current stable, proxies argument removed
- [Upstash Replit integration docs](https://upstash.com/docs/redis/integrations/replit-templates) — confirmed Replit+Upstash Redis support
- [Angular polling with RxJS — production patterns](https://medium.com/@sourabhda1998/5-genius-ways-to-build-a-polling-service-using-rxjs-interval-that-actually-work-in-production-414cdccd1e35) — MEDIUM confidence (web search)
- [FastAPI httpOnly cookie JWT pattern](https://www.fastapitutorial.com/blog/fastapi-jwt-httponly-cookie/) — HIGH confidence, documented official pattern
- [aioredis abandoned, merged into redis-py](https://redis.io/faq/doc/26366kjrif/what-is-the-difference-between-aioredis-v2-0-and-redis-py-asyncio) — HIGH confidence, official Redis FAQ

---

*Stack research for: BrainSuite creative scoring integration + production hardening*
*Researched: 2026-03-20*
