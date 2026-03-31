# Phase 8: Score-to-ROAS Correlation - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

One deliverable: a scatter chart showing every scored creative as a point with effectiveness score (X-axis) vs ROAS (Y-axis), with quadrant framing that tells users immediately which creatives to scale or cut.

Entry point: the existing **Avg ROAS stat tile** in the dashboard header — clicking it opens a right-side slide-in drawer containing the scatter chart. No new panel in the main dashboard layout.

</domain>

<decisions>
## Implementation Decisions

### Panel Entry Point & Layout

- **D-01:** The existing **Avg ROAS stat tile** in the dashboard header stats row is made **clickable**. It opens a **right-side slide-in drawer** (overlay panel) containing the scatter chart. The tile gets a visual affordance (cursor pointer + subtle hover state) to signal interactivity.
- **D-02:** No new persistent panel is added above the creative grid. The scatter chart lives exclusively inside the drawer. The main dashboard layout is unchanged.
- **D-03:** The drawer is self-contained: scatter chart + spend threshold input + close control. It overlays the dashboard without pushing content.

### Quadrant Reference Lines

- **D-04:** Reference lines are **dynamic** — computed from the **median score × median ROAS** of the currently visible (filtered + spend-threshold-applied) dataset. Lines update whenever the dataset changes.
- **D-05:** Quadrant labels (shown as subtle chart annotations):
  - Top-right (high score + high ROAS) → **"Stars"** — scale these
  - Top-left (low score + high ROAS) → **"Workhorses"** — performing despite low effectiveness
  - Bottom-right (high score + low ROAS) → **"Question Marks"** — effective creative, underperforming on ROAS
  - Bottom-left (low score + low ROAS) → **"Laggards"** — cut these
- **D-06:** Quadrant label style: subtle, low-contrast text in each corner of the chart — not distracting, clearly legible.

### Point Interaction

- **D-07:** **Hover** shows a tooltip per CORR-01: thumbnail, score, ROAS, spend, platform.
- **D-08:** **Clicking a dot** opens the **asset detail dialog** — the same `AssetDetailDialogComponent` opened from the creative grid. The scatter chart is a full navigation entry point into asset detail.

### Spend Threshold

- **D-09:** Minimum spend threshold input is **inside the drawer panel** (above or below the chart). Self-contained — does not affect the main dashboard filter bar or the creative grid.
- **D-10:** Default threshold: **$10**. User can edit inline (number input with currency prefix).

### Null / Zero ROAS Handling (CORR-02)

- **D-11:** **Null ROAS** (asset has no ROAS data) — **excluded** from the chart. Not plotted.
- **D-12:** **Zero ROAS** (asset has data but ROAS = 0) — **plotted at Y = 0**, visually distinct from null. These are legitimate data points (e.g., awareness campaigns with no conversion tracking).
- **D-13:** **Y-axis cap** at the **99th percentile** of ROAS in the visible dataset — prevents outlier distortion. Capped assets are still plotted at the cap value with a visual indicator (Claude's discretion on indicator style).

### Claude's Discretion

- Angular Material component for the drawer: use `MatDrawer` / `MatSidenav` in "over" mode, anchored to the right side. If that adds layout complexity, a `cdkOverlayPanel` or custom right-side overlay is acceptable.
- ECharts `ScatterChart` registration — add `ScatterChart` to the existing `echarts.use([...])` call in `dashboard.component.ts` (same pattern as `LineChart`).
- Dot size: scale by spend (larger spend = larger dot) or fixed size. Either is acceptable.
- Quadrant label opacity and font size — keep subtle so they don't dominate the chart.
- Y-axis cap indicator style (dotted reference line, annotation, or clip with visual cue at top).
- Drawer width: 480–600px feels right; Claude picks based on chart readability.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Dashboard frontend — entry point and chart integration
- `frontend/src/app/features/dashboard/dashboard.component.ts` — existing DashboardStats interface (`avg_roas`, `total_spend`), stats tiles template, ECharts registration (`echarts.use([LineChart, ...])`), `NgxEchartsDirective` imports, existing filter state (`dateFrom`, `dateTo`, `platformFilter`)
- `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` — `AssetDetailDialogComponent` — this is what clicking a scatter dot should open (same as grid card click)

### Backend — data source
- `backend/app/api/v1/endpoints/dashboard.py` — existing `GET /dashboard/assets` endpoint returns `total_score`, `roas`, `spend`, `thumbnail_url`, `platform`, `ad_name` per asset; this is the data source for the scatter chart (no new endpoint likely needed — confirm during research)

### Phase requirements
- `.planning/REQUIREMENTS.md` §CORR-01, §CORR-02

### Prior phase patterns to reuse
- `.planning/phases/07-score-trend-performer-highlights-performance-tab/07-CONTEXT.md` — ECharts pattern (provideEchartsCore, options binding, echart-box class), performer badge overlay patterns
- `.planning/phases/04-dashboard-polish-reliability/04-CONTEXT.md` — orange accent theme, dashboard stat tile styles

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DashboardStats` interface + `/stats` endpoint already returns `avg_roas` — the stat tile that becomes the entry point
- `GET /dashboard/assets` already returns per-asset `total_score`, `roas`, `spend`, `thumbnail_url`, `platform` — likely sufficient as scatter data source without a new endpoint
- `NgxEchartsDirective` + `provideEchartsCore` already set up in `dashboard.component.ts` — just add `ScatterChart` to `echarts.use()`
- `openAssetDetail(asset)` or equivalent method in dashboard component — reuse to open dialog from scatter dot click
- Angular Material already in use — `MatDrawer`/`MatSidenav` likely available

### Established Patterns
- ECharts: `EChartsOption` typed, `[options]` + `[merge]` binding, `echarts` div with `echart-box` CSS class
- Asset detail dialog: opened via `MatDialog.open(AssetDetailDialogComponent, { data: asset })` pattern
- Dashboard filter state: `dateFrom`, `dateTo`, `platformFilter` — scatter should respect these filters (assets shown match the grid's current filter state)
- Stat tiles: styled in dashboard component CSS — adding click affordance (cursor, hover) follows existing patterns

### Integration Points
- Scatter drawer trigger: click handler on the Avg ROAS stat tile in the dashboard template
- Data flow: scatter chart reads from the same filtered asset list the grid already fetches (or a dedicated endpoint if the grid's pagination limits data — check during research)
- Dialog open: reuse existing asset detail dialog open pattern

</code_context>

<specifics>
## Specific Ideas

- Entry point: Avg ROAS stat tile → right-side drawer slide-in. The ROAS tile signals "explore ROAS vs. score" — natural discoverability.
- Quadrant framing communicates action: Stars = scale, Laggards = cut, Workhorses = effective delivery despite low BrainSuite score, Question Marks = strong creative not converting.
- Spend threshold input is inside the drawer, not polluting the main filter bar — correlation view is self-contained.
- Dot click → asset detail dialog gives the scatter chart full navigation power without a separate details pane.

</specifics>

<deferred>
## Deferred Ideas

- Per-platform ROAS correlation breakdown — out of scope per REQUIREMENTS.md. Future v1.2+.
- Highlighting a clicked dot in the creative grid below — not needed since dot click opens dialog directly.
- Configurable per-org quadrant thresholds — dynamic median is sufficient for v1.1.

</deferred>

---

*Phase: 08-score-to-roas-correlation*
*Context gathered: 2026-03-31*
