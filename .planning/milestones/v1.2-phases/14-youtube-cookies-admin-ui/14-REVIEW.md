---
phase: 14-youtube-cookies-admin-ui
reviewed: 2026-04-27T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - backend/app/models/system_config.py
  - backend/alembic/versions/x6y7z8a9b0c_phase14_system_config_and_superadmin.py
  - backend/app/api/v1/deps.py
  - backend/app/api/v1/endpoints/auth.py
  - backend/app/schemas/user.py
  - backend/app/api/v1/endpoints/super_admin.py
  - backend/app/api/v1/__init__.py
  - backend/app/services/notifications.py
  - backend/app/services/sync/dv360_sync.py
  - frontend/src/app/core/guards/is-superadmin.guard.ts
  - frontend/src/app/features/configuration/pages/admin.component.ts
  - frontend/src/app/core/services/auth.service.ts
  - frontend/src/app/features/configuration/configuration-shell.component.ts
  - frontend/src/app/features/configuration/configuration.routes.ts
  - frontend/src/app/core/layout/header/header.component.ts
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-04-27
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Phase 14 introduces the `system_config` singleton table for encrypted YouTube cookie storage, a SuperAdmin RBAC layer, five new backend endpoints, and an Angular admin UI component. The overall design is sound: the singleton pattern is correctly DB-enforced, cookies are never returned in API responses, and the `is_superuser` flag propagates correctly through the JWT, `/me` endpoint, and Angular guard.

Two critical issues were found. First, the Alembic migration hardcodes a production email address as a SuperAdmin seed — this will fail silently in non-production environments and expose the email in version-controlled migration history as a security concern. Second, `download_assets_post_commit` in `dv360_sync.py` checks cookie validity against env vars only, not the DB; if cookies have been migrated to DB-only storage the code will always consider cookies missing and always log false-positive warnings and fire `COOKIE_FAILED` notifications.

Five warnings cover logic errors and unhandled edge cases; four info items cover minor quality issues.

---

## Critical Issues

### CR-01: Migration hardcodes production email as SuperAdmin seed

**File:** `backend/alembic/versions/x6y7z8a9b0c_phase14_system_config_and_superadmin.py:49-53`

**Issue:** The `upgrade()` function runs `UPDATE users SET is_superuser = true WHERE email = 's.dettweiler@brainsuite.ai'`. This silently does nothing on any non-production database (staging, CI, local) because that user does not exist, meaning developers end up with zero SuperAdmins and cannot reach the admin endpoints at all. Beyond the operational gap, embedding a specific personal email in a committed migration file exposes it permanently in git history and is an unconventional pattern that conflicts with environment-agnostic migration hygiene.

**Fix:** Remove the seed from the migration. The initial SuperAdmin should be set via an env-var-driven seed script or a one-off CLI command that runs at deploy time, not baked into a schema migration. If the seed must stay in the migration for production bootstrap purposes, wrap it in a conditional or move it to a separate `data_seed.py` script outside of Alembic:

```python
# In upgrade(): replace hardcoded email with env-var lookup
import os
superadmin_email = os.environ.get("INITIAL_SUPERADMIN_EMAIL")
if superadmin_email:
    conn.execute(
        sa.text("UPDATE users SET is_superuser = true WHERE email = :email"),
        {"email": superadmin_email},
    )
```

---

### CR-02: `download_assets_post_commit` checks env-var cookie status, not DB cookies

**File:** `backend/app/services/sync/dv360_sync.py:1678-1687`

**Issue:** `download_assets_post_commit` calls `self._check_youtube_cookies("YOUTUBE_COOKIES")` and `self._check_youtube_cookies("YOUTUBE_COOKIES_BACKUP")` to decide whether video downloads are possible and whether to log a "both cookie sets expired/missing" warning. However, Phase 14's whole point is that cookies now live in the DB, not env vars. `_check_youtube_cookies` reads from `os.environ` only. The actual download path (`_download_video_asset` → `_get_cookies_from_db`) correctly reads from DB first, so downloads may succeed — but `download_assets_post_commit` will log `"Both cookie sets expired/missing"` and set `can_download_video = False`, skipping the video download loop entirely (line 1730 re-checks the same flag) for any installation where DB cookies are present but env vars are absent.

```python
# Lines 1678-1687 — env-var-only check, wrong after DB migration
primary_status = self._check_youtube_cookies("YOUTUBE_COOKIES")
backup_status = self._check_youtube_cookies("YOUTUBE_COOKIES_BACKUP")
can_download_video = primary_status == "valid" or backup_status == "valid"
```

