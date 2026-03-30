---
phase: 7
slug: score-trend-performer-highlights-performance-tab
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) |
| **Config file** | `backend/pytest.ini` or `backend/pyproject.toml` |
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

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 1 | TREND-02 | unit | `cd backend && python -m pytest tests/test_score_history.py -x -q` | ❌ W0 | ⬜ pending |
| 7-01-02 | 01 | 1 | TREND-02 | unit | `cd backend && python -m pytest tests/test_score_history.py -x -q` | ❌ W0 | ⬜ pending |
| 7-02-01 | 02 | 1 | TREND-03 | unit | `cd backend && python -m pytest tests/test_score_trend_endpoint.py -x -q` | ❌ W0 | ⬜ pending |
| 7-02-02 | 02 | 1 | TREND-03 | manual | See manual verifications | N/A | ⬜ pending |
| 7-03-01 | 03 | 2 | PERF-01 | unit | `cd backend && python -m pytest tests/test_performer_tag.py -x -q` | ❌ W0 | ⬜ pending |
| 7-03-02 | 03 | 2 | PERF-01 | manual | See manual verifications | N/A | ⬜ pending |
| 7-04-01 | 04 | 2 | UI-01 | manual | See manual verifications | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_score_history.py` — stubs for TREND-02 (history append, upsert dedup)
- [ ] `backend/tests/test_score_trend_endpoint.py` — stubs for TREND-03 (GET endpoint, 30-day window, empty state)
- [ ] `backend/tests/test_performer_tag.py` — stubs for PERF-01 (PERCENT_RANK logic, 10-asset guard)

*Existing test infrastructure covers execution; only new test files need to be created in Wave 0.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ECharts line chart renders in asset detail dialog | TREND-03 | Angular component rendering requires browser | Open asset detail dialog → Score Trend tab → verify line chart appears with data or empty state |
| Performer badge overlays render on grid cards | PERF-01 | Angular DOM overlay requires browser | Open dashboard → verify top/bottom 10% cards show green/red badges at bottom-left |
| Performance tab tile/card layout matches CE tab style | UI-01 | Visual parity requires browser comparison | Open asset detail dialog → Performance tab → compare tile layout against Creative Effectiveness tab |
| Score trend respects dashboard platform filter | TREND-03 | Filter integration requires browser E2E | Select a platform filter → open asset detail → verify trend data reflects selected platform |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
