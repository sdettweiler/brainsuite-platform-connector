#!/usr/bin/env python3
"""
POC: Playwright-based YouTube video recorder.

Evaluates whether Playwright screen recording can serve as a viable fallback
for yt-dlp when downloading YouTube videos. yt-dlp frequently fails due to
bot detection, age-gating, and sign-in walls. This script captures the video
via actual browser playback instead of direct stream download.

Usage:
    python poc_playwright_youtube_recorder.py "https://www.youtube.com/watch?v=VIDEO_ID"
    python poc_playwright_youtube_recorder.py "https://www.youtube.com/watch?v=VIDEO_ID" \
        --api-key YOUR_KEY --output-dir /tmp/output --no-headless
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency check helpers
# ---------------------------------------------------------------------------

def _check_httpx():
    try:
        import httpx  # noqa: F401
    except ImportError:
        print("ERROR: httpx not installed. Run: pip install httpx", file=sys.stderr)
        sys.exit(1)


def _check_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        print(
            "WARNING: playwright not installed.\n"
            "  To install: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return False


def _ensure_chromium():
    """Install Playwright Chromium if not already installed."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium", "--dry-run"],
            capture_output=True,
            text=True,
        )
        if "chromium" in result.stdout.lower() and "already installed" not in result.stdout.lower():
            print("Installing Playwright Chromium browser...", file=sys.stderr)
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True,
            )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Best-effort — proceed and let Playwright raise if needed
        pass


# ---------------------------------------------------------------------------
# YouTube Data API v3 resolution fetch
# ---------------------------------------------------------------------------

DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_resolution(video_id: str, api_key: str) -> tuple[int, int]:
    """
    Query YouTube Data API v3 for video definition.

    Returns (width, height) inferred from contentDetails.definition.
    HD → 1920×1080, SD → 640×480.
    """
    import httpx

    url = (
        "https://www.googleapis.com/youtube/v3/videos"
        f"?part=contentDetails,snippet&id={video_id}&key={api_key}"
    )
    response = httpx.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()

    items = data.get("items", [])
    if not items:
        raise ValueError(f"No video found for ID: {video_id}")

    item = items[0]
    definition = item.get("contentDetails", {}).get("definition", "sd").lower()

    if definition == "hd":
        return 1920, 1080
    else:
        return 640, 480


# ---------------------------------------------------------------------------
# Playwright recording
# ---------------------------------------------------------------------------

