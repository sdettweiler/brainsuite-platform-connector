"""
Test stubs for SEC-05: OAuth redirect URI hardening.

Implementation target: plan 02-01 Task 2 (unskip and implement).

All tests are skipped until implementation is complete.
"""
import pytest


@pytest.mark.skip(reason="stub - implementation in plan 02-01 Task 2")
def test_redirect_uri_ignores_forwarded_host():
    """get_redirect_uri_from_request ignores x-forwarded-host and does not use it in the returned URI."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-01 Task 2")
def test_redirect_uri_uses_base_url():
    """get_redirect_uri_from_request returns a URI whose prefix matches settings.BASE_URL."""
    pass
