# Phase 8: Score-to-ROAS Correlation - Research

**Researched:** 2026-03-31
**Domain:** Angular 17 + ECharts 5.6 scatter chart; right-side overlay drawer; client-side data filtering/statistics
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** The existing Avg ROAS stat tile in the dashboard header stats row is made clickable. It opens a right-side slide-in drawer (overlay panel) containing the scatter chart. The tile gets a visual affordance (cursor pointer + subtle hover state).
- **D-02:** No new persistent panel added to main dashboard layout. Scatter chart lives exclusively inside the drawer.
- **D-03:** Drawer is self-contained: scatter chart + spend threshold input + close control. Overlays without pushing content.
- **D-04:** Reference lines are dynamic — computed from median score x median ROAS of the currently visible (filtered + spend-threshold-applied) dataset. Lines update when dataset changes.
- **D-05:** Quadrant labels: Stars (top-right), Workhorses (top-left), Question Marks (bottom-right), Laggards (bottom-left).
- **D-06:** Quadrant labels: subtle, low-contrast text in each corner — not distracting, clearly legible.
- **D-07:** Hover shows tooltip per CORR-01: thumbnail, score, ROAS, spend, platform.
- **D-08:** Clicking a dot opens the AssetDetailDialogComponent — same as creative grid card click.
- **D-09:** Minimum spend threshold input is inside the drawer panel. Does not affect main dashboard filter bar or creative grid.
- **D-10:** Default threshold: $10. User can edit inline (number input with currency prefix).
- **D-11:** Null ROAS (no ROAS data) — excluded from the chart.
- **D-12:** Zero ROAS (data exists but ROAS = 0) — plotted at Y = 0, visually distinct from null.
- **D-13:** Y-axis capped at 99th percentile of ROAS in visible dataset. Capped assets plotted at cap value with visual indicator.

### Claude's Discretion

- Angular Material component for drawer: use MatDrawer / MatSidenav in "over" mode, anchored right side. cdkOverlayPanel or custom right-side overlay acceptable if MatDrawer adds layout complexity.
- ECharts ScatterChart registration — add ScatterChart to existing `echarts.use([...])` call in dashboard.component.ts.
- Dot size: scale by spend (larger = larger dot) or fixed size. Either acceptable.
- Quadrant label opacity and font size — subtle.
- Y-axis cap indicator style (dotted reference line, annotation, or clip with visual cue at top).
- Drawer width: 480–600px.

### Deferred Ideas (OUT OF SCOPE)

- Per-platform ROAS correlation breakdown — future v1.2+.
- Highlighting a clicked dot in the creative grid below.
- Configurable per-org quadrant thresholds — dynamic median is sufficient for v1.1.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORR-01 | Dashboard includes a score-to-ROAS scatter chart (ECharts) with quadrant reference lines (Stars / Question Marks / Workhorses / Laggards) and hover tooltips showing thumbnail, score, ROAS, spend, platform | ECharts 5.6 ScatterChart + MarkLineComponent confirmed available; custom HTML tooltip formatter pattern documented below |
| CORR-02 | Scatter chart filters out assets below a configurable minimum spend threshold (default $10), treats null and zero ROAS distinctly, and caps Y-axis at the 99th percentile | Client-side filtering pattern confirmed; 99th percentile calculation documented; ECharts yAxis.max configurable; null vs zero ROAS distinction confirmed in existing data model |
</phase_requirements>

---

## Summary

Phase 8 adds a score-to-ROAS scatter chart inside a right-side drawer triggered by clicking the Avg ROAS stat tile. The implementation is almost entirely frontend — the existing `GET /dashboard/assets` endpoint already returns `total_score`, `roas`, `spend`, `thumbnail_url`, and `platform` per asset, which is exactly what the scatter chart needs. No new backend endpoint is required, but there is a critical concern: the endpoint is paginated (default page_size=50, max=250), meaning the scatter chart needs all assets, not just the current page. A dedicated unpaginated endpoint `GET /dashboard/correlation-data` is necessary.

