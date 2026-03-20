"""
Test stubs for SEC-04: Path traversal prevention in the /objects/ endpoint.

Implementation target: plan 02-01 Task 2 (unskip and implement).

All tests are skipped until implementation is complete.
"""
import pytest


@pytest.mark.skip(reason="stub - implementation in plan 02-01 Task 2")
def test_traversal_attack_returns_400():
    """GET /objects/../../etc/passwd returns HTTP 400 with detail 'Invalid asset path'."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-01 Task 2")
def test_valid_asset_path_succeeds():
    """GET /objects/creatives/valid-image.jpg returns 200 (or proxies correctly) for a legitimate path."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-01 Task 2")
def test_double_dot_encoded_returns_400():
    """GET /objects/%2e%2e%2fetc%2fpasswd (URL-encoded traversal) returns HTTP 400."""
    pass
