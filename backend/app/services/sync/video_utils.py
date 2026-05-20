"""Shared video utility functions (Phase 23).

Extracted from dv360_sync.py:1423 so backfill_job and all sync services can share
duration extraction without method-level coupling.
"""
import json
import os
import subprocess
import tempfile
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def probe_video_info_from_bytes(file_bytes: bytes, suffix: str = ".mp4") -> tuple[Optional[float], Optional[int], Optional[int]]:
    """Write bytes to a temp file, probe duration + dimensions with ffprobe.

    Returns (duration_seconds, width_px, height_px). Any field may be None on failure.
    """
    if not file_bytes:
        return None, None, None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(file_bytes)
        tmp.flush()
        tmp.close()
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", tmp.name],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = None
                raw_dur = data.get("format", {}).get("duration")
                if raw_dur:
                    try:
                        duration = float(raw_dur)
                    except ValueError:
                        pass
                width = height = None
                for stream in data.get("streams", []):
                    if stream.get("codec_type") == "video":
                        width = stream.get("width")
                        height = stream.get("height")
                        break
                return duration, width, height
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            logger.debug("ffprobe failed for %s: %s", tmp.name, e)
        return None, None, None
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def probe_duration_from_bytes(file_bytes: bytes, suffix: str = ".mp4") -> Optional[float]:
    """Write bytes to a temp file, probe duration with ffprobe, clean up.

    Used by Meta, TikTok, and any sync that has bytes in memory rather than a path.
    Returns None when ffprobe fails or file_bytes is empty.
    """
    if not file_bytes:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(file_bytes)
        tmp.flush()
        tmp.close()
        return get_video_duration(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def get_video_duration(file_path: str) -> Optional[float]:
    """Extract video duration in seconds via ffprobe.

    Returns None when ffprobe fails or is unavailable.
    Identical behavior to the original dv360_sync._get_video_duration.
    """
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", file_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = data.get("format", {}).get("duration")
            if duration:
                return float(duration)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        logger.debug("ffprobe failed for %s: %s", file_path, e)
    return None
