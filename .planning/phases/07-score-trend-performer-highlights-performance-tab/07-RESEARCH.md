# Phase 7: Score Trend, Performer Highlights + Performance Tab - Research

**Researched:** 2026-03-30
**Domain:** Angular 17 frontend (ECharts, Angular Material), FastAPI backend (SQLAlchemy async, PostgreSQL window functions)
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Asset-level score trends are **not implemented**. BrainSuite scores are persistent/static per asset (Phase 5 D-09). TREND-02/TREND-03 are re-scoped to an aggregate view.
- **D-02:** New **dashboard panel/card above the creative grid** — shows average score trend across all scored assets over the selected date window. Visible on the main dashboard without opening any dialog.
- **D-03:** Data source: **compute on-the-fly** from existing `CreativeScoreResult.scored_at` + `total_score`. No new table. Backend query: `AVG(total_score) GROUP BY date_bucket WHERE scored_at IN [date_from, date_to]` — filtered by org_id and platform filters already in use.
- **D-04:** Default window: **30 days**. User can adjust via **DateRangePickerComponent** (already exists in the project). Chart uses ECharts LineChart (already installed: `ngx-echarts ^17.2.0`).
- **D-05:** No "Score Trend" tab in the asset detail dialog. Per-asset trend is not surfaced anywhere.
- **D-06:** Badge position: **bottom-left corner** of the grid card (score badge is bottom-right — badges are on opposite sides).
- **D-07:** Visual style: **small colored pill/chip** — "Top Performer" in green, "Below Average" in red. Compact and scannable.
- **D-08:** Labels unchanged: **"Top Performer"** / **"Below Average"**. Middle 80% ("Average") show **no badge** — only the extremes get a pill.
- **D-09:** Backend logic switch: `_get_performer_tag()` currently uses score thresholds (≥70 / ≥45). Replace with **`PERCENT_RANK() OVER (ORDER BY total_score)`** computed per org per request. Top 10% → "Top Performer", bottom 10% → "Below Average". **Minimum guard: if fewer than 10 scored assets exist, return null for all** (no badges).
- **D-10:** **Two-column top row** in Performance tab: Left tile = existing KPI trend chart; Right tile = Creative Asset card with header (label + rank badge), preview, filename/duration, and Spend + Impressions mini-tiles.
- **D-11:** **Full-width Performance Summary section** below the top row — metrics grouped by Delivery / Engagement / Conversions / Video / Platform-specific.
- **D-12:** **"Used in X campaigns" section** at the bottom with campaign URL patterns (Meta / TikTok / Google Ads / DV360).
- **D-13:** Overall design: tiles match CE tab aesthetic (`ce-pillar-card` / `ce-pillars-grid` style).
- **D-14:** Tabs in asset detail dialog after this phase: **Performance** | **Creative Effectiveness** (no Score Trend tab added).

### Claude's Discretion

- ECharts line chart color for the aggregate score trend panel (match existing orange accent or use a secondary palette color)
- Exact PERCENT_RANK() SQL expression and WHERE clause for performer tagging (filtered to org, minimum 10 COMPLETE-status scored assets)
- Campaign URL patterns for DV360 (research and implement best known pattern)
- Metric placement for any "orphan" platform-specific metrics that don't fit cleanly into Delivery/Engagement/Conversions/Video
- Null/zero metric handling in the Performance Summary grid (hide vs. grey out)
- Color palette for metric category icons (suggested above — Claude can adjust for consistency with existing theme)

### Deferred Ideas (OUT OF SCOPE)

