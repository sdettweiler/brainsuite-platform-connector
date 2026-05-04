---
quick_id: 260504-n2w
slug: superadmin-scoring-controls
status: complete
completed_at: "2026-05-04"
commits:
  - hash: 875cce4
    message: "feat(260504-n2w): add scoring_enabled + scoring_quota schema columns and migration"
  - hash: b10989c
    message: "feat(260504-n2w): enforce global scoring toggle and per-org quota in scoring_job"
  - hash: b6d7bd0
    message: "feat(260504-n2w): add superadmin scoring control endpoints"
key_files:
  created:
    - backend/alembic/versions/y7z8a1b2c3d4_superadmin_scoring_controls.py
  modified:
    - backend/app/models/system_config.py
    - backend/app/models/brainsuite_config.py
    - backend/app/services/sync/scoring_job.py
    - backend/app/api/v1/endpoints/super_admin.py
---

# Quick Task 260504-n2w: Superadmin Scoring Controls — Summary

**One-liner:** Global scoring toggle (SystemConfig.scoring_enabled) and per-org quota (OrgBrainsuiteConfig.scoring_quota) with 4 superadmin REST endpoints and batch/immediate-rescore enforcement.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | DB schema columns + alembic migration | 875cce4 |
| 2 | Enforce toggle + quota in scoring_job.py | b10989c |
| 3 | 4 superadmin scoring endpoints | b6d7bd0 |

## What Was Built

### Task 1 — Schema + Migration

- `SystemConfig.scoring_enabled: Mapped[bool]` — server_default="true", NOT NULL. Controls whether `run_scoring_batch()` processes any assets.
- `OrgBrainsuiteConfig.scoring_quota: Mapped[Optional[int]]` — nullable. NULL = unlimited. Limits cumulative scored assets (COMPLETE + PROCESSING + PENDING) per org.
- Migration `y7z8a1b2c3d4` with `down_revision = "x6y7z8a9b0c"`. Upgrade adds both columns; downgrade drops both.

### Task 2 — scoring_job.py Enforcement

- `run_scoring_batch()`: loads SystemConfig at entry; if `scoring_enabled=False`, logs and returns immediately.
- `run_scoring_batch()`: per-org quota cache built during Phase 1 loop. Before appending each asset to `batch`, queries `OrgBrainsuiteConfig.scoring_quota` and counts assets in COMPLETE/PROCESSING/PENDING. Skips assets for orgs at quota. Accepted-count is tracked in the cache within the same batch to avoid double-counting.
- `score_asset_now()`: checks per-org quota (never checks global toggle — explicit rescores always fire). Returns early with a warning log if quota reached.

### Task 3 — Superadmin Endpoints

All 4 routes use `Depends(get_current_superadmin)`.

| Method | Route | Action |
|--------|-------|--------|
| GET | /super-admin/scoring/config | Global toggle + per-org quota/scored/pending stats |
| PUT | /super-admin/scoring/config | Update SystemConfig.scoring_enabled |
| PUT | /super-admin/scoring/orgs/{org_id}/quota | Set/clear OrgBrainsuiteConfig.scoring_quota; 404 if no BS config row |
| POST | /super-admin/scoring/orgs/{org_id}/reset | Reset FAILED/COMPLETE → UNSCORED; clears score fields + brainsuite_job_id |

Reset endpoint enforces the project rule: PROCESSING is never in `_ALLOWED_RESET_STATUSES`. Any request containing "PROCESSING" returns HTTP 422.

## Deviations from Plan

None — plan executed exactly as written. All must_have truths satisfied.

## Known Stubs

None.

## Threat Flags

None — all new endpoints are behind `get_current_superadmin`. No new network surface beyond the existing superadmin router.

## Self-Check

- [x] `backend/alembic/versions/y7z8a1b2c3d4_superadmin_scoring_controls.py` — exists
- [x] `backend/app/models/system_config.py` — `scoring_enabled` column present
- [x] `backend/app/models/brainsuite_config.py` — `scoring_quota` column present
- [x] `backend/app/services/sync/scoring_job.py` — SystemConfig check at entry, per-org quota loop, score_asset_now quota guard
- [x] `backend/app/api/v1/endpoints/super_admin.py` — 4 scoring routes present
- [x] Commits 875cce4, b10989c, b6d7bd0 present in git log

## Self-Check: PASSED
