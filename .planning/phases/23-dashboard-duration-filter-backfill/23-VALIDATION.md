---
phase: 23
slug: dashboard-duration-filter-backfill
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-18
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + SQLAlchemy async fixtures |
| **Config file** | `backend/pytest.ini` or `pyproject.toml` |
| **Quick run command** | `pytest backend/tests/test_dashboard_duration.py -x -v` |
| **Full suite command** | `pytest backend/tests/ -x -v` |
| **Estimated runtime** | ~15 seconds (quick) / ~30 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/test_dashboard_duration.py -x -v`
- **After every plan wave:** Run `pytest backend/tests/ -x -v`
- **Before `/gsd:verify-work`:** Full suite must be green + manual browser verification of slider UX
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 23-01-01 | 01 | 1 | DASH-03 | T-23-01 | org_id guard on duration-bounds query | unit | `pytest backend/tests/test_dashboard_duration.py::test_duration_bounds_org_scoped -xvs` | ❌ Wave 0 | ⬜ pending |
| 23-01-02 | 01 | 1 | DASH-03 | — | duration_min/max BETWEEN filter applied | unit | `pytest backend/tests/test_dashboard_duration.py::test_duration_filter_between -xvs` | ❌ Wave 0 | ⬜ pending |
| 23-01-03 | 01 | 1 | DASH-03 | — | null_duration_count returned when filter active | unit | `pytest backend/tests/test_dashboard_duration.py::test_null_duration_count -xvs` | ❌ Wave 0 | ⬜ pending |
| 23-01-04 | 01 | 1 | DASH-03 | — | backfill job lifecycle (create→run→complete) | integration | `pytest backend/tests/test_dashboard_duration.py::test_backfill_job_lifecycle -xvs` | ❌ Wave 0 | ⬜ pending |
| 23-02-01 | 02 | 2 | DASH-03 | — | slider renders only when hasVideoAssets=true | e2e | Manual browser test | ✅ Manual-only | ⬜ pending |
| 23-02-02 | 02 | 2 | DASH-03 | — | NULL callout shown only when filter active | e2e | Manual browser test | ✅ Manual-only | ⬜ pending |
| 23-02-03 | 02 | 2 | DASH-03 | — | duration bounds reload on other filter change | integration | Manual browser test | ✅ Manual-only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_dashboard_duration.py` — stubs for all 4 automated test cases above (test_duration_bounds_org_scoped, test_duration_filter_between, test_null_duration_count, test_backfill_job_lifecycle)
- [ ] Test must import CreativeAsset, Organization, and use async DB fixtures consistent with Phase 22 test patterns

*Existing test infrastructure (pytest async fixtures in conftest.py) covers all other needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Duration slider renders when video assets exist | DASH-03 SC-1 | Angular component visibility requires browser rendering | Load dashboard with VIDEO assets; confirm slider appears in filter bar |
| Duration slider hidden when no video assets | DASH-03 SC-1 | Angular conditional rendering | Load dashboard with IMAGE-only assets; confirm slider absent |
| NULL duration callout shown when filter active | DASH-03 SC-3 | Dynamic count requires real data | Apply duration filter; confirm callout with X count appears below chip row |
| Duration bounds update when other filters change | DASH-03 D-02 | Filter interaction requires live UI state | Apply account filter; confirm slider bounds recompute |
| All three filters compose correctly | DASH-03 SC-5 | Multi-filter composition requires live UI state | Apply metadata + account + duration filters; confirm grid shows correct intersected results |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
