# Domain Pitfalls: v1.1 Feature Additions

**Domain:** Adding AI inference, image scoring, analytics views, notifications, and backfill to production Angular 17 + FastAPI + PostgreSQL system
**Researched:** 2026-03-25
**Confidence:** HIGH — pitfalls grounded in existing codebase patterns + verified against official docs and production issue reports

---

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, cost overruns, or broken production behavior.

---

### Pitfall 1: AI Inference Cost Blowout on Re-Trigger

**What goes wrong:**
The AI metadata inference call fires every time an asset is processed rather than once per asset per lifetime. With 1,000 existing assets in the backfill job plus ongoing syncs, and each image inference call costing ~$0.004 for a 1MP image using Claude Sonnet, a naive implementation that calls the API on every sync pass costs ~$4 per full re-scan of 1,000 images. At 15-minute intervals with 96 scheduler ticks per day, an unguarded inference call will cost hundreds of dollars per day per tenant.

**Why it happens:**
The BrainSuite scoring pipeline already has an `on_conflict_do_nothing` guard that prevents re-scoring completed assets. If inference is added as a step inside the same scoring loop without an equivalent guard, it runs on every scheduler tick regardless of whether inference was already done. The temptation is to co-locate inference with scoring because they share the same asset payload.

**Cost quantification (HIGH confidence — official Anthropic docs):**
- Image token formula: `tokens = (width_px * height_px) / 750`
- 1MP image ≈ 1,334 tokens ≈ $0.004 per inference at claude-sonnet-4-6 pricing ($3/M input tokens)
- 1,000 assets × $0.004 = $4 per full scan
- 96 scheduler ticks/day × $4 = $384/day if not guarded

**Prevention:**
1. Add an `ai_inference_status` column to the creative asset table — identical state machine to scoring: `PENDING → COMPLETE / FAILED`.
2. Use the same `on_conflict_do_nothing` + status-check guard before any inference call. Query `WHERE ai_inference_status IS NULL OR ai_inference_status = 'FAILED'` before dispatching.
3. Store inference results (inferred metadata) in the database immediately after a successful call — never re-infer unless the user explicitly requests it or the asset is replaced.
4. Add a hard per-tenant daily spend cap in the inference service (count calls in Redis, stop after configurable limit, surface warning in UI).

**Detection / warning signs:**
- Inference called inside any loop that runs on a scheduler tick without a status-check guard
- No `ai_inference_status` field on the asset model
- Claude API spend climbing linearly with the number of scheduler ticks in billing dashboard

**Phase:** AI metadata inference phase. Architecture decision must be made before any inference code is written.

---

### Pitfall 2: Image vs. Video Scoring Routed to Wrong BrainSuite Endpoint

**What goes wrong:**
The v1.0 scoring pipeline calls the video endpoint for all assets. When image scoring is added, the most common mistake is using `asset.content_type` (which may be `video/mp4`, `image/jpeg`, etc.) or `asset.asset_type` to branch between the Static (image) and video endpoint — but these fields are populated at sync time from ad platform API responses, which are inconsistent across Meta, TikTok, Google Ads, and DV360. A video thumbnail synced from Meta may arrive with `content_type = image/jpeg`. A GIF ad creative may be classified as `image/gif`. DV360 HTML5 ad creatives may have no content_type at all.

If the dispatch logic does not have an explicit, tested mapping for every (platform, asset_type, content_type) combination, some assets silently hit the wrong endpoint. The BrainSuite video endpoint will reject image payloads with a 4xx error. If tenacity's no-retry-on-4xx rule is already in place (which it is), the asset is immediately marked `FAILED` and never retried — silently producing no score.

**Why it happens:**
The scoring loop processes the queue without inspecting the actual file; it trusts the metadata field set during sync. That metadata was not set with scoring endpoint dispatch in mind — it was set with dashboard display in mind.