- Per-asset score history table (`creative_score_history`) — invalidated by static score architecture.
- Score trend at dashboard/platform level segmented by platform.
- Areas of Interest (AOI) for Static API — already deferred in Phase 5.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TREND-02 | Score history written by the scoring job (re-scoped: aggregate score trend panel on dashboard, on-the-fly from `CreativeScoreResult`) | Backend: new `/dashboard/score-trend` endpoint queries `AVG(total_score) GROUP BY DATE(scored_at)` on existing table; no schema changes |
| TREND-03 | Asset detail Score Trend tab with ECharts line chart (re-scoped: aggregate panel above grid; no dialog tab) | Frontend: new `.score-trend-panel` section in `dashboard.component.ts`; `ngx-echarts` LineChart already imported in dialog — same pattern in dashboard |
| PERF-01 | Dashboard grid performer badge overlays using PERCENT_RANK() with 10-asset minimum guard | Backend: replace `_get_performer_tag()` with window-function subquery; Frontend: relocate `.tile-tag` to `position: absolute; bottom-left` inside `.tile-thumb` |
| UI-01 | Asset detail Performance tab re-laid out as tile/card grid matching CE tab visual style | Frontend: restructure `.perf-tab` using `.perf-top-row` two-column grid + `.perf-summary-group` metric categories + `.perf-campaigns-list` with external campaign links |
</phase_requirements>

---

## Summary

Phase 7 has three distinct deliverables: an aggregate score trend panel on the main dashboard, a performer badge system using relative ranking, and a full Performance tab redesign. All deliverables are frontend-heavy with moderate backend changes — no new database tables are required.

The aggregate score trend panel queries `CreativeScoreResult.scored_at` + `total_score` grouped by date for a given org, which is a straightforward SQL aggregation on existing data. The PERCENT_RANK() performer tagging replaces the current threshold-based `_get_performer_tag()` function with a window function subquery that also respects the 10-asset minimum guard. The Performance tab redesign is a pure UI restructuring — the data is already returned by the existing `GET /dashboard/assets/{asset_id}` endpoint; it just needs to be laid out differently.

The UI-SPEC (07-UI-SPEC.md) has been approved and fully specifies the component structure, CSS, copy, and ECharts configuration. All decisions are locked. No new npm packages are required — `ngx-echarts ^17.2.0` and Angular Material are already installed.

**Primary recommendation:** Three waves of work — (1) backend changes: score-trend endpoint + PERCENT_RANK() performer tagging, (2) frontend score-trend panel + performer badge relocation, (3) Performance tab full redesign. Each wave is independently testable.

---

## Standard Stack

### Core (already installed — no new packages)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ngx-echarts | ^17.2.0 | ECharts Angular wrapper for charts | Already in use in asset-detail-dialog; same import pattern |
| echarts | (peer dep) | Chart engine | `LineChart`, `GridComponent`, `TooltipComponent` already registered |
| @angular/material | ^17.x | UI components: MatTabsModule, MatTooltipModule | Already installed and used throughout |
| FastAPI + SQLAlchemy async | existing | Backend API + ORM | Project standard |
| PostgreSQL | existing | Database with window function support | `PERCENT_RANK()` is a PostgreSQL built-in window function |

### No New Packages Required
The UI-SPEC explicitly confirms: "No new npm packages introduced." All components use existing installed libraries.

---

## Architecture Patterns

### Recommended Project Structure for Phase 7

```
backend/app/api/v1/endpoints/
└── dashboard.py          # Add: GET /dashboard/score-trend endpoint
                          # Modify: _get_performer_tag() → PERCENT_RANK() window function

frontend/src/app/features/dashboard/
├── dashboard.component.ts    # Add: score trend panel, badge relocation
└── dialogs/
    └── asset-detail-dialog.component.ts  # Restructure: Performance tab layout
```

No new files are needed beyond tests.

### Pattern 1: Aggregate Score Trend Endpoint

**What:** New `GET /dashboard/score-trend` endpoint (or extend `/stats`) that returns `[{date, avg_score}]` grouped by `DATE(scored_at)` for assets in the org, filtered by the same date/platform parameters.

**When to use:** Called by the dashboard score trend panel on load and on date range change.

