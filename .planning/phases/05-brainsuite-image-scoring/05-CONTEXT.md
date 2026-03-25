# Phase 5: BrainSuite Image Scoring - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire image creatives into the existing BrainSuite scoring pipeline using the Static API (ACE_STATIC_SOCIAL_STATIC_API). Covers: discovery spike to confirm Static endpoint/payload/schema, `ScoringEndpointType` enum + lookup table populated at sync time, `BrainSuiteStaticScoreService` class, branch inside the 15-min scoring scheduler, `UNSUPPORTED` status for non-Meta image platforms, two new image-specific MetadataFields, and same score badge/CE tab UI as video. PROD-01/02 verification also in this phase.

</domain>

<decisions>
## Implementation Decisions

### Image API Workflow

- **D-01:** Use **Announce→Upload→Start** workflow for image scoring — same as the video scorer. Do NOT use Create-Job (URL-based) even though Static API supports it. Consistency with established pattern takes priority over simplicity.
- **D-02:** **One leg per scoring job** — each image asset gets its own BrainSuite Static job. Static API supports up to 10 legs but we use 1 to match video's one-asset-per-job model and simplify error handling.
- **D-03:** Implement a **separate `BrainSuiteStaticScoreService` class** (e.g. `backend/app/services/brainsuite_static_score.py`) alongside the existing `BrainSuiteScoreService`. Do not extend or modify the video class — different endpoints, different payload shape (`legs[]` + `staticImage{}` vs `assets[]`), clean separation.
- **D-04:** The Announce step for images uses: `POST /v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/announce` with `input{}` containing `channel`, `projectName`, `assetLanguage`, `iconicColorScheme` (default: `"manufactory"`), and `legs[]` with `staticImage{assetId, name}`. Upload and Start steps follow the same pattern as video.
- **D-05:** Areas of Interest (`areasOfInterest`) are **NOT submitted** in Phase 5. The `staticImage` object is sent without AOI fields. See Deferred Ideas for v1.2 AOI implementation plan.

### Unsupported Platform Handling

- **D-06:** Add `UNSUPPORTED` as a new value to the `scoring_status` enum (alongside UNSCORED, PENDING, PROCESSING, COMPLETE, FAILED). Assigned at sync time via the `ScoringEndpointType` lookup table when an image creative comes from a platform the Static API doesn't support (TikTok, Google Ads, DV360 — Static API only accepts `"Facebook"` or `"Instagram"` channels).
- **D-07:** Dashboard display for `UNSUPPORTED`: **grey dash** (same visual as UNSCORED) with an **info tooltip** on hover: `"Image scoring not supported for this platform"`. No new chip or badge needed — minimal UI change.
- **D-08:** `UNSUPPORTED` assets are excluded from the scheduler's scoring batch query — they will never be picked up for scoring.

### ScoringEndpointType Lookup Table

- **D-09:** `ScoringEndpointType` enum values: `VIDEO`, `STATIC_IMAGE`, `UNSUPPORTED` (UNSUPPORTED covers: IMAGE from non-Meta platforms, CAROUSEL assets, and any format not yet mapped).
- **D-10:** Lookup is keyed on `(platform, asset_format, file_extension)`. Source of truth for routing is `creative_asset.asset_format` (IMAGE / VIDEO / CAROUSEL) + `creative_asset.platform`. `file_extension` is a tiebreaker for edge cases. Populated at sync time in `harmonizer.py` — **never inferred at scoring time**.
- **D-11:** Lookup table (initial mapping):

  | platform | asset_format | → ScoringEndpointType |
  |---|---|---|
  | META | VIDEO | VIDEO |
  | META | IMAGE | STATIC_IMAGE |
  | TIKTOK | VIDEO | VIDEO |
  | TIKTOK | IMAGE | UNSUPPORTED |
  | GOOGLE_ADS | VIDEO | VIDEO |
  | GOOGLE_ADS | IMAGE | UNSUPPORTED |
  | DV360 | VIDEO | VIDEO |
  | DV360 | IMAGE | UNSUPPORTED |
  | any | CAROUSEL | UNSUPPORTED |

### Image-Specific Metadata Fields

- **D-12:** Add **two new `MetadataField` rows** (seeded per organization, image-only context):
  - `brainsuite_intended_messages` → `intendedMessages` (TEXT area, one message per line; split on newline when building payload array; max 50 words per item; optional)
  - `brainsuite_iconic_color_scheme` → `iconicColorScheme` (SELECT; valid enum values confirmed during discovery spike; default: `"manufactory"`)