**Prevention:**
1. Define an explicit `ScoringEndpointType` enum: `VIDEO | STATIC_IMAGE`. Populate this field on every asset record at sync time, not at scoring time. Write a separate helper that maps `(platform, raw_content_type, file_extension)` → `ScoringEndpointType`.
2. The BrainSuite spike at the start of the image scoring phase must confirm: exactly which `content_type` values map to the Static endpoint vs. the video endpoint. Document in code as a lookup table, not implicit `if "video" in content_type` string matching.
3. Add a test fixture for each (platform, type) combination that asserts the correct endpoint is selected.
4. If `ScoringEndpointType` cannot be determined at sync time, mark the asset with `score_status = UNROUTABLE` and surface it in an admin view rather than silently failing.

**Warning signs:**
- Scoring dispatch logic uses `if "video" in asset.content_type`
- No test coverage for (TikTok, image/jpeg), (Meta, video/mp4), (DV360, null) combinations
- Sudden spike in `FAILED` score status after image scoring is deployed

**Phase:** BrainSuite image scoring phase. The routing table must be the first deliverable in the phase, before endpoint integration.

---

### Pitfall 3: Backfill Job Competing with Live 15-Minute Scorer

**What goes wrong:**
The backfill job and the live 15-minute scheduler both query `WHERE score_status = 'UNSCORED'` and submit assets to BrainSuite. Without coordination, they will simultaneously pick up the same assets, submit duplicate scoring requests, and attempt to write conflicting score results back. The existing `on_conflict_do_nothing` prevents duplicate row creation, but it does not prevent duplicate BrainSuite API calls — each one consumes API quota and may return slightly different scores (if BrainSuite is non-deterministic or the asset URL produces a different presigned URL on each call).

Worse: if the backfill job runs inside the same APScheduler instance as the live scorer (added as a one-shot job), `SCHEDULER_ENABLED=false` workers correctly skip the live scorer but also skip the backfill trigger — there is no mechanism to run the backfill exactly once across the fleet.

**Why it happens:**
The backfill is conceptually "the same thing as the live scorer, but for old assets." Adding it as a second scheduler job is the path of least resistance, but it shares the same queue with no coordination.

**Prevention:**
1. Introduce a `scoring_lock` field or a `score_submitted_at` timestamp on the asset record. The live scorer and backfill both update this field atomically when they claim an asset: `UPDATE assets SET score_submitted_at = now() WHERE id = :id AND score_submitted_at IS NULL`. Only one job wins the claim.
2. Run the backfill as a one-time triggered API endpoint (`POST /admin/backfill/start`) rather than an APScheduler job. This endpoint is only callable by admin users, runs in a background task, and respects the same claim mechanism as the live scorer. This avoids the `SCHEDULER_ENABLED` multi-worker problem entirely.
3. The backfill must apply the same tenacity retry policy, rate limiting, and session-per-operation pattern already established in the live scorer. Copy the pattern, not the job registration.
4. Add a progress table (`backfill_runs`: id, started_at, completed_at, total_assets, processed_assets, failed_assets) so the backfill is observable and idempotent — if it is interrupted and restarted, it resumes from where it stopped.

**Warning signs:**
- Backfill added as a second APScheduler `interval` or `cron` job alongside the live scorer
- No `score_submitted_at` or equivalent claim field on assets
- Two simultaneous BrainSuite API calls visible in logs for the same `asset_id`

**Phase:** Historical backfill phase. Must be designed before implementation — not retrofitted after.

---

### Pitfall 4: AI Inference Payload Size Blowing the 32 MB API Limit

**What goes wrong:**
Assets stored in MinIO/S3 may be high-resolution source files — ad creatives from Meta or TikTok uploads are often 5–20 MB. The inference service fetches the asset via a presigned URL, encodes it as base64, and includes it in the Claude API request body. A 5 MB image becomes ~6.7 MB base64. The Claude API standard endpoint limit is 32 MB total request size. A request with two or three large images, combined with the system prompt and metadata context, can exceed this limit and return a 413 error — which is a 4xx and therefore not retried by tenacity.

Separately, Claude internally resizes images larger than 1568px on the long edge before processing. This adds latency (time-to-first-token increases) with no quality benefit.

**Why it happens:**
The presigned URL fetch + base64 encode pattern mirrors how the BrainSuite video scoring pipeline was implemented (pass the URL). But BrainSuite fetches the asset server-side from the URL — Claude API with base64 source requires the client to include the full payload.

