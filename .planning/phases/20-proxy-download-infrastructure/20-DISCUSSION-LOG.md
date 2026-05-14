# Phase 20: Proxy Download Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 20-proxy-download-infrastructure
**Areas discussed:** bgutil deployment mode, proxy injection scope, credential redaction approach, validation gate

---

## bgutil Deployment Mode

| Option | Description | Selected |
|--------|-------------|----------|
| Inline Python plugin | pip install, yt-dlp auto-detects, no sidecar process, works on Cloud Run | ✓ |
| HTTP sidecar (same container) | supervisord, persistent token cache, cold-start risk, container complexity | |
| Separate docker-compose service | separate container on port 4416, great for local dev, needs second Cloud Run service | |

**User's choice:** Inline Python plugin
**Notes:** No sidecar complexity; Cloud Run stays single-container.

---

## Proxy Injection Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full yt-dlp session | ydl_opts["proxy"] applies to info extraction + stream download | ✓ |
| Download only | Proxy only on stream download, info extraction hits datacenter IP | |

**User's choice:** Full yt-dlp session

| Option | Description | Selected |
|--------|-------------|----------|
| Proxy on all retry attempts | Every attempt (cookieless, primary cookies, backup) routes through residential IP | ✓ |
| Cookieless attempt only | Only first attempt uses proxy; cookie attempts fall back to direct IP | |

**User's choice:** Proxy active on all retry attempts

---

## Credential Redaction Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Wrap _YDLLogger in closure | Local _redact() helper in closure scope, no shared state | ✓ |
| Module-level redact_credentials() | Shared utility imported by dv360 + google_ads | |

**User's choice:** Wrap _YDLLogger inside the closure

| Option | Description | Selected |
|--------|-------------|----------|
| [PROXY:host] | Shows host for debugging, strips credentials | ✓ |
| [PROXY] (fully opaque) | No host visible, maximum security | |

**User's choice:** [PROXY:host] format

---

## Validation Gate

| Option | Description | Selected |
|--------|-------------|----------|
| Manual ops step on GCP | Trigger sync on production host, confirm video downloads | ✓ |
| Automated test endpoint | GET /proxy-config/test with yt-dlp info extraction | |

**User's choice:** Manual download test on GCP
**Notes:** User decided to skip Webshare free tier entirely and go directly to IPRoyal production proxy. No validation tier needed.

---

## Provider Selection

| Option | Description | Selected |
|--------|-------------|----------|
| IPRoyal | $1.75/GB pay-as-you-go, 7-day sticky sessions, no minimum | ✓ (recommended) |
| Oxylabs / Bright Data | Enterprise rates, lower per-GB at volume >2,000/month | |
| TBD | Capture as blocker | |

**User's choice:** IPRoyal (accepted recommendation)
**Notes:** Switch to Oxylabs/Bright Data when volume consistently exceeds ~2,000 videos/month.

---

## Claude's Discretion

- Sticky session ID format: `{base_username}-session-{secrets.token_urlsafe(9)}` — 12-char URL-safe suffix
- Retry list construction: `["", *cookies] if (proxy_enabled and proxy_url) else (cookies or [""])` — preserves backward compatibility when proxy is disabled

## Deferred Ideas

- Automated proxy test endpoint → possibly Phase 21 UI work
- Separate bgutil Docker sidecar → rejected in favor of inline plugin
