---
status: partial
phase: 20-proxy-download-infrastructure
source: [20-VERIFICATION.md]
started: 2026-05-15T11:45:00Z
updated: 2026-05-15T14:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. bgutil plugin Docker rebuild (PROXY-03 / SC3)
expected: After `docker-compose build backend`, running `docker-compose exec backend python -m pytest tests/test_yt_dlp_plugin.py::test_bgutil_plugin_loaded` should PASS (not skip).
result: PASSED 2026-05-15 — bgutil-ytdlp-pot-provider-1.3.1 installed, test_bgutil_plugin_loaded PASS

### 2. DV360 live proxy download (PROXY-01 / SC1)
expected: Enable proxy in SystemConfig on GCP Cloud Run, trigger a DV360 sync, confirm asset_url is populated in CreativeAsset for at least one video creative.
result: PASSED 2026-05-15 — download confirmed through DataImpulse residential proxy (89.84.121.42, Bouygues Telecom FR). Two fixes applied during UAT: (1) proxy URL must be Fernet-encrypted with prod TOKEN_ENCRYPTION_KEY; (2) sticky-session injection scoped to iproyal.com only — DataImpulse rejects -session- suffix.

### 3. Google Ads live proxy download (PROXY-02 / SC2)
expected: Same configuration, trigger a Google Ads sync, confirm asset_url is populated in CreativeAsset for at least one video creative.
result: blocked
blocked_by: prior-phase
reason: "Two pre-existing issues prevent testing: (1) REQUESTED_METRICS_FOR_MANAGER — connected accounts include MCC manager accounts which reject metric queries; (2) youtube_cookies_runtime_expired flag set by prior IP/rate-limit event blocks all downloads before proxy is reached. Proxy code path in google_ads_sync.py is identical to dv360_sync.py which is confirmed working."

## Summary

total: 3
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 1

## Gaps
