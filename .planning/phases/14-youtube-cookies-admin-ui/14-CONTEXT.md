# Phase 14: YouTube Cookies Admin UI - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 14 delivers three tightly-coupled capabilities under a new SuperAdmin role:

1. **SuperAdmin role + Admin nav** — Introduce a `SuperAdmin` user type using the existing `User.is_superuser` column. Seed `s.dettweiler@brainsuite.ai` as the sole SuperAdmin. Add a new "Admin" top-level nav item under Configuration, visible only to SuperAdmins. The Admin section contains three sub-sections: YouTube Cookies, SuperAdmin Management, and Organization List.

2. **YouTube Cookies system-global management** — Store primary + backup YouTube/DV360 cookies in a new `system_config` singleton DB table (encrypted at rest). SuperAdmins can view, replace, and monitor cookie health from the Admin UI without restarting Docker. `dv360_sync.py` reads cookies from the DB instead of env vars. On download failure when all cookie slots are exhausted/expired, a `COOKIE_FAILED` notification fires to all SuperAdmins.

3. **SuperAdmin management UI** — List all SuperAdmins on the platform and promote existing users to SuperAdmin by email lookup.

4. **Organization list (read-only)** — SuperAdmin-only read-only table showing all organizations: name, slug, user count, created date. No create/delete in Phase 14.

**Not in Phase 14:** Org creation/deletion, per-org cookie overrides, proactive cookie expiry warnings.

</domain>

<decisions>
## Implementation Decisions

### SuperAdmin Role
- **D-01:** Use the existing `User.is_superuser` (Boolean, already in schema) as the SuperAdmin flag — no new column or model change needed. The column is already present but unused for product features.
- **D-02:** Seed `s.dettweiler@brainsuite.ai` as `is_superuser=True` via an Alembic data migration (UPDATE users SET is_superuser=true WHERE email='s.dettweiler@brainsuite.ai').
- **D-03:** New `get_current_superadmin` dependency in `deps.py`: checks `current_user.is_superuser`, raises 403 "SuperAdmin privileges required" if not. Pattern: mirrors `get_current_admin` but simpler — no OrganizationRole query needed.
- **D-04:** Only SuperAdmins can promote other users to SuperAdmin. Promotion endpoint: `POST /api/v1/super-admin/users/promote` body: `{email: str}`. Returns 404 if user not found, 409 if already SuperAdmin.
- **D-05:** `is_superuser` must be added to the JWT access token claims (alongside existing `sub`) and to the `/users/me` response so Angular can gate the Admin menu without an extra API call.

### System Config Singleton Table
- **D-06:** New `system_config` table with a single guaranteed row. Columns: `id` (UUID PK), `singleton_guard` (VARCHAR(1), UNIQUE, DEFAULT 'X') — unique constraint on this column enforces exactly one row, `youtube_cookies_encrypted` (Text, nullable), `youtube_cookies_backup_encrypted` (Text, nullable), `created_at`, `updated_at`.
- **D-07:** Cookies are encrypted at rest using the same Fernet key as `client_secret_encrypted` in `OrgBrainsuiteConfig`. Use the same encryption helper from `backend/app/core/security.py`.
- **D-08:** Alembic migration creates the `system_config` table and inserts the default singleton row in the same migration.

### YouTube Cookie Endpoints (SuperAdmin-only)
- **D-09:** `GET /api/v1/super-admin/youtube-cookies` — returns cookie health status per slot without revealing cookie content: `{primary: {status: "valid"|"expired"|"missing"}, backup: {status: "valid"|"expired"|"missing"}}`. Uses existing `_check_youtube_cookies()` logic applied to decrypted DB values.
- **D-10:** `PUT /api/v1/super-admin/youtube-cookies` — body: `{primary?: str, backup?: str}`. Updates whichever slots are provided (null/absent = keep existing). Encrypts and saves. Returns same health status response as GET. Validation: run expiry check after save and include result in response.

