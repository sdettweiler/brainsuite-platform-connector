---
phase: 20-proxy-download-infrastructure
reviewed: 2026-05-15T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - backend/app/services/sync/dv360_sync.py
  - backend/app/services/sync/google_ads_sync.py
  - backend/app/models/system_config.py
  - backend/alembic/versions/a9b1c2d3e5f6_add_proxy_config.py
  - backend/tests/test_dv360_sync.py
  - backend/tests/test_google_ads_sync.py
  - backend/tests/test_system_config.py
  - backend/tests/test_yt_dlp_plugin.py
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 20: Code Review Report

**Reviewed:** 2026-05-15T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 20 adds residential-proxy support (IPRoyal) to the DV360 and Google Ads yt-dlp download paths. The Alembic migration and `SystemConfig` ORM additions are correct. The proxy injection, session-ID stamping, and `_redact` helper are structurally sound. However, three correctness bugs were found that will cause wrong runtime behaviour, and several quality issues warrant attention.

---

## Critical Issues

### CR-01: `_proxy_cfg` accessed after its AsyncSession is closed — lazy-loaded attributes will raise

**File:** `backend/app/services/sync/google_ads_sync.py:319-321` (identical pattern at `dv360_sync.py:1167-1169`)

**Issue:** `_proxy_cfg` is fetched inside `async with _gsf_proxy()() as _proxy_db:` and the session is closed by the time the `if` block on the next line executes. SQLAlchemy lazy-loads `proxy_enabled` and `proxy_url_encrypted` on attribute access; with an expired/closed async session those accesses will raise `MissingGreenlet` or `DetachedInstanceError`. Under the broad `except Exception` the error is silently swallowed and `proxy_url` stays `None`, meaning the proxy is silently disabled every time.

```python
# Current (broken): session is closed before attributes are read
async with _gsf_proxy()() as _proxy_db:
    _proxy_cfg = (await _proxy_db.execute(...)).scalar_one_or_none()
# ← session closed here
if _proxy_cfg and _proxy_cfg.proxy_enabled ...:   # DetachedInstanceError on async session
```

**Fix:** Move the `if` block — and the decrypt call — inside the `async with` block, or eagerly read the required scalar values before the context manager exits:

```python
async with _gsf_proxy()() as _proxy_db:
    _proxy_cfg = (await _proxy_db.execute(_sel_proxy(_SC_proxy).limit(1))).scalar_one_or_none()
    _p_enabled = bool(_proxy_cfg and _proxy_cfg.proxy_enabled)
    _p_url_enc = _proxy_cfg.proxy_url_encrypted if _proxy_cfg else None

if _p_enabled and _p_url_enc:
    from app.core.security import decrypt_token as _dt_proxy
    proxy_url = _dt_proxy(_p_url_enc)
    proxy_enabled = True
    ...
```

Apply this fix in both `google_ads_sync.py` and `dv360_sync.py`.

---

### CR-02: `winning_slot` index mapping is wrong when proxy is enabled in `google_ads_sync._download_video`

**File:** `backend/app/services/sync/google_ads_sync.py:419-454`

**Issue:** When `proxy_enabled=True` the `attempts` list is `["", *cookies]`, so indices are:
- `0` → cookieless (no-cookie slot)
- `1` → primary cookie
- `2` → backup cookie

But the counter-reset logic on success uses `winning_slot == 0` to reset `youtube_cookies_runtime_expired` and `winning_slot == 1` to reset `youtube_cookies_backup_runtime_expired`. This is off by one: winning on the primary cookie (slot 1 when proxy enabled) incorrectly marks the backup as healthy, and winning on the backup (slot 2) does nothing at all.

```python
# Current (wrong when proxy_enabled):
if winning_slot == 0:
    _upd_vals["youtube_cookies_runtime_expired"] = False    # slot 0 is cookieless, not primary
elif winning_slot == 1:
    _upd_vals["youtube_cookies_backup_runtime_expired"] = False  # slot 1 is primary, not backup
```

**Fix:** Track cookie slot independently of `attempts` index:

```python
winning_slot: int | None = None  # index into `cookies` list, not `attempts`

for i, cookie in enumerate(attempts):
    ...
    await loop.run_in_executor(None, lambda cd=cookie: _do_download_with_cookies(cd))
    # Determine which cookie slot won
    if cookie and cookies:
        winning_slot = cookies.index(cookie)  # 0 = primary, 1 = backup
    break

...
if winning_slot == 0:
    _upd_vals["youtube_cookies_runtime_expired"] = False
elif winning_slot == 1:
    _upd_vals["youtube_cookies_backup_runtime_expired"] = False
```

Note: `dv360_sync.py` uses `label` (a string) for the same decision and has the same semantic problem — the `label` for slot `i==0` when proxy is enabled is `"no cookies"`, so the `label == "primary"` branch never fires. See WR-01 for the DV360 variant.

---

### CR-03: `label` variable in `google_ads_sync._download_video` misclassifies the primary-cookie slot when proxy is enabled

**File:** `backend/app/services/sync/google_ads_sync.py:422`

**Issue:** The label is computed as:
```python
label = "no cookies" if not cookie else ("primary" if i == 0 else "backup")
```

When `proxy_enabled=True`, `attempts = ["", primary, backup]`. At `i=1` (primary cookie), `cookie` is truthy and `i != 0`, so `label` becomes `"backup"` — the log line says "backup" even though the primary cookie is being used. This is a log-accuracy issue, but it also directly causes CR-02 above if the DV360 variant follows the same `label`-based decision.

**Fix:**
```python
# Compute label based on cookie content / position in the cookies list, not attempts index
if not cookie:
    label = "no cookies"
elif cookies and cookie == cookies[0]:
    label = "primary"
else:
    label = "backup"
```

---

## Warnings

### WR-01: Same `winning_slot`/`label` mapping bug exists in `dv360_sync._download_video_asset`

**File:** `backend/app/services/sync/dv360_sync.py:1276-1299`

**Issue:** `dv360_sync` uses `label` (a string) rather than a numeric `winning_slot` to decide which `runtime_expired` flag to reset. When `proxy_enabled=True` the attempts list is `["", *cookies]` and `i==0` gets `label="no cookies"`. The primary cookie is at `i==1`; because `i != 0`, its label is `"backup"`. On success, `label == "primary"` branch never fires and `label == "backup"` branch fires for the primary cookie slot — the wrong flag is cleared. This mirrors CR-02 for DV360.

**Fix:** Same approach as CR-02: track slot by cookie content, not by `i`.

---

### WR-02: `asyncio.get_event_loop()` is deprecated in Python 3.10+ and raises in some environments

**File:** `backend/app/services/sync/google_ads_sync.py:418`
**File:** `backend/app/services/sync/dv360_sync.py:1274`

**Issue:** Both files call `loop = asyncio.get_event_loop()` and then `await loop.run_in_executor(...)`. In Python 3.10+ `get_event_loop()` emits a `DeprecationWarning` when called without a running loop and raises `RuntimeError` in 3.12 if there is no current event loop. The correct idiom in an `async` function is `asyncio.get_running_loop()`.

**Fix:**
```python
loop = asyncio.get_running_loop()
```

---

### WR-03: Proxy URL may contain credentials in the `_proxy_load_err` warning log

**File:** `backend/app/services/sync/google_ads_sync.py:336` and `dv360_sync.py:1185`

**Issue:** `_proxy_load_err` is logged directly via `logger.warning("Failed to load proxy config: %s", _proxy_load_err)`. If the exception is raised after `proxy_url` has been partially assembled (e.g., during session injection), the exception message may embed the raw URL including credentials. The `_redact` helper only runs inside `_do_download_with_cookies` and is not available at this point in the outer scope.

**Fix:** Apply a simple string replacement guard before logging, or wrap the entire proxy-loading block so any partial `proxy_url` is cleared immediately on exception (already done for `proxy_url`/`proxy_enabled`, but not for the exception message itself):
```python
except Exception as _proxy_load_err:
    safe_err = re.sub(r'https?://[^@/]+@([^/:]+)[^"\s]*', r'[PROXY:\1]', str(_proxy_load_err))
    logger.warning("Failed to load proxy config: %s", safe_err)
    proxy_url = None
    proxy_enabled = False
```

---

### WR-04: `test_retry_order_cookieless_first` in both test files will not reliably capture all YoutubeDL calls

**File:** `backend/tests/test_dv360_sync.py:260-265`
**File:** `backend/tests/test_google_ads_sync.py:117-123`

