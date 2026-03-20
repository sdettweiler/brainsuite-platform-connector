"""
Test stubs for SEC-01 and QUAL-04: OAuth session management.

Implementation target: plan 02-02 (Redis-backed OAuth session store).

All tests are skipped until implementation is complete.
"""
import pytest


@pytest.mark.skip(reason="stub - implementation in plan 02-02")
def test_store_and_retrieve_session():
    """OAuth state and code-verifier can be stored and retrieved by key."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-02")
def test_session_expires_after_ttl():
    """Session data is automatically deleted after the TTL expires."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-02")
def test_session_deleted_after_use():
    """Session is deleted from Redis after a single successful retrieval (one-time use)."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-02")
def test_multi_worker_session_isolation():
    """Sessions created by one worker are visible to another worker (shared Redis store)."""
    pass
