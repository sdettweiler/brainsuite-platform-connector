---
phase: quick-260408-fb9
plan: "01"
subsystem: backend/scripts
tags: [poc, playwright, youtube, yt-dlp-fallback, recording]
dependency_graph:
  requires: []
  provides: [POC-PLAYWRIGHT-FALLBACK]
  affects: []
tech_stack:
  added: [playwright (not in requirements — POC only), httpx, ffmpeg (subprocess)]
  patterns: [standalone-script, argparse-cli, timing-report]
key_files:
  created:
    - backend/scripts/poc_playwright_youtube_recorder.py
  modified: []
decisions:
  - "from __future__ import annotations used for Python 3.9 compatibility (system python is 3.9.6)"
  - "playwright not added to requirements.txt per plan spec — POC only"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-08"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Quick Task 260408-fb9: Playwright YouTube Recorder POC Summary

**One-liner:** Standalone Python POC script that records YouTube video playback via Playwright Chromium and converts the recording to .mp4, producing timing and quality reports to evaluate yt-dlp fallback feasibility.

## What Was Built

`backend/scripts/poc_playwright_youtube_recorder.py` — a fully self-contained (466 lines) POC script:

1. **Argument parsing** — positional `youtube_url`, `--api-key` (or `YOUTUBE_API_KEY` env), `--output-dir` (default `/tmp/playwright_poc`), `--headless`/`--no-headless`.

2. **YouTube Data API v3 fetch** — extracts video ID via regex, queries `contentDetails.definition` (hd → 1920×1080, sd → 640×480). Falls back to 1920×1080 with a warning if no API key provided.

3. **Playwright recording** — launches Chromium with `record_video_dir` + `record_video_size`, navigates to YouTube URL, waits for `<video>` element, dismisses cookie consent dialogs, clicks play, requests fullscreen via JS and the 'f' key, reads `video.duration` from DOM, waits `duration + 3s`, closes context to flush the .webm file.

4. **FFmpeg conversion** — runs `ffmpeg -i input.webm -c:v libx264 -crf 23 -preset fast -c:a aac output.mp4 -y`. Gracefully skips and prints install instructions if `ffmpeg` binary not found.

5. **Reports** — prints `=== TIMING REPORT ===` (API fetch / Recording / Conversion / Total) and `=== QUALITY REPORT ===` (target resolution, recorded .webm size, converted .mp4 size).

## Verification

- `python3 -c "import ast; ast.parse(...)"` → **Syntax OK**
- `python3 poc_playwright_youtube_recorder.py --help` → shows all arguments and description
- No imports from `backend/app/` (fully standalone)

## Deviations from Plan

**1. [Rule 1 - Bug] Added `from __future__ import annotations` for Python 3.9 compatibility**
- **Found during:** Task 1 verification
- **Issue:** Script used `str | None` union syntax (PEP 604) which requires Python 3.10+. System Python is 3.9.6.
- **Fix:** Added `from __future__ import annotations` at the top of the file — defers annotation evaluation, making the syntax valid on Python 3.9.
- **Files modified:** `backend/scripts/poc_playwright_youtube_recorder.py`
- **Commit:** 406e97b

## How to Run

```bash
# Basic — no API key (uses 1920x1080 default)
python3 backend/scripts/poc_playwright_youtube_recorder.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# With YouTube Data API key (auto-detects HD/SD resolution)
python3 backend/scripts/poc_playwright_youtube_recorder.py \
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
    --api-key YOUR_YOUTUBE_API_KEY

# Watch the browser (non-headless, useful for debugging)
python3 backend/scripts/poc_playwright_youtube_recorder.py \
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
    --no-headless --output-dir /tmp/my_test

# Prerequisites (one-time setup)
pip install playwright httpx
playwright install chromium
# ffmpeg must be installed separately for conversion step
```

## Known Stubs

None.

## Self-Check: PASSED

- `backend/scripts/poc_playwright_youtube_recorder.py` — FOUND (466 lines)
- Commit 406e97b — FOUND
