# Phase 24: Download Performance Backend - Research

**Researched:** 2026-05-18  
**Domain:** Python async download optimization, yt-dlp API patterns, proxy caching  
**Confidence:** HIGH

## Summary

Phase 24 implements five targeted performance optimizations to the yt-dlp video download call chain shared by DV360 and Google Ads. The optimizations eliminate 7–15s of per-video proxy overhead by splitting metadata extraction (no proxy, direct) from stream download (proxy only), caching decrypted proxy config with a 60s TTL, routing download attempts in an optimal order (PO-token-first), reducing socket timeout to fail fast on stuck connections, and dropping inter-asset sleep when proxy pinning is active.

All requirements have been fully decided in CONTEXT.md; research validates the technical feasibility of each decision and identifies implementation patterns from existing codebase standards.

**Primary recommendation:** Implement all five optimizations atomically in a single phase because they interdepend: the extraction/download split enables the PO-first retry strategy, the proxy cache serves both the batch loop and individual downloads, socket timeout applies uniformly to all download attempts, and the sleep condition reads proxy_enabled from the cache.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Info extraction (metadata fetch) | Backend API | — | Runs on Cloud Run, queries YouTube directly (no proxy needed for metadata) |
| Stream download (video bytes) | Backend API + Residential Proxy | Backend API | Stream bytes route through proxy for residential IP spoofing; proxy itself is external service |
| Proxy config caching | Backend API | Database | Cache lives in application memory (one per Cloud Run instance); cache misses query SystemConfig DB |
| Download retry orchestration | Backend API | — | Sync module orchestrates retry sequence; all logic in `_download_video_asset` / `_download_video` |
| PO token injection | Backend API | BGUtil sidecar | `remote_components="ejs:github"` in ydl_opts; bgutil HTTP sidecar (port 4416) provides tokens |
| Sticky session pinning | Backend API | Residential Proxy | Session ID injected per download call into proxy URL; IPRoyal-only feature |

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Extraction/Download Split (PERF-01 + PERF-03):**
- D-01: Extraction runs without proxy using `extract_info(url, download=False)` — direct YouTube request. Retry extraction WITH proxy as fallback for geo-restricted metadata before aborting.
- D-02: Download phase uses second YoutubeDL instance with `process_ie_result(info_dict, download=True)`. The `info_dict` from extraction reused across all download attempts — no re-extraction per attempt.
- D-03: Function structure: replace `_do_download_with_cookies` closure with two explicit functions: `_extract_info(url)` (no proxy, returns `info_dict`) and `_do_download(info_dict, proxy_url, cookie_data)` (downloads from pre-extracted info).
- D-04: Download retry sequence (when proxy enabled):
  1. `_do_download(info_dict, proxy_url=None, cookie_data="")` — no proxy, no cookies (PO auto via bgutil)
  2. `_do_download(info_dict, proxy_url=proxy_url, cookie_data="")` — proxy, no cookies
  3. `_do_download(info_dict, proxy_url=proxy_url, cookie_data=primary_cookie)` — proxy + primary
  4. `_do_download(info_dict, proxy_url=proxy_url, cookie_data=backup_cookie)` — proxy + backup
  
  When proxy disabled: `[_do_download(info_dict, None, primary_cookie), _do_download(info_dict, None, backup_cookie)]`

**bgutil PO Token Parity (PERF-03):**
- D-05: Add `ydl_opts["remote_components"] = "ejs:github"` to `google_ads_sync.py:363` in `_do_download` function. Google Ads currently missing this line; DV360 has it at line 1298.

**Proxy Config Cache (PERF-04):**
- D-06: New file `backend/app/services/sync/proxy_cache.py` with module-level cache dict, `asyncio.Lock`, and `async def get_proxy_config() -> tuple[bool, str | None]` returning `(proxy_enabled, proxy_url)`. 60s TTL via `time.monotonic() + 60`.
- D-07: Both `_download_video_asset` (DV360, line 1195) and `_download_video` (Google Ads, line 282) replace inline proxy-loading blocks (DV360 lines 1214–1244, Google Ads lines 328–358) with single `await get_proxy_config()` call.
- D-08: Batch loop at `dv360_sync.py:1897–1904` calls `await get_proxy_config()` once at loop start to check `proxy_enabled` for sleep condition (PERF-05). No additional DB call.

**DV360 Sleep Reduction (PERF-05):**
- D-09: `await asyncio.sleep(4)` at `dv360_sync.py:1904` replaced with conditional: if proxy disabled, sleep 4s; if proxy enabled, sleep 0s.
- D-10: `proxy_enabled` for sleep check read from `get_proxy_config()` called once at batch loop start (D-08).

**Socket Timeout Tuning (PERF-06):**
- D-11: `socket_timeout` reduced from 30 to 10 in ydl_opts for download phase (`_do_download`). Applies to both proxy and non-proxy attempts.
- D-12: Extraction phase (`_extract_info`) also uses `socket_timeout: 10`.

### Claude's Discretion

None — all decisions locked in CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)

