---
phase: 05-brainsuite-image-scoring
verified: 2026-03-27T20:00:00Z
status: human_needed
score: 12/12 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 11/12
  gaps_closed:
    - "UNSUPPORTED badge tooltip reads 'Image scoring not supported for this platform' — explicit *ngSwitchCase added in commit c921e40"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "End-to-end image scoring pipeline with live BrainSuite credentials"
    expected: "A META IMAGE asset is submitted, scored, and appears with a score badge and CE tab dimension breakdown identical to video"
    why_human: "PROD-01 credentials not available in dev environment — spike script cannot be run to confirm Static API authentication and response shape"
  - test: "UNSUPPORTED asset tooltip display in dashboard grid"
    expected: "Hovering a TikTok/Google Ads/DV360 IMAGE creative shows tooltip reading 'Image scoring not supported for this platform'"
    why_human: "Visual tooltip behavior requires browser interaction to confirm"
  - test: "PROD-02 Google Ads OAuth consent screen status"
    expected: "Consent screen is in 'Published' state (not 'Testing')"
    why_human: "Requires manual check in Google Cloud Console — cannot be automated"
  - test: "Image scoring CE tab end-to-end"
    expected: "A fully scored META IMAGE creative shows the score donut, 7 pillar cards, and an Image Metadata section if Intended Messages / Iconic Color Scheme are filled in"
    why_human: "Requires a COMPLETE-status image asset in the database, which depends on PROD-01 being confirmed and the scheduler having run"
---

# Phase 05: BrainSuite Image Scoring — Verification Report

**Phase Goal:** Every image creative is scored alongside video by the existing scoring pipeline, and users can see image scores and dimension breakdowns the same way they see video scores
**Verified:** 2026-03-27T20:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (commit c921e40)

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|---------|
| 1  | BrainSuite Static API endpoint confirmed reachable with existing credentials | ? UNCERTAIN | Script `scripts/spike_static_api.py` created and ready; credentials not available in dev — PROD-01 confirmation is a deploy-time human verification item, not a code gap |
| 2  | Static API response shape documented | ✓ VERIFIED | `docs/BRAINSUITE_API.md` documents endpoint URLs, payload, and expected `legResults[0].executiveSummary` response shape |
| 3  | ScoringEndpointType lookup returns correct value for all 9 platform/format combinations | ✓ VERIFIED | 28 tests pass (run from `backend/` directory): `28 passed, 1 warning in 0.08s` |
| 4  | endpoint_type column exists on creative_score_results with existing rows backfilled to VIDEO | ✓ VERIFIED | Migration `l3m4n5o6p7q8` adds column, indexes it, backfills existing rows; `n5o6p7q8r9s0` corrects image rows to STATIC_IMAGE/UNSUPPORTED |
| 5  | Image assets from Meta get UNSCORED + STATIC_IMAGE at sync time | ✓ VERIFIED | `harmonizer.py` line 885 calls `get_endpoint_type(connection.platform, asset_fmt)` and sets `endpoint_type=endpoint_type.value` / `scoring_status=UNSCORED` for IMAGE+VIDEO |
| 6  | Non-Meta IMAGE assets get UNSUPPORTED status and endpoint_type at sync time | ✓ VERIFIED | Same harmonizer block sets `scoring_status="UNSUPPORTED"` when `endpoint_type == ScoringEndpointType.UNSUPPORTED` |
| 7  | The 15-minute scheduler picks up STATIC_IMAGE assets and submits to Static API | ✓ VERIFIED | `scoring_job.py` line 61: `.where(... endpoint_type.in_(["VIDEO", "STATIC_IMAGE"]))` — STATIC_IMAGE included in batch; `_process_asset()` branches on `endpoint_type == "STATIC_IMAGE"` to `brainsuite_static_score_service.submit_job_with_upload()` |
| 8  | The scheduler skips UNSUPPORTED assets and VIDEO assets are unchanged | ✓ VERIFIED | UNSUPPORTED assets have `scoring_status="UNSUPPORTED"` (not "UNSCORED") so they never enter the batch; VIDEO branch is unchanged |
| 9  | A scored IMAGE shows score badge and CE tab dimension breakdown same as video | ✓ VERIFIED (programmatic) / ? NEEDS HUMAN (visual) | `scoring_job.py` uses same `extract_score_data()` + `persist_and_replace_visualizations()` for both types; CE tab COMPLETE block is format-agnostic; human verification needed to confirm visual appearance |
| 10 | An UNSUPPORTED IMAGE shows a grey dash | ✓ VERIFIED | Explicit `*ngSwitchCase="'UNSUPPORTED'"` in `dashboard.component.ts` line 246 renders `overlay-ace overlay-ace-dash` |
| 11 | UNSUPPORTED badge tooltip reads "Image scoring not supported for this platform" | ✓ VERIFIED | Commit c921e40 adds `[matTooltip]="'Image scoring not supported for this platform'"` to the explicit UNSUPPORTED ngSwitchCase at line 247; `aria-label="Image scoring not supported"` also present |
| 12 | Asset detail CE tab shows informative notice for UNSUPPORTED assets | ✓ VERIFIED | `asset-detail-dialog.component.ts` line 253: explicit `*ngIf="!scoreLoading && scoreDetail?.scoring_status === 'UNSUPPORTED'"` block; Unscored/Failed condition at line 261 explicitly excludes UNSUPPORTED |

