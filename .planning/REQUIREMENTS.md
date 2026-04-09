# Requirements: BrainSuite Platform Connector v1.1

**Defined:** 2026-03-25
**Core Value:** A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.

## v1.1 Requirements

### Production Readiness (v1.0 Loose Threads)

- [x] **PROD-01**: BrainSuite API credentials (video and image apps) configured and verified in production environment
- [x] **PROD-02**: Google Ads OAuth consent screen verified as "Published" (not "Testing") to prevent 7-day refresh token expiry for production users

### BrainSuite Image Scoring

- [x] **IMG-01**: BrainSuite Static API endpoint, payload shape, and response schema confirmed via live discovery spike before any implementation begins
- [x] **IMG-02**: `ScoringEndpointType` enum (`VIDEO | STATIC_IMAGE`) assigned at asset sync time using a tested `(platform, content_type, file_extension)` lookup table — never inferred at scoring time
- [x] **IMG-03**: Image assets scored by the existing 15-minute APScheduler batch job (branch inside `run_scoring_batch()`, not a separate job)
- [x] **IMG-04**: Scored image creatives display score badge and Creative Effectiveness tab in the asset detail dialog (same UI as video)

### Historical Backfill

- [x] **BACK-01**: Admin API endpoint `POST /admin/backfill-scoring` queues all pre-v1.1 assets (both IMAGE and VIDEO) without scores for the live scoring pipeline
- [x] **BACK-02**: Backfill uses BackgroundTasks — not APScheduler — so it does not conflict with the live 15-minute scorer

### Score Trend Over Time

- [x] **TREND-01**: Append-only `creative_score_history` table with one row per asset per day, monthly range partitioning, and 90-day retention — schema finalized before first data is written
- [x] **TREND-02**: Score history written automatically by the scoring job after every COMPLETE result
- [x] **TREND-03**: Asset detail dialog includes a Score Trend tab with an ECharts line chart showing score over time (30-day default window; appropriate empty state when fewer than 2 data points exist)

### Top/Bottom Performer Highlights

- [x] **PERF-01**: Dashboard creative grid shows performer badge overlays using relative ranking (`PERCENT_RANK()`) — top 10% and bottom 10% — with a minimum 10-asset sample guard before any badges appear

### Score-to-ROAS Correlation

- [x] **CORR-01**: Dashboard includes a score-to-ROAS scatter chart (ECharts) with quadrant reference lines (Stars / Question Marks / Workhorses / Laggards) and hover tooltips showing thumbnail, score, ROAS, spend, platform
- [x] **CORR-02**: Scatter chart filters out assets below a configurable minimum spend threshold (default $10), treats null and zero ROAS distinctly, and caps Y-axis at the 99th percentile

### AI Metadata Auto-Fill

- [ ] **AI-01**: `ai_metadata_suggestions` table with `ai_inference_status` state machine (`PENDING | COMPLETE | FAILED`) — one row per asset; never writes to live metadata columns directly
- [ ] **AI-02**: `POST /assets/{id}/ai-suggest` triggers async Claude vision analysis and (if audio present) Whisper transcription; returns 202; client polls GET endpoint for status
- [ ] **AI-03**: Inference covers: Voice Over (yes/no), Voice Over Language, Language/Market, Asset Name — auto-applied when high confidence; Brand Names and Asset Stage — surfaced as suggestions requiring user review; Project Name — left empty (not inferable from creative content)
- [ ] **AI-04**: Asset detail dialog includes an "Auto-fill" button; clicking it triggers inference and shows pre-populated metadata fields with per-field confidence indicators; user explicitly confirms before any field is saved
- [ ] **AI-05**: Images fetched server-side and passed to Claude as base64 (MinIO presigned URLs not reachable by Claude API); images downsampled to 1568px max if over 4 MB before encoding
- [ ] **AI-06**: `ai_inference_status` guard prevents re-triggering inference on already-processed assets (prevents cost blowout)

### Performance Tab Redesign

- [ ] **UI-01**: Asset detail dialog performance tab re-laid out as tile/card grid matching the Creative Effectiveness tab visual style (replaces current tabular layout)

### In-App Notifications

- [ ] **NOTIF-01**: `notifications` table with `(id, org_id, type, payload JSONB, read, created_at)` — indexed for efficient polling queries
- [ ] **NOTIF-02**: Notifications created for: sync complete, sync failed, scoring batch complete, platform token expired
- [ ] **NOTIF-03**: Frontend polls `GET /notifications/unread` every 30 seconds — no SSE or WebSockets for v1.1
- [ ] **NOTIF-04**: Bell icon with unread badge in app header; clicking opens notification list via `MatMenu`; individual and bulk mark-as-read supported
- [ ] **NOTIF-05**: Toast (`MatSnackBar`) shown for high-priority events (sync failed, token expired) when user is active in the app

## Future Requirements (v1.2+)

- **NOTIF-v2-01**: Email/Slack notification delivery for sync failures and scoring batch completion
- **AI-v2-01**: Per-tenant AI inference daily spend cap with configurable limit
- **CORR-v2-01**: Per-platform ROAS correlation breakdown (requires sufficient data density per platform)
- **NOTIF-v2-02**: SSE/WebSocket real-time notification delivery (upgrade from polling)
- **TREND-v2-01**: Score trend comparison across multiple creatives on a single chart

## Out of Scope (v1.1)

| Feature | Reason |
|---------|--------|
| Email/Slack notifications | In-app only for v1.1; design `notifications` table to extend in v1.2 without schema migration |
| AI metadata fully replacing human input | Risk of hallucinated brand names / language codes silently corrupting BrainSuite submissions; suggestions + user confirmation is required |
| Per-platform ROAS correlation | Insufficient data density per platform in early tenants |
| Real-time WebSocket score updates | 30-second polling is invisible to users at minute-to-hour event frequency; SSE is 1–2 weeks vs 1–2 days |
| Automated creative retirement based on score | Too prescriptive; surface data, let users act |
| Mobile app | Web-first |

## Traceability

Which phases cover which requirements. Filled by roadmapper.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROD-01 | Phase 5 | Not started |
| PROD-02 | Phase 5 | Not started |
| IMG-01 | Phase 5 | Not started |
| IMG-02 | Phase 5 | Not started |
| IMG-03 | Phase 5 | Not started |
| IMG-04 | Phase 5 | Not started |
| BACK-01 | Phase 6 | Not started |
| BACK-02 | Phase 6 | Not started |
| TREND-01 | Phase 6 | Not started |
| TREND-02 | Phase 7 | Not started |
| TREND-03 | Phase 7 | Not started |
| PERF-01 | Phase 7 | Not started |
| UI-01 | Phase 7 | Not started |
| CORR-01 | Phase 8 | Not started |
| CORR-02 | Phase 8 | Not started |
| AI-01 | Phase 9 | Not started |
| AI-02 | Phase 9 | Not started |
| AI-03 | Phase 9 | Not started |
| AI-04 | Phase 9 | Not started |
| AI-05 | Phase 9 | Not started |
| AI-06 | Phase 9 | Not started |
| NOTIF-01 | Phase 10 | Not started |
| NOTIF-02 | Phase 10 | Not started |
| NOTIF-03 | Phase 10 | Not started |
| NOTIF-04 | Phase 10 | Not started |
| NOTIF-05 | Phase 10 | Not started |

**Coverage:**
- v1.1 requirements: 26 total
- Mapped to phases: 26/26 (100%)

---
*Requirements defined: 2026-03-25*
*Traceability filled: 2026-03-25 (roadmapper)*
