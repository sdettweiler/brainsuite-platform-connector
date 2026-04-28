# Retrospective

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-25
**Phases:** 4 | **Plans:** 19

### What Was Built

1. Docker Compose portability — full stack runs locally and on any cloud with zero Replit dependency (Phase 1)
2. Production security hardening — httpOnly cookie auth, Redis OAuth sessions, Fernet startup validation, path traversal fix, typed DTOs (Phase 2)
3. BrainSuite scoring pipeline — async UNSCORED→COMPLETE state machine, tenacity retry, 15-min APScheduler batch job, score + dimension breakdown UI (Phase 3)
4. Dashboard polish + platform reliability — score range slider, video thumbnail fallback, health badges, reconnect prompts, SCHEDULER_ENABLED guard (Phase 4)

### What Worked

- **Phased dependency ordering** — Infrastructure first unblocked all other phases; Security before external users was the right gate
- **State machine for scoring** — UNSCORED/PENDING/PROCESSING/COMPLETE/FAILED gave clear debuggability and correct retry semantics
- **Session-per-operation pattern** — Separating DB sessions from HTTP calls prevented connection exhaustion during BrainSuite API polling
- **on_conflict_do_nothing for UNSCORED injection** — Re-syncs don't reset already-scored assets; zero incidents from this pattern
- **Verification checkpoint plan (04-04)** — Dedicated final plan for E2E validation caught the ngx-slider missing install and exception audit gaps before release

### What Was Inefficient

- **BrainSuite API schema unknown at Phase 3 start** — Required a live API discovery spike before finalizing DB schema and Angular DTO types; should have been done during research phase
- **CE tab UI bugs** — Post-execution bug sweep on the Creative Effectiveness tab (viz extension detection, presigned URL signatures, Meta thumbnail quality) added unplanned commits
- **Exception audit allowlist lag** — Phase 3/4 functions added broad catches but the allowlist wasn't updated until Phase 4 verification, causing false-positive test failures

### Patterns Established

- Brownfield project: read existing code thoroughly before planning any change
- Security phase before external onboarding: always gate on security before real users
- Score state machine: UNSCORED → PENDING → PROCESSING → COMPLETE | FAILED is the right pattern for any async processing queue
- Verification checkpoint: last plan in each phase should verify E2E, not just unit tests

### Key Lessons

- Always do API discovery spike before committing to DB schema for external API integrations
- Exception audit allowlists must be updated in the same plan that adds the exempted functions
- Pin third-party packages to framework-compatible versions explicitly (ngx-slider 17.0.2 for Angular 17)
- SCHEDULER_ENABLED guard is required for any APScheduler service deployed behind a load balancer

---

## Milestone: v1.2 — BrainSuite Configuration

**Shipped:** 2026-04-28
**Phases:** 4 (11–14) | **Plans:** 13

### What Was Built

1. Per-org BrainSuite credential schema (`org_brainsuite_config` + `org_brainsuite_field_mappings`) with Fernet-encrypted secret, per-org token dict caching, and full scoring pipeline re-wire off `.env` (Phase 11)
2. Brand values metadata fields seeded via Alembic + provisioned on new-org registration; `system_app_name` moved to `BrainsuiteApp` row for cleaner per-app URL control (Phase 11–12)
3. Settings UI: masked secret input, Test Connection live auth check, per-app `system_app_name` accordion, re-score dialog on config change (Phase 12)
4. Field mapping slide panel (750 lines): 12 video / 8 static standard fields, custom CRUD, mandatory toggles, D-06 auto-match; FMAP-07 pipeline guard + `MANDATORY_FIELD_MISSING` notification (Phase 13)
5. `SystemConfig` singleton table + SuperAdmin JWT claim + `/configuration/admin` UI; `dv360_sync.py` reads cookies from DB with env var fallback + `COOKIE_FAILED` broadcast to SuperAdmins (Phase 14)

### What Worked

- **Schema-first phase ordering** — Phase 11 DB schema before any UI unblocked Phases 12, 13, 14 to execute independently; zero cross-phase blocking
- **Static analysis tests** — All schema/endpoint tests used `pathlib.read_text()` with no live DB, enabling fast CI verification; pattern established in Phase 11 paid dividends through Phase 14
- **Session-per-operation everywhere** — `_check_mandatory_fields`, `_get_cookies_from_db`, `create_superadmin_notification` all open their own sessions; no cross-concern session sharing
- **Pydantic Literal for health status** — `CookieSlotHealth.status: Literal["valid","expired","missing"]` structurally prevents any string field leaking decrypted cookie content
- **Phase 14 code review fixes** — 6-item code review caught a hardcoded superadmin email, env var cookie bypass, and missing token refresh; all resolved atomically before UAT

### What Was Inefficient

- **`system_app_name` schema pivot in Phase 12** — Plan 12-01 had to drop `video_app_name`/`static_app_name` columns added in Phase 11 and move to `BrainsuiteApp.system_app_name`; indicates Phase 11 research could have surfaced this earlier
- **Phase 13 UAT field removals** — `channel` field removed post-UAT (auto-derived from platform); `brainsuite_intended_messages_language` metadata field had to be added in a follow-up migration; both gaps could have been caught by dry-running the UI against real data before plan execution
- **STATE.md staleness** — STATE.md had progress showing 1/3 phases complete and described Phase 14 as "Not started" throughout execution; kept getting stale without automatic update

### Patterns Established

- **Singleton guard pattern** — `singleton_guard String(1) UNIQUE` enforces exactly one platform-config row at DB level; no application-layer check needed
- **SuperAdmin tier** — `is_superuser` JWT claim + `get_current_superadmin` dependency is the right pattern for platform-operator capabilities that sit above org admin; class-based guard for explicit intent
- **COOKIE_FAILED notification only when cookies list non-empty** — Cookieless download is a valid fallback; only notify when cookies existed and all failed (D-12/D-13)

### Key Lessons

- Surface schema design questions (where does `app_name` live — app row vs org config?) during research, not mid-execution
- Run UI against real staging data before finalizing field lists for mapping editors — "channel" removal and missing language field were preventable
- `asyncio.create_task` for fire-and-forget notifications is the right pattern; notification failure must never block scoring state transitions

---

## Cross-Milestone Trends

| Milestone | Phases | Plans | Days | Files | LOC Added |
|-----------|--------|-------|------|-------|-----------|
| v1.0 MVP | 4 | 19 | 34 | 276 | ~52,000 |
| v1.1 Insights + Intelligence | 6 | 14 | 21 | 329 | ~23,842 |
| v1.2 BrainSuite Configuration | 4 | 13 | 13 | 123 | ~21,240 |
