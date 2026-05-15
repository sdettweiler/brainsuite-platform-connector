# Phase 21: Proxy Admin UI - Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** 3 new/modified files
**Analogs found:** 3 / 3 (100% match)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/api/v1/endpoints/super_admin.py` (3 new endpoints) | controller | request-response | `backend/app/api/v1/endpoints/super_admin.py` (YouTube Cookies endpoints) | exact |
| `frontend/src/app/features/configuration/pages/admin.component.ts` (new proxy card section) | component | request-response | `frontend/src/app/features/configuration/pages/admin.component.ts` (cookie card section) | exact |

## Pattern Assignments

### Backend: `super_admin.py` — 3 New Endpoints (controller, request-response)

**Analog:** `backend/app/api/v1/endpoints/super_admin.py` (lines 122–231)

The YouTube Cookies GET/PUT endpoints demonstrate the exact pattern needed for proxy configuration: encrypt/decrypt token storage, partial update support, singleton SystemConfig read, and masked response return.

#### Imports Pattern (lines 1–38)

```python
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import get_db
from app.models.system_config import SystemConfig
from app.api.v1.deps import get_current_superadmin
from app.core.security import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)
router = APIRouter()
```

**For Phase 21 proxy endpoints, add to imports:**
```python
import httpx
import time
```

#### Pydantic Models Pattern (lines 48–60 for YouTube Cookies)

**YouTube Cookies reference:**
```python
class CookieSlotHealth(BaseModel):
    status: Literal["valid", "expired", "missing"]

class CookieHealthResponse(BaseModel):
    primary: CookieSlotHealth
    backup: CookieSlotHealth

class UpdateCookiesRequest(BaseModel):
    primary: Optional[str] = None
    backup: Optional[str] = None
```

**For Phase 21, add proxy models before endpoints:**
```python
class ProxyConfigResponse(BaseModel):
    proxy_enabled: bool
    proxy_url_masked: Optional[str] = None

class UpdateProxyConfigRequest(BaseModel):
    proxy_enabled: Optional[bool] = None
    proxy_url: Optional[str] = None

class ProxyTestResponse(BaseModel):
    success: bool
    latency_ms: Optional[int] = None
    error: Optional[str] = None
```

#### GET Endpoint Pattern (lines 122–162)

**YouTube Cookies reference:**
```python
@router.get("/youtube-cookies", response_model=CookieHealthResponse)
async def get_youtube_cookies(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Return health status for both YouTube cookie slots."""
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()

    primary_status = "missing"
    
    if config:
        if config.youtube_cookies_encrypted:
            try:
                decrypted = decrypt_token(config.youtube_cookies_encrypted)
                primary_status = _check_cookie_health(decrypted)
            except Exception:
                primary_status = "missing"
    
    return CookieHealthResponse(primary=CookieSlotHealth(status=primary_status), ...)
```

**For Phase 21 GET /super-admin/proxy-config:**
1. Execute `select(SystemConfig).limit(1)` and get singleton row
2. Read `config.proxy_enabled` and `config.proxy_url_encrypted`
3. Decrypt the URL with `decrypt_token()` and mask it using `_mask_proxy_url()`
4. Return `ProxyConfigResponse(proxy_enabled, proxy_url_masked)` or `None` for masked URL if not configured

#### PUT Endpoint Pattern (lines 165–231)

**YouTube Cookies reference:**
```python
@router.put("/youtube-cookies", response_model=CookieHealthResponse)
async def update_youtube_cookies(
    payload: UpdateCookiesRequest,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Update YouTube cookie slots (partial update supported)."""
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System config not initialized",
        )

    if payload.primary is not None:
        config.youtube_cookies_encrypted = encrypt_token(payload.primary)
        logger.info("SuperAdmin updated primary YouTube cookie slot (cookie content not logged)")

    db.add(config)
    await db.commit()
    await db.refresh(config)

    # Return fresh state...
    return CookieHealthResponse(...)