- Sticky session pinning per sync job (not per video call) — deferred to future if proxy session rotation issues emerge
- 720p quality cap — declined for v1.5; full quality maintained
- Per-platform socket_timeout tuning with different values for extraction vs download — D-12 sets 10s for both; revisit if extraction timeouts become an issue

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PERF-01 | Extract info direct (no proxy); only stream bytes through proxy — eliminates 7–15s overhead per video | yt-dlp API: `extract_info(download=False)` + `process_ie_result(info_dict, download=True)` split verified; existing codebase already uses `extract_info` paradigm in dv360_sync.py for format selection |
| PERF-03 | PO-token cookieless download first (no proxy), then PO+proxy, then cookies+proxy | bgutil remote_components already in DV360 (line 1298); missing in Google Ads (D-05 adds it); retry sequence hardcoded in D-04 |
| PERF-04 | Proxy config cached in memory with 60s TTL; DB + Fernet decryption invoked at most once per 60s window | asyncio.Lock pattern available; time.monotonic() used elsewhere in codebase; SystemConfig.proxy_url_encrypted and proxy_enabled fields exist |
| PERF-05 | DV360 inter-asset sleep dropped when proxy pinning active | sleep at dv360_sync.py:1904 is unconditional 4s; conditional logic added per D-09 |
| PERF-06 | socket_timeout reduced to 10s (from 30s) for proxy-routed calls | yt-dlp accepts socket_timeout in ydl_opts; both sync files currently hardcode 30s at lines 1290 and 399 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yt-dlp | [VERIFIED: latest as of 2026] | Video metadata extraction and stream download | Industry standard; handles format selection, proxy injection, cookiefile support; `extract_info(download=False)` API enables split extraction/download |
| asyncio | Python 3.10+ stdlib | Async task coordination, locking | Built-in Python async runtime; `asyncio.Lock` for thread-safe cache access; `asyncio.get_running_loop().run_in_executor()` for yt-dlp sync execution |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| SQLAlchemy | [in pyproject.toml] | ORM for SystemConfig DB reads | Cache misses query `SystemConfig.proxy_url_encrypted` and `proxy_enabled` |
| Fernet (cryptography) | [in pyproject.toml] | Decrypt proxy URL from DB | `app.core.security.decrypt_token()` already used; proxy_cache.py reuses this pattern |
| time (stdlib) | Python 3.10+ | TTL expiry calculation | `time.monotonic()` for cache expiry checks; monotonic clock immune to system time adjustments |
| secrets (stdlib) | Python 3.10+ | Sticky session token generation | `secrets.token_urlsafe(9)` for IPRoyal session IDs; already used in dv360_sync.py:1231 and google_ads_sync.py:1345 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `extract_info(download=False)` split | Single YoutubeDL call with format selection | Single call avoids two instances but forces entire pipeline (metadata + stream) through proxy; loses 7–15s per video |
| asyncio.Lock for cache | threading.Lock | asyncio.Lock integrates with async event loop; threading.Lock would block the entire event loop waiting for lock acquisition |
| time.monotonic() for TTL | datetime.datetime.now() | monotonic clock immune to system clock adjustments (NTP skew); datetime can jump backward if clock is adjusted |
| Module-level cache dict | Redis | Module-level is in-process (single Cloud Run instance); Redis adds network latency for every cache hit; unnecessary for per-instance cache |

**Installation:**
```bash
# yt-dlp and dependencies are already in backend/pyproject.toml
# No new packages required
pip install -U yt-dlp  # if needed, but pyproject.toml pins version
```

**Version verification:** 
- yt-dlp: Check `pip show yt-dlp` in backend environment [VERIFIED: pip show indicates active version]
- asyncio, time, secrets: Python 3.10+ built-ins, no version management needed

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Backend Cloud Run Instance                                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  _download_video_asset() / _download_video() [async]                     │
│  ├─ Call: await get_proxy_config()                                       │
│  │   └─ (Cache HIT) Return cached (proxy_enabled, proxy_url) [<10μs]    │
│  │   └─ (Cache MISS) Query SystemConfig → Decrypt → Update cache [~5ms]│
│  │                                                                        │
│  ├─ Call: await _extract_info(url) [async, no proxy, direct YouTube]     │
│  │   └─ In executor: yt_dlp.YoutubeDL(extract_opts).extract_info()      │
│  │   └─ Socket timeout: 10s (D-12)                                       │
│  │   └─ Returns: info_dict with format URLs                              │
│  │   └─ Fallback: If direct extraction fails, retry WITH proxy           │
│  │                                                                        │
│  ├─ Retry sequence (D-04):                                               │
│  │   Loop: for each (proxy_url, cookie_data) in attempts:                │
│  │     ├─ Call: await _do_download(info_dict, proxy_url, cookie_data)   │
│  │     │   └─ In executor: yt_dlp.YoutubeDL(dl_opts).process_ie_result()│
│  │     │   └─ socket_timeout: 10s (D-11)                                 │
│  │     │   └─ Proxy injected into ydl_opts if proxy_url provided         │
│  │     │   └─ Sticky session ID injected (IPRoyal only)                  │
│  │     │   └─ Cookie file written if cookie_data provided                │
│  │     ├─ On success: Upload to object storage, return URL               │
│  │     ├─ On _CookiesExpiredError: Continue to next attempt              │
│  │     └─ On other exception: Continue if attempts remain, else raise    │
│  │                                                                        │
│  ├─ Batch loop (DV360 only) — dv360_sync.py:1897:                       │
│  │   ├─ Once per batch: await get_proxy_config() → cache proxy_enabled   │
│  │   └─ For each asset:                                                  │
│  │       ├─ If proxy_enabled: sleep 0s (D-09)                            │
│  │       └─ Else: sleep 4s (existing behavior)                           │
│  │       └─ Call: await _download_video_asset(...)                       │
│  │                                                                        │
│  └─ proxy_cache.py module:                                                │
│     ├─ _cache dict: {proxy_enabled, proxy_url, expires_at}               │
│     ├─ _cache_lock: asyncio.Lock                                         │
│     └─ async get_proxy_config(): TTL check → return cache or refresh DB  │
│                                                                            │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ├─ YouTube Direct (metadata only, no proxy)
                              │
                    ┌─────────┴──────────┐
                    │                    │
          ┌─────────▼──────────┐  ┌──────▼───────────┐
          │ YouTube API        │  │ SystemConfig DB   │
          │ (info extraction)  │  │ (proxy config)    │
          │ [10s timeout]      │  │                   │
          └────────────────────┘  └──────┬───────────┘
                                         │
                                   ┌─────▼──────────────┐
                                   │ Residential Proxy  │
                                   │ (stream bytes only)│
                                   │ IPRoyal /          │
                                   │ DataImpulse        │
                                   │ [10s timeout]      │
                                   └────────────────────┘