The ECharts scatter chart uses `ScatterChart` from `'echarts/charts'` and `MarkLineComponent` from `'echarts/components'` — both verified present in the installed echarts@5.6.0. The drawer uses Angular Material's `MatSidenavModule` (already in `@angular/material@17.3.0`) in "over" mode. All data processing (spend filtering, null/zero ROAS separation, 99th percentile calculation, median computation) is done client-side in a computed property.

**Primary recommendation:** Add a dedicated `/dashboard/correlation-data` backend endpoint that returns all scored assets with ROAS data (no pagination, scoped to current org + date/platform filters). Process all statistical derivations (99th pct cap, median lines, quadrant assignment) on the frontend for immediate reactivity to threshold changes.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| echarts | 5.6.0 (installed) | Scatter chart rendering | Already in use for LineChart in this project |
| ngx-echarts | 17.2.0 (installed) | Angular directive wrapper for echarts | Already set up with `provideEchartsCore` |
| @angular/material | 17.3.0 (installed) | MatSidenav drawer + MatFormField | Already in use throughout dashboard |
| @angular/cdk | 17.3.0 (installed) | CDK overlay primitives (used by MatSidenav) | Required by MatSidenav internally |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ScatterChart (echarts/charts) | 5.6.0 | Scatter series type | Add to echarts.use([]) call |
| MarkLineComponent (echarts/components) | 5.6.0 | Reference lines (median X, median Y, 99th pct cap) | Add to echarts.use([]) call |
| MatSidenavModule (@angular/material/sidenav) | 17.3.0 | Right-side overlay drawer | Import in dashboard component |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| MatSidenav | Custom `position:fixed` div + animation | MatSidenav handles focus trap, backdrop, keyboard (Escape to close) automatically; custom div requires manual implementation — not worth it |
| MarkLine for reference lines | Custom rendered annotations | MarkLine integrates with ECharts coordinate system cleanly; renders correctly on resize |

**Installation:** No new packages needed. All required libraries are already installed.

**Version verification:** echarts@5.6.0 confirmed via `node_modules/echarts/package.json`. `ScatterChart` confirmed in `echarts/charts` sub-package. `MarkLineComponent` confirmed in `echarts/components` sub-package.

---

## Architecture Patterns

### Critical Finding: Pagination Problem

The existing `/dashboard/assets` endpoint is paginated with `page_size` max 250. The scatter chart needs ALL scored assets with ROAS, not just a page. The scatter chart's value comes from showing the full picture — a paginated view would show misleading quadrant distributions.

**Solution:** Add a new endpoint `GET /dashboard/correlation-data` that returns ALL assets with `total_score IS NOT NULL` AND `roas IS NOT NULL OR roas = 0` (zero-ROAS assets must be included), scoped to current org + date range + platform filters. No pagination. This endpoint only returns the fields needed by the scatter chart: `id`, `ad_name`, `platform`, `thumbnail_url`, `total_score`, `roas`, `spend`.

The `/dashboard/assets` endpoint query already has the subquery pattern for aggregating `roas` and `total_spend` per asset. The correlation endpoint reuses the same `perf_subq` pattern but without pagination and with a tighter column selection.

### Recommended Project Structure

```
frontend/src/app/features/dashboard/
├── dashboard.component.ts        # Add drawer state + scatter logic here
├── dialogs/
│   └── asset-detail-dialog.component.ts   # No change
backend/app/api/v1/endpoints/
└── dashboard.py                  # Add GET /dashboard/correlation-data
```

No new component files needed. The drawer and chart live inline in `dashboard.component.ts` (same pattern as the score trend panel).

### Pattern 1: ECharts Scatter with MarkLine (Reference Lines)

**What:** ScatterChart series with two MarkLine entries on the scatter series (one vertical = median X, one horizontal = median Y), plus a third series or MarkLine for the 99th pct cap line.

