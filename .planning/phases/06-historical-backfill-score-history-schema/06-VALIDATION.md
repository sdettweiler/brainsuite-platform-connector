---
phase: 6
slug: historical-backfill-score-history-schema
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | backend/pytest.ini or pyproject.toml |
| **Quick run command** | `cd backend && pytest tests/ -x -q --tb=short` |
| **Full suite command** | `cd backend && pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `cd backend && pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 6-01-01 | 01 | 0 | BACK-01 | unit stub | `pytest tests/test_backfill.py -x -q` | ❌ W0 | ⬜ pending |
| 6-01-02 | 01 | 1 | BACK-01 | unit | `pytest tests/test_backfill.py -x -q` | ✅ | ⬜ pending |
| 6-01-03 | 01 | 1 | BACK-02 | unit | `pytest tests/test_backfill.py -x -q` | ✅ | ⬜ pending |
| 6-02-01 | 02 | 1 | BACK-01, BACK-02 | integration | `pytest tests/test_backfill.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_backfill.py` — stubs for BACK-01, BACK-02
- [ ] Fixtures for mock `creative_score_results` rows without scores

*Existing pytest infrastructure covers the framework; Wave 0 only needs test stubs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Admin endpoint returns 202 with approximate count | BACK-01 | Requires live DB with unscored rows | Call `POST /admin/backfill-scoring`, verify 202 + body contains `queued` count |
| BackgroundTask does not block response | BACK-02 | Runtime behavior, not testable with unit mocks | Response returns before backfill finishes; check server logs for background completion |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
