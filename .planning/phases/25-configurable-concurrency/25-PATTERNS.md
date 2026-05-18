# Phase 25: Configurable Concurrency - Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 7 new/modified files
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/alembic/versions/[new].py` | migration | schema-change | `backend/alembic/versions/a9b1c2d3e5f6_add_proxy_config.py` | exact |
| `backend/app/models/system_config.py` | model | CRUD | `backend/app/models/system_config.py` (existing) | same-file |
| `backend/app/services/sync/proxy_cache.py` | service | CRUD-with-cache | `backend/app/services/sync/proxy_cache.py` (existing) | same-file |
| `backend/app/services/sync/dv360_sync.py` | service | async-streaming | `backend/app/services/sync/dv360_sync.py` (existing) | same-file |
| `backend/app/services/sync/google_ads_sync.py` | service | async-streaming | `backend/app/services/sync/google_ads_sync.py` (existing) | same-file |
| `backend/app/api/v1/endpoints/super_admin.py` | controller | request-response | `backend/app/api/v1/endpoints/super_admin.py` (existing) | same-file |
| `frontend/src/app/features/configuration/pages/admin.component.ts` | component | UI-form | `frontend/src/app/features/configuration/pages/admin.component.ts` (existing) | same-file |

## Pattern Assignments

### `backend/alembic/versions/[new-migration].py` (migration, schema-change)

**Analog:** `backend/alembic/versions/a9b1c2d3e5f6_add_proxy_config.py`

**Structure** (lines 1-45):
```python
"""Add max_concurrent_downloads to system_config

Revision ID: [new_id]
Revises: [previous_id]
Create Date: 2026-05-18

Adds one column to system_config for Phase 25 download concurrency control:
  max_concurrent_downloads (Integer, NOT NULL, default 3) — max parallel downloads (1–10)
"""
from alembic import op
import sqlalchemy as sa

revision = "[new_id]"
down_revision = "[previous_id]"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "max_concurrent_downloads",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
    )


def downgrade() -> None:
    op.drop_column("system_config", "max_concurrent_downloads")
```

---

### `backend/app/models/system_config.py` (model, CRUD)

**Analog:** `backend/app/models/system_config.py` (existing file, lines 1–47)

**New column pattern** (add to line 43, before `__table_args__`):
```python
# Download concurrency control (Phase 25)
max_concurrent_downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
```

**Imports already present** (lines 1–7):
```python
from sqlalchemy import String, DateTime, UniqueConstraint, Text, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
```

**Existing column patterns to match** (lines 27–42):
```python
scoring_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
proxy_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
```

---

### `backend/app/services/sync/proxy_cache.py` (service, CRUD-with-cache)

**Analog:** `backend/app/services/sync/proxy_cache.py` (existing file, lines 1–102)

**Module-level cache structure** (lines 32–46):
```python
CACHE_TTL_SECONDS = 60

_cache: dict = {
    "proxy_enabled": False,
    "proxy_url": None,
    "expires_at": 0.0,
}

_cache_lock = asyncio.Lock()
```

**Add new function after `reset_cache()` (after line 102)**:
```python
# ---------------------------------------------------------------------------
# Concurrency semaphore cache (Phase 25)
# ---------------------------------------------------------------------------

_concurrency_cache: dict = {
    "semaphore": asyncio.Semaphore(3),  # default capacity
    "expires_at": 0.0,
}


async def get_concurrency_semaphore() -> asyncio.Semaphore:
    """Return the current asyncio.Semaphore for download concurrency control.
    
    On cache hit (within 60s of last DB load): returns immediately from memory.
    On cache miss (TTL expired): reads max_concurrent_downloads from SystemConfig DB,
    creates a new Semaphore with that capacity, and caches it.
    
    In-flight downloads holding the old semaphore finish on the old semaphore;
    new downloads acquire from the new semaphore after TTL expiry.
    This is acceptable because sync jobs run every 15 minutes (D-03, D-04).
    """
    async with _cache_lock:
        now = time.monotonic()
        
        # Cache hit — TTL not yet expired
        if now < _concurrency_cache["expires_at"]:
            return _concurrency_cache["semaphore"]
        
        # Cache miss — load fresh from DB
        max_concurrent = 3  # default
        
        try:
            async with get_session_factory()() as db:
                cfg = (
                    await db.execute(select(SystemConfig).limit(1))
                ).scalar_one_or_none()
                
                if cfg and cfg.max_concurrent_downloads:
                    max_concurrent = cfg.max_concurrent_downloads
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to load concurrency config from DB: %s", e)
        
        # Create new semaphore and cache it
        _concurrency_cache["semaphore"] = asyncio.Semaphore(max_concurrent)
        _concurrency_cache["expires_at"] = now + CACHE_TTL_SECONDS
        
        return _concurrency_cache["semaphore"]
