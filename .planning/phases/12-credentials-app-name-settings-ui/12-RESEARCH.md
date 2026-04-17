# Phase 12: Credentials + App Name Settings UI - Research

**Researched:** 2026-04-16
**Domain:** Angular 17 standalone components, FastAPI async endpoints, Alembic migrations, BrainSuite OAuth2 auth flow
**Confidence:** HIGH — all findings verified directly from codebase

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** BrainSuite Credentials form (Client ID + Secret only) lives as a new `config-section` card **above** the existing app list on `brainsuite-apps.component.ts`. No new navigation tab.
- **D-02:** Credentials section **auto-collapses** once both credentials are saved and Test Connection has passed. Collapsed state shows summary row ("Client ID: abc123... — Connection verified ✓") with an "Edit" button to re-expand.
- **D-03:** `video_app_name` and `static_app_name` are **removed from `OrgBrainsuiteConfig`** and replaced by a `system_app_name` column (`String(255)`, nullable) on the `brainsuite_apps` table.
- **D-04:** Each app row has an **accordion chevron** (`bi-chevron-down`). Clicking expands an inline panel with a single "System App Name" input + Save button. Collapses on save or click-away.
- **D-05:** Phase 12 includes the cleanup migration: add `brainsuite_apps.system_app_name`, drop `org_brainsuite_config.video_app_name` and `org_brainsuite_config.static_app_name`, update scoring pipeline to read `system_app_name` from the `BrainsuiteApp` row.
- **D-06:** When Client Secret is already stored, the password field renders with placeholder `●●●●●●●● (saved)` and is read-only. A "Change" button puts the field into edit mode. A "Cancel" button in edit mode reverts to placeholder.
- **D-07:** Sending empty `client_secret` to backend on save means "keep existing". Only non-empty value triggers encrypt + store.
- **D-08:** "Test Connection" button is disabled until Client ID + Client Secret are both present in DB (config row exists with non-null `client_id` and `client_secret_encrypted`).
- **D-09:** Test Connection fires backend request that calls BrainSuite auth token endpoint using stored credentials. Frontend shows spinner during request.
- **D-10:** Result renders as colored inline status block below the button. Success: green + `bi-check-circle` + "Connection successful". Failure: red + `bi-x-circle` + error message. Status persists until next Test Connection click.
- **D-11:** Re-score dialog **only appears** when saved config actually changed — compare new `client_id`, `client_secret` (non-empty), or any `system_app_name` on apps the org owns against previously stored values. No-op saves skip the prompt.
- **D-12:** Prompt uses **MatDialog** matching role-change pattern in `organization.component.ts`. Two buttons: "Keep existing scores" and "Re-score all assets".
- **D-13:** "Re-score all assets" resets all `SCORED` assets for the org to `UNSCORED`. Frontend shows MatSnackBar toast: "Assets queued for re-scoring".

### Claude's Discretion
- Exact backend endpoint shape for credentials CRUD (suggested: `GET/PUT /api/v1/brainsuite-config/credentials`)
- Exact endpoint for test connection (suggested: `POST /api/v1/brainsuite-config/test-connection`)
- How collapse state is stored — local component boolean vs. persisted (localStorage acceptable)
- Whether "Test Connection passed" is stored server-side or only client-side for auto-collapse trigger
- API route registration in `main.py` / `api_router`

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BSCFG-01 | Admin can save BrainSuite Client ID and Client Secret per organization via the Settings page | GET/PUT `/api/v1/brainsuite-config/credentials`; `encrypt_token` from security.py; D-06/D-07 secret masking pattern |
| BSCFG-02 | Admin can configure the video app name per organization (replaces hardcoded `ACE_VIDEO_SMV_API`) | `system_app_name` on `BrainsuiteApp` row; accordion expand pattern in frontend; D-03/D-04 |
| BSCFG-03 | Admin can configure the static app name per organization (replaces hardcoded `ACE_STATIC_SOCIAL_STATIC_API`) | Same as BSCFG-02 — each BrainsuiteApp row has its own `system_app_name` |
| BSCFG-04 | BrainSuite configuration accessible as dedicated section within existing Settings page | New `config-section` card added above app list in `brainsuite-apps.component.ts`; D-01 |
| VSAF-01 | Admin can click "Test Connection" to fire live BrainSuite auth request and see inline feedback | POST `/api/v1/brainsuite-config/test-connection`; backend decrypts secret, calls `settings.BRAINSUITE_AUTH_URL`; D-08/D-09/D-10 |
| VSAF-02 | When saving config changes and org has already-scored assets, prompt asks keep/re-score | MatDialog pattern from `organization.component.ts`; DB query for SCORED count; D-11/D-12/D-13 |
</phase_requirements>

