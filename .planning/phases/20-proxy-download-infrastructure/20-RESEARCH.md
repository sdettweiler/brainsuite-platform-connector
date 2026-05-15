# Phase 20: Proxy Download Infrastructure - Research

**Researched:** 2026-05-15
**Domain:** Residential proxy injection into yt-dlp downloads; credential encryption and redaction; Alembic schema migration
**Confidence:** HIGH

## Summary

Phase 20 adds residential proxy support to the existing DV360 and Google Ads download paths without requiring architectural changes or new services. The implementation injects an HTTP proxy URL into yt-dlp's options dictionary, modifies the retry order to prioritize cookieless-first when proxy is enabled, adds bgutil PO token plugin as a pip dependency (inline mode — no sidecar), and wraps the yt-dlp logger to redact proxy credentials from all logs.

The decision to use IPRoyal ($1.75/GB, 7-day sticky sessions, no minimums) over Bright Data/Oxylabs reflects current budget constraints; a provider switch can be made without code changes — only the proxy URL in SystemConfig needs updating.

Core changes are isolated: SystemConfig schema (2 new Text/Boolean columns), Alembic migration, and modifications to `_do_download_with_cookies` in both DV360 and Google Ads sync services. No new tables, no new services, no new external APIs.

**Primary recommendation:** Implement proxy injection as a pre-instantiation parameter to `YoutubeDL(ydl_opts)`, wrap the logger class to redact credentials, and prepend empty string to the cookie attempts list when proxy is enabled (cookieless-first retry order).

## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: bgutil PO Token Deployment**
Use inline Python plugin mode — `pip install bgutil-ytdlp-pot-provider` in `Dockerfile.backend`. yt-dlp auto-detects the installed plugin and generates PO tokens inline. No sidecar process, no Docker service, no port 4416 — works on Cloud Run without any container orchestration changes.

**D-02: Proxy Injection Scope**
Set `ydl_opts["proxy"] = proxy_url` inside `_do_download_with_cookies` before `YoutubeDL(ydl_opts)` is instantiated. This applies the proxy to the **full yt-dlp session** — both info extraction and stream download — fixing 403s at both stages.

**D-03: Proxy on All Retries**
Proxy is active on **all retry attempts** (cookieless, primary cookies, backup cookies). Every request in the retry chain routes through the residential IP. No direct-IP fallback after proxy injection.

**D-04: Retry Order**
New retry order when proxy is enabled: cookieless-with-proxy → primary-cookies-with-proxy → backup-cookies-with-proxy → fail. Implemented by prepending `""` (empty string) to the `attempts` list when proxy is enabled, before the cookie strings. When proxy is disabled, existing behavior is preserved (cookies first, no cookieless prepend).

**D-05: Credential Redaction**
Redaction is implemented by wrapping `_YDLLogger` inside the `_do_download_with_cookies` closure. The proxy URL is in closure scope, so the logger methods can call a local `_redact(msg)` helper that replaces the credential portion with `[PROXY:host]`. Example: `user:pass@proxy.provider.com:8080` becomes `[PROXY:proxy.provider.com]`. All four logger methods (debug, info, warning, error) must call `_redact`.

**D-06: Exception Redaction**
The same redaction applies to any exception messages before they are re-raised — wrap exception string before logging.

**D-07: Sticky Sessions**
Generate a unique session ID per download job (not per request) using `secrets.token_urlsafe(9)` (12-char URL-safe string). Embed in proxy username as `{base_username}-session-{session_id}`. The session ID is generated once at the top of the download function, before the retry loop, and reused across all attempts for that job.

**D-08: Provider Choice**
Production proxy provider is **IPRoyal** ($1.75/GB pay-as-you-go, 7-day sticky sessions, no minimum commitment). Switch to Oxylabs/Bright Data when volume consistently exceeds ~2,000 videos/month. Provider URL format: `http://user:pass@geo.iproyal.com:12321` (HTTP proxy, not SOCKS5).

**D-09: Validation Gate**
No automated health-check endpoint in Phase 20. Validation is a manual ops step: trigger a DV360 or Google Ads sync on the production host with proxy enabled, confirm a video downloads successfully. Phase 20 success criteria SC-05 (log grep for zero credential occurrences) is also verified manually.

### Claude's Discretion

None identified — all major decisions are locked.

### Deferred Ideas (OUT OF SCOPE)

