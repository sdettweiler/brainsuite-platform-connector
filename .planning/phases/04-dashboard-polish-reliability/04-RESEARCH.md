# Phase 4: Dashboard Polish + Reliability - Research

**Researched:** 2026-03-24
**Domain:** Angular 17 standalone components, SQLAlchemy nullslast, platform health state machine
**Confidence:** HIGH

## Summary

Phase 4 is a targeted polish pass over the existing dashboard and configuration pages. Four work items are in scope: (1) a dual-handle score range slider (new npm dependency), (2) thumbnail fallback for video creatives (a code fix to an existing function), (3) nulls-last sort enforcement on score column for both asc and asc directions (a one-line SQLAlchemy fix), and (4) a platform health badge + reconnect prompt in the Configuration > Platform Connections page (pure frontend with no new endpoints).

All backend infrastructure is already in place. The `PlatformConnection` model carries `token_expiry`, `last_synced_at`, and `sync_status` fields. The key gap is that `token_expiry` is NOT currently exposed in `PlatformConnectionResponse` — it must be added. Health state computation is entirely client-side Angular logic.

A critical pre-existing bug is in scope: the frontend sends `sort_by=total_score` but the backend `sort_col_map` keys on `"score"`. This means score sorting is currently silently falling back to spend. Phase 4 must align these two sides.

**Primary recommendation:** Add `@angular-slider/ngx-slider@17.0.2` (the Angular 17-compatible version), expose `token_expiry` in the platform schema, fix the `total_score`/`score` sort key mismatch, and implement health state as a pure Angular computed property from fields already returned by the API.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Dual-handle range slider using `@angular-slider/ngx-slider` — one new npm dependency, dual handle out of the box, Material-compatible styling.
- **D-02:** Slider range: 0–100 (matches BrainSuite score scale). Default: full range (no filter applied).
- **D-03:** Filter is applied as `score_min` / `score_max` query params sent to the backend `/dashboard/assets` endpoint. Backend already filters by platform — add score range in the same WHERE clause.
- **D-04:** Slider lives in the existing filter bar alongside platform buttons, format filter, and sort dropdown. No new panel needed.
- **D-05:** When no scored assets exist yet, slider is visible but disabled (opacity-reduced) with a tooltip "No scored creatives yet".
- **D-06:** Video creatives with no `thumbnail_url`: show the platform icon centered on a dark background (`#111`) with a small `VIDEO` tag in the bottom-right corner — same treatment as the CE tab media panel.
- **D-07:** Image creatives with no `asset_url` or `thumbnail_url`: fall back to the existing `placeholder.svg`.
- **D-08:** `thumbnail_url` is already returned by the backend and referenced in the frontend card template. Verify the CSS correctly constrains `object-fit: cover` for the card grid tile (currently `height: 160px` in dashboard styles). No backend changes needed.
- **D-09:** Sort-by-score nulls always last — `NULLS LAST` in the SQL ORDER BY regardless of asc/desc direction. Backend already has a `sort_col_map` for `score`; add `nullslast()` wrapper via SQLAlchemy.
- **D-10:** Default sort on page load remains `spend desc` (existing behavior). No change.
- **D-11:** Sort options already in the dropdown: Spend, CTR, ROAS, ACE Score, Platform. Verify all 5 map correctly in the backend `sort_col_map` — `total_score` column via `CreativeScoreResult` outer join.
- **D-12:** Health panel lives on the **Configuration page** — each platform connection row is extended with: last sync time (human-relative: "2 hours ago"), health badge, and inline reconnect button.
- **D-13:** Three health states per connection: `connected` (last sync within 24h, token not expired) → green badge; `token_expired` (`token_expiry` < now) → amber badge + "Reconnect" button; `sync_failed` (last sync >48h ago or stored error flag) → red badge + "Reconnect" button.
- **D-14:** "Reconnect" button triggers the existing OAuth re-auth flow — reuse `startOAuth()` method, no new endpoints needed.
- **D-15:** Health state is computed client-side from `token_expiry` and `last_synced_at` fields already returned by `GET /api/v1/platforms/connections`. No new backend endpoint required.
- **D-16:** No dashboard-level banner or header chip — health info lives on Configuration page only.

### Claude's Discretion

