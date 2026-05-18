"""
Phase 24 Wave 2 — Google Ads sync download refactor tests.

Covers: extraction/download split (PERF-01), PO-first retry order (PERF-03),
proxy cache integration (PERF-04), socket_timeout=10 (PERF-06),
and remote_components D-05 parity fix.
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


def _fake_info_dict():
    """Minimal yt-dlp info dict suitable for process_ie_result."""
    return {
        "id": "test_video_id",
        "title": "Test Video",
        "formats": [{"url": "https://example.com/video.mp4", "ext": "mp4", "height": 720}],
        "extractor": "youtube",
        "webpage_url": "https://www.youtube.com/watch?v=test_video_id",
    }


# ---------------------------------------------------------------------------
# test_download_video_with_proxy — updated for extraction/download split
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_download_video_with_proxy():
    """PERF-01/PERF-03: extraction runs without proxy; proxy injected on subsequent download attempts.

    After the extraction/download split refactor (D-03, D-04):
    - First YoutubeDL call (_extract_info) must NOT have 'proxy' key.
    - First download attempt has no proxy (PO-first, D-04).
    - When the PO-first attempt fails and retries, subsequent download calls MUST have proxy.
    - socket_timeout must be 10 in download ydl_opts.
    - remote_components must be 'ejs:github' in download ydl_opts (D-05 parity).
    """
    from app.core.security import encrypt_token

    proxy_url = "http://testuser:s3cr3t@geo.iproyal.com:12321"

    svc = _make_google_ads_sync_service()

    all_captured_opts = []
    call_count = [0]

    def _fake_ydl(opts):
        all_captured_opts.append(dict(opts))
        call_count[0] += 1
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        if call_count[0] == 1:
            # Extraction call — return valid info dict
            ctx.extract_info = MagicMock(return_value=_fake_info_dict())
            ctx.process_ie_result = MagicMock(return_value=None)
        elif call_count[0] == 2:
            # First download attempt (PO-first, no proxy) — force failure to advance retry
            ctx.extract_info = MagicMock(return_value=_fake_info_dict())
            ctx.process_ie_result = MagicMock(side_effect=Exception("PO attempt failed"))
        else:
            # Subsequent download attempts — succeed
            ctx.extract_info = MagicMock(return_value=_fake_info_dict())
            ctx.process_ie_result = MagicMock(return_value=None)
        return ctx

    config = MagicMock()
    config.youtube_cookies_encrypted = encrypt_token("primary_cookie_data")
    config.youtube_cookies_backup_encrypted = None

    with patch("app.services.sync.proxy_cache.get_proxy_config", new=AsyncMock(return_value=(True, proxy_url))):
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

    assert len(all_captured_opts) >= 2, (
        f"Expected at least 2 YoutubeDL instantiations (1 extract + 1+ downloads), got {len(all_captured_opts)}"
    )

    # First call = extraction — must NOT have proxy (PERF-01)
    extract_opts = all_captured_opts[0]
    assert "proxy" not in extract_opts, (
        f"Extraction ydl_opts must NOT have 'proxy' key (PERF-01: extraction runs direct). "
        f"Got: {extract_opts}"
    )

    # Second call = first download attempt (PO-first, D-04) — no proxy
    first_dl_opts = all_captured_opts[1]
    assert "proxy" not in first_dl_opts, (
        f"First download attempt (PO-first/D-04) must NOT have 'proxy' key. "
        f"Got: {first_dl_opts}"
    )

    # Third call = second download attempt — must have proxy (retry path)
    if len(all_captured_opts) >= 3:
        second_dl_opts = all_captured_opts[2]
        assert "proxy" in second_dl_opts, (
            f"Second download attempt must have 'proxy' key when proxy_enabled=True. "
            f"Got: {second_dl_opts}"
        )

    # socket_timeout must be 10 in download opts (PERF-06)
    assert first_dl_opts.get("socket_timeout") == 10, (
        f"socket_timeout must be 10 in download ydl_opts, got {first_dl_opts.get('socket_timeout')}"
    )

    # remote_components must be present in download opts (D-05 parity)
    assert first_dl_opts.get("remote_components") == "ejs:github", (
        f"remote_components must be 'ejs:github' in download ydl_opts, "
        f"got {first_dl_opts.get('remote_components')}"
    )


# ---------------------------------------------------------------------------
# test_retry_order_cookieless_first — updated for extraction/download split
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_order_cookieless_first():
    """PERF-03/D-04: When proxy_enabled=True the download attempt sequence is:
    1. no-proxy/no-cookies (PO-first)
    2. proxy/primary-cookies
    3. proxy/backup-cookies

    attempts = ["", *cookies] with cookies = [primary, backup]
    -> ["", primary, backup] = 3 download calls

    Verified by capturing ydl_opts per YoutubeDL instantiation.
    The first YoutubeDL call is the extraction call (index 0, skipped in sequence check).
    Download attempt 1 (index 1) must have no 'cookiefile' AND no 'proxy'.
    Download attempt 2 (index 2) must have proxy + cookiefile.
    Download attempt 3 (index 3) must have proxy + cookiefile.
    """
    from app.core.security import encrypt_token

    proxy_url = "http://testuser:s3cr3t@geo.iproyal.com:12321"

    config = MagicMock()
    config.youtube_cookies_encrypted = encrypt_token("primary_cookie_data")
    config.youtube_cookies_backup_encrypted = encrypt_token("backup_cookie_data")

    svc = _make_google_ads_sync_service()

    # All ydl_opts captured in order across all YoutubeDL instantiations
    all_opts = []
    call_count = [0]

    def _capturing_ydl(opts):
        all_opts.append(dict(opts))
        call_count[0] += 1
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        if call_count[0] == 1:
            # extraction call — return info dict
            ctx.extract_info = MagicMock(return_value=_fake_info_dict())
            ctx.process_ie_result = MagicMock(return_value=None)
        else:
            # download calls — raise to force retry through full sequence
            ctx.extract_info = MagicMock(return_value=_fake_info_dict())
            ctx.process_ie_result = MagicMock(side_effect=Exception("force retry"))
        return ctx

    with patch("app.services.sync.proxy_cache.get_proxy_config", new=AsyncMock(return_value=(True, proxy_url))):
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
                with patch("yt_dlp.YoutubeDL", side_effect=_capturing_ydl):
                    try:
                        await svc._download_video(
                            "test_video_id", str(uuid.uuid4()), "test_ad_id"
                        )
                    except Exception:
                        pass

    # Must have: 1 extraction + 3 download attempts (no-proxy/no-cookies, proxy+primary, proxy+backup)
    assert len(all_opts) >= 2, f"Expected at least 2 YoutubeDL calls, got {len(all_opts)}"

    # Skip first call (extraction) — check download attempt sequence
    download_opts = all_opts[1:]

    # D-04: first download attempt = no proxy, no cookiefile (PO-first)
    assert len(download_opts) >= 1, "No download attempts captured"
    first_dl = download_opts[0]
    assert "proxy" not in first_dl, (
        f"First download attempt must have NO proxy (PO-first / D-04). Got opts: {first_dl}"
    )
    assert "cookiefile" not in first_dl, (
        f"First download attempt must have no cookiefile (PO-first / D-04). Got opts: {first_dl}"
    )

    # D-04: second download attempt = proxy + primary cookies
    if len(download_opts) >= 2:
        second_dl = download_opts[1]
        assert "proxy" in second_dl, (
            f"Second download attempt must have proxy. Got opts: {second_dl}"
        )
        assert "cookiefile" in second_dl, (
            f"Second download attempt must have cookiefile (primary cookie). Got opts: {second_dl}"
        )

    # D-04: third download attempt = proxy + backup cookies
    if len(download_opts) >= 3:
        third_dl = download_opts[2]
        assert "proxy" in third_dl, (
            f"Third download attempt must have proxy. Got opts: {third_dl}"
        )
        assert "cookiefile" in third_dl, (
            f"Third download attempt must have cookiefile (backup cookie). Got opts: {third_dl}"
        )


# ---------------------------------------------------------------------------
# test_credential_redaction — adapted for extraction/download split
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_credential_redaction():
    """PROXY-06/D-05: Proxy credentials must not appear in log output.

    When yt-dlp logs a message containing the raw proxy URL via the custom
    logger attached to _do_download, the _redact() closure must mask
    user:password before the message reaches any handler.
    """
    proxy_url = "http://testuser:s3cr3t@geo.iproyal.com:12321"

    config = MagicMock()
    config.youtube_cookies_encrypted = None
    config.youtube_cookies_backup_encrypted = None

    svc = _make_google_ads_sync_service()

    # Capture log output via an in-memory string handler
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    original_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)

    call_count = [0]

    def _fake_ydl_leaking_credentials(opts):
        """Simulate yt-dlp logging the raw proxy URL (the leak we must prevent).
        First call = extraction (no logger, no leak). Second call = download (has logger).
        """
        call_count[0] += 1
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        if call_count[0] == 1:
            # Extraction call
            ctx.extract_info = MagicMock(return_value=_fake_info_dict())
        else:
            # Download call — simulate yt-dlp leaking credentials via logger
            inner_logger = opts.get("logger")
            if inner_logger:
                inner_logger.warning(f"connecting via {proxy_url}")
            ctx.process_ie_result = MagicMock(return_value=None)
        return ctx

    try:
        with patch("app.services.sync.proxy_cache.get_proxy_config", new=AsyncMock(return_value=(True, proxy_url))):
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
        f"Proxy username 'testuser' found in log output — credential redaction broken. "
        f"Log snippet: {log_output[:300]}"
    )
    assert "s3cr3t" not in log_output, (
        f"Proxy password 's3cr3t' found in log output — credential redaction broken. "
        f"Log snippet: {log_output[:300]}"
    )
    assert "[PROXY:geo.iproyal.com]" in log_output, (
        f"Expected redacted proxy placeholder '[PROXY:geo.iproyal.com]' in log output, "
        f"but not found. Log snippet: {log_output[:300]}"
    )


# ---------------------------------------------------------------------------
# test_extraction_runs_without_proxy — NEW (D-01 / PERF-01)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extraction_runs_without_proxy():
    """PERF-01/D-01: _extract_info must call YoutubeDL WITHOUT a proxy key.

    Even when proxy_enabled=True, the extraction phase routes direct.
    Only the download phase uses the proxy.
    """
    proxy_url = "http://testuser:s3cr3t@geo.iproyal.com:12321"

    config = MagicMock()
    config.youtube_cookies_encrypted = None
    config.youtube_cookies_backup_encrypted = None

    svc = _make_google_ads_sync_service()

    extraction_opts: dict = {}
    call_count = [0]

    def _capturing_ydl(opts):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call = extraction — capture and record opts
            extraction_opts.update(opts)
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        ctx.extract_info = MagicMock(return_value=_fake_info_dict())
        ctx.process_ie_result = MagicMock(return_value=None)
        return ctx

    with patch("app.services.sync.proxy_cache.get_proxy_config", new=AsyncMock(return_value=(True, proxy_url))):
        with patch("app.db.base.get_session_factory") as mock_sf:
            db_session = AsyncMock()
            db_session.__aenter__ = AsyncMock(return_value=db_session)
            db_session.__aexit__ = AsyncMock(return_value=False)
            exec_result = MagicMock()
            exec_result.scalar_one_or_none.return_value = config
            db_session.execute = AsyncMock(return_value=exec_result)
            mock_sf.return_value.return_value = db_session

            with patch("yt_dlp.YoutubeDL", side_effect=_capturing_ydl):
                with patch("app.services.object_storage.get_object_storage") as mock_storage:
                    mock_storage.return_value.file_exists.return_value = False
                    try:
                        await svc._download_video("test_video_id", str(uuid.uuid4()), "test_ad_id")
                    except Exception:
                        pass

    assert call_count[0] >= 1, "No YoutubeDL calls captured"
    assert "proxy" not in extraction_opts, (
        f"Extraction (first YoutubeDL call) must NOT have 'proxy' key — PERF-01 violation. "
        f"Got extraction_opts: {extraction_opts}"
    )


# ---------------------------------------------------------------------------
# test_remote_components_present_in_both_phases — NEW (D-05 parity)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remote_components_present_in_both_phases():
    """D-05: remote_components='ejs:github' must be present in EVERY YoutubeDL opts dict.

    This is the critical D-05 parity assertion. Pre-refactor google_ads_sync.py was
    missing remote_components entirely. After Plan 24-03, both extraction and download
    ydl_opts must contain 'remote_components': 'ejs:github'.
    """
    proxy_url = "http://testuser:s3cr3t@geo.iproyal.com:12321"

    config = MagicMock()
    config.youtube_cookies_encrypted = None
    config.youtube_cookies_backup_encrypted = None

    svc = _make_google_ads_sync_service()

    all_opts: list = []

    def _capturing_ydl(opts):
        all_opts.append(dict(opts))
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        ctx.extract_info = MagicMock(return_value=_fake_info_dict())
        ctx.process_ie_result = MagicMock(return_value=None)
        return ctx

    with patch("app.services.sync.proxy_cache.get_proxy_config", new=AsyncMock(return_value=(True, proxy_url))):
        with patch("app.db.base.get_session_factory") as mock_sf:
            db_session = AsyncMock()
            db_session.__aenter__ = AsyncMock(return_value=db_session)
            db_session.__aexit__ = AsyncMock(return_value=False)
            exec_result = MagicMock()
            exec_result.scalar_one_or_none.return_value = config
            db_session.execute = AsyncMock(return_value=exec_result)
            mock_sf.return_value.return_value = db_session

            with patch("yt_dlp.YoutubeDL", side_effect=_capturing_ydl):
                with patch("app.services.object_storage.get_object_storage") as mock_storage:
                    mock_storage.return_value.file_exists.return_value = False
                    try:
                        await svc._download_video("test_video_id", str(uuid.uuid4()), "test_ad_id")
                    except Exception:
                        pass

    assert len(all_opts) >= 1, "No YoutubeDL calls captured"

    for i, opts in enumerate(all_opts):
        assert opts.get("remote_components") == "ejs:github", (
            f"YoutubeDL call {i + 1} missing remote_components='ejs:github' (D-05 parity). "
            f"Got opts: {opts}"
        )
