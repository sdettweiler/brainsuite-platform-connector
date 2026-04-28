# Phase 13: Field Mapping Editor + Mandatory Field Enforcement - Research

**Researched:** 2026-04-20
**Domain:** Angular 17 slide panel components, FastAPI async endpoints, dynamic form arrays, scoring pipeline field mapping, mandatory field validation
**Confidence:** HIGH — findings verified directly from codebase, CONTEXT.md locked decisions, and Phase 12 existing patterns

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** The "Configure Field Mappings" trigger lives inside each BrainsuiteApp accordion panel (Phase 12 accordion), alongside the "System App Name" field, not in a separate credentials section
- **D-02:** Clicking the trigger opens a **right-side slide panel** (slides in from the right, page remains visible underneath). No existing side-panel pattern — new CSS component required
- **D-03:** Panel scoped to specific BrainsuiteApp: 12 standard fields for VIDEO apps, 8 standard fields for STATIC apps. No VIDEO/STATIC tabs inside panel
- **D-04:** `org_brainsuite_field_mappings` gains `brainsuite_app_id` FK → `brainsuite_apps.id` (CASCADE delete). Mappings per individual BrainsuiteApp, not per org+app_type. Requires Alembic migration chaining from Phase 11
- **D-05:** `app_type` column on `org_brainsuite_field_mappings` may be kept as denormalized convenience column — Claude's discretion
- **D-06:** When panel opens for app with no mapping rows yet, system **auto-matches** standard fields by name (e.g. `brandValues` → `brainsuite_brand_values`). Pre-matches shown in dropdowns but not persisted until Save
- **D-07:** Each standard field row has **inline dropdown** showing all org metadata fields + "— Unmapped —". No separate edit mode
- **D-08:** Custom fields appear below standard fields. Admin adds via inline **"+ Add custom field"** row with text input for API field name + metadata dropdown. Existing rows have delete icon (`bi-trash`)
- **D-09:** Each row has **toggle switch** in "Mandatory" column. Mandatory rows get subtle visual indicator (light red tint or `bi-asterisk` badge)
- **D-10:** Single **"Save"** button at panel bottom commits all changes (mappings + toggles + custom field adds/deletes) in one `PUT /api/v1/brainsuite-config/apps/{app_id}/field-mappings`. "Cancel" discards changes and closes panel. No auto-save
- **D-11:** **Sticky alert banner** at top of Brainsuite Apps settings page when config incomplete (missing credentials, missing `system_app_name`, or mandatory field unmapped). Uses existing `api-note` styling extended with warning variant
- **D-12:** When pipeline encounters asset where mandatory field has no mapped metadata field or no asset value, asset **stays UNSCORED** and `MANDATORY_FIELD_MISSING` notification created via `create_org_notification`
- **D-13:** Scoring pipeline skips queueing assets for orgs with missing/null `client_id`/`client_secret_encrypted` or null `system_app_name` on relevant app. Assets stay UNSCORED silently (no notification for missing creds — only PIPE-03 UI warning covers)

### Claude's Discretion
- Whether to keep `app_type` as denormalized column or drop it and always derive from BrainsuiteApp row
- Auto-match logic: server-side (GET returns pre-filled rows) or client-side (frontend maps field names before save)
- FMAP-07 notifications: batched (one per scoring run) or per asset
- Exact endpoint shape for field mappings CRUD (suggested: `GET/PUT /api/v1/brainsuite-config/apps/{app_id}/field-mappings`)
- Side panel CSS approach: Angular CDK Overlay, custom absolute-positioned div, or CSS transform slide
- Incomplete config check logic: backend endpoint or derive from existing GET responses on frontend

### Deferred Ideas (OUT OF SCOPE)
- **YouTube cookies DB storage** — Store in `org_brainsuite_config` or dedicated table, add admin API endpoint, update `dv360_sync.py` to read from DB. Deferred to Phase 14

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FMAP-01 | Admin can view and update metadata field mapped to each 12 standard video API fields | Slide panel with dropdown per field; values from metadata_fields table; D-07 |
| FMAP-02 | Admin can view and update metadata field mapped to each 8 standard static API fields | Same as FMAP-01 — `app_type` on BrainsuiteApp filters field list; D-03 |
| FMAP-03 | Admin can add custom API field for video app and select metadata field | "Add custom field" row with text input; dynamically append to FormArray; D-08 |
| FMAP-04 | Admin can add custom API field for static app and select metadata field | Same as FMAP-03 — field scoped by app_type |
| FMAP-05 | Admin can remove custom field mapping (standard fields cannot be removed, only unmapped) | Delete icon on custom field rows; FormArray.removeAt(); validation prevents removing standard fields |
| FMAP-06 | Admin can mark any field (standard or custom) as mandatory | Toggle switch per row; `is_mandatory` column; D-09 visual indicator |
| FMAP-07 | For asset where mandatory field has no mapping or no value, scoring skipped and user notified | Pipeline skips asset, sets UNSCORED, creates `MANDATORY_FIELD_MISSING` notification; D-12 |
| PIPE-02 | Assets for org with incomplete config remain UNSCORED and not queued | Pipeline guard before queuing; D-13; silent (no notification) |
| PIPE-03 | Org admin sees visible warning when config incomplete | Sticky banner on settings page; D-11; lists missing creds/app_name/mandatory fields |

