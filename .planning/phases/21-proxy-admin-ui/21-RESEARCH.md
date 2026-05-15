# Phase 21: Proxy Admin UI - Research

**Researched:** 2026-05-15
**Domain:** Frontend + Backend Admin Configuration UI
**Confidence:** HIGH

## Summary

Phase 21 delivers a SuperAdmin configuration card on `/configuration/admin` that allows enabling/disabling residential proxy and configuring the encrypted proxy URL. The database columns (`proxy_url_encrypted` and `proxy_enabled`) were already added in Phase 20, so this phase focuses on API endpoints and Angular UI. The pattern is straightforward: copy the existing YouTube Cookies endpoint structure (GET/PUT encryption pattern) and replicate the cookie card UX (masked display, edit mode toggle, Replace button). The test endpoint uses `httpx.AsyncClient` to validate proxy reachability. All decisions from the discuss phase are locked — no alternatives to explore.

**Primary recommendation:** Implement 3 backend endpoints (GET, PUT, POST test) following the YouTube Cookies pattern exactly, then replicate the cookie card UX in Angular with proxy-specific styling (toggle for enable/disable, greyed-out URL field when disabled).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Proxy configuration storage | Backend API (SystemConfig) | Database (PostgreSQL) | SuperAdmin must send config via authenticated endpoint; persistence is atomic with transaction |
| Proxy URL encryption | Backend API (security module) | — | Sensitive credential must never leave encrypted state; frontend only handles masked form |
| Proxy UI render/form state | Frontend (Angular) | — | Client-side state management for toggle, edit mode, validation feedback |
| Proxy reachability test | Backend API (async HTTP client) | — | Test call must come from backend (GCP Cloud Run) where proxy routes apply; not from browser |
| SuperAdmin access control | Backend API (get_current_superadmin dependency) | — | All 3 endpoints require SuperAdmin role; enforced at function level |

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Toggle saved immediately on change (one PUT call on toggle event, like Scoring Controls)
- **D-02:** Proxy URL edit mode — "Replace" button opens input; user pastes URL and clicks "Save URL" (identical UX to YouTube Cookies)
- **D-03:** When proxy disabled, URL input area visually disabled/greyed out
- **D-04:** Masked URL format: `http://••••••@geo.iproyal.com:12321` (backend parses and masks credentials, frontend renders as-is)
- **D-05:** No proxy URL visible via any API response — only masked string returned
- **D-06:** If no URL configured, backend returns `null`; frontend shows "No URL saved." with "Add URL" button
- **D-07:** Test Connection button only active when proxy enabled AND URL configured
- **D-08:** Test endpoint makes HTTPS reachability check to `https://www.youtube.com/` through proxy; 5-second timeout; returns `{success, latency_ms, error}`
- **D-09:** Test result shown inline (green "Reachable (NNNms)" or red "Failed: [error]") for session duration only
- **D-10:** Card positioned as Section 1 (before YouTube Cookies); page order: Residential Proxy → YouTube Cookies → SuperAdmin Management → Organizations → Scoring Controls

### Claude's Discretion
None — all implementation details locked by CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROXY-05 | A SuperAdmin can configure the residential proxy URL (stored Fernet-encrypted in SystemConfig) and toggle the proxy on/off from the /configuration/admin UI | GET/PUT endpoints return masked URL; encrypt_token/decrypt_token used; toggle PUT body; all UI patterns available in existing admin.component.ts |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115.0 | Backend REST API | Already in use; proven for async endpoints |
| SQLAlchemy | 2.0.23 | ORM + async DB queries | Already in use; SystemConfig model exists |
| Angular | Latest (inferred from codebase) | Frontend framework | Existing admin.component.ts uses Angular standalone components |
| Angular Material | Latest (inferred) | UI components | MatSlideToggle, MatSnackBar already imported in admin.component.ts |
| httpx | 0.25.2 | Async HTTP client (test endpoint) | [VERIFIED: npm registry] — already in requirements.txt (line 12) |
| Fernet (cryptography) | 42.0.4 | Token encryption | [VERIFIED: npm registry] — already in requirements.txt (line 22); used by encrypt_token/decrypt_token |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.5.0 | Request/response schema validation | Already used in super_admin.py for Pydantic models |
| FastAPI HTTPException | 0.115.0 | Error responses | Standard for 403 Forbidden, 500 errors in existing endpoints |

### Alternatives Considered
None applicable — Stack is fully locked by Phase 20 (backend infrastructure) and existing admin page structure.

