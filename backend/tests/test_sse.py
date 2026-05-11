"""
SSE Transport tests — Phase 18.

Wave 0 stubs: all 5 functions exist and fail immediately.
Wave 1 (Plan 18-02): stubs replaced with real assertions.

Test map (from 18-VALIDATION.md):
  test_sse_yields_job_update        — SSE-01, task 18-02-01
  test_sse_rejects_non_superadmin   — SSE-01, task 18-02-02
  test_sse_burst_24h_on_connect     — SSE-01, task 18-02-03
  test_sse_heartbeat_30s            — SSE-02, task 18-02-04
  test_sse_cleanup_on_disconnect    — SSE-02, task 18-02-05
"""
import pytest


@pytest.mark.asyncio
async def test_sse_yields_job_update():
    """SSE-01: pubsub message → DB fetch → job_update event yielded."""
    pytest.fail("stub — implement in Plan 18-02")


@pytest.mark.asyncio
async def test_sse_rejects_non_superadmin():
    """SSE-01: non-superuser JWT raises HTTP 403."""
    pytest.fail("stub — implement in Plan 18-02")


@pytest.mark.asyncio
async def test_sse_burst_24h_on_connect():
    """SSE-01: on connect, all jobs started_at > (now-24h) are yielded before live loop."""
    pytest.fail("stub — implement in Plan 18-02")


@pytest.mark.asyncio
async def test_sse_heartbeat_30s():
    """SSE-02: ping event yielded after 30s without pubsub message."""
    pytest.fail("stub — implement in Plan 18-02")


@pytest.mark.asyncio
async def test_sse_cleanup_on_disconnect():
    """SSE-02: pubsub.unsubscribe and pubsub.close called on disconnect."""
    pytest.fail("stub — implement in Plan 18-02")
