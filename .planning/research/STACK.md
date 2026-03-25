# Technology Stack — v1.1 Additions

**Project:** BrainSuite Platform Connector
**Milestone:** v1.1 Insights + Intelligence
**Researched:** 2026-03-25
**Scope:** New library additions only. Existing stack (FastAPI 0.115, SQLAlchemy 2.0, httpx 0.25.2, tenacity, APScheduler 3.10.4, Redis, boto3, Angular 17, NgRx 17, ECharts 5.6 / ngx-echarts 17.2, Angular Material 17) is validated and NOT repeated here.

---

## New Backend Dependencies

### 1. Anthropic Python SDK — AI Metadata Inference

| Property | Value |
|----------|-------|
| Package | `anthropic` |
| Version | `>=0.86.0` (latest as of 2026-03-25) |
| Install | `pip install anthropic` |
| Python requirement | 3.9+ |

**Why:** The AI metadata auto-fill feature requires analyzing creative images and video frames to infer Language/Market, Brand Names, Project Name, Asset Name, Asset Stage, and Voice Over presence. The Claude vision API supports all of this in a single multimodal call — no separate object-detection library needed.

**Model to use:** `claude-haiku-4-5-20251001`

Rationale: Haiku 4.5 is the fastest current-generation model at $1/$5 per MTok input/output. Structured metadata extraction from ad creatives (not deep reasoning) fits Haiku's capability profile. Cost per creative inference stays low. If Haiku produces poor-quality output for a specific field, escalate to `claude-sonnet-4-6` ($3/$15) for that field only — test Haiku first.

**Image passing pattern — base64 preferred for MinIO assets:**
```python
import anthropic
import base64
import httpx

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

# Fetch from MinIO presigned URL, encode to base64
image_bytes = httpx.get(presigned_url).content
image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

response = await client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=512,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",  # or image/png, image/webp, image/gif
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": "<structured extraction prompt>"},
            ],
        }
    ],
)
```

**Why base64 over presigned URL:** Presigned MinIO URLs are only valid inside the Docker network. Claude's API cannot reach a local MinIO instance. Fetch bytes server-side, encode to base64, pass inline.

**Multi-image (image + video frames) in a single call:** Pass multiple `image` content blocks before the text block. Haiku 4.5 has a 200k-token context window, which limits batch requests to 100 images per call. For ad creatives, 1 image or 2-3 video keyframes per inference call is typical — well within limits.

**Image format constraints:**
- Supported: JPEG, PNG, GIF, WebP
- Max 5 MB per image
- Resize to ≤1568 px on the long edge before encoding — reduces token count and latency
- Approximate cost: ~1,600 tokens at 1 megapixel (1092×1092 px), ~$0.0016 per image at Haiku pricing

**AsyncAnthropic client:** Use `anthropic.AsyncAnthropic()` for non-blocking calls inside FastAPI async handlers and APScheduler jobs. The sync `anthropic.Anthropic()` client blocks the event loop and must not be used in async contexts.

**Confidence:** HIGH — verified against official Anthropic API docs and PyPI (2026-03-25).

---

### 2. OpenAI Python SDK — Audio Transcription for Voice Over Detection

| Property | Value |
|----------|-------|
| Package | `openai` |
| Version | `>=2.29.0` (latest as of 2026-03-25) |
| Install | `pip install openai` |
| Python requirement | 3.9+ |

**Why:** Claude does not process audio directly. Voice Over presence and Voice Over Language require audio transcription. The OpenAI Whisper API (`whisper-1` model) returns both the transcript text and the detected language ISO-639-1 code in a single API call — exactly the two data points needed (`has_voice_over`, `voice_over_language`).

**Usage pattern:**
```python
from openai import AsyncOpenAI
import io

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Fetch audio bytes from MinIO (extracted from video using imageio-ffmpeg, already in stack)
audio_bytes = await fetch_audio_from_minio(asset_key)

transcription = await openai_client.audio.transcriptions.create(
    model="whisper-1",
    file=("audio.mp3", io.BytesIO(audio_bytes), "audio/mpeg"),
    response_format="verbose_json",  # returns .text + .language
)

has_voice_over = len(transcription.text.strip()) > 0
voice_over_language = transcription.language  # ISO-639-1 code, e.g. "en", "de", "fr"
```

**Why `whisper-1` via OpenAI API over local Whisper:**
- No GPU dependency in Docker Compose — local Whisper large-v3 requires ~1.5 GB model download and significant CPU at startup
- Language detection is built into the `verbose_json` response — no second call needed
- Cost is negligible for ad creative durations: $0.006/minute, and a typical ad is under 60 seconds
- `imageio-ffmpeg` is already in `requirements.txt` — use it to extract the audio track from video assets before sending to Whisper

**Audio format support:** mp3, mp4, mpeg, mpga, m4a, wav, webm — all common ad creative formats are covered.

**Confidence:** HIGH — verified against OpenAI API reference (transcriptions.create endpoint) and PyPI (2026-03-25).

---

### 3. No New Libraries for BrainSuite Image Scoring or Historical Backfill

- **BrainSuite Static endpoint (image scoring):** Uses existing `httpx` + `tenacity`. The difference from video scoring is endpoint URL, payload shape, and state-machine routing. No new library.
- **APScheduler backfill job:** Uses existing `apscheduler==3.10.4`. No new library.

---

## New Frontend Dependencies

### 4. No New Libraries for In-App Notifications

**Use Angular Material `MatSnackBar` for toasts and a custom NgRx-backed notification center for the bell.**

Angular Material 17 (`@angular/material: ^17.3.0`) is already in the stack. `MatSnackBar` ships with it and works with standalone components — inject `MatSnackBar` directly, no additional module imports beyond what is already configured.

