# Architecture Patterns — v1.1 Integration

**Project:** BrainSuite Platform Connector
**Milestone:** v1.1 Insights + Intelligence
**Researched:** 2026-03-25
**Confidence:** HIGH — based on direct codebase inspection

---

## Existing Architecture (Baseline)

Understanding the v1.0 boundary is required before specifying changes.

### Component Map

| Component | File(s) | Responsibility |
|-----------|---------|---------------|
| Scoring service | `app/services/brainsuite_score.py` | OAuth token, announce→upload→start flow, job polling, score extraction, viz persistence |
| Scoring job | `app/services/sync/scoring_job.py` | Batch driver: query UNSCORED VIDEOs, mark PENDING, call scoring service, write results |
| Scheduler | `app/services/sync/scheduler.py` | APScheduler singleton; registers `scoring_batch` (IntervalTrigger 15 min) + per-connection daily sync crons |
| Score model | `app/models/scoring.py` | `creative_score_results` — one row per asset, unique on `creative_asset_id`, JSONB `score_dimensions` |
| Asset model | `app/models/creative.py` | `creative_assets.asset_format` = IMAGE/VIDEO/CAROUSEL; one-to-one relationship to score_result |
| Dashboard endpoint | `app/api/v1/endpoints/dashboard.py` | Aggregated asset list with LEFT JOIN on score_results; `_get_performer_tag()` uses `total_score` thresholds |
| Scoring endpoint | `app/api/v1/endpoints/scoring.py` | rescore, status poll, detail, refetch |
| Metadata model | `app/models/metadata.py` + `app/models/creative.py` | `metadata_fields` + `asset_metadata_values`; `brainsuite_*` prefix keys drive scoring payload |
| NgRx store | `frontend/src/app/core/store/app.state.ts` | Currently only `auth` slice |
| Asset detail dialog | `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` | Metadata form + score tab; where AI auto-fill and score trend must integrate |

### Key Design Invariants to Preserve

1. **Session-per-operation** — no DB session held during HTTP calls. All three phases of the scoring job (fetch batch, write PROCESSING, write result) use separate short-lived sessions.
2. **`on_conflict_do_nothing` for UNSCORED injection** — prevents re-sync from resetting completed scores.
3. **`SCHEDULER_ENABLED` guard** — prevents duplicate job execution in multi-worker deployments.
4. **BrainSuite token singleton** — `brainsuite_score_service` is a module-level singleton; its token cache is shared across calls from the same worker process.
5. **Unique constraint** `uq_score_per_asset` on `creative_score_results(creative_asset_id)` — one scoring record per asset total.

---

## Feature Integration Analysis

### 1. BrainSuite Image Scoring

**Decision: Same scheduler, branching logic inside the existing batch job — not a separate job.**

Rationale: a second APScheduler job for images would duplicate the PENDING-lock and session-per-operation machinery, and would compete for the same BrainSuite rate limit. A clean branch inside `run_scoring_batch` is simpler and keeps rate-limit exposure in one place.

**What changes:**

`scoring_job.py` — the batch query currently hardcodes `asset_format == "VIDEO"`. Change to query both formats in a single batch (or two sequential sub-batches within the same run). Add format-detection before calling the scoring service.

`brainsuite_score.py` — add `submit_image_job_with_upload()` method that calls the Static image endpoint (different base path, different payload shape — exact shape TBD at Phase 5 spike). The existing `submit_job_with_upload()` targets `ACE_VIDEO/ACE_VIDEO_SMV_API`; image scoring will target a separate product path (e.g. `ACE_STATIC/ACE_STATIC_API` — to be confirmed against BrainSuite API docs at phase start). Both flows share `_get_token()`, `_api_post_with_retry()`, `_upload_to_brainsuite_s3()`, and `persist_and_replace_visualizations()`.

`build_scoring_payload()` — needs an `asset_type` parameter; IMAGE assets skip `voiceOver`/`voiceOverLanguage` and may omit video-specific `channel` mappings.

**New components:** none. Extension of existing service + job.

**Modified components:**
- `scoring_job.py`: remove `asset_format == "VIDEO"` filter; add `if asset.asset_format == "IMAGE": ... else: ...` branch
- `brainsuite_score.py`: add `submit_image_job_with_upload()` and `_announce_image_job()` (different endpoint path); extend `build_scoring_payload()` for static

**Data model changes:** none to `creative_score_results` — IMAGE and VIDEO scoring results share the same table and state machine. The `score_dimensions` JSONB shape will differ between image and video responses but is schema-free by design.

