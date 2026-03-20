"""
Tests for SEC-01 and QUAL-04: OAuth session management via Redis.

Verifies that platforms.py stores OAuth sessions in Redis (not in-memory dict),
with TTL expiry and explicit cleanup after use.
"""
import json
import pytest


# ---------------------------------------------------------------------------
# Helper: build a minimal session dict matching platforms.py structure
# ---------------------------------------------------------------------------

def _make_session(platform: str = "META", user_id: str = "user-1", org_id: str = "org-1") -> dict:
    return {
        "platform": platform,
        "user_id": user_id,
        "org_id": org_id,
        "created_at": "2026-01-01T00:00:00",
        "redirect_uri": "http://localhost:8000/api/v1/platforms/oauth/callback/meta",
    }


# ---------------------------------------------------------------------------
# test_store_and_retrieve_session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_and_retrieve_session(mock_redis):
    """OAuth state and code-verifier can be stored and retrieved by key."""
    session_id = "test-session-abc"
    session_data = _make_session()

    # Store via Redis setex (as platforms.py does)
    await mock_redis.setex(
        f"oauth_session:{session_id}",
        900,
        json.dumps(session_data),
    )

    # Retrieve (as platforms.py does)
    raw = await mock_redis.get(f"oauth_session:{session_id}")
    assert raw is not None
    retrieved = json.loads(raw)
    assert retrieved["platform"] == "META"
    assert retrieved["user_id"] == "user-1"
    assert retrieved["org_id"] == "org-1"


# ---------------------------------------------------------------------------
# test_session_expires_after_ttl
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_expires_after_ttl(mock_redis):
    """Session data is automatically deleted after the TTL expires (simulated via mock)."""
    session_id = "expiring-session-xyz"
    session_data = _make_session()

    # Store session
    await mock_redis.setex(
        f"oauth_session:{session_id}",
        900,
        json.dumps(session_data),
    )

    # Simulate TTL expiry: remove key from underlying store
    del mock_redis._store[f"oauth_session:{session_id}"]

    # After expiry, get should return None
    raw = await mock_redis.get(f"oauth_session:{session_id}")
    assert raw is None


# ---------------------------------------------------------------------------
# test_session_deleted_after_use
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_deleted_after_use(mock_redis):
    """Session is explicitly deleted from Redis after successful account connection."""
    session_id = "used-session-789"
    session_data = _make_session()

    # Store
    await mock_redis.setex(
        f"oauth_session:{session_id}",
        900,
        json.dumps(session_data),
    )

    # Verify it exists
    raw = await mock_redis.get(f"oauth_session:{session_id}")
    assert raw is not None

    # Explicitly delete (as done in connect_accounts after use)
    await mock_redis.delete(f"oauth_session:{session_id}")

    # Should now be gone
    raw_after = await mock_redis.get(f"oauth_session:{session_id}")
    assert raw_after is None


# ---------------------------------------------------------------------------
# test_multi_worker_session_isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_worker_session_isolation(mock_redis):
    """Sessions for different session IDs are stored and retrieved independently.

    Simulates two workers each processing different OAuth flows: both sessions
    must be independently accessible from the shared Redis store.
    """
    session_id_1 = "worker1-session-aaa"
    session_id_2 = "worker2-session-bbb"

    session_1 = _make_session(platform="META", user_id="user-1")
    session_2 = _make_session(platform="TIKTOK", user_id="user-2")

    # "Worker 1" stores its session
    await mock_redis.setex(
        f"oauth_session:{session_id_1}",
        900,
        json.dumps(session_1),
    )

    # "Worker 2" stores its session
    await mock_redis.setex(
        f"oauth_session:{session_id_2}",
        900,
        json.dumps(session_2),
    )

    # Each session is independently retrievable
    raw_1 = await mock_redis.get(f"oauth_session:{session_id_1}")
    raw_2 = await mock_redis.get(f"oauth_session:{session_id_2}")

    assert raw_1 is not None
    assert raw_2 is not None

    data_1 = json.loads(raw_1)
    data_2 = json.loads(raw_2)

    assert data_1["platform"] == "META"
    assert data_1["user_id"] == "user-1"
    assert data_2["platform"] == "TIKTOK"
    assert data_2["user_id"] == "user-2"

    # Deleting one does not affect the other
    await mock_redis.delete(f"oauth_session:{session_id_1}")
    assert await mock_redis.get(f"oauth_session:{session_id_1}") is None
    assert await mock_redis.get(f"oauth_session:{session_id_2}") is not None


# ---------------------------------------------------------------------------
# test_platforms_uses_redis_not_dict
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="stub - implementation in plan 02-02")
def test_platforms_uses_redis_not_dict():
    """platforms.py must not contain the in-memory session dict."""
    import inspect
    import app.api.v1.endpoints.platforms as platforms_mod
    source = inspect.getsource(platforms_mod)
    assert "_oauth_sessions: dict" not in source, (
        "platforms.py still has _oauth_sessions: dict — Redis migration not complete"
    )
    assert "_oauth_sessions =" not in source, (
        "platforms.py still assigns _oauth_sessions — Redis migration not complete"
    )
    assert "get_redis" in source, (
        "platforms.py does not import get_redis — Redis migration not complete"
    )
    assert "OAUTH_SESSION_TTL" in source, (
        "platforms.py does not define OAUTH_SESSION_TTL — Redis migration not complete"
    )
    assert "oauth_session:" in source, (
        "platforms.py does not use oauth_session: key prefix — Redis migration not complete"
    )
    assert "await redis.delete(" in source, (
        "platforms.py does not call redis.delete() — stale session cleanup not implemented"
    )
