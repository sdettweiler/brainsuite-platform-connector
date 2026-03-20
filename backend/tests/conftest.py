"""
Shared pytest fixtures for the Phase 02 security hardening test suite.

Provides:
    - app: FastAPI test application with mocked settings
    - async_client: httpx.AsyncClient for async test requests
    - mock_redis: AsyncMock mimicking redis.asyncio.Redis
    - mock_settings: patched Settings with test-safe defaults
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cryptography.fernet import Fernet


# ---------------------------------------------------------------------------
# Generate a stable valid Fernet key for all tests
# ---------------------------------------------------------------------------

_TEST_FERNET_KEY = Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# mock_settings fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_settings():
    """Return a mock Settings object with test-safe defaults."""
    mock = MagicMock()
    mock.TOKEN_ENCRYPTION_KEY = _TEST_FERNET_KEY
    mock.BASE_URL = "http://localhost:8000"
    mock.DEBUG = True
    mock.BACKEND_CORS_ORIGINS = ["http://localhost:4200"]
    mock.APP_NAME = "Test App"
    mock.APP_VERSION = "0.0.0"
    mock.API_V1_STR = "/api/v1"
    mock.SECRET_KEY = "test-secret-key"
    mock.ALGORITHM = "HS256"
    mock.ACCESS_TOKEN_EXPIRE_MINUTES = 30
    mock.REFRESH_TOKEN_EXPIRE_DAYS = 7
    return mock


# ---------------------------------------------------------------------------
# mock_redis fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    """Return an AsyncMock that mimics redis.asyncio.Redis.

    Supports setex, get, delete as async methods backed by an in-memory dict
    for realistic behaviour in tests that exercise session storage logic.
    """
    store: dict = {}

    redis = AsyncMock()

    async def _setex(name, time, value):
        store[name] = value

    async def _get(name):
        return store.get(name)

    async def _delete(*names):
        for name in names:
            store.pop(name, None)

    redis.setex.side_effect = _setex
    redis.get.side_effect = _get
    redis.delete.side_effect = _delete
    redis._store = store  # expose for assertions in tests

    return redis


# ---------------------------------------------------------------------------
# app fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """
    Return the FastAPI application with TOKEN_ENCRYPTION_KEY mocked to a
    valid Fernet key so startup validation does not fail during test collection.
    """
    import os
    os.environ.setdefault("TOKEN_ENCRYPTION_KEY", _TEST_FERNET_KEY)

    # Patch settings before importing app.main so the module-level
    # settings instantiation sees the valid key.
    with patch.dict("os.environ", {"TOKEN_ENCRYPTION_KEY": _TEST_FERNET_KEY}):
        # Import after env is set
        import importlib
        import app.core.config as config_mod
        import app.core.security as security_mod

        # Reload modules so they pick up the patched env
        importlib.reload(config_mod)
        importlib.reload(security_mod)

        import app.main as main_mod
        importlib.reload(main_mod)

        yield main_mod.app


# ---------------------------------------------------------------------------
# async_client fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def async_client(app):
    """
    Return a synchronous TestClient wrapping the FastAPI app.

    Uses fastapi.testclient.TestClient (synchronous) so no pytest-asyncio
    dependency is required.  For async-specific tests, httpx.AsyncClient with
    anyio can be used directly.
    """
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