```

**Imports already present** (lines 19–28):
```python
import asyncio
import logging
import time
from typing import Optional, Tuple

from sqlalchemy import select

from app.db.base import get_session_factory
from app.models.system_config import SystemConfig
```

---

### `backend/app/services/sync/dv360_sync.py` (service, async-streaming)

**Analog:** `backend/app/services/sync/dv360_sync.py` (existing file, lines 1206–1401)

**Wrapping pattern at `_download_video_asset` call site** (line 1401):

**Before (Phase 24):**
```python
try:
    for i, cookie in enumerate(attempts):
        # ... attempt setup ...
        try:
            await _do_download(info_dict, proxy=attempt_proxy, cookie_data=cookie)
```

**After (Phase 25):**
```python
try:
    for i, cookie in enumerate(attempts):
        # ... attempt setup ...
        try:
            # Phase 25: Acquire semaphore slot before downloading (PERF-02)
            from app.services.sync import proxy_cache
            semaphore = await proxy_cache.get_concurrency_semaphore()
            
            async with semaphore:
                await _do_download(info_dict, proxy=attempt_proxy, cookie_data=cookie)
```

**Import to add at top of file** (add to existing imports from `app.services.sync`):
```python
from app.services.sync import proxy_cache
```

---

### `backend/app/services/sync/google_ads_sync.py` (service, async-streaming)

**Analog:** `backend/app/services/sync/google_ads_sync.py` (existing file, lines 282–503)

**Wrapping pattern at `_download_video` call site** (line 503):

**Before (Phase 24):**
```python
try:
    for i, cookie in enumerate(attempts):
        # ... attempt setup ...
        try:
            await _do_download(info_dict, proxy=attempt_proxy, cookie_data=cookie)
```

**After (Phase 25):**
```python
try:
    for i, cookie in enumerate(attempts):
        # ... attempt setup ...
        try:
            # Phase 25: Acquire semaphore slot before downloading (PERF-02)
            from app.services.sync import proxy_cache
            semaphore = await proxy_cache.get_concurrency_semaphore()
            
            async with semaphore:
                await _do_download(info_dict, proxy=attempt_proxy, cookie_data=cookie)
```

**Import to add at top of file** (add to existing imports from `app.services.sync`):
```python
from app.services.sync import proxy_cache
```

---

### `backend/app/api/v1/endpoints/super_admin.py` (controller, request-response)

**Analog:** `backend/app/api/v1/endpoints/super_admin.py` (existing file, lines 276–344)

**Pydantic response model pattern** (add after line 72, following `UpdateProxyConfigRequest`):
```python
class ConcurrencyConfigResponse(BaseModel):
    """Response model for GET/PUT /download-concurrency endpoint."""
    max_concurrent_downloads: int
    
    class Config:
        from_attributes = True  # Allow loading from SQLAlchemy model
```

**GET endpoint pattern** (add after the proxy test endpoint, after line 382):
```python
@router.get("/download-concurrency", response_model=ConcurrencyConfigResponse)
async def get_concurrency_config(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Return current max_concurrent_downloads setting."""
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()
    
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System config not initialized",
        )
    
    return ConcurrencyConfigResponse(
        max_concurrent_downloads=config.max_concurrent_downloads or 3
    )
```

**PUT endpoint pattern** (add after GET endpoint):
```python
@router.put("/download-concurrency", response_model=ConcurrencyConfigResponse)
async def update_concurrency_config(
    payload: ConcurrencyConfigRequest,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Update max_concurrent_downloads setting (range 1–10).
    
    Changes take effect within 60 seconds (cache TTL).
    No explicit cache invalidation needed (D-05).
    """
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System config not initialized",
        )
    
    config.max_concurrent_downloads = payload.max_concurrent_downloads
    db.add(config)
    await db.commit()
    await db.refresh(config)
    
    logger.info(
        "SuperAdmin %s set max_concurrent_downloads=%s",
        current_user.email,
        payload.max_concurrent_downloads,
    )
    
    return ConcurrencyConfigResponse(
        max_concurrent_downloads=config.max_concurrent_downloads or 3
    )
```

**Request model to add after ConcurrencyConfigResponse**:
```python
class ConcurrencyConfigRequest(BaseModel):
    """Request model for PUT /download-concurrency endpoint."""
    max_concurrent_downloads: int  # Range 1–10 enforced by Pydantic Field validation
    
    class Config:
        from_attributes = True
