# Phase 22: Dashboard Metadata + Account Filters - Research

**Researched:** 2026-05-15
**Domain:** Full-stack filter implementation (frontend + backend + database)
**Confidence:** HIGH

## Summary

Phase 22 delivers two independent dashboard filters on top of an existing v1.3 creative asset grid:

1. **DASH-01 (New Build):** A two-step metadata field value filter — users select a metadata field, then type to autocomplete from actual asset values, with support for stacking multiple field filters using AND logic.
2. **DASH-02 (Verification + Polish):** Verify the ad account multi-select filter (already present in main) and add platform grouping (META → TIKTOK → GOOGLE ADS → DV360) with section headers.

The phase depends on Phase 20's Alembic migration that adds a composite index on `asset_metadata_values(field_id, value)` to support efficient autocomplete lookups. This index was deferred from Phase 20 to Phase 22 per CONTEXT.md D-13.

**Primary recommendation:** Implement DASH-01 first (metadata filter), verify + test DASH-02 second (account filter polish), then test all filters composing with AND logic before closing the phase.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

| ID | Decision | Constraint |
|------|----------|-----------|
| D-01 | Two-step metadata filter UX (field selector → value autocomplete) | No alternative model; this is the locked design |
| D-02 | Show all active org metadata fields in step 1 dropdown | Includes fields with no asset values yet |
| D-03 | Metadata button inline in filter bar after Ad Accounts button | Positioning is fixed per filter bar layout |
| D-04 | Autocomplete suggestions from DISTINCT actual asset values only | Use case: real data only, no synthetic suggestions |
| D-05 | Prefix-match autocomplete, case-insensitive, client-side filtering | Once values loaded, no keystroke-debounced requests |
| D-06 | All values for selected field loaded in single API call | No pagination of autocomplete suggestions |
| D-07 | Multiple metadata filters stack simultaneously (AND logic) | Same field can appear twice with different values |
| D-08 | Active metadata filters shown as dismissible chips below filter bar | Each chip shows "FieldLabel: value" format |
| D-09 | Chips cleared with individual dismiss button or global "Clear all" button | UX contract defines button placement and styling |
| D-10 | API filter encoding as repeated query params `metadata_filter=field_name:value` | Backend parses each string as field_name:value pair |
| D-11 | Ad account filter already fully coded; add platform grouping with section headers | No rebuild required, only verification + grouping UI |
| D-12 | DASH-02 is smoke-test + grouping UI only, not a feature rebuild | Verify existing toggle behavior and API integration |
| D-13 | Alembic migration with composite index belongs in Phase 22, not Phase 20 | Index created on `asset_metadata_values(field_id, value)` |

### Claude's Discretion

No discretionary areas — all implementation details are locked in CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)

- **Filter state URL persistence** — v1.5 candidate; not in v1.4 scope
- **Saved filter presets** — v1.5 candidate; not in v1.4 scope
- **"Only fields with at least one asset value" optimization** — user chose simpler "all active fields" approach

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01 | A user can filter the creative grid by metadata field value using a searchable autocomplete input; suggestions limited to user's organization (no cross-org leakage) | Org-scoped query via MetadataField.organization_id + AssetMetadataValue join; API returns DISTINCT values; frontend loads once, filters client-side |
| DASH-02 | A user can filter the creative grid by one or more ad accounts using a multi-select filter; selecting multiple accounts shows creatives from all selected accounts | Ad account filter already implemented (commit e403eaf); Phase 22 adds platform grouping (META/TIKTOK/GOOGLE_ADS/DV360 section headers) |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Metadata field list retrieval | API / Backend | — | Requires org-scoped database query; no client-side data source |
| Metadata value autocomplete data fetch | API / Backend | — | Requires DISTINCT query on asset_metadata_values table with org isolation |
| Autocomplete suggestion filtering (prefix match, case-insensitive) | Browser / Client | — | All values loaded at once; client-side filtering avoids keystroke-debounced requests |
| Metadata filter chip management (state, add, remove) | Browser / Client | — | Pure UI state; calls onFilterChange() to trigger grid re-query |
| Filter composition & AND logic | API / Backend | — | Backend applies multiple metadata filter clauses via repeated WHERE joins |
| Ad account multi-select state management | Browser / Client | — | Already implemented; Phase 22 adds grouping UI only |
| Platform grouping in account dropdown | Browser / Client | — | Pure UI/template concern; no backend changes |

---

## Standard Stack

### Core Framework Stack

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Angular** | 17.3.0 | Frontend framework | Standalone components, signals, reactive forms already in use |
| **Angular Material** | 17.3.0 | UI component library | mat-menu, mat-autocomplete, mat-chips already available; no new package needed |
| **FastAPI** | 0.115.0 | Backend REST API | Async SQLAlchemy ORM support; type-safe request/response schemas |
| **SQLAlchemy** | 2.0.23 | Python ORM | Async support with asyncpg driver; already used for all data queries |
| **PostgreSQL** | 15.4+ | Primary database | Composite indexes supported; DISTINCT queries with joins |
| **Alembic** | 1.12.1 | Schema migrations | SQLAlchemy-based migration management; existing project standard |