**SQL Pattern:**
```python
# Source: SQLAlchemy async pattern consistent with existing dashboard.py queries
from sqlalchemy import func, cast, Date

trend_query = (
    select(
        cast(CreativeScoreResult.scored_at, Date).label("score_date"),
        func.avg(CreativeScoreResult.total_score).label("avg_score"),
        func.count(CreativeScoreResult.id).label("count"),
    )
    .join(CreativeAsset, CreativeAsset.id == CreativeScoreResult.creative_asset_id)
    .where(
        CreativeAsset.organization_id == current_user.organization_id,
        CreativeScoreResult.scoring_status == "COMPLETE",
        CreativeScoreResult.scored_at >= date_from,
        CreativeScoreResult.scored_at <= date_to,
        # Platform filter: if platform_list, join to CreativeAsset and filter
    )
    .group_by(cast(CreativeScoreResult.scored_at, Date))
    .order_by(cast(CreativeScoreResult.scored_at, Date))
)
```

Response shape: `{"trend": [{"date": "2026-03-01", "avg_score": 67.4}, ...], "data_points": 12}`

Empty state guard: if `data_points < 2`, frontend shows the empty state (not the chart).

**Note on platform filter:** The platform attribute lives on `CreativeAsset.platform`, not on `CreativeScoreResult`. The join is already present in the endpoint pattern — add `.where(CreativeAsset.platform.in_(platform_list))` if platforms are specified.

### Pattern 2: PERCENT_RANK() Performer Tagging

**What:** Replace `_get_performer_tag()` function with a window-function subquery that computes `PERCENT_RANK()` across all scored assets in the org for each request.

**Critical constraint:** Must only count assets with `scoring_status = 'COMPLETE'` and a non-null `total_score`. The minimum guard of 10 scored assets means if the count is < 10, all tags return `null`.

**SQL Pattern (SQLAlchemy):**
```python
# Source: SQLAlchemy docs — window functions with over()
from sqlalchemy import func

# Subquery: compute PERCENT_RANK for every COMPLETE-scored asset in org
rank_subq = (
    select(
        CreativeScoreResult.creative_asset_id,
        func.percent_rank()
            .over(order_by=CreativeScoreResult.total_score)
            .label("pct_rank"),
        func.count(CreativeScoreResult.id)
            .over()
            .label("total_scored"),
    )
    .join(CreativeAsset, CreativeAsset.id == CreativeScoreResult.creative_asset_id)
    .where(
        CreativeAsset.organization_id == current_user.organization_id,
        CreativeScoreResult.scoring_status == "COMPLETE",
        CreativeScoreResult.total_score.isnot(None),
    )
    .subquery()
)
```

Then in the assets loop, look up each asset's `pct_rank` and `total_scored` from the subquery result. The helper logic becomes:

```python
def _compute_performer_tag(pct_rank: float | None, total_scored: int) -> str | None:
    if pct_rank is None or total_scored < 10:
        return None  # no badge
    if pct_rank >= 0.90:
        return "Top Performer"
    if pct_rank <= 0.10:
        return "Below Average"
    return None  # middle 80% — no badge
```

**Important:** `PERCENT_RANK()` returns 0.0 for the lowest-ranked asset and approaches 1.0 for the highest. So:
- `pct_rank >= 0.90` → top 10% → "Top Performer"
- `pct_rank <= 0.10` → bottom 10% → "Below Average"
- Otherwise → `None` (no badge rendered, not "Average")

This is a behavioral change from the current implementation which always returns a tag value. The frontend must handle `null` performer_tag by rendering nothing (which it already does correctly — the `.tile-tag` div only renders if `performer_tag` has a value).

**Performance note:** The subquery computes once per request and is joined to the main asset query. For orgs with hundreds of scored assets this is efficient — PostgreSQL window functions execute in a single pass.

### Pattern 3: Score Trend Panel in Dashboard

**What:** New panel inserted between the filter toolbar and the assets grid in `dashboard.component.ts`.

**When to use:** Always visible on the dashboard. Collapses to empty state if < 2 data points.