The flag `can_download_video` gates the entire video download loop at line 1730 (`if not can_download_video: logger.warning(...)` then continues into the loop anyway — actually the loop does run — but the warning is misleading and the logic at line 1686-1687 is the wrong signal). More importantly the check at line 1680 is used for logging and the "skip" warning, and the `COOKIE_FAILED` notification may fire redundantly.

**Fix:** Replace the env-var check with a DB-aware check that mirrors `_get_cookies_from_db` logic:

```python
# In download_assets_post_commit, replace the env-var cookie check:
db_cookies = await self._get_cookies_from_db()
can_download_video = len(db_cookies) > 0
```

---

## Warnings

### WR-01: `IsSuperAdminGuard` relies on in-memory user state — no refresh on stale session

**File:** `frontend/src/app/core/guards/is-superadmin.guard.ts:12-13`

**Issue:** `canActivate()` reads `this.authService.currentUser?.is_superuser` directly. If the user was granted SuperAdmin after their last login (i.e., the user object in memory was loaded before the promotion), `is_superuser` will be `false` even though the account is now a SuperAdmin. The guard will deny access and redirect to `/` with no explanation. The backend will correctly enforce the check, but the user is left unable to reach the admin page until they manually log out and back in.

**Fix:** Either reload the current user before checking, or display an error message rather than silently redirecting to root:

```typescript
canActivate(): Observable<boolean> | boolean {
  if (this.authService.currentUser?.is_superuser) {
    return true;
  }
  // Attempt a fresh load before denying
  return this.authService.loadCurrentUser().pipe(
    map(user => {
      if (user.is_superuser) return true;
      this.router.navigate(['/']);
      return false;
    }),
    catchError(() => {
      this.router.navigate(['/']);
      return of(false);
    }),
  );
}
```

---

### WR-02: `refresh` endpoint does not carry `is_superuser` in the new access token

**File:** `backend/app/api/v1/endpoints/auth.py:329`

**Issue:** When the `/auth/refresh` endpoint issues a new access token it calls `create_access_token({"sub": user_id})` — without the `is_superuser` claim. By contrast, the `/auth/login` endpoint at line 271 includes `"is_superuser": user.is_superuser` in the token payload. After a token rotation any backend middleware or service that reads the `is_superuser` JWT claim directly (rather than fetching from the DB via `get_current_user`) will see the claim as absent/falsy. If future code ever short-circuits the DB lookup and checks the claim directly, a SuperAdmin's promoted status would be silently dropped after the first token refresh.

**Fix:** Mirror the login call in the refresh path:

```python
# In refresh_token(), replace lines 329-330:
result = await db.execute(select(User).where(User.id == stored.user_id))
user = result.scalar_one_or_none()
new_access = create_access_token({"sub": user_id, "is_superuser": user.is_superuser if user else False})
new_refresh = create_refresh_token({"sub": user_id, "is_superuser": user.is_superuser if user else False})
```

---

### WR-03: `saveCookie` does not clear textarea content on save error

**File:** `frontend/src/app/features/configuration/pages/admin.component.ts:407-412`

**Issue:** In the `error` callback of `saveCookie`, the saving flag is cleared and a snackbar is shown, but `editingPrimary`/`editingBackup` and `newPrimaryCookie`/`newBackupCookie` are not reset. This is correct UX — the user should be able to retry — however `discardEdit` on a successful save (line 402) also clears the textarea, meaning the cookie content lives in `newPrimaryCookie` as a plain string in component memory until the user explicitly discards. This is a security hygiene issue: for the duration of the component lifecycle after a successful save the raw cookie string remains in Angular's component state. On a failed save it stays there indefinitely.

**Fix:** Zero out the cookie string from memory as soon as it is no longer needed:

```typescript
next: (updated) => {
  this.cookieHealth = updated;
  if (slot === 'primary') { this.savingPrimary = false; this.editingPrimary = false; this.newPrimaryCookie = ''; }
  else { this.savingBackup = false; this.editingBackup = false; this.newBackupCookie = ''; }
  this.snackBar.open('Cookie updated successfully.', 'Close', { duration: 3000 });
},
```

(Note: `discardEdit` already does this zeroing; the issue is that `savingPrimary = false` is set after `discardEdit`, meaning the spinner is still rendered briefly while memory still holds the content. Inline the clear instead of calling `discardEdit` first.)

---

### WR-04: `ConfigurationShellComponent` builds nav on `OnInit` — not reactive to user changes

**File:** `frontend/src/app/features/configuration/configuration-shell.component.ts:73-78`

