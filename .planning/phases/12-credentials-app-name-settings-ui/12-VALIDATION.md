---
phase: 12
slug: credentials-app-name-settings-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-16
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (confirmed from conftest.py + test_phase11_*.py) |
| **Config file** | `backend/pytest.ini` or `pyproject.toml` (verify before Wave 0) |
| **Quick run command** | `cd backend && python -m pytest tests/test_phase12_credentials.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_phase12_credentials.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-??-01 | migration | 1 | BSCFG-02/03 | — | N/A | unit | `pytest tests/test_phase12_credentials.py::test_brainsuite_app_has_system_app_name -x` | ❌ W0 | ⬜ pending |
| 12-??-02 | migration | 1 | BSCFG-02/03 | — | N/A | unit | `pytest tests/test_phase12_credentials.py::test_config_columns_dropped -x` | ❌ W0 | ⬜ pending |
| 12-??-03 | backend-creds | 2 | BSCFG-01 | Client Secret exposure | GET returns `{client_id, has_secret}` only — never raw secret | unit | `pytest tests/test_phase12_credentials.py::test_get_credentials_masks_secret -x` | ❌ W0 | ⬜ pending |
| 12-??-04 | backend-creds | 2 | BSCFG-01 | — | Empty secret on PUT keeps existing encrypted value | unit | `pytest tests/test_phase12_credentials.py::test_put_credentials_empty_secret_keeps_existing -x` | ❌ W0 | ⬜ pending |
| 12-??-05 | backend-test-conn | 2 | VSAF-01 | SSRF | Test-conn calls fixed auth URL only; returns `{success, message}` | unit | `pytest tests/test_phase12_credentials.py::test_test_connection_response_shape -x` | ❌ W0 | ⬜ pending |
| 12-??-06 | backend-rescore | 2 | VSAF-02 | Org scope | Re-score resets SCORED → UNSCORED; PROCESSING assets untouched | unit | `pytest tests/test_phase12_credentials.py::test_rescore_only_resets_scored_not_processing -x` | ❌ W0 | ⬜ pending |
| 12-??-07 | pipeline-rewire | 2 | BSCFG-02/03 | — | Scoring reads `system_app_name` from BrainsuiteApp (not OrgBrainsuiteConfig) | unit | `pytest tests/test_phase12_credentials.py::test_scoring_reads_system_app_name -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase12_credentials.py` — stubs for all 7 test cases above (Wave 0 creates the file; tasks fill in assertions)
- [ ] No new framework config needed — `conftest.py` already provides Fernet key injection and mock patterns

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Credentials section auto-collapses after save + Test Connection pass | BSCFG-04 / D-02 | Angular component state; requires browser interaction | 1. Save valid credentials. 2. Click "Test Connection" → verify success. 3. Confirm section collapses to summary row with "Edit" button. |
| Client Secret field shows placeholder `●●●●●●●● (saved)` when secret stored | BSCFG-01 / D-06 | DOM rendering of password field | 1. Save credentials with secret. 2. Reload page. 3. Verify field shows masked placeholder, not actual value. |
| "Change" + "Cancel" secret edit flow | BSCFG-01 / D-06 | Browser interaction | 1. Click "Change" → field becomes editable. 2. Click "Cancel" → field reverts to masked placeholder without API call. |
| Accordion expand / collapse on app rows | BSCFG-02 / D-04 | Angular accordion state | 1. Click chevron → panel expands with "System App Name" input. 2. Click away → panel collapses. |
| Re-score dialog only appears on actual config change | VSAF-02 / D-11 | Requires prior saved state | 1. Save credentials. 2. Save again with same values → no dialog. 3. Change client_id → dialog appears. |
| Re-score dialog buttons (Keep / Re-score all) | VSAF-02 / D-12 | MatDialog interaction | 1. Trigger re-score dialog. 2. "Keep existing scores" → no change to assets. 3. "Re-score all assets" → assets reset + snackbar shown. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
