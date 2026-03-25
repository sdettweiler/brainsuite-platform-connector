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

## Cross-Milestone Trends

| Milestone | Phases | Plans | Days | Files | LOC Added |
|-----------|--------|-------|------|-------|-----------|
| v1.0 MVP | 4 | 19 | 34 | 276 | ~52,000 |
