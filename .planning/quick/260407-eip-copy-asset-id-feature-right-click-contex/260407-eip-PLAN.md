---
phase: quick
plan: 260407-eip
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/app/features/dashboard/dashboard.component.ts
  - frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts
autonomous: true
requirements: [QUICK-260407-eip]
must_haves:
  truths:
    - "Right-clicking an asset tile shows 'Copy Asset ID' in the context menu"
    - "Clicking 'Copy Asset ID' copies the asset's UUID to the clipboard and shows a snackbar confirmation"
    - "Asset detail dialog shows a small copy icon next to the asset name that copies the asset ID on click"
  artifacts:
    - path: "frontend/src/app/features/dashboard/dashboard.component.ts"
      provides: "Copy Asset ID context menu option"
      contains: "Copy Asset ID"
    - path: "frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts"
      provides: "Copy icon next to asset name in detail dialog"
      contains: "copyAssetId"
  key_links:
    - from: "context menu Copy Asset ID button"
      to: "navigator.clipboard.writeText"
      via: "copyAssetId method"
      pattern: "navigator\\.clipboard\\.writeText"
    - from: "detail dialog copy icon"
      to: "navigator.clipboard.writeText"
      via: "copyAssetId method"
      pattern: "navigator\\.clipboard\\.writeText"
---

<objective>
Add a "Copy Asset ID" feature in two places: (1) as a new option in the existing right-click context menu on dashboard asset tiles, and (2) as a small copy icon next to the asset name in the asset detail dialog.

Purpose: Allow users to quickly grab an asset's internal UUID for debugging, API calls, or cross-referencing.
Output: Updated dashboard and detail dialog components with clipboard copy functionality.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@frontend/src/app/features/dashboard/dashboard.component.ts
@frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts

<interfaces>
<!-- Existing context menu structure (dashboard.component.ts line 442-459) -->
The context menu is a positioned div with buttons. Each button has a bootstrap icon and click handler.
The `contextMenu` object: `{ visible: boolean, x: number, y: number, asset: DashboardAsset | null }`
DashboardAsset has `id: string` (UUID).

<!-- Existing copy pattern (organization.component.ts line 486-488) -->
```typescript
navigator.clipboard.writeText(value);
this.snackBar.open('Copied to clipboard', '', { duration: 2000 });
```

<!-- Asset detail dialog header (asset-detail-dialog.component.ts line 133-139) -->
```html
<div class="detail-header">
  <div class="detail-title-area">
    <div class="detail-platform">...</div>
    <h2>{{ asset?.ad_name || 'Unnamed Ad' }}</h2>
    <div class="metadata-chips">...</div>
  </div>
</div>
```
Dialog receives `data.assetId: string` and sets `this.asset` (AssetDetailResponse with `id: string`).
MatSnackBar is already injected in both components.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add "Copy Asset ID" to dashboard context menu</name>
  <files>frontend/src/app/features/dashboard/dashboard.component.ts</files>
  <action>
In the context menu template (around line 442-459), add a new button AFTER the "Edit Metadata" button and BEFORE the `<hr class="context-divider" />` separator:

```html
<button (click)="copyAssetId(contextMenu.asset!)">
  <i class="bi bi-clipboard"></i> Copy Asset ID
</button>
```

In the component class, add a `copyAssetId` method (near the other context menu action methods around line 1700+):

```typescript
copyAssetId(asset: DashboardAsset): void {
  navigator.clipboard.writeText(asset.id);
  this.snackBar.open('Asset ID copied to clipboard', '', { duration: 2000 });
  this.contextMenu.visible = false;
}
```

This follows the exact same pattern used in organization.component.ts for slug copying.
  </action>
  <verify>
    <automated>cd /Users/sebastian.dettweiler/Claude\ Code/platform-connector/brainsuite-platform-connector && grep -n "Copy Asset ID" frontend/src/app/features/dashboard/dashboard.component.ts && grep -n "copyAssetId" frontend/src/app/features/dashboard/dashboard.component.ts</automated>
  </verify>
  <done>Context menu shows "Copy Asset ID" option with clipboard icon; clicking it copies the asset UUID and shows a snackbar; menu closes after click.</done>
</task>

<task type="auto">
  <name>Task 2: Add copy icon next to asset name in detail dialog</name>
  <files>frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts</files>
  <action>
In the detail dialog template (around line 139), modify the h2 line to include a copy icon button next to the asset name. Wrap the h2 content in a flex container:

```html
<div class="detail-title-row">
  <h2>{{ asset?.ad_name || 'Unnamed Ad' }}</h2>
  <button class="copy-id-btn" (click)="copyAssetId()" matTooltip="Copy Asset ID">
    <i class="bi bi-clipboard"></i>
  </button>
</div>
```

Add styles (in the styles block, near `.detail-title-area h2` around line 557):

```css
.detail-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.detail-title-row h2 {
  margin-bottom: 0;
}
.copy-id-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  border-radius: 4px;
  transition: color var(--transition), background var(--transition);
}
.copy-id-btn i.bi { font-size: 14px; }
.copy-id-btn:hover {
  color: var(--accent);
  background: var(--bg-hover);
}
```

Remove the existing `margin-bottom: 8px` from `.detail-title-area h2` since the wrapper now handles spacing.

In the component class, add a `copyAssetId` method:

```typescript
copyAssetId(): void {
  const id = this.data.assetId;
  navigator.clipboard.writeText(id);
  this.snackBar.open('Asset ID copied to clipboard', '', { duration: 2000 });
}
```

MatSnackBar is already imported and injected in this component (line 9, used elsewhere).
  </action>
  <verify>
    <automated>cd /Users/sebastian.dettweiler/Claude\ Code/platform-connector/brainsuite-platform-connector && grep -n "copyAssetId\|copy-id-btn\|Copy Asset ID" frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts && npx ng build 2>&1 | tail -5</automated>
  </verify>
  <done>Detail dialog header shows a small clipboard icon next to the asset name; clicking it copies the asset UUID and shows a snackbar confirmation; icon uses muted color with accent hover state.</done>
</task>

</tasks>

<verification>
1. `npx ng build` completes without errors
2. Right-click any asset tile on dashboard — context menu includes "Copy Asset ID" with clipboard icon
3. Click "Copy Asset ID" — clipboard contains the asset UUID, snackbar confirms, menu closes
4. Open any asset detail dialog — small clipboard icon appears next to the asset name heading
5. Click the clipboard icon — clipboard contains the asset UUID, snackbar confirms
</verification>

<success_criteria>
- Both copy locations work: context menu option and detail dialog icon
- Clipboard receives the asset's internal UUID (not ad_id or ad_name)
- Snackbar feedback shown for both actions
- Context menu closes after copying
- Build succeeds with no errors
</success_criteria>

<output>
After completion, create `.planning/quick/260407-eip-copy-asset-id-feature-right-click-contex/260407-eip-SUMMARY.md`
</output>
