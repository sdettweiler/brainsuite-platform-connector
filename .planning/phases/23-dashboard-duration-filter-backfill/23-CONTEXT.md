# Phase 23: Dashboard Duration Filter + Backfill - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Full-stack phase. Delivers:

1. **Duration filter (DASH-03):** A dual-handle range slider in the dashboard filter bar, visible only when VIDEO assets are present in the current grid. Filters the creative grid by `video_duration` range; assets with NULL duration are excluded from filtered results and a count callout is shown inline.
2. **Async backfill job:** Triggered after each sync run. Populates `video_duration` for VIDEO assets that have a local file but NULL duration, using `ffprobe` (the existing `_get_video_duration()` pattern). Covers all platforms where videos are downloaded locally.

Phase 23 does NOT include filter state URL persistence (v1.5 candidate) or saved filter presets.

</domain>

<decisions>
## Implementation Decisions

### Slider Bounds (Dynamic, Filter-Aware)
- **D-01:** Slider bounds are **dynamic** — a `GET /dashboard/duration-bounds` endpoint returns the actual `min(video_duration)` / `max(video_duration)` scoped to the current org. No hardcoded ceiling.
- **D-02:** Bounds are **filter-aware** — they recompute when other active filters change (ad account, metadata, date range). The bounds call does NOT refire when the slider itself moves (that would be circular). Debounce appropriately.
- **D-03:** Slider labels are **formatted** — a `formatDuration(seconds: number): string` helper converts raw seconds to human-readable `Xm Ys` (e.g. 15 seconds → "15s", 135 seconds → "2m 15s"). Used in the slider label and the chip label.

### Slider Visibility
- **D-04:** Slider is **hidden completely** when `hasVideoAssets` is false. It does not appear as disabled. Clean filter bar for image-only orgs.
- **D-05:** `hasVideoAssets` is derived from the dashboard asset response — true if any asset in the current grid has `asset_type == 'video'`.

### NULL Duration Callout
- **D-06:** Callout appears **only when the duration filter is active** (i.e. `durationMin` or `durationMax` has been adjusted from the full range). Not shown by default.
- **D-07:** The count `X` in "X assets have no duration data and are excluded from this filter" is the count of VIDEO assets matching all OTHER active filters (account, metadata, date range) but excluded because their `video_duration` IS NULL. Returned as a sidebar field from the `/dashboard/assets` response (e.g. `null_duration_count`) — dynamic per filter state.
- **D-08:** Callout renders **below the chip row**, inline near the filter. Small info text — not a prominent banner.

### Backfill Job
- **D-09:** Backfill is **triggered after each sync run** — at the end of DV360, Google Ads, TikTok, and Meta sync, if any VIDEO assets with NULL `video_duration` AND a local file were created or updated. Uses the existing `BackgroundJob` model and job_tracker pattern.
- **D-10:** Targets **all platforms where the video file is local**: `asset_type = 'video' AND video_duration IS NULL AND local_file_path IS NOT NULL`. Not limited to DV360/Google Ads.
- **D-11:** **Batch of 100, sequential** within each run. `ffprobe` is local/CPU-bound so sequential batching avoids CPU spikes. If more than 100 NULL-duration assets exist, subsequent runs (triggered by later syncs) chip away at the backlog.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Frontend — Slider Pattern to Reuse
- `frontend/src/app/features/dashboard/dashboard.component.ts` — `NgxSliderModule` is already imported (line 18); score range slider uses `[(value)]="scoreMin" [(highValue)]="scoreMax" [options]="sliderOptions"` (line 222–227). Duration slider reuses this exact pattern with `durationMin` / `durationMax` state.
- `@angular-slider/ngx-slider` — already in `package.json`; `Options` interface drives `floor`, `ceil`, `translate`, `disabled`, `step`

### Frontend — Filter Bar Integration
- `frontend/src/app/features/dashboard/dashboard.component.ts` — metadata filter button/chip row (Phase 22, commits 88518fa + cfb37d4) is the structural pattern for placement in the filter bar and chip row. Duration filter follows the same slot.
- `tbd-trigger` / `tbd-menu` / `tbd-badge` CSS classes — used by all filter buttons in the filter bar

### Backend — Dashboard Endpoint to Extend
- `backend/app/api/v1/endpoints/dashboard.py` §`get_dashboard_assets` — add `duration_min: Optional[float]` + `duration_max: Optional[float]` params; extend WHERE clause with `CreativeAsset.video_duration.between(duration_min, duration_max)` when set; add `null_duration_count` to the response
- New endpoint needed: `GET /dashboard/duration-bounds` — returns `{"min_duration": float, "max_duration": float}` from `select(func.min, func.max).where(CreativeAsset.video_duration != None, CreativeAsset.asset_type == 'video', CreativeAsset.organization_id == current_user.organization_id)`; must accept and apply the same filter params as `/dashboard/assets` (for filter-aware bounds per D-02)