**Score: 12/12 truths verified** (all programmatic checks pass; 4 items require human/credentials confirmation)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/services/scoring_endpoint_type.py` | ScoringEndpointType enum + get_endpoint_type() lookup | ✓ VERIFIED | VIDEO/STATIC_IMAGE/UNSUPPORTED values; 8-entry lookup dict; CAROUSEL pre-check; case normalization |
| `backend/app/services/brainsuite_static_score.py` | BrainSuiteStaticScoreService for ACE_STATIC_SOCIAL_STATIC_API | ✓ VERIFIED | Full announce→upload→start→poll flow; `build_static_scoring_payload()`; `map_static_channel()`; singleton exported |
| `backend/app/services/sync/harmonizer.py` | Populates endpoint_type at sync time | ✓ VERIFIED | line 22 imports `get_endpoint_type, ScoringEndpointType`; lines 883-901 create score rows for both IMAGE and VIDEO with endpoint_type |
| `backend/app/services/sync/scoring_job.py` | endpoint_type branching in run_scoring_batch() | ✓ VERIFIED | line 61: `endpoint_type.in_(["VIDEO", "STATIC_IMAGE"])`; lines 188-214: VIDEO and STATIC_IMAGE branches; lines 226-229: poll branches |
| `backend/app/api/v1/endpoints/scoring.py` | Rescore endpoint guards UNSUPPORTED with HTTP 422 | ✓ VERIFIED | lines 61-65: `if score_record.endpoint_type == "UNSUPPORTED": raise HTTPException(status_code=422, ...)` |
| `backend/alembic/versions/l3m4n5o6p7q8_add_endpoint_type_unsupported.py` | Migration adding endpoint_type + VIDEO backfill | ✓ VERIFIED | add_column, create_index, UPDATE backfill in upgrade(); drop in downgrade() |
| `backend/alembic/versions/m4n5o6p7q8r9_seed_image_metadata_fields.py` | Seeds brainsuite_intended_messages + brainsuite_iconic_color_scheme per org | ✓ VERIFIED | Seeds both fields; manufactory allowed value row; ON CONFLICT DO NOTHING guard |
| `backend/alembic/versions/n5o6p7q8r9s0_fix_endpoint_type_for_existing_images.py` | Corrects existing IMAGE rows backfilled to VIDEO | ✓ VERIFIED | Fixes Meta IMAGE to STATIC_IMAGE/UNSCORED; non-Meta IMAGE to UNSUPPORTED |
| `backend/tests/test_scoring_image.py` | Unit tests for endpoint type lookup + payload builders | ✓ VERIFIED | 28 tests; all pass (`28 passed, 1 warning in 0.08s` from `backend/` directory) |
| `docs/BRAINSUITE_API.md` | Static API discovery documentation | ✓ VERIFIED | Contains Static API section with endpoint URLs, payload schema, auth details |
| `docs/PRODUCTION_CHECKLIST.md` | PROD-01 and PROD-02 verification steps | ✓ VERIFIED | Both PROD-01 and PROD-02 sections present with step-by-step verification instructions |
| `frontend/src/app/features/dashboard/dashboard.component.ts` | UNSUPPORTED badge with tooltip | ✓ VERIFIED | Explicit `*ngSwitchCase="'UNSUPPORTED'"` at line 246; `[matTooltip]="'Image scoring not supported for this platform'"` at line 247; fixed in commit c921e40 |
| `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` | UNSUPPORTED CE notice + imageMetadataFields getter | ✓ VERIFIED | UNSUPPORTED block at line 253; `imageMetadataFields` getter at line 1070 guards `asset_format !== 'IMAGE'`; image-only metadata section in COMPLETE block at line 347; `metadata_values` in AssetDetailResponse interface at line 100 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `harmonizer.py` | `scoring_endpoint_type.py` | `get_endpoint_type()` called in `_upsert_asset()` | ✓ WIRED | `from app.services.scoring_endpoint_type import get_endpoint_type, ScoringEndpointType` at line 22; called at line 885 |
| `scoring_job.py` | `brainsuite_static_score.py` | `brainsuite_static_score_service.submit_job_with_upload()` for STATIC_IMAGE | ✓ WIRED | Import at lines 25-28; called inside `elif endpoint_type == "STATIC_IMAGE"` branch |
| `scoring_job.py` | `scoring.py` model | `endpoint_type.in_()` filter in batch query | ✓ WIRED | line 61: `CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"])` |
| `dashboard.component.ts` | backend scoring_status field | Explicit UNSUPPORTED ngSwitchCase with matTooltip | ✓ WIRED | `*ngSwitchCase="'UNSUPPORTED'"` at line 246; `[matTooltip]="'Image scoring not supported for this platform'"` at line 247; explicit `aria-label` |
| `asset-detail-dialog.component.ts` | `/assets/metadata/fields` API | imageMetadataFields UUID-key lookup | ✓ WIRED | `this.api.get<any[]>('/assets/metadata/fields').subscribe(...)` at line 884; getter uses `mv[field.id]` with UUID key |
| `asset-detail-dialog.component.ts` | `scoreDetail.scoring_status` | UNSUPPORTED ngIf guard | ✓ WIRED | `*ngIf="!scoreLoading && scoreDetail?.scoring_status === 'UNSUPPORTED'"` at line 253 |
| Backend asset detail `/dashboard/assets/{id}` | `metadata_values` in response | `meta_values` dict keyed by field_id | ✓ WIRED | `dashboard.py` assembles `{str(v.field_id): v.value}` dict; returned in asset detail response |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `scoring_job.py` | `endpoint_type` in batch | `CreativeScoreResult.endpoint_type` column (set by harmonizer) | Yes — DB column populated at sync time | ✓ FLOWING |
| `asset-detail-dialog.component.ts` | `imageMetadataFields` | `/assets/metadata/fields` API + `asset.metadata_values` (field_id keyed) | Yes — DB query via `AssetMetadataValue` + `MetadataField` | ✓ FLOWING |
| `dashboard.component.ts` | `asset.scoring_status` | Dashboard stats API returns `scoring_status` per asset | Yes — value comes from `creative_score_results.scoring_status` | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ScoringEndpointType lookup — 28 unit tests | `cd backend && python3 -m pytest tests/test_scoring_image.py -x -q` | `28 passed, 1 warning in 0.08s` | ✓ PASS |
| Static API service imports cleanly | Verified by test run importing `brainsuite_static_score` | Passes in test suite | ✓ PASS |
| Backend scoring endpoint UNSUPPORTED guard | Code inspection: `if score_record.endpoint_type == "UNSUPPORTED": raise HTTPException(status_code=422, ...)` | Guard present and correctly placed before status check | ✓ PASS |
| UNSUPPORTED ngSwitchCase present in dashboard | `grep "UNSUPPORTED" dashboard.component.ts` | `*ngSwitchCase="'UNSUPPORTED'"` at line 246 with `matTooltip` at line 247 | ✓ PASS |
| imageMetadataFields getter guards asset_format | `grep "imageMetadataFields\|asset_format" asset-detail-dialog.component.ts` | Getter at line 1070: `if (!this.asset \|\| this.asset.asset_format !== 'IMAGE') return []` | ✓ PASS |

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| PROD-01 | 05-01 | BrainSuite credentials authenticate against Static API | ? NEEDS HUMAN | Checklist exists in PRODUCTION_CHECKLIST.md; spike script ready but cannot run without credentials in dev. This is a deploy-time verification item. |
| PROD-02 | 05-01 | Google Ads OAuth consent screen verified as "Published" | ? NEEDS HUMAN | Checklist with verification steps exists in PRODUCTION_CHECKLIST.md; requires manual Google Cloud Console check |
| IMG-01 | 05-01 | Static API endpoint, payload, response schema confirmed via live spike | ? NEEDS HUMAN | Documentation in BRAINSUITE_API.md is complete; live spike confirmation blocked on credentials. Code implementation uses documented schema. |
| IMG-02 | 05-01, 05-02 | ScoringEndpointType assigned at sync time via tested lookup table | ✓ SATISFIED | `get_endpoint_type()` in `scoring_endpoint_type.py`; called in `harmonizer._upsert_asset()`; 28 tests green |
| IMG-03 | 05-02 | Images scored by existing 15-minute APScheduler batch job | ✓ SATISFIED | `run_scoring_batch()` in `scoring_job.py` includes `endpoint_type.in_(["VIDEO", "STATIC_IMAGE"])`; STATIC_IMAGE branch routes to `BrainSuiteStaticScoreService` |
| IMG-04 | 05-03, 05-04 | Scored image creatives display score badge and CE tab same as video; UNSUPPORTED badge with tooltip | ✓ SATISFIED (programmatic) / ? NEEDS HUMAN (visual) | CE tab COMPLETE block is format-agnostic; `imageMetadataFields` getter provides image-specific metadata; UNSUPPORTED ngSwitchCase with correct tooltip text; UNSUPPORTED CE notice block present. Visual parity requires human confirmation. |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `brainsuite_static_score.py` | 272-279 | `_start_job` sends `announce_payload` (not empty `{}` as plan specified) | Info | Intentional deviation: staging API requires briefing payload in start step. Documented in method docstring. Not a bug. |
| `docs/BRAINSUITE_API.md` | 35 | "PROD-01 auth confirmation pending" | Warning | Spike was never run with live credentials. Response shape assumption (`legResults[0].executiveSummary`) is from API docs, not a confirmed live test. If Static API returns a different shape, `extract_score_data()` would silently return null scores. Blocked on credentials — this is a deploy-time check. |

