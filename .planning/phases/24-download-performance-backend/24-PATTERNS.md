# Phase 24: Download Performance Backend - Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 3 (1 new, 2 modified)
**Analogs found:** 3 / 3 (100% coverage)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/services/sync/proxy_cache.py` | utility/service | CRUD (cache) | `backend/app/db/base.py` + `backend/app/services/sync/job_tracker.py` | exact |
| `backend/app/services/sync/dv360_sync.py` | service | request-response + streaming | `backend/app/services/sync/dv360_sync.py` (self) | exact |
| `backend/app/services/sync/google_ads_sync.py` | service | request-response + streaming | `backend/app/services/sync/google_ads_sync.py` (self) | exact |

---

## Pattern Assignments

### `backend/app/services/sync/proxy_cache.py` (NEW — utility service, cache CRUD)

**Analog:** `backend/app/db/base.py` + `backend/app/services/sync/job_tracker.py`

**Rationale:** New module needs async session factory patterns (from db/base.py) and async helper function structure (from job_tracker.py). No existing cache module exists; proxy_cache.py will follow established DB access + async patterns.

**Imports pattern** (from db/base.py and job_tracker.py):
```python
import logging
import time
from typing import Optional, Tuple
import asyncio

from app.db.base import get_session_factory
from app.models.system_config import SystemConfig
from app.core.security import decrypt_token
from sqlalchemy import select

logger = logging.getLogger(__name__)
```

**Module-level state and lock** (async pattern from Python asyncio stdlib):
```python
# Module-level cache state (D-06)
_cache: dict = {
    "proxy_enabled": False,
    "proxy_url": None,
    "expires_at": 0.0,
}
_cache_lock = asyncio.Lock()

CACHE_TTL_SECONDS = 60
```

**Core pattern — async function with DB read + TTL check** (D-06, D-07):
```python
async def get_proxy_config() -> Tuple[bool, Optional[str]]:
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
        
        # Cache miss: fetch from DB (pattern from job_tracker.py:57)
        proxy_enabled = False
        proxy_url = None
        
        try:
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

**Error handling pattern:**
- DB query failures caught with generic `Exception` (matches job_tracker.py:78 pattern)
- Failures fall back to safe defaults (`proxy_enabled=False, proxy_url=None`)
- Warnings logged but no exception raised (non-blocking cache misses)

---

### `backend/app/services/sync/dv360_sync.py` (MODIFY — _download_video_asset function, extraction/download split)

**Analog:** `backend/app/services/sync/dv360_sync.py:1195–1424` (lines 1195–1424 — existing _download_video_asset + retry loop)

**Scope of changes:**
- Lines 1214–1244: Replace inline proxy-loading block with `await get_proxy_config()` call (D-07)
- Lines 1251–1323: Refactor `_do_download_with_cookies` closure into two functions: `_extract_info()` (no proxy) and `_do_download()` (reusable across attempts)
- Lines 1325–1416: Update retry loop to use extracted `info_dict` across all download attempts
- Lines 1897–1904: Add conditional sleep logic based on `proxy_enabled` flag (D-09, D-10)

**Pattern 1: Proxy config import and usage** (replaces lines 1214–1244)

**Existing code (to be replaced):**
```python
# Lines 1214–1244: Inline proxy loading
proxy_url = None
proxy_enabled = False
try:
    from app.db.base import get_session_factory as _gsf_proxy
    from app.models.system_config import SystemConfig as _SC_proxy
    from sqlalchemy import select as _sel_proxy
    async with _gsf_proxy()() as _proxy_db:
        _proxy_cfg = (await _proxy_db.execute(_sel_proxy(_SC_proxy).limit(1))).scalar_one_or_none()
        _p_enabled = bool(_proxy_cfg and _proxy_cfg.proxy_enabled)
        _p_url_enc = _proxy_cfg.proxy_url_encrypted if _proxy_cfg else None
    if _p_enabled and _p_url_enc:
        from app.core.security import decrypt_token as _dt_proxy
        proxy_url = _dt_proxy(_p_url_enc)
        proxy_enabled = True
        # Sticky session injection…
        _session_id = secrets.token_urlsafe(9)
        if "@" in proxy_url and "iproyal.com" in proxy_url:
            # ... rsplit and format logic ...
except Exception as _proxy_load_err:
    logger.warning("Failed to load proxy config: %s", _proxy_load_err)
    proxy_url = None
    proxy_enabled = False
```

