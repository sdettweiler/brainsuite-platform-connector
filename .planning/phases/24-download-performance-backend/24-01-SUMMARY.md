---
phase: 24-download-performance-backend
plan: 01
subsystem: api
tags: [asyncio, sqlalchemy, fernet, proxy, cache, performance]

# Dependency graph
requires: []
provides:
  - "async get_proxy_config() -> Tuple[bool, Optional[str]] with 60s in-memory TTL cache"
  - "reset_cache() test helper to force cache miss"
  - "7 pytest-asyncio unit tests: cache hit, miss, TTL expiry, DB error fallback, concurrent lock"
affects:
  - "24-02 (dv360_sync.py proxy-loading block replaced with get_proxy_config())"
  - "24-03 (google_ads_sync.py proxy-loading block replaced with get_proxy_config())"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio.Lock wraps both the TTL read-check and _cache dict write in a single async with block"
    - "module-level _cache dict with expires_at: 0.0 initial value forces first call to DB"
    - "try/except Exception around get_session_factory()() call with safe (False, None) defaults"

key-files:
  created:
    - backend/app/services/sync/proxy_cache.py
    - backend/tests/test_proxy_cache.py
  modified: []

key-decisions:
  - "reset_cache() sets expires_at=0.0 so tests can force cache miss without sleeping (not sleepable in Docker test environment)"
  - "Lock wraps the entire TTL check + DB load atomically — concurrent tasks that both see a miss will block on the lock; first acquirer loads DB and writes cache; second acquirer finds cache warm on lock release"
  - "fake_monotonic() in test_cache_expires_after_ttl supplies sequential values [1000, 1000, 2000, 2000] simulating >TTL jump between calls"

patterns-established:
  - "Proxy config callers: from app.services.sync.proxy_cache import get_proxy_config — one import replaces inline DB read block"

requirements-completed:
  - PERF-04

# Metrics
duration: 4min
completed: 2026-05-18
---

# Phase 24 Plan 01: Proxy Config Cache Summary

**Shared in-memory proxy config cache with 60s TTL and asyncio.Lock, eliminating per-download SystemConfig DB query + Fernet decryption for Plans 02 and 03**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-18T17:14:02Z
- **Completed:** 2026-05-18T17:18:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `backend/app/services/sync/proxy_cache.py` with `get_proxy_config()` returning `(proxy_enabled, proxy_url)` tuple from an in-memory cache with 60s TTL
- asyncio.Lock serializes concurrent cache reads and writes (T-24-02 mitigation)
- DB failure safe-fallback to `(False, None)` without raising (T-24-03 mitigation)
- 7 pytest-asyncio unit tests all passing in Docker (Python 3.11, pytest 9.0.3)

## Task Commits

Each task was committed atomically:

1. **Tasks 1 + 2: proxy_cache module + unit tests** - `6288c01` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/app/services/sync/proxy_cache.py` — module with `_cache` dict, `_cache_lock`, `CACHE_TTL_SECONDS = 60`, `async get_proxy_config()`, `reset_cache()`
- `backend/tests/test_proxy_cache.py` — 7 pytest-asyncio tests covering all behaviors

## Decisions Made

- `reset_cache()` is exposed as a test helper (sets `expires_at=0.0`) rather than monkeypatching; this is the pattern established in existing code (test helpers in module, not just fixtures)
- `asyncio.Lock` wraps both the TTL check and cache write atomically; this means a second concurrent miss waits for the first to finish DB load and finds the cache warm — exactly one DB call for concurrent misses
- `fake_monotonic()` provides values `[1000, 1000, 2000, 2000]` where each get_proxy_config() call consumes exactly 2 values (TTL check + TTL write); the second pair returns 2000 which exceeds `expires_at = 1000 + 60 = 1060`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TTL expiry test fake_monotonic() logic**

- **Found during:** Task 2 (unit tests)
- **Issue:** Initial `fake_monotonic()` returned `[1000, 1059, 1061, 1062]` — second call's TTL write set `expires_at = 1000 + 60 = 1060`, then second check `1061 < 1060` was False... wait, actually `1061 < 1060` is False so it WOULD miss. Re-tracing: the write uses call[1]=1059, so `expires_at = 1059 + 60 = 1119`. Then second check uses call[2]=1061: `1061 < 1119` is True — cache hit, not miss. Test failed with `call_count == 1`.
- **Fix:** Replaced sequential counter-based logic with explicit sequential values `[1000, 1000, 2000, 2000]` — each pair (check, write) clearly places the second call past any possible TTL
- **Files modified:** `backend/tests/test_proxy_cache.py`
- **Verification:** `test_cache_expires_after_ttl` passes
- **Committed in:** `6288c01` (same task commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test logic)
**Impact on plan:** Test-logic fix only; no change to production code. All 7 tests pass.

## Issues Encountered

None beyond the TTL test logic issue documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plans 02 and 03 can immediately import:
```python
from app.services.sync.proxy_cache import get_proxy_config, reset_cache
```

`get_proxy_config()` returns `(proxy_enabled: bool, proxy_url: str | None)` where `proxy_url` is the decrypted base URL. Callers append the sticky-session suffix per-call.

## Self-Check: PASSED

- FOUND: backend/app/services/sync/proxy_cache.py
- FOUND: backend/tests/test_proxy_cache.py
- FOUND: commit 6288c01

---
*Phase: 24-download-performance-backend*
*Completed: 2026-05-18*
