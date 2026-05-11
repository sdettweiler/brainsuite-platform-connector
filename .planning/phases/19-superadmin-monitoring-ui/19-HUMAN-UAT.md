---
status: partial
phase: 19-superadmin-monitoring-ui
source: [19-VERIFICATION.md]
started: 2026-05-11T21:38:04Z
updated: 2026-05-11T21:38:04Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. SSE badge goes Live and jobs populate tabs
expected: Navigate to /configuration/jobs as SuperAdmin — SSE badge shows "Live" (green dot), tabs show job rows from the last 24h populated in real time.
result: [pending]

### 2. Detail panel slide animation + Copy job ID works
expected: Click a job row — panel slides in from the right with translateX animation. "Copy" button next to job_id copies UUID to clipboard. Pressing Escape closes the panel.
result: [pending]

### 3. Clear jobs fires DELETE + snackbar + reconnect
expected: Click "Clear completed" — DELETE fires for all types in the active tab, snackbar confirms "N completed jobs cleared", SSE reconnects and tab refreshes.
result: [pending]

### 4. Error traceback visible on FAILED jobs
expected: Click a FAILED job row — detail panel shows scrollable error traceback (truncated at 10KB) with "Copy traceback" button.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