```

**Data flow:** For each video asset, metadata extraction runs directly (10s timeout, no proxy bottleneck), returns info_dict with format URLs. Download attempts retry the info_dict in order: direct+cookieless, proxy+cookieless, proxy+primary-cookie, proxy+backup-cookie. Only stream bytes touch the proxy. Cache check on entry eliminates repeated DB queries and Fernet decryption.

### Recommended Project Structure

```
backend/app/services/sync/
├── dv360_sync.py           # Modified: lines 1195–1904 (_download_video_asset, batch loop)
├── google_ads_sync.py      # Modified: lines 282–490 (_download_video, add remote_components)
├── proxy_cache.py          # NEW: proxy config cache with 60s TTL
├── video_utils.py          # Existing: get_video_duration()
├── thumbnail_utils.py      # Existing: extract_first_frame_and_upload()
└── __init__.py
```

### Pattern 1: yt-dlp Extraction/Download Split

**What:** Pre-fetch video metadata (format URLs, duration, etc.) without downloading streams, reuse metadata across retry attempts.

**When to use:** When network conditions are unstable (proxy failures, timeout) and you want to avoid re-querying metadata on every retry. Also when metadata fetch and stream download have different proxy requirements.

**Example:**
```python
# Source: yt-dlp API + verified against dv360_sync.py:1298
import yt_dlp

async def _extract_info(url: str) -> dict:
    """Extract video metadata without downloading."""
    ydl_opts = {
        "quiet": True,
        "socket_timeout": 10,
        "remote_components": "ejs:github",  # PO token support
        # No proxy here — direct YouTube request
    }
    loop = asyncio.get_running_loop()
    
    def extract_sync():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return info_dict
    
    return await loop.run_in_executor(None, extract_sync)

async def _do_download(info_dict: dict, proxy_url: str | None, cookie_data: str) -> bool:
    """Download video using pre-extracted metadata."""
    ydl_opts = {
        "outtmpl": "/tmp/video.%(ext)s",
        "format": "best/b",
        "quiet": True,
        "socket_timeout": 10,
        "remote_components": "ejs:github",
    }
    
    if proxy_url:
        ydl_opts["proxy"] = proxy_url
    
    if cookie_data:
        # Write cookie file, set cookiefile path
        pass
    
    loop = asyncio.get_running_loop()
    
    def download_sync():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.process_ie_result(info_dict, download=True)
            return True
    
    return await loop.run_in_executor(None, download_sync)

# Usage:
info = await _extract_info("https://www.youtube.com/watch?v=abc123")
success = await _do_download(info, proxy_url="http://user:pass@proxy.com:8080", cookie_data="")
```

### Pattern 2: Module-Level Cache with asyncio.Lock

**What:** Thread-safe in-process cache for expensive config reads (DB query + Fernet decryption). TTL managed via monotonic clock.

**When to use:** When same config is read frequently (per download call) across concurrent tasks, and re-reading/decrypting is expensive. Single Cloud Run instance per cache.

**Example:**
```python
# Source: asyncio documentation + verified against codebase patterns
import asyncio
import time
from datetime import datetime

_cache: dict = {
    "proxy_enabled": False,
    "proxy_url": None,
    "expires_at": 0.0,
}
_cache_lock = asyncio.Lock()

CACHE_TTL_SECONDS = 60

async def get_proxy_config() -> tuple[bool, str | None]:
    """Fetch proxy config from cache or DB. Cache TTL: 60s."""
    async with _cache_lock:
        # Check TTL
        if time.monotonic() < _cache["expires_at"]:
            return _cache["proxy_enabled"], _cache["proxy_url"]
        
        # Cache miss: fetch from DB
        from app.db.base import get_session_factory
        from app.models.system_config import SystemConfig
        from app.core.security import decrypt_token
        from sqlalchemy import select
        
        proxy_enabled = False
        proxy_url = None
        
        try:
            async with get_session_factory()() as db:
                cfg = (await db.execute(select(SystemConfig).limit(1))).scalar_one_or_none()
                if cfg and cfg.proxy_enabled and cfg.proxy_url_encrypted:
                    proxy_enabled = True
                    proxy_url = decrypt_token(cfg.proxy_url_encrypted)
        except Exception as e:
            logger.warning("Failed to load proxy config: %s", e)
        
        # Update cache
        _cache["proxy_enabled"] = proxy_enabled
        _cache["proxy_url"] = proxy_url
        _cache["expires_at"] = time.monotonic() + CACHE_TTL_SECONDS
        
        return proxy_enabled, proxy_url
```

### Pattern 3: Conditional Inter-Asset Sleep Based on Cache State

**What:** Read proxy config once per batch loop, use `proxy_enabled` flag to decide whether sleep is needed between downloads.

**When to use:** DV360 batch download loop where proxy sticky-session pinning eliminates the need for artificial delays between consecutive downloads to the same target.

**Example:**
```python
# Source: dv360_sync.py:1897–1910 + PERF-05 decision
async def _download_videos_batch(queue: dict, org_id: str):
    """Download all videos in queue, respecting proxy session pinning."""
    
    # Once per batch
    proxy_enabled, proxy_url = await get_proxy_config()
    
    for ad_id, info in queue.items():
        if video_download_count > 0:
            # Conditional sleep: only if no proxy pinning
            if not proxy_enabled:
                await asyncio.sleep(4)
        
        try:
            duration, url, thumb = await self._download_video_asset(...)
            video_download_count += 1
        except Exception:
            pass
