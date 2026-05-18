---
phase: 25-configurable-concurrency
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, asyncio, semaphore, cache, ttl, postgresql]

# Dependency graph
requires:
  - phase: 24-download-performance-backend
    provides: proxy_cache.py module-level TTL cache pattern, _cache_lock asyncio.Lock, CACHE_TTL_SECONDS constant
provides:
  - SystemConfig.max_concurrent_downloads column (Integer, NOT NULL, default=3, server_default='3')
  - Alembic migration a1b2c3d5e7f9 chaining onto a9b0c1d2e3f4 (Phase 23 duration index head)
  - get_concurrency_semaphore() async function in proxy_cache.py — TTL-cached asyncio.Semaphore accessor
  - reset_concurrency_cache() test helper
  - 8 unit tests covering default-3, DB value, cache hit/miss, TTL expiry, capacity change, DB error, lock serialization
affects:
  - 25-02 (download call sites in dv360_sync.py + google_ads_sync.py wrap _do_download with semaphore; super_admin.py GET/PUT /download-concurrency endpoint reads/writes the column)
  - 25-03 (Angular admin component reads max_concurrent_downloads via the API endpoint that Plan 25-02 exposes)
  - 26-tech-debt-closure (DEBT-01 Alembic 4-head merge must absorb this migration into the linear chain)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level async cache with capacity-change detection: _concurrency_cache dict tracks both the Semaphore object and the integer capacity (max_concurrent) so a new Semaphore is created only when the DB value changes — preserving the in-flight-finishes-on-old-semaphore property (D-03)"
    - "Single shared asyncio.Lock for multiple caches: _cache_lock serializes both proxy and concurrency cache mutations — no second lock added"

key-files:
  created:
    - backend/alembic/versions/a1b2c3d5e7f9_phase25_max_concurrent_downloads.py
  modified:
    - backend/app/models/system_config.py
    - backend/app/services/sync/proxy_cache.py
    - backend/tests/test_proxy_cache.py

key-decisions:
  - "Single _cache_lock reused for both proxy and concurrency caches (D-03) — one asyncio.Lock keeps the module concurrency story simple; no second lock introduced"
  - "_concurrency_cache tracks max_concurrent integer alongside the Semaphore object — enables capacity-change detection without inspecting asyncio.Semaphore._value internals"
  - "Migration chains onto a9b0c1d2e3f4 (Phase 23 duration index) per plan spec — Phase 26 DEBT-01 will merge all v1.5 heads into the linear chain"

patterns-established:
  - "Capacity-change detection pattern: cache dict stores both the object (semaphore) and the scalar that determines its shape (max_concurrent); rebuild only when scalar changes"
  - "TDD cycle enforced: 8 tests written and verified green before committing implementation (15 total tests passing)"

requirements-completed:
  - PERF-02

# Metrics
duration: 15min
completed: 2026-05-18
---

# Phase 25 Plan 01: Configurable Concurrency — DB + Semaphore Cache Summary

**SystemConfig.max_concurrent_downloads column + TTL-cached asyncio.Semaphore accessor in proxy_cache.py, backed by 8 new unit tests covering default-3, TTL, capacity-change, and DB-error fallback**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-18T20:46:00Z
- **Completed:** 2026-05-18T20:51:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `max_concurrent_downloads` (Integer, NOT NULL, default 3, server_default '3') to SystemConfig model with matching Alembic migration chaining onto the Phase 23 head
- Extended `proxy_cache.py` with `get_concurrency_semaphore()` — 60s TTL-cached `asyncio.Semaphore` that reuses the existing `_cache_lock`, creates a new Semaphore instance only on capacity change, and falls back to `Semaphore(3)` on DB error
- Added 8 unit tests; full suite passes with 15 tests (7 existing proxy + 8 new concurrency)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add max_concurrent_downloads column to SystemConfig model and create Alembic migration** - `b1bd260` (feat)
2. **Task 2: Extend proxy_cache.py with get_concurrency_semaphore() + reset_concurrency_cache()** - `b716ef9` (feat)
3. **Task 3: Unit tests for get_concurrency_semaphore (default, TTL, capacity-change, DB error, lock serialization)** - `6ffd685` (test)

_Note: Task 3 is TDD — tests written alongside GREEN implementation in Task 2; all 15 pass together_

## Files Created/Modified

- `backend/app/models/system_config.py` - Added `max_concurrent_downloads: Mapped[int]` column positioned after `proxy_enabled`
- `backend/alembic/versions/a1b2c3d5e7f9_phase25_max_concurrent_downloads.py` - Alembic migration: upgrade adds column with server_default='3', downgrade drops it; chains onto a9b0c1d2e3f4
- `backend/app/services/sync/proxy_cache.py` - Added `_concurrency_cache` dict, `get_concurrency_semaphore()`, `reset_concurrency_cache()` after existing `reset_cache()`
- `backend/tests/test_proxy_cache.py` - Added 8 concurrency semaphore tests + helper functions `_make_system_config_concurrency` and `_make_session_factory_mock_for_concurrency`

## Decisions Made

- Reused `_cache_lock` (the existing `asyncio.Lock` from Phase 24) for the concurrency cache — one lock for both proxy and semaphore caches keeps the module's concurrency model simple (D-03)
- `_concurrency_cache` dict tracks `max_concurrent` as an integer alongside the `semaphore` object — this enables capacity-change detection without inspecting `asyncio.Semaphore._value` internals, which is an implementation detail
- Migration revision `a1b2c3d5e7f9` chains onto `a9b0c1d2e3f4` per plan spec; Phase 26 DEBT-01 will merge all v1.5 heads into the linear chain

## Deviations from Plan

None — plan executed exactly as written. The PATTERNS.md draft for `_concurrency_cache` omitted the `max_concurrent` key that the Task 2 spec explicitly requires; the Task 2 spec was followed (all three keys: semaphore, max_concurrent, expires_at).

## Issues Encountered

- Container test run: The Docker container mounts the main repo (not the worktree), so tests were run by temporarily copying worktree files into the container, verifying 15 passed, then restoring the container to main-branch state. This is standard worktree execution behavior.

## User Setup Required

None — no external service configuration required. The Alembic migration (`a1b2c3d5e7f9`) will run automatically on next `alembic upgrade head` after Phase 26 DEBT-01 resolves the multi-head situation.

## Next Phase Readiness

- `get_concurrency_semaphore()` and `reset_concurrency_cache()` are ready for Plan 25-02 to consume at the DV360 and Google Ads download call sites
- `SystemConfig.max_concurrent_downloads` column is ready for the Plan 25-02 API endpoints (`GET/PUT /download-concurrency`)
- Plan 25-03 (Angular admin UI slider) depends on the Plan 25-02 API surface, not on this plan directly
- Phase 26 DEBT-01 Alembic merge must wait until all v1.5 migrations land (Plans 25-02 and 25-03 do not add migrations, so this plan's migration is the last v1.5 DB change)

## Self-Check

Files created/modified:
- `backend/app/models/system_config.py` — FOUND
- `backend/alembic/versions/a1b2c3d5e7f9_phase25_max_concurrent_downloads.py` — FOUND
- `backend/app/services/sync/proxy_cache.py` — FOUND
- `backend/tests/test_proxy_cache.py` — FOUND

Commits:
- b1bd260 — FOUND
- b716ef9 — FOUND
- 6ffd685 — FOUND

## Self-Check: PASSED

---
*Phase: 25-configurable-concurrency*
*Completed: 2026-05-18*
