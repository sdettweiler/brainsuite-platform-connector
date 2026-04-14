---
phase: quick
plan: 260401-qpu
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/api/v1/endpoints/dashboard.py
  - backend/tests/test_correlation.py
  - frontend/src/app/features/dashboard/dashboard.component.ts
autonomous: true
requirements: [QPU-01]
must_haves:
  truths:
    - "User can select a Y-axis metric (ROAS, CTR, VTR, CPM, CVR, CPC, Conversions) from a dropdown in the scatter chart drawer"
    - "Scatter chart re-renders with the selected metric on the Y-axis when metric is changed"
    - "Backend returns all selectable metrics in the correlation-data response"
    - "Quadrant labels (Stars/Workhorses/Question Marks/Laggards) still function correctly with any metric"
  artifacts:
    - path: "frontend/src/app/features/dashboard/dashboard.component.ts"
      provides: "Metric selector dropdown in correlation drawer, dynamic chart axis"
    - path: "backend/app/api/v1/endpoints/dashboard.py"
      provides: "Extended correlation-data endpoint returning multiple metrics per asset"
  key_links:
    - from: "frontend scatter chart"
      to: "backend correlation-data"
      via: "CorrelationAsset interface includes all metric fields"
      pattern: "ctr.*cpm.*vtr.*cvr.*cpc.*conversions"
---

<objective>
Add a metric selector dropdown to the scatter chart correlation drawer so the user can choose any Y-axis metric instead of hardcoded ROAS.

Purpose: Currently the scatter chart only shows Score vs. ROAS. Users need to correlate ACE Score against other performance metrics (CTR, VTR, CPM, CVR, CPC, Conversions) to gain deeper creative insights.

Output: Extended backend endpoint returning multiple metrics, frontend dropdown selector, dynamic chart axis labelling and formatting.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@frontend/src/app/features/dashboard/dashboard.component.ts
@backend/app/api/v1/endpoints/dashboard.py
@backend/app/models/performance.py

<interfaces>
<!-- CorrelationAsset interface (currently in dashboard.component.ts line 82-90) -->
```typescript
interface CorrelationAsset {
  id: string;
  ad_name: string | null;
  platform: string;
  thumbnail_url: string | null;
  total_score: number;
  roas: number | null;
  spend: number | null;
}
```

<!-- Backend serializer (dashboard.py line 844-858) -->
```python
def _serialize_correlation_asset(row) -> dict:
    return {
        "id": str(row.id),
        "ad_name": row.ad_name,
        "platform": row.platform,
        "thumbnail_url": row.thumbnail_url,
        "total_score": int(row.total_score),
        "roas": float(row.roas) if row.roas is not None else None,
        "spend": float(row.total_spend) if row.total_spend is not None else None,
    }
```

<!-- HarmonizedPerformance relevant columns (performance.py lines 526-566) -->
Available aggregatable metrics: spend, impressions, clicks, cpm, cpc, ctr, outbound_clicks, outbound_ctr, cpv, video_views, vtr, conversions, conversion_value, cvr, cost_per_conversion, roas

<!-- MatSelectModule already imported in component (line 96) -->
<!-- NgxSlider pattern already in drawer for min-spend slider -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extend backend correlation-data endpoint to return all selectable metrics</name>
  <files>backend/app/api/v1/endpoints/dashboard.py, backend/tests/test_correlation.py</files>
  <action>
Extend the `get_correlation_data` endpoint and `_serialize_correlation_asset` to return additional aggregated metrics alongside ROAS.

1. Update the `perf_subq` subquery in `get_correlation_data` (line ~883) to also select these aggregated columns:
   - `ctr`: weighted average — `SUM(clicks) / NULLIF(SUM(impressions), 0) * 100` (as percentage)
   - `vtr`: weighted average — `SUM(video_views) / NULLIF(SUM(impressions), 0) * 100` (as percentage)
   - `cpm`: weighted average — `SUM(spend) / NULLIF(SUM(impressions), 0) * 1000`
   - `cvr`: weighted average — `SUM(conversions) / NULLIF(SUM(clicks), 0) * 100` (as percentage)
   - `cpc`: `SUM(spend) / NULLIF(SUM(clicks), 0)`
   - `conversions`: `SUM(conversions)`

   IMPORTANT: Use weighted averages (re-derive from raw sums) rather than averaging pre-computed daily rates. This matches the existing ROAS pattern which computes `SUM(conversion_value) / NULLIF(SUM(spend), 0)`.

2. Add these columns to the main `select()` query (line ~901) via `perf_subq.c.ctr`, etc.

3. Update `_serialize_correlation_asset` to include the new fields, using the same `float(row.X) if row.X is not None else None` pattern for each.

4. Update `backend/tests/test_correlation.py` — ensure existing tests still pass and add a test assertion that the response includes the new metric fields (ctr, vtr, cpm, cvr, cpc, conversions) with correct types.
  </action>
  <verify>
    <automated>cd /Users/sebastian.dettweiler/Claude\ Code/platform-connector/brainsuite-platform-connector && python -m pytest backend/tests/test_correlation.py -x -v 2>&1 | tail -30</automated>
  </verify>
  <done>GET /dashboard/correlation-data returns objects with roas, ctr, vtr, cpm, cvr, cpc, conversions fields. Tests pass.</done>
</task>