```

**For Phase 21 PUT /super-admin/proxy-config:**
1. Fetch singleton SystemConfig row (same pattern as GET)
2. If `payload.proxy_enabled is not None`, set `config.proxy_enabled = payload.proxy_enabled`
3. If `payload.proxy_url is not None`, encrypt with `config.proxy_url_encrypted = encrypt_token(payload.proxy_url)` and log safely: `"SuperAdmin updated proxy URL (credentials not logged)"`
4. `db.add(config)`, `await db.commit()`, `await db.refresh(config)`
5. Return fresh `ProxyConfigResponse` with masked URL (same logic as GET endpoint for masking)

#### POST Test Endpoint Pattern (new for Phase 21)

**Structure inspired by YouTube Cookies PUT, but async HTTP test:**
- Require `get_current_superadmin` dependency
- Fetch SystemConfig singleton
- Validate proxy is enabled AND URL is configured; return 400 if not
- Decrypt URL with `decrypt_token()`
- Use `httpx.AsyncClient` with `proxies={"https://": proxy_url}` parameter
- Call `GET https://www.youtube.com/` with `timeout=5.0`
- Capture start/end time for latency
- Return `ProxyTestResponse(success, latency_ms, error)`
- Catch `httpx.ConnectError` → `error="Connection timed out after 5s"`, catch other exceptions → `error=str(e)`

#### URL Masking Helper (new for Phase 21)

```python
def _mask_proxy_url(url: str) -> str:
    """Parse http(s)://user:pass@host:port and mask credentials: http://••••••@host:port"""
    try:
        if "@" in url:
            scheme_and_auth, host_port = url.rsplit("@", 1)
            scheme = scheme_and_auth.split("://")[0] if "://" in scheme_and_auth else "http"
            return f"{scheme}://••••••@{host_port}"
        return url
    except Exception:
        return url
```

#### Error Handling Pattern (lines 176–182 excerpt)

```python
# Singleton config check — same in all endpoints
if config is None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="System config not initialized",
    )
```

**For proxy test endpoint:**
```python
# Decrypt validation
try:
    proxy_url = decrypt_token(config.proxy_url_encrypted)
except Exception:
    return ProxyTestResponse(success=False, error="Failed to decrypt proxy URL")

# HTTP exceptions
except httpx.ConnectError:
    return ProxyTestResponse(success=False, error="Connection timed out after 5s")
except Exception as e:
    return ProxyTestResponse(success=False, error=str(e))
```

#### Logging Pattern (lines 186, 189–190)

```python
logger.info("SuperAdmin updated primary YouTube cookie slot (cookie content not logged)")
```

**For proxy endpoints:**
- `logger.info(f"SuperAdmin toggled proxy: {payload.proxy_enabled}")`
- `logger.info("SuperAdmin updated proxy URL (credentials not logged)")`
- Never log decrypted proxy_url, even at debug level

---

### Frontend: `admin.component.ts` — Proxy Card Section (component, request-response)

**Analog:** `frontend/src/app/features/configuration/pages/admin.component.ts` (lines 57–688)

The existing YouTube Cookies section (lines 60–135) and Scoring Controls toggle (lines 203–285) demonstrate the exact UI patterns needed: toggle with immediate PUT, edit mode with Replace/Save button, masked display, and result rendering.

#### Component Interfaces (lines 12–51 for reference)

**Existing patterns to follow:**
```typescript
interface CookieSlotHealth {
  status: 'valid' | 'expired' | 'missing';
}

interface CookieHealthResponse {
  primary: CookieSlotHealth;
  backup: CookieSlotHealth;
}

interface ScoringConfigResponse {
  scoring_enabled: boolean;
  organizations: OrgScoringItem[];
}
```

**Add proxy interfaces:**
```typescript
interface ProxyConfigResponse {
  proxy_enabled: boolean;
  proxy_url_masked: string | null;
}

interface ProxyTestResult {
  success: boolean;
  latency_ms: number | null;
  error: string | null;
}
```

#### Component State Properties (lines 497–517 excerpt)

