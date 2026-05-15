---
status: partial
phase: 20-proxy-download-infrastructure
source: [20-VERIFICATION.md]
started: 2026-05-15T11:45:00Z
updated: 2026-05-15T11:45:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. bgutil plugin Docker rebuild (PROXY-03 / SC3)
expected: After `docker-compose build backend`, running `docker-compose exec backend python -m pytest tests/test_yt_dlp_plugin.py::test_bgutil_plugin_loaded` should PASS (not skip).
result: PASSED 2026-05-15 — bgutil-ytdlp-pot-provider-1.3.1 installed, test_bgutil_plugin_loaded PASS

### 2. DV360 live proxy download (PROXY-01 / SC1)
expected: Enable proxy in SystemConfig (set proxy_enabled=True, proxy_url_encrypted=<IPRoyal URL>) on GCP Cloud Run, trigger a DV360 sync, confirm asset_url is populated in CreativeAsset for at least one video creative.
result: [pending]

### 3. Google Ads live proxy download (PROXY-02 / SC2)
expected: Same configuration as above, trigger a Google Ads sync, confirm asset_url is populated in CreativeAsset for at least one video creative.
result: [pending]

## Summary

total: 3
passed: 1
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
