"""
APScheduler-based job scheduler.
Schedules daily data syncs at 00:10 in each ad account's local timezone.
"""
import logging
import asyncio
import os
from datetime import date, timedelta, datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from app.db.base import get_session_factory

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

MAX_DEADLOCK_RETRIES = 3
DEADLOCK_BACKOFF_BASE = 2

# Redis key TTL for in-progress sync tracking: 1 hour safety net prevents zombie keys if process crashes
SYNC_IN_PROGRESS_TTL = 3600


async def _set_sync_in_progress(connection_id: str, label: str = "sync") -> None:
    """Mark a connection as actively syncing in Redis."""
    from app.core.redis import get_redis
    try:
        redis = get_redis()
        await redis.setex(f"sync:{connection_id}:in_progress", SYNC_IN_PROGRESS_TTL, label)
    except Exception as e:
        logger.warning(f"Failed to set sync-in-progress flag for {connection_id}: {e}")


async def _clear_sync_in_progress(connection_id: str) -> None:
    """Clear the syncing flag for a connection."""
    from app.core.redis import get_redis
    try:
        redis = get_redis()
        await redis.delete(f"sync:{connection_id}:in_progress")
    except Exception as e:
        logger.warning(f"Failed to clear sync-in-progress flag for {connection_id}: {e}")


async def _harmonize_with_deadlock_retry(harmonizer, db, connection, date_from, date_to):
    for attempt in range(1, MAX_DEADLOCK_RETRIES + 1):
        try:
            return await harmonizer.harmonize_connection(db, connection, date_from, date_to)
        except Exception as exc:
            exc_name = type(exc).__name__
            is_deadlock = "deadlock" in str(exc).lower() or "DeadlockDetected" in exc_name
            if not is_deadlock or attempt == MAX_DEADLOCK_RETRIES:
                raise
            wait = DEADLOCK_BACKOFF_BASE * attempt
            logger.warning(f"Deadlock detected during harmonization (attempt {attempt}/{MAX_DEADLOCK_RETRIES}), retrying in {wait}s: {exc_name}: {exc}")
            await db.rollback()
            await asyncio.sleep(wait)


