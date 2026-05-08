---
phase: 16
slug: job-persistence-schema
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
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
| 16-01-01 | 01 | 1 | JOBS-01 | — | BackgroundJob columns match schema; FK constraints enforce org ownership | unit | `pytest tests/models/test_jobs.py::test_background_job_model_columns -x` | ❌ W0 | ⬜ pending |
| 16-01-02 | 01 | 1 | JOBS-01 | — | Migration creates table with correct columns, indexes, FK constraints, autovacuum settings | integration | `pytest tests/migrations/test_phase16_migration.py::test_phase16_migration_file_exists -x` | ❌ W0 | ⬜ pending |
| 16-03-01 | 03 | 2 | JOBS-02 | — | Cleanup deletes records older than 30 days; preserves recent records | unit | `pytest tests/services/test_maintenance.py::test_cleanup_old_background_jobs_deletes_old_records -x` | ❌ W0 | ⬜ pending |
| 16-03-02 | 03 | 2 | JOBS-02 | — | Cleanup job registered inside SCHEDULER_ENABLED guard in startup_scheduler | unit | `pytest tests/services/test_scheduler.py::test_cleanup_job_registration -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/models/test_jobs.py` — BackgroundJob model tests: schema columns, defaults, FK relationships
- [ ] `tests/migrations/test_phase16_migration.py` — Alembic migration tests: table creation, index creation, autovacuum settings in pg_class
- [ ] `tests/services/test_maintenance.py` — Cleanup function tests: age filtering (>30 days deleted, <30 days preserved), error handling
- [ ] `tests/services/test_scheduler.py` — Scheduler registration test: SCHEDULER_ENABLED guard respected, CronTrigger(hour=3, minute=0), id='cleanup_background_jobs'

All four files are created by Plan 01 Task 2. No shared conftest.py is required — tests use inline unittest.mock patching.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Autovacuum settings visible in pg_class after migration | JOBS-01 | Requires live PostgreSQL instance | `SELECT reloptions FROM pg_class WHERE relname = 'background_jobs';` — must show autovacuum_vacuum_scale_factor=0.05 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
