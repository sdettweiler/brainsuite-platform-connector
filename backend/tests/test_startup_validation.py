"""
Test stubs for SEC-03: Fernet key startup validation.

Implementation target: plan 02-01 Task 2 (unskip and implement).

All tests are skipped until implementation is complete.
"""
import pytest


@pytest.mark.skip(reason="stub - implementation in plan 02-01 Task 2")
def test_missing_fernet_key_raises():
    """Creating Settings with TOKEN_ENCRYPTION_KEY empty or missing raises ValidationError."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-01 Task 2")
def test_malformed_fernet_key_raises():
    """Creating Settings with TOKEN_ENCRYPTION_KEY='not-a-valid-key' raises ValidationError."""
    pass


@pytest.mark.skip(reason="stub - implementation in plan 02-01 Task 2")
def test_valid_fernet_key_passes():
    """Creating Settings with a properly encoded Fernet key succeeds without error."""
    pass
