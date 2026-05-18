---
phase: 24
slug: download-performance-backend
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-18
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest backend/tests/test_dv360_sync.py::test_download_video_with_proxy -xvs` |
| **Full suite command** | `pytest backend/tests/test_dv360_sync.py backend/tests/test_google_ads_sync.py -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/test_dv360_sync.py::test_download_video_with_proxy -xvs`
- **After every plan wave:** Run `pytest backend/tests/test_dv360_sync.py backend/tests/test_google_ads_sync.py -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| proxy-cache | — | 0 | PERF-04 | — | asyncio.Lock guards all cache reads/writes; no race conditions | unit | `pytest backend/tests/test_sync/test_proxy_cache.py -v` | ❌ W0 | ⬜ pending |
| conditional-sleep | — | 0 | PERF-05 | — | N/A | unit | `pytest backend/tests/test_dv360_sync.py::test_batch_download_sleep_conditional -v` | ❌ W0 | ⬜ pending |
| socket-timeout | — | 0 | PERF-06 | — | N/A | unit | `pytest backend/tests/test_dv360_sync.py -k "socket_timeout" -v` | ❌ W0 | ⬜ pending |
| extract-info-split | — | 1 | PERF-01 | — | Proxy URL not passed to extraction call | unit | `pytest backend/tests/test_dv360_sync.py -k "extract" -v` | ✅ | ⬜ pending |
| po-first-retry | — | 1 | PERF-03 | — | N/A | unit | `pytest backend/tests/test_dv360_sync.py::test_download_video_with_proxy -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_sync/test_proxy_cache.py` — stubs for PERF-04: TTL expiry test, concurrent access test, cache hit test
- [ ] `backend/tests/test_dv360_sync.py::test_batch_download_sleep_conditional` — new test for PERF-05 conditional sleep (proxy_enabled=True → no sleep, proxy_enabled=False → 4s sleep)
- [ ] Update `backend/tests/test_dv360_sync.py::test_download_video_with_proxy` — add assertion that `socket_timeout: 10` is set in ydl_opts (PERF-06)
- [ ] Add test in `backend/tests/test_google_ads_sync.py` asserting `remote_components="ejs:github"` present in ydl_opts (PERF-03 parity)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DV360 download wall-clock time 3–5x faster | PERF-01 + PERF-03 | Requires live proxy + real YouTube video | Run DV360 sync job with proxy enabled; observe job log timestamps; verify proxy overhead 7–15s is eliminated |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