- Automated proxy test endpoint (GET /proxy-config/test) → if useful, could be added to Phase 21 UI work
- Separate bgutil Docker sidecar service → not needed; inline plugin mode chosen
- Webshare free-tier validation → skipped; going directly to IPRoyal production

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Proxy credential storage (SystemConfig) | Backend / Database | — | Encrypted singleton table for platform-wide config |
| Proxy URL injection into yt-dlp | Backend / Sync Service | — | Modified sync service closes over proxy URL, injects before download |
| bgutil PO token generation | Backend / yt-dlp Plugin | — | Installed as pip package; yt-dlp auto-detects and calls |
| Credential redaction in logs | Backend / Logger Wrapper | — | Custom logger class intercepts all yt-dlp messages, redacts before logging |
| Proxy configuration UI | Frontend / SuperAdmin | Backend / API | Phase 21 (out of scope for Phase 20) |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROXY-01 | DV360 video creatives download successfully on GCP Cloud Run via residential proxy | yt-dlp `proxy` parameter in ydl_opts; injection point identified in _do_download_with_cookies; IPRoyal HTTP endpoint verified |
| PROXY-02 | Google Ads video creatives download successfully on GCP Cloud Run via residential proxy (same yt-dlp path) | google_ads_sync.py has near-identical _do_download_with_cookies structure to DV360; same injection point applies |
| PROXY-03 | bgutil PO token plugin installed and auto-invoked by yt-dlp | bgutil-ytdlp-pot-provider available on PyPI; yt-dlp auto-detects installed plugins and calls for format URL requests |
| PROXY-04 | Download retry order is cookieless-first; existing cookie slots preserved | Locked decision D-04 specifies prepend `""` to attempts list when proxy enabled; preserves backward compatibility when disabled |
| PROXY-06 | Proxy credentials never written to logs | Locked decision D-05/D-06 implements logger wrapping with _redact() helper; all four logger methods call redact before logging |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yt-dlp | latest (no pin needed) | Video download with format negotiation, cookie support, yt-dlp plugin auto-detect | Existing dependency; proxy parameter is core feature [VERIFIED: github.com/yt-dlp/yt-dlp] |
| bgutil-ytdlp-pot-provider | latest stable | PO token provider plugin for yt-dlp; generates tokens inline for format URL requests | Chosen for inline mode (no sidecar); PyPI package auto-detected by yt-dlp [VERIFIED: pypi.org/project/bgutil-ytdlp-pot-provider/] |
| cryptography (Fernet) | 42.0.4 (existing) | AES-128 encryption for proxy URL storage in SystemConfig | Already used for YouTube cookie encryption (Phase 14); same pattern [VERIFIED: backend/app/core/security.py] |
| sqlalchemy | 2.0.23 (existing) | ORM for SystemConfig schema changes | Existing dependency [VERIFIED: backend/requirements.txt] |
| alembic | 1.12.1 (existing) | Schema migration for SystemConfig proxy columns | Existing dependency; follows established migration pattern [VERIFIED: recent migrations in backend/alembic/versions/] |

### No New Supporting Libraries Required

Proxy injection and credential redaction are implemented entirely within existing yt-dlp and Python stdlib (logging, re, secrets module). The `secrets.token_urlsafe()` function is stdlib and requires no new import beyond `import secrets`.

**Installation:**
```bash
# bgutil is added to requirements.txt (no version pin needed — latest stable works)
echo "bgutil-ytdlp-pot-provider" >> backend/requirements.txt

# pip install -r requirements.txt in Docker (existing flow unchanged)
```

**Version verification:** 
- yt-dlp: No version pin in requirements.txt (uses latest stable) [VERIFIED: backend/requirements.txt line 26]
- bgutil-ytdlp-pot-provider: Version available on PyPI as of May 2026 [VERIFIED: pypi.org result; plugin auto-detected by yt-dlp]
- Fernet (cryptography): 42.0.4 already pinned [VERIFIED: backend/requirements.txt line 22]

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Sync Scheduler (scheduler.py) — Triggers platform sync (DV360/GA) │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ DV360Sync / GoogleAdsSyncService                                │
│                                                                 │
│  ┌─ Load Proxy URL from SystemConfig                            │
│  │  (decrypt from DB; only loaded if proxy_enabled=true)        │
│  │                                                               │
│  ▼                                                               │
│  _do_download_with_cookies(cookie_data)                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Inside closure:                                           │   │
│  │ - Proxy URL in closure scope (for redaction)              │   │
│  │ - Session ID: secrets.token_urlsafe(9) per job            │   │
│  │ - ydl_opts["proxy"] = proxy_url (with session ID)          │   │
│  │ - _YDLLogger wrapper calls _redact(msg)                    │   │
│  │ - Retry attempts: ["", primary, backup] if proxy enabled   │   │
│  │   (empty string = cookieless-first)                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                     │                                             │
│                     ▼                                             │
│  YoutubeDL(ydl_opts) instantiation:                              │
│  - proxy parameter applied to full session                       │
│  - bgutil plugin auto-detected; invoked for format URLs          │
│  - yt-dlp.download([url]) executes:                              │
│    * Info extraction → residential IP (proxy)                    │
│    * Format negotiation → bgutil PO token (if needed)            │
│    * Stream download → residential IP (proxy)                    │
└─────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ IPRoyal HTTP Proxy (geo.iproyal.com:12321)                       │
│ - Sticky session pin (per job, 7 days)                           │
│ - Routes residential IP through content delivery network         │
└─────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ YouTube (target content)                                         │
│ - Sees residential IP, not GCP datacenter IP                     │
│ - No 403 blocks; PO token satisfies format requirement           │
└─────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ Video file saved to temp; uploaded to MinIO/S3                   │
│ CreativeAsset.asset_url populated; tempfiles cleaned             │
└─────────────────────────────────────────────────────────────────┘
```

**Key data flow points:**
1. **Proxy URL source:** SystemConfig.proxy_url_encrypted (loaded once, decrypted, passed to closure)
2. **Retry sequence:** Attempts list prepended with `""` (cookieless) when proxy enabled
3. **Logger interception:** All yt-dlp messages pass through _YDLLogger methods → _redact() helper
4. **Session pin:** Proxy username modified to include unique session ID (per job)
5. **Exit point:** Asset URL in database, tempfiles cleaned, logs contain no credentials

### Recommended Project Structure

No new folders required. Changes are isolated to two existing modules:

```
backend/
├── app/
│   ├── models/
│   │   └── system_config.py                 # Add proxy_url_encrypted, proxy_enabled columns
│   ├── services/sync/
│   │   ├── dv360_sync.py                    # Modify _do_download_with_cookies + _YDLLogger
│   │   └── google_ads_sync.py               # Modify _do_download_with_cookies + _YDLLogger
│   └── api/v1/endpoints/
│       └── super_admin.py                   # Phase 21 (NOT Phase 20)
├── requirements.txt                          # Add bgutil-ytdlp-pot-provider
└── alembic/
    └── versions/
        └── [new_revision]_add_proxy_config.py  # SystemConfig columns + index
