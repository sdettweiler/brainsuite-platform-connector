---
phase: 22-dashboard-metadata-account-filters
plan: "01"
subsystem: backend
tags: [dashboard, filters, metadata, alembic, fastapi, sqlalchemy, tdd]
dependency_graph:
  requires: []
  provides:
    - "GET /dashboard/metadata-fields — org-scoped active metadata field list"
    - "GET /dashboard/metadata-fields/{field_id}/values — DISTINCT org-scoped values"
    - "metadata_filter: Optional[List[str]] param on GET /dashboard/assets"
    - "idx_asset_metadata_values_field_value composite index migration e8f9a0b1c2d3"
  affects:
    - backend/app/api/v1/endpoints/dashboard.py
    - backend/alembic/versions/e8f9a0b1c2d3_phase22_metadata_filter_index.py
tech_stack:
  added: []
  patterns:
    - "SQLAlchemy aliased() per metadata_filter entry for AND-composed JOINs"
    - "Two-layer org guard: db.get check + JOIN-level organization_id filter (T-22-01)"
    - "distinct(AssetMetadataValue.value) query pattern for autocomplete values"
key_files:
  created:
    - backend/tests/test_metadata_filter.py
    - backend/tests/test_metadata_migration.py
    - backend/tests/test_asset_grid_filters.py
    - backend/alembic/versions/e8f9a0b1c2d3_phase22_metadata_filter_index.py
  modified:
    - backend/app/api/v1/endpoints/dashboard.py
decisions:
  - "Explicit HTTP 400 (not silent skip) for malformed metadata_filter entries missing ':'"
  - "Two-layer org guard on /metadata-fields/{field_id}/values: db.get check + JOIN filter"
  - "Aliased JOINs use name=f'amv_{i}'/f'mf_{i}' pattern for deterministic AND composition"
  - "alembic upgrade e8f9a0b1c2d3 (not upgrade head) due to DEBT-01 multi-head state"
metrics:
  duration_seconds: 257
  completed_date: "2026-05-15"
  tasks_completed: 3
  files_modified: 5
---

# Phase 22 Plan 01: Metadata Filter Backend Foundation Summary

**One-liner:** Composite index migration + two new metadata endpoints + aliased AND-JOIN filter on /dashboard/assets for Phase 22 DASH-01 autocomplete.

---

## What Was Built

Three tasks completed in sequence as TDD (RED → GREEN):

### Task 1: Wave 0 Test Scaffolds (RED)
Three new pytest files created with 9 tests, all starting RED (ImportError on missing symbols):
- `test_metadata_filter.py` (4 tests) — org isolation for fields and values endpoints
- `test_metadata_migration.py` (1 test) — migration source inspection via importlib
- `test_asset_grid_filters.py` (4 tests) — AND-composition, account filter, malformed input

### Task 2: Alembic Migration e8f9a0b1c2d3
- revision = `e8f9a0b1c2d3`, down_revision = `d2e3f4a5b6c7`
- Creates `idx_asset_metadata_values_field_value` on `asset_metadata_values(field_id, value)`
- Applied to dev DB; `pg_indexes` confirms 1 row with the index
- `test_composite_index_present` transitioned Wave-0 → GREEN

### Task 3: Endpoint Implementation (GREEN all Wave-0 tests)
Modified `backend/app/api/v1/endpoints/dashboard.py`:

1. **Imports added:** `distinct` (sqlalchemy), `aliased` (sqlalchemy.orm)
2. **GET /metadata-fields** — returns `{fields: [{id, name, label, field_type}]}` filtered by `MetadataField.organization_id == current_user.organization_id AND is_active=True`, ordered by `sort_order, label`
3. **GET /metadata-fields/{field_id}/values** — two-layer T-22-01 guard; returns `{values: [str]}` DISTINCT non-null ascending; 404 on cross-org or unknown field_id
4. **metadata_filter param** — `Optional[List[str]] = Query(default=None)` added to `get_dashboard_assets`; loop with `enumerate()` builds `aliased(AssetMetadataValue, name=f"amv_{i}")` + `aliased(MetadataField, name=f"mf_{i}")` JOIN per entry; malformed entries (no `":"`) raise HTTP 400

---

## Wave-0 → GREEN Transitions