<task type="auto">
  <name>Task 2: Add metric selector dropdown and make scatter chart Y-axis dynamic</name>
  <files>frontend/src/app/features/dashboard/dashboard.component.ts</files>
  <action>
1. **Extend CorrelationAsset interface** (line ~82) to add new fields:
   ```typescript
   ctr: number | null;
   vtr: number | null;
   cpm: number | null;
   cvr: number | null;
   cpc: number | null;
   conversions: number | null;
   ```

2. **Add metric config map** as a class property:
   ```typescript
   readonly correlationMetrics: { key: string; label: string; format: (v: number) => string; suffix: string }[] = [
     { key: 'roas', label: 'ROAS', format: (v) => v.toFixed(2) + 'x', suffix: 'x' },
     { key: 'ctr', label: 'CTR', format: (v) => v.toFixed(2) + '%', suffix: '%' },
     { key: 'vtr', label: 'VTR', format: (v) => v.toFixed(2) + '%', suffix: '%' },
     { key: 'cpm', label: 'CPM', format: (v) => '$' + v.toFixed(2), suffix: '' },
     { key: 'cvr', label: 'CVR', format: (v) => v.toFixed(2) + '%', suffix: '%' },
     { key: 'cpc', label: 'CPC', format: (v) => '$' + v.toFixed(2), suffix: '' },
     { key: 'conversions', label: 'Conversions', format: (v) => v.toFixed(0), suffix: '' },
   ];
   selectedCorrelationMetric = 'roas';
   ```

3. **Add dropdown in drawer header** (line ~391). Replace the static `<h4>Score vs. ROAS</h4>` with:
   ```html
   <div style="display:flex;align-items:center;gap:12px">
     <h4 style="margin:0;white-space:nowrap">Score vs.</h4>
     <mat-form-field appearance="outline" style="width:150px;margin:0" subscriptSizing="dynamic">
       <mat-select [(value)]="selectedCorrelationMetric" (selectionChange)="buildScatterChart()">
         <mat-option *ngFor="let m of correlationMetrics" [value]="m.key">{{ m.label }}</mat-option>
       </mat-select>
     </mat-form-field>
   </div>
   ```

4. **Make `correlationEligibleCount` getter dynamic** — filter on `a[selectedCorrelationMetric]` instead of `a.roas`:
   ```typescript
   get correlationEligibleCount(): number {
     return this.correlationAssets.filter(
       a => (a as any)[this.selectedCorrelationMetric] !== null && (a.spend ?? 0) >= this.correlationMinSpend
     ).length;
   }
   ```

5. **Refactor `buildScatterChart()`** to use the selected metric dynamically:
   - Get the active metric config: `const metric = this.correlationMetrics.find(m => m.key === this.selectedCorrelationMetric)!;`
   - Replace `a.roas` with `(a as any)[metric.key]` throughout
   - Replace hardcoded `'ROAS'` yAxis name with `metric.label`
   - Update tooltip formatter to use `metric.format(params.data[1])` instead of hardcoded `toFixed(2)x`
   - Update the cap note text from `"ROAS capped at 99th pct."` to `"${metric.label} capped at 99th pct."`
   - The cap-note in template is static HTML — change it to interpolation: `{{ selectedMetricLabel }} capped at 99th pct.`
     Add getter: `get selectedMetricLabel() { return this.correlationMetrics.find(m => m.key === this.selectedCorrelationMetric)?.label ?? ''; }`

6. **Update empty state message** (line ~423): Change "No scored creatives with ROAS data" to "No scored creatives with {{ selectedMetricLabel }} data".

7. **Style the form field** to match the dark drawer theme. Add to the correlation styles section:
   ```css
   .correlation-drawer-header .mat-mdc-form-field {
     font-size: 14px;
   }
   .correlation-drawer-header .mat-mdc-form-field .mat-mdc-select-value {
     font-weight: 600;
   }
   ```
  </action>
  <verify>
    <automated>cd /Users/sebastian.dettweiler/Claude\ Code/platform-connector/brainsuite-platform-connector && npx ng build 2>&1 | tail -10</automated>
  </verify>
  <done>Dropdown renders in drawer header showing all metrics. Selecting a metric re-renders the scatter chart with that metric on Y-axis. Tooltip, axis label, cap note, and empty state all reflect the selected metric. Default is ROAS (backward compatible). Build succeeds with no errors.</done>
</task>

</tasks>

<verification>
1. `ng build` succeeds with no errors
2. Backend tests pass: `pytest backend/tests/test_correlation.py -x`
3. Manual check: Open dashboard, click Avg ROAS stat to open drawer, verify ROAS is default, switch to CTR/CPM/VTR and confirm chart re-renders with correct axis label and tooltip formatting
</verification>

<success_criteria>
- Metric selector dropdown visible in scatter chart drawer header
- All 7 metrics selectable: ROAS, CTR, VTR, CPM, CVR, CPC, Conversions
- Chart Y-axis, tooltip, cap note, and empty state dynamically reflect selected metric
- Default metric is ROAS (no change to existing behavior when drawer first opens)
- Backend returns all metric fields in correlation-data response
- Build and tests pass
</success_criteria>

<output>
After completion, create `.planning/quick/260401-qpu-add-metric-selector-dropdown-to-scatter-/260401-qpu-SUMMARY.md`
</output>