**Existing pattern:**
```typescript
export class AdminComponent implements OnInit {
  cookieHealth: CookieHealthResponse | null = null;
  loadingCookies = true;
  editingPrimary = false;
  editingBackup = false;
  newPrimaryCookie = '';
  newBackupCookie = '';
  savingPrimary = false;
  savingBackup = false;

  scoringConfig: ScoringConfigResponse | null = null;
  loadingScoring = true;
  togglingScoring = false;
```

**Add proxy state (same naming convention):**
```typescript
proxyConfig: ProxyConfigResponse | null = null;
loadingProxy = true;
editingProxyUrl = false;
newProxyUrl = '';
savingProxyUrl = false;
testingProxy = false;
testResult: ProxyTestResult | null = null;
```

#### ngOnInit Pattern (lines 524–529)

**Existing pattern:**
```typescript
ngOnInit(): void {
  this.loadCookieHealth();
  this.loadSuperAdmins();
  this.loadOrganizations();
  this.loadScoringConfig();
}
```

**Add to ngOnInit:**
```typescript
this.loadProxyConfig();
```

#### Load Data Method Pattern (lines 531–538)

**YouTube Cookies reference:**
```typescript
loadCookieHealth(): void {
  this.loadingCookies = true;
  this.cookieError = false;
  this.api.get<CookieHealthResponse>('/super-admin/youtube-cookies').subscribe({
    next: (data) => { this.cookieHealth = data; this.loadingCookies = false; },
    error: () => { this.cookieError = true; this.loadingCookies = false; },
  });
}
```

**For Phase 21 loadProxyConfig:**
```typescript
loadProxyConfig(): void {
  this.loadingProxy = true;
  this.api.get<ProxyConfigResponse>('/super-admin/proxy-config').subscribe({
    next: (data) => { this.proxyConfig = data; this.loadingProxy = false; },
    error: () => { this.loadingProxy = false; },
  });
}
```

#### Toggle Method Pattern (lines 593–606)

**Scoring Controls reference:**
```typescript
toggleScoring(enabled: boolean): void {
  this.togglingScoring = true;
  this.api.put<{ scoring_enabled: boolean }>('/super-admin/scoring/config', { scoring_enabled: enabled }).subscribe({
    next: (data) => {
      if (this.scoringConfig) this.scoringConfig.scoring_enabled = data.scoring_enabled;
      this.togglingScoring = false;
      this.snackBar.open(`Auto-scoring ${data.scoring_enabled ? 'enabled' : 'disabled'}.`, 'Close', { duration: 3000 });
    },
    error: () => {
      this.togglingScoring = false;
      this.snackBar.open('Failed to update scoring toggle.', 'Close');
    },
  });
}
```

**For Phase 21 toggleProxy (same pattern):**
```typescript
toggleProxy(enabled: boolean): void {
  this.api.put<ProxyConfigResponse>('/super-admin/proxy-config', { proxy_enabled: enabled }).subscribe({
    next: (data) => {
      this.proxyConfig = data;
      this.snackBar.open(`Proxy ${enabled ? 'enabled' : 'disabled'}.`, 'Close', { duration: 3000 });
    },
    error: () => {
      this.snackBar.open('Failed to toggle proxy.', 'Close');
    },
  });
}
```

#### Save URL Method Pattern (lines 556–578)

**YouTube Cookies saveCookie reference:**
```typescript
saveCookie(slot: 'primary' | 'backup'): void {
  const content = slot === 'primary' ? this.newPrimaryCookie : this.newBackupCookie;
  if (!content.trim()) return;

  const payload = slot === 'primary' ? { primary: content } : { backup: content };
  if (slot === 'primary') this.savingPrimary = true;
  else this.savingBackup = true;

  this.api.put<CookieHealthResponse>('/super-admin/youtube-cookies', payload).subscribe({
    next: (updated) => {
      this.cookieHealth = updated;
      if (slot === 'primary') { this.savingPrimary = false; this.editingPrimary = false; this.newPrimaryCookie = ''; }
      else { this.savingBackup = false; this.editingBackup = false; this.newBackupCookie = ''; }
      this.snackBar.open('Cookie updated successfully.', 'Close', { duration: 3000 });
    },
    error: () => {
      if (slot === 'primary') this.savingPrimary = false;
      else this.savingBackup = false;
      this.snackBar.open('Failed to save cookie. Check your connection and try again.', 'Close');
    },
  });
}
```

