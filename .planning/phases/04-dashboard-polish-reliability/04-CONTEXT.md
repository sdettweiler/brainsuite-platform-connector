# Phase 4: Dashboard Polish + Reliability - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Complete the creative performance UI so agencies can identify top/bottom performers at a glance, and surface platform sync health so users trust the data is current. Covers: score range filter (new), platform health panel on Configuration page with reconnect prompts (new), thumbnail fallback for video creatives (fix), and score sort null-handling (fix). DASH-02, DASH-03, REL-03 are already done in Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Score Range Filter (DASH-05)

- **D-01:** Dual-handle range slider using `@angular-slider/ngx-slider` — one new npm dependency, dual handle out of the box, Material-compatible styling.
- **D-02:** Slider range: 0–100 (matches BrainSuite score scale). Default: full range (no filter applied).
- **D-03:** Filter is applied as `score_min` / `score_max` query params sent to the backend `/dashboard/assets` endpoint. Backend already filters by platform — add score range in the same WHERE clause.
- **D-04:** Slider lives in the existing filter bar alongside platform buttons, format filter, and sort dropdown. No new panel needed.
- **D-05:** When no scored assets exist yet, slider is visible but disabled (opacity-reduced) with a tooltip "No scored creatives yet".

### Thumbnail Fallback (DASH-01)

- **D-06:** Video creatives with no `thumbnail_url`: show the platform icon centered on a dark background (`#111`) with a small `VIDEO` tag in the bottom-right corner — same treatment as the CE tab media panel.
- **D-07:** Image creatives with no `asset_url` or `thumbnail_url`: fall back to the existing `placeholder.svg`.
- **D-08:** `thumbnail_url` is already returned by the backend and referenced in the frontend card template. Verify the CSS correctly constrains `object-fit: cover` for the card grid tile (currently `height: 160px` in dashboard styles). No backend changes needed.

### Sort Completeness (DASH-04)

- **D-09:** Sort-by-score nulls always last — `NULLS LAST` in the SQL ORDER BY regardless of asc/desc direction. Backend already has a `sort_col_map` for `score`; add `nullslast()` wrapper via SQLAlchemy.
- **D-10:** Default sort on page load remains `spend desc` (existing behavior). No change.
- **D-11:** Sort options already in the dropdown: Spend, CTR, ROAS, ACE Score, Platform. Verify all 5 map correctly in the backend `sort_col_map` — `total_score` column via `CreativeScoreResult` outer join.

### Platform Health Panel (REL-01, REL-02)

- **D-12:** Health panel lives on the **Configuration page** — each platform connection row is extended with: last sync time (human-relative: "2 hours ago"), health badge, and inline reconnect button.
- **D-13:** Three health states per connection:
  - `connected` — last sync within 24h, token not expired → green badge "Connected"
  - `token_expired` — `token_expiry` < now → amber badge "Token expired" + "Reconnect" button
  - `sync_failed` — last sync attempted but no successful sync in >48h, or a stored error flag → red badge "Sync failed" + "Reconnect" button
- **D-14:** "Reconnect" button triggers the existing OAuth re-auth flow (same as initial connect) — reuse `connectPlatform()` method, no new endpoints needed.
- **D-15:** Health state is computed client-side from `token_expiry` and `last_synced_at` fields already returned by `GET /api/v1/platforms/connections`. No new backend endpoint required.
- **D-16:** No dashboard-level banner or header chip — health info lives on Configuration page only.

### Claude's Discretion

- Exact ngx-slider styling (track color, handle size) — match the existing orange accent theme.
- Debounce duration for slider change → API call (300–500ms recommended).
- Exact "sync failed" threshold (e.g. 48h without successful sync) — Claude can pick a reasonable value.
- Configuration page layout adjustment to fit the new health columns without breaking existing connection management UI.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements
- `.planning/REQUIREMENTS.md` §Dashboard Enhancements — DASH-01 through DASH-05
- `.planning/REQUIREMENTS.md` §Reliability — REL-01, REL-02, REL-03
- `.planning/ROADMAP.md` §Phase 4 — Success criteria (5 items)

### Existing code to modify
- `frontend/src/app/features/dashboard/dashboard.component.ts` — add score range slider, thumbnail fallback, nulls-last sort
- `backend/app/api/v1/endpoints/dashboard.py` — add `score_min` / `score_max` query params + NULLS LAST on score sort
- `frontend/src/app/features/configuration/` — add health badge + reconnect button to each platform connection row (find exact file path at implementation time)
- `backend/app/api/v1/endpoints/platforms.py` — verify `token_expiry` and `last_synced_at` are returned in connections list response (line ~583 already returns `last_synced`)

### Existing patterns to follow
- `frontend/src/app/features/dashboard/dashboard.component.ts` — existing `onFilterChange()` / `loadAssets()` pattern for adding new filter params
- `backend/app/api/v1/endpoints/dashboard.py` — `sort_col_map` dict + SQLAlchemy `.order_by()` (line ~223) — add `nullslast()` wrapper
- `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` — CE tab media panel dark-bg + platform icon fallback pattern (reuse for card grid thumbnail fallback)

</canonical_refs>

<code_context>
## Existing Code Insights

### Already Implemented (do not re-implement)
- Score badge in dashboard grid: `total_score` + `total_rating` already rendered (Phase 3)
- CE tab dimension breakdown: fully implemented (Phase 3)
- SCHEDULER_ENABLED guard on scoring job (Phase 3) and sync jobs (existing)
- Platform filter buttons in dashboard: `selectedPlatforms` Set + `onFilterChange()` (existing)
- Sort dropdown: `sortBy` state + `sort_by` query param (existing, all 5 options already in UI)
- `last_synced_at` on PlatformConnection model and returned in platforms list endpoint

### Reusable Assets
- `dashboard.component.ts` → `onFilterChange()` — call this after slider debounce to reload assets with new score_min/max params
- `platforms.ts endpoint` → `/api/v1/platforms/connections` — already returns `last_synced_at`, `token_expiry` (verify field name); health state computed in Angular, no new endpoint
- Platform icon URLs already in `getPlatformOverlayIcon()` — reuse for thumbnail fallback

### Integration Points
- ngx-slider: add to `frontend/package.json`, import `NgxSliderModule` in dashboard standalone component
- Score filter params: `loadAssets()` already passes params object to `api.get('/dashboard/assets', params)` — add `score_min` / `score_max` keys
- Backend sort: `sort_col_map` in `dashboard.py` maps `"score"` to `CreativeScoreResult.total_score` — wrap with `nullslast()`

</code_context>

<specifics>
## Specific Ideas

- Slider uses orange accent (`#FF7700`) to match existing theme — consistent with score badges and pillar colors
- "2 hours ago" relative time formatting for last sync — Angular `DatePipe` with custom relative pipe or simple JS `Date` math
- Health badge uses existing CSS classes: `--success` (connected), `--warning` (token expired), `--error` (sync failed)

</specifics>

<deferred>
## Deferred Ideas

- Dashboard-level warning banner when any platform has issues — user chose Configuration-only; defer to v2 if needed
- Score-to-ROAS correlation view — DASH-v2-01 (v2 backlog, already deferred)
- Top/bottom performer highlighting — DASH-v2-02 (v2 backlog)
- "Never synced" fourth health state — could add later if needed; not in Phase 4 scope

</deferred>

---

*Phase: 04-dashboard-polish-reliability*
*Context gathered: 2026-03-24*
