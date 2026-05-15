"""
Tests for Plan 21-01 | PROXY-05

Behaviors:
- GET /super-admin/proxy-config returns proxy_enabled flag + masked proxy_url_masked (or null)
- PUT /super-admin/proxy-config with {proxy_enabled: bool} updates SystemConfig.proxy_enabled
- PUT /super-admin/proxy-config with {proxy_url: '<raw url>'} encrypts and stores URL
- POST /super-admin/proxy-config/test makes HTTPS GET to YouTube via proxy; returns shape
- Non-SuperAdmin receives 403 on all three proxy endpoints
- _mask_proxy_url helper masks credentials correctly
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers (copied verbatim pattern from test_super_admin_endpoints.py)
# ---------------------------------------------------------------------------

def _make_superuser():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "admin@example.com"
    user.is_superuser = True
    user.is_active = True
    return user


def _make_system_config_proxy(proxy_url_enc=None, proxy_enabled=False):
    """Mirror of _make_system_config but for proxy columns."""
    config = MagicMock()
    config.proxy_url_encrypted = proxy_url_enc
    config.proxy_enabled = proxy_enabled
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
# test_get_proxy_config_no_url
# ---------------------------------------------------------------------------

def test_get_proxy_config_no_url(app):
    """GET /proxy-config with no URL stored returns {proxy_enabled: false, proxy_url_masked: null}."""
    from app.db.base import get_db
    from app.api.v1.deps import get_current_superadmin

    config = _make_system_config_proxy(proxy_url_enc=None, proxy_enabled=False)
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
        response = client.get("/api/v1/super-admin/proxy-config")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["proxy_enabled"] is False
    assert body["proxy_url_masked"] is None


# ---------------------------------------------------------------------------
# test_get_proxy_config_with_url_returns_masked
# ---------------------------------------------------------------------------

def test_get_proxy_config_with_url_returns_masked(app):
    """GET /proxy-config with encrypted URL returns masked URL, never plaintext."""
    from app.core.security import encrypt_token
    from app.db.base import get_db
    from app.api.v1.deps import get_current_superadmin

    raw_url = "http://user:pass@geo.iproyal.com:12321"
    encrypted = encrypt_token(raw_url)
    config = _make_system_config_proxy(proxy_url_enc=encrypted, proxy_enabled=True)
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
        response = client.get("/api/v1/super-admin/proxy-config")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["proxy_enabled"] is True
    assert body["proxy_url_masked"] == "http://••••••@geo.iproyal.com:12321"

    # Plaintext credentials must NOT appear in response
    response_text = response.text
    assert "user" not in response_text, "Credential 'user' leaked into GET response"
    assert "pass" not in response_text, "Credential 'pass' leaked into GET response"


# ---------------------------------------------------------------------------
# test_put_proxy_toggle_updates_enabled
# ---------------------------------------------------------------------------

def test_put_proxy_toggle_updates_enabled(app):
    """PUT /proxy-config {proxy_enabled: true} updates proxy_enabled and returns fresh state."""
    from app.db.base import get_db
    from app.api.v1.deps import get_current_superadmin

    config = _make_system_config_proxy(proxy_url_enc=None, proxy_enabled=False)
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
            "/api/v1/super-admin/proxy-config",
            json={"proxy_enabled": True},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert "proxy_enabled" in body
    assert "proxy_url_masked" in body

    # config.proxy_enabled must have been mutated to True
    assert config.proxy_enabled is True

    # db.add and db.commit must have been called
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# test_put_proxy_url_encrypts_and_returns_masked
# ---------------------------------------------------------------------------

def test_put_proxy_url_encrypts_and_returns_masked(app):
    """PUT /proxy-config {proxy_url} encrypts the URL; plaintext must not appear in response."""
    from app.db.base import get_db
    from app.api.v1.deps import get_current_superadmin

    config = _make_system_config_proxy(proxy_url_enc=None, proxy_enabled=True)
    mock_db = _make_db_with_config(config)

    raw_url = "http://u:p@host:9000"

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
            "/api/v1/super-admin/proxy-config",
            json={"proxy_url": raw_url},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()

    # proxy_url_encrypted must be set (not None and not equal to plaintext)
    assert config.proxy_url_encrypted is not None
    assert config.proxy_url_encrypted != raw_url

    # Masked URL should be the bullet-masked form
    assert body["proxy_url_masked"] == "http://••••••@host:9000"

    # Plaintext URL must not appear anywhere in response
    assert raw_url not in response.text, "Plaintext URL leaked into PUT response"
    assert "u:p" not in response.text, "Credentials leaked into PUT response"


# ---------------------------------------------------------------------------
# test_post_proxy_test_returns_success_shape
# ---------------------------------------------------------------------------

def test_post_proxy_test_returns_success_shape(app):
    """POST /proxy-config/test with proxy enabled + valid URL returns {success: true, latency_ms >= 0}."""
    from app.core.security import encrypt_token
    from app.db.base import get_db
    from app.api.v1.deps import get_current_superadmin

    raw_url = "http://u:p@host:9000"
    encrypted = encrypt_token(raw_url)
    config = _make_system_config_proxy(proxy_url_enc=encrypted, proxy_enabled=True)
    mock_db = _make_db_with_config(config)

    async def override_get_db():
        yield mock_db

    async def override_superadmin():
        return _make_superuser()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_superadmin] = override_superadmin

    # Mock httpx.AsyncClient to avoid real network call
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    try:
        from fastapi.testclient import TestClient
        with patch("app.api.v1.endpoints.super_admin.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app, raise_server_exceptions=True)
            response = client.post("/api/v1/super-admin/proxy-config/test")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["latency_ms"], int)
    assert body["latency_ms"] >= 0
    assert body["error"] is None


# ---------------------------------------------------------------------------
# test_post_proxy_test_rejects_when_disabled_or_missing_url
# ---------------------------------------------------------------------------

def test_post_proxy_test_rejects_when_disabled_or_missing_url(app):
    """POST /proxy-config/test returns 400 when proxy disabled OR URL not set."""
    from app.db.base import get_db
    from app.api.v1.deps import get_current_superadmin

    # Sub-case 1: proxy_enabled=False with a URL
    from app.core.security import encrypt_token
    config_disabled = _make_system_config_proxy(
        proxy_url_enc=encrypt_token("http://u:p@host:9000"), proxy_enabled=False
    )

    async def override_get_db_disabled():
        yield _make_db_with_config(config_disabled)

    async def override_superadmin():
        return _make_superuser()

    app.dependency_overrides[get_db] = override_get_db_disabled
    app.dependency_overrides[get_current_superadmin] = override_superadmin
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/super-admin/proxy-config/test")
        assert response.status_code == 400, f"Expected 400 (disabled), got {response.status_code}: {response.text}"
        assert "Proxy not configured or disabled" in response.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)

    # Sub-case 2: proxy_enabled=True but no URL
    config_no_url = _make_system_config_proxy(proxy_url_enc=None, proxy_enabled=True)

    async def override_get_db_no_url():
        yield _make_db_with_config(config_no_url)

    app.dependency_overrides[get_db] = override_get_db_no_url
    app.dependency_overrides[get_current_superadmin] = override_superadmin
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/super-admin/proxy-config/test")
        assert response.status_code == 400, f"Expected 400 (no URL), got {response.status_code}: {response.text}"
        assert "Proxy not configured or disabled" in response.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)


# ---------------------------------------------------------------------------
# test_proxy_endpoints_reject_non_superadmin
# ---------------------------------------------------------------------------

def test_proxy_endpoints_reject_non_superadmin(app):
    """GET, PUT, and POST /proxy-config/test each return 403 for non-SuperAdmin."""
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

        r_get = client.get("/api/v1/super-admin/proxy-config")
        assert r_get.status_code == 403, f"GET expected 403, got {r_get.status_code}"

        r_put = client.put("/api/v1/super-admin/proxy-config", json={"proxy_enabled": True})
        assert r_put.status_code == 403, f"PUT expected 403, got {r_put.status_code}"

        r_post = client.post("/api/v1/super-admin/proxy-config/test")
        assert r_post.status_code == 403, f"POST expected 403, got {r_post.status_code}"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_superadmin, None)


# ---------------------------------------------------------------------------
# test_mask_proxy_url_helper
# ---------------------------------------------------------------------------

def test_mask_proxy_url_helper():
    """Direct unit test of _mask_proxy_url helper — 4 cases."""
    from app.api.v1.endpoints.super_admin import _mask_proxy_url

    # Case 1: standard IPRoyal format
    assert _mask_proxy_url("http://user:pass@geo.iproyal.com:12321") == "http://••••••@geo.iproyal.com:12321"

    # Case 2: https with short credentials
    assert _mask_proxy_url("https://u:p@host:9000") == "https://••••••@host:9000"

    # Case 3: no @ — return input unchanged
    assert _mask_proxy_url("no-at-sign-string") == "no-at-sign-string"

    # Case 4: empty string — return empty string, no crash
    assert _mask_proxy_url("") == ""