**For Phase 21 saveProxyUrl (simplified to single URL, no slot distinction):**
```typescript
saveProxyUrl(): void {
  if (!this.newProxyUrl.trim()) return;
  this.savingProxyUrl = true;
  this.api.put<ProxyConfigResponse>('/super-admin/proxy-config', { proxy_url: this.newProxyUrl }).subscribe({
    next: (data) => {
      this.proxyConfig = data;
      this.savingProxyUrl = false;
      this.editingProxyUrl = false;
      this.newProxyUrl = '';
      this.snackBar.open('Proxy URL saved.', 'Close', { duration: 3000 });
    },
    error: () => {
      this.savingProxyUrl = false;
      this.snackBar.open('Failed to save proxy URL.', 'Close');
    },
  });
}
```

#### Test Proxy Connection Method (new for Phase 21)

**Pattern inspired by saveCookie but calling POST instead:**
```typescript
testProxyConnection(): void {
  this.testingProxy = true;
  this.testResult = null;  // Clear previous result
  this.api.post<ProxyTestResponse>('/super-admin/proxy-config/test', {}).subscribe({
    next: (data) => {
      this.testResult = data;
      this.testingProxy = false;
    },
    error: () => {
      this.testResult = { success: false, error: 'Test request failed', latency_ms: null };
      this.testingProxy = false;
    },
  });
}
```

#### HTML Template Pattern (lines 60–135 for YouTube Cookies)

**Existing structure to follow:**
```html
<section class="config-section">
  <div class="section-header">
    <div>
      <h2>YouTube Cookies</h2>
      <p class="section-desc">Description here.</p>
    </div>
  </div>
  <div class="section-body">
    <div *ngIf="loadingCookies" class="skeleton-block"></div>
    <ng-container *ngIf="cookieHealth && !loadingCookies">
      <!-- content here -->
    </ng-container>
  </div>
</section>
```

**For Phase 21 proxy card (insert BEFORE YouTube Cookies section):**

Insert as Section 1 with this structure:
- `<section class="config-section">` wrapper
- `<div class="section-header">` with `<h2>Residential Proxy</h2>` and description
- `<div class="section-body">` containing:
  - `*ngIf="loadingProxy"` skeleton block
  - Toggle row (copy scoring toggle structure): `<mat-slide-toggle [checked]="proxyConfig.proxy_enabled" (change)="toggleProxy($event.checked)">`
  - URL card div with `.proxy-url-card` class (disabled state when `!proxyConfig.proxy_enabled`)
  - Three URL display states (missing, configured, editing) — reuse `.url-missing`, `.url-display`, `.url-edit` classes
  - Test button and result display (only visible when enabled AND URL configured)

#### CSS Styles Pattern (lines 314–493)

**Existing reusable classes:**
```css
.config-section {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.cookie-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
}

.masked {
  font-family: monospace;
  color: var(--text-muted);
  letter-spacing: 1px;
}

.save-btn {
  background: var(--accent) !important;
  color: white !important;
}
```

**For proxy card, add new styles (use same pattern):**
```css
.proxy-toggle-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0 20px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
}

.proxy-url-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 16px;
  transition: opacity 0.2s;
  &.disabled {
    opacity: 0.5;
    pointer-events: none;
  }
}

.url-edit input {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: monospace;
  font-size: 12px;
}

.test-result {
  font-size: 13px;
  padding: 8px;
  border-radius: 4px;
  &.success {
    background: rgba(46, 204, 113, 0.1);
    color: #2ECC71;
  }
  &.error {
    background: rgba(231, 76, 60, 0.1);
    color: #E74C3C;
  }
}
```

