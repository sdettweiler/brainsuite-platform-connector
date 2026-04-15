# BrainSuite Platform Connector

## What This Is

A production-ready multi-tenant SaaS platform that connects Meta, TikTok, Google Ads, and DV360 ad accounts, syncs creative assets and performance metrics into a unified dashboard, automatically scores every imported creative for effectiveness via the BrainSuite API, and surfaces AI-powered metadata inference, score-to-ROAS correlation, and in-app notifications. Agencies use it to immediately identify which creatives to scale or kill based on objective effectiveness scores alongside ROAS, CTR, and spend.

## Core Value

A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.

## Current State

**Version:** v1.1 (shipped 2026-04-15)

**Stack:** Angular 17 + FastAPI + PostgreSQL + Redis + MinIO — fully containerized via Docker Compose
**Deployment:** Any cloud host or local dev via `docker-compose up`
**LOC:** ~52,000 lines (v1.0) + ~23,842 net additions across 329 files in v1.1

**What works:**
- Multi-tenant organization with RBAC
- OAuth connection + background sync for Meta, TikTok, Google Ads, DV360
- Creative asset storage via S3-compatible storage (MinIO local / S3 production)
- Automatic BrainSuite scoring pipeline (15-min scheduler) — video AND image creatives
- Image scoring via BrainSuite Static API with `ScoringEndpointType` lookup; UNSUPPORTED badge for non-Meta platforms
- Admin backfill endpoint to score all pre-v1.1 unscored assets
- Score trend chart (GET /dashboard/score-trend); top/bottom performer badges via PERCENT_RANK
- Performance tab redesigned as tile/card grid; score-to-ROAS scatter chart with Stars/Q-Marks/Workhorses/Laggards quadrants
- Gemini 2.5 Flash Vision + Whisper auto-fill on every new asset sync; per-field toggle on metadata config page; inference status badge in asset detail
- In-app notifications: bell icon + unread badge + MatMenu inbox + 30s polling + MatSnackBar toasts for SYNC_FAILED and TOKEN_EXPIRED

**Known tech debt (v1.1):**
- Performer badge minimum guard is 3 assets (requirement: 10) — minor threshold mismatch
- Score trend shows single data point per asset (no append-only history table — intentional per D-09)
- Phases 7, 8, 10 missing formal VERIFICATION.md files
- `get_asset_detail()` hardcoded None for score fields (unused by frontend; confusing for API consumers)

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

### Active

*(v1.2 requirements — to be defined via /gsd-new-milestone)*

### Out of Scope

- Real-time notifications (Slack/email) — in-app only for v1.1; v1.2 candidate
- Mobile app — web-first
- Audience/targeting asset import — user specified images and video only
- Ad copy / text creative scoring — not in scope
- Creative identity across platforms — deferred to v2
- Replit deployment — replaced by portable Docker Compose
- Per-tenant AI inference daily spend cap — deferred to v1.2 (AI-v2-01)
- SSE/WebSocket real-time notifications — polling sufficient for v1.1 event frequency

## Constraints

- **Deployment**: Docker Compose on any host — fully portable (Redis, MinIO, Postgres, backend, frontend)
- **BrainSuite API**: Video (ACE_SOCIAL) and Static image (ACE_STATIC_SOCIAL_STATIC_API) endpoints confirmed and integrated
- **AI metadata inference**: Gemini 2.5 Flash (Vision) + Whisper (audio transcription) via GEMINI_API_KEY
- **Storage**: Assets in S3-compatible storage — presigned URLs per request
- **Audience**: Production-ready — external users can onboard after v1.1

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
*Last updated: 2026-04-15 after v1.1 milestone*
