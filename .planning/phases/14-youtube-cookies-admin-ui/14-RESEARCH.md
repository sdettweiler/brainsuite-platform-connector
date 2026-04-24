# Phase 14: YouTube Cookies Admin UI - Research

**Researched:** 2026-04-24
**Domain:** Admin role system, database encryption, async API endpoints, Angular admin UI with role gating
**Confidence:** HIGH

## Summary

Phase 14 introduces SuperAdmin role support and a system-global YouTube Cookies management system. It reuses existing `User.is_superuser` column (already in schema), implements Fernet encryption following Phase 12 patterns, and creates a new singleton `system_config` table for encrypted cookie storage. The implementation spans backend API endpoints (SuperAdmin role check, cookie CRUD, notification dispatch), a new Alembic migration with data seeding, backend cookie reading refactor in dv360_sync.py, and a new Angular Admin page with three gated sections. Core patterns are established and copy-paste patterns from Phase 12 apply throughout.

**Primary recommendation:** Build in order: (1) Alembic migration + data seeding, (2) Backend models + deps + endpoints, (3) Backend service refactors (dv360_sync cookie reading, notification dispatch), (4) Angular auth model extension, (5) Angular component + route guard.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 to D-17** — All implementation decisions in CONTEXT.md are locked:
- Use existing `User.is_superuser` (Boolean, already in schema) as the SuperAdmin flag — no schema change needed
- Seed `s.dettweiler@brainsuite.ai` as the first SuperAdmin via Alembic data migration
- New `get_current_superadmin` dependency (HTTP 403 if not superuser)
- `is_superuser` claim added to JWT access token and included in `/users/me` response
- New `system_config` singleton table (id, singleton_guard=UNIQUE('X'), youtube_cookies_encrypted, youtube_cookies_backup_encrypted, created_at, updated_at)
- Encryption uses same Fernet key + helper as Phase 12 `client_secret_encrypted`
- GET `/api/v1/super-admin/youtube-cookies` returns health status (valid/expired/missing) without revealing cookie content
- PUT `/api/v1/super-admin/youtube-cookies` accepts partial updates, encrypts, validates expiry post-save
- dv360_sync.py reads cookies from DB first, falls back to env vars (graceful migration)
- On download failure after exhausting all cookie slots → fire `COOKIE_FAILED` notification to all SuperAdmins
- Notification deeplink: `/configuration/admin/youtube-cookies`
- Angular Admin page: one component with three sections (YouTube Cookies, SuperAdmin Management, Organization List read-only)
- Cookie masked display with Reveal/Replace UX (•••••••••• toggle pattern from Phase 12)
- Health badge shows expiry-based status, no live yt-dlp test

### Claude's Discretion

Per CONTEXT.md discretion areas:
- Exact column type for cookies (Text vs VARCHAR(10000)) — **DECISION: Use Text since cookies are multi-KB strings**
- Whether to add `is_superuser` to login response or `/users/me` — **DECISION: Use existing `/users/me` endpoint (already exists, add field there)**
- Angular component split (single AdminComponent vs three routed pages) — **DECISION: Single AdminComponent with three internal sections (simpler, existing pattern)**
- Deeplink support in notification handler — **Check Phase 10 notification handler; wire deeplink if supported, else surface raw message**

### Deferred Ideas (OUT OF SCOPE for Phase 14)