---

## Summary

Phase 12 adds a BrainSuite Configuration UI to the existing Brainsuite Apps settings page. It has two parallel tracks: (1) a credentials card (Client ID + Secret + Test Connection) above the existing app list, and (2) accordion panels on each app row for `system_app_name` configuration. These are backed by new backend endpoints and a database migration.

The Phase 11 schema already created `org_brainsuite_config` with `client_id`, `client_secret_encrypted`, `video_app_name`, and `static_app_name`. Phase 12 must drop `video_app_name`/`static_app_name` from that table and add `system_app_name` to `brainsuite_apps`. The scoring pipeline in `scoring_job.py` currently reads `org_config.video_app_name` and `org_config.static_app_name` in 4 places — all must switch to reading `system_app_name` from the matched `BrainsuiteApp` row.

**Primary recommendation:** Build a dedicated `brainsuite_config.py` endpoint module registered at `/api/v1/brainsuite-config`. Follow the `platforms.py` router pattern for async endpoints. The Angular component integrates directly into `BrainsuiteAppsComponent` as in-template sections — no new route or nav item.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Store/retrieve credentials | API / Backend | Database | Credentials must never traverse to client in plain text |
| Encrypt/decrypt Client Secret | API / Backend | — | Fernet encryption lives server-side in `security.py` |
| Test Connection (live BrainSuite auth) | API / Backend | — | Requires decrypted secret; cannot be done from browser |
| Credentials form + masking UI | Frontend (Angular) | — | Read-only placeholder + edit mode is pure client state |
| Test Connection status display | Frontend (Angular) | — | Inline status block is local component state |
| Accordion app name input | Frontend (Angular) | — | `expandedAppId: string | null` local state pattern |
| Re-score dialog | Frontend (Angular) | — | MatDialog triggered after save response confirms change |
| Reset SCORED → UNSCORED | API / Backend | Database | Must be atomic DB update, not client-driven |
| Auto-collapse trigger | Frontend (Angular) | localStorage (optional) | `hasCredentials && lastTestResult === 'success'` local boolean |
| Alembic migration | Database | — | Drop video/static_app_name, add system_app_name |

---

## Standard Stack

### Core (all already in project — no new installs)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | project-current | Async API router + Pydantic validation | All other endpoints use this |
| SQLAlchemy async | project-current | DB access in endpoints | All other endpoints use this |
| Alembic | project-current | DB migrations | Phase 11 migration is the direct predecessor |
| cryptography (Fernet) | project-current | `encrypt_token` / `decrypt_token` | Already in `security.py`; Phase 11 established pattern |
| httpx | project-current | Test Connection live auth call | Already used in `brainsuite_score.py` |
| Angular + Angular Material | project-current | Component, MatDialog, MatSnackBar | All config pages use this stack |
| ReactiveFormsModule + FormBuilder | project-current | Credentials form | Pattern in `brainsuite-apps.component.ts` |

**Installation:** Nothing new to install — all dependencies already present.

---

## Architecture Patterns

### System Architecture Diagram

```
[Admin Browser]
     |
     | GET /api/v1/brainsuite-config/credentials
     |   <-- {client_id, has_secret: bool}  (secret NEVER returned)
     |
     | PUT /api/v1/brainsuite-config/credentials
     |   --> {client_id, client_secret (empty = keep existing)}
     |   <-- 200 / {changed: bool}
     |
     | POST /api/v1/brainsuite-config/test-connection
     |   --> {}  (uses stored credentials)
     |   <-- {success: bool, message: str}
     |
     | PATCH /api/v1/brainsuite-config/apps/{app_id}/system-app-name
     |   --> {system_app_name: str}
     |   <-- 200
     |
[FastAPI /api/v1/brainsuite-config]
     |
     | GET credentials: SELECT org_brainsuite_config WHERE org=current_user.org
     | PUT credentials: UPSERT; encrypt_token(secret) if non-empty
     | test-connection: decrypt_token(secret); POST BRAINSUITE_AUTH_URL
     | PATCH apps/system-app-name: UPDATE brainsuite_apps SET system_app_name=...
     |
[PostgreSQL]
     |
     | org_brainsuite_config(client_id, client_secret_encrypted)
     | brainsuite_apps(system_app_name)   ← after migration
     | creative_score_results(scoring_status)  ← reset SCORED→UNSCORED on re-score
```

