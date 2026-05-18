---
slug: platform-connections-ux
created: 2026-05-18
status: in-progress
---

# Platform Connections UX Improvements

## Goal
Two improvements to the platform connections page:
1. Responsive columns — all columns shrink naturally; actions (three-dots) always visible via sticky right.
2. Asset count chip — new column showing complete/total assets per connection, color-coded green/amber/red.

## Tasks

### T-01: Backend — asset counts on connections list
- Add `asset_count: int = 0` and `complete_count: int = 0` to `PlatformConnectionResponse` schema
- In `list_connections` endpoint: after fetching items, run batch COUNT query grouped by `platform_connection_id`
- "Complete" = `asset_url IS NOT NULL AND thumbnail_url IS NOT NULL`
- Attach counts to each item in response (model_dump + extend dict)

### T-02: Frontend template — responsive columns + asset chip
- `platforms.component.ts` (inline template):
  - Add `asset_count?: number; complete_count?: number` to `PlatformConnection` interface
  - Add `<th class="col-assets">Assets</th>` between health and currency
  - Add `<td class="col-assets">` chip using `getAssetChipClass(conn)` / `getAssetChipLabel(conn)`
- Add methods `getAssetChipClass` and `getAssetChipLabel` to component class

### T-03: Frontend SCSS — responsive table + sticky actions + chip styles
- Switch `table-layout: fixed` → `table-layout: auto`
- All columns: use `min-width` not hard `width` (except check/checkbox column)
- `.col-actions`: `position: sticky; right: 0; z-index: 2; background: var(--bg-card)`
- Add `box-shadow: -2px 0 4px rgba(0,0,0,0.08)` on sticky actions column
- Override sticky bg for hover/selected rows
- Add `.asset-chip` with `.chip-green`, `.chip-amber`, `.chip-red`, `.chip-gray`

## Files
- `backend/app/schemas/platform.py`
- `backend/app/api/v1/endpoints/platforms.py`
- `frontend/src/app/features/configuration/pages/platforms.component.ts`
- `frontend/src/app/features/configuration/pages/platforms.component.scss`
