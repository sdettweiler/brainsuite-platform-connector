---
phase: 03-brainsuite-scoring-pipeline
verified: 2026-03-24T00:00:00Z
status: human_needed
score: 8/8 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 7/8
  gaps_closed:
    - "No broken ace_score / brainsuite_metadata references remain in the codebase"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Scored asset view in Creative Effectiveness tab"
    expected: "When an asset has a COMPLETE score record, the Creative Effectiveness tab in the asset detail dialog shows the score hero row (Effectiveness Score label + colored badge + rating text) followed by the per-category breakdown list."
    why_human: "BrainSuite OAuth credentials are not configured in this environment; no COMPLETE score records can be produced to verify the COMPLETE-state rendering branch."
---

# Phase 3: BrainSuite Scoring Pipeline Verification Report

**Phase Goal:** Deliver an end-to-end BrainSuite scoring pipeline — from OAuth auth through job submission, polling, score storage, and frontend display — so that creative assets are automatically scored in the background and their effectiveness scores are visible in the dashboard and asset detail view.

**Verified:** 2026-03-24
**Status:** human_needed
**Re-verification:** Yes — after gap closure (previous status: gaps_found, 7/8)

---

## Re-verification Summary

**Gap closed:** The single blocking gap from the initial verification has been resolved.

`backend/app/api/v1/endpoints/assets.py` no longer accesses `asset.brainsuite_metadata` or `asset.ace_score`. Both dropped-column attribute accesses have been removed. The export endpoint dict now contains `"ace_score": None` (static literal — no attribute access, no AttributeError). The `brainsuite_metadata` block is completely absent from the file.

**Scan confirms no new regressions:** A full grep of `backend/app/**/*.py` for `ace_score` and `brainsuite_metadata` finds only:
- `assets.py` line 403: `"ace_score": None` — static literal, safe
- `export_service.py` lines 112 and 176: stale field name keys in `BRAINSUITE_FIELDS` / `DEFAULT_EXPORT_FIELDS` — pre-existing warning, non-crashing, unchanged

All 8 truths are now verified. The only remaining item is the human-verification checkpoint that existed in the initial report (COMPLETE-state rendering in the Creative Effectiveness tab), which cannot be exercised without live BrainSuite credentials.

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|---------|
| 1  | CreativeScoreResult model exists with all required fields and state machine statuses | VERIFIED | `backend/app/models/scoring.py` — full model with UNSCORED/PENDING/PROCESSING/COMPLETE/FAILED statuses, all required columns, UniqueConstraint, CASCADE FK |
| 2  | Alembic migration creates creative_score_results table and drops old ace_score columns | VERIFIED | `e1f2g3h4i5j6_add_creative_score_results.py` — creates table, two indexes, drops ace_score, ace_score_confidence, brainsuite_metadata |
| 3  | BrainSuiteScoreService handles OAuth token caching, 429/5xx retry, job creation, polling, channel mapping, score extraction | VERIFIED | `backend/app/services/brainsuite_score.py` — 430 lines, all methods present and substantive, singleton exported |
| 4  | Scoring batch job runs every 15 minutes via APScheduler, batches up to 20 UNSCORED VIDEO assets, no DB held during HTTP | VERIFIED | `backend/app/services/sync/scoring_job.py` + scheduler.py — BATCH_SIZE=20, IntervalTrigger(minutes=15), max_instances=1, SCHEDULER_ENABLED guard, Phase 1/Phase 2 session discipline |
| 5  | New VIDEO assets from harmonizer automatically get UNSCORED score records; existing records are NOT reset | VERIFIED | `backend/app/services/sync/harmonizer.py` — pg_insert(CreativeScoreResult).on_conflict_do_nothing at line 885-889 |
| 6  | Scoring API endpoints (rescore, status, detail) exist and are registered | VERIFIED | `backend/app/api/v1/endpoints/scoring.py` — all three endpoints substantive; registered in `__init__.py` at prefix="/scoring" |
| 7  | Dashboard /assets endpoint returns scoring_status and total_score instead of ace_score | VERIFIED | dashboard.py — outerjoin CreativeScoreResult, returns scoring_status/total_score/total_rating; ace_score fully absent |
| 8  | No broken ace_score / brainsuite_metadata references remain in the codebase after model column drops | VERIFIED | `assets.py` export dict now uses static `"ace_score": None` — no attribute access, no AttributeError; `brainsuite_metadata` block fully removed. Remaining `ace_score` strings in export_service.py are non-crashing field-name keys (Warning only). |
| 9  | Frontend score badge, polling, context menu, and Creative Effectiveness tab are implemented | VERIFIED | All four behaviors confirmed in dashboard.component.ts and asset-detail-dialog.component.ts |