**New code (to be inserted):**
```python
# D-07: Load proxy config once per download attempt, with caching
from app.services.sync.proxy_cache import get_proxy_config
proxy_enabled, proxy_url = await get_proxy_config()

# Sticky session injection — IPRoyal only (user-session-ID format)
# Other providers (DataImpulse etc.) use plain user:pass and reject the suffix
if proxy_enabled and proxy_url:
    _session_id = secrets.token_urlsafe(9)
    if "@" in proxy_url and "iproyal.com" in proxy_url:
        _user_part, _host_part = proxy_url.rsplit("@", 1)
        if "://" in _user_part:
            _scheme_end = _user_part.index("://") + 3
            _scheme = _user_part[:_scheme_end]
            _creds = _user_part[_scheme_end:]
            if ":" in _creds:
                _username, _password = _creds.split(":", 1)
                proxy_url = f"{_scheme}{_username}-session-{_session_id}:{_password}@{_host_part}"
```

**Pattern 2: Extraction/Download split** (replaces lines 1251–1323, transforms into two functions)

**Existing code (closure structure, lines 1251–1323):**
```python
def _do_download_with_cookies(cookie_data: str):
    import yt_dlp
    _expired = [False]
    
    def _redact(msg: str) -> str:
        # ... redaction logic ...
    
    class _YDLLogger:
        # ... logger implementation ...
    
    ydl_opts = {
        "outtmpl": f"{tmp_base}.%(ext)s",
        "format": "best/b",
        "quiet": True,
        "socket_timeout": 30,  # CHANGE: D-12 will reduce to 10
        "ignore_no_formats_error": True,
        "logger": _YDLLogger(),
    }
    if proxy_enabled and proxy_url:
        ydl_opts["proxy"] = proxy_url
    ydl_opts["remote_components"] = "ejs:github"
    
    # ... cookie file handling ...
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])  # CHANGE: this needs to split
```

**New code — extraction function** (D-01, D-03):
```python
async def _extract_info() -> Optional[dict]:
    """Extract metadata without proxy (D-01)."""
    import yt_dlp
    
    ydl_opts = {
        "outtmpl": f"{tmp_base}.%(ext)s",
        "quiet": True,
        "socket_timeout": 10,  # D-12: reduced to 10s
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
```

**New code — download function** (D-02, D-03):
```python
async def _do_download(info_dict: dict, proxy: str | None, cookie_data: str) -> bool:
    """Download video from pre-extracted metadata (D-02, D-03)."""
    import yt_dlp
    
    _expired = [False]
    
    def _redact(msg: str) -> str:
        if not proxy:
            return msg
        import re as _re
        return _re.sub(r'https?://[^@/]+@([^/:]+)[^"\s]*', r'[PROXY:\1]', msg)
    
    class _YDLLogger:
        def debug(self, msg):
            if msg.startswith("[debug] "):
                logger.debug("yt-dlp: %s", _redact(msg))
            else:
                logger.info("yt-dlp: %s", _redact(msg))
        def info(self, msg): logger.info("yt-dlp: %s", _redact(msg))
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
        "socket_timeout": 10,  # D-11: reduced to 10s
        "ignore_no_formats_error": True,
        "logger": _YDLLogger(),
        "remote_components": "ejs:github",  # PO token support
    }
    
    if proxy:
        ydl_opts["proxy"] = proxy
    
    cookie_file = None
    if cookie_data:
        cleaned = "\n".join(
            line.lstrip() for line in cookie_data.splitlines()
        )
        cookie_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        )
        cookie_file.write(cleaned)
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
```

