"""
Tests for Task 14-03-01 | COOK-02

Behavior: _get_cookies_from_db reads from SystemConfig DB and falls back to env vars
when DB is empty.

Also contains Wave 0 failing stubs for Phase 20 (proxy injection, retry order,
credential redaction) — these fail until Plan 02 implements the functionality.
"""
import io
import logging
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


# ---------------------------------------------------------------------------
# Phase 20 Wave 0 failing stubs — proxy injection, retry order, redaction
# These tests MUST FAIL until Plan 02 implements proxy support in dv360_sync.py.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_download_video_with_proxy():
    """PROXY-01: _download_video_asset passes proxy URL in ydl_opts when proxy_enabled=True.

    Fails until D-02 (proxy injection) is implemented in dv360_sync.py.
    """
    from app.core.security import encrypt_token

    proxy_url = "http://testuser:s3cr3t@geo.iproyal.com:12321"

    config = MagicMock()
    config.proxy_enabled = True
    config.proxy_url_encrypted = encrypt_token(proxy_url)
    config.youtube_cookies_encrypted = None
    config.youtube_cookies_backup_encrypted = None
    config.youtube_cookies_runtime_expired = False
    config.youtube_cookies_backup_runtime_expired = False

    svc = _make_sync_service()

    captured_opts = {}

    def _fake_ydl(opts):
        captured_opts.update(opts)
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        ctx.download = MagicMock(return_value=0)
        return ctx

    with patch("app.db.base.get_session_factory") as mock_sf:
        db_session = AsyncMock()
        db_session.__aenter__ = AsyncMock(return_value=db_session)
        db_session.__aexit__ = AsyncMock(return_value=False)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = config
        db_session.execute = AsyncMock(return_value=exec_result)
        mock_sf.return_value.return_value = db_session

        with patch("yt_dlp.YoutubeDL", side_effect=_fake_ydl):
            with patch("app.services.object_storage.get_object_storage") as mock_storage:
                mock_storage.return_value.file_exists.return_value = False
                try:
                    await svc._download_video_asset("test_video_id", str(uuid.uuid4()), "test_ad_id")
                except Exception:
                    pass

    assert "proxy" in captured_opts, (
        "ydl_opts must contain 'proxy' key when proxy_enabled=True — not yet implemented (Plan 02 D-02)"
    )


@pytest.mark.asyncio
async def test_retry_order_cookieless_first():
    """PROXY-04: When proxy_enabled=True the first download attempt uses no cookies.

    Retry order must be: empty string → primary cookie → backup cookie.
    Fails until D-04 (cookieless-first retry order) is implemented in dv360_sync.py.
    """
    from app.core.security import encrypt_token

    proxy_url = "http://testuser:s3cr3t@geo.iproyal.com:12321"

    config = MagicMock()
    config.proxy_enabled = True
    config.proxy_url_encrypted = encrypt_token(proxy_url)
    config.youtube_cookies_encrypted = encrypt_token("primary_cookie_data")
    config.youtube_cookies_backup_encrypted = encrypt_token("backup_cookie_data")
    config.youtube_cookies_runtime_expired = False
    config.youtube_cookies_backup_runtime_expired = False

    svc = _make_sync_service()

    attempt_cookies = []

    original_do_download = None

    def _capture_attempts(cookie_data: str):
        attempt_cookies.append(cookie_data)
        raise Exception("stop after capture")

    with patch("app.db.base.get_session_factory") as mock_sf:
        db_session = AsyncMock()
        db_session.__aenter__ = AsyncMock(return_value=db_session)
        db_session.__aexit__ = AsyncMock(return_value=False)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = config
        db_session.execute = AsyncMock(return_value=exec_result)
        mock_sf.return_value.return_value = db_session

        with patch("app.services.object_storage.get_object_storage") as mock_storage:
            mock_storage.return_value.file_exists.return_value = False
            with patch.object(
                type(svc),
                "_download_video_asset",
                wraps=svc._download_video_asset,
            ):
                with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
                    mock_ydl_ctx = MagicMock()
                    mock_ydl_ctx.__enter__ = MagicMock(return_value=mock_ydl_ctx)
                    mock_ydl_ctx.__exit__ = MagicMock(return_value=False)
                    mock_ydl_ctx.download = MagicMock(side_effect=_capture_attempts)
                    mock_ydl_cls.return_value = mock_ydl_ctx

                    try:
                        await svc._download_video_asset(
                            "test_video_id", str(uuid.uuid4()), "test_ad_id"
                        )
                    except Exception:
                        pass

    # When proxy_enabled, first attempt must be cookieless (empty string)
    assert len(attempt_cookies) >= 1, "No download attempts captured"
    assert attempt_cookies[0] == "", (
        f"First attempt must be cookieless (empty string) when proxy_enabled=True, "
        f"got: {attempt_cookies[0]!r} — not yet implemented (Plan 02 D-04)"
    )


