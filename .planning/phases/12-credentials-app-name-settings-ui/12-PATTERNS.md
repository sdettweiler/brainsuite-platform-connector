# Phase 12: Credentials + App Name Settings UI - Pattern Map

**Mapped:** 2026-04-16
**Files analyzed:** 8 new/modified files
**Analogs found:** 7 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/api/v1/endpoints/brainsuite_config.py` | controller | request-response | `backend/app/api/v1/endpoints/platforms.py` | exact |
| `backend/app/schemas/brainsuite_config.py` | model | transform | `backend/app/schemas/platform.py` | exact |
| `backend/alembic/versions/u2v3w4x5y6z7_phase12_system_app_name.py` | migration | batch | `backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py` | exact |
| `backend/app/api/v1/__init__.py` | config | request-response | self (modify) | exact |
| `backend/app/models/brainsuite_config.py` | model | CRUD | self (modify) | exact |
| `backend/app/models/platform.py` | model | CRUD | self (modify) | exact |
| `backend/app/services/sync/scoring_job.py` | service | batch | self (modify — 4 sites) | exact |
| `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts` | component | request-response | self (modify) + `organization.component.ts` | exact |

---

## Pattern Assignments

### `backend/app/api/v1/endpoints/brainsuite_config.py` (controller, request-response)

**Analog:** `backend/app/api/v1/endpoints/platforms.py`

**Imports pattern** (lines 1-31):
```python
import logging
import base64
import httpx
from datetime import datetime, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.base import get_db
from app.models.user import User
from app.models.brainsuite_config import OrgBrainsuiteConfig
from app.models.platform import BrainsuiteApp
from app.models.creative import CreativeScoreResult
from app.schemas.brainsuite_config import (
    CredentialsResponse,
    CredentialsUpdate,
    TestConnectionResponse,
    SystemAppNameUpdate,
)
from app.api.v1.deps import get_current_admin
from app.core.security import encrypt_token, decrypt_token
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()
```

**Auth/guard pattern** — admin-only guard (platforms.py lines 55-58):
```python
async def create_brainsuite_app(
    payload: BrainsuiteAppCreate,
    current_user: User = Depends(get_current_admin),   # <-- admin-only
    db: AsyncSession = Depends(get_db),
):
```

**Core GET credentials pattern** (platforms.py lines 41-51):
```python
@router.get("/apps", response_model=List[BrainsuiteAppResponse])
async def list_brainsuite_apps(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BrainsuiteApp).where(
            BrainsuiteApp.organization_id == current_user.organization_id,
            BrainsuiteApp.is_active == True,
        )
    )
    return result.scalars().all()
```

**PUT credentials (upsert + encrypt) pattern** — from RESEARCH.md verified patterns:
```python
@router.put("/credentials")
async def upsert_credentials(
    payload: CredentialsUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrgBrainsuiteConfig).where(
            OrgBrainsuiteConfig.organization_id == current_user.organization_id
        )
    )
    config = result.scalar_one_or_none()

    if config is None:
        config = OrgBrainsuiteConfig(
            organization_id=current_user.organization_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(config)

    old_client_id = config.client_id
    config.client_id = payload.client_id

    if payload.client_secret:   # D-07: empty = keep existing
        config.client_secret_encrypted = encrypt_token(payload.client_secret)

    config.updated_at = datetime.now(timezone.utc)
    await db.commit()

    changed = (old_client_id != config.client_id) or bool(payload.client_secret)
    return {"changed": changed}
```

**Test Connection auth flow pattern** — based directly on `brainsuite_score.py` lines 48-84:
```python
# The test-connection endpoint must replicate the _get_token auth call
credentials = f"{client_id}:{client_secret}"
encoded = base64.b64encode(credentials.encode()).decode()
async with httpx.AsyncClient(timeout=15) as client:
    resp = await client.post(
        settings.BRAINSUITE_AUTH_URL,
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},
    )
