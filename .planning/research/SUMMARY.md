# Project Research Summary

**Project:** BrainSuite Platform Connector
**Domain:** Multi-tenant ad creative analytics platform with AI effectiveness scoring
**Researched:** 2026-03-20
**Confidence:** MEDIUM-HIGH

## Executive Summary

BrainSuite Platform Connector is a brownfield SaaS product for ad agencies that already syncs creatives from Meta, TikTok, Google Ads, and DV360 into a unified dashboard. The gap being closed in this milestone is threefold: wiring BrainSuite's pre-launch creative effectiveness API into the scoring pipeline, hardening the platform against production security vulnerabilities that exist in the current codebase, and surfacing sync health and scores in the UI. Experts build this class of product with a decoupled async scoring pipeline — never blocking the sync or request path on a third-party AI API call — and with Redis-backed session state to handle horizontal scaling.

The recommended approach is to execute in three sequential phases: security hardening first (two critical blockers must be fixed before real users onboard), then BrainSuite scoring pipeline integration (the primary milestone deliverable), then dashboard polish and sync reliability improvements that make the product trustworthy at agency scale. The existing FastAPI + Angular + PostgreSQL + APScheduler stack is retained unchanged. New additions are minimal: redis-py asyncio (already configured, just needs wiring), tenacity for retry logic, and an httpx upgrade. No new infrastructure is required for v1.

The key risk is the existing codebase's in-memory OAuth session dict and localStorage JWT storage — both are production blockers exploitable under Replit Autoscale or by XSS. A second risk is the BrainSuite API schema: it is not publicly documented, so the scoring schema (dimension names, score range, response format) must be validated against a live API call before UI work proceeds. A third risk is APScheduler running on every worker in a multi-worker deploy, which can cause duplicate sync execution and double-counted ad metrics — this must be resolved in the reliability phase with a single-scheduler env var guard.

## Key Findings

### Recommended Stack

The existing stack (FastAPI 0.115, Angular 17, PostgreSQL, APScheduler 3.10.4, httpx 0.25.2) is fixed and not re-evaluated. New additions are strictly minimal. Redis is already configured via `REDIS_URL` — it just needs the `redis.asyncio` client wired up to replace the in-memory OAuth session dict and act as ephemeral job state store. Tenacity 9.1.4 provides composable retry logic for BrainSuite API calls with differentiated backoff per exception type (429 = long backoff, 5xx = short backoff, 4xx = no retry). httpx should be upgraded from 0.25.2 to 0.28.1 for bug fixes.

Three libraries are explicitly off-limits: `aioredis` (abandoned, merged into redis-py, breaks Python 3.12), `arq` (maintenance-only since March 2025), and `httpx-retry` (abandoned April 2025). The existing APScheduler handles scoring jobs — no second task system should be introduced. For Replit Autoscale, Upstash Redis is the recommended backing service since Replit does not include a Redis sidecar.

**Core technologies:**
- `redis.asyncio` (redis-py 7.1.1): OAuth session store + scoring job state — already configured, needs wiring
- `tenacity` 9.1.4: Retry logic for BrainSuite API calls — composable per-exception backoff
- `httpx` 0.28.1: HTTP client for BrainSuite — already in use, upgrade for bug fixes
- `APScheduler` 3.10.4 (existing): Background scoring jobs — extend existing scheduler, do not add a second system
- `pytest` + `pytest-asyncio` + `pytest-httpx`: Test coverage for BrainSuite client before wiring to production

### Expected Features

The product's core value proposition — a pre-launch AI effectiveness score alongside live performance data — requires completing BrainSuite integration before any UI polish makes sense. Competitors (Motion, Superads) derive scores from performance data after ads run; BrainSuite scores creatives independently of spend. The UI must reinforce this distinction clearly.

**Must have (table stakes):**
- BrainSuite API integration (POST asset URL, receive score + dimensions, persist) — primary milestone gap
- Score + dimension breakdown visible per creative — agencies trust breakdown, not just an aggregate number
- Auto-scoring on sync — no manual trigger; score present when creative appears
- Production security hardening (Redis OAuth sessions, httpOnly JWT cookies) — gate before external users
- Sort and filter by score, ROAS, CTR, spend, platform, date range — core navigation
- Creative thumbnail visible — users need to see the ad, not just data
- Sync status display + sync error surfacing — stale/failed data destroys trust
- Fernet key startup validation — prevents catastrophic token loss on container restart

