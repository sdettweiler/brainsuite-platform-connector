---
phase: quick
plan: 260401-qpu
subsystem: dashboard
tags: [scatter-chart, correlation, metrics, frontend, backend]
dependency_graph:
  requires: []
  provides: [dynamic-y-axis-metric-selector-scatter-chart]
  affects: [dashboard-correlation-drawer]
tech_stack:
  added: []
  patterns: [weighted-avg-metrics-subquery, mat-select-dynamic-chart-axis]
key_files:
  created: []
  modified:
    - backend/app/api/v1/endpoints/dashboard.py
    - backend/tests/test_correlation.py
    - frontend/src/app/features/dashboard/dashboard.component.ts
decisions:
  - "Weighted averages re-derived from raw sums (not averages of daily rates) — consistent with existing ROAS pattern"
  - "selectedCorrelationMetric defaults to 'roas' ensuring backward-compatible drawer open behavior"
  - "correlationMetrics config array drives all dynamic behavior: label, format fn, suffix — single source of truth"
metrics:
  duration: ~3 minutes
  completed: 2026-04-01
  tasks_completed: 2
  files_modified: 3
---

# Quick Task 260401-qpu: Add Metric Selector Dropdown to Scatter Chart Summary

**One-liner:** Metric selector dropdown in scatter chart drawer — 7 selectable metrics (ROAS/CTR/VTR/CPM/CVR/CPC/Conversions) with dynamic axis, tooltip, and cap note via correlationMetrics config array.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend backend correlation-data endpoint with additional metrics | bd6c766 | dashboard.py, test_correlation.py |
| 2 | Add metric selector dropdown and dynamic Y-axis | 33cceed | dashboard.component.ts |

## What Was Built

### Backend (Task 1)
- Extended `perf_subq` subquery in `get_correlation_data` to aggregate 6 new metrics using weighted averages:
  - `ctr`: SUM(clicks) / NULLIF(SUM(impressions), 0) * 100
  - `vtr`: SUM(video_views) / NULLIF(SUM(impressions), 0) * 100
  - `cpm`: SUM(spend) / NULLIF(SUM(impressions), 0) * 1000
  - `cvr`: SUM(conversions) / NULLIF(SUM(clicks), 0) * 100
  - `cpc`: SUM(spend) / NULLIF(SUM(clicks), 0)
  - `conversions`: SUM(conversions)
- Updated main `select()` to include all 6 new columns via `perf_subq.c.*`
- Extended `_serialize_correlation_asset` to serialize all new fields with `is not None` guard
- Updated test file: expanded `test_serialization_returns_expected_keys` to include new keys; added `test_new_metric_fields_returned_as_float` and `test_new_metric_fields_null_when_absent`

### Frontend (Task 2)
- Extended `CorrelationAsset` interface with `ctr`, `vtr`, `cpm`, `cvr`, `cpc`, `conversions` fields
- Added `correlationMetrics` config array (readonly) with key, label, format fn, suffix per metric
- Added `selectedCorrelationMetric = 'roas'` class property (backward-compatible default)
- Replaced static `<h4>Score vs. ROAS</h4>` with dynamic `mat-form-field` + `mat-select` dropdown
- Refactored `buildScatterChart()` to derive all dynamic values from selected metric config
- Updated `correlationEligibleCount` getter to filter on selected metric key
- Added `selectedMetricLabel` getter for template bindings
- Updated empty-state message and cap note to use `selectedMetricLabel`
- Added CSS for dropdown styling in dark drawer theme

## Verification

- `pytest backend/tests/test_correlation.py -x -v`: 8 passed
- `ng build`: succeeds, no new errors (2 pre-existing NG8107 optional-chain warnings in asset-detail-dialog, out of scope)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all metrics are fully wired from backend aggregation through to chart rendering.

## Self-Check: PASSED
