# Phase 5: BrainSuite Image Scoring - Research

**Researched:** 2026-03-25
**Domain:** BrainSuite Static API integration, SQLAlchemy enum migration, APScheduler batch branching, Angular conditional UI
**Confidence:** HIGH — all findings verified against actual codebase and official API docs

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Image API Workflow**
- D-01: Use Announce→Upload→Start workflow for image scoring — same as video. Do NOT use Create-Job even though Static API supports it.
- D-02: One leg per scoring job — each image asset gets its own BrainSuite Static job. Static API supports up to 10 legs but use 1 to match video model.
- D-03: Implement a separate `BrainSuiteStaticScoreService` class in `backend/app/services/brainsuite_static_score.py`. Do not extend or modify the video class.
- D-04: Announce step uses: `POST /v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/announce` with `input{}` containing `channel`, `projectName`, `assetLanguage`, `iconicColorScheme`, and `legs[]` with `staticImage{assetId, name}`.
- D-05: `areasOfInterest` NOT submitted in Phase 5.

**Unsupported Platform Handling**
- D-06: Add `UNSUPPORTED` as new value to `scoring_status` enum. Assigned at sync time via `ScoringEndpointType` lookup table.
- D-07: Dashboard display for `UNSUPPORTED`: grey dash + info tooltip "Image scoring not supported for this platform". No new chip/badge.
- D-08: `UNSUPPORTED` assets excluded from scheduler's scoring batch query.

**ScoringEndpointType Lookup Table**
- D-09: `ScoringEndpointType` enum values: `VIDEO`, `STATIC_IMAGE`, `UNSUPPORTED`.
- D-10: Lookup keyed on `(platform, asset_format, file_extension)`. Source of truth: `creative_asset.asset_format` + `creative_asset.platform`. Populated at sync time in `harmonizer.py` — never inferred at scoring time.
- D-11: Lookup table:
  - META + VIDEO → VIDEO
  - META + IMAGE → STATIC_IMAGE
  - TIKTOK + VIDEO → VIDEO
  - TIKTOK + IMAGE → UNSUPPORTED
  - GOOGLE_ADS + VIDEO → VIDEO
  - GOOGLE_ADS + IMAGE → UNSUPPORTED
  - DV360 + VIDEO → VIDEO
  - DV360 + IMAGE → UNSUPPORTED
  - any + CAROUSEL → UNSUPPORTED

**Image-Specific Metadata Fields**
- D-12: Add two new `MetadataField` rows per org: `brainsuite_intended_messages` (TEXT) and `brainsuite_iconic_color_scheme` (SELECT, default "manufactory").
- D-13: `brandValues` NOT added as metadata field in Phase 5 — omit from Static API payload.
- D-14: Image-specific metadata fields surface only when `asset_format = IMAGE`.

**Production Credentials (PROD-01)**
- D-15: Same `BRAINSUITE_CLIENT_ID` / `BRAINSUITE_CLIENT_SECRET` authenticates against both Video and Static endpoints. No new env vars.
- D-16: PROD-01 deliverable: submit one real image job during discovery spike. Document in `BRAINSUITE_API.md`.

**Google Ads OAuth (PROD-02)**
- D-17: PROD-02 is a manual verification step: confirm consent screen is "Published" in Google Cloud Console. No code changes required.

### Claude's Discretion
- Static API job polling interval and timeout (mirror video: 60 polls × 30s = 30 min max)
- Token caching for `BrainSuiteStaticScoreService` (same 50-min cache as video)
- Exact `iconicColorScheme` valid enum values — confirmed from discovery spike before seeding MetadataField options (current docs show only "manufactory")
- `intendedMessages` UI widget in asset detail dialog (textarea with hint text vs. tag-input component)
- Exact file where `ScoringEndpointType` enum + lookup table live (new `enums.py` or inline in `creative.py`)

### Deferred Ideas (OUT OF SCOPE)
- Areas of Interest (AOI) — v1.2: LLM Vision auto-detection + bounding box UI
- `brandValues` metadata field — future phase
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROD-01 | BrainSuite API credentials (video and image apps) configured and verified in production | D-15/D-16: same credentials cover both endpoints; discovery spike verifies auth; document in BRAINSUITE_API.md |
| PROD-02 | Google Ads OAuth consent screen verified as "Published" to prevent 7-day token expiry | D-17: manual verification in Google Cloud Console; no code changes; document in PRODUCTION_CHECKLIST.md |
| IMG-01 | BrainSuite Static API endpoint, payload shape, and response schema confirmed via live discovery spike | SMS_api_docs.md contains full OpenAPI spec; spike submits real job, captures full response JSON, confirms output shape |
| IMG-02 | `ScoringEndpointType` enum assigned at asset sync time using a tested lookup table | `creative_score_results` needs `endpoint_type` column (Alembic); harmonizer.py upsert populates it; lookup is pure Python dict |
| IMG-03 | Image assets scored by the existing 15-minute APScheduler batch job (branch inside `run_scoring_batch()`) | scoring_job.py needs branch: VIDEO path (existing) + STATIC_IMAGE path (new BrainSuiteStaticScoreService) + UNSUPPORTED skip |
| IMG-04 | Scored image creatives display score badge and Creative Effectiveness tab identical to video | dashboard.component.ts `[ngSwitch]` needs UNSUPPORTED case; asset-detail-dialog already uses status-driven rendering; image-only metadata fields need conditional show logic |
</phase_requirements>

