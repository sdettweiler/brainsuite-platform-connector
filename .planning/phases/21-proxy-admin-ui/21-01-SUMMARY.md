---
phase: 21-proxy-admin-ui
plan: 01
subsystem: api
tags: [fastapi, pydantic, fernet, httpx, encryption, proxy, superadmin]

# Dependency graph
requires:
  - phase: 20-proxy-download-infrastructure
    provides: SystemConfig.proxy_url_encrypted + proxy_enabled columns (already migrated)

provides:
  - GET /api/v1/super-admin/proxy-config endpoint — returns proxy_enabled flag + masked URL
  - PUT /api/v1/super-admin/proxy-config endpoint — partial update for toggle and/or encrypted URL
  - POST /api/v1/super-admin/proxy-config/test endpoint — httpx reachability check via proxy, returns {success, latency_ms, error}
  - _mask_proxy_url helper — replaces user:pass@ with ••••••@ for safe frontend display
  - ProxyConfigResponse, UpdateProxyConfigRequest, ProxyTestResponse Pydantic models
  - 8-test pytest suite covering all PROXY-05 behaviors

affects:
  - 21-02 (frontend plan) — consumes all 3 endpoints with these exact response shapes
  - Any future proxy health monitoring — test endpoint is the reference pattern

# Tech tracking
tech-stack:
  added: []  # httpx and cryptography were already in requirements.txt
  patterns:
    - "Fernet encrypt-on-write / decrypt-for-masking pattern (copy of youtube-cookies endpoints)"
    - "Singleton SystemConfig read with scalar_one_or_none + config.proxy_url_encrypted access"
    - "_mask_proxy_url helper: rsplit('@', 1) to split credentials from host:port"

key-files:
  created:
    - backend/tests/test_super_admin_proxy.py
  modified:
    - backend/app/api/v1/endpoints/super_admin.py

key-decisions:
  - "Masking uses rsplit('@', 1) to handle any number of '@' in username/password — rightmost @ is auth boundary"
  - "Test endpoint returns success=True only for HTTP 200; any other 2xx falls through as error (strict match per D-08)"
  - "PUT endpoint returns full ProxyConfigResponse (not just changed field) to prevent frontend state sync issues (Pitfall 7)"
  - "Imports httpx at module level (not inline) matching project convention for async HTTP client"

patterns-established:
  - "Pattern: All 3 proxy endpoints inherit get_current_superadmin dependency — 403 enforced at function level, not route level"
  - "Pattern: Credentials never appear in logger.info() calls — use constant strings for security audit"
  - "Pattern: On decrypt failure in masking path return '[URL configured]' not exception detail (T-21-06)"

requirements-completed:
  - PROXY-05

# Metrics
duration: 3min
completed: 2026-05-15
---

# Phase 21 Plan 01: Proxy Config Backend Endpoints Summary

**Three SuperAdmin API endpoints for encrypted residential proxy configuration with Fernet URL masking, 5s-timeout reachability test, and full PROXY-05 pytest coverage**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-15T14:08:41Z
- **Completed:** 2026-05-15T14:11:34Z
- **Tasks:** 3 (2 TDD + 1 verification)
- **Files modified:** 2

## Accomplishments

- GET/PUT `/proxy-config` endpoints reading and writing `SystemConfig.proxy_url_encrypted` and `proxy_enabled`, returning only the masked URL (never plaintext)
- POST `/proxy-config/test` endpoint that httpx-proxies a GET to `https://www.youtube.com/` with a 5-second hard timeout and returns `{success, latency_ms, error}`
- `_mask_proxy_url` helper that parses `http://user:pass@host:port` into `http://••••••@host:port` via rightmost-`@` split
- 8-test pytest suite (all pass): covers both proxy states on GET, partial updates on PUT, httpx mock on test endpoint, 403 gate for non-SuperAdmin, and 4 masking edge cases
- Full regression: 25/25 tests pass (new proxy tests + existing super_admin_endpoints + deps + system_config)
- Security grep confirms no logger call interpolates decrypted proxy URL (T-21-02 verified at source)

## Task Commits

1. **Task 1: Write failing test suite for proxy-config endpoints** - `56dcd9e` (test)
2. **Task 2: Implement 3 proxy endpoints + masking helper** - `7186579` (feat)

## Files Created/Modified

- `/Users/sebastian.dettweiler/Claude Code/platform-connector/brainsuite-platform-connector/backend/tests/test_super_admin_proxy.py` — 8-test TDD suite; RED→GREEN cycle confirmed
- `/Users/sebastian.dettweiler/Claude Code/platform-connector/brainsuite-platform-connector/backend/app/api/v1/endpoints/super_admin.py` — Added `import httpx`, `import time`; 3 Pydantic models; `_mask_proxy_url` helper; 3 async endpoint handlers (GET/PUT/POST)

## Decisions Made

- Masking implementation uses `rsplit("@", 1)` (not `split`) so passwords containing `@` are handled correctly — the rightmost `@` is always the auth/host boundary
- PUT returns full `ProxyConfigResponse` (not a minimal ack) to keep frontend state in sync on every write — avoids Pitfall 7 documented in RESEARCH.md
- `import httpx` added at module level (top of file) consistent with other top-level imports in the file, not inside the test endpoint function
- `httpx.ConnectError` caught specifically before the broad `except Exception` to produce a user-friendly fixed string per T-21-06

## Deviations from Plan

None — plan executed exactly as written. All 8 must_have truths satisfied by the implementation and test suite.

## Issues Encountered

None — `docker-compose exec backend python -m pytest` was used instead of bare `pytest` since the project runs in Docker. This is the standard pattern for this project (not a deviation).

## Known Stubs

None — the three endpoints are fully wired to `SystemConfig` via the existing singleton pattern. No placeholder data.

## Threat Flags

No new threat surface introduced. The three endpoints are a subset of the SuperAdmin router already registered at `/api/v1/super-admin`. No new network endpoints, auth paths, or schema changes beyond what the threat model in the plan already covers (T-21-01 through T-21-07).

## TDD Gate Compliance

- RED gate commit: `56dcd9e` — `test(21-01): add failing test suite for proxy-config endpoints` (8 tests, all failing with 404)
- GREEN gate commit: `7186579` — `feat(21-01): implement proxy-config endpoints and _mask_proxy_url helper` (8 tests, all passing)

## Next Phase Readiness

- Plan 21-02 (Angular frontend) can now consume all 3 endpoints — response shapes are exactly as specified in the plan's `<interfaces>` block
- No blockers — all SuperAdmin proxy routes are live in the existing router registration

---
*Phase: 21-proxy-admin-ui*
*Completed: 2026-05-15*