**Risk flag:** BrainSuite Static API endpoint/payload is not yet confirmed. Phase start requires a discovery spike against the actual API before any implementation.

---

### 2. AI Metadata Auto-Fill

**Decision: On-demand per request (FastAPI endpoint + BackgroundTasks), not a scheduler job.**

Rationale: AI inference is triggered by user action ("fill from creative"), not a background sweep. It is latency-sensitive from a UX perspective (user is waiting) but not so fast that it must be inline-synchronous. The BackgroundTasks pattern already used in `scoring.py` for `/refetch` is the right model: return `202 Accepted` immediately, run inference async, client polls for result.

Using APScheduler for this would be over-engineering — inference is ad-hoc, per-asset, user-initiated.

**What changes:**

Backend — new:
- `app/services/ai_metadata.py` — AI inference service. Takes asset bytes (image) or the stored thumbnail (video), calls Claude API (or configured provider), returns structured suggestions: `{language, market, brand_names, project_name, asset_name, asset_stage, voice_over, voice_over_language}`.
- New router: `POST /api/v1/assets/{asset_id}/ai-suggest` returns 202 and queues inference; `GET /api/v1/assets/{asset_id}/ai-suggest` returns status + suggestions when ready.

Backend — modified:
- `app/core/config.py` — add `ANTHROPIC_API_KEY`, `AI_MODEL` settings.

Frontend — modified:
- `asset-detail-dialog.component.ts` — add "Auto-fill" button to the metadata tab. On click: POST to `/ai-suggest`, show loading state, poll GET, populate form fields with suggestions. Fields remain editable before user saves. Suggestions are not auto-saved.

**Data model changes:**
- New `ai_metadata_suggestions` table for suggestion persistence (so dialog can reload suggestions on re-open without re-running inference):

```
ai_metadata_suggestions
  id             UUID PK
  creative_asset_id  UUID FK → creative_assets CASCADE
  status         VARCHAR(50)   -- PENDING | COMPLETE | FAILED
  suggestions    JSONB         -- {language, market, brand_names, ...}
  error_reason   TEXT
  created_at     TIMESTAMPTZ
  updated_at     TIMESTAMPTZ
  UNIQUE(creative_asset_id)    -- overwritten on re-run
```

**Video frame extraction:** use the stored thumbnail (already in S3) for v1.1. This avoids adding ffmpeg to the container. Frame extraction can be a later enhancement.

---

### 3. Score-to-ROAS Correlation View

**Decision: New endpoint reading existing tables — no schema changes.**

The data is already in `creative_score_results` (`total_score`) and `harmonized_performance` (`conversion_value`, `spend` → ROAS = `conversion_value / spend`). This is a pure query + new frontend view.

**What changes:**

Backend — new:
- `GET /api/v1/dashboard/score-roas` — returns per-asset `{asset_id, asset_name, total_score, total_roas, spend, platform, asset_format}` for the requested date range, filtered to assets that have COMPLETE score and performance data. JOIN: `creative_assets` → `creative_score_results` (WHERE status=COMPLETE) → `harmonized_performance` (aggregated by asset).

Frontend — new:
- New tab or panel in dashboard — scatter chart (ECharts already imported) with `total_score` on X axis, ROAS on Y axis, bubble size = spend.

**Data model changes:** none.

---

### 4. Top/Bottom Performer Highlights

**Decision: Compute in existing `/assets` endpoint query — visual overlay in existing grid.**

`_get_performer_tag()` already exists in `dashboard.py` and classifies assets as "Top Performer" / "Average" / "Below Average" using `total_score`. This is primarily a frontend change once the tag is confirmed in the API response.

**What changes:**

Backend: confirm `performer_tag` is included in the `CreativeAssetResponse` dict returned by `get_dashboard_assets`. If missing, add it (trivial one-liner).

Frontend — modified:
- `dashboard.component.ts` — add conditional CSS class or overlay badge on asset card/grid cell based on `performer_tag` value.

**Data model changes:** none.

---

### 5. Score Trend Over Time

**Decision: New append-only `creative_score_history` table — not versioned records on the existing table.**

Rationale: the current `creative_score_results` table has `UniqueConstraint("creative_asset_id", name="uq_score_per_asset")`. Versioning inside that table would require either removing this constraint (breaking the `on_conflict_do_nothing` injection pattern) or adding a version column (complicating all existing queries). An append-only history table is clean separation: `creative_score_results` stays as the "current score" source of truth; `creative_score_history` logs every scoring event.

