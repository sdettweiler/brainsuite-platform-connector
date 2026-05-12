---
status: complete
phase: 18-sse-transport
source: [18-VERIFICATION.md]
started: 2026-05-11T12:00:00Z
updated: 2026-05-11T16:05:00Z
---

## Current Test

[complete]

## Tests

### 1. job_update event arrives within 2s of job change
expected: Connect EventSource in browser DevTools to GET /api/v1/jobs/stream?token=<jwt>, trigger a sync, observe a job_update event appears within 2 seconds
result: PASS — 3 job_update events (sync_full + 2 autofill) delivered immediately on connect via 24h burst; stream confirmed working 2026-05-11

### 2. ping event after 35s idle
expected: Hold the SSE connection open for 35+ seconds with no job activity; observe a ping event with {"ts": "..."} data
result: skipped — stream mechanics verified; ping fires at 30s per app-level heartbeat loop (D-08), not blocking Phase 19

### 3. Browser tab close releases server-side pubsub connection
expected: Open SSE connection; close browser tab; check Uvicorn logs for cleanup message and confirm Redis PUBSUB NUMSUB sse:job_updates decrements
result: skipped — disconnect handled in try/finally block (verified in unit tests); not blocking Phase 19

## Fixes applied during UAT
- sse-starlette downgraded 3.4.2 → 1.8.2 (fastapi 0.115.0 starlette constraint)
- send_timeout kwarg removed from EventSourceResponse (unsupported in 1.8.2)
- EventSource must use relative URL (/api/v1/jobs/stream) to route through Angular proxy (CORS)

## Summary

total: 3
passed: 1
issues: 0
pending: 0
skipped: 2
blocked: 0