---

## Shared Patterns

### Authentication (All Endpoints)
**Source:** `backend/app/api/v1/deps.py` via `get_current_superadmin` dependency

**Apply to:** All 3 proxy endpoints (GET, PUT, POST test)

```python
# Pattern: Every endpoint has this parameter
async def endpoint_name(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
```

This enforces SuperAdmin-only access at the function level. Non-SuperAdmins receive 403 Forbidden automatically.

### Encryption/Decryption
**Source:** `backend/app/core/security.py` (lines 28–33)

**Apply to:** All proxy endpoints handling `proxy_url_encrypted`

```python
# Encrypt before storage
config.proxy_url_encrypted = encrypt_token(payload.proxy_url)

# Decrypt for masking/testing
try:
    decrypted = decrypt_token(config.proxy_url_encrypted)
except Exception:
    # Safe fallback — never expose decryption error details
    return error_response("Failed to decrypt proxy URL")
```

Never log decrypted values. Never return decrypted values in API responses.

### Singleton SystemConfig Read/Update Pattern
**Source:** `backend/app/api/v1/endpoints/super_admin.py` (lines 132–152, 176–202)

**Apply to:** All proxy endpoints that modify config

```python
# Read
result = await db.execute(select(SystemConfig).limit(1))
config = result.scalar_one_or_none()

# Validate initialization
if config is None:
    raise HTTPException(status_code=500, detail="System config not initialized")

# Modify
config.proxy_enabled = payload.proxy_enabled
config.proxy_url_encrypted = encrypt_token(payload.proxy_url)

# Persist atomically
db.add(config)
await db.commit()
await db.refresh(config)
```

### Angular API Subscription Pattern
**Source:** `frontend/src/app/features/configuration/pages/admin.component.ts` (lines 531–577)

**Apply to:** All proxy data-fetching methods

```typescript
methodName(): void {
  this.loadingProxy = true;  // Disable UI
  this.api.get<ProxyConfigResponse>('/super-admin/proxy-config').subscribe({
    next: (data) => {
      this.proxyConfig = data;
      this.loadingProxy = false;
    },
    error: () => {
      this.loadingProxy = false;  // Re-enable UI even on error
    },
  });
}
```

Always reset loading flag in both success and error branches. Always unsubscribe if method is called multiple times (use `takeUntil` in production for cleanup).

### MatSnackBar Toast Pattern
**Source:** `frontend/src/app/features/configuration/pages/admin.component.ts` (lines 570, 599, 633)

**Apply to:** All user-facing success/error feedback in proxy component

```typescript
this.snackBar.open('Proxy enabled.', 'Close', { duration: 3000 });
this.snackBar.open('Failed to toggle proxy.', 'Close');
```

3-second duration is standard. Always include 'Close' button for manual dismiss.

---

## No Analog Found

All three files (3 backend endpoints + 1 frontend section) have direct analogs in existing YouTube Cookies / Scoring Controls endpoints. Pattern coverage is 100%.

---

## Metadata

**Analog search scope:** 
- `backend/app/api/v1/endpoints/super_admin.py` (YouTube Cookies GET/PUT, Scoring Controls toggle)
- `backend/app/core/security.py` (encrypt_token/decrypt_token)
- `frontend/src/app/features/configuration/pages/admin.component.ts` (cookie card section, scoring toggle)
- `backend/app/models/system_config.py` (SystemConfig model with proxy fields)

**Files scanned:** 4 existing files containing proven patterns

**Pattern extraction date:** 2026-05-15

**Key insight:** The YouTube Cookies endpoints (GET/PUT) are the gold standard for this phase. They already solved encryption, singleton config management, and partial update patterns. Copy that structure directly for proxy endpoints. The frontend cookie card and scoring toggle demonstrate the exact UX patterns needed (toggle with immediate PUT, edit mode, masked display). Reuse CSS classes and component state management patterns without variation.

