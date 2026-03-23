---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Ready to execute
stopped_at: Completed 03-06-PLAN.md
last_updated: "2026-03-23T19:00:10.204Z"
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 15
  completed_plans: 12
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-20)

**Core value:** A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.
**Current focus:** Phase 03 — brainsuite-scoring-pipeline

## Current Position

Phase: 03 (brainsuite-scoring-pipeline) — EXECUTING
Plan: 4 of 6

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: -

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01 P01 | 3min | 2 tasks | 6 files |
| Phase 01 P02 | 6 | 1 tasks | 4 files |
| Phase 01 P03 | 2 | 2 tasks | 2 files |
| Phase 02 P03 | 18 | 1 tasks | 3 files |
| Phase 02 P01 | 9 | 2 tasks | 15 files |
| Phase 02 P01 | 9 | 2 tasks | 15 files |
| Phase 02 P02 | 15 | 2 tasks | 5 files |
| Phase 02 P04 | 15 | 2 tasks | 6 files |
| Phase 02 P06 | 25 | 2 tasks | 6 files |
| Phase 02 P05 | 10 | 2 tasks | 12 files |
| Phase 03 P02 | 15 | 1 tasks | 2 files |
| Phase 03 P01 | 15 | 2 tasks | 7 files |
| Phase 03 P06 | 8 | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 4 phases — Infra Portability first (unblocks cloud deploy), then Security (gates external users), then BrainSuite scoring (primary deliverable), then Dashboard + Reliability
- [Phase 2 flag]: BrainSuite API schema unknown — Phase 3 must start with an API discovery spike before finalizing DB schema or Angular types
- [Phase 01]: Pin MinIO to RELEASE.2025-10-15T17-29-55Z (last official tag before Oct 2025 maintenance mode)
- [Phase 01]: SCHEDULER_STARTUP_DELAY_SECONDS replaces REPLIT_DEPLOYMENT boolean guard in main.py — more explicit for production tuning
- [Phase 01]: _object_name() returns relative_path unchanged: bucket is the namespace, GCS public_prefix prefix wrapper removed
- [Phase 01]: Tests use unittest.mock (not moto) for object storage unit tests: avoids extra dependency, sufficient for method contract testing
- [Phase 01]: setup.py uses sys.stdin.isatty() guard so --dry-run < /dev/null works without prompts
- [Phase 01]: Platform OAuth credentials optional in setup.py — only DB/storage/auto-generated keys required for local dev
- [Phase 02]: Refresh token removed from TokenResponse body — delivered only via httpOnly cookie (path=/api/v1/auth, secure=not DEBUG, samesite=lax)
- [Phase 02 P01]: Use PurePosixPath for path traversal detection — avoids filesystem access, httpx normalizes bare ../../ so encoded %2e%2e forms are the real attack surface
- [Phase 02 P01]: TOKEN_ENCRYPTION_KEY validated at Settings load time via field_validator; security.py direct Fernet init with no silent fallback
- [Phase 02]: Redis singleton uses lazy-init get_redis() - mirrors ObjectStorageService._ensure_client() pattern from Phase 1
- [Phase 02]: OAuth session cleanup in connect_accounts (not oauth_callback) - session must survive until user confirms account selection
- [Phase 02]: asyncio_mode=auto in pyproject.toml - eliminates per-test @pytest.mark.asyncio boilerplate for Phase 2 async tests
- [Phase 02]: APP_INITIALIZER added to app.config.ts: silently attempts httpOnly cookie refresh on startup — prevents flash-of-login-page on page reload when session is valid
- [Phase 02]: auth.effects.ts logout$ kept for router navigation only — AuthService.logout() clears BehaviorSubject and calls backend endpoint, effect handles redirect
- [Phase 02]: snake_case field names in TypeScript interfaces match JSON wire format from FastAPI
- [Phase 02]: Both /apps/{id} and /brainsuite-apps/{id} DELETE alias routes fixed to return 204 consistently
- [Phase 02]: Function-name allowlist in AST test for scheduler.py — allows APScheduler job wrapper functions to keep broad catches for job isolation
- [Phase 02]: OAuth endpoint catches changed to 502 status — upstream platform auth failures are gateway errors, not bad requests
- [Phase 03]: Token cached 50 minutes — shorter than OAuth TTL to avoid edge cases where token expires mid-request
- [Phase 03]: 429 backoff uses x-ratelimit-reset header + 2s buffer; falls back to now+60s if header is malformed
- [Phase 03]: map_channel normalizes reels→reel via string replace to handle both instagram_reels and instagram_reel placements
- [Phase 03]: UniqueConstraint on creative_asset_id (uq_score_per_asset): one score record per asset enforced at DB level
- [Phase 03]: down_revision=k2l3m4n5o6p7 for e1f2g3h4i5j6 migration: latest in chain at execution time
- [Phase 03]: down_revision=e1f2g3h4i5j6 for f2g3h4i5j6k7 seed migration: latest in chain at execution time
- [Phase 03]: Language values in metadata seed sorted alphabetically by label for consistent sort_order across environments

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 3]: BrainSuite API schema (dimension field names, score range, response envelope) is unknown — must do a live API discovery spike before committing to creative_score_results table schema or Angular DTO types
- [Phase 4]: UX score color thresholds depend on confirmed BrainSuite score scale from Phase 3
- [General]: Google Ads OAuth consent screen — verify "Published" status before Phase 4 (Testing mode = 7-day refresh token expiry in production)

## Session Continuity

Last session: 2026-03-23T19:00:10.202Z
Stopped at: Completed 03-06-PLAN.md
Resume file: None
