---
phase: 13-field-mapping-editor-mandatory-field-enforcement
fixed_at: 2026-04-21T00:00:00Z
review_path: .planning/phases/13-field-mapping-editor-mandatory-field-enforcement/13-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 13: Code Review Fix Report

**Fixed at:** 2026-04-21
**Source review:** .planning/phases/13-field-mapping-editor-mandatory-field-enforcement/13-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (2 Critical, 5 Warning)
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01: Migration data-loss — orphan rows silently blocked by NOT NULL

**Files modified:** `backend/alembic/versions/v5y6z7a8b9c_phase13_field_mappings_per_app.py`
**Commit:** c1bc11f
**Applied fix:** Added a `SELECT COUNT(*) WHERE brainsuite_app_id IS NULL` pre-check before `op.alter_column(..., nullable=False)`. If any rows could not be backfilled, a `RuntimeError` is raised with a clear message telling the operator how many rows need manual resolution before the migration can proceed.

### CR-02: Migration unique constraint race — concurrent DML can insert duplicates

**Files modified:** `backend/alembic/versions/v5y6z7a8b9c_phase13_field_mappings_per_app.py`
**Commit:** c1bc11f
**Applied fix:** Added `LOCK TABLE org_brainsuite_field_mappings IN SHARE ROW EXCLUSIVE MODE` at the very top of `upgrade()` (before any DDL), ensuring no concurrent DML can insert duplicate `(brainsuite_app_id, api_field_name)` rows during the migration window. Both CR-01 and CR-02 were committed atomically in a single commit since they touch the same file.

### WR-01: N+1 queries in `_check_mandatory_fields`

**Files modified:** `backend/app/services/sync/scoring_job.py`
**Commit:** cdb9e0c
**Applied fix:** Replaced the two-step (fetch mappings, then per-field value SELECT) loop with a single `SELECT ... OUTER JOIN` query that fetches all mandatory field mappings and their associated `AssetMetadataValue` rows in one round-trip. The empty-rows fast-path (`return (True, [])`) is now outside the session context. The fix requires no new imports — `select`, `and_`, `OrgBrainsuiteFieldMapping`, and `AssetMetadataValue` were already imported at the top of the file.

### WR-02: Untracked subscriptions in `loadAllFieldMappings()`

**Files modified:** `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts`
**Commit:** 7015ed6
**Applied fix:** Added `Subject` and `takeUntil` imports from `rxjs`/`rxjs/operators`. Added `OnDestroy` to the `@angular/core` import and to the class `implements` list. Added a `private destroy$ = new Subject<void>()` field and `ngOnDestroy()` lifecycle hook. Piped `takeUntil(this.destroy$)` into every subscription inside `loadAllFieldMappings()` so in-flight HTTP requests are cancelled when the component is destroyed.

### WR-03: Race condition in `loadFieldMappings()` — no switchMap/cancellation

**Files modified:** `frontend/src/app/features/configuration/pages/field-mappings-panel.component.ts`
**Commit:** bf0e857
**Applied fix:** Added `OnInit`, `OnDestroy`, `Subject`, `takeUntil`, and `switchMap` imports. Added `private loadRequest$` and `private destroy$` subjects. Wired a single `switchMap` pipeline in `ngOnInit()` that cancels the prior in-flight request whenever a new app id is emitted. `loadFieldMappings()` now just sets loading state and emits on `loadRequest$` instead of subscribing directly. `ngOnDestroy()` completes both subjects. The panel starts closed (`isOpen = false`), so `ngOnChanges` never calls `loadFieldMappings()` before `ngOnInit()` sets up the pipeline.

### WR-04: Custom field `api_field_name` has no frontend pattern validation

**Files modified:** `frontend/src/app/features/configuration/pages/field-mappings-panel.component.ts`
**Commit:** 3da7d9b
**Applied fix:** Added `Validators.pattern(/^[a-zA-Z][a-zA-Z0-9_]*$/)` to the `api_field_name` control in both `buildForm()` (for existing custom fields loaded from the API) and `addCustomField()` (for new custom fields). Also added a `<span class="custom-name-error">` in the template that surfaces the pattern error message "Must start with a letter; letters, digits, underscores only" when the field is touched and invalid, preventing the user from submitting and seeing only a generic 422 error snackbar.

### WR-05: `saveApp()` snackbar always shows "created" due to premature null

**Files modified:** `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts`
**Commit:** aad4c06
**Applied fix:** Captured `const wasEditing = !!this.editingApp` before `this.editingApp = null`, then used `wasEditing` in the snackbar ternary. The snackbar now correctly shows "App updated" when editing an existing app and "App created" when adding a new one.

---

_Fixed: 2026-04-21_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
