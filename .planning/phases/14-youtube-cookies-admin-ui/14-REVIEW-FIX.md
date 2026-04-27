---
phase: 14-youtube-cookies-admin-ui
fixed_at: 2026-04-27T00:00:00Z
review_path: .planning/phases/14-youtube-cookies-admin-ui/14-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 14: Code Review Fix Report

**Fixed at:** 2026-04-27
**Source review:** .planning/phases/14-youtube-cookies-admin-ui/14-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (2 Critical + 5 Warning)
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01: Migration hardcodes production email as SuperAdmin seed

**Files modified:** `backend/alembic/versions/x6y7z8a9b0c_phase14_system_config_and_superadmin.py`
**Commit:** 17497ad
**Applied fix:** Removed the hardcoded `s.dettweiler@brainsuite.ai` UPDATE from the migration. Added `import os` and replaced the seed block with an env-var-driven conditional: `superadmin_email = os.environ.get("INITIAL_SUPERADMIN_EMAIL")` — the UPDATE only runs when that variable is set. Also replaced `datetime.utcnow()` with `datetime.now(timezone.utc)` (adds `timezone` to the existing import) to fix the deprecated naive UTC datetime used for the singleton row insert.

---

### CR-02: `download_assets_post_commit` checks env-var cookie status, not DB cookies

**Files modified:** `backend/app/services/sync/dv360_sync.py`
**Commit:** 1e60ea6
**Applied fix:** Replaced the `_check_youtube_cookies("YOUTUBE_COOKIES")` / `_check_youtube_cookies("YOUTUBE_COOKIES_BACKUP")` env-var checks with `db_cookies = await self._get_cookies_from_db()` and `can_download_video = len(db_cookies) > 0`. The log message was updated to reflect the DB-aware check result rather than the old env-var status strings.

---

### WR-01: `IsSuperAdminGuard` relies on in-memory user state — no refresh on stale session

**Files modified:** `frontend/src/app/core/guards/is-superadmin.guard.ts`
**Commit:** 71db493
**Applied fix:** Added `Observable`, `of`, `map`, `catchError` imports. Changed `canActivate()` return type to `Observable<boolean> | boolean`. If the in-memory snapshot shows `is_superuser`, returns `true` immediately (fast path). Otherwise calls `authService.loadCurrentUser()` to do a fresh `/auth/me` fetch — maps to `true` on success with `is_superuser`, navigates to `/` and returns `false` otherwise. `catchError` handles network failures gracefully.

---

### WR-02: `refresh` endpoint does not carry `is_superuser` in the new access token

**Files modified:** `backend/app/api/v1/endpoints/auth.py`
**Commit:** 3148f80
**Applied fix:** In `refresh_token()`, added a DB lookup for the user record (`select(User).where(User.id == stored.user_id)`). Both `create_access_token` and `create_refresh_token` now receive `"is_superuser": is_superuser` in the payload, mirroring the login endpoint. Defaults to `False` if the user record is unexpectedly missing.

---

### WR-03: `saveCookie` does not clear textarea content on save error / leaves cookie in memory

**Files modified:** `frontend/src/app/features/configuration/pages/admin.component.ts`
**Commit:** f5ced8d
**Applied fix:** Replaced the `discardEdit(slot)` call followed by separate `saving*=false` in the `next` handler with an inlined simultaneous clear: sets `saving*`, `editing*`, and `new*Cookie` all to their cleared values in one expression per slot. This ensures the raw cookie string is zeroed from component memory atomically at the same moment the spinner is cleared, with no intermediate state where the spinner is still shown but the content persists.

---

### WR-04: `ConfigurationShellComponent` builds nav on `OnInit` — not reactive to user changes

**Files modified:** `frontend/src/app/features/configuration/configuration-shell.component.ts`
**Commit:** cf0a1df
**Applied fix:** Replaced the one-time snapshot read (`this.authService.currentUser?.is_superuser`) with a subscription to `this.authService.currentUser$`. The `navItems` array is now rebuilt reactively whenever the user object changes, so the Admin nav item appears correctly even if the component renders before `/auth/me` completes on app init.

---

### WR-05: `_upsert_records` has a dead `if records:` guard immediately after an earlier identical guard

**Files modified:** `backend/app/services/sync/dv360_sync.py`
**Commit:** d7a51fc
**Applied fix:** Removed the redundant `if records:` wrapper (lines 1312-1315 before fix) in `_upsert_records` — the early-return guard above it already guarantees `records` is non-empty. Applied the same fix to the identical dead guard in `_upsert_conversion_records`. Both `first_row = records[0]` lines are now direct assignments as intended.

---

_Fixed: 2026-04-27_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
