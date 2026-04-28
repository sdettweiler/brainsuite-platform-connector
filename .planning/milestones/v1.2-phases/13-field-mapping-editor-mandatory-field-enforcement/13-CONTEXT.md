# Phase 13: Field Mapping Editor + Mandatory Field Enforcement - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Frontend + backend work to give org admins per-app BrainSuite API field mappings:

1. **Field Mapping Editor** — Right-side slide panel opened from each BrainsuiteApp accordion. Admin maps 12 video or 8 static standard fields to org metadata fields, adds/removes custom fields, and toggles mandatory flags. Changes saved atomically via a single PUT.

2. **DB schema update** — `org_brainsuite_field_mappings` gains a `brainsuite_app_id` FK so mappings are stored per individual app (not per org+app_type). Requires migration.

3. **Mandatory Field Enforcement (FMAP-07)** — Pipeline skips assets where a mandatory field has no metadata mapping or no asset value, stays UNSCORED, and emits a `MANDATORY_FIELD_MISSING` in-app notification listing the missing field(s).

4. **Incomplete config warning (PIPE-02, PIPE-03)** — Pipeline does not queue assets for orgs without credentials/app name. A sticky page-top alert banner appears on the Brainsuite Apps settings page when config is incomplete.

**Not in Phase 13:** YouTube cookie DB-backed storage (deferred to Phase 14).

</domain>

<decisions>
## Implementation Decisions

### Field Mapping Panel — Entry Point
- **D-01:** The "Configure Field Mappings" trigger lives inside each BrainsuiteApp accordion panel (Phase 12 accordion). The trigger button appears alongside the "System App Name" field in the expanded accordion, not in the credentials section.
- **D-02:** Clicking the trigger opens a **right-side slide panel** (slides in from the right, page remains visible underneath). No existing side-panel pattern — new CSS component required.
- **D-03:** The panel is scoped to the specific BrainsuiteApp that was clicked. It shows only the fields for that app's type: 12 standard fields for VIDEO apps, 8 standard fields for STATIC apps. No VIDEO/STATIC tabs needed inside the panel.

### DB Schema — Per-App Mappings
- **D-04:** `org_brainsuite_field_mappings` gains a `brainsuite_app_id` UUID FK → `brainsuite_apps.id` (CASCADE delete). Mappings are per individual BrainsuiteApp, not per org+app_type. Requires Alembic migration chaining from `v3w4x5y6z7a8_backfill_default_metadata_fields.py`.
- **D-05:** `app_type` column on `org_brainsuite_field_mappings` may be kept as a denormalized convenience column (derivable from the BrainsuiteApp row) — Claude's discretion. Unique constraint (if added) should be on `(brainsuite_app_id, api_field_name)`.

### Default Mappings on First Open
- **D-06:** When a panel opens for an app with no mapping rows yet, the system **auto-matches** standard fields to org metadata fields by name where obvious matches exist (e.g. `brandValues` → `brainsuite_brand_values`, `assetLanguage` → `brainsuite_asset_language`, `voiceOverLanguage` → `brainsuite_voice_over_language`). These pre-matches are shown in the dropdowns but not persisted until the admin clicks Save.

### Mapping Edit UX
- **D-07:** Each standard field row has an **inline dropdown (always visible)** showing all org metadata fields as options, plus a blank "— Unmapped —" option. No separate edit mode — admin picks directly from the dropdown.
- **D-08:** Custom fields appear below the standard fields list. Admin adds custom fields via an inline **"+ Add custom field"** row that reveals a text input for the API field name + a metadata field dropdown. Existing custom field rows have a delete (`bi-trash`) icon to remove them.

### Mandatory Toggle
- **D-09:** Each row has a **toggle switch** in a "Mandatory" column. Toggle ON = this field is mandatory; scoring skips assets that have no value for this field. Mandatory rows get a subtle visual indicator when toggled on (e.g. light red row tint or `bi-asterisk` badge on the field name).

### Save Behavior
- **D-10:** A single **"Save"** button at the bottom of the slide panel commits all changes (mappings + mandatory toggles + custom field additions/deletions) in one `PUT /api/v1/brainsuite-config/apps/{app_id}/field-mappings` request. A "Cancel" button discards all pending changes and closes the panel. No auto-save.

### Incomplete Config Warning (PIPE-03)
- **D-11:** A **sticky alert banner** appears at the top of the Brainsuite Apps settings page (above all section cards) when the org's BrainSuite configuration is incomplete (missing credentials, missing system_app_name on any app, or any mandatory field with no metadata mapping). The banner disappears once all incomplete conditions are resolved. It uses the existing `api-note` styling pattern extended with a warning/alert variant.

### Pipeline Enforcement (FMAP-07)
- **D-12:** When the scoring pipeline encounters an asset where a mandatory field has no mapped metadata field, or the asset has no value for that field, the asset is **left UNSCORED** (not FAILED) and a `MANDATORY_FIELD_MISSING` notification is created for the org via the existing `create_org_notification` service. Notification title: "Scoring skipped — mandatory field missing". Message lists the field name(s) and the affected asset name/ID.

### Incomplete Config Pipeline Guard (PIPE-02)
- **D-13:** The scoring pipeline (`scoring_job.py`) skips queueing assets for orgs where `OrgBrainsuiteConfig` is missing or has null `client_id` / `client_secret_encrypted`, or where the relevant `BrainsuiteApp.system_app_name` is null. Assets stay UNSCORED silently (no notification for missing credentials — only PIPE-03 UI warning covers this case).