**Prevention:**
1. Before encoding: fetch asset headers (Content-Length) via a HEAD request. If the file exceeds 4 MB, downsample to a maximum of 1568px on the long edge and 1.15 megapixels before encoding. This is explicitly recommended by Anthropic docs for time-to-first-token optimization.
2. Prefer the Claude Files API (`beta.files.upload` + `file_id` reference) for assets that will be re-analyzed. This keeps the request payload small regardless of image size and avoids re-uploading the same file.
3. For video inference, never send the raw video binary. Extract a representative frame at a fixed timestamp (e.g., 1 second in) using ffmpeg or a lightweight frame extractor, then send the frame. Videos in MinIO can be large (100+ MB) — never pass video bytes directly to Claude.
4. Set `max_tokens` conservatively on inference calls (256–512 tokens is sufficient for metadata field inference) — this constrains output cost while not limiting the quality of structured JSON metadata responses.

**Warning signs:**
- Inference service fetches presigned URL and passes full binary directly without checking size
- No image downsampling step before base64 encoding
- `max_tokens` set to 1024+ on inference calls that only need metadata field values

**Phase:** AI metadata inference phase. Downsampling utility must be implemented before any inference calls against real production assets.

---

### Pitfall 5: Low-Confidence Inference Results Overwriting Good User Data

**What goes wrong:**
The AI inference result is written directly to the asset metadata fields (Language, Market, Brand Name, etc.) without asking the user. If the inference is wrong — which it will be for some percentage of assets — the user's existing metadata (potentially carefully entered by hand) is silently overwritten. Worse: if the inference runs on every sync and writes back to the database, user corrections are overwritten on the next scheduler tick.

This is the canonical "helpful AI feature that destroys user trust" failure mode. One wrong brand name inference on a key campaign asset is enough for a user to distrust the entire feature.

**Why it happens:**
The quickest implementation path writes the inference result directly to the same metadata columns used for display. There is no distinction between "human-entered" and "AI-inferred" provenance.

**Prevention:**
1. Never overwrite existing metadata fields that have been set by a user. Add a `metadata_source` enum (`USER_PROVIDED | AI_INFERRED | PLATFORM_API | EMPTY`) per metadata field (or at minimum a `metadata_confirmed` boolean on the asset).
2. Store inference results in a separate `ai_metadata_suggestions` table (or JSONB column), not in the live metadata columns. Surface them as suggestions in the UI with an "Apply" / "Dismiss" action.
3. Include a `confidence` score in the inference response (prompt Claude to return a confidence level for each field). Only auto-apply suggestions above a threshold (e.g., 0.85) — and only to fields that are currently empty, not fields with existing values.
4. If the inference API call fails or returns below-threshold confidence on all fields, the asset remains unchanged and the failure is logged — it does not block any other pipeline step.

**Warning signs:**
- Inference result written directly via `UPDATE assets SET language = :inferred_language`
- No separate storage for AI-suggested vs. user-confirmed metadata
- Inference runs on already-scored assets with populated metadata fields

**Phase:** AI metadata inference phase.

---

### Pitfall 6: Score Trend Table Growing Without Bound

**What goes wrong:**
A `creative_score_history` table that appends one row per asset per scoring run, with the 15-minute scheduler and hundreds of assets per tenant, produces:
- 1 row per asset × 96 ticks/day × 365 days = 35,040 rows/year per asset
- At 500 assets per tenant and 10 tenants: 175,200,000 rows/year

This is before backfill (which may produce scores for historical dates retroactively). Without a retention policy, this table becomes the largest table in the database within months, degrades dashboard query performance (the trend chart query must aggregate across all historical rows), and makes backups slow.

**Why it happens:**
The natural implementation appends a row every time the scoring pipeline writes a score. Partitioning and retention are "future problems" that never get prioritized.

**Prevention:**
1. Score trend does not need per-tick granularity. Store one row per asset per **day**, not per scoring run. If the score did not change since the last entry, do not insert a new row (`INSERT ... WHERE NOT EXISTS (SELECT 1 FROM score_history WHERE asset_id = :id AND date = :today AND score = :score)`).
2. Add a retention policy at the database level from day one. For an agency tool, 90 days of trend history is sufficient. Use PostgreSQL range partitioning on `scored_at` with monthly partitions — dropping a partition is near-instant and does not generate dead tuples, unlike a `DELETE` statement.
3. Index on `(asset_id, scored_at DESC)` — the primary query pattern for trend charts is "last N days for this asset."
4. For the backfill job: only insert one historical score per asset per day, not one per historical occurrence.

