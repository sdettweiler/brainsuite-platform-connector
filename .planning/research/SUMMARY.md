# Project Research Summary

**Project:** BrainSuite Platform Connector — v1.1 Insights + Intelligence
**Domain:** Creative analytics dashboard for performance marketing agencies
**Researched:** 2026-03-25
**Confidence:** HIGH

## Executive Summary

The v1.1 milestone adds seven capabilities to a working v1.0 product: BrainSuite image scoring, AI metadata auto-fill, score-to-ROAS correlation view, top/bottom performer highlights, score trend over time, in-app notifications, and historical backfill scoring. The existing stack (FastAPI, SQLAlchemy 2.0, APScheduler, Redis, Angular 17, NgRx, ECharts 5.6) handles all of these without any new frontend packages. The only net-new backend dependencies are `anthropic >=0.86.0` (Claude vision for metadata inference) and `openai >=2.29.0` (Whisper for audio transcription and voice-over detection). Every other feature extends code and patterns that are already working and well-understood.

The recommended build order treats image scoring as the critical prerequisite. Image scoring unlocks historical backfill for both asset types, which fills the data needed to make the analytics views (correlation chart, trend, highlights) meaningful on day one. AI metadata auto-fill is independent and can be built in parallel. In-app notifications are also independent; the PITFALLS research is unambiguous that polling (30-second interval) is the correct scope for v1.1 — not SSE or WebSockets. The ARCHITECTURE research nonetheless chose Redis pub/sub → SSE. This is the single area where the two research files are in direct tension and the conflict must be resolved before implementation begins. The polling approach is recommended.

The three highest-risk areas are: (1) AI inference cost blowout if re-triggering is not guarded with an `ai_inference_status` state machine (up to ~$384/day/tenant if unguarded), (2) image vs. video scoring routed to the wrong BrainSuite endpoint due to unreliable `content_type` values from ad platform APIs, and (3) a score history table that grows without bound if deduplication and partitioning are not built in from day one. All three risks are well-documented with clear prevention patterns. The BrainSuite Static API endpoint and payload for image scoring remain explicitly unconfirmed — a discovery spike must be the first deliverable of the image scoring phase before any implementation begins.

---

## Key Findings

### Recommended Stack Additions

The existing stack requires only two new backend Python packages. No new frontend packages are needed — Angular Material, ECharts 5.6, and NgRx already cover all new UI requirements.

**Net-new dependencies:**

| Layer | Package | Version | Purpose |
|-------|---------|---------|---------|
| Backend | `anthropic` | `>=0.86.0` | Claude vision API for AI metadata inference — use `claude-haiku-4-5-20251001` as primary model; escalate to Sonnet only if output quality is insufficient for a specific field |
| Backend | `openai` | `>=2.29.0` | Whisper API (`whisper-1`) for audio transcription and voice-over language detection — avoids GPU/model-size dependency that local Whisper would require |

**New environment variables required:**
- `ANTHROPIC_API_KEY` — add to `.env` and pydantic `Settings`
- `OPENAI_API_KEY` — add to `.env` and pydantic `Settings`

**Existing stack components used by v1.1 (no changes needed):**
- `AsyncAnthropic` client — non-blocking; sync `Anthropic()` client must not be used in async contexts
- ECharts `ScatterChart` and `LineChart` — register alongside existing chart types in `app.config.ts`; do not switch to the full `import 'echarts'` bundle (adds ~1 MB to Angular bundle)
- `MatSnackBar`, `MatBadge`, `MatMenu` — all ship with `@angular/material 17` already installed; do not add `ngx-toastr`

**Image passing pattern — base64 required for MinIO assets.** MinIO presigned URLs are only valid inside the Docker network. Claude's API cannot reach a local MinIO instance. Fetch bytes server-side, encode to base64, pass inline. Approximate cost: ~1,600 tokens at 1 megapixel = ~$0.0016 per image at Haiku pricing.

