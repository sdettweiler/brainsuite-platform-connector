---
phase: 14
slug: youtube-cookies-admin-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-24
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) / Karma+Jasmine (Angular frontend) |
| **Config file** | `backend/pytest.ini` or `backend/setup.cfg` |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ && cd ../frontend && ng test --watch=false` |
| **Estimated runtime** | ~30 seconds (backend), ~60 seconds (frontend) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ && cd ../frontend && ng test --watch=false`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (backend quick run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | COOK-01 | T-14-01 | is_superuser check raises 403 if false | unit | `pytest tests/test_super_admin_deps.py -x -q` | ❌ W0 | ⬜ pending |
| 14-01-02 | 01 | 1 | COOK-01 | T-14-02 | JWT includes is_superuser claim | unit | `pytest tests/test_auth.py::test_jwt_superuser_claim -x -q` | ❌ W0 | ⬜ pending |
| 14-02-01 | 02 | 1 | COOK-02 | T-14-03 | system_config singleton enforced by unique constraint | unit | `pytest tests/test_system_config.py -x -q` | ❌ W0 | ⬜ pending |
| 14-02-02 | 02 | 1 | COOK-02 | T-14-04 | Cookies encrypted at rest (Fernet) | unit | `pytest tests/test_system_config.py::test_cookie_encryption -x -q` | ❌ W0 | ⬜ pending |
| 14-02-03 | 02 | 2 | COOK-02 | — | GET endpoint returns health status, not plaintext | unit | `pytest tests/test_super_admin_endpoints.py::test_get_cookies_no_plaintext -x -q` | ❌ W0 | ⬜ pending |
| 14-02-04 | 02 | 2 | COOK-02 | — | PUT endpoint updates slot and returns health | unit | `pytest tests/test_super_admin_endpoints.py::test_put_cookies -x -q` | ❌ W0 | ⬜ pending |
| 14-03-01 | 03 | 2 | COOK-02 | — | dv360_sync reads from DB, falls back to env vars | unit | `pytest tests/test_dv360_sync.py::test_get_cookies_from_db -x -q` | ❌ W0 | ⬜ pending |
| 14-03-02 | 03 | 3 | COOK-03 | — | COOKIE_FAILED notification sent to all SuperAdmins | unit | `pytest tests/test_notifications.py::test_superadmin_notification -x -q` | ❌ W0 | ⬜ pending |
| 14-04-01 | 04 | 3 | COOK-01 | — | Admin route guarded by isSuperAdminGuard | manual | Angular guard: navigate to /configuration/admin as non-superadmin → 403/redirect | N/A | ⬜ pending |
| 14-04-02 | 04 | 3 | COOK-01 | — | Admin nav item hidden for non-SuperAdmins | manual | Login as non-superadmin → Admin nav item not visible | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_super_admin_deps.py` — stubs for COOK-01 SuperAdmin dependency
- [ ] `backend/tests/test_system_config.py` — stubs for COOK-02 system_config model + encryption
- [ ] `backend/tests/test_super_admin_endpoints.py` — stubs for COOK-02 GET/PUT cookie endpoints
- [ ] `backend/tests/test_dv360_sync.py` — stubs for COOK-02 DB-backed cookie reading
- [ ] `backend/tests/test_notifications.py` — stubs for COOK-03 SuperAdmin notification fan-out
- [ ] `backend/tests/test_auth.py` — extend with JWT is_superuser claim test

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Admin route guard redirects non-SuperAdmin | COOK-01 | Angular route guards require browser E2E | Login as non-superadmin user, navigate to /configuration/admin, verify redirect |
| Admin nav item hidden for non-SuperAdmin | COOK-01 | Angular template rendering requires browser | Login as non-superadmin, verify "Admin" nav item is not visible in sidebar |
| Cookie reveal/replace UX (masked input) | COOK-02 | Angular component interaction | Login as SuperAdmin, go to YouTube Cookies section, verify •••• masking and Reveal/Replace buttons work |
| SuperAdmin promote user flow | COOK-01 | Full flow requires UI + API integration | Login as SuperAdmin, enter email in Promote User input, verify success/error response |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
