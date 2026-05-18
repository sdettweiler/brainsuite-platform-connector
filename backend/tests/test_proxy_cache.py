"""
Tests for Phase 24, Plan 01 | PERF-04

Behaviors tested:
1. Cache miss loads from DB and returns (True, url) when proxy_enabled=True
2. Cache miss returns (False, None) when proxy_enabled=False
3. Cache miss returns (False, None) when SystemConfig row is absent
4. Cache hit within TTL skips DB entirely
5. Cache expires after TTL and re-queries DB
6. DB error returns (False, None) and logs a warning without raising
7. Concurrent calls serialize through asyncio.Lock — DB loaded at most once on miss
"""
import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.sync.proxy_cache import get_proxy_config, reset_cache, CACHE_TTL_SECONDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_factory_mock(config_row):
    """Return a mock that behaves as get_session_factory() returning an async CM.

    Usage pattern in proxy_cache.py:
        async with get_session_factory()() as db:
            cfg = (await db.execute(...)).scalar_one_or_none()
    """
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = config_row

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=scalar_result)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    # get_session_factory()() returns mock_db (an async context manager)
    session_instance = MagicMock(return_value=mock_db)
    mock_factory = MagicMock(return_value=session_instance)
    return mock_factory, mock_db


def _make_system_config(proxy_enabled: bool, proxy_url_encrypted=None):
    cfg = MagicMock()
    cfg.proxy_enabled = proxy_enabled
    cfg.proxy_url_encrypted = proxy_url_encrypted
    return cfg


# ---------------------------------------------------------------------------
# Test 1: cache miss — proxy enabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_miss_loads_from_db_when_proxy_enabled():
    """First call with proxy_enabled=True returns (True, decrypted_url) from DB."""
    reset_cache()

    cfg = _make_system_config(proxy_enabled=True, proxy_url_encrypted="enc")
    mock_factory, _ = _make_session_factory_mock(cfg)

    with patch("app.services.sync.proxy_cache.get_session_factory", mock_factory):
        with patch("app.services.sync.proxy_cache.decrypt_token", return_value="http://user:pass@proxy.example.com:8080"):
            result = await get_proxy_config()

    assert result == (True, "http://user:pass@proxy.example.com:8080"), f"Unexpected result: {result}"


# ---------------------------------------------------------------------------
# Test 2: cache miss — proxy disabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_miss_returns_defaults_when_proxy_disabled():
    """First call with proxy_enabled=False returns (False, None)."""
    reset_cache()

    cfg = _make_system_config(proxy_enabled=False, proxy_url_encrypted="enc")
    mock_factory, _ = _make_session_factory_mock(cfg)

    with patch("app.services.sync.proxy_cache.get_session_factory", mock_factory):
        with patch("app.services.sync.proxy_cache.decrypt_token", return_value="http://user:pass@proxy.example.com:8080"):
            result = await get_proxy_config()

    assert result == (False, None), f"Expected (False, None), got {result}"


# ---------------------------------------------------------------------------
# Test 3: cache miss — no DB row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_miss_returns_defaults_when_no_row():
    """First call when SystemConfig row is absent returns (False, None)."""
    reset_cache()

    mock_factory, _ = _make_session_factory_mock(config_row=None)

    with patch("app.services.sync.proxy_cache.get_session_factory", mock_factory):
        result = await get_proxy_config()

    assert result == (False, None), f"Expected (False, None), got {result}"


# ---------------------------------------------------------------------------
# Test 4: cache hit within TTL skips DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_within_ttl_skips_db():
    """Second call within TTL must not invoke get_session_factory again."""
    reset_cache()

    cfg = _make_system_config(proxy_enabled=True, proxy_url_encrypted="enc")
    mock_factory, _ = _make_session_factory_mock(cfg)

    with patch("app.services.sync.proxy_cache.get_session_factory", mock_factory):
        with patch("app.services.sync.proxy_cache.decrypt_token", return_value="http://user:pass@proxy.example.com:8080"):
            # First call — cache miss, DB load
            await get_proxy_config()
            # Second call — should be cache hit, no DB access
            await get_proxy_config()

    # get_session_factory was called only once (for the first miss)
    assert mock_factory.call_count == 1, f"Expected 1 DB call, got {mock_factory.call_count}"


# ---------------------------------------------------------------------------
# Test 5: cache expires after TTL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_expires_after_ttl():
    """After TTL expires, next call re-queries the DB."""
    reset_cache()

    cfg = _make_system_config(proxy_enabled=True, proxy_url_encrypted="enc")
    mock_factory, _ = _make_session_factory_mock(cfg)

    # Monotonic clock values supplied in order.
    # proxy_cache.py calls time.monotonic() twice per get_proxy_config() call:
    #   [0] TTL check (first call)          -> 1000.0  (expires_at=0, so miss)
    #   [1] TTL write (first call)          -> 1000.0  -> expires_at = 1060.0
    #   [2] TTL check (second call)         -> 2000.0  (2000.0 < 1060.0? No -> miss)
    #   [3] TTL write (second call)         -> 2000.0  -> expires_at = 2060.0
    mono_values = iter([1000.0, 1000.0, 2000.0, 2000.0])

    with patch("app.services.sync.proxy_cache.get_session_factory", mock_factory):
        with patch("app.services.sync.proxy_cache.decrypt_token", return_value="http://proxy"):
            with patch("app.services.sync.proxy_cache.time.monotonic", side_effect=mono_values):
                await get_proxy_config()   # first call — miss (expires_at=0 < 1000)
                await get_proxy_config()   # second call — miss (2000 > 1060)

    assert mock_factory.call_count == 2, f"Expected 2 DB calls after TTL, got {mock_factory.call_count}"


# ---------------------------------------------------------------------------
# Test 6: DB error returns defaults + logs warning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_db_error_returns_defaults_and_logs_warning(caplog):
    """DB error returns (False, None) without raising; warning is logged."""
    reset_cache()

    def raise_error():
        raise RuntimeError("boom")

    with patch("app.services.sync.proxy_cache.get_session_factory", side_effect=raise_error):
        with caplog.at_level(logging.WARNING, logger="app.services.sync.proxy_cache"):
            result = await get_proxy_config()

    assert result == (False, None), f"Expected (False, None) on DB error, got {result}"
    assert any("Failed to load proxy config" in r.message for r in caplog.records), (
        f"Expected warning not found in logs: {[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# Test 7: concurrent calls serialize through Lock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_calls_serialize_db_load():
    """Two concurrent get_proxy_config() calls must invoke DB at most once on cache miss."""
    reset_cache()

    cfg = _make_system_config(proxy_enabled=True, proxy_url_encrypted="enc")
    mock_factory, _ = _make_session_factory_mock(cfg)

    with patch("app.services.sync.proxy_cache.get_session_factory", mock_factory):
        with patch("app.services.sync.proxy_cache.decrypt_token", return_value="http://user:pass@proxy.example.com:8080"):
            results = await asyncio.gather(get_proxy_config(), get_proxy_config())

    # Both calls should return the same result
    assert results[0] == results[1], f"Concurrent calls returned different results: {results}"

    # The lock ensures only one DB load occurred even on concurrent cache miss
    assert mock_factory.call_count <= 1, (
        f"Expected at most 1 DB call (lock serializes), got {mock_factory.call_count}"
    )
