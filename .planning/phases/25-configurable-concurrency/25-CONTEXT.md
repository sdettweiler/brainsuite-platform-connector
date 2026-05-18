# Phase 25: Configurable Concurrency - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers one thing: a configurable download concurrency cap.

A SuperAdmin sets `max_concurrent_downloads` (integer 1–10, default 3) via the admin UI at `/configuration/admin`. The value is persisted in the `SystemConfig` DB row. At runtime, a shared `asyncio.Semaphore` in `proxy_cache.py` enforces the limit across all concurrent DV360 and Google Ads download calls.

**Also in scope:** Restructure the admin page layout — merge existing "Residential Proxy" and "DV360 Cookies" sections into a single "Download Settings" section with visual separators.

**Not in scope:** Per-platform concurrency limits, semaphore-based throttling for non-download operations, TikTok/Meta download changes, Alembic merge (Phase 26).

</domain>

<decisions>
## Implementation Decisions

### Semaphore Architecture

- **D-01:** One global `asyncio.Semaphore` shared across DV360 and Google Ads. Both platforms compete for the same N slots — total concurrent downloads across the system equals `max_concurrent_downloads`. NOT per-platform limits.
- **D-02:** Semaphore lives in `backend/app/services/sync/proxy_cache.py` (extended from Phase 24). The module already holds module-level async state with `asyncio.Lock` — semaphore cache follows the same pattern. File may be renamed (e.g., `download_cache.py`) or kept as-is; planner decides.
- **D-03:** Semaphore capacity is cached with a 60-second TTL, matching the proxy config cache TTL. On TTL expiry, the next download call re-reads `max_concurrent_downloads` from DB. If the value changed, a new `asyncio.Semaphore(new_value)` is created and replaces the module-level reference. In-flight downloads finish on the old semaphore (no cancellation); new downloads acquire from the new semaphore.

### Update Timing

- **D-04:** Setting changes take effect within 60 seconds (TTL-based). This satisfies ROADMAP SC-4 ("next download job without a server restart") — sync jobs run every 15 minutes, well beyond the 60s TTL window.
- **D-05:** No explicit cache invalidation when admin saves. The TTL expiry mechanism is sufficient. No changes needed to the `PUT /proxy-config` endpoint or a new invalidation endpoint.

### Admin UI Layout Restructure

- **D-06:** Phase 25 restructures `/configuration/admin`. The existing standalone "Residential Proxy" and "DV360 Cookies" sections are merged into a single top-level section: **"Download Settings"**. Within that section, three subsections separated by visual dividers:
  1. **Parallel Downloads** (new — positioned first, most prominent)
  2. **Residential Proxy** (moved from existing standalone section)
  3. **Cookies** (moved from existing standalone section)
- **D-07:** Section structure uses the existing `<section class="config-section">` / `section-header` / `section-body` pattern. Visual separators between subsections are `<hr>` or `<mat-divider>` — planner decides the exact element.
- **D-08:** "Parallel Downloads" subsection is positioned at the TOP of "Download Settings" — it's the new feature and the primary reason for this phase.

### Number Input UX

- **D-09:** Discrete `mat-slider` with `step=1`, `min=1`, `max=10`, tick marks at each integer (`discrete` mode). Current value displayed as the slider thumb label.
- **D-10:** Save/Discard buttons confirm the change — consistent with the existing proxy URL save pattern in the admin page. No autosave on blur or slide.
- **D-11:** Default value displayed when no custom value exists: 3 (server-default on the DB column).

### DB Schema

- **D-12:** New column on `SystemConfig`: `max_concurrent_downloads = mapped_column(Integer, nullable=False, default=3, server_default="3")`. New Alembic migration required — this migration must exist before Phase 26 runs the Alembic 4-head merge (DEBT-01).

### API Endpoint

- **D-13:** New endpoint(s) on `backend/app/api/v1/endpoints/super_admin.py` following the existing proxy-config GET/PUT pattern. Response model exposes `max_concurrent_downloads: int`. Planner decides whether to add a dedicated `/download-concurrency` route or extend a general `/system-config` route.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements

- `.planning/REQUIREMENTS.md` §PERF-02 — acceptance criteria (range 1–10, default 3, shared semaphore, all platforms)
- `.planning/ROADMAP.md` §Phase 25 — 4 success criteria (SC-1: setting persists; SC-2: monitoring UI shows queuing; SC-3: default 3 on fresh install; SC-4: change takes effect next job without restart)

### Backend — Semaphore Module

- `backend/app/services/sync/proxy_cache.py` — **extend this file** with semaphore cache; reuse existing module-level `asyncio.Lock` + TTL pattern (D-02, D-03)

### Backend — Download Call Sites

- `backend/app/services/sync/dv360_sync.py` §`_download_video_asset` — wrap the `_do_download()` calls (established in Phase 24) with `async with semaphore`
- `backend/app/services/sync/google_ads_sync.py` §`_download_video` — same wrapping pattern

### Backend — Model + API

- `backend/app/models/system_config.py` — add `max_concurrent_downloads` column (D-12)
- `backend/app/api/v1/endpoints/super_admin.py` — existing GET/PUT `/proxy-config` endpoint pattern; add analogous endpoint(s) for concurrency config (D-13)

### Frontend — Admin UI

- `frontend/src/app/features/configuration/pages/admin.component.ts` — restructure sections (D-06); add `mat-slider` for concurrency (D-09, D-10); inline template (no separate .html file)

### Prior Phase Context

- `.planning/phases/24-download-performance-backend/24-CONTEXT.md` — semaphore placement note and Phase 24 download call chain decisions (D-03 through D-04 of Phase 24 establish the function signatures that Phase 25 wraps)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `proxy_cache.py` module-level cache pattern (`_cache: dict`, `_cache_lock = asyncio.Lock()`, TTL via `time.monotonic()`) — semaphore cache follows identical structure; 7 unit tests already validate the pattern
- `admin.component.ts` `<section class="config-section">` / `section-header` / `section-body` / `section-desc` classes — new "Download Settings" section uses same DOM structure
- Existing Save/Discard button pattern in proxy URL card (`save-btn` mat-flat-button + discard mat-stroked-button) — reuse for concurrency slider confirmation

### Established Patterns

- `SystemConfig` singleton: `proxy_enabled` (Boolean) and `proxy_url_encrypted` (Text) are read-only pattern for new `max_concurrent_downloads` (Integer) column
- `super_admin.py` GET/PUT endpoint pair with Pydantic response model, `_mask_proxy_url` security annotation — follow same structure for concurrency endpoint
- Async session in proxy_cache.py via `get_session_factory()` + `select(SystemConfig)` — same DB read pattern for new cache function

### Integration Points

- Both `_download_video_asset` (dv360_sync.py) and `_download_video` (google_ads_sync.py) call `_do_download()` — semaphore acquisition wraps this call in both files
- SuperAdmin JWT guard already on all super_admin.py endpoints — new concurrency endpoint inherits same protection automatically
- Angular `mat-slider` (Angular Material 17.3.0, already installed) — no new packages needed

</code_context>

<specifics>
## Specific Ideas

- User explicitly wants all download-related admin controls (concurrency, proxy, cookies) in ONE section with visual separators — not three separate top-level sections. "Parallel Downloads" subsection comes first.
- Slider over number input — visual representation of the 1–10 range is preferred over a bare number field.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 25-configurable-concurrency*
*Context gathered: 2026-05-18*
