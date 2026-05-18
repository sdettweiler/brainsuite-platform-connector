# Phase 24: Download Performance Backend - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Backend-only phase. Delivers 5 performance optimizations to the yt-dlp download call chain in `dv360_sync.py` and `google_ads_sync.py`:

1. **PERF-01**: Extraction/download split — `extract_info()` runs direct (no proxy); only stream bytes route through proxy
2. **PERF-03**: PO-first retry order — download attempts: no-proxy/no-cookies → proxy/no-cookies → proxy+primary-cookies → proxy+backup-cookies
3. **PERF-04**: Proxy config in-memory cache (60s TTL) in a new shared `proxy_cache.py`
4. **PERF-05**: DV360 inter-download sleep dropped to 0s when proxy is enabled
5. **PERF-06**: `socket_timeout` reduced to 10s for proxy-routed yt-dlp calls

**Also in scope:** Add `remote_components='ejs:github'` to `google_ads_sync.py` (bgutil PO token parity with DV360 — project rule: fix all platforms simultaneously).

**Not in scope:** DB migrations, frontend changes, new endpoints, semaphore concurrency (Phase 25), Alembic merge (Phase 26).

</domain>

<decisions>
## Implementation Decisions

### Extraction/Download Split (PERF-01 + PERF-03)

- **D-01:** Extraction runs without proxy using `extract_info(url, download=False)` — returns `info_dict` with format URLs. If direct extraction fails, retry extraction WITH proxy as fallback (handles geo-restricted metadata) before aborting.
- **D-02:** Download phase uses a second `YoutubeDL` instance with `process_ie_result(info_dict, download=True)`. The `info_dict` from extraction is reused across all download attempts — no re-extraction per attempt.
- **D-03:** Function structure: replace the current `_do_download_with_cookies` closure with two explicit functions:
  - `_extract_info(url)` — no proxy, returns `info_dict`
  - `_do_download(info_dict, proxy_url, cookie_data)` — downloads from pre-extracted info with explicit proxy and cookie params
- **D-04:** Download retry sequence (when proxy enabled):
  1. `_do_download(info_dict, proxy_url=None, cookie_data="")`  — no proxy, no cookies (PO auto via bgutil plugin)
  2. `_do_download(info_dict, proxy_url=proxy_url, cookie_data="")` — proxy, no cookies
  3. `_do_download(info_dict, proxy_url=proxy_url, cookie_data=primary_cookie)` — proxy + primary cookies
  4. `_do_download(info_dict, proxy_url=proxy_url, cookie_data=backup_cookie)` — proxy + backup cookies

  When proxy disabled: `[_do_download(info_dict, None, primary_cookie), _do_download(info_dict, None, backup_cookie)]` (existing behavior).

### bgutil PO Token Parity (Google Ads)

- **D-05:** Add `ydl_opts["remote_components"] = "ejs:github"` to `google_ads_sync.py`'s `_do_download` function — mirrors `dv360_sync.py:1298`. Required for PERF-03 PO-first retry to work correctly on the Google Ads path.

### Proxy Config Cache (PERF-04)

- **D-06:** New file: `backend/app/services/sync/proxy_cache.py`. Contains:
  - Module-level `_proxy_config_cache: dict` with `proxy_url`, `proxy_enabled`, `expires_at`
  - `asyncio.Lock` for concurrent access safety
  - `async def get_proxy_config() -> tuple[bool, str | None]` — returns `(proxy_enabled, proxy_url)` from cache or DB
  - 60s TTL: `expires_at = time.monotonic() + 60`
- **D-07:** Both `dv360_sync.py` and `google_ads_sync.py` replace their inline proxy-loading blocks with a single `await get_proxy_config()` call at the start of `_download_video_asset` / `_download_video`.
- **D-08:** The batch loop at `dv360_sync.py:1893` also calls `await get_proxy_config()` once at loop start to check `proxy_enabled` for the sleep condition (PERF-05).

### DV360 Sleep Reduction (PERF-05)

- **D-09:** `await asyncio.sleep(4)` at `dv360_sync.py:1900` is replaced with:
  ```python
  if not proxy_enabled:
      await asyncio.sleep(4)
  ```
  When proxy is enabled: sleep is 0s (dropped entirely). When proxy is disabled: existing 4s sleep preserved.
- **D-10:** `proxy_enabled` for the sleep check is read from `get_proxy_config()` called once at the start of the batch loop (D-08). No additional DB call.

### Socket Timeout Tuning (PERF-06)

- **D-11:** `socket_timeout` reduced from `30` to `10` in `ydl_opts` for the download phase (`_do_download` function). Applies to both proxy and non-proxy attempts.
- **D-12:** Extraction phase (`_extract_info`) also uses `socket_timeout: 10` — extraction is a metadata fetch, not a large stream read, so 10s is sufficient.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Core Download Files to Modify

- `backend/app/services/sync/dv360_sync.py` §`_download_video_asset` (line 1195) — current proxy-loading block (lines 1214–1244), `_do_download_with_cookies` closure (lines 1251–1323), retry loop (lines 1325–1416), and inter-download sleep at line 1900
- `backend/app/services/sync/google_ads_sync.py` §`_download_video` (line 282) — identical structure; proxy block (328–358), `_do_download_with_cookies` (363–426), retry loop (431 onwards); missing `remote_components` vs DV360