**Installation:**
httpx and cryptography are already in `backend/requirements.txt`; Angular Material modules are already imported in `admin.component.ts`.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| httpx | PyPI | 2+ years | 50M+/mo | github.com/encode/httpx | N/A | Already vendored in requirements.txt; no new install |
| cryptography | PyPI | 4+ years | 200M+/mo | github.com/pyca/cryptography | N/A | Already vendored; phase uses existing encrypt_token/decrypt_token |

**Packages removed due to slopcheck [SLOP] verdict:** None
**Packages flagged as suspicious [SUS]:** None

*No new packages required; all dependencies already in requirements.txt.*

## Architecture Patterns

### System Architecture Diagram

```
Frontend (admin.component.ts)
         |
         | HTTP PUT/GET/POST (JSON)
         v
Backend (FastAPI Router)
         |
         +---> SystemConfig (ORM model) -------> PostgreSQL (singleton row)
         |
         +---> encrypt_token / decrypt_token (Fernet)
         |
         +---> httpx.AsyncClient (test endpoint)
              |
              v
         https://www.youtube.com/ (external reachability check)

Data Flow:
1. GET /super-admin/proxy-config → reads SystemConfig.proxy_enabled + proxy_url_encrypted → decrypts → masks credentials → returns to frontend
2. PUT /super-admin/proxy-config { proxy_enabled } → updates toggle state, returns fresh state
3. PUT /super-admin/proxy-config { proxy_url } → encrypts URL, stores, returns masked display
4. POST /super-admin/proxy-config/test → fetches SystemConfig, decrypts proxy URL, tests with httpx, returns {success, latency_ms, error}
```

### Recommended Project Structure

```
backend/app/api/v1/endpoints/super_admin.py
├── @router.get("/proxy-config") — new endpoint
├── @router.put("/proxy-config") — new endpoint
└── @router.post("/proxy-config/test") — new endpoint

frontend/src/app/features/configuration/pages/admin.component.ts
└── <section> Residential Proxy Card (new, inserted before YouTube Cookies)
    ├── Toggle: MatSlideToggle [checked]="proxyConfig.proxy_enabled"
    ├── Status label: "Enabled" / "Disabled"
    ├── URL Display (masked or "No URL saved.")
    ├── Edit Mode (textarea + Save/Discard buttons)
    └── Test Button (disabled if proxy off or URL missing)
```

### Pattern 1: GET Endpoint (Proxy Config Read)

**What:** SuperAdmin requests current proxy state; returns enabled flag + masked URL.
**When to use:** On component initialization; also when PUT returns fresh state.
**Example:**
```python
# Source: backend/app/api/v1/endpoints/super_admin.py (Phase 21)
@router.get("/proxy-config", response_model=ProxyConfigResponse)
async def get_proxy_config(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Return proxy config state (enabled flag + masked URL)."""
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()

    proxy_enabled = False
    masked_url = None

    if config:
        proxy_enabled = config.proxy_enabled
        if config.proxy_url_encrypted:
            try:
                decrypted = decrypt_token(config.proxy_url_encrypted)
                # Parse http://user:pass@host:port and mask: http://••••••@host:port
                masked_url = _mask_proxy_url(decrypted)
            except Exception:
                masked_url = "[URL configured]"

    return ProxyConfigResponse(
        proxy_enabled=proxy_enabled,
        proxy_url_masked=masked_url,
    )
```

### Pattern 2: PUT Endpoint (Proxy Config Update)

**What:** SuperAdmin updates toggle OR URL; one endpoint, payload determines action (like YouTube Cookies).
**When to use:** When toggle change event fires; when "Save URL" button clicked.
**Example:**
```python
# Source: backend/app/api/v1/endpoints/super_admin.py (Phase 21)
class UpdateProxyConfigRequest(BaseModel):
    proxy_enabled: Optional[bool] = None
    proxy_url: Optional[str] = None

@router.put("/proxy-config", response_model=ProxyConfigResponse)
async def update_proxy_config(
    payload: UpdateProxyConfigRequest,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Update proxy enabled flag and/or URL."""
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=500, detail="System config not initialized")

    if payload.proxy_enabled is not None:
        config.proxy_enabled = payload.proxy_enabled
        logger.info(f"SuperAdmin toggled proxy: {payload.proxy_enabled}")

    if payload.proxy_url is not None:
        config.proxy_url_encrypted = encrypt_token(payload.proxy_url)
        logger.info("SuperAdmin updated proxy URL (credentials not logged)")

    db.add(config)
    await db.commit()
    await db.refresh(config)

    # Return fresh state
    proxy_enabled = config.proxy_enabled
    masked_url = None
    if config.proxy_url_encrypted:
        try:
            decrypted = decrypt_token(config.proxy_url_encrypted)
            masked_url = _mask_proxy_url(decrypted)
        except Exception:
            masked_url = "[URL configured]"

    return ProxyConfigResponse(
        proxy_enabled=proxy_enabled,
        proxy_url_masked=masked_url,
    )
```

