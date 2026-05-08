"""Maintenance jobs for background task cleanup.

Contains scheduled jobs for cleaning up old records to prevent table bloat.
All functions are registered in startup_scheduler() in scheduler.py.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete

from app.db.base import get_session_factory
from app.models.jobs import BackgroundJob

logger = logging.getLogger(__name__)


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
