"""
Tests for Tasks 14-02-03 and 14-02-04 | COOK-02

Behaviors:
- GET /super-admin/youtube-cookies returns only health status (valid/expired/missing),
  never plaintext cookie content
- PUT /super-admin/youtube-cookies updates the slot and returns health status
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_superuser():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "admin@example.com"
    user.is_superuser = True
    user.is_active = True
    return user


def _make_system_config(primary_enc=None, backup_enc=None):
    config = MagicMock()
    config.youtube_cookies_encrypted = primary_enc
    config.youtube_cookies_backup_encrypted = backup_enc
    return config


def _make_db_with_config(config):
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = config

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=scalar_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    return mock_db


# ---------------------------------------------------------------------------
# Gap 5: GET /youtube-cookies never returns plaintext (14-02-03)
# ---------------------------------------------------------------------------

def test_get_cookies_no_plaintext(app):
    """GET /super-admin/youtube-cookies returns only health status, never cookie content."""
    from app.core.security import encrypt_token
    from app.db.base import get_db
    from app.api.v1.deps import get_current_superadmin

    # Encrypt a real-looking cookie so it can be decrypted for health check
    cookie_content = (
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t9999999999\tYSC\tsensitive_cookie_value_abc123\n"
    )
    encrypted = encrypt_token(cookie_content)

    config = _make_system_config(primary_enc=encrypted)
    mock_db = _make_db_with_config(config)

    async def override_get_db():
        yield mock_db

    async def override_superadmin():
        return _make_superuser()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_superadmin] = override_superadmin
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/api/v1/super-admin/youtube-cookies")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()

    # Response must have primary and backup keys
    assert "primary" in body, f"Response missing 'primary' key: {body}"
    assert "backup" in body, f"Response missing 'backup' key: {body}"

    # Each slot must have only a 'status' field
    assert set(body["primary"].keys()) == {"status"}, (
        f"primary slot must only contain 'status', got: {set(body['primary'].keys())}"
    )
    assert set(body["backup"].keys()) == {"status"}, (
        f"backup slot must only contain 'status', got: {set(body['backup'].keys())}"
    )

    # Status values must be one of the allowed literals
    allowed = {"valid", "expired", "missing"}
    assert body["primary"]["status"] in allowed, (
        f"primary status must be one of {allowed}, got: {body['primary']['status']!r}"
    )
    assert body["backup"]["status"] in allowed, (
        f"backup status must be one of {allowed}, got: {body['backup']['status']!r}"
    )

    # The raw cookie content must NOT appear anywhere in the response body
    response_text = response.text
    assert "sensitive_cookie_value_abc123" not in response_text, (
        "Plaintext cookie content leaked into GET response"
    )
    assert "Netscape" not in response_text, (
        "Netscape cookie header leaked into GET response"
    )


def test_get_cookies_missing_when_no_config(app):
    """GET /super-admin/youtube-cookies returns missing for both slots when SystemConfig is empty."""
    from app.db.base import get_db
    from app.api.v1.deps import get_current_superadmin

    mock_db = _make_db_with_config(None)  # No system config row

    async def override_get_db():
        yield mock_db

    async def override_superadmin():
        return _make_superuser()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_superadmin] = override_superadmin
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/api/v1/super-admin/youtube-cookies")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)

    assert response.status_code == 200
    body = response.json()
    assert body["primary"]["status"] == "missing"
    assert body["backup"]["status"] == "missing"


def test_get_cookies_requires_superadmin(app):
    """GET /super-admin/youtube-cookies returns 403 for non-SuperAdmin users."""
    from app.db.base import get_db
    from app.api.v1.deps import get_current_superadmin
    from fastapi import HTTPException

    async def override_get_db():
        yield AsyncMock()

    async def override_non_superadmin():
        raise HTTPException(status_code=403, detail="SuperAdmin privileges required")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_superadmin] = override_non_superadmin
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/super-admin/youtube-cookies")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Gap 6: PUT /youtube-cookies updates slot and returns health status (14-02-04)
# ---------------------------------------------------------------------------

def test_put_cookies(app):
    """PUT /super-admin/youtube-cookies encrypts cookie and returns health status."""
    from app.db.base import get_db
    from app.api.v1.deps import get_current_superadmin

    # Start with empty config (no cookies set yet)
    config = _make_system_config(primary_enc=None, backup_enc=None)

    # After PUT, the encrypted value will be set on the config object.
    # Simulate db.refresh by having config reflect the updated encrypted value.
    from app.core.security import encrypt_token

    new_cookie = (
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t9999999999\tYSC\tnew_cookie_val\n"
    )

    def fake_add(obj):
        # Simulate that encrypt_token was called and the value is set
        pass

    async def fake_refresh(obj):
        # After commit+refresh, the encrypted value should already be on obj
        # (it was set by the endpoint handler before commit)
        pass

    mock_db = _make_db_with_config(config)
    mock_db.add.side_effect = fake_add
    mock_db.refresh.side_effect = fake_refresh

    async def override_get_db():
        yield mock_db

    async def override_superadmin():
        return _make_superuser()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_superadmin] = override_superadmin
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=True)
        response = client.put(
            "/api/v1/super-admin/youtube-cookies",
            json={"primary": new_cookie},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()

    # Response must have primary and backup slots with health status
    assert "primary" in body, f"Response missing 'primary': {body}"
    assert "backup" in body, f"Response missing 'backup': {body}"

    allowed = {"valid", "expired", "missing"}
    assert body["primary"]["status"] in allowed, (
        f"primary status must be one of {allowed}, got: {body['primary']['status']!r}"
    )
    assert body["backup"]["status"] in allowed, (
        f"backup status must be one of {allowed}, got: {body['backup']['status']!r}"
    )

    # The plaintext cookie must NOT appear in the response
    assert new_cookie not in response.text, (
        "Plaintext cookie content leaked into PUT response"
    )

    # db.add and db.commit must have been called
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


def test_put_cookies_partial_update_only_primary(app):
    """PUT with only primary field does not overwrite backup slot."""
    from app.db.base import get_db
    from app.api.v1.deps import get_current_superadmin
    from app.core.security import encrypt_token

    backup_enc = encrypt_token("existing_backup_cookie_data")
    config = _make_system_config(primary_enc=None, backup_enc=backup_enc)

    mock_db = _make_db_with_config(config)

    async def override_get_db():
        yield mock_db

    async def override_superadmin():
        return _make_superuser()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_superadmin] = override_superadmin
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=True)
        response = client.put(
            "/api/v1/super-admin/youtube-cookies",
            json={"primary": "new_primary_cookie"},  # no backup field
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    # backup_encrypted must be unchanged on the config object
    assert config.youtube_cookies_backup_encrypted == backup_enc, (
        "Partial update must not overwrite the backup slot"
    )


def test_put_cookies_500_when_config_not_initialized(app):
    """PUT /super-admin/youtube-cookies returns 500 when system config row is missing."""
    from app.db.base import get_db
    from app.api.v1.deps import get_current_superadmin

    mock_db = _make_db_with_config(None)  # No system config row

    async def override_get_db():
        yield mock_db

    async def override_superadmin():
        return _make_superuser()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_superadmin] = override_superadmin
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)
        response = client.put(
            "/api/v1/super-admin/youtube-cookies",
            json={"primary": "some_cookie"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)

    assert response.status_code == 500, (
        f"Expected 500 when system config not initialized, got {response.status_code}"
    )
