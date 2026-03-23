# Phase 3: BrainSuite Scoring Pipeline - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the BrainSuite API into an async scoring pipeline and surface scores in the dashboard. Covers: DB schema for scoring state machine, BrainSuite API client service, APScheduler scoring job, manual re-score trigger, frontend score badge with pending indicator, and "Creative Effectiveness" tab population in the existing asset-detail-dialog. Phase 4 handles sorting, filtering, thumbnails, and reliability polish.

</domain>

<decisions>
## Implementation Decisions

### BrainSuite API — Auth & Endpoints

- **Auth**: OAuth 2.0 Client Credentials flow
  - Token endpoint: `https://auth.brainsuite.ai/oauth2/token`
  - Encode `client_id:client_secret` as Base64, send as Basic auth with `grant_type=client_credentials`
  - Returns `{"token_type": "Bearer", "access_token": "..."}` — only one active token per client at a time
- **Video scoring endpoint**: `POST https://api.brainsuite.ai/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/create`
- **Workflow**: Create-Job (URL-based) — send a signed S3 URL per SCORE-03, no file upload needed
- **Status polling**: `GET https://api.brainsuite.ai/v1/jobs/{jobId}` until status is `Succeeded` or `Failed`
  - Status values: `Scheduled` → `Created` → `Started` → `Succeeded` | `Failed` | `Stale`
  - Poll every ~30 seconds while `Scheduled` or `Created`
- **Staging base URL**: `https://api.staging.brainsuite.ai` (use for dev/test)
- **Production base URL**: `https://api.brainsuite.ai`

### BrainSuite API — Request Payload

The Create-Job request body (`CreateJobInput`) has two top-level keys: `input` and `assets`.

**`assets` array** (one asset per job for our use case):
```json
{
  "assets": [
    {
      "assetId": "video",
      "name": "filename.mp4",
      "url": "<fresh signed S3 URL>"
    }
  ]
}
```

**`input` object** — all fields sourced from the asset's MetadataField values (see Metadata-driven API fields below):
```json
{
  "input": {
    "channel": "<mapped from platform+placement>",
    "assetLanguage": "<from metadata>",
    "brandNames": ["<from metadata>"],
    "projectName": "<from metadata, default: Spring Campaign 2026>",
    "assetName": "<from metadata, default: asset_name>",
    "assetStage": "<from metadata, default: finalVersion>",
    "voiceOver": "<from metadata, optional>",
    "voiceOverLanguage": "<from metadata, required if voiceOver set>"
  }
}
```

### BrainSuite API — Channel Mapping

Channel is auto-mapped from `creative_asset.platform` + `creative_asset.placement`:

| Platform | Placement | BrainSuite channel |
|---|---|---|
| META | `facebook_feed` | `facebook_feed` |
| META | `facebook_story` | `facebook_story` |
| META | `instagram_feed` | `instagram_feed` |
| META | `instagram_story` | `instagram_story` |
| META | `instagram_reels` / `instagram_reel` | `instagram_reel` |
| META | `audience_network_*` or unknown | `facebook_feed` (fallback) |
| TIKTOK | any | `tiktok` |
| GOOGLE_ADS | any | `youtube` |
| DV360 | any | `youtube` |

Normalization: lowercase + strip, `reels` → `reel`. Channel is overridable via metadata field if set.

### BrainSuite API — Metadata-Driven Fields

All BrainSuite API input fields are sourced from the asset's `AssetMetadataValue` records. The field's `name` attribute acts as the key mapping to the BrainSuite payload field name.

**Required fields** (seeded as `MetadataField` entries with `is_required=True` per organization):
- `brainsuite_brand_names` → `brandNames` (array — split by comma or newline)
- `brainsuite_asset_language` → `assetLanguage` (SELECT, enum values from BrainSuite lang list)

**Optional fields** (seeded as `MetadataField` entries with `is_required=False`):
- `brainsuite_project_name` → `projectName` (default: `Spring Campaign 2026`)
- `brainsuite_asset_name` → `assetName` (default: `asset_name`)
- `brainsuite_asset_stage` → `assetStage` (SELECT: `firstVersion`, `iteration`, `finalVersion`; default: `finalVersion`)
- `brainsuite_voice_over` → `voiceOver` (TEXT, optional)
- `brainsuite_voice_over_language` → `voiceOverLanguage` (SELECT, required only if voiceOver is set)

Seeding: a Alembic data migration (or startup seed) creates these `MetadataField` rows per existing organization. New orgs get them on first setup.

### BrainSuite API — Response / Score Shape

