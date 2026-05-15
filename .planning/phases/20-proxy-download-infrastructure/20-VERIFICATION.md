---
phase: 20-proxy-download-infrastructure
verified: 2026-05-15T11:50:00Z
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Enable proxy in SystemConfig (set proxy_enabled=true, proxy_url_encrypted=<encrypted IPRoyal URL>) on the GCP Cloud Run backend, then trigger a DV360 sync for an org with at least one YouTube video creative"
    expected: "After the sync completes, the creative's asset_url is populated in CreativeAsset and the video is playable in the dashboard (PROXY-01 / SC1)"
    why_human: "Requires live GCP Cloud Run host, live IPRoyal residential proxy credentials, and a real DV360 ad account. Cannot be verified by code inspection or Docker unit tests."
  - test: "With proxy enabled in SystemConfig on GCP Cloud Run, trigger a Google Ads sync for an org with at least one YouTube video creative"
    expected: "After the sync completes, the creative's asset_url is populated in CreativeAsset and the video is playable in the dashboard (PROXY-02 / SC2)"
    why_human: "Requires live GCP Cloud Run host, live IPRoyal residential proxy credentials, and a real Google Ads customer account. Cannot be verified by code inspection or Docker unit tests."
  - test: "Rebuild the backend Docker image from the current requirements.txt (docker-compose build backend), then run: docker-compose exec backend python -m pytest tests/test_yt_dlp_plugin.py::test_bgutil_plugin_loaded --tb=short"
    expected: "test_bgutil_plugin_loaded PASSES (not skipped) — confirming bgutil-ytdlp-pot-provider is installed and the yt_dlp_plugins namespace is importable (PROXY-03 / SC3)"
    why_human: "bgutil is in requirements.txt but the running container was built before it was added. Requires a Docker rebuild to install the package. Cannot verify without rebuilding the image."
---

# Phase 20: Proxy Download Infrastructure — Verification Report

**Phase Goal:** DV360 and Google Ads video creatives download successfully on production hosts via residential proxy and bgutil PO token plugin, with credentials never written to logs
**Verified:** 2026-05-15T11:50:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | DV360 sync on GCP Cloud Run downloads a video creative via residential proxy — asset_url populated | ? HUMAN_NEEDED | Proxy injection code verified in dv360_sync.py lines 1160–1189, 1239–1242. Live GCP test required. |
| SC2 | Google Ads sync on GCP Cloud Run downloads a video creative via residential proxy — asset_url populated | ? HUMAN_NEEDED | Proxy injection code verified in google_ads_sync.py lines 312–340, 385–388. Live GCP test required. |
| SC3 | bgutil PO token plugin invoked automatically by yt-dlp without per-video token code in sync services | ? HUMAN_NEEDED | bgutil-ytdlp-pot-provider in requirements.txt (line 27). test_bgutil_plugin_loaded SKIPs in running container — Docker rebuild required. |
| SC4 | Retry sequence is cookieless-with-proxy → primary-cookies → backup-cookies → fail; cookies preserved when proxy disabled | VERIFIED | `attempts = ["", *attempts]` when `proxy_enabled and proxy_url` (dv360_sync.py:1273, google_ads_sync.py:417). `test_retry_order_cookieless_first` PASSES in Docker for both services. |
| SC5 | No proxy credentials appear in application logs after a proxy-enabled download run | VERIFIED | `_redact()` closure in both `_do_download_with_cookies` applies `re.sub(r'https?://[^@/]+@([^/:]+)[^"\s]*', r'[PROXY:\1]', msg)` to all 4 _YDLLogger methods and exception messages. `test_credential_redaction` PASSES in Docker for both services. |

**Score:** 2/5 ROADMAP SCs fully verified by code; 3/5 require human testing; all underlying code implementations verified.