### dv360_sync.py Cookie Reading
- **D-11:** Replace `_get_cookie_env_vars_to_try()` with an async `_get_cookies_from_db()` method that queries the `system_config` row and returns a list of decrypted cookie strings (primary first, then backup) for valid slots. Fall through to env var (`YOUTUBE_COOKIES`, `YOUTUBE_COOKIES_BACKUP`) if the DB row has no cookies — graceful migration path.
- **D-12:** When `_download_video_asset()` fails after exhausting all cookie slots (DB + env var fallback), fire `create_superadmin_notification(type="COOKIE_FAILED", ...)`. This requires a new `create_superadmin_notification()` function targeting all `User.is_superuser=True` users (not org-scoped — system-wide).
- **D-13:** Notification payload: `{type: "COOKIE_FAILED", title: "YouTube cookies failed", message: "yt-dlp download failed for asset {ad_id} — all cookie slots exhausted or expired. Update cookies in Admin settings.", data: {"deeplink": "/configuration/admin/youtube-cookies"}}`.

### Admin Section UI
- **D-14:** New Angular route `/configuration/admin` with `AdminComponent`. The Configuration sidebar adds an "Admin" nav item visible only when `authService.currentUser?.is_superuser === true`. Route guard: `isSuperAdminGuard` using the same `is_superuser` flag.
- **D-15:** Admin page has three distinct sections using the existing `config-section` card layout:
  - **YouTube Cookies** — primary + backup slot cards with health badge (VALID / EXPIRED / MISSING), masked cookie display (•••••••••• [Reveal] [Replace]), expiry-based status loaded on page open and refreshed after save.
  - **SuperAdmin Management** — table listing all SuperAdmins (email, name, joined date), plus "Promote User" input (email text field + "Promote" button).
  - **Organization List** — read-only table: org name, slug, user count, created date.

### Cookie Input UX
- **D-16:** Cookie content is masked after save: shown as `••••••••••••••••••••` with a "Reveal" toggle (same pattern as Client Secret in Phase 12). A "Replace" button swaps the masked display for a large `<textarea>` pre-filled with nothing — admin pastes new Netscape cookie text then clicks Save.
- **D-17:** Health badge uses the expiry-based check (`_check_youtube_cookies()` logic) run server-side on PUT and on GET page load. No live yt-dlp test — purely expiry timestamp parsing.

### Claude's Discretion
- Exact column type for `youtube_cookies_encrypted` — Text vs VARCHAR(10000). Use Text since cookies can be large multi-KB strings.
- Whether to add `is_superuser` to the existing login response DTO or create a separate `/users/me` endpoint. Check if `/users/me` already exists; if so, add field there. If not, add to the login response.
- Angular component split: one `AdminComponent` with three internal sections, or three separate page components routed under `/configuration/admin/*`. Use the simpler single-component approach unless the org list needs lazy loading.
- Whether to include the COOKIE_FAILED notification deeplink routing in the Angular notification handler (the bell `data.deeplink` field). If the notification handler already supports deeplinks from Phase 10, wire it there; otherwise, just surface the raw message.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Auth & Role Model
- `backend/app/models/user.py` — `User.is_superuser` field (line 39), `OrganizationRole` model; is_superuser already present, unused
- `backend/app/api/v1/deps.py` — `get_current_admin` pattern (lines 46–64) to mirror for `get_current_superadmin`; also note `get_current_admin` already grants access if `is_superuser` — do not break this behavior
- `backend/app/core/security.py` — `create_access_token()` (line 36); JWT currently only encodes `{"sub": user_id}` — must add `is_superuser` claim

### Encryption Pattern
- `backend/app/models/brainsuite_config.py` — `client_secret_encrypted` (String(1000), Fernet); use same encryption helper for cookie columns, but use `Text` type (not String) since cookies are larger