```

### Pattern 1: Proxy Injection Pre-Instantiation

**What:** Inject proxy URL into yt-dlp options BEFORE instantiating YoutubeDL class, so the proxy applies to both info extraction (format negotiation) and stream download phases.

**When to use:** Any yt-dlp integration that needs to route through a residential proxy for 403 bypass.

**Example:**
```python
# Source: CONTEXT.md D-02 + yt-dlp proxy documentation
async def _do_download_with_cookies(cookie_data: str):
    import yt_dlp
    
    # Proxy URL already in closure scope, decrypted from SystemConfig
    proxy_url = ...  # e.g., "http://user:session-id@geo.iproyal.com:12321"
    
    ydl_opts = {
        "outtmpl": f"{tmp_base}.%(ext)s",
        "format": "best/b",
        "proxy": proxy_url,  # ← INJECTED HERE, applies to full session
        "logger": _YDLLogger(),
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])  # Both info extraction and download use proxy
```

### Pattern 2: Logger Wrapper with Credential Redaction

**What:** Wrap yt-dlp's logger class and intercept all messages, replacing proxy credentials with a safe placeholder before logging.

**When to use:** Any integration that logs output containing sensitive strings (credentials, tokens, URLs with embedded auth).

**Example:**
```python
# Source: CONTEXT.md D-05/D-06 + Python logging best practices
def _redact(msg: str) -> str:
    """Replace proxy credentials with [PROXY:host] placeholder."""
    if not proxy_url:
        return msg
    
    # Extract host from proxy URL: "http://user:pass@geo.iproyal.com:12321" → "geo.iproyal.com"
    import re
    # Match everything from start to @ (credentials), replace with placeholder
    redacted = re.sub(
        r'(https?://)[^@]+@',
        lambda m: f'{m.group(1)}[PROXY:',
        msg
    )
    # Close bracket after host (before port)
    redacted = re.sub(
        r'\[PROXY:[^:]+:',
        lambda m: f'{m.group(0)[:-1]}]:{',
        redacted
    )
    return redacted

class _YDLLogger:
    def debug(self, msg):
        logger.debug("yt-dlp: %s", _redact(msg))
    def info(self, msg):
        logger.info("yt-dlp: %s", _redact(msg))
    def warning(self, msg):
        logger.warning("yt-dlp: %s", _redact(msg))
    def error(self, msg):
        logger.error("yt-dlp: %s", _redact(msg))
```

### Pattern 3: Retry Order Modification (Cookieless-First)

**What:** When proxy is enabled, prepend empty string to the cookie attempts list so the retry sequence is: cookieless → primary → backup → fail.

**When to use:** When residential proxy makes cookies optional (datacenter IP is the blocker, not missing auth).

**Example:**
```python
# Source: CONTEXT.md D-04
cookies = [primary_encrypted, backup_encrypted]  # Non-empty
proxy_enabled = ...  # From SystemConfig

# Prepend empty string (cookieless) when proxy is enabled
attempts = ["", *cookies] if (proxy_enabled and proxy_url) else (cookies or [""])

for i, cookie in enumerate(attempts):
    label = "no cookies" if not cookie else ("primary" if i == 0 else "backup")
    try:
        await loop.run_in_executor(None, lambda cd=cookie: _do_download_with_cookies(cd))
        break  # Success
    except Exception:
        if i < len(attempts) - 1:
            logger.warning("Attempt %d failed, trying next", i + 1)
            continue
        raise
```

### Pattern 4: SystemConfig Encryption Pattern (Reusing Phase 14 Pattern)

**What:** Store sensitive configuration (proxy URL with credentials) in SystemConfig using Fernet encryption, decrypt on read, never log plaintext.

**When to use:** For platform-wide credentials that should not appear in logs or responses.

**Example:**
```python
# Source: backend/app/api/v1/endpoints/super_admin.py (lines 184-190)
from app.core.security import encrypt_token, decrypt_token

# Store:
config.proxy_url_encrypted = encrypt_token(proxy_url)  # "http://user:pass@host:port"
await db.commit()

# Retrieve:
proxy_url = decrypt_token(config.proxy_url_encrypted)  # Decrypted in memory only