async def run_daily_sync(connection_id: str) -> None:
    """Execute daily sync for a single platform connection."""
    from sqlalchemy import select
    from app.models.platform import PlatformConnection
    from app.models.performance import SyncJob
    from app.services.sync.meta_sync import meta_sync
    from app.services.sync.tiktok_sync import tiktok_sync
    from app.services.sync.google_ads_sync import google_ads_sync
    from app.services.sync.dv360_sync import dv360_sync
    from app.services.sync.harmonizer import harmonizer
    import uuid

    date_from = date.today() - timedelta(days=2)
    date_to = date.today() - timedelta(days=1)
    dv360_asset_queue = None
    conn_id_for_assets = None
    platform = None
    is_dv360 = False
    dv360_report_data = None
    dv360_info = None

    async with get_session_factory()() as db:
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

        await _set_sync_in_progress(connection_id, "daily")

        platform = connection.platform
        is_dv360 = platform == "DV360"

        job = SyncJob(
            platform_connection_id=connection.id,
            job_type="DAILY",
            status="RUNNING",
            started_at=datetime.utcnow(),
            date_from=date_from,
            date_to=date_to,
        )
        db.add(job)
        await db.flush()
        job_id = str(job.id)

        try:
            if is_dv360:
                from app.core.security import decrypt_token
                access_token = await dv360_sync._get_valid_token(db, connection)
                _dv360_pending = {
                    "access_token": access_token,
                    "connection_id": connection.id,
                    "refresh_token_encrypted": connection.refresh_token_encrypted,
                    "advertiser_id": connection.ad_account_id,
                    "job_id": job_id,
                }
                await db.commit()
                dv360_info = _dv360_pending
            elif connection.platform == "META":
                result = await meta_sync.sync_date_range(db, connection, date_from, date_to, job_id)
                job.records_fetched = result.get("fetched", 0)
                db.add(job)
                await db.commit()
                logger.info(f"Daily sync raw data committed for {connection.platform}: {result}")
            elif connection.platform == "TIKTOK":
                result = await tiktok_sync.sync_date_range(db, connection, date_from, date_to, job_id)
                job.records_fetched = result.get("fetched", 0)
                db.add(job)
                await db.commit()
                logger.info(f"Daily sync raw data committed for {connection.platform}: {result}")
            elif connection.platform == "GOOGLE_ADS":
                result = await google_ads_sync.sync_date_range(db, connection, date_from, date_to, job_id)
                job.records_fetched = result.get("fetched", 0)
                db.add(job)
                await db.commit()
                logger.info(f"Daily sync raw data committed for {connection.platform}: {result}")
            else:
                result = {"fetched": 0, "upserted": 0}
                await db.commit()

        except Exception as e:
            logger.error(f"Daily sync fetch failed for connection {connection_id}: {type(e).__name__}: {e}")
            await db.rollback()
            job.status = "FAILED"
            job.error_message = f"{type(e).__name__}: {e}"[:4000]
            job.completed_at = datetime.utcnow()
            db.add(job)
            connection.sync_status = "ERROR"
            db.add(connection)
            await db.commit()
            await _clear_sync_in_progress(connection_id)
            return

        if not is_dv360:
            dv360_asset_queue = result.get("_asset_queue") if platform == "DV360" else None
            conn_id_for_assets = connection.id if dv360_asset_queue else None

            try:
                harmonized = await _harmonize_with_deadlock_retry(harmonizer, db, connection, date_from, date_to)

                connection.last_synced_at = datetime.utcnow()
                connection.sync_status = "ACTIVE"
                db.add(connection)

                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                job.records_processed = harmonized
                db.add(job)

                await db.commit()
                logger.info(f"Daily sync completed for {connection.platform} {connection.ad_account_id}: {result}")
                await _clear_sync_in_progress(connection_id)

            except Exception as e:
                logger.error(f"Daily sync harmonization failed for connection {connection_id}: {type(e).__name__}: {e}")
                await db.rollback()
                job.status = "FAILED"
                job.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                job.completed_at = datetime.utcnow()
                db.add(job)
                connection.sync_status = "ERROR"
                db.add(connection)
                await db.commit()
                await _clear_sync_in_progress(connection_id)

    if is_dv360 and dv360_info:
        try:
            logger.info(f"DV360 daily sync: polling reports with no DB session held")
            dv360_report_data = await dv360_sync.fetch_report_data(
                dv360_info["access_token"], dv360_info["connection_id"],
                dv360_info["refresh_token_encrypted"],
                dv360_info["advertiser_id"], date_from, date_to,
            )
        except Exception as e:
            logger.error(f"DV360 daily sync report fetch failed: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            async with get_session_factory()() as db:
                from sqlalchemy import select as sel
                from app.models.performance import SyncJob as SJ
                sj = (await db.execute(sel(SJ).where(SJ.id == uuid.UUID(dv360_info["job_id"])))).scalar_one_or_none()
                conn = (await db.execute(sel(PlatformConnection).where(PlatformConnection.id == dv360_info["connection_id"]))).scalar_one_or_none()
                if sj:
                    sj.status = "FAILED"
                    sj.error_message = f"{type(e).__name__}: {e}"[:4000]
                    sj.completed_at = datetime.utcnow()
                    db.add(sj)
                if conn:
                    conn.sync_status = "ERROR"
                    db.add(conn)
                await db.commit()
            await _clear_sync_in_progress(connection_id)
            return

        async with get_session_factory()() as db:
            conn = (await db.execute(
                select(PlatformConnection).where(PlatformConnection.id == dv360_info["connection_id"])
            )).scalar_one_or_none()
            sj = (await db.execute(
                select(SyncJob).where(SyncJob.id == uuid.UUID(dv360_info["job_id"]))
            )).scalar_one_or_none()

            if not conn or not sj:
                logger.error(f"DV360 daily sync: connection or job disappeared")
                await _clear_sync_in_progress(connection_id)
                return

            try:
                sync_result = await dv360_sync.store_report_data(db, conn, dv360_report_data, dv360_info["job_id"])
                sj.records_fetched = sync_result.get("fetched", 0)
                db.add(sj)
                await db.commit()
                logger.info(f"DV360 daily sync raw data committed: {sync_result}")
            except Exception as e:
                logger.error(f"DV360 daily sync upsert failed: {type(e).__name__}: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"{type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                conn.sync_status = "ERROR"
                db.add(conn)
                await db.commit()
                await _clear_sync_in_progress(connection_id)
                return

            dv360_asset_queue = sync_result.get("_asset_queue")
            conn_id_for_assets = conn.id if dv360_asset_queue else None

            try:
                harmonized = await _harmonize_with_deadlock_retry(harmonizer, db, conn, date_from, date_to)
                conn.last_synced_at = datetime.utcnow()
                conn.sync_status = "ACTIVE"
                db.add(conn)
                sj.status = "COMPLETED"
                sj.completed_at = datetime.utcnow()
                sj.records_processed = harmonized
                db.add(sj)
                await db.commit()
                logger.info(f"DV360 daily sync completed: {sync_result}")
                await _clear_sync_in_progress(connection_id)
            except Exception as e:
                logger.error(f"DV360 daily sync harmonization failed: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                conn.sync_status = "ERROR"
                db.add(conn)
                await db.commit()
                await _clear_sync_in_progress(connection_id)

    if dv360_asset_queue and conn_id_for_assets:
        await _run_dv360_asset_downloads(conn_id_for_assets, dv360_asset_queue)


async def _run_dv360_asset_downloads(connection_id, asset_queue: dict) -> None:
    from app.services.sync.dv360_sync import dv360_sync
    from sqlalchemy import select
    from app.models.platform import PlatformConnection
    import uuid
    import traceback
    try:
        async with get_session_factory()() as db:
            result = await db.execute(
                select(PlatformConnection).where(
                    PlatformConnection.id == (connection_id if isinstance(connection_id, uuid.UUID) else uuid.UUID(str(connection_id)))
                )
            )
            connection = result.scalar_one_or_none()
            if not connection:
                logger.error("_run_dv360_asset_downloads: connection %s not found", connection_id)
                return
            logger.info("_run_dv360_asset_downloads: calling download_assets_post_commit for %s", connection_id)
            await dv360_sync.download_assets_post_commit(db, connection, asset_queue)
            logger.info("_run_dv360_asset_downloads: done for %s", connection_id)
    except Exception as e:
        logger.error("_run_dv360_asset_downloads: FAILED for %s: %s: %s\n%s", connection_id, type(e).__name__, e, traceback.format_exc())


async def run_full_resync(connection_id: str) -> None:
    """Full resync: re-fetch all historical data (24 months) with latest field mappings."""
    from sqlalchemy import select
    from app.models.platform import PlatformConnection
    from app.models.performance import SyncJob
    from app.services.sync.meta_sync import meta_sync
    from app.services.sync.tiktok_sync import tiktok_sync
    from app.services.sync.google_ads_sync import google_ads_sync
    from app.services.sync.dv360_sync import dv360_sync
    from app.services.sync.harmonizer import harmonizer
    import uuid

    logger.info(f"=== Starting full resync for connection {connection_id} ===")

    is_dv360 = False
    dv360_info = None
    dv360_asset_queue = None
    conn_id_for_assets = None

    async with get_session_factory()() as db:
        result = await db.execute(
            select(PlatformConnection).where(
                PlatformConnection.id == uuid.UUID(connection_id),
                PlatformConnection.is_active == True,
            )
        )
        connection = result.scalar_one_or_none()

        if not connection:
            logger.warning(f"Connection {connection_id} not found for full resync")
            return

        await _set_sync_in_progress(connection_id, "resync")

        is_dv360 = connection.platform == "DV360"
        if is_dv360:
            date_from = date.today() - timedelta(days=180)
        else:
            date_from = date.today() - timedelta(days=730)
        date_to = date.today() - timedelta(days=1)

        job = SyncJob(
            platform_connection_id=connection.id,
            job_type="FULL_RESYNC",
            status="RUNNING",
            started_at=datetime.utcnow(),
            date_from=date_from,
            date_to=date_to,
        )
        db.add(job)
        await db.flush()
        job_id = str(job.id)

        try:
            if is_dv360:
                access_token = await dv360_sync._get_valid_token(db, connection)
                _dv360_pending = {
                    "access_token": access_token,
                    "connection_id": connection.id,
                    "refresh_token_encrypted": connection.refresh_token_encrypted,
                    "advertiser_id": connection.ad_account_id,
                    "job_id": job_id,
                    "date_from": date_from,
                    "date_to": date_to,
                }
                await db.commit()
                dv360_info = _dv360_pending
            elif connection.platform == "META":
                sync_result = await meta_sync.sync_date_range(db, connection, date_from, date_to, job_id)
                job.records_fetched = sync_result.get("fetched", 0)
                db.add(job)
                await db.commit()
                logger.info(f"Full resync raw data committed for {connection.platform}: {sync_result}")
            elif connection.platform == "TIKTOK":
                sync_result = await tiktok_sync.sync_date_range(db, connection, date_from, date_to, job_id)
                job.records_fetched = sync_result.get("fetched", 0)
                db.add(job)
                await db.commit()
                logger.info(f"Full resync raw data committed for {connection.platform}: {sync_result}")
            elif connection.platform == "GOOGLE_ADS":
                sync_result = await google_ads_sync.sync_date_range(db, connection, date_from, date_to, job_id)
                job.records_fetched = sync_result.get("fetched", 0)
                db.add(job)
                await db.commit()
                logger.info(f"Full resync raw data committed for {connection.platform}: {sync_result}")
            else:
                sync_result = {"fetched": 0}
                await db.commit()

        except Exception as e:
            logger.error(f"Full resync fetch failed for connection {connection_id}: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await db.rollback()
            job.status = "FAILED"
            job.error_message = f"{type(e).__name__}: {e}"[:4000]
            job.completed_at = datetime.utcnow()
            db.add(job)
            connection.sync_status = "ERROR"
            db.add(connection)
            await db.commit()
            await _clear_sync_in_progress(connection_id)
            return

        if not is_dv360:
            dv360_asset_queue = sync_result.get("_asset_queue") if connection.platform == "DV360" else None
            conn_id_for_assets = connection.id if dv360_asset_queue else None

            try:
                harmonized = await _harmonize_with_deadlock_retry(harmonizer, db, connection, date_from, date_to)
                connection.last_synced_at = datetime.utcnow()
                connection.sync_status = "ACTIVE"
                db.add(connection)
                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                job.records_processed = harmonized
                db.add(job)
                await db.commit()
                logger.info(f"Full resync completed for {connection.platform} {connection.ad_account_id}: {sync_result}")
                await _clear_sync_in_progress(connection_id)
            except Exception as e:
                logger.error(f"Full resync harmonization failed for connection {connection_id}: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await db.rollback()
                job.status = "FAILED"
                job.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                job.completed_at = datetime.utcnow()
                db.add(job)
                connection.sync_status = "ERROR"
                db.add(connection)
                await db.commit()
                await _clear_sync_in_progress(connection_id)

    if is_dv360 and dv360_info:
        try:
            logger.info(f"DV360 full resync: polling reports with no DB session held")
            dv360_report_data = await dv360_sync.fetch_report_data(
                dv360_info["access_token"], dv360_info["connection_id"],
                dv360_info["refresh_token_encrypted"],
                dv360_info["advertiser_id"],
                dv360_info["date_from"], dv360_info["date_to"],
            )
        except Exception as e:
            logger.error(f"DV360 full resync report fetch failed: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            async with get_session_factory()() as db:
                sj = (await db.execute(select(SyncJob).where(SyncJob.id == uuid.UUID(dv360_info["job_id"])))).scalar_one_or_none()
                conn = (await db.execute(select(PlatformConnection).where(PlatformConnection.id == dv360_info["connection_id"]))).scalar_one_or_none()
                if sj:
                    sj.status = "FAILED"
                    sj.error_message = f"{type(e).__name__}: {e}"[:4000]
                    sj.completed_at = datetime.utcnow()
                    db.add(sj)
                if conn:
                    conn.sync_status = "ERROR"
                    db.add(conn)
                await db.commit()
            await _clear_sync_in_progress(connection_id)
            return

        async with get_session_factory()() as db:
            conn = (await db.execute(
                select(PlatformConnection).where(PlatformConnection.id == dv360_info["connection_id"])
            )).scalar_one_or_none()
            sj = (await db.execute(
                select(SyncJob).where(SyncJob.id == uuid.UUID(dv360_info["job_id"]))
            )).scalar_one_or_none()

            if not conn or not sj:
                logger.error(f"DV360 full resync: connection or job disappeared")
                await _clear_sync_in_progress(connection_id)
                return

            try:
                sync_result = await dv360_sync.store_report_data(db, conn, dv360_report_data, dv360_info["job_id"])
                sj.records_fetched = sync_result.get("fetched", 0)
                db.add(sj)
                await db.commit()
                logger.info(f"DV360 full resync raw data committed: {sync_result}")
            except Exception as e:
                logger.error(f"DV360 full resync upsert failed: {type(e).__name__}: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"{type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                conn.sync_status = "ERROR"
                db.add(conn)
                await db.commit()
                await _clear_sync_in_progress(connection_id)
                return

            dv360_asset_queue = sync_result.get("_asset_queue")
            conn_id_for_assets = conn.id if dv360_asset_queue else None

            try:
                harmonized = await _harmonize_with_deadlock_retry(harmonizer, db, conn, dv360_info["date_from"], dv360_info["date_to"])
                conn.last_synced_at = datetime.utcnow()
                conn.sync_status = "ACTIVE"
                db.add(conn)
                sj.status = "COMPLETED"
                sj.completed_at = datetime.utcnow()
                sj.records_processed = harmonized
                db.add(sj)
                await db.commit()
                logger.info(f"DV360 full resync completed: {sync_result}")
                await _clear_sync_in_progress(connection_id)
            except Exception as e:
                logger.error(f"DV360 full resync harmonization failed: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                conn.sync_status = "ERROR"
                db.add(conn)
                await db.commit()
                await _clear_sync_in_progress(connection_id)

    if dv360_asset_queue and conn_id_for_assets:
        await _run_dv360_asset_downloads(conn_id_for_assets, dv360_asset_queue)


async def run_initial_sync(connection_id: str) -> None:
    """Fetch first 30 days immediately after account connect."""
    from sqlalchemy import select
    from app.models.platform import PlatformConnection
    from app.models.performance import SyncJob
    from app.services.sync.meta_sync import meta_sync
    from app.services.sync.tiktok_sync import tiktok_sync
    from app.services.sync.google_ads_sync import google_ads_sync
    from app.services.sync.dv360_sync import dv360_sync
    from app.services.sync.harmonizer import harmonizer
    import uuid

    logger.info(f"=== Starting initial sync for connection {connection_id} ===")

    date_from = date.today() - timedelta(days=30)
    date_to = date.today() - timedelta(days=1)
    is_dv360 = False
    dv360_info = None
    dv360_asset_queue = None
    conn_id_for_assets = None
    trigger_historical = False

    async with get_session_factory()() as db:
        result = await db.execute(
            select(PlatformConnection).where(PlatformConnection.id == uuid.UUID(connection_id))
        )
        connection = result.scalar_one_or_none()
        if not connection:
            logger.error(f"Connection {connection_id} not found")
            return

        await _set_sync_in_progress(connection_id, "initial")

        logger.info(f"Connection found: platform={connection.platform}, account={connection.ad_account_id}, name={connection.ad_account_name}")
        is_dv360 = connection.platform == "DV360"

        job = SyncJob(
            platform_connection_id=connection.id,
            job_type="INITIAL_30D",
            status="RUNNING",
            started_at=datetime.utcnow(),
            date_from=date_from,
            date_to=date_to,
        )
        db.add(job)
        await db.flush()
        job_id = str(job.id)

        try:
            if is_dv360:
                access_token = await dv360_sync._get_valid_token(db, connection)
                _dv360_pending = {
                    "access_token": access_token,
                    "connection_id": connection.id,
                    "refresh_token_encrypted": connection.refresh_token_encrypted,
                    "advertiser_id": connection.ad_account_id,
                    "job_id": job_id,
                }
                await db.commit()
                dv360_info = _dv360_pending
            elif connection.platform == "META":
                sync_result = await meta_sync.sync_date_range(db, connection, date_from, date_to, job_id)
                job.records_fetched = sync_result.get("fetched", 0)
                db.add(job)
                await db.commit()
                logger.info(f"Initial sync raw data committed for {connection.platform}: {sync_result}")
            elif connection.platform == "TIKTOK":
                sync_result = await tiktok_sync.sync_date_range(db, connection, date_from, date_to, job_id)
                job.records_fetched = sync_result.get("fetched", 0)
                db.add(job)
                await db.commit()
                logger.info(f"Initial sync raw data committed for {connection.platform}: {sync_result}")
            elif connection.platform == "GOOGLE_ADS":
                sync_result = await google_ads_sync.sync_date_range(db, connection, date_from, date_to, job_id)
                job.records_fetched = sync_result.get("fetched", 0)
                db.add(job)
                await db.commit()
                logger.info(f"Initial sync raw data committed for {connection.platform}: {sync_result}")
            else:
                sync_result = {"fetched": 0}
                await db.commit()

        except Exception as e:
            logger.error(f"Initial sync fetch failed for {connection_id}: {type(e).__name__}: {e}")
            await db.rollback()
            job.status = "FAILED"
            job.error_message = f"{type(e).__name__}: {e}"[:4000]
            db.add(job)
            await db.commit()
            await _clear_sync_in_progress(connection_id)
            return

        if not is_dv360:
            dv360_asset_queue = sync_result.get("_asset_queue") if connection.platform == "DV360" else None
            conn_id_for_assets = connection.id if dv360_asset_queue else None

            try:
                harmonized = await _harmonize_with_deadlock_retry(harmonizer, db, connection, date_from, date_to)
                connection.initial_sync_completed = True
                connection.last_synced_at = datetime.utcnow()
                db.add(connection)
                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                job.records_processed = harmonized
                db.add(job)
                await db.commit()
                trigger_historical = True
                await _clear_sync_in_progress(connection_id)
            except Exception as e:
                logger.error(f"Initial sync harmonization failed for {connection_id}: {type(e).__name__}: {e}")
                await db.rollback()
                job.status = "FAILED"
                job.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                db.add(job)
                await db.commit()
                await _clear_sync_in_progress(connection_id)

    if is_dv360 and dv360_info:
        try:
            logger.info(f"DV360 initial sync: polling reports with no DB session held")
            dv360_report_data = await dv360_sync.fetch_report_data(
                dv360_info["access_token"], dv360_info["connection_id"],
                dv360_info["refresh_token_encrypted"],
                dv360_info["advertiser_id"], date_from, date_to,
            )
        except Exception as e:
            logger.error(f"DV360 initial sync report fetch failed: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            async with get_session_factory()() as db:
                sj = (await db.execute(select(SyncJob).where(SyncJob.id == uuid.UUID(dv360_info["job_id"])))).scalar_one_or_none()
                if sj:
                    sj.status = "FAILED"
                    sj.error_message = f"{type(e).__name__}: {e}"[:4000]
                    sj.completed_at = datetime.utcnow()
                    db.add(sj)
                await db.commit()
            await _clear_sync_in_progress(connection_id)
            return

        async with get_session_factory()() as db:
            conn = (await db.execute(
                select(PlatformConnection).where(PlatformConnection.id == dv360_info["connection_id"])
            )).scalar_one_or_none()
            sj = (await db.execute(
                select(SyncJob).where(SyncJob.id == uuid.UUID(dv360_info["job_id"]))
            )).scalar_one_or_none()

            if not conn or not sj:
                logger.error(f"DV360 initial sync: connection or job disappeared")
                await _clear_sync_in_progress(connection_id)
                return

            try:
                sync_result = await dv360_sync.store_report_data(db, conn, dv360_report_data, dv360_info["job_id"])
                sj.records_fetched = sync_result.get("fetched", 0)
                db.add(sj)
                await db.commit()
                logger.info(f"DV360 initial sync raw data committed: {sync_result}")
            except Exception as e:
                logger.error(f"DV360 initial sync upsert failed: {type(e).__name__}: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"{type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await db.commit()
                await _clear_sync_in_progress(connection_id)
                return

            dv360_asset_queue = sync_result.get("_asset_queue")
            conn_id_for_assets = conn.id if dv360_asset_queue else None

            try:
                harmonized = await _harmonize_with_deadlock_retry(harmonizer, db, conn, date_from, date_to)
                conn.initial_sync_completed = True
                conn.last_synced_at = datetime.utcnow()
                db.add(conn)
                sj.status = "COMPLETED"
                sj.completed_at = datetime.utcnow()
                sj.records_processed = harmonized
                db.add(sj)
                await db.commit()
                trigger_historical = True
                logger.info(f"DV360 initial sync completed: {sync_result}")
                await _clear_sync_in_progress(connection_id)
            except Exception as e:
                logger.error(f"DV360 initial sync harmonization failed: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await db.commit()
                await _clear_sync_in_progress(connection_id)

    if trigger_historical:
        asyncio.create_task(run_historical_sync(connection_id))

    if dv360_asset_queue and conn_id_for_assets:
        await _run_dv360_asset_downloads(conn_id_for_assets, dv360_asset_queue)


async def run_historical_sync(connection_id: str) -> None:
    """Fetch full historical data (lifetime) after initial sync."""
    from sqlalchemy import select
    from app.models.platform import PlatformConnection
    from app.models.performance import SyncJob
    from app.services.sync.meta_sync import meta_sync
    from app.services.sync.tiktok_sync import tiktok_sync
    from app.services.sync.google_ads_sync import google_ads_sync
    from app.services.sync.dv360_sync import dv360_sync
    from app.services.sync.harmonizer import harmonizer
    import uuid

    is_dv360 = False
    dv360_info = None
    dv360_asset_queue = None
    conn_id_for_assets = None

    async with get_session_factory()() as db:
        result = await db.execute(
            select(PlatformConnection).where(PlatformConnection.id == uuid.UUID(connection_id))
        )
        connection = result.scalar_one_or_none()
        if not connection:
            return

        await _set_sync_in_progress(connection_id, "historical")

        is_dv360 = connection.platform == "DV360"
        date_to = date.today() - timedelta(days=31)
        date_from = date_to - timedelta(days=720)

        if is_dv360:
            max_lookback = date.today() - timedelta(days=700)
            if date_from < max_lookback:
                date_from = max_lookback

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
        job_id = str(job.id)

        connection.historical_sync_started_at = datetime.utcnow()
        db.add(connection)
        await db.flush()

        try:
            if is_dv360:
                access_token = await dv360_sync._get_valid_token(db, connection)
                _dv360_pending = {
                    "access_token": access_token,
                    "connection_id": connection.id,
                    "refresh_token_encrypted": connection.refresh_token_encrypted,
                    "advertiser_id": connection.ad_account_id,
                    "job_id": job_id,
                    "date_from": date_from,
                    "date_to": date_to,
                }
                await db.commit()
                dv360_info = _dv360_pending
            elif connection.platform == "META":
                sync_result = await meta_sync.sync_date_range(db, connection, date_from, date_to, job_id)
                job.records_fetched = sync_result.get("fetched", 0)
                db.add(job)
                await db.commit()
                logger.info(f"Historical sync raw data committed for {connection.platform}: {sync_result}")
            elif connection.platform == "TIKTOK":
                sync_result = await tiktok_sync.sync_date_range(db, connection, date_from, date_to, job_id)
                job.records_fetched = sync_result.get("fetched", 0)
                db.add(job)
                await db.commit()
                logger.info(f"Historical sync raw data committed for {connection.platform}: {sync_result}")
            elif connection.platform == "GOOGLE_ADS":
                sync_result = await google_ads_sync.sync_date_range(db, connection, date_from, date_to, job_id)
                job.records_fetched = sync_result.get("fetched", 0)
                db.add(job)
                await db.commit()
                logger.info(f"Historical sync raw data committed for {connection.platform}: {sync_result}")
            else:
                sync_result = {"fetched": 0}
                await db.commit()

        except Exception as e:
            logger.error(f"Historical sync fetch failed for {connection_id}: {type(e).__name__}: {e}")
            await db.rollback()
            job.status = "FAILED"
            job.error_message = f"{type(e).__name__}: {e}"[:4000]
            db.add(job)
            await db.commit()
            await _clear_sync_in_progress(connection_id)
            return

        if not is_dv360:
            dv360_asset_queue = sync_result.get("_asset_queue") if connection.platform == "DV360" else None
            conn_id_for_assets = connection.id if dv360_asset_queue else None

            try:
                harmonized = await _harmonize_with_deadlock_retry(harmonizer, db, connection, date_from, date_to)
                connection.historical_sync_completed = True
                db.add(connection)
                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                job.records_processed = harmonized
                db.add(job)
                await db.commit()
                await _clear_sync_in_progress(connection_id)
            except Exception as e:
                logger.error(f"Historical sync harmonization failed for {connection_id}: {type(e).__name__}: {e}")
                await db.rollback()
                job.status = "FAILED"
                job.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                db.add(job)
                await db.commit()
                await _clear_sync_in_progress(connection_id)

    if is_dv360 and dv360_info:
        try:
            logger.info(f"DV360 historical sync: polling reports with no DB session held")
            dv360_report_data = await dv360_sync.fetch_report_data(
                dv360_info["access_token"], dv360_info["connection_id"],
                dv360_info["refresh_token_encrypted"],
                dv360_info["advertiser_id"],
                dv360_info["date_from"], dv360_info["date_to"],
            )
        except Exception as e:
            logger.error(f"DV360 historical sync report fetch failed: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            async with get_session_factory()() as db:
                sj = (await db.execute(select(SyncJob).where(SyncJob.id == uuid.UUID(dv360_info["job_id"])))).scalar_one_or_none()
                if sj:
                    sj.status = "FAILED"
                    sj.error_message = f"{type(e).__name__}: {e}"[:4000]
                    sj.completed_at = datetime.utcnow()
                    db.add(sj)
                await db.commit()
            await _clear_sync_in_progress(connection_id)
            return

        async with get_session_factory()() as db:
            conn = (await db.execute(
                select(PlatformConnection).where(PlatformConnection.id == dv360_info["connection_id"])
            )).scalar_one_or_none()
            sj = (await db.execute(
                select(SyncJob).where(SyncJob.id == uuid.UUID(dv360_info["job_id"]))
            )).scalar_one_or_none()

            if not conn or not sj:
                logger.error(f"DV360 historical sync: connection or job disappeared")
                await _clear_sync_in_progress(connection_id)
                return

            try:
                sync_result = await dv360_sync.store_report_data(db, conn, dv360_report_data, dv360_info["job_id"])
                sj.records_fetched = sync_result.get("fetched", 0)
                db.add(sj)
                await db.commit()
                logger.info(f"DV360 historical sync raw data committed: {sync_result}")
            except Exception as e:
                logger.error(f"DV360 historical sync upsert failed: {type(e).__name__}: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"{type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await db.commit()
                await _clear_sync_in_progress(connection_id)
                return

            dv360_asset_queue = sync_result.get("_asset_queue")
            conn_id_for_assets = conn.id if dv360_asset_queue else None

            try:
                harmonized = await _harmonize_with_deadlock_retry(harmonizer, db, conn, dv360_info["date_from"], dv360_info["date_to"])
                conn.historical_sync_completed = True
                db.add(conn)
                sj.status = "COMPLETED"
                sj.completed_at = datetime.utcnow()
                sj.records_processed = harmonized
                db.add(sj)
                await db.commit()
                await _clear_sync_in_progress(connection_id)
            except Exception as e:
                logger.error(f"DV360 historical sync harmonization failed: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await db.commit()
                await _clear_sync_in_progress(connection_id)

    if dv360_asset_queue and conn_id_for_assets:
        await _run_dv360_asset_downloads(conn_id_for_assets, dv360_asset_queue)


async def run_fetch_assets(connection_id: str) -> None:
    """Download missing video/thumbnail assets for an existing connection without re-syncing data."""
    from app.models.platform import PlatformConnection
    from app.services.sync.dv360_sync import dv360_sync
    from app.services.sync.google_ads_sync import google_ads_sync
    from sqlalchemy import select, text, update as sa_update, or_ as sa_or_
    import os
    import traceback

    import uuid

    logger.info("run_fetch_assets: START for connection %s", connection_id)
    await _set_sync_in_progress(connection_id, "fetch_assets")
    try:
        asset_info = None
        conn_platform = None

        async with get_session_factory()() as db:
            result = await db.execute(
                select(PlatformConnection).where(
                    PlatformConnection.id == uuid.UUID(connection_id),
                    PlatformConnection.is_active == True,
                )
            )
            conn = result.scalar_one_or_none()
            if not conn:
                logger.error("run_fetch_assets: connection %s not found or inactive", connection_id)
                await _clear_sync_in_progress(connection_id)
                return

            conn_platform = conn.platform
            org_id = str(conn.organization_id) if conn.organization_id else None
            if not org_id:
                logger.error("run_fetch_assets: connection %s has no organization_id", connection_id)
                await _clear_sync_in_progress(connection_id)
                return

            if conn.platform == "DV360":
                from app.models.performance import Dv360RawPerformance

                rows = (await db.execute(
                    select(
                        Dv360RawPerformance.youtube_ad_video_id,
                        Dv360RawPerformance.ad_id,
                        Dv360RawPerformance.thumbnail_url,
                    ).where(
                        Dv360RawPerformance.platform_connection_id == conn.id,
                        Dv360RawPerformance.youtube_ad_video_id.isnot(None),
                        Dv360RawPerformance.youtube_ad_video_id != "",
                        sa_or_(
                            Dv360RawPerformance.video_url.is_(None),
                            Dv360RawPerformance.video_url == "",
                        ),
                    ).distinct(Dv360RawPerformance.youtube_ad_video_id)
                )).all()

                logger.info("run_fetch_assets: DV360 — found %d rows with missing video_url for %s", len(rows), connection_id)
                if rows:
                    queue = {
                        r.youtube_ad_video_id: {
                            "youtube_video_id": r.youtube_ad_video_id,
                            "thumbnail_url": r.thumbnail_url or "",
                        }
                        for r in rows
                    }
                    org_dir = os.path.join(
                        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "creatives")),
                        org_id,
                    )
                    os.makedirs(org_dir, exist_ok=True)
                    asset_info = {"org_dir": org_dir, "org_id": org_id, "queue": queue}
                else:
                    logger.info("run_fetch_assets: nothing to download for %s — will still propagate existing raw URLs", connection_id)

            elif conn.platform == "GOOGLE_ADS":
                from app.models.performance import GoogleAdsRawPerformance

                rows = (await db.execute(
                    select(
                        GoogleAdsRawPerformance.video_id,
                        GoogleAdsRawPerformance.ad_id,
                    ).where(
                        GoogleAdsRawPerformance.platform_connection_id == conn.id,
                        GoogleAdsRawPerformance.video_id.isnot(None),
                        GoogleAdsRawPerformance.video_id != "",
                        GoogleAdsRawPerformance.video_url.like("https://www.youtube.com/watch%"),
                    ).distinct(GoogleAdsRawPerformance.video_id)
                )).all()

                logger.info("run_fetch_assets: Google Ads — found %d rows with fallback URL for %s", len(rows), connection_id)
                if not rows:
                    logger.info("run_fetch_assets: nothing to download for %s — will still propagate existing raw URLs", connection_id)
                else:
                    org_dir = os.path.join(
                        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "creatives")),
                        org_id,
                    )
                    os.makedirs(org_dir, exist_ok=True)

                    import asyncio
                    downloaded = 0
                    for i, row in enumerate(rows):
                        if i > 0:
                            await asyncio.sleep(4)
                        logger.info("run_fetch_assets: Google Ads downloading video %s (%d/%d)", row.video_id, i + 1, len(rows))
                        try:
                            _, thumb_url = await google_ads_sync._download_thumbnail(row.video_id, org_dir, org_id, row.ad_id)
                            _, video_url = await google_ads_sync._download_video(row.video_id, org_dir, org_id, row.ad_id)
                            logger.info("run_fetch_assets: Google Ads video %s result: video_url=%s thumb_url=%s", row.video_id, video_url, thumb_url)
                            if video_url and not video_url.startswith("https://www.youtube.com/watch"):
                                await db.execute(
                                    sa_update(GoogleAdsRawPerformance)
                                    .where(
                                        GoogleAdsRawPerformance.platform_connection_id == conn.id,
                                        GoogleAdsRawPerformance.video_id == row.video_id,
                                    )
                                    .values(
                                        video_url=video_url,
                                        **({"thumbnail_url": thumb_url} if thumb_url else {}),
                                    )
                                )
                                downloaded += 1
                        except Exception as e:
                            logger.error("run_fetch_assets: Google Ads video %s FAILED: %s: %s\n%s", row.video_id, type(e).__name__, e, traceback.format_exc())
                    await db.commit()
                    logger.info("run_fetch_assets: Google Ads DONE — %d/%d videos downloaded for %s", downloaded, len(rows), connection_id)
                # Propagate downloaded URLs into creative_assets so the dashboard reflects them
                await db.execute(
                    text("""
                        UPDATE creative_assets ca
                        SET
                            asset_url = gr.video_url,
                            thumbnail_url = COALESCE(
                                CASE WHEN gr.thumbnail_url NOT LIKE 'https://img.youtube.com%'
                                          AND gr.thumbnail_url NOT LIKE 'https://www.youtube.com%'
                                     THEN gr.thumbnail_url END,
                                ca.thumbnail_url
                            )
                        FROM (
                            SELECT DISTINCT ON (ad_id) ad_id, video_url, thumbnail_url
                            FROM google_ads_raw_performance
                            WHERE platform_connection_id = :conn_id
                              AND video_url IS NOT NULL
                              AND video_url NOT LIKE 'https://www.youtube.com/watch%'
                            ORDER BY ad_id, video_url
                        ) gr
                        WHERE ca.platform_connection_id = :conn_id
                          AND ca.ad_id = gr.ad_id
                    """),
                    {"conn_id": conn.id},
                )
                await db.commit()
                logger.info("run_fetch_assets: Google Ads — creative_assets propagated for %s", connection_id)
                await _clear_sync_in_progress(connection_id)
                return

            else:
                logger.error("run_fetch_assets: platform %s does not support asset fetch", conn.platform)
                await _clear_sync_in_progress(connection_id)
                return

        if conn_platform == "DV360":
            if asset_info:
                logger.info("run_fetch_assets: DV360 — starting download of %d videos", len(asset_info.get("queue", {})))
                await _run_dv360_asset_downloads(connection_id, asset_info)
                logger.info("run_fetch_assets: DV360 — download pass complete for %s", connection_id)
            # Propagate downloaded URLs into creative_assets so the dashboard reflects them
            async with get_session_factory()() as db:
                conn_uuid = uuid.UUID(connection_id) if isinstance(connection_id, str) else connection_id
                await db.execute(
                    text("""
                        UPDATE creative_assets ca
                        SET
                            asset_url = dr.asset_url,
                            thumbnail_url = COALESCE(
                                CASE WHEN dr.thumbnail_url NOT LIKE 'https://img.youtube.com%'
                                          AND dr.thumbnail_url NOT LIKE 'https://www.youtube.com%'
                                     THEN dr.thumbnail_url END,
                                ca.thumbnail_url
                            )
                        FROM (
                            SELECT DISTINCT ON (ad_id) ad_id, asset_url, thumbnail_url
                            FROM dv360_raw_performance
                            WHERE platform_connection_id = :conn_id
                              AND asset_url IS NOT NULL
                              AND asset_url NOT LIKE 'https://www.youtube.com%'
                            ORDER BY ad_id, asset_url
                        ) dr
                        WHERE ca.platform_connection_id = :conn_id
                          AND ca.ad_id = dr.ad_id
                    """),
                    {"conn_id": conn_uuid},
                )
                await db.commit()
                logger.info("run_fetch_assets: DV360 — creative_assets propagated for %s", connection_id)
        await _clear_sync_in_progress(connection_id)

    except Exception as e:
        logger.error("run_fetch_assets: UNHANDLED ERROR for connection %s: %s: %s\n%s", connection_id, type(e).__name__, e, traceback.format_exc())
        await _clear_sync_in_progress(connection_id)


def schedule_connection(connection_id: str, timezone: str = "UTC") -> None:
    """Register a daily 00:10 job for an ad account connection."""
    job_id = f"daily_sync_{connection_id}"

    # Remove existing job if any
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    try:
        tz = pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
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

    async with get_session_factory()() as db:
        result = await db.execute(
            select(PlatformConnection).where(PlatformConnection.is_active == True)
        )
        connections = result.scalars().all()

        for conn in connections:
            timezone = conn.timezone or "UTC"
            schedule_connection(str(conn.id), timezone)
            if not conn.initial_sync_completed:
                pending_initial.append(str(conn.id))

    from app.core.config import settings as _settings
    from app.services.sync.scoring_job import run_scoring_batch

    if _settings.SCHEDULER_ENABLED:
        scheduler.add_job(
            run_scoring_batch,
            trigger=IntervalTrigger(minutes=15),
            id="scoring_batch",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("Registered scoring_batch job (every 15 minutes)")
    else:
        logger.info("SCHEDULER_ENABLED=False — skipping scoring_batch registration")

    scheduler.start()
    logger.info(f"Scheduler started with {len(connections)} active connections")

    if pending_initial:
        logger.info(f"Found {len(pending_initial)} connections needing initial sync, triggering now...")
        for conn_id in pending_initial:
            asyncio.create_task(run_initial_sync(conn_id))
