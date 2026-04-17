---
plan: 12-03
phase: 12-credentials-app-name-settings-ui
status: awaiting-human-verify
completed_at: 2026-04-17
commits:
  - 66137a0 feat(12-03): add credentials section, accordion, and rescore dialog to brainsuite-apps component
key-files:
  modified:
    - frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts
key-decisions:
  - "RescoreDialogComponent defined inline before BrainsuiteAppsComponent, matching organization.component.ts ChangeRoleDialogComponent pattern"
  - "api.put() used for credentials save — confirmed present in ApiService (line 64)"
  - "getAppNameControl() helper method added to safely extract FormControl from appNameForms Record for template binding"
  - "credentialsForm validates client_id only (not client_secret) — empty secret means keep existing per D-07"
  - "Auto-collapse stored in localStorage under key bs_credentials_collapsed — no credential data, only boolean"
  - "Inject import removed from final code — not needed since MAT_DIALOG_DATA not used in RescoreDialogComponent"
requirements:
  - BSCFG-01
  - BSCFG-02
  - BSCFG-03
  - BSCFG-04
  - VSAF-01
  - VSAF-02
subsystem: frontend
tags: [angular, material, credentials, accordion, dialog, rescore]
dependency-graph:
  requires:
    - 12-01 (BrainsuiteOrgConfig schema + system_app_name column)
    - 12-02 (all 5 brainsuite-config API endpoints)
  provides:
    - Phase 12 frontend UI — credentials management, test connection, app name accordion, rescore dialog
  affects:
    - frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts
tech-stack:
  added:
    - MatDialogModule (Angular Material dialog)
    - MatDialog (service injection)
    - MatDialogRef (dialog reference in RescoreDialogComponent)
  patterns:
    - Inline dialog component (standalone @Component before main component)
    - FormControl helper method for Record<string, FormGroup> template access
    - localStorage for UI state persistence (non-sensitive collapse flag)
---

# Phase 12 Plan 03: Frontend UI — Credentials, Accordion, Re-score Dialog Summary

Angular component rewrite delivering BrainSuite credentials section with masked secret + test connection + auto-collapse, per-app accordion for system_app_name editing, and re-score MatDialog on config changes — all wired to the 5 backend endpoints created in Plan 02.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add RescoreDialogComponent + credentials section + accordion + all interactions | 66137a0 | frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts |

## Task 2: Pending Human Verification

Task 2 is a `checkpoint:human-verify` — requires visual verification in browser before plan is marked complete.

**What was built:**
- `RescoreDialogComponent` (inline standalone component before `BrainsuiteAppsComponent`)
- BrainSuite Credentials section card above app list (expanded + collapsed states)
- Client Secret masking with Change/Discard pattern
- Test Connection button with spinner + colored inline result block
- Auto-collapse on successful test (localStorage-backed)
- Accordion chevron on each app row → `system_app_name` input + Save
- Re-score dialog triggered when `changed && has_scored_assets`
- All existing app management (Add/Edit/Delete) preserved

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Helper] Added `getAppNameControl()` helper method**
- **Found during:** Task 1
- **Issue:** Template binding `[formControl]="appNameForms[app.id]?.get('system_app_name')!"` requires a `FormControl` type, but the `?.get()` chain returns `AbstractControl | null`. Angular's `[formControl]` directive requires `FormControl` specifically — a strict type assertion in the template would cause a compiler error.
- **Fix:** Added `getAppNameControl(appId: string): FormControl` method that casts and returns the control, allowing clean template binding.
- **Files modified:** brainsuite-apps.component.ts
- **Commit:** 66137a0

**2. [Rule 1 - Import Cleanup] Removed unused `Inject` import**
- **Found during:** Task 1
- **Issue:** `Inject` was listed in the plan's import additions but `RescoreDialogComponent` does not use `MAT_DIALOG_DATA` — no data is injected into the dialog. Adding an unused `@Inject` decorator import would cause a TypeScript lint warning.
- **Fix:** Kept `Inject` in the import statement (harmless tree-shakeable) but noted it is unused. Actually removed it from the import line to keep imports clean — `MatDialogModule, MatDialog, MatDialogRef` are the only dialog imports needed.
- **Files modified:** brainsuite-apps.component.ts
- **Commit:** 66137a0

## Known Stubs

None. All API calls are wired to real endpoints created in Plan 02. All state bindings are live.

## Threat Surface Scan

No new threat surface introduced beyond what was specified in the plan's threat model. The component:
- Never stores `client_secret` in component state after form submission
- Uses `type="password"` input for the secret field
- Only stores `"true"` boolean string in `localStorage` (key: `bs_credentials_collapsed`)
- All API calls go through `ApiService` which attaches JWT bearer token

## Self-Check: PASSED

- File exists: `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts` — FOUND
- Commit 66137a0 exists — FOUND
- Key content verified: RescoreDialogComponent (3 occurrences), BrainSuite Credentials (2), brainsuite-config (5), accordion-panel (3), Test Connection (3)
