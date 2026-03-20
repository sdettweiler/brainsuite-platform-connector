"""
Test stubs for SEC-02: HttpOnly cookie-based token delivery.

Implementation target: plan 02-03.

All tests are skipped until implementation is complete.
"""
import pytest


@pytest.mark.skip(reason="stub - implementation in plan 02-03")
def test_login_sets_httponly_cookie():
    """POST /api/v1/auth/login sets an HttpOnly cookie containing the access token."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-03")
def test_refresh_reads_cookie_only():
    """POST /api/v1/auth/refresh reads the refresh token from the cookie, not the request body."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-03")
def test_refresh_rejects_body_token():
    """POST /api/v1/auth/refresh ignores (or rejects) a refresh token supplied in the JSON body."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-03")
def test_logout_clears_cookie():
    """POST /api/v1/auth/logout clears the access-token cookie (Max-Age=0 or expires in the past)."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-03")
def test_refresh_rotates_token():
    """Each successful refresh issues a new token pair and invalidates the previous refresh token."""
    pass