**Angular/ECharts Pattern (consistent with asset-detail-dialog.component.ts):**
```typescript
// Source: existing pattern in asset-detail-dialog.component.ts lines 11-15, 115, 207-208
import { NgxEchartsDirective, provideEchartsCore } from 'ngx-echarts';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';

// Template binding (same pattern as dialog):
// <div echarts [options]="scoreTrendOptions" class="echart-box"></div>

scoreTrendOptions: EChartsOption = {
  color: ['#FF7700'],  // accent color per UI-SPEC
  xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 12 } },
  yAxis: { type: 'value', min: 0, max: 100, axisLabel: { fontSize: 12 } },
  series: [{ type: 'line', data: scores, smooth: true, lineStyle: { width: 2 } }],
  tooltip: { trigger: 'axis', formatter: (params: any) => `Score: ${params[0].value}` },
  grid: { left: 40, right: 20, top: 16, bottom: 32 },
};
```

**Dashboard component needs:** Add `NgxEchartsDirective` to imports array, register `echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])`. The dialog already does this — replicate the pattern.

### Pattern 4: Performer Badge Relocation (CSS Only)

**What:** Move `.tile-tag` from `.tile-body` to `.tile-thumb` (the relative-positioned thumbnail container) as an absolute-positioned element at bottom-left.

**Current state:** `.tile-tag` is inside `.tile-body` (below the thumbnail), rendered as an inline-block element. The dashboard template at line 276 shows `<div class="tile-tag" [class]="getTagClass(...)">`.

**Required changes:**
1. Move the `<div class="tile-tag">` from inside `.tile-body` to inside `.tile-thumb` (alongside existing `.overlay-ace`, `.overlay-format`, `.overlay-platform` elements).
2. Update CSS: change `.tile-tag` from `display: inline-block` to `position: absolute; bottom: 8px; left: 8px`.
3. Change null handling: only render the badge if `performer_tag` is not null (currently "Average" is rendered; after D-08 change the tag is null for middle 80%).

Per UI-SPEC line 164: "Middle 80%: no badge rendered." This means the `*ngIf` guard must be `*ngIf="asset.performer_tag"` (not displaying when null).

### Pattern 5: Performance Tab Restructure

**What:** Replace the existing two-column `.perf-layout` with a vertical flow:
1. `.perf-top-row` — two-column grid (KPI chart tile + Creative Asset tile)
2. `.perf-summary` — full-width Performance Summary with metric category groups
3. `.perf-campaigns` — full-width "Used in X campaigns" section

**Existing `.kpi-table` section** (lines 215-230 of asset-detail-dialog) gets replaced entirely. The existing `.asset-col` with asset preview and campaigns also gets replaced by the new structure.

**Campaign URL construction** — frontend helper method:
```typescript
getCampaignUrl(campaign: { campaign_id?: string; platform?: string }, asset: AssetDetailResponse): string {
  const cid = campaign.campaign_id ?? '';
  const act = asset.ad_account_id ?? '';  // need ad_account_id in response
  switch ((asset.platform || '').toLowerCase()) {
    case 'meta':
      return `https://www.facebook.com/adsmanager/manage/campaigns?act=${act}&campaign_ids=${cid}`;
    case 'tiktok':
      return `https://ads.tiktok.com/i18n/account/campaigns?keyword=${cid}`;
    case 'google_ads':
      return `https://ads.google.com/aw/campaigns?campaignId=${cid}`;
    case 'dv360':
      return `https://displayvideo.google.com/#ng_nav/p/${act}/c/${cid}`;
    default:
      return '';
  }
}
```

**Important:** The campaign URL construction for Meta requires `ad_account_id`. Currently `GET /dashboard/assets/{asset_id}` does NOT return `ad_account_id` in the response (confirmed at lines 475-640 of dashboard.py). The endpoint must be extended to include `ad_account_id` from `CreativeAsset.ad_account_id` (confirmed present in `creative.py` line 44).

**DV360 URL pattern:** The UI-SPEC specifies `https://displayvideo.google.com/#ng_nav/p/{account_id}/c/{campaign_id}`. This pattern uses DV360's partner_id (which maps to `ad_account_id` in the harmonized model) as the `p/` segment and the campaign ID as the `c/` segment. This is the canonical DV360 campaign deep-link pattern used in Display & Video 360 UI navigation. Confidence: MEDIUM (consistent with known DV360 URL structure; the UI-SPEC has already codified this).

**Metric category mapping** (from UI-SPEC, confirmed against `AssetPerformanceDetail` interface in component):

