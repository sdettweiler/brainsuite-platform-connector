"""AI metadata auto-fill service.

Triggered after asset binary is stored to MinIO during sync (D-02).
Uses GPT-4o Vision for image/video frame analysis and Whisper for audio
transcription. Writes results directly to AssetMetadataValue (D-04).

Session-per-operation pattern (never hold session during OpenAI calls) — D-10.
"""
import asyncio
import base64
import io
import logging
import uuid
from datetime import datetime
from typing import Optional

from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.db.base import get_session_factory
from app.models.ai_inference import AIInferenceTracking
from app.models.metadata import MetadataField
from app.models.creative import CreativeAsset, AssetMetadataValue
from app.services.object_storage import get_object_storage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants: auto_fill_type routing sets
# ---------------------------------------------------------------------------

AUTO_FILL_TYPE_VISION = {"language", "brand_names"}
AUTO_FILL_TYPE_AUDIO = {"vo_transcript", "vo_language"}
AUTO_FILL_TYPE_SYNC = {"campaign_name", "ad_name"}
AUTO_FILL_TYPE_FIXED = {"fixed_value"}

TRANSCRIPT_MAX_CHARS = 2000

# ---------------------------------------------------------------------------
# Language → locale code normalization
# Maps full names, lowercase names, and ISO 639-1 codes to BCP 47 locale codes.
# ---------------------------------------------------------------------------

_LANGUAGE_TO_LOCALE: dict[str, str] = {
    # Full names (from GPT-4o)
    "arabic": "ar_SA", "bulgarian": "bg_BG", "chinese": "zh_CN",
    "croatian": "hr_HR", "czech": "cs_CZ", "danish": "da_DK",
    "dutch": "nl_NL", "english": "en_US", "finnish": "fi_FI",
    "french": "fr_FR", "german": "de_DE", "greek": "el_GR",
    "hebrew": "he_IL", "hindi": "hi_IN", "hungarian": "hu_HU",
    "indonesian": "id_ID", "italian": "it_IT", "japanese": "ja_JP",
    "korean": "ko_KR", "malay": "ms_MY", "norwegian": "no_NO",
    "polish": "pl_PL", "portuguese": "pt_BR", "romanian": "ro_RO",
    "russian": "ru_RU", "slovak": "sk_SK", "slovenian": "sl_SI",
    "spanish": "es_ES", "swedish": "sv_SE", "thai": "th_TH",
    "turkish": "tr_TR", "vietnamese": "vi_VN",
    # ISO 639-1 codes (legacy stored values / Whisper short codes)
    "ar": "ar_SA", "bg": "bg_BG", "zh": "zh_CN", "hr": "hr_HR",
    "cs": "cs_CZ", "da": "da_DK", "nl": "nl_NL", "en": "en_US",
    "fi": "fi_FI", "fr": "fr_FR", "de": "de_DE", "el": "el_GR",
    "he": "he_IL", "hi": "hi_IN", "hu": "hu_HU", "id": "id_ID",
    "it": "it_IT", "ja": "ja_JP", "ko": "ko_KR", "ms": "ms_MY",
    "no": "no_NO", "pl": "pl_PL", "pt": "pt_BR", "ro": "ro_RO",
    "ru": "ru_RU", "sk": "sk_SK", "sl": "sl_SI", "es": "es_ES",
    "sv": "sv_SE", "th": "th_TH", "tr": "tr_TR", "vi": "vi_VN",
}


def _to_locale(lang: Optional[str]) -> Optional[str]:
    """Normalize any language representation to a BCP 47 locale code (e.g. en_US).

    Accepts full names ('English', 'indonesian'), ISO 639-1 codes ('en', 'id'),
    and already-normalized locale codes ('en_US'). Returns None if unrecognized.
    """
    if not lang:
        return None
    normalized = lang.strip().lower().replace("-", "_")
    # Already a locale code (e.g. 'en_US' → 'en_us' after lower)
    if "_" in normalized:
        parts = normalized.split("_")
        return f"{parts[0]}_{parts[1].upper()}"
    return _LANGUAGE_TO_LOCALE.get(normalized)


# ---------------------------------------------------------------------------
# Pydantic model for GPT-4o Vision structured output
# ---------------------------------------------------------------------------

