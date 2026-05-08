---
phase: 17
slug: service-instrumentation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (async via pytest-asyncio) |
| **Config file** | `backend/pytest.ini` or `backend/pyproject.toml` |
| **Quick run command** | `cd backend && python -m pytest tests/services/test_instrumentation.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/services/test_instrumentation.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 0 | INSTR-01–05 | — | N/A | unit | `pytest tests/services/test_instrumentation.py -x -q` | ❌ W0 | ⬜ pending |
| 17-02-01 | 02 | 1 | INSTR-01 | — | N/A | unit | `pytest tests/services/test_instrumentation.py::test_sync_job_creates_background_job -x -q` | ❌ W0 | ⬜ pending |
| 17-03-01 | 03 | 1 | INSTR-02 | — | N/A | unit | `pytest tests/services/test_instrumentation.py::test_download_progress_increments -x -q` | ❌ W0 | ⬜ pending |
| 17-04-01 | 04 | 1 | INSTR-03 | — | N/A | unit | `pytest tests/services/test_instrumentation.py::test_autofill_output_schema -x -q` | ❌ W0 | ⬜ pending |
| 17-05-01 | 05 | 1 | INSTR-04, INSTR-05 | — | N/A | unit | `pytest tests/services/test_instrumentation.py::test_scoring_output_schema -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/services/test_instrumentation.py` — stubs for INSTR-01 through INSTR-05 (all five requirements)
- [ ] Shared mock fixtures for `get_session_factory()` — prevents real DB hits in unit tests

*Wave 0 must be committed before Wave 1 instrumentation work begins.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PENDING → RUNNING → COMPLETE transition in real DB | INSTR-01 | Requires running sync against live platform | Trigger sync, query `background_jobs` table, verify status transitions |
| progress_current increments live during download | INSTR-02 | Requires download in flight | Start download batch, poll DB every 2 seconds, verify count rises |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
