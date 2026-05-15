# Roadmap: BrainSuite Platform Connector

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-03-25) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Insights + Intelligence** — Phases 5–10 (shipped 2026-04-15) — [archive](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 BrainSuite Configuration** — Phases 11–14 (shipped 2026-04-28) — [archive](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 SuperAdmin Monitoring & TikTok Downloads** — Phases 15–19.3 (shipped 2026-05-13) — [archive](milestones/v1.3-ROADMAP.md)
- 🔄 **v1.4 YouTube Downloads & Dashboard Filters** — Phases 20–23 (started 2026-05-14)

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

<details>
<summary>✅ v1.3 SuperAdmin Monitoring & TikTok Downloads (Phases 15–19.3) — SHIPPED 2026-05-13</summary>

**Milestone Goal:** A SuperAdmin can see every background job running on the platform in real time — sync runs, asset downloads, AI autofills, scoring — with progress bars, drill-in detail views, and full error tracebacks; TikTok asset download gap is closed.

- [x] **Phase 15: TikTok Asset Download** - Close the TikTok video and image download gap to unblock AI autofill and BrainSuite scoring (complete 2026-05-08)
- [x] **Phase 16: Job Persistence Schema** - PostgreSQL `background_jobs` table with indexes, autovacuum tuning, and cleanup job (complete 2026-05-08)
- [x] **Phase 17: Service Instrumentation** - Wire all four job types (sync, download, autofill, scoring) to write job records with progress (complete 2026-05-11)
- [x] **Phase 18: SSE Transport** - FastAPI streaming endpoint with keepalive heartbeats and connection lifecycle management (complete 2026-05-11)
- [x] **Phase 19: SuperAdmin Monitoring UI** - Angular job monitor at /configuration/jobs with real-time updates and drill-in detail panels (completed 2026-05-11)
- [x] **Phase 19.1: Close gap: BLOCKER-02+03** — null token race + EventSource leak in job-monitor.service.ts (complete 2026-05-13)
- [x] **Phase 19.2: Close gap: INSTR-05/MON-07** — move brainsuite_job_id to metadata_ so References panel shows it; drop orphaned platform_sync_run_id key (INSERTED) (completed 2026-05-13)
- [x] **Phase 19.3: Close gap: Phase 15** — add asset_url/video_source_url to _upsert_records ON CONFLICT exclusion + scoring_enabled guard on download path (INSERTED) (completed 2026-05-13)

</details>

### v1.4 YouTube Downloads & Dashboard Filters

**Milestone Goal:** YouTube and Google Ads video creatives download reliably in production via residential proxy + PO token plugin; the dashboard has all three creative filters working.

- [ ] **Phase 20: Proxy Download Infrastructure** — DV360 + Google Ads download via residential proxy with bgutil PO token plugin; cookieless-first retry order; credential redaction
- [x] **Phase 21: Proxy Admin UI** — SuperAdmin can configure and toggle residential proxy from /configuration/admin (complete 2026-05-15)
- [ ] **Phase 22: Dashboard Metadata + Account Filters** — Metadata autocomplete filter and ad account multi-select filter (full stack)
- [ ] **Phase 23: Dashboard Duration Filter + Backfill** — Video duration range slider with legacy asset backfill job (full stack)

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
**Goal**: SuperAdmins can view, filter, and drill into all background jobs in real time at /configuration/jobs, including progress bars, error tracebacks, and full output details
**Depends on**: Phase 18
**Requirements**: MON-01, MON-02, MON-03, MON-04, MON-05, MON-06, MON-07
**Success Criteria** (what must be TRUE):
  1. The /configuration/jobs page displays all active and recent jobs grouped by type (sync / download / autofill / scoring) and updates without a page refresh via SSE
  2. In-progress download and sync jobs show a determinate progress bar (e.g. "7 / 10 assets") that advances in real time
  3. Drilling into an autofill job shows the full Gemini field output (field names, determined values, raw API response) in a readable panel
  4. Drilling into a download job shows a manifest of downloaded assets with links to each file
  5. Drilling into a failed job shows the full error traceback (copyable to clipboard, truncated at 10 KB)
  6. Drilling into a scoring job shows per-asset score outcomes and any per-asset failures
  7. Every job detail view displays the internal job ID and any external API job IDs (e.g. BrainSuite job ID)
**Plans**: 6 plans

**Wave 1** *(parallel — no dependencies)*
- [x] 19-01-PLAN.md — Pydantic schemas (JobListItem + JobDetail) + 9 test stubs in test_jobs_api.py
- [x] 19-03-PLAN.md — JobMonitorService (SSE + in-memory Map + REST helpers) — MON-01, MON-02
- [x] 19-04-PLAN.md — Route + sidebar registration (/configuration/jobs + Job Monitor nav item)

**Wave 2** *(blocked on 19-01)*
- [x] 19-02-PLAN.md — REST endpoints (GET /jobs, GET /jobs/{id}, DELETE /jobs) + 9 passing tests — MON-01, MON-02, MON-05, MON-07

**Wave 3** *(blocked on 19-03 + 19-04)*
- [x] 19-05-PLAN.md — Job monitor page component (tabs, filter, table, progress bars, clear actions, SSE badge) — MON-01, MON-02

**Wave 4** *(blocked on 19-05)*
- [x] 19-06-PLAN.md — Job detail panel (slide-in, type-specific drill-ins, error traceback, copy buttons) — MON-03, MON-04, MON-05, MON-06, MON-07

### Phase 19.1: Close gap: BLOCKER-02+03 (INSERTED)
**Goal**: Fix null token race and EventSource leak in job-monitor.service.ts so that the SSE connection to /configuration/jobs reliably establishes on page load and does not leak server-side pubsub subscriptions
**Depends on**: Phase 19
**Requirements**: SSE-01, SSE-02
**Success Criteria** (what must be TRUE):
  1. Navigating to /configuration/jobs always shows "Live" SSE badge (no permanent "Disconnected" due to null token on first load)
  2. The reconnectAttempts counter resets after a successful reconnect
  3. No duplicate server-side pubsub subscriptions accumulate when connect() is called more than once per component lifecycle

### Phase 19.2: Close gap: INSTR-05/MON-07 (INSERTED)
**Goal**: brainsuite_job_id for scoring jobs moves from output JSONB to metadata_ so the References panel in the job detail view displays it; orphaned platform_sync_run_id removed from KNOWN_EXTERNAL_ID_KEYS
**Depends on**: Phase 19.1
**Requirements**: INSTR-05, MON-07
**Success Criteria** (what must be TRUE):
  1. After a scoring job completes, the job detail References panel shows brainsuite_job_id (not just in the per-asset scoring section)
  2. KNOWN_EXTERNAL_ID_KEYS in the frontend no longer includes platform_sync_run_id
  3. Existing scoring job records are unaffected; only new records land brainsuite_job_id in metadata_
**Plans**: 1 plan
Plans:

**Wave 1**
- [x] 19.2-01-PLAN.md — Add metadata merge to update_background_job + call with brainsuite_job_id after BrainSuite API returns; remove platform_sync_run_id from KNOWN_EXTERNAL_ID_KEYS; update test assertion (INSTR-05, MON-07)
**Plans**: 1 plan
Plans:
- [x] 19.2-01-PLAN.md — Add metadata_ brainsuite_job_id update to job_tracker + scoring_job; remove platform_sync_run_id from frontend constant; update test assertion

### Phase 19.3: Close gap: Phase 15 (INSERTED)
**Goal**: TikTok asset_url and video_source_url are protected from null during re-sync; asset download respects SystemConfig.scoring_enabled across all platforms
**Depends on**: Phase 19.2
**Requirements**: TKTOK-01, TKTOK-02
**Success Criteria** (what must be TRUE):
  1. A re-sync of an already-downloaded TikTok creative does not temporarily null asset_url or video_source_url in CreativeAsset
  2. When SystemConfig.scoring_enabled is false, no asset downloads are initiated for any platform (Meta, TikTok, Google Ads, DV360)
  3. The ON CONFLICT exclusion list in _upsert_records includes asset_url and video_source_url
**Plans**: 2 plans
Plans:

**Wave 1**
- [x] 19.3-01-PLAN.md — TDD stubs: 4 failing tests (upsert preservation × 2, download gate × 2) — TKTOK-01, TKTOK-02

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 19.3-02-PLAN.md — Add scoring_enabled gate to all 4 _run_*_asset_downloads functions in scheduler.py; run all 4 tests to GREEN — TKTOK-01, TKTOK-02
**Plans:** 2/2 plans complete
Plans:
- [x] 19.3-01-PLAN.md — Wave 1: Write failing test stubs (upsert invariant + scoring_enabled gate)
- [x] 19.3-02-PLAN.md — Wave 2: Add scoring_enabled gate to all 4 download functions in scheduler.py

---

### Phase 20: Proxy Download Infrastructure
**Goal**: DV360 and Google Ads video creatives download successfully on production hosts via residential proxy and bgutil PO token plugin, with credentials never written to logs
**Depends on**: Phase 19.3 (existing sync pipeline)
**Requirements**: PROXY-01, PROXY-02, PROXY-03, PROXY-04, PROXY-06
**Success Criteria** (what must be TRUE):
  1. A DV360 sync on a GCP Cloud Run host successfully downloads a video creative using the residential proxy — asset_url is populated in CreativeAsset
  2. A Google Ads sync on a GCP Cloud Run host successfully downloads a video creative using the same residential proxy path — asset_url is populated in CreativeAsset
  3. yt-dlp invokes the bgutil PO token plugin automatically for format URL requests without any per-video token code in the sync services
  4. The download retry sequence is: cookieless-with-proxy → primary-cookies-with-proxy → backup-cookies-with-proxy → fail; existing cookie slots are preserved and still function when proxy is disabled
  5. A grep across application logs after a proxy-enabled download run finds no occurrences of the proxy URL's embedded username or password
**Plans**: 2 plans
Plans:
- [x] 20-01-PLAN.md — Wave 0 test stubs + bgutil dep + SystemConfig proxy columns + Alembic migration (complete 2026-05-15)
- [x] 20-02-PLAN.md — Proxy injection into DV360 + Google Ads sync services (complete 2026-05-15)

**Wave Structure:**
- Wave 1: 20-01-PLAN.md (test stubs, schema, deps)
- Wave 2: 20-02-PLAN.md (sync service modifications — blocked on Wave 1)

### Phase 21: Proxy Admin UI
**Goal**: A SuperAdmin can enable or disable the residential proxy and configure the proxy URL from the /configuration/admin page without a code deploy
**Depends on**: Phase 20
**Requirements**: PROXY-05
**Success Criteria** (what must be TRUE):
  1. A SuperAdmin sees a "Residential Proxy" card in the /configuration/admin page with an enable/disable toggle and a proxy URL input field
  2. Saving a proxy URL encrypts and persists it in SystemConfig; the URL is never returned in any API response (only a masked indicator is shown)
  3. Toggling the proxy off immediately causes subsequent download attempts to skip proxy injection (no restart required)
  4. The proxy card is not visible to non-SuperAdmin users
**Plans**: 3 plans
Plans:

**Wave 1**
- [x] 21-01-PLAN.md — 3 SuperAdmin proxy-config endpoints (GET/PUT + POST test) + `_mask_proxy_url` helper + 8 pytest cases (PROXY-05)

**Wave 2** *(blocked on Wave 1)*
- [x] 21-02-PLAN.md — Residential Proxy card inserted as Section 1 of admin.component.ts (interfaces, state, methods, template, CSS) (PROXY-05)

**Wave 3** *(blocked on Waves 1 + 2)*
- [x] 21-03-PLAN.md — Visual UAT checkpoint: 7 acceptance criteria covering all 4 ROADMAP success criteria + D-04/D-05/D-07/D-08/D-09/D-10 (PROXY-05)

**UI hint**: yes

### Phase 22: Dashboard Metadata + Account Filters
**Goal**: Users can filter the creative grid by metadata field value using searchable autocomplete, and by one or more ad accounts using a multi-select filter
**Depends on**: Phase 20 (relies on composite index migration from Phase 20's schema work)
**Requirements**: DASH-01, DASH-02
**Success Criteria** (what must be TRUE):
  1. A user types at least 2 characters into the metadata filter and sees matching metadata values from their own organization only — no values from other organizations appear
  2. Selecting a metadata filter value narrows the creative grid to only assets that have that metadata value; clearing the filter restores the full grid
  3. A user can select multiple ad accounts from the filter menu and the creative grid shows creatives from all selected accounts simultaneously
  4. All active filters compose with AND logic and persist correctly across pagination clicks
  5. A "Clear filters" control resets all filter state and re-queries the grid
**Plans**: TBD
**UI hint**: yes

### Phase 23: Dashboard Duration Filter + Backfill
**Goal**: Users can filter the creative grid by video duration range using a dual-handle slider; legacy assets with NULL duration are backfilled asynchronously so the filter becomes progressively more useful
**Depends on**: Phase 22
**Requirements**: DASH-03
**Success Criteria** (what must be TRUE):
  1. A dual-handle duration range slider is visible in the dashboard filter row when at least one VIDEO asset exists in the grid
  2. Adjusting the slider range narrows the creative grid to assets whose video_duration falls within the selected range; assets with NULL duration are excluded from the filtered result set
  3. A callout note shows how many assets lack duration data (e.g. "X assets have no duration data and are excluded from this filter")
  4. An async background backfill job populates video_duration for legacy NULL-duration assets in batches without blocking sync or scoring pipelines
  5. The duration filter composes correctly with the metadata and account filters from Phase 22 (all three active simultaneously returns correct results)
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
| 18. SSE Transport | v1.3 | 2/2 | Complete | 2026-05-11 |
| 19. SuperAdmin Monitoring UI | v1.3 | 6/6 | Complete   | 2026-05-11 |
| 19.1. Close gap: BLOCKER-02+03 | v1.3 | 1/1 | Complete | 2026-05-13 |
| 19.2. Close gap: INSTR-05/MON-07 | v1.3 | 1/1 | Complete    | 2026-05-13 |
| 19.3. Close gap: Phase 15 | v1.3 | 2/2 | Complete    | 2026-05-13 |
| 20. Proxy Download Infrastructure | v1.4 | 0/2 | Planned | - |
| 21. Proxy Admin UI | v1.4 | 3/3 | Complete | 2026-05-15 |
| 22. Dashboard Metadata + Account Filters | v1.4 | 0/TBD | Not started | - |
| 23. Dashboard Duration Filter + Backfill | v1.4 | 0/TBD | Not started | - |

## Backlog

- **999.1** Dashboard metadata filter with autocomplete — built in Apr 2026 (commits 1d8edb6, aa9273f), lost in later session; recover from git history (conflicts with current dashboard.py/dashboard.component.ts) — **addressed in Phase 22**
- **999.2** Dashboard ad account multi-select filter — verify still present (last seen in commits e403eaf–d05999e); if lost, recover from git history — **addressed in Phase 22**
