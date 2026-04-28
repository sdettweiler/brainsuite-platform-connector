---
phase: 11-per-org-config-schema-pipeline-wiring
verified: 2026-04-16T10:00:00Z
status: passed
score: 7/7
overrides_applied: 0
requirements: [FMAP-08, PIPE-01]
---

# Phase 11 Verification

**Phase Goal:** Per-org BrainSuite config schema and pipeline wiring — each organization can hold its own BrainSuite credentials and app names; the scoring pipeline reads those credentials from DB instead of global .env; orgs without config fall through gracefully to UNSCORED.

**Verified:** 2026-04-16T10:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Requirements Coverage

### FMAP-08 — Brand Values metadata fields provisioned for all orgs

COVERED.

- Alembic migration `t1u2v3w4x5y6` seeds `brainsuite_brand_values` (TEXT, sort_order=10) and `brainsuite_brand_values_language` (SELECT, sort_order=11, 31 language values) for all existing organizations using `ON CONFLICT DO NOTHING` on `metadata_fields`.
- `backend/app/api/v1/endpoints/auth.py` provisions the same two fields inline in the `else` branch (lines 157–201), with `db.flush()` after each `MetadataField` add to obtain a UUID before referencing it for `MetadataFieldValue` inserts. The `is_pending_join=True` join path is correctly excluded.
- 4 static-analysis tests in `backend/tests/test_phase11_seed.py` validate migration field definitions, language count (31), auth.py provisioning presence, and downgrade cleanup.

### PIPE-01 — Scoring pipeline reads per-org credentials from DB

COVERED.

- `backend/app/services/brainsuite_score.py` and `backend/app/services/brainsuite_static_score.py` no longer read `settings.BRAINSUITE_CLIENT_ID` or `settings.BRAINSUITE_CLIENT_SECRET`. Both services use `self._tokens: dict[str, str]` and `self._token_expires: dict[str, datetime]` keyed by `org_id`.
- `backend/app/services/sync/scoring_job.py` imports `OrgBrainsuiteConfig` and `decrypt_token`, looks up the per-org config row at the top of `_process_asset`, and passes `org_id`, `client_id`, `client_secret`, and `app_name` to all four service calls (two `submit_job_with_upload`, two `poll_job_status`).
- Missing or incomplete config triggers `_mark_unscored()` which only transitions rows in `PENDING` state, never `PROCESSING`.
- 7 static-analysis tests in `backend/tests/test_phase11_pipeline.py` validate all of the above.

## Must-Have Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | OrgBrainsuiteConfig model exists with client_id, client_secret_encrypted, video_app_name, static_app_name columns | VERIFIED | `backend/app/models/brainsuite_config.py` lines 27-30: all four columns present with correct types (String(500), String(1000), String(255), String(255)) |
| 2 | OrgBrainsuiteFieldMapping model exists with org_id, app_type, api_field_name, metadata_field_id, is_mandatory, is_custom columns | VERIFIED | `backend/app/models/brainsuite_config.py` lines 54-61: all six columns present; UniqueConstraint on organization_id in OrgBrainsuiteConfig, composite Index on (organization_id, app_type) in OrgBrainsuiteFieldMapping |
| 3 | Alembic migration creates both tables with correct FKs, constraints, and indexes | VERIFIED | `backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py`: creates `org_brainsuite_config` (UniqueConstraint uq_org_brainsuite_config_org, FK organizations.id CASCADE) and `org_brainsuite_field_mappings` (FK organizations.id CASCADE, FK metadata_fields.id SET NULL, composite index ix_org_brainsuite_field_mappings_org_app); downgrade() drops indexes before tables |
| 4 | New models exported from app.models and visible to Alembic | VERIFIED | `backend/app/models/__init__.py` line 16: `from app.models.brainsuite_config import OrgBrainsuiteConfig, OrgBrainsuiteFieldMapping`; lines 28-29: both names in `__all__` |
| 5 | brainsuite_brand_values (TEXT) and brainsuite_brand_values_language (SELECT, 31 languages) seeded for all orgs; new-org registration provisions same fields | VERIFIED | Migration `t1u2v3w4x5y6` loops all orgs, inserts both fields with ON CONFLICT DO NOTHING, seeds 31 language values (ar..zh) for SELECT field. auth.py lines 157-201 provision both fields inline in else branch with sort_order 10/11 and 31 MetadataFieldValue rows |
| 6 | Scoring pipeline reads per-org credentials from OrgBrainsuiteConfig instead of global .env | VERIFIED | No occurrences of `ACE_VIDEO_SMV_API`, `ACE_STATIC_SOCIAL_STATIC_API`, `settings.BRAINSUITE_CLIENT_ID`, or `settings.BRAINSUITE_CLIENT_SECRET` in either service file. Both services use `self._tokens[org_id]` dict. scoring_job.py passes org_id/client_id/client_secret/app_name to all four service call sites (lines 272-280, 288-296, 312-318, 320-326) |
| 7 | Missing config falls through to _mark_unscored without raising; PENDING-only guard enforced | VERIFIED | `scoring_job.py` lines 196-212: compound guard checks `not org_config`, `not org_config.client_id`, `not org_config.client_secret_encrypted`, `not required_app_name` — calls `_mark_unscored` and returns. `_mark_unscored` (lines 413-429) checks `score_row.scoring_status == "PENDING"` before transitioning; PROCESSING rows are never touched |