---

## Summary

Phase 5 wires image creative assets into the existing BrainSuite scoring pipeline using the ACE_STATIC_SOCIAL_STATIC_API. The pattern is well-established: a working video scorer (`brainsuite_score.py`) serves as the template, and the Static API follows an identical Announce→Upload→Start→Poll flow. The primary differences are the endpoint path (`ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API`), the payload shape (`legs[]` + `staticImage{}` vs `assets[]`), and the channel enum (only "Facebook" or "Instagram" — no TikTok/YouTube).

The most structurally significant work is the `ScoringEndpointType` routing layer: a new column on `creative_score_results`, populated by `harmonizer.py` at sync time, that drives the branch inside `scoring_job.py`. This is a clean, explicit routing mechanism that avoids any string inference at scoring time. The `UNSUPPORTED` status for non-Meta image assets flows naturally from this — those rows are created at sync time with `endpoint_type = UNSUPPORTED` and `scoring_status = UNSUPPORTED`, and the scheduler query simply excludes them.

The frontend changes are minimal: the existing `[ngSwitch]` on `scoring_status` needs one new case for `UNSUPPORTED` (grey dash + tooltip), and the asset detail dialog needs a conditional block to surface image-only metadata fields. The CE tab and score badge display are already identical for any `COMPLETE` asset regardless of format.

**Primary recommendation:** Build in wave order: discovery spike + DB migration first, then the static service class, then harmonizer/scheduler branching, then UI changes. Do not start the static service implementation before the discovery spike confirms the output shape matches `legResults[]` (the SMS docs suggest it does, but confirmation is required).

---

## Standard Stack

### Core

| Library / Tool | Version (verified) | Purpose | Why Standard |
|---|---|---|---|
| Python / FastAPI | 3.9.6 / (existing) | Backend service | Project uses throughout |
| SQLAlchemy async + Alembic | (existing) | ORM + migrations | All DB changes follow this pattern |
| httpx | (existing) | Async HTTP client | Used by existing `brainsuite_score.py` |
| APScheduler | (existing) | 15-min scoring batch | `scoring_job.py` is the established pattern |
| Angular + Angular Material | (existing) | Frontend | Project uses throughout |

### No New Dependencies

This phase introduces zero new Python packages. All required libraries (httpx, SQLAlchemy, APScheduler, Alembic) are already installed. The Static service is a structural copy of the video service.

**Installation:** None required.

---

## Architecture Patterns

### Recommended Project Structure

New files this phase:

```
backend/
├── app/
│   ├── services/
│   │   └── brainsuite_static_score.py   # NEW: BrainSuiteStaticScoreService
│   ├── models/
│   │   └── (no new file — enum added to creative.py or new enums.py)
│   └── services/sync/
│       ├── scoring_job.py               # MODIFY: add image branch
│       └── harmonizer.py               # MODIFY: populate endpoint_type
├── alembic/versions/
│   └── l3m4n5o6p7q8_add_endpoint_type_unsupported.py  # NEW migration
docs/
├── BRAINSUITE_API.md                    # MODIFY: document Static endpoint spike result
└── PRODUCTION_CHECKLIST.md             # NEW: PROD-02 verification checklist
frontend/src/app/features/dashboard/
├── dashboard.component.ts              # MODIFY: UNSUPPORTED badge case
└── dialogs/asset-detail-dialog.component.ts  # MODIFY: image-only metadata fields
```

### Pattern 1: BrainSuiteStaticScoreService — Mirror the Video Service

The existing `BrainSuiteScoreService` is the canonical template. The Static service follows the same method signatures and internal structure:

