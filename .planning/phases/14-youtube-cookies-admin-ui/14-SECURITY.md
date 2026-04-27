---
phase: 14-youtube-cookies-admin-ui
audited: 2026-04-27
threats_total: 14
threats_mitigated: 10
threats_accepted: 4
threats_open: 0
status: secured
---

# Phase 14 Security Audit

## Threat Verification

### Mitigated Threats (10)

| Threat ID | Category | Disposition | Evidence |
|-----------|----------|-------------|----------|
| T-14-01 | Tampering | mitigate | `get_current_user` loads User from DB via JWT `sub` claim; `get_current_superadmin` reads `current_user.is_superuser` from the DB-loaded model, not from JWT claim directly. `deps.py:67-80`. JWT signed HS256 via `create_access_token`. `auth.py:271` |
| T-14-02 | Tampering | mitigate | `UniqueConstraint("singleton_guard", name="uq_system_config_singleton")` on `system_config.py:36-38`. Migration enforces it at DB level: `op.create_unique_constraint("uq_system_config_singleton", ...)` at `x6y7z8a9b0c_...py:36` |
| T-14-03 | EoP | mitigate | `get_current_superadmin` raises `HTTP_403_FORBIDDEN` before any endpoint logic executes at `deps.py:75-79`. No registration path sets `is_superuser`; only the Alembic migration seed does. |
| T-14-05 | Info Disclosure | mitigate | `CookieHealthResponse` Pydantic model at `super_admin.py:45-47` contains only `primary: CookieSlotHealth` and `backup: CookieSlotHealth`. `CookieSlotHealth.status` is `Literal["valid","expired","missing"]` — no string field for cookie content. Decrypted value is only used in-memory for `_check_cookie_health()`. |
| T-14-06 | Info Disclosure | mitigate | PUT endpoint at `super_admin.py:171-177` logs only `"SuperAdmin updated primary YouTube cookie slot (cookie content not logged)"` and `"SuperAdmin updated backup YouTube cookie slot (cookie content not logged)"`. No `payload.primary` or decrypted value is logged at any level. |
| T-14-08 | EoP | mitigate | All five endpoints in `super_admin.py` use `Depends(get_current_superadmin)`. `POST /users/promote` at `super_admin.py:230-261` is gated by this dependency. No self-registration path to SuperAdmin exists in `auth.py`. |
| T-14-10 | Info Disclosure | mitigate | `_get_cookies_from_db` in `dv360_sync.py:1113,1118` logs only `"Failed to decrypt primary YouTube cookie from DB"` and `"Failed to decrypt backup YouTube cookie from DB"` — no cipher text or decrypted content included in log messages. |
| T-14-11 | EoP | mitigate | `IsSuperAdminGuard` at `is-superadmin.guard.ts:14-29` checks `authService.currentUser?.is_superuser` before allowing navigation, redirects to `/` on failure. Route registered with `canActivate: [IsSuperAdminGuard]` at `configuration.routes.ts:29`. API still returns 403 regardless via server-side enforcement. |
| T-14-12 | Info Disclosure | mitigate | `GET /youtube-cookies` returns only `CookieHealthResponse` health status (`super_admin.py:115-149`). Frontend `admin.component.ts:70,100` renders hardcoded bullet characters (`&#x2022;` × 20) — actual cookie content is never sent to frontend. |
| T-14-13 | Tampering | mitigate | `is_superuser` is read from `GET /users/me` response via `loadCurrentUser()` at `auth.service.ts:96-100`, which fetches from the `/auth/me` endpoint backed by the DB model. Not decoded from JWT on the client. |

### Accepted Threats (4)

| Threat ID | Category | Rationale |
|-----------|----------|-----------|
| T-14-04 | Info Disclosure | `is_superuser` boolean in JWT carries no sensitive data. Transmitted over HTTPS only. JWT is signed; boolean cannot be forged. |
| T-14-07 | Tampering | Arbitrary cookie text accepted by PUT endpoint. Invalid cookies result in "missing" health status from expiry check. No server-side format validation by design decision. |
| T-14-09 | DoS | SuperAdmin count is < 10. Bulk insert of < 10 Notification rows per `create_superadmin_notification` call is trivial. No DoS risk. |
| T-14-14 | Info Disclosure | SuperAdmin list (`GET /super-admin/users`) reveals email addresses, but only to users who already have SuperAdmin platform access. Acceptable information disclosure. |

### Unregistered Flags

None. No threat flags were raised in SUMMARY.md `## Threat Flags` sections beyond those mapped to the registered threat register.

## Notes

- T-14-01 has a minor implementation divergence worth noting: the Alembic migration (`x6y7z8a9b0c_...py:50-55`) seeds the SuperAdmin via `INITIAL_SUPERADMIN_EMAIL` env var at migration time rather than hardcoding `s.dettweiler@brainsuite.ai` as specified in the plan. This is a **security improvement** — it avoids hardcoding a specific email in version-controlled migration code. The mitigation intent (no public path sets `is_superuser`) is fully preserved.
- `IsSuperAdminGuard` implements a fresh `loadCurrentUser()` call on cache miss (`is-superadmin.guard.ts:19-29`), which is more robust than the synchronous check specified in the plan. This is a security improvement, not a gap.
