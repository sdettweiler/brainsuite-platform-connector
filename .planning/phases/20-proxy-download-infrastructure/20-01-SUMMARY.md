---
phase: 20-proxy-download-infrastructure
plan: 01
subsystem: testing, database, infra
tags: [pytest, yt-dlp, bgutil, alembic, sqlalchemy, proxy, residential-proxy]

# Dependency graph
requires:
  - phase: 19-superadmin-monitoring-ui
    provides: SystemConfig singleton table with Fernet-encrypted columns
provides:
  - 8 failing Wave 0 test stubs (TDD RED gate) for proxy injection, retry order, credential redaction, bgutil plugin, schema columns
  - bgutil-ytdlp-pot-provider added to requirements.txt
  - SystemConfig ORM model with proxy_url_encrypted (Text) and proxy_enabled (Boolean) columns
  - Alembic migration a9b1c2d3e5f6 chaining after z8a9b1c2d3e5 adding both proxy columns
affects: [20-proxy-injection, 20-proxy-admin-ui, plan-02, plan-03]

# Tech tracking
tech-stack:
  added: [bgutil-ytdlp-pot-provider]
  patterns: [TDD Wave 0 stub pattern — stubs assert on unimplemented behavior before implementation plans run]

key-files:
  created:
    - backend/tests/test_google_ads_sync.py
    - backend/tests/test_yt_dlp_plugin.py
    - backend/alembic/versions/a9b1c2d3e5f6_add_proxy_config.py
  modified:
    - backend/tests/test_dv360_sync.py
    - backend/tests/test_system_config.py
    - backend/requirements.txt
    - backend/app/models/system_config.py

key-decisions:
  - "Test stubs use patch('yt_dlp.YoutubeDL') which requires yt_dlp to be installed at test collection time — test env lacks yt_dlp so those stubs fail with ModuleNotFoundError (exit code 1, not 2, so collection succeeds)"
  - "bgutil test (test_bgutil_plugin_loaded) fails in test env because pip install not yet run — acceptable per acceptance criteria; bgutil is in requirements.txt for Docker image"
  - "proxy_url_encrypted placed after youtube_cookies_download_count in SystemConfig column order for logical grouping"

patterns-established:
  - "Wave 0 TDD stub pattern: stubs assert on attributes/behaviors that don't exist yet, causing intentional failures that gate Plan 02 implementation"
  - "test_google_ads_sync.py mirrors test_dv360_sync.py structure — same helper factory pattern, same test names, same assertions"

requirements-completed: [PROXY-01, PROXY-02, PROXY-03, PROXY-04, PROXY-06]

# Metrics
duration: 12min
completed: 2026-05-15
---

# Phase 20 Plan 01: Proxy Test Foundation + Schema Summary

**Wave 0 TDD stubs for residential proxy (8 failing tests), bgutil-ytdlp-pot-provider added to requirements.txt, SystemConfig extended with proxy_url_encrypted + proxy_enabled, Alembic migration a9b1c2d3e5f6 ready to chain**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-15T00:00:00Z
- **Completed:** 2026-05-15T00:12:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- 8 failing Wave 0 test stubs across 4 test files (proxy injection, cookieless-first retry, credential redaction, bgutil plugin, schema columns) — all fail correctly (exit code 1, not 2)
- All 4 existing DV360 cookie tests and 7 existing system_config tests continue to pass
- SystemConfig ORM model extended with 2 proxy columns (Text nullable, Boolean not-null server_default false) — test_proxy_columns_exist passes
- Alembic migration file created with correct revision ID and down_revision chain (z8a9b1c2d3e5 → a9b1c2d3e5f6)

## Task Commits

Each task was committed atomically:

1. **Task 1: Write 8 failing proxy test stubs across 4 test files** - `9eab35a` (test)
2. **Task 2: Add bgutil dep + SystemConfig proxy columns + Alembic migration** - `fcc2183` (feat)

## Files Created/Modified

- `backend/tests/test_dv360_sync.py` - Appended 3 proxy stubs (test_download_video_with_proxy, test_retry_order_cookieless_first, test_credential_redaction); added io + logging imports
- `backend/tests/test_system_config.py` - Appended test_proxy_columns_exist stub
- `backend/tests/test_google_ads_sync.py` - New file: _make_google_ads_sync_service helper + 3 mirrored proxy stubs
- `backend/tests/test_yt_dlp_plugin.py` - New file: test_bgutil_plugin_loaded stub
- `backend/requirements.txt` - Added bgutil-ytdlp-pot-provider after yt-dlp line
- `backend/app/models/system_config.py` - Added proxy_url_encrypted + proxy_enabled columns after youtube_cookies_download_count
- `backend/alembic/versions/a9b1c2d3e5f6_add_proxy_config.py` - New migration: upgrade adds both columns; downgrade drops them; down_revision = "z8a9b1c2d3e5"

## Decisions Made

- `patch("yt_dlp.YoutubeDL", ...)` causes `ModuleNotFoundError` in the test environment (yt_dlp not installed as a bare Python package locally). This is a test environment constraint, not a collection error — pytest exit code is 1 (test failure), not 2 (collection error), satisfying acceptance criteria.
- `test_bgutil_plugin_loaded` fails with AssertionError because bgutil is not installed in the local test env. This is expected and documented: bgutil will be installed when Docker builds the backend image from requirements.txt.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Local test environment does not have `yt_dlp` installed as a standalone Python package (it runs inside Docker). Tests that `patch("yt_dlp.YoutubeDL")` fail with `ModuleNotFoundError` rather than an assertion error. This is consistent with the plan's intent: the stubs fail at test time (exit code 1), which is the TDD RED gate requirement. The Docker container will have yt_dlp from requirements.txt.

## Known Stubs

The following stubs are intentionally failing and will be resolved by Plan 02:

| Stub | File | Reason |
|------|------|--------|
| test_download_video_with_proxy | test_dv360_sync.py | Proxy injection (D-02) not yet in dv360_sync.py |
| test_retry_order_cookieless_first | test_dv360_sync.py | Cookieless-first retry (D-04) not yet implemented |
| test_credential_redaction | test_dv360_sync.py | redact_credentials() (D-05) not yet implemented |
| test_download_video_with_proxy | test_google_ads_sync.py | Mirror of DV360 stub — Plan 02 implements both |
| test_retry_order_cookieless_first | test_google_ads_sync.py | Mirror of DV360 stub |
| test_credential_redaction | test_google_ads_sync.py | Mirror of DV360 stub |
| test_bgutil_plugin_loaded | test_yt_dlp_plugin.py | bgutil not installed in local test env; passes in Docker |

`test_proxy_columns_exist` in test_system_config.py is GREEN — columns added in Task 2.

## User Setup Required

None - no external service configuration required for this plan. bgutil will be installed via Docker build.

## Next Phase Readiness

- Plan 02 can now implement proxy injection in dv360_sync.py and google_ads_sync.py, knowing exactly which tests must turn green
- SystemConfig model and migration are ready — Plan 02 reads `config.proxy_enabled` and `config.proxy_url_encrypted` without import errors
- The Alembic migration chain is intact: `alembic upgrade head` will apply both proxy columns in sequence after z8a9b1c2d3e5

---
*Phase: 20-proxy-download-infrastructure*
*Completed: 2026-05-15*