On `Succeeded`, the response `output` contains:
```json
{
  "output": {
    "legResults": [
      {
        "name": "...",
        "executiveSummary": {
          "rawTotalScore": 72.4,
          "totalScore": 72.4,
          "totalRating": "positive"
        },
        "categories": [
          { "name": "CategoryName", "rawScore": 68.1, "score": 68.1, "rating": "positive", "visualizations": {...} }
        ],
        "kpis": {
          "heatmovie": { "name": "...", "score": 55.2, "rating": "positive", "visualizations": [...] },
          "brandAttention": { "name": "...", "score": 78.1, "rating": "positive" },
          "engagingBeginning": { "name": "...", "score": 61.0, "rating": "medium" }
          // ... more kpis
        }
      }
    ]
  }
}
```

Store: `totalScore` as the primary score, full `output` blob as JSONB. Visualizations expire 1 hour after retrieval — do **not** store visualization URLs.

**Note:** The exact set of `categories` and `kpis` returned by the API must be confirmed via a real API response spike at the start of Phase 3 execution. The "Creative Effectiveness" tab metric selection depends on this spike output.

### Rate Limiting

- `x-ratelimit-limit`, `x-ratelimit-used`, `x-ratelimit-reset` (ISO 8601 UTC) headers on every POST response
- 429 → long backoff (wait until `x-ratelimit-reset` timestamp, not a fixed duration)
- 5xx → short exponential backoff (tenacity)
- 4xx (except 429) → no retry, mark asset as FAILED with error reason

### Data Model

**New table: `creative_score_results`** (SCORE-01)
- State machine: `UNSCORED` → `PENDING` → `PROCESSING` → `COMPLETE` | `FAILED`
- Fields: `creative_asset_id` (FK), `organization_id`, `scoring_status`, `brainsuite_job_id` (nullable), `total_score` (Float, nullable), `total_rating` (String, nullable), `score_dimensions` (JSONB — full `output` blob minus visualizations), `error_reason` (Text, nullable), `scored_at` (DateTime, nullable), `created_at`, `updated_at`
- One record per creative asset (upsert on re-score)
- Indexed on: `scoring_status` (for job query), `creative_asset_id`

**Dropped from `creative_assets`** (same Alembic migration):
- `ace_score`
- `ace_score_confidence`
- `brainsuite_metadata`

### Scoring Job Architecture

- **Scheduler**: Standalone APScheduler job, runs every 15 minutes, registered at startup alongside existing sync jobs
- **Batch size**: Up to 20 UNSCORED VIDEO assets per run (per SCORE-04); skip IMAGE assets (left as UNSCORED in Phase 3)
- **Job flow per batch**:
  1. Query up to 20 `creative_score_results` rows with `scoring_status=UNSCORED` where asset is VIDEO
  2. For each: generate fresh signed S3 URL, read metadata field values, build payload
  3. POST to BrainSuite create endpoint → set status `PENDING`, store `brainsuite_job_id`
  4. Poll each `PENDING`/`PROCESSING` job until `Succeeded`/`Failed`
  5. On success: store `total_score`, `score_dimensions`, set `COMPLETE`
  6. On failure: set `FAILED` with `error_reason`

- **Auto-queue on sync**: After platform sync inserts new `CreativeAsset` records, upsert a `creative_score_results` row with `scoring_status=UNSCORED` for each new VIDEO asset

- **Manual re-score**: `POST /api/v1/scoring/{asset_id}/rescore` endpoint → resets status to `UNSCORED` (picked up by next scheduler run). Also exposed via right-click context menu in the dashboard table ("Score now").

### Frontend — Score Display

- **Score badge in table**: New column in existing creative table showing:
  - `UNSCORED` / `FAILED`: grey dash or "–"
  - `PENDING` / `PROCESSING`: spinner + "Scoring…" chip
  - `COMPLETE`: score number badge (color-coded by totalRating: positive=green, medium=amber, negative=red)
- **Frontend polling**: `/api/v1/scoring/status?asset_ids=...` called only while PENDING/PROCESSING assets are visible on screen; stops when none remain (per SCORE-08)
- **Dimension breakdown**: "Creative Effectiveness" tab in existing `asset-detail-dialog`. Phase 3 populates it with `totalScore` + `categories[]` (names + scores + ratings). Exact metric selection and layout confirmed after first real API response spike.
- **Right-click context menu**: "Score now" option triggers `POST /api/v1/scoring/{asset_id}/rescore`; shows toast confirmation

### Claude's Discretion

- Tenacity retry configuration (backoff multiplier, max attempts for 5xx)
- Token caching strategy for BrainSuite Bearer token (cache until expiry vs. re-fetch per job run)
- Exact polling interval and max poll attempts before marking job as FAILED/STALE
- Score badge color thresholds (using totalRating enum from API: positive/medium/negative)
- `score_dimensions` JSONB schema (exact fields stored — determined from spike)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements
- `.planning/REQUIREMENTS.md` §BrainSuite Scoring — SCORE-01 through SCORE-08: full requirement list for this phase
- `.planning/ROADMAP.md` §Phase 3 — Success criteria (5 items) that define done

