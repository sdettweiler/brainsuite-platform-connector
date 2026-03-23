---
phase: 3
slug: brainsuite-scoring-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4.0+ with pytest-asyncio 0.23.0+ |
| **Config file** | `pyproject.toml` (`testpaths = ["backend/tests"]`, `asyncio_mode = "auto"`) |
| **Quick run command** | `pytest backend/tests/test_scoring.py -x` |
| **Full suite command** | `pytest backend/tests/ -x` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/test_scoring.py -x`
- **After every plan wave:** Run `pytest backend/tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-??-01 | 01 | 0 | SCORE-01 | unit | `pytest backend/tests/test_scoring.py::test_score_result_model -x` | ❌ W0 | ⬜ pending |
| 3-??-02 | 01 | 0 | SCORE-02 | unit | `pytest backend/tests/test_scoring.py::test_token_caching -x` | ❌ W0 | ⬜ pending |
| 3-??-03 | 01 | 0 | SCORE-02 | unit | `pytest backend/tests/test_scoring.py::test_retry_logic -x` | ❌ W0 | ⬜ pending |
| 3-??-04 | 01 | 0 | SCORE-03 | unit | `pytest backend/tests/test_scoring.py::test_signed_url_generation -x` | ❌ W0 | ⬜ pending |
| 3-??-05 | 01 | 0 | SCORE-04 | unit | `pytest backend/tests/test_scoring.py::test_batch_size_limit -x` | ❌ W0 | ⬜ pending |
| 3-??-06 | 01 | 0 | SCORE-05 | unit | `pytest backend/tests/test_scoring.py::test_unscored_queue_injection -x` | ❌ W0 | ⬜ pending |
| 3-??-07 | 01 | 0 | SCORE-06 | unit | `pytest backend/tests/test_scoring.py::test_rescore_endpoint -x` | ❌ W0 | ⬜ pending |
| 3-??-08 | 01 | 0 | SCORE-07 | unit | `pytest backend/tests/test_scoring.py::test_score_dimensions_no_viz_urls -x` | ❌ W0 | ⬜ pending |
| 3-??-09 | 01 | 0 | SCORE-08 | unit | `pytest backend/tests/test_scoring.py::test_scoring_status_endpoint -x` | ❌ W0 | ⬜ pending |
| 3-??-10 | 01 | 0 | SCORE-08 | unit | `pytest backend/tests/test_scoring.py::test_channel_mapping -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_scoring.py` — stubs for SCORE-01 through SCORE-08
- [ ] `backend/requirements.txt` — add `tenacity>=8.2.0`
- [ ] No new conftest.py needed — existing `backend/tests/conftest.py` has reusable fixtures

*Existing pytest infrastructure covers setup; only scoring-specific test file is missing.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Score badge renders in dashboard and dimension breakdown panel opens on click | SCORE-07 | Frontend visual/interaction — cannot be automated without browser | 1. Sync a platform 2. Wait for scheduler run 3. Verify badge visible on creative card 4. Click badge, verify panel opens with all dimension keys |
| BrainSuite API spike — capture real scoring response shape | SCORE-07 | Requires live API credentials and a real video asset | Submit one video to BrainSuite scoring endpoint and capture the full JSON response to finalize `score_dimensions` schema |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