### Frontend Modules (No New Packages)

| Module | Version | Purpose | Already Imported? |
|--------|---------|---------|-------------------|
| **MatAutocompleteModule** | 17.3.0 | Dropdown suggestions with input | ✗ Must add to imports array |
| **MatChipsModule** | 17.3.0 | Dismissible metadata filter chips | ✗ Must add to imports array |
| **FormsModule** | 17.3.0 | ngModel two-way binding for autocomplete input | ✓ Already imported |
| **ReactiveFormsModule** | 17.3.0 | Form state management | ✓ Already imported |
| **MatMenuModule** | 17.3.0 | Dropdown menu for field selection (step 1) | ✓ Already imported |
| **CommonModule** | 17.3.0 | *ngIf, *ngFor | ✓ Already imported |

### Backend Query Patterns (No New Libraries)

| Pattern | Library | Purpose | Usage |
|---------|---------|---------|-------|
| Async SQLAlchemy queries | sqlalchemy + asyncpg | Database operations with org isolation | JOINs through AssetMetadataValue → MetadataField with organization_id guards |
| Query parameter parsing | FastAPI Query | Dashboard endpoint signature | `metadata_filter: Optional[List[str]] = Query(default=None)` |
| Org-scoped filtering | SQLAlchemy where() | Security requirement | Every metadata query includes `MetadataField.organization_id == current_user.organization_id` |

**Installation Note:** MatAutocompleteModule and MatChipsModule are already installed as dependencies of @angular/material v17.3.0. Only add to component imports array; no npm install needed.

---

## Architecture Patterns

### System Architecture Diagram

```
User (Browser)
    ↓
[Dashboard Component]
    ├─ Step 1: Metadata Field Selector (mat-menu)
    │   └─ GET /dashboard/metadata-fields → MetadataField.is_active, org-scoped
    │
    ├─ Step 2: Value Autocomplete Input
    │   ├─ GET /dashboard/metadata-fields/{field_id}/values → DISTINCT asset values
    │   └─ Client-side filtering (prefix match, case-insensitive)
    │
    ├─ Filter Chip Row (active filters)
    │   └─ Stores array: [{field: name, value: string}, ...]
    │
    └─ Trigger Grid Re-query (onFilterChange)
       └─ GET /dashboard/assets?metadata_filter=field_name:value&metadata_filter=field_name:value
           └─ Backend: Apply metadata filter JOINs (one per filter, AND logic)
               └─ [Asset Grid] displays filtered results
```

### Recommended Project Structure

No new directories required. All Phase 22 changes are within existing components:

```
backend/
├── app/api/v1/endpoints/
│   └── dashboard.py          # Add metadata filter param to get_dashboard_assets; add new /metadata-fields endpoint
├── alembic/versions/
│   └── [new migration]       # Composite index on asset_metadata_values(field_id, value)
└── tests/
    └── test_dashboard_filters.py  # Expand tests for metadata filter (DASH-01)

frontend/
└── src/app/features/dashboard/
    └── dashboard.component.ts  # Add metadata filter UI + chip management
```

### Pattern 1: Two-Step Dropdown (Metadata Field Selection → Value Autocomplete)

**What:** A two-layer dropdown interaction where step 1 is a static field list, and step 2 is a dynamic input with autocomplete suggestions.

**When to use:** When filtering by a dynamic field with many possible values (e.g., metadata field values like "Indonesian", "English", "US", "EU"), and values are not pre-configured but discovered from actual data.

**Example (frontend):**

```typescript
// Source: CONTEXT.md design patterns + Angular Material documentation

// State management
selectedMetadataFieldId: string | null = null;
selectedMetadataFieldName: string | null = null;
selectedMetadataFieldLabel: string | null = null;
metadataFields: MetadataField[] = [];
metadataFieldValues: string[] = [];
metadataValueInput = '';
activeMetadataFilters: {field: string; value: string}[] = [];

// Step 1: Load and display field list
loadMetadataFields(): void {
  this.api.get<MetadataFieldsResponse>('/dashboard/metadata-fields').subscribe(
    (response) => {
      this.metadataFields = response.fields;
    }
  );
}

// On field selection
selectMetadataField(field: MetadataField): void {
  this.selectedMetadataFieldId = field.id;
  this.selectedMetadataFieldName = field.name;
  this.selectedMetadataFieldLabel = field.label;
  this.metadataValueInput = '';
  
  // Step 2: Load values for the selected field
  this.api.get<MetadataValuesResponse>(
    `/dashboard/metadata-fields/${field.id}/values`
  ).subscribe(
    (response) => {
      this.metadataFieldValues = response.values;
    }
  );
}

// Client-side filtering (prefix match, case-insensitive)
get filteredMetadataValues(): string[] {
  const input = this.metadataValueInput.toLowerCase();
  return this.metadataFieldValues.filter(v => 
    v.toLowerCase().startsWith(input)
  );
}

// On value selection
selectMetadataValue(value: string): void {
  this.activeMetadataFilters.push({
    field: this.selectedMetadataFieldName!,
    value: value
  });
  this.selectedMetadataFieldId = null;
  this.onFilterChange();
}

// Remove chip
removeMetadataFilter(index: number): void {
  this.activeMetadataFilters.splice(index, 1);
  this.onFilterChange();
}

// Clear all chips
clearAllMetadataFilters(): void {
  this.activeMetadataFilters = [];
  this.onFilterChange();
}

// Trigger grid re-query
onFilterChange(): void {
  // Existing method — called by all filters
  // Builds query params including metadata_filter array
  this.loadData();
}
```

