---
phase: 08-score-to-roas-correlation
plan: "02"
subsystem: frontend/dashboard
tags: [scatter-chart, echarts, correlation, roas, drawer, angular-material]
dependency_graph:
  requires: ["08-01"]
  provides: [correlation-drawer, scatter-chart, roas-tile-click]
  affects: [frontend/src/app/features/dashboard/dashboard.component.ts]
tech_stack:
  added: [ScatterChart (echarts), MarkLineComponent (echarts), MatSidenavModule (mat sidenav)]
  patterns: [fixed-position overlay drawer, ECharts scatter series with markLine, client-side spend filtering]
key_files:
  modified:
    - frontend/src/app/features/dashboard/dashboard.component.ts
decisions:
  - Used fixed-position overlay div instead of MatSidenav to avoid height-propagation issues — documented in plan as accepted alternative
  - ECharts ScatterChart + MarkLineComponent added to echarts.use() call alongside existing LineChart
  - loadCorrelationData uses selectedPlatforms (not platformFilter) — plan referenced platformFilter which does not exist; auto-corrected to match actual codebase
metrics:
  duration: 15
  completed: "2026-03-31T13:15:00Z"
  tasks_completed: 1
  tasks_total: 2
  files_modified: 1
---

# Phase 8 Plan 02: Scatter Chart Correlation Drawer Summary

Scatter chart right-side overlay drawer triggered by ROAS stat tile click — plots ACE Score vs. ROAS per scored creative with quadrant framing, median reference lines, hover tooltips, dot-click to asset detail, and spend threshold filtering.

## What Was Built

Added a complete score-vs-ROAS correlation drawer to `dashboard.component.ts`:

- **ROAS tile affordance**: Avg ROAS stat tile gains `clickable: true`, `bi-bar-chart-line` icon, hover border accent, and `matTooltip="Explore score vs. ROAS correlation"`
- **Correlation drawer**: Fixed-position 560px overlay from right (z-index 1001), animated slide-in via CSS transform, semi-transparent backdrop (z-index 1000) that closes on click
- **ECharts scatter chart**: ScatterChart + MarkLineComponent registered; `buildScatterChart()` computes medians, 99th-pct ROAS cap, quadrant dot colors, and full EChartsOption
- **Quadrant system**: Stars (#FF7700), Workhorses (#F39C12), Question Marks (#4285F4), Laggards (#707070) — color callback in itemStyle
- **Reference lines**: Vertical median score + horizontal median ROAS (dashed #404040) + 99th-pct cap line (accent orange at 40% opacity)
- **Dot hover tooltip**: HTML-formatted tooltip with 48×48 thumbnail, ad name, score · ROAS · spend · platform
- **Dot click**: `onScatterClick()` guards `componentType === 'series'` to ignore markLine clicks; closes drawer and opens `AssetDetailDialogComponent` after 200ms
- **Spend threshold**: `correlationMinSpend = 10`; `onCorrelationMinSpendChange()` calls `buildScatterChart()` — no API call, synchronous client-side filter
- **Empty/error/loading states**: skeleton shimmer during load, error message, empty-state with `bi-scatter` icon and descriptive copy
- **Legend row**: Four color swatches with quadrant labels
- **Cap annotation**: "ROAS capped at 99th pct." right-aligned below chart

## Deviations from Plan

### Auto-corrected Issues

**1. [Rule 1 - Bug] `platformFilter` reference replaced with `selectedPlatforms`**
- **Found during:** Task 1
- **Issue:** Plan's `loadCorrelationData()` pseudocode referenced `this.platformFilter || undefined` — this property does not exist in the component; the actual filter is `this.selectedPlatforms` (a `Set<string>`)
- **Fix:** Used `[...this.selectedPlatforms].join(',')` matching the pattern in `loadData()` and `loadScoreTrend()`
- **Files modified:** frontend/src/app/features/dashboard/dashboard.component.ts

**2. [Rule 1 - Bug] Duplicate `id` property in spread object**
- **Found during:** Task 1 build check
- **Issue:** `{ id: asset.id, ...asset }` caused TS2783 — `id` specified twice since `asset` already has `id`
- **Fix:** Simplified to `{ ...asset }` — `CorrelationAsset.id` is already present in the spread
- **Files modified:** frontend/src/app/features/dashboard/dashboard.component.ts

**3. [Plan option selected] Fixed-position overlay instead of MatSidenav**
- **Rationale:** Plan section 7 explicitly offered fixed-position div as acceptable alternative to avoid MatSidenav height-propagation issues
- **Implementation:** `position: fixed; right: 0; top: 0; height: 100vh; width: 560px; z-index: 1001` with CSS transform slide animation
- Not a deviation — explicitly permitted by plan

## Known Stubs

None — the scatter chart calls the live `/dashboard/correlation-data` endpoint built in Plan 01.

## Checkpoint Pending

Task 2 is `checkpoint:human-verify` — awaiting manual end-to-end verification of the drawer in a running environment before marking plan complete.

## Self-Check: PASSED

- [x] `frontend/src/app/features/dashboard/dashboard.component.ts` modified and committed (9f6ef73)
- [x] Build: `npx ng build --configuration=development` — zero errors (only pre-existing warnings in asset-detail-dialog.component.ts)
- [x] All acceptance criteria verified: ScatterChart, MarkLineComponent, CorrelationAsset interface, correlationDrawerOpen, correlationMinSpend, loadCorrelationData, buildScatterChart, onScatterClick, correlation-data endpoint, "Score vs. ROAS", quadrant labels, roas !== null guard, 99th percentile, agg-stat-clickable, Explore tooltip, bi-bar-chart-line icon
