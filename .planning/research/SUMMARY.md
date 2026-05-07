# Project Research Summary

**Project:** BrainSuite Platform Connector
**Domain:** Multi-tenant SaaS ad intelligence platform — SuperAdmin observability + TikTok asset pipeline
**Milestone:** v1.3 — SuperAdmin Monitoring & TikTok Downloads
**Researched:** 2026-05-07
**Confidence:** HIGH

## Executive Summary

v1.3 adds two capabilities to an existing, validated FastAPI + Angular + PostgreSQL stack: a real-time job monitoring dashboard visible to SuperAdmins, and closure of the TikTok asset download gap that currently blocks AI autofill and BrainSuite scoring for TikTok creatives. The technical approach is well-established and low-risk: a new `background_jobs` PostgreSQL table serves as the single instrumentation foundation, one new backend package (`sse-starlette==3.4.2`) powers the SSE streaming endpoint, and the TikTok download path is largely already written via the existing `_download_tiktok_thumbnail()` helper — it needs wiring into the main sync pipeline and progress tracking. Zero new npm packages are required on the frontend; Angular Material, RxJS, and the existing ECharts install cover all UI needs.

The recommended build order is strict and dependency-driven: schema must land first because every other component reads or writes to it. Helper services come second, then service instrumentation, then the SSE endpoint, then the Angular client, and finally TikTok wiring. Skipping this order — for example, building the UI before the SSE endpoint is instrumented — will require rework. The architecture is deliberately simple for phase 1: a polling-based SSE generator against PostgreSQL (no Redis pub/sub required) with a DB-side cleanup job to prevent table bloat.

The single highest-risk concern is SSE connection lifecycle management. Unreleased EventSource connections in Angular will exhaust Uvicorn worker slots under production load, causing cascading failures that look like system instability rather than a connection leak. Prevention (explicit `ngOnDestroy` cleanup + server-side `timeout-keep-alive`) must be implemented in the same phase as the SSE endpoint — not deferred. Table bloat cleanup via an APScheduler job must similarly be added in the same phase as table creation.

## Key Findings

### Recommended Stack

The existing v1.1/v1.0 stack (FastAPI 0.115, SQLAlchemy 2.0, APScheduler 3.10.4, Angular 17, NgRx 17, Angular Material 17, ECharts 5.6) requires exactly one new addition for v1.3.

**Core technologies for v1.3:**
- `sse-starlette==3.4.2`: SSE streaming for FastAPI — the only new backend package; wraps streaming response with `EventSourceResponse`
- `yt-dlp`: TikTok asset download — already in `requirements.txt`; needs exponential retry wrapper and size/timeout limits added
- `JSONB` (PostgreSQL via SQLAlchemy): already in stack; used for `output` and `metadata` columns on the new `background_jobs` table
- `EventSource` (browser-native Web API): SSE client in Angular — zero npm installs; built into all modern browsers
- `Angular Material` (already installed): `mat-table`, `mat-progress-bar`, `mat-chip`, `mat-sidenav`, `mat-tab-group` cover the entire monitoring UI

Nothing is added to package.json. The frontend stack is complete as-is.

### Expected Features

**Must have (table stakes):**
- Real-time job list with status indicators (PENDING/RUNNING/COMPLETE/FAILED badges) — SuperAdmins expect live visibility without SSHing into containers
- Per-job-type grouping (sync, download, autofill, scoring) — operational context differs enough that visual separation is required
- Per-sync-run progress bar with numerator/denominator ("7/10 assets") — determinate progress is expected; spinners are insufficient
- Error visibility with traceback display — root-cause debugging without container access
- Job drill-in detail panel with tabs (metadata, output, files, errors)
- TikTok asset download during sync — closes the gap blocking AI autofill and BrainSuite scoring for TikTok creatives

**Should have (competitive for v1.3 MVP):**
- Live summary cards ("Syncing: 3 | Downloading: 2 | Autofill: 1") — high UX value, low complexity
- SSE connection status badge in header — users need to know if the live view is actually live
- JSONB collapsible viewer for AI autofill output in detail panel
- File manifest table with presigned download URLs