**Example (backend):**

```python
# Source: FastAPI + SQLAlchemy async pattern from existing dashboard.py

from fastapi import APIRouter, Query, Depends
from sqlalchemy import select, func, distinct
from app.models.metadata import MetadataField
from app.models.creative import AssetMetadataValue
from app.api.v1.deps import get_current_user

router = APIRouter()

@router.get("/metadata-fields")
async def get_metadata_fields(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all active metadata fields for the current organization."""
    query = select(MetadataField).where(
        MetadataField.organization_id == current_user.organization_id,
        MetadataField.is_active.is_(True),
    ).order_by(MetadataField.sort_order)
    
    result = await db.execute(query)
    fields = result.scalars().all()
    
    return {
        "fields": [
            {
                "id": str(f.id),
                "name": f.name,
                "label": f.label,
                "field_type": f.field_type,  # SELECT, TEXT, NUMBER
            }
            for f in fields
        ]
    }

@router.get("/metadata-fields/{field_id}/values")
async def get_metadata_field_values(
    field_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return DISTINCT values for a metadata field scoped to the user's organization."""
    # Verify field belongs to org
    field = await db.get(MetadataField, field_id)
    if not field or field.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Field not found")
    
    # Query DISTINCT values via JOIN through CreativeAsset
    query = (
        select(distinct(AssetMetadataValue.value))
        .join(MetadataField, MetadataField.id == AssetMetadataValue.field_id)
        .join(CreativeAsset, CreativeAsset.id == AssetMetadataValue.asset_id)
        .where(
            MetadataField.organization_id == current_user.organization_id,
            MetadataField.id == field_id,
            AssetMetadataValue.value.isnot(None),
        )
        .order_by(AssetMetadataValue.value)
    )
    
    result = await db.execute(query)
    values = [row[0] for row in result.all()]
    
    return {"values": values}

# Modify existing get_dashboard_assets to accept metadata filters
@router.get("/assets")
async def get_dashboard_assets(
    # ... existing params ...
    metadata_filter: Optional[List[str]] = Query(default=None),  # NEW: "field_name:value"
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated assets with metadata filtering."""
    # ... existing setup ...
    
    query = (
        select(CreativeAsset, perf_subq, CreativeScoreResult.total_score, ...)
        .where(CreativeAsset.organization_id == current_user.organization_id)
    )
    
    # NEW: Apply metadata filters (one JOIN per filter, AND logic)
    if metadata_filter:
        for meta_filter_str in metadata_filter:
            field_name, filter_value = meta_filter_str.split(':', 1)
            
            # JOIN asset_metadata_values for this field and value
            query = query.join(
                AssetMetadataValue,
                and_(
                    AssetMetadataValue.asset_id == CreativeAsset.id,
                    AssetMetadataValue.value == filter_value,
                )
            ).join(
                MetadataField,
                and_(
                    MetadataField.id == AssetMetadataValue.field_id,
                    MetadataField.name == field_name,
                    MetadataField.organization_id == current_user.organization_id,
                )
            )
    
    # ... rest of existing query logic ...
    return {...}
```

### Pattern 2: Platform-Grouped Multi-Select Dropdown

**What:** A multi-select dropdown where options are grouped by platform with non-clickable section headers.

**When to use:** When a single-dimension multi-select (ad accounts) can be logically grouped by a secondary dimension (platform).

**Example (frontend template):**

