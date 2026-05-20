"""Maintenance jobs for background task cleanup.

Contains scheduled jobs for cleaning up old records to prevent table bloat.
All functions are registered in startup_scheduler() in scheduler.py.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, update

from app.db.base import get_session_factory
from app.models.jobs import BackgroundJob

logger = logging.getLogger(__name__)


async def reset_stale_background_jobs() -> None:
    """Mark stale PENDING and RUNNING jobs for cleanup.

    PENDING autofill/scoring jobs older than 10 minutes are marked FAILED — they
    never reached RUNNING (Redis stall or process crash mid-flight).

    RUNNING download/sync_daily jobs older than 3 hours are marked INTERRUPTED so
    auto_resume_interrupted_jobs() can retry them. sync_full/historical/initial are
    excluded — they can legitimately run for many hours.

    Runs every 10 minutes via IntervalTrigger registered in startup_scheduler().
    """
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    async with get_session_factory()() as db:
        try:
            result = await db.execute(
                update(BackgroundJob)
                .where(
                    BackgroundJob.status == "PENDING",
                    BackgroundJob.job_type.in_(["autofill", "scoring"]),
                    BackgroundJob.started_at < cutoff,
                )
                .values(
                    status="FAILED",
                    error={"type": "StalePending", "message": "Job stuck at PENDING — likely orphaned by Redis stall or process restart", "traceback": ""},
                    ended_at=datetime.utcnow(),
                )
                .returning(BackgroundJob.id)
            )
            stale_ids = [row[0] for row in result.all()]
            await db.commit()
            if stale_ids:
                logger.warning("reset_stale_background_jobs: marked %d stale PENDING job(s) as FAILED: %s", len(stale_ids), stale_ids)
        except Exception as e:
            logger.error("reset_stale_background_jobs failed: %s: %s", type(e).__name__, e)
            await db.rollback()

    running_cutoff = datetime.utcnow() - timedelta(hours=3)
    async with get_session_factory()() as db:
        try:
            result_running = await db.execute(
                update(BackgroundJob)
                .where(
                    BackgroundJob.status == "RUNNING",
                    BackgroundJob.job_type.in_(["download", "sync_daily"]),
                    BackgroundJob.started_at < running_cutoff,
                )
                .values(
                    status="INTERRUPTED",
                    error={"type": "StaleRunning", "message": "Job stuck RUNNING >3h with no completion — interrupted for auto-resume", "traceback": ""},
                    ended_at=datetime.utcnow(),
                )
                .returning(BackgroundJob.id)
            )
            stale_running_ids = [row[0] for row in result_running.all()]
            await db.commit()
            if stale_running_ids:
                logger.warning("reset_stale_background_jobs: marked %d stale RUNNING job(s) as INTERRUPTED: %s", len(stale_running_ids), stale_running_ids)
        except Exception as e:
            logger.error("reset_stale_background_jobs (RUNNING cleanup) failed: %s: %s", type(e).__name__, e)
            await db.rollback()


async def cleanup_old_background_jobs() -> None:
    """Delete background job records older than 30 days.

    Runs nightly at 03:00 UTC via APScheduler CronTrigger.
    Registered in startup_scheduler() behind SCHEDULER_ENABLED guard.

    Note: platform_connection_id is nullable (NULL for autofill/scoring jobs);
    this does not affect deletion — all records older than 30 days are removed
    regardless of job_type or platform_connection_id.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    async with get_session_factory()() as db:
        try:
            result = await db.execute(
                delete(BackgroundJob).where(BackgroundJob.created_at < cutoff_date)
            )
            deleted_count = result.rowcount
            await db.commit()
            if deleted_count > 0:
                logger.info(
                    f"Cleaned up {deleted_count} background job records older than 30 days"
                )
            else:
                logger.debug("No background job records to clean up")
        except Exception as e:
            logger.error(
                f"Failed to clean up background jobs: {type(e).__name__}: {e}"
            )
            await db.rollback()
            raise
