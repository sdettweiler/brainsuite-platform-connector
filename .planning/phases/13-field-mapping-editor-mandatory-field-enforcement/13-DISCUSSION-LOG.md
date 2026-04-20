# Phase 13: Field Mapping Editor + Mandatory Field Enforcement - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 13-field-mapping-editor-mandatory-field-enforcement
**Areas discussed:** Field mapping layout, Mapping edit + custom fields, Mandatory toggle UX, Incomplete config warning + YouTube cookies scope

---

## Field Mapping Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Same page, new section | Add a 'Field Mappings' config-section card below existing content — consistent with Phase 12 | |
| New Settings nav tab | New tab alongside Organization / Platforms / Metadata / Brainsuite Apps | |
| Button opens lightbox (modal) | Opens centered MatDialog over page — reuses existing MatDialog pattern | |
| Button opens right side panel | Slides in from the right while page remains visible underneath | ✓ |
| Trigger in BrainSuite config section | Button inside the credentials/config section card | |
| Trigger in app accordion | Button inside each BrainsuiteApp accordion panel | ✓ |
| Video/Static: two tabs inside panel | Tab switcher at top of panel — VIDEO tab + STATIC tab | |
| Video/Static: per app (no tabs) | Panel scoped to clicked app's type — no tabs needed | ✓ |
| All unmapped on first open | Standard fields show as Unmapped — admin configures from scratch | |
| Auto-matched on first open | System pre-fills mappings for obvious name matches | ✓ |

**User's choice:** Right-side slide panel, triggered from each app row accordion, scoped to that app's type, with auto-matching on first open.
**Notes:** User clarified that field mapping must happen at the app level (per BrainsuiteApp), not globally per org or per app_type. This drove the decision to store mappings per brainsuite_app_id.

---

## Mapping Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Shared per app_type | All VIDEO apps share one mapping. DB schema as-is (org + app_type). | |
| Per individual app (app ID) | Each BrainsuiteApp has its own mapping. Requires brainsuite_app_id FK migration. | ✓ |

**User's choice:** Per individual app (BrainsuiteApp ID).
**Notes:** Requires Alembic migration to add `brainsuite_app_id` FK to `org_brainsuite_field_mappings`.

---

## Mapping Edit + Custom Fields

| Option | Description | Selected |
|--------|-------------|----------|
| Inline dropdown, always visible | Each row shows select dropdown — no edit mode needed. Save at panel bottom. | ✓ |
| Click row → expand inline edit | Read-only until clicked, then expands to show dropdown. | |
| Inline "Add custom field" row | "+ Add custom field" adds a blank editable row inline at bottom of list. | ✓ |
| Mini dialog for custom field add | Opens small dialog: enter field name + pick metadata field. | |

**User's choice:** Inline dropdowns always visible, inline "+ Add custom field" row.

---

## Mandatory Toggle UX

| Option | Description | Selected |
|--------|-------------|----------|
| Toggle switch column | On/off toggle in "Mandatory" column. Mandatory rows get visual indicator. | ✓ |
| Checkbox column | Simple checkbox in "Mandatory" column. | |

**User's choice:** Toggle switch column with visual indicator for mandatory-on rows.

---

## Save Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Single Save at panel bottom | One Save button commits all changes atomically. Cancel discards. | ✓ |
| Auto-save per field change | Each change fires immediate PATCH. | |

**User's choice:** Single Save at panel bottom.

---

## FMAP-07 Notification

| Option | Description | Selected |
|--------|-------------|----------|
| In-app notification (MANDATORY_FIELD_MISSING) | Uses existing notification system — bell icon + Notification model. | ✓ |
| Only UNSCORED badge | Asset silently stays UNSCORED, no notification. | |

**User's choice:** In-app notification via existing `create_org_notification()` service.

---

## Incomplete Config Warning (PIPE-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Sticky page-top alert banner | Full-width alert at top of Brainsuite Apps page — disappears when config is complete. | ✓ |
| Inline api-note per section | Warning note inside each incomplete section. | |

**User's choice:** Sticky page-top alert banner.

---

## YouTube Cookies Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Include in Phase 13 | Cookie DB storage + admin endpoint + dv360_sync.py update in this phase. | |
| Separate Phase 14 | Phase 13 stays focused on field mappings. Phase 14 handles cookies. | ✓ |

**User's choice:** Separate Phase 14.

---

## Claude's Discretion

- Whether to keep `app_type` column on `org_brainsuite_field_mappings` or derive from BrainsuiteApp
- Auto-match logic implementation (server-side vs. client-side)
- FMAP-07 notification batching strategy
- Exact endpoint URLs for field mappings CRUD
- Side panel CSS approach (CdkOverlay vs. custom fixed position)
- Incomplete config check computation (backend endpoint vs. frontend derivation)

## Deferred Ideas

- YouTube cookie DB storage — deferred to Phase 14