### Claude's Discretion
- Whether to keep `app_type` as a denormalized column on `org_brainsuite_field_mappings` or drop it and always derive from the BrainsuiteApp row
- Auto-match logic: whether pre-matching happens server-side (GET returns pre-filled rows) or client-side (frontend maps field names to known metadata field slugs before saving)
- Whether FMAP-07 notifications are batched (one notification per scoring run summarizing all skipped assets) or emitted per asset
- Exact endpoint shape for field mappings CRUD (suggested: `GET /api/v1/brainsuite-config/apps/{app_id}/field-mappings`, `PUT /api/v1/brainsuite-config/apps/{app_id}/field-mappings`)
- Side panel CSS approach (Angular CDK Overlay, custom absolute-positioned div, or CSS transform slide)
- Incomplete config check logic — whether to compute incompleteness in the backend (dedicated endpoint) or derive from existing GET responses on the frontend

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Schema — Models to Modify
- `backend/app/models/brainsuite_config.py` — `OrgBrainsuiteFieldMapping` model; `brainsuite_app_id` FK column to add; index to update
- `backend/app/models/platform.py` — `BrainsuiteApp` model; `app_type` field (VIDEO/STATIC) and `system_app_name` column added in Phase 12

### Migrations — Chain Reference
- Most recent migration: `backend/alembic/versions/v3w4x5y6z7a8_backfill_default_metadata_fields.py` — new Phase 13 migration chains from this

### Scoring Pipeline — Enforcement Points
- `backend/app/services/brainsuite_score.py` — video scoring; PIPE-02 and FMAP-07 guards go here
- `backend/app/services/brainsuite_static_score.py` — static scoring; same guards
- `backend/app/services/sync/scoring_job.py` — SCORING_BATCH_COMPLETE notification pattern (analog for MANDATORY_FIELD_MISSING)

### Notification Service
- `backend/app/services/notifications.py` — `create_org_notification()` function; use for MANDATORY_FIELD_MISSING

### Frontend — Integration Target
- `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts` — accordion panel (Phase 12) where trigger button slots in; sticky banner goes at page top; side panel component slots here or as child component

### Existing Patterns
- Phase 12 CONTEXT.md: `backend/app/models/brainsuite_config.py` — encryption pattern, credential endpoints shape
- `backend/app/api/v1/endpoints/` — endpoint pattern for new brainsuite-config routes
- Phase 12 `config-section` / `accordion-panel` / `api-note` CSS: already in `brainsuite-apps.component.ts`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config-section` / `section-header` / `section-body` CSS: in `brainsuite-apps.component.ts` — reuse for any wrapper
- `accordion-panel` CSS + `expandedAppId` pattern: Phase 12 added this — trigger button slots into this expanded panel
- `create_org_notification()`: `backend/app/services/notifications.py` — drop-in for MANDATORY_FIELD_MISSING and PIPE-03 alerts
- `MatSnackBar` toast: reuse for "Mappings saved" feedback
- `bi-*` Bootstrap Icons: `bi-trash` for delete custom field, `bi-asterisk` or similar for mandatory indicator
- `ReactiveFormsModule` + `FormBuilder`: established pattern for form rows; custom field rows need dynamic FormArray

### Established Patterns
- Standalone Angular components, lazy-loaded via `CONFIGURATION_ROUTES`
- `async def` endpoints + `Depends(get_db)` + `Depends(get_current_user)` — backend endpoint pattern
- Pydantic Create/Update/Response schemas per resource
- `api-note` div: existing inline warning style — extend for sticky banner variant

### Integration Points
- Slide panel: new CSS pattern needed (no existing overlay/drawer component). Consider `position: fixed; right: 0; top: 0; width: 480px; height: 100vh` with `transform: translateX(100%)` animation.
- Backend: new endpoint file or add to existing `brainsuite_config.py` endpoint file (Phase 12 created this)
- `org_brainsuite_field_mappings` table: currently empty for all orgs (Phase 11 created the table, Phase 13 owns population)

</code_context>

<specifics>
## Specific Ideas

- Side panel width: ~480px, full viewport height, white background, z-index above page content, with a semi-transparent backdrop
- Panel header: app name + app type badge (e.g. "My Video App — VIDEO"), close `bi-x-lg` button
- Standard fields section: labeled "Standard Fields (read-only names)" — API field name in left column, metadata field dropdown in middle, mandatory toggle on right. Standard field names are non-editable.
- Custom fields section: below standard fields, labeled "Custom Fields" — same columns but with a `bi-trash` delete icon on each row and the API field name is an editable text input
- Auto-match candidates: `brandValues → brainsuite_brand_values`, `brandValuesLanguage → brainsuite_brand_values_language`, `assetLanguage → brainsuite_asset_language`, `voiceOverLanguage → brainsuite_voice_over_language`, `assetName → brainsuite_asset_name` (if such a metadata field exists)
- Sticky banner: yellow/amber warning with `bi-exclamation-triangle` icon listing what's incomplete (e.g. "Missing credentials · Video App has no app name · 2 mandatory fields unmapped")

</specifics>

<deferred>
## Deferred Ideas

- **YouTube cookies DB storage** — Store YouTube cookies in `org_brainsuite_config` (or dedicated table), add admin API endpoint to update without Docker restart, update `dv360_sync.py` to read from DB. Deferred to Phase 14. (Surfaced during Phase 12 UAT 2026-04-17.)

</deferred>

---

*Phase: 13-field-mapping-editor-mandatory-field-enforcement*
*Context gathered: 2026-04-20*
