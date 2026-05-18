"""Shared video utility functions (Phase 23).

Extracted from dv360_sync.py:1423 so backfill_job and all sync services can share
duration extraction without method-level coupling.
"""
import json
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)


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