**Score: 7/7 truths verified**

## Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `backend/app/models/brainsuite_config.py` | VERIFIED | Contains OrgBrainsuiteConfig and OrgBrainsuiteFieldMapping with all required columns, constraints, and indexes |
| `backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py` | VERIFIED | revision=s0t1u2v3w4x5, down_revision=r9s0t1u2v3w4; creates both tables with FKs, UniqueConstraint, composite index |
| `backend/alembic/versions/t1u2v3w4x5y6_seed_brand_values_metadata_fields.py` | VERIFIED | revision=t1u2v3w4x5y6, down_revision=s0t1u2v3w4x5; seeds brand_values fields for all orgs, 31 language values |
| `backend/app/api/v1/endpoints/auth.py` | VERIFIED | Provisions brand_values + brand_values_language in else branch; MetadataField/MetadataFieldValue imports at top |
| `backend/app/services/brainsuite_score.py` | VERIFIED | per-org _tokens dict; _get_token(org_id, client_id, client_secret); no hardcoded app names or global settings reads |
| `backend/app/services/brainsuite_static_score.py` | VERIFIED | Same per-org re-wire as video service; _tokens/_token_expires dicts confirmed |
| `backend/app/services/sync/scoring_job.py` | VERIFIED | Imports OrgBrainsuiteConfig and decrypt_token; DB lookup at _process_asset start; _mark_unscored with PENDING guard |
| `backend/tests/test_phase11_schema.py` | VERIFIED | File exists (5 tests for model columns, constraint, FK, and exports) |
| `backend/tests/test_phase11_seed.py` | VERIFIED | File exists (4 static analysis tests for seed migration and auth.py provisioning) |
| `backend/tests/test_phase11_pipeline.py` | VERIFIED | File exists (7 tests for UNSCORED fallback, token cache dict, hardcoded name removal, imports) |

## Key Link Verification

| From | To | Via | Status | Evidence |
|------|----|-----|--------|---------|
| `backend/app/models/__init__.py` | `backend/app/models/brainsuite_config.py` | `from app.models.brainsuite_config import OrgBrainsuiteConfig, OrgBrainsuiteFieldMapping` | VERIFIED | Line 16 in __init__.py matches exact pattern |
| `backend/alembic/versions/s0t1u2v3w4x5_...py` | `backend/alembic/versions/r9s0t1u2v3w4_...py` | `down_revision = "r9s0t1u2v3w4"` | VERIFIED | Line 12 in schema migration file |
| `backend/alembic/versions/t1u2v3w4x5y6_...py` | `backend/alembic/versions/s0t1u2v3w4x5_...py` | `down_revision = "s0t1u2v3w4x5"` | VERIFIED | Line 18 in seed migration file |
| `backend/app/api/v1/endpoints/auth.py` | `backend/app/models/metadata.py` | `MetadataField(` / `MetadataFieldValue(` ORM inserts | VERIFIED | Lines 16, 158, 171, 196 in auth.py |
| `backend/app/services/sync/scoring_job.py` | `backend/app/models/brainsuite_config.py` | `from app.models.brainsuite_config import OrgBrainsuiteConfig` | VERIFIED | Line 18 in scoring_job.py |
| `backend/app/services/sync/scoring_job.py` | `backend/app/core/security.py` | `from app.core.security import decrypt_token` | VERIFIED | Line 22 in scoring_job.py |
| `backend/app/services/sync/scoring_job.py` | `backend/app/services/brainsuite_score.py` | `submit_job_with_upload(org_id=str(asset.organization_id), ...)` | VERIFIED | Lines 272-280 in scoring_job.py |

