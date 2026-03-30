# Phase 7: Score Trend, Performer Highlights + Performance Tab - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Three deliverables:
1. **Aggregate Score Trend panel** — new dashboard panel above the creative grid showing avg BrainSuite score trend over time across all scored assets, computed on-the-fly
2. **Performer Badges** — top/bottom 10% badge overlays on grid cards using PERCENT_RANK() (10-asset minimum guard)
3. **Performance Tab Redesign** — asset detail dialog Performance tab replaced with a tile/card grid layout matching the CE tab aesthetic

**Critical scope correction:** TREND-02 and TREND-03 as originally specified (per-asset score history + Score Trend tab) are invalidated — asset-level BrainSuite scores are static (D-09 from Phase 5). Score trend is only meaningful at the aggregate/portfolio level. No `creative_score_history` table is created.

</domain>

<decisions>
## Implementation Decisions

### Score Trend (Aggregate — Re-scoped from TREND-02/TREND-03)

- **D-01:** Asset-level score trends are **not implemented**. BrainSuite scores are persistent/static per asset (Phase 5 D-09). TREND-02/TREND-03 are re-scoped to an aggregate view.
- **D-02:** New **dashboard panel/card above the creative grid** — shows average score trend across all scored assets over the selected date window. Visible on the main dashboard without opening any dialog.
- **D-03:** Data source: **compute on-the-fly** from existing `CreativeScoreResult.scored_at` + `total_score`. No new table. Backend query: `AVG(total_score) GROUP BY date_bucket WHERE scored_at IN [date_from, date_to]` — filtered by org_id and platform filters already in use.
- **D-04:** Default window: **30 days**. User can adjust via **DateRangePickerComponent** (already exists in the project). Chart uses ECharts LineChart (already installed: `ngx-echarts ^17.2.0`).
- **D-05:** No "Score Trend" tab in the asset detail dialog. Per-asset trend is not surfaced anywhere.

### Performer Badges (PERF-01)

- **D-06:** Badge position: **bottom-left corner** of the grid card (score badge is bottom-right — badges are on opposite sides).
- **D-07:** Visual style: **small colored pill/chip** — "⬆ Top Performer" in green, "⬇ Below Average" in red. Compact and scannable.
- **D-08:** Labels unchanged: **"Top Performer"** / **"Below Average"**. Middle 80% ("Average") show **no badge** — only the extremes get a pill.
- **D-09:** Backend logic switch: `_get_performer_tag()` currently uses score thresholds (≥70 / ≥45). Replace with **`PERCENT_RANK() OVER (ORDER BY total_score)`** computed per org per request. Top 10% → "Top Performer", bottom 10% → "Below Average". **Minimum guard: if fewer than 10 scored assets exist, return null for all** (no badges).

### Performance Tab Redesign (UI-01)

- **D-10:** **Two-column top row:**
  - Left tile: Existing KPI trend chart (ECharts multi-line, spend/CTR/ROAS over time) — retains current KPI selector (multi-select checkboxes for Spend, CTR, ROAS, etc.)
  - Right tile: **Creative Asset tile** containing:
    - Header row: "Creative Asset" label (top-left) + **Rank badge** (top-right, "Top Performer" / "Below Average" pill — same style as grid badge)
    - Asset preview (thumbnail/video preview)
    - Filename (left-aligned, below preview) + video duration (right-aligned on same line, if video)
    - Two small data tiles inline below: **Spend** and **Impressions**