**New table:**
```
creative_score_history
  id                UUID PK
  creative_asset_id UUID FK → creative_assets CASCADE
  organization_id   UUID FK → organizations
  total_score       FLOAT
  total_rating      VARCHAR(50)
  scored_at         TIMESTAMPTZ   -- timestamp from BrainSuite response
  brainsuite_job_id VARCHAR(255)
  INDEX (creative_asset_id, scored_at)
```

**What changes:**

Backend — modified:
- `scoring_job.py` — after writing a COMPLETE result to `creative_score_results`, also INSERT a row into `creative_score_history`. This is a fire-and-forget append; failure must not block the main score write (wrap in try/except).
- Add `GET /api/v1/assets/{asset_id}/score-history` endpoint returning the time series ordered by `scored_at`.

Frontend — modified:
- `asset-detail-dialog.component.ts` — add a "Score Trend" tab with an ECharts line chart. `LineChart` is already imported in that component.

**Data model changes:** one new table, one migration, one index. No changes to `creative_score_results`.

**Backfill note:** on first deploy, `creative_score_history` will be empty for existing scored assets. The backfill job (feature 7) can seed initial history entries from existing `creative_score_results.scored_at` + `total_score` values as a one-time migration step.

---

### 6. In-App Notifications

**Decision: Redis pub/sub → Server-Sent Events (SSE) for delivery; `notifications` DB table for persistence; NgRx slice for frontend state.**

Option comparison:

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| Polling (GET every N sec) | Trivially simple | Lag, extra DB reads, chatty | Acceptable but poor UX for async events |
| Redis pub/sub → SSE | Redis already deployed; SSE works over HTTP/1.1 through existing reverse proxy; no WebSocket upgrade needed | Persistent connection per tab; requires Redis subscription in async context | Recommended |
| WebSocket | Bidirectional, real-time | Requires WS upgrade support in reverse proxy; overkill for read-only push | Rejected |

**SSE implementation in FastAPI:**
```python
# GET /api/v1/notifications/stream
# Returns StreamingResponse with media_type="text/event-stream"
# Subscribes to Redis channel notifications:{org_id}
# Yields SSE events until client disconnects
```

**Event publishing from background jobs:**
```python
# After scoring completes / sync completes:
await redis_client.publish(f"notifications:{org_id}", json.dumps({
    "type": "scoring_complete",
    "asset_id": str(asset_id),
    "total_score": score_data["total_score"],
    "timestamp": datetime.utcnow().isoformat(),
}))
```

**New DB table:**
```
notifications
  id               UUID PK
  organization_id  UUID FK → organizations
  type             VARCHAR(50)    -- scoring_complete | sync_complete | scoring_failed | backfill_complete
  payload          JSONB
  read             BOOLEAN DEFAULT false
  created_at       TIMESTAMPTZ
  INDEX (organization_id, read, created_at)
```
Persist to DB so the bell icon shows correct unread count on page load and history is accessible regardless of whether SSE connection was open when the event fired.

**What changes:**

Backend — new:
- `app/api/v1/endpoints/notifications.py` — SSE stream endpoint (`GET /notifications/stream`), list endpoint (`GET /notifications`), mark-read endpoint (`PATCH /notifications/{id}/read` or bulk).

Backend — modified:
- `app/core/redis.py` — add async `publish()` helper (currently only used for OAuth sessions).
- `scoring_job.py` — publish event after COMPLETE/FAILED result.
- `scheduler.py` — publish event after each daily sync completes.

Frontend — new:
- `core/store/notifications/` — NgRx actions, reducer, effects, selectors.
- `core/services/notification.service.ts` — establishes `EventSource` connection; dispatches NgRx actions on received events.
- Bell icon component in header with unread count badge and dropdown.

Frontend — modified:
- `app.state.ts` — add `notifications: NotificationsState` to `AppState`.
- `header.component.ts` — mount bell component.

**Data model changes:** one new `notifications` table; Redis channel naming convention `notifications:{org_id}`.

---

### 7. Historical Backfill Scoring Job

**Decision: One-time triggered job exposed as an admin API endpoint — not an additional recurring APScheduler job.**

Rationale: a recurring scheduler job for backfill would permanently run alongside the regular 15-min scorer and compete for the same BATCH_SIZE lock window. A one-time trigger (admin endpoint) is predictable and safe.