### Backend — Duration Extraction Utility
- `backend/app/services/sync/dv360_sync.py` §`_get_video_duration` (line 1423) — existing `ffprobe`-based duration extraction. Backfill job re-uses this exact utility (or extracts it to a shared `video_utils.py`).
- `backend/app/services/sync/harmonizer.py` line 541, 703, 894 — `video_duration` is already wired into `_ensure_asset` for DV360/Google Ads; backfill fills the gaps for assets that were created before the download step completed

### Backend — Backfill Job Pattern
- `backend/app/models/jobs.py` §`BackgroundJob` — `job_type`, `org_id`, `status`, `params` fields; backfill uses `job_type = 'duration_backfill'`
- `backend/app/services/sync/job_tracker.py` — existing job lifecycle management; backfill job follows same acquire/complete/fail pattern

### Data Model
- `backend/app/models/creative.py` line 51 — `video_duration: Mapped[float] = mapped_column(Float, nullable=True)` — already exists; no migration needed
- `backend/app/schemas/creative.py` line 98 — `video_duration: Optional[float]` — already in schema; no schema change needed

### Requirements
- `.planning/REQUIREMENTS.md` §DASH-03 — acceptance criteria for duration filter
- `.planning/ROADMAP.md` §Phase 23 — 5 success criteria; SC-3 (callout note), SC-4 (async backfill), SC-5 (composition with Phase 22 filters)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `NgxSliderModule` — already imported in `dashboard.component.ts`; `Options` config with `translate` callback drives label formatting; reuse directly for duration slider
- `sliderOptions: Options` pattern (lines 1407–1413) — copy for `durationSliderOptions: Options`; set `floor`, `ceil` from API response, `translate: (value) => formatDuration(value)`
- `_get_video_duration(file_path)` in `dv360_sync.py` — `ffprobe`-based duration extraction; extract to `backend/app/services/sync/video_utils.py` so backfill job and sync services share it
- `BackgroundJob` + `job_tracker.py` — proven pattern for all async jobs; backfill job is a new `job_type = 'duration_backfill'`

### Established Patterns
- Score filter params: `if (this.scoreMin > 0) params['score_min'] = this.scoreMin` (line 1765). Duration follows same conditional send — only append params when non-default.
- `onFilterChange()` — called by every filter action; duration slider `(userChangeEnd)` event calls this
- Sync post-hook: add `await self._trigger_duration_backfill()` at end of sync if NULLs detected. Check for NULLs with a `SELECT COUNT(*) WHERE asset_type='video' AND video_duration IS NULL AND local_file_path IS NOT NULL AND organization_id=X` before dispatching.

### Integration Points
- `/dashboard/assets` — extend with `duration_min`, `duration_max`, and `null_duration_count` in response
- `/dashboard/duration-bounds` — new endpoint; must share the account/metadata/date-range filter logic from `/dashboard/assets` (extract shared `_build_asset_filter_clause()` helper or pass params through)
- Sync services (dv360, google_ads, meta, tiktok) — each needs post-sync hook to dispatch backfill if NULLs found

</code_context>

<specifics>
## Specific Ideas

- `formatDuration(seconds: number): string` helper in `dashboard.component.ts` — `const m = Math.floor(seconds / 60); const s = Math.round(seconds % 60); return m > 0 ? \`${m}m ${s}s\` : \`${s}s\``
- Callout text: `"${nullDurationCount} video${nullDurationCount !== 1 ? 's' : ''} have no duration data and are excluded from this filter"`
- `null_duration_count` returned from `/dashboard/assets` — only compute/return when `duration_min` or `duration_max` param is present (avoids cost on every unfiltered request)
- Duration chip label: `"Duration: ${formatDuration(durationMin)} – ${formatDuration(durationMax)}"` — consistent with metadata chip format `"FieldLabel: value"`
- `hasVideoAssets = this.assets.some(a => a.asset_type === 'video')` — derived in `loadData()` response handler

</specifics>

<deferred>
## Deferred Ideas

- Filter state URL persistence (duration_min/max in query params) — v1.5 candidate, explicitly Out of Scope per REQUIREMENTS.md
- Saved filter presets (save active filter combination with a name) — REQUIREMENTS.md Out of Scope
- Duration histogram overlay on slider (show distribution of asset durations as bars behind the slider) — nice-to-have, not in ROADMAP scope

</deferred>

---

*Phase: 23-dashboard-duration-filter-backfill*
*Context gathered: 2026-05-18*