See `/STACK.md` for implementation patterns including base64 image encoding, Whisper transcription, ECharts scatter and line option structures, and the Angular Material bell notification pattern.

---

### Expected Features

**Must have — Table Stakes (v1.1):**
- **BrainSuite image scoring** — images are a primary ad format; video-only scoring is a conspicuous gap agencies ask about immediately; parity requirement
- **Top/bottom performer highlights** — every comparable creative analytics tool (Triple Whale, Motion, Superads, Segwise) provides this; users scan grids, not tables
- **Score-to-ROAS correlation view** — without this, the BrainSuite score is a black box; agencies need to validate that score predicts performance to maintain buy-in
- **In-app notifications for sync/scoring events** — async workflows require status feedback; expected in any SaaS tool with background jobs
- **Historical backfill scoring** — assets synced before Phase 3 have no scores; without backfill the correlation and trend views are underpowered and confusing on first use

**Should have — Differentiators:**
- **AI metadata auto-fill** — eliminates manual entry of 7 BrainSuite fields per creative; agencies managing hundreds of assets find this friction a direct barrier to scoring adoption
- **Score trend over time** — creative fatigue signal; VidMob and Segwise offer this; the 15-minute scheduler already generates the data

**Defer to v2+:**
- Real-time WebSocket score updates — 30-second polling is invisible to users at this event frequency
- AI metadata fully replacing human input — hallucinated brand names or language codes silently corrupt BrainSuite submissions; suggestions with user confirmation is the correct pattern
- Email/Slack notifications — design the notifications data model now to extend to external channels in v1.2 without schema migration
- Per-platform ROAS correlation breakdown — insufficient data per platform in early tenants
- Automated creative retirement based on score — too prescriptive; surface data, let users act

**AI inference field accuracy by type:**

| Field | Accuracy | Auto-apply? |
|-------|----------|-------------|
| Voice Over (yes/no) | ~95% | Yes — high confidence |
| Voice Over Language | ~90% major languages | With confidence indicator |
| Language/Market | ~90% when legible text present | With confidence indicator |
| Asset Name | ~85% (filename normalization) | Yes |
| Brand Names | Variable — hallucination risk on niche brands | Suggestion with review required |
| Asset Stage | Loose visual correlation only | Suggestion with review required |
| Project Name | Not inferable from creative content | Manual entry required |

**UX requirement:** Never auto-submit AI-filled fields to BrainSuite without user confirmation. Use a two-phase interaction: inference runs async on modal open → pre-populated form shown with per-field confidence indicators → user reviews and explicitly submits.

See `/FEATURES.md` for full feature deep-dives including scatter plot edge cases, notification event table, trend data density analysis, and wave sequencing.

---

### Architecture Approach

The v1.1 features integrate into the existing codebase primarily through extension of `scoring_job.py`, `brainsuite_score.py`, and `asset-detail-dialog.component.ts`, plus three new database tables and one new NgRx slice. No new Docker services are required.

**Key architectural decisions:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Image vs. video scoring routing | Same APScheduler job, branch inside `run_scoring_batch()` on `asset_format` | A second APScheduler job duplicates the PENDING-lock machinery and competes for the same BrainSuite rate limit window |
| AI inference trigger | FastAPI `BackgroundTasks` on-demand — `POST /assets/{id}/ai-suggest` returns 202; client polls GET | User-initiated, latency-sensitive but not synchronous; APScheduler is wrong trigger model for per-user ad-hoc actions |
| Score trend storage | New append-only `creative_score_history` table | The `uq_score_per_asset` unique constraint and `on_conflict_do_nothing` injection pattern on `creative_score_results` must be preserved; history is a separate append concern |
| Notifications transport | **CONFLICT — see Research Flags.** ARCHITECTURE.md: Redis pub/sub → SSE. PITFALLS.md: polling only. | Resolve before Phase 7 implementation |
| Backfill job design | Admin-only `POST /admin/backfill-scoring` endpoint using BackgroundTasks | Avoids `SCHEDULER_ENABLED=false` multi-worker problem; PENDING state machine is the natural mutex against the live scorer |