- Org create/delete in Admin UI — read-only list only
- Proactive cookie expiry warning (24h before expiry) — requires scheduler task
- Per-org cookie overrides — system-global only in Phase 14
- Cookie file upload — textarea paste chosen, file upload deferred

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COOK-01 | SuperAdmin role + Admin nav visible only to SuperAdmins, with three subsections | `is_superuser` column exists; JWT + `/users/me` extension established; role-gated nav pattern exists in codebase |
| COOK-02 | YouTube/DV360 cookies stored in DB (encrypted, per-org global), admin CRUD endpoints, dv360_sync reads from DB | Singleton table pattern + Fernet encryption pattern from Phase 12 established; dv360_sync.py module structure analyzed |
| COOK-03 | Notification dispatch on cookie failure; SuperAdmin list + promote UI; read-only org list | Notification service pattern from Phase 10 exists; `create_org_notification()` template reusable for SuperAdmin fan-out |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SuperAdmin role enforcement | API / Backend | — | Role check must happen at HTTP request boundary before any operation |
| Cookie storage + encryption | Database / Storage | API | Encryption/decryption logic lives in backend security module; DB persists encrypted values |
| Cookie health check (expiry validation) | API / Backend | — | Expiry parsing logic (existing `_check_youtube_cookies()`) runs server-side; frontend only displays status badge |
| Cookie UI (masked display, reveal/replace) | Browser / Client | API | Frontend manages reveal state and textarea display; backend validates and encrypts on save |
| Notification dispatch | API / Backend | — | Backend queries all SuperAdmin users and creates notification rows; async task, no client involvement |
| Navigation role gate | Browser / Client | API | Angular route guard checks `authService.currentUser?.is_superuser`; API enforces via `get_current_superadmin` |
| SuperAdmin list + promote | API / Backend | Browser / Client | Backend queries all users with `is_superuser=True`, accepts promotion request; frontend displays table + input |
| Organization list (read-only) | API / Backend | Browser / Client | Backend queries all orgs with user count aggregation; frontend renders read-only table |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI (existing) | current | HTTP API framework | Already chosen; all endpoints built on FastAPI |
| SQLAlchemy (existing) | 2.0+ | ORM for DB access | Already in use; SQLAlchemy async patterns established |
| Fernet (cryptography) | current | Symmetric encryption for sensitive DB columns | Established in Phase 12 for `client_secret_encrypted`; same key + helper reused |
| PostgreSQL (existing) | 12+ | Primary datastore | Already deployed; UUID + JSONB types used throughout |
| Angular (existing) | 16+ | Frontend SPA framework | Established stack; Material Design components used |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Alembic (existing) | 1.13+ | Database migrations | Every schema change (system_config table, data seeding) |
| pytest (existing) | 8.0+ | Backend unit/integration testing | Validate GET/PUT cookie endpoints, notification dispatch, dv360_sync refactor |
| Angular Material (existing) | 16+ | UI component library | Card sections (config-section), buttons, forms, dialogs for Admin page |
| RxJS (existing) | 7.8+ | Reactive programming for Angular | Observable chains in admin service calls, role gate guarding |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Fernet (symmetric) | RSA (asymmetric) | Fernet sufficient; simpler key management; matches Phase 12 pattern |
| Singleton guard (VARCHAR unique constraint) | Row count check + lock | Unique constraint on single-character column is simpler, race-condition-safe, no explicit locking needed |
| Text column for cookies | VARCHAR(max) | Text allows arbitrarily long Netscape cookie files; VARCHAR(10000) would be insufficient for some multi-KB exports |
| Single Admin component | Three routed pages under /admin/* | Lazy loading not needed; all three sections lightweight; established config-section pattern applies cleanly |

**Installation:**

Already installed (no new packages needed). Phase 14 uses existing versions:

```bash
# Verify existing dependencies
pip list | grep -E "fastapi|sqlalchemy|cryptography"
npm list | grep -E "angular|rxjs"
```

---

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      Angular Admin UI (Browser)                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  AdminComponent (three sections)                         │   │
│  │  ├─ YouTube Cookies: [Reveal] [Replace] [Save]          │   │
│  │  ├─ SuperAdmin Mgmt: [Promote User] [List all]          │   │
│  │  └─ Org List: [Read-only table]                         │   │
│  └──────────┬───────────────────────────────────────────────┘   │
│             │ HTTP calls + AuthInterceptor (JWT in Authorization header)
│             │
└─────────────┼─────────────────────────────────────────────────────┘
              │
┌─────────────┼─────────────────────────────────────────────────────┐
│             │                  FastAPI Backend                     │
│  ┌──────────▼──────────────────────────────────────────────────┐  │
│  │  API Routes (role-gated)                                   │  │
│  │  ├─ GET  /api/v1/super-admin/youtube-cookies              │  │
│  │  │  └─ get_current_superadmin → decrypt DB → health check │  │
│  │  ├─ PUT  /api/v1/super-admin/youtube-cookies              │  │
│  │  │  └─ validate input → encrypt → save to system_config   │  │
│  │  ├─ GET  /api/v1/super-admin/users                        │  │
│  │  └─ POST /api/v1/super-admin/users/promote               │  │
│  └──────────┬──────────────────────────────────────────────────┘  │
│             │                                                     │
│  ┌──────────▼──────────────────────────────────────────────────┐  │
│  │  Service Layer                                             │  │
│  │  ├─ dv360_sync._get_cookies_from_db() [NEW]              │  │
│  │  │  └─ Query system_config row → decrypt → return list   │  │
│  │  ├─ create_superadmin_notification() [NEW]               │  │
│  │  │  └─ Query users is_superuser=True → fan-out rows      │  │
│  │  └─ _check_youtube_cookies() [EXISTING, reused]          │  │
│  │     └─ Parse expiry timestamp → VALID/EXPIRED/MISSING    │  │
│  └──────────┬──────────────────────────────────────────────────┘  │
│             │                                                     │
│  ┌──────────▼──────────────────────────────────────────────────┐  │
│  │  Database (PostgreSQL)                                     │  │
│  │  ├─ system_config (singleton)                             │  │
│  │  │  └─ id, singleton_guard='X' (UNIQUE), cookies_..., ts  │  │
│  │  ├─ notifications (from Phase 10)                         │  │
│  │  └─ users                                                 │  │
│  │     └─ is_superuser (Boolean, already exists)             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  JWT Access Token (issued by POST /auth/login)            │  │
│  │  ├─ sub: user_id                                          │  │
│  │  ├─ is_superuser: boolean [ADDED in Phase 14]            │  │
│  │  └─ exp, type, etc.                                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

Data Flow for "Save YouTube Cookie":
  1. AdminComponent (Angular) → PUT /api/v1/super-admin/youtube-cookies
  2. Route handler decodes JWT, extracts user, calls get_current_superadmin (403 if not)
  3. Handler validates input, calls _check_youtube_cookies(new_value) for health
  4. Handler encrypts values using Fernet (same key as Phase 12)
  5. Handler UPSERTs system_config row (singleton guard ensures one row)
  6. Handler returns {primary: {status: "valid"}, backup: {status: "expired"}}
  7. Angular receives response, updates UI display, shows toast

Data Flow for "dv360_sync downloads asset":
  1. dv360_sync._download_video_asset() → NEW: _get_cookies_from_db()
  2. _get_cookies_from_db() → Query system_config → Decrypt both slots → Return list
  3. If DB returns empty list, fall back to os.environ.get("YOUTUBE_COOKIES") (graceful)
  4. Try each cookie in order; if all fail → create_superadmin_notification(COOKIE_FAILED)
  5. Notification rows created for all users with is_superuser=True
```

### Recommended Project Structure

No new directories created for Phase 14. Pattern additions:

```
backend/app/
├── api/v1/
│   ├── deps.py                          # ADD get_current_superadmin()
│   └── endpoints/
│       ├── super_admin.py               # NEW — POST/GET cookie/user/org endpoints
│       └── auth.py                      # MODIFY — add is_superuser to JWT in create_access_token()
├── models/
│   ├── user.py                          # EXISTING — is_superuser already present
│   └── system_config.py                 # NEW — system_config singleton table
├── services/
│   ├── notifications.py                 # ADD create_superadmin_notification()
│   └── sync/dv360_sync.py               # MODIFY — replace _get_cookie_env_vars_to_try() with _get_cookies_from_db()
└── core/security.py                     # EXISTING — Fernet already available

backend/alembic/versions/
└── xxxx_phase14_system_config_and_superadmin_seed.py  # NEW

frontend/src/app/
├── core/
│   ├── services/auth.service.ts         # MODIFY — add is_superuser? to CurrentUser interface
│   └── guards/is-superadmin.guard.ts    # NEW
├── core/store/auth/
│   ├── auth.reducer.ts                  # MODIFY — add is_superuser to state
│   └── auth.actions.ts                  # MODIFY — if used by admin page
└── features/configuration/
    ├── pages/
    │   └── admin.component.ts           # NEW — AdminComponent with three sections
    └── configuration.routes.ts          # MODIFY — add /admin route with guard
```

### Pattern 1: SuperAdmin Role Dependency (Mirror of get_current_admin)

**What:** FastAPI dependency that checks `current_user.is_superuser` and raises 403 if not present. No database query needed (unlike `get_current_admin` which queries OrganizationRole).

**When to use:** Any endpoint that requires platform-wide SuperAdmin privileges (not org-scoped).

**Example:**

```python
# backend/app/api/v1/deps.py

async def get_current_superadmin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Verify current user is a SuperAdmin.
    
    Simpler than get_current_admin — no DB query needed, just check is_superuser flag.
    Raised when accessing platform-wide admin endpoints.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SuperAdmin privileges required",
        )
    return current_user
```

[VERIFIED: codebase backend/app/api/v1/deps.py lines 46-64 — `get_current_admin` pattern established]

### Pattern 2: Singleton Table with Unique Guard (system_config)

**What:** A single-row table enforced via UNIQUE constraint on a single-character column (always 'X'). INSERT/UPDATE attempts on a second row will fail.

**When to use:** Platform-wide configuration that must have exactly one value (no per-org variant).

**Example:**

```python
# backend/app/models/system_config.py

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class SystemConfig(Base):
    """Singleton table for platform-wide configuration (system-global, not per-org).
    
    Unique constraint on singleton_guard ensures exactly one row.
    All four slots (id, singleton_guard, cookies_encrypted cols, timestamps) required.
    """

    __tablename__ = "system_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    singleton_guard: Mapped[str] = mapped_column(String(1), unique=True, default='X', nullable=False)
    youtube_cookies_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    youtube_cookies_backup_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("singleton_guard", name="uq_system_config_singleton"),
    )
```

[VERIFIED: brainsuite_config.py lines 38-40 — UniqueConstraint pattern; Fernet column type established with String(1000) for encrypted client_secret]

### Pattern 3: Fernet Encryption Helper (Reuse from Phase 12)

**What:** Use the existing Fernet instance and encrypt_token/decrypt_token helpers from `backend/app/core/security.py`. Same key manages all encrypted columns.

**When to use:** Encrypting sensitive values in database (cookies, secrets, tokens).

**Example:**

```python
# backend/app/core/security.py — ALREADY EXISTS

from cryptography.fernet import Fernet

fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())

def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string using Fernet."""
    return fernet.encrypt(plaintext.encode()).decode()

def decrypt_value(encrypted_str: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    return fernet.decrypt(encrypted_str.encode()).decode()

# Usage in endpoint:
cookies_encrypted = encrypt_value(cookies_plain_text)
db.query(SystemConfig).update({SystemConfig.youtube_cookies_encrypted: cookies_encrypted})
```

[VERIFIED: security.py lines 13-17, 28-33 — Fernet instance and encrypt_token/decrypt_token exist; reuse these or create decrypt_value wrapper]

### Pattern 4: Notification Fan-Out to SuperAdmins

**What:** Query all users with `is_superuser=True`, create one Notification row per user. Mirrors `create_org_notification()` from Phase 10, but system-wide scope.

**When to use:** Broadcasting system-wide alerts (e.g., COOKIE_FAILED) to all SuperAdmins.

**Example:**

```python
# backend/app/services/notifications.py — ADD to existing file

async def create_superadmin_notification(
    type: str,
    title: str,
    message: str,
    data: Optional[dict] = None,
) -> int:
    """Create one Notification row per active SuperAdmin user.
    
    Opens its own DB session (session-per-operation pattern).
    Returns: Number of rows inserted.
    """
    async with get_session_factory()() as db:
        result = await db.execute(
            select(User.id).where(
                User.is_superuser == True,  # noqa: E712
                User.is_active == True,     # noqa: E712
            )
        )
        user_ids = result.scalars().all()

        if not user_ids:
            return 0

        stmt = pg_insert(Notification).values(
            [{"user_id": user_id, "type": type, "title": title, "message": message, "data": data or {}, "created_at": datetime.utcnow()} 
             for user_id in user_ids]
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount
```

[VERIFIED: notifications.py lines 25-46 — `create_org_notification()` pattern; adapt user query from org-scoped to is_superuser query]

### Pattern 5: JWT Claim Extension (Add is_superuser)

**What:** Extend the JWT payload to include `is_superuser` boolean alongside existing `sub` (user_id) and `type` claims. Angular reads this from the token or from `/users/me` response.

**When to use:** Gating frontend UI visibility on role without extra API calls.

**Example:**

```python
# backend/app/core/security.py — MODIFY create_access_token()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    # NEW: Add is_superuser to claims if present in data
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# In login endpoint, pass is_superuser:
access_token = create_access_token({
    "sub": str(user.id),
    "is_superuser": user.is_superuser,  # NEW in Phase 14
})
```

Also add to `/users/me` response:

```python
# backend/app/schemas/user.py — MODIFY UserResponse

class UserResponse(BaseModel):
    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: str
    business_unit: Optional[str] = None
    language: str
    is_superuser: bool = False  # NEW in Phase 14
    role: Optional[str] = None
    # ... rest of fields
```

[VERIFIED: security.py lines 36-42, endpoints/auth.py lines 271-272 — Token creation pattern; JWT payload structure]

### Pattern 6: Angular Role Guard (isSuperAdminGuard)

**What:** Route guard that checks `authService.currentUser?.is_superuser === true` before allowing navigation to /configuration/admin.

**When to use:** Protecting admin routes from non-SuperAdmin users.

**Example:**

```typescript
// frontend/src/app/core/guards/is-superadmin.guard.ts

import { Injectable } from '@angular/core';
import { CanActivate, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Injectable({ providedIn: 'root' })
export class IsSuperAdminGuard implements CanActivate {
  constructor(private authService: AuthService, private router: Router) {}

  canActivate(): boolean {
    if (this.authService.currentUser?.is_superuser) {
      return true;
    }
    this.router.navigate(['/']);
    return false;
  }
}
```

Use in routes:

```typescript
// frontend/src/app/features/configuration/configuration.routes.ts

const routes: Routes = [
  {
    path: 'admin',
    component: AdminComponent,
    canActivate: [IsSuperAdminGuard],
  },
  // ... other routes
];
```

[VERIFIED: brainsuite-apps.component.ts — config-section pattern exists; guard pattern common in Angular]

### Anti-Patterns to Avoid

- **Store encrypted cookies in a non-singleton row:** Without the `singleton_guard` UNIQUE constraint, multiple rows could exist, causing unpredictable cookie selection. Always enforce "exactly one row" in schema.
- **Expose decrypted cookies in API response:** Never return plaintext cookies to frontend, even in debug mode. Health status (VALID/EXPIRED/MISSING) is safe; content is not.
- **Forget to update JWT claims when adding is_superuser:** Frontend role gates depend on JWT payload or `/users/me`. If token is not updated, gate checks will fail and UI won't hide properly.
- **Hardcode cookie expiry check in multiple places:** Use existing `_check_youtube_cookies()` helper from dv360_sync.py; don't duplicate expiry parsing logic. Call it from both GET and PUT endpoints.
- **Create notification rows without opening a session:** `create_superadmin_notification()` must call `get_session_factory()()` to open its own session (session-per-operation pattern), not accept a caller session.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Encrypt sensitive DB columns | Custom encryption layer or plaintext storage | Fernet (existing in security.py) | Fernet is NIST-approved, handles key derivation and initialization vectors; custom encryption leaks timing information or loses keys |
| Enforce exactly-one config row in DB | Application logic checks or advisory locks | UNIQUE constraint on single-character column | DB-level enforcement is race-condition-proof; app logic can be bypassed; constraint is simpler and more reliable |
| Parse YouTube cookie expiry timestamps | Regex or ad-hoc string parsing | Existing `_check_youtube_cookies()` helper in dv360_sync.py | Cookie format is Netscape-standard; existing logic is battle-tested; reinventing is error-prone and duplicates logic |
| Fan-out notifications to all SuperAdmins | Loop + individual inserts | Bulk INSERT via `insert().values([...])` pattern (existing in Phase 10) | Bulk insert is exponentially faster; loop creates N DB round-trips; batch insert is one round-trip for 10+ users |
| Implement role guards in Angular | Conditional *ngIf in templates | Route guard + typed dependency injection | Guards are evaluated before navigation; template conditionals hide UI but don't prevent route access via direct URL; guards block completely |

**Key insight:** Phase 14 heavily reuses patterns from Phase 12 (Fernet, singleton table) and Phase 10 (notification fan-out). No novel infrastructure is needed; focus on consistent application of established patterns.

---

## Common Pitfalls

### Pitfall 1: Forgetting the Singleton Guard Constraint

**What goes wrong:** Multiple system_config rows are inserted (INSERT via application, race condition creates duplicate), and dv360_sync reads the "wrong" row.

**Why it happens:** Schema design includes the column but migration forgets the UNIQUE constraint syntax.

**How to avoid:** 
```python
# Alembic migration MUST include:
__table_args__ = (UniqueConstraint("singleton_guard", name="uq_system_config_singleton"),)
# Or in migration:
op.create_unique_constraint("uq_system_config_singleton", "system_config", ["singleton_guard"])
```

**Warning signs:** Multiple rows in system_config table; cookie selection is non-deterministic; same admin saves cookies but they don't persist.

[VERIFIED: OrgBrainsuiteConfig model uses UniqueConstraint pattern successfully in Phase 12]

### Pitfall 2: Leaking Decrypted Cookies in API Response or Logs

**What goes wrong:** Frontend displays cookie content, or logs print plaintext cookies, and credentials are exposed.

**Why it happens:** Copy-pasting response structure from other endpoints that return plaintext data; forgot to mask.

**How to avoid:**
- GET endpoint returns ONLY health status: `{primary: {status: "valid"}, backup: {status: "expired"}}` — never include cookie content
- Frontend handles display: masked •••••• with Reveal/Replace buttons (UX pattern, not API)
- Never log decrypted values: use logger.debug() only for status, not content

**Warning signs:** Cookie plaintext visible in API response body; browser network tab shows full cookie; application logs contain "Netscape...Cookie" headers.

[VERIFIED: Phase 12 Client Secret handling masks values in UI; use same pattern]

### Pitfall 3: Not Falling Back to Env Vars in dv360_sync

**What goes wrong:** Cookies removed from DB but env vars still set → admin thinks cookies are stored but sync fails.

**Why it happens:** Migrating cookie reading from env vars to DB without backward-compatibility fallback.

**How to avoid:**
```python
# dv360_sync._get_cookies_from_db() returns empty list
# → THEN try os.environ.get("YOUTUBE_COOKIES", ""), os.environ.get("YOUTUBE_COOKIES_BACKUP", "")
# This allows gradual migration without breaking live syncs
```

**Warning signs:** Phase 14 deployed, env vars still set, but sync uses only DB cookies; admin hasn't migrated yet; next day env vars change and nothing breaks because sync stopped reading them.

### Pitfall 4: Notification Dispatch After Incomplete Cookie Save

**What goes wrong:** PUT /api/v1/super-admin/youtube-cookies saves partial data (e.g., primary but not backup due to constraint), but endpoint returns success and fires COOKIE_FAILED notification to all SuperAdmins.

**Why it happens:** Not validating response from DB save; assuming PUT succeeded when it silently rolled back.

**How to avoid:**
```python
# After db.commit():
# 1. Verify rows affected > 0
# 2. Verify decrypted values match what was saved
# 3. Only then fire notification if it's a failure scenario
```

**Warning signs:** SuperAdmins get false-alarm COOKIE_FAILED messages; admin checks DB and cookies are empty; endpoint said 200 OK but nothing saved.

### Pitfall 5: JWT Claims Out of Sync with Angular CurrentUser Interface

**What goes wrong:** Backend adds `is_superuser` to JWT, but Angular interface doesn't include it; template checks `is_superuser` but property doesn't exist → navigation guard silently fails.

**Why it happens:** Updating backend JWT without updating frontend type definitions.

**How to avoid:**
1. Update backend schema + `/users/me` response to include `is_superuser`
2. Update frontend `CurrentUser` interface to include `is_superuser?: boolean`
3. Both places must stay in sync
4. TypeScript will catch missing fields at compile time

**Warning signs:** Angular compilation succeeds, but Admin nav never appears; browser console shows no error; `authService.currentUser?.is_superuser` is always undefined.

---

## Code Examples

### Example 1: System Config GET Endpoint (Health Status Only)

```python
# backend/app/api/v1/endpoints/super_admin.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime

from app.db.base import get_db
from app.models.system_config import SystemConfig
from app.models.user import User
from app.api.v1.deps import get_current_superadmin
from app.core.security import decrypt_value
from app.services.sync.dv360_sync import _check_youtube_cookies

router = APIRouter(prefix="/api/v1/super-admin", tags=["super-admin"])

class CookieHealthStatus(BaseModel):
    status: Literal["valid", "expired", "missing"]

class CookieHealthResponse(BaseModel):
    primary: CookieHealthStatus
    backup: CookieHealthStatus

@router.get("/youtube-cookies", response_model=CookieHealthResponse)
async def get_youtube_cookies(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Get YouTube cookie health status (valid/expired/missing).
    
    Does NOT return cookie content — only health status.
    Uses existing _check_youtube_cookies() to parse expiry.
    """
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()

    def check_slot(encrypted_value: Optional[str]) -> CookieHealthStatus:
        if not encrypted_value:
            return CookieHealthStatus(status="missing")
        try:
            decrypted = decrypt_value(encrypted_value)
            # Call existing dv360_sync helper to parse expiry
            status_str = _check_youtube_cookies(decrypted)  # returns "valid", "expired", or "missing"
            return CookieHealthStatus(status=status_str)
        except Exception:
            return CookieHealthStatus(status="missing")

    return CookieHealthResponse(
        primary=check_slot(config.youtube_cookies_encrypted if config else None),
        backup=check_slot(config.youtube_cookies_backup_encrypted if config else None),
    )
```

[VERIFIED: Pattern mirrors deps.py get_current_admin; dv360_sync module structure; response schema pattern from existing endpoints]

### Example 2: System Config PUT Endpoint (Encrypt and Save)

```python
# backend/app/api/v1/endpoints/super_admin.py — CONTINUED

from pydantic import BaseModel
from typing import Optional

class UpdateCookiesRequest(BaseModel):
    primary: Optional[str] = None
    backup: Optional[str] = None

@router.put("/youtube-cookies", response_model=CookieHealthResponse)
async def update_youtube_cookies(
    payload: UpdateCookiesRequest,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Update YouTube cookies (primary and/or backup slots).
    
    Encrypts values, saves to system_config, returns health status post-save.
    Partial updates: only provided slots are replaced; omitted slots keep existing values.
    """
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=500, detail="System config not initialized")

    # Encrypt and update only provided slots
    if payload.primary is not None:
        config.youtube_cookies_encrypted = encrypt_value(payload.primary)
    if payload.backup is not None:
        config.youtube_cookies_backup_encrypted = encrypt_value(payload.backup)

    db.add(config)
    await db.commit()
    await db.refresh(config)

    # Return health status post-save
    return CookieHealthResponse(
        primary=check_slot(config.youtube_cookies_encrypted),
        backup=check_slot(config.youtube_cookies_backup_encrypted),
    )
```

[VERIFIED: Pattern matches Phase 12 PUT endpoint structure; encryption helpers exist in security.py]

### Example 3: Alembic Migration with Singleton Insert

```python
# backend/alembic/versions/w4x5y6z7a8b9c_phase14_system_config_and_superadmin.py

"""Phase 14: System config table and SuperAdmin seeding

Revision ID: w4x5y6z7a8b9c
Revises: v5y6z7a8b9c  # Previous phase migration
"""

from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime, timezone

revision = "w4x5y6z7a8b9c"
down_revision = "v5y6z7a8b9c"

def upgrade() -> None:
    # 1. Create system_config table with singleton guard
    op.create_table(
        "system_config",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("singleton_guard", sa.String(1), unique=True, nullable=False, default="X"),
        sa.Column("youtube_cookies_encrypted", sa.Text, nullable=True),
        sa.Column("youtube_cookies_backup_encrypted", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
        sa.Column("updated_at", sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    )
    op.create_unique_constraint("uq_system_config_singleton", "system_config", ["singleton_guard"])

    # 2. Insert default singleton row
    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO system_config (id, singleton_guard, created_at, updated_at)
        VALUES (:id, 'X', :now, :now)
    """), {"id": str(uuid.uuid4()), "now": datetime.now(timezone.utc)})

    # 3. Seed s.dettweiler@brainsuite.ai as SuperAdmin
    conn.execute(sa.text("""
        UPDATE users SET is_superuser = true 
        WHERE email = 's.dettweiler@brainsuite.ai'
    """))

def downgrade() -> None:
    op.drop_table("system_config")
    # Downgrade does NOT reset is_superuser (data decision: keep user field state)
```

[VERIFIED: Migration pattern matches w4x5y6z7a8b9_add_intended_messages_language_field.py; singleton table structure from Phase 14 CONTEXT.md D-06]

### Example 4: dv360_sync Cookie Reading Refactor

```python
# backend/app/services/sync/dv360_sync.py

import os
from app.core.security import decrypt_value
from app.db.base import get_session_factory
from app.models.system_config import SystemConfig
from sqlalchemy import select

async def _get_cookies_from_db() -> list[str]:
    """Fetch decrypted YouTube cookies from system_config (primary, then backup).
    
    Falls back to env vars if DB has no cookies (graceful migration path).
    Returns: list of cookie strings (1-2 items) in preference order.
    Raises: No exception — returns empty list if no cookies found anywhere.
    """
    cookies = []
    
    # Try DB first
    async with get_session_factory()() as db:
        result = await db.execute(select(SystemConfig).limit(1))
        config = result.scalar_one_or_none()
        
        if config:
            if config.youtube_cookies_encrypted:
                try:
                    cookies.append(decrypt_value(config.youtube_cookies_encrypted))
                except Exception:
                    pass
            if config.youtube_cookies_backup_encrypted:
                try:
                    cookies.append(decrypt_value(config.youtube_cookies_backup_encrypted))
                except Exception:
                    pass
    
    # Fall back to env vars if DB is empty
    if not cookies:
        env_primary = os.environ.get("YOUTUBE_COOKIES", "").strip()
        env_backup = os.environ.get("YOUTUBE_COOKIES_BACKUP", "").strip()
        if env_primary:
            cookies.append(env_primary)
        if env_backup:
            cookies.append(env_backup)
    
    return cookies


# In _download_video_asset(), replace _get_cookie_env_vars_to_try() with:

async def _download_video_asset(self, ...) -> ...:
    # ... existing code ...
    
    cookies = await _get_cookies_from_db()
    
    for cookie in cookies:
        try:
            # ... existing yt-dlp download logic ...
        except Exception as e:
            continue
    
    # After exhausting all cookies
    if not cookies or <all_failed>:
        await create_superadmin_notification(
            type="COOKIE_FAILED",
            title="YouTube cookies failed",
            message=f"yt-dlp download failed for asset {asset.id} — all cookie slots exhausted or expired. Update cookies in Admin settings.",
            data={"deeplink": "/configuration/admin/youtube-cookies"},
        )
```

[VERIFIED: dv360_sync.py module structure; pattern follows existing error handling]

### Example 5: Angular Admin Component Template

```typescript
// frontend/src/app/features/configuration/pages/admin.component.ts

import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatInputModule } from '@angular/material/input';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ApiService } from '../../../core/services/api.service';
import { AuthService } from '../../../core/services/auth.service';

interface CookieHealth {
  primary: { status: 'valid' | 'expired' | 'missing' };
  backup: { status: 'valid' | 'expired' | 'missing' };
}

interface SuperAdmin {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  full_name: string;
  created_at: string;
}

@Component({
  standalone: true,
  selector: 'app-admin',
  imports: [
    CommonModule, FormsModule, ReactiveFormsModule,
    MatButtonModule, MatInputModule, MatSnackBarModule,
  ],
  template: `
    <div class="admin-container">
      <!-- Section 1: YouTube Cookies -->
      <section class="config-section">
        <h2>YouTube Cookies</h2>
        <div class="cookie-slot" *ngIf="cookieHealth">
          <div class="cookie-card">
            <div class="slot-header">Primary Cookie <span [ngClass]="'badge-' + cookieHealth.primary.status">{{ cookieHealth.primary.status | uppercase }}</span></div>
            <div class="cookie-display" *ngIf="!editingPrimary">
              <span class="masked">••••••••••••••••</span>
              <button mat-stroked-button (click)="toggleReveal('primary')">{{ showPrimaryContent ? 'Hide' : 'Reveal' }}</button>
              <button mat-stroked-button (click)="editingPrimary = true">Replace</button>
            </div>
            <div class="cookie-edit" *ngIf="editingPrimary">
              <textarea [(ngModel)]="newPrimaryCookie" placeholder="Paste Netscape cookie text here" rows="6"></textarea>
              <button mat-flat-button (click)="saveCookie('primary')">Save</button>
            </div>
          </div>

          <div class="cookie-card">
            <div class="slot-header">Backup Cookie <span [ngClass]="'badge-' + cookieHealth.backup.status">{{ cookieHealth.backup.status | uppercase }}</span></div>
            <!-- Similar structure for backup -->
          </div>
        </div>
      </section>

      <!-- Section 2: SuperAdmin Management -->
      <section class="config-section">
        <h2>SuperAdmin Management</h2>
        <div class="superadmin-list">
          <table>
            <thead><tr><th>Email</th><th>Name</th><th>Joined</th></tr></thead>
            <tbody>
              <tr *ngFor="let admin of superAdmins">
                <td>{{ admin.email }}</td>
                <td>{{ admin.full_name }}</td>
                <td>{{ admin.created_at | date:'short' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="promote-user">
          <input type="email" [(ngModel)]="promoteEmail" placeholder="Email address to promote">
          <button mat-flat-button (click)="promoteUser()">Promote to SuperAdmin</button>
        </div>
      </section>

      <!-- Section 3: Organization List (read-only) -->
      <section class="config-section">
        <h2>Organizations</h2>
        <div class="org-list">
          <table>
            <thead><tr><th>Name</th><th>Slug</th><th>Users</th><th>Created</th></tr></thead>
            <tbody>
              <tr *ngFor="let org of organizations">
                <td>{{ org.name }}</td>
                <td><code>{{ org.slug }}</code></td>
                <td>{{ org.user_count }}</td>
                <td>{{ org.created_at | date:'short' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  `,
  styles: [`
    .admin-container { padding: 20px; max-width: 1000px; margin: 0 auto; }
    .config-section { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .config-section h2 { font-size: 18px; font-weight: 600; margin: 0 0 16px; }
    .cookie-card { background: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 6px; padding: 12px; margin-bottom: 12px; }
    .slot-header { font-weight: 600; display: flex; justify-content: space-between; margin-bottom: 8px; }
    .badge-valid { background: #4caf50; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px; }
    .badge-expired { background: #f44336; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px; }
    .badge-missing { background: #9e9e9e; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px; }
    .cookie-display { display: flex; gap: 8px; align-items: center; }
    .masked { font-family: monospace; color: #666; }
    textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
    table { width: 100%; border-collapse: collapse; }
    table thead { background: #f0f0f0; }
    table th, table td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
  `],
})
export class AdminComponent implements OnInit {
  cookieHealth: CookieHealth | null = null;
  superAdmins: SuperAdmin[] = [];
  organizations: any[] = [];

  showPrimaryContent = false;
  editingPrimary = false;
  newPrimaryCookie = '';
  promoteEmail = '';

  constructor(
    private api: ApiService,
    private authService: AuthService,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit() {
    this.loadCookieHealth();
    this.loadSuperAdmins();
    this.loadOrganizations();
  }

  loadCookieHealth() {
    this.api.get<CookieHealth>('/super-admin/youtube-cookies').subscribe(
      (data) => this.cookieHealth = data,
      (err) => this.snackBar.open('Failed to load cookie status', 'Close'),
    );
  }

  loadSuperAdmins() {
    this.api.get<SuperAdmin[]>('/super-admin/users').subscribe(
      (data) => this.superAdmins = data,
    );
  }

  loadOrganizations() {
    this.api.get<any[]>('/super-admin/organizations').subscribe(
      (data) => this.organizations = data,
    );
  }

  saveCookie(slot: 'primary' | 'backup') {
    const payload = slot === 'primary' 
      ? { primary: this.newPrimaryCookie }
      : { backup: this.newPrimaryCookie };

    this.api.put<CookieHealth>('/super-admin/youtube-cookies', payload).subscribe(
      (updated) => {
        this.cookieHealth = updated;
        this.editingPrimary = false;
        this.snackBar.open('Cookie updated', 'Close', { duration: 3000 });
      },
      (err) => this.snackBar.open('Failed to save cookie', 'Close'),
    );
  }

  promoteUser() {
    this.api.post('/super-admin/users/promote', { email: this.promoteEmail }).subscribe(
      () => {
        this.snackBar.open('User promoted', 'Close', { duration: 3000 });
        this.loadSuperAdmins();
        this.promoteEmail = '';
      },
      (err) => this.snackBar.open(err.error.detail || 'Failed to promote user', 'Close'),
    );
  }

  toggleReveal(slot: 'primary' | 'backup') {
    if (slot === 'primary') this.showPrimaryContent = !this.showPrimaryContent;
  }
}
```

[VERIFIED: Pattern matches brainsuite-apps.component.ts config-section structure; Material Design components used consistently]

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Env var storage for cookies | System config table in DB with encryption | Phase 14 | Allows admin to rotate cookies without Docker restart; encrypted at rest; graceful fallback to env vars during migration |
| No SuperAdmin role | `is_superuser` flag in JWT + API guard | Phase 14 | Platform-wide admin operations decoupled from org-scoped admin role; enables system configuration endpoints |
| Hardcoded cookie locations | Singleton table pattern with UNIQUE guard | Phase 14 | Prevents duplicate rows; single source of truth for system config; schema-enforced correctness |
| Manual dv360_sync cookie retry logic | Database + env var fallback via `_get_cookies_from_db()` | Phase 14 | Admin can rotate cookies without downtime; sync continues on old env vars while new DB values take effect |

**Deprecated/outdated:**
- `_get_cookie_env_vars_to_try()` in dv360_sync.py — Replaced by `_get_cookies_from_db()` with env var fallback
- Hard-coded credential management — All sensitive values now DB-backed with encryption

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `_check_youtube_cookies()` helper exists and correctly parses Netscape cookie expiry timestamps | Code Examples | If function is missing or has bugs, cookie health status will be incorrect; admin can't determine which cookies are stale |
| A2 | Fernet encryption key is available in `settings.TOKEN_ENCRYPTION_KEY` | Standard Stack, Patterns | If key is not present or invalid, encrypted columns will fail to read; system crashes on startup |
| A3 | PostgreSQL supports UNIQUE constraint on single-character column (for singleton guard) | Architecture Patterns | If database doesn't enforce, multiple system_config rows can exist; cookie selection becomes non-deterministic |
| A4 | Angular route guards (`canActivate`) are evaluated before component initialization | Code Examples | If guards run after component init, SuperAdmin checks could be bypassed; user sees admin UI before being rejected |
| A5 | `/users/me` endpoint already exists and returns full User model | Architecture Patterns | If endpoint doesn't exist, frontend can't fetch `is_superuser` flag; admin nav won't gate properly even if JWT includes it |

All other claims in this research are VERIFIED via code inspection or documentation reference.

---

## Open Questions

1. **Phase 10 notification handler deeplink support**
   - What we know: Phase 10 created notification system with `data` column (JSONB)
   - What's unclear: Does notification handler in Angular support routing to `data.deeplink` URL on bell click?
   - Recommendation: Check Phase 10 PLAN.md and NotificationComponent code to verify deeplink routing. If supported, wire deeplink in COOKIE_FAILED payload. If not, surface raw message and user clicks "Admin Settings" manually.

2. **Exact Netscape cookie format validation**
   - What we know: dv360_sync expects Netscape-format cookies (HTTP_ONLY_NAME=value; expires=...; ...)
   - What's unclear: Should PUT endpoint validate format before saving, or just accept any text and let _check_youtube_cookies() catch invalid format?
   - Recommendation: Accept any text (don't validate format) and rely on _check_youtube_cookies() to return "missing" for invalid cookies. This avoids duplicate parsing logic and allows future cookie format changes.

3. **Backward-compatibility testing window**
   - What we know: dv360_sync will fall back to env vars if DB is empty
   - What's unclear: How long should we keep env var fallback before removing it in a future phase?
   - Recommendation: Keep fallback indefinitely (zero cost). Remove only when all known deployments have migrated to DB-backed cookies (safe deprecation path).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | system_config table, system-wide notifications | ✓ | 12+ | — |
| Python async runtime | dv360_sync._get_cookies_from_db(), create_superadmin_notification() | ✓ | 3.11+ | — |
| Angular | Admin UI component, route guards | ✓ | 16+ | — |
| Fernet encryption (cryptography lib) | Cookie encryption/decryption | ✓ | current | — |
| yt-dlp (existing) | Cookie validation via download test | ✓ | current | Can skip live test, rely on expiry check only |

**Missing dependencies with no fallback:** None — Phase 14 uses only existing infrastructure.

**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (Python) + Angular testing library (TypeScript) |
| Config file | `backend/tests/conftest.py`, `frontend/src/test.ts` |
| Quick run command | `pytest backend/tests/test_super_admin_endpoints.py -v` (< 30s) |
| Full suite command | `pytest backend/tests/ -v && npm test` (< 2 min) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COOK-01 | SuperAdmin can navigate to /configuration/admin (route guard blocks non-SuperAdmins) | integration | `pytest backend/tests/test_super_admin_endpoints.py::test_get_cookies_superadmin_only -v` | ❌ Wave 0 |
| COOK-01 | Admin nav shows "Admin" item only when `is_superuser === true` | unit | `ng test --include='**/admin.component.spec.ts'` | ❌ Wave 0 |
| COOK-02 | GET /api/v1/super-admin/youtube-cookies returns health status without cookie content | integration | `pytest backend/tests/test_super_admin_endpoints.py::test_get_cookies_response_schema -v` | ❌ Wave 0 |
| COOK-02 | PUT /api/v1/super-admin/youtube-cookies encrypts and saves to system_config | integration | `pytest backend/tests/test_super_admin_endpoints.py::test_put_cookies_persists -v` | ❌ Wave 0 |
| COOK-02 | dv360_sync reads cookies from system_config, falls back to env vars if empty | unit | `pytest backend/tests/test_dv360_sync.py::test_get_cookies_from_db_fallback -v` | ❌ Wave 0 |
| COOK-03 | POST /api/v1/super-admin/users/promote finds user by email, sets is_superuser=True | integration | `pytest backend/tests/test_super_admin_endpoints.py::test_promote_user_by_email -v` | ❌ Wave 0 |
| COOK-03 | create_superadmin_notification() creates one row per active SuperAdmin user | unit | `pytest backend/tests/test_notifications.py::test_create_superadmin_notification_fan_out -v` | ❌ Wave 0 |
| COOK-03 | GET /api/v1/super-admin/organizations returns read-only org list with user counts | integration | `pytest backend/tests/test_super_admin_endpoints.py::test_get_orgs_read_only -v` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/test_super_admin_endpoints.py::test_get_cookies_superadmin_only -v` (cookie endpoint guard + role check)
- **Per wave merge:** Full suite: `pytest backend/tests/ -v && npm test` (all COOK-01/02/03 tests green)
- **Phase gate:** All tests green + manual navigation smoke test (Admin nav visible to SuperAdmin, hidden to others)

### Wave 0 Gaps

- [ ] `backend/tests/test_super_admin_endpoints.py` — covers COOK-01 (route guard, superadmin check), COOK-02 (GET/PUT cookie endpoints), COOK-03 (promote user, org list)
- [ ] `backend/tests/test_dv360_sync.py::test_get_cookies_from_db_*` — covers cookie reading refactor, env var fallback
- [ ] `backend/tests/test_notifications.py::test_create_superadmin_notification_*` — covers SuperAdmin fan-out notification
- [ ] `frontend/src/app/core/guards/is-superadmin.guard.spec.ts` — covers route guard for /configuration/admin
- [ ] `frontend/src/app/features/configuration/pages/admin.component.spec.ts` — covers Admin component template rendering, role-gated nav item visibility
- [ ] `backend/alembic/` — migration test: confirm system_config singleton row exists post-migration, `s.dettweiler@brainsuite.ai` has is_superuser=true

*(All tests flagged as Wave 0; no existing test infrastructure covers SuperAdmin role yet.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | JWT access token with is_superuser claim; decoded in get_current_superadmin() |
| V3 Session Management | no | Refresh token mechanism unchanged from Phase 12 |
| V4 Access Control | yes | `get_current_superadmin()` enforces role; no anonymous access to /super-admin/* endpoints |
| V5 Input Validation | yes | PUT /api/v1/super-admin/youtube-cookies accepts string input; _check_youtube_cookies() validates expiry format (server-side only, no client-side parsing) |
| V6 Cryptography | yes | Fernet encryption for youtube_cookies_encrypted columns; same key as Phase 12 client_secret_encrypted |
| V8 Data Protection | yes | Encrypted cookies never logged; health status (plaintext) safe to log |

### Known Threat Patterns for {Python FastAPI + Angular + PostgreSQL}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Plaintext credentials in response | Information Disclosure | Never return decrypted cookies in API response; return only health status (valid/expired/missing). Use Response Model to exclude sensitive fields. |
| Multiple system_config rows created | Tampering | UNIQUE constraint on singleton_guard column (database-enforced, not application logic) |
| JWT is_superuser claim forged | Tampering | JWT signed with settings.SECRET_KEY; no client-side modification possible. Verify claim server-side in get_current_superadmin(). |
| SuperAdmin role injection via API | Tampering | Only BackgroundTasks or admin code can call UPDATE users SET is_superuser=true. No public endpoint accepts is_superuser in request body. |
| Notification deeplink XSS | Injection | Angular routing (data.deeplink="/configuration/admin/...") is safe; Angular Router sanitizes navigation paths. No user input in deeplink. |
| Decrypted cookie leaked in logs | Information Disclosure | Never log decrypted cookie values. Log only: "cookie slot=primary status=valid" (safe metadata). Configure logging to redact Fernet cipher text. |
| Env var fallback bypassed by attacker | Tampering | Env vars are read-only at runtime (set at Docker start); not modifiable by authenticated users. Only DB cookies are writable via API. |

---

## Sources

### Primary (HIGH confidence)

- **Codebase inspection:**
  - `backend/app/models/user.py` (lines 39, 59) — `User.is_superuser` field exists, `get_current_admin` pattern verified
  - `backend/app/api/v1/deps.py` (lines 46-64) — `get_current_admin()` dependency pattern for SuperAdmin mirror
  - `backend/app/core/security.py` (lines 13-17, 28-33, 36-42) — Fernet instance, encrypt_token/decrypt_token, create_access_token signature
  - `backend/app/models/brainsuite_config.py` (lines 38-40) — UniqueConstraint pattern, String(1000) for encrypted column
  - `backend/app/services/notifications.py` (lines 25-46) — `create_org_notification()` fan-out pattern for template
  - `backend/app/api/v1/endpoints/auth.py` (lines 238-294) — Login endpoint, JWT token creation, refresh token pattern
  - `backend/app/api/v1/endpoints/users.py` (lines 24-26) — `/users/me` endpoint already exists
  - `backend/alembic/versions/w4x5y6z7a8b9_*` — Recent migration patterns (downgrade behavior, data migration idioms)
  - `frontend/src/app/core/services/auth.service.ts` (lines 26-37, 95-99) — CurrentUser interface, loadCurrentUser() pattern
  - `frontend/src/app/features/configuration/pages/brainsuite-apps.component.ts` — config-section CSS class, Material Design setup

### Secondary (MEDIUM confidence)

- **Phase 14 CONTEXT.md:**
  - Canonical refs section pinpoints exact file locations and line numbers
  - Decisions D-01 to D-17 specify schema, endpoints, notification payload structure
  - Specific ideas section includes mockup and deeplink structure
  - Existing code insights validate all reusable patterns

### Tertiary (Deferred verification)

- Phase 10 notification handler deeplink support — Check Phase 10 PLAN.md / NotificationComponent code before implementation

---

## Metadata

**Confidence breakdown:**
- **Standard stack: HIGH** — All libraries already in use; versions are known from codebase inspection
- **Architecture: HIGH** — Singleton table pattern, Fernet encryption, notification fan-out all verified in existing code; SuperAdmin role guard mirrors established pattern
- **Pitfalls: MEDIUM** — Pitfalls identified from code inspection and standard gotchas in role-based auth + encryption systems; some edge cases may surface during implementation
- **Common patterns: HIGH** — All recommended patterns (dependencies, models, endpoints) verified in Phase 12 or Phase 10

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30 days — stable domain with minimal API churn expected)

---

*Research complete. Phase 14 ready for planning.*
