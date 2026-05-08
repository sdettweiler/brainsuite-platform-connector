# Requirements: BrainSuite Platform Connector

**Defined:** 2026-05-08
**Core Value:** A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.

## v1.3 Requirements

### TikTok Asset Download (TKTOK)

- [x] **TKTOK-01**: User sees TikTok video creatives in the dashboard after sync (video files downloaded to MinIO/S3, stored as video_url on CreativeAsset) — Validated in Phase 15 (2026-05-08)
- [x] **TKTOK-02**: User sees TikTok image creatives in the dashboard after sync (image files downloaded to MinIO/S3, stored as image_url on CreativeAsset) — Validated in Phase 15 (2026-05-08)

### Job Persistence Layer (JOBS)

- [ ] **JOBS-01**: Platform persists every background job run (sync, download, autofill, scoring) in PostgreSQL with type, org_id, status, progress_current, progress_total, output (JSONB), error, started_at, and ended_at fields
- [ ] **JOBS-02**: Job records older than 30 days are automatically cleaned up to prevent background_jobs table bloat

### Service Instrumentation (INSTR)

- [ ] **INSTR-01**: Platform sync runs (Meta, TikTok, Google Ads, DV360) create a job record and update status + progress as they execute
- [ ] **INSTR-02**: Asset download batches update job progress in real time (progress_current/progress_total, e.g. 7/10 assets downloaded)
- [ ] **INSTR-03**: AI autofill runs store the complete Gemini + Whisper field output (field name → determined value, raw response) in the job output JSONB field
- [ ] **INSTR-04**: BrainSuite scoring runs store per-asset outcomes (asset_id, status: scored/failed/skipped, score value) in the job output JSONB field
- [ ] **INSTR-05**: Every job record includes the internal job ID and any external API job IDs (e.g. BrainSuite job ID, platform sync run ID)

### SSE Real-Time Transport (SSE)

- [ ] **SSE-01**: Backend exposes a Server-Sent Events endpoint that streams job-updated events to connected SuperAdmin browser clients in real time
- [ ] **SSE-02**: SSE connections include keepalive heartbeats to prevent proxy timeouts and are cleaned up on client disconnect to prevent Uvicorn worker pool exhaustion

### SuperAdmin Monitoring UI (MON)

- [ ] **MON-01**: SuperAdmin can view all active and recent background jobs grouped by type (sync / download / autofill / scoring) at /configuration/admin
- [ ] **MON-02**: SuperAdmin can see per-run progress bars (current/total) for in-progress download and sync jobs that update in real time via SSE
- [ ] **MON-03**: SuperAdmin can drill into an autofill job and read the full Gemini field output (which fields were determined, their values, and the raw API response)
- [ ] **MON-04**: SuperAdmin can drill into a download job and see a manifest of downloaded assets with links to each asset
- [ ] **MON-05**: SuperAdmin can drill into any failed job and see the full error traceback (truncated at 10 KB, copyable to clipboard)
- [ ] **MON-06**: SuperAdmin can drill into a scoring job and see per-asset scores and any failures
- [ ] **MON-07**: Every job detail view displays the internal job ID and any external API job IDs

## Future Requirements

### External Notifications

- **NOTIF-01**: User receives Slack notification when token expires or sync fails
- **NOTIF-02**: User receives email notification when score threshold is crossed
- **NOTIF-03**: User can configure notification preferences per channel

### AI Inference Controls

- **AI-01**: Per-tenant daily AI inference spend cap configurable by admin

### SSE Scaling

- **SSE-03**: SSE transport upgraded to Redis pub/sub backend for deployments with 50+ concurrent SuperAdmin connections

### Account-Level Metadata Defaults

- **META-01**: Admin can configure connection-level metadata defaults (connection_metadata_defaults table) that pre-fill new asset metadata on sync
- **META-02**: Field mapping editor falls back to connection-level defaults when no asset-level value exists

## Out of Scope

- Real-time Slack/email notifications — in-app + SuperAdmin monitoring only for v1.3 (deferred NOTIF-01 through NOTIF-03)
- Mobile app — web-first
- WebSocket transport — SSE is sufficient for one-way job status push
- Redis pub/sub for SSE — DB polling sufficient at v1.3 scale (defer to v1.4 at 50+ concurrent SuperAdmins)
- Retry controls in the monitoring UI — SuperAdmin can observe and investigate, not re-trigger jobs from the UI
- Bulk job operations — individual job drill-in only
- Creative identity across platforms — deferred to v2
- Per-tenant AI inference daily spend cap — deferred (AI-01)

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| TKTOK-01 | Phase 15 | Complete (2026-05-08) |
| TKTOK-02 | Phase 15 | Complete (2026-05-08) |
| JOBS-01 | Phase 16 | Pending |
| JOBS-02 | Phase 16 | Pending |
| INSTR-01 | Phase 17 | Pending |
| INSTR-02 | Phase 17 | Pending |
| INSTR-03 | Phase 17 | Pending |
| INSTR-04 | Phase 17 | Pending |
| INSTR-05 | Phase 17 | Pending |
| SSE-01 | Phase 18 | Pending |
| SSE-02 | Phase 18 | Pending |
| MON-01 | Phase 19 | Pending |
| MON-02 | Phase 19 | Pending |
| MON-03 | Phase 19 | Pending |
| MON-04 | Phase 19 | Pending |
| MON-05 | Phase 19 | Pending |
| MON-06 | Phase 19 | Pending |
| MON-07 | Phase 19 | Pending |