```python
# backend/app/services/brainsuite_static_score.py

class BrainSuiteStaticScoreService:
    """Async client for BrainSuite ACE_STATIC_SOCIAL_STATIC_API."""

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def _get_token(self) -> str:
        # IDENTICAL to BrainSuiteScoreService._get_token()
        # Same BRAINSUITE_CLIENT_ID / BRAINSUITE_CLIENT_SECRET
        # Same 50-minute cache

    async def _api_post_with_retry(self, url, json_body, log_name) -> dict:
        # IDENTICAL retry/backoff/401-refresh logic

    async def _announce_job(self, announce_payload: dict) -> str:
        # POST /v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/announce
        # Payload: {"input": {channel, projectName, assetLanguage,
        #                      iconicColorScheme, legs[{name, staticImage{assetId, name}}]}}
        # Returns job id from response {"id": "...", "msg": "...", "type": "..."}

    async def _announce_asset(self, job_id: str, asset_id: str, filename: str) -> dict:
        # POST /v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/{jobId}/assets
        # Body: {"assetId": asset_id, "name": filename}
        # Returns: {"uploadUrl": "...", "fields": {...}}

    async def _upload_to_brainsuite_s3(self, upload_url, fields, file_bytes, filename):
        # IDENTICAL to video service — S3 presigned POST

    async def _start_job(self, job_id: str) -> None:
        # POST /v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/{jobId}/start
        # Body: {} (empty — briefing data was in announce for Static API)

    async def submit_job_with_upload(
        self, file_bytes: bytes, filename: str, announce_payload: dict
    ) -> str:
        # announce_job → announce_asset → upload_to_s3 → start_job → return job_id

    async def poll_job_status(self, job_id: str, max_polls=60, poll_interval=30) -> dict:
        # GET /v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/{jobId}
        # Same terminal status set: Succeeded / Failed / Stale
```

**Key difference from video**: The briefing data (channel, projectName, etc.) goes into the **Announce** request body for Static API, NOT the Start request. The Start request body is `{}` (empty). Verify this with the discovery spike — the SMS API docs show this pattern, but the General docs' announce example shows `input{}` in the announce body.

### Pattern 2: ScoringEndpointType Enum + Lookup Table

```python
# Option A: inline in backend/app/models/creative.py
# Option B: new backend/app/services/scoring_endpoint_type.py

from enum import Enum

class ScoringEndpointType(str, Enum):
    VIDEO = "VIDEO"
    STATIC_IMAGE = "STATIC_IMAGE"
    UNSUPPORTED = "UNSUPPORTED"

# Lookup table — populated at sync time by harmonizer.py
_ENDPOINT_TYPE_LOOKUP: dict[tuple[str, str], ScoringEndpointType] = {
    ("META", "VIDEO"):       ScoringEndpointType.VIDEO,
    ("META", "IMAGE"):       ScoringEndpointType.STATIC_IMAGE,
    ("TIKTOK", "VIDEO"):     ScoringEndpointType.VIDEO,
    ("TIKTOK", "IMAGE"):     ScoringEndpointType.UNSUPPORTED,
    ("GOOGLE_ADS", "VIDEO"): ScoringEndpointType.VIDEO,
    ("GOOGLE_ADS", "IMAGE"): ScoringEndpointType.UNSUPPORTED,
    ("DV360", "VIDEO"):      ScoringEndpointType.VIDEO,
    ("DV360", "IMAGE"):      ScoringEndpointType.UNSUPPORTED,
}

def get_endpoint_type(platform: str, asset_format: str) -> ScoringEndpointType:
    """Look up ScoringEndpointType from (platform, asset_format).
    CAROUSEL and any unknown combination → UNSUPPORTED.
    """
    if (asset_format or "").upper() == "CAROUSEL":
        return ScoringEndpointType.UNSUPPORTED
    key = ((platform or "").upper(), (asset_format or "").upper())
    return _ENDPOINT_TYPE_LOOKUP.get(key, ScoringEndpointType.UNSUPPORTED)
```

### Pattern 3: DB Migration — Two New Things

**Migration 1:** Add `endpoint_type` column to `creative_score_results` and extend `scoring_status` to accept `UNSUPPORTED`.

```python
# backend/alembic/versions/l3m4n5o6p7q8_add_endpoint_type_unsupported.py
def upgrade() -> None:
    op.add_column(
        "creative_score_results",
        sa.Column("endpoint_type", sa.String(50), nullable=True),
    )
    op.create_index(
        "ix_score_results_endpoint_type",
        "creative_score_results",
        ["endpoint_type"],
    )
    # scoring_status is a String(50) — no enum constraint in DB,
    # so UNSUPPORTED is a valid value without a separate ALTER TYPE
```

Note: `scoring_status` is `String(50)` in the DB (not a PostgreSQL ENUM type), confirmed from `e1f2g3h4i5j6_add_creative_score_results.py`. Adding `UNSUPPORTED` as a string value requires no DB ALTER — just application-level enforcement.

**Migration 2:** Seed two new `MetadataField` rows per organization.

```python
# backend/alembic/versions/m4n5o6p7q8r9_seed_image_metadata_fields.py
# Seed per org (same pattern as f2g3h4i5j6k7):
# - brainsuite_intended_messages: TEXT, sort_order=8, not required
# - brainsuite_iconic_color_scheme: SELECT, sort_order=9, default="manufactory"
# After discovery spike confirms iconicColorScheme enum values → seed MetadataFieldValue rows
# Current documented values: ["manufactory"]
# Planner note: spike must run BEFORE this migration is written in full
```