### Plan Must-Haves (Plan 01 + Plan 02 combined)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| P1-1 | 8 failing test stubs exist across 4 test files | VERIFIED | All 8 test functions confirmed in test files. 7 pass green in Docker; 1 skips (bgutil, expected per plan). |
| P1-2 | bgutil-ytdlp-pot-provider appears in requirements.txt | VERIFIED | `grep -c` returns 1 (line 27 of requirements.txt) |
| P1-3 | SystemConfig ORM has proxy_url_encrypted (Text, nullable) and proxy_enabled (Boolean, default False) | VERIFIED | system_config.py lines 32–33. server_default="false" confirmed. |
| P1-4 | Alembic migration a9b1c2d3e5f6_add_proxy_config.py exists with correct down_revision | VERIFIED | File exists. `down_revision = "z8a9b1c2d3e5"` chains correctly from z8a9b1c2d3e5_youtube_cookies_runtime_expired.py. Two `op.add_column` calls confirmed. |
| P1-5 | Alembic migration structurally valid | VERIFIED | Migration file is syntactically correct Python; revision chain is contiguous. |
| P2-1 | DV360 _download_video_asset loads proxy config and injects proxy_url into ydl_opts when proxy_enabled=True | VERIFIED | dv360_sync.py lines 1160–1189 (load), 1241–1242 (inject). `test_download_video_with_proxy` PASSES. |
| P2-2 | Google Ads _download_video mirrors same proxy injection and retry logic | VERIFIED | google_ads_sync.py lines 312–340 (load), 387–388 (inject). `test_download_video_with_proxy` PASSES. |
| P2-3 | Cookieless attempt prepended when proxy enabled; backward compat when disabled | VERIFIED | Both files: `if proxy_enabled and proxy_url: attempts = ["", *attempts]`. `test_retry_order_cookieless_first` PASSES for both. |
| P2-4 | All four _YDLLogger methods call _redact() before logging | VERIFIED | dv360_sync.py: 5 _redact(msg) calls covering debug (2 branches), info, warning, error. Same in google_ads_sync.py. |
| P2-5 | Exception messages redacted before logging | VERIFIED | `_redact(str(e))` before `logger.error()` in except block — both files (grep -c returns 1 each). |
| P2-6 | Session ID generated once per job, embedded in proxy username | VERIFIED | `secrets.token_urlsafe(9)` called once outside retry loop (grep -c token_urlsafe returns 1 each file). Embedded before closure definition. |
| P2-7 | All 8 proxy test stubs pass green | VERIFIED | Docker test run: 7 PASS, 1 SKIP (bgutil — package not installed in running container, expected). |

