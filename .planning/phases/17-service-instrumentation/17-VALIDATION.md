---
phase: 17
slug: service-instrumentation
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-08
audited: 2026-05-13
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (async via pytest-asyncio) |
| **Config file** | `backend/pytest.ini` or `backend/pyproject.toml` |
| **Quick run command** | `pytest tests/services/test_instrumentation.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/services/test_instrumentation.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 0 | D-16 | — | N/A | unit | `pytest tests/services/test_instrumentation.py::test_create_background_job_returns_uuid -x` | ✅ | ✅ green |
| 17-01-02 | 01 | 0 | D-16 | — | ended_at auto-set on COMPLETE | unit | `pytest tests/services/test_instrumentation.py::test_update_background_job_sets_status -x` | ✅ | ✅ green |
| 17-02-01 | 02 | 1 | INSTR-01 | — | N/A | unit | `pytest tests/services/test_instrumentation.py::test_sync_job_creates_background_job -x` | ✅ | ✅ green |
| 17-03-01 | 03 | 1 | INSTR-02 | — | N/A | unit | `pytest tests/services/test_instrumentation.py::test_download_progress_increments -x` | ✅ | ✅ green |
| 17-04-01 | 04 | 1 | INSTR-03 | — | N/A | unit | `pytest tests/services/test_instrumentation.py::test_autofill_output_schema -x` | ✅ | ✅ green (fixed 2026-05-13: add get_session_factory mock for asset_url prefetch guard) |
| 17-05-01 | 05 | 1 | INSTR-04, INSTR-05 | — | N/A | unit | `pytest tests/services/test_instrumentation.py::test_scoring_output_schema -x` | ✅ | ✅ green |
| 17-06-01 | 06 | 3 | D-13 | — | error traceback ≤ 10000 chars | unit | `pytest tests/services/test_instrumentation.py::test_error_traceback_truncated_at_10000_chars -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `backend/tests/services/test_instrumentation.py` — 7 tests covering D-16, INSTR-01 through INSTR-05, D-13 (confirmed 2026-05-13)
- [x] `_make_mock_session_factory(mock_db)` shared helper — prevents real DB hits in unit tests
- [x] `_make_config_guard_db()` helper — scoring config guard mock for `_process_asset`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PENDING → RUNNING → COMPLETE transition in real DB | INSTR-01 | Requires running sync against live platform | Trigger sync, query `background_jobs` table, verify status transitions |
| progress_current increments live during download | INSTR-02 | Requires download in flight | Start download batch, poll DB every 2 seconds, verify count rises |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s (7 tests run in 1.65s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** 2026-05-13 (gsd-validate-phase audit)

## Validation Audit 2026-05-13

| Metric | Count |
|--------|-------|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |
| Tests run | 7 (all green, 1.65s) |
| Fix applied | `test_autofill_output_schema`: added `get_session_factory` mock for `ai_autofill` module — commit `00f5c99` added an `asset_url` prefetch guard that hit the real DB; mock asset with non-empty `asset_url` makes the guard pass |
| Result | CONFIRMED nyquist_compliant |
