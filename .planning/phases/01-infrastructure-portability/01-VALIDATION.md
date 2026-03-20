---
phase: 1
slug: infrastructure-portability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) |
| **Config file** | `backend/pytest.ini` or `backend/pyproject.toml` — Wave 0 installs if missing |
| **Quick run command** | `cd backend && pytest tests/test_storage.py -q` |
| **Full suite command** | `cd backend && pytest -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_storage.py -q`
- **After every plan wave:** Run `cd backend && pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| storage-01 | storage | 1 | INFRA-04, INFRA-05 | unit | `pytest tests/test_storage.py::test_upload_file -q` | ❌ W0 | ⬜ pending |
| storage-02 | storage | 1 | INFRA-04, INFRA-05 | unit | `pytest tests/test_storage.py::test_signed_url -q` | ❌ W0 | ⬜ pending |
| compose-01 | compose | 1 | INFRA-01, INFRA-06 | integration | `docker compose config --quiet` | ✅ | ⬜ pending |
| compose-02 | compose | 1 | INFRA-02 | integration | `docker compose -f docker-compose.yml config --quiet` | ✅ | ⬜ pending |
| setup-01 | setup | 2 | INFRA-07, INFRA-08 | integration | `python scripts/setup.py --dry-run` | ❌ W0 | ⬜ pending |
| config-01 | config | 1 | INFRA-03 | unit | `pytest tests/test_config.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_storage.py` — stubs for INFRA-04, INFRA-05 (boto3 client, upload, download, signed URL, list, delete methods)
- [ ] `backend/tests/test_config.py` — stubs for INFRA-03 (no Replit env vars required at startup, BASE_URL env var works)
- [ ] `scripts/setup.py --dry-run` support — dry run flag for CI/test validation of setup script
- [ ] pytest installed in `backend/requirements.txt` if missing

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docker compose up` starts full stack successfully | INFRA-01 | Requires Docker daemon running locally | Run `docker compose up`, verify all services healthy in `docker ps` |
| MinIO bucket accessible at `http://localhost:9001` | INFRA-04 | Requires running Docker stack | Open MinIO console, verify bucket exists |
| `make dev` auto-creates `.env` when missing | INFRA-08 | Requires interactive terminal | Delete `.env`, run `make dev`, verify setup prompt appears |
| New developer onboarding end-to-end | INFRA-07, INFRA-08 | Full workflow test | Fresh clone → `make dev` → verify `.env` generated, stack starts |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
