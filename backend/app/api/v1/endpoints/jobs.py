"""SSE streaming endpoint for real-time BackgroundJob updates (Phase 18).

GET /api/v1/jobs/stream — streams job_update and ping events to connected
SuperAdmin browsers. Authentication via ?token=<access_jwt> query parameter
(D-04: EventSource cannot send custom headers).

Decision references: D-01 through D-10 in .planning/phases/18-sse-transport/18-CONTEXT.md

REST endpoints for job list, detail, and bulk delete are appended below (Phase 19).
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.v1.deps import get_current_superadmin, get_current_superadmin_sse, get_current_user
from app.core.redis import get_redis
from app.db.base import get_db, get_session_factory
from app.models.creative import CreativeAsset
from app.models.jobs import BackgroundJob
from app.models.platform import PlatformConnection
from app.models.user import Organization, User
from app.schemas.jobs import JobDetail, JobListItem
from app.services.sync.job_tracker import create_background_job

logger = logging.getLogger(__name__)

router = APIRouter()

_HEARTBEAT_INTERVAL_SECONDS = 30  # D-08
_PUBSUB_POLL_TIMEOUT_SECONDS = 5.0  # Short timeout so disconnect is detected promptly


def serialize_job_event(job: BackgroundJob, org_name: Optional[str] = None) -> str:
    """Serialize BackgroundJob to minimal D-06 SSE event payload.

    Includes ONLY: job_id, job_type, org_id, org_name, status, progress_current,
    progress_total, started_at, ended_at.

    Does NOT include output or error — those are fetched via REST in Phase 19.
    """
    payload = {
        "job_id": str(job.id),
        "job_type": job.job_type,
        "org_id": str(job.org_id),
        "org_name": org_name,
        "status": job.status,
        "progress_current": job.progress_current,
        "progress_total": job.progress_total,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "ended_at": job.ended_at.isoformat() if job.ended_at else None,
    }
    return json.dumps(payload)


async def sse_generator(request: Request, current_user: User):
    """Async generator yielding SSE-compatible event dicts.

    Flow:
      1. D-07: Query background_jobs started in last 24h; yield each as job_update.
      2. D-02/D-03: Open dedicated Redis pubsub connection; subscribe to sse:job_updates.
      3. Main loop:
         - D-09: Check request.is_disconnected(); break if True.
         - D-02: Poll pubsub.get_message(timeout=5); if message, fetch BackgroundJob + yield.
         - D-08: Yield ping event if >=30s since last ping.
         - D-09: Re-check disconnect after event send.
      4. D-03: Finally block — unsubscribe + close pubsub even on exception or disconnect.
    """
    pubsub = None
    try:
        # D-07: 24h burst on connect — JOIN with Organization to include org_name
        cutoff = datetime.utcnow() - timedelta(hours=24)
        async with get_session_factory()() as db:
            result = await db.execute(
                select(BackgroundJob, Organization.name.label("org_name"))
                .outerjoin(Organization, Organization.id == BackgroundJob.org_id)
                .where(BackgroundJob.started_at > cutoff)
                .order_by(BackgroundJob.started_at.desc())
            )
            recent_jobs = result.all()

        for job, org_name in recent_jobs:
            if await request.is_disconnected():
                return
            yield {
                "event": "job_update",
                "data": serialize_job_event(job, org_name),
                "id": str(job.id),
            }

        # D-02/D-03: Dedicated pubsub connection (do NOT reuse singleton for SUBSCRIBE)
        redis = get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe("sse:job_updates")

        last_ping_at = datetime.utcnow()

        while True:
            # D-09: Disconnect check before any blocking operation
            if await request.is_disconnected():
                break

            # D-02: Non-blocking poll; timeout lets us check disconnect/ping regularly
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=_PUBSUB_POLL_TIMEOUT_SECONDS,
            )

            if message and isinstance(message.get("data"), str):
                raw_job_id = message["data"]
                # Validate it looks like a UUID before querying DB (T-18-02-01)
                try:
                    job_uuid = uuid.UUID(raw_job_id)
                except ValueError:
                    logger.warning("SSE: received non-UUID pubsub message: %r", raw_job_id)
                else:
                    async with get_session_factory()() as db:
                        job = await db.get(BackgroundJob, job_uuid)
                        if job:
                            org = await db.get(Organization, job.org_id)
                            org_name = org.name if org else None
                    if job:
                        if await request.is_disconnected():
                            break
                        yield {
                            "event": "job_update",
                            "data": serialize_job_event(job, org_name),
                            "id": str(job.id),
                        }

            # D-08: Heartbeat every 30 seconds
            now = datetime.utcnow()
            if (now - last_ping_at).total_seconds() >= _HEARTBEAT_INTERVAL_SECONDS:
                if await request.is_disconnected():
                    break
                yield {
                    "event": "ping",
                    "data": json.dumps({"ts": now.isoformat()}),
                }
                last_ping_at = now

            # D-09: Final disconnect check after yielding
            if await request.is_disconnected():
                break

            # Avoid a busy-loop when get_message returns immediately with no message
            await asyncio.sleep(0.05)

    finally:
        # D-03: Always clean up pubsub connection, even on exception or abrupt disconnect
        if pubsub is not None:
            try:
                await pubsub.unsubscribe("sse:job_updates")
                await pubsub.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("SSE: error closing pubsub connection: %s", exc)


@router.get("/stream")
async def stream_jobs(
    request: Request,
    current_user: User = Depends(get_current_superadmin_sse),
):
    """Stream real-time job updates to connected SuperAdmin browsers.

    Authentication: ?token=<access_jwt> query parameter (D-04).
    Protocol: Server-Sent Events (text/event-stream).
    Events: job_update (D-06 payload) and ping (D-08 keepalive).
    Scope: Global firehose — all jobs, all orgs (D-05).
    """
    return EventSourceResponse(
        sse_generator(request, current_user),
        ping=15,
        headers={"Cache-Control": "no-cache"},
    )


# ---------------------------------------------------------------------------
# REST endpoints (Phase 19) — D-07 from 19-CONTEXT.md
# ---------------------------------------------------------------------------

@router.get("", response_model=List[JobListItem])
async def list_jobs(
    job_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
) -> List[JobListItem]:
    """List background jobs with org name (SuperAdmin only). Global scope — no org filter (D-05)."""
    q = (
        select(BackgroundJob, Organization.name.label("org_name"))
        .outerjoin(Organization, Organization.id == BackgroundJob.org_id)
        .order_by(BackgroundJob.started_at.desc())
    )
    if job_type is not None:
        q = q.where(BackgroundJob.job_type == job_type)
    if status is not None:
        q = q.where(BackgroundJob.status == status)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    rows = result.all()
    return [
        JobListItem(
            id=job.id,
            job_type=job.job_type,
            org_id=job.org_id,
            status=job.status,
            progress_current=job.progress_current,
            progress_total=job.progress_total,
            started_at=job.started_at,
            ended_at=job.ended_at,
            metadata_=job.metadata_,
            org_name=org_name,
        )
        for job, org_name in rows
    ]


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
) -> JobDetail:
    """Get full job detail with enriched org, connection, and asset info (SuperAdmin only)."""
    job = await db.get(BackgroundJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    org = await db.get(Organization, job.org_id)
    org_name = org.name if org else None

    connection_name: Optional[str] = None
    platform_ad_account_id: Optional[str] = None
    if job.platform_connection_id:
        conn = await db.get(PlatformConnection, job.platform_connection_id)
        if conn:
            connection_name = conn.ad_account_name
            platform_ad_account_id = conn.ad_account_id

    asset_name: Optional[str] = None
    asset_url: Optional[str] = None
    asset_format: Optional[str] = None
    thumbnail_url: Optional[str] = None
    asset_id_str = (job.metadata_ or {}).get("asset_id")
    if asset_id_str:
        try:
            asset = await db.get(CreativeAsset, uuid.UUID(asset_id_str))
            if asset:
                asset_name = asset.ad_name
                asset_url = asset.asset_url
                asset_format = asset.asset_format
                thumbnail_url = asset.thumbnail_url
        except (ValueError, AttributeError):
            pass

    # For download jobs: enrich output.downloaded with asset names.
    # asset_id in the list is an internal UUID for Google Ads, but a platform ad_id
    # string for Meta/TikTok — try both lookup paths.
    output = job.output
    if job.job_type == "download" and isinstance(output, dict):
        downloaded = output.get("downloaded") or []
        enriched = []
        for item in downloaded:
            aid_str = item.get("asset_id")
            name = None
            fmt = None
            if aid_str:
                a = None
                try:
                    a = await db.get(CreativeAsset, uuid.UUID(aid_str))
                except (ValueError, AttributeError):
                    pass
                if a is None:
                    res = await db.execute(
                        select(CreativeAsset).where(CreativeAsset.ad_id == aid_str).limit(1)
                    )
                    a = res.scalar_one_or_none()
                if a:
                    name = a.ad_name
                    fmt = a.asset_format
            enriched.append({**item, "asset_name": name, "asset_format": fmt})
        output = {**output, "downloaded": enriched}

    return JobDetail(
        id=job.id,
        job_type=job.job_type,
        org_id=job.org_id,
        status=job.status,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
        started_at=job.started_at,
        ended_at=job.ended_at,
        metadata_=job.metadata_,
        output=output,
        error=job.error,
        org_name=org_name,
        connection_name=connection_name,
        platform_ad_account_id=platform_ad_account_id,
        asset_name=asset_name,
        asset_url=asset_url,
        asset_format=asset_format,
        thumbnail_url=thumbnail_url,
    )


_PROTECTED_STATUSES = {"RUNNING", "PENDING"}


@router.delete("", status_code=204, response_class=Response)
async def delete_jobs(
    job_type: str = Query(...),
    status: str = Query(...),
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Bulk delete background jobs by type + status (SuperAdmin only). Returns 204."""
    if status in _PROTECTED_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot bulk-delete jobs with status '{status}'. Only COMPLETE, FAILED, INTERRUPTED, and PARTIAL are permitted.",
        )
    await db.execute(
        delete(BackgroundJob).where(
            BackgroundJob.job_type == job_type,
            BackgroundJob.status == status,
        )
    )
    await db.commit()
    return Response(status_code=204)