### Pattern 4: Harmonizer — Populate endpoint_type at Sync Time

The current harmonizer code at line 882–890 creates `CreativeScoreResult` only for VIDEO assets. Phase 5 changes this to: create a row for IMAGE assets too, and populate `endpoint_type` on both:

```python
# backend/app/services/sync/harmonizer.py
# In _upsert_asset() (currently around line 882)

from app.services.scoring_endpoint_type import get_endpoint_type, ScoringEndpointType

asset_fmt = (kwargs.get("asset_format") or "IMAGE").upper()
endpoint_type = get_endpoint_type(platform, asset_fmt)

# Create score result row for VIDEO and IMAGE assets (not CAROUSEL/unknown)
if endpoint_type != ScoringEndpointType.UNSUPPORTED or asset_fmt in ("VIDEO", "IMAGE"):
    # For UNSUPPORTED: create row with scoring_status="UNSUPPORTED"
    # For VIDEO: scoring_status="UNSCORED"  (existing behavior)
    # For STATIC_IMAGE: scoring_status="UNSCORED"
    initial_status = (
        "UNSUPPORTED" if endpoint_type == ScoringEndpointType.UNSUPPORTED
        else "UNSCORED"
    )
    score_stmt = pg_insert(CreativeScoreResult).values(
        creative_asset_id=asset.id,
        organization_id=connection.organization_id,
        scoring_status=initial_status,
        endpoint_type=endpoint_type.value,
    ).on_conflict_do_nothing(index_elements=["creative_asset_id"])
    await db.execute(score_stmt)
```

Decision point: create score rows for ALL asset formats (IMAGE, VIDEO, CAROUSEL) with UNSUPPORTED for non-scoreable ones, or only for VIDEO+IMAGE. The approach above creates rows for all IMAGE and VIDEO assets, using UNSUPPORTED status for the ones that can't be scored. CAROUSEL assets can be skipped entirely if preferred.

### Pattern 5: scoring_job.py Branch

```python
# backend/app/services/sync/scoring_job.py

async def run_scoring_batch() -> None:
    # Phase 1: Fetch UNSCORED batch (VIDEO + STATIC_IMAGE)
    result = await db.execute(
        select(CreativeScoreResult, CreativeAsset)
        .join(CreativeAsset, ...)
        .where(
            CreativeScoreResult.scoring_status == "UNSCORED",
            CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"]),
        )
        .order_by(CreativeScoreResult.created_at.asc())
        .limit(BATCH_SIZE)
    )

    # Phase 2: Per-asset, branch on endpoint_type
    for item in batch:
        if item["endpoint_type"] == "VIDEO":
            # existing path — brainsuite_score_service.submit_job_with_upload(...)
        elif item["endpoint_type"] == "STATIC_IMAGE":
            # new path — brainsuite_static_score_service.submit_job_with_upload(...)
            # build_static_scoring_payload(...) instead of build_scoring_payload(...)
```

### Pattern 6: Static API Announce Payload

```python
# build_static_scoring_payload() in brainsuite_static_score.py
def build_static_scoring_payload(
    asset_name: str,
    platform: str,
    placement: Optional[str],
    metadata: dict[str, str],
) -> dict:
    """Build the Static API AnnounceJobInput payload."""
    channel = map_static_channel(platform, placement)  # "Facebook" or "Instagram"

    # intendedMessages: split brainsuite_intended_messages on newlines
    raw_messages = metadata.get("brainsuite_intended_messages", "")
    intended_messages = [
        m.strip() for m in raw_messages.split("\n")
        if m.strip()
    ]

    iconic_color_scheme = metadata.get("brainsuite_iconic_color_scheme", "manufactory")

    leg_asset_id = "leg1"

    input_obj = {
        "channel": channel,
        "projectName": metadata.get("brainsuite_project_name") or "Spring Campaign 2026",
        "assetLanguage": metadata.get("brainsuite_asset_language", "en-US"),
        "iconicColorScheme": iconic_color_scheme,
        "legs": [
            {
                "name": asset_name,
                "staticImage": {
                    "assetId": leg_asset_id,
                    "name": asset_name,
                }
            }
        ],
    }

    if intended_messages:
        input_obj["intendedMessages"] = intended_messages
        input_obj["intendedMessagesLanguage"] = metadata.get("brainsuite_asset_language", "en-US")

    return {"input": input_obj}


def map_static_channel(platform: str, placement: Optional[str]) -> str:
    """Map platform + placement to Static API channel: 'Facebook' or 'Instagram'.

    Static API only accepts 'Facebook' or 'Instagram'.
    META placement determines Facebook vs. Instagram.
    Non-Meta platforms → should never reach here (UNSUPPORTED), fallback to 'Facebook'.
    """
    if (platform or "").upper() == "META":
        normalized = (placement or "").lower()
        if "instagram" in normalized:
            return "Instagram"
        return "Facebook"
    return "Facebook"  # fallback — should not be reached for non-Meta
```