- Exact ngx-slider styling (track color, handle size) — match the existing orange accent theme.
- Debounce duration for slider change → API call (300–500ms recommended).
- Exact "sync failed" threshold (e.g. 48h without successful sync) — Claude can pick a reasonable value.
- Configuration page layout adjustment to fit the new health columns without breaking existing connection management UI.

### Deferred Ideas (OUT OF SCOPE)

- Dashboard-level warning banner when any platform has issues — Configuration-only; defer to v2 if needed.
- Score-to-ROAS correlation view — DASH-v2-01 (v2 backlog, already deferred).
- Top/bottom performer highlighting — DASH-v2-02 (v2 backlog).
- "Never synced" fourth health state — could add later if needed; not in Phase 4 scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01 | Creative thumbnail visible per creative in list/table view | `getTileThumbnail()` already exists; fix video path (D-06, D-07, D-08) |
| DASH-02 | BrainSuite score badge visible per creative | Already implemented in Phase 3 — verify only |
| DASH-03 | Score dimension breakdown panel accessible per creative | Already implemented in Phase 3 — verify only |
| DASH-04 | Creatives sortable by score, ROAS, CTR, spend | Fix `total_score` vs `score` mismatch + `nullslast()` on asc direction (D-09, D-11) |
| DASH-05 | Creatives filterable by platform, date range, and score range | New ngx-slider + backend `score_min`/`score_max` params (D-01 through D-05) |
| REL-01 | Last sync time and connection health displayed per platform | Platform health panel — add columns to existing table (D-12, D-13, D-15) |
| REL-02 | Failed syncs and expired tokens surfaced with reconnect prompt | Reconnect button reuses `startOAuth()` (D-14) |
| REL-03 | APScheduler runs on exactly one worker | Already implemented in Phase 3 (SCHEDULER_ENABLED guard) — verify only |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@angular-slider/ngx-slider` | 17.0.2 | Dual-handle range slider | Maintained Angular-native; peer deps match Angular 17.x exactly |
| SQLAlchemy `nullslast()` | (built-in) | Null ordering in ORDER BY | Native SQLAlchemy function, no extra dep |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Angular `DatePipe` + JS `Date` math | (Angular 17 built-in) | Relative time "2 hours ago" | No external dependency needed for simple relative formatting |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@angular-slider/ngx-slider@17.0.2` | `@angular-slider/ngx-slider@21.0.0` | v21 requires Angular 21 — incompatible with this project's Angular 17 |
| `@angular-slider/ngx-slider@17.0.2` | `mat-slider` with thumbs | Angular Material range slider is experimental/limited in v17; ngx-slider has a cleaner API for dual handles |
| JS Date math for relative time | `date-fns` `formatDistanceToNow` | `date-fns` is already in `package.json` — use it instead of rolling custom logic |

**Installation:**
```bash
cd frontend && npm install @angular-slider/ngx-slider@17.0.2
```

**Version verification:** `@angular-slider/ngx-slider@17.0.2` confirmed against npm registry (2026-03-24). Peer deps: `@angular/core ^17.1.1`, `@angular/forms ^17.1.1`, `@angular/common ^17.1.1`. Project uses `^17.3.0` — fully compatible.

## Architecture Patterns

### Recommended Project Structure
No new files or directories are needed. All changes are targeted modifications to:
```
backend/app/
├── schemas/platform.py           # Add token_expiry to PlatformConnectionResponse
├── api/v1/endpoints/dashboard.py # Add score_min/score_max params + fix sort key
frontend/src/app/features/
├── dashboard/
│   └── dashboard.component.ts    # Add NgxSliderModule, score filter state, thumbnail fix
└── configuration/pages/
    └── platforms.component.ts    # Add health badge, last-sync display, reconnect button
```

### Pattern 1: Debounced Slider → API Call

**What:** Score range slider emits `valueChange` on every handle drag. Debounce prevents per-pixel API calls.

**When to use:** Any slider that triggers a network request.