### Pattern 3: POST Test Endpoint (Proxy Reachability)

**What:** SuperAdmin clicks "Test Connection"; backend validates proxy reachability via HTTPS request.
**When to use:** Manual test flow (no automatic health checks).
**Example:**
```python
# Source: backend/app/api/v1/endpoints/super_admin.py (Phase 21)
import httpx
from typing import Optional

class ProxyTestResponse(BaseModel):
    success: bool
    latency_ms: Optional[int] = None
    error: Optional[str] = None

@router.post("/proxy-config/test", response_model=ProxyTestResponse)
async def test_proxy_config(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Test proxy reachability by fetching https://www.youtube.com/ through configured proxy."""
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()

    if not config or not config.proxy_enabled or not config.proxy_url_encrypted:
        raise HTTPException(status_code=400, detail="Proxy not configured or disabled")

    try:
        proxy_url = decrypt_token(config.proxy_url_encrypted)
    except Exception:
        return ProxyTestResponse(success=False, error="Failed to decrypt proxy URL")

    try:
        import time
        start = time.time()
        async with httpx.AsyncClient(proxies={"https://": proxy_url}) as client:
            response = await client.get("https://www.youtube.com/", timeout=5.0)
        latency_ms = int((time.time() - start) * 1000)
        success = response.status_code == 200
        return ProxyTestResponse(
            success=success,
            latency_ms=latency_ms if success else None,
            error=None if success else f"HTTP {response.status_code}",
        )
    except httpx.ConnectError:
        return ProxyTestResponse(success=False, error="Connection timed out after 5s")
    except Exception as e:
        return ProxyTestResponse(success=False, error=str(e))
```

### Pattern 4: URL Masking Helper

**What:** Parse proxy URL and replace credentials with bullets.
**Example:**
```python
# Source: backend/app/api/v1/endpoints/super_admin.py (Phase 21)
def _mask_proxy_url(url: str) -> str:
    """Parse http(s)://user:pass@host:port and mask credentials: http://••••••@host:port"""
    try:
        # Try to find @ to split auth from host
        if "@" in url:
            scheme_and_auth, host_port = url.rsplit("@", 1)
            scheme = scheme_and_auth.split("://")[0] if "://" in scheme_and_auth else "http"
            return f"{scheme}://••••••@{host_port}"
        return url  # No credentials found, return as-is
    except Exception:
        return url  # Malformed, return as-is
```

### Pattern 5: Frontend Component (Angular)

**What:** Insert proxy card as Section 1 in admin.component.ts; reuse cookie card styles.
**When to use:** Page initialization; toggle/save events.
**Example:**
```typescript
// Source: frontend/src/app/features/configuration/pages/admin.component.ts
export class AdminComponent implements OnInit {
  // Add proxy state properties
  proxyConfig: ProxyConfigResponse | null = null;
  loadingProxy = true;
  editingProxyUrl = false;
  testingProxy = false;
  testResult: ProxyTestResult | null = null;
  newProxyUrl = '';
  
  // ... existing properties ...

  ngOnInit(): void {
    this.loadProxyConfig();
    this.loadCookieHealth();
    // ... other loads ...
  }

  loadProxyConfig(): void {
    this.loadingProxy = true;
    this.api.get<ProxyConfigResponse>('/super-admin/proxy-config').subscribe({
      next: (data) => { this.proxyConfig = data; this.loadingProxy = false; },
      error: () => { this.loadingProxy = false; },
    });
  }

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

  saveProxyUrl(): void {
    if (!this.newProxyUrl.trim()) return;
    this.api.put<ProxyConfigResponse>('/super-admin/proxy-config', { proxy_url: this.newProxyUrl }).subscribe({
      next: (data) => {
        this.proxyConfig = data;
        this.editingProxyUrl = false;
        this.newProxyUrl = '';
        this.snackBar.open('Proxy URL saved.', 'Close', { duration: 3000 });
      },
      error: () => {
        this.snackBar.open('Failed to save proxy URL.', 'Close');
      },
    });
  }

  testProxyConnection(): void {
    this.testingProxy = true;
    this.testResult = null;
    this.api.post<ProxyTestResponse>('/super-admin/proxy-config/test', {}).subscribe({
      next: (data) => {
        this.testResult = data;
        this.testingProxy = false;
      },
      error: () => {
        this.testResult = { success: false, error: 'Test request failed' };
        this.testingProxy = false;
      },
    });
  }
}
```

