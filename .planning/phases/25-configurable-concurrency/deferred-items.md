# Deferred Items — Phase 25 Plan 02

## Pre-existing Test Failures (not introduced by Phase 25)

### remote_components list vs string mismatch

**Files:** backend/tests/test_dv360_sync.py, backend/tests/test_google_ads_sync.py
**Tests:**
- `test_dv360_sync.py::test_remote_components_present_in_both_phases`
- `test_google_ads_sync.py::test_remote_components_present_in_both_phases`
- `test_google_ads_sync.py::test_download_video_with_proxy`

**Issue:** Tests assert `opts.get("remote_components") == "ejs:github"` (string) but the production code uses `"remote_components": ["ejs:github"]` (list). This mismatch existed on main branch before Phase 25 work.

**Verified pre-existing:** Confirmed by running the tests against main branch dv360_sync.py and google_ads_sync.py in the container — same 3 failures.

**Action required:** Fix in a future tech-debt session. The correct value should be a string `"ejs:github"` (the yt-dlp remote_components option expects a string or list — need to verify which is correct with yt-dlp docs and update either code or tests accordingly).
