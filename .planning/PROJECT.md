# BrainSuite Platform Connector

## What This Is

A production-ready multi-tenant SaaS platform that connects Meta, TikTok, Google Ads, and DV360 ad accounts, syncs creative assets and performance metrics into a unified dashboard, automatically scores every imported creative for effectiveness via the BrainSuite API, and surfaces AI-powered metadata inference, score-to-ROAS correlation, and in-app notifications. Agencies use it to immediately identify which creatives to scale or kill based on objective effectiveness scores alongside ROAS, CTR, and spend.

## Core Value

A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.

## Current State

**Version:** v1.5 — in progress (started 2026-05-18)

**Stack:** Angular 17 + FastAPI + PostgreSQL + Redis + MinIO — fully containerized via Docker Compose
**Deployment:** Any cloud host or local dev via `docker-compose up`
**LOC:** ~52,000 (v1.0) + ~23,842 net (v1.1) + ~21,240 net (v1.2) + ~15,000 net (v1.3)

**What works:**
- Multi-tenant organization with RBAC
- OAuth connection + background sync for Meta, TikTok, Google Ads, DV360
- Creative asset storage via S3-compatible storage (MinIO local / S3 production)
- TikTok video and image asset download to MinIO/S3 — unblocks AI autofill + BrainSuite scoring for TikTok creatives
- Automatic BrainSuite scoring pipeline (15-min scheduler) — video AND image creatives
- Image scoring via BrainSuite Static API with `ScoringEndpointType` lookup; UNSUPPORTED badge for non-Meta platforms
- Admin backfill endpoint to score all pre-v1.1 unscored assets
- Score trend chart (GET /dashboard/score-trend); top/bottom performer badges via PERCENT_RANK
- Performance tab redesigned as tile/card grid; score-to-ROAS scatter chart with Stars/Q-Marks/Workhorses/Laggards quadrants
- Gemini 2.5 Flash Vision + Whisper auto-fill on every new asset sync; per-field toggle on metadata config page; inference status badge in asset detail
- In-app notifications: bell icon + unread badge + MatMenu inbox + 30s polling + MatSnackBar toasts for SYNC_FAILED and TOKEN_EXPIRED
- Per-org BrainSuite credentials (Client ID + encrypted Secret) + app names stored in DB; scoring pipeline reads from DB, not `.env`
- BrainSuite Settings UI: masked secret, Test Connection live auth check, `system_app_name` accordion per app, re-score dialog on config change
- Field mapping editor (slide panel): standard + custom API fields per app type, mandatory flag, D-06 auto-match, FMAP-07 pipeline guard
- `SystemConfig` singleton table with Fernet-encrypted YouTube cookie slots; SuperAdmin role + JWT claim + `/configuration/admin` UI; `dv360_sync.py` reads cookies from DB (env var fallback); `COOKIE_FAILED` notification broadcast to SuperAdmins
- PostgreSQL `background_jobs` persistence layer with autovacuum tuning and 30-day cleanup
- Full service instrumentation: sync, download, autofill, scoring all write job records with real-time progress via Redis pub/sub
- SSE real-time transport (`/api/v1/jobs/stream`) with 30s keepalive heartbeat and clean connection lifecycle management
- SuperAdmin monitoring UI at /configuration/jobs — 4-tab job table, real-time SSE progress bars, drill-in detail panels (full Gemini output, download manifests, error tracebacks, per-asset scores)
- Residential proxy (IPRoyal/DataImpulse) injected into DV360 and Google Ads yt-dlp download paths — credential redaction, sticky session IDs, cookieless-first retry, bgutil PO token plugin auto-invoked
- SuperAdmin proxy config UI at /configuration/admin — Fernet-encrypted URL, enable/disable toggle, masked display, httpx reachability test
- Dashboard metadata filter — org-scoped autocomplete, OR-within-field / AND-across-fields composition, chip row
- Dashboard ad account multi-select filter — platform-grouped (Meta → TikTok → Google Ads → DV360) with search input
- Dashboard video duration range slider — dual-handle, async backfill at all 8 sync sites, NULL callout, ffprobe extraction for all 4 platforms

**Known tech debt:**
- Performer badge minimum guard is 3 assets (requirement: 10) — minor threshold mismatch
- Score trend shows single data point per asset (no append-only history table — intentional per D-09)
- Phases 7, 8, 10 missing formal VERIFICATION.md files; Phase 12 missing VERIFICATION.md (implementation confirmed via integration checks)
- `get_asset_detail()` hardcoded None for score fields (unused by frontend; confusing for API consumers)
- GCP Cloud SQL DB password (`BrainsuiteDB2024!`) is a placeholder — must be rotated before production go-live