def record_youtube_video(
    url: str,
    output_dir: Path,
    width: int,
    height: int,
    headless: bool,
) -> tuple[Path | None, float]:
    """
    Launch Chromium via Playwright, navigate to URL, record fullscreen playback.

    Returns (path_to_webm, duration_seconds) or (None, 0) on failure.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

    output_dir.mkdir(parents=True, exist_ok=True)
    record_dir = output_dir / "recording"
    record_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.perf_counter()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(
            viewport={"width": width, "height": height},
            record_video_dir=str(record_dir),
            record_video_size={"width": width, "height": height},
        )
        page = context.new_page()

        try:
            print(f"  Navigating to: {url}", file=sys.stderr)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for the video element to appear
            page.wait_for_selector("video", timeout=15000)
            print("  Video element found.", file=sys.stderr)

            # Dismiss cookie / consent dialogs if present
            for selector in [
                "button:has-text('Accept all')",
                "button:has-text('Accept')",
                "button:has-text('I agree')",
            ]:
                try:
                    page.click(selector, timeout=3000)
                    print(f"  Dismissed consent dialog: {selector}", file=sys.stderr)
                    page.wait_for_timeout(1000)
                    break
                except PlaywrightTimeout:
                    pass

            # Click the video to ensure playback starts
            try:
                page.click("video", timeout=5000)
            except PlaywrightTimeout:
                pass

            # Attempt to enter fullscreen via JavaScript
            try:
                page.evaluate("document.querySelector('video').requestFullscreen()")
                page.wait_for_timeout(500)
            except Exception:
                pass

            # Fallback: press 'f' for YouTube's native fullscreen
            try:
                page.keyboard.press("f")
                page.wait_for_timeout(500)
            except Exception:
                pass

            # Get video duration from DOM
            video_duration: float = 0.0
            for _ in range(10):
                try:
                    dur = page.evaluate("document.querySelector('video').duration")
                    if dur and not (isinstance(dur, float) and dur != dur):  # NaN check
                        video_duration = float(dur)
                        break
                except Exception:
                    pass
                page.wait_for_timeout(1000)

            if video_duration <= 0:
                print(
                    "  WARNING: Could not read video duration from DOM. "
                    "Defaulting to 30-second recording.",
                    file=sys.stderr,
                )
                video_duration = 30.0

            wait_ms = int((video_duration + 3) * 1000)
            print(
                f"  Video duration: {video_duration:.1f}s — waiting {video_duration + 3:.1f}s for full playback...",
                file=sys.stderr,
            )
            page.wait_for_timeout(wait_ms)

        finally:
            page.close()
            context.close()
            browser.close()

    t_end = time.perf_counter()
    recording_duration = t_end - t_start

    # Find the .webm file Playwright wrote
    webm_files = list(record_dir.glob("*.webm"))
    if not webm_files:
        print("  ERROR: No .webm file found after recording.", file=sys.stderr)
        return None, recording_duration

    # Pick the most recently modified file
    webm_path = max(webm_files, key=lambda p: p.stat().st_mtime)
    return webm_path, recording_duration


# ---------------------------------------------------------------------------
# FFmpeg conversion
# ---------------------------------------------------------------------------

def convert_webm_to_mp4(webm_path: Path, output_dir: Path) -> tuple[Path | None, float]:
    """
    Convert .webm to .mp4 via ffmpeg subprocess.

    Returns (mp4_path, duration_seconds) or (None, 0) if ffmpeg not found.
    """
    mp4_path = output_dir / (webm_path.stem + ".mp4")

    try:
        t_start = time.perf_counter()
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", str(webm_path),
                "-c:v", "libx264",
                "-crf", "23",
                "-preset", "fast",
                "-c:a", "aac",
                str(mp4_path),
                "-y",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        t_end = time.perf_counter()
        return mp4_path, t_end - t_start

    except FileNotFoundError:
        print(
            "  NOTE: ffmpeg not found — skipping .webm → .mp4 conversion.\n"
            "  Install ffmpeg: https://ffmpeg.org/download.html",
            file=sys.stderr,
        )
        return None, 0.0

    except subprocess.CalledProcessError as exc:
        print(f"  ERROR: ffmpeg conversion failed:\n{exc.stderr}", file=sys.stderr)
        return None, 0.0


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def _mb(path: Path) -> str:
    if path and path.exists():
        return f"{path.stat().st_size / 1_048_576:.2f} MB"
    return "N/A"


def print_timing_report(
    t_api: float,
    t_record: float,
    t_convert: float,
) -> None:
    total = t_api + t_record + t_convert
    print()
    print("=== TIMING REPORT ===")
    print(f"API fetch:    {t_api:.2f}s")
    print(f"Recording:    {t_record:.2f}s")
    print(f"Conversion:   {t_convert:.2f}s")
    print(f"Total:        {total:.2f}s")


def print_quality_report(
    width: int,
    height: int,
    webm_path: Path | None,
    mp4_path: Path | None,
) -> None:
    print()
    print("=== QUALITY REPORT ===")
    print(f"Target resolution:  {width}x{height}")
    if webm_path:
        print(f"Recorded file:      {webm_path.name} ({_mb(webm_path)})")
    else:
        print("Recorded file:      NONE (recording failed)")
    if mp4_path:
        print(f"Converted file:     {mp4_path.name} ({_mb(mp4_path)})")
    else:
        print("Converted file:     NONE (conversion skipped or failed)")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="poc_playwright_youtube_recorder",
        description=(
            "POC: Record a YouTube video via Playwright browser playback.\n"
            "Evaluates Playwright recording as a yt-dlp fallback.\n\n"
            "Produces timing and quality reports to inform feasibility decision."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "youtube_url",
        help="YouTube video URL (e.g. https://www.youtube.com/watch?v=VIDEO_ID)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("YOUTUBE_API_KEY"),
        help="YouTube Data API v3 key (or set YOUTUBE_API_KEY env var)",
    )
    parser.add_argument(
        "--output-dir",
        default="/tmp/playwright_poc",
        help="Directory to write recorded files (default: /tmp/playwright_poc)",
    )
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        default=True,
        help="Run Chromium headless (default: True)",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Run Chromium with visible window (useful for debugging)",
    )
    return parser


def main() -> None:
    _check_httpx()

    parser = build_parser()
    args = parser.parse_args()

    youtube_url: str = args.youtube_url
    api_key: str | None = args.api_key
    output_dir = Path(args.output_dir)
    headless: bool = args.headless

    # --- Validate playwright availability ---
    if not _check_playwright():
        print(
            "ERROR: playwright is required. Install with:\n"
            "  pip install playwright\n"
            "  playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    _ensure_chromium()

    # --- Step 1: Extract video ID ---
    video_id = extract_video_id(youtube_url)
    if not video_id:
        print(f"ERROR: Could not extract video ID from URL: {youtube_url}", file=sys.stderr)
        sys.exit(1)

    print(f"\nVideo ID: {video_id}")
    print(f"Output directory: {output_dir}")
    print(f"Headless: {headless}\n")

    # --- Step 2: YouTube Data API resolution fetch ---
    t_api = 0.0
    width, height = DEFAULT_WIDTH, DEFAULT_HEIGHT

    if api_key:
        print("[1/4] Fetching resolution from YouTube Data API v3...")
        t_api_start = time.perf_counter()
        try:
            width, height = fetch_resolution(video_id, api_key)
            t_api = time.perf_counter() - t_api_start
            print(f"  Resolved: {width}x{height} ({t_api:.2f}s)")
        except Exception as exc:
            t_api = time.perf_counter() - t_api_start
            print(f"  WARNING: API fetch failed ({exc}). Using default {width}x{height}.", file=sys.stderr)
    else:
        print(
            "[1/4] No API key provided — skipping resolution fetch.\n"
            f"  WARNING: Using default resolution {width}x{height}.",
            file=sys.stderr,
        )

    # --- Step 3: Playwright browser recording ---
    print("\n[2/4] Recording YouTube playback via Playwright...")
    webm_path, t_record = record_youtube_video(
        url=youtube_url,
        output_dir=output_dir,
        width=width,
        height=height,
        headless=headless,
    )
    print(f"  Recording complete ({t_record:.2f}s)")
    if webm_path:
        print(f"  Output: {webm_path}")

    # --- Step 4: FFmpeg conversion ---
    mp4_path: Path | None = None
    t_convert = 0.0

    if webm_path:
        print("\n[3/4] Converting .webm to .mp4 via ffmpeg...")
        mp4_path, t_convert = convert_webm_to_mp4(webm_path, output_dir)
        if mp4_path:
            print(f"  Conversion complete ({t_convert:.2f}s)")
            print(f"  Output: {mp4_path}")
    else:
        print("\n[3/4] Skipping conversion — no .webm file produced.")

    # --- Step 5: Reports ---
    print_timing_report(t_api, t_record, t_convert)
    print_quality_report(width, height, webm_path, mp4_path)


if __name__ == "__main__":
    main()
