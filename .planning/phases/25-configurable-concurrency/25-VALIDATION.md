---
phase: 25
slug: configurable-concurrency
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-18
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) / Angular Karma+Jasmine (frontend) |
| **Config file** | `backend/pytest.ini` (or `pyproject.toml`) / `frontend/karma.conf.js` |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 25-01-01 | 01 | 1 | PERF-02 | — | max_concurrent_downloads default=3 on fresh row | unit | `pytest tests/ -k "test_system_config"` | ❌ W0 | ⬜ pending |
| 25-01-02 | 01 | 1 | PERF-02 | — | Alembic migration applies without error | unit | `pytest tests/ -k "test_migration"` | ❌ W0 | ⬜ pending |
| 25-02-01 | 02 | 2 | PERF-02 | — | Semaphore created with correct capacity from DB | unit | `pytest tests/ -k "test_semaphore_cache"` | ❌ W0 | ⬜ pending |
| 25-02-02 | 02 | 2 | PERF-02 | — | DV360 _do_download wrapped with semaphore | unit | `pytest tests/ -k "test_dv360_semaphore"` | ❌ W0 | ⬜ pending |
| 25-02-03 | 02 | 2 | PERF-02 | — | Google Ads _download_video wrapped with semaphore | unit | `pytest tests/ -k "test_google_ads_semaphore"` | ❌ W0 | ⬜ pending |
| 25-02-04 | 02 | 2 | PERF-02 | — | GET endpoint returns max_concurrent_downloads | unit | `pytest tests/ -k "test_concurrency_get"` | ❌ W0 | ⬜ pending |
| 25-02-05 | 02 | 2 | PERF-02 | — | PUT endpoint validates range 1–10 | unit | `pytest tests/ -k "test_concurrency_put"` | ❌ W0 | ⬜ pending |
| 25-03-01 | 03 | 3 | PERF-02 | — | Admin page renders Parallel Downloads subsection | manual | n/a — visual UAT | manual | ⬜ pending |
| 25-03-02 | 03 | 3 | PERF-02 | — | mat-slider visible with range 1–10, default 3 | manual | n/a — visual UAT | manual | ⬜ pending |
| 25-03-03 | 03 | 3 | PERF-02 | — | Save persists value to DB; discard reverts slider | manual | n/a — visual UAT | manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_system_config_concurrency.py` — unit tests for SystemConfig.max_concurrent_downloads default and Alembic migration
- [ ] `backend/tests/test_semaphore_cache.py` — unit tests for semaphore cache creation, TTL refresh, and capacity update on config change
- [ ] `backend/tests/test_concurrency_api.py` — unit tests for GET/PUT concurrency endpoints (range validation, auth guard)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Admin page section restructure (Parallel Downloads → Residential Proxy → Cookies) | PERF-02 D-06 | Angular component visual layout — not unit-testable | Open /configuration/admin, confirm three subsections with dividers in correct order |
| mat-slider discrete tick marks visible at each integer | PERF-02 D-09 | Angular Material visual rendering — not unit-testable | Open admin page, inspect slider for tick marks at 1–10 |
| Two simultaneous download jobs visibly queue in monitoring UI | SC-2 | Integration behavior requiring live jobs | Set max=1, trigger two simultaneous downloads, observe monitoring UI queuing |
| Concurrency change takes effect within 60s | SC-4 | TTL cache timing — requires live running service | Change setting, wait 60s, verify next download respects new limit |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
