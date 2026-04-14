"""
TDD tests for Task 2: ai_autofill.py service.

Phase 09, Plan 01.

Tests cover:
- COMPLETE guard (AI-06): re-processing prevention
- No auto_fill_enabled fields: COMPLETE without Gemini call
- All 7 auto_fill_type routing paths
- GEMINI_API_KEY=None graceful no-op (D-09)
- Image >4MB downsample (AI-05)
- Exception sets FAILED status
- FAILED resets to PENDING on retry (D-12)
- VO transcript truncation at 2000 chars
"""
import io
import uuid
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_field(auto_fill_type: str, default_value: str = "default") -> MagicMock:
    f = MagicMock()
    f.id = uuid.uuid4()
    f.auto_fill_type = auto_fill_type
    f.default_value = default_value
    return f


def _make_asset(asset_format: str = "IMAGE", campaign_name: str = "Camp", ad_name: str = "Ad") -> MagicMock:
    a = MagicMock()
    a.id = uuid.uuid4()
    a.asset_format = asset_format
    a.asset_url = "/objects/assets/test.jpg"
    a.campaign_name = campaign_name
    a.ad_name = ad_name
    return a


def _make_tracking(status: str) -> MagicMock:
    t = MagicMock()
    t.ai_inference_status = status
    return t