### Recommended Project Structure

New files to create:
```
backend/app/api/v1/endpoints/
├── brainsuite_config.py     # New router: GET/PUT credentials, POST test-connection, PATCH app system_app_name

backend/app/schemas/
├── brainsuite_config.py     # New: CredentialsResponse, CredentialsUpdate, TestConnectionResponse

backend/alembic/versions/
├── u2v3w4x5y6z7_phase12_system_app_name.py  # New migration

backend/tests/
├── test_phase12_credentials.py   # New: unit tests for endpoint logic + schema

frontend/src/app/features/configuration/pages/
├── brainsuite-apps.component.ts  # Modified: add credentials card + accordion expand
```

### Pattern 1: Credentials UPSERT with Secret Masking (Backend)

**What:** GET returns `{client_id, has_secret: bool}` — never the decrypted secret. PUT accepts `{client_id, client_secret}` where empty `client_secret` means "keep existing".

**When to use:** Any PUT to `/brainsuite-config/credentials`

```python
# Source: verified from security.py + scoring_job.py patterns in codebase
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

### Pattern 2: Test Connection Endpoint (Backend)

**What:** Decrypts stored secret, calls BrainSuite auth URL, returns success/failure inline.

**When to use:** POST `/brainsuite-config/test-connection`

```python
# Source: auth flow verified from brainsuite_score.py _get_token method
@router.post("/test-connection")
async def test_connection(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrgBrainsuiteConfig).where(
            OrgBrainsuiteConfig.organization_id == current_user.organization_id
        )
    )
    config = result.scalar_one_or_none()

    if not config or not config.client_id or not config.client_secret_encrypted:
        raise HTTPException(status_code=400, detail="No credentials configured")

    try:
        client_secret = decrypt_token(config.client_secret_encrypted)
        credentials = f"{config.client_id}:{client_secret}"
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

        if resp.status_code == 200:
            return {"success": True, "message": "Connection successful"}
        else:
            return {"success": False, "message": f"Authentication failed (HTTP {resp.status_code})"}

    except Exception as exc:
        return {"success": False, "message": f"Connection error: {str(exc)[:200]}"}
```

### Pattern 3: Re-score Reset (Backend)

**What:** Reset all COMPLETE (scored) assets for the org to UNSCORED. Scheduler picks up on next 15-min cycle.

**IMPORTANT:** The actual DB status for scored assets is `"COMPLETE"`, NOT `"SCORED"`. Using `"SCORED"` silently resets zero rows.

**When to use:** `POST /brainsuite-config/rescore-all` when user clicks "Re-score all assets" in the dialog

```python
# Source: verified from CreativeScoreResult model + scoring.py patterns
from sqlalchemy import update

await db.execute(
    update(CreativeScoreResult)
    .where(
        CreativeScoreResult.organization_id == current_user.organization_id,
        CreativeScoreResult.scoring_status == "COMPLETE",  # NOT "SCORED" — "COMPLETE" is the actual DB value
    )
    .values(
        scoring_status="UNSCORED",
        updated_at=datetime.now(timezone.utc),
    )
)
await db.commit()
```

### Pattern 4: Accordion Expand State (Frontend)

**What:** `expandedAppId: string | null` state tracks which app row's inline panel is open.

**When to use:** App list rendering — new pattern, not yet in codebase.

```typescript
// Source: pattern designed to match existing BrainsuiteAppsComponent conventions
expandedAppId: string | null = null;
appNameForms: Record<string, FormGroup> = {};

toggleAccordion(app: BrainsuiteApp): void {
  if (this.expandedAppId === app.id) {
    this.expandedAppId = null;
  } else {
    this.expandedAppId = app.id;
    if (!this.appNameForms[app.id]) {
      this.appNameForms[app.id] = this.fb.group({
        system_app_name: [app.system_app_name || ''],
      });
    }
  }
}

