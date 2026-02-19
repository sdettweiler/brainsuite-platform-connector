"""
APScheduler-based job scheduler.
Schedules daily data syncs at 00:10 in each ad account's local timezone.
"""
import logging
import asyncio
from datetime import date, timedelta, datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from app.db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_daily_sync(connection_id: str) -> None:
    """Execute daily sync for a single platform connection."""
    from sqlalchemy import select
    from app.models.platform import PlatformConnection
    from app.models.performance import SyncJob
    from app.services.sync.meta_sync import meta_sync
    from app.services.sync.tiktok_sync import tiktok_sync
    from app.services.sync.youtube_sync import youtube_sync
    from app.services.sync.harmonizer import harmonizer
    import uuid

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PlatformConnection).where(
                PlatformConnection.id == uuid.UUID(connection_id),
                PlatformConnection.is_active == True,
            )
        )
        connection = result.scalar_one_or_none()

        if not connection:
            logger.warning(f"Connection {connection_id} not found for daily sync")
            return

        # Create sync job record
        job = SyncJob(
            platform_connection_id=connection.id,
            job_type="DAILY",
            status="RUNNING",
            started_at=datetime.utcnow(),
            date_from=date.today() - timedelta(days=2),  # 2-day lookback for late data
            date_to=date.today() - timedelta(days=1),
        )
        db.add(job)
        await db.flush()
        job_id = str(job.id)

        try:
            date_from = date.today() - timedelta(days=2)
            date_to = date.today() - timedelta(days=1)

            if connection.platform == "META":
                result = await meta_sync.sync_date_range(db, connection, date_from, date_to, job_id)
            elif connection.platform == "TIKTOK":
                result = await tiktok_sync.sync_date_range(db, connection, date_from, date_to, job_id)
            elif connection.platform == "YOUTUBE":
                result = await youtube_sync.sync_date_range(db, connection, date_from, date_to, job_id)
            else:
                result = {"fetched": 0, "upserted": 0}

            # Harmonize new data
            harmonized = await harmonizer.harmonize_connection(db, connection, date_from, date_to)

            # Update connection last_synced
            connection.last_synced_at = datetime.utcnow()
            db.add(connection)

            job.status = "COMPLETED"
            job.completed_at = datetime.utcnow()
            job.records_fetched = result.get("fetched", 0)
            job.records_processed = harmonized
            db.add(job)

            await db.commit()
            logger.info(f"Daily sync completed for {connection.platform} {connection.ad_account_id}: {result}")

        except Exception as e:
            logger.error(f"Daily sync failed for connection {connection_id}: {e}")
            job.status = "FAILED"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.add(job)
            connection.sync_status = "ERROR"
            db.add(connection)
            await db.commit()


async def run_initial_sync(connection_id: str) -> None:
    """Fetch first 30 days immediately after account connect."""
    from sqlalchemy import select
    from app.models.platform import PlatformConnection
    from app.models.performance import SyncJob
    from app.services.sync.meta_sync import meta_sync
    from app.services.sync.tiktok_sync import tiktok_sync
    from app.services.sync.youtube_sync import youtube_sync
    from app.services.sync.harmonizer import harmonizer
    import uuid

    logger.info(f"=== Starting initial sync for connection {connection_id} ===")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PlatformConnection).where(PlatformConnection.id == uuid.UUID(connection_id))
        )
        connection = result.scalar_one_or_none()
        if not connection:
            logger.error(f"Connection {connection_id} not found")
            return

        logger.info(f"Connection found: platform={connection.platform}, account={connection.ad_account_id}, name={connection.ad_account_name}")

        job = SyncJob(
            platform_connection_id=connection.id,
            job_type="INITIAL_30D",
            status="RUNNING",
            started_at=datetime.utcnow(),
            date_from=date.today() - timedelta(days=30),
            date_to=date.today() - timedelta(days=1),
        )
        db.add(job)
        await db.flush()

        try:
            date_from = date.today() - timedelta(days=30)
            date_to = date.today() - timedelta(days=1)

            if connection.platform == "META":
                sync_result = await meta_sync.sync_date_range(db, connection, date_from, date_to, str(job.id))
            elif connection.platform == "TIKTOK":
                sync_result = await tiktok_sync.sync_date_range(db, connection, date_from, date_to, str(job.id))
            elif connection.platform == "YOUTUBE":
                sync_result = await youtube_sync.sync_date_range(db, connection, date_from, date_to, str(job.id))
            else:
                sync_result = {"fetched": 0}

            harmonized = await harmonizer.harmonize_connection(db, connection, date_from, date_to)

            connection.initial_sync_completed = True
            connection.last_synced_at = datetime.utcnow()
            db.add(connection)

            job.status = "COMPLETED"
            job.completed_at = datetime.utcnow()
            job.records_fetched = sync_result.get("fetched", 0)
            job.records_processed = harmonized
            db.add(job)

            await db.commit()

            # Kick off historical sync in background
            asyncio.create_task(run_historical_sync(connection_id))

        except Exception as e:
            logger.error(f"Initial sync failed for {connection_id}: {e}")
            job.status = "FAILED"
            job.error_message = str(e)
            db.add(job)
            await db.commit()


