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

---

## Milestone: v1.3 — SuperAdmin Monitoring & TikTok Downloads

**Shipped:** 2026-05-13
**Phases:** 8 (Phases 15–19.3) | **Plans:** 23

### What Was Built

1. TikTok video and image asset download pipeline to MinIO/S3, closing the gap that blocked AI autofill and BrainSuite scoring for TikTok creatives (Phase 15)
2. PostgreSQL `background_jobs` table with autovacuum tuning, composite indexes, and 30-day nightly cleanup via APScheduler (Phase 16)
3. `job_tracker.py` helper module wiring all 4 job types (sync, download, autofill, scoring) to structured BackgroundJob records with real-time progress and JSONB output (Phase 17)
4. SSE real-time transport: FastAPI streaming endpoint with Redis pub/sub, 30s keepalive heartbeat, SuperAdmin JWT guard, and clean client-disconnect lifecycle (Phase 18)
5. SuperAdmin monitoring UI at /configuration/jobs: 4-tab OnPush job table, SSE-fed live progress bars, slide-in detail panels with type-specific drill-ins — Gemini output, download manifests, error tracebacks (10KB truncated), per-asset scores (Phase 19)
6. Three audit-driven gap-closure phases (19.1, 19.2, 19.3): null-token SSE race fix + EventSource leak, brainsuite_job_id moved to metadata_ for References panel, asset_url/video_source_url protected in ON CONFLICT exclusion, scoring_enabled gate enforced on all 4 platform download functions

### What Worked

- **TDD red-green pattern throughout** — Wave 0 test stubs written before implementation in every phase; all 4 gap-closure tests were RED baseline before Wave 2 fixed them to GREEN. Zero regression surprises at verification.
- **Decimal phase gap-closure pattern** — Inserting Phases 19.1, 19.2, 19.3 post-audit kept the main phase sequence intact, gave each gap its own plan/verify cycle, and produced clean commit history. The pattern is worth preserving for v1.4.
- **Milestone audit as insertion trigger** — Running a formal audit before declaring complete surfaced 3 categories of gaps that would have shipped as silent defects. Audit-to-insertion workflow is now a validated pattern.
- **Brownfield E2E flow tracing** — Documenting the full data path (scheduler.py line 169 → job_tracker → Redis PUBLISH → SSE generator → Angular NgZone) before executing prevented integration bugs at every phase boundary.

### What Was Inefficient

- **3 inserted gap-closure phases** — The milestone audit found gaps requiring 3 extra phases (19.1, 19.2, 19.3), each with its own plan/execute/verify cycle. Total overhead: ~6 additional plans over 1 day. Root cause: Phase 17 and 19 original plans did not cross-check the full References panel contract end-to-end before marking complete.
- **REQUIREMENTS.md checkbox staleness** — All 16 v1.3 requirement checkboxes remained `[ ] Pending` throughout execution because the CLI traceability table was never wired to phase completion. Had to be explicitly noted in the audit as "stale — all implemented." Requires a workflow fix.
- **sse-starlette version mismatch** — requirements.txt pinned 1.8.2 while the milestone spec stated 3.4.2; the discrepancy was only caught by the audit, not during Phase 18 execution. API compatibility happened to hold but it's a latent risk.

### Patterns Established

- **Audit-before-close as a milestone gate** — Running `gsd-audit-milestone` before declaring complete and treating findings as insertion candidates (not just notes) is the right pattern. Prevents silent tech debt at ship.
- **Decimal phases for post-audit gap closure** — 19.1/19.2/19.3 proved cleaner than amending original phases. Each decimal phase is independently verifiable and revertable.
- **Job tracker session-per-operation** — `create_background_job` and `update_background_job` open and close their own sessions; never share a session with the calling service. Consistent with the v1.2 pattern — no cross-concern session sharing.

### Key Lessons

1. Before marking a phase complete, verify the full end-to-end display path for any metadata field that is both written by backend and read by frontend. The brainsuite_job_id gap (output vs metadata_) would have been caught in Phase 17/19 if the References panel contract had been traced end-to-end.
2. REQUIREMENTS.md traceability checkboxes need to be updated in the same plan that validates the requirement — not deferred to a later cleanup pass. Stale checkboxes erode audit confidence.
3. Pin third-party packages to the exact version specified in the milestone spec (sse-starlette 3.4.2, not 1.8.2). Version drift is only caught by the audit, not by unit tests.
4. The milestone audit pattern (audit → classify gaps → insert decimal phases) adds ~15–20% time overhead but prevents silent defects. The overhead is worth it.

---

## Cross-Milestone Trends

| Milestone | Phases | Plans | Days | Files | LOC Added |
|-----------|--------|-------|------|-------|-----------|
| v1.0 MVP | 4 | 19 | 34 | 276 | ~52,000 |
| v1.1 Insights + Intelligence | 6 | 14 | 21 | 329 | ~23,842 |
| v1.2 BrainSuite Configuration | 4 | 13 | 13 | 123 | ~21,240 |
| v1.3 SuperAdmin Monitoring & TikTok | 8 | 23 | 6 | — | ~15,000 |