```

**Validation pattern with Pydantic Field** (update ConcurrencyConfigRequest):
```python
from pydantic import BaseModel, Field

class ConcurrencyConfigRequest(BaseModel):
    """Request model for PUT /download-concurrency endpoint."""
    max_concurrent_downloads: int = Field(ge=1, le=10)
```

**Imports already present** (lines 21–40):
```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
```

---

### `frontend/src/app/features/configuration/pages/admin.component.ts` (component, UI-form)

**Analog:** `frontend/src/app/features/configuration/pages/admin.component.ts` (existing file, lines 1–210)

**Component interface to add** (after line 62, following ProxyTestResult interface):
```typescript
interface ConcurrencyConfig {
  max_concurrent_downloads: number;
}
```

**Import mat-slider module** (update imports at line 67):
```typescript
import { MatSliderModule } from '@angular/material/slider';

imports: [
  CommonModule, 
  FormsModule, 
  MatButtonModule, 
  MatFormFieldModule, 
  MatInputModule, 
  MatProgressSpinnerModule, 
  MatSlideToggleModule, 
  MatSnackBarModule,
  MatSliderModule,  // ADD THIS
],
```

**Component properties to add** (add to class properties):
```typescript
concurrencyConfig: ConcurrencyConfig | null = null;
savingConcurrency = false;
concurrencyDraft: number = 3;  // local draft value before save
```

**Load concurrency config in ngOnInit** (add to existing ngOnInit method):
```typescript
// Load concurrency config on init
this.loadConcurrencyConfig();
```

**Add method to load config**:
```typescript
async loadConcurrencyConfig() {
  try {
    this.concurrencyConfig = await this.api.get('/api/v1/super-admin/download-concurrency').toPromise() as ConcurrencyConfig;
    this.concurrencyDraft = this.concurrencyConfig?.max_concurrent_downloads || 3;
  } catch (err) {
    this.snackBar.open('Failed to load concurrency config', 'Close', { duration: 5000 });
  }
}
```

**Add save and discard methods**:
```typescript
async saveConcurrency() {
  this.savingConcurrency = true;
  try {
    const response = await this.api.put('/api/v1/super-admin/download-concurrency', {
      max_concurrent_downloads: this.concurrencyDraft,
    }).toPromise();
    this.concurrencyConfig = response as ConcurrencyConfig;
    this.snackBar.open('Concurrency setting saved', 'Close', { duration: 3000 });
  } catch (err) {
    this.snackBar.open('Failed to save concurrency setting', 'Close', { duration: 5000 });
  } finally {
    this.savingConcurrency = false;
  }
}

