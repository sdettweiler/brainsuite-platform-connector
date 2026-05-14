# Stack Research — v1.4 Residential Proxy + Dashboard Filters

**Project:** BrainSuite Platform Connector  
**Researched:** 2026-05-14  
**Scope:** New features only (residential proxy integration, PO token plugin, dashboard filters)

---

## Executive Summary

v1.4 adds three capability layers to the existing stack with minimal new dependencies:

1. **Residential proxy for yt-dlp** — proxy URL injection (no new packages; yt-dlp built-in support)
2. **YouTube POT token plugin** — `bgutil-ytdlp-pot-provider==1.3.1` (single Python package + Docker sidecar service)
3. **Dashboard filters** — Angular Material components already installed; `@angular-slider/ngx-slider` already in use for duration range filter

**NEW packages added:** Only `bgutil-ytdlp-pot-provider==1.3.1` to backend requirements.  
**NEW infrastructure:** Single Docker service (`bgutil-pot` sidecar on port 4416) for token generation.  
**NO breaking changes** to existing stack.

---

## New Packages Required

### Backend (Python)

| Package | Version | Purpose | Installation | Notes |
|---------|---------|---------|--------------|-------|
| `bgutil-ytdlp-pot-provider` | `==1.3.1` | YouTube proof-of-origin (POT) token generation plugin for yt-dlp to bypass "Sign in to confirm you're not a bot" verification | `pip install bgutil-ytdlp-pot-provider==1.3.1` | **Requires yt-dlp >= 2025.05.22** (verify current version in requirements.txt). Supports HTTP server mode (recommended) where plugin retrieves tokens from sidecar on port 4416. No additional Python dependencies beyond what's already in requirements.txt. Recommended flavor: Deno-based Docker image (`brainicism/bgutil-ytdlp-pot-provider:1.3.1-deno`) — faster startup than Node.js. |

### Frontend (npm)

**No new packages needed.** All required components already installed:

| Package | Version | Already Installed? | Usage |
|---------|---------|-------------------|-------|
| `@angular/material` | `^17.3.0` | ✓ Yes | `MatAutocomplete` (metadata filter), `MatFormField`, `MatInput` |
| `@angular/cdk` | `^17.3.0` | ✓ Yes | `MatAutocompleteTrigger`, `CdkConnectedOverlay` for positioning |
| `@angular-slider/ngx-slider` | `^17.0.2` | ✓ Yes | Range slider for duration filter (already supports dual-handle range) |

---

## Docker Changes

### Add bgutil-pot Sidecar Service

**File:** `docker-compose.yml`  
**Action:** Insert new service between `backend` and `frontend`.

```yaml
# ─── bgutil-pot (YouTube POT token provider) ────────────────────────────────
bgutil-pot:
  image: brainicism/bgutil-ytdlp-pot-provider:1.3.1-deno
  container_name: brainsuite_bgutil_pot
  restart: unless-stopped
  ports:
    - "4416:4416"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:4416/health"]
    interval: 15s
    timeout: 5s
    retries: 3
  environment:
    # Optional: customize token TTL (default 6 hours)
    TOKEN_TTL: 6
```

**Dependency in backend service:**

```yaml
backend:
  # ... existing config ...
  depends_on:
    # ... existing dependencies ...
    bgutil-pot:
      condition: service_healthy
```

### Environment Variables

Add to `.env` (optional, for production proxy config):

```bash
# Residential proxy settings
RESIDENTIAL_PROXY_URL=http://proxy.provider.com:port  # Will be passed to yt-dlp if configured
PROXY_USERNAME=optional_username
PROXY_PASSWORD=optional_password
```

**Note:** Proxy URL is intentionally NOT required at startup. It's stored in `SystemConfig` table (encrypted) and used on-demand during download jobs. Null proxy = cookieless fallback.

---

## Residential Proxy Integration (No New Infrastructure)

### How yt-dlp Proxy Support Works

yt-dlp has built-in proxy support via the `--proxy` flag and `'proxy'` option in Python API:

```python
ydl_opts = {
    'proxy': 'http://username:password@proxy.com:port',
    'socket_timeout': 30,
}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])
```

**Sticky sessions:** Residential proxy providers handle sticky IP assignment. Pass session ID as query param in proxy URL (provider-specific):

```python
ydl_opts = {
    'proxy': 'http://user:pass@gateway.provider.com:port?session_id=unique_job_id',
}
```