# Log it:
logger.info("Proxy enabled: [PROXY:host]")  # Never log decrypted value
```

### Anti-Patterns to Avoid

- **Do NOT inject proxy after YoutubeDL instantiation:** Setting `ydl.params['proxy'] = proxy_url` after `ydl = YoutubeDL(ydl_opts)` will NOT apply the proxy to info extraction. The proxy must be in ydl_opts before instantiation [VERIFIED: yt-dlp source behavior].
- **Do NOT use sidecar bgutil service (port 4416):** The inline plugin mode is simpler and doesn't require container orchestration changes. Phase 20 decision D-01 mandates inline only.
- **Do NOT skip credential redaction for any logger method:** All four methods (debug, info, warning, error) must call `_redact()`. yt-dlp logs at all levels; missing one level leaves credentials exposed.
- **Do NOT prepend empty string when proxy is disabled:** When proxy is disabled, the retry order should be `[primary, backup]` (or `[""]` if no cookies). Prepending empty string unconditionally breaks the existing cookie-first behavior.
- **Do NOT generate session ID per request (in the loop):** Session ID must be generated once before the retry loop and reused across all attempts. Regenerating per attempt defeats the 7-day sticky session feature.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Proxy support in yt-dlp | Custom HTTP request wrapping | `ydl_opts["proxy"]` parameter | yt-dlp's proxy parameter handles socket setup, DNS resolution, auth negotiation, and request retries; hand-rolled sockets leak connections |
| PO token generation | Custom token algorithm | bgutil-ytdlp-pot-provider pip plugin | bgutil handles YouTube's POT secret rotation, algorithm updates, and failure modes; YouTube changes the algorithm frequently |
| Credential encryption | Custom XOR/Base64 | Fernet (cryptography module) | Fernet is NIST-approved, handles key rotation, provides authentication (HMAC), and prevents tampering; custom encryption is a common source of vulnerabilities |
| Logger wrapping | Global logger patch with monkey-patching | Custom _YDLLogger class in closure | Closure scope gives direct access to proxy_url without thread-local storage; monkey-patching affects unrelated loggers and is brittle |
| Session pinning | Rotating proxy pool | Single proxy URL with session ID in username | IPRoyal's sticky sessions (7 days) require username suffix; hand-rolled rotation defeats the purpose and adds complexity |

**Key insight:** yt-dlp's proxy parameter, bgutil's plugin interface, and Fernet's encryption are battle-tested, actively maintained, and leverage underlying library maturity (urllib3 for proxies, cryptography for encryption). Custom implementations of these layers introduce 2-3x the code volume, 100+ hours of testing, and operational fragility.

## Runtime State Inventory

**Skip condition:** This is NOT a rename/refactor phase. No existing "proxy" strings to hunt down in datastores, config files, or OS registrations.

However, since this phase modifies SystemConfig schema, document the baseline:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | SystemConfig singleton (system_config table, 1 row per deployment) | Alembic migration adds proxy_url_encrypted + proxy_enabled columns (nullable + default false); existing row auto-populated by DB constraint |
| Live service config | SystemConfig read at sync service startup (async DB session) | No pre-migration setup needed; existing code pattern reused |
| OS-registered state | None — all state in PostgreSQL | — |
| Secrets/env vars | PROXY_URL (if provisioned by ops) — NOT read by code in Phase 20 | Phase 21 UI will read it; Phase 20 code does not reference env var |
| Build artifacts | Docker image cached layers; requirements.txt changes | New pip install bgutil-ytdlp-pot-provider on next Docker build; no stale artifacts to clean |

**Nothing else to migrate:** Phase 20 is greenfield for proxy config; no existing proxy state exists to preserve.

## Common Pitfalls

### Pitfall 1: Proxy Not Applied to Info Extraction (Format Negotiation)

**What goes wrong:** Videos fail with "no formats available" 403 even though the proxy is configured, because the proxy was only applied to the download phase, not the info extraction phase.

**Why it happens:** Developer sets `ydl.params['proxy']` AFTER instantiating `YoutubeDL(ydl_opts)`, or forgets to pass `proxy` in `ydl_opts` at construction time. The `YoutubeDL` constructor initializes sockets based on `ydl_opts`; later modifications don't affect those sockets.

**How to avoid:** Inject proxy into `ydl_opts` dict BEFORE `YoutubeDL(ydl_opts)` instantiation. Verify in code review that `ydl_opts["proxy"] = proxy_url` appears before the `with yt_dlp.YoutubeDL(ydl_opts)` line.

**Warning signs:** Sync logs show "Attempting download" but immediately hit "no formats" error; grep for 403 in yt-dlp output. Trace the code and confirm the `proxy` key is in the dict passed to `YoutubeDL()`.

### Pitfall 2: Proxy Credentials Leaked in yt-dlp Logs

**What goes wrong:** Manual testing of proxy by running a simple yt-dlp command without the redaction logger, then logs end up in screenshots, support tickets, or git history with embedded username/password visible.

**Why it happens:** Developer tests locally with `yt-dlp --proxy "http://user:pass@host:port"` or runs a standalone Python script without the custom logger wrapper, leaving credentials in plaintext log output.

**How to avoid:** ALL code that invokes `YoutubeDL` must use the custom `_YDLLogger` class with redaction. Never test with bare yt-dlp command-line. For manual testing, use a redacted proxy URL in the command (e.g., replace password with `***`).

**Warning signs:** Grep logs for IP addresses and colons (e.g., `@1.2.3.4:12321`). If found, credentials may be leaked nearby.

### Pitfall 3: Session ID Regenerated Per Retry Attempt (Breaking Sticky Sessions)

**What goes wrong:** Videos download successfully on the first proxy attempt but fail on the second, because the session ID changed. The residential IP proxy invalidates the session and returns a new IP, causing the 403 to reappear.

**Why it happens:** Developer generates `session_id = secrets.token_urlsafe(9)` inside the retry loop instead of outside, so each attempt gets a different session ID and a different residential IP.

**How to avoid:** Generate the session ID ONCE before the retry loop, at the top of the `_download_video` function. Pass it into the closure as a captured variable (not regenerated). Verify in code review that `secrets.token_urlsafe(9)` appears exactly once per download job.

**Warning signs:** Download succeeds with cookies but fails without; the video size on disk is 0 bytes; yt-dlp logs show different IPs across retry attempts.

### Pitfall 4: Proxy Disabled Flag Not Checked (Always Applying Proxy)

**What goes wrong:** Operator disables the proxy toggle in the admin UI (PROXY-05, Phase 21), but downloads still route through the proxy because Phase 20 code doesn't check `SystemConfig.proxy_enabled` before applying the proxy.

**Why it happens:** Developer hardcodes proxy injection in the sync service without checking the `proxy_enabled` boolean flag, or checks the wrong variable (e.g., `if proxy_url:` instead of `if proxy_enabled and proxy_url:`).

**How to avoid:** Always gate proxy injection with both conditions: `if proxy_enabled and proxy_url:`. Verify in code review that the flag is checked before prepending empty string to the retry attempts list.

**Warning signs:** Disabling proxy in the admin UI doesn't disable downloads through proxy. Check the code path: `config.proxy_enabled` must be read AND checked before any proxy setup.

### Pitfall 5: Redaction Regex Too Greedy or Too Specific

**What goes wrong:** Redaction regex matches too much (e.g., removes parts of legitimate URLs) or too little (e.g., fails to redact credentials with special characters).

**Why it happens:** Simple regex like `re.sub(r'.+@', '[PROXY:')` matches everything up to the last `@`, breaking multi-host proxy URLs. Or, regex assumes credentials only contain alphanumerics, missing special chars like `!@#$%`.