```html
<!-- Account dropdown with platform grouping (DASH-02) -->
<button class="tbd-trigger" [matMenuTriggerFor]="accountMenu">
  {{selectedAdAccountIds.length === 0 ? 'All Accounts' : selectedAdAccountIds.length + ' Account' + (selectedAdAccountIds.length > 1 ? 's' : '')}}<i class="bi bi-chevron-down tbd-arrow"></i>
</button>
<mat-menu #accountMenu="matMenu" class="tbd-menu">
  <!-- "All Accounts" option at top (before grouping) -->
  <button mat-menu-item (click)="$event.stopPropagation(); selectedAdAccountIds = []; onFilterChange()">
    <span class="tbd-check" [class.checked]="selectedAdAccountIds.length === 0">&#10003;</span>
    All Accounts
  </button>
  
  <!-- Platform groups (only if multiple platforms connected) -->
  <ng-container *ngIf="accountsByPlatform.length > 1">
    <ng-container *ngFor="let group of accountsByPlatform">
      <!-- Platform group header (not clickable) -->
      <div class="tbd-group-header">{{group.platform}}</div>
      
      <!-- Account options within group -->
      <button mat-menu-item *ngFor="let acc of group.accounts" 
        (click)="$event.stopPropagation(); toggleAdAccount(acc.ad_account_id)">
        <span class="tbd-check" [class.checked]="selectedAdAccountIds.includes(acc.ad_account_id)">&#10003;</span>
        <span class="tbd-name">{{acc.ad_account_name}}</span>
        <span class="tbd-badge">{{acc.platform}}</span>
      </button>
      
      <!-- Divider between platform groups -->
      <div class="tbd-group-divider" *ngIf="!isLastGroup(group)"></div>
    </ng-container>
  </ng-container>
  
  <!-- Flat list if only one platform -->
  <ng-container *ngIf="accountsByPlatform.length <= 1">
    <button mat-menu-item *ngFor="let acc of adAccounts" 
      (click)="$event.stopPropagation(); toggleAdAccount(acc.ad_account_id)">
      <span class="tbd-check" [class.checked]="selectedAdAccountIds.includes(acc.ad_account_id)">&#10003;</span>
      <span class="tbd-name">{{acc.ad_account_name}}</span>
      <span class="tbd-badge">{{acc.platform}}</span>
    </button>
  </ng-container>
</mat-menu>
```

**Example (frontend component logic):**

```typescript
// Group accounts by platform (in ngOnInit after loading accounts)
get accountsByPlatform() {
  const platformOrder = ['META', 'TIKTOK', 'GOOGLE_ADS', 'DV360'];
  const grouped = new Map<string, any[]>();
  
  for (const acc of this.adAccounts) {
    if (!grouped.has(acc.platform)) {
      grouped.set(acc.platform, []);
    }
    grouped.get(acc.platform)!.push(acc);
  }
  
  // Return in platform order
  return platformOrder
    .filter(p => grouped.has(p))
    .map(p => ({ platform: p, accounts: grouped.get(p)! }));
}

isLastGroup(group: any): boolean {
  const groups = this.accountsByPlatform;
  return groups.indexOf(group) === groups.length - 1;
}
```

### Anti-Patterns to Avoid

- **Keystroke-debounced autocomplete requests:** D-05 and D-06 explicitly avoid this — load all values once, filter client-side. Don't add debounce(500) on input keyups.
- **Missing org-id guards on metadata queries:** Every query touching MetadataField or AssetMetadataValue must include `MetadataField.organization_id == current_user.organization_id`. Missing this = data leakage.
- **Allowing same field twice with duplicate values:** D-09 allows same field with different values (which ANDs to zero results), but prevents duplicate field+value pairs in chips.
- **Hardcoding field names in filter encoding:** D-10 uses `field_name:value` format where field_name comes from `MetadataField.name`, not `.label`. Planner must ensure API and UI coordinate field identity correctly.
- **Rebuilding account filter instead of verifying:** DASH-02 is verification + grouping only. Don't rewrite the entire account filter — it works; just test and add grouping.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dropdown menu with multiple selection states | Custom div + manual click handlers | Angular Material `mat-menu` + template directives | Material handles focus, keyboard nav, click-outside-closes, ARIA |
| Autocomplete input with dynamic suggestions | Custom input + manual filtering logic | Angular Material `mat-autocomplete` | Handles input focus, panel positioning, arrow key nav, async loading |
| Dismissible chips / tags | Custom div + manual hover states | Angular Material `mat-chips` | Material handles chip styling, delete button focus, accessibility |
| Organization data isolation in queries | Custom WHERE clauses | SQLAlchemy ORM with explicit org_id guards | Prevents accidental cross-org data leakage when queries are refactored |
| Composite index for performance | Manual SQL CREATE INDEX statements | Alembic migration in Python | Alembic tracks schema versioning; easier to rollback if needed |

**Key insight:** Angular Material components abstract away keyboard navigation (arrow keys, Enter, Escape), focus management, and ARIA attributes — hand-rolling loses all of this. SQLAlchemy's ORM makes org isolation explicit and auditable — raw SQL hides it and invites refactoring bugs.

---

## Common Pitfalls

### Pitfall 1: Org-ID Guard Missing in Autocomplete Query

**What goes wrong:** Metadata autocomplete returns values from other organizations, violating the org isolation requirement.

**Why it happens:** The DISTINCT query on asset_metadata_values only filters by field_id, forgetting the join to metadata_fields where org_id is stored.

**How to avoid:** Every query must follow the pattern:
```python
select(distinct(AssetMetadataValue.value))
  .join(MetadataField, MetadataField.id == AssetMetadataValue.field_id)
  .join(CreativeAsset, CreativeAsset.id == AssetMetadataValue.asset_id)
  .where(
    MetadataField.organization_id == current_user.organization_id,  # REQUIRED
    MetadataField.id == field_id,
    AssetMetadataValue.value.isnot(None)
  )
```