```

**PATCH app system_app_name pattern** (platforms.py lines 70-85):
```python
@router.patch("/apps/{app_id}", response_model=BrainsuiteAppResponse)
async def update_brainsuite_app(
    app_id: uuid.UUID,
    payload: BrainsuiteAppUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(BrainsuiteApp, app_id)
    if not app or app.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="App not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(app, field, value)
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app
```

**Rescore-all reset pattern** — using SQLAlchemy bulk update (from RESEARCH.md + scoring_job.py):
```python
from sqlalchemy import update

await db.execute(
    update(CreativeScoreResult)
    .where(
        CreativeScoreResult.organization_id == current_user.organization_id,
        CreativeScoreResult.scoring_status == "SCORED",
    )
    .values(
        scoring_status="UNSCORED",
        updated_at=datetime.now(timezone.utc),
    )
)
await db.commit()
```

---

### `backend/app/schemas/brainsuite_config.py` (model, transform)

**Analog:** `backend/app/schemas/platform.py`

**Imports + Base pattern** (platform.py lines 1-5):
```python
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
```

**Base + Create + Update + Response layering** (platform.py lines 7-33):
```python
class BrainsuiteAppBase(BaseModel):
    name: str
    ...

class BrainsuiteAppCreate(BrainsuiteAppBase):
    pass

class BrainsuiteAppUpdate(BaseModel):
    name: Optional[str] = None
    ...

class BrainsuiteAppResponse(BrainsuiteAppBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
```

**Schemas to create for this phase:**
```python
class CredentialsResponse(BaseModel):
    client_id: Optional[str] = None
    has_secret: bool = False   # NEVER return the actual secret

    class Config:
        from_attributes = True

class CredentialsUpdate(BaseModel):
    client_id: str
    client_secret: str = ""    # empty string = keep existing (D-07)

class TestConnectionResponse(BaseModel):
    success: bool
    message: str

class SystemAppNameUpdate(BaseModel):
    system_app_name: Optional[str] = None
```

---

### `backend/alembic/versions/u2v3w4x5y6z7_phase12_system_app_name.py` (migration, batch)

**Analog:** `backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py`

**Header + revision chain pattern** (s0t1u2v3w4x5 lines 1-14):
```python
"""add system_app_name to brainsuite_apps, drop video/static_app_name from org_brainsuite_config

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6          # <-- must chain from latest Phase 11 migration
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "u2v3w4x5y6z7"
down_revision = "t1u2v3w4x5y6"   # current head after Phase 11
branch_labels = None
depends_on = None
```

**Add column pattern** (s0t1u2v3w4x5 lines 17-39):
```python
def upgrade() -> None:
    # Add system_app_name to brainsuite_apps
    op.add_column(
        "brainsuite_apps",
        sa.Column("system_app_name", sa.String(255), nullable=True),
    )
    # Drop deprecated columns from org_brainsuite_config
    op.drop_column("org_brainsuite_config", "video_app_name")
    op.drop_column("org_brainsuite_config", "static_app_name")

def downgrade() -> None:
    op.add_column("org_brainsuite_config", sa.Column("video_app_name", sa.String(255), nullable=True))
    op.add_column("org_brainsuite_config", sa.Column("static_app_name", sa.String(255), nullable=True))
    op.drop_column("brainsuite_apps", "system_app_name")
```

---

### `backend/app/api/v1/__init__.py` (config — modify only)

**Analog:** self

**Current pattern to extend** (lines 1-11):
```python
from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, platforms, dashboard, assets, scoring

api_router = APIRouter()
...
api_router.include_router(scoring.router, prefix="/scoring", tags=["scoring"])
```

**Add after existing includes:**
```python
from app.api.v1.endpoints import brainsuite_config
api_router.include_router(brainsuite_config.router, prefix="/brainsuite-config", tags=["brainsuite-config"])
```

---

### `backend/app/models/brainsuite_config.py` (model — modify only)

**Analog:** self

**Columns to drop** (current lines 29-30):
```python
video_app_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
static_app_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

These two lines are deleted. The model docstring on line 11-18 also needs the reference to "video and static app names" updated.

---

### `backend/app/models/platform.py` (model — modify only)

**Analog:** `backend/app/models/brainsuite_config.py` (column type pattern)

**Column to add** — after line 20 (`is_active`), follow existing `Mapped[Optional[str]]` pattern:
```python
# Insert after is_default_for_image (line 19), before is_active (line 20)
system_app_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

String(255) + nullable=True matches every optional string in `OrgBrainsuiteConfig` (brainsuite_config.py lines 27-30).

---

### `backend/app/services/sync/scoring_job.py` (service — modify 4 sites)

**Analog:** self

**4 sites to update** (all currently read `org_config.video_app_name` / `org_config.static_app_name`):

Site 1 — lines 192-197 (required_app_name derivation):
```python
# BEFORE (Phase 11):
if endpoint_type == "VIDEO":
    required_app_name = org_config.video_app_name
elif endpoint_type == "STATIC_IMAGE":
    required_app_name = org_config.static_app_name

# AFTER (Phase 12): read from brainsuite_app row
# Load app row in the same DB session block that loads org_config
# Then: required_app_name = brainsuite_app.system_app_name if brainsuite_app else None
```

Sites 2-4 — lines 282, 298, 320, 328 (app_name= kwargs passed to score services):
```python
# BEFORE:
app_name=org_config.video_app_name,
app_name=org_config.static_app_name,

# AFTER:
app_name=required_app_name,   # already derived from brainsuite_app.system_app_name above
```

**BrainsuiteApp lookup to add** — in the same async DB session block (scoring_job.py ~line 183-215):
```python
async with get_session_factory()() as db:
    config_result = await db.execute(
        select(OrgBrainsuiteConfig).where(
            OrgBrainsuiteConfig.organization_id == asset.organization_id
        )
    )
    org_config = config_result.scalar_one_or_none()

    # Phase 12: resolve BrainsuiteApp row to get system_app_name
    brainsuite_app = None
    if asset.brainsuite_app_id:  # from connection
        brainsuite_app = await db.get(BrainsuiteApp, asset.brainsuite_app_id)
```

---

### `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts` (component — modify)

**Primary analog:** self (existing `BrainsuiteAppsComponent`)
**Dialog analog:** `organization.component.ts` (`ChangeRoleDialogComponent` pattern)

**Import additions** — to existing import block (lines 1-11):
```typescript
import { MatDialogModule, MatDialog, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
// Inject MAT_DIALOG_DATA is already used in organization.component.ts line 9
```

**Existing component structure to preserve** (lines 237-321):
```typescript
export class BrainsuiteAppsComponent implements OnInit {
  apps: BrainsuiteApp[] = [];
  loading = true;
  saving = false;
  showForm = false;
  editingApp: BrainsuiteApp | null = null;
  appForm?: FormGroup;

  constructor(
    private api: ApiService,
    private fb: FormBuilder,
    private snackBar: MatSnackBar,
  ) {}
```

**New state to add to component class** (insert after existing state, before constructor):
```typescript
// Credentials section state
credentials: { client_id: string | null; has_secret: boolean } | null = null;
credentialsForm?: FormGroup;
credentialsCollapsed = false;
secretEditMode = false;
savingCredentials = false;
testingConnection = false;
testResult: { success: boolean; message: string } | null = null;

// Accordion state
expandedAppId: string | null = null;
appNameForms: Record<string, FormGroup> = {};
savingAppName: Record<string, boolean> = {};
```

**MatDialog open pattern** (organization.component.ts lines 527-541):
```typescript
changeRole(user: OrgUser): void {
  const ref = this.dialog.open(ChangeRoleDialogComponent, {
    data: { email: user.email, currentRole: user.role, roles: ROLES },
    width: '320px',
  });
  ref.afterClosed().subscribe((newRole: string) => {
    if (newRole && newRole !== user.role) {
      this.api.patch(`/users/${user.id}/role`, { role: newRole }).subscribe({
        next: () => {
          user.role = newRole;
          this.snackBar.open('Role updated', '', { duration: 2000 });
        },
      });
    }
  });
}
```

**Inline dialog component pattern** (organization.component.ts lines 16-93):
```typescript
@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, MatButtonModule, MatRadioModule, MatDialogModule],
  template: `
    <div class="role-dialog">
      <h3>Change Role</h3>
      ...
      <div class="role-actions">
        <button mat-button (click)="dialogRef.close()">Cancel</button>
        <button mat-flat-button class="save-btn" [disabled]="..." (click)="dialogRef.close(selectedRole)">Save</button>
      </div>
    </div>
  `,
  styles: [`
    .role-dialog { padding: 8px 4px; min-width: 260px; }
    ...
    .role-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
    .save-btn { background: var(--accent) !important; color: white !important; }
  `],
})
export class ChangeRoleDialogComponent {
  constructor(
    public dialogRef: MatDialogRef<ChangeRoleDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { ... },
  ) {}
}
```

**config-section card pattern** (brainsuite-apps.component.ts lines 31-76):
```html
<section class="config-section">
  <div class="section-header">
    <div>
      <h2>Section Title</h2>
      <p>Subtitle text</p>
    </div>
    <!-- optional right-side button -->
  </div>
  <div class="section-body">
    <!-- content -->
  </div>
</section>
```

**MatProgressSpinner inline in save button** (brainsuite-apps.component.ts lines 121-124):
```html
<button mat-flat-button type="submit" class="save-btn" [disabled]="appForm!.invalid || saving">
  <mat-spinner *ngIf="saving" diameter="16"></mat-spinner>
  {{ saving ? 'Saving...' : 'Save' }}
</button>
```

**api-note div** (brainsuite-apps.component.ts lines 112-118):
```html
<div class="api-note">
  <i class="bi bi-info-circle"></i>
  <div>
    <p><strong>Note:</strong> ...</p>
  </div>
</div>
```

**snackBar feedback pattern** (brainsuite-apps.component.ts line 301):
```typescript
this.snackBar.open('App updated', '', { duration: 2000 });
// Duration 3000 for more important messages (see organization.component.ts line 479)
```

**api.get / api.patch call pattern** (brainsuite-apps.component.ts lines 255-259, 291-294):
```typescript
this.api.get<BrainsuiteApp[]>('/platforms/brainsuite-apps').subscribe({
  next: (apps) => { this.apps = apps; this.loading = false; },
  error: () => { this.loading = false; },
});

this.api.patch(`/platforms/brainsuite-apps/${this.editingApp.id}`, payload)
```

---

## Shared Patterns

### encrypt_token / decrypt_token
**Source:** `backend/app/core/security.py` lines 28-33
**Apply to:** `brainsuite_config.py` endpoint — PUT credentials (encrypt) and test-connection (decrypt)
```python
def encrypt_token(token: str) -> str:
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    return fernet.decrypt(encrypted_token.encode()).decode()
```

### Admin-only guard
**Source:** `backend/app/api/v1/endpoints/platforms.py` lines 55-58
**Apply to:** All endpoints in `brainsuite_config.py` (credentials write, test-connection, system-app-name write, rescore-all)
```python
current_user: User = Depends(get_current_admin)
```
Note: GET credentials uses `get_current_admin` too (not `get_current_user`) — credentials are admin-only.

### Org-scoped query with 404 guard
**Source:** `backend/app/api/v1/endpoints/platforms.py` lines 77-80
**Apply to:** `PATCH /apps/{app_id}/system-app-name`
```python
app = await db.get(BrainsuiteApp, app_id)
if not app or app.organization_id != current_user.organization_id:
    raise HTTPException(status_code=404, detail="App not found")
```

### datetime.now(timezone.utc) — NOT datetime.utcnow()
**Source:** `backend/app/models/brainsuite_config.py` lines 32-38
**Apply to:** All `created_at` / `updated_at` assignments in new endpoint code
```python
from datetime import datetime, timezone
created_at=datetime.now(timezone.utc)   # correct
# NOT: datetime.utcnow()  — deprecated pattern (WR-02 fix in Phase 11)
```

### CSS variables and section styles
**Source:** `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts` lines 152-235
**Apply to:** New credentials section card and accordion panel styles in same component
```typescript
// Reuse verbatim:
.config-section { background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
.section-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 20px 24px; border-bottom: 1px solid var(--border); }
.section-body { padding: 24px; }
.save-btn { background: var(--accent) !important; color: white !important; display: flex; align-items: center; gap: 8px; }
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| *(none)* | — | — | All files have direct analogs in the codebase |

The accordion expand pattern (`expandedAppId: string | null`) is new to the frontend but is a well-understood Angular state pattern. The RESEARCH.md pattern 4 provides the exact implementation design.

---

## Metadata

**Analog search scope:** `backend/app/api/v1/endpoints/`, `backend/app/schemas/`, `backend/app/models/`, `backend/alembic/versions/`, `backend/app/core/`, `backend/app/services/`, `frontend/src/app/features/configuration/pages/`
**Files scanned:** 12 source files read directly
**Pattern extraction date:** 2026-04-16
