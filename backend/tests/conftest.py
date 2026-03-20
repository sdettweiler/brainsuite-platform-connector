"""
Shared pytest fixtures for the Phase 02 security hardening test suite.

Provides:
    - app: FastAPI test application with mocked settings
    - async_client: httpx.AsyncClient for async test requests
    - mock_redis: AsyncMock mimicking redis.asyncio.Redis
    - mock_settings: patched Settings with test-safe defaults

IMPORTANT: TOKEN_ENCRYPTION_KEY must be set before any app module is imported.
This is done here at conftest import time so pytest collection does not fail.
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cryptography.fernet import Fernet


# ---------------------------------------------------------------------------
# Generate a stable valid Fernet key and inject it into the environment
# BEFORE any app module is imported during test collection.
# ---------------------------------------------------------------------------

_TEST_FERNET_KEY = Fernet.generate_key().decode()

# Only set if not already provided (allows CI to override via env).
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", _TEST_FERNET_KEY)


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
    Return the FastAPI application.

    TOKEN_ENCRYPTION_KEY was already injected into os.environ at conftest
    import time, so the app modules load cleanly.
    """
    import importlib
    import app.core.config as config_mod
    import app.core.security as security_mod
    import app.main as main_mod

    # Reload so any test-specific env changes are picked up.
    importlib.reload(config_mod)
    importlib.reload(security_mod)
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
    dependency is required.
    """
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
