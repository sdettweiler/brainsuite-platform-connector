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

from app.db.base import get_session_factory

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


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
            logger.error(f"Daily sync fetch failed for connection {connection_id}: {e}")
            await db.rollback()
            job.status = "FAILED"
            job.error_message = str(e)[:4000]
            job.completed_at = datetime.utcnow()
            db.add(job)
            connection.sync_status = "ERROR"
            db.add(connection)
            await db.commit()
            return

        if not is_dv360:
            dv360_asset_queue = result.get("_asset_queue") if platform == "DV360" else None
            conn_id_for_assets = connection.id if dv360_asset_queue else None

            try:
                harmonized = await harmonizer.harmonize_connection(db, connection, date_from, date_to)

                connection.last_synced_at = datetime.utcnow()
                connection.sync_status = "ACTIVE"
                db.add(connection)

                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                job.records_processed = harmonized
                db.add(job)

                await db.commit()
                logger.info(f"Daily sync completed for {connection.platform} {connection.ad_account_id}: {result}")

            except Exception as e:
                logger.error(f"Daily sync harmonization failed for connection {connection_id}: {e}")
                await db.rollback()
                job.status = "FAILED"
                job.error_message = f"Harmonization: {str(e)[:3980]}"
                job.completed_at = datetime.utcnow()
                db.add(job)
                connection.sync_status = "ERROR"
                db.add(connection)
                await db.commit()

    if is_dv360 and dv360_info:
        try:
            logger.info(f"DV360 daily sync: polling reports with no DB session held")
            dv360_report_data = await dv360_sync.fetch_report_data(
                dv360_info["access_token"], dv360_info["connection_id"],
                dv360_info["refresh_token_encrypted"],
                dv360_info["advertiser_id"], date_from, date_to,
            )
        except Exception as e:
            logger.error(f"DV360 daily sync report fetch failed: {e}")
            async with get_session_factory()() as db:
                from sqlalchemy import select as sel
                from app.models.performance import SyncJob as SJ
                sj = (await db.execute(sel(SJ).where(SJ.id == uuid.UUID(dv360_info["job_id"])))).scalar_one_or_none()
                conn = (await db.execute(sel(PlatformConnection).where(PlatformConnection.id == dv360_info["connection_id"]))).scalar_one_or_none()
                if sj:
                    sj.status = "FAILED"
                    sj.error_message = str(e)[:4000]
                    sj.completed_at = datetime.utcnow()
                    db.add(sj)
                if conn:
                    conn.sync_status = "ERROR"
                    db.add(conn)
                await db.commit()
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
                return

            try:
                sync_result = await dv360_sync.store_report_data(db, conn, dv360_report_data, dv360_info["job_id"])
                sj.records_fetched = sync_result.get("fetched", 0)
                db.add(sj)
                await db.commit()
                logger.info(f"DV360 daily sync raw data committed: {sync_result}")
            except Exception as e:
                logger.error(f"DV360 daily sync upsert failed: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = str(e)[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                conn.sync_status = "ERROR"
                db.add(conn)
                await db.commit()
                return

            dv360_asset_queue = sync_result.get("_asset_queue")
            conn_id_for_assets = conn.id if dv360_asset_queue else None

            try:
                harmonized = await harmonizer.harmonize_connection(db, conn, date_from, date_to)
                conn.last_synced_at = datetime.utcnow()
                conn.sync_status = "ACTIVE"
                db.add(conn)
                sj.status = "COMPLETED"
                sj.completed_at = datetime.utcnow()
                sj.records_processed = harmonized
                db.add(sj)
                await db.commit()
                logger.info(f"DV360 daily sync completed: {sync_result}")
            except Exception as e:
                logger.error(f"DV360 daily sync harmonization failed: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"Harmonization: {str(e)[:3980]}"
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                conn.sync_status = "ERROR"
                db.add(conn)
                await db.commit()

    if dv360_asset_queue and conn_id_for_assets:
        await _run_dv360_asset_downloads(conn_id_for_assets, dv360_asset_queue)


async def _run_dv360_asset_downloads(connection_id, asset_queue: dict) -> None:
    from app.services.sync.dv360_sync import dv360_sync
    from sqlalchemy import select
    from app.models.platform import PlatformConnection
    import uuid
    try:
        async with get_session_factory()() as db:
            result = await db.execute(
                select(PlatformConnection).where(
                    PlatformConnection.id == (connection_id if isinstance(connection_id, uuid.UUID) else uuid.UUID(str(connection_id)))
                )
            )
            connection = result.scalar_one_or_none()
            if not connection:
                return
            await dv360_sync.download_assets_post_commit(db, connection, asset_queue)
    except Exception as e:
        logger.warning(f"DV360 asset download failed (non-fatal): {e}")


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
            logger.error(f"Full resync fetch failed for connection {connection_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await db.rollback()
            job.status = "FAILED"
            job.error_message = str(e)[:4000]
            job.completed_at = datetime.utcnow()
            db.add(job)
            connection.sync_status = "ERROR"
            db.add(connection)
            await db.commit()
            return

        if not is_dv360:
            dv360_asset_queue = sync_result.get("_asset_queue") if connection.platform == "DV360" else None
            conn_id_for_assets = connection.id if dv360_asset_queue else None

            try:
                harmonized = await harmonizer.harmonize_connection(db, connection, date_from, date_to)
                connection.last_synced_at = datetime.utcnow()
                connection.sync_status = "ACTIVE"
                db.add(connection)
                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                job.records_processed = harmonized
                db.add(job)
                await db.commit()
                logger.info(f"Full resync completed for {connection.platform} {connection.ad_account_id}: {sync_result}")
            except Exception as e:
                logger.error(f"Full resync harmonization failed for connection {connection_id}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await db.rollback()
                job.status = "FAILED"
                job.error_message = f"Harmonization: {str(e)[:3980]}"
                job.completed_at = datetime.utcnow()
                db.add(job)
                connection.sync_status = "ERROR"
                db.add(connection)
                await db.commit()

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
            logger.error(f"DV360 full resync report fetch failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            async with get_session_factory()() as db:
                sj = (await db.execute(select(SyncJob).where(SyncJob.id == uuid.UUID(dv360_info["job_id"])))).scalar_one_or_none()
                conn = (await db.execute(select(PlatformConnection).where(PlatformConnection.id == dv360_info["connection_id"]))).scalar_one_or_none()
                if sj:
                    sj.status = "FAILED"
                    sj.error_message = str(e)[:4000]
                    sj.completed_at = datetime.utcnow()
                    db.add(sj)
                if conn:
                    conn.sync_status = "ERROR"
                    db.add(conn)
                await db.commit()
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
                return

            try:
                sync_result = await dv360_sync.store_report_data(db, conn, dv360_report_data, dv360_info["job_id"])
                sj.records_fetched = sync_result.get("fetched", 0)
                db.add(sj)
                await db.commit()
                logger.info(f"DV360 full resync raw data committed: {sync_result}")
            except Exception as e:
                logger.error(f"DV360 full resync upsert failed: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = str(e)[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                conn.sync_status = "ERROR"
                db.add(conn)
                await db.commit()
                return

            dv360_asset_queue = sync_result.get("_asset_queue")
            conn_id_for_assets = conn.id if dv360_asset_queue else None

            try:
                harmonized = await harmonizer.harmonize_connection(db, conn, dv360_info["date_from"], dv360_info["date_to"])
                conn.last_synced_at = datetime.utcnow()
                conn.sync_status = "ACTIVE"
                db.add(conn)
                sj.status = "COMPLETED"
                sj.completed_at = datetime.utcnow()
                sj.records_processed = harmonized
                db.add(sj)
                await db.commit()
                logger.info(f"DV360 full resync completed: {sync_result}")
            except Exception as e:
                logger.error(f"DV360 full resync harmonization failed: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"Harmonization: {str(e)[:3980]}"
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                conn.sync_status = "ERROR"
                db.add(conn)
                await db.commit()

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
            logger.error(f"Initial sync fetch failed for {connection_id}: {e}")
            await db.rollback()
            job.status = "FAILED"
            job.error_message = str(e)[:4000]
            db.add(job)
            await db.commit()
            return

        if not is_dv360:
            dv360_asset_queue = sync_result.get("_asset_queue") if connection.platform == "DV360" else None
            conn_id_for_assets = connection.id if dv360_asset_queue else None

            try:
                harmonized = await harmonizer.harmonize_connection(db, connection, date_from, date_to)
                connection.initial_sync_completed = True
                connection.last_synced_at = datetime.utcnow()
                db.add(connection)
                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                job.records_processed = harmonized
                db.add(job)
                await db.commit()
                trigger_historical = True
            except Exception as e:
                logger.error(f"Initial sync harmonization failed for {connection_id}: {e}")
                await db.rollback()
                job.status = "FAILED"
                job.error_message = f"Harmonization: {str(e)[:3980]}"
                db.add(job)
                await db.commit()

    if is_dv360 and dv360_info:
        try:
            logger.info(f"DV360 initial sync: polling reports with no DB session held")
            dv360_report_data = await dv360_sync.fetch_report_data(
                dv360_info["access_token"], dv360_info["connection_id"],
                dv360_info["refresh_token_encrypted"],
                dv360_info["advertiser_id"], date_from, date_to,
            )
        except Exception as e:
            logger.error(f"DV360 initial sync report fetch failed: {e}")
            async with get_session_factory()() as db:
                sj = (await db.execute(select(SyncJob).where(SyncJob.id == uuid.UUID(dv360_info["job_id"])))).scalar_one_or_none()
                if sj:
                    sj.status = "FAILED"
                    sj.error_message = str(e)[:4000]
                    sj.completed_at = datetime.utcnow()
                    db.add(sj)
                await db.commit()
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
                return

            try:
                sync_result = await dv360_sync.store_report_data(db, conn, dv360_report_data, dv360_info["job_id"])
                sj.records_fetched = sync_result.get("fetched", 0)
                db.add(sj)
                await db.commit()
                logger.info(f"DV360 initial sync raw data committed: {sync_result}")
            except Exception as e:
                logger.error(f"DV360 initial sync upsert failed: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = str(e)[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await db.commit()
                return

            dv360_asset_queue = sync_result.get("_asset_queue")
            conn_id_for_assets = conn.id if dv360_asset_queue else None

            try:
                harmonized = await harmonizer.harmonize_connection(db, conn, date_from, date_to)
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
            except Exception as e:
                logger.error(f"DV360 initial sync harmonization failed: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"Harmonization: {str(e)[:3980]}"
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await db.commit()

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
            logger.error(f"Historical sync fetch failed for {connection_id}: {e}")
            await db.rollback()
            job.status = "FAILED"
            job.error_message = str(e)[:4000]
            db.add(job)
            await db.commit()
            return

        if not is_dv360:
            dv360_asset_queue = sync_result.get("_asset_queue") if connection.platform == "DV360" else None
            conn_id_for_assets = connection.id if dv360_asset_queue else None

            try:
                harmonized = await harmonizer.harmonize_connection(db, connection, date_from, date_to)
                connection.historical_sync_completed = True
                db.add(connection)
                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                job.records_processed = harmonized
                db.add(job)
                await db.commit()
            except Exception as e:
                logger.error(f"Historical sync harmonization failed for {connection_id}: {e}")
                await db.rollback()
                job.status = "FAILED"
                job.error_message = f"Harmonization: {str(e)[:3980]}"
                db.add(job)
                await db.commit()

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
            logger.error(f"DV360 historical sync report fetch failed: {e}")
            async with get_session_factory()() as db:
                sj = (await db.execute(select(SyncJob).where(SyncJob.id == uuid.UUID(dv360_info["job_id"])))).scalar_one_or_none()
                if sj:
                    sj.status = "FAILED"
                    sj.error_message = str(e)[:4000]
                    sj.completed_at = datetime.utcnow()
                    db.add(sj)
                await db.commit()
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
                return

            try:
                sync_result = await dv360_sync.store_report_data(db, conn, dv360_report_data, dv360_info["job_id"])
                sj.records_fetched = sync_result.get("fetched", 0)
                db.add(sj)
                await db.commit()
                logger.info(f"DV360 historical sync raw data committed: {sync_result}")
            except Exception as e:
                logger.error(f"DV360 historical sync upsert failed: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = str(e)[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await db.commit()
                return

            dv360_asset_queue = sync_result.get("_asset_queue")
            conn_id_for_assets = conn.id if dv360_asset_queue else None

            try:
                harmonized = await harmonizer.harmonize_connection(db, conn, dv360_info["date_from"], dv360_info["date_to"])
                conn.historical_sync_completed = True
                db.add(conn)
                sj.status = "COMPLETED"
                sj.completed_at = datetime.utcnow()
                sj.records_processed = harmonized
                db.add(sj)
                await db.commit()
            except Exception as e:
                logger.error(f"DV360 historical sync harmonization failed: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"Harmonization: {str(e)[:3980]}"
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await db.commit()

    if dv360_asset_queue and conn_id_for_assets:
        await _run_dv360_asset_downloads(conn_id_for_assets, dv360_asset_queue)


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

    scheduler.start()
    logger.info(f"Scheduler started with {len(connections)} active connections")

    if pending_initial:
        logger.info(f"Found {len(pending_initial)} connections needing initial sync, triggering now...")
        for conn_id in pending_initial:
            asyncio.create_task(run_initial_sync(conn_id))