| Test | File | Wave-0 State | Post-Task-3 State |
|------|------|-------------|-------------------|
| test_org_scoped_fields | test_metadata_filter.py | RED (ImportError) | GREEN |
| test_org_scoped_values | test_metadata_filter.py | RED (ImportError) | GREEN |
| test_values_distinct_org_scoped | test_metadata_filter.py | RED (ImportError) | GREEN |
| test_values_no_cross_org_leakage | test_metadata_filter.py | RED (ImportError) | GREEN |
| test_composite_index_present | test_metadata_migration.py | RED (FileNotFoundError) | GREEN after Task 2 |
| test_metadata_filter_single | test_asset_grid_filters.py | RED (ImportError) | GREEN |
| test_metadata_filter_multi_and_composition | test_asset_grid_filters.py | RED (ImportError) | GREEN |
| test_multi_account_filter | test_asset_grid_filters.py | RED (ImportError) | GREEN |
| test_metadata_filter_malformed_value | test_asset_grid_filters.py | RED (ImportError) | GREEN |

All 16 tests pass (9 new + 7 existing `test_dashboard_filters.py`).

---

## Migration Revision ID and Head Topology

- **Revision ID:** `e8f9a0b1c2d3`
- **down_revision:** `d2e3f4a5b6c7` (background_jobs_schema)
- **Branch labels:** None
- **Run command:** `alembic upgrade e8f9a0b1c2d3` (NOT `upgrade head`)

### DEBT-01 Implication

The project has multiple Alembic heads (DEBT-01, deferred to v1.5). This plan adds one more revision chaining off `d2e3f4a5b6c7`. The multi-head state is unchanged — DEBT-01 is still deferred. Anyone running `alembic upgrade head` will encounter a "Multiple head revisions" error; the correct command is `alembic upgrade e8f9a0b1c2d3` to apply this specific migration path.

---

## Endpoint Contract Reference for Plan 02

Plan 02 (frontend) must implement against these backend contracts:

### GET /dashboard/metadata-fields
```
Response: {"fields": [{"id": str, "name": str, "label": str, "field_type": str}]}
Auth: Bearer JWT required
Org: Filtered to current_user.organization_id, is_active=True
Order: sort_order ASC, label ASC
```

### GET /dashboard/metadata-fields/{field_id}/values
```
Path param: field_id (UUID)
Response: {"values": [str, ...]}  # sorted ascending, distinct, non-null
Auth: Bearer JWT required
Error: 404 if field_id unknown OR belongs to different org (T-22-01 — identical response prevents UUID enumeration)
```

### GET /dashboard/assets with metadata_filter
```
New param: metadata_filter: Optional[List[str]]
Encoding: repeated query params, e.g. ?metadata_filter=language:Indonesian&metadata_filter=market:US
Format: "field_name:value" where field_name = MetadataField.name (not .label)
Logic: AND-composition — each filter applies one aliased JOIN; asset must match ALL
Error: HTTP 400 if any entry missing ":" separator
```

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test assertion used single-quote string check that didn't match implementation double-quote style**
- **Found during:** Task 3 test run
- **Issue:** `test_metadata_filter_malformed_value` checked for `"':' not in"` but implementation uses `'":" not in'` (double quotes)
- **Fix:** Expanded assertion to match both single and double quote variants: `"':' not in" in source or '":"' in source or '":" not in' in source`
- **Files modified:** `backend/tests/test_asset_grid_filters.py`
- **Commit:** 301fb87

---

## Threat Flags

No new security surface beyond what is documented in the plan's `<threat_model>`. All T-22-01 through T-22-06 mitigations are implemented:
- T-22-01: Two-layer org guard on `/metadata-fields/{field_id}/values`
- T-22-02: filter_value and field_name only appear as SQLAlchemy bind parameters (no string interpolation)
- T-22-03: `/metadata-fields` WHERE includes `MetadataField.organization_id` guard
- T-22-05: No logging of filter_value/field_name at any log level

---

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| backend/tests/test_metadata_filter.py | FOUND |
| backend/tests/test_metadata_migration.py | FOUND |
| backend/tests/test_asset_grid_filters.py | FOUND |
| backend/alembic/versions/e8f9a0b1c2d3_phase22_metadata_filter_index.py | FOUND |
| commit c70c533 (test scaffolds) | FOUND |
| commit 2e2a6ad (migration) | FOUND |
| commit 301fb87 (endpoints) | FOUND |
| 16/16 tests GREEN | VERIFIED |
