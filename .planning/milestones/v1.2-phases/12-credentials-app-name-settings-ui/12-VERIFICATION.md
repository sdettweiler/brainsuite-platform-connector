---
phase: 12-credentials-app-name-settings-ui
verified: 2026-04-27T12:00:00Z
status: human_needed
score: 5/5
overrides_applied: 0
requirements: [BSCFG-01, BSCFG-02, BSCFG-03, BSCFG-04, VSAF-01, VSAF-02]
human_verification:
  - test: "Re-score dialog trigger — save credentials that actually change on an org with COMPLETE score results"
    expected: "MatDialog appears with contextual message ('BrainSuite credentials changed...'), 'Keep existing scores' and 'Re-score all assets' buttons; clicking Re-score fires POST /brainsuite-config/rescore-all and shows toast"
    why_human: "UAT Test 8 was skipped — fresh DB had no COMPLETE scored assets so has_scored_assets was always false; the dialog code path was never exercised end-to-end in a live browser session"
---

# Phase 12: Credentials + App Name Settings UI — Verification Report

**Phase Goal:** Org admins can configure and validate their BrainSuite credentials and app names through the Settings page.
**Verified:** 2026-04-27T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Settings page contains a dedicated "BrainSuite Configuration" section (BSCFG-04) with fields for Client ID, Client Secret, and per-app System App Name | VERIFIED | `brainsuite-apps.component.ts` line 97: `<form [formGroup]="credentialsForm!">` with `client_id` and `client_secret` inputs; line 192: accordion chevron per app row; line 723: `system_app_name` in `inlineEditForms`. Template heading "BrainSuite Credentials" present. 860-line component, well above 500-line minimum. |
| 2 | Admin can save credentials and app names; values persist to DB and are loaded on next page visit | VERIFIED | `PUT /brainsuite-config/credentials` upserts `OrgBrainsuiteConfig` (encrypt via Fernet, lines 129–133 of endpoint). `PATCH /brainsuite-config/apps/{app_id}/system-app-name` updates `BrainsuiteApp.system_app_name` (lines 220–225). `loadCredentials()` on `ngOnInit()` (line 535) reloads from DB on every page visit. UAT Tests 3, 4, 7 passed. |
| 3 | "Test Connection" button fires a live BrainSuite authentication request and displays inline success or failure feedback without leaving the page | VERIFIED | `testConnection()` (line 691) calls `POST /brainsuite-config/test-connection`. Backend (lines 162–205): `httpx.AsyncClient(timeout=15)` posts to `settings.BRAINSUITE_AUTH_URL` with Basic Auth; checks HTTP 200 AND `"access_token" in body` (Pitfall 5). Frontend renders `testResult` block (lines 151–158) with `.test-success` / `.test-failure` classes. UAT Test 5 passed. |
| 4 | When saving changes to an org that already has scored assets, a confirmation dialog appears offering "Keep existing scores" or "Re-score all assets under new config" | VERIFIED (code) / ? HUMAN (live path) | `openRescoreDialog()` (line 767) opens `RescoreDialogComponent` (line 51) — implemented, scoped by app_type with contextual copy. Guard: `resp.changed && resp.has_scored_assets` (line 681 for credentials, line 745 for app name). `POST /brainsuite-config/rescore-all` (line 784) fired on 'rescore' result. UAT Test 8 was SKIPPED — fresh DB had no COMPLETE assets so the dialog was never triggered in live UAT. Code path verified structurally; live behavior needs human verification. |
| 5 | Client Secret field is masked (password input) and the stored value is never returned in plain text to the frontend | VERIFIED | Backend: `CredentialsResponse` schema (lines 6–13 of `brainsuite_config.py`) has no `client_secret` or `client_secret_encrypted` field — only `has_secret: bool`. Frontend: `type="password"` input (line 113); read-only with `••••••••` sentinel seeded by `initCredentialsForm()` (line 644) when `has_secret` is true; `cancelSecretEdit()` (line 663) restores sentinel; `saveCredentials()` (line 673) strips sentinel from PUT payload when not in `secretEditMode`. UAT Test 3 passed; cosmetic issue (Test 4) fixed in commit d6e8f7e. |

