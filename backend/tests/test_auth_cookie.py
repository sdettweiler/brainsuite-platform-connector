"""
Tests for SEC-02: HttpOnly cookie-based refresh token delivery.

Verifies that:
- Login sets refresh_token as httpOnly cookie (not in JSON body)
- Refresh reads from cookie only (rejects body-only tokens)
- Logout clears cookie and returns 204
- Each refresh issues a new cookie value (token rotation)
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user():
    """Return a minimal mock User object suitable for auth tests."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.password_hash = "$2b$12$fake_hash_that_gets_mocked"
    user.is_active = True
    user.is_two_factor_enabled = False
    user.last_login = None
    user.organization_id = uuid.uuid4()
    return user


def _make_rt_record(token: str, user_id):
    """Return a minimal mock RefreshToken DB row."""
    record = MagicMock()
    record.user_id = user_id
    record.token_hash = hashlib.sha256(token.encode()).hexdigest()
    # Use UTC-aware datetime to match the comparison in auth.py
    record.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    record.is_revoked = False
    return record


def _make_db(return_value=None):
    """Return an AsyncMock DB session with a configurable scalar result."""
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = return_value

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=scalar_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    return mock_db


# ---------------------------------------------------------------------------
# Test 1: Login sets httpOnly cookie — refresh_token NOT in response body
# ---------------------------------------------------------------------------

def test_login_sets_httponly_cookie(app):
    user = _make_user()
    mock_db = _make_db(return_value=user)

    async def override_get_db():
        yield mock_db

    from app.db.base import get_db

    with patch("app.api.v1.endpoints.auth.verify_password", return_value=True):
        app.dependency_overrides[get_db] = override_get_db
        try:
            from fastapi.testclient import TestClient
            client = TestClient(app, raise_server_exceptions=True)
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "secret"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    body = response.json()

    # access_token must be present in body
    assert "access_token" in body, "access_token missing from login response body"
    # refresh_token must NOT be present in body
    assert "refresh_token" not in body, (
        "refresh_token should not appear in the JSON body — it must only be set as a cookie"
    )

    # httpOnly cookie must be set with all required attributes
    cookie_header = response.headers.get("set-cookie", "")
    assert "refresh_token=" in cookie_header, (
        f"refresh_token cookie not set. set-cookie: {cookie_header!r}"
    )
    assert "httponly" in cookie_header.lower(), (
        f"Cookie missing httponly flag. set-cookie: {cookie_header!r}"
    )
    assert "samesite=lax" in cookie_header.lower(), (
        f"Cookie missing samesite=lax. set-cookie: {cookie_header!r}"
    )
    assert "path=/api/v1/auth" in cookie_header.lower(), (
        f"Cookie missing path=/api/v1/auth. set-cookie: {cookie_header!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: Refresh reads cookie and returns 200 with new cookie
# ---------------------------------------------------------------------------

def test_refresh_reads_cookie_only(app):
    user = _make_user()

    from app.core.security import create_refresh_token
    rt_value = create_refresh_token({"sub": str(user.id)})
    rt_record = _make_rt_record(rt_value, user.id)

    mock_db = _make_db(return_value=rt_record)

    async def override_get_db():
        yield mock_db

    from app.db.base import get_db
    app.dependency_overrides[get_db] = override_get_db
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": rt_value},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, (
        f"Expected 200 from /auth/refresh with valid cookie, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert "access_token" in body, "access_token missing from refresh response body"

    # A new refresh_token cookie must be set
    cookie_header = response.headers.get("set-cookie", "")
    assert "refresh_token=" in cookie_header, (
        f"New refresh_token cookie not set after refresh. set-cookie: {cookie_header!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: Refresh rejects token supplied only in request body (no cookie)
# ---------------------------------------------------------------------------

def test_refresh_rejects_body_token(app):
    from fastapi.testclient import TestClient
    client = TestClient(app, raise_server_exceptions=False)

    from app.core.security import create_refresh_token
    rt_value = create_refresh_token({"sub": str(uuid.uuid4())})

    # No cookie — token is only in JSON body (old insecure pattern)
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": rt_value},
    )

    assert response.status_code == 401, (
        f"Expected 401 when refresh_token supplied only in body, got {response.status_code}: {response.text}"
    )
    detail = response.json().get("detail", "")
    assert "No refresh token" in detail, (
        f"Expected 'No refresh token' in detail, got: {detail!r}"
    )


# ---------------------------------------------------------------------------
# Test 4: Logout clears cookie and returns 204 No Content
# ---------------------------------------------------------------------------

def test_logout_clears_cookie(app):
    user = _make_user()

    from app.core.security import create_refresh_token, create_access_token
    access_token = create_access_token({"sub": str(user.id)})
    rt_value = create_refresh_token({"sub": str(user.id)})
    rt_record = _make_rt_record(rt_value, user.id)

    mock_db = _make_db(return_value=rt_record)

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    from app.db.base import get_db
    from app.api.v1.deps import get_current_user
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            cookies={"refresh_token": rt_value},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 204, (
        f"Expected 204 No Content from /auth/logout, got {response.status_code}: {response.text}"
    )

    # The response must include a set-cookie that clears the refresh_token
    cookie_header = response.headers.get("set-cookie", "")
    assert "refresh_token=" in cookie_header, (
        f"Expected set-cookie header to clear the cookie. set-cookie: {cookie_header!r}"
    )
    # FastAPI delete_cookie sets Max-Age=0
    assert "max-age=0" in cookie_header.lower() or "expires=" in cookie_header.lower(), (
        f"Cookie not properly cleared (expected max-age=0). set-cookie: {cookie_header!r}"
    )


# ---------------------------------------------------------------------------
# Test 5: Each refresh rotates to a new cookie value
# ---------------------------------------------------------------------------

def test_refresh_rotates_token(app):
    user = _make_user()

    from app.core.security import create_refresh_token
    first_rt = create_refresh_token({"sub": str(user.id)})
    first_record = _make_rt_record(first_rt, user.id)

    mock_db = _make_db(return_value=first_record)

    async def override_get_db():
        yield mock_db

    # Mock create_refresh_token so the rotated token is guaranteed to be
    # different from the original, regardless of how fast the test runs
    # (JWT exp may be identical within the same second).
    rotated_rt = "rotated_refresh_token_value_different_from_original"

    from app.db.base import get_db
    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.v1.endpoints.auth.create_refresh_token", return_value=rotated_rt):
            from fastapi.testclient import TestClient
            client = TestClient(app, raise_server_exceptions=True)
            response = client.post(
                "/api/v1/auth/refresh",
                cookies={"refresh_token": first_rt},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, (
        f"Expected 200 from /auth/refresh, got {response.status_code}: {response.text}"
    )

    cookie_header = response.headers.get("set-cookie", "")
    assert "refresh_token=" in cookie_header, (
        f"No new refresh_token cookie after refresh. set-cookie: {cookie_header!r}"
    )

    # Extract the new token value from the set-cookie header
    # Header format: refresh_token=<value>; Path=...; Max-Age=...
    new_token_part = [
        segment.strip()
        for segment in cookie_header.split(";")
        if segment.strip().lower().startswith("refresh_token=")
    ]
    assert new_token_part, f"Could not parse refresh_token from cookie: {cookie_header!r}"
    new_token_value = new_token_part[0].split("=", 1)[1]

    assert new_token_value != first_rt, (
        "Token rotation failed: new refresh_token cookie is identical to the one sent"
    )
    assert new_token_value == rotated_rt, (
        f"Expected rotated token '{rotated_rt}', got: '{new_token_value}'"
    )
