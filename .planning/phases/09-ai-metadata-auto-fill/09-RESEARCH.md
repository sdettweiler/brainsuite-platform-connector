# Phase 9: AI Metadata Auto-Fill — Research

**Researched:** 2026-04-01
**Domain:** OpenAI GPT-4o Vision + Whisper API integration, pipeline-triggered async metadata fill, FastAPI async patterns, SQLAlchemy Alembic migrations
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `MetadataField` model gets two new columns: `auto_fill_enabled` (boolean, default `false`) and `auto_fill_type` (nullable string enum). Values: `language | brand_names | vo_transcript | vo_language | campaign_name | ad_name | fixed_value`.
- **D-02:** Auto-fill triggers **immediately after an asset binary is stored to MinIO during sync** in the four platform sync services (`meta_sync.py`, `tiktok_sync.py`, `google_ads_sync.py`, `dv360_sync.py`). Runs as a `BackgroundTask` or async call; does not block the sync loop. Not part of the scoring job.
- **D-03:** `MetadataField.default_value` is propagated to `AssetMetadataValue` at auto-fill time if no value exists. AI inference may then overwrite the default. `default_value` is the fallback if inference fails or `OPENAI_API_KEY` is absent.
- **D-04:** Auto-fill results are written directly to `AssetMetadataValue` — no intermediate suggestions table, no user confirmation step.
- **D-05:** AI-inferred fields: Language (GPT-4o Vision), Brand Names (GPT-4o Vision), Voice Over transcript (Whisper, full text), Voice Over Language (Whisper).
- **D-06:** Deterministic fields: Project Name → `campaign_name`, Asset Name → `ad_name` — both from `CreativeAsset` columns, no AI.
- **D-07:** Fixed field: Asset Stage → always `"Final"`, hardcoded, no AI.
- **D-08:** OpenAI only. GPT-4o Vision for image/video frame analysis; Whisper API (`whisper-1`) for audio transcription.
- **D-09:** `OPENAI_API_KEY` is optional. If absent, AI-inferred fields (D-05) fall back to `default_value` or remain unset. No hard error. Deterministic (D-06) and fixed (D-07) fields are unaffected.
- **D-10:** `ai_inference_tracking` table (one row per asset). Schema: `(id, asset_id, org_id, ai_inference_status, created_at, updated_at)`. Status values: `PENDING | COMPLETE | FAILED`. `COMPLETE` guard prevents re-inference on re-sync. `FAILED` resets to `PENDING` on next sync to allow retry.
- **D-11:** No confidence tracking — skip entirely.
- **D-12:** `FAILED` status resets to `PENDING` on the next sync run to allow automatic retry.
- **D-13:** Users can manually overwrite any auto-filled `AssetMetadataValue` from the asset detail dialog.
- **D-14:** Manual metadata edit resets asset `scoring_status` to `UNSCORED`. No immediate rescore — the 15-minute APScheduler batch picks it up.

### Claude's Discretion

- GPT-4o vs GPT-4o-mini for vision: researcher/planner should evaluate cost vs quality for brand name extraction.
- Whether VO transcript is stored as full text or truncated (e.g. 2000-char limit) — decide based on `MetadataField.value` column constraints (`String(500)` currently).
- Exact async mechanism for triggering auto-fill from sync services — `BackgroundTasks`, `asyncio.create_task()`, or queue entry.
- Image/video frame extraction approach for GPT-4o Vision — first frame vs. multiple frames vs. existing MinIO thumbnail.

### Deferred Ideas (OUT OF SCOPE)

- Per-tenant daily OpenAI spend cap (AI-v2-01)
- Per-field confidence tracking
- On-demand "Re-run auto-fill" button in asset detail dialog
- AI-04 (original): dialog Auto-fill button with user review and confirmation step
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AI-01 | `ai_metadata_suggestions` table (renamed in CONTEXT to execution tracking table) with `ai_inference_status` state machine (`PENDING | COMPLETE | FAILED`) — one row per asset | Schema design, Alembic migration pattern, `on_conflict_do_nothing` guard |
| AI-02 | Async trigger after asset download in sync services; returns without blocking sync loop | `BackgroundTask` + `asyncio.create_task()` patterns; session-per-operation rule |
| AI-03 | Inference covers Language, Brand Names (Vision); VO transcript, VO Language (Whisper); Project Name and Asset Name from sync data; Asset Stage fixed "Final" | OpenAI API call patterns, prompt design, field routing logic |
| AI-04 | SUPERSEDED — original dialog button replaced by pipeline integration per D-02 | No research needed |
| AI-05 | Images fetched server-side from MinIO as bytes; downsampled to 1568px max if over 4 MB before base64 encoding | Pillow resize pattern; `download_blob()` already exists in `ObjectStorageService` |
| AI-06 | `ai_inference_status = COMPLETE` guard prevents re-triggering inference on already-processed assets | `on_conflict_do_nothing` insert + pre-check in sync service |
</phase_requirements>