**Issue:** `ngOnInit` reads `this.authService.currentUser?.is_superuser` once and builds `navItems`. If the current user object is loaded asynchronously (e.g., the shell component renders before `/auth/me` completes on app init), `is_superuser` will be `undefined` at init time and the Admin nav item will never appear even for genuine SuperAdmins, requiring a full page refresh. This differs from the guard which also has the same snapshot issue (WR-01) but at least triggers a re-check on navigation.

**Fix:** Subscribe to `currentUser$` instead of reading the snapshot:

```typescript
ngOnInit(): void {
  this.authService.currentUser$.subscribe(user => {
    this.navItems = [...this.baseNavItems];
    if (user?.is_superuser) {
      this.navItems.push({ path: 'admin', label: 'Admin', icon: 'shield-lock' });
    }
  });
}
```

---

### WR-05: `_upsert_records` has a dead `if records:` guard immediately after an earlier identical guard

**File:** `backend/app/services/sync/dv360_sync.py:1319-1322`

**Issue:** Lines 1315-1317 return early if `not records`. Line 1319 then checks `if records:` again before accessing `records[0]`. The second check is unreachable dead code that suggests the original early-return guard was added later as a patch without cleaning up the redundant branch. This is a minor logic smell, but if someone refactors the early return away the inner `if records:` guard masks the fact that `records[0]` would be accessed on an empty list without it.

**Fix:** Remove the redundant `if records:` wrapper on line 1319; the code inside it is already guaranteed to run only when `records` is non-empty:

```python
# Remove lines 1319-1322 wrapper, keep only the body:
first_row = records[0]
csv_columns = list(first_row.keys())
logger.info(f"DV360 perf CSV columns ({len(csv_columns)}): {csv_columns}")
```

The same pattern appears in `_upsert_conversion_records` at lines 1795-1798.

---

## Info

### IN-01: `datetime.utcnow()` is deprecated — migration uses naive UTC datetime

**File:** `backend/alembic/versions/x6y7z8a9b0c_phase14_system_config_and_superadmin.py:39`

**Issue:** `datetime.utcnow()` is deprecated since Python 3.12 and returns a naive (timezone-unaware) datetime. The `system_config` table columns are `DateTime(timezone=True)`, so storing a naive datetime here may produce a warning or behave inconsistently depending on the DB driver and SQLAlchemy version.

**Fix:**
```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

---

### IN-02: `_check_cookie_health` uses `datetime.now()` (local time) instead of UTC

**File:** `backend/app/api/v1/endpoints/super_admin.py:89`

**Issue:** `now_ts = datetime.now().timestamp()` uses local system time. `datetime.now()` returns local time, and `.timestamp()` converts it to a Unix timestamp correctly — but this is fragile: if the server's local timezone is misconfigured the expiry comparison will be off. The sibling method `_check_youtube_cookies` in `dv360_sync.py` line 1054 has the same pattern. Since Netscape cookie expiry values are Unix timestamps (UTC-based), using `datetime.now(timezone.utc).timestamp()` is strictly correct and self-documenting.

**Fix:**
```python
from datetime import timezone
now_ts = datetime.now(timezone.utc).timestamp()
```

---

### IN-03: `promote_user` endpoint does not deactivate or re-check the promoted user's `is_active` status

**File:** `backend/app/api/v1/endpoints/super_admin.py:250`

**Issue:** The `promote_user` endpoint sets `is_superuser = True` without checking `user.is_active`. It is possible to promote an inactive (disabled or pending-join) account to SuperAdmin. Such a user cannot log in (the login endpoint blocks inactive users), but the data is inconsistent and could be confusing. There is no security risk because inactive users cannot obtain tokens, but the 409 guard only checks `is_superuser`, not `is_active`.

**Fix:** Add an active check before promotion:
```python
if not user.is_active:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot promote an inactive user")
```

---

### IN-04: `admin.component.ts` — `loadingAdmins` and `loadingOrgs` flags are set but never read in the template

**File:** `frontend/src/app/features/configuration/pages/admin.component.ts:375, 383`

**Issue:** The component sets `loadingAdmins` and `loadingOrgs` flags (lines 340-341, 375-376, 383-384), but the template for the SuperAdmin and Organizations sections does not use them — there are no skeleton loaders or spinners for those sections. Only `loadingCookies` is consumed in the template (line 51). The unused flags are dead state.

**Fix:** Either add skeleton blocks to those sections (consistent with the cookie section's UX), or remove the unused flags to avoid confusion:
```typescript
// If adding skeletons, use in template:
// <div *ngIf="loadingAdmins" class="skeleton-block"></div>

// Or simply remove the flags and inline the assignments:
// this.api.get<SuperAdminUser[]>('/super-admin/users').subscribe({ next: (data) => { this.superAdmins = data; }, ... });
```

---

_Reviewed: 2026-04-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