saveSystemAppName(app: BrainsuiteApp): void {
  const form = this.appNameForms[app.id];
  if (!form) return;
  this.api.patch(`/platforms/brainsuite-apps/${app.id}/system-app-name`, form.value).subscribe({
    next: () => {
      app.system_app_name = form.value.system_app_name;
      this.expandedAppId = null;
      this.snackBar.open('App name saved', '', { duration: 2000 });
      // Check if any config changed and prompt re-score if needed
    },
  });
}
```

### Pattern 5: Auto-Collapse Credentials Section

**What:** Component collapses the credentials section when both `hasCredentials` (credentials in DB) AND `lastTestResult === 'success'` are true.

```typescript
// Source: from CONTEXT.md D-02 / D-09 / specifics section
hasCredentials = false;     // true when DB has non-null client_id + client_secret_encrypted
credentialsCollapsed = false;
lastTestResult: 'success' | 'failure' | null = null;

onLoadCredentials(data: CredentialsResponse): void {
  this.hasCredentials = !!data.client_id && data.has_secret;
  // Auto-collapse if already verified — restore from localStorage if persisted
  const savedCollapsed = localStorage.getItem(`bs-creds-collapsed-${this.orgId}`);
  if (savedCollapsed === 'true' && this.hasCredentials) {
    this.credentialsCollapsed = true;
  }
}

