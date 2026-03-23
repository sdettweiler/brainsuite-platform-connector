---
phase: 03-brainsuite-scoring-pipeline
plan: 05
subsystem: frontend
status: paused-at-checkpoint
tags: [angular, scoring-ui, dashboard, polling, ux]
dependency_graph:
  requires: [03-04]
  provides: [scoring-ui-surface, creative-effectiveness-tab]
  affects: [dashboard.component.ts, asset-detail-dialog.component.ts]
tech_stack:
  added: [MatProgressSpinnerModule, MatSnackBarModule, MatDividerModule]
  patterns: [smart-polling, rxjs-interval, switchMap-polling]
key_files:
  created: []
  modified:
    - frontend/src/app/features/dashboard/dashboard.component.ts
    - frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts
    - frontend/src/app/core/services/api.service.ts
    - frontend/src/styles.scss
decisions:
  - "Score badge uses ngSwitch on scoring_status (not ace_score) — aligns with Plan 04 API changes"
  - "Polling resets on every data load: stopPolling$.next() before startScoringPolling ensures old subscription is cleared"
  - "rescoreAsset in dashboard sets pollingActive guard before re-starting polling for single asset"
  - "Dialog loads score detail independently on open via getScoreDetail(assetId)"
metrics:
  duration_minutes: 25
  completed_tasks: 2
  total_tasks: 3
  files_modified: 4
  completed_date: "2026-03-23"
---

# Phase 03 Plan 05: Frontend Scoring UI Summary

**One-liner:** Score badge with UNSCORED/PENDING/PROCESSING/COMPLETE/FAILED states, 10-second smart polling, Score now context menu, and Creative Effectiveness tab with live BrainSuite score data.

## Status

Paused at checkpoint Task 3 (human visual verification). Tasks 1 and 2 complete.

---

## Completed Tasks

### Task 1: Dashboard score badge + polling + context menu
**Commit:** `f8fd95f`

- Replaced `ace_score` overlay with a 5-state score badge using `ngSwitch` on `scoring_status`
- COMPLETE state: colored circle (`.ace-positive`/`.ace-medium`/`.ace-negative`) with `aria-label` and tooltip
- PENDING/PROCESSING state: `mat-spinner diameter=20` + "Scoring…" label inline
- UNSCORED/FAILED state: grey dash "–" with `aria-label="Not yet scored"` or tooltip "Scoring failed"
- Smart polling: `interval(10000)` + `switchMap` + `stopPolling$` Subject — starts when page loads with pending assets, stops when none remain
- Score now: context menu item calling `POST /scoring/{id}/rescore` via `ApiService.rescoreAsset()`; shows MatSnackBar toast on success/error
- Added `getScoringStatus()`, `rescoreAsset()`, `getScoreDetail()` to `ApiService`
- Added `.ace-positive`, `.ace-negative`, `.score-dash`, `.scoring-label` to `styles.scss`

**Files modified:**
- `frontend/src/app/features/dashboard/dashboard.component.ts`
- `frontend/src/app/core/services/api.service.ts`
- `frontend/src/styles.scss`

### Task 2: Creative Effectiveness tab in asset-detail-dialog
**Commit:** `70387a4`

- Replaced "DUMMY DATA" placeholder with real score display driven by `getScoreDetail(assetId)` on dialog open
- Loading state: centered `mat-spinner diameter=32`
- COMPLETE state: score hero row (Effectiveness Score label + colored circle badge + rating label) + `mat-divider` + categories list per `score_dimensions.output.legResults[0].categories`
- PENDING/PROCESSING state: centered spinner + "BrainSuite is scoring this creative…"
- UNSCORED/FAILED state: `bi-graph-up` icon + "No score yet" / "Scoring failed" copy + Score now `mat-stroked-button`
- `rescoreFromDialog()` optimistically sets `scoreDetail = { scoring_status: 'PENDING' }` and shows toast
- Added component-scoped CSS: `.score-hero-row`, `.score-category-row`, `.rating-dot`, `.score-pending-state`, `.score-empty-state`, `.score-loading-state`

**Files modified:**
- `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts`

---

## Task 3: Visual verification (CHECKPOINT — awaiting human)

Human verification required. See checkpoint message above.

---

## Deviations from Plan

**1. [Rule 2 - Enhancement] Polling guard reset on page reload**
- **Found during:** Task 1 implementation
- **Issue:** Plan's polling code didn't account for navigating between pages (filter/page changes call `loadData()` again, which could leave stale polling subscriptions)
- **Fix:** Added `this.stopPolling$.next(); this.pollingActive = false;` before `startScoringPolling()` in the `loadData()` subscribe callback — ensures clean restart on every page load
- **Files modified:** `dashboard.component.ts`
- **Commit:** `f8fd95f`

**2. [Rule 2 - Enhancement] rescoreAsset pollingActive guard**
- **Found during:** Task 1 implementation
- **Issue:** If user clicks "Score now" while polling is already active (other pending assets), the guard `if (pendingIds.length === 0 || this.pollingActive) return` would skip adding the new asset to polling
- **Fix:** Changed to only call `startScoringPolling([asset])` when `!this.pollingActive`, so the existing polling subscription picks up the newly-PENDING asset on next tick
- **Files modified:** `dashboard.component.ts`
- **Commit:** `f8fd95f`

---

## Known Stubs

None — score data is wired to live BrainSuite API responses. Categories list will be empty if `score_dimensions.output.legResults` is absent (returns empty array from `getCategories()`).

---

## Self-Check

- FOUND: `frontend/src/app/features/dashboard/dashboard.component.ts`
- FOUND: `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts`
- FOUND: `frontend/src/app/core/services/api.service.ts`
- FOUND: `frontend/src/styles.scss`
- FOUND: commit `f8fd95f` (Task 1)
- FOUND: commit `70387a4` (Task 2)

## Self-Check: PASSED
