"""
Tests for Task 14-03-01 | COOK-02

Behavior: _get_cookies_from_db reads from SystemConfig DB and falls back to env vars
when DB is empty.
"""
import os
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helper to build a minimal DV360SyncService instance without real credentials
# ---------------------------------------------------------------------------

def _make_sync_service():
    """Return a DV360SyncService instance with mocked credentials."""
    from app.services.sync.dv360_sync import DV360SyncService

    connection = MagicMock()
    connection.id = uuid.uuid4()
    connection.organization_id = uuid.uuid4()
    connection.credentials_encrypted = None
    connection.platform_account_id = "test_advertiser_id"

    with patch.object(DV360SyncService, "__init__", lambda self, *a, **kw: None):
        svc = DV360SyncService.__new__(DV360SyncService)
        # Minimal attributes the service needs for our test target
        svc.connection = connection
        svc.logger = MagicMock()
        import logging
        svc.logger = logging.getLogger("test_dv360_sync")
    return svc


# ---------------------------------------------------------------------------
# Gap 7: _get_cookies_from_db reads DB, falls back to env vars (14-03-01)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_cookies_from_db_returns_decrypted_db_cookies():
    """_get_cookies_from_db returns decrypted cookies from SystemConfig DB rows."""
    from app.core.security import encrypt_token

    primary_plain = "primary_cookie_content_abc"
    backup_plain = "backup_cookie_content_xyz"
    primary_enc = encrypt_token(primary_plain)
    backup_enc = encrypt_token(backup_plain)

    config = MagicMock()
    config.youtube_cookies_encrypted = primary_enc
    config.youtube_cookies_backup_encrypted = backup_enc

    svc = _make_sync_service()

    with patch("app.services.sync.dv360_sync.DV360SyncService._get_cookies_from_db", wraps=svc._get_cookies_from_db):
        # Patch get_session_factory used inside _get_cookies_from_db
        with patch("app.db.base.get_session_factory") as mock_sf:
            db_session = AsyncMock()
            db_session.__aenter__ = AsyncMock(return_value=db_session)
            db_session.__aexit__ = AsyncMock(return_value=False)

            scalar_result = MagicMock()
            scalar_result.scalar_one_or_none.return_value = config
            exec_result = MagicMock()
            # scalars() path is not used here; scalar_one_or_none is used
            db_session.execute = AsyncMock(return_value=exec_result)
            exec_result.scalar_one_or_none.return_value = config

            mock_sf.return_value.return_value = db_session

            cookies = await svc._get_cookies_from_db()

    assert len(cookies) == 2, f"Expected 2 cookies from DB, got {len(cookies)}: {cookies}"
    assert cookies[0] == primary_plain, f"Primary cookie mismatch: {cookies[0]!r}"
    assert cookies[1] == backup_plain, f"Backup cookie mismatch: {cookies[1]!r}"


@pytest.mark.asyncio
async def test_get_cookies_from_db_falls_back_to_env_when_db_empty():
    """_get_cookies_from_db falls back to YOUTUBE_COOKIES env vars when DB has no cookies."""
    config = MagicMock()
    config.youtube_cookies_encrypted = None
    config.youtube_cookies_backup_encrypted = None

    svc = _make_sync_service()

    env_primary = "env_primary_cookie_value"
    env_backup = "env_backup_cookie_value"

    with patch.dict(os.environ, {
        "YOUTUBE_COOKIES": env_primary,
        "YOUTUBE_COOKIES_BACKUP": env_backup,
    }):
        with patch("app.db.base.get_session_factory") as mock_sf:
            db_session = AsyncMock()
            db_session.__aenter__ = AsyncMock(return_value=db_session)
            db_session.__aexit__ = AsyncMock(return_value=False)

            exec_result = MagicMock()
            exec_result.scalar_one_or_none.return_value = config
            db_session.execute = AsyncMock(return_value=exec_result)

            mock_sf.return_value.return_value = db_session

            cookies = await svc._get_cookies_from_db()

    assert env_primary in cookies, (
        f"Expected env YOUTUBE_COOKIES in fallback result, got: {cookies}"
    )
    assert env_backup in cookies, (
        f"Expected env YOUTUBE_COOKIES_BACKUP in fallback result, got: {cookies}"
    )


@pytest.mark.asyncio
async def test_get_cookies_from_db_falls_back_to_env_when_db_raises():
    """_get_cookies_from_db falls back to env vars when DB query raises an exception."""
    svc = _make_sync_service()

    env_primary = "fallback_primary_on_db_error"

    with patch.dict(os.environ, {
        "YOUTUBE_COOKIES": env_primary,
        "YOUTUBE_COOKIES_BACKUP": "",
    }):
        with patch("app.db.base.get_session_factory") as mock_sf:
            db_session = AsyncMock()
            db_session.__aenter__ = AsyncMock(return_value=db_session)
            db_session.__aexit__ = AsyncMock(return_value=False)
            db_session.execute = AsyncMock(side_effect=Exception("DB connection failed"))

            mock_sf.return_value.return_value = db_session

            cookies = await svc._get_cookies_from_db()

    assert env_primary in cookies, (
        f"Expected env fallback on DB error, got: {cookies}"
    )


@pytest.mark.asyncio
async def test_get_cookies_from_db_returns_empty_when_db_and_env_both_empty():
    """_get_cookies_from_db returns empty list when DB has no cookies and env vars are unset."""
    config = MagicMock()
    config.youtube_cookies_encrypted = None
    config.youtube_cookies_backup_encrypted = None

    svc = _make_sync_service()

    # Ensure env vars are absent
    env_patch = {k: "" for k in ["YOUTUBE_COOKIES", "YOUTUBE_COOKIES_BACKUP"]}

    with patch.dict(os.environ, env_patch):
        with patch("app.db.base.get_session_factory") as mock_sf:
            db_session = AsyncMock()
            db_session.__aenter__ = AsyncMock(return_value=db_session)
            db_session.__aexit__ = AsyncMock(return_value=False)

            exec_result = MagicMock()
            exec_result.scalar_one_or_none.return_value = config
            db_session.execute = AsyncMock(return_value=exec_result)

            mock_sf.return_value.return_value = db_session

            cookies = await svc._get_cookies_from_db()

    assert cookies == [], f"Expected empty list, got: {cookies}"