## Requirements

### Validated

- ✓ User authentication (register, login, JWT session management) — existing
- ✓ Multi-tenant organization structure with RBAC — existing
- ✓ Meta OAuth connection and background sync — existing
- ✓ TikTok OAuth connection and background sync — existing
- ✓ Google Ads OAuth connection and background sync — existing
- ✓ DV360 OAuth connection and background sync — existing
- ✓ Creative asset storage (images, videos) via S3-compatible storage — v1.0 (Phase 1)
- ✓ Data harmonization layer (normalized metrics across platforms) — existing
- ✓ Unified dashboard with performance metrics — existing + v1.0
- ✓ Currency conversion across platforms — existing
- ✓ Docker Compose portability — zero Replit dependency — v1.0 (Phase 1)
- ✓ Production security hardening — httpOnly cookie auth, encrypted tokens, path traversal fix — v1.0 (Phase 2)
- ✓ BrainSuite API integration (video) — POST asset + metadata, receive score + dimensions, store results — v1.0 (Phase 3)
- ✓ Creative scoring visible in dashboard — score badge, CE dimension tab, sort/filter by score range — v1.0 (Phase 3–4)
- ✓ Platform data reliability — health badges, reconnect prompts, token_expiry exposed, SCHEDULER_ENABLED guard — v1.0 (Phase 3–4)
- ✓ Dashboard UX polish — thumbnail fallback, score range slider, nullslast sort — v1.0 (Phase 4)
- ✓ BrainSuite image scoring (ScoringEndpointType enum, Static API) — v1.1 (Phase 5)
- ✓ Historical asset backfill — admin endpoint queues all UNSCORED assets cross-tenant — v1.1 (Phase 6)
- ✓ Score trend chart + top/bottom performer highlights — v1.1 (Phase 7)
- ✓ Performance tab tile/card grid redesign — v1.1 (Phase 7)
- ✓ Score-to-ROAS correlation scatter chart — v1.1 (Phase 8)
- ✓ AI metadata auto-fill (Gemini Vision + Whisper, pipeline-integrated) — v1.1 (Phase 9)
- ✓ In-app notifications (bell + polling + toasts) — v1.1 (Phase 10)
- ✓ Per-org BrainSuite config schema + pipeline wiring — v1.2 (Phase 11)
- ✓ Credentials + app name settings UI — v1.2 (Phase 12)
- ✓ Field mapping editor + mandatory field enforcement (FMAP-01–07, PIPE-02–03) — v1.2 (Phase 13)
- ✓ YouTube/DV360 cookie DB storage + SuperAdmin UI + COOKIE_FAILED notifications — v1.2 (Phase 14)
- ✓ TikTok video asset download to MinIO/S3 (TKTOK-01) — v1.3 (Phase 15)
- ✓ TikTok image asset download to MinIO/S3 (TKTOK-02) — v1.3 (Phase 15)
- ✓ PostgreSQL background_jobs persistence layer with autovacuum (JOBS-01, JOBS-02) — v1.3 (Phase 16)
- ✓ Service instrumentation — all 4 job types instrumented with real-time progress (INSTR-01–05) — v1.3 (Phase 17)
- ✓ SSE real-time transport with keepalive + connection lifecycle (SSE-01, SSE-02) — v1.3 (Phase 18)
- ✓ SuperAdmin monitoring UI at /configuration/jobs — 4-tab job table, drill-in panels, error tracebacks (MON-01–07) — v1.3 (Phase 19)
- ✓ Residential proxy (DV360 + Google Ads) with bgutil PO token plugin — cookieless-first retry, credential redaction (PROXY-01, PROXY-03, PROXY-04, PROXY-06) — v1.4 (Phase 20)
- ✓ SuperAdmin proxy config UI — Fernet-encrypted URL, enable/disable toggle (PROXY-05) — v1.4 (Phase 21)
- ✓ Dashboard metadata filter with org-scoped autocomplete, OR/AND composition, chip row (DASH-01) — v1.4 (Phase 22)
- ✓ Dashboard ad account multi-select filter with platform grouping (DASH-02) — v1.4 (Phase 22)
- ✓ Dashboard video duration range slider with async backfill, NULL callout, ffprobe extraction (DASH-03) — v1.4 (Phase 23)

## Current Milestone: v1.5 — Download Performance & Tech Debt

**Goal:** Cut video download wall-clock time 3–5× via parallel + split-proxy architecture, and clear outstanding tech debt before next feature work.

