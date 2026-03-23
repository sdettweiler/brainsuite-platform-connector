---
phase: 03-brainsuite-scoring-pipeline
plan: "01"
subsystem: backend/scoring
tags: [scoring, sqlalchemy, alembic, config, testing]
dependency_graph:
  requires: []
  provides:
    - CreativeScoreResult SQLAlchemy model with state machine (UNSCORED/PENDING/PROCESSING/COMPLETE/FAILED)
    - Alembic migration e1f2g3h4i5j6 creating creative_score_results table
    - BRAINSUITE_* env vars declared in Settings
    - tenacity>=8.2.0 dependency
    - Test scaffolds for all 8 SCORE requirements (23 test stubs)
  affects:
    - backend/app/models/creative.py (removed ace_score/ace_score_confidence/brainsuite_metadata, added score_result relationship)
tech_stack:
  added:
    - tenacity>=8.2.0 (retry logic for BrainSuite API calls)
  patterns:
    - SQLAlchemy Mapped[Optional[T]] pattern for nullable fields
    - UniqueConstraint per asset (one score record per creative asset)
    - pytest.mark.skip with structured docstrings for TDD scaffold
key_files:
  created:
    - backend/app/models/scoring.py
    - backend/alembic/versions/e1f2g3h4i5j6_add_creative_score_results.py
    - backend/tests/test_scoring.py
  modified:
    - backend/app/models/creative.py
    - backend/app/models/__init__.py
    - backend/app/core/config.py
    - backend/requirements.txt
decisions:
  - "UniqueConstraint on creative_asset_id (uq_score_per_asset): one score record per asset enforced at DB level"
  - "scoring_status default='UNSCORED' on both model and migration server_default for consistency"
  - "down_revision=k2l3m4n5o6p7 (add_dv360_cost_per_view): latest migration in chain at time of plan execution"
  - "test_channel_mapping uses pytest.mark.parametrize with 14 cases covering full mapping table"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-03-23"
  tasks_completed: 2
  files_changed: 7
---

# Phase 03 Plan 01: Foundation Model, Migration, Config, and Test Scaffolds Summary

**One-liner:** CreativeScoreResult SQLAlchemy model with 5-state scoring state machine, Alembic migration dropping legacy ace_score columns, BRAINSUITE_* Settings vars, tenacity dependency, and 23 pytest stubs covering all 8 SCORE requirements.

## What Was Built

### Task 1: CreativeScoreResult Model + Migration + Config + Dependency

**`backend/app/models/scoring.py`** — New SQLAlchemy model:
- `creative_score_results` table with all required columns
- ForeignKey to `creative_assets.id` with `ondelete="CASCADE"`
- `UniqueConstraint("creative_asset_id", name="uq_score_per_asset")` — one record per asset
- `scoring_status` with default `"UNSCORED"` (valid: UNSCORED/PENDING/PROCESSING/COMPLETE/FAILED)
- JSONB `score_dimensions` for BrainSuite dimension breakdown storage

**`backend/alembic/versions/e1f2g3h4i5j6_add_creative_score_results.py`** — Migration:
- Creates `creative_score_results` table
- Indexes: `ix_score_results_status` on scoring_status, `ix_score_results_asset` on creative_asset_id
- Drops `ace_score`, `ace_score_confidence`, `brainsuite_metadata` from `creative_assets`
- Downgrade re-adds dropped columns and drops the new table

**`backend/app/models/creative.py`** — Updated:
- Removed `ace_score`, `ace_score_confidence`, `brainsuite_metadata` fields
- Added `score_result: Mapped[Optional["CreativeScoreResult"]]` relationship with `back_populates` and `uselist=False`

**`backend/app/core/config.py`** — Added 4 BRAINSUITE_* vars:
- `BRAINSUITE_CLIENT_ID: Optional[str] = None`
- `BRAINSUITE_CLIENT_SECRET: Optional[str] = None`
- `BRAINSUITE_BASE_URL: str = "https://api.brainsuite.ai"`
- `BRAINSUITE_AUTH_URL: str = "https://auth.brainsuite.ai/oauth2/token"`

**`backend/requirements.txt`** — Added `tenacity>=8.2.0`

### Task 2: Test Scaffolds for All SCORE Requirements

**`backend/tests/test_scoring.py`** — 23 pytest stubs:
- `test_score_result_model` (SCORE-01) — model instantiation and defaults
- `test_token_caching` (SCORE-02) — BrainSuiteClient token cache TTL behavior
- `test_retry_logic` (SCORE-02) — 429/5xx/4xx response handling
- `test_signed_url_generation` (SCORE-03) — S3 key without /objects/ prefix
- `test_batch_size_limit` (SCORE-04) — max 20 VIDEO assets per batch
- `test_unscored_queue_injection` (SCORE-05) — INSERT ON CONFLICT DO NOTHING
- `test_rescore_endpoint` (SCORE-06) — POST /api/v1/scoring/{id}/rescore
- `test_score_dimensions_no_viz_urls` (SCORE-07) — strip visualization keys before storage
- `test_scoring_status_endpoint` (SCORE-08) — GET /api/v1/scoring/status bulk status
- `test_channel_mapping` (SCORE-08) — 14 parametrized platform+placement cases

All stubs have `@pytest.mark.skip(reason="Implementation pending")`, clear docstrings describing expected behavior, and import structure ready for implementation.

## Verification Results

- `python -c "from app.models.scoring import CreativeScoreResult"` — PASS
- `pytest backend/tests/test_scoring.py --collect-only` — 23 tests collected
- `grep -c "BRAINSUITE" backend/app/core/config.py` — 4
- `grep "tenacity" backend/requirements.txt` — tenacity>=8.2.0

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree branch behind main branch**
- **Found during:** Initial setup — worktree branch `worktree-agent-abb9e357` was branched from an old commit (99a5beb) before Phase 01/02 work
- **Fix:** Ran `git rebase main` in the worktree to bring it up to date with all Phase 01/02 changes
- **Files modified:** None (rebase only)
- **Commit:** N/A (rebase operation)

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| `down_revision = "k2l3m4n5o6p7"` | Latest migration file in versions/ at execution time was k2l3m4n5o6p7_add_dv360_cost_per_view.py |
| `server_default="UNSCORED"` in migration | Ensures existing rows (if any) get UNSCORED status; consistent with model default |
| 14 parametrized channel mapping cases | Covers full table from CONTEXT.md including edge cases (None placement, unknown placements) |
| `uselist=False` on score_result relationship | One score record per asset (backed by UniqueConstraint); ORM should reflect this |

## Known Stubs

None — all stubs in test_scoring.py are intentional scaffolds with `pytest.mark.skip`. The test file itself is a scaffold; implementations will be added in Plans 02-05.

## Self-Check: PASSED

Files created:
- FOUND: backend/app/models/scoring.py
- FOUND: backend/alembic/versions/e1f2g3h4i5j6_add_creative_score_results.py
- FOUND: backend/tests/test_scoring.py

Commits:
- FOUND: 94df16c (feat(03-01): CreativeScoreResult model, migration, config, and dependency)
- FOUND: 2d7c5ba (test(03-01): scaffold test stubs for all SCORE requirements)
