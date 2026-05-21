# Download Pipeline Fixes — Handoff Plan
> Created: 2026-05-21 | Status: Ready to implement next session

## Context

Downloads are working (DataImpulse confirms 1–5MB video transfers). However there are 5 issues to fix:

1. Sequential backfill (main perf issue)
2. Logging noise / missing success logs
3. NoneType crash on auto-resume
4. Wrong harmonizer method call in DV360 retry
5. OOM / double-registration noise

---

## Bug Inventory

### BUG-1 — NoneType crash on auto-resume (CRITICAL)
**File**: `backend/app/services/sync/scheduler.py:2210`
**Symptom**: After OOM kill, `auto_resume_interrupted_jobs` re-dispatches backfill jobs. Backfill jobs have `params=None` (created without params). `trigger_download_retry` calls `params.get("platform")` → `AttributeError: 'NoneType' object has no attribute 'get'`.
**Fix**:
```python
async def trigger_download_retry(params: dict, job_id: str) -> None:
    # ADD THIS AT THE TOP:
    if not params:
        logger.warning("trigger_download_retry: job %s has no params — skipping (backfill jobs are not retryable)", job_id)
        if job_uuid := (_uuid.UUID(str(job_id)) if job_id else None):
            await update_background_job(job_uuid, status="FAILED", error={"type": "MissingParams", "message": "Backfill download jobs cannot be auto-retried (no stored params)", "traceback": ""})
        return
```
Also add to `auto_resume_interrupted_jobs` filter (scheduler.py ~line 2024) to exclude JSONB null params jobs:
```python
_func.jsonb_typeof(_BJ.params).notin_(["null"]),  # exclude JSON null (backfill jobs)
```
Import: `from sqlalchemy import func as _func` is already imported.

### BUG-2 — Wrong harmonizer method in DV360 sync retry (HIGH)
**File**: `backend/app/services/sync/scheduler.py:2345`
**Symptom**: `'HarmonizationService' object has no attribute 'harmonize'` — method is `harmonize_connection`.
**Current code**:
```python
await harmonizer.harmonize(db, conn2, sj2)
```
**Fix**: Replace with correct call pattern used everywhere else:
```python
from datetime import date as _date
await harmonizer.harmonize_connection(db, conn2, date_from, date_to)
```
Note: `date_from` and `date_to` are already in scope in `trigger_dv360_sync_retry`.

### BUG-3 — Sequential backfill loop (PERF — main issue)
**File**: `backend/app/services/sync/scheduler.py:2565–2581` (`backfill_missing_downloads_for_connection._run()`)
**Symptom**: Downloads one video at a time, ~88s each. 50 videos = ~73 minutes.
**Current code**:
```python
async def _run():
    downloaded = []
    for i, asset in enumerate(missing):
        ok = await _download_asset_for_backfill(asset)
        ...
        await update_background_job(bg_job_id, progress_current=i + 1)
```
**Fix**: Replace with bounded concurrency gather:
```python
async def _run():
    from app.services.sync.proxy_cache import get_concurrency_semaphore
    sem = await get_concurrency_semaphore()
    downloaded = []
    failed = []
    lock = asyncio.Lock()
    progress = [0]

    async def _do_one(asset):
        async with sem:
            ok = False
            try:
                ok = await _download_asset_for_backfill(asset)
            except _CookiesExpiredError:
                async with lock:
                    await update_background_job(bg_job_id, status="FAILED", progress_current=progress[0],
                        error={"type": "CookiesExpiredError", "message": "YouTube cookies expired", "traceback": ""})
                raise
            except Exception as exc:
                logger.warning("backfill: asset %s failed: %s", asset.id, exc)
            async with lock:
                if ok:
                    downloaded.append({"asset_id": str(asset.id), "ad_id": asset.ad_id})
                progress[0] += 1
                await update_background_job(bg_job_id, progress_current=progress[0])

    try:
        await asyncio.gather(*[_do_one(a) for a in missing])
    except _CookiesExpiredError:
        return
    await update_background_job(bg_job_id, status="COMPLETE", progress_current=len(missing),
        output={"downloaded": downloaded})
```

### BUG-4 — OOM (INFRA)
**Symptom**: Memory 1086MB vs 1024MB limit → container killed → triggers BUG-1 loop.
**Fix**: Raise Cloud Run memory to 2048MB:
```
gcloud run services update brainsuite-backend --memory=2048Mi --region=us-central1 --project=PROJECT_ID
```
Also consider reducing default concurrency semaphore from 10 to 5 in `proxy_cache.py` (line 109):
```python
"semaphore": asyncio.Semaphore(5),  # was 10
"max_concurrent": 5,
```
This halves peak memory usage from concurrent downloads.