async def _dispatch_job_retry(
    job_type: str,
    params: dict,
    new_job_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
) -> None:
    """Dispatch a retry job. Each service wires up its job_type in Wave 2."""
    if job_type == "download":
        from app.services.sync.scheduler import trigger_download_retry
        await trigger_download_retry(params, new_job_id)
        return
    logger.warning(
        "Retry dispatch not yet wired for job_type=%s. Job %s created but not started.",
        job_type,
        new_job_id,
    )


@router.post("/{job_id}/retry", status_code=202)
async def retry_job(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new job using the params from a previous INTERRUPTED/FAILED/PARTIAL job."""
    result = await db.execute(
        select(BackgroundJob).where(BackgroundJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("INTERRUPTED", "FAILED", "PARTIAL"):
        raise HTTPException(
            status_code=400,
            detail="Only INTERRUPTED, FAILED, or PARTIAL jobs can be retried",
        )
    if not job.params:
        raise HTTPException(
            status_code=400,
            detail="Job has no stored params — cannot retry",
        )

    new_job_id = await create_background_job(
        org_id=job.org_id,
        job_type=job.job_type,
        platform_connection_id=job.platform_connection_id,
        params=job.params,
    )

    await _dispatch_job_retry(job.job_type, job.params, str(new_job_id), background_tasks, db)

    return {"job_id": str(new_job_id), "status": "queued"}
