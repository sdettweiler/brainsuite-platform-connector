---
phase: 22
slug: dashboard-metadata-account-filters
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini or pyproject.toml |
| **Quick run command** | `pytest tests/ -x -q --tb=short` |
| **Full suite command** | `pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `pytest tests/ -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 22-01-01 | 01 | 0 | DASH-01 | T-22-01 | Metadata endpoint guards org_id; cross-org values never returned | unit | `pytest tests/test_metadata_filter.py -x -q` | ❌ W0 | ⬜ pending |
| 22-01-02 | 01 | 1 | DASH-01 | T-22-01 | Alembic migration creates composite index on asset_metadata_values(field_id, value) | unit | `pytest tests/test_metadata_migration.py -x -q` | ❌ W0 | ⬜ pending |
| 22-01-03 | 01 | 1 | DASH-01 | — | GET /metadata-fields returns only fields for current user's org | unit | `pytest tests/test_metadata_filter.py::test_org_scoped_fields -x -q` | ❌ W0 | ⬜ pending |
| 22-01-04 | 01 | 1 | DASH-01 | — | GET /metadata-fields/{id}/values returns only values present in current org's assets | unit | `pytest tests/test_metadata_filter.py::test_org_scoped_values -x -q` | ❌ W0 | ⬜ pending |
| 22-01-05 | 01 | 2 | DASH-01 | — | metadata_filter query param applied as AND JOIN on asset grid endpoint | unit | `pytest tests/test_asset_grid_filters.py -x -q` | ❌ W0 | ⬜ pending |
| 22-02-01 | 02 | 2 | DASH-02 | — | Account filter multi-select persists across pagination and composes with metadata filter | unit | `pytest tests/test_asset_grid_filters.py::test_multi_account_filter -x -q` | ❌ W0 | ⬜ pending |
| 22-02-02 | 02 | 2 | DASH-02 | — | Platform grouping renders correct section headers (META, TIKTOK, GOOGLE ADS, DV360) | manual | see Manual-Only section | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_metadata_filter.py` — stubs for DASH-01 org-scoped field/value endpoints
- [ ] `tests/test_metadata_migration.py` — stub for composite index migration verification
- [ ] `tests/test_asset_grid_filters.py` — stubs for multi-filter AND composition + multi-account filter

*Existing pytest infrastructure covers the framework; only new test files are required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Platform grouping headers in account dropdown | DASH-02 | DOM/visual assertion not in current pytest scope | Open dashboard, expand Ad Accounts filter, verify section headers META / TIKTOK / GOOGLE ADS / DV360 appear above their respective accounts |
| Two-step metadata picker UX (field list → value autocomplete) | DASH-01 | Angular component interaction | Open Metadata filter, select a field, type 2+ chars, verify matching suggestions appear from org data only |
| Clear all filters resets grid | DASH-01, DASH-02 | State reset across multiple Angular components | Apply metadata + account filter, click "Clear all filters", verify grid returns to unfiltered state |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