| Category | Backend fields (available in `detail.performance`) |
|----------|---------------------------------------------------|
| Delivery | spend, impressions, cpm, reach, clicks, frequency, cpp, cpc |
| Engagement | ctr, outbound_ctr, unique_ctr, inline_link_click_ctr, outbound_clicks, unique_clicks, inline_link_clicks, post_engagements, likes, comments, shares, follows |
| Conversions | roas, purchase_roas, cvr, conversions, cost_per_conversion, conversion_value, cost_per_result (= cost_per_conversion alias), purchases, purchase_value, leads, cost_per_lead, app_installs, cost_per_install, in_app_purchases, in_app_purchase_value |
| Video | video_views, vtr, video_plays, video_3_sec_watched, video_30_sec_watched, video_p25, video_p50, video_p75, video_p100, video_completion_rate, thruplay, cost_per_thruplay, trueview_views, focused_view, cost_per_focused_view, cost_per_view |
| Platform-specific | subscribe, offline_purchases, offline_purchase_value, messaging_conversations_started, estimated_ad_recallers, estimated_ad_recall_rate |

All these fields are confirmed present in `AssetPerformanceDetail` interface (lines 21-78 of asset-detail-dialog) and returned by the backend endpoint (lines 493-640 of dashboard.py).

**Null/zero handling decision (Claude's discretion):** Omit entirely null values. Show zero spend as "$0.00" (meaningful). All other zero values: omit. This matches the UI-SPEC states table: "Null spend → Show '$0.00'; Null impressions → Show '0'; all other null/zero: omit."

### Anti-Patterns to Avoid

- **Creating a new `creative_score_history` table:** Explicitly deferred (D-01). Do not implement.
- **Adding a Score Trend tab to the asset detail dialog:** Explicitly excluded (D-05, D-14).
- **Keeping threshold-based performer tagging:** Replace entirely with PERCENT_RANK() — do not add PERCENT_RANK as a fallback alongside thresholds.
- **Rendering "Average" performer_tag as a badge:** Middle 80% return `null` from backend; the frontend renders nothing. Remove the "Average" fallback in `getTagClass()`.
- **Importing new npm packages:** UI-SPEC prohibits new packages. Use existing `ngx-echarts`, Angular Material, Bootstrap Icons.
- **Using `@apply` or Tailwind:** This is an Angular Material + custom CSS variables project. No Tailwind.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Window function percentile ranking | Custom Python loop to rank assets | `func.percent_rank().over(order_by=...)` in SQLAlchemy | PostgreSQL computes in one pass; Python loop requires loading all assets to memory |
| Date grouping for trend | String manipulation on Python side | `cast(CreativeScoreResult.scored_at, Date)` + `GROUP BY` in SQL | DB-side grouping is more efficient and handles timezone consistently |
| ECharts line chart | Custom SVG chart | `NgxEchartsDirective` + `LineChart` from echarts/core | Already installed, used in dialog component, handles resize/tooltip/animation |
| Date range picker | Custom date input | `DateRangePickerComponent` (already in project) | Already used in both dashboard and dialog; consistent behavior and styling |
| Campaign URL construction | External API lookup | Simple string interpolation per platform | campaign_id and ad_account_id are already in the data model |

---

## Common Pitfalls

### Pitfall 1: PERCENT_RANK() Returns 0.0 for Lowest, ~1.0 for Highest
**What goes wrong:** Developer assumes top performers have `pct_rank >= 0.9` but tests with a 2-asset dataset where both get tags because 1/2 = 50% and the logic seems wrong.
**Why it happens:** `PERCENT_RANK()` formula is `(rank - 1) / (N - 1)`. With N=1, it returns 0 for all. With N=2, the top asset gets 1.0 and the bottom gets 0.0. Both would be tagged if no minimum guard existed.
**How to avoid:** Always apply the 10-asset minimum guard FIRST. Check `total_scored < 10` before evaluating `pct_rank`. The `func.count().over()` window gives total count in the same subquery pass.
**Warning signs:** All assets showing badges in a small org (< 10 scored assets).

### Pitfall 2: Missing `ad_account_id` in Asset Detail Response
**What goes wrong:** Campaign URL for Meta (`?act={account_id}`) renders blank because `ad_account_id` is not in the current `/dashboard/assets/{asset_id}` response.
**Why it happens:** Current endpoint returns `id, platform, ad_id, ad_name, ...` but does NOT include `ad_account_id` (confirmed by reading lines 475-492 of dashboard.py). `CreativeAsset` model has `ad_account_id` at line 44 of creative.py.
**How to avoid:** Add `"ad_account_id": str(asset.ad_account_id)` to the endpoint response dict. Update `AssetDetailResponse` in frontend accordingly.
**Warning signs:** Meta campaign links open to the Ads Manager without selecting the account (wrong URL).

### Pitfall 3: ECharts Not Registered in Dashboard Component
**What goes wrong:** `NgxEchartsDirective` is imported in the dialog but NOT in `dashboard.component.ts`. Adding the chart to the dashboard template without registering the echarts charts/components causes a silent render failure.
**Why it happens:** `echarts.use([LineChart, ...])` is called at module level in `asset-detail-dialog.component.ts` — but this registration is global for the echarts instance. However, `NgxEchartsDirective` must be explicitly added to the `imports` array in the standalone `dashboard.component.ts` and `provideEchartsCore({ echarts })` must be in `providers`.
**How to avoid:** Add to dashboard component: imports `[NgxEchartsDirective]`, providers `[provideEchartsCore({ echarts })]`, and `echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])` at the top level. The dialog already sets the precedent — replicate.
**Warning signs:** Chart container renders but is empty; no console errors (silent failure).

### Pitfall 4: `.tile-tag` CSS Position Context
**What goes wrong:** Moving `.tile-tag` to the `.tile-thumb` container requires `.tile-thumb` to be `position: relative`. If it isn't, the `position: absolute; bottom: 8px; left: 8px` offsets apply to the nearest positioned ancestor instead.
**Why it happens:** The current `.tile-thumb` CSS may not declare `position: relative` (the overlay badges work because they were already designed into the positioned context, but double-check).
**How to avoid:** Verify `.tile-thumb` has `position: relative` — confirmed at line 203 which shows `class="tile-thumb" [class.video-no-thumb]="..."` — the existing overlay elements (overlay-ace, overlay-format, overlay-platform) already use absolute positioning, so `.tile-thumb` must already be `position: relative`. Safe to add the badge there.
**Warning signs:** Badge appears at corner of the page rather than the card corner.

### Pitfall 5: Score Trend Query Returns No Rows for New Orgs
**What goes wrong:** New orgs with no COMPLETE scoring results return an empty array, and the frontend crashes if it tries to render the chart without checking array length.
**Why it happens:** `AVG(total_score) GROUP BY date` returns zero rows when `WHERE` filters match nothing.
**How to avoid:** Frontend empty state guard: `*ngIf="scoreTrendData.length >= 2"` for chart, `*ngIf="scoreTrendData.length < 2"` for empty state. Backend returns `{"trend": [], "data_points": 0}` when no data.
**Warning signs:** Chart container shows as blank white box on initial load for new users.

### Pitfall 6: Campaign `ad_account_id` vs `campaign_id` Source
**What goes wrong:** Campaigns are returned from `HarmonizedPerformance` in the asset detail endpoint. The `campaign_id` field is available (confirmed: `HarmonizedPerformance.campaign_id` at line 511 of performance.py). However, `ad_account_id` must come from `CreativeAsset.ad_account_id`, not from `HarmonizedPerformance.ad_account_id` — both exist but `CreativeAsset.ad_account_id` is the canonical one for URL construction.
**How to avoid:** Include `"ad_account_id": str(asset.ad_account_id)` in the asset detail response at the asset level, not per-campaign.

---

## Code Examples

Verified patterns from existing project source:

### ECharts Line Chart (from asset-detail-dialog.component.ts, line 207-208)
```typescript
// Source: asset-detail-dialog.component.ts
<div echarts [options]="chartOption" [merge]="chartMerge" class="echart-box"></div>
// CSS: .echart-box { width: 100%; height: 260px; }
// Dashboard panel: height: 200px (per UI-SPEC)
```

### DateRangePickerComponent Usage (from dashboard.component.ts, line 87-93)
```html
<!-- Source: dashboard.component.ts lines 87-93 -->
<app-date-range-picker
  [dateFrom]="dateFrom"
  [dateTo]="dateTo"
  [selectedPreset]="selectedPreset"
  (dateChange)="onDateRangeChange($event)"
></app-date-range-picker>
```

### Existing Overlay Badge Pattern (from dashboard.component.ts, lines 221-256)
```html
<!-- Score badge (bottom-right) — existing pattern -->
<div class="overlay-ace ace-score" ...>{{ asset.total_score }}</div>
<!-- Performer badge (bottom-left) — NEW, same container (.tile-thumb) -->
<div class="tile-tag" [class]="getTagClass(asset.performer_tag)"
  *ngIf="asset.performer_tag"
  [matTooltip]="getPerformerTooltip(asset.performer_tag)">
  {{ asset.performer_tag }}
</div>
```

### CE Pillar Card CSS (existing — reference for Performance tab tiles)
```scss
/* Source: asset-detail-dialog.component.ts lines 670-680 */
.ce-pillar-card {
  background: var(--bg-card);
  border-radius: 8px;
  padding: 12px 10px;
  border: 1px solid var(--border);
  /* Use same border-radius, shadow, padding, background for .perf-kpi-tile and .perf-asset-tile */
}
```

### PERCENT_RANK Window Function (SQLAlchemy)
```python
# Source: SQLAlchemy documentation — window functions
from sqlalchemy import func

# Returns float 0.0–1.0; lowest-ranked asset = 0.0, highest = 1.0
pct_rank_col = (
    func.percent_rank()
    .over(order_by=CreativeScoreResult.total_score)
    .label("pct_rank")
)
total_scored_col = (
    func.count(CreativeScoreResult.id)
    .over()
    .label("total_scored")
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Threshold-based performer tags (≥70 = Top, ≥45 = Average) | PERCENT_RANK() relative ranking | Phase 7 | Tags are now meaningful regardless of score scale; reflects actual distribution |
| Performer tag always non-null ("Average" for middle) | `null` for middle 80% | Phase 7 | Frontend renders no badge for middle assets; `*ngIf="asset.performer_tag"` gate |
| Performance tab: tabular kpi-table layout | Tile/card grid matching CE tab aesthetic | Phase 7 | Visual consistency between tabs; metric categories grouped by type |
| Campaigns section: no external links | Campaign name + external link icon | Phase 7 | Direct navigation to publisher Ads Manager |

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — all libraries already installed, PostgreSQL already running, no new tools required).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 + pytest-asyncio |
| Config file | none — tests run from `backend/` directory |
| Quick run command | `cd backend && python -m pytest tests/test_dashboard_filters.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TREND-02 | `GET /dashboard/score-trend` returns `{trend: [...], data_points: N}` | unit (source inspection) | `python -m pytest tests/test_score_trend.py -x -q` | ❌ Wave 0 |
| TREND-02 | Empty result when no COMPLETE scores exist | unit | `python -m pytest tests/test_score_trend.py::test_score_trend_empty -x -q` | ❌ Wave 0 |
| TREND-03 | Fewer than 2 data points → `data_points < 2` in response | unit | `python -m pytest tests/test_score_trend.py::test_score_trend_insufficient_data -x -q` | ❌ Wave 0 |
| PERF-01 | `_compute_performer_tag()` returns null when total_scored < 10 | unit | `python -m pytest tests/test_performer_tag.py::test_minimum_guard -x -q` | ❌ Wave 0 |
| PERF-01 | pct_rank >= 0.90 → "Top Performer"; pct_rank <= 0.10 → "Below Average"; else null | unit | `python -m pytest tests/test_performer_tag.py::test_percent_rank_boundaries -x -q` | ❌ Wave 0 |
| PERF-01 | `ad_account_id` present in `GET /dashboard/assets/{id}` response | unit (source inspection) | `python -m pytest tests/test_performer_tag.py::test_asset_detail_has_account_id -x -q` | ❌ Wave 0 |
| UI-01 | Performance tab renders `.perf-top-row`, `.perf-summary-group`, `.perf-campaigns-list` | manual visual | — | manual |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_performer_tag.py tests/test_score_trend.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_score_trend.py` — covers TREND-02, TREND-03
- [ ] `backend/tests/test_performer_tag.py` — covers PERF-01 backend logic

*(UI-01 is frontend-only; verified by manual inspection per existing project pattern — no Angular unit test infrastructure present.)*

---

## Open Questions

1. **Score trend date granularity**
   - What we know: `scored_at` is a `DateTime(timezone=True)` column. Grouping by `DATE(scored_at)` gives daily buckets.
   - What's unclear: If an org runs 3 scoring batches in one day, all three get collapsed into one data point for that day. This is correct behavior but the chart may appear to have fewer points than runs.
   - Recommendation: Daily granularity is appropriate for a 30-day window. Document this in the endpoint comment.

2. **Platform filter on score trend**
   - What we know: The score trend data comes from `CreativeScoreResult`, joined to `CreativeAsset` for org_id. The dashboard filter bar includes a platform filter.
   - What's unclear: Whether the score trend panel should respect the dashboard platform filter or always show all-platform aggregate.
   - Recommendation: Respect the platform filter for consistency with the rest of the dashboard. The join to `CreativeAsset` makes this straightforward.

3. **`ad_account_id` for campaigns in asset detail response**
   - What we know: `CreativeAsset.ad_account_id` exists (confirmed in creative.py line 44). The current `get_asset_detail` endpoint does not return it.
   - What's unclear: Nothing — this is a confirmed gap that requires adding one field to the response.
   - Recommendation: Add `"ad_account_id": str(asset.ad_account_id) if asset.ad_account_id else None` to the response dict in `get_asset_detail`.

---

## Project Constraints (from CLAUDE.md)

CLAUDE.md does not exist at the project root. No project-specific directives to enforce beyond the constraints in CONTEXT.md and standard patterns observed in the codebase.

---

## Sources

### Primary (HIGH confidence)
- Direct code reading: `backend/app/api/v1/endpoints/dashboard.py` — `_get_performer_tag()`, `get_dashboard_assets()`, `get_asset_detail()` functions
- Direct code reading: `frontend/src/app/features/dashboard/dashboard.component.ts` — `tile-tag`, `overlay-ace`, `getTagClass()`, existing template structure
- Direct code reading: `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` — CE tab classes, ECharts import pattern, Performance tab layout
- Direct code reading: `backend/app/models/scoring.py` — `CreativeScoreResult` schema, `scored_at`, `total_score`, `scoring_status` fields
- Direct code reading: `backend/app/models/performance.py` — `HarmonizedPerformance` fields, `ad_account_id`, `campaign_id` availability
- Direct code reading: `backend/app/schemas/creative.py` — `DashboardStats`, `CreativeAssetResponse`, `performer_tag` field
- `.planning/phases/07-score-trend-performer-highlights-performance-tab/07-UI-SPEC.md` — Fully approved UI contract for all three deliverables

### Secondary (MEDIUM confidence)
- SQLAlchemy documentation pattern for `func.percent_rank().over()` — consistent with existing SQLAlchemy usage in the project
- DV360 campaign URL pattern (`displayvideo.google.com/#ng_nav/p/{partner_id}/c/{campaign_id}`) — codified in UI-SPEC; consistent with known DV360 navigation structure

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all confirmed installed and in use
- Architecture: HIGH — all patterns derived from direct code reading of existing files
- Pitfalls: HIGH — derived from direct code gaps identified in current implementation
- SQL window functions: HIGH — standard PostgreSQL feature; SQLAlchemy syntax verified against project patterns
- DV360 URL pattern: MEDIUM — canonical but not verified against live DV360 instance

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable stack; 30-day horizon)