- **D-13:** `brandValues` is **NOT** added as a metadata field in Phase 5 — omit from the Static API payload entirely (field is optional; no user input needed).
- **D-14:** These new metadata fields are image-specific — surface them in the asset detail dialog metadata tab only when `asset_format = IMAGE`. Do not show on video assets.

### Production Credentials (PROD-01)

- **D-15:** The **same** `BRAINSUITE_CLIENT_ID` / `BRAINSUITE_CLIENT_SECRET` authenticates against both the Video and Static endpoints. No new env vars needed.
- **D-16:** PROD-01 deliverable: during the discovery spike (IMG-01), submit one real image job using existing credentials against the Static endpoint. Confirm authentication succeeds. Document result (endpoint, auth success, sample response) in `BRAINSUITE_API.md`.

### Google Ads OAuth (PROD-02)

- **D-17:** PROD-02 is a manual verification step: confirm the Google Ads OAuth consent screen is in "Published" (not "Testing") status in Google Cloud Console. No code changes required. Document verification result in a checklist item or comment in `BRAINSUITE_API.md` or a new `PRODUCTION_CHECKLIST.md`.

### Claude's Discretion

- Static API job polling interval and timeout (same tenacity/poll pattern as video — Claude mirrors that)
- Token caching for `BrainSuiteStaticScoreService` (same 50-minute cache pattern as video)
- Exact `iconicColorScheme` valid enum values — confirmed from discovery spike before seeding MetadataField options
- `intendedMessages` UI widget in asset detail dialog (textarea with hint text vs. tag-input component)
- Exact file where `ScoringEndpointType` enum + lookup table live (new `enums.py` or inline in `creative.py`)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements
- `.planning/REQUIREMENTS.md` §BrainSuite Image Scoring — IMG-01 through IMG-04: full requirement list
- `.planning/REQUIREMENTS.md` §Production Readiness — PROD-01, PROD-02
- `.planning/ROADMAP.md` §Phase 5 — Success criteria (5 items)

### BrainSuite API docs
- `brainsuite_api/API Docs General.txt` — Auth flow (OAuth 2.0 Client Credentials), async poll-based retrieval, rate limiting headers
- `brainsuite_api/SMS_api_docs.md` — ACE_STATIC_SOCIAL_STATIC_API OpenAPI spec: Announce, Upload, Start endpoints; full `AnnounceJobInput` schema (legs[], staticImage{}, channel enum "Facebook"|"Instagram", iconicColorScheme, intendedMessages, brandValues); response shape
- `brainsuite_api/SMV API Docs_compressed.txt` — ACE_VIDEO_SMV_API spec (reference for how video announce/upload/start works — mirror this pattern for Static)

### Prior phase context (carry-forward decisions)
- `.planning/phases/03-brainsuite-scoring-pipeline/03-CONTEXT.md` — video scoring architecture: token management, announce→upload→start flow, rate limiting strategy, `creative_score_results` state machine, channel mapping, score extraction
- `.planning/phases/04-dashboard-polish-reliability/04-CONTEXT.md` — score badge display patterns, existing filter/sort infrastructure

### Existing code to modify
- `backend/app/services/brainsuite_score.py` — reference implementation for auth, polling, rate limiting; do NOT modify — use as pattern for the new static service
- `backend/app/models/creative.py` — `CreativeAsset.asset_format` field (IMAGE/VIDEO/CAROUSEL); add `ScoringEndpointType` enum or reference
- `backend/app/services/sync/harmonizer.py` — after inserting new `CreativeAsset` rows, populate `endpoint_type` on `creative_score_results` upsert
- `backend/app/services/sync/scheduler.py` — add image scoring branch inside `run_scoring_batch()` referencing `ScoringEndpointType`
- `backend/app/models/metadata.py` — seed two new `MetadataField` rows for image-only fields
- `backend/app/core/config.py` — no new env vars; verify `BRAINSUITE_CLIENT_ID`/`BRAINSUITE_CLIENT_SECRET` cover Static endpoint
- `frontend/src/app/features/dashboard/dashboard.component.ts` — handle `UNSUPPORTED` status in score badge display (grey dash + tooltip)
- `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` — show new image-only metadata fields conditionally