@pytest.mark.asyncio
async def test_credential_redaction():
    """PROXY-06: Proxy credentials must not appear in log output.

    When yt-dlp logs a message containing the raw proxy URL, the application
    logger must redact user:password before the message reaches any handler.
    Fails until D-05 (redact_credentials) is implemented in dv360_sync.py.
    """
    from app.core.security import encrypt_token

    proxy_url = "http://testuser:s3cr3t@geo.iproyal.com:12321"

    config = MagicMock()
    config.proxy_enabled = True
    config.proxy_url_encrypted = encrypt_token(proxy_url)
    config.youtube_cookies_encrypted = None
    config.youtube_cookies_backup_encrypted = None
    config.youtube_cookies_runtime_expired = False
    config.youtube_cookies_backup_runtime_expired = False

    svc = _make_sync_service()

    # Capture log output via an in-memory string handler
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    original_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)

    def _fake_ydl_leaking_credentials(opts):
        """Simulate yt-dlp logging the raw proxy URL (the leak we must prevent)."""
        inner_logger = opts.get("logger")
        if inner_logger:
            inner_logger.warning(f"connecting via {proxy_url}")
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        ctx.download = MagicMock(return_value=0)
        return ctx

    try:
        with patch("app.db.base.get_session_factory") as mock_sf:
            db_session = AsyncMock()
            db_session.__aenter__ = AsyncMock(return_value=db_session)
            db_session.__aexit__ = AsyncMock(return_value=False)
            exec_result = MagicMock()
            exec_result.scalar_one_or_none.return_value = config
            db_session.execute = AsyncMock(return_value=exec_result)
            mock_sf.return_value.return_value = db_session

            with patch("yt_dlp.YoutubeDL", side_effect=_fake_ydl_leaking_credentials):
                with patch("app.services.object_storage.get_object_storage") as mock_storage:
                    mock_storage.return_value.file_exists.return_value = False
                    try:
                        await svc._download_video_asset(
                            "test_video_id", str(uuid.uuid4()), "test_ad_id"
                        )
                    except Exception:
                        pass
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(original_level)

    log_output = log_stream.getvalue()

    assert "testuser" not in log_output, (
        f"Proxy username 'testuser' found in log output — credential redaction not implemented (Plan 02 D-05). "
        f"Log snippet: {log_output[:300]}"
    )
    assert "s3cr3t" not in log_output, (
        f"Proxy password 's3cr3t' found in log output — credential redaction not implemented (Plan 02 D-05). "
        f"Log snippet: {log_output[:300]}"
    )
    assert "[PROXY:geo.iproyal.com]" in log_output, (
        f"Expected redacted proxy placeholder '[PROXY:geo.iproyal.com]' in log output, "
        f"but not found — Plan 02 D-05 not yet implemented. "
        f"Log snippet: {log_output[:300]}"
    )