**Example:**
```typescript
// Import NgxSliderModule in the standalone component's imports array
import { NgxSliderModule, Options } from '@angular-slider/ngx-slider';

// Component state
scoreMin = 0;
scoreMax = 100;
sliderOptions: Options = {
  floor: 0,
  ceil: 100,
  step: 1,
  noSwitching: true,
};
private scoreChange$ = new Subject<void>();

// In ngOnInit — debounce slider changes
this.scoreChange$.pipe(
  debounceTime(400),
  takeUntil(this.destroy$)
).subscribe(() => this.onFilterChange());

// Template event handler
onScoreChange(): void {
  this.scoreChange$.next();
}
```

**In `loadData()` — add params:**
```typescript
if (this.scoreMin > 0) params['score_min'] = this.scoreMin;
if (this.scoreMax < 100) params['score_max'] = this.scoreMax;
```

### Pattern 2: Client-Side Health State Computation

**What:** Compute health badge from two fields already in the API response — no new endpoint.

**When to use:** When state can be derived from existing data without server round-trip.

**Example:**
```typescript
// Extend PlatformConnection interface in platforms.component.ts
interface PlatformConnection {
  // ...existing fields...
  token_expiry?: string;   // ADD — must also be added to PlatformConnectionResponse schema
}

type HealthState = 'connected' | 'token_expired' | 'sync_failed';

getHealthState(conn: PlatformConnection): HealthState {
  const now = new Date();
  if (conn.token_expiry && new Date(conn.token_expiry) < now) {
    return 'token_expired';
  }
  if (!conn.last_synced_at) return 'sync_failed';
  const hoursSinceSync = (now.getTime() - new Date(conn.last_synced_at).getTime()) / 3_600_000;
  if (hoursSinceSync > 48) return 'sync_failed';
  return 'connected';
}

getRelativeTime(isoString: string | undefined): string {
  if (!isoString) return 'Never';
  // Use date-fns which is already in package.json
  import { formatDistanceToNow } from 'date-fns';
  return formatDistanceToNow(new Date(isoString), { addSuffix: true });
}
```

### Pattern 3: Thumbnail Fallback for Video Creatives

**What:** The existing `getTileThumbnail()` returns `placeholder.svg` for videos with no thumbnail. Replace with a data-URI or CSS-driven dark-bg + platform icon fallback per D-06.

**When to use:** When an `<img>` tag cannot display a valid URL.

**Approach — CSS class toggle (simpler than data-URI):**
```typescript
// Modified getTileThumbnail() returns null for video-no-thumb case
getTileThumbnail(asset: DashboardAsset): string | null {
  if (asset.asset_format !== 'VIDEO') {
    // Image creative: use asset_url or thumbnail_url
    return asset.asset_url || asset.thumbnail_url || null;
  }
  // Video creative: use thumbnail if available, else null triggers CSS fallback
  return asset.thumbnail_url || null;
}

isVideoNoThumb(asset: DashboardAsset): boolean {
  return asset.asset_format === 'VIDEO' && !asset.thumbnail_url;
}
```

**Template update:**
```html
<div class="tile-thumb" [class.video-no-thumb]="isVideoNoThumb(asset)">
  <img *ngIf="getTileThumbnail(asset) as thumb" [src]="thumb" [alt]="asset.ad_name" (error)="onImgError($event)" />
  <!-- video fallback rendered by CSS + background platform icon -->
  <div *ngIf="isVideoNoThumb(asset)" class="video-fallback">
    <img [src]="getPlatformOverlayIcon(asset.platform)" class="video-fallback-icon" />
    <span class="video-tag">VIDEO</span>
  </div>
  <!-- ...overlays unchanged... -->
</div>
```

**CSS addition:**
```scss
.video-no-thumb { background: #111; }
.video-fallback {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  position: relative;
}
.video-fallback-icon { width: 48px; height: 48px; opacity: 0.6; object-fit: contain; }
.video-tag {
  position: absolute; bottom: 6px; right: 6px;
  background: rgba(0,0,0,0.65); color: white;
  font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;
  text-transform: uppercase;
}
```

### Pattern 4: SQLAlchemy nullslast on Both Directions

**What:** Current code uses `.nullslast()` for DESC but `.nullsfirst()` for ASC. D-09 requires nulls last regardless of direction.

**Fix in `dashboard.py` (line ~224):**
```python
from sqlalchemy import nullslast

sort_col = sort_col_map.get(sort_by, perf_subq.c.total_spend)
if sort_order.lower() == "desc":
    query = query.order_by(nullslast(sort_col.desc()))
else:
    query = query.order_by(nullslast(sort_col.asc()))
```

