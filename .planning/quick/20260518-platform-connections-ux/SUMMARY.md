---
slug: platform-connections-ux
status: complete
completed: 2026-05-18
commit: 1fad753
---

# Summary

All three tasks complete in a single commit (1fad753).

## What was done

**T-01 Backend asset counts**
- Added `asset_count: int = 0` and `complete_count: int = 0` to `PlatformConnectionResponse`
- `list_connections` runs a batch `GROUP BY platform_connection_id` query after fetching connections
- "Complete" = `asset_url IS NOT NULL AND thumbnail_url IS NOT NULL`
- Counts injected into each item dict before returning

**T-02 Frontend template**
- `PlatformConnection` interface extended with `asset_count?` and `complete_count?`
- New `<th class="col-assets">` and `<td>` with `.asset-chip` chip
- `getAssetChipClass()` / `getAssetChipLabel()` methods added to component

**T-03 SCSS**
- `table-layout: fixed` → `table-layout: auto`; all columns use `min-width`
- `.col-actions`: `position: sticky; right: 0` with per-row bg overrides for hover/selected
- Subtle `box-shadow: -2px 0 6px` on sticky column
- `.asset-chip` with `.chip-green`, `.chip-amber`, `.chip-red`, `.chip-gray` variants
