"""BrainSuiteStaticScoreService — async httpx client for BrainSuite Static API scoring.

Handles OAuth 2.0 Client Credentials token management, the announce→upload→start
job flow for static images (no public URL required), job polling, channel mapping,
and payload construction.

Key differences from the video service (brainsuite_score.py):
  - Endpoint path: ACE_STATIC/{app_name} (not ACE_VIDEO/{app_name})
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

class BrainSuiteStaticScoreService:
    """Async client for the BrainSuite ACE_STATIC scoring pipeline (per-org credentials).

    Mirrors the structure of BrainSuiteScoreService (video) with differences for
    the Static API: briefing data travels in the announce payload, start body is empty.
    """

    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}           # org_id -> token
        self._token_expires: dict[str, datetime] = {}  # org_id -> expiry

    # ------------------------------------------------------------------
    # Auth — identical pattern to video service, per-org token caching
    # ------------------------------------------------------------------

    async def _get_token(self, org_id: str, client_id: str, client_secret: str) -> str:
        """Return a valid Bearer token for the given org, fetching a new one if necessary.

        Caches the token for 50 minutes per org to avoid unnecessary round-trips.
        On a 401 from any API call the caller should call _invalidate_token(org_id)
        and then call this method again to force a refresh.
        """
        now = datetime.now(timezone.utc)
        if (
            org_id in self._tokens
            and org_id in self._token_expires
            and now < self._token_expires[org_id]
        ):
            return self._tokens[org_id]

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

        self._tokens[org_id] = data["access_token"]
        self._token_expires[org_id] = now + timedelta(minutes=50)
        logger.info(
            "BrainSuite static token refreshed for org=%s, expires at %s",
            org_id,
            self._token_expires[org_id].isoformat(),
        )
        return self._tokens[org_id]

    def _invalidate_token(self, org_id: str) -> None:
        """Invalidate the cached token for the given org."""
        self._tokens.pop(org_id, None)
        self._token_expires.pop(org_id, None)

    # ------------------------------------------------------------------
    # Low-level API helper with retry — identical logic to video service
    # ------------------------------------------------------------------

    async def _api_post_with_retry(
        self,
        url: str,
        json_body: Optional[dict] = None,
        log_name: str = "",
        org_id: str = "",
        client_id: str = "",
        client_secret: str = "",
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
                token = await self._get_token(org_id, client_id, client_secret)
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
                    self._invalidate_token(org_id)
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

    async def _announce_job(
        self,
        announce_payload: dict,
        app_name: str,
        org_id: str = "",
        client_id: str = "",
        client_secret: str = "",
    ) -> str:
        """POST /announce — creates a new job in Announced state, returns job_id.

        For the Static API, the full briefing data (channel, legs[], etc.) is sent
        in the announce step — NOT in the start step (D-04).

        Args:
            announce_payload: Full payload dict with input{} containing channel,
                              projectName, assetLanguage, iconicColorScheme, legs[].
            app_name:         BrainSuite app name for this org (static endpoint).
            org_id:           Organization UUID string for per-org token caching.
            client_id:        BrainSuite client ID for this org.
            client_secret:    Decrypted BrainSuite client secret for this org.

        Returns:
            job_id string.
        """
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_STATIC/{app_name}/announce"
        import json as _json
        logger.info("BrainSuite static _announce_job payload: %s", _json.dumps(announce_payload)[:500])
        resp = await self._api_post_with_retry(
            url,
            json_body=announce_payload,
            log_name="announce",
            org_id=org_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        job_id = resp.get("id")
        if not job_id:
            raise ValueError(f"BrainSuite static announce response missing id: {resp}")
        return str(job_id)

    async def _announce_asset(
        self,
        job_id: str,
        asset_id: str,
        filename: str,
        app_name: str,
        org_id: str = "",
        client_id: str = "",
        client_secret: str = "",
    ) -> dict:
        """POST /{jobId}/assets — announces a single asset and returns uploadUrl + fields."""
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_STATIC/{app_name}/{job_id}/assets"
        resp = await self._api_post_with_retry(
            url,
            json_body={"assetId": asset_id, "name": filename},
            log_name="announce_asset",
            org_id=org_id,
            client_id=client_id,
            client_secret=client_secret,
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

    async def _start_job(
        self,
        job_id: str,
        announce_payload: dict,
        app_name: str,
        org_id: str = "",
        client_id: str = "",
        client_secret: str = "",
    ) -> None:
        """POST /{jobId}/start — transitions job from Announced to Scheduled/Created.

        Despite the API docs saying the start body is empty ({}), the staging API
        requires the same {"input": {...}} briefing payload that was sent in announce.
        """
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_STATIC/{app_name}/{job_id}/start"
        await self._api_post_with_retry(
            url,
            json_body=announce_payload,
            log_name="start",
            org_id=org_id,
            client_id=client_id,
            client_secret=client_secret,
        )

    async def submit_job_with_upload(
        self,
        file_bytes: bytes,
        filename: str,
        announce_payload: dict,
        org_id: str = "",
        client_id: str = "",
        client_secret: str = "",
        app_name: str = "",
    ) -> str:
        """Run the full announce→upload→start flow and return the job_id.

        For the Static API:
          1. announce(payload with channel/legs/etc.) → job_id
          2. announce_asset(job_id, "leg1", filename) → upload URL + fields
          3. upload file to S3
          4. start(job_id, announce_payload) — start requires the same input payload

        Args:
            file_bytes:       Raw image bytes.
            filename:         Original filename including extension (e.g. "image.jpg").
            announce_payload: Full payload for both announce and start steps — {"input": {...}}.
            org_id:           Organization UUID string for per-org token caching.
            client_id:        BrainSuite client ID for this org.
            client_secret:    Decrypted BrainSuite client secret for this org.
            app_name:         BrainSuite app name for this org (static endpoint).

        Returns:
            job_id string to pass to poll_job_status().
        """
        job_id = await self._announce_job(announce_payload, app_name, org_id=org_id, client_id=client_id, client_secret=client_secret)
        logger.info("BrainSuite static job announced: job_id=%s", job_id)

        asset_id = "leg1"
        upload_info = await self._announce_asset(job_id, asset_id, filename, app_name, org_id=org_id, client_id=client_id, client_secret=client_secret)
        upload_url = upload_info["uploadUrl"]
        s3_fields = upload_info.get("fields", {})

        await self._upload_to_brainsuite_s3(upload_url, s3_fields, file_bytes, filename)

        await self._start_job(job_id, announce_payload, app_name, org_id=org_id, client_id=client_id, client_secret=client_secret)
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
        org_id: str = "",
        client_id: str = "",
        client_secret: str = "",
        app_name: str = "",
    ) -> dict:
        """Poll the BrainSuite static job status endpoint until a terminal status.

        Terminal statuses:
            Succeeded — returns the full response JSON
            Failed / Stale — raises BrainSuiteJobError

        Raises:
            BrainSuiteJobError: if job fails, goes stale, or max_polls is exhausted.
        """
        url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_STATIC/{app_name}/{job_id}"
        in_progress = {"Announced", "Scheduled", "Created", "Started"}

        consecutive_401s = 0
        for poll_num in range(max_polls):
            token = await self._get_token(org_id, client_id, client_secret)
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                )

            if resp.status_code == 401:
                consecutive_401s += 1
                self._invalidate_token(org_id)
                if consecutive_401s >= 3:
                    raise BrainSuiteJobError(
                        f"BrainSuite static job {job_id}: persistent 401 after {consecutive_401s} attempts"
                        " — check org credentials (client_id / client_secret)"
                    )
                logger.warning(
                    "BrainSuite static job %s: 401 on poll %d/%d — invalidating token, retrying after sleep",
                    job_id, poll_num + 1, max_polls,
                )
                await asyncio.sleep(poll_interval)
                continue

            consecutive_401s = 0

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
