---
phase: 15
slug: tiktok-asset-download
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing infrastructure in backend/tests/) |
| **Config file** | pyproject.toml or pytest.ini |
| **Quick run command** | `pytest backend/tests/test_tiktok_sync.py -x -v` |
| **Full suite command** | `pytest backend/tests/ -x` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/test_tiktok_sync.py -x -v`
- **After every plan wave:** Run `pytest backend/tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 1 | TKTOK-01 | — | N/A | unit | `pytest backend/tests/test_tiktok_sync.py::test_download_video_asset -xvs` | ❌ W0 | ⬜ pending |
| 15-01-02 | 01 | 1 | TKTOK-01 | — | N/A | unit | `pytest backend/tests/test_tiktok_sync.py::test_download_video_asset_success -xvs` | ❌ W0 | ⬜ pending |
| 15-01-03 | 01 | 1 | TKTOK-02 | — | N/A | unit | `pytest backend/tests/test_tiktok_sync.py::test_download_image_asset -xvs` | ❌ W0 | ⬜ pending |
| 15-01-04 | 01 | 1 | TKTOK-02 | — | N/A | unit | `pytest backend/tests/test_tiktok_sync.py::test_download_image_asset_success -xvs` | ❌ W0 | ⬜ pending |
| 15-01-05 | 01 | 1 | TKTOK-01, TKTOK-02 | — | Download failure must not abort sync | unit | `pytest backend/tests/test_tiktok_sync.py::test_download_failure_resilience -xvs` | ❌ W0 | ⬜ pending |
| 15-01-06 | 01 | 1 | TKTOK-01, TKTOK-02 | — | N/A | unit | `pytest backend/tests/test_tiktok_sync.py::test_skip_existing_asset -xvs` | ❌ W0 | ⬜ pending |
| 15-02-01 | 02 | 2 | TKTOK-01, TKTOK-02 | — | scoring_enabled gate applies to all platforms | integration | `pytest backend/tests/test_scoring_gate.py::test_all_platforms_honor_scoring_enabled -xvs` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_tiktok_sync.py` — stubs for unit tests: `test_download_video_asset`, `test_download_image_asset`, `test_download_failure_resilience`, `test_skip_existing_asset`
- [ ] `backend/tests/test_tiktok_sync.py` — integration coverage via `test_download_video_asset_success` and `test_download_image_asset_success` (harmonizer pipe verified in Plan 02 test_scoring_gate.py)
- [ ] `backend/tests/test_scoring_gate.py` — cross-platform scoring gate test stub: `test_all_platforms_honor_scoring_enabled`
- [ ] Mock httpx responses for TikTok `/file/video/ad/` and `/file/image/ad/` endpoints in test fixtures

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| TikTok video creative plays in dashboard | TKTOK-01 | Requires live TikTok account with video ads | Trigger sync, open dashboard, confirm video plays |
| TikTok image creative shows thumbnail | TKTOK-02 | Requires live TikTok account with image ads | Trigger sync, open dashboard, confirm image visible |
| Spark ad fallback (null asset_url) | TKTOK-01 | Spark ad API endpoint unconfirmed | If Spark ads present, verify asset_url is null (not error) |
| AI autofill processes TikTok video | TKTOK-01 | Requires live scoring pipeline | Trigger autofill, confirm TikTok video processed by Gemini/Whisper |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