---

## Summary

Phase 9 integrates OpenAI's GPT-4o Vision and Whisper APIs into the existing sync pipeline to auto-fill per-field metadata immediately after an asset binary is stored to MinIO. The implementation adds two columns to `MetadataField` (`auto_fill_enabled`, `auto_fill_type`), creates a new `ai_inference_tracking` table, and inserts a non-blocking auto-fill call into the four existing sync services after the asset download step. Results are written directly to `AssetMetadataValue` using the same upsert logic already present in `PATCH /{asset_id}/metadata`.

The two new OpenAI library dependencies — `openai>=2.0.0` (for `AsyncOpenAI`) and `Pillow>=10.0.0` (for image resize) — are not currently in `requirements.txt` and must be added. The `imageio-ffmpeg` package is already present and can extract the first video frame for GPT-4o Vision. Audio extraction from video can use `ffmpeg` subprocess via `asyncio.create_subprocess_exec`.

**Primary recommendation:** Use `AsyncOpenAI` client with `client.beta.chat.completions.parse()` for structured Vision output, and `client.audio.transcriptions.create()` (async) for Whisper. Trigger from sync services via `asyncio.create_task()` (not FastAPI `BackgroundTasks`, which requires a request context). Keep all OpenAI calls outside DB sessions.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `openai` | `>=2.0.0` (latest: `2.30.0` as of 2026-03-25) | AsyncOpenAI client — GPT-4o Vision + Whisper API | Official SDK; async support; structured output via `.parse()` |
| `Pillow` | `>=10.0.0` (latest: `12.1.1` as of 2026-04-01) | Image resize before base64 encoding | Only pure-Python image library with async-safe resize; already used by imageio ecosystem |

### Supporting (already in requirements.txt)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `imageio-ffmpeg` | `>=0.5.1` | Extract first video frame as bytes | VIDEO assets — call before GPT-4o Vision |
| `boto3` | `>=1.42.0` | MinIO blob download (`download_blob`) | Already used — no change needed |
| `httpx` | `0.25.2` | Not used for OpenAI calls (use `openai` SDK) | Existing sync HTTP pattern |
| `asyncpg` / SQLAlchemy | `2.0.23` | Async DB sessions | Existing pattern |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `openai` SDK `AsyncOpenAI` | `httpx` raw calls to OpenAI REST | SDK handles auth, retries, typed responses — raw calls add maintenance cost with no benefit |
| `Pillow` for resize | `cv2` (OpenCV) | OpenCV adds a large binary dependency; Pillow is lighter and sufficient for a simple longest-edge resize |
| `asyncio.create_task()` for auto-fill trigger | FastAPI `BackgroundTasks` | `BackgroundTasks` requires a live request context and is tied to the HTTP lifecycle; sync services run outside request scope — `asyncio.create_task()` is the correct choice |

**Installation (new packages only):**
```bash
pip install "openai>=2.0.0" "Pillow>=10.0.0"
```