**New database tables (3):**

| Table | Purpose | Critical design constraint |
|-------|---------|---------------------------|
| `creative_score_history` | Append-only score time series | One row per asset per day (not per scheduler tick); monthly range partitioning on `scored_at`; 90-day retention; index `(creative_asset_id, scored_at DESC)` |
| `ai_metadata_suggestions` | AI inference result persistence | Status machine PENDING/COMPLETE/FAILED; one row per asset (UNIQUE); never writes to live metadata columns |
| `notifications` | Per-org notification inbox | `(id, org_id, type, payload JSONB, read, created_at)`; index `(organization_id, read, created_at)` |

**Modified backend components:**
- `scoring_job.py` — remove `asset_format == "VIDEO"` filter; add IMAGE branch; append to `creative_score_history`; publish notification events
- `brainsuite_score.py` — add `submit_image_job_with_upload()` and `_announce_image_job()`; extend `build_scoring_payload()` for static assets
- `app/core/config.py` — add `ANTHROPIC_API_KEY`, `AI_MODEL`, `OPENAI_API_KEY`
- `dashboard.py` — add `GET /dashboard/score-roas` endpoint; confirm `performer_tag` in response schema

**Modified frontend components:**
- `asset-detail-dialog.component.ts` — AI auto-fill button + loading state; Score Trend tab with ECharts line chart
- `dashboard.component.ts` — performer overlay badges; score-ROAS scatter panel
- `app.state.ts` — add `notifications: NotificationsState`
- `header.component.ts` — mount bell icon component

See `/ARCHITECTURE.md` for full component boundary tables, data model DDL, and the A–G build order.

---

### Critical Pitfalls

**Critical severity — architecture decisions must be made before writing code:**

1. **AI inference cost blowout on re-trigger (Pitfall 1)** — without an `ai_inference_status` state machine, inference fires on every scheduler tick for every asset. At 1,000 assets and 96 APScheduler ticks/day using Claude Haiku pricing: ~$384/day per tenant. Prevention: add `ai_inference_status` (`PENDING | COMPLETE | FAILED`) to asset records with the same `on_conflict_do_nothing` guard pattern used by scoring. Never co-locate inference inside the scoring loop.

2. **Image vs. video routing to wrong BrainSuite endpoint (Pitfall 2)** — `content_type` from ad platform APIs is unreliable across Meta, TikTok, Google Ads, and DV360 (e.g., video thumbnails arrive as `image/jpeg`). Implicit `if "video" in content_type` string matching silently FAIL-marks assets. Prevention: define an explicit `ScoringEndpointType` enum (`VIDEO | STATIC_IMAGE`); populate it at sync time using a tested `(platform, raw_content_type, file_extension)` lookup table; add test fixtures for each platform/type combination.

3. **Backfill job competing with live 15-minute scorer (Pitfall 3)** — if implemented as a second APScheduler job, both pick up the same `WHERE score_status = 'UNSCORED'` queue simultaneously, producing duplicate BrainSuite API calls. Prevention: implement as an admin API endpoint using BackgroundTasks, not APScheduler. The existing PENDING state machine provides the natural claim lock.

**High severity — must be designed before implementation:**

4. **Score trend table unbounded growth (Pitfall 6)** — one row per scoring run × 96 ticks/day × 500 assets × 10 tenants = 175M rows/year. Prevention: insert one row per asset per day only (conditional insert where score AND date match); PostgreSQL monthly range partitioning on `scored_at` from day one; 90-day retention. Note: partitioned tables cannot be created with `CREATE TABLE LIKE` in Alembic — write as raw DDL.

