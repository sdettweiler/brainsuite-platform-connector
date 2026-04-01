---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Insights + Intelligence
status: Phase 08 Complete — Ready for Phase 09
stopped_at: "Phase 09 — not yet planned"
last_updated: "2026-04-01T17:25:00.000Z"
last_activity: "2026-04-01 - Quick task 260401-qpu: add metric selector dropdown to scatter chart drawer — 7 metrics: ROAS, CTR, VTR, CPM, CVR, CPC, Conversions"
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 10
  completed_plans: 10
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-25 — v1.1 started)

**Core value:** A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.
**Current focus:** Phase 08 — score-to-roas-correlation

## Current Position

Phase: 08 (score-to-roas-correlation) — EXECUTING
Plan: 1 of 2
Phase: 08 (score-to-roas-correlation) — READY TO PLAN

## Accumulated Context

### Decisions

All v1.0 decisions logged in PROJECT.md Key Decisions table.

**v1.1 architectural decisions (locked at roadmap stage):**

- Notifications transport: polling (`GET /notifications/unread` every 30 seconds) — not SSE or WebSockets. Resolves ARCHITECTURE.md vs. PITFALLS.md conflict in favour of PITFALLS recommendation: 1–2 days of work vs. 1–2 weeks, no user-visible difference at minute-to-hour event frequency.
- Backfill mechanism: admin API endpoint using BackgroundTasks — not a second APScheduler job — to avoid competing with the live 15-minute scorer on the same `UNSCORED` queue.
- AI metadata writes: suggestions-only table (`ai_metadata_suggestions`) — never writes to live metadata columns without explicit user confirmation.
- Score trend deduplication: one row per asset per day in `creative_score_history` (conditional insert); monthly range partitioning from day one; 90-day retention.
- Image scoring routing: explicit `ScoringEndpointType` enum populated at sync time from a `(platform, raw_content_type, file_extension)` lookup table — never inferred at scoring time.
- [Phase 05-brainsuite-image-scoring]: ScoringEndpointType in dedicated module with explicit 8-entry D-11 lookup table and UNSUPPORTED default; endpoint_type Alembic migration backfills existing rows to VIDEO
- [Phase 05]: Static API channel mapping uses substring match ('instagram' in placement) for simplicity; rescore endpoint returns 422 for UNSUPPORTED assets
- [Phase 05]: Used ngSwitch on scoring_status in dashboard tile to add UNSUPPORTED case alongside existing numeric badge
- [Phase 05]: Load metadata field definitions at init so imageMetadataFields getter resolves UUID keys synchronously without extra API calls
- [Phase 06]: TREND-01 deferred: creative_score_history table not created — BrainSuite scores are static per D-09
- [Phase 06]: BackgroundTasks used for backfill (not APScheduler) to avoid competing with 15-min batch on same UNSCORED queue
- [Phase 07-score-trend-performer-highlights-performance-tab]: PERCENT_RANK() replaces fixed-threshold performer tagging — relative ranking adapts to any org's score distribution, 10-asset minimum guard prevents misleading rankings in small orgs
- [Phase 07-score-trend-performer-highlights-performance-tab]: Score trend data_points < 2 threshold for empty-state is frontend concern; backend returns all data points including single-point results
- [Phase 07-score-trend-performer-highlights-performance-tab]: Score trend panel reuses main filter bar date range — no separate DateRangePicker in panel (single source of truth)
- [Phase 07-score-trend-performer-highlights-performance-tab]: Score trend panel reuses dashboard filter bar date range — no separate DateRangePicker added (single source of truth)
- [Phase 07-score-trend-performer-highlights-performance-tab]: getTagClass() returns full class string 'tile-tag tag-top' because [class] binding replaces base class
- [Phase 07-03]: Zero spend shows $0.00; all other null/zero metrics omitted — zero is data-absent noise except for spend
- [Phase 07-03]: getCampaignUrl() uses ad_account_id for Meta/DV360 URL construction; tile styles reuse --bg-card/--border CSS vars for CE tab visual consistency
- [Phase 08]: Fixed-position overlay drawer instead of MatSidenav — avoids height-propagation issues, explicitly allowed by plan
- [Phase quick]: Quick task 260401-qpu: correlationMetrics config array drives all scatter chart dynamic behavior — label, format fn, suffix — single source of truth

### Pending Todos

- Phase 5 gate: BrainSuite Static API discovery spike must be first deliverable — no implementation before confirmed endpoint URL, payload shape, response schema, and rate limit tier. Document in `BRAINSUITE_API.md`.
- Phase 9 gate: Targeted spike on Claude tool-use / structured output schema for metadata inference fields + per-field confidence scoring. Validate cost model against real samples. Confirm `OPENAI_API_KEY` optionality.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260331-l16 | analyze the entire folder structure for legacy/obsolete files. Especially replit leftovers etc. build a clean up plan | 2026-03-31 | a6dc5b6 | [260331-l16-analyze-the-entire-folder-structure-for-](.planning/quick/260331-l16-analyze-the-entire-folder-structure-for-/) |
| 260401-n93 | improve platform sync status display — fix new account showing sync failed, add running sync indicators | 2026-04-01 | 6e34c94 | [260401-n93-improve-platform-sync-status-display-fix](.planning/quick/260401-n93-improve-platform-sync-status-display-fix/) |
| 260401-qpu | Add metric selector dropdown to scatter chart correlation drawer (7 metrics: ROAS, CTR, VTR, CPM, CVR, CPC, Conversions) | 2026-04-01 | 33cceed | [260401-qpu-add-metric-selector-dropdown-to-scatter-](.planning/quick/260401-qpu-add-metric-selector-dropdown-to-scatter-/) |

### Blockers/Concerns

- BrainSuite Static API endpoint/payload: unconfirmed — mandatory discovery spike gates Phase 5 implementation.
- BrainSuite production credentials: need configuration (PROD-01).
- Google Ads OAuth consent screen: verify "Published" status (PROD-02).
- AI inference field accuracy on real agency creatives: empirical validation needed before enabling for all tenants; set per-tenant daily spend cap in Redis from day one.

## Session Continuity

Last activity: 2026-04-01 - Completed quick task 260401-qpu: add metric selector dropdown to scatter chart drawer — 7 metrics: ROAS, CTR, VTR, CPM, CVR, CPC, Conversions
Last session: 2026-04-01T17:25:00.000Z
Stopped at: Phase 08 complete — advancing to Phase 09 (AI Metadata Auto-Fill)
Resume: Discuss or plan Phase 09
