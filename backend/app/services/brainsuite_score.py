"""BrainSuiteScoreService — async httpx client for BrainSuite API scoring.

Handles OAuth 2.0 Client Credentials token management, job creation with
429/5xx retry logic, job polling, channel mapping, payload construction,
and score extraction with visualization URL stripping.
"""
import asyncio
import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class BrainSuiteRateLimitError(Exception):
    """Raised when BrainSuite API responds with HTTP 429."""

    def __init__(self, reset_at: datetime) -> None:
        self.reset_at = reset_at
        super().__init__(f"Rate limited until {reset_at.isoformat()}")


class BrainSuite5xxError(Exception):
    """Raised when BrainSuite API responds with a 5xx error."""
    pass


class BrainSuiteJobError(Exception):
    """Raised when a BrainSuite job fails, goes stale, or times out."""
    pass


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
    # Low-level job creation
    # ------------------------------------------------------------------

    async def _create_job_raw(self, token: str, payload: dict) -> dict:
        """POST the scoring payload and return the parsed JSON response.

        Raises:
            BrainSuiteRateLimitError: on HTTP 429 (caller must respect x-ratelimit-reset).
            BrainSuite5xxError: on HTTP 5xx (caller should apply exponential backoff).
            ValueError: on other 4xx errors (no retry — log as FAILED).
        """
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/create"
        logger.info("BrainSuite create job: POST %s | channel=%s asset=%s",
                    url,
                    payload.get("input", {}).get("channel"),
                    payload.get("assets", [{}])[0].get("name"))
        logger.debug("BrainSuite create job payload: %s", payload)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        logger.info("BrainSuite create job response: status=%s body=%s", resp.status_code, resp.text[:500])

        if resp.status_code == 429:
            reset_header = resp.headers.get("x-ratelimit-reset", "")
            try:
                reset_at = datetime.fromisoformat(reset_header.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                # Fallback: back off 60 seconds if header is malformed
                reset_at = datetime.now(timezone.utc) + timedelta(seconds=60)
            raise BrainSuiteRateLimitError(reset_at)

        if resp.status_code >= 500:
            logger.warning(
                "BrainSuite 5xx: status=%s body=%s", resp.status_code, resp.text[:200]
            )
            raise BrainSuite5xxError(f"BrainSuite {resp.status_code}: {resp.text[:200]}")

        if resp.status_code >= 400:
            raise ValueError(
                f"BrainSuite {resp.status_code}: {resp.text[:500]}"
            )

        return resp.json()

    # ------------------------------------------------------------------
    # High-level job creation with retry
    # ------------------------------------------------------------------

    async def create_job_with_retry(self, payload: dict) -> dict:
        """Create a BrainSuite scoring job, retrying on 429 and 5xx.

        - 429: waits until x-ratelimit-reset + 2 seconds
        - 5xx: exponential backoff (5s, 10s, 20s … capped at 120s)
        - 401: invalidates token, retries with a fresh token
        - 4xx (other): raises immediately — caller marks asset FAILED
        - Exhausted retries: raises RuntimeError
        """
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                token = await self._get_token()
                return await self._create_job_raw(token, payload)

            except BrainSuiteRateLimitError as exc:
                now_utc = datetime.now(timezone.utc)
                wait_secs = max(0.0, (exc.reset_at - now_utc).total_seconds()) + 2
                logger.warning(
                    "BrainSuite 429 — waiting %.1fs until %s (attempt %d/%d)",
                    wait_secs,
                    exc.reset_at.isoformat(),
                    attempt + 1,
                    max_attempts,
                )
                await asyncio.sleep(wait_secs)

            except BrainSuite5xxError:
                backoff = min(2 ** attempt * 5, 120)
                logger.warning(
                    "BrainSuite 5xx — exponential backoff %ds (attempt %d/%d)",
                    backoff,
                    attempt + 1,
                    max_attempts,
                )
                await asyncio.sleep(backoff)

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    logger.warning(
                        "BrainSuite 401 — invalidating token, retrying (attempt %d/%d)",
                        attempt + 1,
                        max_attempts,
                    )
                    self._invalidate_token()
                    continue
                raise

        raise RuntimeError("BrainSuite create_job exhausted retries")

    # ------------------------------------------------------------------
    # Job polling
    # ------------------------------------------------------------------

    async def poll_job_status(
        self,
        job_id: str,
        max_polls: int = 60,
        poll_interval: int = 30,
    ) -> dict:
        """Poll the BrainSuite job status endpoint until a terminal status.

        Terminal statuses:
            Succeeded — returns the full response JSON
            Failed / Stale — raises BrainSuiteJobError

        Raises:
            BrainSuiteJobError: if job fails, goes stale, or max_polls is exhausted.
        """
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/{job_id}"
        in_progress = {"Scheduled", "Created", "Started"}

        for poll_num in range(max_polls):
            token = await self._get_token()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                )

            if resp.status_code == 401:
                self._invalidate_token()
                continue

            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "")

            logger.info(
                "BrainSuite job %s — status=%s (poll %d/%d)",
                job_id,
                status,
                poll_num + 1,
                max_polls,
            )

            if status == "Succeeded":
                return data

            if status in ("Failed", "Stale"):
                error_detail = data.get("errorDetail") or data.get("error") or status
                raise BrainSuiteJobError(
                    f"BrainSuite job {job_id} ended with status={status}: {error_detail}"
                )

            if status in in_progress:
                await asyncio.sleep(poll_interval)
                continue

            # Unexpected status — treat as transient, keep polling
            logger.warning("BrainSuite job %s — unexpected status=%s", job_id, status)
            await asyncio.sleep(poll_interval)

        raise BrainSuiteJobError(f"Job polling timed out for job_id={job_id} after {max_polls} polls")


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
    signed_url: str,
    platform: str,
    placement: Optional[str],
    metadata: dict[str, str],
) -> dict:
    """Build the BrainSuite CreateJobInput payload.

    Args:
        asset_name: Filename of the creative asset (e.g. "video.mp4").
        signed_url: Fresh pre-signed S3 URL valid for the duration of the job.
        platform: Ad platform identifier (e.g. "META", "TIKTOK").
        placement: Ad placement string from the sync layer (may be None).
        metadata: Dict of MetadataField name → value for this asset.

    Returns:
        Dict matching the BrainSuite CreateJobInput schema:
        {"assets": [...], "input": {...}}
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
        "assetLanguage": metadata.get("brainsuite_asset_language", "en"),
        "brandNames": brand_names,
        "projectName": metadata.get("brainsuite_project_name") or "Spring Campaign 2026",
        "assetName": metadata.get("brainsuite_asset_name") or "asset_name",
        "assetStage": metadata.get("brainsuite_asset_stage") or "finalVersion",
    }

    voice_over = metadata.get("brainsuite_voice_over")
    if voice_over:
        input_obj["voiceOver"] = voice_over
        input_obj["voiceOverLanguage"] = metadata.get("brainsuite_voice_over_language") or "en"

    assets = [
        {
            "assetId": "video",
            "name": asset_name,
            "url": signed_url,
        }
    ]

    return {"assets": assets, "input": input_obj}


def _strip_visualizations(obj: object) -> object:
    """Recursively remove all 'visualizations' keys from a nested dict/list.

    BrainSuite visualization URLs expire 1 hour after retrieval — they must
    not be persisted to the database.
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


def extract_score_data(job_response: dict) -> dict:
    """Extract the primary score fields from a successful BrainSuite job response.

    Navigates to output.legResults[0].executiveSummary for the score values.
    The full output blob is stored (minus visualization URLs) as score_dimensions.

    Returns:
        {
            "total_score": float,
            "total_rating": str,
            "score_dimensions": dict  # full output with visualizations stripped
        }

    Raises:
        KeyError / IndexError: if the response does not match the expected shape.
    """
    output = job_response.get("output", {})
    leg_results = output.get("legResults", [])
    summary = leg_results[0].get("executiveSummary", {}) if leg_results else {}

    total_score = summary.get("totalScore") or summary.get("rawTotalScore") or 0.0
    total_rating = summary.get("totalRating", "")

    score_dimensions = _strip_visualizations(output)

    return {
        "total_score": float(total_score),
        "total_rating": str(total_rating),
        "score_dimensions": score_dimensions,
    }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

brainsuite_score_service = BrainSuiteScoreService()
