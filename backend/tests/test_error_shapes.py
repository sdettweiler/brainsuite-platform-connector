"""
Tests for QUAL-03: Consistent error response shapes.

Verifies that:
- All 4xx error responses use {"detail": "..."} shape (not {"error": "..."})
- DELETE /platforms/apps/{app_id} returns 204 with no body
- POST /auth/logout returns 204 with no body
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(is_admin: bool = True):
    """Return a minimal mock User suitable for auth tests."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.is_active = True
    user.organization_id = uuid.uuid4()
    user.role = "ADMIN" if is_admin else "STANDARD"
    return user


def _make_brainsuite_app(org_id):
    """Return a minimal mock BrainsuiteApp DB row."""
    app = MagicMock()
    app.id = uuid.uuid4()
    app.organization_id = org_id
    app.name = "Test App"
    app.is_active = True
    return app


def _make_db(return_value=None):
    """Return an AsyncMock DB session with configurable scalar result."""
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = return_value

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=scalar_result)
    mock_db.get = AsyncMock(return_value=return_value)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    return mock_db


# ---------------------------------------------------------------------------
# Test 1: Error responses use {"detail": "..."} shape, not {"error": "..."}
# ---------------------------------------------------------------------------

def test_error_response_has_detail_key(app):
    """All 4xx error responses include a top-level 'detail' key in the JSON body."""
    from fastapi.testclient import TestClient

    # Use a DB that returns no user → triggers 401 "Invalid credentials"
    mock_db = _make_db(return_value=None)

    async def override_get_db():
        yield mock_db

    from app.db.base import get_db
    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrongpassword"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401, (
        f"Expected 401 for invalid credentials, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert "detail" in body, (
        f"Expected 'detail' key in error response body, got: {body}"
    )
    assert "error" not in body, (
        f"Response body should not contain 'error' key, got: {body}"
    )


# ---------------------------------------------------------------------------
# Test 2: DELETE /platforms/apps/{app_id} returns 204 with no body
# ---------------------------------------------------------------------------

def test_delete_returns_204(app):
    """DELETE /platforms/apps/{app_id} returns HTTP 204 with empty body on success."""
    from fastapi.testclient import TestClient
    from app.core.security import create_access_token

    user = _make_user(is_admin=True)
    brainsuite_app = _make_brainsuite_app(user.organization_id)
    # db.get returns the app record
    mock_db = _make_db(return_value=brainsuite_app)

    async def override_get_db():
        yield mock_db

    async def override_current_admin():
        return user

    from app.db.base import get_db
    from app.api.v1.deps import get_current_admin

    access_token = create_access_token({"sub": str(user.id)})
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_admin] = override_current_admin
    try:
        client = TestClient(app, raise_server_exceptions=True)
        response = client.delete(
            f"/api/v1/platforms/apps/{brainsuite_app.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_admin, None)

    assert response.status_code == 204, (
        f"Expected 204 from DELETE /platforms/apps/{{id}}, got {response.status_code}: {response.text}"
    )
    # 204 must have no body
    assert response.text == "" or response.content == b"", (
        f"Expected empty body for 204 response, got: {response.text!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: POST /auth/logout returns 204 No Content
# ---------------------------------------------------------------------------

def test_logout_returns_204(app):
    """POST /api/v1/auth/logout returns HTTP 204 (not 200) on success."""
    from fastapi.testclient import TestClient
    from app.core.security import create_access_token, create_refresh_token

    user = _make_user()
    mock_db = _make_db(return_value=None)  # no refresh token record found — still succeeds

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    from app.db.base import get_db
    from app.api.v1.deps import get_current_user

    access_token = create_access_token({"sub": str(user.id)})
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    try:
        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 204, (
        f"Expected 204 from POST /auth/logout, got {response.status_code}: {response.text}"
    )
    # 204 must have no body
    assert response.text == "" or response.content == b"", (
        f"Expected empty body for 204 response, got: {response.text!r}"
    )
