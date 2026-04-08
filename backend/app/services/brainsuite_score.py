"""BrainSuiteScoreService — async httpx client for BrainSuite API scoring.

Handles OAuth 2.0 Client Credentials token management, the announce→upload→start
job flow (no public URL required), job polling, channel mapping, payload
construction, and score extraction with visualization URL stripping.
"""
import asyncio
import base64
import logging
import mimetypes
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.core.config import settings
from app.services.brainsuite_exceptions import (
    BrainSuiteRateLimitError,
    BrainSuite5xxError,
    BrainSuiteJobError,
)

logger = logging.getLogger(__name__)


# BrainSuiteRateLimitError, BrainSuite5xxError, and BrainSuiteJobError are
# imported from app.services.brainsuite_exceptions (shared module) so that all
# BrainSuite service modules raise the same class objects — enabling callers to
# catch them with a single import regardless of which service raised them.


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class BrainSuiteScoreService:
    """Async client for the BrainSuite ACE_VIDEO_SMV_API scoring pipeline."""

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def _get_token(self) -> str:
        """Return a valid Bearer token, fetching a new one if necessary.

        Caches the token for 50 minutes to avoid unnecessary round-trips.
        On a 401 from any API call the caller should set _token = None and
        call this method again to force a refresh.
        """
        now = datetime.now(timezone.utc)
        if self._token and self._token_expires_at and now < self._token_expires_at:
            return self._token

        client_id = settings.BRAINSUITE_CLIENT_ID or ""
        client_secret = settings.BRAINSUITE_CLIENT_SECRET or ""
        credentials = f"{client_id}:{client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        logger.info("BrainSuite auth: POST %s (client_id=%s...)", settings.BRAINSUITE_AUTH_URL, client_id[:8] if client_id else "MISSING")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                settings.BRAINSUITE_AUTH_URL,
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )

        logger.info("BrainSuite auth response: status=%s body=%s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        data = resp.json()

        self._token = data["access_token"]
        self._token_expires_at = now + timedelta(minutes=50)
        logger.info("BrainSuite token refreshed, expires at %s", self._token_expires_at.isoformat())
        return self._token

    def _invalidate_token(self) -> None:
        """Invalidate the cached token so the next call fetches a new one."""
        self._token = None
        self._token_expires_at = None

    # ------------------------------------------------------------------
    # Low-level API helper with retry
    # ------------------------------------------------------------------

    async def _api_post_with_retry(
        self, url: str, json_body: Optional[dict] = None, log_name: str = ""
    ) -> dict:
        """POST to a BrainSuite API endpoint with 429/5xx retry and 401 token refresh.

        Raises:
            BrainSuiteRateLimitError: on HTTP 429 (caller must respect x-ratelimit-reset).
            BrainSuite5xxError: on HTTP 5xx (caller should apply exponential backoff).
            ValueError: on other 4xx errors (no retry — caller marks asset FAILED).
            RuntimeError: if all retry attempts are exhausted.
        """
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                token = await self._get_token()
                logger.info("BrainSuite %s: POST %s", log_name, url)
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        json=json_body or {},
                    )

                logger.info(
                    "BrainSuite %s response: status=%s body=%s",
                    log_name,
                    resp.status_code,
                    resp.text[:300],
                )

                if resp.status_code == 429:
                    reset_header = resp.headers.get("x-ratelimit-reset", "")
                    try:
                        reset_at = datetime.fromisoformat(reset_header.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        reset_at = datetime.now(timezone.utc) + timedelta(seconds=60)
                    raise BrainSuiteRateLimitError(reset_at)

                if resp.status_code >= 500:
                    logger.warning(
                        "BrainSuite %s 5xx: status=%s body=%s",
                        log_name,
                        resp.status_code,
                        resp.text[:200],
                    )
                    raise BrainSuite5xxError(f"BrainSuite {resp.status_code}: {resp.text[:200]}")

                if resp.status_code == 401:
                    logger.warning(
                        "BrainSuite %s 401 — invalidating token, retrying (attempt %d/%d)",
                        log_name,
                        attempt + 1,
                        max_attempts,
                    )
                    self._invalidate_token()
                    continue

                if resp.status_code >= 400:
                    raise ValueError(f"BrainSuite {resp.status_code}: {resp.text[:500]}")

                return resp.json()

            except BrainSuiteRateLimitError as exc:
                now_utc = datetime.now(timezone.utc)
                wait_secs = max(0.0, (exc.reset_at - now_utc).total_seconds()) + 2
                logger.warning(
                    "BrainSuite %s 429 — waiting %.1fs (attempt %d/%d)",
                    log_name,
                    wait_secs,
                    attempt + 1,
                    max_attempts,
                )
                await asyncio.sleep(wait_secs)

            except BrainSuite5xxError:
                backoff = min(2 ** attempt * 5, 120)
                logger.warning(
                    "BrainSuite %s 5xx — backoff %ds (attempt %d/%d)",
                    log_name,
                    backoff,
                    attempt + 1,
                    max_attempts,
                )
                await asyncio.sleep(backoff)

        raise RuntimeError(f"BrainSuite {log_name} exhausted retries")

    # ------------------------------------------------------------------
    # Announce → Upload → Start flow
    # ------------------------------------------------------------------

    async def _announce_job(self) -> str:
        """POST /announce — creates a new job in Announced state, returns job_id."""
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/announce"
        resp = await self._api_post_with_retry(url, log_name="announce")
        job_id = resp.get("id")
        if not job_id:
            raise ValueError(f"BrainSuite announce response missing id: {resp}")
        return str(job_id)

    async def _announce_asset(self, job_id: str, asset_id: str, filename: str) -> dict:
        """POST /{jobId}/assets — announces a single asset and returns uploadUrl + fields."""
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/{job_id}/assets"
        resp = await self._api_post_with_retry(
            url,
            json_body={"assetId": asset_id, "name": filename},
            log_name="announce_asset",
        )
        if "uploadUrl" not in resp:
            raise ValueError(f"BrainSuite announce_asset response missing uploadUrl: {resp}")
        return resp  # {assetId, name, uploadUrl, fields}

    async def _upload_to_brainsuite_s3(
        self, upload_url: str, fields: dict, file_bytes: bytes, filename: str
    ) -> None:
        """Upload file bytes to BrainSuite's S3 using the presigned POST envelope.

        The S3 presigned POST requires all policy fields to come before the file.
        Returns nothing; raises ValueError on non-2xx response.
        """
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "video/mp4"

        # Build multipart: policy fields first, then the file (S3 requirement)
        form_files: dict = {k: (None, v) for k, v in fields.items()}
        form_files["file"] = (filename, file_bytes, content_type)

        logger.info(
            "BrainSuite S3 upload: POST %s filename=%s size=%d bytes",
            upload_url[:60],
            filename,
            len(file_bytes),
        )
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(upload_url, files=form_files)

        if resp.status_code not in (200, 204):
            raise ValueError(
                f"BrainSuite S3 upload failed: HTTP {resp.status_code} — {resp.text[:300]}"
            )
        logger.info("BrainSuite S3 upload complete (status=%s)", resp.status_code)

    async def _start_job(self, job_id: str, briefing_data: dict) -> None:
        """POST /{jobId}/start — transitions job from Announced to Scheduled/Created."""
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/{job_id}/start"
        await self._api_post_with_retry(url, json_body=briefing_data, log_name="start")

    async def submit_job_with_upload(
        self, file_bytes: bytes, filename: str, briefing_data: dict
    ) -> str:
        """Run the full announce→upload→start flow and return the job_id.

        This avoids the need for a publicly reachable video URL — the file is
        downloaded from internal storage and pushed directly to BrainSuite's S3.

        Args:
            file_bytes: Raw video bytes.
            filename:   Original filename including extension (e.g. "video.mp4").
            briefing_data: BriefingData payload (channel, language, etc.) — same
                           shape as the old /create payload but assets use
                           {assetId, name} without a url field.

        Returns:
            job_id string to pass to poll_job_status().
        """
        job_id = await self._announce_job()
        logger.info("BrainSuite job announced: job_id=%s", job_id)

        asset_id = "video"
        upload_info = await self._announce_asset(job_id, asset_id, filename)
        upload_url = upload_info["uploadUrl"]
        s3_fields = upload_info.get("fields", {})

        await self._upload_to_brainsuite_s3(upload_url, s3_fields, file_bytes, filename)

        await self._start_job(job_id, briefing_data)
        logger.info("BrainSuite job started: job_id=%s channel=%s", job_id, briefing_data.get("input", {}).get("channel"))

        return job_id

    # ------------------------------------------------------------------
    # Job polling
    # ------------------------------------------------------------------

    async def poll_job_status(
        self,
        job_id: str,
        fast_polls: int = 60,
        fast_interval: int = 30,
        slow_interval: int = 90,
    ) -> dict:
        """Poll the BrainSuite job status endpoint until a terminal status.

        Polls indefinitely — never times out. Only stops on a terminal status:
            Succeeded — returns the full response JSON
            Failed / Stale — raises BrainSuiteJobError

        Interval strategy:
            First fast_polls attempts: fast_interval seconds between polls.
            After that: slow_interval seconds (job is taking unusually long but
            BrainSuite will eventually return a terminal status).

        Raises:
            BrainSuiteJobError: if BrainSuite reports Failed or Stale.
        """
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/{job_id}"
        in_progress = {"Announced", "Scheduled", "Created", "Started"}
        poll_num = 0

        while True:
            token = await self._get_token()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                )

            if resp.status_code == 401:
                self._invalidate_token()
                poll_num += 1
                continue

            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "")
            interval = fast_interval if poll_num < fast_polls else slow_interval

            logger.info(
                "BrainSuite job %s — status=%s (poll %d, next in %ds)",
                job_id, status, poll_num + 1, interval,
            )

            if status == "Succeeded":
                return data

            if status in ("Failed", "Stale"):
                error_detail = data.get("errorDetail") or data.get("error") or status
                raise BrainSuiteJobError(
                    f"BrainSuite job {job_id} ended with status={status}: {error_detail}"
                )

            if poll_num == fast_polls:
                logger.warning(
                    "BrainSuite job %s still in progress after %d polls — switching to %ds interval",
                    job_id, fast_polls, slow_interval,
                )

            if status not in in_progress:
                logger.warning("BrainSuite job %s — unexpected status=%s, continuing", job_id, status)

            await asyncio.sleep(interval)
            poll_num += 1


