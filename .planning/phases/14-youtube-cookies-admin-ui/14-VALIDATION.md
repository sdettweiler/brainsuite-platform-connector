---
phase: 14
slug: youtube-cookies-admin-ui
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-24
audited: 2026-04-27
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
| 14-01-01 | 01 | 1 | COOK-01 | T-14-01 | is_superuser check raises 403 if false | unit | `pytest tests/test_super_admin_deps.py -x -q` | ✅ | ✅ green |
| 14-01-02 | 01 | 1 | COOK-01 | T-14-01 | JWT includes is_superuser claim | unit | `pytest tests/test_auth_cookie.py::test_jwt_superuser_claim -x -q` | ✅ | ✅ green |
| 14-02-01 | 02 | 1 | COOK-02 | T-14-02 | system_config singleton enforced by unique constraint | unit | `pytest tests/test_system_config.py -x -q` | ✅ | ✅ green |
| 14-02-02 | 02 | 1 | COOK-02 | T-14-05 | Cookies encrypted at rest (Fernet) | unit | `pytest tests/test_system_config.py::test_cookie_encryption -x -q` | ✅ | ✅ green |
| 14-02-03 | 02 | 2 | COOK-02 | T-14-05 | GET endpoint returns health status, not plaintext | unit | `pytest tests/test_super_admin_endpoints.py::test_get_cookies_no_plaintext -x -q` | ✅ | ✅ green |
| 14-02-04 | 02 | 2 | COOK-02 | — | PUT endpoint updates slot and returns health | unit | `pytest tests/test_super_admin_endpoints.py::test_put_cookies -x -q` | ✅ | ✅ green |
| 14-03-01 | 03 | 2 | COOK-02 | T-14-10 | dv360_sync reads from DB, falls back to env vars | unit | `pytest tests/test_dv360_sync.py::test_get_cookies_from_db -x -q` | ✅ | ✅ green |
| 14-03-02 | 03 | 3 | COOK-03 | — | COOKIE_FAILED notification sent to all SuperAdmins | unit | `pytest tests/test_notifications.py::test_superadmin_notification -x -q` | ✅ | ✅ green |
| 14-04-01 | 03 | 3 | COOK-01 | T-14-11 | Admin route guarded by IsSuperAdminGuard | manual | Angular guard: navigate to /configuration/admin as non-superadmin → redirect | N/A | ✅ manual |
| 14-04-02 | 03 | 3 | COOK-01 | — | Admin nav item hidden for non-SuperAdmins | manual | Login as non-superadmin → Admin nav item not visible in sidebar | N/A | ✅ manual |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `backend/tests/test_super_admin_deps.py` — COOK-01 SuperAdmin dependency 403 guard
- [x] `backend/tests/test_system_config.py` — COOK-02 system_config singleton + Fernet encryption
- [x] `backend/tests/test_super_admin_endpoints.py` — COOK-02 GET/PUT cookie endpoints
- [x] `backend/tests/test_dv360_sync.py` — COOK-02 DB-backed cookie reading with env var fallback
- [x] `backend/tests/test_notifications.py` — COOK-03 SuperAdmin notification fan-out (extended)
- [x] `backend/tests/test_auth_cookie.py` — JWT is_superuser claim (extended)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Admin route guard redirects non-SuperAdmin | COOK-01 | Angular route guards require browser E2E | Login as non-superadmin user, navigate to /configuration/admin, verify redirect |
| Admin nav item hidden for non-SuperAdmin | COOK-01 | Angular template rendering requires browser | Login as non-superadmin, verify "Admin" nav item is not visible in sidebar |
| Cookie reveal/replace UX (masked input) | COOK-02 | Angular component interaction | Login as SuperAdmin, go to YouTube Cookies section, verify •••• masking and Replace button work |
| SuperAdmin promote user flow | COOK-01 | Full flow requires UI + API integration | Login as SuperAdmin, enter email in Promote User input, verify success/error response |

---

## Validation Audit 2026-04-27

| Metric | Count |
|--------|-------|
| Gaps found | 8 |
| Resolved (automated) | 8 |
| Escalated to manual | 0 |

---

## Validation Sign-Off

- [x] All tasks have automated verify or manual justification
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** 2026-04-27 (Nyquist auditor)
