# Phase 22: Dashboard Metadata + Account Filters - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Full-stack phase. Delivers two dashboard filters:

1. **DASH-01 (new build):** A metadata field value filter — two-step (field selector → value autocomplete) rendered inline in the filter bar. Multiple filters can be stacked (AND logic), shown as dismissible chips below the filter bar.
2. **DASH-02 (verify + polish):** Ad account multi-select filter — already fully implemented in `main`. Phase 22 verifies it works and adds platform grouping (section headers by platform) to the dropdown.

Phase 22 does NOT include video duration filter (that is Phase 23).

</domain>

<decisions>
## Implementation Decisions

### Metadata Filter UX (DASH-01)
- **D-01:** Two-step interaction model — step 1: user clicks "Metadata" button in filter bar and selects a field from the dropdown (all active org metadata fields listed); step 2: an autocomplete input appears inline, user types to filter suggestions and picks a value.
- **D-02:** All active org metadata fields are listed in step 1 — `MetadataField.is_active = true` AND `MetadataField.organization_id = current_user.organization_id`. Includes fields with no asset values yet.
- **D-03:** The Metadata filter button is inserted inline in the existing filter bar, after the Ad Accounts button, before the Sort button. Follows the existing `tbd-trigger`/`tbd-menu` CSS/UX pattern.

### Autocomplete Data Source (DASH-01)
- **D-04:** Autocomplete suggestions come from **actual asset values only** — `DISTINCT AssetMetadataValue.value` for the selected field, scoped to the current org via `MetadataField.organization_id`. Works for all field types (SELECT, TEXT, NUMBER). No cross-org leakage by design.
- **D-05:** Autocomplete matching is **prefix match** (value starts with typed text). Case-insensitive. Implemented client-side on the loaded values.
- **D-06:** All values for the selected field are loaded in a single API call on field selection. The user types to filter the loaded list client-side. No keystroke-debounced requests.

### Multi-field Filtering (DASH-01)
- **D-07:** Multiple metadata filters can be stacked simultaneously — e.g., Language=Indonesian AND Market=US.
- **D-08:** Stacked filters use **AND logic** — an asset must match all active metadata filters to appear in the grid.
- **D-09:** Active metadata filters are shown as dismissible chips below the main filter bar row (e.g., "Language: Indonesian ×"). A "Clear all" button clears all active metadata chips at once. Adding a new field+value adds a chip; the same field can appear twice with different values if user selects it again (OR within a field) — planner decides if same-field duplicates should be prevented.
- **D-10:** API encoding: metadata filters passed as repeated query params — `metadata_filter=field_name:value` (e.g., `metadata_filter=language:Indonesian&metadata_filter=market:US`). Backend receives `List[str]`, parses each as `field_name:value`, applies one JOIN per filter.

