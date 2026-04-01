---
phase: 9
slug: ai-metadata-auto-fill
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-01
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `backend/pytest.ini` or `backend/pyproject.toml` |
| **Quick run command** | `cd backend && python -m pytest tests/test_ai_autofill.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_ai_autofill.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 9-01-01 | 01 | 1 | AI-01 | unit | `pytest tests/test_ai_autofill.py::test_openai_config -xq` | ❌ W0 | ⬜ pending |
| 9-01-02 | 01 | 1 | AI-01 | unit | `pytest tests/test_ai_autofill.py::test_image_download_and_downscale -xq` | ❌ W0 | ⬜ pending |
| 9-01-03 | 01 | 1 | AI-01 | unit | `pytest tests/test_ai_autofill.py::test_whisper_transcription -xq` | ❌ W0 | ⬜ pending |
| 9-01-04 | 01 | 1 | AI-02 | unit | `pytest tests/test_ai_autofill.py::test_gpt4o_vision_inference -xq` | ❌ W0 | ⬜ pending |
| 9-01-05 | 01 | 1 | AI-03 | unit | `pytest tests/test_ai_autofill.py::test_inference_status_guard -xq` | ❌ W0 | ⬜ pending |
| 9-02-01 | 02 | 2 | AI-04 | unit | `pytest tests/test_ai_autofill.py::test_api_trigger_endpoint -xq` | ❌ W0 | ⬜ pending |
| 9-02-02 | 02 | 2 | AI-04 | unit | `pytest tests/test_ai_autofill.py::test_api_result_endpoint -xq` | ❌ W0 | ⬜ pending |
| 9-03-01 | 03 | 3 | AI-05 | manual | — | — | ⬜ pending |
| 9-03-02 | 03 | 3 | AI-06 | manual | — | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_ai_autofill.py` — stubs for AI-01 through AI-04 test cases
- [ ] `backend/tests/conftest.py` — add fixtures for mock OpenAI client, mock MinIO object storage

*Existing pytest infrastructure is present; new test file and fixtures required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Auto-fill toggle + type selector renders on metadata config page; toggling on/off shows/hides type selector; saving persists state | AI-05 | Requires Angular frontend + browser; no headless test infra for Angular in this project | Open metadata config for any field; toggle on; verify type selector appears; select a type; save; reload and verify state persisted |
| InferenceStatusBadge shows correct state (PENDING/COMPLETE/FAILED) after triggering auto-fill; UI polls until COMPLETE | AI-06 | Requires live backend + frontend + real or mocked OpenAI call; E2E browser test | Trigger auto-fill on an asset; verify badge shows PENDING; wait for completion; verify badge shows COMPLETE and metadata fields are pre-populated |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