**Should have (competitive):**
- Score-to-performance correlation view (score vs. ROAS scatter/table) — builds agency trust in scoring system
- Manual re-score trigger — for missing or stale scores
- Top/bottom performer visual identification — "scale this, kill that" decision support
- Read-only share link — agencies share results with clients; higher value than notifications

**Defer (v2+):**
- Notification system (Slack/email on score arrival)
- White-label reports
- Multi-platform creative identity (same creative on Meta and TikTok)
- Ad copy / text creative scoring
- Creative scoring trend over time

### Architecture Approach

The correct architecture for this integration is a state-machine-backed async scoring pipeline: sync services mark new assets as `UNSCORED` in a `creative_score_results` table, an APScheduler job (every 15 minutes) picks up batches of unscored assets and calls `BrainSuiteScoreService`, results are written back to both the authoritative `creative_score_results` table and denormalized onto `creative_assets.ace_score` for fast dashboard queries. The frontend polls a status endpoint every 30 seconds only while PENDING/PROCESSING assets are visible — not on every page load.

Build order matters: schema and Alembic migration first, then the `BrainSuiteScoreService` (testable in isolation), then scheduler integration, then API endpoints, then frontend score badge, then dimension breakdown panel, then conditional polling.

**Major components:**
1. `creative_score_results` table — authoritative scoring status per asset; states: UNSCORED → PENDING → PROCESSING → COMPLETE | FAILED
2. `BrainSuiteScoreService` (`backend/app/services/brainsuite_score.py`) — async httpx client with tenacity retry; generates fresh GCS signed URLs per request
3. APScheduler scoring job — registered alongside existing sync jobs; 15-minute interval; batch of 20; respects BrainSuite rate limits via semaphore
4. Scoring API endpoints (`/scoring/trigger`, `/scoring/status`) — manual trigger + frontend polling surface
5. Score badge + dimension breakdown components — Angular components wired into existing dashboard table

### Critical Pitfalls

1. **In-memory OAuth sessions break under Autoscale** — Replace `_oauth_sessions` dict with Redis `SETEX` (10-minute TTL). This is a hard production blocker; second worker cannot find sessions created by the first. Must land before any external user onboarding.

2. **JWT in localStorage exposes all ad platform tokens on XSS** — Migrate to hybrid pattern: access token in Angular service memory only, refresh token in `httpOnly; Secure; SameSite=Lax` cookie. Remove all `localStorage.setItem` calls in `auth.service.ts`. Ad creative metadata rendered in the dashboard is an XSS surface.

3. **APScheduler runs on every worker — duplicate syncs, double-counted metrics** — Add `SCHEDULER_ENABLED` env var; disable scheduler in secondary workers. The existing deadlock retry string-matching in `scheduler.py` is evidence this is already occurring.

4. **BrainSuite N+1 scoring inline during sync** — Never call BrainSuite inside the asset sync loop. Mark assets `UNSCORED` after sync; let the separate scoring scheduler handle batched submission with rate limiting.

5. **Fernet key lost on container restart invalidates all stored platform tokens** — Add startup assertion: fail fast if `TOKEN_ENCRYPTION_KEY` is not set and valid. Store in Replit secrets, not `.env`.

## Implications for Roadmap

Based on combined research, a three-phase structure is recommended. Security blockers gate real users, BrainSuite integration is the milestone's primary deliverable, and dashboard/reliability polish is the final layer.

### Phase 1: Security Hardening

**Rationale:** Two critical vulnerabilities (in-memory OAuth sessions, localStorage JWT) are production blockers that make external user onboarding unsafe. A third (Fernet key validation) is a potential catastrophic data loss event. These must be fixed before any new feature work is visible to real users. All fixes are well-understood, low-dependency, and can be completed without touching the scoring pipeline.

**Delivers:** A production-safe auth stack; OAuth flows that survive multi-worker deploys; tokens protected from XSS; startup key validation; path traversal fix on asset endpoint; CORS lockdown.

**Addresses pitfalls:** Pitfall 1 (OAuth sessions), Pitfall 2 (OAuth redirect URI injection), Pitfall 3 (JWT in localStorage), Pitfall 6 (Fernet key rotation), Pitfall 8 (path traversal)

**Features:** Production security hardening (P1); enables safe external user onboarding gate

