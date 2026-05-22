"""Job tracker helpers for BackgroundJob instrumentation (Phase 17, D-16).

All four service types (sync, download, autofill, scoring) call these helpers
to create and update BackgroundJob rows without duplicating session lifecycle
or error-schema logic.

Session-per-operation pattern (D-14): each helper opens its own fresh DB
session, commits, and returns before any external HTTP call can occur.
"""
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm.attributes import flag_modified

from app.db.base import get_session_factory
from app.models.jobs import BackgroundJob
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


async def create_background_job(
    job_type: str,
    org_id: uuid.UUID,
    platform_connection_id: Optional[uuid.UUID] = None,
    metadata: Optional[dict] = None,
    params: Optional[dict] = None,
    initial_status: str = "PENDING",
    progress_total: Optional[int] = None,
) -> uuid.UUID:
    """Insert a new BackgroundJob row and return its UUID.

    Commits before returning so the row is visible to any background task that
    uses the returned job_id (avoids the race described in RESEARCH.md Pitfall 1).

    Pass initial_status="RUNNING" (and progress_total) for job types that start
    executing immediately (e.g. autofill) to skip the PENDING window and avoid
    orphaned PENDING records if the process dies between create and the first update.

    Args:
        job_type: One of "sync_daily", "sync_full", "sync_initial",
                  "sync_historical", "download", "autofill", "scoring" (D-03, D-06, D-07).
        org_id: Organization UUID — sourced from connection.organization_id
                or asset.organization_id (D-02, D-07).
        platform_connection_id: Optional FK to platform_connections.id.
                                 NULL for autofill jobs (D-06).
        metadata: Optional dict stored in the metadata JSONB column.
                  Used to cross-reference SyncJob.id (D-12) or CreativeScoreResult.id (D-09).
        initial_status: Initial status string, defaults to "PENDING".
        progress_total: Optional total units of work, set in the same write as status.

    Returns:
        UUID of the newly created BackgroundJob row.
    """
    async with get_session_factory()() as db:
        job = BackgroundJob(
            job_type=job_type,
            org_id=org_id,
            platform_connection_id=platform_connection_id,
            status=initial_status,
            started_at=datetime.utcnow(),
            metadata_=metadata or {},
            params=params,
            progress_total=progress_total,
        )
        db.add(job)
        await db.flush()
        job_id = job.id
        await db.commit()

    # D-01: Notify SSE subscribers of new job. Failures must not block job creation.
    try:
        import asyncio as _asyncio
        redis = get_redis()
        await _asyncio.wait_for(redis.publish("sse:job_updates", str(job_id)), timeout=2.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SSE publish failed for job %s: %s", job_id, exc)

    return job_id


async def get_job_status(job_id: uuid.UUID) -> Optional[str]:
    """Return the current status of a BackgroundJob, or None if not found."""
    async with get_session_factory()() as db:
        job = await db.get(BackgroundJob, job_id)
        return job.status if job else None


async def update_background_job(
    job_id: uuid.UUID,
    status: Optional[str] = None,
    progress_current: Optional[int] = None,
    progress_total: Optional[int] = None,
    output: Optional[dict] = None,
    error: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Update an existing BackgroundJob row.

    Automatically sets ended_at=datetime.utcnow() when status transitions
    to COMPLETE or FAILED (prevents NULL ended_at per RESEARCH.md Pitfall 3).

    Args:
        job_id: UUID returned by create_background_job().
        status: New status string. One of PENDING, RUNNING, COMPLETE, FAILED.
        progress_current: Current items processed (e.g. 7 out of 10 assets).
        progress_total: Total items in batch. Set on first RUNNING update (D-04, D-05, D-06).
        output: Job-type-specific output dict (D-08, D-10, D-11, D-12).
                Stored as JSONB; SQLAlchemy serialises the Python dict automatically.
        error: Error dict with keys "type", "message", "traceback" (D-13).
               Set only on FAILED status.
        metadata: Optional dict to MERGE into the existing metadata_ JSONB.
                  Uses dict spread so existing keys are preserved.
                  Example: {"brainsuite_job_id": "<str>"} adds one key without
                  touching asset_id or creative_score_result_id.
    """
    async with get_session_factory()() as db:
        job = await db.get(BackgroundJob, job_id)
        if job is None:
            logger.warning("update_background_job: BackgroundJob %s not found", job_id)
            return

        if status is not None:
            job.status = status
        if progress_current is not None:
            job.progress_current = progress_current
        if progress_total is not None:
            job.progress_total = progress_total
        if output is not None:
            job.output = output
            flag_modified(job, "output")
        if error is not None:
            job.error = error
            flag_modified(job, "error")
        if metadata is not None:
            job.metadata_ = {**(job.metadata_ or {}), **metadata}
            flag_modified(job, "metadata_")

        if status in ("COMPLETE", "FAILED", "INTERRUPTED", "PARTIAL", "RETRIED"):
            job.ended_at = datetime.utcnow()

        db.add(job)
        await db.commit()

    # D-01: Notify SSE subscribers of job update. Failures must not block update.
    try:
        import asyncio as _asyncio
        redis = get_redis()
        await _asyncio.wait_for(redis.publish("sse:job_updates", str(job_id)), timeout=2.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SSE publish failed for job %s: %s", job_id, exc)


async def revive_background_job(job_id: uuid.UUID) -> bool:
    """Atomically revive an INTERRUPTED job back to RUNNING.

    Clears error, ended_at, stale output and progress so the worker starts
    from a clean slate. Records the revival timestamp in metadata.

    Returns True if the job was claimed (was INTERRUPTED), False if another
    process already claimed it or the job was not found.
    """
    from sqlalchemy import update as _update, literal_column as _lc
    now = datetime.utcnow()

    async with get_session_factory()() as db:
        result = await db.execute(
            _update(BackgroundJob)
            .where(BackgroundJob.id == job_id, BackgroundJob.status == "INTERRUPTED")
            .values(
                status="RUNNING",
                error=None,
                ended_at=None,
                progress_current=0,
                output={},
                started_at=now,
                metadata_=_lc(
                    "metadata || jsonb_build_object('resumed_at', to_jsonb(now()::text))"
                ),
            )
            .returning(BackgroundJob.id)
        )
        row = result.fetchone()
        await db.commit()
        claimed = row is not None

    if not claimed:
        return False

    try:
        import asyncio as _asyncio
        redis = get_redis()
        await _asyncio.wait_for(redis.publish("sse:job_updates", str(job_id)), timeout=2.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SSE publish failed for job %s: %s", job_id, exc)

    return True


async def heartbeat_background_job(job_id: uuid.UUID) -> None:
    """Update last_heartbeat_at to prove the job is still alive.

    Called every 30s from long-running jobs. Swallows all exceptions so a
    transient DB hiccup never crashes the job that's heartbeating.
    """
    from sqlalchemy import update as _update
    try:
        async with get_session_factory()() as db:
            await db.execute(
                _update(BackgroundJob)
                .where(BackgroundJob.id == job_id)
                .values(last_heartbeat_at=datetime.utcnow())
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat failed for job %s: %s", job_id, exc)
