# Research Summary — v1.4 YouTube Downloads & Dashboard Filters

**Project:** BrainSuite Platform Connector
**Domain:** Multi-tenant SaaS ad intelligence platform — residential proxy layer + dashboard UX
**Milestone:** v1.4 — YouTube/DV360 Proxy Downloads & Dashboard Filters
**Researched:** 2026-05-14
**Confidence:** HIGH

---

## Stack Additions

- **`bgutil-ytdlp-pot-provider==1.3.1`** (Python, backend only) — YouTube proof-of-origin (PO) token plugin. YouTube's BotGuard attestation layer requires a PO token on every format URL request; without it yt-dlp returns 403 regardless of proxy or cookie state. Install in backend image; plugin auto-registers with yt-dlp at import time. Requires yt-dlp >= 2025.05.22 — verify pin in requirements.txt.
- **bgutil HTTP server Docker service** — Run `brainicism/bgutil-ytdlp-pot-provider:1.3.1-deno` as a persistent sidecar on port 4416 (HTTP mode, not script mode). HTTP mode pools tokens across requests; script mode spawns a subprocess per token request, causing cold-start latency and orphan processes on container crash. Backend `depends_on: bgutil-pot` with `service_healthy` condition.
- **No new npm packages** — All dashboard filter components (`MatAutocomplete`, `ngx-slider` dual-handle range, MatMenu with checkboxes) are already installed in `@angular/material 17.3.0` and `@angular-slider/ngx-slider 17.0.2`.
- **Two new `system_config` columns** (Alembic migration, no new table) — `proxy_url_encrypted: Text` (nullable, Fernet-encrypted) and `proxy_enabled: Boolean` (default False). No other schema changes.

---

## Feature Table Stakes

**Proxy download track — done means:**
- Proxy URL stored encrypted (Fernet, same key as YouTube cookies) in `SystemConfig`; never appears in logs, error messages, or API responses
- SuperAdmin can toggle proxy on/off and configure URL via existing `/configuration/admin` panel — no code deploy required to change proxy config
- DV360 and Google Ads sync inject the proxy URL into `yt_dlp.YoutubeDL()` opts; both platforms patched simultaneously (never one without the other per project rule)
- Sticky session ID embedded in proxy username per download job (`user-session-{12_random_chars}:pass@host:port`) — exit IP stable for entire job; no mid-download IP rotation
- bgutil plugin auto-generates PO tokens when yt-dlp encounters a format URL — no explicit per-video token code needed
- Cookieless-first retry path preserved; proxy is an additive layer, not a replacement
- YouTube video downloads verified to succeed against GCP Cloud Run environment

**Dashboard filters track — done means:**
- Metadata autocomplete: user types partial value (min 2 chars, 300ms debounce), dropdown shows matching values from harmonized metadata; `switchMap` + `takeUntil(destroy$)` prevents request spam and memory leaks
- Ad account multi-select: existing implementation (commit e403eaf) verified working with all new filter API params; regression test passes
- Video duration range slider: dual-handle ngx-slider visible only when `hasAnyVideo = true` (sticky flag set on first response with VIDEO assets); applies `WHERE video_duration BETWEEN min AND max` via new `duration_min` / `duration_max` query params
- All three filters compose with AND logic and work simultaneously; pagination preserves active filters
- "Clear filters" resets all filter state and re-queries
- Backend `GET /dashboard/assets` extended with `meta_filters` (comma-separated `field_id:value` pairs), `duration_min`, `duration_max` — all optional, fully backward compatible

---

## Architecture Changes

**New files:** None

**Modified files:**
- `backend/app/models/system_config.py` — add `proxy_url_encrypted` (Text, nullable) and `proxy_enabled` (Boolean, default False)
- `backend/alembic/versions/{hash}.py` — additive migration; 2 columns, 0 constraint changes, no data backfill
- `backend/app/api/v1/endpoints/super_admin.py` — add `GET /proxy-config` (status only, never decrypted URL) and `PUT /proxy-config` (encrypts URL via existing `encrypt_token()`, sets flag); copy-exact auth pattern from `/youtube-cookies` endpoints (~80 lines)
- `backend/app/services/sync/dv360_sync.py` — proxy injection into `ydl_opts` dict inside `_do_download_with_cookies()` after dict construction; sticky session ID generation; retry order updated to cookieless-first (~15 lines)
- `backend/app/services/sync/google_ads_sync.py` — identical changes to DV360; same `_do_download_with_cookies` structure (~15 lines)
- `backend/Dockerfile` — `RUN pip install bgutil-ytdlp-pot-provider==1.3.1` (+1 line)
- `docker-compose.yml` — new `bgutil-pot` service (Deno image, port 4416, health check); `backend` gains `depends_on: bgutil-pot`
- `backend/app/api/v1/endpoints/dashboard.py` — add `meta_filters`, `duration_min`, `duration_max` optional query params; JOIN on `AssetMetadataValue` filtered by `organization_id`; numeric WHERE clauses (~20 lines)
- `frontend/src/app/features/dashboard/dashboard.component.ts` — merge quick-work commits (afc4fef, 44d8dda, 3dd4b1c); add `selectedMetaFilters`, `durationMin/Max`, `hasAnyVideo`, `durationChange$`, API param serialization in `loadData()` (~150 lines net)
- `frontend/src/app/features/dashboard/dashboard.component.html` — metadata popover + chip row; duration slider after score slider

**DB indexes to add with migration:**
- Composite index on `asset_metadata_value (asset_id, metadata_field_id, organization_id)` — required for metadata filter JOIN to stay under 100ms at 10k assets/org

