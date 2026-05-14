# Phase 20: Proxy Download Infrastructure - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Backend-only phase. Delivers residential proxy injection into the yt-dlp download path for DV360 and Google Ads, bgutil PO token plugin installation, SystemConfig schema additions, cookieless-first retry order, and credential redaction. No UI this phase — that is Phase 21.

</domain>

<decisions>
## Implementation Decisions

### bgutil PO Token Deployment
- **D-01:** Use inline Python plugin mode — `pip install bgutil-ytdlp-pot-provider` in `Dockerfile.backend`. yt-dlp auto-detects the installed plugin and generates PO tokens inline. No sidecar process, no Docker service, no port 4416 — works on Cloud Run without any container orchestration changes.

### Proxy Injection Scope
- **D-02:** Set `ydl_opts["proxy"] = proxy_url` inside `_do_download_with_cookies` before `YoutubeDL(ydl_opts)` is instantiated. This applies the proxy to the **full yt-dlp session** — both info extraction and stream download — fixing 403s at both stages.
- **D-03:** Proxy is active on **all retry attempts** (cookieless, primary cookies, backup cookies). Every request in the retry chain routes through the residential IP. No direct-IP fallback after proxy injection.

### Retry Order
- **D-04:** New retry order when proxy is enabled: cookieless-with-proxy → primary-cookies-with-proxy → backup-cookies-with-proxy → fail. Implemented by prepending `""` (empty string) to the `attempts` list when proxy is enabled, before the cookie strings. When proxy is disabled, existing behavior is preserved (cookies first, no cookieless prepend).

### Credential Redaction
- **D-05:** Redaction is implemented by wrapping `_YDLLogger` inside the `_do_download_with_cookies` closure. The proxy URL is in closure scope, so the logger methods can call a local `_redact(msg)` helper that replaces the credential portion with `[PROXY:host]`. Example: `user:pass@proxy.provider.com:8080` becomes `[PROXY:proxy.provider.com]`. All four logger methods (debug, info, warning, error) must call `_redact`.
- **D-06:** The same redaction applies to any exception messages before they are re-raised — wrap exception string before logging.

### Sticky Sessions
- **D-07:** Generate a unique session ID per download job (not per request) using `secrets.token_urlsafe(9)` (12-char URL-safe string). Embed in proxy username as `{base_username}-session-{session_id}`. The session ID is generated once at the top of the download function, before the retry loop, and reused across all attempts for that job.

### Provider Choice
- **D-08:** Production proxy provider is **IPRoyal** ($1.75/GB pay-as-you-go, 7-day sticky sessions, no minimum commitment). Switch to Oxylabs/Bright Data when volume consistently exceeds ~2,000 videos/month. Provider URL format: `http://user:pass@geo.iproyal.com:12321` (HTTP proxy, not SOCKS5).

### Validation Gate
- **D-09:** No automated health-check endpoint in Phase 20. Validation is a manual ops step: trigger a DV360 or Google Ads sync on the production host with proxy enabled, confirm a video downloads successfully. Phase 20 success criteria SC-05 (log grep for zero credential occurrences) is also verified manually.

### What is NOT in Phase 20
- SuperAdmin UI for proxy config → Phase 21
- Google Ads sync proxy injection can be done in the same phase as DV360 (same `_do_download_with_cookies` structure)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Download Implementation
- `backend/app/services/sync/dv360_sync.py` §`_do_download_with_cookies` (line ~1164) — closure structure; proxy injection goes here; `_YDLLogger` class is the redaction target; retry loop at line ~1223
- `backend/app/services/sync/google_ads_sync.py` — near-identical `_do_download_with_cookies` structure; apply same changes

### Schema and Encryption Pattern
- `backend/app/models/system_config.py` — existing SystemConfig model; add `proxy_url_encrypted` (Text, nullable) and `proxy_enabled` (Boolean, default False, server_default="false")
- `backend/app/api/v1/endpoints/super_admin.py` — `encrypt_token`/`decrypt_token` usage pattern for SystemConfig fields; GET/PUT endpoint structure to copy for Phase 21

### Requirements
- `.planning/REQUIREMENTS.md` — PROXY-01 through PROXY-06 definitions
- `.planning/ROADMAP.md` §Phase 20 — success criteria SC-01 through SC-05

No external specs — decisions fully captured above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `encrypt_token` / `decrypt_token` from `backend/app/core/security.py` — use exactly as cookie slots use them; no new crypto needed
- `tempfile.NamedTemporaryFile` cookie pattern in `_do_download_with_cookies` — shows how to handle temp state in the executor thread; sticky session ID follows the same "generate once, pass into closure" pattern
- `secrets.token_urlsafe(9)` — standard library, no import needed beyond `import secrets`

### Established Patterns
- SystemConfig is a singleton table (singleton_guard String(1) unique); read once per download call using `get_db()` session, same as cookie loading in `dv360_sync.py`
- `loop.run_in_executor(None, lambda ...)` — all yt-dlp calls must go through this; the closure captures `proxy_url` from async scope into the sync closure safely
- Cookie loading in dv360_sync already does `decrypt_token(config.youtube_cookies_encrypted)` — proxy loading is one additional field on the same config object

### Integration Points
- Alembic migration: one new revision; two nullable columns on `system_config`; no foreign keys or constraint changes
- `backend/requirements.txt` — add `bgutil-ytdlp-pot-provider` (no version pin needed; latest stable)
- `docker/Dockerfile.backend` — `bgutil-ytdlp-pot-provider` installs via `pip install -r requirements.txt`; no Docker changes beyond the requirements file

</code_context>

<specifics>
## Specific Ideas

- Log format for redacted proxy: `[PROXY:proxy.provider.com]` — host visible for debugging which provider is active, credentials stripped
- Session ID in proxy username: `{base_username}-session-{secrets.token_urlsafe(9)}` — 12-char suffix, unique per download job
- Retry prepend: `attempts = ["", *cookies] if (proxy_enabled and proxy_url) else (cookies or [""])` — clean one-liner that preserves backward compatibility when proxy is disabled

</specifics>

<deferred>
## Deferred Ideas

- Automated proxy test endpoint (GET /proxy-config/test) → if useful, could be added to Phase 21 UI work
- Separate bgutil Docker sidecar service → not needed; inline plugin mode chosen
- Webshare free-tier validation → skipped; going directly to IPRoyal production

</deferred>

---

*Phase: 20-proxy-download-infrastructure*
*Context gathered: 2026-05-14*
