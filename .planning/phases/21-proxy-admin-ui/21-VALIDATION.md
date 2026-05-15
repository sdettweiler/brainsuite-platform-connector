---
phase: 21
slug: proxy-admin-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pytest.ini` or `pyproject.toml` |
| **Quick run command** | `pytest tests/test_super_admin_proxy.py -v` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_super_admin_proxy.py -v`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 21-01-01 | 01 | 0 | PROXY-05 | — | N/A | unit | `pytest tests/test_super_admin_proxy.py -v` | ❌ W0 | ⬜ pending |
| 21-02-01 | 02 | 1 | PROXY-05 | T-21-01 | Non-SuperAdmin gets 403 | unit | `pytest tests/test_super_admin_proxy.py::test_get_proxy_config_unauthorized -v` | ❌ W0 | ⬜ pending |
| 21-02-02 | 02 | 1 | PROXY-05 | T-21-02 | URL never returned decrypted | unit | `pytest tests/test_super_admin_proxy.py::test_url_never_returned_plaintext -v` | ❌ W0 | ⬜ pending |
| 21-02-03 | 02 | 1 | PROXY-05 | T-21-03 | Toggle state persists correctly | unit | `pytest tests/test_super_admin_proxy.py::test_toggle_enabled_disabled -v` | ❌ W0 | ⬜ pending |
| 21-03-01 | 03 | 2 | PROXY-05 | — | Card hidden from non-SuperAdmin | manual | UI inspection | — | ⬜ pending |
| 21-03-02 | 03 | 2 | PROXY-05 | — | Masked URL shown in configured state | manual | UI inspection | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_super_admin_proxy.py` — stubs for PROXY-05 (8 tests)
- [ ] Existing `tests/conftest.py` — shared fixtures (already exists)

*Wave 0 must create test stubs before any backend implementation.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Proxy card hidden from non-SuperAdmin | PROXY-05 | Angular role-based rendering requires browser | Log in as non-SuperAdmin, navigate to /configuration/admin, confirm Residential Proxy card is absent |
| Masked URL shown in UI (never decrypted) | PROXY-05 | Visual masking requires browser | Save a proxy URL, reload page, confirm display shows masked format only |
| Toggle disable immediately stops proxy injection | PROXY-05 | Requires live download trigger after toggle | Toggle off, trigger a download, confirm request logs show no proxy headers |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