- **D-11:** **Full-width Performance Summary section** below the top row — metrics grouped by category, each row color-coded with a leading icon:
  - **Delivery** (blue): spend, impressions, CPM, reach (if available), clicks
  - **Engagement** (orange/amber): CTR, outbound CTR, unique CTR, inline link click CTR
  - **Conversions** (green): ROAS, purchase ROAS, CVR, conversions, cost per result
  - **Video** (purple): video views, VTR, video completions (platform-specific)
  - **Platform-specific** (grey): any remaining metrics that don't map to the above (Claude recommends placement for orphan metrics)

  Metrics are non-interactive (display only — no click behavior). Null/zero metrics can be shown greyed out or omitted (Claude's discretion).

- **D-12:** **"Used in X campaigns" section** at the bottom (full width) — lists all campaigns this asset appeared in. Each row: campaign name + link icon (opens campaign URL at publisher in new tab). Campaign URL constructed from `campaign_id` + `platform` using known URL patterns:
  - Meta: `https://www.facebook.com/adsmanager/manage/campaigns?act={account_id}&campaign_ids={campaign_id}`
  - TikTok: `https://ads.tiktok.com/i18n/account/campaigns?keyword={campaign_id}`
  - Google Ads: `https://ads.google.com/aw/campaigns?campaignId={campaign_id}`
  - DV360: campaign dashboard link (Claude researches the canonical URL pattern)

- **D-13:** Overall design: tiles match CE tab aesthetic (`ce-pillar-card` / `ce-pillars-grid` style — same border-radius, shadow, padding, background).

- **D-14:** Tabs in asset detail dialog after this phase: **Performance** | **Creative Effectiveness** (no Score Trend tab added).

### Claude's Discretion

- ECharts line chart color for the aggregate score trend panel (match existing orange accent or use a secondary palette color)
- Exact PERCENT_RANK() SQL expression and WHERE clause for performer tagging (filtered to org, minimum 10 COMPLETE-status scored assets)
- Campaign URL patterns for DV360 (research and implement best known pattern)
- Metric placement for any "orphan" platform-specific metrics that don't fit cleanly into Delivery/Engagement/Conversions/Video
- Null/zero metric handling in the Performance Summary grid (hide vs. grey out)
- Color palette for metric category icons (suggested above — Claude can adjust for consistency with existing theme)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing implementation — reuse patterns
- `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` — CE tab layout (ce-pillar-card, ce-pillars-grid) is the visual reference for the new Performance tab tile style
- `frontend/src/app/features/dashboard/dashboard.component.ts` — existing performer_tag field, overlay badge patterns, tile-tag CSS class
- `backend/app/api/v1/endpoints/dashboard.py` — `_get_performer_tag()` function to replace with PERCENT_RANK() logic; existing dashboard query structure

### Phase requirements
- `.planning/REQUIREMENTS.md` §TREND-02, §TREND-03 (re-scoped per D-01–D-05), §PERF-01, §UI-01
- `.planning/phases/07-score-trend-performer-highlights-performance-tab/07-CONTEXT.md` (this file)

### Prior phase decisions
- `.planning/phases/05-brainsuite-image-scoring/05-CONTEXT.md` D-09 — ScoringEndpointType; confirms scores are static per asset
- `.planning/phases/04-dashboard-polish-reliability/04-CONTEXT.md` — orange accent theme, existing dashboard filter bar, ngx-slider pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `NgxEchartsDirective` + `LineChart`, `GridComponent`, `TooltipComponent`, `DataZoomComponent` — already imported in `asset-detail-dialog.component.ts`; same imports available for the new dashboard panel
- `DateRangePickerComponent` — already used in the Performance tab; reuse for the aggregate score trend date range picker
- `.ce-pillar-card` / `.ce-pillars-grid` — CSS classes in asset-detail-dialog styles; copy/adapt for the new Performance tab tile grid
- `performer_tag` — already returned from backend `GET /dashboard/assets`; dashboard template has `.tile-tag` class already rendering it

### Established Patterns
- ECharts configuration: `EChartsOption` typed, `[options]` + `[merge]` binding, `echarts` div with `echart-box` class
- Overlay badges: `position: absolute` inside a relative card container, bottom/right offsets for score badge — extend for bottom-left performer pill
- Dashboard stats: existing `DashboardStats` schema and `/stats` endpoint — likely where the new avg score trend endpoint attaches

### Integration Points
- New aggregate score trend panel: inserts above the existing creative grid in `dashboard.component.ts`; needs a new backend endpoint or extends `/stats`
- `_get_performer_tag()` replacement: backend function in `dashboard.py` — switch to a window function subquery scoped per org
- Performance tab tile grid: replaces `.kpi-table` section inside `.perf-tab` in `asset-detail-dialog.component.ts`

</code_context>

<specifics>
## Specific Ideas

- Performance tab top row: score/KPI chart on the left, creative asset card on the right — the chart tile is the existing KPI trend chart (not a score trend chart)
- Creative Asset tile: "Creative Asset" headline + Rank badge in the header, then preview, filename (left) + duration (right if video), then inline Spend + Impressions tiles below the preview
- Performance Summary: grouped rows with color-coded category label + icon on the left, metric values on the right — inspired by CE tab pillar rows
- Campaigns section: each row has campaign name + external link icon → opens publisher campaign URL in new tab
- Aggregate score trend: new panel above the grid, not inside any dialog

</specifics>

<deferred>
## Deferred Ideas

- Per-asset score history table (`creative_score_history`) — invalidated by static score architecture. Re-evaluate only if BrainSuite scoring model changes to support multiple score versions per asset.
- Score trend at dashboard/platform level segmented by platform — aggregate trend across all assets is phase 7 scope; per-platform segmentation could be a future phase 7.1 or phase 8+.
- Areas of Interest (AOI) for Static API — already deferred in Phase 5; not in scope here.

</deferred>

---

*Phase: 07-score-trend-performer-highlights-performance-tab*
*Context gathered: 2026-03-30*
