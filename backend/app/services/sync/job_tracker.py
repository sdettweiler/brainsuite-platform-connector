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

from app.db.base import get_session_factory
from app.models.jobs import BackgroundJob

logger = logging.getLogger(__name__)


async def create_background_job(
    job_type: str,
    org_id: uuid.UUID,
    platform_connection_id: Optional[uuid.UUID] = None,
    metadata: Optional[dict] = None,
) -> uuid.UUID:
    """Insert a new BackgroundJob row with status=PENDING and return its UUID.

    Commits before returning so the row is visible to any background task that
    uses the returned job_id (avoids the race described in RESEARCH.md Pitfall 1).

    Args:
        job_type: One of "sync_daily", "sync_full", "sync_initial",
                  "sync_historical", "download", "autofill", "scoring" (D-03, D-06, D-07).
        org_id: Organization UUID — sourced from connection.organization_id
                or asset.organization_id (D-02, D-07).
        platform_connection_id: Optional FK to platform_connections.id.
                                 NULL for autofill jobs (D-06).
        metadata: Optional dict stored in the metadata JSONB column.
                  Used to cross-reference SyncJob.id (D-12) or CreativeScoreResult.id (D-09).

    Returns:
        UUID of the newly created BackgroundJob row.
    """
    async with get_session_factory()() as db:
        job = BackgroundJob(
            job_type=job_type,
            org_id=org_id,
            platform_connection_id=platform_connection_id,
            status="PENDING",
            started_at=datetime.utcnow(),
            metadata_=metadata or {},
        )
        db.add(job)
        await db.flush()
        job_id = job.id
        await db.commit()
    return job_id


async def update_background_job(
    job_id: uuid.UUID,
    status: Optional[str] = None,
    progress_current: Optional[int] = None,
    progress_total: Optional[int] = None,
    output: Optional[dict] = None,
    error: Optional[dict] = None,
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
        if error is not None:
            job.error = error

        if status in ("COMPLETE", "FAILED"):
            job.ended_at = datetime.utcnow()

        db.add(job)
        await db.commit()