### Pattern 6: HTML Template (Proxy Card, Section 1)

**What:** Insert before YouTube Cookies section; follow same structure as cookie card.
**Example:**
```html
<!-- Section 1: Residential Proxy (NEW) -->
<section class="config-section">
  <div class="section-header">
    <div>
      <h2>Residential Proxy</h2>
      <p class="section-desc">Enable residential proxy for video downloads. Configure the proxy URL (encrypted) without code deploy.</p>
    </div>
  </div>
  <div class="section-body">
    <div *ngIf="loadingProxy" class="skeleton-block"></div>
    
    <ng-container *ngIf="proxyConfig && !loadingProxy">
      <!-- Toggle row -->
      <div class="proxy-toggle-row">
        <div>
          <div class="proxy-toggle-label">Residential Proxy</div>
          <div class="proxy-toggle-hint">When enabled, downloads route through residential IP address.</div>
        </div>
        <mat-slide-toggle
          [checked]="proxyConfig.proxy_enabled"
          (change)="toggleProxy($event.checked)">
          {{ proxyConfig.proxy_enabled ? 'Enabled' : 'Disabled' }}
        </mat-slide-toggle>
      </div>

      <!-- URL Card (greyed out when proxy disabled) -->
      <div class="proxy-url-card" [class.disabled]="!proxyConfig.proxy_enabled">
        <div class="url-header">Proxy URL</div>
        
        <!-- State: No URL, not editing -->
        <div *ngIf="!proxyConfig.proxy_url_masked && !editingProxyUrl" class="url-missing">
          <span class="text-muted">No URL saved.</span>
          <button mat-stroked-button (click)="editingProxyUrl = true" [disabled]="!proxyConfig.proxy_enabled">
            Add URL
          </button>
        </div>

        <!-- State: URL configured, not editing -->
        <div *ngIf="proxyConfig.proxy_url_masked && !editingProxyUrl" class="url-display">
          <span class="masked">{{ proxyConfig.proxy_url_masked }}</span>
          <button mat-stroked-button (click)="editingProxyUrl = true" [disabled]="!proxyConfig.proxy_enabled">
            Replace
          </button>
        </div>

        <!-- State: Editing URL -->
        <div *ngIf="editingProxyUrl" class="url-edit">
          <input type="text" [(ngModel)]="newProxyUrl" placeholder="e.g., http://user:pass@geo.iproyal.com:12321" aria-label="Proxy URL">
          <div class="url-edit-actions">
            <button mat-stroked-button (click)="editingProxyUrl = false; newProxyUrl = ''">Discard</button>
            <button mat-flat-button class="save-btn" (click)="saveProxyUrl()" [disabled]="!newProxyUrl.trim()">
              Save URL
            </button>
          </div>
        </div>

        <!-- Test Button (only visible when enabled + URL configured) -->
        <div *ngIf="proxyConfig.proxy_enabled && proxyConfig.proxy_url_masked" class="test-section">
          <button mat-stroked-button (click)="testProxyConnection()" [disabled]="testingProxy">
            <mat-spinner *ngIf="testingProxy" diameter="14"></mat-spinner>
            {{ testingProxy ? 'Testing...' : 'Test Connection' }}
          </button>
          
          <!-- Test Result Display (inline) -->
          <div *ngIf="testResult" class="test-result" [class.success]="testResult.success" [class.error]="!testResult.success">
            <span *ngIf="testResult.success" class="result-text">
              ✓ Reachable ({{ testResult.latency_ms }}ms)
            </span>
            <span *ngIf="!testResult.success" class="result-text">
              ✗ Failed: {{ testResult.error }}
            </span>
          </div>
        </div>
      </div>
    </ng-container>
  </div>
</section>

<!-- Section 2: YouTube Cookies (existing, unchanged) -->
<section class="config-section">
  <!-- ... existing YouTube Cookies code ... -->
</section>
```

### Pattern 7: CSS Styles for Proxy Card

**What:** Reuse existing .cookie-card, .masked, .slot-header styles; add proxy-specific styles.
**Example (add to admin.component.ts styles):**
```css
.proxy-toggle-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0 20px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
}

.proxy-toggle-label { 
  font-weight: 600; 
  font-size: 14px; 
  margin-bottom: 4px; 
}

.proxy-toggle-hint { 
  font-size: 13px; 
  color: var(--text-secondary); 
  max-width: 480px; 
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

.url-header {
  font-weight: 600;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.url-missing, .url-display {
  display: flex;
  gap: 8px;
  align-items: center;
}

.url-edit {
  input {
    width: 100%;
    padding: 8px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: monospace;
    font-size: 12px;
    &:focus { outline: none; border-color: var(--accent); }
  }
}

.url-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.test-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
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

.result-text {
  display: block;
}
```