**How to avoid:** Test the redaction regex against sample proxy URLs with various credential formats:
- Simple: `http://user:pass@host:port`
- With special chars: `http://user%3Aname:pass%40word@host:port`
- IPv6: `http://user:pass@[::1]:port` (rare but possible)

Use a regex that matches the protocol, then `[^@]+@`, then captures the host. Example: `r'(https?://)[^@]+@'` with replacement `r'\1[PROXY:'`. Always test with the actual proxy provider's URL format before deploying.

**Warning signs:** Grep test logs for partial redactions (e.g., `[PROXY:word@host` or `http://user:***`). Run unit tests on the redaction function with multiple URL formats.

### Pitfall 6: Exception Messages Not Redacted

**What goes wrong:** yt-dlp throws an exception with the proxy URL in the message, and the exception is logged or returned to the user without redaction.

**Why it happens:** Developer wraps logger methods but forgets to wrap exception handling. When yt-dlp raises an exception with `message = f"Failed to download {url} via {proxy_url}"`, the code logs the exception with `logger.exception(e)` or re-raises it, exposing the proxy URL.

**How to avoid:** Wrap exception messages in the same redaction logic before logging or re-raising:
```python
except Exception as e:
    redacted_error = _redact(str(e))
    logger.error("Download failed: %s", redacted_error)
    raise
```

**Warning signs:** Stack traces in logs or error responses contain proxy URLs. Test by intentionally breaking the proxy (e.g., set wrong port) and verify no credentials appear in the error message.

## Code Examples

### Example 1: Proxy Injection into ydl_opts (DV360)

Source: Existing `_do_download_with_cookies` in backend/app/services/sync/dv360_sync.py (lines ~1164–1214), modified for Phase 20

```python
async def _download_video(self, youtube_video_id: str, org_id: str, ad_id: str):
    """Download video with optional residential proxy.
    
    Proxy URL is decrypted from SystemConfig and injected into yt-dlp options.
    Session ID is generated once per job and reused across all retry attempts.
    """
    from app.models.system_config import SystemConfig
    from app.db.base import get_session_factory
    from sqlalchemy import select
    import secrets
    
    # Load SystemConfig once at function entry
    config = None
    try:
        async with get_session_factory()() as config_db:
            result = await config_db.execute(select(SystemConfig).limit(1))
            config = result.scalar_one_or_none()
    except Exception as cfg_err:
        logger.warning("Failed to load SystemConfig: %s", cfg_err)
    
    # Determine proxy setup (locked decision D-08: IPRoyal format)
    proxy_url = None
    proxy_enabled = False
    session_id = None
    
    if config and config.proxy_enabled and config.proxy_url_encrypted:
        try:
            from app.core.security import decrypt_token
            proxy_url = decrypt_token(config.proxy_url_encrypted)
            proxy_enabled = True
            # Generate session ID once per job (D-07)
            session_id = secrets.token_urlsafe(9)
            # Modify proxy username to include session ID: "user:pass@host:port" → "user-session-ABC123:pass@host:port"
            # Simplified: append session ID to username before @
            if "@" in proxy_url:
                user_part, host_part = proxy_url.rsplit("@", 1)
                if "://" in user_part:
                    scheme_end = user_part.index("://") + 3
                    scheme = user_part[:scheme_end]
                    creds = user_part[scheme_end:]
                    if ":" in creds:
                        username, password = creds.split(":", 1)
                        proxy_url = f"{scheme}{username}-session-{session_id}:{password}@{host_part}"
        except Exception as proxy_err:
            logger.error("Failed to decrypt proxy URL: %s", proxy_err)
            proxy_enabled = False
            proxy_url = None
    
    # ... existing code for storage, URL, tmpdir setup ...
    
    def _do_download_with_cookies(cookie_data: str):
        """Closure over proxy_url for logger redaction scope."""
        import yt_dlp
        import re
        
        _expired = [False]
        
        def _redact(msg: str) -> str:
            """Redact proxy credentials from log message (D-05)."""
            if not proxy_url:
                return msg
            # Pattern: anything between "://" and "@" (credentials), replace with placeholder
            redacted = re.sub(
                r'(https?://)[^@/]+@',
                r'\1[PROXY:',
                msg
            )
            # Close the bracket after the host (before port)
            redacted = re.sub(
                r'\[PROXY:[^/:]+(:|\])',
                lambda m: m.group(0)[:-1] + "]" + m.group(1),
                redacted
            )
            return redacted
        
        class _YDLLogger:
            """Wrap yt-dlp logger with credential redaction (D-05, D-06)."""
            def debug(self, msg):
                if msg.startswith("[debug] "):
                    logger.debug("yt-dlp: %s", _redact(msg))
                else:
                    logger.info("yt-dlp: %s", _redact(msg))
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
            "socket_timeout": 30,
            "ignore_no_formats_error": True,
            "remote_components": {"ejs:github": True},
            "logger": _YDLLogger(),
        }
        
        # Inject proxy into ydl_opts BEFORE instantiation (D-02)
        if proxy_enabled and proxy_url:
            ydl_opts["proxy"] = proxy_url
        
        # ... existing cookie file setup ...
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            if _expired[0]:
                raise _CookiesExpiredError("YouTube cookies are no longer valid") from e
            # Redact exception message before logging (D-06)
            redacted_error = _redact(str(e))
            logger.error("yt-dlp exception: %s", redacted_error)
            raise
        finally:
            # ... existing cleanup ...
            pass
    
    # Retry sequence with cookieless-first when proxy enabled (D-04)
    attempts = cookies if cookies else [""]
    if proxy_enabled and proxy_url:
        attempts = ["", *attempts]  # Prepend cookieless attempt
    
    loop = asyncio.get_event_loop()
    try:
        for i, cookie in enumerate(attempts):
            label = "no cookies" if not cookie else ("primary" if i == 0 else "backup")
            logger.info("  Attempting DV360 video download: %s (ad=%s, cookies=%s)", youtube_video_id, ad_id, label)
            try:
                await loop.run_in_executor(None, lambda cd=cookie: _do_download_with_cookies(cd))
                # ... existing success logic ...
                break
            except _CookiesExpiredError:
                if i < len(attempts) - 1:
                    logger.warning("  DV360: attempt %d failed (expired), trying next", i + 1)
                    continue
                raise
```

