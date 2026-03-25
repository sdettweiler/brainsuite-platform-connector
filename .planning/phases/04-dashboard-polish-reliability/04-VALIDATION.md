---
phase: 4
slug: dashboard-polish-reliability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + Angular Karma/Jasmine (frontend) |
| **Config file** | `backend/pytest.ini` / `frontend/karma.conf.js` |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ && cd ../frontend && ng test --watch=false` |
| **Estimated runtime** | ~30 seconds (backend) / ~60 seconds (frontend) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ && cd ../frontend && ng test --watch=false`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | DASH-01 | unit | `pytest tests/test_thumbnail.py -x -q` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 1 | DASH-02 | unit | `pytest tests/test_sort_filter.py -x -q` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 1 | DASH-03 | unit | `pytest tests/test_platform_health.py -x -q` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 1 | DASH-04 | unit | `pytest tests/test_reconnect.py -x -q` | ❌ W0 | ⬜ pending |
| 4-03-01 | 03 | 2 | DASH-04 | e2e | manual — browser reconnect flow | N/A | ⬜ pending |
| 4-03-02 | 03 | 2 | DASH-05 | unit | `pytest tests/test_sort_filter.py::test_null_handling -x -q` | ❌ W0 | ⬜ pending |
| 4-04-01 | 04 | 2 | REL-01 | unit | `pytest tests/test_scheduler.py -x -q` | ❌ W0 | ⬜ pending |
| 4-04-02 | 04 | 2 | REL-02 | integration | `pytest tests/test_scheduler.py::test_single_worker -x -q` | ❌ W0 | ⬜ pending |
| 4-04-03 | 04 | 2 | REL-03 | unit | `pytest tests/test_scheduler.py::test_scheduler_enabled_guard -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_thumbnail.py` — stubs for DASH-01 (thumbnail URL in creative response)
- [ ] `backend/tests/test_sort_filter.py` — stubs for DASH-02, DASH-05 (sort keys, null handling)
- [ ] `backend/tests/test_platform_health.py` — stubs for DASH-03 (health indicator field in response)
- [ ] `backend/tests/test_reconnect.py` — stubs for DASH-04 (token_expiry field, reconnect trigger)
- [ ] `backend/tests/test_scheduler.py` — stubs for REL-01, REL-02, REL-03 (SCHEDULER_ENABLED guard)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Inline reconnect prompt appears when token expires | DASH-04 | Browser OAuth flow required | 1. Expire a Meta token in DB. 2. Load platform panel. 3. Verify reconnect CTA visible |
| Thumbnail renders for image and video creatives | DASH-01 | Requires actual Meta presigned URL | 1. Open creative list. 2. Verify img/video thumbnail visible for each creative type |
| Sorted results update without page reload | DASH-02 | Requires browser interaction | 1. Click BrainSuite score column header. 2. Verify list reorders without full reload |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
