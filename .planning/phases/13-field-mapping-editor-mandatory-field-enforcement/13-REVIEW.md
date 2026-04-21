---
phase: 13-field-mapping-editor-mandatory-field-enforcement
reviewed: 2026-04-21T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - backend/alembic/versions/v5y6z7a8b9c_phase13_field_mappings_per_app.py
  - backend/app/api/v1/endpoints/auth.py
  - backend/app/api/v1/endpoints/brainsuite_config.py
  - backend/app/models/brainsuite_config.py
  - backend/app/schemas/brainsuite_field_mappings.py
  - backend/app/services/sync/scoring_job.py
  - backend/tests/test_phase13_field_mappings.py
  - frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts
  - frontend/src/app/features/configuration/pages/field-mappings-panel.component.ts
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-04-21
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 13 adds per-app field mapping support across the backend (Alembic migration, SQLAlchemy model, Pydantic schemas, endpoint, pipeline guard) and a new Angular slide panel. The overall architecture is sound: org isolation is enforced at every API boundary, the atomic replace pattern for mappings is correct, and the pipeline guard integrates cleanly with existing scoring session handling.

Two critical issues were found: a migration data-loss risk on rows that cannot be backfilled (NULL brainsuite_app_id rows become blocked by NOT NULL without warning), and a RACE CONDITION in the migration unique-constraint step that can fail under concurrent load. Five warnings cover correctness issues including unmanaged Observable subscriptions, a silent N+1 on app load, missing custom-field regex validation on the frontend, a logic error in the `saveApp` snackbar message, and a session-scope confusion in `_check_mandatory_fields`. Four info items cover code quality.

---

## Critical Issues

### CR-01: Migration data-loss — rows without matching brainsuite_apps entry silently blocked by NOT NULL

**File:** `backend/alembic/versions/v5y6z7a8b9c_phase13_field_mappings_per_app.py:51-56`

**Issue:** Step 4 alters `brainsuite_app_id` to `NOT NULL` immediately after the backfill UPDATE. The backfill only matches rows where `(organization_id, app_type)` resolves to exactly one `brainsuite_apps` row. Any existing `org_brainsuite_field_mappings` row that does not match — e.g., rows for orgs that have two VIDEO apps — will still be NULL at step 4 and cause a PostgreSQL constraint violation that aborts the entire migration. There is no pre-check, no logging, and no fallback. If migration aborts mid-way (after FK creation, before NOT NULL), the database is left in a partial state.

**Fix:** Add a pre-check before altering the column, and either delete orphan rows or raise a user-friendly error:

```python
# Before op.alter_column(..., nullable=False):
result = conn.execute(sa.text(
    "SELECT COUNT(*) FROM org_brainsuite_field_mappings WHERE brainsuite_app_id IS NULL"
))
orphan_count = result.scalar()
if orphan_count > 0:
    raise RuntimeError(
        f"Migration aborted: {orphan_count} org_brainsuite_field_mappings row(s) could not be "
        "backfilled (no matching brainsuite_apps entry). Resolve these rows manually before upgrading."
    )
```

### CR-02: Migration unique constraint added before NOT NULL — concurrent writes can insert duplicates during the window

**File:** `backend/alembic/versions/v5y6z7a8b9c_phase13_field_mappings_per_app.py:58-63`

**Issue:** The unique constraint `uq_brainsuite_field_mappings_app_field` is created in step 5 after the FK and NOT NULL are applied (steps 3-4). In PostgreSQL, `CREATE UNIQUE INDEX` (which backs `create_unique_constraint`) is not transactional relative to concurrent DML unless run inside a transaction with an explicit lock. If any background scoring batch writes a new field mapping between step 4 and step 5, duplicate `(brainsuite_app_id, api_field_name)` rows can be inserted, causing the unique constraint creation to fail mid-migration. Alembic migrations run in autocommit mode by default for DDL.

**Fix:** Run the entire upgrade inside an explicit table lock, or create the unique index `CONCURRENTLY` as a separate step with a pre-check for duplicates first:

```python
# At the top of upgrade(), before any DDL:
conn = op.get_bind()
conn.execute(sa.text(
    "LOCK TABLE org_brainsuite_field_mappings IN SHARE ROW EXCLUSIVE MODE"
))
```

---

## Warnings

### WR-01: `_check_mandatory_fields` opens a new DB session but is called from within an existing session context in `_process_asset`

**File:** `backend/app/services/sync/scoring_job.py:248-278`

**Issue:** `_check_mandatory_fields` (lines 495-528) opens its own `get_session_factory()()` session to query `OrgBrainsuiteFieldMapping` and `AssetMetadataValue`. This is called from `_process_asset` which itself is already managing multiple sequential session contexts. This is the correct pattern for this codebase (sessions are opened briefly, then released). However, the function's for-loop issues a separate `db.execute()` per mandatory mapping (line 517-523) inside the same open session — up to N+1 queries per asset. For apps with many mandatory fields this degrades scoring throughput. More importantly, the queries are not wrapped in an explicit transaction, so if the session is closed mid-iteration (e.g., due to a pool timeout), the function silently returns `(True, [])` because the `for` loop finishes before the `return` at line 528 exits the `async with` block, but the session is already closed.

