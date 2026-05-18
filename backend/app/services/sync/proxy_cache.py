"""Proxy configuration cache module (Phase 24, PERF-04).

Exposes a single async function get_proxy_config() that returns (proxy_enabled, proxy_url)
by reading from the SystemConfig DB row on first call, then serving from an in-memory cache
for up to CACHE_TTL_SECONDS seconds.

Purpose: Eliminates per-download SystemConfig DB query + Fernet decryption (~5ms each).
Both dv360_sync.py and google_ads_sync.py call this instead of their inline proxy-loading
blocks.

Thread/task safety: _cache_lock (asyncio.Lock) serializes all reads and writes so that
concurrent download coroutines cannot race on _cache dict mutation.

Security note (T-24-01): The decrypted proxy URL (including credentials) is held in
module-level _cache for up to 60s. This is intentional and acceptable per ASVS V6.
The URL is never logged — only the warning message format "Failed to load proxy config
from DB: %s" is emitted on errors.
"""
import asyncio
import logging
import time
from typing import Optional, Tuple

from sqlalchemy import select

from app.db.base import get_session_factory
from app.models.system_config import SystemConfig
from app.core.security import decrypt_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level cache state (D-06)
# ---------------------------------------------------------------------------

CACHE_TTL_SECONDS = 60

_cache: dict = {
    "proxy_enabled": False,
    "proxy_url": None,
    "expires_at": 0.0,
}

# T-24-02: asyncio.Lock serializes every read/write so concurrent download
# coroutines do not race on _cache dict writes.
_cache_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_proxy_config() -> Tuple[bool, Optional[str]]:
    """Return (proxy_enabled, proxy_url) for the current SystemConfig row.

    proxy_url is the DECRYPTED base URL (e.g. "http://user:pass@host:port").
    No sticky-session suffix is injected here — callers append the session ID
    per download call.

    On cache hit (within 60s of last DB load): returns immediately from memory.
    On cache miss: reads SystemConfig from DB and caches the result.
    On DB failure: logs a warning and returns (False, None) safe defaults.
    """
    async with _cache_lock:
        # Cache hit — TTL not yet expired
        if time.monotonic() < _cache["expires_at"]:
            return (_cache["proxy_enabled"], _cache["proxy_url"])

        # Cache miss — load fresh from DB
        proxy_enabled = False
        proxy_url = None

        try:
            async with get_session_factory()() as db:
                cfg = (
                    await db.execute(select(SystemConfig).limit(1))
                ).scalar_one_or_none()

                if cfg and cfg.proxy_enabled and cfg.proxy_url_encrypted:
                    proxy_enabled = True
                    proxy_url = decrypt_token(cfg.proxy_url_encrypted)

        except Exception as e:  # noqa: BLE001
            # T-24-03: DB outage or Fernet error — return safe defaults, do not raise
            logger.warning("Failed to load proxy config from DB: %s", e)

        # Update cache regardless of success/failure (T-24-04: never log proxy_url)
        _cache["proxy_enabled"] = proxy_enabled
        _cache["proxy_url"] = proxy_url
        _cache["expires_at"] = time.monotonic() + CACHE_TTL_SECONDS

        return (proxy_enabled, proxy_url)


def reset_cache() -> None:
    """Force the next get_proxy_config() call to re-query the DB.

    # Test helper — not part of public API.
    Sets expires_at to 0.0 so the TTL check fails on the next call.
    """
    _cache["expires_at"] = 0.0
