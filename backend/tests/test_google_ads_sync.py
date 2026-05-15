"""
Phase 20 Wave 0 failing stubs — Google Ads proxy injection, retry order, credential redaction.

These tests MUST FAIL until Plan 02 implements proxy support in google_ads_sync.py.
Requirements: PROXY-02 (proxy injection), PROXY-04 (retry order), PROXY-06 (redaction).
"""
import io
import logging
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helper to build a minimal GoogleAdsSyncService instance without credentials
# ---------------------------------------------------------------------------

def _make_google_ads_sync_service():
    """Return a GoogleAdsSyncService instance with mocked credentials."""
    from app.services.sync.google_ads_sync import GoogleAdsSyncService

    connection = MagicMock()
    connection.id = uuid.uuid4()
    connection.organization_id = uuid.uuid4()
    connection.credentials_encrypted = None
    connection.platform_account_id = "test_customer_id"

    with patch.object(GoogleAdsSyncService, "__init__", lambda self, *a, **kw: None):
        svc = GoogleAdsSyncService.__new__(GoogleAdsSyncService)
        svc.connection = connection
        svc.logger = logging.getLogger("test_google_ads_sync")
    return svc


# ---------------------------------------------------------------------------
# Phase 20 Wave 0 failing stubs — proxy injection, retry order, redaction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_download_video_with_proxy():
    """PROXY-02: _download_video passes proxy URL in ydl_opts when proxy_enabled=True.

    Fails until D-02 (proxy injection) is implemented in google_ads_sync.py.
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

    svc = _make_google_ads_sync_service()

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
                    await svc._download_video("test_video_id", str(uuid.uuid4()), "test_ad_id")
                except Exception:
                    pass

    assert "proxy" in captured_opts, (
        "ydl_opts must contain 'proxy' key when proxy_enabled=True — not yet implemented (Plan 02 D-02)"
    )


@pytest.mark.asyncio
async def test_retry_order_cookieless_first():
    """PROXY-04: When proxy_enabled=True the first download attempt uses no cookies.

    Retry order must be: empty string → primary cookie → backup cookie.
    Fails until D-04 (cookieless-first retry order) is implemented in google_ads_sync.py.
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

    svc = _make_google_ads_sync_service()

    attempt_cookies = []

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
            with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
                mock_ydl_ctx = MagicMock()
                mock_ydl_ctx.__enter__ = MagicMock(return_value=mock_ydl_ctx)
                mock_ydl_ctx.__exit__ = MagicMock(return_value=False)
                mock_ydl_ctx.download = MagicMock(side_effect=_capture_attempts)
                mock_ydl_cls.return_value = mock_ydl_ctx

                try:
                    await svc._download_video(
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
    Fails until D-05 (redact_credentials) is implemented in google_ads_sync.py.
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

    svc = _make_google_ads_sync_service()

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
                        await svc._download_video(
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
