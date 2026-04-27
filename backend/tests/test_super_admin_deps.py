"""
Tests for Task 14-01-01 | COOK-01 | T-14-01

Behavior: get_current_superadmin raises HTTP 403 when current_user.is_superuser is False
"""
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException


def _make_user(is_superuser: bool = False):
    user = MagicMock()
    user.is_superuser = is_superuser
    user.is_active = True
    return user


@pytest.mark.asyncio
async def test_get_current_superadmin_raises_403_for_non_superuser():
    """get_current_superadmin raises HTTP 403 when current_user.is_superuser is False."""
    from app.api.v1.deps import get_current_superadmin

    non_superuser = _make_user(is_superuser=False)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_superadmin(current_user=non_superuser)

    assert exc_info.value.status_code == 403
    assert "SuperAdmin" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_superadmin_returns_user_for_superuser():
    """get_current_superadmin returns the user when is_superuser is True."""
    from app.api.v1.deps import get_current_superadmin

    superuser = _make_user(is_superuser=True)

    result = await get_current_superadmin(current_user=superuser)

    assert result is superuser


@pytest.mark.asyncio
async def test_get_current_superadmin_no_db_parameter():
    """get_current_superadmin does NOT accept a db parameter (lighter than get_current_admin)."""
    import inspect
    from app.api.v1.deps import get_current_superadmin

    sig = inspect.signature(get_current_superadmin)
    param_names = list(sig.parameters.keys())

    assert "db" not in param_names, (
        "get_current_superadmin must NOT accept a db parameter"
    )