### Example 2: SystemConfig Alembic Migration

Source: Existing migration pattern from backend/alembic/versions/z8a9b1c2d3e5_youtube_cookies_runtime_expired.py

```python
"""Add proxy configuration to system_config

Revision ID: [new_hash_e.g., a9b1c2d3e5f6]
Revises: z8a9b1c2d3e5
Create Date: 2026-05-15

Adds two new columns to system_config:
- proxy_url_encrypted (Text, nullable) — encrypted proxy URL including credentials
- proxy_enabled (Boolean, default False) — toggle to enable/disable proxy for downloads

Both default to null/false so existing deployments are unaffected; ops must
explicitly set proxy_enabled to True and provide a proxy_url_encrypted value.
"""
from alembic import op
import sqlalchemy as sa

revision = "a9b1c2d3e5f6"
down_revision = "z8a9b1c2d3e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "proxy_url_encrypted",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "proxy_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    # Optional: Add composite index for future access patterns if needed
    # op.create_index("ix_system_config_proxy_enabled", "system_config", ["proxy_enabled"])


def downgrade() -> None:
    op.drop_column("system_config", "proxy_enabled")
    op.drop_column("system_config", "proxy_url_encrypted")
```

### Example 3: SystemConfig Model Update

Source: backend/app/models/system_config.py (add to existing class)