</phase_requirements>

---

## Summary

Phase 13 adds a **field mapping editor slide panel** to the Brainsuite Apps settings page, allowing org admins to configure which metadata fields map to BrainSuite API fields (12 standard for VIDEO, 8 for STATIC), mark fields as mandatory, and add/remove custom fields. The scoring pipeline enforces mandatory field presence and validates that credentials + app names are configured before queueing assets.

**Key architecture changes:**
1. Database: `org_brainsuite_field_mappings` gains `brainsuite_app_id` FK — mappings are now per individual app, not per org+app_type
2. Frontend: New slide panel component (CSS-based, right-side slide from 480px width) with dynamic form rows for standard + custom fields
3. Backend: New endpoint `PUT /api/v1/brainsuite-config/apps/{app_id}/field-mappings` to persist field mapping changes atomically
4. Pipeline: New guards in `scoring_job.py` to (a) skip orgs with missing credentials/app names (PIPE-02), and (b) skip assets with unmapped/missing mandatory fields (FMAP-07)
5. UI: Sticky warning banner on settings page listing incomplete config items (PIPE-03)

**Primary recommendation:** Build slide panel as new Angular component or inline in `brainsuite-apps.component.ts`. Use `ReactiveFormsModule` with `FormArray` for dynamic custom fields. Backend endpoint pattern mirrors Phase 12's `brainsuite_config.py`. Alembic migration adds `brainsuite_app_id` column and migrates existing rows to new schema.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Store field mappings per app | Database | API Backend | `org_brainsuite_field_mappings.brainsuite_app_id` FK |
| Fetch metadata fields for dropdown | API Backend | Database | GET `/apps/{app_id}/field-mappings` includes metadata field list |
| Render slide panel UI | Frontend (Angular) | — | CSS `position: fixed; transform: translateX()` animation, no backend state |
| Manage form state (mappings + custom fields) | Frontend (Angular) | — | `ReactiveFormsModule` FormArray for dynamic rows |
| Auto-match standard fields on first open | Either (Claude's discretion) | — | Server-side simpler for consistency; client-side avoids extra DB query |
| Persist mapping changes atomically | API Backend | Database | Single `PUT` endpoint commits all changes in one transaction |
| Skip orgs with missing credentials | Scoring Pipeline | API Backend | Guard in `scoring_job.py` before queueing; reads `OrgBrainsuiteConfig` |
| Skip assets with unmapped/missing mandatory fields | Scoring Pipeline | Database | Guard in `score_asset_now()` after fetching asset metadata |
| Emit MANDATORY_FIELD_MISSING notification | Scoring Pipeline | Notifications service | Call `create_org_notification()` from `scoring_job.py` |
| Display incomplete config warning | Frontend (Angular) | API Backend | Sticky banner derived from GET `/credentials` + per-app data |
| Validate mandatory field presence | API Backend | Scoring Pipeline | Pipeline enforces; frontend shows UI indicator only |

---

## Standard Stack

### Core (all already in project — no new installs)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | project-current | Async routing, Pydantic validation for field mapping payloads | All other endpoints use this; Phase 12 established pattern |
| SQLAlchemy async | project-current | ORM + querying for field mappings, metadata fields | All other endpoints use this |
| Alembic | project-current | DB migration to add `brainsuite_app_id` FK | Phase 11 migration is direct predecessor; migration chaining follows project pattern |
| Angular 17 + Material | project-current | Slide panel component, form controls, dropdowns, toggle switches | All config pages use this; ReactiveFormsModule already in use |
| ReactiveFormsModule + FormBuilder | project-current | Reactive form for dynamic custom field rows (FormArray) | Phase 12 established pattern in brainsuite-apps component |
| Bootstrap Icons (bi-*) | project-current | Icons: `bi-asterisk` (mandatory indicator), `bi-trash` (delete), `bi-x` (close panel) | Already used throughout UI |

**Installation:** Nothing new to install — all dependencies already present.

**Version verification:** [VERIFIED: codebase] Angular 17, Material, FastAPI, SQLAlchemy async, Alembic are all actively used in existing code (Phase 12, scoring pipeline, models).

---

## Architecture Patterns

### System Architecture Diagram

```
[Admin Browser]
     |
     | Click "Configure Field Mappings" in accordion
     | (opens slide panel from right side, page stays visible)
     |
     | GET /api/v1/brainsuite-config/apps/{app_id}/field-mappings
     |   <-- {standard_fields: [{api_field, metadata_field_id, is_mandatory, ...}], 
     |        custom_fields: [...], metadata_options: [{id, name, field_type}, ...]}
     |   (pre-matched metadata_field_ids populated by server)
     |
     | Admin edits in slide panel:
     |   - Change metadata dropdown for standard field
     |   - Toggle mandatory switch on any field
     |   - Add custom field via "+" row (new API field name + dropdown)
     |   - Delete custom field (bi-trash icon)
     |
     | Click Save → PUT /api/v1/brainsuite-config/apps/{app_id}/field-mappings
     |   --> {standard_fields: [...], custom_fields: [...]}
     |   <-- 200 / {success: bool}
     |
     | Panel closes, page-top banner updates if config now complete
     |
[FastAPI /api/v1/brainsuite-config/apps/{app_id}/field-mappings]
     |
     | GET: SELECT metadata_fields WHERE org = current_user.org
     |      SELECT field_mappings WHERE app_id = app_id
     |      Return auto-matched pre-filled rows for standard fields
     |
     | PUT: UPSERT all rows (delete removed custom, insert new, update existing)
     |      Validate: at most 8 (STATIC) or 12 (VIDEO) standard fields
     |      Validate: custom field names not duplicating standard names
     |
[PostgreSQL]
     |
     | org_brainsuite_field_mappings(brainsuite_app_id, api_field_name, 
     |                                metadata_field_id, is_mandatory, is_custom)
     | metadata_fields(id, name, field_type)
     | metadata_field_values(field_id, value, label)  ← for SELECT fields

[Scoring Pipeline — scoring_job.py]
     |
     | Phase 2.5 (new guard): Before queuing asset, check:
     |   - org has OrgBrainsuiteConfig with client_id + secret (PIPE-02)
     |   - relevant BrainsuiteApp has system_app_name (PIPE-02)
     |   - if asset fails either check → stays UNSCORED, no notification
     |
     | Phase 3 (new guard in _process_asset): After fetching asset metadata:
     |   - For each field marked is_mandatory on the app's field mappings
     |   - Check: does asset have AssetMetadataValue for that metadata_field_id?
     |   - If any mandatory field is missing → skip asset, stay UNSCORED,
     |     create MANDATORY_FIELD_MISSING notification (FMAP-07)
```

### Recommended Project Structure

**New files to create:**
```
backend/app/schemas/
├── brainsuite_field_mappings.py     # New: FieldMappingResponse, FieldMappingUpdate, MetadataFieldOption

backend/alembic/versions/
├── v5y6z7a8b9c_phase13_field_mappings_per_app.py  # New migration

backend/tests/
├── test_phase13_field_mappings.py   # New: unit tests for endpoint + field validation

frontend/src/app/features/configuration/pages/
├── field-mappings-panel.component.ts  # New: slide panel component (or inline in brainsuite-apps)
├── brainsuite-apps.component.ts        # Modified: add panel trigger button, banner logic
```

**Modified files:**
```
backend/app/api/v1/endpoints/
├── brainsuite_config.py             # Add new route: GET/PUT /apps/{app_id}/field-mappings

backend/app/services/sync/
├── scoring_job.py                   # Add PIPE-02 + FMAP-07 guards

backend/app/services/
├── notifications.py                 # Uses existing create_org_notification()

backend/app/models/
├── brainsuite_config.py             # Add brainsuite_app_id FK to OrgBrainsuiteFieldMapping
```

### Pattern 1: Dynamic Field Mapping Form with Custom Fields (Frontend)

**What:** Reactive form using FormArray for custom fields; standard fields from pre-fetched list; inline dropdowns + toggle switches for each row.

**When to use:** Any form that collects variable-length lists of field mappings with add/remove capability.

**Example:**
```typescript
// Source: Adapted from ReactiveFormsModule pattern in existing brainsuite-apps.component.ts
// Standard fields are controls in a FormGroup; custom fields in a FormArray

constructor(private fb: FormBuilder) {
  this.form = this.fb.group({
    standard_fields: this.fb.group({
      // One control per standard field: brainsuiteFieldName -> FormControl(metadataFieldId)
      assetName: this.fb.control(null),
      brandValues: this.fb.control(null),
      // ... 10 more for VIDEO, 6 more for STATIC
    }),
    custom_fields: this.fb.array([
      // Each custom field: {api_field_name, metadata_field_id, is_mandatory}
    ]),
  });
}

// Add custom field row
addCustomField() {
  const customArray = this.form.get('custom_fields') as FormArray;
  customArray.push(this.fb.group({
    api_field_name: ['', Validators.required],
    metadata_field_id: [null],
    is_mandatory: [false],
  }));
}

// Save all changes in one request
async save() {
  const payload = {
    standard_fields: Object.entries(this.form.get('standard_fields')!.value)
      .map(([api_field, metadata_field_id]) => ({
        api_field_name: api_field,
        metadata_field_id,
        is_mandatory: this.mandatoryToggles[api_field] || false,
      })),
    custom_fields: (this.form.get('custom_fields') as FormArray).value,
  };
  
  await this.api.put(`/api/v1/brainsuite-config/apps/${this.appId}/field-mappings`, payload)
    .toPromise();
}
```

### Pattern 2: Slide Panel CSS (Frontend)

**What:** Fixed-position panel sliding in from the right edge using CSS transforms. Page content remains visible underneath with optional semi-transparent backdrop.

**When to use:** Any modal-like form that doesn't require full page focus (e.g., side-by-side editing).

**Example:**
```css
/* Source: Custom CSS pattern; no existing cdk-overlay in brainsuite-apps */

.slide-panel-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  opacity: 0;
  transition: opacity 200ms ease-in-out;
  z-index: 999;
}

.slide-panel-backdrop.active {
  opacity: 1;
}

.slide-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 480px;
  height: 100vh;
  background: var(--bg-card);
  border-left: 1px solid var(--border);
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  
  transform: translateX(100%);
  transition: transform 200ms cubic-bezier(0.4, 0, 0.2, 1);
  overflow-y: auto;
}

.slide-panel.open {
  transform: translateX(0);
}

.slide-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.slide-panel-body {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.slide-panel-footer {
  padding: 20px 24px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  flex-shrink: 0;
}
```

### Pattern 3: Field Mapping UPSERT Backend (Backend)

**What:** Single endpoint that deletes old mappings for the app and inserts all new ones in one transaction. Validates field names and counts.

**When to use:** Any atomic bulk update of a variable-length collection.

**Example:**
```python
# Source: FastAPI + SQLAlchemy pattern from brainsuite_config.py (Phase 12)
# Adapted for dynamic field lists

@router.put("/apps/{app_id}/field-mappings", response_model=dict)
async def upsert_field_mappings(
    app_id: uuid.UUID,
    payload: FieldMappingUpdate,  # Contains standard_fields + custom_fields lists
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Persist field mappings for a single BrainsuiteApp."""
    
    app = await db.get(BrainsuiteApp, app_id)
    if not app or app.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="App not found")
    
    # Validate: no more than 12 (VIDEO) / 8 (STATIC) standard fields
    max_standard = 12 if app.app_type == "VIDEO" else 8
    if len(payload.standard_fields) > max_standard:
        raise HTTPException(
            status_code=400,
            detail=f"Too many standard fields for {app.app_type} app"
        )
    
    # Delete old mappings for this app
    await db.execute(
        delete(OrgBrainsuiteFieldMapping).where(
            OrgBrainsuiteFieldMapping.brainsuite_app_id == app_id
        )
    )
    
    # Insert new mappings from standard_fields
    for field in payload.standard_fields:
        mapping = OrgBrainsuiteFieldMapping(
            brainsuite_app_id=app_id,
            organization_id=current_user.organization_id,
            api_field_name=field.api_field_name,
            metadata_field_id=field.metadata_field_id,
            is_mandatory=field.is_mandatory,
            is_custom=False,
            app_type=app.app_type,  # denormalized for convenience (D-05)
        )
        db.add(mapping)
    
    # Insert new mappings from custom_fields
    for field in payload.custom_fields:
        # Validate: custom field names don't duplicate standard names
        standard_names = {f.api_field_name for f in payload.standard_fields}
        if field.api_field_name in standard_names:
            raise HTTPException(status_code=400, detail="Custom field name conflicts with standard field")
        
        mapping = OrgBrainsuiteFieldMapping(
            brainsuite_app_id=app_id,
            organization_id=current_user.organization_id,
            api_field_name=field.api_field_name,
            metadata_field_id=field.metadata_field_id,
            is_mandatory=field.is_mandatory,
            is_custom=True,
            app_type=app.app_type,
        )
        db.add(mapping)
    
    await db.commit()
    return {"success": True}
```

### Pattern 4: Pipeline Field Validation (Backend — scoring_job.py)

**What:** Before scoring an asset, check that all mandatory fields have both (a) a metadata field mapping and (b) a value on the asset.

**When to use:** Any asset processing that has conditional requirements.

**Example:**
```python
# Source: Adapted from scoring_job.py pattern
# Called inside _process_asset() after fetching asset metadata

async def _check_mandatory_fields(
    db: AsyncSession,
    asset_id: uuid.UUID,
    app_id: uuid.UUID,
) -> tuple[bool, list[str]]:
    """
    Check if asset has all mandatory field values.
    
    Returns: (is_valid, missing_field_names)
    """
    # Fetch mandatory field mappings for this app
    result = await db.execute(
        select(OrgBrainsuiteFieldMapping).where(
            OrgBrainsuiteFieldMapping.brainsuite_app_id == app_id,
            OrgBrainsuiteFieldMapping.is_mandatory == True,
        )
    )
    mandatory_mappings = result.scalars().all()
    
    missing_fields = []
    for mapping in mandatory_mappings:
        if not mapping.metadata_field_id:
            # Mapped to nothing — field is unmapped
            missing_fields.append(mapping.api_field_name)
            continue
        
        # Check if asset has a value for this metadata field
        result = await db.execute(
            select(AssetMetadataValue).where(
                AssetMetadataValue.asset_id == asset_id,
                AssetMetadataValue.metadata_field_id == mapping.metadata_field_id,
            )
        )
        value_row = result.scalar_one_or_none()
        
        if not value_row or not value_row.value:
            missing_fields.append(mapping.api_field_name)
    
    return (len(missing_fields) == 0, missing_fields)
```

### Anti-Patterns to Avoid

- **Separate request per field mapping:** Don't issue one PUT per field. Use a single atomic endpoint that updates all fields at once (D-10). Multiple requests risk partial updates if one fails.
- **Storing auto-matched fields without user confirmation:** D-06 states pre-matches are shown in dropdowns but "not persisted until Save". Don't silently persist on field detection.
- **Keeping mandatory fields editable after marking:** Once a field is marked mandatory, its mapping becomes critical. Consider disabling the dropdown (read-only once mandatory) or at minimum showing a warning banner.
- **Pipeline notifications for missing credentials:** D-13 says missing credentials cause silent UNSCORED (no notification). Only PIPE-03 UI warning covers this case. Don't emit notifications for missing creds in the pipeline.
- **Renaming standard field names:** API field names like `assetName`, `brandValues` are BrainSuite API contracts. Don't rename them. Use only for custom fields.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dynamic form fields (add/remove at runtime) | Custom array manipulation logic | `ReactiveFormsModule` FormArray + FormBuilder | Handles validation, dirty state, reset; prevents bugs with array indices |
| Slide-in panel animation | Inline `setTimeout` + manual DOM manipulation | CSS `transform: translateX()` with transition | Smoother, composable, doesn't jank on slow devices; cleaner separation of concerns |
| Encrypted credential storage | Plain-text in database | `encrypt_token()` / `decrypt_token()` from `security.py` | Project already has Fernet setup; centralizes encryption logic; prevents accidental plain-text leakage |
| Field validation (required, type constraints) | Manual `if` checks in endpoint | Pydantic schema validation | Catches errors early, provides consistent error messages, auto-generates OpenAPI docs |
| Per-org multi-row relational data with FK | Storing JSON or multiple tables | SQLAlchemy ORM with proper FK relationships | Maintains referential integrity, enables queries across relationships, simplifies migrations |
| Notification dispatch | Direct DB insert in scoring loop | `create_org_notification()` service | Centralizes notification logic, handles async dispatch, prevents duplicate notifications |

**Key insight:** Mandatory field validation and field mapping are domain-specific features that require careful coordination between frontend form state, database schema, and pipeline logic. Using existing framework patterns (ReactiveFormsModule, Alembic migrations, FastAPI schemas) prevents mistakes in this critical path.

---

## Common Pitfalls

### Pitfall 1: Schema Migration Forgot to Backfill brainsuite_app_id
**What goes wrong:** New `brainsuite_app_id` FK on `org_brainsuite_field_mappings` is added, but existing rows have `NULL` because there's no backfill logic. Those rows become orphaned or inaccessible.

**Why it happens:** Alembic down_revision chaining is not checked; developer assumes migration framework auto-populates FKs.

**How to avoid:** In the migration `upgrade()` function, after adding the column, join existing rows to their corresponding BrainsuiteApp using `organization_id` + `app_type` to derive the app_id. See Phase 12's migration for FK pattern.

**Warning signs:** After migration, `SELECT COUNT(*) FROM org_brainsuite_field_mappings WHERE brainsuite_app_id IS NULL` returns a non-zero count. Or, loading field mappings in API fails with FK constraint error.

### Pitfall 2: Mandatory Field Toggle Has No Visual Distinction
**What goes wrong:** Admin marks a field mandatory but the UI gives no visual feedback. Admin forgets which fields are mandatory. Pipeline silently skips assets, admin confused why scoring stopped.

**Why it happens:** Toggle switch works, but no CSS styling or icon applied. Admin relies on memory instead of visual cue.

**How to avoid:** Per D-09, mandatory rows get "subtle visual indicator" — implement as row background tint (light red/warn color) OR `bi-asterisk` icon badge on field name. Test this visually before submission.

**Warning signs:** Viewing the form after toggling mandatory on a field, the field looks identical to non-mandatory fields. Or, admin manual test finds inconsistency between UI state and actual stored `is_mandatory` value.

### Pitfall 3: Auto-Match Logic Runs Every Panel Open, Overwrites User Edits
**What goes wrong:** D-06 states auto-matches happen on first open and are "not persisted until Save". But if logic re-runs on every open, and user edits a dropdown, then closes + reopens panel, their edit is lost.

**Why it happens:** Auto-match logic runs in component init or ngOnInit instead of only on first fetch.

**How to avoid:** Auto-match logic runs only once during GET response processing. Store the result in component state. Subsequent opens use the cached state. Only clear cache if user clicks "Reset to Defaults" or closes panel without saving.

**Warning signs:** Manual test: open panel, edit a field mapping, close panel (Cancel), re-open — the field mapping is back to the auto-matched value instead of the edited value.

### Pitfall 4: Custom Field Name Validation Allows Duplicate API Field Names
**What goes wrong:** Admin adds two custom fields both named `custom_brand_extension`. On Save, one silently overwrites the other in the database (or constraint violation on commit). Admin loses data.

**Why it happens:** Frontend validation only checks against standard fields (D-08 prevents standard field conflicts) but doesn't validate uniqueness within custom fields themselves.

**How to avoid:** Frontend should validate as user types: `[custom_field1.api_field_name, custom_field2.api_field_name, ...]` must all be unique. Backend should enforce same validation in PUT endpoint and return 400 if duplicate detected.

**Warning signs:** Admin adds two custom fields with the same API name. Frontend doesn't show an error. On Save, only one field persists in database.

### Pitfall 5: Incomplete Config Banner Never Disappears After Saving Mandatory Field
**What goes wrong:** D-11 says banner appears when "any mandatory field with no metadata mapping". Admin marks a field mandatory, sees banner, then maps the field to a metadata field and saves. Banner should disappear, but doesn't.

**Why it happens:** Frontend banner logic computes incompleteness once on page load but doesn't refresh after the slide panel closes with a successful save.

**How to avoid:** After successful PUT to field-mappings endpoint, refetch the incomplete config state from the backend (either from same endpoint response or via a dedicated GET). Update the banner visibility based on fresh data.

**Warning signs:** After saving field mappings that fix all incomplete items, page-top warning banner still shows the old warnings. Refresh page makes banner disappear (confirming fresh fetch needed).

### Pitfall 6: Pipeline Asset Skip Doesn't Create Notification When Should
**What goes wrong:** Asset is skipped due to missing mandatory field (FMAP-07), but notification is never created. Admin has no idea why scoring stopped.

**Why it happens:** `create_org_notification()` call is missing from `_process_asset()` in scoring_job.py. Or, call is there but `await` is missing, causing async task to be queued but not awaited, potentially lost.

**How to avoid:** Check scoring_job.py line where field validation fails. Immediately after setting `scoring_status = UNSCORED`, call `await create_org_notification()` synchronously. Include asset ID and field names in notification message. Use existing SCORING_BATCH_COMPLETE as template.

**Warning signs:** Test by creating asset with missing mandatory metadata. Run scoring cycle. Asset stays UNSCORED. Check organization's notifications table — no MANDATORY_FIELD_MISSING row exists.

---

## Runtime State Inventory

> Phase 13 is a feature-add, not a rename/refactor. No runtime state inventory needed.

---

## Code Examples

### Example 1: Standard 12 Video Fields for Auto-Match

```typescript
// Source: CONTEXT.md specifics section + requirements
// Use this list to pre-populate dropdowns and validate field counts

const STANDARD_VIDEO_FIELDS = [
  'channel',
  'projectName',
  'assetName',
  'assetStage',
  'assetLanguage',
  'brandNames',
  'voiceOver',
  'voiceOverLanguage',
  'intendedMessages',
  'intendedMessagesLanguage',
  'brandValues',
  'brandValuesLanguage',
];

const STANDARD_STATIC_FIELDS = [
  'channel',
  'projectName',
  'assetLanguage',
  'iconicColorScheme',
  'intendedMessages',
  'intendedMessagesLanguage',
  'brandValues',
  'brandValuesLanguage',
];

// Auto-match candidates (D-06 examples)
const AUTO_MATCH_HINTS = {
  'brandValues': 'brainsuite_brand_values',
  'brandValuesLanguage': 'brainsuite_brand_values_language',
  'assetLanguage': 'brainsuite_asset_language',
  'voiceOverLanguage': 'brainsuite_voice_over_language',
  'assetName': 'brainsuite_asset_name',
};
```

### Example 2: Incomplete Config Warning Banner Logic

```typescript
// Source: Phase 12 pattern (test-connection status block) extended

get incompleteConfigItems(): string[] {
  const items: string[] = [];
  
  // Check credentials
  if (!this.credentials?.client_id || !this.credentials?.has_secret) {
    items.push('Missing BrainSuite credentials');
  }
  
  // Check app names
  for (const app of this.apps) {
    if (!app.system_app_name) {
      items.push(`${app.name} has no API app name`);
    }
  }
  
  // Check mandatory fields (fetch from backend or derive from cached field mappings)
  for (const app of this.apps) {
    const mappings = this.appFieldMappings[app.id];
    if (!mappings) continue;
    
    const unmappedMandatory = mappings.filter(m => m.is_mandatory && !m.metadata_field_id);
    if (unmappedMandatory.length > 0) {
      items.push(`${app.name}: ${unmappedMandatory.length} mandatory field(s) unmapped`);
    }
  }
  
  return items;
}

get showIncompleteWarning(): boolean {
  return this.incompleteConfigItems.length > 0;
}
```

### Example 3: Field Mapping Pydantic Schema

```python
# Source: FastAPI + Pydantic pattern from brainsuite_config.py (Phase 12)

from pydantic import BaseModel, Field
from typing import Optional
import uuid

class FieldMappingStandard(BaseModel):
    api_field_name: str = Field(..., description="Standard BrainSuite API field name")
    metadata_field_id: Optional[uuid.UUID] = Field(None, description="Mapped metadata field, or None for unmapped")
    is_mandatory: bool = Field(False, description="If True, asset skipped if value missing")

class FieldMappingCustom(BaseModel):
    api_field_name: str = Field(..., min_length=1, max_length=255)
    metadata_field_id: Optional[uuid.UUID] = Field(None)
    is_mandatory: bool = Field(False)

class FieldMappingUpdate(BaseModel):
    standard_fields: list[FieldMappingStandard] = Field(
        ..., 
        max_items=12,  # VIDEO apps can have max 12 standard fields
        description="Updated standard field mappings"
    )
    custom_fields: list[FieldMappingCustom] = Field(
        default_factory=list,
        description="Added/updated custom field mappings"
    )

class MetadataFieldOption(BaseModel):
    id: uuid.UUID
    name: str
    label: str
    field_type: str  # SELECT, TEXT, NUMBER

class FieldMappingResponse(BaseModel):
    app_id: uuid.UUID
    app_type: str  # VIDEO or STATIC
    standard_fields: list[FieldMappingStandard]
    custom_fields: list[FieldMappingCustom]
    metadata_options: list[MetadataFieldOption]
    
    class Config:
        from_attributes = True
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded `ACE_VIDEO_SMV_API` in scoring endpoint URL | Per-app `system_app_name` configured via UI (Phase 12) + field mappings per app (Phase 13) | Phase 12 started, Phase 13 completes | Admins now have full control over API app routing without code changes |
| Single global field mapping for all orgs | Per-org, per-app field mappings stored in `org_brainsuite_field_mappings` | Phase 11 created table, Phase 13 populates it | Multi-tenant support: each org can customize field mappings independently |
| No enforcement of required BrainSuite fields | Mandatory field marking + pipeline validation (FMAP-07, PIPE-02) | Phase 13 | Scores are now valid only when all critical metadata is present; prevents silent data loss |
| Email notifications only | In-app notifications via `create_org_notification()` for MANDATORY_FIELD_MISSING | Phase 13 (notification service from Phase 9) | Admins get immediate, in-context alerts when assets are skipped |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ReactiveFormsModule` FormArray is the right choice for dynamic custom fields | Pattern 1 | If FormArray doesn't integrate well with the existing form layout, may need custom manual array management |
| A2 | CSS `transform: translateX()` approach for slide panel is performant enough | Pattern 2 | If animation is janky on older browsers, may need to downgrade to simpler fade-in or use Angular CDK Overlay |
| A3 | Auto-match logic should be server-side (GET response) not client-side | D-06 discretion | If server-side is too slow (many metadata fields), may need client-side pre-matching logic instead |
| A4 | Batched MANDATORY_FIELD_MISSING notifications (one per scoring run) not per-asset | D-12 discretion | If per-asset notifications needed, would require different notification batching logic in pipeline |

**If any of these assumptions prove wrong, planner will need to re-evaluate approach with discuss-phase.**

---

## Environment Availability

Step 2.6: SKIPPED (Phase 13 is code/UI-only, no external dependencies beyond project's own database, API, frontend runtime)

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (backend) + Jasmine/Karma (frontend) |
| Config file | `backend/tests/conftest.py`, `karma.conf.js` |
| Quick run command (backend) | `pytest tests/test_phase13_field_mappings.py -x` |
| Full suite command (backend) | `pytest tests/ -k "phase13 or brainsuite" --tb=short` |
| Quick run command (frontend) | `ng test --browsers=Chrome --watch=true --include="**/*field-mapping*.spec.ts"` |
| Full suite command (frontend) | `ng test --watch=false --code-coverage` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FMAP-01 | Admin can view 12 video standard fields + current metadata mapping | unit | `pytest tests/test_phase13_field_mappings.py::test_get_field_mappings_video -x` | ❌ Wave 0 |
| FMAP-02 | Admin can view 8 static standard fields + current metadata mapping | unit | `pytest tests/test_phase13_field_mappings.py::test_get_field_mappings_static -x` | ❌ Wave 0 |
| FMAP-03 | Admin can add custom video field + map to metadata field | unit | `pytest tests/test_phase13_field_mappings.py::test_add_custom_field_video -x` | ❌ Wave 0 |
| FMAP-04 | Admin can add custom static field + map to metadata field | unit | `pytest tests/test_phase13_field_mappings.py::test_add_custom_field_static -x` | ❌ Wave 0 |
| FMAP-05 | Admin cannot remove standard fields; can remove custom fields | unit | `pytest tests/test_phase13_field_mappings.py::test_remove_custom_field -x` | ❌ Wave 0 |
| FMAP-06 | Admin can toggle mandatory flag on any field | unit | `pytest tests/test_phase13_field_mappings.py::test_toggle_mandatory -x` | ❌ Wave 0 |
| FMAP-07 | Asset with unmapped/missing mandatory field stays UNSCORED + notification created | integration | `pytest tests/test_phase13_field_mappings.py::test_scoring_skips_missing_mandatory -x` | ❌ Wave 0 |
| PIPE-02 | Assets for org with missing credentials/app_name stay UNSCORED, not queued | integration | `pytest tests/test_phase13_field_mappings.py::test_pipeline_guard_missing_config -x` | ❌ Wave 0 |
| PIPE-03 | Sticky warning banner appears when config incomplete | e2e | `ng test --include="**/*brainsuite-apps*.spec.ts" -k "incomplete-warning"` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** Run quick command for the requirement being implemented (e.g., `pytest tests/test_phase13_field_mappings.py::test_get_field_mappings_video -x`)
- **Per wave merge:** `pytest tests/test_phase13_field_mappings.py -x` (all phase 13 field mapping tests)
- **Phase gate:** `pytest tests/ -k "phase13 or brainsuite" --tb=short` (all brainsuite-related tests) + `ng test --watch=false --code-coverage` (frontend) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_phase13_field_mappings.py` — covers FMAP-01 through PIPE-02
- [ ] `frontend/src/app/features/configuration/pages/brainsuite-apps.component.spec.ts` (extend Phase 12 tests) — covers FMAP-05/06 UI interactions + PIPE-03 banner
- [ ] `backend/tests/test_phase13_scoring_pipeline.py` — covers FMAP-07/PIPE-02 scoring guards
- [ ] Integration tests for auto-match logic (server-side or client-side depending on D-06 decision)
- [ ] Bootstrap fixtures: create test org with metadata fields, BrainsuiteApps (VIDEO + STATIC), CreativeAssets with metadata values

*(If no gaps: Update when Phase 13 PLAN is created and test scaffolding determined)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `get_current_admin` Depends required for all field mapping endpoints; only org admin can modify mappings |
| V3 Session Management | yes | FastAPI session tokens; no new session handling in Phase 13 |
| V4 Access Control | yes | Org isolation: `app.organization_id == current_user.organization_id` check before any CRUD on field mappings |
| V5 Input Validation | yes | Pydantic schema validates field names (alphanumeric, max length), field count limits (8/12), metadata_field_id exists + belongs to same org |
| V6 Cryptography | yes | No new cryptography in Phase 13; Client Secret already encrypted (Phase 12) |
| V8 Data Protection | yes | Field mappings are not sensitive; no PII stored. Metadata field values (asset data) handled by existing CreativeAsset model |

### Known Threat Patterns for {Angular + FastAPI + PostgreSQL}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unauthorized field mapping modification (attacker changes another org's mappings) | Tampering | Always check `current_user.organization_id == app.organization_id` before update. Use `get_current_admin` dependency |
| Malicious field name injection (attacker adds field name with SQL/NoSQL syntax) | Injection | Pydantic validates `api_field_name` as alphanumeric + underscore only. SQLAlchemy parameterized queries prevent injection |
| Mandatory field toggle enables scoring of incomplete data | Tampering | Pipeline validation (FMAP-07) is independent of UI state. Toggle affects database, pipeline enforces. Pipeline reads from DB, not from frontend |
| Cross-tenant data leakage via field mapping queries | Information Disclosure | All queries filter by `organization_id`. Metadata field options fetched for current org only (GET endpoint) |
| Missing field validation allows asset scores with invalid metadata | Tampering | Pipeline guard in `_check_mandatory_fields()` prevents scoring. Pre-save validation in endpoint ensures no invalid mappings persisted |

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: codebase] Phase 12 RESEARCH.md — established patterns for BrainSuite config endpoints, credentials encryption, async form handling, Alembic migration chaining
- [VERIFIED: codebase] `backend/app/api/v1/endpoints/brainsuite_config.py` (Phase 12) — endpoint pattern, async Depends, get_current_admin usage
- [VERIFIED: codebase] `backend/app/models/brainsuite_config.py` — OrgBrainsuiteConfig + OrgBrainsuiteFieldMapping schema; FK relationships
- [VERIFIED: codebase] `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts` — ReactiveFormsModule + FormBuilder pattern, MatSnackBar usage, accordion expand/collapse state
- [VERIFIED: codebase] `backend/app/services/sync/scoring_job.py` — scoring pipeline flow, notification dispatch pattern via `create_org_notification()`
- [VERIFIED: codebase] CONTEXT.md decisions D-01 through D-13 — all locked architectural choices

### Secondary (MEDIUM confidence)
- [CITED: Phase 12 RESEARCH.md] Credentials encryption pattern using `encrypt_token()` from `security.py` — applied to field mapping payloads in same way
- [CITED: codebase patterns] FormArray usage in similar dynamic-list components (though not found in exact current codebase, standard Angular pattern widely used)
- [CITED: existing CSS patterns] `api-note` warning styling in brainsuite-apps.component.ts — extended for sticky banner variant

---

## Metadata

**Confidence breakdown:**
- **Standard Stack:** HIGH — all libraries already in use, no new dependencies
- **Architecture:** HIGH — patterns directly copied from Phase 12 established work + existing codebase
- **Pitfalls:** MEDIUM-HIGH — based on common form validation + pipeline guard mistakes observed in similar projects
- **Runtime State:** N/A — feature-add, no rename/refactor state inventory

**Research date:** 2026-04-20
**Valid until:** 2026-05-04 (14 days — moderate-stability domain with established patterns, no API changes expected)

---

*End of Research — Ready for Planning*