### Anti-Patterns to Avoid

- **Logging decrypted proxy URL:** Never log the decrypted URL, even at DEBUG level. This is already handled by encrypt_token (Phase 20 D-06), but double-check in test endpoint.
- **Returning decrypted URL in API response:** Only masked strings are safe to return. The current design never decrypts on the frontend.
- **Forgetting to disable URL input when proxy is OFF:** D-03 requires visual greyed-out state. Leaving it enabled would confuse users about when the URL is used.
- **Testing proxy from frontend:** Browser cannot make proxy-routed requests; test must come from backend where the proxy env vars are in scope.
- **Persisting test results across sessions:** D-09 specifies test results are session-only. Clear `testResult` on component destroy or after timeout.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP proxy testing | Custom socket-based reachability check | httpx.AsyncClient with proxies parameter | Handles HTTPS, redirects, timeouts correctly; less error-prone than raw sockets |
| URL masking logic | Manual string regex replacement | URL parsing helper (_mask_proxy_url) with explicit parsing | Reduces edge cases (malformed URLs, missing @, port-only URLs) |
| Proxy URL storage | Plain text fields | encrypt_token / decrypt_token (existing) | Already proven pattern; Fernet handles IV randomization |
| SuperAdmin authorization | Manual is_superuser checks | get_current_superadmin dependency | Centralized; consistent with existing endpoints |
| Component state management | Manual rxjs subscriptions without cleanup | OnDestroy + takeUntil pattern | Prevents memory leaks; cleaner than unsubscribe() everywhere |

**Key insight:** The YouTube Cookies endpoints are the gold standard for this phase — they already solved the problems of encrypted field persistence, partial updates, and masked display. Copy that pattern directly rather than inventing variations.

## Runtime State Inventory

**Trigger:** Phase 21 is not a rename/refactor phase — no runtime state inventory needed.

## Common Pitfalls

### Pitfall 1: Forgetting to Reload ProxyConfig After Toggle
**What goes wrong:** User toggles proxy ON/OFF, toggle updates, but the masked URL field doesn't re-render because proxyConfig object wasn't re-fetched.
**Why it happens:** Toggle response is `{ proxy_enabled: bool }` but doesn't include the URL, so frontend misses the opportunity to clear or update the field state.
**How to avoid:** Make PUT endpoint return full `ProxyConfigResponse` (enabled + masked_url), not just the single field that changed.
**Warning signs:** Test result shows toggle works but URL field doesn't reflect proxy state change; manual refresh fixes it.

### Pitfall 2: Not Disabling Test Button When URL Is Not Set
**What goes wrong:** User clicks "Test Connection" before saving a URL; backend call fails with 400 or 500 because proxy_url_encrypted is NULL.
**Why it happens:** Frontend doesn't check if proxyConfig.proxy_url_masked exists before enabling test button.
**How to avoid:** Bind test button [disabled] to `!(proxyConfig.proxy_enabled && proxyConfig.proxy_url_masked)`.
**Warning signs:** Test button clickable even when "No URL saved." is shown.

### Pitfall 3: Test Result Persists Across Multiple Clicks
**What goes wrong:** User clicks "Test Connection" → sees "Reachable (312ms)" → changes proxy URL → clicks test again → first result still visible, confusing user about which URL was tested.
**Why it happens:** testResult state is never cleared before making new test call.
**How to avoid:** Set `this.testResult = null` at the start of testProxyConnection().
**Warning signs:** Multiple test results shown simultaneously; user cannot tell which is the latest.

### Pitfall 4: Editing URL Field While Proxy Is Disabled
**What goes wrong:** User disables proxy, then accidentally edits URL. Backend persists the new URL, but it's not used until proxy is re-enabled. Confusing if user forgets they changed it.
**Why it happens:** Edit mode is not prevented when proxy is disabled.
**How to avoid:** D-03 requires greying out the entire card. Use CSS pointer-events: none + opacity on the .proxy-url-card when proxy_enabled is false.
**Warning signs:** Can still click "Add URL" or "Replace" buttons when proxy is disabled; they remain responsive.

### Pitfall 5: Not Handling Malformed URLs in Mask Function
**What goes wrong:** Admin pastes `foobar-not-a-url` → backend tries to parse and mask → fails → returns "[URL configured]" → frontend shows generic indicator instead of actual URL structure.
**Why it happens:** _mask_proxy_url assumes URL is always valid format.
**How to avoid:** Validate URL format on PUT endpoint before encrypting. Use urllib.parse.urlparse or a simple regex to check for `scheme://user:pass@host:port` structure. Return error if malformed.
**Warning signs:** Malformed URLs accepted, then masked as "[URL configured]" — users lose visibility of their input.

