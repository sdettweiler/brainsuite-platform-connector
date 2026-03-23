---
phase: 02-security-hardening
plan: 05
subsystem: testing
tags: [ast, exception-handling, error-handling, static-analysis, sync, oauth, harmonizer]

requires:
  - phase: 02-01
    provides: Redis OAuth session infrastructure, security layer

provides:
  - QUAL-01 compliance: zero broad except Exception blocks in backend/app/ (outside allowed list)
  - AST-based static analysis test that enforces exception specificity at CI time
  - All ~75 broad exception catches narrowed to specific types with exc_info=True logging

affects:
  - phase-03
  - phase-04

tech-stack:
  added: []
  patterns:
    - "Specific exception typing: httpx.RequestError/HTTPStatusError for HTTP, SQLAlchemyError for DB, (ValueError, InvalidOperation) for parsing"
    - "exc_info=True on all ERROR-level exception catches to include full tracebacks"
    - "AST-based static analysis test scans all Python files at test time to prevent regression"

key-files:
  created:
    - backend/tests/test_exception_audit.py
  modified:
    - backend/app/services/sync/dv360_sync.py
    - backend/app/services/sync/meta_sync.py
    - backend/app/services/sync/google_ads_sync.py
    - backend/app/services/sync/tiktok_sync.py
    - backend/app/services/sync/scheduler.py
    - backend/app/services/sync/harmonizer.py
    - backend/app/services/currency.py
    - backend/app/services/connection_purge.py
    - backend/app/services/platform/google_ads_oauth.py
    - backend/app/api/v1/endpoints/platforms.py
    - backend/app/api/v1/endpoints/users.py
    - backend/app/core/config.py

key-decisions:
  - "Harmonizer per-record catches use (SQLAlchemyError, ValueError, ArithmeticError) — covers DB failures, data parsing errors, and arithmetic in metric calculations"
  - "Asset download helpers (yt-dlp, thumbnail fetchers) use (httpx.RequestError, HTTPStatusError, OSError) or (OSError, RuntimeError) — yt-dlp errors inherit from Exception but manifest as RuntimeError/OSError in subprocess context"
  - "scheduler.py top-level job wrappers (run_daily_sync, run_full_resync, run_initial_sync, run_historical_sync, _run_dv360_asset_downloads) remain broad — APScheduler job isolation pattern"
  - "AST test uses function-name allowlist for scheduler.py to distinguish intentional broad catches from violations"
  - "platforms.py OAuth catches raise 502 (Platform OAuth error) not 400 — correctly signals upstream platform failure vs bad request"

patterns-established:
  - "Exception specificity: always import and catch the concrete exception type the called code raises"
  - "exc_info=True: all ERROR-level except clauses include exc_info=True for full traceback in logs"
  - "Non-fatal download helpers: (httpx.RequestError, HTTPStatusError, OSError) is the canonical catch tuple for asset download methods"
  - "AST regression guard: test_exception_audit.py prevents future reintroduction of broad catches"

requirements-completed:
  - QUAL-01

duration: 10min
completed: 2026-03-23
---

# Phase 02 Plan 05: Exception Audit Summary

**All ~75 broad except Exception blocks replaced with specific exception types and exc_info=True logging, enforced by an AST-based CI test**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-23T08:33:55Z
- **Completed:** 2026-03-23T08:44:00Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- Replaced all broad `except Exception` catches in 9 service files with specific exception types (httpx, SQLAlchemy, ValueError, OSError, etc.)
- Fixed endpoints `platforms.py` and `users.py` to use typed exceptions with proper HTTP status codes (502 for upstream OAuth failures)
- Implemented `test_no_broad_except_exception` using `ast.parse` — test scans all files at CI time and fails if any new broad catch is introduced

## Task Commits

1. **Task 1: Replace broad catches in sync services** - `2cf6ef4` (fix)
2. **Task 2 RED: AST audit test** - `277832b` (test)
3. **Task 2 GREEN: Endpoint fixes + passing test** - `40edd43` (feat)

