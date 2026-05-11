"""
SSE Transport tests — Phase 18.

Tests: SSE-01 (job_update events, 24h burst, auth) and SSE-02 (heartbeat, disconnect cleanup).

Run: cd backend && python -m pytest tests/test_sse.py -x -q
"""
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_superuser(is_superuser: bool = True, is_active: bool = True):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.is_superuser = is_superuser
    user.is_active = is_active
    return user


def _make_job(job_id=None, job_type="sync_daily", status="RUNNING"):
    job = MagicMock()
    job.id = job_id or uuid.uuid4()
    job.job_type = job_type
    job.org_id = uuid.uuid4()
    job.status = status
    job.progress_current = 3
    job.progress_total = 10
    job.started_at = datetime.utcnow()
    job.ended_at = None
    return job


def _make_request(is_disconnected_sequence=None):
    """Return a mock Request whose is_disconnected returns values from the sequence."""
    request = MagicMock()
    if is_disconnected_sequence is None:
        # Never disconnected
        request.is_disconnected = AsyncMock(return_value=False)
    else:
        request.is_disconnected = AsyncMock(side_effect=is_disconnected_sequence)
    return request


async def _collect_n_events(gen, n: int) -> list:
    """Drive an async generator, collecting up to n events before stopping."""
    events = []
    async for event in gen:
        events.append(event)
        if len(events) >= n:
            break
    return events


# ---------------------------------------------------------------------------
# test_sse_yields_job_update — SSE-01
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_yields_job_update():
    """SSE-01: pubsub message with job_id → DB fetch → job_update event yielded."""
    from app.api.v1.endpoints.jobs import sse_generator

    job = _make_job()
    job_id_str = str(job.id)

    # Mock pubsub: subscribe message (ignored) then one data message then disconnect
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {"type": "message", "data": job_id_str},  # First call: real message
        None,                                       # Second call: no message (triggers disconnect)
    ])

    # Mock Redis singleton returning mock_pubsub
    mock_redis = MagicMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

    # Mock DB session: 0 rows for 24h burst; then the job for the pubsub fetch
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    # execute for 24h burst returns empty
    burst_result = MagicMock()
    burst_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=burst_result)
    # db.get returns the job
    mock_db.get = AsyncMock(return_value=job)

    mock_session_factory = MagicMock(return_value=mock_db)

    # Disconnect after the second get_message call
    disconnected_calls = [False, False, False, False, False, True]
    request = _make_request(disconnected_calls)

    with patch("app.api.v1.endpoints.jobs.get_redis", return_value=mock_redis), \
         patch("app.api.v1.endpoints.jobs.get_session_factory", return_value=mock_session_factory), \
         patch("app.api.v1.endpoints.jobs.asyncio.sleep", new_callable=AsyncMock):
        events = await _collect_n_events(sse_generator(request, _make_superuser()), n=1)

    assert len(events) == 1
    assert events[0]["event"] == "job_update"
    payload = json.loads(events[0]["data"])
    assert payload["job_id"] == job_id_str
    assert payload["status"] == job.status
    assert payload["job_type"] == job.job_type


# ---------------------------------------------------------------------------
# test_sse_rejects_non_superadmin — SSE-01
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_rejects_non_superadmin():
    """SSE-01: non-superuser token raises HTTP 403."""
    from app.api.v1.deps import get_current_superadmin_sse

    non_superuser = _make_superuser(is_superuser=False)

    # Mock decode_token to return a valid access payload
    fake_sub = str(uuid.uuid4())
    mock_payload = {"type": "access", "sub": fake_sub}

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = non_superuser
    mock_db.execute = AsyncMock(return_value=db_result)

    request = MagicMock()
    request.query_params = {"token": "fake-valid-token"}

    with patch("app.api.v1.deps.decode_token", return_value=mock_payload):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_superadmin_sse(request=request, db=mock_db)

    assert exc_info.value.status_code == 403
    assert "SuperAdmin" in exc_info.value.detail