**Defer to v1.4+:**
- Job retry / pause / cancel controls — requires job state serialization and transaction safety
- Per-entity progress breakdown (org/account granularity within a multi-tenant sync)
- Export job history as CSV
- Bulk operations
- Per-org job visibility for non-SuperAdmin users

### Architecture Approach

A new `background_jobs` table (UUID PK, org_id FK, job_type, status, progress_current/total ints, output JSONB, error_message text, metadata JSONB, timestamps) is the single source of truth for all background work. Two composite indexes (`org_id + status`, `org_id + created_at`) keep SSE polling queries fast. The SSE endpoint polls this table every 2 seconds inside an async generator and emits `job_update` events; the Angular `JobMonitorService` holds a `BehaviorSubject<BackgroundJob[]>` and deduplicates incoming events by UUID. The existing `SyncJob` model is preserved for backward compatibility.

**Major components:**
1. `backend/app/models/background_job.py` — SQLAlchemy model + Alembic migration
2. `backend/app/services/background_jobs.py` — `create_job()` / `update_progress()` helpers used by all instrumented services
3. `backend/app/services/sync/tiktok_asset_downloader.py` — isolated download service with retry logic; designed for reuse across other platforms
4. `backend/app/api/v1/endpoints/admin_jobs.py` — SSE endpoint (`GET /stream`), job list, job detail; SuperAdmin-gated via JWT `is_superadmin` claim
5. `frontend/.../services/job-monitor.service.ts` — EventSource client with exponential backoff reconnect and `BehaviorSubject` state
6. `frontend/.../components/job-monitor/` — Angular Material table + sidenav detail panel + summary cards

### Critical Pitfalls

1. **SSE connection leaks exhausting Uvicorn worker pool** — Every open EventSource holds one worker slot. With 50+ concurrent SuperAdmins the pool fills and all requests queue indefinitely. Prevention: explicit `ngOnDestroy` EventSource close, server-side `--timeout-keep-alive 30`, 30s server heartbeat, exponential backoff on reconnect. All prevention steps must ship in the same phase as the SSE endpoint.

2. **`background_jobs` table bloat from high-frequency status writes** — A 1000-asset sync produces 5000+ writes. Without a cleanup job, the table reaches millions of rows within months; autovacuum cannot keep up; SSE query latency spikes from 50ms to 2s+. Prevention: APScheduler cleanup job (delete COMPLETE rows older than 30 days, nightly at 02:00) and autovacuum tuning added in the same migration as table creation — not deferred.

3. **SQLAlchemy session violations in APScheduler job tasks** — Passing a single Session across async yield points causes silent write failures and jobs stuck in PROCESSING. Prevention: strict session-per-operation pattern (separate `with Session()` blocks for fetch, progress write, and result write) with try/except that guarantees a FAILED status write on exception.

4. **Browser EventSource reconnect storm after server restart** — 50 clients reconnecting at the default 3s retry generates 50 simultaneous requests/second on the newly-started process. Prevention: exponential backoff on the client (`min(1000 * 2^attempt, 30000)ms`) in the initial implementation.

5. **TikTok download failures blocking entire sync** — yt-dlp fails silently when TikTok updates anti-bot headers (monthly cadence). Prevention: per-asset exponential retry (max 3 attempts, 2^attempt backoff), 30-second per-asset timeout, 500MB size abort, `DOWNLOAD_FAILED` status written per asset with `continue` to keep sync running.

## Implications for Roadmap

Based on combined research, the build order is fixed by hard dependencies. Phases cannot be reordered.

### Phase 1: Database Schema Foundation
**Rationale:** Every other component reads or writes `background_jobs`. This is the hard blocker — nothing can be built or tested before it exists.
**Delivers:** Alembic migration, `BackgroundJob` SQLAlchemy model, two composite indexes, autovacuum tuning, APScheduler cleanup job (all in same phase)
**Addresses:** Data layer for real-time job list, progress tracking, error visibility
**Avoids:** Table bloat (cleanup and autovacuum tuning are part of this phase, not deferred)

