---
phase: 5
slug: brainsuite-image-scoring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) / Angular Karma/Jasmine (frontend) |
| **Config file** | `backend/pytest.ini` or `backend/pyproject.toml` |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 0 | IMG-01 | manual | Discovery spike script | ❌ W0 | ⬜ pending |
| 5-01-02 | 01 | 1 | IMG-02 | unit | `pytest tests/test_scoring_routing.py` | ❌ W0 | ⬜ pending |
| 5-02-01 | 02 | 1 | IMG-03 | unit | `pytest tests/test_brainsuite_static.py` | ❌ W0 | ⬜ pending |
| 5-02-02 | 02 | 2 | IMG-03 | integration | `pytest tests/test_scoring_batch.py` | ❌ W0 | ⬜ pending |
| 5-03-01 | 03 | 2 | IMG-04 | manual | Browser — image asset score badge visible | manual | ⬜ pending |
| 5-04-01 | 04 | 1 | PROD-01 | manual | Submit real image via script, confirm 200 | manual | ⬜ pending |
| 5-04-02 | 04 | 1 | PROD-02 | manual | Google Cloud Console verification | manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_scoring_routing.py` — stubs for IMG-02 (ScoringEndpointType lookup table)
- [ ] `backend/tests/test_brainsuite_static.py` — stubs for BrainSuiteStaticScoreService unit tests
- [ ] `backend/tests/test_scoring_batch.py` — stubs for scheduler batch branch (image path)
- [ ] `backend/tests/conftest.py` — shared fixtures (if not present); mock httpx clients for BrainSuite API

*Existing pytest infrastructure assumed present from Phase 3.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Discovery spike: Static API auth + response shape | IMG-01 | Requires live BrainSuite credentials; output shape not in docs | Run spike script, capture full JSON response, log in BRAINSUITE_API.md |
| Image creative shows score badge after scheduler tick | IMG-03, IMG-04 | End-to-end flow requires running Docker Compose + scheduler | Start app, upload/sync a META IMAGE creative, wait 15 min, check dashboard |
| CE tab populates for image creative | IMG-04 | Frontend rendering — Angular Karma tests don't cover the full dialog flow easily | Open asset detail dialog for scored image, verify CE tab present |
| UNSUPPORTED tooltip shown on TikTok image | IMG-02, IMG-03 | Browser interaction | Add TikTok image creative, hover score dash, verify tooltip text |
| Existing video scoring unaffected | IMG-03 | Regression | Run video creative through scheduler, confirm COMPLETE status |
| Production creds authenticate Static endpoint | PROD-01 | Requires production env credentials | Run spike with production BRAINSUITE_CLIENT_ID/SECRET |
| Google Ads OAuth consent screen "Published" | PROD-02 | Google Cloud Console UI check | Navigate to APIs & Services > OAuth consent screen, verify status |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