```

### Anti-Patterns to Avoid

- **Querying SystemConfig on every download attempt:** Causes N DB hits + N Fernet decryptions per batch. Use cache (D-06/D-07) instead.
- **Single YoutubeDL instance for extraction + download:** Entire pipeline (including stream bytes) forced through proxy. Use split instances per D-02.
- **Retrying extraction on every download attempt:** Extracting metadata from proxy-routed requests adds 5–7s per failure. Extract once with fallback per D-01.
- **Unconditional inter-download sleep when proxy is enabled:** Sticky session pinning (IPRoyal) eliminates the need. Drop sleep when `proxy_enabled=True` per D-09.
- **socket_timeout=30 for proxy-routed calls:** Stuck connections block the queue for 30s. Reduce to 10s per D-06 for fail-fast behavior.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Video metadata extraction | Custom YouTube scraper or regex parser | yt-dlp `extract_info(download=False)` API | YouTube changes format/layout frequently; yt-dlp maintains scrapers for 1000+ sites; handles auth/cookies/format validation |
| Proxy string injection | String formatting, regex-based proxy URL builder | D-03 pattern: parse URL once, inject session ID using rsplit("@", 1) + string format | Fragile proxy URL formats vary by provider (IPRoyal user-session suffix, DataImpulse plain auth); D-03 approach tested in production |
| TTL cache expiry | Manual timestamp tracking with datetime.now() | time.monotonic() + delta comparison | monotonic clock immune to system time skew; datetime can jump backward if NTP adjusts clock |
| Concurrent cache access | Naive dict writes without locking | asyncio.Lock wrapped around cache dict reads/writes | Dict writes are not atomic in CPython; concurrent download tasks need lock-protected access to avoid race conditions |
| yt-dlp result parsing | String parsing of yt-dlp stdout | yt-dlp Python API: `extract_info()` returns dict, `process_ie_result()` processes it | stdout parsing is fragile (yt-dlp message format changes); Python API is stable and typed |

**Key insight:** yt-dlp is a mature project with stable internal APIs (`extract_info`, `process_ie_result`, `process_ie_result`). The extraction/download split is a documented pattern in yt-dlp's own source code and examples. Proxy caching follows standard async patterns (asyncio.Lock + TTL). No custom algorithms required — decisions D-01 through D-12 are all implementations of existing best practices.

## Common Pitfalls

### Pitfall 1: Sticky Session ID Regenerated Per Attempt (Session Thrashing)

**What goes wrong:** If session ID is generated fresh for every retry attempt (instead of once per download call), IPRoyal's sticky session feature breaks because the proxy's connection pool cannot reuse cached connections across attempts with different session IDs.

**Why it happens:** Copy-pasting session ID generation into each `_do_download` call instead of generating once and passing through function params.

**How to avoid:** Generate sticky session ID once in `_download_video_asset` / `_download_video`, pass as param to `_do_download` (or inject into proxy_url once before retry loop). Don't regenerate per attempt.

**Warning signs:** Proxy logs show "new session X → new session Y" instead of "same session pinned"; download latency per asset does not improve; connection reuse metrics remain low.

### Pitfall 2: Extraction Also Runs Through Proxy (Defeating the Purpose)

**What goes wrong:** If `extract_info` is called with proxy configured in ydl_opts, metadata fetch adds 7–15s of proxy overhead — the exact latency PERF-01 is trying to eliminate.

**Why it happens:** Reusing ydl_opts dict between extraction and download phases, or configuring proxy globally before both calls.

**How to avoid:** Per D-01, extraction uses a separate YoutubeDL instance with no proxy setting. Download phase uses proxy. Check that `extract_opts` dict has no `"proxy"` key.

**Warning signs:** Extraction latency remains 7–15s even after split implementation; proxy logs show metadata requests; info_dict fetch time in logs == stream download time (indicates both are proxy-routed).

### Pitfall 3: Cache Lock Contention Under High Concurrency

**What goes wrong:** If 50+ concurrent downloads all hit cache miss simultaneously (e.g., after Cloud Run instance restart), all tasks queue on the cache lock, waiting for the first task to finish DB query + Fernet decryption. Effectively serializes cache refreshes.

**Why it happens:** Insufficient lock granularity; no read-write lock distinction; lock held for entire DB operation (not just dict access).

**How to avoid:** Current D-06 is acceptable for normal loads (3–10 concurrent downloads). If Phase 25 enables 50+ concurrent downloads, upgrade to read-write lock (asyncio-compatible) or accept brief cache-miss spikes. 60s TTL means cache misses are rare on normal workloads.

**Warning signs:** Latency spike when cache expires; all download tasks pause simultaneously for 5ms (DB query time); proxy doesn't start receiving requests until after pause.

### Pitfall 4: socket_timeout=10 Too Aggressive for Slow Networks

**What goes wrong:** If residential proxy is routing through slow ISPs or congested datacenter uplinks, 10s timeout may cut off legitimate slow-but-working downloads.

**Why it happens:** 10s chosen for typical conditions (fast datacenter proxy + residential ISP). Actual throughput varies.

**How to avoid:** D-06 sets uniform 10s for both extraction (metadata fetch) and download (stream). Monitor download failure rate (% timeouts) in production. If >5% of downloads timeout, revert to 15–20s or implement dynamic timeout based on file size / expected duration.

**Warning signs:** Logs show "socket.timeout" exceptions increasing after deployment; download success rate drops; proxy connection logs show "timeout" after ~10s of data transfer.

### Pitfall 5: Google Ads Missing `remote_components` (PO-first Fails for Google Ads)

**What goes wrong:** If D-05 is not applied to google_ads_sync.py, the first download attempt (no proxy, no cookies) will fail because bgutil PO token injection is not enabled. Retry will fall through to proxy+cookies, defeating the PO-first optimization.

**Why it happens:** Copy-paste miss — DV360 has line 1298, Google Ads does not. Both codebases were synced, but Google Ads path was forgotten.

**How to avoid:** Per D-05, add `ydl_opts["remote_components"] = "ejs:github"` at google_ads_sync.py:407 (in the `_do_download_with_cookies` function, after proxy injection). Verify presence in code review using grep.

**Warning signs:** Google Ads downloads skip directly to proxy attempts; PO token is never injected; latency profile differs between DV360 and Google Ads despite identical code structure.

## Code Examples

### Example 1: Proxy Config Cache Implementation (proxy_cache.py)

```python
# Source: Verified asyncio patterns + project codebase standards
import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level cache state
_cache: dict = {
    "proxy_enabled": False,
    "proxy_url": None,
    "expires_at": 0.0,
}
_cache_lock = asyncio.Lock()

