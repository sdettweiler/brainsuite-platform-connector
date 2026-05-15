# Phase 21: Proxy Admin UI - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Frontend + backend phase. Delivers a "Residential Proxy" configuration card as Section 1 of the existing `/configuration/admin` SuperAdmin page. The card allows a SuperAdmin to toggle proxy on/off and set the encrypted proxy URL. No Alembic migration needed — Phase 20 already added `proxy_url_encrypted` and `proxy_enabled` to `SystemConfig`. Deliverables: 3 new backend endpoints (GET + PUT proxy config, POST proxy test) and 1 new Angular section inserted into `admin.component.ts`.

</domain>

<decisions>
## Implementation Decisions

### Toggle and URL — Save Behavior
- **D-01:** Toggle is saved immediately on change (one PUT call on toggle event, like the Scoring Controls toggle). No Save button for the toggle state.
- **D-02:** Proxy URL is saved via a separate edit mode — a "Replace" button opens an input field; user pastes the URL and clicks "Save URL". Identical UX flow to the YouTube Cookies edit mode.
- **D-03:** When proxy is disabled (toggle OFF), the URL input area is visually disabled/greyed out. This signals that the URL only matters when proxy is active.

### URL Display When Configured
- **D-04:** When a proxy URL is saved, the backend returns a host-visible masked string from the GET endpoint. The backend parses `http://user:pass@host:port` and replaces the credentials with bullets: `http://••••••@geo.iproyal.com:12321`. The frontend renders this string as-is — no URL parsing in Angular.
- **D-05:** If no proxy URL is configured, the backend returns `null` for the masked field; the frontend shows "No URL saved." with an "Add URL" button.
- **D-06:** Proxy URL is never returned in decrypted form via any API response. Only the masked string is exposed.

### Test Connection Button
- **D-07:** Include a "Test Connection" button on the card. Only active when proxy is enabled and a URL is configured (otherwise disabled).
- **D-08:** The test endpoint (`POST /super-admin/proxy-config/test`) makes an HTTPS reachability check: uses `httpx.AsyncClient` to GET `https://www.youtube.com/` through the configured proxy URL with a 5-second timeout. Returns `{success: bool, latency_ms: int | null, error: str | null}`. Pass = 2xx received; Fail = timeout, connection error, or non-2xx.
- **D-09:** The frontend shows the test result inline in the card (green "Reachable (NNNms)" or red "Failed: [error]") for the duration of the session. No persistence of test results.

### Card Position
- **D-10:** The Residential Proxy card is inserted as Section 1 in `admin.component.ts`, before the existing "YouTube Cookies" section. Page order becomes: Residential Proxy → YouTube Cookies → SuperAdmin Management → Organizations → Scoring Controls.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### API Pattern to Copy
- `backend/app/api/v1/endpoints/super_admin.py` §`get_youtube_cookies` / `update_youtube_cookies` (lines ~123–225) — GET/PUT endpoint structure, encrypt_token/decrypt_token usage, health response pattern; proxy endpoints copy this pattern directly
- `backend/app/core/security.py` — `encrypt_token` / `decrypt_token` functions; used for all SystemConfig encrypted fields

### Schema (Already Extended by Phase 20)
- `backend/app/models/system_config.py` — `SystemConfig` model; `proxy_url_encrypted` (Text, nullable) and `proxy_enabled` (Boolean, default False) columns already present; no migration needed in Phase 21

### Frontend to Modify
- `frontend/src/app/features/configuration/pages/admin.component.ts` — existing admin page; proxy card inserted as first `<section>` before the YouTube Cookies section; reuse `.config-section`, `.section-header`, `.section-body`, `.cookie-card`, `.slot-header`, `.masked`, and toggle patterns already in this file

### Phase 20 Context (Predecessor Decisions)
- `.planning/phases/20-proxy-download-infrastructure/20-CONTEXT.md` — Phase 20 D-05 defines the redaction format (`[PROXY:host]` in logs); D-08 defines provider URL format (`http://user:pass@geo.iproyal.com:12321`); D-09 explains why no automated health check was in Phase 20 (manual ops step) — Phase 21 adds the UI-facing test

### Requirements
- `.planning/REQUIREMENTS.md` §PROXY-05 — "A SuperAdmin can configure the residential proxy URL (stored Fernet-encrypted in SystemConfig) and toggle the proxy on/off from the /configuration/admin UI"
- `.planning/ROADMAP.md` §Phase 21 — 4 success criteria (card visible to SuperAdmin, URL encrypted + never returned, toggle takes immediate effect, not visible to non-SuperAdmin)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MatSlideToggle` — already imported in `admin.component.ts`; `(change)="onProxyToggle($event.checked)"` + `[disabled]="togglingProxy"` pattern matches scoring toggle exactly
- `MatSnackBar` — already imported; use for "Proxy enabled/disabled", "URL saved", "Test passed/failed" toasts
- `.cookie-card`, `.slot-header`, `.masked`, `.cookie-display`, `.cookie-missing`, `.cookie-edit`, `.cookie-edit-actions` CSS classes — already defined in `admin.component.ts` styles; proxy URL display reuses these without new CSS

### Established Patterns
- `encrypt_token` / `decrypt_token` + nullable Text column on `SystemConfig` — established by youtube-cookies endpoints; proxy URL follows the same pattern
- Singleton SystemConfig read pattern: `result = await db.execute(select(SystemConfig)); config = result.scalar_one_or_none(); if not config: config = SystemConfig(); db.add(config)` — copy from existing super_admin.py endpoints
- `get_current_superadmin` dependency — already imported in `super_admin.py`; use on all 3 new endpoints
- `this.api.get()` / `this.api.put()` / `this.api.post()` via `ApiService` — Angular HTTP pattern already in component

### Integration Points
- `backend/app/api/v1/endpoints/super_admin.py` — add 3 new routes to the existing `router`; no new router or router registration needed
- `frontend/src/app/features/configuration/pages/admin.component.ts` — insert proxy card HTML before the YouTube Cookies `<section>` block; add proxy state properties (`proxyConfig`, `loadingProxy`, `editingProxyUrl`, `testingProxy`, `testResult`) and methods (`loadProxyConfig`, `saveProxyToggle`, `saveProxyUrl`, `testProxy`) to the component class
- `backend/requirements.txt` — `httpx` is likely already present (used elsewhere); verify before adding

</code_context>

<specifics>
## Specific Ideas

- Masked URL format: backend parses the stored URL before masking — if URL matches `http(s)://user:pass@host:port`, replace `user:pass` portion with `••••••`; return `http://••••••@geo.iproyal.com:12321`. If URL doesn't match expected format (malformed), return a generic `[URL configured]` indicator.
- Test endpoint response: `{ "success": true, "latency_ms": 312, "error": null }` or `{ "success": false, "latency_ms": null, "error": "Connection timed out after 5s" }`
- Inline test result shown below the Test button: green text "Reachable (312ms)" or red text "Failed: Connection timed out after 5s" — no separate dialog
- Toggle behavior: proxy_enabled PUT body `{ "proxy_enabled": true/false }` → immediate response with new state; backend reads and writes SystemConfig in same transaction
- Proxy URL PUT body: `{ "proxy_url": "<raw url>" }` → backend encrypts and stores; returns GET response (masked string + enabled state)
- httpx test: `proxies={"https://": proxy_url}` — use the stored (decrypted) URL; never log it

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 21-proxy-admin-ui*
*Context gathered: 2026-05-15*