### Pattern 7: Frontend UNSUPPORTED Badge

```typescript
// dashboard.component.ts — inside <ng-container [ngSwitch]="asset.scoring_status">
// Add after 'FAILED' case:

<ng-container *ngSwitchCase="'UNSUPPORTED'">
  <div class="overlay-ace overlay-ace-dash"
       [matTooltip]="'Image scoring not supported for this platform'"
       aria-label="Image scoring not supported">
    <span class="score-dash">–</span>
  </div>
</ng-container>
```

The existing `.overlay-ace-dash` CSS class (used for FAILED) produces the grey dash styling — reuse it.

```typescript
// asset-detail-dialog.component.ts — in the CE tab "not scored" block:
// UNSUPPORTED falls into the existing "not COMPLETE / not PENDING / not PROCESSING" branch
// Needs an explicit case for UNSUPPORTED to show the right message:

<ng-container *ngIf="scoreDetail?.scoring_status === 'UNSUPPORTED'">
  <h4>Scoring not supported</h4>
  <p>Image scoring is not available for this platform.</p>
</ng-container>
```

### Pattern 8: Image-Only Metadata Fields in Asset Detail Dialog

```typescript
// asset-detail-dialog.component.ts
// Conditional display of image-specific metadata fields:

<ng-container *ngIf="asset.asset_format === 'IMAGE'">
  <!-- brainsuite_intended_messages: textarea -->
  <!-- brainsuite_iconic_color_scheme: select -->
</ng-container>
```

The existing metadata rendering loop already renders all `brainsuite_*` fields. The image-only fields need to either:
1. Be filtered out of the generic loop when `asset_format !== 'IMAGE'`, OR
2. Have a separate image-only metadata section rendered conditionally

Option 1 is simpler: filter the metadata fields list before rendering using `asset_format`.

### Anti-Patterns to Avoid

- **Inferring endpoint type from content_type string at scoring time** — the lookup table in harmonizer is the source of truth; never branch on `asset.asset_format` inside the scheduler
- **Modifying `BrainSuiteScoreService`** — separate class for Static; video scorer is untouched
- **Using Create-Job workflow** (URL-based) even though it's simpler — decision is locked to Announce→Upload→Start
- **Sending `brandValues` in the Static payload** — omit entirely in Phase 5
- **Starting implementation before discovery spike** — the spike verifies output shape; if `legResults[]` is missing or differently named, `extract_score_data()` won't work unmodified

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limiting | Custom counter | Existing `_api_post_with_retry()` pattern from `brainsuite_score.py` | Already handles 429 with `x-ratelimit-reset`, 5xx backoff, 401 token refresh |
| Async HTTP | `requests` or `aiohttp` | `httpx.AsyncClient` (existing) | Already wired, timeout-configured, used throughout |
| Token caching | Custom TTL mechanism | Datetime comparison in `_get_token()` (copy from video service) | 50-min cache pattern already battle-tested |
| DB session isolation | Long-lived session across HTTP calls | `async with get_session_factory()() as db:` per operation | Existing pattern prevents session leaks during BrainSuite polling (may take minutes) |
| S3 multipart upload | Raw boto3 calls | `_upload_to_brainsuite_s3()` from video service (copy verbatim) | S3 presigned POST requires exact field ordering — already solved |
| Visualization URL persistence | In-memory cache | `persist_and_replace_visualizations()` from `brainsuite_score.py` | URLs expire 1hr; existing function handles download+re-upload to our S3 |

**Key insight:** `extract_score_data()` navigates `output.legResults[0].executiveSummary`. The Static API docs suggest results also come in `legResults[]` (same structure). This MUST be confirmed by the discovery spike before assuming `extract_score_data()` can be reused without modification.

---

## Runtime State Inventory

> Phase is an extension of existing scoring pipeline — not a rename/refactor. No runtime state migration required.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `creative_score_results` table: existing rows are all VIDEO — no IMAGE rows yet | None — new Alembic migration adds `endpoint_type` column with `nullable=True`; existing VIDEO rows will have `endpoint_type = NULL` until backfilled (Phase 6 handles backfill) |
| Live service config | No external service config references endpoint type | None |
| OS-registered state | APScheduler `scoring_batch` job registered at startup | No re-registration needed — same job ID, same interval; code change is inside the function |
| Secrets/env vars | `BRAINSUITE_CLIENT_ID` / `BRAINSUITE_CLIENT_SECRET` — same vars cover Static endpoint (D-15) | Verify values are set in production environment (PROD-01 spike) |
| Build artifacts | No stale artifacts relevant to this phase | None |

