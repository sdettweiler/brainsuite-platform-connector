---
phase: quick-260408-gmo
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/app/features/dashboard/dashboard.component.ts
  - frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts
autonomous: true
requirements: [QUICK-legibility-fix]
must_haves:
  truths:
    - "Top Performer and Below Average badges are clearly legible on dashboard tiles"
    - "Top Performer and Below Average badges are clearly legible in asset detail dialog"
    - "Badge colors still convey green=good, red=bad semantics"
  artifacts:
    - path: "frontend/src/app/features/dashboard/dashboard.component.ts"
      provides: "Dashboard tile performer badge styles"
      contains: "tag-top"
    - path: "frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts"
      provides: "Asset detail dialog performer badge styles"
      contains: "tag-top"
  key_links:
    - from: "dashboard.component.ts styles"
      to: "asset-detail-dialog.component.ts styles"
      via: "consistent badge appearance"
      pattern: "tag-top|tag-below"
---

<objective>
Fix top/low performer badge legibility in both the Dashboard tile grid and the asset detail dialog.

Purpose: The current badge backgrounds use rgba at 0.15 opacity, making them nearly invisible against dark card backgrounds. Increase background opacity and ensure text contrast so badges are immediately readable.

Output: Updated CSS styles in both dashboard.component.ts and asset-detail-dialog.component.ts with legible badge colors.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@frontend/src/app/features/dashboard/dashboard.component.ts
@frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts
</context>

<tasks>

<task type="auto">
  <name>Task 1: Increase performer badge opacity in dashboard tiles</name>
  <files>frontend/src/app/features/dashboard/dashboard.component.ts</files>
  <action>
In the inline styles section of dashboard.component.ts, find the `.tile-tag` nested classes (around line 737-744) and update the background opacity from 0.15 to 0.55 for both tag-top and tag-below, and brighten the text color to white for maximum contrast:

BEFORE:
```css
&.tag-top {
  background: rgba(46, 204, 113, 0.15);
  color: #2ECC71;
}
&.tag-below {
  background: rgba(231, 76, 60, 0.15);
  color: #E74C3C;
}
```

AFTER:
```css
&.tag-top {
  background: rgba(46, 204, 113, 0.55);
  color: #ffffff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}
&.tag-below {
  background: rgba(231, 76, 60, 0.55);
  color: #ffffff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}
```

The white text on a 55% opacity colored background ensures clear legibility on any tile thumbnail. The subtle text-shadow adds separation when the badge overlaps lighter image areas.
  </action>
  <verify>
    <automated>cd frontend && npx ng build --configuration production 2>&1 | tail -5</automated>
  </verify>
  <done>tag-top and tag-below in dashboard tiles use 0.55 opacity backgrounds with white text, clearly legible on all tile backgrounds</done>
</task>

<task type="auto">
  <name>Task 2: Increase performer badge opacity in asset detail dialog</name>
  <files>frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts</files>
  <action>
In the inline styles of asset-detail-dialog.component.ts, find the `.perf-asset-header` tag classes (around line 659-660) and apply the same fix:

BEFORE:
```css
.perf-asset-header .tag-top { background: rgba(46,204,113,0.15); color: #2ECC71; }
.perf-asset-header .tag-below { background: rgba(231,76,60,0.15); color: #E74C3C; }
```

AFTER:
```css
.perf-asset-header .tag-top { background: rgba(46,204,113,0.55); color: #ffffff; text-shadow: 0 1px 2px rgba(0,0,0,0.3); }
.perf-asset-header .tag-below { background: rgba(231,76,60,0.55); color: #ffffff; text-shadow: 0 1px 2px rgba(0,0,0,0.3); }
```

Must match the dashboard tile styling exactly for visual consistency.
  </action>
  <verify>
    <automated>cd frontend && npx ng build --configuration production 2>&1 | tail -5</automated>
  </verify>
  <done>tag-top and tag-below in asset detail dialog use 0.55 opacity backgrounds with white text, matching dashboard tile badge styling</done>
</task>

</tasks>

<verification>
- `ng build --configuration production` succeeds with no errors
- Visual: Dashboard tile badges for "Top Performer" and "Below Average" are immediately readable
- Visual: Asset detail dialog badges match the updated styling
</verification>

<success_criteria>
All performer badges across the dashboard (tile grid and detail dialog) display with clearly legible text on sufficiently opaque colored backgrounds. No new features added, only opacity/color values changed.
</success_criteria>

<output>
After completion, create `.planning/quick/260408-gmo-fix-top-low-performer-badge-legibility-i/260408-gmo-SUMMARY.md`
</output>
