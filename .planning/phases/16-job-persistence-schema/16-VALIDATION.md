---
phase: 16
slug: job-persistence-schema
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-08
audited: 2026-05-13
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (unit + integration) |
| **Config file** | `backend/pytest.ini` or `pyproject.toml` |
| **Quick run command** | `pytest tests/models/test_jobs.py tests/services/test_maintenance.py tests/services/test_scheduler.py -x -v` |
| **Full suite command** | `pytest tests/ -x --cov=app` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/models/test_jobs.py tests/services/test_maintenance.py tests/services/test_scheduler.py -x -v`
- **After every plan wave:** Run `pytest tests/ -x --cov=app`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | JOBS-01 | — | BackgroundJob columns match schema; FK constraints enforce org ownership | unit | `pytest tests/models/test_jobs.py::test_background_job_model_columns -x` | ✅ | ✅ green |
| 16-01-02 | 01 | 1 | JOBS-01 | — | Migration creates table with correct columns, indexes, FK constraints, autovacuum settings | integration | `pytest tests/migrations/test_phase16_migration.py::test_phase16_migration_file_exists -x` | ✅ | ✅ green |
| 16-01-03 | 01 | 1 | JOBS-01 | — | Both composite indexes declared in __table_args__ | unit | `pytest tests/models/test_jobs.py::test_background_job_model_indexes -x` | ✅ | ✅ green |
| 16-01-04 | 01 | 1 | JOBS-01 | — | FK non-nullable on org_id, nullable on platform_connection_id | unit | `pytest tests/models/test_jobs.py::test_background_job_model_fk_constraints -x` | ✅ | ✅ green |
| 16-01-05 | 01 | 1 | JOBS-01 | — | JSONB columns use default=dict (not mutable default={}) | unit | `pytest tests/models/test_jobs.py::test_background_job_jsonb_defaults_use_dict -x` | ✅ | ✅ green |
| 16-03-01 | 03 | 2 | JOBS-02 | — | Cleanup deletes records older than 30 days; preserves recent records | unit | `pytest tests/services/test_maintenance.py::test_cleanup_old_background_jobs_deletes_old_records -x` | ✅ | ✅ green |
| 16-03-02 | 03 | 2 | JOBS-02 | — | Cleanup rolls back and re-raises on DB error | unit | `pytest tests/services/test_maintenance.py::test_cleanup_old_background_jobs_rollback_on_error -x` | ✅ | ✅ green |
| 16-03-03 | 03 | 2 | JOBS-02 | — | Cleanup job registered inside SCHEDULER_ENABLED guard in startup_scheduler | unit | `pytest tests/services/test_scheduler.py::test_cleanup_job_registration -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/models/test_jobs.py` — 4 tests: columns, indexes, FK constraints, JSONB defaults (confirmed 2026-05-13)
- [x] `tests/migrations/test_phase16_migration.py` — 1 test: migration file exists, autovacuum, down_revision (confirmed 2026-05-13)
- [x] `tests/services/test_maintenance.py` — 2 tests: delete+commit path, rollback+re-raise path (confirmed 2026-05-13)
- [x] `tests/services/test_scheduler.py` — 1 test: SCHEDULER_ENABLED guard, CronTrigger(hour=3), id=cleanup_background_jobs (confirmed 2026-05-13)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Autovacuum settings visible in pg_class after migration | JOBS-01 | Requires live PostgreSQL instance | `SELECT reloptions FROM pg_class WHERE relname = 'background_jobs';` — must show autovacuum_vacuum_scale_factor=0.05 |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** 2026-05-13 (gsd-validate-phase audit)

## Validation Audit 2026-05-13

| Metric | Count |
|--------|-------|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |
| Final test count | 4 (test_jobs.py) + 2 (test_maintenance.py) + 1 (test_scheduler.py) + 1 (test_phase16_migration.py) = 8 |
