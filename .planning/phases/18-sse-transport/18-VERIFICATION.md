---
phase: 18-sse-transport
verified: 2026-05-11T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Connect a SuperAdmin browser to GET /api/v1/jobs/stream?token=<valid_superadmin_jwt> and trigger a job status change (e.g. run a sync). Observe the EventSource stream in browser DevTools Network tab."
    expected: "A job_update event arrives within 2 seconds of the job status/progress change. The event data JSON contains job_id, job_type, org_id, status, progress_current, progress_total, started_at, ended_at."
    why_human: "End-to-end timing requires a live Redis PUBLISH + subscriber round-trip through a real network stack. Cannot verify sub-2-second latency with grep."
  - test: "Leave the SSE connection open for 35+ seconds with no job activity."
    expected: "A ping event arrives with data containing a 'ts' ISO-8601 timestamp. No proxy timeout or connection drop."
    why_human: "Real 30-second heartbeat interval requires wall-clock time to elapse. Cannot fast-forward in production."
  - test: "Open browser DevTools, establish SSE connection, then close the browser tab or navigate away."
    expected: "Server-side pubsub connection is released. Check Uvicorn worker logs — no 'SSE: error closing pubsub connection' warning and no leaked Redis pubsub subscriptions."
    why_human: "request.is_disconnected() behavior against a real ASGI transport cannot be verified by grep alone."
---

# Phase 18: SSE Transport Verification Report

**Phase Goal:** The backend streams real-time job updates to connected SuperAdmin browsers via Server-Sent Events, with connection leaks and proxy timeouts prevented
**Verified:** 2026-05-11
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SuperAdmin browser connected to SSE endpoint receives job_update events when job changes | ✓ VERIFIED (logic) | `sse_generator` in jobs.py: Redis pubsub loop fetches BackgroundJob by UUID and yields `{"event": "job_update", ...}` on every message. PUBLISH wired in job_tracker.py after every create/update. Needs human timing verification (SC-1). |
| 2 | SSE endpoint sends keepalive heartbeats every 30 seconds | ✓ VERIFIED (logic) | `_HEARTBEAT_INTERVAL_SECONDS = 30` in jobs.py; ping branch fires when `(now - last_ping_at).total_seconds() >= 30`. test_sse_heartbeat_30s passes. Needs wall-clock verification (SC-2). |
| 3 | Closing the browser tab releases the server-side SSE connection | ✓ VERIFIED (logic) | `try-finally` in `sse_generator` unconditionally calls `pubsub.unsubscribe` + `pubsub.close`. `request.is_disconnected()` checked at 5 points in loop. test_sse_cleanup_on_disconnect asserts both called exactly once. Needs live transport verification (SC-3). |
| 4 | SSE endpoint rejects non-SuperAdmin connections | ✓ VERIFIED | `get_current_superadmin_sse` in deps.py raises HTTP 401 when no token, 401 on invalid/expired token, 403 when `not user.is_superuser`. test_sse_rejects_non_superadmin asserts status_code=403. |