**Warning signs:**
- `INSERT INTO score_history` inside the main scoring loop with no deduplication check
- No `UNIQUE` constraint or conditional insert on `(asset_id, date)`
- No table partitioning plan or retention policy in the schema design

**Phase:** Score trend / analytics views phase. Schema design is the critical deliverable — cannot be easily changed after data is written.

---

### Pitfall 7: ROAS Correlation Chart Skewed by Zero and Missing Data Points

**What goes wrong:**
The correlation view plots BrainSuite score on one axis, ROAS on the other. Three data quality problems corrupt the chart:

1. **Zero ROAS:** Assets that have impressions and spend but zero conversions/revenue have ROAS = 0. These are not outliers — they are common in top-of-funnel creative. Plotting them collapses the regression line toward zero regardless of score, making high-score awareness creatives look like they perform the same as low-score assets.

2. **Missing ROAS:** Assets synced from platforms that do not report revenue (e.g., DV360 brand campaigns, TikTok accounts without pixel setup) have `NULL` ROAS. If the frontend filters these out silently, the correlation is computed only on direct-response campaigns, introducing survivorship bias.

3. **Low-spend outliers:** A creative with $0.50 spend and 3 conversions shows ROAS = 600x. One outlier point anchors the trendline and makes the correlation appear stronger than it is.

**Why it happens:**
Aggregation queries return whatever data is in the database. The chart component receives the raw records and passes them to a charting library. The charting library plots every point without awareness of spend significance.

**Prevention:**
1. Separate NULL ROAS and zero ROAS explicitly in the UI. NULL ROAS should show the asset in a separate "Untracked" section or with a distinct visual treatment — never silently excluded. Zero ROAS is valid and should be displayed, but the chart should label the "ROAS = 0" cluster explicitly.
2. Apply a minimum spend threshold filter (configurable, default: exclude assets with less than $10 total spend from the correlation scatter). Surface the filter threshold and the number of excluded assets in the chart legend ("Excluding 23 assets with < $10 spend").
3. Use a log scale on the ROAS axis (or Winsorize at the 95th percentile) to prevent extreme outliers from distorting the view. Provide a UI toggle between log and linear scale.
4. The SQL query must return spend alongside ROAS — the frontend needs spend to implement client-side filtering without a separate round trip.
5. Do not compute a correlation coefficient or trendline server-side and present it as "statistically significant." With typical agency account sizes (20–200 assets), the sample size is insufficient for reliable Pearson correlation. Either omit the trendline entirely or display it with an explicit "indicative only" label.

**Warning signs:**
- Correlation chart query does not return `total_spend` alongside `roas`
- NULL and zero ROAS treated identically (both filtered out or both included without distinction)
- No minimum spend filter at chart render time
- Trendline or correlation coefficient displayed without a confidence interval or sample size note

**Phase:** Score-to-ROAS correlation / analytics views phase.

---

### Pitfall 8: Notification System Complexity Creep

**What goes wrong:**
The in-app notification feature is scoped to bell + toasts for v1.1, with Slack/email explicitly out of scope. The temptation is to build a "proper" notification infrastructure: a `notifications` table, a WebSocket channel per user, a Redis pub/sub fan-out, event types, read/unread state, notification preferences, and an admin delivery panel. This takes 2–3x longer than the feature warrants and introduces new infrastructure components (long-lived WebSocket connections, Redis pub/sub) that must be operated and debugged.

For an in-app-only, sync/scoring status notification system, none of this complexity is required.

**Why it happens:**
"Notifications" triggers a mental model of enterprise notification systems. The pattern of WebSocket + Redis Streams + fan-out is heavily promoted in tutorials but is designed for chat applications and systems with thousands of concurrent users — not for a multi-tenant agency tool where one user is active at a time per organization.