### Phase 2: Instrumentation Helpers
**Rationale:** Services cannot write job status without shared helper functions. Centralizing `create_job()` and `update_progress()` prevents each service from implementing inconsistent patterns.
**Delivers:** `services/background_jobs.py` helper module; `services/sync/tiktok_asset_downloader.py` with exponential retry and size limits; `sse-starlette==3.4.2` added to requirements.txt
**Avoids:** Session violations (session-per-operation pattern enforced in helper function signatures)

### Phase 3: Service Instrumentation
**Rationale:** Wire helpers into existing services before building the SSE consumer. Instrumenting after the endpoint is built means SSE shows empty data during development and masks integration bugs.
**Delivers:** `scoring_job.py`, `ai_autofill.py`, and `tiktok_sync.py` modified to write `BackgroundJob` rows with progress updates throughout execution
**Addresses:** Scoring instrumentation, AI autofill output capture, TikTok download progress tracking

### Phase 4: SSE Streaming Endpoint
**Rationale:** Backend API must exist before the Angular client can be built or tested. Polling generator against PostgreSQL (no Redis) is sufficient for phase 1 and keeps the implementation simple.
**Delivers:** `GET /api/v1/admin/jobs/stream` (EventSourceResponse), `GET /api/v1/admin/jobs` (list), `GET /api/v1/admin/jobs/{id}` (detail); all SuperAdmin-gated
**Avoids:** SSE connection leaks — `timeout-keep-alive`, 30s heartbeat, and Uvicorn concurrency limits configured here in the same PR

### Phase 5: Angular Monitoring UI
**Rationale:** UI built last because it depends on a working, instrumented backend. Building UI before Phase 3-4 means mocking data that may not match the real schema or SSE event shape.
**Delivers:** `JobMonitorService` with exponential backoff reconnect; job list with Angular Material table, grouped card sections per job type, status chips, progress bars; sidenav detail panel with metadata/output/files/errors tabs; live summary cards
**Avoids:** EventSource memory leaks (`ngOnDestroy` cleanup required); reconnect storm (exponential backoff required — both are prerequisites, not polish)

### Phase 6: TikTok Asset Download Wiring
**Rationale:** Separated from Phase 3 service instrumentation to allow independent verification that `_download_tiktok_thumbnail()` integrates cleanly with `BackgroundJob` tracking and that download failures genuinely do not block sync completion.
**Delivers:** TikTok creatives downloaded to MinIO/S3 during sync; `CreativeAsset.video_url` and `image_url` populated; per-asset `DOWNLOAD_FAILED` on failure without blocking sync; AI autofill and BrainSuite scoring unblocked for TikTok
**Avoids:** TikTok download blocking sync (isolated per-asset retry with `continue` on failure); yt-dlp header drift (smoke test against live URL at phase start)

### Phase Ordering Rationale

- Phases 1 through 5 form a strict dependency chain (schema → helpers → instrumentation → API → UI). No phase can move earlier in the sequence.
- Phase 6 (TikTok download) can run in parallel with Phase 5 if team bandwidth allows, but sequencing it after Phase 5 ensures the monitoring UI is ready to observe the first real TikTok download runs — valuable for verifying the instrumentation works end-to-end.
- The cleanup job (table bloat prevention) is placed in Phase 1 by design. This is the single most important sequencing decision in the entire milestone: deferred cleanup is a documented production failure pattern.
- `sse-starlette` is added to requirements.txt in Phase 2 (not Phase 4) so the environment is consistent when Phase 3 services are tested.

### Research Flags