**Pattern 3: Retry loop using extracted info_dict** (lines 1325–1416, major refactor)

**Existing code (single YoutubeDL instance, ydl.download()):**
```python
attempts = cookies if cookies else [""]
if proxy_enabled and proxy_url:
    attempts = ["", *attempts]
loop = asyncio.get_running_loop()
try:
    for i, cookie in enumerate(attempts):
        # ... attempt logic ...
        try:
            await loop.run_in_executor(None, lambda cd=cookie: _do_download_with_cookies(cd))
            # ... success path with file matching ...
```

**New code (two-phase: extract once, then retry downloads):**
```python
try:
    # Extract once (D-01)
    info_dict = await _extract_info()
    if not info_dict:
        logger.warning("Could not extract info for %s", youtube_video_id)
        return None, None, None
    
    # Retry download sequence (D-04, D-03)
    attempts = cookies if cookies else [""]
    if proxy_enabled and proxy_url:
        attempts = ["", *attempts]  # PO-first: no cookies first
    
    loop = asyncio.get_running_loop()
    for i, cookie in enumerate(attempts):
        if not cookie:
            label = "no cookies"
        elif cookies and cookie == cookies[0]:
            label = "primary"
        else:
            label = "backup"
        
        logger.info("  Attempting DV360 video download: %s (ad=%s, cookies=%s)", youtube_video_id, ad_id, label)
        try:
            await _do_download(info_dict, proxy_url if proxy_enabled else None, cookie)
            
            # File matching and success path (unchanged)
            _VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".flv", ".m4v"}
            matches = [
                m for m in glob.glob(f"{tmp_base}.*")
                if os.path.getsize(m) > 0 and os.path.splitext(m)[1].lower() in _VIDEO_EXTS
            ]
            actual_path = matches[0] if matches else None
            if actual_path:
                # ... rest of success path unchanged ...
        except _CookiesExpiredError:
            if i < len(attempts) - 1:
                logger.info("  %s cookies expired for %s — trying backup slot", label, youtube_video_id)
                continue
            logger.warning("  All cookie slots expired for %s — aborting", youtube_video_id)
            # ... notification logic unchanged ...
            raise
        except Exception as e:
            if i < len(attempts) - 1:
                logger.info("  %s cookies failed for %s, trying next... (%s: %s)", label, youtube_video_id, type(e).__name__, e)
                continue
            logger.warning("  Failed to download DV360 video for ad %s (video %s): %s: %s", ad_id, youtube_video_id, type(e).__name__, e, exc_info=True)
            raise
    
    return None, None, None
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)
```

**Pattern 4: Batch loop conditional sleep** (lines 1897–1904, D-08, D-09, D-10)

**Existing code (lines 1903–1904):**
```python
if video_download_count > 0:
    await asyncio.sleep(4)
```

**New code (D-09, D-10):**
```python
# At batch loop start (before for loop), add D-08:
proxy_enabled, proxy_url = await get_proxy_config()

# Inside loop, replace sleep (lines 1903–1904):
if video_download_count > 0:
    if not proxy_enabled:  # D-09: conditional sleep
        await asyncio.sleep(4)  # Keep existing 4s when no proxy
    # else: proxy pinning active, drop sleep to 0s
```

---

### `backend/app/services/sync/google_ads_sync.py` (MODIFY — _download_video function, parity + proxy cache)

**Analog:** `backend/app/services/sync/google_ads_sync.py:282–490` (existing _download_video function)