**No sticky session module needed** — just URL string manipulation.

### Integration Points

1. **Backend:** Read proxy URL from `SystemConfig.residential_proxy_url` (existing Fernet-encrypted Text column, to be added to schema)
2. **Download functions:** Pass proxy to `yt_dlp.YoutubeDL()` opts before calling `ydl.download([url])`
3. **Fallback:** If `SystemConfig.residential_proxy_enabled = False` OR proxy URL is None, skip proxy (cookieless/network-native fallback already works)

**Existing code pattern:** `dv360_sync.py` and `google_ads_sync.py` already have cookie fallback logic. Proxy is additive — it just changes the proxy config, not the download structure.

---

## Dashboard Filters (Frontend Angular)

### 1. Metadata Filter with Autocomplete

**Component:** `MatAutocomplete` (already in `@angular/material`)  
**Implementation:**

```typescript
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

// In component
metadataForm = new FormControl('');
filteredMetadata: Observable<string[]>;

ngOnInit() {
  this.filteredMetadata = this.metadataForm.valueChanges.pipe(
    startWith(''),
    debounceTime(300),
    switchMap(value => this.apiService.getMetadataOptions(value, this.org_id))
  );
}
```

**Template:**

```html
<mat-form-field>
  <mat-label>Metadata</mat-label>
  <input matInput [formControl]="metadataForm" [matAutocomplete]="auto" />
  <mat-autocomplete #auto="matAutocomplete">
    <mat-option *ngFor="let opt of filteredMetadata | async" [value]="opt">
      {{ opt }}
    </mat-option>
  </mat-autocomplete>
</mat-form-field>
```

**API endpoint:** Reuse existing `/api/v1/dashboard/metadata-options?org_id=X&search=Y` or create new.

### 2. Ad Account Multi-Select Filter

**Component:** Existing pattern in dashboard (ad account toggle menu)  
**Current implementation:** MatMenu with checkboxes for ad_account_id  
**Already in code:** `selectedAdAccountIds: string[]` with toggle/filter logic (lines 149–161 of dashboard.component.ts)  
**Enhancement:** Convert to Material `MatSelect` with multiple option if desired (optional polish).

**Current working code:** Dashboard already has ad account multi-select via MatMenu + checkbox pattern. Keep as-is or upgrade to `MatSelectModule` with `multiple` attribute.

### 3. Video Duration Range Slider

**Component:** `@angular-slider/ngx-slider` (already installed v17.0.2)  
**Already supports range mode** via `highValue` property (dual handles for min/max).

**Template:**

```html
<div class="duration-slider-wrapper">
  <span class="slider-label">Duration (seconds)</span>
  <ngx-slider
    [(value)]="durationMin"
    [(highValue)]="durationMax"
    [options]="durationSliderOptions"
    (userChangeEnd)="onDurationChange()"
  ></ngx-slider>
  <span class="slider-values">{{ durationMin }}s - {{ durationMax }}s</span>
</div>
```

**Component TypeScript:**

```typescript
durationMin = 0;
durationMax = 600; // 10 minutes default max
durationSliderOptions: Options = {
  floor: 0,
  ceil: 3600, // 1 hour max
  step: 15,
  noSwitching: true,
  preventEqualMinMax: false,
};

onDurationChange() {
  this.onFilterChange(); // Trigger API call with ?duration_min=X&duration_max=Y
}
```

**API query param:** `?duration_min_sec=X&duration_max_sec=Y` (backend filters `video_duration` column).

---

## No New Infrastructure Needed

✓ **Proxy URL storage:** Existing `SystemConfig` table with Fernet encryption (add `residential_proxy_url` nullable Text column via migration)  
✓ **Proxy toggle:** Add `SystemConfig.residential_proxy_enabled` boolean flag (default False)  
✓ **Token cache:** bgutil-pot sidecar handles internally (TTL via env var, defaults to 6h)  
✓ **Sticky sessions:** Handled by proxy provider (session ID embedded in URL)  
✓ **Dashboard API:** Existing `/api/v1/dashboard/assets` endpoint adds query params for filters  

---

## What NOT to Add (Anti-Patterns)