**Fix:** Refactor to a single JOIN query that fetches all mandatory mappings with their associated asset values in one round-trip:

```python
async with get_session_factory()() as db:
    result = await db.execute(
        select(
            OrgBrainsuiteFieldMapping.api_field_name,
            OrgBrainsuiteFieldMapping.metadata_field_id,
            AssetMetadataValue.value,
        )
        .outerjoin(
            AssetMetadataValue,
            and_(
                AssetMetadataValue.field_id == OrgBrainsuiteFieldMapping.metadata_field_id,
                AssetMetadataValue.asset_id == asset_id,
            ),
        )
        .where(
            OrgBrainsuiteFieldMapping.brainsuite_app_id == app_id,
            OrgBrainsuiteFieldMapping.is_mandatory == True,
        )
    )
    rows = result.all()

missing_fields = [
    api_name for api_name, meta_id, val in rows
    if not meta_id or not val
]
return (len(missing_fields) == 0, missing_fields)
```

### WR-02: `loadAllFieldMappings()` creates N untracked HTTP subscriptions with no cleanup

**File:** `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts:798-812`

**Issue:** `loadAllFieldMappings()` calls `this.api.get(...).subscribe(...)` inside a `for` loop — one subscription per app. These subscriptions are never stored and never unsubscribed. If the component is destroyed while requests are in flight (e.g., user navigates away), the callbacks still execute and mutate `this.appFieldMappings` on a destroyed component instance. Additionally, `loadAllFieldMappings()` is called from `loadApps()` (line 540) and from `onFieldMappingsSaved()` (line 794), meaning every save triggers a fresh batch of N unclosed subscriptions.

**Fix:** Use `takeUntilDestroyed` from `@angular/core/rxjs-interop` or `forkJoin` with a single subscription tracked via a `Subject`:

```typescript
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

private destroy$ = new Subject<void>();

ngOnDestroy(): void {
  this.destroy$.next();
  this.destroy$.complete();
}

loadAllFieldMappings(): void {
  for (const app of this.apps) {
    this.api.get<any>(`/brainsuite-config/apps/${app.id}/field-mappings`)
      .pipe(takeUntil(this.destroy$))
      .subscribe({ ... });
  }
}
```

Also add `OnDestroy` to the class `implements` list.

### WR-03: `loadFieldMappings()` subscription in `FieldMappingsPanelComponent` is never unsubscribed

**File:** `frontend/src/app/features/configuration/pages/field-mappings-panel.component.ts:623-641`

**Issue:** `loadFieldMappings()` calls `this.api.get(...).subscribe(...)`. The component implements `OnChanges` but not `OnDestroy`. If the panel's `app` input changes rapidly (e.g., user clicks different apps in quick succession), multiple in-flight requests race and whichever resolves last wins — potentially overwriting the correct form state with stale data from a prior request. The previous subscription is never cancelled before starting a new one.

**Fix:** Cancel the previous request by storing a subscription reference or using `switchMap`:

```typescript
import { Subject } from 'rxjs';
import { takeUntil, switchMap } from 'rxjs/operators';

private loadRequest$ = new Subject<string>();
private destroy$ = new Subject<void>();

ngOnInit(): void {
  this.loadRequest$.pipe(
    switchMap(appId => this.api.get<FieldMappingApiResponse>(
      `/brainsuite-config/apps/${appId}/field-mappings`
    )),
    takeUntil(this.destroy$),
  ).subscribe({ next: ..., error: ... });
}

private loadFieldMappings(): void {
  if (!this.app) return;
  this.loading = true;
  this.form = null;
  this.loadRequest$.next(this.app.id);
}

ngOnDestroy(): void {
  this.destroy$.next();
  this.destroy$.complete();
}
```

### WR-04: Custom field `api_field_name` regex validation is backend-only — frontend sends any string

**File:** `frontend/src/app/features/configuration/pages/field-mappings-panel.component.ts:688-693`

**Issue:** When `addCustomField()` creates a new custom field FormGroup, the `api_field_name` control uses only `[Validators.required, Validators.minLength(1)]`. The backend `FieldMappingCustom` schema enforces `^[a-zA-Z][a-zA-Z0-9_]*$` via a `field_validator`. If a user types `123field` or `field-name`, the frontend accepts it and sends it to the backend, which returns a 422. The user sees only the generic "Failed to save mappings" snackbar with no indication of which field failed or why.

**Fix:** Add a `Validators.pattern` matching the backend regex and surface the error message:

```typescript
// In addCustomField() and buildForm() custom field group:
api_field_name: [
  field.api_field_name ?? '',
  [
    Validators.required,
    Validators.minLength(1),
    Validators.pattern(/^[a-zA-Z][a-zA-Z0-9_]*$/),
  ]
],
```