## Commit Verification

All 9 commits documented in SUMMARYs confirmed present in git history:

| Commit | Description |
|--------|-------------|
| 3b5dd91 | feat(11-01): add OrgBrainsuiteConfig and OrgBrainsuiteFieldMapping models |
| 136da15 | feat(11-01): add Alembic migration for org_brainsuite_config tables |
| 663ebae | test(11-01): add unit tests for OrgBrainsuiteConfig and OrgBrainsuiteFieldMapping schemas |
| 4aef3d2 | feat(11-02): seed brainsuite_brand_values metadata fields for all existing orgs |
| bb76b9a | feat(11-02): provision brand_values metadata fields in new-org registration |
| a070e80 | test(11-02): add static analysis tests for brand_values seed migration and provisioning |
| 79d9da2 | feat(11-03): re-wire score services for per-org credentials and app_name |
| 79d9cea | feat(11-03): re-wire scoring_job.py to load OrgBrainsuiteConfig per org |
| a0a223c | test(11-03): add 7 unit tests for per-org pipeline re-wire |

## Anti-Patterns Found

None of significance. Spot-checks on all modified production files:

- No TODO/FIXME/placeholder comments in production code paths
- No `return null` or empty stub implementations
- No hardcoded empty data passed to rendering/processing paths
- `client_secret_encrypted` is String(1000) throughout (never Text) — T-11-01 satisfied
- `_mark_unscored` logs the missing field name (`missing` variable), never the secret value — T-11-05 satisfied
- PROCESSING assets are guarded: `_mark_unscored` checks `score_row.scoring_status == "PENDING"` before any write

## Behavioral Spot-Checks

Step 7b: SKIPPED for live API/DB behavioral checks (require running server). Static structural checks performed instead via grep and direct file inspection — all critical behaviors confirmed structurally:

- `_mark_unscored` called before `return` on all 4 missing-config conditions (no raise path)
- Credential decryption (`decrypt_token`) called after config guard, result passed to service — never stored or logged
- `org_id_str` threaded to all 4 service call sites

## Human Verification Required

None — all must-haves are verifiable through static analysis. The following items would benefit from a live run but are not blockers for phase closure:

1. **Test:** `docker-compose exec backend alembic upgrade head` applies both migrations cleanly against a real database
   **Why human:** Requires a running DB environment; migration DDL correctness cannot be verified purely from file contents

2. **Test:** Register a new organization via the API and confirm `brainsuite_brand_values` and `brainsuite_brand_values_language` fields appear in the org's metadata
   **Why human:** Requires a running stack with active DB

## Verdict

Phase 11 goal is achieved. All 7 must-have truths are fully verified in the codebase. Both SQLAlchemy models exist with correct columns, constraints, and FK cascade rules. The Alembic migration chain is correct (r9s0t1u2v3w4 → s0t1u2v3w4x5 → t1u2v3w4x5y6). Brand-values metadata fields are seeded for existing orgs via migration and for new orgs via auth.py provisioning. The scoring pipeline has been fully re-wired to per-org credentials with graceful UNSCORED fallback and a PENDING-only guard that protects live PROCESSING jobs. All 9 documented commits are present in git history.

---

_Verified: 2026-04-16T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
