---
plan: 23-02
phase: 23
status: complete
completed_at: 2026-05-18
---

# Plan 23-02 — Duration Slider Frontend

## Outcome

Dashboard duration filter fully wired and UAT-approved. Single file modified: `frontend/src/app/features/dashboard/dashboard.component.ts`.

## Commits

- `843ce30` feat(23-02): add duration filter state, formatDuration helper, computed getter, and methods
- `c0dec26` feat(23-02): add duration slider template, chip, NULL callout, and CSS
- `1918d94` fix(23-02): preserve slider visibility and bounds handles when duration filter active
- `9d1adc7` fix(23-02): apply duration filter only to VIDEO assets; non-video always pass through
- `abec3e9` fix(23-02): show slider when VIDEO assets exist regardless of backfill state
- `4f3f698` fix(23-02): bounds update correctly on filter change; slider hides for image-only accounts
- `9b9e64b` fix(23-02): accept single-value duration bounds (min == max)
- `7280b6e` fix(23-02): reset duration handles to full range when bounds change

## Supporting changes (same session)

- `4152a8f` feat(23): probe video_duration inline during asset download for all 4 platforms (Meta, TikTok, Google Ads, DV360)
- `9be5daa` fix(23): exclude empty asset_url from duration backfill query
- Backend `duration-bounds` extended with `has_video_assets` flag; returns null bounds instead of 0/3600 fallback
- 228 VIDEO assets duration-backfilled via one-off `run_duration_backfill` run

## UAT Results

All scenarios approved:
- A: Slider visible only when VIDEO assets present ✓
- B: Handles filter grid; non-video ads always pass through ✓
- C: Duration chip with dismiss resets to full range ✓
- D: NULL callout appears when filter active and null_duration_count > 0 ✓
- E: Bounds reload on other filter changes; bounds reset handles when range changes ✓

## Key decisions / bugs fixed

1. `hasDurationData` guard removed from `*ngIf` — slider shows for VIDEO assets regardless of backfill state
2. `has_video_assets` from backend is authoritative for slider visibility (filter-aware, not page-scoped)
3. `isDurationFilterActive` only preserved handles if bounds didn't change; bounds-change always resets handles
4. `manualRefresh` EventEmitter added to force ngx-slider re-render on floor/ceil updates
5. `hasRealBounds` uses `>=` not `>` — single-value range (min == max) is valid
