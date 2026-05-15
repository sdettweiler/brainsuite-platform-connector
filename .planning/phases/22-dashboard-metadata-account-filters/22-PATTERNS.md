# Phase 22: Dashboard Metadata + Account Filters - Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** 5
**Analogs found:** 4 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/api/v1/endpoints/dashboard.py` | controller/endpoint | CRUD + request-response | `backend/app/api/v1/endpoints/dashboard.py` (existing) | exact |
| `backend/alembic/versions/[new_migration].py` | migration | DDL | `backend/alembic/versions/a1b2c3d4e5f6_normalize_language_codes_to_locale.py` | exact |
| `backend/tests/test_dashboard_filters.py` | test | assertion | `backend/tests/test_dashboard_filters.py` (existing) | exact |
| `frontend/src/app/features/dashboard/dashboard.component.ts` | component | request-response | `frontend/src/app/features/dashboard/dashboard.component.ts` (existing) | exact |

---

## Pattern Assignments

### `backend/app/api/v1/endpoints/dashboard.py` (controller, request-response)

**Analog:** Same file — modify existing `get_dashboard_assets` endpoint

**Imports pattern** (lines 1-27):
```python
from datetime import date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text, case, nullslast, cast, distinct
from sqlalchemy.orm import aliased

from app.db.base import get_db
from app.models.user import User
from app.models.creative import CreativeAsset, AssetMetadataValue
from app.models.metadata import MetadataField
from app.api.v1.deps import get_current_user