**Score: 5/5 truths verified** (Truth 4 is structurally verified but requires live human confirmation of the dialog trigger path)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/u2v3w4x5y6z7_phase12_system_app_name.py` | Migration adding system_app_name, dropping video/static_app_name | VERIFIED | Exists. `down_revision = "t1u2v3w4x5y6"` (correct chain from Phase 11 head). `op.add_column("brainsuite_apps", ...)`, `op.drop_column("org_brainsuite_config", "video_app_name")`, `op.drop_column("org_brainsuite_config", "static_app_name")` — all three DDL ops present. Downgrade restores dropped columns. |
| `backend/app/models/brainsuite_config.py` | OrgBrainsuiteConfig without video/static_app_name | VERIFIED | No `video_app_name` or `static_app_name` attributes. Columns present: `client_id` (String 500), `client_secret_encrypted` (String 1000). Docstring updated to reference per-app storage. |
| `backend/app/models/platform.py` | BrainsuiteApp with system_app_name column | VERIFIED | Line 22: `system_app_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)` — exact spec match. |
| `backend/app/schemas/platform.py` | BrainsuiteAppResponse with system_app_name field | VERIFIED | Line 31: `system_app_name: Optional[str] = None` in `BrainsuiteAppResponse`. |
| `backend/app/services/sync/scoring_job.py` | Pipeline reads system_app_name from BrainsuiteApp row | VERIFIED | Zero occurrences of `video_app_name` or `static_app_name`. Line 19: `from app.models.platform import BrainsuiteApp, PlatformConnection`. Line 233: `brainsuite_app = await db.get(BrainsuiteApp, app_id)`. Line 235: `required_app_name = brainsuite_app.system_app_name if brainsuite_app else None`. Four `app_name=required_app_name` call sites (lines 354, 370, 392, 400). |
| `backend/app/schemas/brainsuite_config.py` | Pydantic schemas for credentials endpoints | VERIFIED | All five required schemas present: `CredentialsResponse`, `CredentialsUpdate`, `CredentialsSaveResponse`, `TestConnectionResponse`, `SystemAppNameUpdate`. Additionally contains `RescoreRequest` (added for Phase 13 app_type scoping — benign addition). |
| `backend/app/api/v1/endpoints/brainsuite_config.py` | 5 routes: GET/PUT credentials, POST test-connection, PATCH system-app-name, POST rescore-all | VERIFIED | All 5 Phase 12 routes present. File also contains Phase 13 field-mapping endpoints (GET/PUT `/apps/{app_id}/field-mappings`) — added in same file per Phase 13 plan; no regression to Phase 12 routes. `encrypt_token`/`decrypt_token` imported from `app.core.security`. `datetime.now(timezone.utc)` pattern used throughout (no deprecated `utcnow()`). |
| `backend/app/api/v1/__init__.py` | Router registered at /brainsuite-config prefix | VERIFIED | Line 2: `brainsuite_config` in endpoint imports. Line 12: `api_router.include_router(brainsuite_config.router, prefix="/brainsuite-config", tags=["brainsuite-config"])`. |
| `backend/tests/test_phase12_schema_pipeline.py` | Static analysis tests for schema/pipeline changes | VERIFIED | 71 lines. Tests cover: `BrainsuiteApp.system_app_name` presence, no `video_app_name`/`static_app_name` in model or scoring_job.py, `BrainsuiteApp` import in scoring_job.py, `system_app_name` usage, `BrainsuiteAppResponse` schema, migration file existence and chain. |
| `backend/tests/test_phase12_endpoints.py` | Static analysis tests for endpoint structure | VERIFIED | 84 lines. Tests cover: module existence/importability, router registration with prefix, admin guard (no `Depends(get_current_user)` directly), `CredentialsResponse` has no `client_secret` field, COMPLETE not SCORED targeting, access_token check, D-07 empty-secret guard, encrypt/decrypt imports, `datetime.now(timezone.utc)` pattern. |
| `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts` | Credentials section, accordion, re-score dialog | VERIFIED | 860 lines (min_lines 500 satisfied). `RescoreDialogComponent` class defined at line 51. All 7 required methods present: `loadCredentials`, `saveCredentials`, `testConnection`, `toggleAccordion`, `saveSystemAppName` (via `saveAppInline`), `openRescoreDialog`, `onClickAway`. Existing methods preserved: `loadApps`, `openAdd`, `editApp`, `saveApp`, `cancelForm`, `deleteApp`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `scoring_job.py` | `platform.py` (BrainsuiteApp) | `brainsuite_app.system_app_name` lookup | VERIFIED | Line 19: import present; lines 221–235: async `db.get(BrainsuiteApp, app_id)` inside session block; line 235: `required_app_name = brainsuite_app.system_app_name if brainsuite_app else None` |
| `u2v3w4x5y6z7_phase12_system_app_name.py` | `t1u2v3w4x5y6_seed_brand_values_metadata_fields.py` | `down_revision` | VERIFIED | Line 11: `down_revision = "t1u2v3w4x5y6"` — exact match to Phase 11 head |
| `backend/app/api/v1/__init__.py` | `endpoints/brainsuite_config.py` | `api_router.include_router` | VERIFIED | Lines 2 and 12 of `__init__.py` — import and prefix registration confirmed |
| `endpoints/brainsuite_config.py` | `app/core/security.py` | `encrypt_token` / `decrypt_token` | VERIFIED | Line 37: `from app.core.security import encrypt_token, decrypt_token` |
| `brainsuite-apps.component.ts` | `GET /brainsuite-config/credentials` | `api.get(...)` | VERIFIED | Line 620: `this.api.get<{...}>('/brainsuite-config/credentials').subscribe(...)` |
| `brainsuite-apps.component.ts` | `PUT /brainsuite-config/credentials` | `api.put(...)` | VERIFIED | Line 676: `this.api.put<{...}>('/brainsuite-config/credentials', payload).subscribe(...)` |
| `brainsuite-apps.component.ts` | `POST /brainsuite-config/test-connection` | `api.post(...)` | VERIFIED | Line 694: `this.api.post<{...}>('/brainsuite-config/test-connection', {}).subscribe(...)` |
| `brainsuite-apps.component.ts` | `PATCH /brainsuite-config/apps/{app_id}/system-app-name` | `api.patch(...)` | VERIFIED | Line 737: `this.api.patch<{...}>('/brainsuite-config/apps/${app.id}/system-app-name', { system_app_name })` |
| `brainsuite-apps.component.ts` | `POST /brainsuite-config/rescore-all` | `api.post(...)` from dialog callback | VERIFIED | Line 784: `this.api.post('/brainsuite-config/rescore-all', body).subscribe(...)` inside `openRescoreDialog()` afterClosed handler |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `brainsuite-apps.component.ts` credentials section | `credentials` | `GET /brainsuite-config/credentials` → DB query `select(OrgBrainsuiteConfig).where(org_id == ...)` | Yes — DB row read, no static return | FLOWING |
| `brainsuite-apps.component.ts` test result block | `testResult` | `POST /brainsuite-config/test-connection` → live httpx call to BrainSuite auth URL | Yes — real external HTTP call, result reflected | FLOWING |
| `brainsuite-apps.component.ts` re-score dialog guard | `resp.has_scored_assets` | `_has_scored_assets()` → `select(func.count()).where(scoring_status == "COMPLETE")` | Yes — live DB count | FLOWING |
| `scoring_job.py` | `required_app_name` | `db.get(BrainsuiteApp, asset.brainsuite_app_id)` → `.system_app_name` | Yes — primary key DB lookup | FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED — checks require a running server and DB. Static structural checks confirm all behaviors are wired. Critical paths confirmed via grep:

- `_mark_unscored` called when `required_app_name` is None (line 242 of scoring_job.py) — null system_app_name falls through gracefully
- `encrypt_token` called before DB write; `decrypt_token` called only in-memory during test-connection
- Rescore targets `scoring_status == "COMPLETE"` exclusively — `PROCESSING` appears only in docstring/comment (line 243), never in query conditions

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BSCFG-01 | 12-02, 12-03 | Client Secret is masked in UI and never returned from API | VERIFIED | `CredentialsResponse` has no secret field; `has_secret: bool` only signal; `type="password"` input + sentinel placeholder; PUT payload strips sentinel when not in edit mode |
| BSCFG-02 | 12-01, 12-03 | Admin can configure per-app system app name (replaces video/static_app_name) | VERIFIED | `BrainsuiteApp.system_app_name` column; `PATCH /apps/{app_id}/system-app-name`; accordion UI with `system_app_name` input per app row |
| BSCFG-03 | 12-01, 12-03 | system_app_name drives scoring pipeline instead of legacy org-level app names | VERIFIED | Zero `video_app_name`/`static_app_name` references in `scoring_job.py`; pipeline reads `brainsuite_app.system_app_name` from BrainsuiteApp row |
| BSCFG-04 | 12-03 | Settings page has dedicated BrainSuite Configuration section with Client ID, Client Secret, app name fields | VERIFIED | "BrainSuite Credentials" section card above app list; form fields for `client_id`, `client_secret`; per-app accordion with `system_app_name` |
| VSAF-01 | 12-02, 12-03 | Test Connection button fires live auth request; shows inline success/failure | VERIFIED | `POST /brainsuite-config/test-connection` uses httpx + access_token check; frontend renders `.test-success`/`.test-failure` block inline. UAT Test 5 passed. |
| VSAF-02 | 12-02, 12-03 | Re-score dialog offered when saved config changed and org has scored assets | VERIFIED (code) / ? HUMAN (trigger) | Guard `resp.changed && resp.has_scored_assets` confirmed; `RescoreDialogComponent` opens and calls `rescore-all`; UAT Test 8 skipped (no scored assets in fresh DB) |

### Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| `brainsuite-apps.component.ts` line 116 | `[placeholder]="... '••••••••'"` | Info | Intentional masking sentinel — this is the UAT-fix from commit d6e8f7e, not a stub |
| `brainsuite-apps.component.ts` line 672 | Comment references "sentinel placeholder value" | Info | Explains the strip logic — informational, not a code smell |

No blockers found. No TODO/FIXME/PLACEHOLDER in production code paths. No empty return stubs. No hardcoded empty data passed to rendering paths. `datetime.utcnow()` never used — all timestamps use `datetime.now(timezone.utc)`.

### Commit Verification

All 8 documented commits confirmed present in git history:

| Commit | Description |
|--------|-------------|
| 8e2260f | feat(12-01): add system_app_name to BrainsuiteApp, drop video/static_app_name from OrgBrainsuiteConfig |
| b2dd585 | feat(12-01): re-wire scoring pipeline to read system_app_name from BrainsuiteApp row |
| 9714515 | test(12-01): add static analysis tests for Phase 12 schema and pipeline changes |
| 85c739d | feat(12-02): add Pydantic schemas for brainsuite config endpoints |
| 5b86ffa | feat(12-02): add brainsuite-config endpoints + router registration |
| fafa42c | test(12-02): add static analysis tests for Phase 12 config endpoints |
| 66137a0 | feat(12-03): add credentials section, accordion, and rescore dialog to brainsuite-apps component |
| d6e8f7e | fix(12-03): seed sentinel placeholder in locked client secret field when has_secret is true |

### Human Verification Required

#### 1. Re-score Dialog — Live Trigger Path

**Test:** In a running stack with at least one asset that has `scoring_status = 'COMPLETE'`:
1. Navigate to Settings > Brainsuite Apps
2. Change the Client ID or Client Secret and click "Save Credentials"
3. Expected: A Material Dialog appears with message "BrainSuite credentials changed. Re-score all previously scored assets under the new configuration?"
4. Click "Re-score all assets"
5. Expected: Toast "Assets queued for re-scoring" appears; backend resets COMPLETE assets to UNSCORED

**Expected:** Dialog appears, "Re-score all assets" button fires `POST /brainsuite-config/rescore-all`, assets transition to UNSCORED
**Why human:** UAT Test 8 was explicitly skipped — fresh DB had no COMPLETE scored assets. The `has_scored_assets` guard worked correctly (suppressed dialog when false), but the `true` branch was never exercised in a live browser session. All code paths are structurally verified; only the end-to-end browser flow against real data remains untested.

### Gaps Summary

No structural gaps found. All artifacts exist, are substantive, and are wired to their data sources.

The single human verification item (re-score dialog live trigger) is a UAT gap, not a code gap. The implementation is complete and structurally correct — the dialog, its guard conditions, and the rescore API call are all implemented and connected. The item simply requires a live run with scored data to confirm the end-to-end browser behavior.

---

_Verified: 2026-04-27T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