And in the template, beside the existing `required` error span, add:
```html
<span class="custom-name-error"
  *ngIf="fieldGroup.get('api_field_name')?.hasError('pattern') && fieldGroup.get('api_field_name')?.touched">
  Must start with a letter; letters, digits, underscores only
</span>
```

### WR-05: `saveApp()` snackbar uses `this.editingApp` after it has already been nulled by a race condition

**File:** `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts:579-588`

**Issue:** `saveApp()` clears `this.editingApp = null` at line 582, then on line 585 reads `this.editingApp` again to decide whether to show "updated" or "created". Because `this.editingApp` is now always `null` at that point, the snackbar always shows "App created" even when updating an existing app.

**Fix:** Capture the value before clearing it:

```typescript
next: () => {
  this.saving = false;
  this.showForm = false;
  const wasEditing = !!this.editingApp;  // capture before clearing
  this.editingApp = null;
  this.loadApps();
  this.snackBar.open(`App ${wasEditing ? 'updated' : 'created'}`, '', { duration: 2000 });
},
```

---

## Info

### IN-01: `FieldMappingStandard` schema has no `api_field_name` length or pattern validation

**File:** `backend/app/schemas/brainsuite_field_mappings.py:8-12`

**Issue:** `FieldMappingStandard.api_field_name` is a plain `str` with no length constraint or pattern validator. The PUT endpoint does not validate that incoming standard field names are actually members of `STANDARD_VIDEO_FIELDS` or `STANDARD_STATIC_FIELDS`. A caller can send arbitrary `api_field_name` values for standard fields (e.g., an empty string or a 10,000-character string) and they will be persisted. The unique constraint on `(brainsuite_app_id, api_field_name)` will catch exact duplicates but not garbage values.

**Fix:** Add `Field(..., min_length=1, max_length=255)` to `FieldMappingStandard.api_field_name`, and optionally validate the name is in the expected set in the PUT endpoint:

```python
api_field_name: str = Field(..., min_length=1, max_length=255, description="...")
```

### IN-02: `auth.py` register endpoint seeds `iconic_color_field` but only adds one `MetadataFieldValue` — inconsistent with other multi-value SELECT fields

**File:** `backend/app/api/v1/endpoints/auth.py:231`

**Issue:** All language SELECT fields receive 31 values (the full `_LANGUAGES` list). `asset_stage_field` receives 3 values. But `iconic_color_field` receives only one value — `"manufactory"`. If the BrainSuite API expects other color scheme options, new orgs are provisioned with an incomplete dropdown. This is a data seeding inconsistency, not a security issue, but it will silently produce incorrect metadata for any org using this field.

**Fix:** Confirm with the BrainSuite API spec whether additional iconic color scheme values exist and add them at registration time, or leave a comment explaining why only one value is expected.

### IN-03: `app_type` denormalized column on `OrgBrainsuiteFieldMapping` is not validated at insert time

**File:** `backend/app/api/v1/endpoints/brainsuite_config.py:434`

**Issue:** The PUT endpoint sets `app_type=app.app_type` from the `BrainsuiteApp` row, which is safe. However, the model column `app_type: Mapped[str] = mapped_column(String(20))` has no `CheckConstraint` limiting it to `"VIDEO"` or `"STATIC"`. The comment on line 63 of the model says `"VIDEO" or "STATIC"` but the BrainsuiteApp itself can be `"MIXED"`. If a MIXED app's mappings are inserted, `app_type="MIXED"` will be stored. The pipeline query in `scoring_job.py` uses `endpoint_type` not `app_type` for routing, so no immediate correctness break occurs, but this denormalized value could mislead future queries.

**Fix:** Add a `CheckConstraint` to the model or document the allowed values:

```python
__table_args__ = (
    UniqueConstraint("brainsuite_app_id", "api_field_name", name="uq_brainsuite_field_mappings_app_field"),
    sa.CheckConstraint("app_type IN ('VIDEO', 'IMAGE', 'MIXED')", name="ck_field_mapping_app_type"),
)
```

### IN-04: `test_field_mapping_endpoints_use_admin_guard` asserts `get_current_user` is never used — but `auth.py` `get_me` uses it legitimately

**File:** `backend/tests/test_phase13_field_mappings.py:53`

**Issue:** The test asserts `"Depends(get_current_user)" not in src` on `brainsuite_config.py`, which is correct for that file. However, the assertion message says "get_current_user should not be used directly" as a blanket rule, which could mislead future developers into thinking the pattern is always wrong. The `auth.py` file uses `get_current_user` correctly in the `/me` endpoint. The test is scoped to the right file, but the comment is overly broad.

**Fix:** Tighten the assertion message to clarify scope:

```python
assert "Depends(get_current_user)" not in src, \
    "brainsuite_config.py must use get_current_admin (not get_current_user) for org isolation"
```

---

_Reviewed: 2026-04-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