router = APIRouter()
```

**Endpoint signature & parameter pattern** (lines 184-200):
```python
@router.get("/assets", response_model=dict)
async def get_dashboard_assets(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    # ... existing params ...
    ad_account_ids: Optional[str] = Query(default=None),  # EXISTING pattern for multi-select
    metadata_filter: Optional[List[str]] = Query(default=None),  # NEW: add this param
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
```

**Query parameter parsing pattern** (lines 208-211):
```python
platform_list = [p.strip().upper() for p in platforms.split(",")] if platforms else None
format_list = [f.strip().upper() for f in formats.split(",")] if formats else None
account_id_list = [a.strip() for a in ad_account_ids.split(",")] if ad_account_ids else None

# NEW: Parse metadata_filter repeated params as list of "field_name:value" strings
# metadata_filter already comes as List[str] from FastAPI, no parsing needed
```

**Filter application pattern — org-scoped query** (lines 268-306):
```python
# Existing pattern (copy for new metadata filter):
query = (
    select(CreativeAsset, perf_subq, CreativeScoreResult.scoring_status, ...)
    .where(CreativeAsset.organization_id == current_user.organization_id)  # REQUIRED ORG GUARD
)

# Existing single-field filter application:
if account_id_list:
    query = query.where(CreativeAsset.ad_account_id.in_(account_id_list))

# NEW: Apply metadata filters using JOIN per filter (AND logic)
if metadata_filter:
    for i, meta_filter_str in enumerate(metadata_filter):
        field_name, filter_value = meta_filter_str.split(':', 1)
        
        # Use aliased tables for multiple JOINs to same table
        amv_alias = aliased(AssetMetadataValue, name=f"amv_{i}")
        mf_alias = aliased(MetadataField, name=f"mf_{i}")
        
        query = query.join(
            amv_alias,
            and_(
                amv_alias.asset_id == CreativeAsset.id,
                amv_alias.value == filter_value,
            )
        ).join(
            mf_alias,
            and_(
                mf_alias.id == amv_alias.field_id,
                mf_alias.name == field_name,
                mf_alias.organization_id == current_user.organization_id,  # ORG GUARD
            )
        )
```

**New endpoints: Metadata field list and values**

Add two new endpoints to the same `dashboard.py` file:

```python
@router.get("/metadata-fields")
async def get_metadata_fields(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all active metadata fields for the current organization."""
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
                "name": f.name,              # Used for API filter encoding
                "label": f.label,            # Used for chip display
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
    
    # Query DISTINCT values with org guard via JOIN
    query = (
        select(distinct(AssetMetadataValue.value))
        .join(MetadataField, MetadataField.id == AssetMetadataValue.field_id)
        .join(CreativeAsset, CreativeAsset.id == AssetMetadataValue.asset_id)
        .where(
            MetadataField.organization_id == current_user.organization_id,  # ORG GUARD
            MetadataField.id == field_id,
            AssetMetadataValue.value.isnot(None),
        )
        .order_by(AssetMetadataValue.value)
    )
    
    result = await db.execute(query)
    values = [row[0] for row in result.all()]
    
    return {"values": values}
```

---

### `backend/alembic/versions/[new_migration].py` (migration, DDL)

**Analog:** `backend/alembic/versions/a1b2c3d4e5f6_normalize_language_codes_to_locale.py` (lines 1-16)

**Migration structure pattern**:
```python
"""add composite index on asset_metadata_values for autocomplete

Revision ID: a9b0c1d2e3f4
Revises: z8a9b1c2d3e5
Create Date: 2026-05-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a9b0c1d2e3f4'
down_revision = 'z8a9b1c2d3e5'  # Replace with actual previous migration ID
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

### `backend/tests/test_dashboard_filters.py` (test, assertion)

**Analog:** `backend/tests/test_dashboard_filters.py` (existing file, lines 1-100)

**Test structure pattern** (lines 1-50):
```python
"""
Phase 22 Plan — Dashboard Metadata + Account Filters Tests.

Tests for:
- GET /dashboard/metadata-fields returns is_active=true, org-scoped fields
- GET /dashboard/metadata-fields/{field_id}/values returns DISTINCT values, no cross-org leakage
- GET /dashboard/assets?metadata_filter=field_name:value applies filter correctly
- Multiple metadata_filter params AND together correctly

These tests validate DASH-01 requirements.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db():
    """Async DB session mock."""
    return AsyncMock()


@pytest.fixture
def mock_user():
    """Minimal user mock."""
    user = MagicMock()
    user.organization_id = uuid.uuid4()
    return user
```

**Test case pattern** (lines 65-92):
```python
def test_metadata_fields_org_scoped():
    """GET /dashboard/metadata-fields returns only fields for current org."""
    # Arrange: Mock fields from current org and another org
    org1_id = uuid.uuid4()
    org2_id = uuid.uuid4()
    
    current_user = MagicMock()
    current_user.organization_id = org1_id
    
    # Act: Call endpoint
    # Assert: Verify only org1 fields returned, no org2 leakage
    assert True  # Implement full test body


def test_metadata_values_org_guard():
    """GET /dashboard/metadata-fields/{field_id}/values enforces org isolation."""
    # Arrange: Field from org1, asset from org1, org2 user requests
    # Act: org2_user calls endpoint with org1 field_id
    # Assert: HTTPException 404 (field not found for org2_user)
    assert True  # Implement full test body


def test_metadata_filter_composition():
    """GET /dashboard/assets?metadata_filter=language:Indonesian&metadata_filter=market:US applies AND logic."""
    # Arrange: Multiple metadata filters
    # Act: Query with two metadata_filter params
    # Assert: Results match BOTH conditions (asset.language == Indonesian AND asset.market == US)
    assert True  # Implement full test body
```

---

### `frontend/src/app/features/dashboard/dashboard.component.ts` (component, request-response)

**Analog:** Same file — modify existing filter state management and `onFilterChange()` method

**Imports to ADD** (lines 1-27):
```typescript
// ADD to existing imports:
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatChipsModule } from '@angular/material/chips';

// Already imported:
// import { CommonModule } from '@angular/common';
// import { ReactiveFormsModule, FormsModule } from '@angular/forms';
// import { MatMenuModule } from '@angular/material/menu';
```

**Component imports array** (line 100-108):
```typescript
@Component({
  standalone: true,
  imports: [
    CommonModule, ReactiveFormsModule, FormsModule,
    MatButtonModule, MatSelectModule, MatFormFieldModule,
    MatInputModule, MatMenuModule, MatDialogModule, MatTooltipModule,
    MatAutocompleteModule,  // ADD THIS
    MatChipsModule,         // ADD THIS
    // ... rest of existing imports ...
  ],
  // ...
})
```

**Filter state properties to ADD** (after line 1176 `selectedAdAccountIds`):
```typescript
// Metadata filter state
metadataFields: any[] = [];                      // From GET /dashboard/metadata-fields
selectedMetadataFieldId: string | null = null;  // Step 1: field selection
selectedMetadataFieldName: string | null = null;
selectedMetadataFieldLabel: string | null = null;
metadataFieldValues: string[] = [];              // From GET /dashboard/metadata-fields/{field_id}/values
metadataValueInput = '';                         // Step 2: autocomplete input
activeMetadataFilters: {field: string; value: string}[] = [];  // Stacked filters
metadataValuesLoading = false;
```

**Load metadata fields on init** (add to `ngOnInit()`, after line 1301):
```typescript
// Load metadata fields for dropdown
this.loadMetadataFields();
```

**Methods to ADD**:
```typescript
loadMetadataFields(): void {
  this.api.get<{fields: any[]}>('/dashboard/metadata-fields')
    .subscribe({
      next: (res) => {
        this.metadataFields = res.fields;
      },
    });
}

selectMetadataField(field: any): void {
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

// Client-side prefix matching (no HTTP request per keystroke)
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
```

**Modify loadData()** (lines 1553-1595):

After line 1567 `if (this.selectedAdAccountIds.length > 0) params['ad_account_ids'] = ...`, ADD:

```typescript
// NEW: Metadata filters as repeated params
if (this.activeMetadataFilters.length > 0) {
  params.metadata_filter = this.activeMetadataFilters.map(f => `${f.field}:${f.value}`);
}
```

**Template changes** (lines 112-201):

After the "Ad Account filter" button block (lines 148-161), INSERT the "Metadata filter" button:

```html
<!-- Metadata filter -->
<button class="tbd-trigger" [matMenuTriggerFor]="metadataMenu">
  {{activeMetadataFilters.length === 0 ? 'Metadata' : 'Metadata (' + activeMetadataFilters.length + ')'}}<i class="bi bi-chevron-down tbd-arrow"></i>
</button>
<mat-menu #metadataMenu="matMenu" class="tbd-menu">
  <!-- Step 1: Field selector -->
  <ng-container *ngIf="selectedMetadataFieldId === null">
    <button mat-menu-item *ngFor="let field of metadataFields" (click)="$event.stopPropagation(); selectMetadataField(field)">
      <span class="tbd-name">{{field.label}}</span>
    </button>
  </ng-container>
  
  <!-- Step 2: Value autocomplete -->
  <ng-container *ngIf="selectedMetadataFieldId !== null">
    <button mat-menu-item (click)="$event.stopPropagation()" disabled style="padding: 0;">
      <input 
        [(ngModel)]="metadataValueInput"
        placeholder="Type to filter..."
        style="width: 100%; padding: 8px; border: none; background: transparent; color: var(--text-primary, #fff); font-size: 14px;"
        (click)="$event.stopPropagation()"
      />
    </button>
    <!-- Loading indicator -->
    <button mat-menu-item *ngIf="metadataValuesLoading" disabled>
      <span style="font-size: 12px; color: var(--text-muted, #999);">Loading...</span>
    </button>
    <!-- Value suggestions (client-side filtered) -->
    <button mat-menu-item *ngFor="let val of filteredMetadataValues" (click)="$event.stopPropagation(); selectMetadataValue(val)">
      <span class="tbd-name">{{val}}</span>
    </button>
    <!-- No matches -->
    <button mat-menu-item *ngIf="filteredMetadataValues.length === 0 && !metadataValuesLoading" disabled>
      <span style="font-size: 12px; color: var(--text-muted, #999);">No matches</span>
    </button>
  </ng-container>
</mat-menu>

<!-- Metadata filter chips (active filters below filter bar) -->
<div class="metadata-filter-chips" *ngIf="activeMetadataFilters.length > 0">
  <div class="chip" *ngFor="let filter of activeMetadataFilters; let i = index">
    <span>{{filter.field}}: {{filter.value}}</span>
    <button class="chip-dismiss" (click)="removeMetadataFilter(i)" type="button">×</button>
  </div>
  <button class="clear-all-btn" (click)="clearAllMetadataFilters()" *ngIf="activeMetadataFilters.length > 1">
    Clear all
  </button>
</div>
```

**Styles to ADD** (in component `styles` array):

```css
.metadata-filter-chips {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  flex-wrap: wrap;
  background: rgba(255, 255, 255, 0.05);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: rgba(255, 119, 0, 0.2);
  border: 1px solid rgba(255, 119, 0, 0.4);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-primary, #fff);
}

.chip-dismiss {
  background: none;
  border: none;
  color: var(--text-muted, #999);
  cursor: pointer;
  font-size: 14px;
  padding: 0;
  line-height: 1;
  margin-left: 2px;
}

.chip-dismiss:hover {
  color: var(--text-primary, #fff);
}

.clear-all-btn {
  padding: 4px 8px;
  font-size: 11px;
  color: var(--text-muted, #999);
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s;
}

.clear-all-btn:hover {
  background: rgba(255, 119, 0, 0.1);
  border-color: rgba(255, 119, 0, 0.4);
}
```

---

## Shared Patterns

### Organization-Scoped Query Pattern

**Apply to:** All metadata-related queries (both fetch and filter endpoints)

Every query touching `MetadataField` or `AssetMetadataValue` MUST include:

```python
.where(MetadataField.organization_id == current_user.organization_id)
```

This prevents cross-org data leakage. See backend pattern assignments above for examples.

### Filter State Management Pattern

**Apply to:** All filter components (both new metadata filters and existing ad account filter)

Pattern observed in lines 1176, 1687-1694 of `dashboard.component.ts`:

```typescript
// State properties
selectedFilterIds: string[] = [];
activeFilters: {field: string; value: string}[] = [];

// Toggle method
toggleFilter(id: string): void {
  const idx = this.selectedFilterIds.indexOf(id);
  if (idx >= 0) {
    this.selectedFilterIds.splice(idx, 1);
  } else {
    this.selectedFilterIds.push(id);
  }
  this.onFilterChange();
}

// Trigger re-query
onFilterChange(): void {
  this.page = 1;  // Reset pagination
  this.loadData();
}
```

### Query Parameter Encoding Pattern

**Apply to:** All filter params passed to API

Observed in lines 1555-1567 of `dashboard.component.ts`:

```typescript
const params: any = {
  date_from: this.dateFrom,
  date_to: this.dateTo,
};
if (this.selectedAdAccountIds.length > 0) 
  params['ad_account_ids'] = this.selectedAdAccountIds.join(',');  // Comma-separated single-value
if (this.activeMetadataFilters.length > 0) 
  params.metadata_filter = this.activeMetadataFilters.map(f => `${f.field}:${f.value}`);  // Array of strings

this.api.get<DashboardAssetsResponse>('/dashboard/assets', params).subscribe({...});
```

FastAPI automatically converts:
- `ad_account_ids=a,b,c` → `Optional[str]`
- `metadata_filter=f1:v1&metadata_filter=f2:v2` → `Optional[List[str]]`

---

## No Analog Found

All files have direct analogs in the existing codebase. No new patterns needed beyond what already exists.

---

## Metadata

**Analog search scope:** 
- `backend/app/api/v1/endpoints/` (FastAPI endpoint patterns)
- `backend/alembic/versions/` (Alembic migration structure)
- `backend/tests/test_*.py` (pytest test patterns)
- `frontend/src/app/features/dashboard/` (Angular component state management)

**Pattern extraction date:** 2026-05-15

**Key implementation dependencies:**
1. Composite index migration must run BEFORE first autocomplete request
2. New endpoints (`/metadata-fields`, `/metadata-fields/{field_id}/values`) must exist before frontend loads
3. Frontend metadata filter chip rendering requires `MatAutocompleteModule` + `MatChipsModule` in component imports
4. Every metadata-related query requires explicit `MetadataField.organization_id == current_user.organization_id` guard

---

## Implementation Checklist

- [ ] **Backend: Add migration** — Composite index on `asset_metadata_values(field_id, value)`
- [ ] **Backend: Add two new endpoints** — `/metadata-fields` and `/metadata-fields/{field_id}/values`
- [ ] **Backend: Modify existing endpoint** — Add `metadata_filter` param to `get_dashboard_assets()`
- [ ] **Backend: Tests** — Add test cases for org isolation and filter composition
- [ ] **Frontend: Update imports** — Add `MatAutocompleteModule`, `MatChipsModule`
- [ ] **Frontend: Add state properties** — Metadata field/value state for two-step interaction
- [ ] **Frontend: Add methods** — Field selection, value autocomplete, chip management
- [ ] **Frontend: Update template** — Metadata filter button, autocomplete input, chip row
- [ ] **Frontend: Update styles** — Chip styling + dismissal UX
- [ ] **Frontend: Update loadData()** — Encode metadata filters as repeated query params

---
