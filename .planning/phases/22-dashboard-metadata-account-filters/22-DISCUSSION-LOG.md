# Phase 22: Dashboard Metadata + Account Filters - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 22-dashboard-metadata-account-filters
**Areas discussed:** Metadata filter UX, Autocomplete data source, Multi-field filtering, DASH-02 scope

---

## Metadata Filter UX

| Option | Description | Selected |
|--------|-------------|----------|
| Two-step: field → value | Dropdown picks field, then autocomplete shows values for that field only. Matches existing tbd-menu pattern. | ✓ |
| Single autocomplete across all fields | One input searches across all fields; suggestions formatted as "Field: Value" | |
| Free-text value search | User types a value; matches any asset where any field contains that text | |

**User's choice:** Two-step (field → value)
**Notes:** Recommended option accepted without modification.

---

| Option | Description | Selected |
|--------|-------------|----------|
| All active org metadata fields | Every MetadataField with is_active=true for the org | ✓ |
| Only fields with at least one asset value | JOIN to asset_metadata_values — only surface fields that appear on real assets | |

**User's choice:** All active org metadata fields
**Notes:** Simpler query; includes fields with no values yet.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Inline in existing filter bar | New "Metadata" button after Ad Accounts, before Sort; tbd-trigger/tbd-menu pattern | ✓ |
| Second row below filter bar | Dedicated filter row — more space but changes page layout | |
| Inside "More Filters" expander | Collapsible panel — adds an extra click | |

**User's choice:** Inline in existing filter bar
**Notes:** Consistent with existing filter bar pattern.

---

## Autocomplete Data Source

| Option | Description | Selected |
|--------|-------------|----------|
| Actual asset values only | DISTINCT AssetMetadataValue.value for selected field, org-scoped | ✓ |
| Configured allowed values only | MetadataFieldValue table — only works for SELECT fields | |
| Merge both sources | Union of allowed values + actual asset values — two queries | |

**User's choice:** Actual asset values only
**Notes:** Works for all field types (SELECT, TEXT, NUMBER); only shows values that real assets have.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Prefix match (starts with) | Filter suggestions starting with typed text | ✓ |
| Substring match (contains) | ILIKE '%text%' — more flexible but heavier | |
| You decide | Planner chooses based on index structure | |

**User's choice:** Prefix match
**Notes:** Standard autocomplete behavior; fast with simple index.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Load all values on field select, filter client-side | Single network call per field; client-side filtering as user types | ✓ |
| Debounced API call on each keystroke | Lazy fetch — needed only if fields have thousands of values | |

**User's choice:** Load all on field select, filter client-side
**Notes:** Single call per field selection is sufficient given typical metadata cardinality.

---

## Multi-field Filtering

| Option | Description | Selected |
|--------|-------------|----------|
| Multiple metadata filters stacked | User can add Language=Indonesian AND Market=US simultaneously | ✓ |
| One active metadata filter at a time | Selecting a new filter replaces the previous | |

**User's choice:** Multiple stacked filters
**Notes:** More powerful; chip UI needed for state visualization.

---

| Option | Description | Selected |
|--------|-------------|----------|
| AND (must match all filters) | Asset must match every active metadata filter | ✓ |
| OR (match any filter) | Asset appears if it matches any filter | |
| You decide | Planner picks AND | |

**User's choice:** AND logic
**Notes:** Natural semantic for drill-down filtering.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Chips below filter bar with × remove | Each active filter shown as chip; "Clear all" option | ✓ |
| Filter badge on Metadata button | Count badge; hover/click shows active filters | |
| In-menu checkmarks | Applied filters shown with checkmarks in two-step menu | |

**User's choice:** Chips below filter bar
**Notes:** Standard search UI pattern; easy to see and remove individual filters.

---

## DASH-02 Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Verify + smoke test, mark done | Quick verification pass only — no code changes | |
| Verify + add platform grouping to dropdown | Smoke-test existing code + add section headers by platform | ✓ |
| Rebuild from scratch | Treat as untested, re-implement from zero | |

**User's choice:** Verify + add platform grouping
**Notes:** Existing implementation confirmed complete in `main` (accounts loaded from `/platforms/connections`, toggleAdAccount() wired, selectedAdAccountIds passed to API). Polish with platform grouping headers.

---

## Claude's Discretion

- Same-field stacking behavior: if user adds Language=Indonesian and Language=English, allow both chips (produces zero results, user can remove one). Planner decides whether to prevent or allow.
- Exact shape of metadata fields + values API endpoint (single endpoint vs. two endpoints) — planner decides.

## Deferred Ideas

- Filter state URL persistence — explicitly Out of Scope (REQUIREMENTS.md v1.5 candidate)
- Saved filter presets — Out of Scope
- "Only fields with at least one asset value" optimization for step-1 dropdown
