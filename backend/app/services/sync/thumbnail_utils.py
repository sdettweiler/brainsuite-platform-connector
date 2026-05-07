import asyncio
import logging
import os
import re
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

_UNSAFE = re.compile(r"[^\w\-]")


def _safe_id(ad_id: str) -> str:
    return _UNSAFE.sub("_", ad_id)[:80]


def is_raw_cdn_url(url: Optional[str]) -> bool:
    """Return True if url is a raw platform CDN link we should not persist."""
    if not url:
        return False
    return (
        "img.youtube.com" in url
        or "ytimg.com" in url
        or "p16-ad-sg.ibyteimg.com" in url
        or "p16-ad.tiktokcdn.com" in url
        or "p19-ad.tiktokcdn.com" in url
    )


async def extract_first_frame_and_upload(
    local_video_path: str,
    org_id: str,
    ad_id: str,
    prefix: str,
    obj_storage,
) -> Optional[str]:
    """Extract the first video frame via ffmpeg and upload to object storage.

    Returns the served URL, or None if extraction fails.
    """
    filename = f"thumb_{prefix}_{_safe_id(ad_id)}.jpg"
    relative_path = f"creatives/{org_id}/{filename}"

    if obj_storage.file_exists(relative_path):
        return obj_storage.served_url(relative_path)

    tmp_thumb = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmp_thumb = f.name

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["ffmpeg", "-y", "-i", local_video_path, "-frames:v", "1", "-q:v", "2", tmp_thumb],
                capture_output=True,
                timeout=30,
            ),
        )

        if result.returncode == 0 and os.path.exists(tmp_thumb) and os.path.getsize(tmp_thumb) > 100:
            with open(tmp_thumb, "rb") as f:
                thumb_bytes = f.read()
            served_url = obj_storage.upload_bytes(thumb_bytes, relative_path, "image/jpeg")
            logger.info("Extracted first-frame thumbnail for ad %s: %s (%d bytes)", ad_id, filename, len(thumb_bytes))
            return served_url

        logger.warning(
            "ffmpeg first-frame extraction failed for ad %s (returncode=%s stderr=%s)",
            ad_id, result.returncode, (result.stderr or b"")[:200],
        )
    except Exception as e:
        logger.warning("First-frame extraction failed for ad %s: %s", ad_id, e, exc_info=True)
    finally:
        if tmp_thumb and os.path.exists(tmp_thumb):
            try:
                os.unlink(tmp_thumb)
            except OSError:
                pass
    return None