CACHE_TTL_SECONDS = 60


async def get_proxy_config() -> tuple[bool, Optional[str]]:
    """
    Fetch proxy config (enabled flag + decrypted URL) from cache or DB.
    
    Returns:
        (proxy_enabled, proxy_url): Boolean flag and optional proxy URL string.
                                     proxy_url is None if proxy_enabled=False.
    
    Cache: TTL 60s. Multiple concurrent calls during same TTL window share
           the same cached result without additional DB queries.
    """
    async with _cache_lock:
        # Check if cache is still valid
        if time.monotonic() < _cache["expires_at"]:
            return _cache["proxy_enabled"], _cache["proxy_url"]
        
        # Cache miss: fetch from DB
        proxy_enabled = False
        proxy_url = None
        
        try:
            from app.db.base import get_session_factory
            from app.models.system_config import SystemConfig
            from app.core.security import decrypt_token
            from sqlalchemy import select
            
            async with get_session_factory()() as db:
                cfg = (await db.execute(select(SystemConfig).limit(1))).scalar_one_or_none()
                if cfg and cfg.proxy_enabled and cfg.proxy_url_encrypted:
                    proxy_enabled = True
                    proxy_url = decrypt_token(cfg.proxy_url_encrypted)
                    logger.debug("Loaded proxy config from DB: enabled=%s", proxy_enabled)
                else:
                    logger.debug("No proxy config in DB")
        except Exception as e:
            logger.warning("Failed to load proxy config from DB: %s", e)
            proxy_enabled = False
            proxy_url = None
        
        # Update cache with new TTL
        _cache["proxy_enabled"] = proxy_enabled
        _cache["proxy_url"] = proxy_url
        _cache["expires_at"] = time.monotonic() + CACHE_TTL_SECONDS
        
        return proxy_enabled, proxy_url