## Files Created/Modified

- `backend/tests/test_exception_audit.py` - AST-based QUAL-01 audit test, scans backend/app/ for broad catches with function-level allowlist
- `backend/app/services/sync/harmonizer.py` - Per-record loop catches narrowed to (SQLAlchemyError, ValueError, ArithmeticError) with exc_info=True
- `backend/app/services/sync/dv360_sync.py` - 21 catches narrowed: conversion report, Bid Manager poll/token refresh, asset download helpers, safe parse helpers
- `backend/app/services/sync/meta_sync.py` - 10 catches narrowed: insight pagination, creative/dimension batch fetchers, asset download
- `backend/app/services/sync/google_ads_sync.py` - Download helpers narrowed to (httpx, OSError)
- `backend/app/services/sync/tiktok_sync.py` - _safe_decimal -> (ValueError, InvalidOperation), ad info batch -> httpx errors
- `backend/app/services/sync/scheduler.py` - schedule_connection timezone catch narrowed to pytz.exceptions.UnknownTimeZoneError
- `backend/app/services/currency.py` - HTTP fetchers narrowed to httpx errors; DB cache narrowed to (IntegrityError, SQLAlchemyError)
- `backend/app/services/connection_purge.py` - All DB steps narrowed to SQLAlchemyError; object storage to OSError
- `backend/app/services/platform/google_ads_oauth.py` - Per-customer detail fetch narrowed to httpx errors
- `backend/app/api/v1/endpoints/platforms.py` - OAuth callback catches narrowed to httpx errors; added import httpx and logger; 502 for upstream failures
- `backend/app/api/v1/endpoints/users.py` - Re-harmonize catch narrowed to (SQLAlchemyError, ValueError, ArithmeticError) with exc_info=True
- `backend/app/core/config.py` - Fernet key validation narrowed to (ValueError, TypeError)

## Decisions Made

- Used function-name allowlist in AST test for scheduler.py — allows top-level APScheduler job wrappers (`run_daily_sync`, `run_full_resync`, `run_initial_sync`, `run_historical_sync`, `_run_dv360_asset_downloads`) to keep broad catches for job isolation
- Asset download helpers use `(OSError, RuntimeError)` for yt-dlp blocks since yt-dlp errors surface as these types through `run_in_executor`; HTTP download blocks use `(httpx.RequestError, httpx.HTTPStatusError, OSError)`
- OAuth endpoint catches changed from 400 to 502 status code — upstream platform auth failures are gateway errors, not bad requests

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] scheduler.py schedule_connection timezone catch was not in an allowed function**
- **Found during:** Task 2 (AST audit test run)
- **Issue:** `schedule_connection` used `except Exception` for pytz.timezone() call but was not in the allowed function list. AST test flagged it as a violation.
- **Fix:** Narrowed to `except pytz.exceptions.UnknownTimeZoneError`
- **Files modified:** backend/app/services/sync/scheduler.py
- **Verification:** Test passes after fix
- **Committed in:** 40edd43 (Task 2 commit)

**2. [Rule 2 - Missing Critical] config.py Fernet validation catch needed narrowing**
- **Found during:** Task 1 verification (AST script)
- **Issue:** `validate_fernet_key` used `except Exception` for cryptography.fernet.Fernet() call
- **Fix:** Narrowed to `except (ValueError, TypeError)` — the actual exceptions Fernet raises for invalid keys
- **Files modified:** backend/app/core/config.py
- **Verification:** AST scan passes
- **Committed in:** 2cf6ef4 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing narrowing)
**Impact on plan:** Both in-scope files not listed in the plan but required narrowing. No scope creep.

## Issues Encountered

None — plan executed with expected scope plus 2 auto-fixes for files not in original list.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- QUAL-01 fully addressed: all broad exception catches are specific and logged with exc_info=True
- AST audit test provides regression protection — any future `except Exception` outside the allowed list will fail CI
- Ready for remaining Phase 02 security plans
