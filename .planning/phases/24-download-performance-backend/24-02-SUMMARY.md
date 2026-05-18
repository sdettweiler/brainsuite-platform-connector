---
phase: 24
plan: "02"
subsystem: backend/download
status: COMPLETE
tags: [perf, yt-dlp, dv360, proxy, refactor]
dependency_graph:
  requires:
    - 24-01  # proxy_cache.py must exist before dv360_sync.py can import get_proxy_config
  provides:
    - dv360-extraction-download-split   # _extract_info + _do_download pattern
    - dv360-po-first-retry              # PO-first retry order established
    - dv360-proxy-cache-integration     # get_proxy_config() used in both download and batch loop
    - dv360-conditional-sleep           # batch sleep gated on proxy_enabled
  affects:
    - 24-03  # google_ads_sync.py gets same refactor; uses identical pattern
    - 25-01  # semaphore wraps _download_video_asset call chain established here
tech_stack:
  added: []
  patterns:
    - extraction/download split via yt_dlp extract_info + process_ie_result
    - proxy_url captured in outer closure for _redact regardless of per-attempt proxy
    - module-level import of get_proxy_config for patch-ability in tests
key_files:
  modified:
    - backend/app/services/sync/dv360_sync.py
    - backend/tests/test_dv360_sync.py
decisions:
  - _redact uses outer proxy_url (not per-attempt proxy param) so PO-first attempt also redacts credentials
  - get_proxy_config imported at module level so tests can patch app.services.sync.dv360_sync.get_proxy_config
  - _do_download uses copy.deepcopy(info_dict) to prevent process_ie_result mutations bleeding across retry attempts
metrics:
  duration_minutes: 60
  completed_date: "2026-05-18"
  tasks_completed: 2
  files_modified: 2
---

# Phase 24 Plan 02: DV360 Download Refactor Summary

**One-liner:** DV360 yt-dlp refactored into _extract_info (no proxy) + _do_download (proxy), PO-first retry, 10s socket timeout, proxy-conditional batch sleep.

## What Was Built

Delivered PERF-01, PERF-03, PERF-04 (caller side), PERF-05, and PERF-06 for the DV360 download path:

**PERF-01 — Extraction/download split:**
- `_extract_info()` async closure runs `ydl.extract_info(url, download=False)` with NO proxy
- `_do_download(info_dict, proxy, cookie_data)` async closure runs `ydl.process_ie_result(info_copy, download=True)`
- info_dict extracted once, reused across all download retry attempts
- Fallback: if direct extraction fails AND proxy_enabled, retry extraction with proxy once

**PERF-03 — PO-first retry order (D-04):**
- When proxy enabled: attempts = `["", *cookies]` with first download using `proxy=None, cookie_data=""`
- Sequence: no-proxy/no-cookies → proxy/no-cookies → proxy/primary-cookie → proxy/backup-cookie
- When proxy disabled: original `[primary, backup]` behavior preserved

**PERF-04 — Proxy config cache integration:**
- Module-level import: `from app.services.sync.proxy_cache import get_proxy_config`
- Single `await get_proxy_config()` call at start of `_download_video_asset`
- Second call in `download_assets_post_commit` batch loop for sleep gating

**PERF-05 — Conditional batch sleep:**
- `proxy_enabled, _ = await get_proxy_config()` called once at batch loop start
- `if not proxy_enabled and video_download_count > 0: await asyncio.sleep(4)`
- When proxy active: 0s sleep. When proxy disabled: original 4s preserved.

**PERF-06 — Socket timeout reduction:**
- `"socket_timeout": 10` in both `_extract_info` and `_do_download` ydl_opts
- `"remote_components": "ejs:github"` in both phases

## Commit

`93157b6` — feat(24-02): refactor dv360_sync extraction/download split, PO-first, proxy cache, conditional sleep

## Verification Results

### Tests: 10/10 passed