**Total surface:** ~130 lines net backend, ~150 lines net frontend, 1 additive migration. No breaking changes.

---

## Watch Out For

1. **Proxy credentials leaking into yt-dlp error messages** — yt-dlp error strings include the full proxy URL (`Failed to connect to proxy://user:pass@...`). Add a `redact_credentials(msg)` utility (regex strip `proxy://[^@]+@[^/]+`) before any `logger.warning/error` call that touches yt-dlp output. This is a security requirement, not polish. Verify with `grep -r "proxy://" logs/` after first production run.

2. **bgutil running in script mode instead of HTTP mode** — Script mode spawns a subprocess per PO token request (500ms–2s overhead each) and leaves orphan processes on container crash. Always use HTTP mode via the Deno Docker service on port 4416. Confirm port 4416 is reachable from the backend container (`curl http://bgutil-pot:4416/health`) before any download test runs.

3. **Cherry-picking old filter commits instead of surgical recovery** — Quick-work commits afc4fef and 44d8dda predate v1.3 architecture changes and will produce merge conflicts in 5–10 files. Do not cherry-pick. Read both versions side-by-side, re-implement filters using the current v1.3 component patterns, and add integration tests for debounce timing and filter state before merging. Recover one filter type at a time (metadata → accounts → duration), commit, test, then next.

4. **Video duration `NULL` for legacy assets making the duration filter appear broken** — Assets synced before v1.3 have `video_duration = NULL`. A duration range filter returning zero results confuses users. Two required mitigations: (a) async background backfill job (batches of 50, 1s sleep, graceful `FileNotFoundError` skip if video missing from MinIO); (b) UI callout noting "Duration filter applies to assets synced after [date]. X of Y assets have duration data." Both must ship in v1.4, not deferred.

5. **Metadata filter JOIN missing `organization_id` guard** — The `AssetMetadataValue` join in `dashboard.py` must include `organization_id == current_org_id` in every join condition. Omitting this exposes metadata values from other organizations. This is a security bug. Test with a two-org fixture (org A's metadata should never appear in org B's autocomplete results) before merging.

---

## Build Order Recommendation

1. **Alembic migration + SystemConfig model** — Add `proxy_url_encrypted`, `proxy_enabled` to `system_config`; add composite index on `asset_metadata_value`. Additive only, zero risk. Unblocks both tracks in parallel.

2. **SuperAdmin proxy config endpoints** — `GET /proxy-config` and `PUT /proxy-config` in `super_admin.py`, mirroring `/youtube-cookies` pattern exactly. Verify proxy URL never appears in any API response. Lets ops configure the proxy URL before sync code lands.

3. **bgutil Docker setup + backend install** — Add `bgutil-pot` service to `docker-compose.yml` (Deno image, health check on port 4416). Add package to `requirements.txt` and `Dockerfile`. Confirm container-to-container connectivity. Unblocks all download work.

4. **DV360 proxy injection + sticky session + credential redaction** — Modify `dv360_sync.py`: read + decrypt proxy config, generate sticky session ID, inject into `ydl_opts`, implement `redact_credentials()` utility. Smoke test with Webshare free tier against a public YouTube URL on a GCP host.

5. **Google Ads proxy injection** — Identical changes to `google_ads_sync.py`. Must be done in the same step as DV360 per the project rule of patching all platforms simultaneously.

6. **Dashboard backend filter params** — Extend `GET /dashboard/assets` with `meta_filters`, `duration_min`, `duration_max`. Add JOINs and WHERE clauses with `organization_id` guard. Unit test: each filter alone, all three combined, cross-org isolation.

7. **Dashboard frontend filters** — Merge/re-implement quick-work branches using current architecture. Add metadata popover + chip row + duration slider. Wire params into `loadData()`. Implement correct RxJS pipeline for autocomplete (`filter` + `debounceTime(300)` + `distinctUntilChanged` + `switchMap` + `takeUntil(destroy$)`). Set `hasAnyVideo` sticky flag. Smoke test all three filters independently and in combination with pagination.

8. **Duration backfill job + UI callout** — Async background job to populate `video_duration` for legacy assets via ffprobe from MinIO, batched with sleep and graceful skip on missing files. Add UI note about filter coverage. Can run in parallel with step 7 but must ship in this milestone.

---

## Open Questions

- **Proxy provider for production** — STACK.md names Webshare (validation) and IPRoyal (production). Which has been trialed/purchased? The sticky session ID format in the proxy username is provider-specific. Confirm before step 4.

- **Proxy session pin duration** — PITFALLS-v1.4.md recommends 86400s (1 day) for Cloud Run cold start resilience. Confirm whether the chosen provider's plan supports daily session pinning or caps at a shorter TTL (e.g., 300s on some Webshare tiers).

- **Metadata autocomplete: client-side vs server-side endpoint** — ARCHITECTURE.md recommends client-side (parse from asset response, no new endpoint). Acceptable for most orgs. If any org has >500 unique metadata values, upgrade to `GET /dashboard/metadata-filter-values` server-side endpoint before that org reports slow load times. Decide threshold before shipping.

- **Ad account multi-select already working?** — ARCHITECTURE.md states it is already in main (e403eaf). Verify manually before building new filters on top of it. If broken, fix first.

- **Cloud Run `--min-instances` cost trade-off** — PITFALLS-v1.4.md recommends `--min-instances=1` to prevent bgutil cold-start latency on the first download of the day. Confirm whether scale-to-zero is required or if always-on is acceptable given production usage patterns.

---

*Research completed: 2026-05-14*
*Ready for roadmap: yes*
