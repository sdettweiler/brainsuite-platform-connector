---
phase: 17-service-instrumentation
plan: "03"
subsystem: api
tags: [sqlalchemy, asyncio, postgresql, background-jobs, download, instrumentation, scheduler]

requires:
  - phase: 17-service-instrumentation
    plan: "01"
    provides: create_background_job / update_background_job helpers in job_tracker.py
  - phase: 17-service-instrumentation
    plan: "02"
    provides: scheduler.py with job_tracker import already in place

provides:
  - _run_google_ads_asset_downloads(): per-asset BackgroundJob progress tracking (job_type="download")
  - _run_dv360_asset_downloads(): per-asset BackgroundJob progress tracking (job_type="download")
  - _run_meta_creatives_deferred(): per-asset BackgroundJob progress tracking (job_type="download") + org_id param
  - _run_tiktok_creatives_deferred(): per-asset BackgroundJob progress tracking (job_type="download") + org_id param
  - All four helpers: D-11 output manifest (downloaded/failed lists) on COMPLETE, D-13 error dict on FAILED
  - 8 Meta/TikTok call sites updated to pass org_id=connection.organization_id

affects:
  - 17-06 (Wave 3 test implementation — test_instrumentation.py stubs cover INSTR-02 download behaviour)
  - 19 (SuperAdmin Monitoring UI — reads download BackgroundJob rows with progress_current/progress_total)

tech-stack:
  added: []
  patterns:
    - "Per-asset loop pattern: enumerate(asset_queue.items(), start=1) / enumerate(ad_ids, start=1) — idx runs 1..N for incremental progress updates (D-05, D-15)"
    - "Per-asset exception isolation: inner try/except accumulates to failed[] without aborting batch; _CookiesExpiredError re-raised to outer handler"
    - "bg_job_id = None sentinel before try block — safe no-op in all except handlers if create_background_job raises before assignment"
    - "inline import traceback as _tb — matches pre-existing style in file; avoids top-level import shadowing"

key-files:
  created: []
  modified:
    - backend/app/services/sync/scheduler.py

key-decisions:
  - "Per-asset loop replaces single batch call: download_assets_post_commit / fetch_and_store_creatives_deferred / enrich_creatives_deferred each called once per asset with a single-item queue/list — enables progress_current=idx increment after each individual asset (D-05)"
  - "Meta and TikTok helpers add org_id=None parameter — required because these helpers previously had no connection lookup (thin pass-through); org_id passed from all 8 call sites where connection is already in scope"
  - "DV360 backfill_failed_autofill_for_connection create_task placed after the per-asset loop but before the COMPLETE update — preserves existing semantics (fire-and-forget after all downloads done)"
  - "COMPLETE update uses progress_current=len(batch) not idx — idempotent final state even if loop exits early via re-raise"

requirements-completed:
  - INSTR-02
  - INSTR-05

duration: 18min
completed: 2026-05-11
---

# Phase 17 Plan 03: Download Helper Instrumentation Summary

**All four deferred-download/creative helpers in scheduler.py now create BackgroundJob records with per-asset progress tracking (D-05), D-11 output manifests (downloaded/failed lists), and D-13 error dicts — covering Google Ads, DV360, Meta, and TikTok platforms**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-05-11T07:38:00Z
- **Completed:** 2026-05-11T07:56:12Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- `_run_google_ads_asset_downloads`: refactored from single `download_assets_post_commit(db, connection, asset_queue)` batch call to per-asset loop; creates BackgroundJob with `job_type="download"`, sets RUNNING with `progress_total=len(asset_queue)`, increments `progress_current=idx` after each asset, writes D-11 `{"downloaded": [...], "failed": [...]}` on COMPLETE; `_CookiesExpiredError` preserved — writes `youtube_cookies_runtime_expired=True` to DB
- `_run_dv360_asset_downloads`: same per-asset loop pattern; `backfill_failed_autofill_for_connection` task placement preserved (fires after all assets done, before COMPLETE); `_CookiesExpiredError` handler preserved
- `_run_meta_creatives_deferred`: refactored from 2-line pass-through to full BackgroundJob lifecycle; adds `org_id=None` parameter; per-`ad_id` loop calling `fetch_and_store_creatives_deferred(connection_id, [ad_id])` one at a time
- `_run_tiktok_creatives_deferred`: same as Meta but calls `enrich_creatives_deferred(connection_id, [ad_id])`
- All 8 call sites (lines 299, 301, 977, 979, 1328, 1330, 1645, 1647) updated to pass `org_id=connection.organization_id`
- `metadata_` dict contains `{"platform": "<platform>", "asset_count": len(batch)}` on every create call (INSTR-05)

## Task Commits

1. **Task 1: Add per-asset BackgroundJob instrumentation to all four deferred helpers** — `b1fb07c` (feat)

## Files Created/Modified

- `backend/app/services/sync/scheduler.py` — 277 net insertions; 14 lines of old helper bodies replaced; all 8 call sites updated

## Decisions Made

- Per-asset loop is the correct interpretation of D-05: `progress_current` must reflect individual assets, not entire batches. Each call to `download_assets_post_commit` or `fetch_and_store_creatives_deferred` is scoped to a single-item queue/list per iteration.
- Meta and TikTok helpers previously had no DB session; `org_id` is now passed from call sites (all have `connection` in scope) rather than doing an additional connection lookup inside the helper — cleaner and avoids an extra DB round-trip.
- `bg_job_id = None` sentinel placed before the `try` block in all four helpers — consistent with plan 17-02 pattern for safe no-ops in exception handlers.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all four helpers write real BackgroundJob rows with real progress/output data.

## Threat Flags

No new network endpoints, auth paths, or file access patterns. T-17-08 (DoS via N+1 DB writes) is mitigated: asset batches are bounded by platform API page sizes (typically <100). T-17-09 (traceback disclosure) is mitigated: truncated at 10,000 chars; `_CookiesExpiredError` uses empty traceback string.

---

## Self-Check: PASSED

- `backend/app/services/sync/scheduler.py` — FOUND (modified; syntax ok)
- `job_type="download"` — FOUND (4 occurrences)
- `progress_total=len(asset_queue)` — FOUND (2 occurrences, Google Ads + DV360)
- `progress_total=len(ad_ids)` — FOUND (2 occurrences, TikTok + Meta)
- `"platform": "google_ads"` — FOUND (1 occurrence)
- `"platform": "dv360"` — FOUND (1 occurrence)
- `"platform": "meta"` — FOUND (1 occurrence)
- `"platform": "tiktok"` — FOUND (1 occurrence)
- `org_id=None` in Meta signature — FOUND
- `org_id=None` in TikTok signature — FOUND
- 8 call sites with `org_id=connection.organization_id` — FOUND (8 deferred helper call sites)
- `for idx, (asset_id, asset_info) in enumerate(asset_queue.items(), start=1)` — FOUND (2 occurrences)
- `for idx, ad_id in enumerate(ad_ids, start=1)` — FOUND (2 occurrences)
- `await update_background_job(bg_job_id, status="RUNNING", progress_current=idx)` — FOUND (4 occurrences)
- `"downloaded": downloaded` — FOUND (4 occurrences in COMPLETE output dicts)
- `youtube_cookies_runtime_expired=True` — FOUND (2 occurrences, Google Ads + DV360)
- `backfill_failed_autofill_for_connection` in DV360 helper — FOUND
- Python syntax check — PASSED
- pytest tests/services/test_scheduler.py — 1 passed, 0 failures
- Commit `b1fb07c` — FOUND

---
*Phase: 17-service-instrumentation*
*Completed: 2026-05-11*
