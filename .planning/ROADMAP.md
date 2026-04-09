# Roadmap: BrainSuite Platform Connector

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-03-25) — [archive](milestones/v1.0-ROADMAP.md)
- 🚧 **v1.1 Insights + Intelligence** — Phases 5–10 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2026-03-25</summary>

- [x] Phase 1: Infrastructure Portability (3/3 plans) — completed 2026-03-20
- [x] Phase 2: Security Hardening (6/6 plans) — completed 2026-03-23
- [x] Phase 3: BrainSuite Scoring Pipeline (6/6 plans) — completed 2026-03-24
- [x] Phase 4: Dashboard Polish + Reliability (4/4 plans) — completed 2026-03-25

</details>

### 🚧 v1.1 Insights + Intelligence

- [x] **Phase 5: BrainSuite Image Scoring** — Production credentials verified; image assets scored alongside video in the existing pipeline (completed 2026-03-27)
- [x] **Phase 6: Historical Backfill + Score History Schema** — All pre-v1.1 assets scored; append-only history table seeded (completed 2026-03-30)
- [x] **Phase 7: Score Trend, Performer Highlights + Performance Tab** — Score trend chart live; top/bottom badges visible; performance tab redesigned (completed 2026-03-30)
- [x] **Phase 8: Score-to-ROAS Correlation** — Scatter chart with quadrant framing live in dashboard (completed 2026-03-31)
- [ ] **Phase 9: AI Metadata Auto-Fill** — Auto-fill button triggers Claude inference with confidence indicators and user confirmation
- [ ] **Phase 10: In-App Notifications** — Bell icon + unread badge; toasts for high-priority events; 30-second polling

## Phase Details

### Phase 5: BrainSuite Image Scoring
**Goal**: Every image creative is scored alongside video by the existing scoring pipeline, and users can see image scores and dimension breakdowns the same way they see video scores
**Depends on**: Phase 4 (v1.0 scoring pipeline)
**Requirements**: PROD-01, PROD-02, IMG-01, IMG-02, IMG-03, IMG-04
**Success Criteria** (what must be TRUE):
  1. BrainSuite production credentials (video app and image/static app) are configured and the app can submit to both endpoints without authentication errors
  2. Google Ads OAuth consent screen is confirmed "Published" so production users receive refresh tokens that do not expire after 7 days
  3. An image creative asset in the dashboard receives a score badge after the next 15-minute scheduler tick — without the user triggering anything
  4. The asset detail dialog for an image creative shows the score badge and Creative Effectiveness dimension tab, identical to the video experience
  5. Routing to the image vs. video BrainSuite endpoint is determined by an explicit `ScoringEndpointType` lookup table — not by string-matching `content_type` at scoring time
**Plans:** 4/4 plans complete
Plans:
- [x] 05-01-PLAN.md — Discovery spike + ScoringEndpointType enum + DB migration
- [x] 05-02-PLAN.md — BrainSuiteStaticScoreService + scoring pipeline wiring
- [x] 05-03-PLAN.md — Frontend UI (UNSUPPORTED badge, image metadata, CE tab)
- [x] 05-04-PLAN.md — Gap closure: imageMetadataFields getter, UNSUPPORTED CE notice, image-only metadata section
**UI hint**: yes

### Phase 6: Historical Backfill + Score History Schema
**Goal**: All pre-v1.1 assets that were never scored get scored via an admin-only backfill endpoint using BackgroundTasks (TREND-01 deferred per D-09 — scores are static)
**Depends on**: Phase 5 (image scoring must be wired before backfill covers both asset types)
**Requirements**: BACK-01, BACK-02, TREND-01
**Success Criteria** (what must be TRUE):
  1. An admin can call `POST /api/v1/scoring/admin/backfill` and all pre-v1.1 assets without scores are queued for the live pipeline — without duplicating BrainSuite API calls already in flight from the 15-minute scheduler
  2. Backfill runs via BackgroundTasks, not APScheduler, so it does not compete with the live scorer or interfere with `SCHEDULER_ENABLED` multi-worker deployments
  3. TREND-01 (creative_score_history table) intentionally deferred — BrainSuite scores are static (computed once per asset, never change); a trend chart would have at most one data point per asset
**Plans:** 1/1 plans complete
Plans:
- [x] 06-01-PLAN.md — Admin backfill endpoint + run_backfill_task + tests

### Phase 7: Score Trend, Performer Highlights + Performance Tab
**Goal**: Users can see how each creative's score has evolved over time, can immediately spot top and bottom performers in the grid, and find performance metrics presented in a cleaner card layout
**Depends on**: Phase 6 (history table must exist and be seeded before the trend chart has data)
**Requirements**: TREND-02, TREND-03, PERF-01, UI-01
**Success Criteria** (what must be TRUE):
  1. After each scoring batch run, a row is appended to `creative_score_history` for every asset that received a COMPLETE result — one row per asset per day maximum
  2. The asset detail dialog has a Score Trend tab with an ECharts line chart; a 30-day window is shown by default; an appropriate empty state appears when fewer than 2 data points exist
  3. Dashboard grid cards for the top 10% and bottom 10% of scored assets (by relative rank) display a performer badge overlay — and no badges appear when the scored asset pool is fewer than 10 assets
  4. The asset detail dialog performance tab presents metrics in a tile/card grid layout that visually matches the Creative Effectiveness tab style
