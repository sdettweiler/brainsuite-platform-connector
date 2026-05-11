---
status: partial
phase: 18-sse-transport
source: [18-VERIFICATION.md]
started: 2026-05-11T12:00:00Z
updated: 2026-05-11T12:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. job_update event arrives within 2s of job change
expected: Connect EventSource in browser DevTools to GET /api/v1/jobs/stream?token=<jwt>, trigger a sync, observe a job_update event appears within 2 seconds
result: [pending]

### 2. ping event after 35s idle
expected: Hold the SSE connection open for 35+ seconds with no job activity; observe a ping event with {"ts": "..."} data
result: [pending]

### 3. Browser tab close releases server-side pubsub connection
expected: Open SSE connection; close browser tab; check Uvicorn logs for cleanup message and confirm Redis PUBSUB NUMSUB sse:job_updates decrements
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