**Target features:**
- Extraction/download split — info extraction runs direct (no proxy); only stream bytes route through residential proxy → saves 7–15s per video
- Configurable parallel downloads — SuperAdmin sets max concurrent downloads; semaphore-guarded; default 3
- PO-first retry order — cookieless+PO → PO+proxy → cookies+proxy
- Proxy config in-memory cache (60s TTL) — no DB decrypt per video
- DV360 sleep reduction — drop 4s inter-download sleep when proxy+session pinning active
- socket_timeout tuning — 10s for proxy calls (down from 30s)
- DEBT-01: Alembic 4-head merge — fix `alembic upgrade head` ambiguity on fresh installs
- PROXY-02: Google Ads live download validation (environment unblocked)

### Active (v1.5)

- PERF-01: Download extraction/stream split — info extraction without proxy, stream download with proxy
- PERF-02: Configurable parallel downloads via SuperAdmin (max_concurrent_downloads, default 3)
- PERF-03: PO-first retry order — cookieless+PO → PO+proxy → cookies+proxy
- PERF-04: Proxy config in-memory cache (60s TTL) — no DB decrypt per video
- PERF-05: DV360 sleep reduction when proxy+session pinning active
- PERF-06: socket_timeout tuned to 10s for proxy calls
- DEBT-01: Alembic 4-head merge — fix `alembic upgrade head` ambiguity on fresh installs
- PROXY-02: Google Ads live download validation

### Deferred

- TikTok live-run UAT confirmation (TKTOK-01/02 — pending live sync)
- SSE Redis pub/sub upgrade at 50+ concurrent SuperAdmins (SSE-03)
- Account-level metadata defaults: connection_metadata_defaults table + account config UI + lookup fallback (META-01, META-02)
- Dashboard filter state URL persistence

### Out of Scope

- Real-time notifications (Slack/email) — in-app only for v1.x; deferred to v1.3 candidate
- Mobile app — web-first
- Audience/targeting asset import — user specified images and video only
- Ad copy / text creative scoring — not in scope
- Creative identity across platforms — deferred to v2
- Replit deployment — replaced by portable Docker Compose
- Per-tenant AI inference daily spend cap — deferred (AI-01)
- SSE/WebSocket real-time notifications — polling sufficient for v1.x event frequency
- Moving GEMINI_API_KEY to DB — platform-wide key, not per-org

## Constraints