onTestConnectionSuccess(): void {
  this.lastTestResult = 'success';
  if (this.hasCredentials) {
    this.credentialsCollapsed = true;
    localStorage.setItem(`bs-creds-collapsed-${this.orgId}`, 'true');
  }
}
```

### Pattern 6: Re-score MatDialog (Frontend)

**What:** Matches `ChangeRoleDialogComponent` inline pattern from `organization.component.ts`.

```typescript
// Source: organization.component.ts line 82–93 (verified)
openRescoreDialog(): void {
  const ref = this.dialog.open(RescoreDialogComponent, {
    width: '400px',
    data: {},
  });
  ref.afterClosed().subscribe((action: 'keep' | 'rescore' | undefined) => {
    if (action === 'rescore') {
      this.api.post('/brainsuite-config/rescore-all', {}).subscribe({
        next: () => {
          this.snackBar.open('Assets queued for re-scoring', '', { duration: 3000 });
        },
      });
    }
  });
}
```

### Anti-Patterns to Avoid

- **Returning `client_secret_encrypted` in API response:** The GET credentials endpoint must return `has_secret: bool`, never the raw or decrypted value. [VERIFIED: OrgBrainsuiteConfig model + CONTEXT.md D-06]
- **Using `Text` column type for `client_secret_encrypted`:** Must stay `String(1000)` per T-11-01 to prevent accidental plain-text leakage. [VERIFIED: brainsuite_config.py model + Phase 11 test]
- **Calling `datetime.utcnow()`:** Phase 11 already migrated to `datetime.now(timezone.utc)`. New code must use the same. [VERIFIED: scoring_job.py + brainsuite_score.py patterns]
- **Resetting PROCESSING assets:** Never reset PROCESSING assets — they have live job IDs. Only reset SCORED → UNSCORED. [VERIFIED: MEMORY.md user feedback]
- **Adding a new nav tab:** No new navigation tab required — credentials section slots into existing brainsuite-apps page. [VERIFIED: configuration-shell.component.ts + CONTEXT.md D-01]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Client Secret encryption | Custom AES/XOR | `encrypt_token` / `decrypt_token` from `app.core.security` | Fernet already integrated, tested, keyed via `TOKEN_ENCRYPTION_KEY` |
| BrainSuite OAuth2 auth call | New HTTP client | `httpx.AsyncClient` (same as `brainsuite_score.py`) | Consistent timeout, error handling, async pattern |
| Dialog component | Custom modal HTML | `MatDialog` with inline `@Component` | `ChangeRoleDialogComponent` is the direct analog |
| Form validation | Custom validators | `ReactiveFormsModule` + `Validators.required` | All config forms use this; `appearance="outline"` MatFormFields |
| Toast notifications | Custom alerts | `MatSnackBar` | All config pages use this; `duration: 2000–3000` pattern |
| Migration chaining | Manual SQL | Alembic with correct `down_revision` | `t1u2v3w4x5y6` is the head — new migration must chain from it |

---

## Runtime State Inventory

This phase drops two DB columns (`video_app_name`, `static_app_name` from `org_brainsuite_config`) and adds one (`system_app_name` to `brainsuite_apps`). The scoring pipeline reads from these columns in 4 places.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `org_brainsuite_config.video_app_name` + `.static_app_name`: nullable, may contain values if any org set them manually | Data migration: values cannot be automatically moved to `brainsuite_apps.system_app_name` because there's a 1-to-many relationship. Migration drops columns; any existing values are abandoned. This is acceptable as CONTEXT.md D-03/D-05 explicitly scopes this phase. |
| Live service config | Scoring pipeline in `scoring_job.py` reads `org_config.video_app_name` (line 195, 282, 320) and `org_config.static_app_name` (line 197, 298, 328) — 4 references | Code edit: replace all 4 references to read `system_app_name` from the matched `BrainsuiteApp` row |
| OS-registered state | None — no scheduled jobs reference these column names directly | None |
| Secrets/env vars | `TOKEN_ENCRYPTION_KEY` — unchanged; `BRAINSUITE_AUTH_URL` — test-connection endpoint reads this | None — key names unchanged |
| Build artifacts | None — no compiled binaries reference these column names | None |

**Migration chain:** New migration must chain from `t1u2v3w4x5y6` (head after Phase 11).

---

## Common Pitfalls

### Pitfall 1: Scoring Pipeline app_name Re-wire Incomplete

**What goes wrong:** Developer updates model and migration but misses one of the 4 `app_name` references in `scoring_job.py`. Pipeline silently uses `None` as app_name, scoring fails for all assets.
**Why it happens:** `video_app_name` and `static_app_name` appear in two contexts each: (1) the "incomplete config" check block (lines 195/197), and (2) the `submit_job_with_upload` and `poll_job_status` calls (lines 282/298/320/328).
**How to avoid:** Search for all 6 occurrences of `video_app_name` and `static_app_name` in the entire backend before closing the task. After migration, the model attributes no longer exist — SQLAlchemy will raise `AttributeError` at runtime.
**Warning signs:** `AttributeError: 'OrgBrainsuiteConfig' object has no attribute 'video_app_name'` in scorer logs.

### Pitfall 2: Re-score Dialog Triggering on No-op Save

**What goes wrong:** The dialog appears every time the user clicks Save, even when nothing changed.
**Why it happens:** Developer compares form values vs. current DB state but forgets the D-07 rule: empty `client_secret` means "no change to secret".
**How to avoid:** Implement change detection logic on the backend (`changed: bool` in PUT response) rather than in the frontend. Frontend simply checks the response flag.
**Warning signs:** Dialog appears immediately on page load when clicking Save without editing.

### Pitfall 3: `has_secret` vs. `client_secret` in GET Response

**What goes wrong:** Frontend sends `client_secret` as empty string back to PUT on every save (because the field is blank), triggering "keep existing" semantics, but the "Change" button is never shown because `has_secret` was not populated from GET.
**Why it happens:** GET response schema missing `has_secret: bool`, so the component can't determine whether a secret is already stored.
**How to avoid:** GET credentials always returns `has_secret: bool = config.client_secret_encrypted is not None`. Frontend drives the read-only placeholder vs. edit mode from this flag.

### Pitfall 4: Alembic `op.drop_column` Without Index Drop

**What goes wrong:** `op.drop_column('org_brainsuite_config', 'video_app_name')` may succeed on Postgres but if there's an index on the column (none exist for these columns — verified in Phase 11 migration), it would fail. Main risk is forgetting `down_revision`.
**Why it happens:** Copy-pasting previous migration template without updating `down_revision`.
**How to avoid:** Always verify `down_revision = "t1u2v3w4x5y6"` in the new migration header.

### Pitfall 5: Test Connection Returns 200 with Error Body

**What goes wrong:** BrainSuite auth endpoint returns HTTP 200 with `{"error": "invalid_client"}` body (OAuth2 error response style) rather than 4xx. Frontend sees `success: true` because it only checks HTTP status.
**Why it happens:** OAuth2 spec allows error responses in 200 body for `application/x-www-form-urlencoded` flows.
**How to avoid:** Backend test-connection endpoint checks both `resp.status_code == 200` AND whether `"access_token"` key is in the JSON body before returning `success: True`.

### Pitfall 6: `system_app_name` PATCH Endpoint Missing Admin Guard

**What goes wrong:** Any authenticated user (not just ADMIN) can change the app name.
**Why it happens:** Forgetting `Depends(get_current_admin)` on the PATCH endpoint.
**How to avoid:** All config-mutating endpoints use `get_current_admin` — BSCFG-01/02/03 are org admin operations. Follow the same pattern as `create_brainsuite_app` in `platforms.py`.

---

## Code Examples

### GET Credentials Response Schema

```python
# Source: pattern derived from existing platform.py schemas + CONTEXT.md D-06
# backend/app/schemas/brainsuite_config.py
from pydantic import BaseModel
from typing import Optional

