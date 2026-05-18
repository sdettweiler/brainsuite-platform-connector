---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: YouTube Downloads & Dashboard Filters
status: executing
stopped_at: Phase 23 UI-SPEC approved
last_updated: "2026-05-18T10:48:56.740Z"
last_activity: 2026-05-18
progress:
  total_phases: 13
  completed_phases: 11
  total_plans: 32
  completed_plans: 33
  percent: 85
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-14 — v1.4 milestone started)

**Core value:** A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.
**Current focus:** Phase 23 — dashboard-duration-filter-backfill

## Current Position

Phase: 23 (dashboard-duration-filter-backfill) — EXECUTING
Plan: 2 of 2
Status: Ready to execute
Last activity: 2026-05-18

## Progress Bar

```
v1.4: [P] Phase 20  [ ] Phase 21  [ ] Phase 22  [ ] Phase 23
      0 / 4 phases complete  (P = planned)
```

## Accumulated Context

### Decisions

- Residential proxy required because datacenter IPs (GCP/Cloud Run) are blocked at the network layer before cookies are evaluated
- Three-layer stack (all required): residential proxy → cookies → bgutil PO token plugin
- Provider: Webshare free tier (validation) → IPRoyal pay-as-you-go (production); sticky sessions per job not per request
- Both DV360 and Google Ads use the same yt-dlp path — fix both in v1.4 together per project rule (fix all platforms simultaneously)
- bgutil sidecar MUST run in HTTP server mode (port 4416) — Script mode spawns subprocess per token request, causing cold-start latency + orphan processes on Cloud Run
- Dashboard filter features were built in April 2026 (commits 1d8edb6/aa9273f for metadata, e403eaf–d05999e for ad account) but lost; Phase 22 re-implements from scratch using v1.3 architecture — do NOT cherry-pick (conflict risk)
- PROXY-06 credential redaction ships in the same phase as proxy injection (Phase 20) — never deferred
- Metadata filter JOIN must include org_id guard in every WHERE clause — omitting exposes cross-org data (security requirement)
- Dashboard filter state URL persistence deferred to v1.5 (see REQUIREMENTS.md Out of Scope)
- Phase 20 includes: Alembic migration (2 new SystemConfig columns + composite index on asset_metadata_value) + bgutil Docker sidecar + proxy injection in both dv360_sync.py and google_ads_sync.py + redact_credentials() utility
- Phase 22 can start in parallel with Phase 21 — depends on Phase 20's migration (composite index), not Phase 21's UI
- Phase 22 Plan 01: metadata filter backend (explicit 400 for malformed filter, not silent skip; two-layer org guard T-22-01; alembic upgrade e8f9a0b1c2d3 not upgrade head due to DEBT-01)
- Phase 23 Plan 01: null_duration_count computed only when duration filter active (D-07) to avoid COUNT on every dashboard load; backfill gated by has_null_duration_assets > 0 at each sync site; ix_creative_assets_org_format_duration composite index chains onto f8a2b3c4d5e6

### Roadmap Evolution

- 2026-05-14: Initial v1.4 roadmap — 4 phases (20–23), 9 requirements mapped

### Blockers/Concerns

- Webshare free tier proxy validation must succeed before Phase 20 is closed — validate against a public YouTube URL from a GCP host
- Confirm bgutil port 4416 reachability from backend container before any download test (curl http://bgutil-pot:4416/health)
- Ad account multi-select (DASH-02) may already be present in main (commit e403eaf) — verify before building Phase 22 on top of it

## Deferred Items

Items carried to v1.5 or backlog:

| Type | ID / Slug | Status |
|------|-----------|--------|
| uat_gap | Phase 15 (v1.3) | deferred — live TikTok sync required |
| verification_gap | Phase 15 (v1.3) | deferred — live TikTok sync required |
| v2_req | SSE-03 | SSE Redis pub/sub at 50+ concurrent SuperAdmins |
| v2_req | META-01, META-02 | Account-level metadata defaults |
| v2_req | DEBT-01 | Alembic 4-head merge |
| out_of_scope | Filter state URL persistence | v1.5 candidate |

## Session Continuity

Last session: 2026-05-18T10:48:56.732Z
Stopped at: Completed 23-01-PLAN.md (duration filter backend)
Resume file: None

## Operator Next Steps

- Execute Plan 23-02 (duration filter frontend — Angular slider + bounds endpoint integration)
- Phase 23 Plan 01 complete; Plan 02 is the final deliverable for v1.4 milestone