**Score:** 8/8 truths verified

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `backend/app/models/scoring.py` | VERIFIED | CreativeScoreResult with all fields, FK, UniqueConstraint, state machine |
| `backend/alembic/versions/e1f2g3h4i5j6_add_creative_score_results.py` | VERIFIED | Creates table + indexes, drops 3 legacy columns, has downgrade |
| `backend/alembic/versions/f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py` | VERIFIED | Seeds 7 MetadataField rows per org, language/stage MetadataFieldValue rows, ON CONFLICT DO NOTHING, downgrade present |
| `backend/app/services/brainsuite_score.py` | VERIFIED | 430 lines — BrainSuiteScoreService, BrainSuiteRateLimitError, BrainSuite5xxError, BrainSuiteJobError, map_channel, build_scoring_payload, extract_score_data, singleton |
| `backend/app/services/sync/scoring_job.py` | VERIFIED | run_scoring_batch, BATCH_SIZE=20, two-phase session discipline, COMPLETE/FAILED transitions |
| `backend/app/services/sync/scheduler.py` | VERIFIED | scoring_batch registered, IntervalTrigger(minutes=15), max_instances=1, SCHEDULER_ENABLED guard |
| `backend/app/services/sync/harmonizer.py` | VERIFIED | CreativeScoreResult import, on_conflict_do_nothing injection for VIDEO assets, no generate_ace_score reference |
| `backend/app/api/v1/endpoints/scoring.py` | VERIFIED | POST /{asset_id}/rescore, GET /status, GET /{asset_id} — all substantive with auth and DB logic |
| `backend/app/api/v1/__init__.py` | VERIFIED | `scoring.router` included at prefix="/scoring" |
| `backend/app/api/v1/endpoints/dashboard.py` | VERIFIED | outerjoin CreativeScoreResult, scoring_status/total_score/total_rating in response, no ace_score |
| `backend/app/schemas/creative.py` | VERIFIED | scoring_status, total_score, total_rating fields present; ace_score absent |
| `backend/app/core/config.py` | VERIFIED | BRAINSUITE_CLIENT_ID, BRAINSUITE_CLIENT_SECRET, BRAINSUITE_BASE_URL, BRAINSUITE_AUTH_URL, SCHEDULER_ENABLED all present |
| `backend/requirements.txt` | VERIFIED | tenacity>=8.2.0 present |
| `backend/tests/test_scoring.py` | VERIFIED | 23 test items collected (pytest --collect-only) — all required stubs present with skip decorators |
| `scripts/setup.py` | VERIFIED | BRAINSUITE_CLIENT_ID/SECRET/BASE_URL/AUTH_URL prompts; no BRAINSUITE_API_KEY |
| `.env.example` | VERIFIED | All 4 BRAINSUITE_* env vars documented |
| `frontend/src/app/features/dashboard/dashboard.component.ts` | VERIFIED | scoring_status/total_score/total_rating in DashboardAsset, score badge with ngSwitch, interval(10000) polling, stopPolling$, rescoreAsset method, "Score now" context menu, mat-spinner, "Scoring…" label, aria-label |
| `frontend/src/app/core/services/api.service.ts` | VERIFIED | getScoringStatus, rescoreAsset, getScoreDetail methods present |
| `frontend/src/styles.scss` | VERIFIED | .ace-positive, .ace-medium, .ace-negative, .score-dash, .scoring-label CSS classes present |
| `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` | VERIFIED | scoreDetail, getScoreDetail call on init, getCategories, rescoreFromDialog, "Effectiveness Score", "BrainSuite is scoring this creative…", "No score yet", "Scoring failed", "Score now", score-hero-row, score-category-row, mat-spinner |
| `backend/app/services/ace_score.py` | VERIFIED (deleted) | File does not exist — dummy scorer fully removed |
| `backend/app/api/v1/endpoints/assets.py` | VERIFIED | `brainsuite_metadata` block removed; `ace_score` is now static `None` literal — no attribute access on dropped column |
| `backend/app/services/export_service.py` | WARNING | BRAINSUITE_FIELDS still contains stale 'ace_score' key; DEFAULT_EXPORT_FIELDS still contains 'ace_score' — non-crashing, produces an empty column in exports |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/services/brainsuite_score.py` | `backend/app/core/config.py` | `settings.BRAINSUITE_CLIENT_ID`, `settings.BRAINSUITE_BASE_URL`, `settings.BRAINSUITE_AUTH_URL` | WIRED | All four settings referenced in service |
| `backend/app/services/sync/scoring_job.py` | `backend/app/services/brainsuite_score.py` | `brainsuite_score_service.create_job_with_retry()`, `poll_job_status()` | WIRED | Both calls present with response handling |
| `backend/app/services/sync/scoring_job.py` | `backend/app/services/object_storage.py` | `get_object_storage().generate_signed_url()` | WIRED | Line 86 — called with s3_key and ttl_sec |
| `backend/app/services/sync/harmonizer.py` | `backend/app/models/scoring.py` | `pg_insert(CreativeScoreResult).on_conflict_do_nothing(index_elements=["creative_asset_id"])` | WIRED | Lines 885-889 — exactly the specified pattern |
| `backend/app/api/v1/endpoints/scoring.py` | `backend/app/models/scoring.py` | `CreativeScoreResult` queries | WIRED | All three endpoints query CreativeScoreResult |
| `backend/app/api/v1/__init__.py` | `backend/app/api/v1/endpoints/scoring.py` | `api_router.include_router(scoring.router)` | WIRED | Line 11 of __init__.py |
| `backend/app/api/v1/endpoints/dashboard.py` | `backend/app/models/scoring.py` | `outerjoin(CreativeScoreResult, ...)` | WIRED | Line 189 — outerjoin present, scoring_status/total_score in SELECT |
| `frontend/dashboard.component.ts` | `/api/v1/scoring/status` | `interval(10000)` + `switchMap` polling | WIRED | Line 915 — interval(10000), takeUntil(stopPolling$), api.getScoringStatus |
| `frontend/dashboard.component.ts` | `/api/v1/scoring/{id}/rescore` | POST on context menu click | WIRED | rescoreAsset method calls api.rescoreAsset(asset.id) |
| `frontend/asset-detail-dialog.component.ts` | `/api/v1/scoring/{asset_id}` | GET on dialog open | WIRED | Line 805 — api.getScoreDetail(this.data.assetId) in ngOnInit |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `dashboard.component.ts` score badge | `asset.scoring_status`, `asset.total_score` | Dashboard `/assets` endpoint → outerjoin CreativeScoreResult | Yes — real DB join to creative_score_results table | FLOWING |
| `asset-detail-dialog.component.ts` effectiveness tab | `scoreDetail` | GET `/api/v1/scoring/{asset_id}` → scoring.py get_score_detail | Yes — queries CreativeScoreResult directly | FLOWING |
| Polling update in dashboard | `asset.scoring_status` patch | GET `/api/v1/scoring/status` → scoring.py get_scoring_status | Yes — live DB query per poll | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Check | Result | Status |
|----------|-------|--------|--------|
| Test stubs collected by pytest | `python3 -m pytest backend/tests/test_scoring.py --collect-only` | 23 tests collected | PASS |
| scoring_batch registered in scheduler | grep for `scoring_batch`, `IntervalTrigger(minutes=15)`, `max_instances=1` | All three found in scheduler.py | PASS |
| on_conflict_do_nothing prevents COMPLETE reset | grep harmonizer.py | `on_conflict_do_nothing(index_elements=["creative_asset_id"])` at line 889 | PASS |
| ace_score.py fully deleted | `test ! -f backend/app/services/ace_score.py` | File does not exist | PASS |
| Export endpoint runtime crash (re-check) | grep assets.py for `ace_score\|brainsuite_metadata` attribute access | Only `"ace_score": None` (static literal) remains; `brainsuite_metadata` block fully absent | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| SCORE-01 | 03-01 | `creative_score_results` table with scoring state machine | SATISFIED | Model + migration verified |
| SCORE-02 | 03-02, 03-06 | BrainSuiteScoreService with OAuth + retry logic | SATISFIED | brainsuite_score.py — token caching, 429/5xx retry, 4xx raise, all branches present |
| SCORE-03 | 03-02 | Fresh signed S3 URLs generated per scoring request | SATISFIED | scoring_job.py line 86 — generate_signed_url(s3_key, ttl_sec=3600) called per asset |
| SCORE-04 | 03-03, 03-06 | APScheduler job every 15 min, up to 20 UNSCORED assets | SATISFIED | scheduler.py + scoring_job.py — BATCH_SIZE=20, IntervalTrigger(minutes=15) |
| SCORE-05 | 03-03 | New assets auto-queued as UNSCORED after platform sync | SATISFIED | harmonizer.py — on_conflict_do_nothing injection for VIDEO assets |
| SCORE-06 | 03-04, 03-05 | Manual re-score trigger via UI and API | SATISFIED | POST /scoring/{asset_id}/rescore endpoint + frontend "Score now" context menu + dialog button |
| SCORE-07 | 03-04, 03-05 | Score dimensions stored and retrievable per creative | SATISFIED | GET /scoring/{asset_id} returns score_dimensions; extract_score_data strips visualizations; Creative Effectiveness tab calls getScoreDetail |
| SCORE-08 | 03-04, 03-05 | Scoring status endpoint for frontend polling | SATISFIED | GET /scoring/status endpoint substantive + frontend interval(10000) polling wired |

All 8 SCORE requirements (SCORE-01 through SCORE-08) are satisfied by the implementation. No orphaned requirements for Phase 3.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/services/export_service.py` | 112, 176 | `"ace_score"` key in BRAINSUITE_FIELDS and DEFAULT_EXPORT_FIELDS | Warning | Stale column name in CSV/Excel export field definitions; produces an empty column in exports (assets.py supplies `None` for this key). Non-crashing. |

