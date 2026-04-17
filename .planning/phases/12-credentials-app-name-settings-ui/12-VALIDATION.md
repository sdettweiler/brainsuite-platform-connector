---
phase: 12
slug: credentials-app-name-settings-ui
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-16
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (confirmed from conftest.py + test_phase11_*.py) |
| **Config file** | `backend/pytest.ini` or `pyproject.toml` (verify before Wave 1) |
| **Quick run command** | `cd backend && python -m pytest tests/test_phase12_schema_pipeline.py tests/test_phase12_endpoints.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run the plan-specific test file (see per-task map below)
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

> Wave 0 note: Tests are created inline by each plan's Task 3 — no separate Wave 0 plan required. All files are `✅ inline` (created and run within the same task that writes them).

| Task | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File |
|------|------|------|-------------|-----------------|-----------|-------------------|------|
| 12-01 T1 | migration | 1 | BSCFG-02/03 | N/A | unit | `pytest tests/test_phase12_schema_pipeline.py::test_brainsuite_app_has_system_app_name -x` | ✅ inline |
| 12-01 T1 | migration | 1 | BSCFG-02/03 | N/A | unit | `pytest tests/test_phase12_schema_pipeline.py::test_org_config_no_video_app_name -x` | ✅ inline |
| 12-01 T1 | migration | 1 | BSCFG-02/03 | N/A | unit | `pytest tests/test_phase12_schema_pipeline.py::test_org_config_no_static_app_name -x` | ✅ inline |
| 12-01 T2 | pipeline-rewire | 1 | BSCFG-02/03 | Scoring reads system_app_name from BrainsuiteApp (not OrgBrainsuiteConfig) | unit | `pytest tests/test_phase12_schema_pipeline.py::test_scoring_job_uses_system_app_name -x` | ✅ inline |
| 12-01 T2 | pipeline-rewire | 1 | BSCFG-02/03 | N/A | unit | `pytest tests/test_phase12_schema_pipeline.py::test_scoring_job_imports_brainsuite_app -x` | ✅ inline |
| 12-01 T2 | pipeline-rewire | 1 | BSCFG-02/03 | N/A | unit | `pytest tests/test_phase12_schema_pipeline.py::test_scoring_job_no_video_app_name -x` | ✅ inline |
| 12-02 T2 | backend-creds | 2 | BSCFG-01 | GET returns `{client_id, has_secret}` only — never raw secret | unit | `pytest tests/test_phase12_endpoints.py::test_secret_never_returned -x` | ✅ inline |
| 12-02 T2 | backend-creds | 2 | BSCFG-01 | Empty secret on PUT keeps existing encrypted value | unit | `pytest tests/test_phase12_endpoints.py::test_empty_secret_keeps_existing -x` | ✅ inline |
| 12-02 T2 | backend-test-conn | 2 | VSAF-01 | Test-conn checks access_token key (not just HTTP 200) | unit | `pytest tests/test_phase12_endpoints.py::test_test_connection_checks_access_token -x` | ✅ inline |
| 12-02 T2 | backend-rescore | 2 | VSAF-02 | Re-score resets COMPLETE → UNSCORED; PROCESSING assets untouched | unit | `pytest tests/test_phase12_endpoints.py::test_rescore_targets_complete_not_scored -x` | ✅ inline |
| 12-02 T2 | backend-rescore | 2 | VSAF-02 | N/A | unit | `pytest tests/test_phase12_endpoints.py::test_rescore_does_not_touch_processing -x` | ✅ inline |
| 12-02 T1 | router-registration | 2 | BSCFG-04 | All endpoints use get_current_admin guard | unit | `pytest tests/test_phase12_endpoints.py::test_all_endpoints_use_admin_guard -x` | ✅ inline |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Inline approach — no separate Wave 0 plan. Each plan's Task 3 creates and immediately runs its test file:

- ✅ `tests/test_phase12_schema_pipeline.py` — created by Plan 01 Task 3 (10 tests: schema, migration, pipeline re-wire)
- ✅ `tests/test_phase12_endpoints.py` — created by Plan 02 Task 3 (10 tests: endpoint logic, security, rescore)
- ✅ No new framework config needed — `conftest.py` already provides Fernet key injection and mock patterns

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Credentials section auto-collapses after save + Test Connection pass | BSCFG-04 / D-02 | Angular component state; requires browser interaction | 1. Save valid credentials. 2. Click "Test Connection" → verify success. 3. Confirm section collapses to summary row with "Edit credentials" button. |
| Client Secret field shows placeholder `●●●●●●●● (saved)` when secret stored | BSCFG-01 / D-06 | DOM rendering of password field | 1. Save credentials with secret. 2. Reload page. 3. Verify field shows masked placeholder, not actual value. |
| "Change secret" + "Discard changes" flow | BSCFG-01 / D-06 | Browser interaction | 1. Click "Change secret" → field becomes editable. 2. Click "Discard changes" → field reverts to masked placeholder without API call. |
| Accordion expand / collapse on app rows | BSCFG-02 / D-04 | Angular accordion state | 1. Click chevron → panel expands with "BrainSuite API App Name" input. 2. Click away → panel collapses. |
| Re-score dialog only appears on actual config change | VSAF-02 / D-11 | Requires prior saved state | 1. Save credentials. 2. Save again with same values → no dialog. 3. Change client_id → dialog appears. |
| Re-score dialog buttons (Keep / Re-score all) | VSAF-02 / D-12 | MatDialog interaction | 1. Trigger re-score dialog. 2. "Keep existing scores" → no change to assets. 3. "Re-score all assets" → assets reset + snackbar shown. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (inline approach — Task 3 in each plan)
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-17