### Existing patterns to follow
- `backend/app/services/brainsuite_score.py` — `_get_token()`, `_check_rate_limit_headers()`, tenacity retry, job polling loop — mirror all of these in `BrainSuiteStaticScoreService`
- `backend/app/services/sync/scheduler.py` — `SCHEDULER_ENABLED` guard (must be applied to image scoring branch too)
- `backend/app/core/config.py` — `Settings` pattern for any new env vars

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/services/brainsuite_score.py` → `BrainSuiteScoreService` — complete reference implementation: `_get_token()` (50-min cache), `_check_rate_limit_headers()` (429 → wait until reset), `_announce_job()` / `_upload_asset()` / `_start_job()` / `_poll_job()` — replicate this structure for `BrainSuiteStaticScoreService`
- `backend/app/services/object_storage.py` → `generate_presigned_url()` + `download_file()` — used to fetch image bytes before uploading to BrainSuite
- `backend/app/models/metadata.py` → `MetadataField` + `AssetMetadataValue` — add two new rows for image-specific fields; existing query pattern (`field.name LIKE 'brainsuite_%'`) already reads these

### Established Patterns
- `scoring_status` state machine: UNSCORED → PENDING → PROCESSING → COMPLETE | FAILED — adding `UNSUPPORTED` as a terminal state (never transitions)
- APScheduler job: wrap in try/except, per-asset failure continues batch, `SCHEDULER_ENABLED` guard
- Async DB session: `async with get_async_session() as db:` pattern — session-per-operation, never held during HTTP calls

### Integration Points
- `harmonizer.py` sync completion → upsert `creative_score_results` with `endpoint_type` field (new column) set from lookup table
- `run_scoring_batch()` in scheduler → branch: if `endpoint_type = VIDEO` → existing video path; if `endpoint_type = STATIC_IMAGE` → new static path; if `endpoint_type = UNSUPPORTED` → skip
- `creative_score_results` table needs new `endpoint_type` column (Alembic migration)
- Dashboard score badge: add `UNSUPPORTED` case → grey dash + tooltip (alongside existing UNSCORED/PENDING/COMPLETE/FAILED cases)

</code_context>

<specifics>
## Specific Ideas

- `BrainSuiteStaticScoreService` lives in `backend/app/services/brainsuite_static_score.py` — separate file, not mixed into video scorer
- Static API payload structure for Announce: `input.legs[0].staticImage = {assetId: "leg1", name: "filename.jpg"}` — no `url` in announce step (Announce→Upload→Start flow)
- `brainsuite_intended_messages` MetadataField: textarea, split on newlines to produce the `intendedMessages` array; each item validated at max 50 words before submission
- `iconicColorScheme` valid values must be confirmed from discovery spike — default `"manufactory"` is documented; add as SELECT MetadataField after enum values are confirmed
- PROD-02: verify Google Ads consent screen status in Google Cloud Console → OAuth consent screen → Publishing status. No code change.
- IMG-01 discovery spike must be the **first deliverable** — submit one real image, capture full response JSON, confirm Static endpoint URL, confirm auth works with existing credentials, confirm `output` shape matches or differs from video's `legResults[]` structure

</specifics>

<deferred>
## Deferred Ideas

### Areas of Interest (AOI) — v1.2

Undocumented BrainSuite Static API feature. Not submitted in Phase 5 — the `staticImage` object is sent without `areasOfInterest`.

**v1.2 deliverables (two things):**
1. **LLM Vision auto-detection** — Use a vision model to auto-detect AOI bounding boxes from image content, pre-populating the AOI fields before submission
2. **Bounding box UI** — UI for users to adjust, edit, or manually draw bounding boxes on the image to define AOIs

**AOI payload syntax (for v1.2 reference):**
```json
"staticImage": {
  "areasOfInterest": [
    {
      "x": 33,
      "y": 364,
      "width": 451,
      "height": 255,
      "label": "brand-logo"
    }
  ],
  "assetId": "leg1-pack"
}
```

**Supported AOI label values:**
- `"brand-logo"` — Brand
- `"flexible-3"` — Product
- `"flexible-4"` — Key Message
- `"flexible-2"` — Call-to-Action
- `"default"` — Other Areas of Interest

### brandValues metadata field
Not adding `brainsuite_brand_values` as a MetadataField in Phase 5. Field is optional in Static API and omitted from payload. Can be added in a future phase if agencies need it.

</deferred>

---

*Phase: 05-brainsuite-image-scoring*
*Context gathered: 2026-03-25*