**Plans:** 3/3 plans complete
Plans:
- [x] 07-01-PLAN.md -- Backend: score trend endpoint + PERCENT_RANK performer tagging + tests
- [x] 07-02-PLAN.md -- Frontend: score trend panel + performer badge relocation
- [x] 07-03-PLAN.md -- Frontend: Performance tab redesign (tile/card grid)
**UI hint**: yes

### Phase 8: Score-to-ROAS Correlation
**Goal**: Users can see a scatter chart that plots every scored creative's effectiveness score against its ROAS, with quadrant framing that tells them immediately which creatives to scale or cut
**Depends on**: Phase 6 (backfill must populate enough scored assets for the chart to be meaningful on first use)
**Requirements**: CORR-01, CORR-02
**Success Criteria** (what must be TRUE):
  1. The dashboard includes an ECharts scatter panel showing each creative as a point with score on the X-axis and ROAS on the Y-axis, with reference lines dividing the chart into Stars / Question Marks / Workhorses / Laggards quadrants
  2. Hovering a data point shows a tooltip with the creative's thumbnail, score, ROAS, spend, and platform
  3. Assets below a configurable minimum spend threshold (default $10) are excluded from the chart; null and zero ROAS are handled distinctly (neither silently excluded nor plotted together); the Y-axis is capped at the 99th percentile to prevent outlier distortion
**Plans:** 2/2 plans complete
Plans:
- [x] 08-01-PLAN.md — Backend: TDD correlation-data endpoint (unpaginated, zero-ROAS preserved)
- [x] 08-02-PLAN.md — Frontend: scatter chart drawer with quadrant framing + tooltips + spend threshold
**UI hint**: yes

### Phase 9: AI Metadata Auto-Fill
**Goal**: Users can trigger AI-powered inference on any creative to get pre-filled metadata fields with confidence indicators, review the suggestions, and confirm before anything is saved
**Depends on**: Phase 5 (MinIO asset fetch pattern confirmed; image scoring shows the server-side asset access model)
**Requirements**: AI-01, AI-02, AI-03, AI-04, AI-05, AI-06
**Success Criteria** (what must be TRUE):
  1. Clicking "Auto-fill" on the asset detail dialog triggers async Claude vision analysis (and Whisper transcription if audio is present); the UI shows a loading state and polls for completion — no fields are written yet
  2. When inference completes, the metadata form is pre-populated with AI suggestions; per-field confidence indicators are visible; fields flagged as requiring review (Brand Names, Asset Stage) are visually distinguished from auto-apply fields
  3. No metadata is saved to the live asset record until the user explicitly confirms; Project Name is always left blank (not inferred)
  4. Clicking "Auto-fill" on an asset that has already been analyzed does not trigger a new inference run — the `ai_inference_status` guard prevents re-triggering
  5. Images over 4 MB are downsampled server-side to 1568px on the long edge before being encoded as base64 and passed to Claude — the Claude API never receives a presigned MinIO URL
**Plans**: TBD
**UI hint**: yes

### Phase 10: In-App Notifications
**Goal**: Users are informed of sync completions, scoring batch results, and token expiry events via a bell icon inbox and high-priority toasts — without any polling logic, SSE, or WebSocket infrastructure beyond a simple 30-second GET interval
**Depends on**: Phase 5 (scoring pipeline must be stable before wiring notification events into it)
**Requirements**: NOTIF-01, NOTIF-02, NOTIF-03, NOTIF-04, NOTIF-05
**Success Criteria** (what must be TRUE):
  1. After a sync completes, a sync-failed event occurs, a scoring batch finishes, or a platform token expires, a notification row is written to the `notifications` table for the affected org
  2. The app header displays a bell icon; when there are unread notifications, the icon shows a numeric unread badge
  3. Clicking the bell icon opens a notification list (via `MatMenu`); the user can mark individual notifications or all notifications as read
  4. The frontend polls `GET /notifications/unread` every 30 seconds — no SSE or WebSocket connections are opened
  5. When the user is active in the app and a high-priority event occurs (sync failed, token expired), a `MatSnackBar` toast appears without requiring the user to open the notification inbox
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure Portability | v1.0 | 3/3 | Complete | 2026-03-20 |
| 2. Security Hardening | v1.0 | 6/6 | Complete | 2026-03-23 |
| 3. BrainSuite Scoring Pipeline | v1.0 | 6/6 | Complete | 2026-03-24 |
| 4. Dashboard Polish + Reliability | v1.0 | 4/4 | Complete | 2026-03-25 |
| 5. BrainSuite Image Scoring | v1.1 | 4/4 | Complete   | 2026-03-27 |
| 6. Historical Backfill + Score History Schema | v1.1 | 1/1 | Complete   | 2026-03-30 |
| 7. Score Trend, Performer Highlights + Performance Tab | v1.1 | 3/3 | Complete   | 2026-03-30 |
| 8. Score-to-ROAS Correlation | v1.1 | 2/2 | Complete   | 2026-03-31 |
| 9. AI Metadata Auto-Fill | v1.1 | 0/? | Not started | - |
| 10. In-App Notifications | v1.1 | 0/? | Not started | - |
