---
phase: 18
slug: sse-transport
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-11
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (async with anyio/asyncio) |
| **Config file** | backend/tests/ (existing conftest.py) |
| **Quick run command** | `cd backend && python -m pytest tests/test_sse.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_sse.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 18-01-01 | 01 | 0 | SSE-01 | — | N/A | unit | `cd backend && python -m pytest tests/test_sse.py -x -q -k "stub"` | ❌ W0 | ⬜ pending |
| 18-01-02 | 01 | 1 | SSE-01 | — | PUBLISH fires after every job update | unit | `cd backend && python -m pytest tests/test_sse.py -x -q -k "publish"` | ❌ W0 | ⬜ pending |
| 18-02-01 | 02 | 1 | SSE-01 | — | SSE endpoint streams job_update events | integration | `cd backend && python -m pytest tests/test_sse.py -x -q -k "stream"` | ❌ W0 | ⬜ pending |
| 18-02-02 | 02 | 1 | SSE-01 | — | Non-SuperAdmin JWT rejected with 403 | unit | `cd backend && python -m pytest tests/test_sse.py -x -q -k "auth"` | ❌ W0 | ⬜ pending |
| 18-02-03 | 02 | 1 | SSE-02 | — | ping heartbeat emitted every 30s | unit | `cd backend && python -m pytest tests/test_sse.py -x -q -k "heartbeat"` | ❌ W0 | ⬜ pending |
| 18-02-04 | 02 | 1 | SSE-02 | — | pubsub connection closed on disconnect | unit | `cd backend && python -m pytest tests/test_sse.py -x -q -k "disconnect"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_sse.py` — stubs for SSE-01, SSE-02 (connection, auth, heartbeat, disconnect cleanup)
- [ ] Existing `backend/tests/conftest.py` — shared fixtures (check async client support)

*All Wave 0 stubs must exist before Wave 1 implementation tasks run.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Browser EventSource connects and receives live job_update within 2s of job change | SSE-01 | Requires running backend + browser DevTools | 1. Start backend; 2. Open DevTools Network tab; 3. Trigger a sync; 4. Observe SSE stream for job_update within 2s |
| Closing browser tab releases server connection (no worker slot leak) | SSE-02 | Requires process-level monitoring | 1. Connect browser to /api/v1/jobs/stream; 2. Close tab; 3. Check Uvicorn logs for connection cleanup |
| 30-minute token expiry forces EventSource reconnect | SSE-01 | Requires waiting or time mocking | Verify 401 returned when expired token is passed as query param |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
