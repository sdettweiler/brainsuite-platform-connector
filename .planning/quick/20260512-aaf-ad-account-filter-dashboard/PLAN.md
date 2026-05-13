---
slug: aaf-ad-account-filter-dashboard
description: Add Ad Account multi-select filter to the dashboard asset list
created: 2026-05-12
status: in-progress
---

# Ad Account Filter — Dashboard

## Goal
Let users filter the dashboard asset table by one or more ad accounts.

## Tasks

### Task 1 — Backend: add `ad_account_ids` param to `/dashboard/assets`
File: `backend/app/api/v1/endpoints/dashboard.py`
- Add `ad_account_ids: Optional[str] = Query(default=None)` parameter to `get_dashboard_assets`
- Parse into list: `[a.strip() for a in ad_account_ids.split(",")]`
- Add WHERE clause: `query = query.where(CreativeAsset.ad_account_id.in_(account_list))`

### Task 2 — Frontend: load ad accounts for filter options
File: `frontend/src/app/features/dashboard/dashboard.component.ts`
- Add `adAccounts: {ad_account_id: string, ad_account_name: string, platform: string}[]` property
- Add `selectedAdAccountIds: Set<string>` property (default: empty = all)
- On init, call `apiService` to GET `/platform/connections` and populate `adAccounts`
  (the connections endpoint already exists and returns `ad_account_id`, `ad_account_name`, `platform`)
- Pass `ad_account_ids` (comma-joined) to `loadData()` query params when set

### Task 3 — Frontend: Add filter UI to dashboard toolbar
File: `frontend/src/app/features/dashboard/dashboard.component.ts` (inline template)
- Add a multi-select dropdown button that shows "All Accounts" when none selected, or "{N} Accounts" when filtered
- Dropdown lists accounts grouped by platform icon + name
- Clicking an account toggles it in `selectedAdAccountIds`
- Calls `onFilterChange()` on selection change
- Style consistent with existing format/sort dropdowns (match `.filter-select` pattern)