# ---------------------------------------------------------------------------
# Module-level functions
# ---------------------------------------------------------------------------


def map_channel(
    platform: str,
    placement: Optional[str],
    metadata: Optional[dict[str, str]] = None,
) -> str:
    """Map platform + placement to a BrainSuite channel identifier.

    Override: if metadata contains a non-empty 'brainsuite_channel' key,
    that value is returned as-is.

    Mapping table (per CONTEXT.md):
        META + facebook_feed         → facebook_feed
        META + facebook_story        → facebook_story
        META + instagram_feed        → instagram_feed
        META + instagram_story       → instagram_story
        META + instagram_reels/reel  → instagram_reel
        META + audience_network_*/unknown → facebook_feed (fallback)
        TIKTOK + *                   → tiktok
        GOOGLE_ADS + *               → youtube
        DV360 + *                    → youtube
        Default fallback             → facebook_feed
    """
    if metadata and metadata.get("brainsuite_channel"):
        return metadata["brainsuite_channel"]

    # Normalize placement
    normalized = (placement or "").lower().strip()
    # Normalise plural "reels" → "reel"
    normalized = normalized.replace("reels", "reel")

    platform_upper = (platform or "").upper()

    if platform_upper == "META":
        valid_placements = {
            "facebook_feed",
            "facebook_story",
            "instagram_feed",
            "instagram_story",
            "instagram_reel",
        }
        if normalized in valid_placements:
            return normalized
        # audience_network_* or anything unknown → fallback
        return "facebook_feed"

    if platform_upper == "TIKTOK":
        return "tiktok"

    if platform_upper in ("GOOGLE_ADS", "DV360"):
        return "youtube"

    return "facebook_feed"