class VisionResult(BaseModel):
    language: Optional[str] = None
    brand_names: list[str] = []


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_autofill_for_asset(asset_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """Entry point — called via asyncio.create_task() from sync services.

    Wraps _autofill() in a top-level try/except so exceptions are logged
    and the tracking row is set to FAILED rather than silently swallowed
    (Pitfall 3 from RESEARCH.md).
    """
    try:
        await _autofill(asset_id, org_id)
    except Exception as exc:
        logger.exception("auto-fill failed for asset_id=%s: %s", asset_id, exc)
        await _set_status(asset_id, "FAILED")


# ---------------------------------------------------------------------------
# Core orchestration
# ---------------------------------------------------------------------------

async def _autofill(asset_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """4-phase auto-fill: read → download → infer → write."""

    # ------------------------------------------------------------------
    # Phase 1: DB read (close session before any HTTP calls)
    # ------------------------------------------------------------------
    async with get_session_factory()() as db:
        # Insert tracking row — silently ignored if asset_id already exists
        await db.execute(
            pg_insert(AIInferenceTracking).values(
                id=uuid.uuid4(),
                asset_id=asset_id,
                org_id=org_id,
                ai_inference_status="PENDING",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ).on_conflict_do_nothing(index_elements=["asset_id"])
        )
        await db.commit()

        # COMPLETE guard: do not re-run inference on already-processed assets (AI-06)
        tracking = (
            await db.execute(
                select(AIInferenceTracking).where(AIInferenceTracking.asset_id == asset_id)
            )
        ).scalar_one_or_none()

        if tracking and tracking.ai_inference_status == "COMPLETE":
            return

        # D-12: FAILED status resets to PENDING to allow retry
        if tracking and tracking.ai_inference_status == "FAILED":
            await db.execute(
                update(AIInferenceTracking)
                .where(AIInferenceTracking.asset_id == asset_id)
                .values(ai_inference_status="PENDING", updated_at=datetime.utcnow())
            )
            await db.commit()

        # Load auto-fill enabled fields for this org
        fields = (
            await db.execute(
                select(MetadataField).where(
                    MetadataField.organization_id == org_id,
                    MetadataField.auto_fill_enabled.is_(True),
                    MetadataField.is_active.is_(True),
                )
            )
        ).scalars().all()

        if not fields:
            await _set_status(asset_id, "COMPLETE")
            return

        # Load asset data
        asset = await db.get(CreativeAsset, asset_id)
        if not asset:
            logger.warning("auto-fill: asset_id=%s not found", asset_id)
            return

        # Collect data before session closes
        field_data = [(f.id, f.auto_fill_type, f.default_value) for f in fields]
        asset_format = asset.asset_format or "IMAGE"
        asset_url = asset.asset_url or ""
        campaign_name = asset.campaign_name
        ad_name = asset.ad_name
        # Session closes here (exits async with block)

    # ------------------------------------------------------------------
    # Phase 2: Download asset binary (no DB session held)
    # ------------------------------------------------------------------
    storage = get_object_storage()
    # Derive S3 key: strip leading "/" and remove "objects/" prefix
    s3_key = asset_url.lstrip("/")
    if s3_key.startswith("objects/"):
        s3_key = s3_key[len("objects/"):]

    needs_vision = any(t in AUTO_FILL_TYPE_VISION for _, t, _ in field_data)
    needs_audio = any(t in AUTO_FILL_TYPE_AUDIO for _, t, _ in field_data)

    asset_bytes: Optional[bytes] = None
    content_type: str = "image/jpeg"

    if (needs_vision or needs_audio) and s3_key:
        asset_bytes, ct = storage.download_blob(s3_key)
        content_type = ct or "application/octet-stream"

    # ------------------------------------------------------------------
    # Phase 3: Run inference (no DB session held)
    # ------------------------------------------------------------------
    vision_result: dict = {}
    audio_result: dict = {}

    if settings.OPENAI_API_KEY:
        if needs_vision and asset_bytes:
            vision_result = await _run_vision(asset_bytes, content_type, asset_format)

        if needs_audio and asset_bytes:
            audio_bytes = await _extract_audio_bytes(asset_bytes)
            if audio_bytes and len(audio_bytes) >= 1000:
                audio_result = await _run_whisper(audio_bytes)

    # ------------------------------------------------------------------
    # Phase 4: Route values and write to DB
    # ------------------------------------------------------------------
    values_to_write: dict[uuid.UUID, str] = {}

    for field_id, auto_fill_type, default_value in field_data:
        value = None

        if auto_fill_type == "language":
            value = vision_result.get("language") or default_value

        elif auto_fill_type == "brand_names":
            brand_list = vision_result.get("brand_names", [])
            value = ", ".join(brand_list) if brand_list else default_value

        elif auto_fill_type == "vo_transcript":
            text = audio_result.get("text", "")
            value = text[:TRANSCRIPT_MAX_CHARS] if text else default_value

        elif auto_fill_type == "vo_language":
            value = audio_result.get("language") or default_value

        elif auto_fill_type == "campaign_name":
            value = campaign_name or default_value

        elif auto_fill_type == "ad_name":
            value = ad_name or default_value

        elif auto_fill_type == "fixed_value":
            value = default_value

        if value is not None:
            values_to_write[field_id] = value

    await _write_values(values_to_write, asset_id)
    await _set_status(asset_id, "COMPLETE")


# ---------------------------------------------------------------------------
# DB helpers (each opens its own session)
# ---------------------------------------------------------------------------

async def _write_values(values: dict, asset_id: uuid.UUID) -> None:
    """Upsert AssetMetadataValue rows for the given asset."""
    if not values:
        return

    async with get_session_factory()() as db:
        for field_id, value in values.items():
            existing = (
                await db.execute(
                    select(AssetMetadataValue).where(
                        AssetMetadataValue.asset_id == asset_id,
                        AssetMetadataValue.field_id == field_id,
                    )
                )
            ).scalar_one_or_none()

            if existing:
                existing.value = value
                existing.updated_at = datetime.utcnow()
                db.add(existing)
            else:
                db.add(
                    AssetMetadataValue(
                        asset_id=asset_id,
                        field_id=field_id,
                        value=value,
                    )
                )
        await db.commit()


async def _set_status(asset_id: uuid.UUID, status: str) -> None:
    """Open a new session, update tracking row status, commit."""
    async with get_session_factory()() as db:
        await db.execute(
            update(AIInferenceTracking)
            .where(AIInferenceTracking.asset_id == asset_id)
            .values(ai_inference_status=status, updated_at=datetime.utcnow())
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Vision inference
# ---------------------------------------------------------------------------

async def _run_vision(
    asset_bytes: bytes,
    content_type: str,
    asset_format: str,
) -> dict:
    """Call GPT-4o Vision and return {language, brand_names}.

    For VIDEO assets, extract the first frame as JPEG.
    Downsamples images over 4 MB before base64 encoding (AI-05).
    """
    image_bytes = asset_bytes
    image_content_type = content_type

    if asset_format == "VIDEO":
        frame = _extract_first_frame(asset_bytes)
        if frame is None:
            return {}
        image_bytes = frame
        image_content_type = "image/jpeg"

    # Downsample if > 4 MB
    image_bytes = _downsample_image(image_bytes, image_content_type)

    # Build base64 data URI
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    mime = image_content_type if image_content_type.startswith("image/") else "image/jpeg"

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        response = await client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze this ad creative image (which may be a frame from a video ad).\n\n"
                                "Return:\n"
                                "- language: The PRIMARY language of the ad's TARGET AUDIENCE — "
                                "i.e. the language used in the voiceover, body copy, and majority of "
                                "the ad's textual content. Ignore incidental English words (brand names, "
                                "product names, hashtags, or short English phrases that appear in "
                                "otherwise non-English ads). If the ad is Indonesian, Thai, Arabic, etc., "
                                "return that language even if some English text is visible. "
                                "Return the full English language name (e.g. 'Indonesian', 'German', 'English').\n"
                                "- brand_names: List of brand names visually present in the ad "
                                "(logos, product packaging, watermarks). Empty list if none."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                    ],
                }
            ],
            response_format=VisionResult,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            return {}
        return {
            "language": _to_locale(parsed.language),
            "brand_names": parsed.brand_names,
        }
    except Exception as exc:
        logger.warning("GPT-4o Vision call failed: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Audio inference
# ---------------------------------------------------------------------------

async def _extract_audio_bytes(video_bytes: bytes) -> Optional[bytes]:
    """Extract audio from video as 16kHz mono WAV bytes using ffmpeg.

    Uses imageio_ffmpeg.get_ffmpeg_exe() as the binary (not system ffmpeg).
    Returns None if audio stream is absent or too short.
    """
    try:
        import imageio_ffmpeg

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        proc = await asyncio.create_subprocess_exec(
            ffmpeg_exe,
            "-i", "pipe:0",
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate(input=video_bytes)
        if proc.returncode != 0 or len(stdout) < 1000:
            return None
        return stdout
    except Exception as exc:
        logger.warning("Audio extraction failed: %s", exc)
        return None


async def _run_whisper(audio_bytes: bytes) -> dict:
    """Transcribe audio via Whisper API. Returns {text, language}."""
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"  # Required: BytesIO needs .name with valid extension

        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
        )
        return {
            "text": transcript.text or "",
            "language": _to_locale(getattr(transcript, "language", "") or "") or "",
        }
    except Exception as exc:
        logger.warning("Whisper API call failed: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Image utilities
# ---------------------------------------------------------------------------

def _downsample_image(image_bytes: bytes, content_type: str) -> bytes:
    """Downsample image to <=1568px longest edge if > 4 MB (AI-05).

    Uses Pillow LANCZOS filter. Returns original bytes if under threshold.
    """
    if len(image_bytes) <= 4 * 1024 * 1024:
        return image_bytes

    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        img.thumbnail((1568, 1568), Image.LANCZOS)
        buf = io.BytesIO()
        fmt = "PNG" if content_type == "image/png" else "JPEG"
        img.save(buf, format=fmt, quality=85)
        return buf.getvalue()
    except Exception as exc:
        logger.warning("Image downsample failed: %s", exc)
        return image_bytes


def _extract_first_frame(video_bytes: bytes) -> Optional[bytes]:
    """Extract first frame from video as JPEG bytes via imageio-ffmpeg.

    Returns JPEG bytes or None on failure.
    """
    import tempfile
    import os

    try:
        import imageio_ffmpeg
        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        try:
            reader = imageio_ffmpeg.read_frames(tmp_path)
            meta = next(reader)  # First item is metadata dict
            frame_bytes = next(reader)  # First actual frame (raw RGB)
            w, h = meta["size"]
            img = Image.frombytes("RGB", (w, h), frame_bytes)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
        finally:
            os.unlink(tmp_path)
    except Exception as exc:
        logger.warning("First frame extraction failed: %s", exc)
        return None