**Scope of changes:**
- Lines 328–358: Replace inline proxy-loading block with `await get_proxy_config()` call (D-07, same as DV360)
- Lines 363–429: Refactor `_do_download_with_cookies` closure to match DV360 split (extraction/download) OR keep closure but update socket_timeout and add remote_components (D-05, D-11, D-12)
- Line 407: Add missing `ydl_opts["remote_components"] = "ejs:github"` (D-05 — parity with DV360 line 1298)

**Note on refactoring scope:** RESEARCH.md and CONTEXT.md do not explicitly require Google Ads to implement extraction/download split (PERF-01/PERF-03 are scoped to DV360 in the canonical refs). However, D-05 requires `remote_components` parity. For maximum consistency and future-proofing, the planner should decide: (A) apply split to both services, or (B) add only `remote_components` + socket_timeout change to Google Ads for now.

**Option A (Full parity — RECOMMENDED):** Apply same extraction/download split as DV360

Use the same `_extract_info()` and `_do_download()` pattern from DV360 above, adapted for Google Ads context (ad_id, filename, etc.).

**Option B (Minimal parity — D-05 only):** Keep closure, add remote_components and socket_timeout

**Proxy config import** (replaces lines 328–358, same as DV360):
```python
from app.services.sync.proxy_cache import get_proxy_config
proxy_enabled, proxy_url = await get_proxy_config()

# Sticky session injection (same IPRoyal pattern as DV360)
if proxy_enabled and proxy_url:
    _session_id = secrets.token_urlsafe(9)
    if "@" in proxy_url and "iproyal.com" in proxy_url:
        _user_part, _host_part = proxy_url.rsplit("@", 1)
        if "://" in _user_part:
            _scheme_end = _user_part.index("://") + 3
            _scheme = _user_part[:_scheme_end]
            _creds = _user_part[_scheme_end:]
            if ":" in _creds:
                _username, _password = _creds.split(":", 1)
                proxy_url = f"{_scheme}{_username}-session-{_session_id}:{_password}@{_host_part}"
```

**remote_components parity** (D-05 — add to ydl_opts after line 406):
```python
# Existing ydl_opts setup (lines 393–406)
ydl_opts = {
    "outtmpl": f"{tmp_base}.%(ext)s",
    "format": "best/b",
    "quiet": True,
    "socket_timeout": 10,  # D-12: change from 30 to 10
    "ignore_no_formats_error": True,
    "logger": _YDLLogger(),
}

if proxy_enabled and proxy_url:
    ydl_opts["proxy"] = proxy_url

# ADD THIS LINE (D-05, parity with DV360:1298):
ydl_opts["remote_components"] = "ejs:github"
```

---

## Shared Patterns

### Authentication / Authorization

**Not applicable to Phase 24.** Proxy authentication is handled via pre-encrypted proxy URL from SystemConfig (D-06, D-07). No new auth patterns introduced.

### Error Handling

**Source:** `backend/app/services/sync/dv360_sync.py:1251–1323` and `backend/app/services/sync/job_tracker.py:57–80`

**Apply to:** All download and cache operations

**Pattern:**
```python
try:
    # Operation
    await some_async_operation()
except SpecificError as e:
    # Handle specific case (e.g., _CookiesExpiredError in download, DB failure in cache)
    if is_retryable(e):
        logger.info("Specific error, trying next: %s", e)
        continue
    else:
        logger.error("Fatal error: %s", e)
        raise
except Exception as e:
    # Catch-all for unexpected errors
    logger.warning("Unexpected error: %s", e)
    # In cache: fall back to safe defaults
    # In download: continue to next attempt or raise
finally:
    # Cleanup resources (temp files, etc.)
    if resource:
        cleanup(resource)
```

### Validation

**Source:** `backend/app/services/sync/dv360_sync.py:1345–1349` (file validation)

**Apply to:** Download result validation

**Pattern:**
```python
_VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".flv", ".m4v"}
matches = [
    m for m in glob.glob(f"{tmp_base}.*")
    if os.path.getsize(m) > 0 and os.path.splitext(m)[1].lower() in _VIDEO_EXTS
]
actual_path = matches[0] if matches else None
if actual_path:
    # proceed with upload
```