**Warning signs:** Autocomplete dropdown shows values from accounts/organizations the user is not part of; test with multi-org scenario.

### Pitfall 2: Keystroke Debouncing on Autocomplete

**What goes wrong:** User types quickly, experiences lag between keystroke and suggestion updates, feels unresponsive.

**Why it happens:** Developer adds `debounceTime(300)` to input.valueChanges, thinking it's an optimization. It's not — values are already loaded.

**How to avoid:** D-05 and D-06 are explicit: load values on field selection, filter client-side immediately. No debounce, no HTTP request per keystroke. Filtering 100 values in memory is instant.

**Warning signs:** User types quickly and suggestions don't update immediately; Rxjs debounce operators in the input change stream.

### Pitfall 3: Same Field Stacked Without Prevention

**What goes wrong:** User adds "Language: Indonesian" and "Language: English" and the grid shows no results (AND logic = impossible condition).

**Why it happens:** D-09 allows same-field stacking, but doesn't mandate prevention; the condition is logically impossible and confusing.

**How to avoid:** Optional: add client-side warning or prevention. Better: allow it and let the grid show zero results — the user will immediately understand AND logic. D-09 recommendation is to allow and educate.

**Warning signs:** Test with same field twice; verify grid correctly shows zero results and does not error.

### Pitfall 4: Missing Composite Index Leading to Slow Autocomplete

**What goes wrong:** Autocomplete response is slow (> 1 second) for large organizations with 100k+ assets.

**Why it happens:** D-13 migration is deferred to Phase 22. If planner forgets to include it, the DISTINCT query does a full table scan.

**How to avoid:** Verify the Alembic migration exists in the plan before execution. The migration must run before the first GET `/dashboard/metadata-fields/{field_id}/values` call.

**Warning signs:** First autocomplete request is slow; check PostgreSQL query plan for `sequential scan` on asset_metadata_values table.

### Pitfall 5: Field-to-Value Join Ambiguity in Multi-Filter Query

**What goes wrong:** Backend applies two metadata filters and returns wrong results; the JOIN logic double-counts or misses assets.

**Why it happens:** Multiple JOINs to the same tables (asset_metadata_values, metadata_fields) without careful alias/deduplication can cause Cartesian products.

**How to avoid:** For each metadata filter, add a separate JOIN with a unique table alias:
```python
from sqlalchemy import and_, or_
query = select(CreativeAsset).where(CreativeAsset.organization_id == org_id)
for i, meta_filter_str in enumerate(metadata_filter):
    field_name, filter_value = meta_filter_str.split(':', 1)
    amv_alias = aliased(AssetMetadataValue, name=f"amv_{i}")
    mf_alias = aliased(MetadataField, name=f"mf_{i}")
    query = query.join(
        amv_alias,
        and_(amv_alias.asset_id == CreativeAsset.id, amv_alias.value == filter_value)
    ).join(
        mf_alias,
        and_(
            mf_alias.id == amv_alias.field_id,
            mf_alias.name == field_name,
            mf_alias.organization_id == org_id
        )
    )
```

**Warning signs:** Test with two metadata filters; verify result count is less than either filter alone (AND behavior). Also check SQL query in PostgreSQL logs.

### Pitfall 6: Chip Label Using `.name` Instead of `.label`

**What goes wrong:** Chips display "language: Indonesian" instead of "Language: Indonesian" (field.name instead of field.label).

**Why it happens:** Frontend fetches MetadataField and uses `.name` for display. But `.label` is the human-readable label.

**How to avoid:** Chip display template uses field.label: `"{{field.label}}: {{value}}"`. API response from /metadata-fields must include both name and label:
```python
{
  "id": str(f.id),
  "name": f.name,      # e.g., "language" (used for API filter encoding)
  "label": f.label,    # e.g., "Language" (used for chip display)
  "field_type": f.field_type
}
```

**Warning signs:** UI-SPEC says "Language: Indonesian" but chip shows "language: Indonesian".

---

## Code Examples

### API Endpoint: Fetch Metadata Fields

```python
# Source: FastAPI + SQLAlchemy async pattern from dashboard.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.metadata import MetadataField
from app.models.user import User
from app.db.base import get_db
from app.api.v1.deps import get_current_user
import uuid

@router.get("/dashboard/metadata-fields")
async def get_metadata_fields(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all active metadata fields for the current organization.
    
    Response: {"fields": [{"id": str, "name": str, "label": str, "field_type": str}, ...]}
    """
    query = select(MetadataField).where(
        MetadataField.organization_id == current_user.organization_id,
        MetadataField.is_active.is_(True),
    ).order_by(MetadataField.sort_order, MetadataField.label)
    
    result = await db.execute(query)
    fields = result.scalars().all()
    
    return {
        "fields": [
            {
                "id": str(f.id),
                "name": f.name,
                "label": f.label,
                "field_type": f.field_type,
            }
            for f in fields
        ]
    }
```

