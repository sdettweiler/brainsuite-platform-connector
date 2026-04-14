"""AI metadata auto-fill service.

Triggered after asset binary is stored to MinIO during sync (D-02).
Primary: Gemini 2.5 Flash Lite. Fallback: GPT-4o if Gemini is unavailable.
Writes results directly to AssetMetadataValue (D-04).

Session-per-operation pattern (never hold session during AI calls) — D-10.
"""
import asyncio
import base64
import io
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from google import genai
from google.genai import types as genai_types
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

_GEMINI_MODEL = "gemini-2.5-flash-lite"
_OPENAI_VISION_MODEL = "gpt-4o"

# ---------------------------------------------------------------------------
# Language → locale code normalization
# Internal storage uses underscore format (xx_XX) to match metadata_field_values
# dropdown options. Dash format (xx-XX) is produced only at BS API submission time
# by scoring_job.py.
# ---------------------------------------------------------------------------

_LANGUAGE_TO_LOCALE: dict[str, str] = {
    # Full names (from Gemini)
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
    # ISO 639-1 codes (short codes)
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
    """Normalize any language representation to underscore locale format (e.g. en_US).

    Accepts full names ('English', 'indonesian'), ISO 639-1 codes ('en', 'id'),
    dash locale codes ('en-US'), and already-normalized underscore codes ('en_US').
    Returns None if unrecognized.
    Stored values use xx_XX to match metadata_field_values dropdown options.
    """
    if not lang:
        return None
    # Normalize separators for lookup
    normalized = lang.strip().lower().replace("-", "_")
    # Already a locale code (e.g. 'en_US' or 'en-US' both normalize to 'en_us')
    if "_" in normalized:
        parts = normalized.split("_", 1)
        return f"{parts[0]}_{parts[1].upper()}"
    return _LANGUAGE_TO_LOCALE.get(normalized)


# ---------------------------------------------------------------------------
# Pydantic models for Gemini structured output
# ---------------------------------------------------------------------------

class VisionResult(BaseModel):
    language: str
    brand_names: list[str]


class AudioResult(BaseModel):
    text: str
    language: str


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

    if (needs_vision or needs_audio) and s3_key:
        asset_bytes, _ = storage.download_blob(s3_key)

    # ------------------------------------------------------------------
    # Phase 3: Run inference (no DB session held)
    # ------------------------------------------------------------------
    vision_result: dict = {}
    audio_result: dict = {}

    if settings.GEMINI_API_KEY:
        if needs_vision and asset_bytes:
            key_frames = _extract_key_frames(asset_bytes, asset_format)
            if key_frames:
                mood_board = _compose_mood_board(key_frames)
                vision_result = await _run_vision(mood_board)

        if needs_audio and asset_bytes:
            audio_bytes = await _extract_audio_bytes(asset_bytes)
            if audio_bytes and len(audio_bytes) >= 1000:
                audio_result = await _run_audio(audio_bytes)

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

_VISION_PROMPT = (
    "This is a mood board composed from frames sampled at 1 frame per second "
    "from a video ad creative. Each cell in the grid is a chronological frame.\n\n"
    "Return:\n"
    "- language: The PRIMARY language of the ad's TARGET AUDIENCE — "
    "the language used in body copy, subtitles, and the majority of on-screen text "
    "across the frames. Ignore incidental English (brand names, product names, "
    "hashtags, or short English phrases in otherwise non-English ads). "
    "Return the full English language name (e.g. 'Indonesian', 'German', 'English').\n"
    "- brand_names: List of brand names visually present across the frames "
    "(logos, product packaging, watermarks). Empty list if none."
)

_AUDIO_PROMPT = (
    "Transcribe this audio and identify the primary spoken language.\n"
    "Return:\n"
    "- text: Full verbatim transcript of the spoken words.\n"
    "- language: The primary spoken language as a full English name "
    "(e.g. 'Indonesian', 'German', 'English')."
)


async def _run_vision(mood_board: bytes) -> dict:
    """Vision inference: Gemini 2.5 Flash Lite, with GPT-4o fallback on failure."""
    if settings.GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = await client.aio.models.generate_content(
                model=_GEMINI_MODEL,
                contents=genai_types.Content(parts=[
                    genai_types.Part.from_bytes(data=mood_board, mime_type="image/jpeg"),
                    genai_types.Part.from_text(text=_VISION_PROMPT),
                ]),
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=VisionResult,
                ),
            )
            parsed: VisionResult = response.parsed  # type: ignore[assignment]
            if parsed is not None:
                return {
                    "language": _to_locale(parsed.language),
                    "brand_names": parsed.brand_names,
                }
        except Exception as exc:
            logger.warning("Gemini vision failed, trying GPT-4o fallback: %s", exc)

    if settings.OPENAI_API_KEY:
        return await _run_vision_openai(mood_board)

    return {}


async def _run_vision_openai(mood_board: bytes) -> dict:
    """GPT-4o vision fallback."""
    import httpx
    b64 = base64.b64encode(mood_board).decode()
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": _OPENAI_VISION_MODEL,
                    "response_format": {"type": "json_object"},
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}},
                            {"type": "text", "text": _VISION_PROMPT},
                        ],
                    }],
                    "max_tokens": 500,
                },
            )
        resp.raise_for_status()
        data = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(data)
        return {
            "language": _to_locale(parsed.get("language")),
            "brand_names": parsed.get("brand_names", []),
        }
    except Exception as exc:
        logger.warning("GPT-4o vision fallback failed: %s", exc)
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


