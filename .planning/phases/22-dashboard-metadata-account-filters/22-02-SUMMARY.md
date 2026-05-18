---
phase: 22-dashboard-metadata-account-filters
plan: "02"
subsystem: frontend + backend
tags: [dashboard, filters, metadata, angular, autocomplete, chips, ad-accounts]
dependency_graph:
  requires:
    - "GET /dashboard/metadata-fields (22-01)"
    - "GET /dashboard/metadata-fields/{field_id}/values (22-01)"
    - "metadata_filter param on GET /dashboard/assets (22-01)"
  provides:
    - "Metadata filter button + dropdown panel in dashboard filter bar"
    - "Per-field autocomplete with multi-value selection (OR within field, AND across fields)"
    - "Chip row showing active metadata filters with individual remove + Clear all"
    - "Ad account dropdown with platform section headers (META → TIKTOK → GOOGLE ADS → DV360)"
    - "OR-within-field backend grouping (amv.value.in_() per field bucket)"
  affects:
    - frontend/src/app/features/dashboard/dashboard.component.ts
    - backend/app/api/v1/endpoints/dashboard.py
tech_stack:
  added: []
  patterns:
    - "memoized groupedAdAccounts getter to prevent ngFor teardown on click"
    - "Single fetch per field on selectMetadataField() — values cached in component state"
    - "activeMetadataFilters: {field, fieldLabel, value}[] drives chip row and params builder"
    - "Backend: bucket same-field filters → .in_() OR; different fields still use aliased AND-JOINs"
key_files:
  modified:
    - frontend/src/app/features/dashboard/dashboard.component.ts
    - backend/app/api/v1/endpoints/dashboard.py
decisions:
  - "OR logic within a field, AND logic across fields — matches DASH-01 D-07/D-08 spec"
  - "Value list stays open after selection (multi-pick per field); items toggle with checkmarks"
  - "Duplicate chips prevented — selecting an already-active value is a no-op"
  - "memoize groupedAdAccounts to prevent ngFor teardown + mat-menu close on each click"
  - "Platform grouping order: META → TIKTOK → GOOGLE ADS → DV360; flat-list fallback when only one platform connected"
  - "Search input added to ad account dropdown for large account lists"
metrics:
  completed_date: "2026-05-15"
  tasks_completed: 6
  commits: [88518fa, cfb37d4, 527abd2, 2e8944e, 358819b, 12e7a4c]
---

# Phase 22 Plan 02: Dashboard Filter UI Summary

**One-liner:** Angular metadata filter button, autocomplete dropdown, multi-value chip row, and platform-grouped ad account selector shipped to `dashboard.component.ts`; backend updated for OR-within-field grouping.

---

## What Was Built

### Task 1 — TS State + Methods (commit 88518fa)
Added to `dashboard.component.ts`:
- `activeMetadataFilters: {field: string, fieldLabel: string, value: string}[]`
- `metadataFields: {id, name, label}[]` loaded on filter panel open
- `selectMetadataField(field)` — fetches values via `GET /dashboard/metadata-fields/{id}/values` once per field; caches in `currentFieldValues`
- `addMetadataFilter(value)` — adds chip (deduplication guard), collapses panel, triggers `loadData()`
- `removeMetadataFilter(index)` — removes chip, triggers `loadData()`
- `clearAllMetadataFilters()` — resets state, triggers `loadData()`
- `loadData()` params builder extended: `metadata_filter = activeMetadataFilters.map(f => \`${f.field}:${f.value}\`)`
- `groupedAdAccounts` getter (memoized) producing ordered platform sections for the ad account dropdown

### Task 2 — Template + Chip Row (commit cfb37d4)
- Metadata filter button in filter bar (after Ad Accounts, before Sort)
- Dropdown panel with field list; on selection shows autocomplete input with loaded values
- Chip row below toolbar — each chip renders `FieldLabel: value ×`; "Metadata (N)" badge on button when filters active
- "Clear all filters" button in chip row when ≥ 2 chips active
- Ad account mat-menu updated with non-clickable platform section headers

### Task 3 — Bug fix: ng-template else branch (commit 527abd2)
Replaced `ng-template` else-branch pattern with direct `*ngIf`/`*ngFor` — the template ref caused the account dropdown to close immediately on click.

### Task 4 — Memoize groupedAdAccounts (commit 2e8944e)
`groupedAdAccounts` getter was recomputing on every change detection cycle, causing ngFor to tear down and re-create the DOM, which closed the mat-menu on each render tick. Fixed by memoizing on `adAccounts` reference equality.

### Task 5 — Search input for ad account dropdown (commit 358819b)
Added a text input at the top of the ad account dropdown to filter displayed accounts client-side — useful when an org has 10+ ad accounts across platforms.

### Task 6 — OR-within-field logic (commit 12e7a4c)
**Backend:** `dashboard.py` updated — `metadata_filter` entries are first bucketed by field name; each bucket uses a single aliased JOIN with `amv.value.in_(values)` (OR); different-field buckets still use separate JOINs (AND). This lets the user pick multiple values for the same field (e.g. `language: Indonesian OR English`) without requiring separate JOINs per value.

**Frontend:** Value list stays open after selection; items render checkmarks for active selections; adding a value that is already in `activeMetadataFilters` for that field is a no-op (no duplicate chips).

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Bug] ng-template else-branch closed mat-menu on click**
- `*ngIf` with `else templateRef` caused the overlay to re-render and dismiss. Fixed by removing the `ng-template` and using direct structural directives.

**2. [Bug] groupedAdAccounts getter triggered teardown on every CD cycle**
- Memoized on `adAccounts` reference; only recomputes when the array changes.

---

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| Metadata filter button in dashboard filter bar | SHIPPED (88518fa + cfb37d4) |
| Autocomplete per field (single fetch on selection) | SHIPPED (88518fa) |
| Chip row with remove + Clear all | SHIPPED (cfb37d4) |
| OR within field, AND across fields | SHIPPED (12e7a4c) |
| Platform-grouped ad account dropdown | SHIPPED (88518fa + cfb37d4) |
| Ad account search input | SHIPPED (358819b) |
| Mat-menu teardown fix (memoize + ngFor) | SHIPPED (527abd2 + 2e8944e) |