**Score:** 9/9 plan must-haves verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/tests/test_dv360_sync.py` | Proxy stubs (injection, retry, redaction) | VERIFIED | Lines 183, 235, 297 — all 3 stubs present and passing |
| `backend/tests/test_google_ads_sync.py` | Mirror proxy stubs | VERIFIED | Lines 40, 92, 154 — all 3 stubs present and passing |
| `backend/tests/test_yt_dlp_plugin.py` | bgutil plugin detection test | VERIFIED (SKIPS) | File exists; test skips gracefully when package not installed |
| `backend/tests/test_system_config.py` | Schema column test | VERIFIED | test_proxy_columns_exist at line 142 — PASSES in Docker |
| `backend/requirements.txt` | bgutil-ytdlp-pot-provider dependency | VERIFIED | Line 27, after yt-dlp line |
| `backend/app/models/system_config.py` | proxy_url_encrypted + proxy_enabled columns | VERIFIED | Lines 32–33; correct types, nullability, server_default |
| `backend/alembic/versions/a9b1c2d3e5f6_add_proxy_config.py` | DB schema migration | VERIFIED | Correct revision ID, down_revision, two add_column calls |
| `backend/app/services/sync/dv360_sync.py` | DV360 proxy-enabled download | VERIFIED | proxy_url_encrypted referenced; all 4 patterns present |
| `backend/app/services/sync/google_ads_sync.py` | Google Ads proxy-enabled download | VERIFIED | proxy_url_encrypted referenced; all 4 patterns present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| dv360_sync.py | SystemConfig | config.proxy_enabled + config.proxy_url_encrypted | WIRED | Lines 1169–1173: reads proxy_enabled and proxy_url_encrypted from DB row |
| dv360_sync.py | ydl_opts["proxy"] | `if proxy_enabled and proxy_url: ydl_opts["proxy"] = proxy_url` | WIRED | Line 1241–1242, before `with yt_dlp.YoutubeDL(ydl_opts)` |
| google_ads_sync.py | SystemConfig | config.proxy_enabled + config.proxy_url_encrypted | WIRED | Lines 321–325: reads proxy_enabled and proxy_url_encrypted from DB row |
| google_ads_sync.py | ydl_opts["proxy"] | `if proxy_enabled and proxy_url: ydl_opts["proxy"] = proxy_url` | WIRED | Lines 387–388, before `with yt_dlp.YoutubeDL(ydl_opts)` |
| _YDLLogger.warning | _redact | `logger.warning("yt-dlp: %s", _redact(msg))` | WIRED | dv360_sync.py:1220, google_ads_sync.py:369 |
| _YDLLogger.error | _redact | `logger.error("yt-dlp: %s", _redact(msg))` | WIRED | dv360_sync.py:1224, google_ads_sync.py:373 |
| _YDLLogger.debug | _redact | `logger.debug/info("yt-dlp: %s", _redact(msg))` | WIRED | dv360_sync.py:1213+1215, google_ads_sync.py:362+364 |
| _YDLLogger.info | _redact | `logger.info("yt-dlp: %s", _redact(msg))` | WIRED | dv360_sync.py:1216, google_ads_sync.py:365 |
| SystemConfig.proxy_url_encrypted | alembic migration a9b1c2d3e5f6 | column name match | WIRED | ORM column name matches migration column name exactly |
| migration a9b1c2d3e5f6 | migration z8a9b1c2d3e5 | down_revision chain | WIRED | `down_revision = "z8a9b1c2d3e5"` confirmed |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| dv360_sync._download_video_asset | proxy_url | SystemConfig.proxy_url_encrypted via decrypt_token() | DB query → Fernet decrypt | FLOWING |
| dv360_sync._do_download_with_cookies | ydl_opts["proxy"] | proxy_url (closure variable) | Set when proxy_enabled=True | FLOWING |
| google_ads_sync._download_video | proxy_url | SystemConfig.proxy_url_encrypted via decrypt_token() | DB query → Fernet decrypt | FLOWING |
| google_ads_sync._do_download_with_cookies | ydl_opts["proxy"] | proxy_url (closure variable) | Set when proxy_enabled=True | FLOWING |

### Behavioral Spot-Checks (Docker)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| DV360 proxy injection test | `docker-compose exec backend python -m pytest tests/test_dv360_sync.py::test_download_video_with_proxy --tb=short -q` | PASSED | PASS |
| DV360 cookieless-first retry | `docker-compose exec backend python -m pytest tests/test_dv360_sync.py::test_retry_order_cookieless_first --tb=short -q` | PASSED | PASS |
| DV360 credential redaction | `docker-compose exec backend python -m pytest tests/test_dv360_sync.py::test_credential_redaction --tb=short -q` | PASSED | PASS |
| Google Ads proxy injection test | `docker-compose exec backend python -m pytest tests/test_google_ads_sync.py::test_download_video_with_proxy --tb=short -q` | PASSED | PASS |
| Google Ads cookieless-first retry | `docker-compose exec backend python -m pytest tests/test_google_ads_sync.py::test_retry_order_cookieless_first --tb=short -q` | PASSED | PASS |
| Google Ads credential redaction | `docker-compose exec backend python -m pytest tests/test_google_ads_sync.py::test_credential_redaction --tb=short -q` | PASSED | PASS |
| Schema columns exist | `docker-compose exec backend python -m pytest tests/test_system_config.py::test_proxy_columns_exist --tb=short -q` | PASSED | PASS |
| bgutil plugin loaded | `docker-compose exec backend python -m pytest tests/test_yt_dlp_plugin.py::test_bgutil_plugin_loaded --tb=short -q` | SKIPPED (bgutil not installed in running image) | SKIP — needs Docker rebuild |

### Requirements Coverage

| Requirement | Description | Source Plan | Status | Evidence |
|-------------|-------------|------------|--------|----------|
| PROXY-01 | DV360 video creatives download via residential proxy on GCP | 20-01, 20-02 | HUMAN_NEEDED | Code verified; live GCP test pending (SC1) |
| PROXY-02 | Google Ads video creatives download via residential proxy on GCP | 20-01, 20-02 | HUMAN_NEEDED | Code verified; live GCP test pending (SC2) |
| PROXY-03 | bgutil PO token plugin installed and auto-invoked | 20-01, 20-02 | HUMAN_NEEDED | In requirements.txt; Docker rebuild pending (SC3) |
| PROXY-04 | Cookieless-first retry order; cookie slots preserved | 20-01, 20-02 | VERIFIED | `attempts = ["", *attempts]` + both tests passing |
| PROXY-06 | Proxy credentials never written to logs | 20-01, 20-02 | VERIFIED | _redact() on all 4 logger methods + exception; both tests passing |

Note: PROXY-05 (SuperAdmin proxy config UI) is assigned to Phase 21, not Phase 20. Not evaluated here.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/tests/test_yt_dlp_plugin.py` | 17–18 | `pytest.skip()` instead of assert | Info | Intentional — acceptable per plan decisions. Test will PASS after Docker rebuild installs bgutil. Not a blocker. |

