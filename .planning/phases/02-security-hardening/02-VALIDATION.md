---
phase: 2
slug: security-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (>=7.4.0, from requirements.txt) |
| **Config file** | None — Wave 0 creates conftest.py |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full pytest suite green + `cd frontend && npx tsc --noEmit` must pass
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01 | SEC-01 | 0 | SEC-01, QUAL-04 | unit (mock redis) | `pytest tests/test_oauth_session.py -x` | ❌ W0 | ⬜ pending |
| 2-02 | SEC-02 | 0 | SEC-02 | unit (TestClient) | `pytest tests/test_auth_cookie.py -x` | ❌ W0 | ⬜ pending |
| 2-03 | SEC-03 | 0 | SEC-03 | unit | `pytest tests/test_startup_validation.py -x` | ❌ W0 | ⬜ pending |
| 2-04 | SEC-04 | 0 | SEC-04 | unit (mock obj storage) | `pytest tests/test_path_traversal.py -x` | ❌ W0 | ⬜ pending |
| 2-05 | SEC-05 | 0 | SEC-05 | unit | `pytest tests/test_redirect_uri.py -x` | ❌ W0 | ⬜ pending |
| 2-06 | SEC-06 | 1 | SEC-06 | manual / env check | inspect `.env.example` | N/A | ⬜ pending |
| 2-07 | QUAL-01 | 1 | QUAL-01 | static analysis | `pytest tests/test_exception_audit.py -x` | ❌ W0 | ⬜ pending |
| 2-08 | QUAL-02 | 1 | QUAL-02 | build | `cd frontend && npx tsc --noEmit --strict` | ❌ (config check) | ⬜ pending |
| 2-09 | QUAL-03 | 1 | QUAL-03 | unit (TestClient) | `pytest tests/test_error_shapes.py -x` | ❌ W0 | ⬜ pending |
| 2-10 | QUAL-04 | 0 | QUAL-04 | unit (mock redis) | covered in SEC-01 test | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/conftest.py` — shared fixtures (FastAPI TestClient, mock redis, mock settings)
- [ ] `backend/tests/test_oauth_session.py` — stubs for SEC-01, QUAL-04
- [ ] `backend/tests/test_auth_cookie.py` — stubs for SEC-02
- [ ] `backend/tests/test_startup_validation.py` — stubs for SEC-03
- [ ] `backend/tests/test_path_traversal.py` — stubs for SEC-04
- [ ] `backend/tests/test_redirect_uri.py` — stubs for SEC-05
- [ ] `backend/tests/test_error_shapes.py` — stubs for QUAL-03
- [ ] `backend/tests/test_exception_audit.py` — AST-based static check for QUAL-01

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `BACKEND_CORS_ORIGINS` env var documented; no wildcard default | SEC-06 | Config/docs check, not runtime behavior | Inspect `.env.example` — verify `BACKEND_CORS_ORIGINS` key present with example value, no `*` default |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