### New File to Create

- `backend/app/services/sync/proxy_cache.py` — new file; module-level shared cache with asyncio.Lock + get_proxy_config() (D-06). Phase 25 semaphore can live here too.

### Requirements

- `.planning/REQUIREMENTS.md` §PERF-01, PERF-03, PERF-04, PERF-05, PERF-06 — acceptance criteria
- `.planning/ROADMAP.md` §Phase 24 — 5 success criteria; SC-1 (proxy overhead eliminated), SC-2 (PO-first direct attempt), SC-3 (10s timeout), SC-4 (no inter-download sleep), SC-5 (60s cache)

### Related Architecture

- `backend/app/models/system_config.py` §SystemConfig — `proxy_url_encrypted`, `proxy_enabled` fields that the cache reads from
- `backend/app/core/security.py` §`decrypt_token` — used in cache loading to decrypt `proxy_url_encrypted`
- `backend/app/db/base.py` §`get_session_factory` — async session pattern used in cache DB read

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `_redact(msg)` closure in `dv360_sync.py:1256` — regex strips proxy credentials from log messages. Needs to be accessible from both `_extract_info` and `_do_download` functions. Move to module-level or pass `proxy_url` as param.
- `_CookiesExpiredError` at `dv360_sync.py:66` — custom exception for detecting expired cookies in yt-dlp logger callbacks. Preserved in new `_do_download` function.
- `_YDLLogger` class inside `_do_download_with_cookies` — captures `_expired[0]` state and redacts logs. Needs to stay scoped to each download attempt (closure over `_expired` flag).
- `get_video_duration()` import and usage at `dv360_sync.py:1348` — called on downloaded file path. Unchanged by this refactor.
- `secrets.token_urlsafe(9)` sticky session injection at `dv360_sync.py:1231` — generates per-call session ID for IPRoyal. Moves into `get_proxy_config()` or into `_do_download` to keep per-attempt session pinning.

### Established Patterns

- Session-per-operation: cache's DB read follows `async with get_session_factory()() as db:` pattern (same as all other SystemConfig reads)
- `asyncio.get_running_loop().run_in_executor(None, lambda: ...)` — yt-dlp is synchronous; kept in `_do_download` for thread pool execution
- `remote_components = "ejs:github"` in `ydl_opts` before `YoutubeDL(ydl_opts)` — must appear in BOTH the extraction YDL instance and the download YDL instance (PO tokens needed at both phases)
- Sticky session ID: per-download-call, not per-job. IPRoyal-only format (`user-session-{token}:pass@host:port`). Other providers use plain `user:pass` and reject the suffix.

### Integration Points

- `dv360_sync.py:1893–1916` — batch download loop: add `proxy_cfg = await get_proxy_config()` at loop start; use `proxy_cfg.proxy_enabled` for sleep condition (D-09/D-10)
- Both `_download_video_asset` (DV360) and `_download_video` (Google Ads) — replace inline proxy-loading with `await get_proxy_config()`; then call `_extract_info` + retry loop with `_do_download`

</code_context>

<specifics>
## Specific Ideas

- `proxy_cache.py` cache structure:
  ```python
  _cache: dict = {"proxy_enabled": False, "proxy_url": None, "expires_at": 0.0}
  _cache_lock = asyncio.Lock()

  async def get_proxy_config() -> tuple[bool, str | None]:
      async with _cache_lock:
          if time.monotonic() < _cache["expires_at"]:
              return _cache["proxy_enabled"], _cache["proxy_url"]
          # load from DB, decrypt, inject sticky session, update _cache
  ```
- Sticky session injection moves into `get_proxy_config()` so the cached `proxy_url` already has `-session-{id}` embedded. But note: sticky sessions are per-download-call, so the cache should store the base proxy URL, and sticky session suffix is injected by the caller per download attempt. Researcher/planner should clarify this.
- `_do_download` signature: `def _do_download(info_dict, proxy_url: str | None, cookie_data: str, *, tmp_base: str, redact_fn)` — receives pre-extracted info, explicit proxy URL (None = no proxy), cookie string, and the redact closure.
- `remote_components = "ejs:github"` must be set on BOTH the extraction YDL instance (no-proxy) and each download YDL instance. Bgutil PO tokens are needed during info extraction format URL validation AND during stream download.

</specifics>

<deferred>
## Deferred Ideas

- Sticky session pinning per sync job (not per video call) — the current code generates a fresh session ID per `_download_video_asset` call. True job-level session pinning would require passing the session ID through the call chain. Deferred to future if proxy session rotation issues emerge.
- 720p quality cap (`"format": "bestvideo[height<=720]+bestaudio/best[height<=720]"`) — declined for v1.5; full quality maintained.
- Per-platform socket_timeout tuning (extraction vs download phases with different values) — D-12 sets 10s for both; revisit if extraction timeouts become an issue.

</deferred>

---

*Phase: 24-download-performance-backend*
*Context gathered: 2026-05-18*