**Conflict prevention with the regular scorer:**
Both the backfill and regular scorer query `WHERE scoring_status = 'UNSCORED'` and immediately mark assets PENDING. They cannot double-process the same asset because the first to execute the PENDING write wins. No additional mutex is needed. If both run simultaneously the effective batch size doubles, which is acceptable.

**What changes:**

Backend — new (minimal):
- `POST /api/v1/admin/backfill-scoring` — admin-only endpoint (org owner or superuser role required). Calls `run_scoring_batch()` in a BackgroundTask with an optional `limit` parameter. Optionally also inserts UNSCORED records for any assets that have no `creative_score_results` row at all (can happen for assets synced before the scoring migration).

Backend — modified: none beyond the image-scoring change in `scoring_job.py` (feature 1). Once image scoring lands, `run_scoring_batch` handles both IMAGE and VIDEO, so the backfill endpoint automatically covers all asset types.

**Data model changes:** none.

---

## Component Boundary Summary

### New Backend Components

| Component | Type | Feeds |
|-----------|------|-------|
| `app/services/ai_metadata.py` | Service | AI suggest endpoint |
| `app/api/v1/endpoints/notifications.py` | Router | Frontend SSE + bell |
| `app/api/v1/endpoints/admin.py` (or extend assets) | Router | Backfill trigger |
| `creative_score_history` table + model | DB | Score trend endpoint |
| `ai_metadata_suggestions` table + model | DB | AI suggest endpoint |
| `notifications` table + model | DB | Bell unread count + history |

### Modified Backend Components

| Component | What Changes |
|-----------|-------------|
| `scoring_job.py` | Remove VIDEO-only filter; add IMAGE branch; append to score history; publish Redis events |
| `brainsuite_score.py` | Add image job flow methods; extend payload builder for static assets |
| `app/core/config.py` | Add `ANTHROPIC_API_KEY`, `AI_MODEL`; note Redis publish |
| `app/core/redis.py` | Add async `publish()` helper |
| `dashboard.py` | Add score-ROAS aggregation endpoint; confirm `performer_tag` in response |
| `scoring.py` | Add score-history endpoint |

### New Frontend Components

| Component | Type | Notes |
|-----------|------|-------|
| `core/store/notifications/` (actions, reducer, effects, selectors) | NgRx slice | Full slice |
| `core/services/notification.service.ts` | Service | EventSource + NgRx dispatch |
| Bell icon component | UI | Badge + dropdown in header |
| Score-ROAS scatter panel | UI | ECharts scatter, mounts in dashboard |

### Modified Frontend Components

| Component | What Changes |
|-----------|-------------|
| `asset-detail-dialog.component.ts` | Add AI auto-fill button + loading state; add Score Trend tab (ECharts line chart — LineChart already imported) |
| `dashboard.component.ts` | Top/bottom performer overlays on grid cards; mount score-ROAS panel |
| `app.state.ts` | Add `notifications: NotificationsState` to `AppState` |
| `header.component.ts` | Mount bell component |

---

## Data Model Changes Summary

| Table | Change | Reason |
|-------|--------|--------|
| `creative_score_history` | NEW — append-only | Score trend over time without breaking existing score table |
| `ai_metadata_suggestions` | NEW — one row per asset | AI auto-fill suggestion persistence across dialog re-opens |
| `notifications` | NEW — per-org inbox | In-app notifications history + unread count on page load |
| `creative_score_results` | None | Existing table sufficient; shared by IMAGE + VIDEO |
| `creative_assets` | None | `asset_format` already distinguishes IMAGE/VIDEO |
| `metadata_fields` / `asset_metadata_values` | None | AI suggestions save via existing metadata save flow |

All three new tables are independent; they can be one Alembic migration or three separate ones. One migration is operationally simpler.

---

## Key Architectural Decisions

### Q1: Image vs Video Scoring Routing

**Same scheduler, branching logic inside `run_scoring_batch()`.**

Remove the `asset_format == "VIDEO"` where-clause. Add format branch inside the per-asset loop. Do not create a second APScheduler job — rate limit on BrainSuite is shared regardless of how many jobs submit.

### Q2: Where AI Inference Runs

**On-demand via FastAPI BackgroundTasks — not a scheduler job, not inline.**

Inline blocks for 5-15 seconds (unacceptable). APScheduler is wrong trigger model (user-initiated). BackgroundTasks is the standard FastAPI pattern already used in `scoring.py /refetch`: return `202`, client polls, correct.

### Q3: Score Trend Storage

