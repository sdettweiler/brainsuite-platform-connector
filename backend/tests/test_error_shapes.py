"""
Test stubs for QUAL-03: Consistent error response shapes.

Implementation target: plan 02-04.

All tests are skipped until implementation is complete.
"""
import pytest


@pytest.mark.skip(reason="stub - implementation in plan 02-04")
def test_error_response_has_detail_key():
    """All 4xx error responses include a top-level 'detail' key in the JSON body."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-04")
def test_delete_returns_204():
    """DELETE endpoints return HTTP 204 with no body on successful deletion."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-04")
def test_logout_returns_204():
    """POST /api/v1/auth/logout returns HTTP 204 (not 200) on success."""
    pass
