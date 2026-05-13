---
phase: 15
slug: tiktok-asset-download
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-08
audited: 2026-05-13
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
| 15-01-01 | 01 | 1 | TKTOK-01 | — | N/A | unit | `pytest backend/tests/test_tiktok_sync.py::test_download_video_asset_success -xvs` | ✅ | ✅ green |
| 15-01-02 | 01 | 1 | TKTOK-01 | — | N/A | unit | `pytest backend/tests/test_tiktok_sync.py::test_fetch_video_download_url_success -xvs` | ✅ | ✅ green |
| 15-01-03 | 01 | 1 | TKTOK-02 | — | N/A | unit | `pytest backend/tests/test_tiktok_sync.py::test_download_image_asset_success -xvs` | ✅ | ✅ green |
| 15-01-04 | 01 | 1 | TKTOK-02 | — | N/A | unit | `pytest backend/tests/test_tiktok_sync.py::test_download_image_asset_too_small -xvs` | ✅ | ✅ green |
| 15-01-05 | 01 | 1 | TKTOK-01, TKTOK-02 | — | Download failure must not abort sync | unit | `pytest backend/tests/test_tiktok_sync.py::test_download_failure_resilience -xvs` | ✅ | ✅ green |
| 15-01-06 | 01 | 1 | TKTOK-01, TKTOK-02 | — | S3 idempotency — no re-download if exists | unit | `pytest backend/tests/test_tiktok_sync.py::test_skip_existing_asset -xvs` | ✅ | ✅ green |
| 15-01-07 | 01 | 1 | TKTOK-01, TKTOK-02 | D-02 | Spark ads must not trigger any download | unit | `pytest backend/tests/test_tiktok_sync.py::test_spark_ad_skips_download -xvs` | ✅ | ✅ green |
| 15-02-01 | 02 | 2 | TKTOK-01, TKTOK-02 | — | scoring_enabled gate applies to all platforms | integration | `pytest backend/tests/test_scoring_gate.py::test_all_platforms_honor_scoring_enabled -xvs` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `backend/tests/test_tiktok_sync.py` — 12 tests covering all download behaviors (confirmed 2026-05-13)
- [x] `backend/tests/test_tiktok_sync.py` — `test_download_video_asset_success`, `test_download_image_asset_success`, `test_spark_ad_skips_download` all present
- [x] `backend/tests/test_scoring_gate.py` — 10 tests including `test_all_platforms_honor_scoring_enabled` (confirmed 2026-05-13)
- [x] httpx responses mocked inline in each test function (no shared fixture needed)

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

- [x] All tasks have automated verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s (pytest run ~30s in Docker)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** 2026-05-13 (gsd-validate-phase audit)

## Validation Audit 2026-05-13

| Metric | Count |
|--------|-------|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |
| Final test count | 12 (test_tiktok_sync.py) + 10 (test_scoring_gate.py) = 22 |

## Validation Audit 2026-05-13 (re-verify)

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Tests run | 22 (all green, 1.67s) |
| Result | CONFIRMED nyquist_compliant |