### API Endpoint: Fetch Metadata Field Values

```python
# Source: FastAPI + SQLAlchemy async pattern with org guard

from sqlalchemy import distinct
from sqlalchemy.orm import aliased

@router.get("/dashboard/metadata-fields/{field_id}/values")
async def get_metadata_field_values(
    field_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return DISTINCT values for a metadata field, scoped to the user's organization.
    
    Response: {"values": ["Indonesian", "English", "Spanish", ...]}
    
    Query plan without composite index: Sequential scan on asset_metadata_values + JOIN.
    With index on (field_id, value): Index range scan (O(log n) + O(k) where k = matching rows).
    """
    # Verify field belongs to org
    field = await db.get(MetadataField, field_id)
    if not field or field.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Field not found")
    
    # Query DISTINCT values with org guard
    query = (
        select(distinct(AssetMetadataValue.value))
        .join(MetadataField, MetadataField.id == AssetMetadataValue.field_id)
        .join(CreativeAsset, CreativeAsset.id == AssetMetadataValue.asset_id)
        .where(
            MetadataField.organization_id == current_user.organization_id,
            MetadataField.id == field_id,
            AssetMetadataValue.value.isnot(None),
        )
        .order_by(AssetMetadataValue.value)
    )
    
    result = await db.execute(query)
    values = [row[0] for row in result.all()]
    
    return {"values": values}
```

### Frontend: Metadata Filter Dropdown & Autocomplete

```typescript
// Source: Angular Material mat-menu + mat-autocomplete pattern from dashboard.ts

// In component imports array (MUST ADD):
// imports: [..., MatAutocompleteModule, MatChipsModule]

// In component class:
export class DashboardComponent {
  metadataFields: MetadataField[] = [];
  selectedMetadataFieldId: string | null = null;
  selectedMetadataFieldName: string | null = null;
  selectedMetadataFieldLabel: string | null = null;
  metadataFieldValues: string[] = [];
  metadataValueInput = '';
  activeMetadataFilters: {field: string; value: string}[] = [];
  metadataValuesLoading = false;
  
  constructor(private api: ApiService) {}
  
  ngOnInit(): void {
    // Load metadata fields on init
    this.loadMetadataFields();
  }
  
  loadMetadataFields(): void {
    this.api.get<{fields: MetadataField[]}>('/dashboard/metadata-fields')
      .subscribe({
        next: (res) => {
          this.metadataFields = res.fields;
        },
      });
  }
  
  selectMetadataField(field: MetadataField): void {
    this.selectedMetadataFieldId = field.id;
    this.selectedMetadataFieldName = field.name;
    this.selectedMetadataFieldLabel = field.label;
    this.metadataValueInput = '';
    this.metadataValuesLoading = true;
    
    // Load values for this field (once)
    this.api.get<{values: string[]}>(`/dashboard/metadata-fields/${field.id}/values`)
      .subscribe({
        next: (res) => {
          this.metadataFieldValues = res.values;
          this.metadataValuesLoading = false;
        },
        error: () => {
          this.metadataValuesLoading = false;
        }
      });
  }
  
  // Client-side prefix matching (no HTTP request)
  get filteredMetadataValues(): string[] {
    const input = this.metadataValueInput.toLowerCase();
    return this.metadataFieldValues.filter(v => 
      v.toLowerCase().startsWith(input)
    );
  }
  
  selectMetadataValue(value: string): void {
    this.activeMetadataFilters.push({
      field: this.selectedMetadataFieldName!,
      value: value
    });
    this.selectedMetadataFieldId = null;
    this.selectedMetadataFieldName = null;
    this.onFilterChange();
  }
  
  removeMetadataFilter(index: number): void {
    this.activeMetadataFilters.splice(index, 1);
    this.onFilterChange();
  }
  
  clearAllMetadataFilters(): void {
    this.activeMetadataFilters = [];
    this.onFilterChange();
  }
  
  // Called by all filter changes (existing method)
  onFilterChange(): void {
    this.page = 1;  // Reset to first page
    this.loadData();
  }
  
  // In loadData(), build query params including metadata filters
  loadData(): void {
    const params: any = {
      date_from: this.dateFrom,
      date_to: this.dateTo,
      sort_by: this.sortBy,
      sort_order: this.sortOrder,
      page: this.page,
      page_size: this.pageSize,
    };
    
    // Existing filters...
    if (this.selectedFormat) params.formats = this.selectedFormat;
    if (this.selectedAdAccountIds.length > 0) params.ad_account_ids = this.selectedAdAccountIds.join(',');
    
    // NEW: Metadata filters as repeated params
    if (this.activeMetadataFilters.length > 0) {
      params.metadata_filter = this.activeMetadataFilters.map(f => `${f.field}:${f.value}`);
    }
    
    this.api.get<DashboardAssetsResponse>('/dashboard/assets', params).subscribe({
      next: (res) => {
        this.assets = res.items;
        this.total = res.total;
        this.totalPages = res.total_pages;
        this.loading = false;
      },
    });
  }
}
```

