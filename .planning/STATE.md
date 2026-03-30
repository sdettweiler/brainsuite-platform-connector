---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Insights + Intelligence
status: Ready to plan
stopped_at: Completed 06-01-PLAN.md
last_updated: "2026-03-30T07:41:17.388Z"
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 5
  completed_plans: 5
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-25 — v1.1 started)

**Core value:** A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.
**Current focus:** Phase 06 — historical-backfill-score-history-schema

## Current Position

Phase: 7
Plan: Not started

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

### Pending Todos

- Phase 5 gate: BrainSuite Static API discovery spike must be first deliverable — no implementation before confirmed endpoint URL, payload shape, response schema, and rate limit tier. Document in `BRAINSUITE_API.md`.
- Phase 9 gate: Targeted spike on Claude tool-use / structured output schema for metadata inference fields + per-field confidence scoring. Validate cost model against real samples. Confirm `OPENAI_API_KEY` optionality.

### Blockers/Concerns

- BrainSuite Static API endpoint/payload: unconfirmed — mandatory discovery spike gates Phase 5 implementation.
- BrainSuite production credentials: need configuration (PROD-01).
- Google Ads OAuth consent screen: verify "Published" status (PROD-02).
- AI inference field accuracy on real agency creatives: empirical validation needed before enabling for all tenants; set per-tenant daily spend cap in Redis from day one.

## Session Continuity

Last session: 2026-03-30T07:37:53.814Z
Stopped at: Completed 06-01-PLAN.md
Resume: Start Phase 5 with BrainSuite Static API discovery spike, then PROD-01/02 credential verification