**The correct scope for v1.1:**
- Backend: A `notifications` table with `(id, org_id, user_id, type, message, created_at, read_at)`. Insert rows from the scoring pipeline and sync service when key events occur (sync complete, scoring complete, error).
- Backend: A `GET /api/v1/notifications/unread` polling endpoint. No WebSockets. No pub/sub.
- Frontend: Angular polling service calls this endpoint every 30 seconds when the user is on the dashboard. Renders bell badge (unread count) and toast for new notifications.
- Frontend: `POST /api/v1/notifications/:id/read` to mark read.

This is 1–2 days of work, not 1–2 weeks. It handles the stated scope (sync and scoring events, in-app only) without any new infrastructure.

**Prevention:**
Do not add WebSockets, Redis pub/sub, PostgreSQL LISTEN/NOTIFY, or server-sent events to this project for v1.1 notifications. The polling approach is sufficient, observable, debuggable, and extends trivially to email/Slack in v2 by changing the delivery step in the same event insertion function.

**Warning signs:**
- Notification design document mentions WebSocket, SSE, or Redis pub/sub
- Notification design involves more than 2 new database tables
- Notification design involves a new Docker service or infrastructure component

**Phase:** Notifications phase. The architecture decision (polling vs. push) must be made and locked before implementation starts.

---

## Moderate Pitfalls

### Pitfall 9: BrainSuite API Discovery Spike Skipped or Rushed

**What goes wrong:**
The PROJECT.md explicitly flags: "Static image endpoint has different endpoint/payload — requires API discovery spike at Phase 5 start." If this spike is skipped to save time and the image endpoint is assumed to mirror the video endpoint, the implementation is built on a false assumption. The BrainSuite Static endpoint likely has a different:
- HTTP method or URL path
- Required metadata fields (aspect ratio, image format are different concepts for static vs. video)
- Response schema (may not return identical dimension names as video)
- Rate limit tier

A built-and-deployed image scoring pipeline that calls the wrong endpoint or sends malformed payloads wastes the entire phase deliverable.

**Prevention:**
1. Before writing any image scoring code: make one authenticated test call to the Static endpoint with a real image from MinIO. Confirm the request schema, response schema, HTTP status codes, and rate limit behavior.
2. Document the confirmed endpoint details in a `BRAINSUITE_API.md` reference file. This becomes the source of truth for the phase — not assumptions from the video endpoint.
3. If the BrainSuite API returns dimension names that differ between video and image responses, write a normalization layer that maps both to the same internal representation before storing in the database.

**Phase:** First deliverable of the BrainSuite image scoring phase.

---

### Pitfall 10: Backfill Job Holds DB Sessions During BrainSuite HTTP Calls

**What goes wrong:**
The existing scoring pipeline's critical pattern is "session-per-operation: never hold a DB session during HTTP calls." The backfill job, written under time pressure, opens a session to fetch a batch of unscored assets, then calls BrainSuite inside the same session context before committing. BrainSuite API calls take 2–10 seconds each. With 500 assets in the backfill queue, this holds DB connections for hours, exhausting the asyncpg pool and causing 500 errors for all other requests.

**Prevention:**
1. Fetch the batch of asset IDs (not full asset records) in one short-lived session. Close that session.
2. For each asset ID: open a fresh session → fetch asset → close session → call BrainSuite → open fresh session → write result → close session.
3. This is the exact pattern already established in the live scorer. The backfill must copy this pattern verbatim, not simplify it.

**Warning signs:**
- Backfill function opens a session with `async with db_session()` before the BrainSuite call loop, not inside it
- Connection pool utilization at 100% during backfill runs

**Phase:** Historical backfill phase.

---

### Pitfall 11: Top/Bottom Performer Highlights Using Absolute Score vs. Relative Rank

**What goes wrong:**
"Top performer" is implemented as `WHERE score >= 80` (absolute threshold). In an account where all scores are between 45 and 65 — common for early campaigns — no assets qualify as "top performers" and the highlights section is permanently empty. Conversely, in a strong-performing account where most assets score above 80, too many assets qualify and the highlights are not useful.

**Prevention:**
Top/bottom highlights should use relative rank, not absolute threshold:
- "Top performers" = top 10% by score within the organization's scored assets (or top N, whichever is smaller)
- "Bottom performers" = bottom 10% by score within the organization's scored assets