- **Deployment**: Docker Compose on any host — fully portable (Redis, MinIO, Postgres, backend, frontend)
- **BrainSuite API**: Video (ACE_SOCIAL) and Static image (ACE_STATIC_SOCIAL_STATIC_API) endpoints confirmed and integrated
- **AI metadata inference**: Gemini 2.5 Flash (Vision) + Whisper (audio transcription) via GEMINI_API_KEY
- **Storage**: Assets in S3-compatible storage — presigned URLs per request
- **Audience**: Production-ready — external users can onboard after v1.2

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Angular 17 + FastAPI stack | Already built — brownfield project | ✓ Good |
| S3-compatible storage (MinIO/boto3) | Replaced Replit GCS sidecar — portable | ✓ Good |
| MinIO pinned to RELEASE.2025-10-15T17-29-55Z | Last official tag before maintenance mode | ✓ Good |
| httpOnly cookie for refresh token | XSS prevention — token never in localStorage | ✓ Good |
| Redis OAuth sessions (replace in-memory dict) | Survives multi-worker restarts | ✓ Good |
| Session-per-operation for BrainSuite scoring | Never hold DB session during HTTP calls | ✓ Good |
| on_conflict_do_nothing for UNSCORED injection | Prevents re-sync resetting completed scores | ✓ Good |
| SCHEDULER_ENABLED env var guard | Multi-worker Autoscale / cloud deployments | ✓ Good |
| ngx-slider pinned to 17.0.2 | Angular 17 compatible | ✓ Good |
| ScoringEndpointType enum at sync time | Never infer endpoint type at scoring time | ✓ Good |
| BackgroundTasks for backfill (not APScheduler) | Avoids competing with live 15-min scorer | ✓ Good |
| TREND-01 deferred (D-09) | BrainSuite scores static — history table has no value | ✓ Good |
| 30-second polling for notifications | Invisible to users at minute-to-hour event frequency; SSE is 10× more work | ✓ Good |
| Gemini 2.5 Flash for AI auto-fill | Cost-effective vision model; GEMINI_API_KEY already in .env | ✓ Good |
| Pipeline-integrated auto-fill (D-04) | Fires on sync, not on user button click — simpler UX, no suggestion staging table | ✓ Good |
| Performer badge minimum guard: 3 assets | Implementation used 3; requirement said 10 — minor tech debt | ⚠️ Revisit |
| Fernet String(1000) for client_secret_encrypted | Enforces max length at DB level; never Text (D-05/T-11-01) | ✓ Good |
| Per-org token dict cache keyed by org_id | No cross-org token sharing possible; T-11-06 mitigation | ✓ Good |
| system_app_name on BrainsuiteApp (not OrgBrainsuiteConfig) | Each app row owns its URL segment — cleaner than per-org duplication | ✓ Good |
| CredentialsResponse has no client_secret field | `has_secret: bool` only — secret never returned to frontend (T-12-04) | ✓ Good |
| COMPLETE-only rescore-all target | Never touch PROCESSING/PENDING rows on re-score trigger (T-12-07) | ✓ Good |
| app_type denormalized on OrgBrainsuiteFieldMapping | Avoids pipeline JOIN; composite index pre-built for Phase 13 queries (D-05) | ✓ Good |
| _check_mandatory_fields session-per-operation | Consistent with all scoring_job.py helpers; T-13-09 mitigation | ✓ Good |
| MANDATORY_FIELD_MISSING via asyncio.create_task | Fire-and-forget — notification failure must not block scoring | ✓ Good |
| SystemConfig singleton_guard String(1) unique | DB-level enforcement of exactly one platform config row (T-14-02) | ✓ Good |
| Text (not String) for YouTube cookie columns | Cookies are multi-KB; String(1000) would overflow | ✓ Good |
| _do_download_with_cookies accepts string not env var | Eliminates os.environ.get inside executor — no accidental cookie logging (T-14-10) | ✓ Good |
| COOKIE_FAILED only when cookies list non-empty | Cookieless download is normal fallback, not an error state (D-12/D-13) | ✓ Good |
| SyncJob preserved alongside BackgroundJob | Backward compatibility — existing sync state machine unchanged; only new job types write to BackgroundJob (v1.3) | ✓ Good |
| SSE transport uses DB polling, not Redis pub/sub | Sufficient at v1.3 scale (1–3 concurrent SuperAdmins); defer Redis pub/sub to v1.4 at 50+ concurrent users (SSE-03) | ✓ Good |
| brainsuite_job_id written to metadata_ (not output) | Ensures References panel displays it alongside sync_job_id; consistent KNOWN_EXTERNAL_ID_KEYS contract (v1.3 gap closure) | ✓ Good |
| asset_url/video_source_url in ON CONFLICT exclusion | Prevents null window during TikTok re-sync — S3-stored URL preserved across upserts (v1.3 gap closure) | ✓ Good |
| scoring_enabled gate on all 4 download functions | SystemConfig.scoring_enabled=false suppresses downloads on all platforms uniformly (v1.3 gap closure) | ✓ Good |
| Three-layer proxy stack (residential IP → cookies → bgutil) | Datacenter IPs blocked at network layer before cookies evaluated; all three required for production YouTube downloads | ✓ Good |
| bgutil sidecar in HTTP server mode (port 4416) | Script mode spawns subprocess per token request — cold-start latency + orphan processes on Cloud Run | ✓ Good |
| proxy= singular kwarg (httpx 0.25.2) | proxies= dict removed in httpx 0.25.x; discovered as BLOCKER-01 in audit, fixed before milestone close | ✓ Good |
| _redact() closure in yt-dlp logger | Proxy credentials in URL format http://user:pass@host stripped from all 4 YDLLogger methods; single regex pass | ✓ Good |
| SQLAlchemy aliased() per metadata_filter entry | AND-composition across fields; OR-within-field via value.in_() bucket grouping — matches DASH-01 D-07/D-08 spec | ✓ Good |
| Two-layer org guard on metadata values endpoint | db.get check + JOIN-level organization_id — prevents UUID enumeration while blocking cross-org leakage (T-22-01) | ✓ Good |
| null_duration_count gated on filter activity | Avoids expensive COUNT(*) subquery on every unfiltered dashboard load (D-07) | ✓ Good |
| has_video_assets flag from duration-bounds | Frontend shows slider only when VIDEO assets exist — filter-aware, not page-scoped; authoritative from backend | ✓ Good |
| memoized groupedAdAccounts getter | Prevents ngFor teardown + mat-menu close on every Angular change detection cycle | ✓ Good |

## Evolution

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-18 — milestone v1.5 started*
