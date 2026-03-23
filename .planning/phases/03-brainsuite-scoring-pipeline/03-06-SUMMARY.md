---
phase: 03-brainsuite-scoring-pipeline
plan: "06"
subsystem: backend/database
tags: [alembic, migration, metadata, brainsuite, setup]
dependency_graph:
  requires: [03-01]
  provides: [brainsuite-metadata-fields-seeded, brainsuite-env-vars-documented]
  affects: [backend/alembic, scripts/setup.py, .env.example]
tech_stack:
  added: []
  patterns: [alembic-data-migration, raw-sql-op-execute, on-conflict-do-nothing]
key_files:
  created:
    - backend/alembic/versions/f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py
  modified:
    - scripts/setup.py
    - .env.example
decisions:
  - "down_revision=e1f2g3h4i5j6 — chains directly after creative_score_results table migration (Plan 01), the latest migration in the chain at execution time"
  - "Language values sorted alphabetically by label for consistent sort_order across environments"
  - "brainsuite_voice_over_language uses same language enum as brainsuite_asset_language"
metrics:
  duration_minutes: 8
  completed_date: "2026-03-23"
  tasks_completed: 2
  files_changed: 3
---

# Phase 03 Plan 06: Seed BrainSuite MetadataField Rows + Setup/Env Updates Summary

**One-liner:** Alembic data migration seeds 7 BrainSuite MetadataField rows (+ enum values for SELECT fields) per org, and setup.py/env.example updated from BRAINSUITE_API_KEY to OAuth credential pattern.

## What Was Built

### Task 1: Alembic data migration — seed BrainSuite MetadataField rows per organization

Created `backend/alembic/versions/f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py` — a data-only migration (no schema changes) that:

- Queries all existing organization IDs from `organizations`
- For each org, inserts 7 `MetadataField` rows with `ON CONFLICT DO NOTHING` for idempotency
- Fields seeded: `brainsuite_brand_names` (TEXT, required), `brainsuite_asset_language` (SELECT, required), `brainsuite_project_name` (TEXT, optional, default "Spring Campaign 2026"), `brainsuite_asset_name` (TEXT, optional), `brainsuite_asset_stage` (SELECT, optional, default "finalVersion"), `brainsuite_voice_over` (TEXT, optional), `brainsuite_voice_over_language` (SELECT, optional)
- Seeds `MetadataFieldValue` enum rows for SELECT fields: 31 language values (alphabetical) for `brainsuite_asset_language` and `brainsuite_voice_over_language`; 3 stage values for `brainsuite_asset_stage`
- `downgrade()` deletes all `brainsuite_%` field values and fields

### Task 2: Update setup.py + .env.example with BrainSuite OAuth credentials

- `scripts/setup.py`: Replaced single `brainsuite_api_key` prompt with 4 OAuth credential prompts (`BRAINSUITE_CLIENT_ID`, `BRAINSUITE_CLIENT_SECRET`, `BRAINSUITE_BASE_URL`, `BRAINSUITE_AUTH_URL`); BASE_URL and AUTH_URL use sensible defaults and only prompt if CLIENT_ID is provided
- `.env.example`: Added `# ─── BrainSuite ───` section documenting all 4 env vars with default URLs

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | d76571d | feat(03-06): seed BrainSuite MetadataField rows per organization |
| 2 | 08cd4d1 | feat(03-06): update setup.py and .env.example with BrainSuite OAuth credentials |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None — migration is data-seeding only; no UI or API surface stubs exist.

## Self-Check: PASSED

- [x] `backend/alembic/versions/f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py` — FOUND
- [x] `scripts/setup.py` contains `BRAINSUITE_CLIENT_ID` — FOUND
- [x] `.env.example` contains `BRAINSUITE_CLIENT_ID` — FOUND
- [x] Commits d76571d and 08cd4d1 exist in git log