Use `PERCENT_RANK()` or `NTILE(10)` window functions. Add a minimum sample size guard: if fewer than 10 scored assets exist, show "Not enough data for highlights" rather than presenting misleading top/bottom labels.

**Phase:** Analytics views / dashboard redesign phase.

---

### Pitfall 12: AI Inference Prompt Returns Unstructured Text

**What goes wrong:**
The Claude API is prompted to "infer metadata fields" and returns a paragraph of prose instead of machine-parseable JSON. The inference service attempts to parse the response and either crashes (KeyError, AttributeError) or stores the raw prose in the suggestions table. This is a silent failure mode that shows users garbled "suggestions."

**Prevention:**
1. Use structured output via the Claude API's tool use / function calling feature to enforce a JSON schema. Define the exact metadata schema as a tool input schema — Claude will return structured JSON conforming to the schema.
2. Alternatively: include explicit JSON format instructions in the system prompt, set `temperature: 0` for determinism, and validate the response against a Pydantic model before storing. If validation fails, log the raw response and mark the inference as `FAILED` — do not store partial results.
3. Include a `confidence` field (0.0–1.0) for each inferred field in the schema. This enables threshold-based auto-apply logic.

**Phase:** AI metadata inference phase.

---

## Minor Pitfalls

### Pitfall 13: Presigned URL Expiry Mismatch for Inference

**What goes wrong:**
MinIO presigned URLs are generated with a short expiry (15–60 minutes, per the v1.0 signed URL pattern). If the AI inference service passes this presigned URL to the Claude API's URL image source (instead of base64), and there is any queue delay between URL generation and Claude fetching it, the URL may have expired by the time Claude makes the fetch request. This results in a 403 from MinIO that Claude treats as an image load failure.

**Prevention:**
Generate presigned URLs for inference with a longer TTL (1 hour minimum for queued inference). Or: fetch the asset bytes immediately upon queue pickup and use base64 source in the Claude request — this is safer for queued systems.

**Phase:** AI metadata inference phase.

---

### Pitfall 14: Score Trend Chart Shows Flat Line for Most Assets

**What goes wrong:**
BrainSuite scores are deterministic for a given asset — the same asset submitted twice returns the same score. Score trend will show a flat line for every asset that has not changed. This makes the "Score Trend" tab look broken or useless to users who do not understand that scores are stable unless the asset content changes.

**Prevention:**
1. Document in the UI tooltip: "Score trend changes when an asset is re-submitted to BrainSuite with updated content."
2. Consider whether the trend chart should only show assets where the score has actually changed at least once. If 95% of assets have flat lines, the trend tab is not useful as a primary analytics surface.
3. If trend is primarily useful for showing regression after a creative edit, scope it accordingly in the UX: "How has this creative's effectiveness changed over time?"

**Phase:** Score trend / analytics views phase — UX scoping before implementation.

---

## Phase-Specific Warning Summary

| Phase Topic | Pitfall | Severity | Mitigation |
|-------------|---------|----------|------------|
| BrainSuite image scoring | Wrong endpoint called for images vs. videos (Pitfall 2) | CRITICAL | Explicit routing table; spike before code |
| BrainSuite image scoring | API discovery spike skipped (Pitfall 9) | HIGH | Confirmed test call is phase gate |
| AI metadata inference | Cost blowout from re-triggering (Pitfall 1) | CRITICAL | `ai_inference_status` guard before every call |
| AI metadata inference | Payload too large for API (Pitfall 4) | HIGH | Downsample to 1568px max before encoding |
| AI metadata inference | Overwrites user-entered data (Pitfall 5) | HIGH | Suggestions table, never overwrite user data |
| AI metadata inference | Unstructured response crashes parser (Pitfall 12) | MEDIUM | Structured output / tool use enforced |
| AI metadata inference | Presigned URL expiry in queue (Pitfall 13) | LOW | 1-hour TTL or fetch-then-base64 |
| Historical backfill | Competes with live scorer (Pitfall 3) | CRITICAL | Claim lock on asset; admin endpoint not scheduler job |
| Historical backfill | DB session held during HTTP calls (Pitfall 10) | HIGH | Copy session-per-operation pattern from live scorer |
| Score trend | Unbounded table growth (Pitfall 6) | HIGH | One row/day/asset; monthly partitions; 90-day retention |
| Score trend | Flat line for most assets (Pitfall 14) | LOW | UX scope check before building |
| ROAS correlation | Zero/null ROAS skews chart (Pitfall 7) | HIGH | Explicit NULL/zero treatment; spend threshold filter |
| Top/bottom highlights | Absolute threshold produces empty sections (Pitfall 11) | MEDIUM | Relative rank (PERCENT_RANK) with minimum sample guard |
| Notifications | Over-engineering for in-app scope (Pitfall 8) | HIGH | Polling endpoint only; no WebSockets for v1.1 |

