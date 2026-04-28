---
phase: 13-field-mapping-editor-mandatory-field-enforcement
plan: "01"
subsystem: backend-data-layer
tags: [field-mappings, sqlalchemy, alembic, pydantic, schema]
dependency_graph:
  requires: [phase-11-org-brainsuite-config-schema, v3w4x5y6z7a8-migration]
  provides: [OrgBrainsuiteFieldMapping-brainsuite_app_id-FK, migration-v5y6z7a8b9c, field-mapping-pydantic-schemas]
  affects: [phase-13-02-endpoints, phase-13-03-pipeline-guards, phase-13-04-frontend]
tech_stack:
  added: [brainsuite_field_mappings-schemas]
  patterns: [sqlalchemy-mapped-column, alembic-backfill-migration, pydantic-v2-field_validator]
key_files:
  created:
    - backend/alembic/versions/v5y6z7a8b9c_phase13_field_mappings_per_app.py
    - backend/app/schemas/brainsuite_field_mappings.py
  modified:
    - backend/app/models/brainsuite_config.py
decisions:
  - "Keep app_type as denormalized column on OrgBrainsuiteFieldMapping to avoid JOIN in pipeline queries (D-05)"
  - "FieldMappingStandard skips field_validator — standard names are backend-controlled, not user input"
  - "FieldMappingCustom enforces ^[a-zA-Z][a-zA-Z0-9_]*$ to prevent injection (T-13-01)"
  - "Migration adds column nullable first, backfills, then alters to NOT NULL — safe for existing data"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-20T14:01:30Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 13 Plan 01: Data Layer Foundation for Per-App Field Mappings Summary

**One-liner:** Added `brainsuite_app_id` FK (CASCADE) to `OrgBrainsuiteFieldMapping`, Alembic migration with backfill SQL, and Pydantic schemas for GET/PUT field mapping endpoints.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Update OrgBrainsuiteFieldMapping model + create Alembic migration | b4a1fdc | backend/app/models/brainsuite_config.py, backend/alembic/versions/v5y6z7a8b9c_phase13_field_mappings_per_app.py |
| 2 | Create Pydantic schemas for field mapping endpoints | 671fae2 | backend/app/schemas/brainsuite_field_mappings.py |

## What Was Built

### Task 1: Model + Migration

**Model changes (`backend/app/models/brainsuite_config.py`):**
- Added `brainsuite_app_id: Mapped[uuid.UUID]` FK referencing `brainsuite_apps.id` with `ondelete="CASCADE"`, placed immediately after `id`
- Added `brainsuite_app: Mapped["BrainsuiteApp"] = relationship("BrainsuiteApp")` ORM convenience relationship
- Added `relationship` to `sqlalchemy.orm` imports
- Replaced `Index("ix_org_brainsuite_field_mappings_org_app", "organization_id", "app_type")` with `UniqueConstraint("brainsuite_app_id", "api_field_name", name="uq_brainsuite_field_mappings_app_field")`
- Kept `app_type` as denormalized column (avoids pipeline JOIN per D-05)
- Updated docstring to reflect per-app rather than per-org+app_type scoping

**Migration (`backend/alembic/versions/v5y6z7a8b9c_phase13_field_mappings_per_app.py`):**
- `down_revision = "v3w4x5y6z7a8"` — chains from Phase 12's last migration
- `upgrade()` sequence:
  1. `op.add_column` — adds `brainsuite_app_id` as nullable UUID
  2. Backfill SQL: `UPDATE org_brainsuite_field_mappings m SET brainsuite_app_id = app.id FROM brainsuite_apps app WHERE m.organization_id = app.organization_id AND m.app_type = app.app_type AND m.brainsuite_app_id IS NULL`
  3. `op.create_foreign_key('fk_org_brainsuite_field_mappings_app_id', ...)` with `ondelete='CASCADE'`
  4. `op.alter_column(..., nullable=False)` after backfill
  5. `op.create_unique_constraint('uq_brainsuite_field_mappings_app_field', ...)`
  6. `op.drop_index('ix_org_brainsuite_field_mappings_org_app', ...)`
- `downgrade()` reverses all steps cleanly

### Task 2: Pydantic Schemas

**`backend/app/schemas/brainsuite_field_mappings.py`** exports 6 classes:
- `FieldMappingStandard` — PUT item for standard fields (api_field_name, metadata_field_id, is_mandatory)
- `FieldMappingCustom` — PUT item for custom fields; `@field_validator("api_field_name")` enforces `^[a-zA-Z][a-zA-Z0-9_]*$` (T-13-01 mitigation)
- `FieldMappingUpdate` — full PUT body (standard_fields + custom_fields lists)
- `FieldMappingRow` — GET response row with is_custom flag for frontend separation
- `FieldMappingResponse` — full GET response with app metadata + metadata_options
- `MetadataFieldOption` — dropdown option (id, name, label, field_type)

## Deviations from Plan

None — plan executed exactly as written.

## Threat Mitigations Applied

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-13-01 | `FieldMappingCustom.@field_validator("api_field_name")` enforces `^[a-zA-Z][a-zA-Z0-9_]*$` |
| T-13-02 | Backfill SQL uses `JOIN ON organization_id + app_type`; NOT NULL enforced after backfill |

## Known Stubs

None — this plan creates data layer only (no rendering, no API endpoints wired).

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary crossings introduced in this plan.

## Self-Check: PASSED

- `backend/app/models/brainsuite_config.py` — modified, contains `brainsuite_app_id`
- `backend/alembic/versions/v5y6z7a8b9c_phase13_field_mappings_per_app.py` — created, `down_revision = "v3w4x5y6z7a8"`
- `backend/app/schemas/brainsuite_field_mappings.py` — created, contains all 6 schema classes
- Commits b4a1fdc and 671fae2 confirmed in git log
