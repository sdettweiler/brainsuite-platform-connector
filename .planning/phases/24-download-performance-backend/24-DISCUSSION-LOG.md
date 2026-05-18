# Phase 24: Download Performance Backend - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 24-download-performance-backend
**Areas discussed:** Extraction/retry split, bgutil parity gap, Proxy cache placement, Sleep drop condition

---

## Extraction/Retry Split

### Q1: Download retry sequence

| Option | Description | Selected |
|--------|-------------|----------|
| PO-direct first, then proxy | Attempt 1: no proxy/no cookies. Attempt 2: proxy/no cookies. Attempt 3: proxy+primary cookies. Attempt 4: proxy+backup cookies. | ✓ |
| Proxy first (skip direct download) | Skip no-proxy download attempt; go straight to proxy since extraction verified access | |
| You decide | Claude picks | |

**User's choice:** PO-direct first, then proxy

---

### Q2: yt-dlp API for split

| Option | Description | Selected |
|--------|-------------|----------|
| Two separate YDL instances (Recommended) | Instance 1: extract_info(url, download=False) no proxy. Instance 2: process_ie_result(info_dict, download=True) per attempt. | ✓ |
| Full re-extract per attempt | Each attempt calls ydl.download([url]) — defeats PERF-01 | |
| Extract with yt-dlp, download via httpx | Hybrid approach; more complex | |

**User's choice:** Two separate YDL instances

---

### Q3: Function structure

| Option | Description | Selected |
|--------|-------------|----------|
| New _extract_info(url) and _do_download(info_dict, proxy_url, cookie_data) (Recommended) | Clean separation; replaces _do_download_with_cookies closure | ✓ |
| Extend existing closure with proxy_override kwarg | Fewer changes but mixes concerns | |
| You decide | Claude picks | |

**User's choice:** New separate functions

---

### Q4: Extraction failure handling

| Option | Description | Selected |
|--------|-------------|----------|
| Fail fast | Extraction without proxy should succeed for public videos; if fails, skip | |
| Retry extraction with proxy as fallback | If direct extraction fails, retry with proxy — handles geo-restricted metadata | ✓ |
| You decide | Claude picks | |

**User's choice:** Retry extraction with proxy as fallback

---

## bgutil Parity Gap

### Q1: Add remote_components to google_ads_sync.py

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — add it in Phase 24 (Recommended) | Project rule: fix all platforms simultaneously. Needed for PERF-03 to work on Google Ads. | ✓ |
| No — defer to Phase 26 (PROXY-02) | Keep scoped to validation phase | |
| You decide | Claude picks | |

**User's choice:** Add in Phase 24

---

## Proxy Cache Placement

### Q1: Cache scope

| Option | Description | Selected |
|--------|-------------|----------|
| Module-level shared cache (Recommended) | Single shared cache between DV360 and Google Ads; one DB hit per 60s even when both run concurrently | ✓ |
| Per-class cache | Each class maintains its own; simpler but may double DB hits on concurrent runs | |
| You decide | Claude picks | |

**User's choice:** Module-level shared cache

---

### Q2: Cache file location

| Option | Description | Selected |
|--------|-------------|----------|
| New proxy_cache.py in services/sync/ (Recommended) | Clean separation; both sync files import from it; Phase 25 semaphore can live nearby | ✓ |
| Inline at top of each sync file | Not truly shared — would be per-module, contradicts decision | |
| You decide | Claude picks | |

**User's choice:** New proxy_cache.py

---

## Sleep Drop Condition

### Q1: Sleep value when proxy enabled

| Option | Description | Selected |
|--------|-------------|----------|
| Drop to 0s entirely (Recommended) | Residential proxy + sticky session isolates each video; no rate-limiting needed | ✓ |
| Reduce to 1s | Minimal safety buffer | |
| Keep 4s with config flag | Over-engineered for Phase 24 | |

**User's choice:** Drop to 0s entirely

---

### Q2: Sleep condition data source

| Option | Description | Selected |
|--------|-------------|----------|
| Read from proxy_cache.py (Recommended) | get_proxy_config() at batch loop start; cache makes it cheap | ✓ |
| Pass proxy_enabled down from caller | Pre-fetch once and pass as param; avoids extra import | |
| You decide | Claude picks | |

**User's choice:** Read from proxy_cache.py

---

## Claude's Discretion

None — all areas had clear user selections.

## Deferred Ideas

- Sticky session pinning per sync job (not per video) — would require session ID threading through call chain; deferred pending proxy session rotation issues
- 720p quality cap — explicitly declined for v1.5
- Per-phase socket_timeout differentiation (extraction vs download) — 10s applied uniformly; revisit if extraction timeouts emerge