---

## Integration Gotchas Specific to v1.1

| Integration Point | Gotcha | Correct Pattern |
|-------------------|--------|-----------------|
| Claude API + MinIO assets | Passing MinIO presigned URL directly as Claude `url` source — MinIO may not be publicly accessible in Docker Compose deployment | Fetch bytes from MinIO via backend, encode as base64 for Claude request; never assume MinIO is internet-accessible |
| BrainSuite Static endpoint | Assuming same payload shape as video endpoint | Confirmed via spike: separate required fields for images (no video duration, different aspect ratio handling) |
| BrainSuite + tenacity | Retry policy applied globally to all BrainSuite calls, including new image endpoint | Confirm image endpoint returns same HTTP status codes as video; add image endpoint to retry policy explicitly |
| APScheduler + backfill | Backfill registered as APScheduler one-shot job — `SCHEDULER_ENABLED=false` workers skip it | Use admin API endpoint that triggers background task; bypass APScheduler entirely for one-time jobs |
| PostgreSQL + trend table | Adding partitioned table to existing schema via Alembic — partitioned tables cannot be created with `CREATE TABLE LIKE` | Write partition creation as raw DDL in Alembic migration; test migration on a copy of production schema before deploying |
| Angular + polling notifications | Polling interval creates memory leak if component is destroyed before interval clears | Use `takeUntilDestroyed()` or explicit `ngOnDestroy` unsubscription on the polling interval observable |
| Claude API + structured output | Tool use / function calling requires `anthropic-beta` header for some model versions | Pin the exact model version and beta header used during development; document in `.env.example` |

---

## Sources

- Anthropic Vision docs (official, HIGH confidence): https://platform.claude.com/docs/en/build-with-claude/vision
- Claude API image token formula `tokens = (width_px * height_px) / 750`: official Anthropic docs, verified 2026-03-25
- Claude Sonnet image pricing $3/M input tokens, $4.80/1k images at 1.19MP: official Anthropic pricing docs
- APScheduler `max_instances`, `coalesce`, `misfire_grace_time` — concurrent job pitfalls: https://apscheduler.readthedocs.io/en/3.x/userguide.html
- APScheduler duplicate execution real production issue: https://github.com/agronholm/apscheduler/issues/356
- PostgreSQL range partitioning for time-series, instant partition drop vs. DELETE: https://www.postgresql.org/docs/current/ddl-partitioning.html
- Notification systems: polling vs. WebSocket vs. SSE — no WebSocket needed for simple in-app notifications: https://hexshift.medium.com/real-time-notifications-with-fastapi-websockets-and-postgres-listen-notify-f26dbb9fe3e2
- ROAS data quality and skewed correlation: https://www.linkedin.com/advice/0/what-main-challenges-pitfalls-measuring
- Statistical correlation with skewed/outlier data: https://pmc.ncbi.nlm.nih.gov/articles/PMC5079093/
- FastAPI SQLAlchemy session leak in background jobs: https://dev.to/akarshan/asynchronous-database-sessions-in-fastapi-with-sqlalchemy-1o7e
- FinOps for Claude API at scale — cost blowout risk: https://www.cloudzero.com/blog/finops-for-claude/

---
*Pitfalls research for: v1.1 feature additions — BrainSuite image scoring, AI inference, analytics views, notifications, backfill*
*Researched: 2026-03-25*
*Supersedes v1.0 pitfalls in this file for new features; v1.0 pitfalls (OAuth, JWT, APScheduler multi-worker) remain addressed as of 2026-03-25*