async def run_historical_sync(connection_id: str) -> None:
    """Fetch full historical data (lifetime) after initial sync."""
    from sqlalchemy import select
    from app.models.platform import PlatformConnection
    from app.models.performance import SyncJob
    from app.services.sync.meta_sync import meta_sync
    from app.services.sync.tiktok_sync import tiktok_sync
    from app.services.sync.youtube_sync import youtube_sync
    from app.services.sync.harmonizer import harmonizer
    import uuid

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PlatformConnection).where(PlatformConnection.id == uuid.UUID(connection_id))
        )
        connection = result.scalar_one_or_none()
        if not connection:
            return

        # Fetch 24 months historical (don't go beyond API limits)
        date_to = date.today() - timedelta(days=31)  # Avoid overlap with initial sync
        date_from = date_to - timedelta(days=720)    # ~24 months

        job = SyncJob(
            platform_connection_id=connection.id,
            job_type="HISTORICAL",
            status="RUNNING",
            started_at=datetime.utcnow(),
            date_from=date_from,
            date_to=date_to,
        )
        db.add(job)
        await db.flush()

        connection.historical_sync_started_at = datetime.utcnow()
        db.add(connection)
        await db.flush()

        try:
            if connection.platform == "META":
                sync_result = await meta_sync.sync_date_range(db, connection, date_from, date_to, str(job.id))
            elif connection.platform == "TIKTOK":
                sync_result = await tiktok_sync.sync_date_range(db, connection, date_from, date_to, str(job.id))
            elif connection.platform == "YOUTUBE":
                sync_result = await youtube_sync.sync_date_range(db, connection, date_from, date_to, str(job.id))
            else:
                sync_result = {"fetched": 0}

            harmonized = await harmonizer.harmonize_connection(db, connection, date_from, date_to)

            connection.historical_sync_completed = True
            db.add(connection)

            job.status = "COMPLETED"
            job.completed_at = datetime.utcnow()
            job.records_fetched = sync_result.get("fetched", 0)
            job.records_processed = harmonized
            db.add(job)

            await db.commit()

        except Exception as e:
            logger.error(f"Historical sync failed for {connection_id}: {e}")
            job.status = "FAILED"
            job.error_message = str(e)
            db.add(job)
            await db.commit()


def schedule_connection(connection_id: str, timezone: str = "UTC") -> None:
    """Register a daily 00:10 job for an ad account connection."""
    job_id = f"daily_sync_{connection_id}"

    # Remove existing job if any
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    try:
        tz = pytz.timezone(timezone)
    except Exception:
        tz = pytz.UTC

    scheduler.add_job(
        run_daily_sync,
        trigger=CronTrigger(hour=0, minute=10, timezone=tz),
        id=job_id,
        args=[connection_id],
        replace_existing=True,
        misfire_grace_time=3600,  # Allow 1h grace for missed fires
    )
    logger.info(f"Scheduled daily sync for connection {connection_id} at 00:10 {timezone}")


def remove_connection_schedule(connection_id: str) -> None:
    job_id = f"daily_sync_{connection_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


async def startup_scheduler(db_session=None) -> None:
    """Load all active connections and schedule their daily syncs.
    Also triggers initial sync for any connections that missed it."""
    from sqlalchemy import select
    from app.models.platform import PlatformConnection

    pending_initial = []

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PlatformConnection).where(PlatformConnection.is_active == True)
        )
        connections = result.scalars().all()

        for conn in connections:
            timezone = conn.timezone or "UTC"
            schedule_connection(str(conn.id), timezone)
            if not conn.initial_sync_completed:
                pending_initial.append(str(conn.id))

    scheduler.start()
    logger.info(f"Scheduler started with {len(connections)} active connections")

    if pending_initial:
        logger.info(f"Found {len(pending_initial)} connections needing initial sync, triggering now...")
        for conn_id in pending_initial:
            asyncio.create_task(run_initial_sync(conn_id))
