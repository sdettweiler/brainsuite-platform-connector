---
phase: 11
plan: "01"
subsystem: backend-models
tags: [sqlalchemy, alembic, schema, per-org-config, postgresql]
dependency_graph:
  requires: []
  provides:
    - OrgBrainsuiteConfig SQLAlchemy model (org_brainsuite_config table)
    - OrgBrainsuiteFieldMapping SQLAlchemy model (org_brainsuite_field_mappings table)
    - Alembic migration s0t1u2v3w4x5 chained from r9s0t1u2v3w4
  affects:
    - backend/app/models/__init__.py (new exports)
    - backend/alembic/versions/ (migration chain extended)
tech_stack:
  added: []
  patterns:
    - SQLAlchemy 2.0 Mapped[T] + mapped_column style (matches existing codebase)
    - Fernet-encrypted column as String(1000) — never Text (D-05/T-11-01)
    - UniqueConstraint in __table_args__ for one-config-per-org enforcement
    - Composite Index in __table_args__ for (org_id, app_type) Phase 13 query pattern
    - Alembic DDL with server_default for Boolean defaults
key_files:
  created:
    - backend/app/models/brainsuite_config.py
    - backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py
    - backend/tests/test_phase11_schema.py
  modified:
    - backend/app/models/__init__.py
decisions:
  - client_secret_encrypted uses String(1000) not Text — enforces maximum length at DB level, satisfies T-11-01 threat mitigation
  - ON DELETE CASCADE on both org FKs — prevents orphan config/mapping rows (T-11-02)
  - Composite index (organization_id, app_type) on field_mappings — pre-built for Phase 13 per-app-type query
  - Alembic migration uses server_default="false" for Boolean columns — DDL-level default independent of ORM layer
metrics:
  duration_minutes: 12
  completed_date: "2026-04-16"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 1
---

# Phase 11 Plan 01: OrgBrainsuiteConfig Schema + Model Exports Summary

**One-liner:** SQLAlchemy 2.0 models for per-org BrainSuite credentials (String(1000) encrypted secret) and field mappings, Alembic migration chaining from Phase 10, and 5 passing schema introspection unit tests.

## What Was Built

Two new SQLAlchemy 2.0 models in `backend/app/models/brainsuite_config.py`:

**OrgBrainsuiteConfig** (`org_brainsuite_config` table):
- UUID PK, `organization_id` FK to `organizations.id` with CASCADE delete
- `client_id` (String 500), `client_secret_encrypted` (String 1000 — never Text per D-05)
- `video_app_name`, `static_app_name` (String 255)
- `created_at`, `updated_at` timestamps
- `UniqueConstraint("organization_id", name="uq_org_brainsuite_config_org")` — one config per org

**OrgBrainsuiteFieldMapping** (`org_brainsuite_field_mappings` table):
- UUID PK, `organization_id` FK + CASCADE, `metadata_field_id` FK with SET NULL
- `app_type` (String 20: VIDEO or STATIC), `api_field_name`, `is_mandatory`, `is_custom`
- `Index("ix_org_brainsuite_field_mappings_org_app", "organization_id", "app_type")`

**Alembic migration** `s0t1u2v3w4x5` chains from `r9s0t1u2v3w4` (Phase 10 notifications indexes).

**Unit tests** (`backend/tests/test_phase11_schema.py`) — all 5 pass:
- `test_config_model`: 8 columns verified, String(1000) type asserted
- `test_field_mapping_model`: 9 columns verified
- `test_config_unique_constraint`: UniqueConstraint name confirmed
- `test_config_fk`: FK target + CASCADE delete confirmed
- `test_models_exported`: both names in `app.models.__all__`

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 3b5dd91 | feat(11-01): add OrgBrainsuiteConfig and OrgBrainsuiteFieldMapping models |
| Task 2 | 136da15 | feat(11-01): add Alembic migration for org_brainsuite_config tables |
| Task 3 | 663ebae | test(11-01): add unit tests for OrgBrainsuiteConfig and OrgBrainsuiteFieldMapping schemas |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. The `client_secret_encrypted` column is a data-at-rest concern handled by the D-05 String(1000) constraint verified in tests.

## Known Stubs

None — this plan creates data layer only (no UI, no service layer, no rendering paths).

## Self-Check: PASSED

- `backend/app/models/brainsuite_config.py` exists in worktree: FOUND
- `backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py` exists in worktree: FOUND
- `backend/tests/test_phase11_schema.py` exists in worktree: FOUND
- Task 1 commit 3b5dd91: FOUND
- Task 2 commit 136da15: FOUND
- Task 3 commit 663ebae: FOUND
- All 5 tests pass: CONFIRMED (docker-compose exec backend pytest)