# ---------------------------------------------------------------------------
# test_sse_burst_24h_on_connect — SSE-01
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_burst_24h_on_connect():
    """SSE-01: on connect, all jobs started_at > (now-24h) yielded before live loop."""
    from app.api.v1.endpoints.jobs import sse_generator

    job_a = _make_job(job_type="sync_daily", status="COMPLETE")
    job_b = _make_job(job_type="download", status="RUNNING")

    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    mock_pubsub.get_message = AsyncMock(return_value=None)

    mock_redis = MagicMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    burst_result = MagicMock()
    burst_result.scalars.return_value.all.return_value = [job_a, job_b]
    mock_db.execute = AsyncMock(return_value=burst_result)
    mock_db.get = AsyncMock(return_value=None)

    mock_session_factory = MagicMock(return_value=mock_db)

    # Disconnect immediately after burst to prevent entering live loop
    disconnected_calls = [False, False, True] + [True] * 20
    request = _make_request(disconnected_calls)

    with patch("app.api.v1.endpoints.jobs.get_redis", return_value=mock_redis), \
         patch("app.api.v1.endpoints.jobs.get_session_factory", return_value=mock_session_factory), \
         patch("app.api.v1.endpoints.jobs.asyncio.sleep", new_callable=AsyncMock):
        events = await _collect_n_events(sse_generator(request, _make_superuser()), n=10)

    assert len(events) == 2, f"Expected 2 burst events, got {len(events)}"
    assert all(e["event"] == "job_update" for e in events)
    job_ids_yielded = {json.loads(e["data"])["job_id"] for e in events}
    assert str(job_a.id) in job_ids_yielded
    assert str(job_b.id) in job_ids_yielded


# ---------------------------------------------------------------------------
# test_sse_heartbeat_30s — SSE-02
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_heartbeat_30s():
    """SSE-02: ping event yielded after 30s without pubsub messages."""
    from app.api.v1.endpoints.jobs import sse_generator

    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    mock_pubsub.get_message = AsyncMock(return_value=None)

    mock_redis = MagicMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    burst_result = MagicMock()
    burst_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=burst_result)

    mock_session_factory = MagicMock(return_value=mock_db)

    # Fast-forward: first utcnow() returns T=0; next returns T=31s (triggers ping)
    t0 = datetime(2026, 1, 1, 0, 0, 0)
    t_plus_31 = t0 + timedelta(seconds=31)
    utcnow_sequence = [t0, t0, t_plus_31, t_plus_31]

    # Disconnect after the ping is triggered
    disconnected_calls = [False] * 4 + [True] * 20
    request = _make_request(disconnected_calls)

    with patch("app.api.v1.endpoints.jobs.get_redis", return_value=mock_redis), \
         patch("app.api.v1.endpoints.jobs.get_session_factory", return_value=mock_session_factory), \
         patch("app.api.v1.endpoints.jobs.asyncio.sleep", new_callable=AsyncMock), \
         patch("app.api.v1.endpoints.jobs.datetime") as mock_dt:
        mock_dt.utcnow = MagicMock(side_effect=utcnow_sequence)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        events = await _collect_n_events(sse_generator(request, _make_superuser()), n=1)

    assert len(events) >= 1
    ping_events = [e for e in events if e["event"] == "ping"]
    assert len(ping_events) >= 1, "Expected at least one ping event"
    ping_data = json.loads(ping_events[0]["data"])
    assert "ts" in ping_data


# ---------------------------------------------------------------------------
# test_sse_cleanup_on_disconnect — SSE-02
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_cleanup_on_disconnect():
    """SSE-02: pubsub.unsubscribe and pubsub.close each called once on disconnect."""
    from app.api.v1.endpoints.jobs import sse_generator

    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    mock_pubsub.get_message = AsyncMock(return_value=None)

    mock_redis = MagicMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    burst_result = MagicMock()
    burst_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=burst_result)

    mock_session_factory = MagicMock(return_value=mock_db)

    # Disconnect immediately upon entering the subscription loop
    disconnected_calls = [False, True] + [True] * 20
    request = _make_request(disconnected_calls)

    with patch("app.api.v1.endpoints.jobs.get_redis", return_value=mock_redis), \
         patch("app.api.v1.endpoints.jobs.get_session_factory", return_value=mock_session_factory), \
         patch("app.api.v1.endpoints.jobs.asyncio.sleep", new_callable=AsyncMock):
        # Exhaust generator (it should exit cleanly)
        events = []
        async for event in sse_generator(request, _make_superuser()):
            events.append(event)

    mock_pubsub.unsubscribe.assert_awaited_once()
    mock_pubsub.close.assert_awaited_once()