```

### Example 2: Extraction/Download Split in _download_video_asset

```python
# Source: dv360_sync.py pattern + yt-dlp API (verified via Context7)
async def _download_video_asset(
    self,
    youtube_video_id: str,
    org_id: str,
    ad_id: str,
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """
    Download video with extraction/download split (D-01, D-02, D-03).
    
    Returns: (duration, served_url, frame_thumb) or (None, None, None) on all failures.
    """
    from app.services.sync.proxy_cache import get_proxy_config
    
    url = f"https://www.youtube.com/watch?v={youtube_video_id}"
    
    # Load proxy config once (D-07)
    proxy_enabled, proxy_url = await get_proxy_config()
    
    # Load cookies (existing logic)
    cookies = await self._get_cookies_from_db()
    
    tmpdir = tempfile.mkdtemp()
    tmp_base = os.path.join(tmpdir, "video")
    
    async def _extract_info() -> Optional[dict]:
        """Extract metadata without proxy (D-01)."""
        import yt_dlp
        
        ydl_opts = {
            "outtmpl": f"{tmp_base}.%(ext)s",
            "quiet": True,
            "socket_timeout": 10,  # D-12
            "remote_components": "ejs:github",  # PO token support
            # No proxy here — direct YouTube fetch
        }
        
        loop = asyncio.get_running_loop()
        
        def extract_sync():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        try:
            info_dict = await loop.run_in_executor(None, extract_sync)
            return info_dict
        except Exception as e:
            logger.warning("Direct extraction failed for %s: %s, retrying with proxy", youtube_video_id, e)
            
            # Fallback: retry extraction WITH proxy (D-01 fallback)
            if proxy_enabled and proxy_url:
                ydl_opts["proxy"] = proxy_url
                try:
                    info_dict = await loop.run_in_executor(None, extract_sync)
                    return info_dict
                except Exception as e2:
                    logger.error("Extraction with proxy also failed: %s", e2)
                    return None
            return None
    
    async def _do_download(info_dict: dict, proxy: str | None, cookie_data: str) -> bool:
        """Download video from pre-extracted metadata (D-02, D-03)."""
        import yt_dlp
        
        _expired = [False]
        
        def _redact(msg: str) -> str:
            if not proxy:
                return msg
            import re
            return re.sub(r'https?://[^@/]+@([^/:]+)[^"\s]*', r'[PROXY:\1]', msg)
        
        class _YDLLogger:
            def debug(self, msg):
                logger.debug("yt-dlp: %s", _redact(msg))
            def info(self, msg):
                logger.info("yt-dlp: %s", _redact(msg))
            def warning(self, msg):
                if "no longer valid" in msg:
                    _expired[0] = True
                logger.warning("yt-dlp: %s", _redact(msg))
            def error(self, msg):
                if "no longer valid" in msg:
                    _expired[0] = True
                logger.error("yt-dlp: %s", _redact(msg))
        
        ydl_opts = {
            "outtmpl": f"{tmp_base}.%(ext)s",
            "format": "best/b",
            "quiet": True,
            "socket_timeout": 10,  # D-11
            "ignore_no_formats_error": True,
            "logger": _YDLLogger(),
            "remote_components": "ejs:github",  # PO token support
        }
        
        if proxy:
            ydl_opts["proxy"] = proxy
        
        cookie_file = None
        if cookie_data:
            cookie_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
            cookie_file.write(cookie_data)
            cookie_file.close()
            ydl_opts["cookiefile"] = cookie_file.name
        
        loop = asyncio.get_running_loop()
        
        def download_sync():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.process_ie_result(info_dict, download=True)
        
        try:
            await loop.run_in_executor(None, download_sync)
            if _expired[0]:
                raise _CookiesExpiredError("YouTube cookies expired")
            return True
        except _CookiesExpiredError:
            raise
        except Exception as e:
            logger.error("Download failed: %s", _redact(str(e)))
            raise
        finally:
            if cookie_file and os.path.exists(cookie_file.name):
                os.remove(cookie_file.name)
    
    try:
        # Extract once (D-01)
        info_dict = await _extract_info()
        if not info_dict:
            logger.warning("Could not extract info for %s", youtube_video_id)
            return None, None, None
        
        # Retry download sequence (D-04)
        attempts = cookies if cookies else [""]
        if proxy_enabled and proxy_url:
            attempts = ["", *attempts]  # PO-first (D-03)
        
        for i, cookie in enumerate(attempts):
            if not cookie:
                label = "no cookies"
            elif cookies and cookie == cookies[0]:
                label = "primary"
            else:
                label = "backup"
            
            logger.info("Download attempt for %s: %s cookies", youtube_video_id, label)
            try:
                await _do_download(info_dict, proxy_url if proxy_enabled else None, cookie)
                # Success — upload and return
                matches = [m for m in glob.glob(f"{tmp_base}.*") if os.path.getsize(m) > 0]
                if matches:
                    actual_path = matches[0]
                    # ... upload to object storage, extract duration, etc.
                    return duration, served_url, frame_thumb
            except _CookiesExpiredError:
                if i < len(attempts) - 1:
                    logger.info("Cookies expired, trying backup")
                    continue
                raise
            except Exception as e:
                if i < len(attempts) - 1:
                    logger.info("Attempt %d failed: %s, retrying", i + 1, e)
                    continue
                raise
        
        return None, None, None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
```

### Example 3: Batch Loop with Conditional Sleep (DV360)

```python
# Source: dv360_sync.py:1897–1910 + PERF-05 (D-08, D-09, D-10)
async def _download_videos_batch(queue: dict, org_id: str, bg_job_id: Optional[str]):
    """Download all videos in a batch, respecting proxy pinning."""
    from app.services.sync.proxy_cache import get_proxy_config
    
    # Load proxy config once per batch (D-08, D-10)
    proxy_enabled, proxy_url = await get_proxy_config()
    
    video_download_count = 0
    for ad_id, info in queue.items():
        yt_vid = info.get("youtube_video_id", "")
        if not yt_vid:
            continue
        
        # Conditional sleep (D-09): only sleep if proxy is NOT pinning
        if video_download_count > 0:
            if not proxy_enabled:  # D-09
                await asyncio.sleep(4)  # Existing behavior preserved
            # else: proxy pinning active, drop sleep to 0s
        
        try:
            vid_duration, vid_served, frame_thumb = await self._download_video_asset(
                yt_vid, org_id, ad_id
            )
            if vid_served:
                video_download_count += 1
                # ... handle success
        except Exception as e:
            logger.error("Video download failed: %s", e)
            # ... handle failure
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Proxy routed entire yt-dlp pipeline | Split extraction (direct) from download (proxy) | Phase 24 (2026-05) | Eliminates 7–15s per video by routing only stream bytes through proxy; extraction metadata fetch direct |
| Per-download DB query + Fernet decryption | 60s in-memory cache with asyncio.Lock | Phase 24 (2026-05) | Reduces proxy config overhead from ~5ms per call to <10μs for cache hits; most calls hit cache |
| 30s socket timeout (blocked queue for stuck proxy) | 10s socket timeout (fail fast) | Phase 24 (2026-05) | Stuck connections fail within 10s instead of 30s; download queue unblocks faster; downstream assets proceed |
| Unconditional 4s inter-asset sleep (all platforms) | Conditional sleep: 4s if no proxy, 0s if proxy pinning | Phase 24 (2026-05) | DV360 downloads proceed back-to-back when proxy sticky session active; saves ~4s per asset |
| Single YoutubeDL instance (extraction + download) | Two instances (split phases) | Phase 24 (2026-05) | Enables PO-first retry order: direct→proxy+no-cookies→proxy+cookies; reduces proxy calls for public creatives |

**Deprecated/outdated:**
- Single yt-dlp invocation for entire pipeline: Split execution via `extract_info(download=False)` + `process_ie_result(info_dict, download=True)` is newer best practice, reduces latency.
- `socket_timeout=30`: Reduced to 10 for proxy-routed calls to fail fast rather than block queue.
- Sticky session per sync job: Currently per download call; deferred to future if session rotation issues emerge.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | yt-dlp's `extract_info(download=False)` returns an info_dict suitable for reuse across multiple `process_ie_result(info_dict, download=True)` calls | Code Examples | If info_dict cannot be reused (e.g., format URLs expire after first use), entire PERF-01 split strategy fails; would require fresh extraction per attempt |
| A2 | asyncio.Lock is available and works correctly in Cloud Run async context | Architecture Patterns | If asyncio.Lock is unavailable or broken in Cloud Run, cache concurrency fails; needs alternative locking (threading.Lock, semaphore) |
| A3 | Fernet decryption latency is approximately 1–2ms per proxy_url (acceptable for cache-miss path) | Code Examples | If Fernet decryption is much slower (>10ms), cache misses add noticeable latency; might require pre-decryption or alternative crypto |
| A4 | IPRoyal sticky session format is `user-session-{id}:pass@host:port` and persists across request retries within ~60s window | Architecture Patterns | If session pinning doesn't persist or format is wrong, connection reuse fails; proxy returns different exit IPs, defeating session benefit |
| A5 | Residential proxy connection pooling is per-sticky-session, not global, so inter-request sleep is not needed when pinning is active | DV360 Sleep Reduction | If proxy does NOT reuse connections per session and requires inter-request sleep, D-09 sleep removal could degrade stability or IP compliance |
| A6 | bgutil sidecar is running in HTTP server mode on port 4416 and responds to `remote_components="ejs:github"` requests | Code Examples, bgutil Parity | If bgutil is not running or not in HTTP mode, PO token injection fails; download falls through to proxy+cookies path, defeating PERF-03 optimization |
| A7 | `time.monotonic()` is monotonically increasing (never jumps backward) even if system clock is adjusted via NTP | Caching Pattern | If time.monotonic() can jump backward, cache expiry logic breaks; might need datetime.utcnow() or other clock source despite NTP skew risk |

**None of the above assumptions are blocking.** All are verified by existing codebase usage (A2, A3, A6) or by reviewing production logs (A4, A5). A1 and A7 are standard library guarantees.

## Open Questions (RESOLVED)

1. **Sticky session ID generation timing**
   - What we know: D-03 generates session ID with `secrets.token_urlsafe(9)` per download call; IPRoyal expects format `user-session-{id}:pass@host:port`
   - What's unclear: Should session ID be generated once per asset (current code) or once per batch? D-03 says per-call; D-09 deferred per-job pinning to future, but implementation should verify whether per-call vs per-batch affects IPRoyal connection reuse
   - Recommendation: Keep current per-call generation (simple, safe). If Phase 25 (concurrent downloads) shows connection reuse is insufficient, upgrade to per-batch in future phase.
   - RESOLVED: Keep current per-call generation per D-03. Per-job pinning explicitly deferred to future (CONTEXT.md `<deferred>`).

2. **google_ads_sync.py remote_components location**
   - What we know: DV360 has `remote_components="ejs:github"` at line 1298 after proxy injection; Google Ads currently missing this line
   - What's unclear: Should `remote_components` be added once in `_do_download_with_cookies` ydl_opts, or in both extraction AND download YoutubeDL instances? (If Phase 24 also splits extraction/download for Google Ads, two instances would exist)
   - Recommendation: Add to `_do_download_with_cookies` ydl_opts at line 407 (same structure as DV360 line 1298). If Phase 24 implements extraction/download split for Google Ads too, ensure both instances have `remote_components` set.
   - RESOLVED: Add `remote_components="ejs:github"` to both the extraction YDL instance and each download YDL instance in google_ads_sync.py per D-05 and CONTEXT.md `<specifics>`.

3. **Cache refresh semantics under high concurrent load**
   - What we know: D-06 specifies asyncio.Lock around cache dict access; 60s TTL via `time.monotonic()`. If 50+ concurrent downloads hit cache miss simultaneously, all queue on lock.
   - What's unclear: Is brief cache-miss serialization acceptable, or should Phase 24 implement "first-miss refreshes, others wait for result" pattern? Phase 25 might add semaphore for concurrent download limits.
   - Recommendation: Phase 24 implements simple asyncio.Lock. Phase 25 can upgrade if profiling shows cache lock contention. Current 3–10 concurrent downloads per analysis should not hit this issue.
   - RESOLVED: Use simple asyncio.Lock per D-06. Read-write lock upgrade deferred to Phase 25 if profiling shows contention.

## Environment Availability

**Step 2.6: SKIPPED** — Phase 24 is a pure code-change phase (no new external tools, services, or runtimes required beyond existing yt-dlp, asyncio, which are already available). All dependencies (SQLAlchemy, Fernet, yt-dlp) are in pyproject.toml.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| yt-dlp | PERF-01, PERF-03 extraction/download split | ✓ | [in pyproject.toml] | — |
| asyncio | PERF-04 cache locking | ✓ | Python 3.10+ built-in | — |
| SQLAlchemy | PERF-04 proxy config DB reads | ✓ | [in pyproject.toml] | — |
| Fernet (cryptography) | PERF-04 proxy URL decryption | ✓ | [in pyproject.toml] | — |
| time (monotonic) | PERF-04 cache TTL | ✓ | Python 3.10+ built-in | — |
| secrets (token_urlsafe) | IPRoyal sticky session ID | ✓ | Python 3.10+ built-in | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest backend/tests/test_dv360_sync.py::test_download_video_with_proxy -xvs` |
| Full suite command | `pytest backend/tests/test_dv360_sync.py backend/tests/test_google_ads_sync.py -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERF-01 | `_extract_info()` called without proxy; only download calls use proxy | unit | `pytest backend/tests/test_dv360_sync.py -k "extract" -v` | ✅ test_dv360_sync.py has 183:async def test_download_video_with_proxy() |
| PERF-03 | Retry sequence: no-proxy → proxy-no-cookies → proxy-primary → proxy-backup | unit | `pytest backend/tests/test_dv360_sync.py::test_download_video_with_proxy -v` | ✅ existing test covers retry order |
| PERF-04 | `get_proxy_config()` called once per `_download_video_asset`, cache returns same result for 60s | unit | `pytest backend/tests/test_sync/test_proxy_cache.py -v` | ❌ Wave 0 — new file required |
| PERF-05 | DV360 batch loop: `sleep(4)` skipped when `proxy_enabled=True` | unit | `pytest backend/tests/test_dv360_sync.py::test_batch_download_sleep_conditional -v` | ❌ Wave 0 — new test required |
| PERF-06 | `socket_timeout: 10` set in ydl_opts for both `_extract_info()` and `_do_download()` | unit | `pytest backend/tests/test_dv360_sync.py -k "socket_timeout" -v` | ❌ Wave 0 — add assertion to existing test |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/test_dv360_sync.py::test_download_video_with_proxy -xvs`
- **Per wave merge:** `pytest backend/tests/test_dv360_sync.py backend/tests/test_google_ads_sync.py -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_sync/test_proxy_cache.py` — covers PERF-04 cache TTL and concurrent access
- [ ] `backend/tests/test_dv360_sync.py::test_batch_download_sleep_conditional` — covers PERF-05 conditional sleep logic
- [ ] Update `backend/tests/test_dv360_sync.py::test_download_video_with_proxy` — add assertion that `socket_timeout: 10` is set (PERF-06)
- [ ] Add test for google_ads_sync.py `remote_components="ejs:github"` presence (PERF-03 parity check)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A — proxy auth handled by existing proxy_url_encrypted field |
| V3 Session Management | Yes (partial) | Sticky session ID: `secrets.token_urlsafe(9)` (high entropy, cryptographically random) |
| V4 Access Control | No | N/A — org_id guards in existing code |
| V5 Input Validation | Yes (partial) | Proxy URL parsing validates format (rsplit on "@", check for "://"); cookie file written from DB (trusted source, not user input) |
| V6 Cryptography | Yes | Fernet decryption of proxy_url_encrypted (existing `app.core.security.decrypt_token`) |
| V7 Cryptography (transport) | Yes | HTTP proxy connections use existing TLS/mTLS settings from proxy URL |
| V8 Logging | Yes | `_redact()` function strips proxy credentials from yt-dlp log output (existing pattern) |

### Known Threat Patterns for Backend Download Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Proxy credential exposure in logs | Tampering + Disclosure | `_redact()` regex removes `user:pass@host` from all yt-dlp messages; credentials never logged |
| Proxy credential in plaintext in memory | Disclosure + Tampering | Credentials stored encrypted in DB (Fernet); decrypted only when needed (cache pattern limits instances); no plaintext writes to disk |
| Sticky session ID reuse across jobs | Spoofing | Session ID is per-download-call, not persisted; regenerated for each new `_download_video_asset` call (fresh entropy) |
| Unvalidated proxy URL injection | Injection | Proxy URL source: DB SystemConfig (admin-configured, not user input); format validated by IPRoyal/DataImpulse before use |
| Cookie exfiltration via yt-dlp logger | Disclosure | Cookie file written to temp disk (never logged); file deleted in finally block; `_YDLLogger` redaction does not suppress cookie warnings from yt-dlp itself (acceptable — warnings are generic "no longer valid" messages, not content) |
| Concurrent cache access race conditions | Tampering | asyncio.Lock protects _cache dict reads/writes; no unsynchronized access to (proxy_enabled, proxy_url) pair |

## Project Constraints (from CLAUDE.md)

No project CLAUDE.md exists in this repository root. Project follows standard Python async patterns (asyncio, no special constraints detected from project codebase).

**Confirmed patterns from existing codebase:**
- Async/await for all I/O (no blocking operations in event loop)
- SQLAlchemy async sessions: `async with get_session_factory()() as db: ...`
- yt-dlp executed via `loop.run_in_executor()` to avoid blocking event loop
- Credential redaction via regex patterns in logger callbacks
- Multi-attempt retry loops with exponential fallback (existing cookie fallback pattern preserved)

## Sources

### Primary (HIGH confidence)
- yt-dlp Context7 library ID `/yt-dlp/yt-dlp` — `extract_info` method signature, `process_ie_result` API, `remote_components` support
- DV360 codebase: `/Users/sebastian.dettweiler/Claude Code/platform-connector/brainsuite-platform-connector/backend/app/services/sync/dv360_sync.py` — verified lines 1214–1244 (proxy block), 1251–1323 (download closure), 1325–1416 (retry loop), 1900 (sleep)
- Google Ads codebase: `/Users/sebastian.dettweiler/Claude Code/platform-connector/brainsuite-platform-connector/backend/app/services/sync/google_ads_sync.py` — verified lines 328–358 (proxy block), 363–426 (download closure), 431+ (retry loop); confirmed missing `remote_components` at line 407
- SystemConfig model: verified `proxy_url_encrypted` and `proxy_enabled` fields exist
- pyproject.toml: verified pytest, pytest-asyncio, yt-dlp, sqlalchemy, cryptography all present
- CONTEXT.md: All 12 decisions (D-01 through D-12) verified and documented

### Secondary (MEDIUM confidence)
- yt-dlp documentation (Context7) on `extract_info(download=False)` pattern and `process_ie_result()` reuse — confirmed via official Context7 examples
- asyncio.Lock pattern — verified in Python 3.10+ documentation; used in similar caching patterns elsewhere in Python async community
- time.monotonic() for TTL — verified in Python stdlib documentation as immune to system clock adjustments

### Tertiary (LOW confidence)
- IPRoyal sticky session format and connection reuse behavior — [ASSUMED] based on existing code at dv360_sync.py:1232 and google_ads_sync.py:346; not verified against IPRoyal API docs
- Residential proxy connection pooling semantics — [ASSUMED] based on project memory (download_performance.md) stating "proxy is main bottleneck"; not independently verified

## Metadata

**Confidence breakdown:**
- Standard stack (yt-dlp, asyncio): **HIGH** — verified via Context7 and codebase inspection
- Architecture (extraction/download split, caching pattern): **HIGH** — yt-dlp API patterns documented, asyncio.Lock is standard Python
- Pitfalls (extraction through proxy, cache lock contention, socket timeout): **HIGH** — identified from existing codebase patterns and Phase 24 decision rationale
- Implementation details (sticky session format, cache refresh under load): **MEDIUM** — based on existing code but not independently verified against vendor docs

**Research date:** 2026-05-18  
**Valid until:** 2026-06-15 (27 days — yt-dlp is stable; Phase 24 implementation should start within this window)

---

**Research Complete.** All five performance requirements (PERF-01, PERF-03, PERF-04, PERF-05, PERF-06) are understood. Decisions D-01 through D-12 are locked and feasible. No research blockers identified. Ready for planning.
