---
phase: 18
slug: sse-transport
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-11
audited: 2026-05-13
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (async via pytest-asyncio) |
| **Config file** | `backend/tests/` (existing conftest.py) |
| **Quick run command** | `pytest tests/test_sse.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_sse.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 18-01-01 | 01 | 0 | SSE-01 | — | N/A | unit | `pytest tests/test_sse.py::test_sse_rejects_non_superadmin -x` | ✅ | ✅ green |
| 18-01-02 | 01 | 1 | SSE-01 | — | PUBLISH fires after every job update | unit | `pytest tests/test_sse.py::test_sse_yields_job_update -x` | ✅ | ✅ green (fixed 2026-05-13: db.get side_effect to return None for org lookup) |
| 18-02-01 | 02 | 1 | SSE-01 | — | SSE endpoint streams job_update events | unit | `pytest tests/test_sse.py::test_sse_burst_24h_on_connect -x` | ✅ | ✅ green (fixed 2026-05-13: burst_result.all not .scalars().all()) |
| 18-02-02 | 02 | 1 | SSE-01 | — | Non-SuperAdmin JWT rejected with 403 | unit | `pytest tests/test_sse.py::test_sse_rejects_non_superadmin -x` | ✅ | ✅ green |
| 18-02-03 | 02 | 1 | SSE-02 | — | ping heartbeat emitted every 30s | unit | `pytest tests/test_sse.py::test_sse_heartbeat_30s -x` | ✅ | ✅ green |
| 18-02-04 | 02 | 1 | SSE-02 | — | pubsub connection closed on disconnect | unit | `pytest tests/test_sse.py::test_sse_cleanup_on_disconnect -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `backend/tests/test_sse.py` — 5 tests: job_update yield, non-superadmin 403, burst, heartbeat, disconnect cleanup (confirmed 2026-05-13)
- [x] `_make_job()` / `_make_request()` / `_collect_n_events()` helpers for mock-driven async generator tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Browser EventSource connects and receives live job_update within 2s of job change | SSE-01 | Requires running backend + browser DevTools | 1. Start backend; 2. Open DevTools Network tab; 3. Trigger a sync; 4. Observe SSE stream for job_update within 2s |
| Closing browser tab releases server connection (no worker slot leak) | SSE-02 | Requires process-level monitoring | 1. Connect browser to /api/v1/jobs/stream; 2. Close tab; 3. Check Uvicorn logs for connection cleanup |
| 30-minute token expiry forces EventSource reconnect | SSE-01 | Requires waiting or time mocking | Verify 401 returned when expired token is passed as query param |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s (5 tests in 0.98s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** 2026-05-13 (gsd-validate-phase audit)

## Validation Audit 2026-05-13

| Metric | Count |
|--------|-------|
| Gaps found | 2 |
| Resolved | 2 |
| Escalated | 0 |
| Tests run | 5 (all green, 0.98s) |
| Fix 1 | `test_sse_yields_job_update`: `mock_db.get = AsyncMock(side_effect=[job, None])` — `return_value=job` returned the job mock for the Org lookup too, making `org.name` a MagicMock that failed `json.dumps` |
| Fix 2 | `test_sse_burst_24h_on_connect`: `burst_result.all.return_value = [(job_a, None), (job_b, None)]` — mock used `.scalars().all()` but production code calls `.all()` directly on the CursorResult |
| Result | CONFIRMED nyquist_compliant |