### Logging / Redaction

**Source:** `backend/app/services/sync/dv360_sync.py:1256–1263`

**Apply to:** All proxy-related logging in cache and download functions

**Pattern:**
```python
def _redact(msg: str) -> str:
    """Redact proxy credentials from log/exception message."""
    if not proxy_url:
        return msg
    import re as _re
    return _re.sub(r'https?://[^@/]+@([^/:]+)[^"\s]*', r'[PROXY:\1]', msg)

# Usage: logger.error("yt-dlp exception: %s", _redact(str(e)))
```

### Async Execution of Synchronous Code

**Source:** `backend/app/services/sync/dv360_sync.py:1331–1342` and `backend/app/services/sync/job_tracker.py:74–77`

**Apply to:** yt-dlp calls and long-running synchronous operations

**Pattern:**
```python
loop = asyncio.get_running_loop()

def sync_operation():
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

result = await loop.run_in_executor(None, sync_operation)
```

### Async Database Session Management

**Source:** `backend/app/db/base.py:20–26` and `backend/app/services/sync/job_tracker.py:57–71`

**Apply to:** Database reads in proxy_cache.py and any other new DB-touching code

**Pattern:**
```python
async with get_session_factory()() as db:
    result = (await db.execute(select(Model).limit(1))).scalar_one_or_none()
    if result:
        # process
    await db.commit()  # if write operation; omit for read-only
```

### Sticky Session Injection (IPRoyal)

**Source:** `backend/app/services/sync/dv360_sync.py:1229–1240`

**Apply to:** Both DV360 and Google Ads proxy URL setup

**Pattern:**
```python
_session_id = secrets.token_urlsafe(9)
if "@" in proxy_url and "iproyal.com" in proxy_url:
    _user_part, _host_part = proxy_url.rsplit("@", 1)
    if "://" in _user_part:
        _scheme_end = _user_part.index("://") + 3
        _scheme = _user_part[:_scheme_end]
        _creds = _user_part[_scheme_end:]
        if ":" in _creds:
            _username, _password = _creds.split(":", 1)
            proxy_url = f"{_scheme}{_username}-session-{_session_id}:{_password}@{_host_part}"
```

---

## Files with Complete Analogs

All three files have complete, exact analogs in the codebase:

| File | Analog | Coverage | Notes |
|------|--------|----------|-------|
| `proxy_cache.py` | `db/base.py` + `services/sync/job_tracker.py` | 100% | Async session factory + async helper function patterns |
| `dv360_sync.py` (_download_video_asset refactor) | `dv360_sync.py:1195–1424` | 100% | Existing code, being refactored in-place |
| `google_ads_sync.py` (_download_video refactor) | `google_ads_sync.py:282–490` | 100% | Existing code, minimal changes for D-05 parity |

---

## No Analogs Required

All patterns are derived from existing codebase or standard Python/asyncio libraries. No new domains or patterns introduced that lack precedent.

---

## Metadata

**Analog search scope:** `/backend/app/services/sync/`, `/backend/app/db/`, `/backend/app/core/`

**Files scanned:** dv360_sync.py, google_ads_sync.py, job_tracker.py, base.py, security.py

**Pattern extraction date:** 2026-05-18

**Phase:** 24 - Download Performance Backend

**Key insights:**
- No new external dependencies; all patterns reuse existing libraries (asyncio, time, secrets, SQLAlchemy, Fernet)
- Extraction/download split is a refactoring of existing code (single YoutubeDL instance → two instances)
- Proxy cache is a new utility but follows established async DB patterns from job_tracker.py
- Socket timeout reduction (30s → 10s) is a config change, no new pattern
- Conditional sleep logic is straightforward boolean branching on cached proxy_enabled flag