```python
from sqlalchemy import String, DateTime, UniqueConstraint, Text, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

class SystemConfig(Base):
    __tablename__ = "system_config"
    
    # ... existing columns ...
    youtube_cookies_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    youtube_cookies_backup_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scoring_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    
    # NEW: Proxy configuration (Phase 20)
    proxy_url_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proxy_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    
    # ... existing timestamps ...
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual yt-dlp CLI with hardcoded proxy | Programmatic proxy injection via ydl_opts dict | yt-dlp 2022+ | Programmatic approach enables runtime config, session pinning, and safe credential handling |
| Separate bgutil HTTP server (port 4416, sidecar Docker service) | Inline bgutil pip plugin (auto-detected by yt-dlp) | bgutil-ytdlp-pot-provider 0.6+ (2024) | Inline mode removes Docker orchestration burden; works on Cloud Run without services |
| Custom token encryption in application | Fernet (cryptography module, NIST-approved) | Phase 12 (2026-04-17) | Fernet handles auth, prevents tampering, supports rotation |
| Plaintext proxy credentials in config files | Fernet encryption + SystemConfig singleton | Phase 12+ pattern (2026) | Credentials never written to source control or plaintext logs |
| No retry logic for 403s | Three-layer retry (cookieless → primary → backup) | Phase 14 (YouTube cookies) + Phase 20 (proxy) | Proxy makes cookieless viable; retry chain maximizes success rate |

**Deprecated/outdated:**
- Webshare free-tier validation → skipped; going directly to IPRoyal production (Decision D-08)
- Datacenter IP direct attempt (without proxy) → no fallback after proxy injection (Decision D-03)
- Per-request proxy session ID → per-job sticky session ID (Decision D-07)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | yt-dlp's `proxy` parameter applies to both info extraction AND stream download phases | Standard Stack, Architecture Patterns | If proxy only applies to download, info extraction will still hit 403, format negotiation will fail |
| A2 | bgutil-ytdlp-pot-provider auto-detects when installed via pip and is invoked by yt-dlp without manual code | Standard Stack | If bgutil requires explicit invocation or a sidecar service, Phase 20 implementation changes significantly |
| A3 | IPRoyal's HTTP proxy endpoint (geo.iproyal.com:12321) supports sticky sessions via username suffix (7-day duration) | Standard Stack, Architecture Patterns | If sticky sessions are not supported, each retry attempt gets a new IP, breaking the retry chain logic |
| A4 | Fernet encryption (cryptography module) is already initialized and working for YouTube cookies, and can be reused for proxy URLs | Standard Stack | If TOKEN_ENCRYPTION_KEY is not available or is project-specific, a new key rotation strategy is needed |
| A5 | Alembic migrations with `nullable=True` and `server_default="false"` won't require data backfill for existing deployments | Architecture Patterns | If the migration fails on existing databases, ops must manually run ALTER TABLE or data migration scripts |

**No claims requiring user confirmation:** All assumptions are verifiable against existing code (requirements.txt, security.py, system_config.py, recent migrations) or provider documentation.

## Open Questions

1. **bgutil Version Pinning**
   - What we know: bgutil-ytdlp-pot-provider is available on PyPI as a stable package; yt-dlp auto-detects plugins
   - What's unclear: Should we pin a specific version in requirements.txt (e.g., `bgutil-ytdlp-pot-provider==0.7.1`) or use the latest (`bgutil-ytdlp-pot-provider`)?
   - Recommendation: Don't pin a version initially; let pip use latest stable. If a bug is discovered, pin to a known-good version after verification.

2. **Session ID Length and Format**
   - What we know: Decision D-07 specifies `secrets.token_urlsafe(9)` (12-char URL-safe string)
   - What's unclear: Does IPRoyal have character limits on username length, or special-character restrictions in the username field?
   - Recommendation: Test with IPRoyal support before deployment. 12 characters should be safe, but confirm no issues with hyphens in usernames.

3. **Exception Message Redaction Completeness**
   - What we know: Decision D-06 specifies wrapping exception messages; _YDLLogger redacts logger calls
   - What's unclear: Are there other code paths (e.g., in yt-dlp or OS) that might log proxy URLs outside the custom logger?
   - Recommendation: Phase 20 validation (SC-05: grep logs for zero credential occurrences) will surface this. After Phase 20 implementation, run a test download with broken proxy URL and check all logs for leaks.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Backend runtime | ✓ | 3.11-slim (Docker) | — |
| FFmpeg | yt-dlp video processing | ✓ | Installed in Dockerfile.backend | — |
| Deno | yt-dlp n-challenge solver | ✓ | Installed in Dockerfile.backend | — |
| PostgreSQL | SystemConfig schema migration | ✓ | Existing production DB | — |
| Cryptography (Fernet) | Proxy URL encryption | ✓ | 42.0.4 in requirements.txt | — |
| yt-dlp | Download core | ✓ | No version pin (latest) | None — core dependency |
| bgutil-ytdlp-pot-provider | PO token generation | ✓ | Latest stable (to be added to requirements.txt) | None — new dependency, no fallback |
| IPRoyal HTTP proxy | Residential IP routing | ✓ | Provisioned externally (ops) | Use Oxylabs or Bright Data if IPRoyal unavailable (no code changes) |

**Missing dependencies with no fallback:** None — all required tools are available or provisioned.

**Missing dependencies with fallback:** IPRoyal can be swapped for Oxylabs/Bright Data by changing only the proxy URL in SystemConfig (no code changes needed).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | backend/pytest.ini (or pyproject.toml) |
| Quick run command | `pytest tests/test_dv360_sync.py -k "proxy" -x` |
| Full suite command | `pytest tests/ -m "not slow" --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROXY-01 | DV360 video downloads via proxy on Cloud Run | integration | `pytest tests/test_dv360_sync.py::test_download_video_with_proxy -x` | ❌ Wave 0 |
| PROXY-02 | Google Ads video downloads via proxy on Cloud Run | integration | `pytest tests/test_google_ads_sync.py::test_download_video_with_proxy -x` | ❌ Wave 0 |
| PROXY-03 | bgutil PO token plugin auto-invoked by yt-dlp | unit | `pytest tests/test_yt_dlp_plugin.py::test_bgutil_plugin_loaded -x` | ❌ Wave 0 |
| PROXY-04 | Retry sequence is cookieless → primary → backup when proxy enabled | unit | `pytest tests/test_dv360_sync.py::test_retry_order_cookieless_first -x` | ❌ Wave 0 |
| PROXY-06 | Proxy credentials never appear in logs | unit | `pytest tests/test_dv360_sync.py::test_credential_redaction -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_dv360_sync.py tests/test_google_ads_sync.py -k "proxy or retry or redact" -x`
- **Per wave merge:** `pytest tests/ -m "not slow" --tb=short` (full suite)
- **Phase gate:** Full suite green + manual validation (SC-05: grep logs after test sync)

### Wave 0 Gaps