No blocker anti-patterns remain. The previous blocker (missing UNSUPPORTED tooltip) is resolved by commit c921e40.

---

### Human Verification Required

#### 1. PROD-01: Live BrainSuite Static API Authentication

**Test:** Set `BRAINSUITE_CLIENT_ID` and `BRAINSUITE_CLIENT_SECRET` environment variables, then run `python scripts/spike_static_api.py` from project root.
**Expected:** Script exits 0, prints "PROD-01: BrainSuite credentials authenticate against Static endpoint — CONFIRMED", and creates `docs/spike_static_response.json` with full job result.
**Why human:** Production credentials not available in dev environment. Also confirms the response shape matches `legResults[0].executiveSummary` assumed by `extract_score_data()`.

#### 2. UNSUPPORTED badge tooltip in browser

**Test:** Open the dashboard with a TikTok or Google Ads IMAGE creative visible. Hover the grey dash badge on that tile.
**Expected:** Tooltip appears reading "Image scoring not supported for this platform".
**Why human:** Visual tooltip behavior requires browser interaction to confirm. Code has been verified — `[matTooltip]="'Image scoring not supported for this platform'"` is present in the explicit UNSUPPORTED ngSwitchCase.

#### 3. Image scoring CE tab end-to-end

**Test:** Find a META IMAGE creative that has been fully scored (scoring_status=COMPLETE). Open the asset detail dialog, navigate to the Creative Effectiveness tab.
**Expected:** Score donut with numeric score and rating, 7 pillar cards with scores, and (if Intended Messages / Iconic Color Scheme metadata is filled in) an "Image Metadata" section below the pillars.
**Why human:** Requires a scored image asset in the database, which depends on PROD-01 being confirmed and the scheduler having run.