### Ad Account Filter Polish (DASH-02)
- **D-11:** Verify the existing ad account multi-select filter works end-to-end (it's already fully coded). Then add platform grouping to the dropdown — accounts grouped by platform with section headers (e.g., "META", "GOOGLE ADS") using `matListSubheaderCssClass` or a `<div class="tbd-group-header">` separator. Flat list fallback if only one platform is connected.
- **D-12:** DASH-02 is not a rebuild. Only: smoke-test toggle behavior + verify API filter + add grouping UI.

### Migration
- **D-13:** Phase 22 adds an Alembic migration with a composite index on `asset_metadata_values(field_id, value)` to support the autocomplete lookup query efficiently. The index the STATE.md references as "Phase 20's migration" was never actually added in Phase 20 — Phase 22 owns it.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend Filter Endpoint
- `backend/app/api/v1/endpoints/dashboard.py` §`get_dashboard_assets` (lines ~185–340) — existing paginated asset query; add `metadata_filter: Optional[List[str]] = Query(default=None)` param; apply JOIN per active filter against `asset_metadata_values` + `metadata_fields` tables with org_id guard
- `backend/app/api/v1/endpoints/dashboard.py` — check if a new `/dashboard/metadata-fields` endpoint is needed to load field list + values, or embed in GET assets query context (planner decides)

### Data Models
- `backend/app/models/creative.py` §`AssetMetadataValue` (~line 96) — `asset_id`, `field_id`, `value` (Text); unique on `(asset_id, field_id)`; the filter JOINs through this table
- `backend/app/models/metadata.py` §`MetadataField` (~line 9) — `organization_id`, `name`, `label`, `field_type`, `is_active`; step-1 field list comes from this table

### Frontend to Modify
- `frontend/src/app/features/dashboard/dashboard.component.ts` — all filter state lives here; ad account filter pattern (lines ~148–161, 1175–1176, 1291–1300, 1567, 1687–1694) is the structural model to copy for metadata filter state
- Add to component imports: `MatAutocompleteModule`, `MatChipsModule` (not currently imported)

### Requirements
- `.planning/REQUIREMENTS.md` §DASH-01, §DASH-02 — acceptance criteria including org isolation requirement for DASH-01
- `.planning/ROADMAP.md` §Phase 22 — 5 success criteria; SC-4 ("All active filters compose with AND logic and persist correctly across pagination clicks") and SC-5 ("Clear filters control")

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tbd-trigger` / `tbd-menu` / `tbd-check` / `tbd-name` / `tbd-badge` CSS classes — already defined in `dashboard.component.ts` styles; metadata filter button and dropdown use these exactly
- `selectedAdAccountIds` / `toggleAdAccount()` pattern (lines 1175–1176, 1687–1694) — direct analog for metadata filter chip state management: `activeMetadataFilters: {field: string; value: string}[]` array + `addMetadataFilter()` + `removeMetadataFilter()`
- `onFilterChange()` method — called by every filter toggle; metadata filter add/remove should call this too
- `ReactiveFormsModule` + `FormsModule` — already imported; autocomplete input can use `[(ngModel)]`

### Established Patterns
- API filter params: comma-separated string for single-value multi-select (see `ad_account_ids`), but metadata needs repeated params (`List[str]`) since each entry is a `field:value` pair
- Org-id guard: every metadata query MUST include `MetadataField.organization_id == current_user.organization_id` — security requirement (no cross-org value leakage)
- Async SQLAlchemy pattern: `select(func.distinct(AssetMetadataValue.value)).join(MetadataField, ...).where(MetadataField.organization_id == org_id, MetadataField.name == field_name)` — one query per field lookup

### Integration Points
- New GET `/dashboard/metadata-fields` (or similar) endpoint returns `{fields: [{name, label, field_type}], values: {field_name: [value, ...]}}` — or two separate endpoints; planner decides shape
- Alembic migration: one new revision adding `CREATE INDEX idx_asset_metadata_values_field_value ON asset_metadata_values(field_id, value)` — enables the autocomplete lookups
- No new models or tables needed

</code_context>

<specifics>
## Specific Ideas

- Chip format: `"Language: Indonesian ×"` where "Language" is `MetadataField.label` (not `.name`); the API filter uses `.name` for the query
- Platform grouping in DASH-02: use a non-clickable `<span class="tbd-group-header">` between platform groups in the `mat-menu`; ordered META → TIKTOK → GOOGLE ADS → DV360
- The "Metadata" button in the filter bar shows a count badge when filters are active: `"Metadata (2)"` — or uses the field label of the first active filter if only one
- Same-field stacking decision: if the user adds Language=Indonesian and then Language=English, both chips appear and the query ANDs two conditions on the same field (which returns zero results by definition — an asset can't have two values for the same field). Planner should either prevent duplicate-field filters or note the zero-result implication. Recommendation: allow it (the user can see it produces no results and remove one).

</specifics>

<deferred>
## Deferred Ideas

- Filter state URL persistence (query param serialization) — explicitly Out of Scope per REQUIREMENTS.md v1.5 candidate
- Saved filter presets — REQUIREMENTS.md Out of Scope
- "Only fields with at least one asset value" optimization for step-1 dropdown — user chose simpler "all active fields" approach

</deferred>

---

*Phase: 22-dashboard-metadata-account-filters*
*Context gathered: 2026-05-15*
