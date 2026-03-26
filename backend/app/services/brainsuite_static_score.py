"""BrainSuiteStaticScoreService — async httpx client for BrainSuite Static API scoring.

Handles OAuth 2.0 Client Credentials token management, the announce→upload→start
job flow for static images (no public URL required), job polling, channel mapping,
and payload construction.

Key differences from the video service (brainsuite_score.py):
  - Endpoint path: ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API (not ACE_VIDEO/ACE_VIDEO_SMV_API)
  - Announce step: payload carries full briefing data (channel, legs[], etc.) — NOT in start
  - Start step: empty body {} — briefing data was already sent in announce (D-04)
  - Announce payload has no AOI or brand value fields (D-05, D-13)
  - Channel mapping: Instagram vs Facebook only (not TikTok/YouTube — image scoring is META-only)
"""
import asyncio
import base64
import logging
import mimetypes
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions (mirrored from video service)
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

class BrainSuiteStaticScoreService:
    """Async client for the BrainSuite ACE_STATIC_SOCIAL_STATIC_API scoring pipeline.

    Mirrors the structure of BrainSuiteScoreService (video) with differences for
    the Static API: briefing data travels in the announce payload, start body is empty.
    """

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Auth — identical to video service (shared credentials per D-15)
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

        logger.info(
            "BrainSuite static auth: POST %s (client_id=%s...)",
            settings.BRAINSUITE_AUTH_URL,
            client_id[:8] if client_id else "MISSING",
        )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                settings.BRAINSUITE_AUTH_URL,
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )

        logger.info(
            "BrainSuite static auth response: status=%s body=%s",
            resp.status_code,
            resp.text[:500],
        )
        resp.raise_for_status()
        data = resp.json()

        self._token = data["access_token"]
        self._token_expires_at = now + timedelta(minutes=50)
        logger.info(
            "BrainSuite static token refreshed, expires at %s",
            self._token_expires_at.isoformat(),
        )
        return self._token

    def _invalidate_token(self) -> None:
        """Invalidate the cached token so the next call fetches a new one."""
        self._token = None
        self._token_expires_at = None

    # ------------------------------------------------------------------
    # Low-level API helper with retry — identical logic to video service
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
                logger.info("BrainSuite static %s: POST %s", log_name, url)
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
                    "BrainSuite static %s response: status=%s body=%s",
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
                        "BrainSuite static %s 5xx: status=%s body=%s",
                        log_name,
                        resp.status_code,
                        resp.text[:200],
                    )
                    raise BrainSuite5xxError(f"BrainSuite static {resp.status_code}: {resp.text[:200]}")

                if resp.status_code == 401:
                    logger.warning(
                        "BrainSuite static %s 401 — invalidating token, retrying (attempt %d/%d)",
                        log_name,
                        attempt + 1,
                        max_attempts,
                    )
                    self._invalidate_token()
                    continue

                if resp.status_code >= 400:
                    raise ValueError(f"BrainSuite static {resp.status_code}: {resp.text[:500]}")

                return resp.json()

            except BrainSuiteRateLimitError as exc:
                now_utc = datetime.now(timezone.utc)
                wait_secs = max(0.0, (exc.reset_at - now_utc).total_seconds()) + 2
                logger.warning(
                    "BrainSuite static %s 429 — waiting %.1fs (attempt %d/%d)",
                    log_name,
                    wait_secs,
                    attempt + 1,
                    max_attempts,
                )
                await asyncio.sleep(wait_secs)

            except BrainSuite5xxError:
                backoff = min(2 ** attempt * 5, 120)
                logger.warning(
                    "BrainSuite static %s 5xx — backoff %ds (attempt %d/%d)",
                    log_name,
                    backoff,
                    attempt + 1,
                    max_attempts,
                )
                await asyncio.sleep(backoff)

        raise RuntimeError(f"BrainSuite static {log_name} exhausted retries")

    # ------------------------------------------------------------------
    # Announce → Upload → Start flow (Static API variant)
    # ------------------------------------------------------------------

    async def _announce_job(self, announce_payload: dict) -> str:
        """POST /announce — creates a new job in Announced state, returns job_id.

        For the Static API, the full briefing data (channel, legs[], etc.) is sent
        in the announce step — NOT in the start step (D-04).

        Args:
            announce_payload: Full payload dict with input{} containing channel,
                              projectName, assetLanguage, iconicColorScheme, legs[].

        Returns:
            job_id string.
        """
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/announce"
        resp = await self._api_post_with_retry(url, json_body=announce_payload, log_name="announce")
        job_id = resp.get("id")
        if not job_id:
            raise ValueError(f"BrainSuite static announce response missing id: {resp}")
        return str(job_id)

    async def _announce_asset(self, job_id: str, asset_id: str, filename: str) -> dict:
        """POST /{jobId}/assets — announces a single asset and returns uploadUrl + fields."""
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/{job_id}/assets"
        resp = await self._api_post_with_retry(
            url,
            json_body={"assetId": asset_id, "name": filename},
            log_name="announce_asset",
        )
        if "uploadUrl" not in resp:
            raise ValueError(f"BrainSuite static announce_asset response missing uploadUrl: {resp}")
        return resp  # {assetId, name, uploadUrl, fields}

    async def _upload_to_brainsuite_s3(
        self, upload_url: str, fields: dict, file_bytes: bytes, filename: str
    ) -> None:
        """Upload file bytes to BrainSuite's S3 using the presigned POST envelope.

        The S3 presigned POST requires all policy fields to come before the file.
        Returns nothing; raises ValueError on non-2xx response.
        """
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "image/jpeg"

        # Build multipart: policy fields first, then the file (S3 requirement)
        form_files: dict = {k: (None, v) for k, v in fields.items()}
        form_files["file"] = (filename, file_bytes, content_type)

        logger.info(
            "BrainSuite static S3 upload: POST %s filename=%s size=%d bytes",
            upload_url[:60],
            filename,
            len(file_bytes),
        )
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(upload_url, files=form_files)

        if resp.status_code not in (200, 204):
            raise ValueError(
                f"BrainSuite static S3 upload failed: HTTP {resp.status_code} — {resp.text[:300]}"
            )
        logger.info("BrainSuite static S3 upload complete (status=%s)", resp.status_code)

    async def _start_job(self, job_id: str) -> None:
        """POST /{jobId}/start — transitions job from Announced to Scheduled/Created.

        For the Static API, the start body is EMPTY ({}).
        Briefing data was already sent in the announce step (D-04).
        """
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/{job_id}/start"
        await self._api_post_with_retry(url, json_body={}, log_name="start")

    async def submit_job_with_upload(
        self, file_bytes: bytes, filename: str, announce_payload: dict
    ) -> str:
        """Run the full announce→upload→start flow and return the job_id.

        For the Static API:
          1. announce(payload with channel/legs/etc.) → job_id
          2. announce_asset(job_id, "leg1", filename) → upload URL + fields
          3. upload file to S3
          4. start(job_id, body={}) — start body is empty

        Args:
            file_bytes:       Raw image bytes.
            filename:         Original filename including extension (e.g. "image.jpg").
            announce_payload: Full payload for the announce step — {"input": {...}}.

        Returns:
            job_id string to pass to poll_job_status().
        """
        job_id = await self._announce_job(announce_payload)
        logger.info("BrainSuite static job announced: job_id=%s", job_id)

        asset_id = "leg1"
        upload_info = await self._announce_asset(job_id, asset_id, filename)
        upload_url = upload_info["uploadUrl"]
        s3_fields = upload_info.get("fields", {})

        await self._upload_to_brainsuite_s3(upload_url, s3_fields, file_bytes, filename)

        await self._start_job(job_id)
        logger.info(
            "BrainSuite static job started: job_id=%s channel=%s",
            job_id,
            announce_payload.get("input", {}).get("channel"),
        )

        return job_id

    # ------------------------------------------------------------------
    # Job polling — identical terminal statuses to video service
    # ------------------------------------------------------------------

    async def poll_job_status(
        self,
        job_id: str,
        max_polls: int = 60,
        poll_interval: int = 30,
    ) -> dict:
        """Poll the BrainSuite static job status endpoint until a terminal status.

        Terminal statuses:
            Succeeded — returns the full response JSON
            Failed / Stale — raises BrainSuiteJobError

        Raises:
            BrainSuiteJobError: if job fails, goes stale, or max_polls is exhausted.
        """
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/{job_id}"
        in_progress = {"Announced", "Scheduled", "Created", "Started"}

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
                "BrainSuite static job %s — status=%s (poll %d/%d)",
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
                    f"BrainSuite static job {job_id} ended with status={status}: {error_detail}"
                )

            if status in in_progress:
                await asyncio.sleep(poll_interval)
                continue

            # Unexpected status — treat as transient, keep polling
            logger.warning("BrainSuite static job %s — unexpected status=%s", job_id, status)
            await asyncio.sleep(poll_interval)

        raise BrainSuiteJobError(
            f"Static job polling timed out for job_id={job_id} after {max_polls} polls"
        )