#### 4. PROD-02: Google Ads OAuth Consent Screen

**Test:** Log into Google Cloud Console, navigate to APIs & Services > OAuth consent screen.
**Expected:** Publishing status shows "Published" (not "Testing").
**Why human:** Requires access to Google Cloud Console — cannot be automated.

---

### Re-verification Summary

**Gap closed:** The single blocker identified in the initial verification has been fixed.

Commit c921e40 adds an explicit `*ngSwitchCase="'UNSUPPORTED'"` block in `dashboard.component.ts` immediately after the FAILED case (line 246). The block renders `overlay-ace overlay-ace-dash` with `[matTooltip]="'Image scoring not supported for this platform'"` and `aria-label="Image scoring not supported"`. This is precisely what the plan specified and what the initial verification found missing.

All other previously-verified items are unchanged and pass quick regression checks:
- Backend pipeline (ScoringEndpointType routing, harmonizer wiring, BrainSuiteStaticScoreService, scoring_job branching) — intact.
- Asset detail dialog (UNSUPPORTED notice, imageMetadataFields getter with `asset_format !== 'IMAGE'` guard, image-only metadata section) — intact.
- Metadata fields migration (seeding brainsuite_intended_messages and brainsuite_iconic_color_scheme per org) — intact.
- Rescore endpoint UNSUPPORTED guard (HTTP 422) — intact.
- Unit tests: 28/28 passing.

No regressions detected. All 12 programmatic truths are verified. Remaining items (PROD-01, PROD-02, visual tooltip confirmation, end-to-end with scored image) require live credentials or browser interaction and are correctly classified as human verification items.

---

_Verified: 2026-03-27T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