### Alembic Migration: Composite Index

```python
# Source: Alembic migration template for Phase 22

"""add composite index on asset_metadata_values for autocomplete

Revision ID: a9b0c1d2e3f4
Revises: z8a9b1c2d3e5
Create Date: 2026-05-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a9b0c1d2e3f4'
down_revision = 'z8a9b1c2d3e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create composite index on (field_id, value) to support autocomplete DISTINCT queries
    op.create_index(
        'idx_asset_metadata_values_field_value',
        'asset_metadata_values',
        ['field_id', 'value'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_asset_metadata_values_field_value', table_name='asset_metadata_values')
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Filter state in route query params | Filter state in component properties (temporary) | Phase 22 | URL not updated during filter changes; fine for v1.4; v1.5 will add query param serialization |
| All metadata values queried per keystroke | Load all values once, filter client-side | Phase 22 | Eliminates keystroke-debounced requests; faster UX; requires composite index |
| Flat account list | Account list grouped by platform | Phase 22 | Improves UX when 4+ platforms are connected; grouping is optional (only if >1 platform) |

**Deprecated/outdated:**
- Keystroke-debounced API calls for autocomplete — unnecessary with in-memory filtering
- Manual dropdown implementation — Angular Material mat-autocomplete is standard now

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Ad account multi-select is already fully implemented in `main` (commit e403eaf) | CONTEXT.md D-12 | If not present, DASH-02 requires full rebuild instead of verification + grouping |
| A2 | Composite index on asset_metadata_values(field_id, value) is not yet created | CONTEXT.md D-13 | If index already exists, migration is redundant but harmless |
| A3 | MatAutocompleteModule and MatChipsModule are bundled with @angular/material v17.3.0 | Standard Stack | If not available, require separate npm install |

---

## Open Questions

1. **Same-field metadata filter stacking behavior**
   - What we know: D-09 allows Language=Indonesian AND Language=English to both be applied (produces zero results)
   - What's unclear: Should UX prevent this, warn about it, or allow silently?
   - Recommendation: Allow silently; let the grid show zero results as the feedback mechanism. User will understand AND semantics.

2. **Composite index performance target**
   - What we know: DISTINCT query on 100k+ assets needs an index for <100ms response
   - What's unclear: What's the actual asset count in the organization at Phase 22 execution?
   - Recommendation: Test with largest org dataset available; if response > 500ms, verify index was created

3. **Platform grouping fallback behavior**
   - What we know: D-11 says flat list if only one platform is connected
   - What's unclear: Does "connected" mean "has at least one account" or "is enabled in platform list"?
   - Recommendation: Use account list presence — if `accountsByPlatform.length <= 1`, render flat list; otherwise render groups

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | Composite index creation | ✓ | 15.4 | — |
| Alembic | Migration execution | ✓ | 1.12.1 | — |
| Angular Material | UI components (autocomplete, chips, menu) | ✓ | 17.3.0 | — |
| FastAPI | Backend API endpoints | ✓ | 0.115.0 | — |
| SQLAlchemy | ORM and async queries | ✓ | 2.0.23 | — |

**Missing dependencies with no fallback:** None — all required tools are already installed.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + asyncpg + SQLAlchemy | pytest/conftest pattern already in use (backend/tests/) |
| Config file | backend/pytest.ini (if exists) or pyproject.toml |
| Quick run command | `pytest backend/tests/test_dashboard_filters.py -x -v` |
| Full suite command | `pytest backend/tests/ -x -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-01 | GET /dashboard/metadata-fields returns is_active=true, org_id-scoped fields | unit | `pytest backend/tests/test_dashboard_filters.py::test_metadata_fields_org_scoped -xvs` | ❌ Wave 0 |
| DASH-01 | GET /dashboard/metadata-fields/{field_id}/values returns DISTINCT values for field, no cross-org leakage | unit | `pytest backend/tests/test_dashboard_filters.py::test_metadata_values_org_guard -xvs` | ❌ Wave 0 |
| DASH-01 | GET /dashboard/assets?metadata_filter=field_name:value applies filter correctly (AND with multiple) | integration | `pytest backend/tests/test_dashboard_filters.py::test_metadata_filter_composition -xvs` | ❌ Wave 0 |
| DASH-01 | Frontend autocomplete loads values on field selection and filters client-side | e2e | Manual or Playwright (WAI) | ✅ Manual-only (no e2e framework) |
| DASH-01 | Frontend chips appear and dismiss, grid re-queries on filter change | e2e | Manual or Playwright (WAI) | ✅ Manual-only (no e2e framework) |
| DASH-02 | Ad account multi-select toggle works (already implemented) | smoke | `pytest backend/tests/test_dashboard_filters.py::test_ad_account_filter_existing -xvs` | ✅ Existing test_dashboard_filters.py covers filters |
| DASH-02 | Platform grouping renders when >1 platform connected, flat when ≤1 | visual | Manual browser inspection | ✅ Manual-only (no visual regression) |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/test_dashboard_filters.py -x` (5-10 sec)
- **Per wave merge:** `pytest backend/tests/ -x` (full suite, ~30 sec)
- **Phase gate:** Full suite + manual browser verification of UI contract (30-40 min)

### Wave 0 Gaps

- [ ] `backend/tests/test_dashboard_filters.py` — new test cases for DASH-01 metadata filter (org isolation, value fetch, multi-filter AND)
- [ ] Composite index migration (alembic/versions/a9b0c1d2e3f4_*.py)
- [ ] Backend endpoints: GET `/dashboard/metadata-fields` + GET `/dashboard/metadata-fields/{field_id}/values` + modify GET `/dashboard/assets` to accept `metadata_filter` param
- [ ] Frontend: Add MatAutocompleteModule, MatChipsModule to dashboard.component imports; implement metadata filter state management and chip rendering

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | User already authenticated via get_current_user() |
| V3 Session Management | no | Phase 22 doesn't modify session handling |
| V4 Access Control | **yes** | MetadataField.organization_id == current_user.organization_id guard on all queries; verified in both /metadata-fields and /metadata-values endpoints |
| V5 Input Validation | **yes** | Metadata filter query param parsed as `field_name:value` string; field_name validated against MetadataField.name; value validated as string (no SQL injection risk with parameterized queries) |
| V6 Cryptography | no | Phase 22 doesn't introduce new cryptographic requirements |

### Known Threat Patterns for {FastAPI + SQLAlchemy + Angular}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via metadata_filter query param | Tampering | SQLAlchemy ORM parameterizes queries; no string concatenation. `filter_value` passed to where() as bind parameter, not concatenated |
| Cross-org metadata leakage via autocomplete | Disclosure | Every query includes `MetadataField.organization_id == current_user.organization_id` guard; verified in code review |
| Metadata field enumeration attack | Information Disclosure | GET /dashboard/metadata-fields lists all fields the user's org has configured — expected behavior. No hidden fields. An attacker must already have org credentials to call this endpoint |
| User-provided field_name in metadata_filter param | Tampering | Field name validated against MetadataField.name column in database. Unknown field names result in empty JOIN (no asset matches) or explicit 404. Frontend constructs filter strings only from loaded field names |
| Filter bypass via modified query params | Tampering | Filters applied in WHERE clauses before pagination; cannot be bypassed by changing page numbers |

---

## Sources

### Primary (HIGH confidence)

- **[VERIFIED: codebase]** backend/app/models/creative.py — AssetMetadataValue model exists with field_id, value columns; unique constraint on (asset_id, field_id)
- **[VERIFIED: codebase]** backend/app/models/metadata.py — MetadataField model with organization_id, name, label, field_type, is_active columns
- **[VERIFIED: codebase]** backend/app/api/v1/endpoints/dashboard.py — existing get_dashboard_assets pattern with org-scoped queries and SQLAlchemy JOINs
- **[VERIFIED: codebase]** frontend/src/app/features/dashboard/dashboard.component.ts — existing filter state management pattern (selectedAdAccountIds, onFilterChange, loadData)
- **[VERIFIED: codebase]** frontend/package.json — @angular/material v17.3.0 already installed; no new npm install needed
- **[VERIFIED: codebase]** backend/alembic/versions — migration naming convention and pattern observed from existing migrations
- **[CITED: .planning/phases/22-dashboard-metadata-account-filters/22-CONTEXT.md]** — Phase 22 scope, decisions D-01 through D-13, canonical references

### Secondary (MEDIUM confidence)

- **[VERIFIED: codebase]** backend/tests/conftest.py + test_dashboard_filters.py — pytest + SQLAlchemy testing pattern established
- **[VERIFIED: codebase]** backend/requirements.txt — fastapi 0.115.0, sqlalchemy 2.0.23, alembic 1.12.1 versions confirmed

### Tertiary (validation deferred)

- A1 (ad account multi-select exists in main) — will be verified before Phase 22 execution per STATE.md "Confirm bgutil port 4416 reachability" pattern
- A2 (composite index not yet created) — will be verified during Alembic migration review

---

## Metadata

**Confidence breakdown:**
- **Standard stack: HIGH** — All technologies verified in codebase (Angular Material, FastAPI, SQLAlchemy, PostgreSQL, Alembic)
- **Architecture: HIGH** — Patterns (org-scoped queries, state management, API endpoints) observed in existing phases
- **Pitfalls: HIGH** — Security concern (org isolation) is clear; performance concern (composite index) is documented in CONTEXT.md D-13
- **Test infrastructure: MEDIUM** — pytest framework confirmed, test patterns observed, but Wave 0 gaps for DASH-01 specific test cases

**Research date:** 2026-05-15
**Valid until:** 2026-05-29 (14 days — filter implementation is stable, but composite index and account filter verification may change if Phase 20 is updated)