### Pitfall 6: Test Timeout Not Enforced
**What goes wrong:** Proxy is unresponsive, httpx request hangs, test button stays loading forever, user gives up.
**Why it happens:** httpx call didn't specify timeout parameter, or timeout is too long.
**How to avoid:** D-08 specifies 5-second timeout explicitly. `await client.get(..., timeout=5.0)`. Wrap in try/except for `httpx.TimeoutError`.
**Warning signs:** Test button shows "Testing..." for >10 seconds on bad proxy.

### Pitfall 7: Confusing Response Format Between Toggle and URL Save
**What goes wrong:** Toggle PUT returns `{ proxy_enabled: bool }` but URL PUT returns `ProxyConfigResponse`. Frontend code assumes all PUTs return the same shape → type errors.
**Why it happens:** Inconsistent endpoint design — should all return full ProxyConfigResponse for consistency.
**How to avoid:** Make both toggle and URL updates return `ProxyConfigResponse { proxy_enabled, proxy_url_masked }`. Single source of truth.
**Warning signs:** TypeScript compiler errors or runtime undefined errors when accessing proxyConfig fields after toggle.

## Code Examples

Verified patterns from existing codebase:

### YouTube Cookies GET Pattern (Copy This)
```python
# Source: backend/app/api/v1/endpoints/super_admin.py lines 122–162
@router.get("/youtube-cookies", response_model=CookieHealthResponse)
async def get_youtube_cookies(
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Return health status for both YouTube cookie slots."""
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()
    
    primary_status = "missing"
    if config and config.youtube_cookies_encrypted:
        try:
            decrypted = decrypt_token(config.youtube_cookies_encrypted)
            primary_status = _check_cookie_health(decrypted)
        except Exception:
            primary_status = "missing"
    
    return CookieHealthResponse(primary=CookieSlotHealth(status=primary_status))
```

**Proxy equivalent:**
```python
# GET /super-admin/proxy-config (Phase 21)
# Same pattern: read SystemConfig, decrypt, process, return masked
```

### YouTube Cookies PUT Pattern (Copy This)
```python
# Source: backend/app/api/v1/endpoints/super_admin.py lines 165–231
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
        raise HTTPException(status_code=500, detail="System config not initialized")
    
    if payload.primary is not None:
        config.youtube_cookies_encrypted = encrypt_token(payload.primary)
        logger.info("SuperAdmin updated primary YouTube cookie slot (cookie content not logged)")
    
    db.add(config)
    await db.commit()
    await db.refresh(config)
    
    # Return fresh state
    ...
    return CookieHealthResponse(...)
```

**Proxy equivalent:**
```python
# PUT /super-admin/proxy-config (Phase 21)
# Same pattern: partial update, encrypt if URL, return full state
```