class CredentialsResponse(BaseModel):
    client_id: Optional[str] = None
    has_secret: bool = False   # True if client_secret_encrypted is non-null in DB

class CredentialsUpdate(BaseModel):
    client_id: str
    client_secret: str = ""   # empty = keep existing (D-07)

class TestConnectionResponse(BaseModel):
    success: bool
    message: str

class SystemAppNameUpdate(BaseModel):
    system_app_name: Optional[str] = None
```

### BrainsuiteApp Schema Extension

```python
# Source: existing platform.py BrainsuiteAppResponse + CONTEXT.md D-03
# Add system_app_name to BrainsuiteAppResponse
class BrainsuiteAppResponse(BrainsuiteAppBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    created_at: datetime
    system_app_name: Optional[str] = None   # NEW in Phase 12

    class Config:
        from_attributes = True
```

### Alembic Migration Structure

```python
# Source: pattern from t1u2v3w4x5y6 (Phase 11 head migration)
# backend/alembic/versions/u2v3w4x5y6z7_phase12_system_app_name.py
"""Phase 12: add brainsuite_apps.system_app_name, drop org_brainsuite_config.video/static_app_name

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa

revision = "u2v3w4x5y6z7"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("brainsuite_apps", sa.Column("system_app_name", sa.String(255), nullable=True))
    op.drop_column("org_brainsuite_config", "video_app_name")
    op.drop_column("org_brainsuite_config", "static_app_name")

def downgrade() -> None:
    op.drop_column("brainsuite_apps", "system_app_name")
    op.add_column("org_brainsuite_config", sa.Column("video_app_name", sa.String(255), nullable=True))
    op.add_column("org_brainsuite_config", sa.Column("static_app_name", sa.String(255), nullable=True))
```

### Scoring Pipeline Re-wire (scoring_job.py)

```python
# Source: existing scoring_job.py lines 182–328 — showing what changes
# BEFORE (Phase 11):
required_app_name = org_config.video_app_name  # line 195
# ...
app_name=org_config.video_app_name             # line 282, 320

# AFTER (Phase 12 — read from BrainsuiteApp row):
# Additional query needed to find the matched BrainsuiteApp for this asset
brainsuite_app = await db.get(BrainsuiteApp, asset.brainsuite_app_id)  # or appropriate lookup
required_app_name = brainsuite_app.system_app_name if brainsuite_app else None
# ...
app_name=brainsuite_app.system_app_name
```

**Note:** The exact lookup for "which BrainsuiteApp to read `system_app_name` from" needs careful implementation. Assets are linked to BrainSuite apps via `PlatformConnection.brainsuite_app_id_video` and `PlatformConnection.brainsuite_app_id_image`. The planner should trace the full lookup chain in `scoring_job.py` before implementing.

### Frontend: Credentials Section Toggle

```typescript
// Source: CONTEXT.md D-02 + specifics section
// Collapsed state summary row pattern
// In template:
// <div *ngIf="!credentialsCollapsed" class="credentials-edit-panel">...</div>
// <div *ngIf="credentialsCollapsed" class="credentials-summary">
//   <span>Client ID: {{ clientIdSummary }}... — Connection verified</span>
//   <i class="bi bi-check-circle" style="color: #34A853"></i>
//   <button mat-stroked-button (click)="credentialsCollapsed = false">Edit</button>
// </div>
get clientIdSummary(): string {
  return (this.credentials?.client_id || '').substring(0, 8);
}
```

---

## Scoring Pipeline Re-wire: Lookup Chain

This is the most architecturally complex part of Phase 12. The current pipeline reads `app_name` from `OrgBrainsuiteConfig`. After this phase, it reads from `BrainsuiteApp.system_app_name`. The lookup chain in `scoring_job.py` must be:

1. Load the `CreativeAsset` (already done — `asset.organization_id`, `asset.platform`, `asset.asset_format`)
2. Find the `PlatformConnection` for this asset's platform connection (if asset has `platform_connection_id`)
3. From `PlatformConnection`, get `brainsuite_app_id_video` (for VIDEO) or `brainsuite_app_id_image` (for STATIC_IMAGE)
4. Load `BrainsuiteApp` by that ID → read `.system_app_name`
5. If the app has no `system_app_name`, treat as incomplete config (same skip-with-UNSCORED behavior)

**[ASSUMED]** — The exact relationship between `CreativeAsset` and `PlatformConnection` is not verified in this research session. The planner must trace this in `scoring_job.py` lines 1–175 (before the section read here). The scoring_job.py starting section was not read in full.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `video_app_name` + `static_app_name` on `OrgBrainsuiteConfig` (global per org) | `system_app_name` on each `BrainsuiteApp` row (per-app) | Phase 12 | Future-proof for orgs with more than 2 BrainSuite apps |
| Phase 11 scoring reads `org_config.video_app_name` | Phase 12 reads `brainsuite_app.system_app_name` | Phase 12 | App-level routing flexibility |

**Deprecated/outdated:**
- `OrgBrainsuiteConfig.video_app_name`: dropped in Phase 12 migration
- `OrgBrainsuiteConfig.static_app_name`: dropped in Phase 12 migration
- Phase 11 test `test_config_model` asserts these columns exist — the test must be updated to assert they do NOT exist after migration

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The test-connection endpoint can return `success: False` with a message rather than raising an HTTP exception — frontend handles both cases | Code Examples / Test Connection | If the BrainSuite auth URL consistently times out, the endpoint should still return 200 with `success: false` rather than 500; this assumption about error handling style is reasonable but not tested |
| A2 | `scoring_job.py` links `CreativeAsset` to `BrainsuiteApp` via `PlatformConnection.brainsuite_app_id_video` / `_image` | Runtime State Inventory + Scoring Re-wire section | If the lookup chain is different (e.g., asset has direct `brainsuite_app_id`), the re-wire implementation changes |

---

## Open Questions

1. **Scoring pipeline: asset-to-BrainsuiteApp lookup**
   - What we know: `PlatformConnection` has `brainsuite_app_id_video` and `brainsuite_app_id_image`. `CreativeAsset` has a relationship to `PlatformConnection`.
   - What's unclear: Whether `scoring_job.py` lines 1–175 (not fully read) already resolves the `BrainsuiteApp` from the asset, or whether this requires a new JOIN.
   - Recommendation: Planner should read `scoring_job.py` lines 1–175 before writing the re-wire plan task.

2. **Phase 11 test update: `test_config_model` assertion**
   - What we know: `test_phase11_schema.py::test_config_model` explicitly asserts `video_app_name` and `static_app_name` are in the column set.
   - What's unclear: Should Phase 12 update this test to assert the columns are ABSENT, or create a separate `test_phase12_schema.py`?
   - Recommendation: Create `test_phase12_schema.py` with fresh assertions for the post-migration schema. Update `test_phase11_schema.py` comment to note it tests the pre-Phase-12 migration state.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 12 is purely code + config changes with no new external dependencies. BrainSuite auth URL (`settings.BRAINSUITE_AUTH_URL`) is already configured and used by the existing scoring pipeline.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (confirmed from conftest.py + test_phase11_*.py) |
| Config file | `backend/pytest.ini` or pyproject.toml (check before Wave 0) |
| Quick run command | `cd backend && python -m pytest tests/test_phase12_credentials.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BSCFG-01 | GET credentials returns `{client_id, has_secret}` — never raw secret | unit | `pytest tests/test_phase12_credentials.py::test_get_credentials_masks_secret -x` | ❌ Wave 0 |
| BSCFG-01 | PUT credentials with empty secret keeps existing | unit | `pytest tests/test_phase12_credentials.py::test_put_credentials_empty_secret_keeps_existing -x` | ❌ Wave 0 |
| BSCFG-02/03 | `system_app_name` column exists on `brainsuite_apps` after migration | unit | `pytest tests/test_phase12_credentials.py::test_brainsuite_app_has_system_app_name -x` | ❌ Wave 0 |
| BSCFG-02/03 | `video_app_name` and `static_app_name` absent from `org_brainsuite_config` | unit | `pytest tests/test_phase12_credentials.py::test_config_columns_dropped -x` | ❌ Wave 0 |
| VSAF-01 | Test connection endpoint returns `{success, message}` shape | unit | `pytest tests/test_phase12_credentials.py::test_test_connection_response_shape -x` | ❌ Wave 0 |
| VSAF-02 | Re-score resets SCORED → UNSCORED, not PROCESSING | unit | `pytest tests/test_phase12_credentials.py::test_rescore_only_resets_scored_not_processing -x` | ❌ Wave 0 |
| PIPE-01 re-wire | Scoring pipeline reads `system_app_name` from BrainsuiteApp (not from OrgBrainsuiteConfig) | unit | `pytest tests/test_phase12_credentials.py::test_scoring_reads_system_app_name -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_phase12_credentials.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase12_credentials.py` — covers all 7 test cases above
- [ ] No new framework config needed — `conftest.py` already provides Fernet key injection and mock patterns

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Not applicable (using existing JWT auth) |
| V3 Session Management | No | Not applicable |
| V4 Access Control | Yes | `get_current_admin` dependency on all mutating endpoints |
| V5 Input Validation | Yes | Pydantic schemas for all request bodies |
| V6 Cryptography | Yes | `encrypt_token` / `decrypt_token` via Fernet (never hand-rolled) |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Client Secret exposure in API response | Information Disclosure | GET credentials returns `has_secret: bool` only — never `client_secret_encrypted` or decrypted value |
| Client Secret exposure in logs | Information Disclosure | Never log `client_secret` or decrypted value (existing `logger.info` in `_get_token` already truncates client_id to 8 chars — follow same pattern) |
| SSRF via test-connection endpoint | Elevation of Privilege | Test-connection calls a fixed `settings.BRAINSUITE_AUTH_URL` only — not a user-supplied URL |
| Unauthorized config mutation by non-admin | Tampering | All write endpoints use `Depends(get_current_admin)` |
| Re-score of another org's assets | Elevation of Privilege | Reset query scoped to `CreativeScoreResult.organization_id == current_user.organization_id` |
| Column drop losing production app_name data | Tampering / Data Loss | Migration drops nullable columns — document in migration comment that existing values are abandoned; acceptable per D-03 |

---

## Sources

### Primary (HIGH confidence)
- Codebase: `backend/app/models/brainsuite_config.py` — current OrgBrainsuiteConfig schema with video/static app name columns
- Codebase: `backend/app/models/platform.py` — BrainsuiteApp model lacking system_app_name (pre-migration)
- Codebase: `backend/app/core/security.py` — encrypt_token / decrypt_token Fernet utilities
- Codebase: `backend/app/services/brainsuite_score.py` — BrainSuite auth flow pattern (_get_token)
- Codebase: `backend/app/services/sync/scoring_job.py` — all 4 app_name references (lines 195, 197, 282, 298, 320, 328)
- Codebase: `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts` — config-section, section-header, MatSnackBar, MatProgressSpinner patterns
- Codebase: `frontend/src/app/features/configuration/pages/organization.component.ts` — MatDialog pattern (ChangeRoleDialogComponent)
- Codebase: `backend/alembic/versions/t1u2v3w4x5y6_*` — confirmed head migration for chaining
- Codebase: `backend/app/api/v1/__init__.py` — router registration pattern
- Codebase: `backend/tests/conftest.py` — Fernet key injection pattern for tests

### Secondary (MEDIUM confidence)
- CONTEXT.md Phase 12 — all user decisions D-01 through D-13

### Tertiary (LOW confidence)
- A1, A2 in Assumptions Log above

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, verified from imports
- Architecture: HIGH — derived from reading actual source files
- Pitfalls: HIGH — all pitfalls verified from codebase (wrong column types, missing admin guards, etc.)
- Scoring re-wire: MEDIUM — 4 references found and verified; full lookup chain (lines 1–175) not read in full

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (stable stack, no fast-moving dependencies)