**Existing VIDEO rows without `endpoint_type`:** After migration adds the column as `nullable=True`, existing VIDEO rows will have `endpoint_type = NULL`. The scoring batch query should treat `NULL` as `VIDEO` for backward compatibility, OR a data migration backfills them. Recommend: add a data migration that sets `endpoint_type = 'VIDEO'` for all existing `UNSCORED`/`PENDING`/`PROCESSING` rows where `endpoint_type IS NULL`. This is a single UPDATE statement in the same Alembic migration.

---

## Common Pitfalls

### Pitfall 1: Static Announce Payload Location

**What goes wrong:** The briefing data (channel, projectName, legs) is placed in the `/start` request body instead of the `/announce` request body.

**Why it happens:** The video scorer puts briefing data in `/start`. The Static API puts it in `/announce`. The docs for both APIs show `input{}` in different steps.

**How to avoid:** In `BrainSuiteStaticScoreService._announce_job()`, pass the full `announce_payload` as the JSON body. The `/start` endpoint receives `{}` (empty body). Confirm with discovery spike.

**Warning signs:** `422 Unprocessable Entity` on the start request, or the job starts but produces no meaningful output.

### Pitfall 2: `extract_score_data()` May Not Work for Static Output

**What goes wrong:** `extract_score_data()` navigates `output.legResults[0].executiveSummary`. The Static API response may structure output differently.

**Why it happens:** The SMS_api_docs.md does not document the full response `output` shape — only the job status response container (`{"detail": [...]}` which looks like an error schema).

**How to avoid:** Discovery spike (IMG-01) MUST capture and log the full response JSON when `status == "Succeeded"`. If `legResults[]` is present with the same structure, reuse `extract_score_data()` directly. If the structure differs, write `extract_static_score_data()`.

**Warning signs:** `KeyError: 'legResults'` or `IndexError` during score extraction.

### Pitfall 3: Alembic Migration Order — endpoint_type nullable

**What goes wrong:** Migration adds `endpoint_type` as `NOT NULL` with no default, breaking existing rows.

**Why it happens:** Column added without `nullable=True` or `server_default`.

**How to avoid:** Add column as `nullable=True`. Include a companion UPDATE statement in the same migration to backfill `endpoint_type = 'VIDEO'` for all existing rows (their format is always VIDEO per current harmonizer logic).

### Pitfall 4: scoring_job.py Query Still Excludes IMAGE Assets

**What goes wrong:** The batch query continues to filter `asset_format == "VIDEO"` instead of `endpoint_type IN ("VIDEO", "STATIC_IMAGE")`, so image assets are never processed.

**Why it happens:** The old query had a hardcoded `asset_format == "VIDEO"` filter. After adding `endpoint_type`, the query should filter on the new column.