Phases with well-documented patterns (no additional research needed during planning):
- **Phase 1:** SQLAlchemy model + Alembic migration is an established pattern in this codebase; schema fields are fully specified in ARCHITECTURE.md
- **Phase 2:** Helper module design is straightforward; session-per-operation pattern already exists in this codebase
- **Phase 4:** `sse-starlette` EventSourceResponse pattern is documented with code samples in ARCHITECTURE.md and PITFALLS.md
- **Phase 5:** Angular Material table, sidenav, and RxJS BehaviorSubject patterns are all established in the existing frontend

Phases that need targeted review at planning time:
- **Phase 3:** Scoring job (`scoring_job.py`) and autofill service (`ai_autofill.py`) internals need a codebase read before instrumentation to confirm exact injection points; no external research needed
- **Phase 6:** yt-dlp impersonation header string should be verified against current TikTok behavior at phase start — run smoke test before writing the downloader

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | sse-starlette is the only net-new package; yt-dlp already in requirements.txt; zero new npm packages; all confirmed |
| Features | HIGH | Job monitoring UI patterns verified against Celery/Flower, BullMQ/Taskforce, AWS Batch; TikTok download complexity confirmed LOW because infrastructure already exists |
| Architecture | HIGH | Build order derived from hard dependency chain with no ambiguity; session-per-operation confirmed correct for this SQLAlchemy + APScheduler combination |
| Pitfalls | HIGH | SSE connection leaks, table bloat, and session violations are verified failure modes with cited production incidents and official documentation |

**Overall confidence:** HIGH

### Gaps to Address

- **yt-dlp impersonation string currency:** The `chrome-131` profile is current as of early 2026 but TikTok updates anti-bot detection monthly. At Phase 6 start, run `yt-dlp --impersonate chrome-131 [sample_url]` and update the profile string if needed. Document the tested profile in code comments.
- **SSE connection count in production:** The 50-concurrent-SuperAdmins estimate is a worst-case assumption. Confirm actual SuperAdmin headcount with the team at Phase 4 to set `--limit-concurrency` and `--workers` correctly for the deployment environment.
- **SyncJob backward compatibility decision:** ARCHITECTURE.md notes that `SyncJob` and `BackgroundJob` coexist but does not specify whether sync services should write to both. Recommended: write only to `BackgroundJob` for new job types (scoring, autofill, TikTok download); leave existing `SyncJob` writes in place unchanged. Confirm at Phase 3 start.

## Sources

### Primary (HIGH confidence)
- `.planning/research/ARCHITECTURE.md` (2026-05-07) — build order, component boundaries, BackgroundJob schema, SSE endpoint signature, Angular service pattern
- `.planning/research/PITFALLS.md` (2026-05-07) — SSE connection leaks, table bloat, session violations, TikTok download failure patterns with production evidence
- `.planning/research/FEATURES.md` (2026-05-07) — table stakes, differentiators, anti-features, MVP recommendation, feature dependency graph
- [Uvicorn Documentation](https://www.uvicorn.org/) — `--limit-concurrency`, `--timeout-keep-alive` flags confirmed
- [SQLAlchemy Async I/O Docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — session-per-operation in async contexts

### Secondary (MEDIUM confidence)
- [Monitoring Celery — Cronitor](https://cronitor.io/guides/monitoring-celery) — job monitoring UI patterns
- [Taskforce.sh BullMQ Dashboard](https://taskforce.sh/) — grouped card layout reference
- [Every TikTok Downloader Quirk — dev.to](https://dev.to/john_jewskiz/every-tiktok-downloader-quirk-i-hit-building-dltkkto-and-how-i-fixed-them-909) — yt-dlp impersonation and retry patterns
- [How to Reduce Bloat in Large PostgreSQL Tables — TigerData](https://www.tigerdata.com/learn/how-to-reduce-bloat-in-large-postgresql-tables) — autovacuum tuning guidance

### Tertiary (LOW confidence — validate at implementation time)
- yt-dlp `chrome-131` impersonation string: valid as of early 2026; verify against live TikTok URL before Phase 6

---
*Research completed: 2026-05-07*
*Ready for roadmap: yes*