### Cookie Logic to Migrate
- `backend/app/services/sync/dv360_sync.py` — `_check_youtube_cookies()` (line 1048), `_get_cookie_env_vars_to_try()` (line 1076), `_download_video_asset()` (line 1087); these methods become the DB-backed equivalents

### Notification Service
- `backend/app/services/notifications.py` — `create_org_notification()` (line 25); mirrors the pattern for new `create_superadmin_notification()` which targets `User.is_superuser=True` instead of org users

### Alembic Migration Chain
- Most recent migration: `backend/alembic/versions/v5y6z7a8b9c_phase13_field_mappings_per_app.py` — Phase 14 migration chains from this

### Frontend Config Page
- `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts` — existing `config-section` card layout, section-header + section-body pattern, accordion pattern
- `frontend/src/app/features/configuration/pages/field-mappings-panel.component.ts` — masked field pattern (Client Secret is password-type input in Phase 12; cookie uses similar reveal/replace UX)
- `frontend/src/app/core/services/auth.service.ts` — `role?: string` already in user interface (line 36); extend with `is_superuser?: boolean`
- `frontend/src/app/core/store/auth/auth.actions.ts` — `role: string` in auth store (line 8); extend with `is_superuser`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `User.is_superuser` (Boolean): already in DB schema — no migration needed for the field itself, only a data migration to seed the first SuperAdmin
- `get_current_admin` in `deps.py`: exact template for `get_current_superadmin` — same pattern, checks `is_superuser` instead of OrganizationRole
- `_check_youtube_cookies()` in `dv360_sync.py`: cookie expiry validation logic is already implemented; extract to a shared helper or call directly from the new endpoint
- `config-section` CSS class in `brainsuite-apps.component.ts`: established card section pattern reusable for Admin page sections
- `create_org_notification()` in `notifications.py`: template for `create_superadmin_notification()`

### Established Patterns
- Fernet encryption for sensitive DB columns (see `client_secret_encrypted`) — same pattern for cookie columns
- `get_current_admin` already passes if `current_user.is_superuser` — SuperAdmin already implicitly passes org-admin checks; don't change this
- Alembic migrations chain from the previous migration's revision ID
- Angular `*ngIf="currentUser?.role === 'ADMIN'"` pattern for role-gated UI — extend for SuperAdmin check

### Integration Points
- `dv360_sync._download_video_asset()` → switch from `os.environ.get()` to async DB read of `system_config`
- Angular `configuration.routes.ts` → add `/admin` child route with `isSuperAdminGuard`
- Angular nav/sidebar → add "Admin" item below Configuration links, gated on `is_superuser`
- Login response (`auth.py` line 271) or `/users/me` → include `is_superuser` in payload

</code_context>

<specifics>
## Specific Ideas

- Cookie health mockup confirmed by user:
  ```
  [ Primary Cookie ]  • VALID
  [••••••••••••••••••••]  [Reveal] [Replace]

  [ Backup Cookie ]   • EXPIRED
  [••••••••••••••••••••]  [Reveal] [Replace]

                           [Save]
  ```
- Notification deeplink: `data.deeplink = "/configuration/admin/youtube-cookies"` — routes bell click directly to the Admin cookies section
- SuperAdmin seeded email: `s.dettweiler@brainsuite.ai`

</specifics>

<deferred>
## Deferred Ideas

- **Org create/delete in Admin** — read-only list only in Phase 14. Org management (create, delete, impersonate) is a future Admin capability.
- **Proactive cookie expiry warning** — "COOKIE_EXPIRING_SOON" notification 24h before expiry. Requires a new scheduler task. Deferred: Phase 14 only does on-failure notification.
- **Per-org cookie overrides** — system-global cookies decided for Phase 14. Per-org cookie slots (for multi-DV360-account setups) deferred to a future phase.
- **Cookie file upload** — textarea paste chosen. File upload (.txt) deferred; textarea covers the use case.

</deferred>

---

*Phase: 14-youtube-cookies-admin-ui*
*Context gathered: 2026-04-24*