**Why not ngx-toastr:** `ngx-toastr` is valid but adds a dependency for functionality Angular Material already provides. The app uses Angular Material throughout — visual consistency is free with `MatSnackBar`. For rich toast layouts, use `MatSnackBar.openFromComponent()` with a custom standalone component.

**Bell notification center — native pattern, no library:**
```typescript
// Notification interface for NgRx store
interface Notification {
  id: string;
  type: 'sync_complete' | 'scoring_complete' | 'error';
  message: string;
  timestamp: Date;
  read: boolean;
}

// Bell icon uses MatBadge (already in @angular/material) for unread count
// Dropdown uses MatMenu or a positioned overlay panel
// Store feeds notifications from polling or Server-Sent Events
```

`MatBadge` and `MatMenu` are both part of `@angular/material 17` — already available, zero additional installs.

**Confidence:** HIGH — Angular Material MatSnackBar, MatBadge, MatMenu verified as part of @angular/material 17.3.

---

### 5. No New Libraries for ECharts Charts

The stack already includes `echarts: ^5.6.0` and `ngx-echarts: ^17.2.0`. Scatter plots and line charts are native ECharts 5 chart types — no additional packages needed.

**Scatter plot (Score-to-ROAS correlation) — ECharts 5 option structure:**
```typescript
// Register ScatterChart alongside existing chart registrations in app.config.ts
import { ScatterChart } from 'echarts/charts';
import { TooltipComponent, GridComponent } from 'echarts/components';
echarts.use([ScatterChart, TooltipComponent, GridComponent, CanvasRenderer]);

// Component chartOption:
const correlationChartOption: EChartsOption = {
  tooltip: {
    trigger: 'item',
    formatter: (params: any) =>
      `${params.data[2]}<br/>Score: ${params.data[0]}<br/>ROAS: ${params.data[1].toFixed(2)}x`,
  },
  xAxis: { name: 'BrainSuite Score', type: 'value', min: 0, max: 100 },
  yAxis: { name: 'ROAS', type: 'value' },
  series: [{
    type: 'scatter',
    // data format: [x, y, label] — label only used in tooltip formatter
    data: assets.map(a => [a.score, a.roas, a.name]),
    symbolSize: 10,
  }],
};
```

**Line chart (Score trend over time) — ECharts 5 option structure:**
```typescript
// Register LineChart alongside existing chart registrations
import { LineChart } from 'echarts/charts';
echarts.use([LineChart]);

const trendChartOption: EChartsOption = {
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'time' },
  yAxis: { name: 'Score', min: 0, max: 100 },
  series: [{
    type: 'line',
    smooth: true,
    data: scoreHistory.map(h => [h.scored_at, h.score]),  // [Date, number]
  }],
};
```

**Tree-shaking note:** The project already imports `echarts/core` with selective chart/component registration (the ngx-echarts pattern). Add `ScatterChart` and `LineChart` to the existing registration block. Do not switch to the full `import 'echarts'` bundle — that would bloat the Angular bundle by ~1 MB.

**Confidence:** HIGH — ECharts 5 scatter and line are core chart types; ngx-echarts 17.2 is already in the stack and verified compatible with Angular 17.

---

## Environment Variables to Add

| Variable | Purpose | Required By |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Claude API for metadata inference | AI metadata auto-fill |
| `OPENAI_API_KEY` | Whisper API for audio transcription | Voice Over detection |

Both are secrets. Add to `.env` (Docker Compose `env_file`) and to the `pydantic-settings` `Settings` model. Never commit values.

---

## Summary: Net-New Additions for v1.1

| Layer | Addition | Version | Purpose |
|-------|----------|---------|---------|
| Backend | `anthropic` | `>=0.86.0` | Claude vision API for AI metadata inference |
| Backend | `openai` | `>=2.29.0` | Whisper API for audio transcription + VO language detection |
| Frontend | none | — | All new UI features use existing Angular Material + ECharts |

Everything else is handled by the existing stack. Do not add:
- `ngx-toastr` — Angular Material MatSnackBar already covers toast needs
- `faster-whisper` or `openai-whisper` (local) — OpenAI API avoids GPU/model-size constraints in Docker
- Any additional charting library — ECharts 5 handles scatter and line natively

---

## Sources

- [Anthropic Models Overview](https://platform.claude.com/docs/en/about-claude/models/overview) — verified 2026-03-25 (HIGH confidence)
- [Anthropic Vision API Docs](https://platform.claude.com/docs/en/build-with-claude/vision) — verified 2026-03-25 (HIGH confidence)
- [anthropic PyPI — v0.86.0](https://pypi.org/project/anthropic/) — version confirmed 2026-03-25 (HIGH confidence)
- [OpenAI Transcriptions API Reference](https://platform.openai.com/docs/api-reference/audio/createTranscription) — method signature verified (HIGH confidence)
- [openai-python GitHub transcriptions.py](https://github.com/openai/openai-python/blob/main/src/openai/resources/audio/transcriptions.py) — response_format and language field confirmed (HIGH confidence)
- [openai PyPI — v2.29.0](https://pypi.org/project/openai/) — version confirmed 2026-03-25 (HIGH confidence)
- [ngx-echarts npm — v17.2.0](https://www.npmjs.com/package/ngx-echarts) — already in stack, Angular 17 compatible (HIGH confidence)
- [Apache ECharts scatter handbook](https://apache.github.io/echarts-handbook/en/how-to/chart-types/scatter/basic-scatter/) — data format [x, y] confirmed (HIGH confidence)
- [Angular Material Snackbar API](https://material.angular.dev/components/snack-bar/api) — part of @angular/material 17, standalone compatible (HIGH confidence)

---

*v1.1 stack research completed 2026-03-25. Supersedes v1.0 STACK.md for new additions.*