def build_scoring_payload(
    asset_name: str,
    platform: str,
    placement: Optional[str],
    metadata: dict[str, str],
) -> dict:
    """Build the BrainSuite BriefingData payload for POST /{jobId}/start.

    Args:
        asset_name: Filename of the creative asset (e.g. "video.mp4").
        platform: Ad platform identifier (e.g. "META", "TIKTOK").
        placement: Ad placement string from the sync layer (may be None).
        metadata: Dict of MetadataField name → value for this asset.

    Returns:
        Dict matching the BrainSuite BriefingData schema used by /start:
        {"assets": [...], "input": {...}}
        Assets reference the already-uploaded file by assetId (no url needed).
    """
    channel = map_channel(platform, placement, metadata)

    # Brand names: split on comma or newline, strip, filter empty
    raw_brand_names = metadata.get("brainsuite_brand_names", "")
    brand_names: list[str] = []
    for part in raw_brand_names.replace("\n", ",").split(","):
        stripped = part.strip()
        if stripped:
            brand_names.append(stripped)

    input_obj: dict = {
        "channel": channel,
        "assetLanguage": (metadata.get("brainsuite_asset_language", "en-US") or "en-US").replace("_", "-"),
        "brandNames": brand_names if brand_names else ["Brand"],
        "projectName": metadata.get("brainsuite_project_name") or "Spring Campaign 2026",
        "assetName": metadata.get("brainsuite_asset_name") or "asset_name",
        "assetStage": metadata.get("brainsuite_asset_stage") or "finalVersion",
    }

    voice_over = metadata.get("brainsuite_voice_over")
    if voice_over:
        input_obj["voiceOver"] = voice_over
        input_obj["voiceOverLanguage"] = (metadata.get("brainsuite_voice_over_language") or "en").replace("_", "-")

    # Assets reference the uploaded file by assetId — no URL needed
    assets = [{"assetId": "video", "name": asset_name}]

    return {"assets": assets, "input": input_obj}


