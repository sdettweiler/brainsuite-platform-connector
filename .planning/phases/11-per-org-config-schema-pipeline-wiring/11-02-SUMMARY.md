---
phase: 11-per-org-config-schema-pipeline-wiring
plan: "02"
subsystem: backend
tags: [alembic, seed-migration, metadata, auth, provisioning, brand-values]
requirements: [FMAP-08]
dependency_graph:
  requires:
    - "11-01: org_brainsuite_config tables (s0t1u2v3w4x5 migration)"
    - "backend/app/models/metadata.py: MetadataField, MetadataFieldValue ORM models"
  provides:
    - "Alembic migration t1u2v3w4x5y6: brand_values fields seeded for all existing orgs"
    - "auth.py: new-org provisioning for brand_values fields (else branch)"
    - "tests/test_phase11_seed.py: static validation suite (4 tests)"
  affects:
    - "backend/app/api/v1/endpoints/auth.py: register() provisioning"
    - "backend/alembic/versions/: migration chain"
tech_stack:
  added: []
  patterns:
    - "Alembic raw SQL seed with ON CONFLICT DO NOTHING for idempotency on metadata_fields"
    - "ORM-level provisioning with db.flush() for UUID generation before FK references"
    - "Static source analysis tests (importlib + file read) -- no live DB needed"
key_files:
  created:
    - backend/alembic/versions/t1u2v3w4x5y6_seed_brand_values_metadata_fields.py
    - backend/tests/test_phase11_seed.py
  modified:
    - backend/app/api/v1/endpoints/auth.py
decisions:
  - "Used static source analysis tests (no live DB) consistent with existing test patterns in conftest.py"
  - "ON CONFLICT DO NOTHING only on metadata_fields (not metadata_field_values) -- matches f2g3h4i5j6k7 pattern"
  - "Provisioning inline in else branch per D-06 -- not extracted to helper"
  - "sort_order 10/11 chosen to not collide with image fields (8/9) from m4n5o6p7q8r9"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-16T08:14:05Z"
  tasks_completed: 3
  files_created: 2
  files_modified: 1
---

# Phase 11 Plan 02: Brand Values Metadata Seed Summary

**One-liner:** Alembic seed migration + auth.py inline provisioning for brainsuite_brand_values (TEXT) and brainsuite_brand_values_language (SELECT, 31 languages) across all orgs, fulfilling FMAP-08.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create Alembic seed migration | 4aef3d2 | backend/alembic/versions/t1u2v3w4x5y6_seed_brand_values_metadata_fields.py (created) |
| 2 | Add brand_values provisioning to auth.py | bb76b9a | backend/app/api/v1/endpoints/auth.py (modified) |
| 3 | Create integration tests | a070e80 | backend/tests/test_phase11_seed.py (created) |

## What Was Built

### Task 1: Alembic Seed Migration (`t1u2v3w4x5y6`)

Migration chains from `s0t1u2v3w4x5` (11-01 schema migration). For every existing organization:

- Inserts `brainsuite_brand_values` (TEXT, sort_order=10, not required) with `ON CONFLICT DO NOTHING`
- Inserts `brainsuite_brand_values_language` (SELECT, sort_order=11, not required) with `ON CONFLICT DO NOTHING`
- Seeds 31 language values for the SELECT field (ar..zh) without `ON CONFLICT` (no unique constraint on metadata_field_values — matches f2g3h4i5j6k7 pattern)

`downgrade()` deletes from `metadata_field_values` first (referential integrity), then `metadata_fields`, targeting both field names by name.

### Task 2: auth.py New-Org Provisioning

Added `from app.models.metadata import MetadataField, MetadataFieldValue` at module level.

In the `else` branch of `register()` (create/implicit-create paths only, NOT join path), after `db.add(image_app)`:

1. Creates `brainsuite_brand_values` MetadataField → `db.flush()` to get UUID
2. Creates `brainsuite_brand_values_language` MetadataField → `db.flush()` to get UUID
3. Seeds all 31 language MetadataFieldValues for the language field

The `is_pending_join=True` path is intentionally excluded per D-06 — that org already exists and will have fields from the migration.

### Task 3: Static Analysis Tests

`test_phase11_seed.py` — 4 tests, all passing green:

1. `test_brand_values_seed_migration_fields_def` — verifies revision chain, field types/names, sort_orders, ON CONFLICT placement
2. `test_brand_values_language_count` — verifies exactly 31 language entries (ar..zh)
3. `test_auth_provisioning_has_brand_values` — verifies import, field names, sort_orders, flush calls, else-branch placement
4. `test_seed_migration_downgrade_deletes` — verifies downgrade order and field name targeting

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test assertion for ON CONFLICT count was too strict**
- **Found during:** Task 3 test run
- **Issue:** Test checked `source.count("ON CONFLICT DO NOTHING") == 1` but migration has 3 occurrences (docstring, SQL block, and a comment saying "No ON CONFLICT"). Count was 3, not 1.
- **Fix:** Replaced count check with a targeted check: find the `INSERT INTO metadata_field_values` block and assert no `ON CONFLICT DO NOTHING` appears within 300 chars of it.
- **Files modified:** backend/tests/test_phase11_seed.py
- **Commit:** included in a070e80

**2. [Rule 1 - Bug] MetadataFieldValue assertion used inline constructor string**
- **Found during:** Task 3 test run
- **Issue:** Test checked for `"MetadataFieldValue(field_id=brand_values_lang_field.id,"` as a single string but the constructor spans multiple lines in auth.py.
- **Fix:** Split into two separate assertions: `"MetadataFieldValue("` and `"field_id=brand_values_lang_field.id,"`.
- **Files modified:** backend/tests/test_phase11_seed.py
- **Commit:** included in a070e80

## Known Stubs

None — all fields are fully wired. The migration seeds real data and auth.py provisioning is live code (not mocked or placeholder).

## Threat Surface Scan

No new network endpoints introduced. Changes are:
- DB-only migration (seed data)
- ORM inserts within an existing transaction in auth.py

No new trust boundaries. Threat model items T-11-03 and T-11-04 are fully addressed:
- T-11-03 (Tampering via re-run): mitigated by `ON CONFLICT DO NOTHING` on metadata_fields inserts
- T-11-04 (DoS via flush latency): accepted — two flushes within existing registration transaction

## Self-Check

- [x] `backend/alembic/versions/t1u2v3w4x5y6_seed_brand_values_metadata_fields.py` exists in worktree
- [x] `backend/app/api/v1/endpoints/auth.py` contains `brainsuite_brand_values` provisioning
- [x] `backend/tests/test_phase11_seed.py` exists with 4 test functions
- [x] Commit 4aef3d2 exists (Task 1)
- [x] Commit bb76b9a exists (Task 2)
- [x] Commit a070e80 exists (Task 3)
- [x] All 4 tests passed green in docker backend container

## Self-Check: PASSED
