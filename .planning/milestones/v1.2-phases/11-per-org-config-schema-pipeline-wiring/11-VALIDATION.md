---
phase: 11
slug: per-org-config-schema-pipeline-wiring
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-15
audited: 2026-04-27
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `backend/pytest.ini` or `backend/pyproject.toml` |
| **Quick run command** | `docker-compose exec backend pytest backend/tests/test_phase11_schema.py backend/tests/test_phase11_seed.py backend/tests/test_phase11_pipeline.py -x -q` |
| **Full suite command** | `docker-compose exec backend pytest backend/tests/ -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | — | T-11-01 | client_secret never stored plaintext | unit | `docker-compose exec backend pytest backend/tests/test_phase11_schema.py::test_config_model -xq` | ✅ | ✅ green |
| 11-01-02 | 01 | 1 | — | — | org_brainsuite_config FK integrity | unit | `docker-compose exec backend pytest backend/tests/test_phase11_schema.py::test_config_fk -xq` | ✅ | ✅ green |
| 11-02-01 | 02 | 1 | FMAP-08 | — | seed idempotent (ON CONFLICT DO NOTHING) | integration | `docker-compose exec backend pytest backend/tests/test_phase11_seed.py::test_brand_values_seed_migration_fields_def -xq` | ✅ | ✅ green |
| 11-03-01 | 03 | 2 | PIPE-01 | T-11-02 | UNSCORED fallthrough on missing config | unit | `docker-compose exec backend pytest backend/tests/test_phase11_pipeline.py::test_no_config_unscored -xq` | ✅ | ✅ green |
| 11-03-02 | 03 | 2 | PIPE-01 | T-11-02 | UNSCORED fallthrough on null client_id | unit | `docker-compose exec backend pytest backend/tests/test_phase11_pipeline.py::test_partial_config_unscored -xq` | ✅ | ✅ green |
| 11-03-03 | 03 | 2 | PIPE-01 | T-11-01 | token cache dict keyed by org_id | unit | `docker-compose exec backend pytest backend/tests/test_phase11_pipeline.py::test_token_cache_per_org -xq` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Nyquist Audit (2026-04-27)

**Result: COMPLIANT**

All Wave 0 test stubs were created and are substantive (no empty stubs). Static analysis confirms:

### test_phase11_schema.py (5 tests)
- `test_config_model` — verifies OrgBrainsuiteConfig tablename, all 8 columns, and `client_secret_encrypted` is `String(1000)` not `Text` (T-11-01 satisfied)
- `test_field_mapping_model` — verifies OrgBrainsuiteFieldMapping tablename and all 9 required columns
- `test_config_unique_constraint` — verifies `uq_org_brainsuite_config_org` UniqueConstraint exists on `organization_id`
- `test_config_fk` — verifies FK to `organizations.id` with `ondelete=CASCADE` (T-11-02 satisfied)
- `test_models_exported` — verifies both models appear in `app.models.__all__`

### test_phase11_seed.py (4 tests)
- `test_brand_values_seed_migration_fields_def` — verifies migration revision chain, `brainsuite_brand_values` (TEXT, sort_order 10), `brainsuite_brand_values_language` (SELECT, sort_order 11), `ON CONFLICT DO NOTHING` on `metadata_fields`, no `ON CONFLICT` on `metadata_field_values` (FMAP-08)
- `test_brand_values_language_count` — verifies all 31 language codes (ar..zh) are present in migration source
- `test_auth_provisioning_has_brand_values` — verifies auth.py `else` branch provisions both fields with correct sort_orders, `db.flush()` calls, `MetadataFieldValue` seeding; confirms provisioning is NOT in join branch
- `test_seed_migration_downgrade_deletes` — verifies downgrade deletes `metadata_field_values` before `metadata_fields` (referential integrity order)

### test_phase11_pipeline.py (7 tests)
- `test_no_config_unscored` — inspects `_mark_unscored` signature and source; confirms `scoring_status == "PENDING"` guard and `scoring_status = "UNSCORED"` assignment (PIPE-01, T-11-02; protects PROCESSING assets per memory rule)
- `test_partial_config_unscored` — reads `scoring_job.py` source; confirms all 3 null checks (`client_id`, `client_secret_encrypted`, `required_app_name`) and endpoint-type branch logic (VIDEO/STATIC_IMAGE) before calling `_mark_unscored` (PIPE-01)
- `test_token_cache_per_org` — instantiates `BrainSuiteScoreService`; asserts `_tokens` and `_token_expires` are dicts and scalar `_token`/`_token_expires_at` are gone (T-11-01)
- `test_token_cache_per_org_static` — same for `BrainSuiteStaticScoreService`
- `test_no_hardcoded_app_names` — reads both service files; asserts `ACE_VIDEO_SMV_API` and `ACE_STATIC_SOCIAL_STATIC_API` are absent (PIPE-01)
- `test_no_global_settings_reads` — reads both service files; asserts `settings.BRAINSUITE_CLIENT_ID` and `settings.BRAINSUITE_CLIENT_SECRET` are absent (PIPE-01)
- `test_scoring_job_imports_config` — reads `scoring_job.py`; asserts `OrgBrainsuiteConfig` and `decrypt_token` imports are present

### Requirements Coverage

| Requirement | Tests | Coverage |
|-------------|-------|---------|
| FMAP-08 | `test_brand_values_seed_migration_fields_def`, `test_brand_values_language_count`, `test_auth_provisioning_has_brand_values`, `test_seed_migration_downgrade_deletes` | Full — seed idempotency, language count, new-org provisioning, downgrade cleanup |
| PIPE-01 | `test_no_config_unscored`, `test_partial_config_unscored`, `test_token_cache_per_org`, `test_token_cache_per_org_static`, `test_no_hardcoded_app_names`, `test_no_global_settings_reads`, `test_scoring_job_imports_config` | Full — UNSCORED fallback, PENDING guard, per-org token dict, no global creds |

---

## Wave 0 Requirements

- [x] `backend/tests/test_phase11_schema.py` — 5 tests for model creation + FK integrity (T-11-01) — EXISTS
- [x] `backend/tests/test_phase11_seed.py` — 4 tests for brand_values seed idempotency (FMAP-08) — EXISTS
- [x] `backend/tests/test_phase11_pipeline.py` — 7 tests for UNSCORED fallthrough + token dict caching (PIPE-01) — EXISTS

*Existing `backend/tests/conftest.py` covers DB fixture. No new framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Alembic migrations apply cleanly on fresh DB | SC1–SC3 | DDL execution requires live DB container | `docker-compose run --rm backend alembic upgrade head` — check 0 errors |
| New-org provisioning injects brand_values fields | SC3 | Requires running registration flow end-to-end | Register new user+org via API, then verify metadata_fields count includes `brainsuite_brand_values` |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all requirement references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** 2026-04-27 — Nyquist audit complete. 16 tests across 3 files cover all 6 verification map tasks and both phase requirements (FMAP-08, PIPE-01). VERIFICATION.md score 7/7. No gaps.