5. **AI inference payload size exceeding 32 MB Claude API limit (Pitfall 4)** — ad creatives are often 5–20 MB; base64 multiplies size by 1.37x. Prevention: HEAD request for `Content-Length` before fetching; downsample to 1568px max on long edge if file exceeds 4 MB (Anthropic's own recommendation for time-to-first-token optimization); use Claude Files API for assets analyzed more than once.

6. **Low-confidence inference overwriting user-entered metadata (Pitfall 5)** — the fastest implementation path writes inference directly to live metadata columns, silently corrupting carefully entered values. Prevention: store all AI results in `ai_metadata_suggestions` only; only suggest for fields that are currently empty; require explicit user confirmation for every field application.

7. **ROAS correlation chart skewed by zero and outlier data (Pitfall 7)** — zero ROAS (no conversions), null ROAS (platform not reporting revenue), and low-spend outliers (3 conversions on $0.50 spend = 600x ROAS) each corrupt the scatter in different ways. Prevention: return `total_spend` alongside ROAS in the query; apply a configurable minimum spend threshold (default $10); treat null and zero ROAS explicitly and distinctly in both query and UI; cap Y-axis at 99th percentile with a log-scale toggle.

8. **Notification system over-engineering (Pitfall 8)** — see Research Flags. The polling approach is 1–2 days of work; Redis pub/sub + SSE infrastructure is 1–2 weeks.

See `/PITFALLS.md` for the full 14-pitfall catalog including top/bottom highlights using absolute vs. relative rank (Pitfall 11), AI prompt returning unstructured text (Pitfall 12), presigned URL expiry for inference (Pitfall 13), and score trend flat-line UX (Pitfall 14).

---

## Implications for Roadmap

The FEATURES.md and ARCHITECTURE.md research both independently converge on the same dependency-driven build order. The suggested phase structure follows the A–G ordering from ARCHITECTURE.md, mapped to user-facing deliverables.

### Phase 1: BrainSuite Image Scoring

**Rationale:** Hard prerequisite for backfill, AI metadata auto-fill, and all analytics views. Without image scoring, the scored asset pool is limited to video assets only, making the analytics views underpowered. Must begin with a BrainSuite Static API discovery spike — no implementation before the spike confirms endpoint/payload/response shape.

**Delivers:** Image assets scored alongside video assets in the existing 15-minute scheduler; explicit `ScoringEndpointType` routing table for all asset types.

**Addresses:** Image scoring (table stakes); routing table that unlocks all subsequent image-aware features.

**Avoids:** Pitfall 2 (wrong endpoint routing) by making the routing lookup table the first deliverable of this phase; Pitfall 9 (API discovery skipped) by gating all implementation on a confirmed test call.

**Research flag: MANDATORY SPIKE.** BrainSuite Static API endpoint URL, required payload fields, response schema, and rate limit tier are unconfirmed. One authenticated test call with a real image asset must be the first deliverable. Document confirmed details in `BRAINSUITE_API.md` before writing any implementation code.

---

### Phase 2: Historical Backfill Scoring

**Rationale:** Depends on Phase 1 so that backfill covers both IMAGE and VIDEO assets. Must run immediately after deployment so that analytics views in Phases 3–5 have sufficient data on first use. The correlation view is explicitly described as showing an empty state without backfill data.

**Delivers:** Admin endpoint `POST /admin/backfill-scoring`; all pre-v1.1 assets scored; `creative_score_history` seeded with initial score entries from existing `creative_score_results` data.

**Addresses:** Historical backfill (table stakes); critical path dependency for the correlation view being useful on day one.

**Avoids:** Pitfall 3 (backfill competing with live scorer) by using BackgroundTasks + admin endpoint, not APScheduler; Pitfall 10 (DB session held during BrainSuite HTTP calls) by copying the session-per-operation pattern from the live scorer verbatim.

**Research flag:** Standard patterns. No research phase needed.

---

### Phase 3: Score Trend Over Time

**Rationale:** Schema decision for `creative_score_history` must be made before any scoring data is written, since retroactive fixes require migration and data reconstruction. Schema and migration work can begin in parallel with Phase 1; endpoint and UI follow Phase 1 completion.

**Delivers:** `creative_score_history` table with monthly partitioning + 90-day retention; `GET /assets/{id}/score-history` endpoint; Score Trend tab in asset detail dialog with ECharts line chart.

**Addresses:** Score trend over time (differentiator).

**Avoids:** Pitfall 6 (unbounded table growth) with one-row-per-day conditional inserts and range partitioning; Pitfall 14 (flat-line UX) by scoping the chart with appropriate empty-state handling (single data point must not render as a line).

**Research flag:** Alembic gotcha — partitioned tables cannot use `CREATE TABLE LIKE`; must write raw DDL. Otherwise standard patterns; no research phase needed.

---

### Phase 4: Top/Bottom Performer Highlights

**Rationale:** Lowest-complexity v1.1 deliverable. `_get_performer_tag()` already exists in `dashboard.py`. Once Phase 1 expands the scored asset pool, the function has enough data to produce meaningful results. This is primarily a frontend CSS/badge overlay change.

**Delivers:** Performer badge/ribbon overlays on dashboard grid cards; relative ranking using `PERCENT_RANK()` window function.

**Addresses:** Top/bottom performer highlights (table stakes).

**Avoids:** Pitfall 11 (absolute threshold produces empty or meaningless sections) by switching from absolute score thresholds to `PERCENT_RANK()` / `NTILE(10)` with a minimum 10-asset sample guard.

**Research flag:** No research phase needed — standard frontend pattern.

---

### Phase 5: Score-to-ROAS Correlation View

**Rationale:** Most compelling analytics feature but depends on having enough data (10+ assets with both score and ROAS populated). Best built after Phases 1–2 have expanded the scored asset pool. No schema changes needed — data already exists in `creative_score_results` and `harmonized_performance`.

**Delivers:** `GET /dashboard/score-roas` endpoint; ECharts scatter panel in dashboard with quadrant reference lines (Stars / Question Marks / Workhorses / Laggards); hover tooltips with thumbnail, score, ROAS, spend, platform.

**Addresses:** Score-to-ROAS correlation (table stakes for agency buy-in).

**Avoids:** Pitfall 7 (zero/null ROAS corruption) by returning `total_spend` in the query, applying a configurable minimum spend threshold ($10 default), treating null vs. zero ROAS distinctly, and capping Y-axis at 99th percentile.

**Research flag:** No research phase needed. Scatter plot with quadrant lines is established by industry consensus across Segwise, VidMob, Madgicx.

---

### Phase 6: AI Metadata Auto-Fill

**Rationale:** Independent of Phases 1–5 at the implementation level and can be built in parallel starting after Phase 1 confirms the MinIO asset fetch pattern. However, the cost-guard architecture (Pitfall 1) must be designed first, before any inference code is written. This is the highest-risk feature and the only one requiring the two new API keys.

**Delivers:** `ai_metadata_suggestions` table + migration; `ai_metadata.py` inference service using `AsyncAnthropic` (vision) and `AsyncOpenAI` (Whisper); `POST /assets/{id}/ai-suggest` + polling GET; Auto-fill button in asset detail dialog with per-field confidence indicators; Pydantic model validation on Claude structured output.

**Addresses:** AI metadata auto-fill (differentiator — reduces scoring adoption friction).

**Avoids:** Pitfall 1 (cost blowout) with `ai_inference_status` state machine; Pitfall 4 (payload size) with pre-encoding downsampling to 1568px max; Pitfall 5 (overwriting user data) with suggestions-only table; Pitfall 12 (unstructured response) with Claude tool use / structured output + Pydantic validation; Pitfall 13 (presigned URL expiry) with fetch-then-base64 pattern.

**Research flag:** Recommended targeted spike on Claude tool-use / structured output schema for the exact metadata field definitions and confidence scoring. Validate cost model against real image samples before enabling for all tenants. Confirm whether `OPENAI_API_KEY` should be optional in config (image-only agencies never call Whisper).

---

### Phase 7: In-App Notifications

**Rationale:** Infrastructure (table, API endpoints, NgRx slice, bell component) can be scaffolded at any point during the milestone; event wiring into `scoring_job.py` and `scheduler.py` is the last step after the scoring pipeline is stable. Must resolve the polling vs. SSE conflict before any implementation begins.

**Delivers:** `notifications` table + migration; notification API (list, mark-read, poll or stream endpoint per architecture decision); NgRx notifications slice; bell icon component in header with unread badge; toast integration via `MatSnackBar`.

**Addresses:** In-app notifications (table stakes).

**Avoids:** Pitfall 8 (over-engineering) — architecture must be locked at polling for v1.1.

**Research flag:** Architecture conflict must be resolved. See below.

---

### Phase Ordering Rationale

- Phases 1 → 2 are hard sequential dependencies: image scoring before backfill (so backfill covers both types); backfill before analytics views (so views have data on first use).
- Phases 3, 4, 5 are independent of each other once Phase 1 is complete and can be parallelized if capacity allows.
- Phase 6 (AI metadata) is independent of all others but requires cost-guard design first; can be built in parallel with Phases 2–5.
- Phase 7 (notifications) infrastructure can be scaffolded early; event wiring is the last step in the milestone.

**Critical path for correlation view being useful on day one:**
1. BrainSuite image scoring (Phase 1) — expands scored asset pool
2. Historical backfill (Phase 2) — run immediately after deployment
3. Score-to-ROAS correlation view (Phase 5) — arrives with data already in it

---

### Research Flags

**Needs research before implementation:**

- **Phase 1 (image scoring) — MANDATORY GATE:** BrainSuite Static API endpoint URL, payload shape, response schema, and rate limit tier are unconfirmed. A single authenticated test call with a real image asset must be the first deliverable of this phase. No implementation code before the spike. Document findings in `BRAINSUITE_API.md`.

- **Phase 6 (AI metadata) — RECOMMENDED:** Targeted spike on Claude tool-use schema for structured metadata output with per-field confidence scoring. Validate cost model against real samples. Confirm `OPENAI_API_KEY` optionality requirement.

**Architecture conflict requiring resolution before Phase 7:**

ARCHITECTURE.md chose Redis pub/sub → SSE for notifications. PITFALLS.md explicitly warns that any infrastructure beyond polling is over-engineering for in-app-only notifications at this usage scale (one active user per org at a time; minute-to-hour event granularity).

**Recommendation: Use polling for v1.1.** The polling approach (`GET /notifications/unread` every 30 seconds) is 1–2 days of work. Redis pub/sub + SSE adds persistent connections per browser tab, Redis channel management, and proxy/Docker network reconnect logic — 1–2 weeks of work for no user-visible benefit at this event frequency. The notifications data model extends to SSE or email/Slack in v1.2 without schema changes.

**Phases with well-established patterns (no research phase needed):**
- Phase 2 (backfill) — copy session-per-operation pattern from live scorer verbatim
- Phase 3 (score trend) — standard PostgreSQL append-only history table; Alembic DDL gotcha is documented
- Phase 4 (highlights) — purely frontend; `PERCENT_RANK()` is standard SQL
- Phase 5 (correlation) — scatter chart with quadrant lines; established industry pattern

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack additions | HIGH | Both new packages verified against official PyPI and API docs on 2026-03-25; versions confirmed; integration patterns verified against official Anthropic and OpenAI API references |
| Features (scope and classification) | MEDIUM–HIGH | Table stakes/differentiator classification supported by competitor analysis (Motion, Superads, Segwise, Triple Whale). AI inference accuracy estimates based on known VLM capabilities, not BrainSuite-specific testing — empirical validation required |
| Architecture (integration patterns) | HIGH | Based on direct codebase inspection of production code; all patterns extend known-working implementations; three key design invariants explicitly identified and preserved |
| Pitfalls | HIGH | Cost formulas from official Anthropic pricing docs; database patterns from PostgreSQL official docs; session-leak patterns from FastAPI SQLAlchemy production issue reports; routing pitfall grounded in observed ad platform API inconsistencies |

**Overall confidence:** HIGH for implementation decisions. One hard unknown: BrainSuite Static API endpoint/payload (Phase 1 spike required). One process decision: polling vs. SSE for notifications (must be locked before Phase 7).

### Gaps to Address

| Gap | How to Handle |
|-----|--------------|
| BrainSuite Static API endpoint/payload | Mandatory spike as Phase 1 gate — confirm endpoint URL, required fields, response schema, rate limit; document in `BRAINSUITE_API.md` |
| Polling vs. SSE for in-app notifications | Architectural decision must be locked before Phase 7 begins; recommendation is polling per PITFALLS.md reasoning |
| AI inference field accuracy on real agency creatives | Validate cost model and output quality against real image samples before enabling for all tenants; set per-tenant daily spend cap in Redis from day one |
| BrainSuite score determinism for trend charts | If BrainSuite returns identical scores for unchanged assets (likely), the trend chart is only meaningful after creative edits — validate this assumption with test submissions and scope trend tab UX accordingly (Pitfall 14) |
| `OPENAI_API_KEY` optionality | If an agency's inventory is images-only, the Whisper path is never called; confirm whether `OPENAI_API_KEY` should be optional in `Settings` or always required at startup |

---

## Sources

### Primary (HIGH confidence)
- Anthropic Models Overview — model IDs, pricing, context windows — verified 2026-03-25
- Anthropic Vision API Docs — image format constraints, token formula, 32 MB request limit, downsampling recommendation — verified 2026-03-25
- `anthropic` PyPI v0.86.0 — version confirmed 2026-03-25
- OpenAI Transcriptions API Reference — `whisper-1`, `verbose_json` response format, language field
- `openai` PyPI v2.29.0 — version confirmed 2026-03-25
- Direct codebase inspection: `scoring_job.py`, `brainsuite_score.py`, `scoring.py`, `dashboard.py`, `redis.py`, `config.py`, `app.state.ts`, `asset-detail-dialog.component.ts`, `alembic/versions/e1f2g3h4i5j6_add_creative_score_results.py`
- PostgreSQL range partitioning docs — partition drop behavior vs. DELETE
- APScheduler 3.x docs — `SCHEDULER_ENABLED` multi-worker behavior
- Angular Material 17 API — `MatSnackBar`, `MatBadge`, `MatMenu` verified as shipped with `@angular/material 17.3`

### Secondary (MEDIUM confidence)
- Improvado creative analytics guide — scatter plot as standard correlation chart type
- Segwise, VidMob, Madgicx — competitor feature analysis for table stakes classification and quadrant framing
- Supermetrics, Triple Whale, Madgicx — 7/30-day trend windows as industry standard for creative fatigue
- LogRocket SSE vs. WebSockets comparison — polling rationale for in-app-only notifications
- FastAPI SQLAlchemy session leak in background jobs — session-per-operation pattern rationale

### Tertiary (needs empirical validation)
- AI inference accuracy estimates (Voice Over ~95%, Language ~90%, Brand Names variable) — based on published VLM capability benchmarks, not BrainSuite-specific testing
- AI inference latency estimate (5–10 seconds per asset) — based on Claude API performance benchmarks; actual latency depends on asset dimensions, API load, and audio extraction approach
- ROAS correlation minimum threshold (10+ assets for visible pattern, 30+ for statistical signal) — industry rule of thumb, not statistically derived

---
*Research completed: 2026-03-25*
*Milestone: v1.1 Insights + Intelligence*
*Supersedes v1.0 SUMMARY.md (2026-03-20)*
*Ready for roadmap: yes — with BrainSuite Static API spike gating Phase 1, and polling/SSE decision locking Phase 7*