### BUG-5 — Double-registration noise (AssertionError: BgUtilHTTP already registered)
**File**: `backend/app/services/sync/dv360_sync.py:1303` (same in `google_ads_sync.py`)
**Symptom**: `remote_components: ["ejs:github"]` causes yt-dlp to re-register BgUtilHTTP (already registered by pip package) → logged as ERROR but non-fatal.
**Fix**: The `remote_components` is needed for n-challenge solving. The double-registration is truly non-fatal. To suppress the log noise, wrap the yt-dlp import section or downgrade the log — actually the cleanest fix is to NOT log this at all since it comes from yt-dlp's own logger, not ours. We can suppress it per-call by adding a logging filter, but this is low priority. **Defer until after other bugs fixed.**

---

## Logging Redesign (Items 2–4)

### Goal: replace per-attempt noise with clean per-video outcome lines

**Current behavior**: All yt-dlp output forwarded at matching severity → 10+ lines per video.
**Target**:
```
WARN [dv360_sync] [DL:Ok4X-Qyl5mc] attempt 1/3 (no cookies): format error — continuing
WARN [dv360_sync] [DL:Ok4X-Qyl5mc] attempt 2/3 (proxy+primary): cookies-invalid warning — download succeeded (file on disk)
WARN [dv360_sync] [DL:Ok4X-Qyl5mc] COMPLETE: vid_dv360_... (4.2 MB, primary cookies)
```

**Changes needed** in both `dv360_sync.py` and `google_ads_sync.py`:

**A) Suppress yt-dlp intermediate noise in `_YDLLogger`**: Change `_YDLLogger.warning()` and `_YDLLogger.error()` to buffer output and only emit on final failure:
```python
class _YDLLogger:
    def __init__(self):
        self._warnings = []
        self._errors = []
    def debug(self, msg):
        if msg.startswith("[debug] "):
            pass  # drop debug entirely
        # else drop too — too noisy
    def info(self, msg):
        pass  # drop all yt-dlp info
    def warning(self, msg):
        if "no longer valid" in msg:
            _expired[0] = True
        self._warnings.append(msg)  # buffer, don't emit
    def error(self, msg):
        if "no longer valid" in msg:
            _expired[0] = True
        self._errors.append(msg)  # buffer, don't emit
    def flush_on_failure(self):
        for w in self._warnings:
            logger.warning("yt-dlp: %s", _redact(w))
        for e in self._errors:
            logger.error("yt-dlp: %s", _redact(e))
```

Note: `_expired` needs to be accessible to the logger. Pass it in via closure or make it a list attribute on the logger instance.

**B) Emit clean outcome lines at WARNING level** in `_download_video_asset`:
- On attempt start: `logger.warning("[DL:%s] attempt %d/%d (%s)", _dl_tag, i+1, len(attempts), label)`
- On attempt success: `logger.warning("[DL:%s] COMPLETE: %s (%.1f MB, %s)", _dl_tag, filename, size_mb, winning_label)`
- On attempt format-error continue: `logger.warning("[DL:%s] attempt %d: format error — trying next", _dl_tag, i+1)`
- On all attempts failed: `logger.warning("[DL:%s] FAILED after %d attempts", _dl_tag, len(attempts))`
- On cookies expired: keep existing notification flow

**C) Only flush `_YDLLogger` buffers on final failure**, not on individual attempt failures.

Apply identical changes to `google_ads_sync.py`.

---

## Implementation Order

1. BUG-1 (NoneType crash) — fixes the infinite INTERRUPTED loop
2. BUG-2 (harmonizer method) — fixes DV360 sync retry harmonization
3. BUG-4 (OOM — memory limit) — run gcloud command, prevents future crashes
4. BUG-4 (concurrency semaphore reduce to 5) — reduces memory pressure
5. Logging redesign (Items 2–4 from user requirements)
6. BUG-3 (parallelize backfill) — after logging is clean, parallelism is observable
7. BUG-5 (double-registration noise) — last, lowest priority

---

## Files to change

- `backend/app/services/sync/scheduler.py` — BUG-1, BUG-2, BUG-3
- `backend/app/services/sync/dv360_sync.py` — Logging redesign, apply to both platforms
- `backend/app/services/sync/google_ads_sync.py` — Same logging changes
- `backend/app/services/sync/proxy_cache.py` — Reduce default semaphore from 10 to 5
- Cloud Run config (gcloud command) — Memory limit increase

---

## Key invariants to preserve

- `_expired[0]` must still be accessible from `_YDLLogger` callbacks (closure)
- `_CookiesExpiredError` must still propagate out of `_do_download` when cookies truly expired (file not on disk)
- Backfill parallelism must use the same shared semaphore (`get_concurrency_semaphore`) to respect the global concurrency limit
- Both `dv360_sync.py` and `google_ads_sync.py` must get identical download/logging changes