discardConcurrencyEdit() {
  this.concurrencyDraft = this.concurrencyConfig?.max_concurrent_downloads || 3;
}
```

**Section restructure in template** (replace Section 1 "Residential Proxy" and Section 2 "YouTube Cookies" with merged "Download Settings" section):

**Insert after line 68** (before existing "Residential Proxy" section):
```typescript
  <!-- NEW: Download Settings (merged from Proxy + Cookies) -->
  <section class="config-section">
    <div class="section-header">
      <div>
        <h2>Download Settings</h2>
        <p class="section-desc">Manage download concurrency, residential proxy, and authentication cookies.</p>
      </div>
    </div>
    <div class="section-body">
      
      <!-- Subsection 1: Parallel Downloads (NEW) -->
      <div class="subsection">
        <h3>Parallel Downloads</h3>
        <div class="slider-container">
          <label for="concurrency-slider">Maximum concurrent downloads:</label>
          <div class="slider-row">
            <mat-slider
              #concurrencySlider
              id="concurrency-slider"
              min="1"
              max="10"
              step="1"
              discrete
              [value]="concurrencyDraft"
              (valueChange)="concurrencyDraft = $event">
            </mat-slider>
            <span class="slider-value">{{ concurrencyDraft }}</span>
          </div>
        </div>
        <div class="slider-actions">
          <button mat-stroked-button (click)="discardConcurrencyEdit()" [disabled]="savingConcurrency">
            Discard
          </button>
          <button mat-flat-button class="save-btn" (click)="saveConcurrency()" [disabled]="savingConcurrency">
            <mat-spinner *ngIf="savingConcurrency" diameter="14"></mat-spinner>
            {{ savingConcurrency ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>
      
      <!-- Visual divider between subsections -->
      <hr class="subsection-divider">
      
      <!-- Subsection 2: Residential Proxy (moved from standalone section) -->
      <div class="subsection">
        <h3>Residential Proxy</h3>
        <!-- COPY proxy configuration UI from existing Section 1, lines 78–131 -->
      </div>
      
      <!-- Visual divider between subsections -->
      <hr class="subsection-divider">
      
      <!-- Subsection 3: Cookies (moved from standalone section) -->
      <div class="subsection">
        <h3>Cookies</h3>
        <!-- COPY cookie configuration UI from existing Section 2, lines 148–208 -->
      </div>
      
    </div>
  </section>
```

**Styles to add** (add to existing styles around line 400):
```css
.subsection {
  border-top: 1px solid var(--border);
  padding-top: 16px;
  margin-top: 16px;
}

.subsection:first-child {
  border-top: none;
  padding-top: 0;
  margin-top: 0;
}

.subsection-divider {
  border: none;
  border-top: 1px solid var(--border);
  margin: 16px 0;
}

.slider-container {
  margin-bottom: 16px;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.slider-value {
  font-weight: 600;
  min-width: 20px;
  text-align: right;
}

.slider-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 12px;
}
```

---

## Shared Patterns

### Module-Level Async Cache with TTL (PERF-04 from Phase 24, reused in Phase 25)

**Source:** `backend/app/services/sync/proxy_cache.py` (lines 32–92)

**Apply to:** All functions reading config from DB with periodic refresh

**Pattern:**
```python
CACHE_TTL_SECONDS = 60

_cache: dict = {
    "data": initial_value,
    "expires_at": 0.0,
}

_cache_lock = asyncio.Lock()


async def get_cached_config():
    async with _cache_lock:
        now = time.monotonic()
        
        if now < _cache["expires_at"]:
            return _cache["data"]  # Cache hit
        
        # Cache miss — load from DB
        _cache["data"] = db_fetch()
        _cache["expires_at"] = now + CACHE_TTL_SECONDS
        return _cache["data"]
```

**Why:** Eliminates per-call DB overhead while allowing config changes to take effect within 60 seconds. Critical for performance-sensitive download loops.

---

### SuperAdmin Endpoint GET/PUT Pattern (ASVS V4 + request validation)

**Source:** `backend/app/api/v1/endpoints/super_admin.py` (lines 276–344)

**Apply to:** All SuperAdmin configuration endpoints

**Pattern:**
1. Pydantic request/response models with `from_attributes = True`
2. `Depends(get_current_superadmin)` guard on every endpoint
3. `Depends(get_db)` for DB session
4. Query with `.limit(1)`, check for None, raise 500 if missing
5. Update model, `db.add()`, `await db.commit()`, `await db.refresh()`
6. Return fresh Pydantic response model
7. Log with `logger.info()`, never log sensitive values

**Security:** Endpoint guard at FastAPI layer, input validation at Pydantic layer, database constraints (CHECK) at SQL layer. Defense in depth.

---

### Async Semaphore Acquisition at High-Concurrency Call Sites

**Source:** `backend/app/services/sync/dv360_sync.py` (Phase 24 `_do_download` call site, line 1401)

**Apply to:** All async operations competing for a shared resource (downloads, proxy bandwidth, connection pool)

**Pattern:**
```python
semaphore = await get_concurrency_semaphore()

async with semaphore:
    # Rate-limited operation
    await _do_download(...)
```

**Why:** Asyncio.Semaphore is the Python standard for coroutine-level rate limiting. Using it prevents unbounded task creation (DoS vector). Acquiring before entering the operation ensures the rate limit is enforced at the most critical point (before proxy/bandwidth usage).

---

## No Analog Found

All files have direct analogs in the existing codebase. No new patterns required.

---

## Metadata

**Analog search scope:** `backend/alembic/versions/`, `backend/app/models/`, `backend/app/services/sync/`, `backend/app/api/v1/endpoints/`, `frontend/src/app/features/configuration/`

**Files scanned:** ~10 source files + 3 Alembic migrations

**Pattern extraction date:** 2026-05-18

**Key insights:**
- Phase 25 is a pure extension of Phase 24 patterns: same cache TTL structure (proxy_cache.py) reused for semaphore cache, same endpoint pattern (super_admin.py GET/PUT) reused for concurrency endpoint, same async wrapping strategy reused for semaphore acquisition in download call sites.
- DB migration is boilerplate (add 1 Integer column with default=3, server_default="3") following the Phase 20 proxy_config migration pattern.
- Frontend restructuring is refactoring only — no new Material components (mat-slider already installed), no new CSS patterns, reuses existing section structure and save/discard button UX.
- All security patterns already in place: SuperAdmin guard on API, input validation with Pydantic Field (ge=1, le=10), DB CHECK constraint on column.