**Issue:** The mock `_capturing_ydl` raises `Exception("stop after capture")` on `ctx.download`. However `_do_download_with_cookies` is run inside `loop.run_in_executor` in a thread. After the first call raises, the outer retry loop continues and a second YoutubeDL instantiation may happen before the test inspects `attempt_cookies`. The test only asserts `attempt_cookies[0] == ""` but does not assert that exactly one attempt was made (or control the number). If `_capturing_ydl` is called synchronously (or if yt-dlp is not patched at the right scope), the assertion passes vacuously. The test structure is fragile and will silently pass even if cookieless-first is not implemented correctly if the first captured call happens to have no cookie.

**Fix:** Assert `len(attempt_cookies) == 1` after the try/except (verifying the call stops after the first attempt raises) and ensure `yt_dlp.YoutubeDL` is patched at the module path used by `_do_download_with_cookies` (inside `dv360_sync`/`google_ads_sync`), not globally.

---

### WR-05: `test_bgutil_plugin_loaded` test is an environment-dependency check, not a unit test — it will fail in CI without the package installed

**File:** `backend/tests/test_yt_dlp_plugin.py:5-16`

**Issue:** The test simply checks `importlib.util.find_spec("yt_dlp_plugins")`. If `bgutil-ytdlp-pot-provider` is not in the test environment's Python environment the test fails. There is no `pytest.importorskip`, no `@pytest.mark.optional`, and no fixture to conditionally skip. This will break CI unless the package is added to `requirements-test.txt` (which is not confirmed by any file in scope).

**Fix:** Either add `bgutil-ytdlp-pot-provider` to the test requirements, or gate with:
```python
pytest.importorskip("yt_dlp_plugins", reason="bgutil-ytdlp-pot-provider not installed")
```

---

## Info

### IN-01: Duplicate proxy-loading code between `dv360_sync` and `google_ads_sync` — no shared helper

**File:** `backend/app/services/sync/dv360_sync.py:1160-1187`
**File:** `backend/app/services/sync/google_ads_sync.py:313-338`

**Issue:** The proxy-loading block (DB read, decrypt, session-ID injection, URL reconstruction) is copy-pasted verbatim across both files. The two copies share all of the bugs above. Any future fix must be applied in two places.

**Fix:** Extract to a shared async helper, e.g. `backend/app/services/sync/proxy_utils.py`:
```python
async def load_proxy_url() -> tuple[bool, str | None]:
    """Returns (proxy_enabled, session-stamped proxy_url or None)."""
```

---

### IN-02: `_redact` regex does not cover HTTPS proxy URLs with a port on the host

**File:** `backend/app/services/sync/dv360_sync.py:1206`
**File:** `backend/app/services/sync/google_ads_sync.py:355`

**Issue:** The pattern `r'https?://[^@/]+@([^/:]+)[^"\s]*'` captures the hostname correctly but the `[^"\s]*` tail is greedy and stops at a `"` or whitespace. For a proxy URL like `http://user:pass@geo.iproyal.com:12321/path` the replacement produces `[PROXY:geo.iproyal.com]` which is correct. However for a URL embedded in a JSON log line such as `{"proxy": "http://user:pass@host:port"}`, the `"` stops the match at the `"` character before `:port`, which means `:port` leaks into the log after the redacted placeholder. This is a minor precision issue, not a full credential leak, but worth noting.

**Fix:** Use `[^\s"'<>]*` or simply replace the full match including the port:
```python
re.sub(r'https?://[^@]+@([^\s"\'<>:]+)(:\d+)?[^\s"\'<>]*', r'[PROXY:\1]', msg)
```

---

### IN-03: `remote_components` is not a recognised yt-dlp option and will be silently ignored

**File:** `backend/app/services/sync/dv360_sync.py:1235`
**File:** `backend/app/services/sync/google_ads_sync.py:383`

**Issue:** `"remote_components": {"ejs:github": True}` is set in `ydl_opts` in both files. This is not a documented yt-dlp configuration key. yt-dlp will silently ignore unknown keys, so this is harmless at runtime but is dead/incorrect configuration that pollutes the options dict and may confuse maintainers.

**Fix:** Remove the `remote_components` key or document the intent in a comment if this is an experimental feature toggle that was added intentionally.

---

_Reviewed: 2026-05-15T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