def _strip_visualizations(obj: object) -> object:
    """Recursively remove all 'visualizations' keys from a nested dict/list.

    BrainSuite visualization URLs expire 1 hour after retrieval — they must
    not be persisted to the database.  Used as a fallback when persistence fails.
    """
    if isinstance(obj, dict):
        return {
            k: _strip_visualizations(v)
            for k, v in obj.items()
            if k != "visualizations"
        }
    if isinstance(obj, list):
        return [_strip_visualizations(item) for item in obj]
    return obj


async def persist_and_replace_visualizations(output: dict, asset_id: str) -> dict:
    """Download all BrainSuite visualization URLs, store in our S3, replace in-place.

    BrainSuite presigned visualization URLs expire ~1 hour after retrieval.
    This function must be called immediately after receiving a successful job result.
    Each url within a 'visualizations' dict is downloaded and re-uploaded to our
    object storage under brainsuite/{asset_id}/viz/... returning a persistent
    /objects/... served URL.  Per-URL failures are logged and the url is set to
    None so the UI can gracefully show "not available".

    Args:
        output:   The raw 'output' dict from a BrainSuite job response.
        asset_id: UUID string of the creative asset (used as S3 path prefix).

    Returns:
        A deep copy of output with all visualization URLs replaced.
    """
    # Import here to avoid circular dependency at module load time
    from app.services.object_storage import get_object_storage
    import os
    import re
    import tempfile

    storage = get_object_storage()

    async def _download_and_store(url: str, s3_path: str, type_hint: str = "") -> Optional[str]:
        """Download a single URL and upload to S3.  Returns served URL or None.

        type_hint: BrainSuite viz type field — "image" or "movie" — used as last-resort
        extension fallback when content-type and URL path give no usable extension.
        """
        content_type: Optional[str] = None
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(
                    "Viz download HTTP %s for %s", resp.status_code, url[:80]
                )
                return None
            content_type = resp.headers.get("content-type", "").split(";")[0].strip() or None
            # 1. Explicit map — mimetypes.guess_extension("video/mp4") returns None on most platforms
            _EXT_MAP = {
                "video/mp4": ".mp4",
                "video/webm": ".webm",
                "video/quicktime": ".mov",
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "image/webp": ".webp",
            }
            ext = _EXT_MAP.get(content_type or "")
            # 2. mimetypes fallback
            if not ext:
                ext = mimetypes.guess_extension(content_type or "") or ""
                if ext in (".jpe", ".jpeg"):
                    ext = ".jpg"
            # 3. Extract from the URL path (presigned URLs often contain the original filename)
            if not ext:
                from urllib.parse import urlparse
                _, url_ext = os.path.splitext(urlparse(url).path)
                if url_ext and len(url_ext) <= 5:
                    ext = url_ext.lower()
            # 4. BrainSuite type hint as last resort
            if not ext:
                ext = ".mp4" if type_hint == "movie" else ".jpg"
            full_s3_path = s3_path + ext if ext else s3_path
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            try:
                served = storage.upload_file(tmp_path, full_s3_path, content_type)
            finally:
                os.unlink(tmp_path)
            logger.info("Persisted viz: %s → %s", url[:60], served)
            return served
        except Exception as exc:
            logger.warning("Could not persist viz %s: %s: %s", url[:60], type(exc).__name__, exc)
            return None

    async def _walk(obj: object, breadcrumb: str) -> object:
        if isinstance(obj, dict):
            result: dict = {}
            for k, v in obj.items():
                child = f"{breadcrumb}/{k}" if breadcrumb else k
                if k == "visualizations":
                    if isinstance(v, dict):
                        # executiveSummary level: {sceneMontage: {type, url}}
                        new_vizs: dict = {}
                        for viz_key, viz_val in v.items():
                            if isinstance(viz_val, dict) and isinstance(viz_val.get("url"), str):
                                raw_url = viz_val["url"]
                                if raw_url.startswith("http"):
                                    safe = re.sub(r"[^a-zA-Z0-9_/.-]", "_", child)
                                    stored = await _download_and_store(
                                        raw_url,
                                        f"creatives/brainsuite/{asset_id}/viz/{safe}/{viz_key}",
                                        type_hint=viz_val.get("type", ""),
                                    )
                                    viz_val = {**viz_val, "url": stored}
                            new_vizs[viz_key] = viz_val
                        result[k] = new_vizs
                    elif isinstance(v, list):
                        # kpi level: [{type: "image"|"movie", url: "..."}, ...]
                        new_list = []
                        for idx, item in enumerate(v):
                            if isinstance(item, dict) and isinstance(item.get("url"), str):
                                raw_url = item["url"]
                                if raw_url.startswith("http"):
                                    safe = re.sub(r"[^a-zA-Z0-9_/.-]", "_", child)
                                    stored = await _download_and_store(
                                        raw_url,
                                        f"creatives/brainsuite/{asset_id}/viz/{safe}/{idx}",
                                        type_hint=item.get("type", ""),
                                    )
                                    item = {**item, "url": stored}
                            new_list.append(item)
                        result[k] = new_list
                    else:
                        result[k] = v
                else:
                    result[k] = await _walk(v, child)
            return result
        if isinstance(obj, list):
            return [await _walk(item, f"{breadcrumb}/{i}") for i, item in enumerate(obj)]
        return obj

    return await _walk(output, "")


