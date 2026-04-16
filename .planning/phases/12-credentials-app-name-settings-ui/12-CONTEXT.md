# Phase 12: Credentials + App Name Settings UI - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Frontend + backend work for the BrainSuite Configuration UI:

1. **Credentials section** — Backend API endpoints for `OrgBrainsuiteConfig` (GET/PUT) + Angular section card on the Brainsuite Apps page for Client ID and Client Secret. Test Connection button fires a live BrainSuite auth request. Re-score prompt on config changes.

2. **App name column** — Add `system_app_name` to `brainsuite_apps` table (drops `video_app_name` / `static_app_name` from `org_brainsuite_config`). Accordion expand on each app row to configure its system app name. Update scoring pipeline to read `system_app_name` from the `BrainsuiteApp` row.

No field mapping UI (Phase 13). No PIPE-02/PIPE-03 admin warning (Phase 13).

</domain>

<decisions>
## Implementation Decisions

### Settings Page Placement (BSCFG-04)
- **D-01:** The BrainSuite Credentials form (Client ID + Secret only) lives as a new `config-section` card **above** the existing app list on the Brainsuite Apps page (`brainsuite-apps.component.ts`). No new navigation tab.
- **D-02:** The credentials section **auto-collapses** once both credentials are saved and the Test Connection has passed. The collapsed state shows a summary row (e.g., "Client ID: abc123... — Connection verified ✓") with an "Edit" button to re-expand.

### App Name Placement (BSCFG-02, BSCFG-03)
- **D-03:** `video_app_name` and `static_app_name` are **removed from `OrgBrainsuiteConfig`** and replaced by a `system_app_name` column (`String(255)`, nullable) on the `brainsuite_apps` table. Each `BrainsuiteApp` row owns its own API URL app name — future-proof for more than 2 apps per org.
- **D-04:** Each app row in the Brainsuite Apps list has an **accordion chevron** (Bootstrap Icons `bi-chevron-down`). Clicking expands an inline panel beneath the row containing a single labeled input: "System App Name" + a Save button. Panel collapses on save or on click-away.
- **D-05:** Phase 12 includes the cleanup migration: add `brainsuite_apps.system_app_name`, drop `org_brainsuite_config.video_app_name` and `org_brainsuite_config.static_app_name`, update scoring pipeline to read `system_app_name` from the `BrainsuiteApp` row (replacing the Phase 11 re-wire that read from `OrgBrainsuiteConfig`).

### Client Secret UX (BSCFG-01, VSAF-01)
- **D-06:** When a Client Secret is already stored, the password field renders with placeholder text `●●●●●●●● (saved)` and is read-only. A "Change" button puts the field into edit mode (clears the placeholder, accepts new input). A "Cancel" button in edit mode reverts to the placeholder state — the stored secret is unchanged if no new value is saved.
- **D-07:** Sending an empty `client_secret` value to the backend on save means "keep existing". Only a non-empty value triggers a new encrypt + store.

### Test Connection (VSAF-01)
- **D-08:** "Test Connection" button is **disabled** until Client ID + Client Secret are both present in the DB (i.e., the config row exists with non-null `client_id` and `client_secret_encrypted`).
- **D-09:** Clicking "Test Connection" fires a backend request that calls the BrainSuite auth token endpoint using the stored credentials (decrypt secret, POST to auth). The frontend shows a spinner (replaces button icon) during the request.
- **D-10:** Result renders as a colored inline status block **below the button**:
  - Success: green background + `bi-check-circle` icon + "Connection successful"
  - Failure: red background + `bi-x-circle` icon + error message (e.g., "Authentication failed: invalid credentials")
  - Status persists until the next Test Connection click.

### Re-score Prompt (VSAF-02)
- **D-11:** The re-score dialog **only appears** when the saved config actually changed — compare new `client_id`, `client_secret` (non-empty), or any `system_app_name` on apps the org owns against the previously stored values. No-op saves skip the prompt entirely.
- **D-12:** The prompt uses a **MatDialog** (matching the role-change dialog pattern in `organization.component.ts`) with two buttons: "Keep existing scores" and "Re-score all assets".
- **D-13:** "Re-score all assets" → backend resets all `SCORED` assets for the org to `UNSCORED` (scheduler picks them up on the next 15-min cycle). Frontend shows a `MatSnackBar` toast: "Assets queued for re-scoring". No immediate score changes are visible.

