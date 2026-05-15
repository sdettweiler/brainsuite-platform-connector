---
phase: 20
slug: proxy-download-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | backend/pytest.ini |
| **Quick run command** | `pytest tests/test_dv360_sync.py tests/test_google_ads_sync.py -k "proxy or retry or redact" -x` |
| **Full suite command** | `pytest tests/ -m "not slow" --tb=short` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_dv360_sync.py tests/test_google_ads_sync.py -k "proxy or retry or redact" -x`
- **After every plan wave:** Run `pytest tests/ -m "not slow" --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green + manual log grep for zero credentials
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 20-01-01 | 01 | 1 | — | — | N/A | unit | `pytest tests/test_dv360_sync.py::test_download_video_with_proxy tests/test_google_ads_sync.py::test_download_video_with_proxy -x` | ❌ W0 | ⬜ pending |
| 20-02-01 | 02 | 2 | PROXY-01, PROXY-02 | D-02/D-03 | Proxy applied to full yt-dlp session (info+download) | unit | `pytest tests/test_dv360_sync.py::test_download_video_with_proxy tests/test_google_ads_sync.py::test_download_video_with_proxy -x` | ❌ W0 | ⬜ pending |
| 20-02-02 | 02 | 2 | PROXY-04 | D-04 | Cookieless attempt prepended when proxy enabled | unit | `pytest tests/test_dv360_sync.py::test_retry_order_cookieless_first tests/test_google_ads_sync.py::test_retry_order_cookieless_first -x` | ❌ W0 | ⬜ pending |
| 20-02-03 | 02 | 2 | PROXY-06 | D-05/D-06 | No credentials in log output | unit | `pytest tests/test_dv360_sync.py::test_credential_redaction tests/test_google_ads_sync.py::test_credential_redaction -x` | ❌ W0 | ⬜ pending |
| 20-02-04 | 02 | 2 | PROXY-03 | D-01 | bgutil plugin auto-detected by yt-dlp | unit | `pytest tests/test_yt_dlp_plugin.py::test_bgutil_plugin_loaded -x` | ❌ W0 | ⬜ pending |
| 20-03-01 | 03 | 3 | PROXY-01, PROXY-02 | — | Migration adds proxy columns + Alembic upgrade head succeeds | unit | `pytest tests/test_system_config.py::test_proxy_columns_exist -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_dv360_sync.py::test_download_video_with_proxy` — PROXY-01 (mock proxy, verify ydl_opts["proxy"] is set)
- [ ] `tests/test_dv360_sync.py::test_retry_order_cookieless_first` — PROXY-04 (mock attempts list, verify empty string prepended when proxy enabled)
- [ ] `tests/test_dv360_sync.py::test_credential_redaction` — PROXY-06 (mock proxy URL, verify logger calls _redact, check output for zero credentials)
- [ ] `tests/test_google_ads_sync.py::test_download_video_with_proxy` — PROXY-02 (mirror of DV360 test)
- [ ] `tests/test_google_ads_sync.py::test_retry_order_cookieless_first` — PROXY-04 (mirror)
- [ ] `tests/test_google_ads_sync.py::test_credential_redaction` — PROXY-06 (mirror)
- [ ] `tests/test_yt_dlp_plugin.py::test_bgutil_plugin_loaded` — PROXY-03 (verify bgutil plugin detected)
- [ ] `tests/test_system_config.py::test_proxy_columns_exist` — schema migration verification

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DV360 video downloads successfully on GCP Cloud Run with proxy | PROXY-01 | Requires live IPRoyal credentials and production GCP host | Trigger DV360 sync with proxy_enabled=true; confirm asset_url populated in CreativeAsset |
| Google Ads video downloads successfully on GCP Cloud Run with proxy | PROXY-02 | Requires live proxy credentials and production host | Trigger Google Ads sync with proxy_enabled=true; confirm asset_url populated |
| No proxy credentials in application logs (SC-05) | PROXY-06 | Requires full download run to generate real log output | After download run, grep all logs for username/password substrings; must return zero matches |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