def extract_score_data(job_response: dict, strip_viz: bool = True) -> dict:
    """Extract the primary score fields from a successful BrainSuite job response.

    Navigates to output.legResults[0].executiveSummary for the score values.
    The full output blob is stored as score_dimensions.

    Args:
        job_response: Full BrainSuite job response dict.
        strip_viz:    When True (default) removes all 'visualizations' keys — use
                      when visualizations have NOT been persisted to our storage.
                      Pass False after calling persist_and_replace_visualizations
                      so the stored /objects/... URLs are preserved.

    Returns:
        {
            "total_score": float,
            "total_rating": str,
            "score_dimensions": dict
        }

    Raises:
        KeyError / IndexError: if the response does not match the expected shape.
    """
    output = job_response.get("output", {})
    leg_results = output.get("legResults", [])
    summary = leg_results[0].get("executiveSummary", {}) if leg_results else {}

    total_score = summary.get("totalScore") or summary.get("rawTotalScore") or 0.0
    total_rating = summary.get("totalRating", "")

    score_dimensions = _strip_visualizations(output) if strip_viz else output

    return {
        "total_score": float(total_score),
        "total_rating": str(total_rating),
        "score_dimensions": score_dimensions,
    }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

brainsuite_score_service = BrainSuiteScoreService()
