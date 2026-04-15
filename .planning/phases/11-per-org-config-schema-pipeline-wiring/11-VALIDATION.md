---
phase: 11
slug: per-org-config-schema-pipeline-wiring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `backend/pytest.ini` or `backend/pyproject.toml` |
| **Quick run command** | `docker-compose exec backend pytest backend/tests/test_scoring.py backend/tests/test_scoring_image.py -x -q` |
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
| 11-01-01 | 01 | 1 | — | T-11-01 | client_secret never stored plaintext | unit | `docker-compose exec backend pytest backend/tests/test_phase11_schema.py::test_config_model -xq` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | — | — | org_brainsuite_config FK integrity | unit | `docker-compose exec backend pytest backend/tests/test_phase11_schema.py::test_config_fk -xq` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 1 | FMAP-08 | — | seed idempotent (ON CONFLICT DO NOTHING) | integration | `docker-compose exec backend pytest backend/tests/test_phase11_seed.py::test_brand_values_seed -xq` | ❌ W0 | ⬜ pending |
| 11-03-01 | 03 | 2 | PIPE-01 | T-11-02 | UNSCORED fallthrough on missing config | unit | `docker-compose exec backend pytest backend/tests/test_phase11_pipeline.py::test_no_config_unscored -xq` | ❌ W0 | ⬜ pending |
| 11-03-02 | 03 | 2 | PIPE-01 | T-11-02 | UNSCORED fallthrough on null client_id | unit | `docker-compose exec backend pytest backend/tests/test_phase11_pipeline.py::test_partial_config_unscored -xq` | ❌ W0 | ⬜ pending |
| 11-03-03 | 03 | 2 | PIPE-01 | T-11-01 | token cache dict keyed by org_id | unit | `docker-compose exec backend pytest backend/tests/test_phase11_pipeline.py::test_token_cache_per_org -xq` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_phase11_schema.py` — stubs for model creation + FK integrity (T-11-01)
- [ ] `backend/tests/test_phase11_seed.py` — stubs for brand_values seed idempotency (FMAP-08)
- [ ] `backend/tests/test_phase11_pipeline.py` — stubs for UNSCORED fallthrough + token dict caching (PIPE-01)

*Existing `backend/tests/conftest.py` covers DB fixture. No new framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Alembic migrations apply cleanly on fresh DB | SC1–SC3 | DDL execution requires live DB container | `docker-compose run --rm backend alembic upgrade head` — check 0 errors |
| New-org provisioning injects brand_values fields | SC3 | Requires running registration flow end-to-end | Register new user+org via API, then verify metadata_fields count includes `brainsuite_brand_values` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