**How to avoid:** Remove `CreativeAsset.asset_format == "VIDEO"` from the batch query. Replace with `CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"])`. Also verify `UNSUPPORTED` rows are excluded (they never have `scoring_status = "UNSCORED"` so they're implicitly excluded, but be explicit).

### Pitfall 5: intendedMessages Language Field Required

**What goes wrong:** Submitting `intendedMessages` array without `intendedMessagesLanguage` causes a validation error.

**Why it happens:** The Static API docs state `intendedMessagesLanguage` is "Conditional — Required if intendedMessages is provided."

**How to avoid:** In `build_static_scoring_payload()`, only add `intendedMessages` when non-empty, and always pair it with `intendedMessagesLanguage` (default to `brainsuite_asset_language` value or `"en-US"`).

### Pitfall 6: Static API `uploadUrl` from `/{jobId}/assets` Response

**What goes wrong:** The `/{jobId}/assets` endpoint response for the Static API is documented as `204 No Content` (the upload confirmation), but the actual asset-announcement response (the one returning `uploadUrl`) is not clearly documented in SMS_api_docs.md.

**Why it happens:** The SMS docs show the `/assets` endpoint but the response for the asset announcement itself (pre-upload) shows `204 No Content`. This is the upload confirmation, not the URL response.

**How to avoid:** The General API docs confirm the announce-asset flow returns `uploadUrl + fields` (same as video). The video scorer at line 210–218 shows the correct call and response shape. Mirror exactly. Confirm with discovery spike.

### Pitfall 7: UNSUPPORTED rows Accumulate for IMAGE Assets on Rescore

**What goes wrong:** The rescore endpoint (`POST /scoring/{id}/rescore`) sets status back to `UNSCORED`, potentially allowing UNSUPPORTED image assets to be queued for scoring.

**Why it happens:** The rescore endpoint may not check `endpoint_type` before resetting status.

**How to avoid:** The rescore endpoint should check `endpoint_type`: if `UNSUPPORTED`, return 400 or 422 (cannot rescore unsupported asset). This is a guard to add during implementation.

---

## Code Examples

Verified patterns from actual codebase:

### Exact Announce→Upload→Start Flow (Video Reference)

```python
# From brainsuite_score.py (lines 199–286) — mirror for Static:
job_id = await self._announce_job()           # POST /announce
upload_info = await self._announce_asset(job_id, "video", filename)  # POST /{jobId}/assets
await self._upload_to_brainsuite_s3(          # POST to S3 presigned URL
    upload_info["uploadUrl"], upload_info.get("fields", {}), file_bytes, filename
)
await self._start_job(job_id, briefing_data)  # POST /{jobId}/start
```

For Static: briefing data moves from `_start_job` to `_announce_job`. The `_start_job` receives `{}`.

### Harmonizer Upsert Pattern (Existing)

```python
# From harmonizer.py lines 885–890:
score_stmt = pg_insert(CreativeScoreResult).values(
    creative_asset_id=asset.id,
    organization_id=connection.organization_id,
    scoring_status="UNSCORED",
).on_conflict_do_nothing(index_elements=["creative_asset_id"])
await db.execute(score_stmt)
```

Phase 5 extends this to include `endpoint_type` and `scoring_status` based on lookup.

### scoring_job.py Batch Query (Existing)

```python
# From scoring_job.py lines 41–50:
result = await db.execute(
    select(CreativeScoreResult, CreativeAsset)
    .join(CreativeAsset, CreativeAsset.id == CreativeScoreResult.creative_asset_id)
    .where(
        CreativeScoreResult.scoring_status == "UNSCORED",
        CreativeAsset.asset_format == "VIDEO",  # ← REPLACE with endpoint_type filter
    )
    .order_by(CreativeScoreResult.created_at.asc())
    .limit(BATCH_SIZE)
)
```

### Dashboard score badge switch (existing + new UNSUPPORTED case)

```typescript
// dashboard.component.ts lines 221–244 + new case:
<ng-container [ngSwitch]="asset.scoring_status">
  <ng-container *ngSwitchCase="'COMPLETE'">...</ng-container>
  <ng-container *ngSwitchCase="'PENDING'">...</ng-container>
  <ng-container *ngSwitchCase="'PROCESSING'">...</ng-container>
  <ng-container *ngSwitchCase="'FAILED'">...</ng-container>
  <!-- NEW: -->
  <ng-container *ngSwitchCase="'UNSUPPORTED'">
    <div class="overlay-ace overlay-ace-dash"
         [matTooltip]="'Image scoring not supported for this platform'">
      <span class="score-dash">–</span>
    </div>
  </ng-container>
</ng-container>
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| `asset_format == "VIDEO"` hardcoded in batch query | `endpoint_type IN ("VIDEO", "STATIC_IMAGE")` lookup column | Phase 5 | Enables image scoring without changing query semantics per-asset-type |
| `scoring_status` ∈ {UNSCORED, PENDING, PROCESSING, COMPLETE, FAILED} | + UNSUPPORTED | Phase 5 | Non-Meta image assets get a terminal state at sync time, never enter the scoring queue |
| Only VIDEO assets get `CreativeScoreResult` row | IMAGE assets also get row (status: UNSCORED or UNSUPPORTED) | Phase 5 | Enables uniform score badge display for all asset formats |

---

## Open Questions

1. **Static API `/start` body — empty or briefing data?**
   - What we know: SMS_api_docs.md shows announce with `input{}` in announce body; start body shown as `{}`. General docs' announce→start diagram implies start needs legs.
   - What's unclear: Whether start for Static API requires legs reference or is truly empty.
   - Recommendation: Discovery spike confirms. If start requires legs, adjust `_start_job()` accordingly.

2. **Static API output shape — does `legResults[]` exist?**
   - What we know: SMS_api_docs.md does not document the full `output` structure; only shows `{"detail": [...]}` for the GET status endpoint (likely the error shape).
   - What's unclear: Whether `output.legResults[0].executiveSummary` is present identically to video.
   - Recommendation: IMG-01 spike MUST capture and log the full `Succeeded` response JSON. If output shape differs, `extract_static_score_data()` must be written.

3. **`iconicColorScheme` valid enum values beyond "manufactory"**
   - What we know: SMS_api_docs.md documents only `"manufactory"` as a Color Scheme Option.
   - What's unclear: Whether there are additional values not yet documented.
   - Recommendation: Discovery spike can test with `"manufactory"`. Seed `MetadataFieldValue` with only this value initially. The SELECT field can have values added later when BrainSuite documents more.

4. **Backfill of `endpoint_type` for existing VIDEO rows**
   - What we know: After migration, existing rows have `endpoint_type = NULL`.
   - What's unclear: Whether the scheduler query should treat NULL as VIDEO, or whether a data backfill is safer.
   - Recommendation: Include a `UPDATE creative_score_results SET endpoint_type = 'VIDEO' WHERE endpoint_type IS NULL` in the Alembic migration. Clean, explicit, no ambiguity in the scheduler query.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| Python 3.9+ | Backend | ✓ | 3.9.6 | — |
| Node.js | Frontend build | ✓ | v24.14.0 | — |
| httpx | BrainSuite HTTP calls | ✓ | (existing install) | — |
| SQLAlchemy async + Alembic | DB migrations | ✓ | (existing install) | — |
| BrainSuite Static API credentials | PROD-01 verification | Unknown | — | Staging credentials for discovery spike |
| PostgreSQL (production) | Live scoring | Unknown (remote) | — | Dev/staging DB for testing |

**Missing dependencies with no fallback:**
- BrainSuite credentials with Static API ("Reports — View + Create") permission for the Static app must be confirmed to be granted before the discovery spike can run.

---

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest (existing) |
| Config file | `backend/pytest.ini` or `pyproject.toml` (existing) |
| Quick run command | `cd backend && pytest tests/test_scoring.py -x -q` |
| Full suite command | `cd backend && pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| IMG-01 | Discovery spike result documented | manual | n/a — manual spike | N/A (doc artifact) |
| IMG-02 | `get_endpoint_type()` returns correct values for all 9 platform/format combinations | unit | `pytest tests/test_scoring_image.py::test_endpoint_type_lookup -x` | ❌ Wave 0 |
| IMG-02 | `endpoint_type` column populated on harmonizer upsert | unit | `pytest tests/test_scoring_image.py::test_harmonizer_endpoint_type -x` | ❌ Wave 0 |
| IMG-03 | Batch query includes STATIC_IMAGE endpoint_type | unit | `pytest tests/test_scoring_image.py::test_batch_query_includes_static_image -x` | ❌ Wave 0 |
| IMG-03 | UNSUPPORTED assets excluded from batch | unit | `pytest tests/test_scoring_image.py::test_batch_query_excludes_unsupported -x` | ❌ Wave 0 |
| IMG-03 | Static announce payload has correct structure | unit | `pytest tests/test_scoring_image.py::test_static_announce_payload -x` | ❌ Wave 0 |
| IMG-03 | map_static_channel() META+instagram_* → "Instagram" | unit | `pytest tests/test_scoring_image.py::test_map_static_channel -x` | ❌ Wave 0 |
| IMG-04 | UNSUPPORTED status present in DashboardAsset interface | smoke | Angular build check | ❌ Wave 0 |
| PROD-01 | BrainSuite client authenticates against Static endpoint | manual | n/a — discovery spike | N/A |
| PROD-02 | Google Ads OAuth consent "Published" | manual | n/a — console check | N/A |

### Sampling Rate

- **Per task commit:** `cd backend && pytest tests/test_scoring_image.py -x -q`
- **Per wave merge:** `cd backend && pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_scoring_image.py` — covers IMG-02, IMG-03 unit tests listed above
- [ ] All test stubs follow the existing pattern in `test_scoring.py` (pytest.mark.skip → implement → remove skip)

---

## Sources

### Primary (HIGH confidence)

- `brainsuite_api/SMS_api_docs.md` — ACE_STATIC_SOCIAL_STATIC_API OpenAPI spec: endpoint paths, Announce/Assets/Start/Status endpoints, AnnounceJobInput schema, channel enum values, iconicColorScheme, intendedMessages constraints
- `brainsuite_api/API Docs General.txt` — Auth flow (OAuth 2.0 Client Credentials), rate limiting headers (`x-ratelimit-reset`), async poll-based retrieval, job status values
- `backend/app/services/brainsuite_score.py` — Complete reference implementation for token management, retry logic, announce→upload→start flow, polling, score extraction
- `backend/app/services/sync/scoring_job.py` — Complete reference for batch job pattern: session isolation, PENDING marking, per-asset error handling, `_mark_failed()`
- `backend/app/services/sync/harmonizer.py` — Score result upsert pattern (lines 882–890)
- `backend/app/models/scoring.py` — `CreativeScoreResult` model; `scoring_status` is `String(50)` not PG enum
- `backend/alembic/versions/e1f2g3h4i5j6_add_creative_score_results.py` — Migration pattern; confirms no DB-level ENUM constraint on scoring_status
- `backend/alembic/versions/f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py` — Metadata field seeding pattern per org

### Secondary (MEDIUM confidence)

- `.planning/phases/05-brainsuite-image-scoring/05-CONTEXT.md` — All locked decisions (D-01 through D-17) verified against codebase patterns

### Tertiary (LOW confidence — requires spike confirmation)

- Static API `output.legResults[]` response shape: assumed identical to video based on General docs "legResults" reference, but not confirmed until IMG-01 spike

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all existing
- Architecture: HIGH — direct mirror of proven video scorer pattern
- Pitfalls: HIGH — identified from actual code inspection (not guesses)
- Static API output shape: LOW — not documented in SMS_api_docs.md; spike required

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable domain; BrainSuite API versioned at 1.0.0)