The two Blocker entries from the initial verification (`assets.py` lines 382 and 405) have been resolved and are no longer present.

---

### Human Verification Required

#### 1. Scored Asset Creative Effectiveness Tab

**Test:** Configure BrainSuite OAuth credentials (`BRAINSUITE_CLIENT_ID`, `BRAINSUITE_CLIENT_SECRET`) in `.env`, start the stack with `docker compose up`, trigger scoring on a VIDEO asset via "Score now", wait for the scoring job to complete (~2 minutes), then open the asset detail dialog and switch to the Creative Effectiveness tab.

**Expected:** The tab shows the "Effectiveness Score" label on the left with a colored score badge (green/amber/red) and rating text on the right, followed by a horizontal rule and a list of per-category score rows (category name on left, score value + colored dot on right).

**Why human:** BrainSuite OAuth credentials are not configured in this test environment. No COMPLETE score records can be produced, so the COMPLETE-state rendering branch in asset-detail-dialog.component.ts cannot be exercised programmatically.

---

### Gaps Summary

All automated gaps are resolved. The phase goal is **fully achieved** across all 8 observable truths and all 8 SCORE requirements.

The one remaining item (COMPLETE-state Creative Effectiveness tab rendering) requires live BrainSuite credentials and cannot be verified programmatically. All code paths for that branch are present and wired; the question is purely whether the rendered output matches the UI spec — a visual and behavioral check that requires a human with credentials.

The pre-existing Warning in `export_service.py` (stale `ace_score` field name in export field definitions) is not a blocker. It will produce an empty column in CSV/Excel exports labelled "ACE Score" — cosmetic noise that can be cleaned up independently.

---

_Verified: 2026-03-24 (re-verification after gap closure)_
_Verifier: Claude (gsd-verifier)_
