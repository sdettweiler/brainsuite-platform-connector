---
phase: 8
slug: score-to-roas-correlation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-31
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 |
| **Config file** | `backend/tests/conftest.py` |
| **Quick run command** | `cd backend && python -m pytest tests/test_correlation.py -x` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_correlation.py -x`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 8-01-01 | 01 | 0 | CORR-01, CORR-02 | unit | `cd backend && python -m pytest tests/test_correlation.py -x` | ❌ W0 | ⬜ pending |
| 8-02-01 | 02 | 1 | CORR-01 | unit | `cd backend && python -m pytest tests/test_correlation.py::test_correlation_data_returns_scored_assets -x` | ❌ W0 | ⬜ pending |
| 8-02-02 | 02 | 1 | CORR-02 | unit | `cd backend && python -m pytest tests/test_correlation.py::test_zero_roas_preserved -x` | ❌ W0 | ⬜ pending |
| 8-02-03 | 02 | 1 | CORR-01 | unit | `cd backend && python -m pytest tests/test_correlation.py::test_null_roas_excluded -x` | ❌ W0 | ⬜ pending |
| 8-03-01 | 03 | 2 | CORR-01, CORR-02 | manual | Angular `ng serve` + browser smoke test | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_correlation.py` — covers CORR-01 (endpoint shape, null exclusion) and CORR-02 (zero ROAS preserved, no pagination)
- [ ] Ensure `backend/tests/conftest.py` fixtures cover the new endpoint (mock DB session pattern from `test_performer_tag.py`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Scatter chart renders in right-side drawer on ROAS tile click | CORR-01 | Angular component rendering; ECharts visual output | Open dashboard, click Avg ROAS tile, verify drawer slides in with scatter chart |
| Hover tooltip shows thumbnail, score, ROAS, spend, platform | CORR-01 | Visual DOM interaction | Hover a dot, verify tooltip content matches expected fields |
| Quadrant labels (Stars/Workhorses/Question Marks/Laggards) visible | CORR-01 | ECharts graphic elements | Inspect chart for 4 corner labels |
| Dot click opens AssetDetailDialogComponent | CORR-01 | Angular Dialog integration | Click a scatter dot, verify asset detail dialog opens with correct asset |
| Spend threshold input filters chart dynamically | CORR-02 | Client-side reactive update | Change threshold from $10 to $100, verify fewer dots displayed |
| Y-axis cap reference line visible for outlier datasets | CORR-02 | Visual output | Requires dataset with ROAS outliers above 99th percentile |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