### BrainSuite API docs
- `brainsuite_api/API Docs General.txt` — Auth flow (OAuth 2.0 Client Credentials), Create-Job vs Announce-Job workflows, rate limiting headers, async poll-based retrieval, report output structure
- `brainsuite_api/SMV API Docs_compressed.txt` — ACE_VIDEO_SMV_API OpenAPI spec: Create-Job endpoint (`/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/create`), full `CreateJobInput` schema (channel enum, assetLanguage enum, brandNames, assetStage enum), response shape with `output.legResults[].executiveSummary` + `categories[]` + `kpis{}`

### Existing code to modify
- `backend/app/services/ace_score.py` — dummy scorer to be replaced; remove after real service is wired
- `backend/app/models/creative.py` — `CreativeAsset` model; drop `ace_score`, `ace_score_confidence`, `brainsuite_metadata` columns
- `backend/app/models/metadata.py` — `MetadataField` + `AssetMetadataValue`; seeded BrainSuite fields read here
- `backend/app/services/sync/scheduler.py` — register new scoring APScheduler job here
- `backend/app/services/sync/harmonizer.py` — after inserting new `CreativeAsset` rows, upsert `creative_score_results` with `UNSCORED`
- `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` — existing dialog with "Creative Effectiveness" tab to populate
- `frontend/src/app/features/dashboard/dashboard.component.ts` — existing table; add score badge column + polling logic

### Existing patterns to follow
- `backend/app/services/object_storage.py` — `generate_presigned_url()` method for fresh signed URLs (SCORE-03)
- `backend/app/services/sync/scheduler.py` — how to register APScheduler jobs; `SCHEDULER_ENABLED` guard (also required for scoring job)
- `backend/app/services/currency.py` — httpx async client with tenacity retry + 429 detection pattern to mirror
- `backend/app/core/config.py` — `Settings` pattern for new env vars (`BRAINSUITE_CLIENT_ID`, `BRAINSUITE_CLIENT_SECRET`, `BRAINSUITE_BASE_URL`)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/services/object_storage.py` → `generate_presigned_url(object_name, expiry_seconds)` — generates fresh signed S3 URLs per scoring request; call this immediately before POSTing to BrainSuite
- `backend/app/services/currency.py` → httpx async client with tenacity retry and 429 backoff — exact pattern to replicate for `BrainSuiteScoreService`
- `backend/app/models/metadata.py` → `MetadataField.name` + `AssetMetadataValue.value` — query by `field.name` LIKE `brainsuite_%` to build the API payload
- `backend/app/services/sync/scheduler.py` → `AsyncIOScheduler`, `startup_scheduler()` pattern — add scoring job with `IntervalTrigger(minutes=15)` alongside existing sync jobs

### Established Patterns
- APScheduler jobs: wrap in try/except, continue on per-asset failure, log with org/asset context
- `SCHEDULER_ENABLED` env var guard: scoring job must also check this flag to prevent duplicate execution in multi-worker deploy
- Async DB session: `async with get_async_session() as db:` pattern used throughout sync services
- `HTTPException(status_code=..., detail="...")` for API error responses (Phase 2 convention)

### Integration Points
- `harmonizer.py` sync completion → upsert `creative_score_results` UNSCORED for new VIDEO assets
- `dashboard.component.ts` table → add score badge column (new `score_status` + `total_score` in assets response DTO)
- `asset-detail-dialog.component.ts` "Creative Effectiveness" tab → populate from `GET /api/v1/scoring/{asset_id}`
- `main.py` lifespan → `startup_scheduler()` already called; scoring job registration happens inside that function

</code_context>

<specifics>
## Specific Ideas

- "Score now" right-click context menu in dashboard table — triggers `POST /api/v1/scoring/{asset_id}/rescore`
- "Creative Effectiveness" tab already exists in asset-detail-dialog — reuse it, do not create a new panel
- Score badge colors follow BrainSuite `totalRating` enum (positive/medium/negative/notAvailable) — not arbitrary thresholds
- Visualization URLs from the BrainSuite response expire after 1 hour — do NOT store them in `score_dimensions` JSONB
- API discovery spike required at Phase 3 start: submit one real video, capture the full `output` JSON, decide which `categories` and `kpis` to surface in the "Creative Effectiveness" tab before building the frontend component
- BrainSuite staging URL (`api.staging.brainsuite.ai`) for dev — make configurable via `BRAINSUITE_BASE_URL` env var

</specifics>

<deferred>
## Deferred Ideas

- Image scoring (ACE_STATIC_SOCIAL_STATIC_API) — future phase once image API docs are available
- Score-to-ROAS correlation view — DASH-v2-01 (v2 backlog)
- Score trend over time per creative — DASH-v2-03 (v2 backlog)
- Backfill scoring for historical assets — SCORE-v2-01 (v2 backlog)
- YouTube Shorts channel mapping (videos under 60s → `youtube_shorts`) — deferred, use `youtube` for now

</deferred>

---

*Phase: 03-brainsuite-scoring-pipeline*
*Context gathered: 2026-03-23*