Note: `nullslast()` is available from `sqlalchemy` directly (not `sqlalchemy.orm`).

### Pattern 5: Fix score sort key mismatch

**What:** Frontend sends `sort_by=total_score` but backend maps only `"score"`. Result: score sort silently falls back to spend (the default). Fix both sides.

**Option A — fix backend only (add alias):**
```python
sort_col_map = {
    # ...existing entries...
    "score": CreativeScoreResult.total_score,
    "total_score": CreativeScoreResult.total_score,  # ADD alias for frontend compat
}
```

**Option B — fix frontend only (change value to `"score"`):**
```html
<mat-option value="score">ACE Score</mat-option>
```

**Recommendation:** Use Option A (add alias in backend) — it avoids changing the wire format and is more defensive. Add the frontend fix too for clarity.

### Anti-Patterns to Avoid

- **ngx-slider version mismatch:** Never install the latest `@angular-slider/ngx-slider` (currently v21) in an Angular 17 project — the peer dep check will fail at build time. Always pin to `17.0.2`.
- **Computing health state server-side:** Adding a `/connections/health` endpoint is unnecessary overhead — all data is already in the existing connections list response.
- **Using `(valueChange)` without debounce:** ngx-slider fires on every pixel drag. Without a `debounceTime(400)` on a Subject, the backend will receive a flood of requests.
- **`nullslast()` as method vs import:** In SQLAlchemy 2.x, the correct import is `from sqlalchemy import nullslast` (standalone function). Do not call `.nulls_last()` as a column method — that API is deprecated in SQLAlchemy 2.x.
- **Exposing `token_expiry` directly in responses:** `token_expiry` is safe to expose (it is a timestamp, not a secret). Never expose `access_token_encrypted` or `refresh_token_encrypted`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dual-handle range slider | Custom `<input type="range">` × 2 with overlap detection | `@angular-slider/ngx-slider@17.0.2` | Overlap detection, ARIA, keyboard nav are complex to get right |
| Relative time formatting | Custom `Date` arithmetic | `date-fns` `formatDistanceToNow()` | Already in `package.json`; handles edge cases (pluralization, just now, etc.) |

**Key insight:** The platform health panel is entirely derivable from existing API fields — no new endpoint, no new model field, only `token_expiry` added to the schema response.

## Common Pitfalls

### Pitfall 1: ngx-slider version incompatibility
**What goes wrong:** `npm install @angular-slider/ngx-slider` installs v21, which requires Angular 21. The Angular build fails with "peer dependency" or type errors.
**Why it happens:** npm installs latest by default.
**How to avoid:** Always pin: `npm install @angular-slider/ngx-slider@17.0.2`.
**Warning signs:** Build error mentioning `@angular/core` version mismatch.

### Pitfall 2: score sort is silently broken (pre-existing bug)
**What goes wrong:** Selecting "ACE Score" in the sort dropdown appears to work but actually sorts by spend (the fallback). Users see incorrect ordering.
**Why it happens:** Frontend sends `sort_by=total_score`; backend `sort_col_map` only has key `"score"`. `sort_col_map.get("total_score", perf_subq.c.total_spend)` returns the default.
**How to avoid:** Add `"total_score"` as an alias in the backend `sort_col_map` dict and align the frontend option value.
**Warning signs:** Score sort gives identical results to spend sort.

### Pitfall 3: `token_expiry` missing from API response
**What goes wrong:** Angular health state computation always falls into `sync_failed` or `connected` because `conn.token_expiry` is always `undefined` — the backend schema does not expose it.
**Why it happens:** `PlatformConnectionResponse` does not include `token_expiry` (verified by reading `backend/app/schemas/platform.py` lines 49–70).
**How to avoid:** Add `token_expiry: Optional[datetime]` to `PlatformConnectionResponse` and add `token_expiry: string | undefined` to the Angular `PlatformConnection` interface.
**Warning signs:** `conn.token_expiry` is always `undefined`; `token_expired` health state is never triggered.