```
tests/test_dv360_sync.py::test_get_cookies_from_db_returns_decrypted_db_cookies PASSED
tests/test_dv360_sync.py::test_get_cookies_from_db_falls_back_to_env_when_db_empty PASSED
tests/test_dv360_sync.py::test_get_cookies_from_db_falls_back_to_env_when_db_raises PASSED
tests/test_dv360_sync.py::test_get_cookies_from_db_returns_empty_when_db_and_env_both_empty PASSED
tests/test_dv360_sync.py::test_download_video_with_proxy PASSED
tests/test_dv360_sync.py::test_retry_order_cookieless_first PASSED
tests/test_dv360_sync.py::test_credential_redaction PASSED
tests/test_dv360_sync.py::test_extraction_runs_without_proxy PASSED
tests/test_dv360_sleep_conditional PASSED
tests/test_dv360_sync.py::test_remote_components_present_in_both_phases PASSED
```

### Acceptance criteria grep checks

| Check | Expected | Actual |
|-------|----------|--------|
| proxy_cache import in dv360_sync.py | >= 1 | 1 |
| socket_timeout 30 in dv360_sync.py | = 0 | 0 |
| socket_timeout 10 in dv360_sync.py | >= 2 | 2 |
| extract_info(url, download=False) | >= 1 | 1 |
| process_ie_result | >= 1 | 3 |
| if not proxy_enabled | >= 1 | 1 |
| _do_download_with_cookies (removed) | = 0 | 0 |
| _gsf_proxy/_SC_proxy/_dt_proxy (removed) | = 0 | 0 |
| remote_components | >= 2 | 2 |
| test_extraction_runs_without_proxy | = 1 | 1 |
| test_batch_download_sleep_conditional | = 1 | 1 |
| test_remote_components_present_in_both_phases | = 1 | 1 |
| socket_timeout 30 in tests | = 0 | 0 |
| socket_timeout 10 in tests | >= 1 | 7 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _redact used per-attempt proxy parameter instead of outer proxy_url**
- **Found during:** Task 2 test execution (test_credential_redaction failure)
- **Issue:** `_redact()` checked `if not proxy:` where `proxy` is the per-attempt parameter. On PO-first attempt, `proxy=None`, so redaction was skipped even though proxy_url is known in outer scope.
- **Fix:** Changed `_redact` to use `proxy_url` from the outer `_download_video_asset` closure, ensuring credentials are always redacted regardless of per-attempt proxy value.
- **Files modified:** backend/app/services/sync/dv360_sync.py
- **Commit:** 93157b6

**2. [Rule 2 - Missing critical functionality] get_proxy_config must be module-level import for testability**
- **Found during:** Task 2 test execution (AttributeError on patch target)
- **Issue:** Local import `from app.services.sync.proxy_cache import get_proxy_config` inside the method body makes the function unpatchable via `patch("app.services.sync.dv360_sync.get_proxy_config")`.
- **Fix:** Moved import to module level, removed local import from method body and batch loop.
- **Files modified:** backend/app/services/sync/dv360_sync.py
- **Commit:** 93157b6

## Key Decisions Made

1. `_redact` uses `proxy_url` from outer closure (not per-attempt `proxy` param) — ensures PO-first attempt also redacts credentials in any yt-dlp log messages that contain the proxy URL.
2. `get_proxy_config` imported at module level so tests can target `app.services.sync.dv360_sync.get_proxy_config` via `patch()`.
3. `copy.deepcopy(info_dict)` in `download_sync` prevents `process_ie_result` mutations from bleeding across retry attempts.

## Threat Flags

None found. All changes are internal to the download call chain. No new network endpoints, auth paths, or external surfaces introduced.

## Known Stubs

None. All functionality is fully wired.

## Output Contract for Phase 25

Phase 25 (semaphore concurrency, PERF-02) wraps the call chain established in this plan. The entry point is:

```python
await self._download_video_asset(yt_vid, org_id, yt_vid)
```

Inside `download_assets_post_commit`. The semaphore should wrap this call. The proxy_enabled state for sleep gating (`proxy_enabled, _ = await get_proxy_config()`) can be read once before the semaphore loop.

Phase 25 also needs a new `SystemConfig` column for the semaphore limit (DB migration required).

## Self-Check: PASSED

- [x] backend/app/services/sync/dv360_sync.py exists and parses correctly
- [x] backend/tests/test_dv360_sync.py exists with all 3 new test functions
- [x] Commit 93157b6 exists in git log
- [x] All 10 tests pass
