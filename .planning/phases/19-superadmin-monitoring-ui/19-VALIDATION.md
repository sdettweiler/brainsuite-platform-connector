---
phase: 19
slug: superadmin-monitoring-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-11
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend), Angular unit tests (frontend) |
| **Config file** | `backend/pytest.ini` or `backend/pyproject.toml` |
| **Quick run command** | `cd backend && python -m pytest tests/test_jobs_api.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_jobs_api.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| Backend schemas | 01 | 1 | MON-03,04,05,06 | No output/error in list response | unit | `pytest tests/test_jobs_api.py::test_list_omits_jsonb -x` | ⬜ pending |
| GET /jobs endpoint | 01 | 1 | MON-01 | 403 for non-SuperAdmin | unit | `pytest tests/test_jobs_api.py::test_list_jobs -x` | ⬜ pending |
| GET /jobs/{id} endpoint | 01 | 1 | MON-03,04,05,06,07 | 404 for unknown ID; 403 for non-SuperAdmin | unit | `pytest tests/test_jobs_api.py::test_get_job_detail -x` | ⬜ pending |
| DELETE /jobs endpoint | 01 | 1 | MON-01 | 403 for non-SuperAdmin; only deletes COMPLETE/FAILED | unit | `pytest tests/test_jobs_api.py::test_delete_jobs -x` | ⬜ pending |
| JobMonitorService | 02 | 2 | MON-01,02 | EventSource closes on destroy | unit | Angular test runner | ⬜ pending |
| Job monitor page | 02 | 2 | MON-01,02 | Tab counts accurate | unit | Angular test runner | ⬜ pending |
| Job detail panel | 03 | 2 | MON-03,04,05,06,07 | Traceback truncated at 10KB | unit | Angular test runner | ⬜ pending |
| Route + sidebar | 02 | 2 | MON-01 | Non-SuperAdmin redirected | integration | manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_jobs_api.py` — stubs for GET /jobs, GET /jobs/{id}, DELETE /jobs (8 test stubs)
- [ ] `backend/app/schemas/jobs.py` — JobListItem + JobDetail Pydantic schemas

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SSE live updates in browser | MON-01, MON-02 | EventSource browser behavior | Open /configuration/jobs, trigger a sync, confirm job row updates without refresh |
| Copy traceback button | MON-05 | Clipboard API requires browser | Open failed job panel, click "Copy traceback", paste into text editor, confirm full traceback |
| Copy job_id button | MON-07 | Clipboard API requires browser | Open any job panel, click copy icon next to job_id, confirm clipboard matches UUID |
| Progress bar advancing | MON-02 | Real-time SSE requires live job | Trigger download, confirm progress bar increments (7/10 → 8/10 etc.) |
| SSE connection badge states | MON-01 | Network manipulation required | Disconnect network, confirm "Reconnecting…" badge; reconnect, confirm "Live" badge |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