### Pitfall 4: Slider disabled state without `hasAnyScored` signal
**What goes wrong:** Slider is always interactive even when no scored creatives exist, confusing users who see it moving but producing no results.
**Why it happens:** Missing a guard on the `sliderOptions.disabled` property.
**How to avoid:** After `loadData()` resolves, check `this.assets.some(a => a.scoring_status === 'COMPLETE')` and set `sliderOptions = { ...this.sliderOptions, disabled: !hasScored }`.
**Warning signs:** Slider moves freely but score filter has no effect (no COMPLETE assets in the dataset).

### Pitfall 5: ASC sort puts nulls first (DASH-04 regression)
**What goes wrong:** When a user sorts ASC by score, all unscored assets (null score) appear at the top — noise before real data.
**Why it happens:** Current code uses `.nullsfirst()` for ASC direction.
**How to avoid:** Apply `nullslast()` wrapper for both ASC and DESC: `query.order_by(nullslast(sort_col.asc()))`.
**Warning signs:** Sorting ASC by score shows `–` badge items at top of grid.

### Pitfall 6: Health badge breaks existing Status column
**What goes wrong:** The table already has a `Status` column showing `sync_status`. Adding a second similar column causes confusion or UI overflow.
**Why it happens:** `sync_status` (ACTIVE/EXPIRED/ERROR/PENDING) and the new health badge are overlapping concepts.
**How to avoid:** Replace or merge the `Status` column — the new health badge derived from `token_expiry` + `last_synced_at` supersedes `sync_status` for user-facing display. Keep `sync_status` as the internal field but display only the health badge to users. Alternatively, augment the existing chip rather than adding a new column.
**Warning signs:** Table has 11+ columns, horizontal scroll on standard viewports.

## Code Examples

### Backend: Add score_min / score_max filter to `get_dashboard_assets`

```python
# Source: backend/app/api/v1/endpoints/dashboard.py — add to function signature
score_min: Optional[float] = Query(default=None, ge=0, le=100),
score_max: Optional[float] = Query(default=None, ge=0, le=100),

# In query construction — after existing where clauses:
if score_min is not None:
    query = query.where(CreativeScoreResult.total_score >= score_min)
if score_max is not None:
    query = query.where(CreativeScoreResult.total_score <= score_max)
```

### Backend: Add `token_expiry` to PlatformConnectionResponse

```python
# Source: backend/app/schemas/platform.py — PlatformConnectionResponse class
token_expiry: Optional[datetime] = None   # ADD this field
```

### Frontend: NgxSliderModule import in dashboard standalone component

```typescript
// In dashboard.component.ts — imports array
import { NgxSliderModule, Options } from '@angular-slider/ngx-slider';

// In @Component imports: [..., NgxSliderModule]
```

### Frontend: Using `date-fns` for relative time (already in package.json)

