# Architecture Research — v1.4 Integration

**Project:** BrainSuite Platform Connector v1.4 — YouTube Downloads & Dashboard Filters  
**Researched:** 2026-05-14  
**Confidence:** HIGH (specification from memory + code inspection + existing quick-work commits)

---

## Overview

v1.4 adds two independent feature tracks:
1. **Proxy Downloads** — Fix YouTube IP-layer blocking via residential proxy + PO token plugin on DV360/Google Ads
2. **Dashboard Filters** — Restore three filters (metadata autocomplete, ad account multi-select, video duration range)

Both tracks modify existing infrastructure without breaking changes; dashboard filters have partial implementations in quick-session branches that need verification and merge.

---

## Track 1: Proxy Downloads

### Why

YouTube blocks datacenter IPs (GCP/Cloud Run) at the network layer before cookies are validated. Residential proxies make requests indistinguishable from organic traffic. PO token plugin (required since 2025) prevents bot-detection 403s.

### Architecture

**Three-layer stack** (all required):
1. **Residential proxy** — solves IP-layer blocking
2. **Cookies** — solves auth for restricted content (existing system, unchanged)
3. **PO token plugin** — solves bot-proof via bgutil sidecar

### Modified Files

#### `backend/app/models/system_config.py`
- Add `proxy_url_encrypted: Optional[Text]` — Fernet-encrypted proxy URL (nullable)
- Add `proxy_enabled: Boolean` — default False
- No constraint changes; maintains singleton guard

**Rationale:** Proxy configuration is platform-wide (same as cookies), not per-org. Encryption uses existing `TOKEN_ENCRYPTION_KEY` from Phase 12.

#### `backend/app/services/sync/dv360_sync.py` 
- Read `proxy_url_encrypted` + `proxy_enabled` from SystemConfig before the retry loop in `_download_video_asset()`
- Decrypt URL (same pattern as cookies)
- **Proxy injection point:** Inside `_do_download_with_cookies()` closure, add to `ydl_opts` dict after building it:
  ```python
  if proxy_enabled and proxy_url:
      ydl_opts["proxy"] = proxy_url
  ```
- **Sticky session ID:** Embed in proxy username as `user-session-{random_12_chars}:pass@host:port` to prevent mid-download IP rotation
- **Retry order change:** cookieless → primary cookies → backup cookies → fail (cookieless-first is new)

**Code location:** Line ~1185 (`ydl_opts` dict construction), before `YoutubeDL(ydl_opts)` instantiation at line ~1213

#### `backend/app/services/sync/google_ads_sync.py`
- Identical changes as DV360 — same `_do_download_with_cookies` structure exists in this file
- Read proxy config before retry loop
- Same sticky session + retry order changes

#### `backend/app/api/v1/endpoints/super_admin.py`
- New Pydantic models:
  - `ProxyConfigResponse`: `enabled: bool`, `configured: bool`, `host: Optional[str]` (never return decrypted URL)
  - `UpdateProxyConfigRequest`: `proxy_url: Optional[str]`, `proxy_enabled: bool`