### Claude's Discretion
- Exact backend endpoint shape for credentials CRUD (suggested: `GET/PUT /api/v1/brainsuite-config/credentials`)
- Exact endpoint for test connection (suggested: `POST /api/v1/brainsuite-config/test-connection`)
- How collapse state is stored — local component boolean vs. persisted (localStorage acceptable)
- Whether "Test Connection passed" is stored server-side or only client-side for auto-collapse trigger
- API route registration in `main.py` / `api_router`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Schema — Models to Modify
- `backend/app/models/brainsuite_config.py` — `OrgBrainsuiteConfig` model; `video_app_name` + `static_app_name` columns to be dropped via migration
- `backend/app/models/platform.py` — `BrainsuiteApp` model; `system_app_name` column to be added

### Scoring Pipeline — Re-wire Target
- `backend/app/services/brainsuite_score.py` — currently reads `video_app_name` from `OrgBrainsuiteConfig` (Phase 11 re-wire); Phase 12 must update to read `system_app_name` from the `BrainsuiteApp` row
- `backend/app/services/brainsuite_static_score.py` — same for static scoring

### Frontend Analog (Pattern Reference)
- `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts` — direct analog: `config-section` cards, ReactiveFormsModule, MatSnackBar, MatProgressSpinner patterns; new credentials section slots above existing app list
- `frontend/src/app/features/configuration/pages/organization.component.ts` — MatDialog pattern for role-change (analog for re-score dialog)
- `frontend/src/app/features/configuration/configuration-shell.component.ts` — nav structure; no new tab needed

### Encryption Pattern
- `backend/app/core/security.py` — `encrypt_token` / `decrypt_token` Fernet utilities (reuse from Phase 11 D-05)

### Existing Migrations (Chain Reference)
- Check `backend/alembic/versions/` for the most recent Phase 11 migration (new migrations chain from it)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config-section` / `section-header` / `section-body` CSS pattern: already in `brainsuite-apps.component.ts` — use verbatim
- `MatSnackBar` toast feedback: used for "App created/updated/deleted" toasts — reuse for "Config saved" and "Assets queued for re-scoring"
- `MatProgressSpinner` (diameter 16): used inline in save button — reuse for test connection spinner
- `encrypt_token` / `decrypt_token` (app.core.security): drop-in for secret handling

### Established Patterns
- Config page uses standalone Angular components, lazy-loaded via `CONFIGURATION_ROUTES`
- Forms: ReactiveFormsModule + `FormBuilder` + `Validators`, `appearance="outline"` MatFormFields
- Angular Bootstrap Icons (`bi-*`) for all icons — no other icon library
- Error/info inline notes: `api-note` div style (yellow border, info icon) — use for any inline warnings
- Backend: `async def` endpoints, `Depends(get_db)`, `Depends(get_current_user)`, Pydantic request/response schemas

### Integration Points
- Credentials section slots into `brainsuite-apps.component.ts` above the existing app list — no new route or nav item
- Accordion expand on app rows is a new pattern (not yet in codebase) — implement as `expandedAppId: string | null` state in the component
- Re-score dialog: inline `@Component` class or separate file — follow org.component.ts pattern (inline dialog component in same file)

</code_context>

<specifics>
## Specific Ideas

- Auto-collapse trigger: credentials section collapses when `hasCredentials && lastTestResult === 'success'` — both conditions must be true
- "Change" button for secret edit mode: small secondary button next to the password field, not inside the field
- Accordion save button: "Save" label, accent-colored, inline with the input in the expanded panel
- `system_app_name` is the BrainSuite API URL parameter (e.g., `ACE_VIDEO_SMV_API`, `ACE_STATIC_SOCIAL_STATIC_API`) — label it "BrainSuite API App Name" in the UI to distinguish from the display `name`

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 12-credentials-app-name-settings-ui*
*Context gathered: 2026-04-16*