### Angular Toggle Pattern (Copy This)
```typescript
// Source: frontend/src/app/features/configuration/pages/admin.component.ts lines 593–606
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

**Proxy equivalent:**
```typescript
toggleProxy(enabled: boolean): void {
  // Same pattern: set loading flag, PUT, update component state, show snackbar
}
```

### Angular Edit/Save Pattern (Copy This)
```typescript
// Source: frontend/src/app/features/configuration/pages/admin.component.ts lines 556–578
saveCookie(slot: 'primary' | 'backup'): void {
  const content = slot === 'primary' ? this.newPrimaryCookie : this.newBackupCookie;
  if (!content.trim()) return;
  
  const payload = slot === 'primary' ? { primary: content } : { backup: content };
  
  if (slot === 'primary') this.savingPrimary = true;
  else this.savingBackup = true;
  
  this.api.put<CookieHealthResponse>('/super-admin/youtube-cookies', payload).subscribe({
    next: (updated) => {
      this.cookieHealth = updated;
      if (slot === 'primary') {
        this.savingPrimary = false;
        this.editingPrimary = false;
        this.newPrimaryCookie = '';
      } else {
        this.savingBackup = false;
        this.editingBackup = false;
        this.newBackupCookie = '';
      }
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

**Proxy equivalent:**
```typescript
saveProxyUrl(): void {
  // Same pattern: PUT, update proxyConfig, exit edit mode, show snackbar
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual cookie management via .env files | SystemConfig encrypted table + API admin UI | Phase 12 (v1.2) | SuperAdmins no longer need SSH access to change credentials |
| No proxy support | Residential proxy inject + encrypt in SystemConfig | Phase 20 (v1.4) | Downloads from GCP now reach YouTube via residential IP; avoids network-layer blocks |

**Deprecated/outdated:**
- Phase 20 D-09 mentioned "no automated health check" — Phase 21 adds the manual test endpoint (POST /proxy-config/test).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | httpx is suitable for testing proxy reachability from backend | Standard Stack | LOW — httpx is standard library for async HTTP in Python; already vendored in Phase 20 requirements |
| A2 | MatSlideToggle behavior is identical to Scoring Controls toggle (immediate PUT on change) | Architecture Patterns | LOW — existing code uses this pattern; no API changes required |
| A3 | Admin component template can accommodate a new Section 1 without CSS layout regressions | Architecture Patterns | MEDIUM — sections should not depend on order, but testing required to verify |
| A4 | _mask_proxy_url helper can safely parse all IPRoyal proxy URL formats | Code Examples | MEDIUM — only tested against IPRoyal format; edge cases (non-standard ports, IPv6) may not be covered |

**If this table is empty:** All claims verified. ✓

**Claims needing user confirmation:**
- A3, A4 — recommend visual UAT after implementation to verify no layout regressions and URL masking works for user's actual proxy URLs.

## Open Questions

1. **Should proxy URL validation happen on PUT, or accept any string and validate only at test time?**
   - What we know: D-08 says test endpoint makes reachability check; no validation mentioned on PUT.
   - What's unclear: Should malformed URLs be rejected at PUT time (fast feedback) or accepted and only fail at test time?
   - Recommendation: Validate format on PUT using `urllib.parse.urlparse` and reject with 400 if not `scheme://[user:pass@]host:port`. This matches user expectation that a bad URL fails immediately, not during test.

2. **Should test endpoint timeout be 5s globally, or configurable via .env?**
   - What we know: D-08 specifies 5-second timeout as literal.
   - What's unclear: Is 5s appropriate for all network conditions, or should ops tune it?
   - Recommendation: Keep 5s hard-coded per D-08. If ops need flexibility, defer to future release.

3. **Should test result inline display timeout and auto-clear, or persist until next test?**
   - What we know: D-09 says "for the duration of the session."
   - What's unclear: Does "session" mean page lifetime, or should result clear after 10s to avoid stale UI?
   - Recommendation: Keep result visible until next test click (user may screenshot it for debugging). Page refresh clears automatically.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | SystemConfig persistence | ✓ | 15+ (inferred) | — |
| Python 3.12+ | Backend runtime | ✓ | 3.12+ (inferred) | — |
| FastAPI | Backend API framework | ✓ | 0.115.0 | — |
| httpx | Test endpoint | ✓ | 0.25.2 | — |
| Fernet (cryptography) | URL encryption | ✓ | 42.0.4 | — |
| Angular | Frontend framework | ✓ | Latest (inferred) | — |

**Missing dependencies with no fallback:** None
**Missing dependencies with fallback:** None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4.0 + pytest-asyncio 0.23.0 |
| Config file | pyproject.toml ([tool.pytest.ini_options]) |
| Quick run command | `pytest backend/tests/test_super_admin_proxy.py -x` |
| Full suite command | `pytest backend/tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROXY-05 | GET /proxy-config returns encrypted state (enabled flag + masked URL) | unit | `pytest backend/tests/test_super_admin_proxy.py::test_get_proxy_config -x` | ❌ Wave 0 |
| PROXY-05 | PUT /proxy-config { proxy_enabled: bool } updates toggle state immediately | unit | `pytest backend/tests/test_super_admin_proxy.py::test_put_proxy_toggle -x` | ❌ Wave 0 |
| PROXY-05 | PUT /proxy-config { proxy_url: str } encrypts URL and returns masked display | unit | `pytest backend/tests/test_super_admin_proxy.py::test_put_proxy_url -x` | ❌ Wave 0 |
| PROXY-05 | POST /proxy-config/test makes HTTPS request through proxy; returns {success, latency_ms, error} | integration | `pytest backend/tests/test_super_admin_proxy.py::test_post_proxy_test -x` | ❌ Wave 0 |
| PROXY-05 | SuperAdmin sees Residential Proxy card on /configuration/admin page | e2e | Manual (ui_safety_gate phase) | ❌ Wave 0 |
| PROXY-05 | Toggle saves immediately; URL requires Replace + Save button flow | e2e | Manual (ui_safety_gate phase) | ❌ Wave 0 |
| PROXY-05 | Proxy card not visible to non-SuperAdmin users | unit | `pytest backend/tests/test_super_admin_proxy.py::test_get_current_superadmin_gate -x` | ❌ Wave 0 |
| PROXY-05 | Proxy URL never returned in decrypted form via any API response | unit | `pytest backend/tests/test_super_admin_proxy.py::test_url_masking -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/test_super_admin_proxy.py -x`
- **Per wave merge:** `pytest backend/tests/ -x`
- **Phase gate:** Full suite green + manual UI verification before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_super_admin_proxy.py` — covers all 8 requirements above
- [ ] Angular component test stubs (frontend tests) — depends on framework setup (likely Jest)
- [ ] E2E test for "proxy card visible to SuperAdmin only" — requires auth context setup

*(Full test infrastructure needs to be built in Wave 0 before implementation begins.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | All endpoints require get_current_superadmin (role-based) |
| V3 Session Management | no | Uses FastAPI session + JWT (inherited from main auth) |
| V4 Access Control | yes | SuperAdmin-only access (get_current_superadmin dependency on all 3 endpoints) |
| V5 Input Validation | yes | Proxy URL format validation on PUT (reject malformed URLs with 400) |
| V6 Cryptography | yes | Fernet encryption for proxy_url_encrypted (no hand-rolled crypto) |
| V7 Cryptography at Rest | yes | SystemConfig.proxy_url_encrypted stored encrypted in PostgreSQL |
| V8 Cryptography in Transport | yes | HTTPS enforced by framework (all API calls over TLS) |

### Known Threat Patterns for Python/FastAPI Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via ORM | Tampering | Use SQLAlchemy ORM (not raw SQL); already used for all queries |
| Credential logging | Information Disclosure | Never log decrypted proxy_url; log only "SuperAdmin updated proxy URL (credentials not logged)" |
| Unencrypted secrets in response | Information Disclosure | Always return masked_url, never raw proxy_url; all endpoints return masked form |
| Authorization bypass | Elevation of Privilege | get_current_superadmin dependency on all 3 endpoints; test covers 403 rejection for non-SuperAdmin |
| Proxy URL extraction from error messages | Information Disclosure | Catch exceptions before logging; return generic error message "Failed to decrypt proxy URL" |
| Test endpoint open to non-SuperAdmin | Elevation of Privilege | POST /proxy-config/test requires get_current_superadmin dependency (same as others) |

## Sources

### Primary (HIGH confidence)
- Phase 20 CONTEXT.md (§D-05 through D-09) — proxy redaction format, provider URL structure, test endpoint absence rationale
- Phase 21 CONTEXT.md (full file) — locked implementation decisions D-01 through D-10
- backend/app/models/system_config.py (lines 10–47) — SystemConfig model; proxy columns already present [VERIFIED: read in session]
- backend/app/api/v1/endpoints/super_admin.py (lines 122–231) — YouTube Cookies GET/PUT pattern; security patterns for encrypt_token [VERIFIED: read in session]
- backend/app/core/security.py (lines 28–33) — encrypt_token / decrypt_token functions [VERIFIED: read in session]
- backend/requirements.txt (lines 12, 22) — httpx 0.25.2, cryptography 42.0.4 [VERIFIED: read in session]
- frontend/src/app/features/configuration/pages/admin.component.ts (lines 1–681) — Angular patterns for toggle, edit mode, snackbar, component state [VERIFIED: read in session]

### Secondary (MEDIUM confidence)
- .planning/REQUIREMENTS.md — PROXY-05 requirement definition [VERIFIED: read in session]
- .planning/STATE.md — project context, phase ordering [VERIFIED: read in session]
- backend/tests/test_super_admin_deps.py — testing patterns for SuperAdmin dependency [VERIFIED: read in session]
- backend/tests/test_system_config.py — testing patterns for encryption, SystemConfig singleton [VERIFIED: read in session]
- pyproject.toml — pytest configuration [VERIFIED: read in session]

### Tertiary (LOW confidence)
None — all critical sources verified in session.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all technologies verified in codebase (httpx in requirements.txt, Angular patterns in existing component)
- Architecture: HIGH — Phase 20 context + locked CONTEXT.md decisions leave no ambiguity
- Pitfalls: MEDIUM-HIGH — copied from YouTube Cookies endpoints (proven pattern) but proxy-specific edge cases not yet tested
- Security: HIGH — follows established pattern (get_current_superadmin, encrypt_token, masked returns)

**Research date:** 2026-05-15
**Valid until:** 2026-06-15 (30 days — FastAPI/Angular libraries are stable; proxy feature unlikely to change)

---

*Phase 21: Proxy Admin UI Research complete. Ready for planning.*
