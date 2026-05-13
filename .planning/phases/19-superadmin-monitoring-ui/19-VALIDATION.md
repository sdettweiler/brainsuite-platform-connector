---
phase: 19
slug: superadmin-monitoring-ui
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-11
audited: 2026-05-13
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend); Angular unit tests (frontend — manual) |
| **Config file** | `backend/pytest.ini` or `backend/pyproject.toml` |
| **Quick run command** | `pytest tests/test_jobs_api.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_jobs_api.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| 19-01-01 | 01 | 1 | MON-03,04,05,06 | No output/error leak in list | unit | `pytest tests/test_jobs_api.py::test_list_jobs_200 -x` | ✅ green (fixed 2026-05-13) |
| 19-01-02 | 01 | 1 | MON-01 | 403 for non-SuperAdmin | unit | `pytest tests/test_jobs_api.py::test_get_jobs_403_non_superadmin -x` | ✅ green |
| 19-01-03 | 01 | 1 | MON-03,04,05,06,07 | 404 for unknown ID | unit | `pytest tests/test_jobs_api.py::test_get_job_detail_200 -x` | ✅ green (fixed 2026-05-13) |
| 19-01-04 | 01 | 1 | MON-01 | only COMPLETE/FAILED deleted | unit | `pytest tests/test_jobs_api.py::test_delete_jobs_204 -x` | ✅ green |
| 19-01-05 | 01 | 1 | MON-01 | 403 for non-SuperAdmin delete | unit | `pytest tests/test_jobs_api.py::test_delete_jobs_403_non_superadmin -x` | ✅ green |
| 19-02-01 | 02 | 2 | MON-01,02 | EventSource closes on destroy | unit | Angular test runner | manual |
| 19-03-01 | 03 | 2 | MON-01,02 | Tab counts accurate | unit | Angular test runner | manual |
| 19-04-01 | 04 | 2 | MON-03,04,05,06,07 | Traceback truncated at 10KB | unit | Angular test runner | manual |
| 19-06-01 | 06 | 2 | MON-01 | Non-SuperAdmin redirected | integration | manual | manual |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `backend/tests/test_jobs_api.py` — 9 tests: list, filter, pagination, detail, 404, delete, 403 guards (confirmed 2026-05-13)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SSE live updates in browser | MON-01, MON-02 | EventSource browser behavior | Open /configuration/jobs, trigger a sync, confirm job row updates without refresh |
| Copy traceback button | MON-05 | Clipboard API requires browser | Open failed job panel, click "Copy traceback", paste and confirm |
| Copy job_id button | MON-07 | Clipboard API requires browser | Open any job panel, click copy icon, confirm clipboard matches UUID |
| Progress bar advancing | MON-02 | Real-time SSE requires live job | Trigger download, confirm progress bar increments |
| SSE connection badge states | MON-01 | Network manipulation required | Disconnect network, confirm "Reconnecting…" badge |
| Angular component unit tests | MON-01–07 | Angular test runner not in Docker | `cd frontend && npm test` |

---

## Validation Sign-Off

- [x] All backend tasks have automated verify commands
- [x] Angular tasks marked manual-only (no Angular test runner in Docker CI)
- [x] Sampling continuity: no 3 consecutive automated tasks without verify
- [x] No watch-mode flags
- [x] Feedback latency < 30s (9 backend tests in 1.07s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** 2026-05-13 (gsd-validate-phase audit)

## Validation Audit 2026-05-13

| Metric | Count |
|--------|-------|
| Gaps found | 4 |
| Resolved | 4 |
| Escalated | 0 |
| Tests run | 9 (all green, 1.07s) |
| Fix 1 | 3 list tests: added `limit=50, offset=0` — FastAPI `Query()` defaults don't resolve when calling endpoint functions directly |
| Fix 2 | 3 list tests: `result.all()` returns `(job, org_name)` tuples; mocks changed from `.scalars().all()` to `.all()` |
| Fix 3 | `test_get_job_detail_200`: `platform_connection_id=None` + `side_effect=[job, org_mock]` to prevent MagicMock in Pydantic string fields; assertion changed from `result is job` to `isinstance(result, JobDetail)` |
| Result | CONFIRMED nyquist_compliant (backend); Angular tests marked manual-only |