```typescript
import { formatDistanceToNow } from 'date-fns';

getRelativeTime(isoString: string | undefined): string {
  if (!isoString) return 'Never';
  return formatDistanceToNow(new Date(isoString), { addSuffix: true });
  // e.g. "2 hours ago", "3 days ago"
}
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `nullsfirst()` for ASC sort | `nullslast()` for both directions (D-09) | Unscored assets no longer pollute top of grid |
| No score range filter | Dual-handle ngx-slider with score_min/score_max API params | Users can isolate high/low scorers |
| Fallback to placeholder.svg for videos | Dark bg + platform icon + VIDEO tag (D-06) | Visually communicates "this is a video" instead of a broken image |
| No health visibility | Health badge + last sync time + reconnect per connection (D-12) | Users can see stale/expired connections without navigating elsewhere |

## Open Questions

1. **sync_status column collision with health badge**
   - What we know: The table has an existing `Status` column showing `sync_status` (ACTIVE/EXPIRED/ERROR/PENDING). The new health badge is conceptually similar.
   - What's unclear: Whether to replace the Status column entirely with the health badge, or add a separate column.
   - Recommendation: Replace the existing Status chip with the new health badge (derived state is richer). Keep `sync_status` internally but don't show it separately. This avoids adding a new column and reduces noise.

2. **Score filter when `score_min`/`score_max` are at default (0 and 100)**
   - What we know: Decision D-03 says default = full range = no filter applied.
   - What's unclear: Should the backend treat absent params differently from `score_min=0&score_max=100`?
   - Recommendation: Only add WHERE clauses if `score_min > 0` or `score_max < 100`. Frontend should omit params at defaults. Backend should only filter when params are present.

3. **Assets with `total_score = NULL` when score range filter is active**
   - What we know: If a user sets `score_min=50`, unscored assets (NULL score) would be excluded — this may or may not be desired.
   - What's unclear: User expectation — should unscored assets always appear, or only when the slider is at full range?
   - Recommendation: When `score_min` or `score_max` params are present, exclude NULL-scored assets (they have no score to compare). Document this in tooltips as "Shows only scored creatives within range."

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend npm install | ✓ | v24.14.0 | — |
| npm | `npm install @angular-slider/ngx-slider@17.0.2` | ✓ | 11.11.0 | — |
| Python 3.12+ | Backend test run | ✗ (3.9.6 detected) | 3.9.6 | pyproject.toml requires >=3.12; use Docker for tests |
| pytest | Backend unit tests | ✓ | 8.4.2 | — |

**Missing dependencies with no fallback:**
- Python 3.12+ on host: `pyproject.toml` specifies `requires-python = ">=3.12"` but host has 3.9.6. Backend tests must run inside Docker (`docker-compose exec backend pytest`) or be noted as host-skipped.

**Missing dependencies with fallback:**
- None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 |
| Config file | `/pyproject.toml` (root) — `testpaths = ["backend/tests"]`, `asyncio_mode = "auto"` |
| Quick run command | `docker-compose exec backend pytest backend/tests/test_dashboard_score_filter.py -x` |
| Full suite command | `docker-compose exec backend pytest backend/tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-01 | `getTileThumbnail()` returns null for VIDEO with no thumbnail | unit (frontend logic) | manual inspect / Angular test | ❌ Wave 0 |
| DASH-04 | Score sort `nullslast()` on both ASC and DESC | unit | `pytest backend/tests/test_dashboard_score_filter.py::test_score_sort_nulls_last -x` | ❌ Wave 0 |
| DASH-05 | `score_min`/`score_max` query params filter correctly | unit | `pytest backend/tests/test_dashboard_score_filter.py::test_score_range_filter -x` | ❌ Wave 0 |
| REL-01 | Health state computation: connected/token_expired/sync_failed | unit (frontend logic) | manual inspect | ❌ Wave 0 |
| REL-03 | SCHEDULER_ENABLED guard | Already covered in Phase 3 | — | ✓ (existing) |

Note: DASH-02, DASH-03 verified via Phase 3 implementation — no new tests needed. REL-02 is behavioral (OAuth redirect) — manual-only.

### Sampling Rate
- **Per task commit:** `docker-compose exec backend pytest backend/tests/ -x -q`
- **Per wave merge:** same
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_dashboard_score_filter.py` — covers DASH-04 (nullslast), DASH-05 (score_min/score_max params)
- [ ] `backend/tests/conftest.py` already exists — check if dashboard async fixtures are present

## Sources

### Primary (HIGH confidence)
- Code inspection: `backend/app/schemas/platform.py` — confirmed `token_expiry` absent from `PlatformConnectionResponse`
- Code inspection: `backend/app/models/platform.py` line 46 — `token_expiry` field exists on model
- Code inspection: `backend/app/api/v1/endpoints/dashboard.py` lines 212–227 — sort_col_map and current nullslast usage
- Code inspection: `frontend/src/app/features/dashboard/dashboard.component.ts` line 125 — sends `total_score`, backend maps only `"score"`
- npm registry: `@angular-slider/ngx-slider@17.0.2` peer deps confirmed compatible with Angular 17.x

### Secondary (MEDIUM confidence)
- npm registry inspection: `@angular-slider/ngx-slider` version history confirms v17.0.2 is the Angular 17 target release
- `date-fns` confirmed in `frontend/package.json` — `formatDistanceToNow` available without new dependency

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — ngx-slider version pinned and peer-dep verified against npm registry; all other tooling is in-tree
- Architecture: HIGH — all integration points traced through actual source files
- Pitfalls: HIGH — `token_expiry` gap and sort key mismatch confirmed by code reading, not assumption

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (ngx-slider version range is stable; Angular 17 LTS)