| Anti-Pattern | Why Avoid | Alternative |
|--------------|-----------|-------------|
| Add `requests` library for proxy support | httpx already installed; urllib built into yt-dlp. `requests` is redundant. | Use yt-dlp's native proxy option (String) |
| Create custom proxy manager service | yt-dlp handles proxy internally. Custom rotating wrapper adds complexity. | Pass static proxy URL (sticky session via query param) or let provider rotate IPs |
| Implement Redis-based token cache | bgutil-pot HTTP server includes built-in memory cache with TTL. No need to duplicate. | Use HTTP server mode (port 4416) |
| Add `ngx-mat-select-search` for autocomplete | `MatAutocomplete` is built-in and sufficient. Extra package = bloat. | Use MatAutocomplete with `async` pipe |
| Create separate metadata options endpoint | Reuse existing asset sync endpoint or add cheap database lookup (no HTTP overhead). | Query `asset_metadata_value` table directly with `LIKE` filter |
| Implement range slider from scratch | ngx-slider already supports dual-handle ranges. Don't reinvent. | Use existing ngx-slider `highValue` property |
| Add request interceptor for proxy injection | Proxy is for yt-dlp subprocess only, not HTTP client calls. Misplaced. | Pass proxy URL directly to `yt_dlp.YoutubeDL()` opts |

---

## Installation / Deployment Checklist

### Backend

```bash
# Add to requirements.txt
bgutil-ytdlp-pot-provider==1.3.1
# Existing yt-dlp (verify >=2025.05.22)
yt-dlp  # or pin to specific version if needed
```

### Docker Compose

```bash
# 1. Update docker-compose.yml with bgutil-pot service (see Docker Changes section)
# 2. Add health check for port 4416
# 3. Set backend depends_on: bgutil-pot
# 4. Rebuild: docker-compose build
```

### Database Migration

```bash
# Alembic migration to add SystemConfig columns:
# - residential_proxy_url: Text, nullable
# - residential_proxy_enabled: Boolean, default False
alembic revision --autogenerate -m "add residential proxy config"
```

### Frontend

```bash
# No npm install needed — all dependencies already present
# Just update dashboard.component.ts to import MatAutocompleteModule
import { MatAutocompleteModule } from '@angular/material/autocomplete';
```

---

## Version Compatibility Matrix

| Component | Current Version | v1.4 Version | Compatible? |
|-----------|-----------------|--------------|-------------|
| Angular | 17.3.0 | 17.3.0 | ✓ Yes (no change) |
| @angular/material | 17.3.0 | 17.3.0 | ✓ Yes (no change) |
| @angular/cdk | 17.3.0 | 17.3.0 | ✓ Yes (no change) |
| ngx-slider | 17.0.2 | 17.0.2 | ✓ Yes (no change) |
| FastAPI | 0.115.0 | 0.115.0 | ✓ Yes (no change) |
| yt-dlp | Latest | >=2025.05.22 | ✓ Verify requirement |
| bgutil-ytdlp-pot-provider | — | 1.3.1 | ✓ New (add) |

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Residential proxy provider downtime | Medium | Fallback to cookieless download (already implemented). Proxy is optional. |
| bgutil-pot sidecar restart loop | Low | Docker health check on port 4416. Logs will show token generation errors. |
| Token cache stale / conflicts | Low | HTTP server mode auto-refreshes tokens. Single instance per deployment. |
| Proxy URL accidentally logged | High | **Already mitigated:** Pass proxy URL as function argument, never from os.environ (T-14-10 decision). Ensure Fernet encryption in DB. |
| Dashboard filter API performance | Medium | Add database indexes on `asset_metadata_value.value`, `video_duration`. Cache frequent metadata options in Redis if queries >100ms. |

---

## References

- **bgutil-ytdlp-pot-provider:** https://pypi.org/project/bgutil-ytdlp-pot-provider/
- **bgutil-ytdlp-pot-provider GitHub:** https://github.com/Brainicism/bgutil-ytdlp-pot-provider
- **bgutil-ytdlp-pot-provider Docker:** https://hub.docker.com/r/brainicism/bgutil-ytdlp-pot-provider
- **yt-dlp proxy integration:** https://developers.oxylabs.io/video-data/high-bandwidth-proxies/youtube-downloader-yt_dlp-integration
- **Angular Material Autocomplete:** https://material.angular.dev/components/autocomplete/overview
- **ngx-slider documentation:** https://angular-slider.github.io/ngx-slider/
- **yt-dlp networking:** https://deepwiki.com/yt-dlp/yt-dlp/5.5-browser-integration-and-cookie-system

---

*v1.4 stack research completed 2026-05-14. Additive to v1.3 STACK-v1.3.md.*
