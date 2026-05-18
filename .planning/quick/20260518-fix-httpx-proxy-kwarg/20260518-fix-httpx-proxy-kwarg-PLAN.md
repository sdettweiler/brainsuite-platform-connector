---
quick_id: 20260518-fix-httpx-proxy-kwarg
slug: fix-httpx-proxy-kwarg
description: Fix httpx proxy kwarg in super_admin.py:370 — change proxies={dict} to proxy=url (httpx 0.25.2)
created: 2026-05-18
must_haves:
  truths:
    - "POST /api/v1/super-admin/proxy-config/test no longer raises TypeError at runtime"
    - "httpx.AsyncClient uses proxy= (singular string) not proxies= (dict)"
  artifacts:
    - backend/app/api/v1/endpoints/super_admin.py
  key_links:
    - "super_admin.py:370 — httpx.AsyncClient(proxy=proxy_url)"
---

# Quick Task: Fix httpx proxy kwarg

## Context

Integration check found that `POST /super-admin/proxy-config/test` crashes with `TypeError: AsyncClient.__init__() got an unexpected keyword argument 'proxies'` because httpx 0.25.2 uses `proxy=` (singular string), not `proxies=` (dict).

The test suite patches `httpx.AsyncClient` entirely so the TypeError is invisible to automated tests.

## Task

**Task 1: Fix httpx AsyncClient proxy kwarg**

- File: `backend/app/api/v1/endpoints/super_admin.py`, line 370
- Action: Change `httpx.AsyncClient(proxies={"https://": proxy_url})` to `httpx.AsyncClient(proxy=proxy_url)`
- Verify: `grep -n "proxy=" backend/app/api/v1/endpoints/super_admin.py | grep AsyncClient` returns `proxy=proxy_url`
- Done: Single edit committed
