---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: Download Performance & Tech Debt
status: roadmapped
last_updated: "2026-05-18T00:00:00.000Z"
last_activity: 2026-05-18
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-18 — milestone v1.5 started)

**Core value:** A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.
**Current focus:** v1.5 — Download Performance & Tech Debt

## Current Position

Phase: Phase 24 — Download Performance Backend (not started)
Plan: —
Status: Roadmap defined; ready to plan Phase 24
Last activity: 2026-05-18 — Roadmap written (3 phases, 8 requirements)

## Progress Bar

```
v1.5: [░░░░░░░░░░] 0 / 3 phases complete
      Phase 24: Download Performance Backend     [ not started ]
      Phase 25: Configurable Concurrency         [ not started ]
      Phase 26: Tech Debt Closure                [ not started ]
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
- v1.5 Phase 24 groups PERF-01/03/04/05/06 together — all modify the same yt-dlp download call chain; must ship atomically so retry order, cache, timeout, and split are internally consistent
- v1.5 Phase 25 (PERF-02) depends on Phase 24 because the semaphore wraps the call chain that Phase 24 establishes; also needs a new SystemConfig column (DB migration) and SuperAdmin UI field
- v1.5 Phase 26 (DEBT-01 + PROXY-02): Alembic merge must run after all v1.5 migrations exist; PROXY-02 is environment troubleshooting, not new code — pair with DEBT-01 as gap-closure work

### Roadmap Evolution

- 2026-05-14: Initial v1.4 roadmap — 4 phases (20–23), 9 requirements mapped
- 2026-05-18: v1.5 roadmap — 3 phases (24–26), 8 requirements mapped; 5 backend perf + 1 UI/backend + 2 tech debt

### Blockers/Concerns

- PROXY-02 (Google Ads live validation) blocked by MCC manager account + expired cookie environment issues — unblock before Phase 26
- DEBT-01 requires all v1.5 Alembic migrations to land first; do not run merge until Phase 25 migration is committed

## Deferred Items

Items carried to v1.6 or backlog:

| Type | ID / Slug | Status |
|------|-----------|--------|
| uat_gap | Phase 15 (v1.3) | deferred — live TikTok sync required |
| verification_gap | Phase 15 (v1.3) | deferred — live TikTok sync required |
| v2_req | SSE-03 | SSE Redis pub/sub at 50+ concurrent SuperAdmins |
| v2_req | META-01, META-02 | Account-level metadata defaults |
| future | Filter state URL persistence | v1.6 candidate |

## Session Continuity

Last session: 2026-05-18T13:27:22.836Z
Stopped at: v1.5 roadmap written
Resume file: None

## Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 20260518-fix-httpx-proxy-kwarg | Fix httpx proxy kwarg in super_admin.py:370 | 2026-05-18 | 734b2d7 | [20260518-fix-httpx-proxy-kwarg](./quick/20260518-fix-httpx-proxy-kwarg/) |

## Operator Next Steps

- Run `/gsd-plan-phase 24` to plan Phase 24: Download Performance Backend