**Version verification (confirmed 2026-04-01):**
- `openai`: latest `2.30.0` — [PyPI](https://pypi.org/project/openai/)
- `Pillow`: latest `12.1.1` — [PyPI](https://pypi.org/project/pillow/)

---

## Architecture Patterns

### Recommended Project Structure

```
backend/app/
├── models/
│   ├── metadata.py          # Add auto_fill_enabled + auto_fill_type to MetadataField
│   └── ai_inference.py      # NEW: AIInferenceTracking model
├── services/
│   ├── ai_autofill.py       # NEW: auto-fill orchestration service
│   └── sync/
│       ├── meta_sync.py     # Hook: call auto-fill after MinIO store
│       ├── tiktok_sync.py   # Same hook
│       ├── google_ads_sync.py   # Same hook
│       └── dv360_sync.py    # Same hook
├── api/v1/endpoints/
│   └── assets.py            # Update PATCH metadata to reset scoring_status
└── core/
    └── config.py            # Add OPENAI_API_KEY: Optional[str] = None
backend/alembic/versions/
    └── o6p7q8r9s0t1_add_ai_autofill_columns.py   # NEW migration
```

### Pattern 1: COMPLETE Guard Insert (`on_conflict_do_nothing`)

The tracking row is inserted with `PENDING` status before any inference runs. If the row already exists with `COMPLETE`, the insert is silently ignored.

**What:** Insert-or-skip tracking row at the start of auto-fill; abort if already `COMPLETE`.
**When to use:** Every sync run, for every asset that has at least one auto-fill-enabled field.

```python
# Source: existing pattern in meta_sync.py and scoring_job.py
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(AIInferenceTracking).values(
    id=uuid.uuid4(),
    asset_id=asset_id,
    org_id=org_id,
    ai_inference_status="PENDING",
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow(),
).on_conflict_do_nothing(index_elements=["asset_id"])
await db.execute(stmt)
await db.commit()

# Check after insert whether the row is already COMPLETE
result = await db.execute(
    select(AIInferenceTracking).where(AIInferenceTracking.asset_id == asset_id)
)
tracking = result.scalar_one_or_none()
if tracking and tracking.ai_inference_status == "COMPLETE":
    return  # Guard: do not re-run
```

### Pattern 2: Session-Per-Operation (No Session During HTTP Calls)

The existing `scoring_job.py` establishes this pattern: fetch + commit in one session, close session, make external HTTP calls (OpenAI), open new session to write results.

**What:** Never hold an async DB session open while awaiting OpenAI or Whisper API responses.
**When to use:** All auto-fill OpenAI calls.

```python
# Pattern from scoring_job.py — Phase 2 comment
# Phase 1: load data, close session
async with get_session_factory()() as db:
    fields = await db.execute(select(MetadataField).where(...))
    # ... collect data
    # session releases here

# Phase 2: call OpenAI — NO db session held
result = await openai_client.beta.chat.completions.parse(...)

# Phase 3: write results — new session
async with get_session_factory()() as db:
    # upsert AssetMetadataValue rows
    await db.commit()
```

### Pattern 3: `asyncio.create_task()` Trigger from Sync Services

Sync services are async functions but run outside a FastAPI request context, so `BackgroundTasks` (which requires `Request`) is not applicable. Use `asyncio.create_task()` to fire-and-forget.

**What:** Non-blocking auto-fill trigger called after MinIO asset store in each sync service.
**When to use:** Inside each `*_sync.py` after the asset binary URL is stored.

```python
# Inside _fetch_and_store_creatives (or equivalent) in each sync service
# After: asset.asset_url = storage.upload_file(...)
import asyncio
from app.services.ai_autofill import run_autofill_for_asset

asyncio.create_task(
    run_autofill_for_asset(asset_id=asset.id, org_id=asset.organization_id)
)
# Sync loop continues immediately; auto-fill runs concurrently
```

### Pattern 4: GPT-4o Vision — Base64 Image with Structured Output

```python
# Source: OpenAI Python SDK docs + community verification
from openai import AsyncOpenAI
from pydantic import BaseModel
import base64, io
from PIL import Image

async def analyze_image_with_gpt4o(
    image_bytes: bytes,
    content_type: str,
) -> dict:
    # Downsample if > 4 MB (AI-05 requirement)
    if len(image_bytes) > 4 * 1024 * 1024:
        img = Image.open(io.BytesIO(image_bytes))
        img.thumbnail((1568, 1568), Image.LANCZOS)
        buf = io.BytesIO()
        fmt = "JPEG" if content_type == "image/jpeg" else "PNG"
        img.save(buf, format=fmt)
        image_bytes = buf.getvalue()

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    mime = content_type if content_type.startswith("image/") else "image/jpeg"

    class VisionResult(BaseModel):
        language: str | None = None
        brand_names: list[str] = []

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.beta.chat.completions.parse(
        model="gpt-4o-mini",   # see cost note below
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze this ad creative. "
                            "Return: language (primary content language, e.g. 'English'), "
                            "brand_names (list of brand names visible in the creative, empty list if none)."
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
    return response.choices[0].message.parsed
```

**Important:** `client.beta.chat.completions.parse()` with a Pydantic `response_format` requires model `gpt-4o-2024-08-06` or later (including `gpt-4o-mini`). The plain `model="gpt-4o"` (latest pointer) also works. Confirmed: Structured Outputs + vision inputs are compatible.

### Pattern 5: Whisper API — Audio from Video via ffmpeg subprocess

```python
# Source: OpenAI SDK docs; ffmpeg subprocess pattern
import asyncio, io
from openai import AsyncOpenAI

async def extract_audio_bytes(video_path_or_s3_key: str, video_bytes: bytes) -> bytes | None:
    """Extract audio stream as WAV bytes using ffmpeg subprocess."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", "pipe:0",
        "-vn",           # no video
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
        return None  # No audio stream or too short
    return stdout


async def transcribe_audio(audio_bytes: bytes) -> dict:
    """Transcribe audio using Whisper API. Returns {text, language}."""
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.wav"   # Required: BytesIO needs .name with valid extension

    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="verbose_json",   # includes detected language
    )
    return {
        "text": transcript.text or "",
        "language": transcript.language or "",
    }
```

**Note on `verbose_json`:** The `verbose_json` response format includes a `language` field (ISO 639-1) at the top level of the transcription object. This covers both `vo_transcript` and `vo_language` in a single API call.

### Pattern 6: First Video Frame Extraction (imageio-ffmpeg, already in requirements)

```python
import io, imageio_ffmpeg

def extract_first_frame_bytes(video_bytes: bytes) -> bytes | None:
    """Extract first frame from video as JPEG bytes."""
    try:
        reader = imageio_ffmpeg.read_frames(
            io.BytesIO(video_bytes), input_params=["-frames:v", "1"]
        )
        meta = next(reader)   # first item is metadata dict
        frame_bytes = next(reader)   # first actual frame (raw RGB)
        w, h = meta["size"]
        # Convert raw RGB bytes to JPEG via Pillow
        from PIL import Image
        img = Image.frombytes("RGB", (w, h), frame_bytes)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception:
        return None
```

**Recommendation:** Use existing MinIO thumbnail (`asset.thumbnail_url`) if available — avoids re-downloading the full video. If thumbnail absent, download video from MinIO and extract first frame using `imageio-ffmpeg`.

### Pattern 7: Metadata PATCH + Scoring Reset (D-14)

The existing `PATCH /{asset_id}/metadata` endpoint writes `AssetMetadataValue` rows. To support D-14 (manual edit resets `scoring_status`), the endpoint must additionally set `CreativeScoreResult.scoring_status = "UNSCORED"` after writing values.

```python
# Addition to existing update_asset_metadata endpoint in assets.py
from app.models.scoring import CreativeScoreResult

# After writing metadata values:
score_result = await db.execute(
    select(CreativeScoreResult).where(
        CreativeScoreResult.creative_asset_id == asset_id
    )
)
score_row = score_result.scalar_one_or_none()
if score_row:
    score_row.scoring_status = "UNSCORED"
    db.add(score_row)
await db.commit()
```

### Anti-Patterns to Avoid

- **Holding a DB session during OpenAI API calls:** OpenAI calls can take 5–20s. Holding a session blocks the connection pool. Always close session before calling OpenAI.
- **Using FastAPI `BackgroundTasks` from a sync service:** `BackgroundTasks` is tied to the HTTP request lifecycle and requires a `Request` or `BackgroundTasks` parameter. Sync services have no request context. Use `asyncio.create_task()`.
- **Passing a bare `io.BytesIO` to Whisper without `.name`:** The OpenAI SDK requires the file object to have a `.name` attribute with a supported extension (`.wav`, `.mp3`, etc.) — otherwise it raises an unrecognized format error.
- **Storing full Whisper transcript in `String(500)` column:** The current `AssetMetadataValue.value` column is `String(500)`. A Whisper transcript can easily exceed 500 chars. Either: (a) truncate at 500 chars in the service, or (b) widen the column to `Text` in a migration. **Recommendation: widen to `Text` via Alembic migration** — truncation loses data silently.
- **Re-running inference on COMPLETE assets:** Always check tracking row status before any OpenAI call. The `on_conflict_do_nothing` insert prevents a race condition on concurrent syncs.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON output from GPT-4o | Custom JSON parsing, regex extraction | `client.beta.chat.completions.parse()` with Pydantic model | 100% schema reliability; handles refusal/None cases; no fragile JSON parsing |
| Audio transcription | Local Whisper model install | OpenAI Whisper API (`whisper-1`) | No GPU needed; 25 MB file limit is sufficient; language detection included |
| Image resize before encoding | Custom byte manipulation | `Pillow.Image.thumbnail()` with `LANCZOS` | Handles all image formats; thumbnail() preserves aspect ratio automatically |
| Video frame extraction | Manual ffmpeg subprocess byte parsing | `imageio-ffmpeg.read_frames()` | Already in requirements.txt; handles codec negotiation |
| Async OpenAI calls | Wrapping sync client in `run_in_executor` | `AsyncOpenAI` client with native `await` | Native async; no thread pool overhead; same interface |

**Key insight:** The OpenAI Python SDK (`>=1.0`) ships with full async support via `AsyncOpenAI`. There is no need to wrap sync calls in executors for this use case.

---

## Common Pitfalls

### Pitfall 1: `AssetMetadataValue.value` Column Too Short for Transcripts

**What goes wrong:** Whisper returns a 600+ character transcript; SQLAlchemy truncates or raises `DataError` on the `String(500)` column.
**Why it happens:** `AssetMetadataValue.value` is currently `String(500)` (defined in `creative.py`). VO transcripts for 30s spots commonly exceed this.
**How to avoid:** Add a migration to widen `asset_metadata_values.value` to `TEXT` (or `String(10000)` at minimum). This migration must run before any transcript is written.
**Warning signs:** `DataError: value too long for type character varying(500)` in backend logs.

### Pitfall 2: OpenAI Calls Inside DB Session (Connection Pool Exhaustion)

**What goes wrong:** Under concurrent syncs, the connection pool drains and new DB operations time out.
**Why it happens:** Holding a session open during a 5–20s OpenAI API call blocks a pool connection.
**How to avoid:** Follow the established 3-phase pattern from `scoring_job.py`: Phase 1 read (commit + close session), Phase 2 OpenAI call (no session), Phase 3 write (new session).
**Warning signs:** `TimeoutError: QueuePool limit of size N overflow N reached` in logs under load.

### Pitfall 3: `asyncio.create_task()` Swallowed Exceptions

**What goes wrong:** Auto-fill silently fails; no error logged; asset tracking row stays `PENDING` indefinitely.
**Why it happens:** Exceptions raised inside a task created with `asyncio.create_task()` are only logged if the task is awaited or has a done-callback.
**How to avoid:** Add a try/except inside `run_autofill_for_asset()` that catches all exceptions, logs them, and sets tracking status to `FAILED`.
**Warning signs:** Assets with `ai_inference_status = PENDING` that never transition after sync completes.

### Pitfall 4: `FAILED` Status Never Retried if Condition Persists

**What goes wrong:** Every sync re-attempts inference, but the underlying error (e.g., bad `OPENAI_API_KEY`) is permanent; assets burn retry attempts.
**Why it happens:** D-12 states that `FAILED` resets to `PENDING` on the next sync — this is correct for transient failures, but not for misconfiguration.
**How to avoid:** Log the failure reason clearly; the key check at the start is `if not settings.OPENAI_API_KEY: return` (graceful no-op, never sets FAILED).
**Warning signs:** `FAILED` rows accumulating rapidly across all assets in logs.

### Pitfall 5: Video Assets Lack Audio — Whisper Call on Silent Video

**What goes wrong:** Whisper API receives a WAV file with no audio data, returns empty string, or raises an error.
**Why it happens:** Some video ad formats (motion graphics, display ads) have no audio track.
**How to avoid:** After `extract_audio_bytes()`, check if returned bytes are `None` or too short (< 1 KB WAV header). If no audio, skip Whisper call entirely and apply `default_value` fallback.
**Warning signs:** Whisper returning empty `text` for all video assets from a particular platform.

### Pitfall 6: `MetadataFieldResponse` Schema Does Not Include `auto_fill_enabled` / `auto_fill_type`

**What goes wrong:** Frontend sends `PATCH /metadata-fields/{id}` with new auto-fill fields but backend ignores them.
**Why it happens:** The existing `MetadataFieldCreate` / `MetadataFieldResponse` Pydantic schemas in `app/schemas/creative.py` were written before these columns existed.
**How to avoid:** Update both input and output schemas in a single wave with the model migration. Add field to `MetadataFieldUpdate` patch schema as well.
**Warning signs:** Toggle saves appearing to succeed (200 response) but value not persisting in DB.

---

## Code Examples

### Full Auto-Fill Service Skeleton

```python
# backend/app/services/ai_autofill.py
# Source: pattern derived from scoring_job.py session-per-operation + OpenAI SDK docs

import asyncio, base64, io, logging, uuid
from datetime import datetime
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.db.base import get_session_factory
from app.models.ai_inference import AIInferenceTracking
from app.models.metadata import MetadataField
from app.models.creative import CreativeAsset, AssetMetadataValue

logger = logging.getLogger(__name__)

AUTO_FILL_TYPE_VISION = {"language", "brand_names"}
AUTO_FILL_TYPE_AUDIO  = {"vo_transcript", "vo_language"}
AUTO_FILL_TYPE_SYNC   = {"campaign_name", "ad_name"}
AUTO_FILL_TYPE_FIXED  = {"fixed_value"}


async def run_autofill_for_asset(asset_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """Entry point called via asyncio.create_task() from sync services."""
    try:
        await _autofill(asset_id, org_id)
    except Exception as exc:
        logger.exception("auto-fill failed for asset_id=%s: %s", asset_id, exc)
        await _set_status(asset_id, "FAILED")


async def _autofill(asset_id: uuid.UUID, org_id: uuid.UUID) -> None:
    # Phase 1: Load fields + asset data; insert tracking row; check COMPLETE guard
    async with get_session_factory()() as db:
        # Insert tracking row (no-op if already exists)
        await db.execute(
            pg_insert(AIInferenceTracking).values(
                id=uuid.uuid4(), asset_id=asset_id, org_id=org_id,
                ai_inference_status="PENDING",
                created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
            ).on_conflict_do_nothing(index_elements=["asset_id"])
        )
        await db.commit()

        tracking = (await db.execute(
            select(AIInferenceTracking).where(AIInferenceTracking.asset_id == asset_id)
        )).scalar_one_or_none()
        if tracking and tracking.ai_inference_status == "COMPLETE":
            return  # COMPLETE guard (AI-06)

        fields = (await db.execute(
            select(MetadataField).where(
                MetadataField.organization_id == org_id,
                MetadataField.auto_fill_enabled == True,
                MetadataField.is_active == True,
            )
        )).scalars().all()
        if not fields:
            await _set_status(asset_id, "COMPLETE")
            return

        asset = await db.get(CreativeAsset, asset_id)
        if not asset:
            return

        # Collect what we need before closing session
        field_data = [(f.id, f.auto_fill_type, f.default_value) for f in fields]
        asset_format = asset.asset_format
        asset_url = asset.asset_url
        campaign_name = asset.campaign_name
        ad_name = asset.ad_name
        # session closes here

    # Phase 2: Download asset binary (outside session)
    from app.services.object_storage import get_object_storage
    storage = get_object_storage()
    s3_key = (asset_url or "").lstrip("/").removeprefix("objects/")
    asset_bytes, content_type = storage.download_blob(s3_key)

    # Phase 3: Run inference (outside session)
    values_to_write: dict[uuid.UUID, str] = {}

    needs_vision = any(t in AUTO_FILL_TYPE_VISION for _, t, _ in field_data)
    needs_audio  = any(t in AUTO_FILL_TYPE_AUDIO  for _, t, _ in field_data)

    vision_result = {}
    audio_result  = {}

    if needs_vision and asset_bytes and settings.OPENAI_API_KEY:
        vision_result = await _run_vision(asset_bytes, content_type, asset_format)

    if needs_audio and asset_bytes and settings.OPENAI_API_KEY:
        audio_result = await _run_whisper(asset_bytes)

    for field_id, auto_fill_type, default_value in field_data:
        value = None
        if auto_fill_type == "language":
            value = vision_result.get("language") or default_value
        elif auto_fill_type == "brand_names":
            brand_list = vision_result.get("brand_names", [])
            value = ", ".join(brand_list) if brand_list else default_value
        elif auto_fill_type == "vo_transcript":
            text = audio_result.get("text", "")
            value = text[:2000] if text else default_value  # cap at 2000 chars; see pitfall 1
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

    # Phase 4: Write results + mark COMPLETE (new session)
    async with get_session_factory()() as db:
        for field_id, value in values_to_write.items():
            existing = (await db.execute(
                select(AssetMetadataValue).where(
                    AssetMetadataValue.asset_id == asset_id,
                    AssetMetadataValue.field_id == field_id,
                )
            )).scalar_one_or_none()
            if existing:
                existing.value = value
            else:
                db.add(AssetMetadataValue(asset_id=asset_id, field_id=field_id, value=value))

        tracking = (await db.execute(
            select(AIInferenceTracking).where(AIInferenceTracking.asset_id == asset_id)
        )).scalar_one_or_none()
        if tracking:
            tracking.ai_inference_status = "COMPLETE"
            tracking.updated_at = datetime.utcnow()
        await db.commit()
```

### Alembic Migration Template

```python
# Source: existing pattern from m4n5o6p7q8r9_seed_image_metadata_fields.py

def upgrade() -> None:
    # 1. Add columns to metadata_fields
    op.add_column("metadata_fields",
        sa.Column("auto_fill_enabled", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("metadata_fields",
        sa.Column("auto_fill_type", sa.String(50), nullable=True))

    # 2. Widen asset_metadata_values.value to TEXT (Pitfall 1 prevention)
    op.alter_column("asset_metadata_values", "value",
        existing_type=sa.String(500), type_=sa.Text(), existing_nullable=True)

    # 3. Create ai_inference_tracking table
    op.create_table(
        "ai_inference_tracking",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("creative_assets.id"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("ai_inference_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), default=datetime.utcnow),
        sa.Column("updated_at", sa.DateTime(timezone=True), default=datetime.utcnow),
    )
    op.create_unique_constraint("uq_ai_inference_asset", "ai_inference_tracking", ["asset_id"])
    op.create_index("ix_ai_inference_status", "ai_inference_tracking", ["ai_inference_status"])
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `openai` v0.x (`openai.ChatCompletion.create`) | `openai` v1.x+ (`AsyncOpenAI`, `.parse()`) | Nov 2023 (v1.0) | Breaking API change; all old examples in training data are outdated |
| `gpt-4-vision-preview` for image input | `gpt-4o`, `gpt-4o-mini` | May 2024 | `gpt-4-vision-preview` deprecated; all vision now through `gpt-4o` family |
| Manual JSON parsing of LLM vision output | `client.beta.chat.completions.parse()` with Pydantic | Aug 2024 | Structured Outputs eliminate fragile JSON parsing |
| Whisper only via `whisper-1` | `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`, `whisper-1` | 2025 | `whisper-1` still valid and cheapest; new models available for higher quality |

**Deprecated/outdated:**
- `openai.ChatCompletion.create(...)` — replaced by `client.chat.completions.create()`
- `gpt-4-vision-preview` — deprecated, use `gpt-4o-mini` or `gpt-4o`
- Synchronous `OpenAI` client wrapped in `asyncio.run_in_executor` — use `AsyncOpenAI` natively

---

## Open Questions

1. **GPT-4o vs GPT-4o-mini for vision (Claude's Discretion)**
   - What we know: `gpt-4o-mini` is ~10x cheaper for vision; both support Structured Outputs. GPT-4o-mini uses 85 tokens for `low` detail images. Brand name extraction is a simple visual OCR-like task, not deep reasoning.
   - What's unclear: Empirical accuracy for brand logo + text recognition at `gpt-4o-mini` quality has not been validated on real agency creatives.
   - Recommendation: Default to `gpt-4o-mini` with the `detail: "high"` parameter. This reduces cost while maintaining pixel-level resolution for text/logo recognition. If brand name accuracy proves insufficient in production, swap model string — no other code change needed since the Pydantic schema is model-agnostic.

2. **VO Transcript field length (Claude's Discretion)**
   - What we know: `AssetMetadataValue.value` is currently `String(500)`. A 30-second ad VO can produce 100–200 words (~600–1200 characters). `verbose_json` from Whisper returns the full transcript.
   - What's unclear: Whether the org admin intends the VO field to store full transcripts or just a language/summary indicator.
   - Recommendation: Widen `asset_metadata_values.value` to `TEXT` via Alembic migration (captures full content), and cap in the service at 2000 characters to prevent unbounded storage from long-form videos.

3. **ffmpeg availability in Docker container**
   - What we know: `imageio-ffmpeg` is in `requirements.txt` and ships its own ffmpeg binary. The audio extraction subprocess approach uses system `ffmpeg`.
   - What's unclear: Whether the backend Docker image has system `ffmpeg` installed.
   - Recommendation: Use `imageio-ffmpeg.get_ffmpeg_exe()` to get the bundled binary path and pass it explicitly to `asyncio.create_subprocess_exec()` — avoids dependency on system `ffmpeg`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `openai` Python package | GPT-4o Vision, Whisper API | No (not in requirements.txt) | — | Must add to requirements.txt |
| `Pillow` Python package | Image resize (AI-05) | No (not in requirements.txt) | — | Must add to requirements.txt |
| `imageio-ffmpeg` | Video frame extraction | Yes (in requirements.txt `>=0.5.1`) | bundled | — |
| System `ffmpeg` | Audio extraction subprocess | Unknown (Docker not running) | — | Use `imageio_ffmpeg.get_ffmpeg_exe()` for bundled binary |
| MinIO `download_blob()` | Fetch asset bytes server-side | Yes — `ObjectStorageService.download_blob()` exists | — | — |
| `OPENAI_API_KEY` env var | All OpenAI calls | Optional by D-09 | — | Graceful no-op; default_value fallback |
| PostgreSQL | DB reads/writes | Yes (in docker-compose.yml) | 16-alpine | — |
| Redis | Not required by auto-fill | N/A | — | — |

**Missing dependencies with no fallback:**
- `openai` package — must be added to `requirements.txt` before any OpenAI calls can be made
- `Pillow` package — must be added to `requirements.txt` for image resize

**Missing dependencies with fallback:**
- System `ffmpeg` — use `imageio_ffmpeg.get_ffmpeg_exe()` to get bundled binary

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `backend/pytest.ini` or `backend/pyproject.toml` (existing pattern) |
| Quick run command | `cd backend && pytest tests/test_ai_autofill.py -x -q` |
| Full suite command | `cd backend && pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AI-01 | `AIInferenceTracking` model instantiates with PENDING status; unique constraint on asset_id | unit | `pytest tests/test_ai_autofill.py::test_tracking_model -x` | Wave 0 |
| AI-02 | `run_autofill_for_asset()` is called from sync service hook; does not block sync loop | unit (mock) | `pytest tests/test_ai_autofill.py::test_autofill_trigger_nonblocking -x` | Wave 0 |
| AI-03 | Language + Brand Names populated from mocked GPT-4o response; VO transcript + language from mocked Whisper; campaign_name/ad_name from asset columns; asset_stage always "Final" | unit (mock) | `pytest tests/test_ai_autofill.py::test_field_routing -x` | Wave 0 |
| AI-05 | Image over 4 MB is downsampled to <= 1568px longest edge before encoding | unit | `pytest tests/test_ai_autofill.py::test_image_downsample -x` | Wave 0 |
| AI-06 | COMPLETE guard: `run_autofill_for_asset()` with a COMPLETE tracking row returns immediately without calling OpenAI | unit (mock) | `pytest tests/test_ai_autofill.py::test_complete_guard -x` | Wave 0 |
| AI-09 | `OPENAI_API_KEY=None` → all AI fields fall back to default_value; no exception raised | unit | `pytest tests/test_ai_autofill.py::test_no_api_key_graceful -x` | Wave 0 |
| D-14 | `PATCH /{asset_id}/metadata` sets `scoring_status = UNSCORED` on the CreativeScoreResult | unit | `pytest tests/test_ai_autofill.py::test_metadata_patch_resets_score -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && pytest tests/test_ai_autofill.py -x -q`
- **Per wave merge:** `cd backend && pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_ai_autofill.py` — all AI-01 through AI-06 + D-14 tests; needs mocks for `AsyncOpenAI`, `ObjectStorageService.download_blob`, `get_session_factory`
- [ ] `backend/app/models/ai_inference.py` — `AIInferenceTracking` model file (needed by test imports)
- [ ] `backend/app/services/ai_autofill.py` — main service file
- [ ] `requirements.txt` additions: `openai>=2.0.0`, `Pillow>=10.0.0`

---

## Project Constraints (from CLAUDE.md)

No `CLAUDE.md` found in the project root. No project-specific constraints apply beyond those documented in CONTEXT.md above.

---

## Sources

### Primary (HIGH confidence)

- OpenAI Python SDK official docs — `AsyncOpenAI`, `client.beta.chat.completions.parse()`, `audio.transcriptions.create()`, base64 vision input format
  - https://developers.openai.com/api/reference/python/resources/audio/subresources/transcriptions/methods/create
  - https://developers.openai.com/api/docs/guides/structured-outputs
- PyPI `openai` — latest version `2.30.0` confirmed (2026-03-25)
  - https://pypi.org/project/openai/
- PyPI `Pillow` — latest version `12.1.1` confirmed (2026-04-01)
  - https://pypi.org/project/pillow/
- Project codebase `scoring_job.py` — session-per-operation pattern (verified by reading source)
- Project codebase `object_storage.py` — `download_blob()` method signature (verified by reading source)
- Project codebase `creative.py` — `AssetMetadataValue.value` is `String(500)` (verified by reading source)
- Project codebase `creative.py` — `CreativeAsset.campaign_name` and `ad_name` columns confirmed (verified by reading source)
- Project codebase `config.py` — `OPENAI_API_KEY` not yet declared (verified by reading source)

### Secondary (MEDIUM confidence)

- OpenAI community: BytesIO `.name` attribute required for Whisper — multiple sources confirm
  - https://github.com/openai/openai-python/issues/2315
- OpenAI community: Structured Outputs compatible with vision inputs on `gpt-4o-mini` and `gpt-4o-2024-08-06`+
  - https://community.openai.com/t/official-documentation-for-supported-schemas-for-response-format-parameter-in-calls-to-client-beta-chats-completions-parse/932422
- `verbose_json` Whisper response includes top-level `language` field — confirmed via API reference

### Tertiary (LOW confidence)

- GPT-4o-mini brand name accuracy on real ad creatives — not empirically validated; production testing recommended before broad rollout

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — package names, versions, and APIs verified via PyPI and official SDK reference
- Architecture: HIGH — patterns derived directly from existing project codebase (`scoring_job.py`, `meta_sync.py`, `object_storage.py`)
- OpenAI API patterns: HIGH — verified via official SDK documentation
- Pitfalls: HIGH — `String(500)` confirmed by reading `creative.py`; session pattern confirmed by reading `scoring_job.py`; BytesIO `.name` confirmed by multiple community sources
- GPT-4o-mini accuracy for brand names: LOW — unvalidated on production data

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (OpenAI SDK moves fast — re-verify model names and Structured Outputs API before implementation)