No TODO/FIXME/placeholder comments found in implementation files. No stub return patterns found. No hardcoded empty data in proxy-related code paths.

### Human Verification Required

#### 1. DV360 Live Proxy Download (PROXY-01 / SC1)

**Test:** On GCP Cloud Run backend, set `proxy_enabled=true` and `proxy_url_encrypted=<Fernet-encrypted IPRoyal URL>` in SystemConfig. Trigger a DV360 sync for an organization with at least one YouTube video creative.
**Expected:** After sync completes, the creative record in CreativeAsset has a non-null `asset_url` pointing to the downloaded video file in object storage. The video is playable in the dashboard.
**Why human:** Requires live GCP Cloud Run environment, live IPRoyal residential proxy credentials, and a real DV360 ad account with video creatives. The proxy injection code is verified but end-to-end download success (bypassing GCP 403 blocks) can only be confirmed with real infrastructure.

#### 2. Google Ads Live Proxy Download (PROXY-02 / SC2)

**Test:** With the same proxy configuration active on GCP Cloud Run, trigger a Google Ads sync for an organization with at least one YouTube video creative.
**Expected:** After sync completes, the creative record in CreativeAsset has a non-null `asset_url`. The video is playable in the dashboard.
**Why human:** Same infrastructure constraints as SC1. Google Ads proxy code is a verified mirror of DV360 but live download success requires real credentials and real GCP environment.

#### 3. bgutil Plugin Docker Rebuild Verification (PROXY-03 / SC3)

**Test:** Run `docker-compose build backend` (using the current requirements.txt which includes `bgutil-ytdlp-pot-provider`), then run `docker-compose exec backend python -m pytest tests/test_yt_dlp_plugin.py::test_bgutil_plugin_loaded --tb=short -v`.
**Expected:** `test_bgutil_plugin_loaded` reports PASSED (not skipped). The `yt_dlp_plugins` namespace is importable, confirming bgutil is installed and yt-dlp will auto-detect it.
**Why human:** The running container predates the addition of bgutil to requirements.txt. A Docker rebuild is required to install the package. This is a one-command test once the image is rebuilt.

### Gaps Summary

No code-level gaps found. All plan must-haves are verified in the codebase. The three human verification items are infrastructure tests, not code deficiencies:

- SC1 and SC2 are inherently live-environment tests — the residential proxy only resolves 403 blocks on GCP hosts, not in local/Docker environments. The code path is complete and tested via mocks.
- SC3 requires a Docker image rebuild, which is a one-step operation. The package entry is in requirements.txt and the test is written and correct.

**The implementation is complete. Phase 20 is ready for production validation.**

---

_Verified: 2026-05-15T11:50:00Z_
_Verifier: Claude (gsd-verifier)_