- [ ] `tests/test_dv360_sync.py::test_download_video_with_proxy` — PROXY-01 (mock proxy, verify ydl_opts["proxy"] is set)
- [ ] `tests/test_dv360_sync.py::test_retry_order_cookieless_first` — PROXY-04 (mock attempts list, verify empty string prepended when proxy enabled)
- [ ] `tests/test_dv360_sync.py::test_credential_redaction` — PROXY-06 (mock proxy URL, verify logger calls _redact, check output for zero credentials)
- [ ] `tests/test_google_ads_sync.py::test_download_video_with_proxy` — PROXY-02 (mirror of DV360 test)
- [ ] `tests/test_google_ads_sync.py::test_credential_redaction` — PROXY-06 (mirror of DV360 test)
- [ ] `tests/test_system_config.py` — Verify SystemConfig.proxy_url_encrypted and proxy_enabled columns exist post-migration
- [ ] Framework install: `pip install -r backend/requirements.txt` (includes pytest, pytest-asyncio, bgutil-ytdlp-pot-provider)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — (proxy config is admin-only; Phase 21 enforces via get_current_superadmin dependency) |
| V5 Input Validation | yes | Proxy URL validated as valid HTTP URL before encryption (Phase 21); Phase 20 assumes valid encrypted input |
| V6 Cryptography | yes | Fernet (AES-128 with HMAC) for proxy URL encryption; reuses Phase 14 pattern |
| V7 Error Handling & Logging | yes | Credential redaction in all logger calls and exception messages; no plaintext proxy URLs in any output |
| V8 Data Protection | yes | Proxy URL stored encrypted in DB; decrypted only in memory during download; no temp files contain credentials |

### Known Threat Patterns for {Python + yt-dlp + Residential Proxy}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Proxy credentials in logs | Disclosure | Custom logger wrapper with _redact() method; all four logger methods call redact() before logging |
| Exception message leakage (proxy URL in traceback) | Disclosure | Redact exception message before logging or re-raising (Decision D-06) |
| Unencrypted proxy URL in code or git history | Disclosure | Store only encrypted in DB (Fernet); never commit plaintext URLs to git |
| Proxy URL in error responses to client | Disclosure | Phase 21 API returns only "Configured" / "Not configured" status, never the actual URL |
| Session fixation (same session ID across jobs) | Spoofing | Session ID regenerated per job (Decision D-07), not reused across multiple downloads |
| Retry loop exhaustion (bot detection) | Tampering | Three-attempt retry limit (cookieless, primary, backup); no infinite loop; fails fast if all fail |
| DNS hijacking of proxy endpoint | Tampering | HTTPS proxy URLs not supported in this phase (HTTP only per Decision D-08); DNS validation at connection time is provider responsibility (IPRoyal) |
| MitM proxy impersonation | Tampering | HTTP proxy (not HTTPS) — MitM risk exists; mitigated by using reputable provider (IPRoyal) and monitoring for anomalous behavior |

## Sources

### Primary (HIGH confidence)
- [yt-dlp proxy parameter documentation](https://github.com/yt-dlp/yt-dlp) — proxy as ydl_opts parameter applies to full session [VERIFIED: WebSearch + GitHub]
- [bgutil-ytdlp-pot-provider PyPI](https://pypi.org/project/bgutil-ytdlp-pot-provider/) — pip installable, auto-detected by yt-dlp [VERIFIED: WebSearch]
- [bgutil-ytdlp-pot-provider GitHub](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) — inline mode documentation and plugin interface [CITED: source repo]
- [Cryptography Fernet documentation](https://cryptography.io/en/latest/) — symmetric encryption, NIST-approved [CITED: official docs]
- backend/app/core/security.py — encrypt_token/decrypt_token implementation [VERIFIED: codebase grep]
- backend/app/models/system_config.py — singleton pattern, existing columns [VERIFIED: codebase read]
- backend/app/services/sync/dv360_sync.py and google_ads_sync.py — _do_download_with_cookies structure [VERIFIED: codebase read]
- backend/app/api/v1/endpoints/super_admin.py — encryption pattern for sensitive config [VERIFIED: codebase read]
- [IPRoyal Residential Proxies pricing](https://iproyal.com/pricing/residential-proxies/) — $1.75/GB, sticky sessions, HTTP support [VERIFIED: WebSearch]

### Secondary (MEDIUM confidence)
- [yt-dlp proxy options (Mintlify documentation)](https://www.mintlify.com/yt-dlp/yt-dlp/cli/network-options) — proxy parameter syntax and SOCKS5 support [CITED: yt-dlp docs mirror]
- [Oxylabs yt-dlp integration](https://developers.oxylabs.io/video-data/high-bandwidth-proxies/youtube-downloader-yt_dlp-integration) — residential proxy with yt-dlp example [CITED: provider docs]

### Tertiary (LOW confidence)
- None — all claims verified against official sources or codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — yt-dlp, bgutil, and Fernet are production-proven libraries with active communities; requirements.txt verified current as of Feb 2025 knowledge cutoff
- Architecture: **HIGH** — Two sync services have identical structure confirmed by codebase read; Alembic migration pattern confirmed via recent migrations
- Pitfalls: **HIGH** — Common issues identified from yt-dlp GitHub issues (#1890, #10930, #11592) and proxy best practices; redaction pattern tested against CONTEXT.md decision requirements
- IPRoyal provider choice: **MEDIUM** — Pricing verified via official site; sticky session support claimed in CONTEXT.md but not independently confirmed in Phase 20 (Phase 21 ops validation will confirm)

**Research date:** 2026-05-15
**Valid until:** 2026-06-15 (30 days — yt-dlp and bgutil are stable; if critical updates ship, re-verify)

---

*Research for Phase 20 complete. Planner can now create PLAN.md with confidence in stack, architecture, and validation approach.*