def _make_tiny_jpeg() -> bytes:
    """Create a minimal valid JPEG in-memory."""
    from PIL import Image
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_large_jpeg(target_mb: float = 5.0) -> bytes:
    """Create a large JPEG exceeding target MB via a real image + padding."""
    from PIL import Image
    img = Image.new("RGB", (3000, 3000), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    raw = buf.getvalue()
    # Pad to ensure > 4 MB
    needed = int(target_mb * 1024 * 1024) - len(raw)
    if needed > 0:
        raw += b"\x00" * needed
    return raw


def _make_db_session_mock(
    tracking_status: str = "PENDING",
    fields=None,
    asset=None,
    extra_execute_results=None,
):
    """Build a DB session mock with proper execute side_effects for _autofill Phase 1."""
    db_session = AsyncMock()

    exec_result_tracking = MagicMock()
    tracking_obj = _make_tracking(tracking_status)
    exec_result_tracking.scalar_one_or_none.return_value = tracking_obj

    exec_result_fields = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = fields if fields is not None else []
    exec_result_fields.scalars.return_value = scalars_mock

    side_effects = [
        MagicMock(),          # pg_insert on_conflict_do_nothing
        exec_result_tracking, # select AIInferenceTracking
    ]

    # If FAILED, add an extra execute for the PENDING reset UPDATE
    if tracking_status == "FAILED":
        side_effects.append(MagicMock())  # update FAILED→PENDING

    side_effects.append(exec_result_fields)  # select MetadataField

    if extra_execute_results:
        side_effects.extend(extra_execute_results)

    db_session.execute = AsyncMock(side_effect=side_effects)
    db_session.get = AsyncMock(return_value=asset)
    db_session.commit = AsyncMock()
    db_session.rollback = AsyncMock()
    db_session.add = MagicMock()
    db_session.__aenter__ = AsyncMock(return_value=db_session)
    db_session.__aexit__ = AsyncMock(return_value=False)

    return db_session


# ---------------------------------------------------------------------------
# Test 1: COMPLETE guard prevents re-inference
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_guard():
    """Assets with COMPLETE tracking row must NOT trigger Gemini calls."""
    from app.services.ai_autofill import run_autofill_for_asset

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()

    with patch("app.services.ai_autofill.get_session_factory") as mock_sf, \
         patch("app.services.ai_autofill.genai") as mock_genai:

        db_session = AsyncMock()
        exec_result_tracking = MagicMock()
        exec_result_tracking.scalar_one_or_none.return_value = _make_tracking("COMPLETE")
        db_session.execute = AsyncMock(side_effect=[MagicMock(), exec_result_tracking])
        db_session.commit = AsyncMock()
        db_session.__aenter__ = AsyncMock(return_value=db_session)
        db_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value.return_value = db_session

        await run_autofill_for_asset(asset_id, org_id)

        mock_genai.Client.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: No auto_fill_enabled fields → COMPLETE without Gemini
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_autofill_fields():
    """When no MetadataFields have auto_fill_enabled=True, status→COMPLETE without AI."""
    from app.services.ai_autofill import run_autofill_for_asset

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()

    with patch("app.services.ai_autofill.get_session_factory") as mock_sf, \
         patch("app.services.ai_autofill._set_status", new_callable=AsyncMock) as mock_set_status, \
         patch("app.services.ai_autofill.genai") as mock_genai:

        db_session = _make_db_session_mock(tracking_status="PENDING", fields=[])
        mock_sf.return_value.return_value = db_session

        await run_autofill_for_asset(asset_id, org_id)

        mock_genai.Client.assert_not_called()
        mock_set_status.assert_called_once_with(asset_id, "COMPLETE")


# ---------------------------------------------------------------------------
# Test 3: language field routing from Vision response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_language_field_routing():
    """language auto_fill_type populates from Gemini Vision response."""
    from app.services.ai_autofill import _autofill

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()
    field = _make_field("language")
    asset = _make_asset(asset_format="IMAGE")

    with patch("app.services.ai_autofill.get_session_factory") as mock_sf, \
         patch("app.services.ai_autofill.settings") as mock_settings, \
         patch("app.services.ai_autofill.get_object_storage") as mock_storage, \
         patch("app.services.ai_autofill._run_vision", new_callable=AsyncMock) as mock_vision, \
         patch("app.services.ai_autofill._write_values", new_callable=AsyncMock) as mock_write, \
         patch("app.services.ai_autofill._set_status", new_callable=AsyncMock):

        mock_settings.GEMINI_API_KEY = "test-key"
        mock_storage.return_value.download_blob.return_value = (_make_tiny_jpeg(), "image/jpeg")
        mock_vision.return_value = {"language": "English", "brand_names": []}

        db_session = _make_db_session_mock(tracking_status="PENDING", fields=[field], asset=asset)
        mock_sf.return_value.return_value = db_session

        await _autofill(asset_id, org_id)

        mock_write.assert_called_once()
        written_values = mock_write.call_args[0][0]
        assert written_values[field.id] == "English"


# ---------------------------------------------------------------------------
# Test 4: brand_names field routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brand_names_field_routing():
    """brand_names auto_fill_type joins list with ', '."""
    from app.services.ai_autofill import _autofill

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()
    field = _make_field("brand_names")
    asset = _make_asset(asset_format="IMAGE")

    with patch("app.services.ai_autofill.get_session_factory") as mock_sf, \
         patch("app.services.ai_autofill.settings") as mock_settings, \
         patch("app.services.ai_autofill.get_object_storage") as mock_storage, \
         patch("app.services.ai_autofill._run_vision", new_callable=AsyncMock) as mock_vision, \
         patch("app.services.ai_autofill._write_values", new_callable=AsyncMock) as mock_write, \
         patch("app.services.ai_autofill._set_status", new_callable=AsyncMock):

        mock_settings.GEMINI_API_KEY = "test-key"
        mock_storage.return_value.download_blob.return_value = (_make_tiny_jpeg(), "image/jpeg")
        mock_vision.return_value = {"language": "English", "brand_names": ["Nike", "Adidas"]}

        db_session = _make_db_session_mock(tracking_status="PENDING", fields=[field], asset=asset)
        mock_sf.return_value.return_value = db_session

        await _autofill(asset_id, org_id)

        mock_write.assert_called_once()
        written_values = mock_write.call_args[0][0]
        assert written_values[field.id] == "Nike, Adidas"


# ---------------------------------------------------------------------------
# Test 5: vo_transcript field routing from Whisper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vo_transcript_field_routing():
    """vo_transcript auto_fill_type populates from audio transcription response text."""
    from app.services.ai_autofill import _autofill

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()
    field = _make_field("vo_transcript")
    asset = _make_asset(asset_format="VIDEO")

    with patch("app.services.ai_autofill.get_session_factory") as mock_sf, \
         patch("app.services.ai_autofill.settings") as mock_settings, \
         patch("app.services.ai_autofill.get_object_storage") as mock_storage, \
         patch("app.services.ai_autofill._run_audio", new_callable=AsyncMock) as mock_audio_run, \
         patch("app.services.ai_autofill._extract_audio_bytes", new_callable=AsyncMock) as mock_audio, \
         patch("app.services.ai_autofill._write_values", new_callable=AsyncMock) as mock_write, \
         patch("app.services.ai_autofill._set_status", new_callable=AsyncMock):

        mock_settings.GEMINI_API_KEY = "test-key"
        mock_storage.return_value.download_blob.return_value = (b"fakevideo", "video/mp4")
        mock_audio.return_value = b"fakeaudio" * 200  # > 1000 bytes
        mock_audio_run.return_value = {"text": "Hello world", "language": "en"}

        db_session = _make_db_session_mock(tracking_status="PENDING", fields=[field], asset=asset)
        mock_sf.return_value.return_value = db_session

        await _autofill(asset_id, org_id)

        mock_write.assert_called_once()
        written_values = mock_write.call_args[0][0]
        assert written_values[field.id] == "Hello world"


# ---------------------------------------------------------------------------
# Test 6: vo_transcript truncation at 2000 chars
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vo_transcript_truncation():
    """vo_transcript value is capped at 2000 chars."""
    from app.services.ai_autofill import _autofill

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()
    field = _make_field("vo_transcript")
    asset = _make_asset(asset_format="VIDEO")
    long_text = "x" * 3000

    with patch("app.services.ai_autofill.get_session_factory") as mock_sf, \
         patch("app.services.ai_autofill.settings") as mock_settings, \
         patch("app.services.ai_autofill.get_object_storage") as mock_storage, \
         patch("app.services.ai_autofill._run_audio", new_callable=AsyncMock) as mock_audio_run, \
         patch("app.services.ai_autofill._extract_audio_bytes", new_callable=AsyncMock) as mock_audio, \
         patch("app.services.ai_autofill._write_values", new_callable=AsyncMock) as mock_write, \
         patch("app.services.ai_autofill._set_status", new_callable=AsyncMock):

        mock_settings.GEMINI_API_KEY = "test-key"
        mock_storage.return_value.download_blob.return_value = (b"fakevideo", "video/mp4")
        mock_audio.return_value = b"fakeaudio" * 200
        mock_audio_run.return_value = {"text": long_text, "language": "en"}

        db_session = _make_db_session_mock(tracking_status="PENDING", fields=[field], asset=asset)
        mock_sf.return_value.return_value = db_session

        await _autofill(asset_id, org_id)

        mock_write.assert_called_once()
        written_values = mock_write.call_args[0][0]
        assert len(written_values[field.id]) == 2000


# ---------------------------------------------------------------------------
# Test 7: vo_language field routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vo_language_field_routing():
    """vo_language auto_fill_type populates language from audio transcription response."""
    from app.services.ai_autofill import _autofill

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()
    field = _make_field("vo_language")
    asset = _make_asset(asset_format="VIDEO")

    with patch("app.services.ai_autofill.get_session_factory") as mock_sf, \
         patch("app.services.ai_autofill.settings") as mock_settings, \
         patch("app.services.ai_autofill.get_object_storage") as mock_storage, \
         patch("app.services.ai_autofill._run_audio", new_callable=AsyncMock) as mock_audio_run, \
         patch("app.services.ai_autofill._extract_audio_bytes", new_callable=AsyncMock) as mock_audio, \
         patch("app.services.ai_autofill._write_values", new_callable=AsyncMock) as mock_write, \
         patch("app.services.ai_autofill._set_status", new_callable=AsyncMock):

        mock_settings.GEMINI_API_KEY = "test-key"
        mock_storage.return_value.download_blob.return_value = (b"fakevideo", "video/mp4")
        mock_audio.return_value = b"fakeaudio" * 200
        mock_audio_run.return_value = {"text": "Hola", "language": "es"}

        db_session = _make_db_session_mock(tracking_status="PENDING", fields=[field], asset=asset)
        mock_sf.return_value.return_value = db_session

        await _autofill(asset_id, org_id)

        mock_write.assert_called_once()
        written_values = mock_write.call_args[0][0]
        assert written_values[field.id] == "es"


# ---------------------------------------------------------------------------
# Test 8: campaign_name field routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_campaign_name_field_routing():
    """campaign_name auto_fill_type populates from asset.campaign_name."""
    from app.services.ai_autofill import _autofill

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()
    field = _make_field("campaign_name")
    asset = _make_asset(campaign_name="Summer Campaign")

    with patch("app.services.ai_autofill.get_session_factory") as mock_sf, \
         patch("app.services.ai_autofill.settings") as mock_settings, \
         patch("app.services.ai_autofill.get_object_storage") as mock_storage, \
         patch("app.services.ai_autofill._write_values", new_callable=AsyncMock) as mock_write, \
         patch("app.services.ai_autofill._set_status", new_callable=AsyncMock):

        mock_settings.GEMINI_API_KEY = "test-key"
        mock_storage.return_value.download_blob.return_value = (_make_tiny_jpeg(), "image/jpeg")

        db_session = _make_db_session_mock(tracking_status="PENDING", fields=[field], asset=asset)
        mock_sf.return_value.return_value = db_session

        await _autofill(asset_id, org_id)

        mock_write.assert_called_once()
        written_values = mock_write.call_args[0][0]
        assert written_values[field.id] == "Summer Campaign"


# ---------------------------------------------------------------------------
# Test 9: ad_name field routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ad_name_field_routing():
    """ad_name auto_fill_type populates from asset.ad_name."""
    from app.services.ai_autofill import _autofill

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()
    field = _make_field("ad_name")
    asset = _make_asset(ad_name="Ad Variant A")

    with patch("app.services.ai_autofill.get_session_factory") as mock_sf, \
         patch("app.services.ai_autofill.settings") as mock_settings, \
         patch("app.services.ai_autofill.get_object_storage") as mock_storage, \
         patch("app.services.ai_autofill._write_values", new_callable=AsyncMock) as mock_write, \
         patch("app.services.ai_autofill._set_status", new_callable=AsyncMock):

        mock_settings.GEMINI_API_KEY = "test-key"
        mock_storage.return_value.download_blob.return_value = (_make_tiny_jpeg(), "image/jpeg")

        db_session = _make_db_session_mock(tracking_status="PENDING", fields=[field], asset=asset)
        mock_sf.return_value.return_value = db_session

        await _autofill(asset_id, org_id)

        mock_write.assert_called_once()
        written_values = mock_write.call_args[0][0]
        assert written_values[field.id] == "Ad Variant A"


# ---------------------------------------------------------------------------
# Test 10: fixed_value field routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fixed_value_field_routing():
    """fixed_value auto_fill_type populates from field.default_value."""
    from app.services.ai_autofill import _autofill

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()
    field = _make_field("fixed_value", default_value="Final")
    asset = _make_asset()

    with patch("app.services.ai_autofill.get_session_factory") as mock_sf, \
         patch("app.services.ai_autofill.settings") as mock_settings, \
         patch("app.services.ai_autofill.get_object_storage") as mock_storage, \
         patch("app.services.ai_autofill._write_values", new_callable=AsyncMock) as mock_write, \
         patch("app.services.ai_autofill._set_status", new_callable=AsyncMock):

        mock_settings.GEMINI_API_KEY = "test-key"
        mock_storage.return_value.download_blob.return_value = (_make_tiny_jpeg(), "image/jpeg")

        db_session = _make_db_session_mock(tracking_status="PENDING", fields=[field], asset=asset)
        mock_sf.return_value.return_value = db_session

        await _autofill(asset_id, org_id)

        mock_write.assert_called_once()
        written_values = mock_write.call_args[0][0]
        assert written_values[field.id] == "Final"


# ---------------------------------------------------------------------------
# Test 11: GEMINI_API_KEY=None graceful no-op
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_api_key_graceful():
    """settings.GEMINI_API_KEY=None: no Gemini calls; AI fields get default_value fallback."""
    from app.services.ai_autofill import _autofill

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()
    field = _make_field("language", default_value="Unknown")
    asset = _make_asset(asset_format="IMAGE")

    with patch("app.services.ai_autofill.get_session_factory") as mock_sf, \
         patch("app.services.ai_autofill.settings") as mock_settings, \
         patch("app.services.ai_autofill.get_object_storage") as mock_storage, \
         patch("app.services.ai_autofill.genai") as mock_genai, \
         patch("app.services.ai_autofill._write_values", new_callable=AsyncMock) as mock_write, \
         patch("app.services.ai_autofill._set_status", new_callable=AsyncMock):

        mock_settings.GEMINI_API_KEY = None
        mock_storage.return_value.download_blob.return_value = (_make_tiny_jpeg(), "image/jpeg")

        db_session = _make_db_session_mock(tracking_status="PENDING", fields=[field], asset=asset)
        mock_sf.return_value.return_value = db_session

        await _autofill(asset_id, org_id)

        # Gemini client should never be instantiated
        mock_genai.Client.assert_not_called()
        # But the field should still get written with default_value
        mock_write.assert_called_once()
        written_values = mock_write.call_args[0][0]
        assert written_values[field.id] == "Unknown"


# ---------------------------------------------------------------------------
# Test 12: Image >4MB is downsampled
# ---------------------------------------------------------------------------

def test_image_downsample():
    """Image >4MB is downsampled to <=1568px on longest edge."""
    from app.services.ai_autofill import _downsample_image
    from PIL import Image

    large_bytes = _make_large_jpeg(5.0)
    assert len(large_bytes) > 4 * 1024 * 1024

    result = _downsample_image(large_bytes, "image/jpeg")

    img = Image.open(io.BytesIO(result))
    w, h = img.size
    assert max(w, h) <= 1568, f"Expected longest edge <=1568, got {max(w, h)}"


# ---------------------------------------------------------------------------
# Test 13: Exception sets tracking status to FAILED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exception_sets_failed():
    """Exception during inference sets tracking status to FAILED."""
    from app.services.ai_autofill import run_autofill_for_asset

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()

    with patch("app.services.ai_autofill._autofill", new_callable=AsyncMock) as mock_autofill, \
         patch("app.services.ai_autofill._set_status", new_callable=AsyncMock) as mock_set_status:

        mock_autofill.side_effect = RuntimeError("Gemini connection error")

        await run_autofill_for_asset(asset_id, org_id)

        mock_set_status.assert_called_once_with(asset_id, "FAILED")


# ---------------------------------------------------------------------------
# Test 14: FAILED status resets to PENDING on next sync (D-12)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failed_resets_to_pending():
    """FAILED tracking row resets to PENDING and inference proceeds (D-12)."""
    from app.services.ai_autofill import _autofill

    asset_id = uuid.uuid4()
    org_id = uuid.uuid4()
    field = _make_field("campaign_name", default_value="fallback")
    asset = _make_asset(campaign_name="Retry Campaign")

    with patch("app.services.ai_autofill.get_session_factory") as mock_sf, \
         patch("app.services.ai_autofill.settings") as mock_settings, \
         patch("app.services.ai_autofill.get_object_storage") as mock_storage, \
         patch("app.services.ai_autofill._write_values", new_callable=AsyncMock) as mock_write, \
         patch("app.services.ai_autofill._set_status", new_callable=AsyncMock):

        mock_settings.GEMINI_API_KEY = None  # No AI; campaign_name is deterministic
        mock_storage.return_value.download_blob.return_value = (_make_tiny_jpeg(), "image/jpeg")

        # FAILED status — helper includes extra execute for FAILED→PENDING update
        db_session = _make_db_session_mock(tracking_status="FAILED", fields=[field], asset=asset)
        mock_sf.return_value.return_value = db_session

        # Should NOT raise like COMPLETE does — should proceed to inference
        await _autofill(asset_id, org_id)

        # Verify _write_values was called (inference proceeded)
        mock_write.assert_called_once()
        written_values = mock_write.call_args[0][0]
        assert written_values[field.id] == "Retry Campaign"
