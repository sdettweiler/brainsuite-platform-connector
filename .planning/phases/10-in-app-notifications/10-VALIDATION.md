---
phase: 10
slug: in-app-notifications
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini or pyproject.toml |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | NOTIF-01 | — | notifications table rows scoped to org_id | unit | `python -m pytest tests/test_notifications.py -x -q` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | NOTIF-01 | — | sync completion fires notification | unit | `python -m pytest tests/test_notifications.py::test_sync_complete_notification -x -q` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 1 | NOTIF-01 | — | sync error fires notification | unit | `python -m pytest tests/test_notifications.py::test_sync_error_notification -x -q` | ❌ W0 | ⬜ pending |
| 10-01-04 | 01 | 2 | NOTIF-02 | — | scoring batch fires per-org notification | unit | `python -m pytest tests/test_notifications.py::test_scoring_batch_notification -x -q` | ❌ W0 | ⬜ pending |
| 10-01-05 | 01 | 2 | NOTIF-03 | — | token expiry fires notification | unit | `python -m pytest tests/test_notifications.py::test_token_expiry_notification -x -q` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 3 | NOTIF-04 | — | GET /notifications/unread returns org-scoped rows | integration | `python -m pytest tests/test_notifications_api.py -x -q` | ❌ W0 | ⬜ pending |
| 10-02-02 | 02 | 3 | NOTIF-04 | — | PATCH /notifications/:id/read marks as read | integration | `python -m pytest tests/test_notifications_api.py::test_mark_read -x -q` | ❌ W0 | ⬜ pending |
| 10-02-03 | 02 | 3 | NOTIF-04 | — | POST /notifications/read-all marks all org notifications | integration | `python -m pytest tests/test_notifications_api.py::test_mark_all_read -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_notifications.py` — stubs for NOTIF-01, NOTIF-02, NOTIF-03
- [ ] `tests/test_notifications_api.py` — stubs for NOTIF-04
- [ ] `tests/conftest.py` — shared fixtures (db session, org fixture)

*Existing pytest infrastructure covers test execution; only test files need creating.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bell icon badge updates after 30s poll | NOTIF-04 | Requires browser + running app + wait 30s | Open app, trigger a notification event, wait 30s, verify badge count increments |
| MatSnackBar toast appears for high-priority events | NOTIF-05 | Browser UI interaction | Expire a token or trigger sync failure, verify toast appears without opening inbox |
| MatMenu opens on bell click, closes on outside click | NOTIF-04 | Browser UI interaction | Click bell, verify list opens; click outside, verify closes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
