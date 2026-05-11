"""SSE streaming endpoint for real-time BackgroundJob updates (Phase 18).

GET /api/v1/jobs/stream — streams job_update and ping events to connected
SuperAdmin browsers. Authentication via ?token=<access_jwt> query parameter
(D-04: EventSource cannot send custom headers).

Decision references: D-01 through D-10 in .planning/phases/18-sse-transport/18-CONTEXT.md
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from app.api.v1.deps import get_current_superadmin_sse
from app.core.redis import get_redis
from app.db.base import get_session_factory
from app.models.jobs import BackgroundJob
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

_HEARTBEAT_INTERVAL_SECONDS = 30  # D-08
_PUBSUB_POLL_TIMEOUT_SECONDS = 5.0  # Short timeout so disconnect is detected promptly


def serialize_job_event(job: BackgroundJob) -> str:
    """Serialize BackgroundJob to minimal D-06 SSE event payload.

    Includes ONLY: job_id, job_type, org_id, status, progress_current,
    progress_total, started_at, ended_at.

    Does NOT include output or error — those are fetched via REST in Phase 19.
    """
    payload = {
        "job_id": str(job.id),
        "job_type": job.job_type,
        "org_id": str(job.org_id),
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
        # D-07: 24h burst on connect
        cutoff = datetime.utcnow() - timedelta(hours=24)
        async with get_session_factory()() as db:
            result = await db.execute(
                select(BackgroundJob)
                .where(BackgroundJob.started_at > cutoff)
                .order_by(BackgroundJob.started_at.desc())
            )
            recent_jobs = result.scalars().all()

        for job in recent_jobs:
            if await request.is_disconnected():
                return
            yield {
                "event": "job_update",
                "data": serialize_job_event(job),
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
                        if await request.is_disconnected():
                            break
                        yield {
                            "event": "job_update",
                            "data": serialize_job_event(job),
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