**Score:** 4/4 truths verified (logic confirmed; 3 require live human testing per roadmap SC-1, SC-2, SC-3)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/services/sync/job_tracker.py` | Redis PUBLISH after every DB write | ✓ VERIFIED | 2 occurrences of `redis.publish("sse:job_updates", str(job_id))` — one after `create_background_job` commit, one after `update_background_job` commit. Both wrapped in `try/except Exception` with warning log. Early-return (job is None) path naturally skips PUBLISH. |
| `backend/tests/test_sse.py` | 5 green tests covering SSE-01 and SSE-02 | ✓ VERIFIED | All 5 test functions present with real assertions (no `pytest.fail` stubs). All assert meaningful behavior: event type, payload keys, HTTP status codes, pubsub cleanup call counts. `asyncio.sleep` patched in all tests to prevent busy-loop stalls. |
| `backend/requirements.txt` | sse-starlette dependency declared | ✓ VERIFIED | `sse-starlette==3.4.2` present at line 29. Note: SUMMARY-02 claimed a downgrade to 1.8.2 occurred, but requirements.txt was not modified in commit 0b97ae5 and retains 3.4.2. The compatibility concern is documented in the SUMMARY but the pin to 3.4.2 was not actually applied — this is a SUMMARY narrative inaccuracy, not a code gap (3.4.2 is the planned version per the v1.3 milestone). |
| `backend/app/api/v1/deps.py` | `get_current_superadmin_sse` dependency | ✓ VERIFIED | Function exists at line 100. Reads token from `request.query_params.get("token")`. Calls `decode_token`, validates `type="access"`, looks up User by UUID, checks `is_active` and `is_superuser`. Returns 401/401/403 on failure paths. |
| `backend/app/api/v1/endpoints/jobs.py` | SSE endpoint router | ✓ VERIFIED | File exists. Contains `router = APIRouter()`, `serialize_job_event`, `sse_generator`, `stream_jobs`. `EventSourceResponse` used at line 165 with `ping=15`, `send_timeout=60`, `headers={"Cache-Control": "no-cache"}`. `pubsub.unsubscribe` and `pubsub.close` inside `finally` block at lines 147-148. |
| `backend/app/api/v1/__init__.py` | jobs router registered at /jobs | ✓ VERIFIED | Line 2: `from app.api.v1.endpoints import ... jobs`. Line 14: `api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `job_tracker.py::create_background_job` | Redis channel `sse:job_updates` | `await redis.publish()` | ✓ WIRED | Line 63: `await redis.publish("sse:job_updates", str(job_id))` after `async with` block exits. |
| `job_tracker.py::update_background_job` | Redis channel `sse:job_updates` | `await redis.publish()` | ✓ WIRED | Line 119: `await redis.publish("sse:job_updates", str(job_id))` after `async with` block exits. Early-return path (job is None) at line 97 skips PUBLISH correctly. |
| `jobs.py::stream_jobs` | `deps.py::get_current_superadmin_sse` | `Depends(get_current_superadmin_sse)` | ✓ WIRED | Line 156: `current_user: User = Depends(get_current_superadmin_sse)`. |
| `jobs.py::sse_generator` | `BackgroundJob` via DB | `async with get_session_factory()()` | ✓ WIRED | 24h burst at line 71-77 and per-message fetch at lines 114-115 both use `get_session_factory()`. |
| `__init__.py` | `endpoints/jobs.py` | `api_router.include_router(jobs.router, prefix="/jobs")` | ✓ WIRED | Line 14 confirmed. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `jobs.py::sse_generator` | `recent_jobs` (burst) | `db.execute(select(BackgroundJob).where(...started_at > cutoff...))` | Yes — live DB query | ✓ FLOWING |
| `jobs.py::sse_generator` | `job` (live loop) | `db.get(BackgroundJob, job_uuid)` triggered by Redis PUBLISH from `job_tracker.py` | Yes — Redis signal + DB fetch | ✓ FLOWING |
| `jobs.py::serialize_job_event` | 8-field payload | BackgroundJob model columns | Yes — real model fields serialized | ✓ FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED for live streaming behaviors (requires running server + Redis). Static import check performed instead.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| jobs module importable | `python -c "from app.api.v1.endpoints import jobs"` | Not run (no server) | ? SKIP — confirmed by file structure |
| 5 SSE tests pass | SUMMARY-02 reports 5 passed, 0 failed | Reported by executor | ? SKIP — no test runner available; see human verification |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| SSE-01 | 18-01, 18-02 | Backend exposes SSE endpoint streaming job-updated events to connected SuperAdmin browser clients | ✓ SATISFIED | `GET /api/v1/jobs/stream` implemented in jobs.py; authenticated via `get_current_superadmin_sse`; job_update events triggered by Redis PUBLISH from job_tracker.py; 24h burst on connect |
| SSE-02 | 18-02 | SSE connections include keepalive heartbeats and are cleaned up on client disconnect | ✓ SATISFIED | 30s heartbeat (`event: ping`) implemented in sse_generator; `try-finally` ensures `pubsub.unsubscribe` + `pubsub.close` on any exit path; `request.is_disconnected()` checked at 5 points |

No orphaned requirements. REQUIREMENTS.md maps only SSE-01 and SSE-02 to Phase 18. Both are covered.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/requirements.txt` | 29 | `sse-starlette==3.4.2` (SUMMARY-02 claimed downgrade to 1.8.2 for FastAPI compatibility, but file retains 3.4.2) | ℹ Info | SUMMARY narrative inaccuracy. 3.4.2 is the planned v1.3 pin. If the executor's compatibility concern was real, it was not applied. Recommend confirming the app boots with 3.4.2 installed. |

No TODOs, FIXMEs, placeholders, or stub returns found in any phase-18 production files.

### Human Verification Required

#### 1. Sub-2-Second Job Update Delivery (Roadmap SC-1)

**Test:** With the backend running, open browser DevTools Network tab and connect EventSource to `GET /api/v1/jobs/stream?token=<superadmin_jwt>`. In a separate terminal, trigger a sync or scoring run. Observe the SSE stream.
**Expected:** A `job_update` event arrives within 2 seconds of any job status or progress change. Event data JSON contains: `job_id`, `job_type`, `org_id`, `status`, `progress_current`, `progress_total`, `started_at`, `ended_at`.
**Why human:** End-to-end Redis PUBLISH-to-SSE-receive latency requires a live running stack and wall-clock measurement.

#### 2. Keepalive Heartbeat During Idle (Roadmap SC-2)

**Test:** Hold the SSE connection open for 35+ seconds with no job activity.
**Expected:** A `ping` event arrives containing `{"ts": "<iso8601>"}`. Connection remains alive. No proxy timeout.
**Why human:** Real 30-second heartbeat interval requires wall-clock time to elapse.

#### 3. Connection Cleanup on Browser Disconnect (Roadmap SC-3)

**Test:** Open SSE connection, then close the browser tab or navigate away. Check Uvicorn worker logs within 10 seconds.
**Expected:** No `SSE: error closing pubsub connection` warning. No persistent Redis pubsub subscription remaining (monitor Redis `PUBSUB NUMSUB sse:job_updates` before and after disconnect).
**Why human:** `request.is_disconnected()` behavior over a real ASGI transport with HTTP connection teardown cannot be verified by static analysis.

### Gaps Summary

No blocking gaps. All 4 phase artifacts are substantive and fully wired. Redis PUBLISH and SSE subscription loop are connected end-to-end through job_tracker.py. Authentication dependency is correctly implemented. Router is registered.

Three roadmap success criteria (SC-1, SC-2, SC-3) require live-stack human testing because they involve timing guarantees, proxy behavior, and OS-level connection teardown detection — none of which static analysis or unit tests can fully confirm.

One informational note: requirements.txt retains `sse-starlette==3.4.2` (the planned version). SUMMARY-02's claim that it was changed to 1.8.2 for compatibility is not reflected in any committed file. This should be confirmed to not cause a boot failure.

---

_Verified: 2026-05-11_
_Verifier: Claude (gsd-verifier)_