# ---------------------------------------------------------------------------
# Module-level functions
# ---------------------------------------------------------------------------


def map_static_channel(platform: Optional[str], placement: Optional[str]) -> str:
    """Map platform + placement to a BrainSuite Static API channel identifier.

    For the Static API, only two channels are relevant:
      - "Instagram" — META assets with Instagram placement
      - "Facebook"  — META assets with any other placement, and all fallbacks

    Non-META platforms should not reach this function (they are routed to
    UNSUPPORTED at sync time), but a "Facebook" fallback is provided for safety.

    Args:
        platform:  Platform identifier (e.g. "META", "TIKTOK").
        placement: Ad placement string (e.g. "instagram_feed", "facebook_feed").

    Returns:
        "Instagram" or "Facebook".
    """
    platform_upper = (platform or "").upper()
    placement_lower = (placement or "").lower()

    if platform_upper == "META" and "instagram" in placement_lower:
        return "Instagram"

    # META non-Instagram, non-META platforms (fallback)
    return "Facebook"


def build_static_scoring_payload(
    asset_name: str,
    platform: str,
    placement: Optional[str],
    metadata: dict,
) -> dict:
    """Build the BrainSuite Static API announce payload for POST /announce.

    The Static API receives briefing data in the announce step (not start).
    Per D-05 and D-13: the announce payload contains no AOI or brand fields.

    Args:
        asset_name: Filename of the creative asset (e.g. "image.jpg").
        platform:   Ad platform identifier (e.g. "META").
        placement:  Ad placement string from the sync layer (may be None).
        metadata:   Dict of MetadataField name → value for this asset.

    Returns:
        Dict matching the BrainSuite Static API announce payload schema:
        {"input": {"channel": ..., "projectName": ..., "legs": [...], ...}}
    """
    channel = map_static_channel(platform, placement)

    raw_messages = metadata.get("brainsuite_intended_messages", "")
    intended_messages = [m.strip() for m in raw_messages.split("\n") if m.strip()]

    iconic_color_scheme = metadata.get("brainsuite_iconic_color_scheme", "manufactory")

    input_obj: dict = {
        "channel": channel,
        "projectName": metadata.get("brainsuite_project_name") or "Default Project",
        "assetLanguage": metadata.get("brainsuite_asset_language", "en-US"),
        "iconicColorScheme": iconic_color_scheme,
        "legs": [
            {
                "name": asset_name,
                "staticImage": {"assetId": "leg1", "name": asset_name},
            }
        ],
    }

    if intended_messages:
        input_obj["intendedMessages"] = intended_messages
        input_obj["intendedMessagesLanguage"] = metadata.get(
            "brainsuite_asset_language", "en-US"
        )

    return {"input": input_obj}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

brainsuite_static_score_service = BrainSuiteStaticScoreService()