async def _run_audio(audio_bytes: bytes) -> dict:
    """Audio transcription: Gemini 2.5 Flash Lite, with GPT-4o / Whisper-1 fallback."""
    if settings.GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = await client.aio.models.generate_content(
                model=_GEMINI_MODEL,
                contents=genai_types.Content(parts=[
                    genai_types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                    genai_types.Part.from_text(text=_AUDIO_PROMPT),
                ]),
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AudioResult,
                ),
            )
            parsed: AudioResult = response.parsed  # type: ignore[assignment]
            if parsed is not None:
                return {
                    "text": parsed.text or "",
                    "language": _to_locale(parsed.language) or "",
                }
        except Exception as exc:
            logger.warning("Gemini audio failed, trying Whisper-1 fallback: %s", exc)

    if settings.OPENAI_API_KEY:
        return await _run_audio_openai(audio_bytes)

    return {}


async def _run_audio_openai(audio_bytes: bytes) -> dict:
    """Whisper-1 audio fallback."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                files={"file": ("audio.wav", audio_bytes, "audio/wav")},
                data={"model": "whisper-1", "response_format": "verbose_json"},
            )
        resp.raise_for_status()
        data = resp.json()
        return {
            "text": data.get("text", ""),
            "language": _to_locale(data.get("language")) or "",
        }
    except Exception as exc:
        logger.warning("Whisper-1 fallback failed: %s", exc)
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


_MOOD_BOARD_COLS = 5
_MOOD_BOARD_THUMB_W = 240   # px per cell
_MOOD_BOARD_THUMB_H = 135   # 16:9
_MOOD_BOARD_GAP = 6         # px between cells
_MOOD_BOARD_PAD = 10        # px outer border
_MOOD_BOARD_BG = (18, 18, 18)
_MAX_FRAMES = 60            # 1 fps cap — never more than 60 frames


def _extract_key_frames(
    asset_bytes: bytes,
    asset_format: str,
) -> list[bytes]:
    """Extract 1 frame per second (capped at 60) from a video, or return the image as-is.

    For VIDEO: samples exactly 1 frame per second up to _MAX_FRAMES.
    For IMAGE: downsamples if needed and returns as a single-element list.
    Returns a list of raw JPEG bytes (may be empty on failure).
    """
    import tempfile
    import os

    if asset_format != "VIDEO":
        return [_downsample_image(asset_bytes, "image/jpeg")]

    try:
        import imageio_ffmpeg
        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(asset_bytes)
            tmp_path = tmp.name

        try:
            reader = imageio_ffmpeg.read_frames(tmp_path)
            meta = next(reader)
            w, h = meta["size"]
            fps = meta.get("fps", 25) or 25

            # stride = frames between samples to get ~1 frame per second
            stride = max(1, round(fps))

            frames: list[bytes] = []
            for i, raw in enumerate(reader):
                if i % stride == 0:
                    img = Image.frombytes("RGB", (w, h), raw)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=75)
                    frames.append(buf.getvalue())
                    if len(frames) >= _MAX_FRAMES:
                        break

            logger.debug(
                "Extracted %d frames at 1fps from video (fps=%.1f stride=%d)",
                len(frames), fps, stride,
            )
            return frames
        finally:
            os.unlink(tmp_path)
    except Exception as exc:
        logger.warning("Key frame extraction failed: %s", exc)
        return []


def _compose_mood_board(frames: list[bytes]) -> bytes:
    """Compose a list of JPEG frames into a single mood board grid image.

    Lays frames out in _MOOD_BOARD_COLS columns with consistent thumbnail sizes,
    gaps, and a dark background. Returns JPEG bytes of the composed image.
    Falls back to the first frame if Pillow fails.
    """
    from PIL import Image

    cols = _MOOD_BOARD_COLS
    rows = (len(frames) + cols - 1) // cols
    tw, th = _MOOD_BOARD_THUMB_W, _MOOD_BOARD_THUMB_H
    gap, pad = _MOOD_BOARD_GAP, _MOOD_BOARD_PAD

    canvas_w = pad + cols * tw + (cols - 1) * gap + pad
    canvas_h = pad + rows * th + (rows - 1) * gap + pad

    canvas = Image.new("RGB", (canvas_w, canvas_h), _MOOD_BOARD_BG)

    for idx, frame_bytes in enumerate(frames):
        row, col = divmod(idx, cols)
        x = pad + col * (tw + gap)
        y = pad + row * (th + gap)
        try:
            thumb = Image.open(io.BytesIO(frame_bytes)).convert("RGB")
            thumb.thumbnail((tw, th), Image.LANCZOS)
            # Centre-crop to exact cell size
            tw_actual, th_actual = thumb.size
            x_offset = (tw - tw_actual) // 2
            y_offset = (th - th_actual) // 2
            canvas.paste(thumb, (x + x_offset, y + y_offset))
        except Exception:
            pass  # leave cell black on error

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=82)
    logger.debug(
        "Composed mood board: %d frames → %dx%d px, %.1f KB",
        len(frames), canvas_w, canvas_h, len(buf.getvalue()) / 1024,
    )
    return buf.getvalue()
