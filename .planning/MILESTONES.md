# Milestones

## v1.4 — YouTube Downloads & Dashboard Filters
**Shipped:** 2026-05-18
**Phases:** 20–23 (4 phases, 9 plans)
**Stats:** 100 files changed, +18,394 / −573 lines, 4 days (2026-05-15 → 2026-05-18)
**Known deferred items at close:** 1 acknowledged gap (PROXY-02 — Google Ads live validation env-blocked)

### Delivered

- Residential proxy (IPRoyal/DataImpulse) injected into DV360 and Google Ads yt-dlp download paths — credential redaction, sticky session IDs, cookieless-first retry, bgutil PO token plugin auto-invoked (Phase 20)
- SuperAdmin proxy config UI — Fernet-encrypted URL storage, enable/disable toggle, masked display, httpx reachability test (Phase 21)
- Dashboard metadata filter — org-scoped autocomplete, OR-within-field / AND-across-fields composition, chip row with remove + Clear all (Phase 22)
- Ad account multi-select filter — platform-grouped (Meta → TikTok → Google Ads → DV360) with search input (Phase 22)
- Video duration range slider — dual-handle, async backfill at all 8 sync sites, NULL callout, ffprobe extraction for all 4 platforms (Phase 23)

### Known Gaps

- PROXY-02: Google Ads live download validation blocked by pre-existing environment issues (MCC manager accounts + expired cookie flag). Code path is identical to DV360 (which validated). Not a code deficiency.

**Archive:** [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) | [v1.4-REQUIREMENTS.md](milestones/v1.4-REQUIREMENTS.md) | [v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md)

---

## v1.3 — SuperAdmin Monitoring & TikTok Downloads
**Shipped:** 2026-05-13
**Phases:** 15–19.3 (8 phases, 23 plans)
**Known deferred items at close:** 6 (see STATE.md Deferred Items)

### Delivered

- TikTok video and image asset download pipeline (MinIO/S3) — unblocks AI autofill + scoring for TikTok creatives
- PostgreSQL `background_jobs` table with autovacuum tuning and 30-day cleanup job
- Full service instrumentation across all 4 job types (sync, download, autofill, scoring) with Redis pub/sub
- SSE real-time transport — FastAPI streaming endpoint with 30s keepalive heartbeat and connection lifecycle management
- SuperAdmin monitoring UI at /configuration/jobs — 4-tab job table, real-time progress bars, drill-in detail panels (full Gemini output, download manifests, error tracebacks, per-asset scores)
- Gap closures: null-token SSE race fix, brainsuite_job_id moved to metadata_ (References panel), asset_url upsert exclusion + scoring_enabled gate on all download functions

**Archive:** [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md)

---

## v1.2 BrainSuite Configuration (Shipped: 2026-04-28)

**Phases completed:** 4 phases, 13 plans
**Stats:** 123 files changed, +21,744 / -504 lines, 13 days (2026-04-15 → 2026-04-28)

**Key accomplishments:**

1. Per-org BrainSuite credential schema (`org_brainsuite_config` + `org_brainsuite_field_mappings` tables) with Fernet-encrypted `String(1000)` secret and per-org token dict caching — scoring pipeline eliminated all hardcoded `.env` credential reads (Phase 11)
2. Brand values metadata fields (`brainsuite_brand_values` + `_language`, 31 language options) seeded for all existing orgs via Alembic + provisioned on new-org registration (Phase 11)
3. BrainSuite credentials + app name Settings UI — masked secret input, live "Test Connection" auth check, per-app `system_app_name` accordion, re-score dialog on config change (Phase 12)
4. Per-app field mapping editor (750-line `FieldMappingsPanelComponent`) with 12 video / 8 static standard fields, custom field CRUD, mandatory toggles, and D-06 auto-match on first open (Phase 13)
5. FMAP-07 pipeline guard: `_check_mandatory_fields` blocks scoring for assets with missing mandatory field values; fires `MANDATORY_FIELD_MISSING` notification via `asyncio.create_task` (Phase 13)
6. `SystemConfig` singleton table with Fernet-encrypted YouTube cookie slots, SuperAdmin JWT claim + `get_current_superadmin` FastAPI dependency, `/configuration/admin` UI, and `dv360_sync.py` reading cookies from DB with env var fallback + `COOKIE_FAILED` notification broadcast (Phase 14)

**Archive:** [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) | [v1.2-REQUIREMENTS.md](milestones/v1.2-REQUIREMENTS.md)

---

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
