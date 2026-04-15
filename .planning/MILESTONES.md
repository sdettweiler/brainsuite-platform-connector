# Milestones

## v1.1 Insights + Intelligence (Shipped: 2026-04-15)

**Phases completed:** 6 phases, 14 plans, 19 tasks

**Key accomplishments:**

- ScoringEndpointType enum + 8-entry D-11 lookup table, endpoint_type Alembic migration with VIDEO backfill, Static API discovery spike script, and BRAINSUITE_API.md + PRODUCTION_CHECKLIST.md documentation foundation
- BrainSuiteStaticScoreService mirroring the video service for ACE_STATIC_SOCIAL_STATIC_API; harmonizer populates endpoint_type at sync time for IMAGE+VIDEO assets; scoring_job.py branches on endpoint_type to route VIDEO vs. STATIC_IMAGE to their respective services
- Angular dashboard UNSUPPORTED badge (grey dash + tooltip), asset detail CE tab UNSUPPORTED notice, image-only metadata display (Intended Messages / Iconic Color Scheme), and Alembic migration seeding two new MetadataField rows per org
- Angular CE tab now shows a dedicated "Scoring not available" block for UNSUPPORTED assets and an image-metadata section (Intended Messages, Iconic Color Scheme) for IMAGE assets in COMPLETE state, via UUID-key field resolution from /assets/metadata/fields
- Admin-only POST /api/v1/scoring/admin/backfill endpoint queuing all UNSCORED VIDEO/STATIC_IMAGE assets cross-tenant via FastAPI BackgroundTasks with per-asset error isolation
- GET /dashboard/score-trend endpoint and PERCENT_RANK() window function performer tagging with 10-asset minimum guard and ad_account_id in asset detail response
- ECharts aggregate score trend panel above creative grid with date-aware loading, plus performer badge relocated to bottom-left thumbnail overlay with green/red color coding
- Performance tab replaced with tile/card grid: two-column top row (KPI chart + Creative Asset card), color-coded metric group summary, and campaign deep-links to publisher Ads Managers
- Unpaginated GET /dashboard/correlation-data endpoint with zero-ROAS preservation fix, backed by 8 TDD tests covering serialization edge cases
- 1. [Rule 1 - Bug] `platformFilter` reference replaced with `selectedPlatforms`
- AIInferenceTracking model + ai_autofill.py service routing 7 auto_fill_type values via GPT-4o Vision and Whisper with session-per-operation pattern and 24 passing tests
- Task 3: Visual verification of auto-fill UI
- One-liner:
- One-liner:

---

## v1.0 MVP — 2026-03-25

**Shipped:** 2026-03-25
**Phases:** 1–4 | **Plans:** 19

A production-ready multi-tenant platform connector that syncs ad creatives from Meta, TikTok, Google Ads, and DV360, automatically scores them via BrainSuite, and surfaces performance metrics + effectiveness scores in a unified dashboard with sort, filter, and health monitoring.

**Key Accomplishments:**

1. Full Docker Compose portability — application runs anywhere with `docker compose up`, zero Replit dependency
2. Production security hardened — httpOnly cookie auth, Redis OAuth sessions, encrypted tokens, path traversal fix, typed frontend DTOs
3. BrainSuite scoring pipeline — async UNSCORED→PENDING→PROCESSING→COMPLETE state machine with tenacity retry, 15-min batch scheduler, score + dimension breakdown UI
4. Dashboard polish — score range slider (ngx-slider), video thumbnail fallback, nullslast sort, score badge + Creative Effectiveness tab
5. Platform reliability — health badges, reconnect prompts, token_expiry exposure, SCHEDULER_ENABLED guard for multi-worker deployments

**Stats:**

- 4 phases, 19 plans
- 276 files changed, +52,640 / -2,333 lines
- 390 commits over 34 days (2026-02-19 → 2026-03-25)

**Archive:** [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md) | [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md)
