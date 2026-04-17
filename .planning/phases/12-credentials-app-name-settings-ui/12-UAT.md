---
status: complete
phase: 12-credentials-app-name-settings-ui
source: 12-01-SUMMARY.md, 12-02-SUMMARY.md, 12-03-SUMMARY.md
started: 2026-04-17T00:00:00Z
updated: 2026-04-17T00:01:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/service. Clear ephemeral state (temp DBs, caches, lock files). Start the application from scratch. Server boots without errors, Alembic migrations (including the Phase 12 migration adding system_app_name to brainsuite_apps and dropping legacy columns from org_brainsuite_config) complete without error, and the frontend loads.
result: pass

### 2. BrainSuite Credentials Section Visible
expected: Navigate to the BrainSuite Apps configuration page. A credentials card/section appears above the app list. It is expanded by default on first visit. It contains a "BrainSuite Credentials" heading or equivalent label.
result: pass

### 3. Credentials Form — Client ID and Masked Secret
expected: The credentials section shows a Client ID text input and a password-type input for the Client Secret (characters are masked). Both inputs are present. The Client ID field is editable. The secret field shows either a "Change" button (if a secret is already saved) or is editable directly if no secret has been saved yet.
result: pass

### 4. Save Credentials — Change/Discard Pattern
expected: When a client secret is already stored, clicking "Change" makes the secret field editable. Clicking "Discard" reverts without saving. Clicking "Save" submits the form (PUT /api/v1/brainsuite-config/credentials) with the new values. After save, the secret field returns to masked/locked state.
result: issue
reported: "the client secret field (locked) looks empty. only when I click in it it shows ******(saved)"
severity: cosmetic

### 5. Test Connection Button
expected: Clicking "Test Connection" shows a loading spinner while the request runs. On success, an inline result block appears with a success indicator (green or similar). On failure (bad credentials), a failure indicator appears with an error message. The button is disabled while the request is in-flight.
result: pass

### 6. Auto-Collapse After Successful Test
expected: After a successful Test Connection, the credentials card automatically collapses. On next page load, it stays collapsed (persisted via localStorage). Manually expanding it works normally.
result: pass

### 7. Per-App Accordion — Expand and Edit System App Name
expected: Each app row in the app list has a chevron/expand control. Clicking it opens an inline panel showing a "System App Name" text input pre-filled with the current value (or empty). Typing a new name and clicking Save sends PATCH /api/v1/brainsuite-config/apps/{app_id}/system-app-name. The accordion closes or shows a success indicator.
result: pass

### 8. Re-score Dialog on Credential Change
expected: When saving credentials where the credentials actually changed AND the org has previously scored assets, a Material Dialog appears asking if the user wants to re-score all assets with the new credentials. Clicking "Yes" triggers POST /api/v1/brainsuite-config/rescore-all. Clicking "No" or dismissing closes the dialog without rescoring.
result: skipped
reason: Fresh DB has no scored assets — dialog correctly suppressed when has_scored_assets is false. Cannot test trigger condition.

### 9. Existing App Management Preserved
expected: Add App, Edit App, and Delete App buttons/actions on the BrainSuite Apps page still work correctly — none of the Phase 12 changes broke the pre-existing app management UI.
result: pass

## Summary

total: 9
passed: 7
issues: 1
pending: 0
skipped: 1
blocked: 0

## Gaps

- truth: "Locked client secret field shows masking placeholder (e.g. ******saved) at rest, without requiring user interaction"
  status: failed
  reason: "User reported: the client secret field (locked) looks empty. only when I click in it it shows ******(saved)"
  severity: cosmetic
  test: 4
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