**Research flag:** No deeper research needed — these are well-documented patterns with HIGH confidence.

### Phase 2: BrainSuite Scoring Pipeline

**Rationale:** This is the primary deliverable of the milestone. The architecture (async scoring pipeline with state machine) must be established before any UI work on scores can begin. The BrainSuite API schema is unknown — the first step of this phase must validate the actual response format from a live API call before schema and UI are finalized. Build order follows component dependency chain: schema → service → scheduler → endpoints → frontend.

**Delivers:** Full scoring pipeline from sync-trigger to dashboard display; `creative_score_results` table with status machine; `BrainSuiteScoreService` with tenacity retry; APScheduler scoring job; score badge and dimension breakdown in dashboard; historical backfill for existing unscored assets.

**Uses:** redis-py asyncio (job state), tenacity 9.1.4 (retry), httpx 0.28.1 (API client), APScheduler (existing)

**Implements:** BrainSuiteScoreService, creative_score_results table, scoring API endpoints, score badge component, dimension breakdown panel, conditional RxJS polling

**Addresses pitfalls:** Pitfall 5 (N+1 scoring), BrainSuite N+1 anti-pattern, scoring status polling anti-pattern

**Research flag:** Needs live BrainSuite API schema validation at phase start — dimension field names, score range, response envelope are unknown. Do not finalize DB schema or Angular component until first real response is inspected.

### Phase 3: Platform Reliability + Dashboard Polish

**Rationale:** With security hardened and scoring working, the remaining work is making the platform trustworthy under real agency usage: silent sync failures must surface, the APScheduler multi-worker duplicate execution risk must be eliminated, and the dashboard UX must meet agency speed/clarity expectations (thumbnails, sort/filter, sync status, top/bottom performer identification).

**Delivers:** Explicit platform connection state machine (connected / token_refresh_failed / disconnected) with UI reconnect prompts; APScheduler single-instance guard via `SCHEDULER_ENABLED` env var; dashboard sort + filter by score, ROAS, CTR, spend; creative thumbnails; sync status display per platform; sync error surfacing; score dimension context (color-coded ranges, tooltips).

**Addresses pitfalls:** Pitfall 4 (silent token refresh failure), Pitfall 7 (APScheduler duplicate execution), performance trap (N+1 dashboard queries), UX pitfall (stale data with no indicator)

**Research flag:** No deeper research needed — platform connection state machines and APScheduler single-instance patterns are standard. UX details (color thresholds for score ranges) depend on BrainSuite's confirmed score scale from Phase 2.

### Phase Ordering Rationale

- Security hardening must come first: the OAuth session and JWT issues are exploitable today and block external onboarding regardless of feature completeness.
- BrainSuite integration is phase-gated on security being clean, and gate-keeps dashboard polish (no point styling score badges before scores exist).
- Dashboard polish and reliability improvements are last because they depend on confirmed scoring schema (BrainSuite dimension field names needed for dimension tooltips) and require the security layer to be stable so UX can be tested with real users.
- The BrainSuite API schema unknown is the single highest-risk dependency gap in the entire roadmap — Phase 2 must start with a spike to validate the actual API response before committing to schema design.

### Research Flags