**Append-only `creative_score_history` table.**

The `uq_score_per_asset` unique constraint and `on_conflict_do_nothing` injection pattern on `creative_score_results` must be preserved. History is a separate append concern that belongs in a separate table.

### Q4: Notifications Transport

**Redis pub/sub → SSE endpoint, with DB persistence.**

Redis is already deployed. SSE is simpler than WebSockets (no protocol upgrade, works through existing reverse proxy). DB persistence ensures correct unread count even when the browser was not connected when the event fired.

### Q5: Backfill Job Design

**Admin endpoint calling the existing batch function — not a new scheduler job.**

One-time trigger via `POST /api/v1/admin/backfill-scoring`. Conflict prevention via the existing PENDING state machine — no additional mutex required.

---

## Suggested Build Order

### Phase A: Image Scoring (prerequisite to backfill)
**Gating dependency:** BrainSuite Static API discovery spike must precede implementation.
- Extend `brainsuite_score.py` with image job flow
- Modify `scoring_job.py` to branch on `asset_format`
- Verify end-to-end with a real image asset

### Phase B: Historical Backfill
**Depends on:** Phase A (so backfill handles both formats).
- Admin endpoint `POST /admin/backfill-scoring`
- Inject UNSCORED records for assets missing score rows
- Run against pre-v1.1 image assets

### Phase C: Score Trend
**Depends on:** Phase A (scoring must work to generate history). Schema change is independent.
- `creative_score_history` table + migration
- Append history row in `scoring_job.py` after COMPLETE
- `GET /assets/{id}/score-history` endpoint
- Score Trend tab in asset detail dialog (ECharts line chart)

### Phase D: Top/Bottom Performer Highlights
**Depends on:** Phase A (scores must be present). Otherwise purely cosmetic with null data.
- Confirm `performer_tag` in API response schema
- Frontend: overlay badges on dashboard grid cards

### Phase E: Score-to-ROAS Correlation View
**Depends on:** Phase A (scores in DB). No schema changes.
- `GET /dashboard/score-roas` endpoint
- ECharts scatter panel in dashboard

### Phase F: AI Metadata Auto-Fill
**Depends on:** Nothing (standalone). Can be built in parallel with A-E.
- `ai_metadata_suggestions` table + migration
- `ai_metadata.py` service
- `/assets/{id}/ai-suggest` endpoint
- Auto-fill button in asset detail dialog metadata tab

### Phase G: In-App Notifications
**Depends on:** Phase A (scoring events) and sync events must exist to publish. Infrastructure (table, SSE, NgRx) can be scaffolded earlier, wired last.
- `notifications` table + migration
- Redis `publish()` helper
- SSE stream endpoint
- NgRx notifications slice + bell component
- Wire publish calls into `scoring_job.py` and `scheduler.py`

**Parallelization:** C, D, E, F are independent of each other once A is done. G infrastructure can be scaffolded during any phase; event wiring happens last.

---

## Pitfalls This Architecture Avoids

1. **Duplicate scoring via concurrent jobs** — single batch job with PENDING lock; image and video share one lock window.
2. **DB session held during BrainSuite HTTP calls** — session-per-operation preserved in image branch.
3. **AI inference blocking HTTP response** — BackgroundTasks pattern.
4. **Notification history lost when browser not connected** — DB persistence for notifications.
5. **Score history breaking existing dashboard queries** — separate append-only table; zero changes to `creative_score_results` queries.
6. **Backfill vs regular scorer race** — PENDING state machine is the natural mutex.
7. **BrainSuite token invalidated mid-backfill** — `_invalidate_token()` + retry in `_api_post_with_retry()` already handles this.

---

## Sources

- Direct inspection: `backend/app/services/sync/scoring_job.py`
- Direct inspection: `backend/app/services/brainsuite_score.py`
- Direct inspection: `backend/app/models/scoring.py`
- Direct inspection: `backend/app/models/creative.py`
- Direct inspection: `backend/app/services/sync/scheduler.py`
- Direct inspection: `backend/app/api/v1/endpoints/scoring.py`
- Direct inspection: `backend/app/api/v1/endpoints/dashboard.py`
- Direct inspection: `backend/app/core/config.py`
- Direct inspection: `backend/app/core/redis.py`
- Direct inspection: `frontend/src/app/core/store/app.state.ts`
- Direct inspection: `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts`
- Direct inspection: `backend/alembic/versions/e1f2g3h4i5j6_add_creative_score_results.py`
