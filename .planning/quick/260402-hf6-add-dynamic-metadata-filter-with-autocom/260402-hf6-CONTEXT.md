---
name: Metadata Filter Context
description: UI/UX decisions for dynamic metadata filter with autocomplete on dashboard
type: project
---

# Quick Task 260402-hf6: add dynamic metadata filter with autocomplete to dashboard - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Task Boundary

Add a dynamic metadata filter to the dashboard. Users should be able to filter assets by any active metadata field (brand, language, stage, etc.). New fields added in Settings automatically appear as filterable options. Autocomplete with combined suggestion source.

</domain>

<decisions>
## Implementation Decisions

### Filter UI Pattern
- "Add Filter" button in the toolbar opens a 2-step popover: step 1 pick a metadata field, step 2 type/select value(s) with autocomplete
- Active filters render as dismissible chips in a row below the toolbar (between toolbar and stats section)
- A "Clear all" link appears when any filters are active
- The popover closes after confirming a field+value selection

### Multi-select per field
- Each metadata field supports multi-select (OR logic within a field): e.g., Brand = "Nike" OR "Adidas"
- Checkboxes in the autocomplete dropdown allow multiple values to be checked
- The chip shows "Brand: Nike, Adidas ×" when multiple values selected

### Autocomplete / Value Source
- Both combined: predefined `MetadataFieldValue` allowed_values shown first (as primary suggestions), then distinct actual values from `AssetMetadataValue` table appended below (de-duplicated)
- Requires a new backend endpoint: `GET /api/v1/assets/metadata-filter-values?field_id=<uuid>` returning combined unique values
- Typing filters both lists in real-time (client-side filter on returned values, not server-side per keystroke)

### Filter → API integration
- Active filters sent as query params: `meta_filters=<field_id>:<value1>,<value2>&meta_filters=<field_id2>:<value>` (repeating param)
- Backend `GET /dashboard/assets` gains a `meta_filters` query param (repeating string param, format: `field_id:value1,value2`)
- SQL: JOIN AssetMetadataValue for each filter, WHERE value IN (selected values) — AND logic across different fields, OR logic within a field's values

### Claude's Discretion
- Exact chip styling, popover animation, and color scheme: match existing toolbar aesthetic
- Toolbar "Add Filter" button placement: after the score slider, before the spacer
- The metadata-filter-values endpoint should be scoped to the org (security)

</decisions>

<specifics>
## Specific Ideas

- The `DashboardFilterParams` schema in `backend/app/schemas/creative.py` already has `metadata_filters: Optional[Dict[str, str]]` — update this to `Dict[str, List[str]]` to support multi-select
- Existing `/assets/metadata-fields` endpoint returns all active fields with `allowed_values` — reuse this on the frontend to populate the field picker step
- New endpoint needed: `GET /assets/metadata-filter-values?field_id=<uuid>` — returns predefined values + distinct DB values combined
- Frontend: `MatAutocomplete` with `MatChipInput` pattern works well for the value selector step
- The filter chips row should be hidden (zero height) when no filters are active, not a visible empty row

</specifics>

<canonical_refs>
## Canonical References

- `backend/app/api/v1/endpoints/dashboard.py` — `get_dashboard_assets()` is the target endpoint to add `meta_filters` param
- `backend/app/schemas/creative.py:109` — `DashboardFilterParams` (already has `metadata_filters` field)
- `backend/app/api/v1/endpoints/assets.py:138` — existing `list_metadata_fields` endpoint (reuse for field picker)
- `backend/app/models/metadata.py` — `MetadataField`, `MetadataFieldValue` models
- `backend/app/models/creative.py` — `AssetMetadataValue` model (source for actual used values)
- `frontend/src/app/features/dashboard/dashboard.component.ts` — target dashboard component

</canonical_refs>
</content>
</invoke>