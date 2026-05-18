---
quick_id: 20260518-fix-httpx-proxy-kwarg
slug: fix-httpx-proxy-kwarg
status: complete
completed_at: 2026-05-18
commits: [734b2d7]
---

# Quick Task Summary: Fix httpx proxy kwarg

**One-liner:** Changed `httpx.AsyncClient(proxies={"https://": proxy_url})` to `httpx.AsyncClient(proxy=proxy_url)` in `super_admin.py:370` — POST /proxy-config/test no longer crashes with TypeError.

## What Was Done

Fixed the `POST /api/v1/super-admin/proxy-config/test` endpoint which was raising `TypeError: AsyncClient.__init__() got an unexpected keyword argument 'proxies'` at runtime on every call.

**Root cause:** httpx 0.25.x removed the `proxies=` (dict) argument. The correct form is `proxy=` (singular string).

**Fix:** `backend/app/api/v1/endpoints/super_admin.py:370`
```python
# Before (broken):
async with httpx.AsyncClient(proxies={"https://": proxy_url}) as client:

# After (fixed):
async with httpx.AsyncClient(proxy=proxy_url) as client:
```

## Why Tests Didn't Catch It

The test at `tests/test_super_admin_proxy.py` fully patches `httpx.AsyncClient` with `unittest.mock.patch`, so the constructor is never called with the wrong kwarg during testing. Only production runtime would surface the TypeError.

## Commit

- `734b2d7` fix(proxy): use httpx proxy= kwarg (singular) — proxies= dict removed in httpx 0.25.x