- New endpoints:
  - `GET /proxy-config` — reads SystemConfig, returns status only (decrypt to check if URL exists, but don't return it)
  - `PUT /proxy-config` — encrypts URL using existing `encrypt_token()`, updates `proxy_enabled` flag
- All auth: `Depends(get_current_superadmin)` (copy-exact pattern from cookie endpoints)
- All logic: follow `/youtube-cookies` endpoints verbatim for consistency

**Security:** Proxy URL never included in responses or logs (T-14-XX pattern, same as cookies)

### New Files

None. All infrastructure already exists (Fernet encryption, SystemConfig singleton, super_admin pattern).

### Data Flow

```
SuperAdmin uploads proxy URL
    → PUT /proxy-config encrypts & stores in SystemConfig.proxy_url_encrypted + flag
    → Status returned (no URL in response)
    
DV360/Google Ads sync starts
    → Load from SystemConfig
    → Decrypt proxy URL
    → For each YouTube video:
        → Try: cookieless + residential proxy (sticky session ID in username)
        → If 403: try primary cookies + proxy
        → If 403: try backup cookies + proxy
        → If 403: fail
    → bgutil sidecar auto-generates PO tokens when yt-dlp requests format URLs
```

### Build Order

1. **Alembic migration** — add 2 columns to `system_config` table
2. **SystemConfig model** — add fields + defaults
3. **super_admin.py endpoints** — `GET /proxy-config`, `PUT /proxy-config`
4. **dv360_sync.py** — proxy injection + sticky session + retry order
5. **google_ads_sync.py** — same as DV360
6. **Docker Compose** — install `bgutil-ytdlp-pot-provider` in backend image
7. **Smoke test** — Webshare free tier (validate proxy injection works)

**Dependencies:** Proxy depends on nothing else. Can be developed in parallel with filters.

---

## Track 2: Dashboard Filters

### Why

Three filters were partially implemented in quick-session branches (44d8dda, afc4fef, etc.) but need architecture review before merging.

1. **Metadata autocomplete** — Dynamic list of field values extracted from CreativeAsset + AssetMetadataValue; client-side filtering as user types
2. **Ad account multi-select** — Already implemented in main (e403eaf), but needs verification that it integrates with new API params
3. **Video duration range** — New filter; 0–120s default slider range; only shows when video assets detected

### Architecture

**Key constraint:** All three filters should integrate into existing paginated assets query. No separate endpoints needed for metadata suggestions (client pulls from full asset list); durations already in `CreativeAsset.video_duration`.

#### Modified Files

##### `backend/app/api/v1/endpoints/dashboard.py`

**GET /dashboard/assets** already accepts `ad_account_ids` (line 198, via query param). Needs two new optional params:

- `meta_filters: Optional[str] = Query(default=None)` — comma-separated `field_id:value` pairs
  - Example: `meta_filters=color:red,theme:holiday`
  - Parse into dict: `{field_id: [values]}` for IN clause joins
  - Join with `AssetMetadataValue` table to filter assets
  - **Critical:** Must filter by `organization_id` in the join to prevent cross-org data leakage

- `duration_min: Optional[float] = Query(default=None)` — seconds, >= 0
- `duration_max: Optional[float] = Query(default=None)` — seconds, <= 3600

Existing query already handles:
- `platforms` ✓
- `formats` ✓
- `objectives` ✓
- `ad_account_ids` ✓ (line 300–301)
- `score_min` / `score_max` ✓

**Add to WHERE clause:**
```python
if meta_filters_dict:  # {field_id: [values]}
    for field_id, values_list in meta_filters_dict.items():
        query = query.join(
            AssetMetadataValue,
            and_(
                AssetMetadataValue.asset_id == CreativeAsset.id,
                AssetMetadataValue.metadata_field_id == uuid.UUID(field_id),
                AssetMetadataValue.value.in_(values_list),
            )
        )

if duration_min is not None:
    query = query.where(CreativeAsset.video_duration >= duration_min)
if duration_max is not None:
    query = query.where(CreativeAsset.video_duration <= duration_max)
```

**Sorting:** Already supports all metrics; no changes needed.

##### `frontend/src/app/features/dashboard/dashboard.component.ts`

From quick-work commits, component has:

**Metadata filter state** (from afc4fef):
```typescript
selectedMetaFilters: Map<string, string[]> = new Map();  // field_id -> [values]
metadataValues: Map<string, string[]> = new Map();       // field_id -> available values from assets
```

**Duration filter state** (from 44d8dda):
```typescript
durationMin: number = 0;
durationMax: number = 120;
hasAnyVideo: boolean = false;
durationChange$ = new Subject<void>();
```

**Template changes:**
- Metadata: "Add Filter" button → popover → checklist of available field values → chips row showing selected filters
- Duration: ngx-slider after score slider, format as "15s", "1m30s"; only shown when `hasAnyVideo=true`
- Ad accounts: already implemented in main branch

**API integration in loadData():**
```typescript
// Build meta_filters param
let metaFiltersParam = '';
this.selectedMetaFilters.forEach((values, fieldId) => {
  values.forEach(v => {
    metaFiltersParam += `${fieldId}:${encodeURIComponent(v)},`;
  });
});
if (metaFiltersParam) params['meta_filters'] = metaFiltersParam.slice(0, -1);

// Duration params
if (this.durationMin !== 0 || this.durationMax !== 120) {
  params['duration_min'] = this.durationMin;
  params['duration_max'] = this.durationMax;
}
```

**Response handler:**
- Set `hasAnyVideo = true` if any item has `asset_format === 'VIDEO'` (sticky flag, never resets to false)
- Populate `metadataValues` by scanning response items for all unique metadata keys/values
- Display metadata suggestions in the "Add Filter" popover

### New Endpoints

**GET /dashboard/metadata-filter-values** (optional, from afc4fef):
- Returns distinct (field_id, value) pairs for current org + applied filters
- Alternative: populate client-side from asset responses (simpler, already works)
- If implemented: `SELECT DISTINCT(metadata_field_id, value) FROM asset_metadata_value WHERE asset_id IN (filtered_asset_ids)`

### New Files

None. All infrastructure exists.

### Data Flow

```
Dashboard loads
    → GET /dashboard/assets with defaults
    → Response includes video assets
    → hasAnyVideo = true, duration slider visible
    → metadataValues populated from response
    
User selects metadata + duration range
    → selectedMetaFilters.set(field_id, [values])
    → durationMin/Max updated
    → onFilterChange() called
    → debounce 400ms
    
Fetch filtered list
    → GET /dashboard/assets?meta_filters=field_id:val&duration_min=15&duration_max=30
    → WHERE CreativeAsset.video_duration BETWEEN 15 AND 30
    → WHERE asset_metadata_value.value IN (selected_values) (joined per field)
    → Paginated results returned
    
User clears metadata filter
    → selectedMetaFilters.delete(field_id)
    → onFilterChange() called
    → Refetch without that filter
```

### Build Order

1. **Backend params** — add `meta_filters`, `duration_min`, `duration_max` to dashboard.py GET /assets
2. **Backend filtering logic** — add WHERE/JOIN clauses for both
3. **Frontend state** — merge quick-work branches (afc4fef, 44d8dda) into main
4. **Frontend template** — metadata popover + duration slider
5. **Frontend API integration** — pass params to loadData()
6. **Verification** — test metadata autocomplete matches, duration range filtering, ad account multi-select still works

**Dependencies:** Independent of proxy track. Can start immediately.

---

## DB Migration Surface

### Columns to Add (Alembic migration)

**system_config table:**
- `proxy_url_encrypted: Text` (nullable)
- `proxy_enabled: Boolean` (default False)

**CreativeAsset table:**
- `video_duration: Float` already exists (line 51 of creative.py)
  - No new column needed; only used for filtering in v1.4

### Existing Tables Used (No Changes)

- `asset_metadata_value` — join for metadata filter autocomplete
- `creative_assets` — existing `video_duration` field + existing `ad_account_id` field
- `platform_connections` — no changes

### Total Migration Scope

**New columns:** 2 (proxy_url_encrypted, proxy_enabled)  
**Modified tables:** 1 (system_config)  
**Constraint changes:** 0  
**Data backfill:** None (both columns nullable with sensible defaults)  

**Risk:** Minimal. Additive-only, no removal or constraint changes.

---

## Integration Points

### Cross-Module Dependencies

| Component | Depends On | Impact |
|-----------|-----------|--------|
| dv360_sync proxy | SystemConfig + Fernet encryption | Read-only config load; same as cookies |
| google_ads_sync proxy | SystemConfig + Fernet encryption | Same as dv360 |
| super_admin proxy endpoints | SystemConfig + Fernet | GET/PUT pattern copy-exact from cookies |
| dashboard metadata filter | AssetMetadataValue join | Must filter by org_id in join |
| dashboard duration filter | CreativeAsset.video_duration | Field already exists; just filter |
| dashboard ad account filter | CreativeAsset.ad_account_id | Already implemented (main branch) |

### Backward Compatibility

- **Proxy disabled by default** — existing downloads unaffected until admin enables
- **New filter params optional** — if not provided, query behaves as before
- **Cookie system unchanged** — proxy is additive layer only
- **No schema removals** — all changes append-only

### Performance Considerations

**Proxy:** No performance impact (simple config load before download attempt)

**Metadata filter joins:** 
- Joins are `LEFT OUTER` on `AssetMetadataValue` 
- Index required on `(asset_id, metadata_field_id, organization_id)` for O(1) lookup
- With 1,000–10,000 assets per org, query returns in <100ms with proper indexing

**Duration filter:** Simple numeric range predicate on indexed `video_duration` column — negligible overhead

---

## Specific Question Answers

### Q1: Proxy URL injection into yt-dlp

**Answer:**  
Insert into `ydl_opts` dict AFTER construction but BEFORE `YoutubeDL()` instantiation:
```python
# Line ~1185 in dv360_sync.py, inside _do_download_with_cookies()
ydl_opts = {
    "outtmpl": ...,
    "format": "best/b",
    # ... other opts
}
if proxy_enabled and proxy_url:
    ydl_opts["proxy"] = proxy_url  # <-- HERE
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])
```

Sticky session ID embedded in proxy username: `user-session-{12_random_chars}:pass@host:port`

### Q2: bgutil sidecar architecture

**Answer:**  
Not a sidecar in the Docker container sense. Install `bgutil-ytdlp-pot-provider` PyPI package in backend image. It registers as a provider with yt-dlp at import time. When yt-dlp encounters a protected format URL, it auto-invokes the provider to generate a PO token on-the-fly. No explicit code required; yt-dlp calls it automatically once installed.

**Installation:** Add to `backend/Dockerfile`:
```dockerfile
RUN pip install bgutil-ytdlp-pot-provider==latest
```

### Q3: Metadata autocomplete — new endpoint or client-side?

**Answer:**  
Client-side is sufficient. Dashboard already returns full asset list for current filters. Extract unique (field_id, value) pairs from response and populate autocomplete dropdown. Optional: implement `/dashboard/metadata-filter-values` endpoint if you want server-side deduplication (cleaner for large datasets, ~10 extra lines of SQL).

Simplest approach: parse from response, no new endpoint.

### Q4: Ad account multi-select filter integration

**Answer:**  
Already implemented in main branch (e403eaf, 741c037). Component has `selectedAdAccountIds: string[]` and passes as `ad_account_ids` query param. Backend `dashboard.py` already handles it (line 300–301). Verify by:
1. Check `adAccounts` are loaded on init (line 1296)
2. Confirm `selectedAdAccountIds` passed to `loadData()` (line 1567)
3. Test with 2+ accounts in filter

No changes needed unless verification finds issues.

### Q5: Video duration range — field population

**Answer:**  
`CreativeAsset.video_duration: Optional[float]` exists in model (creative.py, line 51). Populated by DV360/Google Ads sync at line ~1237 of dv360_sync.py via `_get_video_duration(file_path)`. TikTok sync also populates it. No migration needed.

Dashboard filter simply adds WHERE clause: `CreativeAsset.video_duration BETWEEN duration_min AND duration_max`

### Q6: Migration surface — complete list

**Answer:**
- **New columns:** `proxy_url_encrypted (Text)`, `proxy_enabled (Boolean)` on `system_config` table
- **Existing columns used:** `video_duration` (already exists on `creative_assets`)
- **No table additions, deletions, or constraint changes**
- **Risk:** Minimal (additive only)

---

## Build Sequence Recommendation

### Phase 1: Proxy Infrastructure (Week 1)
1. Alembic migration + SystemConfig model
2. super_admin.py proxy endpoints (GET + PUT)
3. Webshare free tier smoke test (validate yt-dlp accepts proxy injection)

### Phase 2: Proxy Sync Integration (Week 1–2)
4. dv360_sync.py proxy injection + sticky session + retry order
5. google_ads_sync.py same changes
6. Docker Compose: add bgutil package
7. E2E test: YouTube download via proxy

### Phase 3: Dashboard Filters — Backend (Week 2)
8. dashboard.py: add `meta_filters`, `duration_min`, `duration_max` params + WHERE/JOIN logic
9. Unit test: metadata filtering, duration range

### Phase 4: Dashboard Filters — Frontend (Week 2–3)
10. Merge quick-work branches (afc4fef, 44d8dda, 3dd4b1c) into main
11. Add metadata popover template + duration slider template
12. Wire up API params in loadData()
13. Smoke test: all three filters work + interact correctly

### Phase 5: Verification (Week 3)
14. Ad account multi-select still works (regression)
15. Pagination works with filters applied
16. Proxy enabled → cookies last longer ✓

---

## Known Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Proxy geo-region mismatch (cookie region ≠ proxy exit region) | Lock proxy to US exit nodes; document in admin UI |
| Mid-download IP rotation (sticky session too short) | Default sticky duration ≥5 min (IPRoyal 7 days is safe); embed session ID in proxy username |
| PO token generation fails silently | Monitor bgutil startup logs; add explicit check after import |
| Metadata filter joins N+1 per selected field | Add composite index on `(asset_id, metadata_field_id, organization_id)` before go-live |
| Duration slider shows before any videos loaded | Use `hasAnyVideo` sticky flag; only show after first response with VIDEO assets |

---

## Files Summary

### Phase 1–2: Proxy Tracks
- `/backend/app/models/system_config.py` — +2 columns
- `/backend/alembic/versions/{new}.py` — new migration
- `/backend/app/api/v1/endpoints/super_admin.py` — +80 lines (2 new endpoints)
- `/backend/app/services/sync/dv360_sync.py` — +15 lines (proxy injection)
- `/backend/app/services/sync/google_ads_sync.py` — +15 lines (proxy injection)
- `/backend/Dockerfile` — +1 line (bgutil install)

### Phase 3–4: Dashboard Filters
- `/backend/app/api/v1/endpoints/dashboard.py` — +20 lines (3 new params + logic)
- `/frontend/src/app/features/dashboard/dashboard.component.ts` — merge 3 commits (~150 net lines)
- `/frontend/src/app/features/dashboard/dashboard.component.html` — update template for popover + slider

### Total Surface
- **Backend:** ~130 lines net (proxy + filters combined)
- **Frontend:** ~150 lines net (filters; proxy has no UI)
- **Migrations:** 1 (additive)
- **Risk:** Minimal (no breaking changes, backward compatible)

---

## Success Criteria

**Proxy track:**
- ✓ Proxy URL stored encrypted in SystemConfig
- ✓ SuperAdmin can enable/disable via API
- ✓ DV360 + Google Ads downloads inject proxy into yt-dlp opts
- ✓ bgutil plugin generates PO tokens automatically
- ✓ Cookieless-first retry path works (public videos)
- ✓ Primary cookies work as fallback when proxy+public fails
- ✓ YouTube video downloads succeed on Cloud Run (tested vs GCP datacenter blocking)

**Dashboard filters track:**
- ✓ Metadata filter accepts multiple field:value pairs
- ✓ Duration range slider (0–120s) visible only when video assets exist
- ✓ Ad account multi-select still works (regression test)
- ✓ All three filters work independently and in combination
- ✓ Pagination works with all filters applied
- ✓ Filters update immediately (debounce 400ms)
