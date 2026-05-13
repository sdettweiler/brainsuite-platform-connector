"""
Tests for Phase 15: TikTok Asset Download

Behavior: _fetch_video_download_url, _download_video_asset, _download_image_asset
          correctly download TikTok video/image assets to S3 during sync.
          Download failures are non-fatal and do not abort sync.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import httpx


def _make_tiktok_sync_service():
    """Return a TikTokSyncService instance without real credentials."""
    from app.services.sync.tiktok_sync import TikTokSyncService
    with patch.object(TikTokSyncService, "__init__", lambda self, *a, **kw: None):
        svc = TikTokSyncService.__new__(TikTokSyncService)
    return svc


# ---------------------------------------------------------------------------
# _fetch_video_download_url tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_video_download_url_success():
    svc = _make_tiktok_sync_service()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 0, "data": {"list": [{"video_url": "https://cdn.tiktok.com/video.mp4"}]}}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await svc._fetch_video_download_url("token123", "adv_456", ["vid_789"])

    assert result == "https://cdn.tiktok.com/video.mp4"


@pytest.mark.asyncio
async def test_fetch_video_download_url_api_error():
    svc = _make_tiktok_sync_service()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 40001, "message": "auth error"}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await svc._fetch_video_download_url("token123", "adv_456", ["vid_789"])

    assert result is None


@pytest.mark.asyncio
async def test_fetch_video_download_url_http_error():
    svc = _make_tiktok_sync_service()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("connection refused"))
        mock_client_cls.return_value = mock_client

        result = await svc._fetch_video_download_url("token123", "adv_456", ["vid_789"])

    assert result is None


# ---------------------------------------------------------------------------
# _download_video_asset tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_download_video_asset_success():
    svc = _make_tiktok_sync_service()
    fake_bytes = b"X" * 1000

    mock_storage = MagicMock()
    mock_storage.file_exists.return_value = False
    mock_storage.upload_bytes.return_value = "https://storage/creatives/org123/video_tiktok_ad456.mp4"

    mock_resp = MagicMock()
    mock_resp.content = fake_bytes
    mock_resp.raise_for_status = MagicMock()

    with patch("app.services.object_storage.get_object_storage", return_value=mock_storage):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await svc._download_video_asset("https://cdn.tiktok.com/video.mp4", "org123", "ad456")

    assert result == "https://storage/creatives/org123/video_tiktok_ad456.mp4"
    mock_storage.upload_bytes.assert_called_once_with(fake_bytes, "creatives/org123/video_tiktok_ad456.mp4", content_type="video/mp4")


@pytest.mark.asyncio
async def test_download_video_asset_skip_existing():
    svc = _make_tiktok_sync_service()
    mock_storage = MagicMock()
    mock_storage.file_exists.return_value = True
    mock_storage.served_url.return_value = "https://storage/creatives/org123/video_tiktok_ad456.mp4"

    with patch("app.services.object_storage.get_object_storage", return_value=mock_storage):
        with patch("httpx.AsyncClient") as mock_client_cls:
            result = await svc._download_video_asset("https://cdn.tiktok.com/video.mp4", "org123", "ad456")
            mock_client_cls.assert_not_called()

    assert result == "https://storage/creatives/org123/video_tiktok_ad456.mp4"
    mock_storage.upload_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_download_video_asset_http_failure():
    svc = _make_tiktok_sync_service()
    mock_storage = MagicMock()
    mock_storage.file_exists.return_value = False

    with patch("app.services.object_storage.get_object_storage", return_value=mock_storage):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))
            mock_client_cls.return_value = mock_client

            result = await svc._download_video_asset("https://cdn.tiktok.com/video.mp4", "org123", "ad456")

    assert result is None
    mock_storage.upload_bytes.assert_not_called()


# ---------------------------------------------------------------------------
# _download_image_asset tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_download_image_asset_success():
    svc = _make_tiktok_sync_service()
    fake_bytes = b"Y" * 500

    mock_storage = MagicMock()
    mock_storage.file_exists.return_value = False
    mock_storage.upload_bytes.return_value = "https://storage/creatives/org123/image_tiktok_ad456.jpg"

    mock_resp = MagicMock()
    mock_resp.content = fake_bytes
    mock_resp.raise_for_status = MagicMock()

    with patch("app.services.object_storage.get_object_storage", return_value=mock_storage):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await svc._download_image_asset("https://cdn.tiktok.com/image.jpg", "org123", "ad456")

    assert result == "https://storage/creatives/org123/image_tiktok_ad456.jpg"
    mock_storage.upload_bytes.assert_called_once_with(fake_bytes, "creatives/org123/image_tiktok_ad456.jpg", content_type="image/jpeg")


@pytest.mark.asyncio
async def test_download_image_asset_too_small():
    svc = _make_tiktok_sync_service()
    mock_storage = MagicMock()
    mock_storage.file_exists.return_value = False

    mock_resp = MagicMock()
    mock_resp.content = b"X" * 50   # < 100 bytes
    mock_resp.raise_for_status = MagicMock()

    with patch("app.services.object_storage.get_object_storage", return_value=mock_storage):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await svc._download_image_asset("https://cdn.tiktok.com/image.jpg", "org123", "ad456")

    assert result is None
    mock_storage.upload_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_download_image_asset_skip_existing():
    svc = _make_tiktok_sync_service()
    mock_storage = MagicMock()
    mock_storage.file_exists.return_value = True
    mock_storage.served_url.return_value = "https://storage/creatives/org123/image_tiktok_ad456.jpg"

    with patch("app.services.object_storage.get_object_storage", return_value=mock_storage):
        with patch("httpx.AsyncClient") as mock_client_cls:
            result = await svc._download_image_asset("https://cdn.tiktok.com/image.jpg", "org123", "ad456")
            mock_client_cls.assert_not_called()

    assert result == "https://storage/creatives/org123/image_tiktok_ad456.jpg"


# ---------------------------------------------------------------------------
# Resilience: download failure must not abort sync loop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_download_failure_resilience():
    """If _fetch_video_download_url raises, the calling code in _enrich_from_ad_get
    must catch it gracefully and continue with the next ad (asset_url remains None)."""
    svc = _make_tiktok_sync_service()

    # Simulate _fetch_video_download_url raising unexpectedly
    svc._fetch_video_download_url = AsyncMock(side_effect=Exception("unexpected API failure"))
    svc._download_video_asset = AsyncMock(return_value=None)
    svc._download_image_asset = AsyncMock(return_value=None)
    svc._fetch_cover_image_url = AsyncMock(return_value=None)
    svc._download_tiktok_thumbnail = AsyncMock(return_value=None)
    svc._fetch_ad_info = AsyncMock(return_value=[
        {"ad_id": "ad1", "video_id": "vid1", "identity_type": "STANDARD"},
        {"ad_id": "ad2", "video_id": "vid2", "identity_type": "STANDARD"},
    ])

    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    connection = MagicMock()
    connection.id = "conn-id"
    connection.organization_id = "org-id"

    # Must not raise even though _fetch_video_download_url raises for both ads
    await svc._enrich_from_ad_get(db, connection, "token", "adv_id", ["ad1", "ad2"])
    # Both ads still trigger a db.execute call (even with null asset_url)
    assert db.execute.call_count >= 2


# ---------------------------------------------------------------------------
# Skip existing asset test (explicit combined test)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skip_existing_asset():
    """_download_video_asset called with path already in S3 → file_exists returns True
    → httpx.get never called."""
    svc = _make_tiktok_sync_service()
    mock_storage = MagicMock()
    mock_storage.file_exists.return_value = True
    mock_storage.served_url.return_value = "https://storage/creatives/org123/video_tiktok_ad789.mp4"

    with patch("app.services.object_storage.get_object_storage", return_value=mock_storage):
        with patch("httpx.AsyncClient") as mock_client_cls:
            result = await svc._download_video_asset("https://cdn.tiktok.com/video.mp4", "org123", "ad789")
            mock_client_cls.assert_not_called()

    assert result == "https://storage/creatives/org123/video_tiktok_ad789.mp4"
    mock_storage.upload_bytes.assert_not_called()


# ---------------------------------------------------------------------------
# TKTOK-01 / TKTOK-02: Spark ad bypass in _enrich_from_ad_get
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_spark_ad_skips_download():
    """Spark ads (identity_type='AUTH_CODE') must not trigger any download attempt.
    Both _download_video_asset and _download_image_asset must not be called.
    asset_url stays None in the update statement.
    Decision D-02: Spark ads are served creatives; we do not own these files.
    """
    svc = _make_tiktok_sync_service()
    svc._fetch_video_download_url = AsyncMock(return_value="https://cdn.tiktok.com/video.mp4")
    svc._download_video_asset = AsyncMock(return_value="https://storage/video.mp4")
    svc._download_image_asset = AsyncMock(return_value="https://storage/image.jpg")
    svc._fetch_cover_image_url = AsyncMock(return_value=None)
    svc._download_tiktok_thumbnail = AsyncMock(return_value=None)
    svc._fetch_ad_info = AsyncMock(return_value=[
        {"ad_id": "spark1", "video_id": "vid1", "identity_type": "AUTH_CODE"},
    ])

    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    connection = MagicMock()
    connection.id = "conn-id"
    connection.organization_id = "org-id"

    await svc._enrich_from_ad_get(db, connection, "token", "adv_id", ["spark1"])

    svc._download_video_asset.assert_not_called()
    svc._fetch_video_download_url.assert_not_called()
    svc._download_image_asset.assert_not_called()
