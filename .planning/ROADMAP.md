# Roadmap: BrainSuite Platform Connector

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-03-25) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Insights + Intelligence** — Phases 5–10 (shipped 2026-04-15) — [archive](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 BrainSuite Configuration** — Phases 11–14 (shipped 2026-04-28) — [archive](milestones/v1.2-ROADMAP.md)
- 🚧 **v1.3 SuperAdmin Monitoring & TikTok Downloads** — Phases 15–19 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2026-03-25</summary>

- [x] **Phase 1: Infrastructure Portability** (3/3 plans) — completed 2026-03-20
- [x] **Phase 2: Security Hardening** (6/6 plans) — completed 2026-03-23
- [x] **Phase 3: BrainSuite Scoring Pipeline** (6/6 plans) — completed 2026-03-24
- [x] **Phase 4: Dashboard Polish + Reliability** (4/4 plans) — completed 2026-03-25

</details>

<details>
<summary>✅ v1.1 Insights + Intelligence (Phases 5–10) — SHIPPED 2026-04-15</summary>

- [x] **Phase 5: BrainSuite Image Scoring** (4/4 plans) — completed 2026-03-27
- [x] **Phase 6: Historical Backfill + Score History Schema** (1/1 plans) — completed 2026-03-30
- [x] **Phase 7: Score Trend, Performer Highlights + Performance Tab** (3/3 plans) — completed 2026-03-30
- [x] **Phase 8: Score-to-ROAS Correlation** (2/2 plans) — completed 2026-03-31
- [x] **Phase 9: AI Metadata Auto-Fill** (3/3 plans) — completed 2026-04-15
- [x] **Phase 10: In-App Notifications** (2/2 plans) — completed 2026-04-15

</details>

<details>
<summary>✅ v1.2 BrainSuite Configuration (Phases 11–14) — SHIPPED 2026-04-28</summary>

- [x] **Phase 11: Per-Org Config Schema + Pipeline Wiring** (3/3 plans) — completed 2026-04-16
- [x] **Phase 12: Credentials + App Name Settings UI** (3/3 plans) — completed 2026-04-17
- [x] **Phase 13: Field Mapping Editor + Mandatory Field Enforcement** (4/4 plans) — completed 2026-04-21
- [x] **Phase 14: YouTube Cookies Admin UI** (3/3 plans) — completed 2026-04-27

</details>

### 🚧 v1.3 SuperAdmin Monitoring & TikTok Downloads (In Progress)

**Milestone Goal:** A SuperAdmin can see every background job running on the platform in real time — sync runs, asset downloads, AI autofills, scoring — with progress bars, drill-in detail views, and full error tracebacks; TikTok asset download gap is closed.

- [x] **Phase 15: TikTok Asset Download** - Close the TikTok video and image download gap to unblock AI autofill and BrainSuite scoring (complete 2026-05-08)
- [x] **Phase 16: Job Persistence Schema** - PostgreSQL `background_jobs` table with indexes, autovacuum tuning, and cleanup job (complete 2026-05-08)
- [x] **Phase 17: Service Instrumentation** - Wire all four job types (sync, download, autofill, scoring) to write job records with progress (complete 2026-05-11)
- [ ] **Phase 18: SSE Transport** - FastAPI streaming endpoint with keepalive heartbeats and connection lifecycle management
- [ ] **Phase 19: SuperAdmin Monitoring UI** - Angular job monitor at /configuration/admin with real-time updates and drill-in detail panels

## Phase Details

### ✅ Phase 15: TikTok Asset Download (complete 2026-05-08)
**Goal**: TikTok video and image creatives are downloaded to MinIO/S3 during sync, closing the gap that blocks AI autofill and BrainSuite scoring for TikTok assets
**Depends on**: Phase 14 (existing sync pipeline)
**Requirements**: TKTOK-01, TKTOK-02
**Success Criteria** (what must be TRUE):
  1. After a TikTok sync, video creatives appear in the dashboard with playable video (video_url populated in CreativeAsset)
  2. After a TikTok sync, image creatives appear in the dashboard with visible thumbnails (image_url populated in CreativeAsset)
  3. A failed download for one TikTok asset does not block or abort the rest of the sync run
  4. AI autofill and BrainSuite scoring pipelines process TikTok assets (video_url/image_url is available as input)
  5. TikTok asset download and scoring respects the SuperAdmin auto-scoring toggle (global enable/disable); verify all platforms (Meta, TikTok, Google Ads, DV360) honour the same gate
**Plans**: 2 plans
Plans:
- [x] 15-01-PLAN.md — Implement TikTok video + image download methods and extend _enrich_from_ad_get (complete 2026-05-08)
- [x] 15-02-PLAN.md — Verify scoring gate across all 4 platforms (D-05) (complete 2026-05-08)

### Phase 16: Job Persistence Schema
**Goal**: The platform persists every background job run in PostgreSQL, with table bloat prevention built in from day one
**Depends on**: Phase 15 (independent — can depend on Phase 14 directly)
**Requirements**: JOBS-01, JOBS-02
**Success Criteria** (what must be TRUE):
  1. The `background_jobs` table exists with all required columns (type, org_id, status, progress_current, progress_total, output JSONB, error, started_at, ended_at) and composite indexes
  2. Job records older than 30 days are automatically deleted by a nightly APScheduler cleanup job
  3. Alembic migration runs cleanly on a fresh database and on the existing production schema
**Plans**: 3 plans
Plans:
**Wave 1**
- [ ] 16-01-PLAN.md — BackgroundJob model (jobs.py), __init__.py export, Wave-0 test scaffolds

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 16-02-PLAN.md — Alembic migration with autovacuum tuning + BLOCKING alembic upgrade head verification
- [ ] 16-03-PLAN.md — Maintenance service (maintenance.py) + scheduler registration (JOBS-02)

**Cross-cutting constraints:**
- BackgroundJob model must be importable via `from app.models.jobs import BackgroundJob` before migration or maintenance code runs
- All status values must be: PENDING, RUNNING, COMPLETE, FAILED (consistent with SyncJob)

### Phase 17: Service Instrumentation
**Goal**: All four background job types (sync, download, autofill, scoring) write job records with real-time progress updates throughout execution
**Depends on**: Phase 16
**Requirements**: INSTR-01, INSTR-02, INSTR-03, INSTR-04, INSTR-05
**Success Criteria** (what must be TRUE):
  1. Triggering any platform sync (Meta, TikTok, Google Ads, DV360) creates a job record that transitions from PENDING to RUNNING to COMPLETE/FAILED in the database
  2. Asset download batches update progress_current and progress_total incrementally (e.g. 7/10 assets downloaded) while the job is in progress
  3. After an AI autofill run, the job record's output field contains the full Gemini + Whisper field output (field name, determined value, raw response)
  4. After a scoring run, the job record's output field contains per-asset outcomes (asset_id, status, score value)
  5. Every job record stores the internal job ID and any external API job IDs (BrainSuite job ID, platform sync run ID) in the metadata field
**Plans**: 6 plans
Plans:

**Wave 1**
- [x] 17-01-PLAN.md — job_tracker.py helpers + test_instrumentation.py Wave-0 stubs (complete 2026-05-11)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 17-02-PLAN.md — Sync instrumentation (all 4 entry points in scheduler.py) — INSTR-01, INSTR-05 (complete 2026-05-11)
- [x] 17-03-PLAN.md — Download instrumentation (all 4 helpers: Google Ads, DV360, TikTok, Meta) — INSTR-02 (complete 2026-05-11)
- [x] 17-04-PLAN.md — Autofill instrumentation (run_autofill_for_asset) — INSTR-03 (complete 2026-05-11)
- [x] 17-05-PLAN.md — Scoring instrumentation (_process_asset) — INSTR-04, INSTR-05 (complete 2026-05-11)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 17-06-PLAN.md — All 7 instrumentation test assertions (test_instrumentation.py) — INSTR-01, INSTR-02, INSTR-03, INSTR-04, INSTR-05 (complete 2026-05-11)

### Phase 18: SSE Transport
**Goal**: The backend streams real-time job updates to connected SuperAdmin browsers via Server-Sent Events, with connection leaks and proxy timeouts prevented
**Depends on**: Phase 17
**Requirements**: SSE-01, SSE-02
**Success Criteria** (what must be TRUE):
  1. A SuperAdmin browser connected to the SSE endpoint receives a job_update event within 2 seconds of any job status or progress change in the database
  2. The SSE endpoint sends a keepalive heartbeat on a regular interval so proxy connections do not time out during idle periods
  3. Closing the browser tab or navigating away releases the server-side SSE connection (no persistent worker slot leak)
  4. The SSE endpoint is guarded by the SuperAdmin JWT claim and rejects non-SuperAdmin connections
**Plans**: 2 plans
Plans:

**Wave 1**
- [x] 18-01-PLAN.md — Wave 0 test stubs (test_sse.py) + Redis PUBLISH wiring in job_tracker.py + sse-starlette in requirements.txt

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 18-02-PLAN.md — get_current_superadmin_sse dependency + jobs.py SSE endpoint + router registration + 5 green tests

### Phase 19: SuperAdmin Monitoring UI
**Goal**: SuperAdmins can view, filter, and drill into all background jobs in real time at /configuration/admin, including progress bars, error tracebacks, and full output details
**Depends on**: Phase 18
**Requirements**: MON-01, MON-02, MON-03, MON-04, MON-05, MON-06, MON-07
**Success Criteria** (what must be TRUE):
  1. The /configuration/admin page displays all active and recent jobs grouped by type (sync / download / autofill / scoring) and updates without a page refresh via SSE
  2. In-progress download and sync jobs show a determinate progress bar (e.g. "7 / 10 assets") that advances in real time
  3. Drilling into an autofill job shows the full Gemini field output (field names, determined values, raw API response) in a readable panel
  4. Drilling into a download job shows a manifest of downloaded assets with links to each file
  5. Drilling into a failed job shows the full error traceback (copyable to clipboard, truncated at 10 KB)
  6. Drilling into a scoring job shows per-asset score outcomes and any per-asset failures
  7. Every job detail view displays the internal job ID and any external API job IDs (e.g. BrainSuite job ID)
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure Portability | v1.0 | 3/3 | Complete | 2026-03-20 |
| 2. Security Hardening | v1.0 | 6/6 | Complete | 2026-03-23 |
| 3. BrainSuite Scoring Pipeline | v1.0 | 6/6 | Complete | 2026-03-24 |
| 4. Dashboard Polish + Reliability | v1.0 | 4/4 | Complete | 2026-03-25 |
| 5. BrainSuite Image Scoring | v1.1 | 4/4 | Complete | 2026-03-27 |
| 6. Historical Backfill + Score History Schema | v1.1 | 1/1 | Complete | 2026-03-30 |
| 7. Score Trend, Performer Highlights + Performance Tab | v1.1 | 3/3 | Complete | 2026-03-30 |
| 8. Score-to-ROAS Correlation | v1.1 | 2/2 | Complete | 2026-03-31 |
| 9. AI Metadata Auto-Fill | v1.1 | 3/3 | Complete | 2026-04-15 |
| 10. In-App Notifications | v1.1 | 2/2 | Complete | 2026-04-15 |
| 11. Per-Org Config Schema + Pipeline Wiring | v1.2 | 3/3 | Complete | 2026-04-16 |
| 12. Credentials + App Name Settings UI | v1.2 | 3/3 | Complete | 2026-04-17 |
| 13. Field Mapping Editor + Mandatory Field Enforcement | v1.2 | 4/4 | Complete | 2026-04-21 |
| 14. YouTube Cookies Admin UI | v1.2 | 3/3 | Complete | 2026-04-27 |
| 15. TikTok Asset Download | v1.3 | 2/2 | Complete | 2026-05-08 |
| 16. Job Persistence Schema | v1.3 | 3/3 | Complete | 2026-05-08 |
| 17. Service Instrumentation | v1.3 | 6/6 | Complete | 2026-05-11 |
| 18. SSE Transport | v1.3 | 0/2 | Not started | - |
| 19. SuperAdmin Monitoring UI | v1.3 | 0/? | Not started | - |