**When to use:** When reference lines must dynamically update with the dataset (they're defined inside the series options, so updating the `options` object causes them to re-render).

```typescript
// Source: echarts 5.6.0 installed — verified exports
import { ScatterChart } from 'echarts/charts';
import { MarkLineComponent, GridComponent, TooltipComponent } from 'echarts/components';

// In echarts.use() call — add to existing array:
echarts.use([LineChart, ScatterChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer]);

// EChartsOption for scatter:
const option: EChartsOption = {
  tooltip: {
    trigger: 'item',
    formatter: (params: any) => {
      const d = params.data; // [score, roas, assetObject]
      return `<div class="scatter-tooltip">
        <img src="${d[2].thumbnail_url}" style="width:48px;height:48px;object-fit:cover;border-radius:4px">
        <div>${d[2].ad_name}</div>
        <span>Score: ${d[0]} · ROAS: ${d[1].toFixed(2)}x · Spend: $${d[2].spend}</span>
      </div>`;
    }
  },
  xAxis: { name: 'ACE Score', min: 0, max: 100 },
  yAxis: { name: 'ROAS', min: 0, max: roasCap },
  series: [{
    type: 'scatter',
    symbolSize: 8,
    data: scatterData, // [score, roas, assetRef][]
    markLine: {
      silent: true,
      symbol: 'none',
      lineStyle: { color: 'var(--border)', type: 'dashed', width: 1 },
      data: [
        { xAxis: medianScore },   // vertical line at median score
        { yAxis: medianRoas },    // horizontal line at median roas
      ]
    }
  }]
};
```

### Pattern 2: MatSidenav in "Over" Mode (Right-Side Drawer)

**What:** `MatSidenavContainer` wraps the full dashboard content. The `MatSidenav` is positioned `end` (right side), mode `over` (overlays without pushing content). Open/close via `sidenav.toggle()` or `sidenav.open()` / `sidenav.close()`.

**When to use:** Whenever an overlay panel should slide in from the right without affecting main content layout.

```typescript
// Source: @angular/material/sidenav 17.3.0
import { MatSidenavModule } from '@angular/material/sidenav';

// In imports array of dashboard component:
// MatSidenavModule

// Template structure:
// <mat-sidenav-container class="dashboard-sidenav-container">
//   <mat-sidenav #correlationDrawer mode="over" position="end" [style.width.px]="560">
//     <!-- drawer content -->
//   </mat-sidenav>
//   <mat-sidenav-content>
//     <!-- existing dashboard content -->
//   </mat-sidenav-content>
// </mat-sidenav-container>
```

**Critical layout pitfall:** `mat-sidenav-container` requires a defined height. If it's inside a scrolling page container, the container must have `height: 100%` propagated from the host. The existing `.dashboard-page` wrapper sets `position: relative` — the sidenav-container needs `height: 100vh` or similar. See Common Pitfalls section.

**Alternative confirmed:** A custom `position: fixed; right: 0; top: 0; height: 100vh` div with Angular animations also works and avoids the height-propagation issue. Given the existing patterns use `position: fixed` for context menus already, this may be simpler.

### Pattern 3: Client-Side Statistical Computation

**What:** Compute median, 99th percentile, and quadrant assignment in the Angular component from the raw asset array. Update whenever spend threshold changes — no API round-trip needed.

```typescript
// Computed from filtered assets — runs synchronously on threshold change
buildScatterData(assets: CorrelationAsset[], minSpend: number): ScatterDataResult {
  // 1. Filter: must have total_score, spend >= minSpend, roas !== null
  const eligible = assets.filter(a =>
    a.total_score !== null &&
    (a.spend ?? 0) >= minSpend &&
    a.roas !== null  // null = excluded; 0 = included (zero ROAS)
  );

  // 2. 99th percentile cap
  const roasValues = eligible.map(a => a.roas!).sort((a, b) => a - b);
  const p99Index = Math.floor(roasValues.length * 0.99);
  const roasCap = roasValues[p99Index] ?? roasValues[roasValues.length - 1] ?? 1;

  // 3. Median score + median ROAS (for reference lines)
  const scores = eligible.map(a => a.total_score!).sort((a, b) => a - b);
  const midS = Math.floor(scores.length / 2);
  const medianScore = scores.length % 2 ? scores[midS] : (scores[midS - 1] + scores[midS]) / 2;

  const roasSorted = [...roasValues]; // already sorted
  const midR = Math.floor(roasSorted.length / 2);
  const medianRoas = roasSorted.length % 2 ? roasSorted[midR] : (roasSorted[midR - 1] + roasSorted[midR]) / 2;

  // 4. Assign quadrant color per asset
  // ...
  return { eligible, roasCap, medianScore, medianRoas };
}
```

### Pattern 4: Per-Dot Click Opening Asset Detail Dialog

**What:** ECharts emits a `(chartClick)` event from `NgxEchartsDirective`. The event `params.data` contains the asset reference stored as the third element of each data tuple. Use the same `openAssetDetail()` pattern already in the dashboard.

```typescript
// Template:
// <div echarts [options]="scatterOptions" (chartClick)="onScatterClick($event)" class="echart-box"></div>

onScatterClick(params: any): void {
  if (params.componentType === 'series') {
    const asset = params.data[2] as CorrelationAsset;
    this.correlationDrawer.close();
    this.openAssetDetail(asset as any);
  }
}
```

### Pattern 5: Zero ROAS vs Null ROAS Distinction

**What:** The existing backend returns `roas: float | None` from the perf subquery. Zero ROAS (`conversion_value = 0, spend > 0`) produces `roas = 0.0`. Null ROAS means no performance data for that asset in the period.

**How to distinguish in frontend:**
- `roas === null` → exclude from scatter (D-11)
- `roas === 0` → plot at Y = 0 with distinct visual (D-12): use `var(--text-muted)` fill at 60% opacity

**Backend filter for correlation endpoint:** `WHERE perf.roas IS NOT NULL` would exclude zero-ROAS assets incorrectly. The filter must be `WHERE perf.total_spend >= :min_spend AND perf.roas IS NOT NULL` is wrong — use `WHERE perf.total_spend IS NOT NULL` (asset has any data) and let the frontend filter by spend threshold. The backend should return both null-ROAS-excluded and zero-ROAS-included: `WHERE scoring_status = 'COMPLETE' AND total_score IS NOT NULL`.

Actually, cleaner: the correlation endpoint should return all scored assets with performance data. The frontend handles: exclude null ROAS, include zero ROAS, exclude below spend threshold. This keeps all filtering logic in one place (client-side) for instant reactivity to threshold changes.

### Anti-Patterns to Avoid

- **Reusing the paginated `/dashboard/assets` endpoint:** Would only show the current page's assets in the scatter chart — misleading quadrant distributions. Use a dedicated unpaginated endpoint.
- **Server-side spend threshold filtering:** The threshold changes interactively in the drawer; a server-side filter would require a new API call on every keystroke. Client-side filtering is instant and correct.
- **Using `ngx-echarts` `[merge]="true"` when replacing full options:** When the dataset changes substantially (new filter applied), use full options replacement (`[merge]="false"` or just reassign `options`). Use `[merge]="true"` only for incremental tooltip/animation updates.
- **Putting `mat-sidenav-container` inside a `height: auto` parent:** Will cause the sidenav to have zero height. The container needs a defined height — either `100vh` or the alternative fixed-position custom overlay avoids this entirely.
- **Storing the full `DashboardAsset` objects as scatter data points:** Only store the fields needed for the tooltip (`id`, `ad_name`, `thumbnail_url`, `platform`, `total_score`, `roas`, `spend`) to keep the ECharts data array lightweight.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Right-side overlay drawer with backdrop + focus trap | Custom `position:fixed` div with manual backdrop/Escape key handling | MatSidenav in "over" mode | MatSidenav handles focus trap, keyboard dismissal, backdrop click, and ARIA automatically |
| Scatter rendering | Custom SVG/Canvas scatter | ECharts ScatterChart | Already installed; handles resize, HiDPI, tooltip positioning |
| Reference lines on chart | Custom SVG overlays | ECharts MarkLine | Tracks coordinate system on resize; declared in series options |
| 99th percentile calculation | Complex statistical library | Inline sort + index | Trivial for N < 10,000 assets; no library needed |

**Key insight:** All dependencies are already installed. The entire phase is wiring, not installation.

---

## Runtime State Inventory

Not applicable — this phase adds new UI features (drawer, scatter chart) with no renaming or data migration. The new backend endpoint creates no new tables.

---

## Common Pitfalls

### Pitfall 1: MatSidenav Container Height Collapse

**What goes wrong:** The scatter chart area renders as 0px tall; the drawer opens but appears empty or collapsed.

**Why it happens:** `mat-sidenav-container` requires its host to have a defined height. If the `.dashboard-page` div is `height: auto` (typical for a scrollable page), the sidenav container collapses. ECharts renders into a zero-height container and shows nothing.

**How to avoid:** Either (a) set `mat-sidenav-container` to `position: fixed; inset: 0` and manage the dashboard content as `mat-sidenav-content` with scroll — or (b) skip MatSidenav entirely and use a custom `position: fixed; right: 0; top: 0; height: 100vh; width: 560px` div with Angular animations. Option (b) is likely simpler given the existing dashboard is a scrollable page container.

**Warning signs:** Chart area is invisible; `echarts` div has `height: 0` in DevTools; no errors thrown.

### Pitfall 2: ECharts MarkLine Does Not Show on Scatter Series

**What goes wrong:** Reference lines (median score / median ROAS) are not visible on the chart.

**Why it happens:** `MarkLineComponent` must be included in the `echarts.use([...])` call at module level. Forgetting to add it means it silently doesn't register and markLine options are ignored.

**How to avoid:** Add `MarkLineComponent` to the existing `echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])` call — becomes `echarts.use([LineChart, ScatterChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer])`. This call runs once at module level in `dashboard.component.ts`.

**Warning signs:** No errors, but reference lines are absent from chart.

### Pitfall 3: Tooltip with HTML Requires `useHTML: true` — No, Wrong Library

**What goes wrong:** ECharts tooltip shows raw HTML string instead of rendered HTML.

**Why it happens:** ECharts uses its own tooltip rendering. To render HTML in the tooltip, the `formatter` function must return an HTML string AND the tooltip must have no `renderMode: 'svg'` override. In canvas mode (CanvasRenderer), ECharts renders tooltips as HTML overlays by default. No special flag needed.

**How to avoid:** Use `formatter: (params) => '<div>...</div>'` returning a string. ECharts will render it as HTML in a positioned div overlay. Confirm `CanvasRenderer` is used (it is, per existing `echarts.use` call).

**Warning signs:** Tooltip shows literal `<img>` text instead of image.

### Pitfall 4: Zero ROAS Assets Silently Excluded by Backend Filter

**What goes wrong:** Zero-ROAS assets (legitimate awareness campaigns) disappear from scatter chart even though D-12 says to plot them at Y = 0.

**Why it happens:** A naive backend filter `WHERE roas > 0` or `WHERE roas IS NOT NULL AND roas != 0` would exclude them. Even `float(row.roas) if row.roas else None` — because `float(0.0)` is falsy in Python — returns `None` for zero ROAS.

**How to avoid:** The existing dashboard endpoint already has this bug pattern: `"roas": float(row.roas) if row.roas else None` at line 345 of dashboard.py. The correlation endpoint MUST use `float(row.roas) if row.roas is not None else None` to preserve zero values. The frontend then checks `roas !== null` (exclude) vs `roas === 0` (plot at Y=0).

**Warning signs:** Zero-ROAS assets absent from chart; only positive ROAS values visible.

### Pitfall 5: Single-Point Median Calculation

**What goes wrong:** When only 1 asset qualifies (after spend threshold filter), the median calculation throws or returns undefined, crashing the chart.

**Why it happens:** An empty or single-element array breaks even/odd median logic.

**How to avoid:** Guard: if `eligible.length === 0`, show empty state. If `eligible.length === 1`, use the single point's values as medians. Add guards before all statistical computations.

**Warning signs:** Chart component crashes on first render after raising spend threshold past most assets.

### Pitfall 6: ECharts Chart Click Fires on MarkLine Clicks Too

**What goes wrong:** Clicking a reference line also fires `chartClick`, triggering `openAssetDetail()` with undefined data.

**Why it happens:** ECharts `chartClick` fires for all chart components by default.

**How to avoid:** In the click handler, guard: `if (params.componentType === 'series' && params.componentSubType === 'scatter') { ... }`. MarkLine events have `componentType === 'markLine'`.

**Warning signs:** Clicking reference lines opens a blank asset detail dialog.

---

## Code Examples

Verified patterns from codebase inspection:

### Existing echarts.use() Call (dashboard.component.ts line 28)

```typescript
// Source: frontend/src/app/features/dashboard/dashboard.component.ts line 28
echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

// Phase 8 addition — becomes:
echarts.use([LineChart, ScatterChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer]);

// Import additions at top of file:
import { ScatterChart } from 'echarts/charts';
import { MarkLineComponent } from 'echarts/components';
```

### Existing openAssetDetail() Pattern (dashboard.component.ts line 1088)

```typescript
// Source: frontend/src/app/features/dashboard/dashboard.component.ts line 1088
async openAssetDetail(asset: DashboardAsset): Promise<void> {
  this.contextMenu.visible = false;
  const { AssetDetailDialogComponent } = await import('../dashboard/dialogs/asset-detail-dialog.component');
  this.dialog.open(AssetDetailDialogComponent, {
    width: '96vw',
    maxWidth: '1800px',
    height: '92vh',
    data: {
      assetId: asset.id,
      dateFrom: this.dateFrom,
      dateTo: this.dateTo,
      selectedPreset: this.selectedPreset,
      preloaded: this.assetDetailCache.get(asset.id) || null,
    },
    panelClass: 'asset-detail-dialog',
  });
}
```

### Backend: Avoiding the Zero-ROAS Falsy Bug

```python
# Source: backend/app/api/v1/endpoints/dashboard.py line 345 (EXISTING BUG — do not copy)
# BUG: "roas": float(row.roas) if row.roas else None   # drops zero-ROAS!

# CORRECT pattern for correlation endpoint:
"roas": float(row.roas) if row.roas is not None else None  # preserves 0.0
```

### Backend: Correlation Endpoint Skeleton

```python
@router.get("/correlation-data")
async def get_correlation_data(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    platforms: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """All scored assets with performance data for scatter chart.
    No pagination — returns complete dataset for the org+filter combination.
    Returns assets where scoring_status='COMPLETE' AND total_score IS NOT NULL.
    Includes zero-ROAS assets (roas=0.0 preserved, not coerced to None).
    """
    # Reuse perf_subq pattern from get_dashboard_assets()
    # JOIN on CreativeScoreResult for total_score
    # WHERE scoring_status = 'COMPLETE' AND total_score IS NOT NULL
    # WHERE perf.total_spend IS NOT NULL  (asset has any perf data in period)
    # No pagination, no offset/limit
    # Return: [{id, ad_name, platform, thumbnail_url, total_score, roas, spend}]
```

### Scatter Options with Dynamic Reference Lines

```typescript
// Computed whenever eligible dataset changes
buildScatterOptions(
  data: [number, number, CorrelationAsset][],
  medianScore: number,
  medianRoas: number,
  roasCap: number,
): EChartsOption {
  return {
    grid: { top: 40, right: 20, bottom: 40, left: 60 },
    xAxis: {
      name: 'ACE Score', min: 0, max: 100,
      axisLine: { lineStyle: { color: 'var(--border)' } },
      splitLine: { lineStyle: { color: 'var(--border)', opacity: 0.2 } },
    },
    yAxis: {
      name: 'ROAS', min: 0, max: roasCap,
      axisLine: { lineStyle: { color: 'var(--border)' } },
      splitLine: { lineStyle: { color: 'var(--border)', opacity: 0.2 } },
    },
    tooltip: { trigger: 'item', formatter: this.tooltipFormatter },
    series: [
      {
        type: 'scatter',
        symbolSize: 8,
        data: data,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#404040', type: 'dashed', width: 1 },
          data: [
            { xAxis: medianScore },
            { yAxis: medianRoas },
            { yAxis: roasCap, lineStyle: { color: 'rgba(255,119,0,0.4)', type: 'dashed' } },
          ],
        },
        itemStyle: {
          // Color by quadrant: computed per-point via callback
          color: (params: any) => {
            const [score, roas] = params.data;
            if (score >= medianScore && roas >= medianRoas) return '#FF7700'; // Stars
            if (score < medianScore && roas >= medianRoas) return '#F39C12';  // Workhorses
            if (score >= medianScore && roas < medianRoas) return '#4285F4';  // Question Marks
            return '#707070'; // Laggards
          }
        }
      }
    ],
  };
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ECharts v4 (standalone) | ECharts v5 tree-shakeable core (`echarts/core`, `echarts/charts`, `echarts/components`) | ECharts 5.0 (2021) | Must import `ScatterChart` and `MarkLineComponent` separately — not from root `'echarts'` |
| `[options]="options"` causing full re-render | `[options]="options" [merge]="true"` for incremental updates | ngx-echarts 7+ | Use merge for spend threshold changes to avoid chart flicker |

**Deprecated/outdated:**
- `import { use } from 'echarts'` then `use([...])`: The top-level `echarts` import in this project already works via `import * as echarts from 'echarts/core'` pattern — confirmed working from existing LineChart usage.

---

## Open Questions

1. **Should dot click close the drawer first, then open dialog, or open dialog while drawer is still visible?**
   - What we know: D-08 says "clicking a dot opens AssetDetailDialogComponent". The UI-SPEC says "Drawer closes (200ms slide-out); asset detail dialog opens immediately after."
   - What's unclear: Whether to await the drawer close animation before opening the dialog (avoids visual clash) or fire both simultaneously.
   - Recommendation: Close drawer first (`correlationDrawer.close()`), open dialog in the `afterClosed()` or after 200ms delay to match animation duration. Alternatively open both simultaneously — the dialog is full-screen and covers the drawer anyway.

2. **Does the correlation endpoint need format/objective filters?**
   - What we know: CONTEXT.md says scatter "respects these filters (assets shown match the grid's current filter state)". The dashboard currently has date, platform, format, objective, score range, project filters.
   - What's unclear: Whether ALL filters should be passed to the correlation endpoint or just date+platform.
   - Recommendation: Pass date_from, date_to, platforms (same as grid). Omit format/objective/score filters since the scatter chart should show the full scoring-vs-ROAS picture without score range bias. This is a planner decision — flag it.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| echarts | Scatter chart | ✓ | 5.6.0 | — |
| ngx-echarts | Angular ECharts directive | ✓ | 17.2.0 | — |
| @angular/material | MatSidenav, MatFormField | ✓ | 17.3.0 | Custom fixed-div overlay |
| @angular/cdk | CDK used by MatSidenav | ✓ | 17.3.0 | — |
| Python pytest | Backend tests | ✓ | 8.4.2 | — |
| Node.js | Frontend build | ✓ | 24.14.0 | — |
| Docker | Dev environment | ✓ | 29.2.1 | — |

**Missing dependencies with no fallback:** None — all required dependencies are installed.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 |
| Config file | `backend/tests/conftest.py` (exists) |
| Quick run command | `cd backend && python -m pytest tests/test_correlation.py -x` |
| Full suite command | `cd backend && python -m pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORR-01 | `GET /dashboard/correlation-data` returns scored assets with `total_score`, `roas`, `spend`, `thumbnail_url`, `platform` | unit | `pytest tests/test_correlation.py::test_correlation_data_returns_scored_assets -x` | ❌ Wave 0 |
| CORR-01 | Null ROAS assets excluded from response (D-11) | unit | `pytest tests/test_correlation.py::test_null_roas_excluded -x` | ❌ Wave 0 |
| CORR-02 | Zero ROAS assets included with roas=0.0 (D-12, falsy-bug prevention) | unit | `pytest tests/test_correlation.py::test_zero_roas_preserved -x` | ❌ Wave 0 |
| CORR-02 | Assets with spend below threshold not returned when filtered client-side | unit (pure function) | `pytest tests/test_correlation.py::test_spend_threshold_filter -x` | ❌ Wave 0 |
| CORR-02 | Endpoint returns assets without pagination (no `page`/`total_pages` keys) | unit | `pytest tests/test_correlation.py::test_no_pagination -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_correlation.py -x`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_correlation.py` — covers CORR-01, CORR-02
- [ ] Ensure `conftest.py` fixtures cover the new endpoint (mock DB session pattern from `test_performer_tag.py`)

---

## Project Constraints (from CLAUDE.md)

CLAUDE.md does not exist in this project root. No project-specific overrides detected. Conventions inferred from codebase inspection:

- All Angular components are standalone (no NgModule declarations)
- Imports listed in component `imports: []` array, not in a shared module
- ECharts registered once at file level via `echarts.use([...])` — not in constructor
- Lazy imports used for dialogs: `await import('...')` pattern (lines 1090, 1107, 1123)
- CSS variables from `styles.scss` used throughout — no hardcoded colors (`var(--accent)`, `var(--bg-card)`, etc.)
- Bootstrap Icons (`bi-*` class prefix) used for all icons — not Material Icons
- `var(--transition)` = `0.2s cubic-bezier(0.4, 0, 0.2, 1)` used for all animations

---

## Sources

### Primary (HIGH confidence)
- `frontend/src/app/features/dashboard/dashboard.component.ts` — ECharts registration pattern, `openAssetDetail()` implementation, aggStats template, agg-stat CSS, existing filter state
- `backend/app/api/v1/endpoints/dashboard.py` — pagination model, `perf_subq` pattern, zero-ROAS falsy bug at line 345, `_compute_performer_tag` reuse pattern
- `frontend/node_modules/echarts/charts.js` — confirmed `ScatterChart` export
- `frontend/node_modules/echarts/components.js` — confirmed `MarkLineComponent` export
- `frontend/node_modules/@angular/material/sidenav/index.d.ts` — confirmed MatSidenavModule available
- `.planning/phases/08-score-to-roas-correlation/08-CONTEXT.md` — all locked decisions
- `.planning/phases/08-score-to-roas-correlation/08-UI-SPEC.md` — design contract, component inventory, layout contract

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` — CORR-01, CORR-02 full text
- `.planning/STATE.md` — Phase 07 decisions carried forward

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries installed and verified via node_modules inspection
- Architecture: HIGH — existing endpoint code read directly; pagination concern confirmed from source
- Pitfalls: HIGH — zero-ROAS falsy bug identified directly in dashboard.py line 345; MatSidenav height pitfall confirmed from Angular Material docs pattern
- Test patterns: HIGH — conftest.py and test_performer_tag.py read directly as reference

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable dependencies; echarts 5.6 and Angular 17 are not fast-moving at patch level)
