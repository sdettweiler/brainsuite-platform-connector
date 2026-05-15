---
phase: 20-proxy-download-infrastructure
plan: 02
subsystem: service
tags: [yt-dlp, residential-proxy, credential-redaction, iproyal, sqlalchemy, asyncio, tdd]

# Dependency graph
requires:
  - phase: 20-proxy-download-infrastructure
    plan: 01
    provides: 8 failing TDD stubs, SystemConfig proxy columns, Alembic migration a9b1c2d3e5f6
affects: [20-proxy-admin-ui, phase-21, proxy-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_redact() closure pattern — proxy credentials stripped from all log output before logger.* calls using re.sub on http://user:pass@host format"
    - "Cookieless-first retry order — '' prepended to attempts list when proxy_enabled=True (D-04)"
    - "Session ID sticky sessions — secrets.token_urlsafe(9) generated once per job, embedded in proxy username before retry loop (D-07)"
    - "Proxy injection before YoutubeDL instantiation — ydl_opts['proxy'] set after ydl_opts dict, before with YoutubeDL(ydl_opts) context manager (D-02)"

key-files:
  created: []
  modified:
    - backend/app/services/sync/dv360_sync.py
    - backend/app/services/sync/google_ads_sync.py
    - backend/tests/test_dv360_sync.py
    - backend/tests/test_google_ads_sync.py

key-decisions:
  - "_redact regex 'https?://[^@/]+@([^/:]+)[^\\\"\\s]*' → '[PROXY:\\1]' strips credentials AND port, producing '[PROXY:geo.iproyal.com]' not '[PROXY:geo.iproyal.com:12321]'"
  - "Test stubs for test_retry_order_cookieless_first were broken (captured ydl.download args = URL list, not cookie_data). Fixed by capturing YoutubeDL constructor opts and checking 'cookiefile' absence instead."
  - "proxy_url modified to embed session ID in username before the retry loop — single token_urlsafe(9) call per job, reused across all cookie slot attempts for sticky session behavior"

patterns-established:
  - "Both DV360 and Google Ads now have identical proxy injection structure — future platforms should follow the same _do_download_with_cookies closure pattern"

requirements-completed: [PROXY-01, PROXY-02, PROXY-03, PROXY-04, PROXY-06]

# Metrics
duration: 35min
completed: 2026-05-15
---

# Phase 20 Plan 02: Proxy Injection into DV360 and Google Ads Summary

**Residential proxy (IPRoyal) injected into both DV360 and Google Ads yt-dlp download paths with credential redaction, sticky session IDs, and cookieless-first retry order — all 6 proxy tests green**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-05-15T09:30:00Z
- **Completed:** 2026-05-15T10:05:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `_download_video_asset` in dv360_sync.py and `_download_video` in google_ads_sync.py both load proxy config from SystemConfig, inject `ydl_opts["proxy"]` before YoutubeDL instantiation, redact credentials in all log paths, generate a sticky session ID per job, and prepend a cookieless attempt when proxy is enabled
- All 6 proxy implementation tests (3 DV360 + 3 Google Ads) pass green; test_proxy_columns_exist also passes; test_bgutil_plugin_loaded documented as expected SKIP until Docker rebuild
- Pre-existing test failures (16 of them) confirmed unrelated to Plan 02 changes by stash-and-rerun verification

## Task Commits

Each task was committed atomically:

1. **Task 1: Inject proxy into DV360 _download_video_asset** - `b1e0e89` (feat)
2. **Task 2: Mirror proxy injection into Google Ads _download_video** - `e94b2d5` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/app/services/sync/dv360_sync.py` - `import secrets` added; proxy loading block after cookie loading; `_redact()` helper in closure; all 4 `_YDLLogger` methods call `_redact(msg)`; `ydl_opts["proxy"]` injection before YoutubeDL; exception redaction in except block; `attempts = ["", *attempts]` when proxy enabled
- `backend/app/services/sync/google_ads_sync.py` - Same changes mirrored exactly, adapted to inline cookie loading structure
- `backend/tests/test_dv360_sync.py` - Fixed `test_retry_order_cookieless_first` stub (Rule 1 bug)
- `backend/tests/test_google_ads_sync.py` - Fixed `test_retry_order_cookieless_first` stub (Rule 1 bug)

## Decisions Made

- `_redact` regex changed from plan's two-pass approach to single-pass: `re.sub(r'https?://[^@/]+@([^/:]+)[^"\s]*', r'[PROXY:\1]', msg)`. This strips credentials AND port in one pass, producing the `[PROXY:geo.iproyal.com]` format the test asserts.
- `proxy_url` is modified WITH the session ID embedded before the closure is defined. This means the session ID is baked into `proxy_url` as captured by `_redact()` — ensuring consistent session-tagged redaction across all log calls.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed broken test stubs for test_retry_order_cookieless_first**
- **Found during:** Task 1 (test run revealed wrong assertion)
- **Issue:** `_capture_attempts` was set as `side_effect` of `ydl.download`, which receives `[url]` (the URL list), not `cookie_data`. So `attempt_cookies[0]` was always `['https://...']`, never `""`. The test could never pass regardless of implementation.
- **Fix:** Changed both DV360 and Google Ads test stubs to use `YoutubeDL` as `side_effect` (class constructor mock), capturing `opts.get("cookiefile", "")` per instantiation. First attempt with no cookies → `""` in `attempt_cookies`. Assertion `attempt_cookies[0] == ""` now works correctly.
- **Files modified:** `backend/tests/test_dv360_sync.py`, `backend/tests/test_google_ads_sync.py`
- **Verification:** `test_retry_order_cookieless_first` passes green for both DV360 and Google Ads
- **Committed in:** `b1e0e89` (Task 1), `e94b2d5` (Task 2)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test stub)
**Impact on plan:** Test bug fix necessary for tests to pass. No change to implementation behavior — the test now correctly verifies what the plan intended (cookieless first attempt when proxy enabled).

## Issues Encountered

- Docker container mounts main repo `./backend:/app`, not the worktree backend. Worktree code changes required temporary copy to main repo for Docker test execution. Main repo files were restored after each test run.
- `test_bgutil_plugin_loaded` fails with `ModuleNotFoundError: yt_dlp_plugins` because `bgutil-ytdlp-pot-provider` is not installed in the current running Docker image (added to `requirements.txt` in Plan 01 but image not rebuilt). This is expected per Plan 01 decisions and Plan 02 acceptance criteria ("PASSES or documented as SKIPPED if bgutil not installed in test env").

## Known Stubs

None — all proxy functionality is fully implemented in both sync services. The `test_bgutil_plugin_loaded` test remains failing as a test-environment limitation, not a code stub.

## Threat Flags

No new threat surface beyond what was already catalogued in the plan's `<threat_model>`:
- T-20-05 (credential redaction): mitigated — all 4 logger methods call `_redact(msg)`
- T-20-06 (exception redaction): mitigated — `_redact(str(e))` in except block
- T-20-07 (session ID reuse): mitigated — `secrets.token_urlsafe(9)` once per job
- T-20-08 (proxy disabled bypass): mitigated — `if proxy_enabled and proxy_url` guard in both files
- T-20-10 (injection order): mitigated — `ydl_opts["proxy"]` set before `YoutubeDL(ydl_opts)`

## User Setup Required

None — no external service configuration required for this plan. The proxy remains disabled until ops sets `proxy_enabled=True` and provides `proxy_url_encrypted` in SystemConfig via Phase 21 admin UI.

## Next Phase Readiness

- Phase 21 (SuperAdmin proxy config UI) can now implement the `proxy_enabled` toggle and `proxy_url_encrypted` input — both columns exist in SystemConfig and the ORM model is ready
- Ops can enable the proxy immediately by directly updating SystemConfig via SQL: `UPDATE system_config SET proxy_enabled=true, proxy_url_encrypted='<encrypted_url>' WHERE singleton_guard='X'`
- When proxy is enabled, the next DV360 or Google Ads sync will route through the residential proxy automatically

---
*Phase: 20-proxy-download-infrastructure*
*Completed: 2026-05-15*

## Self-Check: PASSED

- FOUND: backend/app/services/sync/dv360_sync.py
- FOUND: backend/app/services/sync/google_ads_sync.py
- FOUND: backend/tests/test_dv360_sync.py
- FOUND: backend/tests/test_google_ads_sync.py
- FOUND: .planning/phases/20-proxy-download-infrastructure/20-02-SUMMARY.md
- FOUND commit: b1e0e89 (feat(20-02): inject proxy into DV360 _download_video_asset)
- FOUND commit: e94b2d5 (feat(20-02): mirror proxy injection into Google Ads _download_video)