Phases needing deeper research during planning:
- **Phase 2 (BrainSuite Scoring):** BrainSuite API schema is unknown. Requires a discovery spike at phase start: POST a test asset to the API, inspect the full response envelope (score field names, dimension structure, score range, error format, rate limit headers). Do not finalize `creative_score_results` table schema or Angular component structure until this is complete.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Security Hardening):** All fixes are well-documented with HIGH confidence sources. Redis OAuth sessions, httpOnly cookies, pathlib path validation, Fernet startup assertion — these are standard production patterns.
- **Phase 3 (Reliability + Polish):** APScheduler single-instance guard and platform connection state machines are standard patterns. UX thresholds (score color ranges) are a product decision, not a research question.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Existing stack verified by codebase analysis. New additions (redis-py, tenacity) verified via PyPI/GitHub. Upstash Redis on Replit is MEDIUM (integration confirmed, sidecar availability not definitively confirmed). |
| Features | MEDIUM-HIGH | Table stakes and differentiators grounded in competitor analysis (Motion, Superads official sources) and PROJECT.md. BrainSuite API capability assumptions (dimensions, score range) are MEDIUM — unconfirmed until live API call. |
| Architecture | HIGH | Grounded in existing codebase analysis + well-established async pipeline patterns (APScheduler + FastAPI BackgroundTasks + PostgreSQL state machine). Build order verified against actual file structure. |
| Pitfalls | HIGH | Most pitfalls identified from direct codebase inspection (`_oauth_sessions`, `localStorage`, deadlock retry string-matching, Fernet fallback generation). Not theoretical — these are confirmed issues in the existing code. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **BrainSuite API schema:** Unknown. Dimension field names, score range (0–100? 0–1?), response envelope, error format, rate limit headers — all unknown. Handle by making the first task of Phase 2 a dedicated API discovery spike. Do not design schema, DB columns, or Angular types until this is confirmed.
- **Upstash Redis availability on Replit Autoscale:** Replit's own Redis sidecar availability is not confirmed from docs. Handle by using Upstash Redis (confirmed Replit integration) as the target from day one rather than assuming a local Redis sidecar.
- **BrainSuite API rate limits:** Not documented. Handle by starting with a conservative batch size (5–10 concurrent requests per scheduler run) and building the semaphore to be configurable. Monitor 429 responses in the first week of production use.
- **Google Ads OAuth consent screen status:** If the Google Cloud project is still in "Testing" mode, refresh tokens expire after 7 days in production. Verify consent screen is published before Phase 3.
- **69 `any` types in Angular frontend:** Increases XSS risk (untyped API responses may carry unexpected HTML) and will cause silent failures when BrainSuite dimension field names are added. Should be addressed as part of Phase 2 frontend work when score types are defined.

## Sources

### Primary (HIGH confidence)
- BrainSuite Platform Connector codebase: direct inspection of `_oauth_sessions`, `auth.service.ts`, `scheduler.py`, `security.py`, `creative.py`, `object_storage.py`
- `.planning/codebase/CONCERNS.md` — identified production concerns from codebase audit
- PROJECT.md — validated project scope and constraints from project owner
- [redis-py PyPI 7.1.1](https://pypi.org/project/redis/) — unified asyncio API, aioredis abandonment confirmed
- [tenacity PyPI 9.1.4](https://pypi.org/project/tenacity/) — Python 3.10+ requirement confirmed
- [FastAPI Background Tasks official docs](https://fastapi.tiangolo.com/tutorial/background-tasks/) — async task pattern
- [FastAPI httpOnly cookie JWT pattern](https://www.fastapitutorial.com/blog/fastapi-jwt-httponly-cookie/) — documented official pattern
- [aioredis abandoned, merged into redis-py](https://redis.io/faq/doc/26366kjrif/what-is-the-difference-between-aioredis-v2-0-and-redis-py-asyncio) — official Redis FAQ

### Secondary (MEDIUM confidence)
- [Superads: How We Built Superads Scores](https://www.superads.ai/blog/how-we-built-superads-scores) — competitor scoring feature analysis
- [Superads vs. Motion Feature Comparison](https://www.superads.ai/superads-vs-motion) — feature landscape
- [Motion: Key Creative Performance Metrics](https://motionapp.com/blog/key-creative-performance-metrics) — competitor feature analysis
- [Upstash Replit integration docs](https://upstash.com/docs/redis/integrations/replit-templates) — confirmed Replit+Upstash Redis support
- [httpx GitHub releases 0.28.1](https://github.com/encode/httpx/releases/tag/0.28.0) — proxies argument removal noted
- [APScheduler multi-process duplicate execution](https://apscheduler.readthedocs.io/en/stable/faq.html) — distributed lock guidance
- [JWT hybrid pattern (access in memory, refresh in httpOnly cookie)](https://medium.com/lets-code-future/stop-using-localstorage-for-jwts-in-your-spa-heres-the-safer-smarter-alternative-in-2025-ece409045978)
- [OAuth 2.0 redirect URI injection](https://securityboulevard.com/2025/03/oauth-2-0-explained-a-complete-guide-to-secure-authorization/)

### Tertiary (LOW confidence)
- [Segwise: Creative Analytics for Meta Ads in 2026](https://segwise.ai/blog/facebook-ads-reporting-creative-intelligence) — industry blog, feature context
- [Madgicx: 10 Best Ad Tech Platforms for Creative Optimization in 2025](https://madgicx.com/blog/ad-tech-platform-for-creative-optimization) — industry blog, feature landscape

---
*Research completed: 2026-03-20*
*Ready for roadmap: yes*
