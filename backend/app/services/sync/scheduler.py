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
from app.services.ai_autofill import run_autofill_for_asset, backfill_failed_autofill_for_connection
from app.services.notifications import create_org_notification
from app.services.sync.backfill_job import run_duration_backfill, has_null_duration_assets
from app.services.sync.job_tracker import create_background_job, update_background_job

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Platform display names used in notification messages
PLATFORM_DISPLAY = {
    "meta": "Meta",
    "META": "Meta",
    "tiktok": "TikTok",
    "TIKTOK": "TikTok",
    "google_ads": "Google Ads",
    "GOOGLE_ADS": "Google Ads",
    "dv360": "DV360",
    "DV360": "DV360",
}

MAX_DEADLOCK_RETRIES = 3
DEADLOCK_BACKOFF_BASE = 2


async def _harmonize_with_deadlock_retry(harmonizer, db, connection, date_from, date_to):
    new_assets = []
    for attempt in range(1, MAX_DEADLOCK_RETRIES + 1):
        try:
            new_assets.clear()
            count = await harmonizer.harmonize_connection(db, connection, date_from, date_to, _new_asset_ids=new_assets)
            return count, new_assets
        except Exception as exc:
            exc_name = type(exc).__name__
            is_deadlock = "deadlock" in str(exc).lower() or "DeadlockDetected" in exc_name
            if not is_deadlock or attempt == MAX_DEADLOCK_RETRIES:
                raise
            wait = DEADLOCK_BACKOFF_BASE * attempt
            logger.warning(f"Deadlock detected during harmonization (attempt {attempt}/{MAX_DEADLOCK_RETRIES}), retrying in {wait}s: {exc_name}: {exc}")
            await db.rollback()
            await asyncio.sleep(wait)


async def _notify_connection_status(connection, new_status: str) -> None:
    """Emit a notification if the connection is transitioning INTO a new error status.

    Only fires when the connection's current sync_status differs from the target status.
    Per D-06: prevents duplicate notifications on repeated sync failures.
    """
    platform_name = PLATFORM_DISPLAY.get(connection.platform, str(connection.platform).title())
    org_id = str(connection.organization_id)
    conn_data = {"platform": connection.platform, "connection_id": str(connection.id)}

    if new_status == "ERROR" and connection.sync_status != "ERROR":
        asyncio.create_task(create_org_notification(
            org_id=org_id,
            type="SYNC_FAILED",
            title=f"{platform_name} Sync Failed",
            message=f"Sync failed for your {platform_name} account. Check your connection settings.",
            data=conn_data,
        ))
    elif new_status == "EXPIRED" and connection.sync_status != "EXPIRED":
        asyncio.create_task(create_org_notification(
            org_id=org_id,
            type="TOKEN_EXPIRED",
            title=f"{platform_name} Token Expired",
            message=f"Your {platform_name} access token has expired. Reconnect to resume syncing.",
            data=conn_data,
        ))


async def _supersede_running_jobs(connection_id: str) -> int:
    """Mark any RUNNING SyncJobs for this connection as FAILED (superseded). Returns count superseded."""
    from sqlalchemy import update
    from app.models.performance import SyncJob
    import uuid
    async with get_session_factory()() as db:
        result = await db.execute(
            update(SyncJob)
            .where(
                SyncJob.platform_connection_id == uuid.UUID(connection_id),
                SyncJob.status == "RUNNING",
            )
            .values(
                status="FAILED",
                error_message="Superseded by new sync",
                completed_at=datetime.utcnow(),
            )
            .returning(SyncJob.id)
        )
        rows = result.fetchall()
        count = len(rows)
        if count:
            await db.commit()
            logger.info(f"Superseded {count} running sync job(s) for connection {connection_id}")
        return count


async def run_daily_sync(connection_id: str) -> None:
    """Execute daily sync for a single platform connection."""
    from sqlalchemy import select
    from app.models.platform import PlatformConnection
    from app.models.performance import SyncJob
    from app.services.sync.meta_sync import meta_sync, MetaTokenError
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

    await _supersede_running_jobs(connection_id)

    # Phase 17: bg_job_id must be accessible to both the first-phase async-with
    # block and the DV360 second-phase blocks below (D-01, Python scoping).
    bg_job_id = None

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

        # Phase 17: Create BackgroundJob alongside SyncJob (D-01, D-03)
        bg_job_id = await create_background_job(
            job_type="sync_daily",
            org_id=connection.organization_id,
            platform_connection_id=connection.id,
            metadata={"sync_job_id": job_id, "platform": connection.platform},
            params={"platform": connection.platform, "platform_connection_id": str(connection.id), "date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "sync_type": "daily"},
        )
        await update_background_job(
            bg_job_id,
            status="RUNNING",
            progress_total=1,
            progress_current=0,
        )

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

        except MetaTokenError as e:
            logger.error(f"Daily sync token error for connection {connection_id}: {e}")
            try:
                await db.rollback()
            except Exception:
                pass
            async with get_session_factory()() as fresh_db:
                from sqlalchemy import update as _upd
                await fresh_db.execute(_upd(PlatformConnection).where(PlatformConnection.id == connection.id).values(sync_status="EXPIRED"))
                await fresh_db.execute(_upd(SyncJob).where(SyncJob.id == job.id).values(status="FAILED", error_message=f"TokenError: {e}"[:4000], completed_at=datetime.utcnow()))
                await fresh_db.commit()
            # Phase 17: Mark BackgroundJob FAILED (D-13)
            if bg_job_id is not None:
                import traceback as _tb
                await update_background_job(
                    bg_job_id,
                    status="FAILED",
                    progress_current=1,
                    error={"type": "MetaTokenError", "message": str(e), "traceback": _tb.format_exc()[:10000]},
                )
            await _notify_connection_status(connection, "EXPIRED")
            return
        except Exception as e:
            logger.error(f"Daily sync fetch failed for connection {connection_id}: {type(e).__name__}: {e}")
            try:
                await db.rollback()
            except Exception:
                pass
            from sqlalchemy import update as _upd
            async with get_session_factory()() as fresh_db:
                await fresh_db.execute(_upd(PlatformConnection).where(PlatformConnection.id == uuid.UUID(connection_id)).values(sync_status="ERROR"))
                await fresh_db.execute(_upd(SyncJob).where(SyncJob.id == uuid.UUID(job_id)).values(status="FAILED", error_message=f"{type(e).__name__}: {e}"[:4000], completed_at=datetime.utcnow()))
                await fresh_db.commit()
            # Phase 17: Mark BackgroundJob FAILED (D-13)
            if bg_job_id is not None:
                import traceback as _tb
                await update_background_job(
                    bg_job_id,
                    status="FAILED",
                    progress_current=1,
                    error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                )
            await _notify_connection_status(connection, "ERROR")
            return

        if not is_dv360:
            try:
                harmonized, new_assets = await _harmonize_with_deadlock_retry(harmonizer, db, connection, date_from, date_to)

                connection.last_synced_at = datetime.utcnow()
                connection.sync_status = "ACTIVE"
                db.add(connection)

                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                job.records_processed = harmonized
                db.add(job)

                await db.commit()
                # Phase 17: Mark BackgroundJob COMPLETE (D-12 output schema)
                if bg_job_id is not None:
                    await update_background_job(
                        bg_job_id,
                        status="COMPLETE",
                        progress_current=1,
                        output={
                            "platform": connection.platform.lower(),
                            "sync_job_id": job_id,
                            "records_fetched": job.records_fetched or 0,
                            "records_processed": harmonized,
                        },
                    )
                new_asset_ids = {aid for aid, _ in new_assets}
                for aid, oid in new_assets:
                    asyncio.create_task(run_autofill_for_asset(asset_id=aid, org_id=oid))
                asyncio.create_task(backfill_failed_autofill_for_connection(connection.id, connection.organization_id, new_asset_ids))
                # Phase 23 (D-09): trigger duration backfill if NULL-duration VIDEO assets exist
                try:
                    _null_count = await has_null_duration_assets(db, connection.organization_id)
                    if _null_count > 0:
                        logger.info("Triggering duration backfill for org %s (%d NULL-duration video assets)", connection.organization_id, _null_count)
                        asyncio.create_task(run_duration_backfill(connection.organization_id))
                except Exception as _e:
                    logger.warning("Failed to trigger duration backfill for connection %s: %s", connection.id, _e)
                if platform == "GOOGLE_ADS" and result.get("_asset_queue"):
                    asyncio.create_task(_run_google_ads_asset_downloads(connection.id, result["_asset_queue"]))
                elif platform == "META" and result.get("_creative_ad_ids"):
                    asyncio.create_task(_run_meta_creatives_deferred(connection.id, result["_creative_ad_ids"], org_id=connection.organization_id))
                elif platform == "TIKTOK" and result.get("_creative_ad_ids"):
                    asyncio.create_task(_run_tiktok_creatives_deferred(connection.id, result["_creative_ad_ids"], org_id=connection.organization_id))
                logger.info(f"Daily sync completed for {connection.platform} {connection.ad_account_id}: {result}")

            except Exception as e:
                logger.error(f"Daily sync harmonization failed for connection {connection_id}: {type(e).__name__}: {e}")
                await db.rollback()
                job.status = "FAILED"
                job.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                job.completed_at = datetime.utcnow()
                db.add(job)
                await _notify_connection_status(connection, "ERROR")
                connection.sync_status = "ERROR"
                db.add(connection)
                await db.commit()
                # Phase 17: Mark BackgroundJob FAILED (D-13)
                if bg_job_id is not None:
                    import traceback as _tb
                    await update_background_job(
                        bg_job_id,
                        status="FAILED",
                        progress_current=1,
                        error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                    )

    if is_dv360 and dv360_info:
        try:
            logger.info(f"DV360 daily sync: polling reports with no DB session held")
            dv360_report_data = await dv360_sync.fetch_report_data(
                dv360_info["access_token"], dv360_info["connection_id"],
                dv360_info["refresh_token_encrypted"],
                dv360_info["advertiser_id"], date_from, date_to,
                bg_job_id=bg_job_id,
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
                    await _notify_connection_status(conn, "ERROR")
                    conn.sync_status = "ERROR"
                    db.add(conn)
                await db.commit()
            # Phase 17: Mark BackgroundJob FAILED (D-13)
            if bg_job_id is not None:
                import traceback as _tb
                await update_background_job(
                    bg_job_id,
                    status="FAILED",
                    progress_current=1,
                    error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                )
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
                logger.error(f"DV360 daily sync upsert failed: {type(e).__name__}: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"{type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await _notify_connection_status(conn, "ERROR")
                conn.sync_status = "ERROR"
                db.add(conn)
                await db.commit()
                # Phase 17: Mark BackgroundJob FAILED (D-13)
                if bg_job_id is not None:
                    import traceback as _tb
                    await update_background_job(
                        bg_job_id,
                        status="FAILED",
                        progress_current=1,
                        error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                    )
                return

            dv360_asset_queue = sync_result.get("_asset_queue")
            conn_id_for_assets = conn.id if dv360_asset_queue else None

            try:
                harmonized, new_assets = await _harmonize_with_deadlock_retry(harmonizer, db, conn, date_from, date_to)
                conn.last_synced_at = datetime.utcnow()
                conn.sync_status = "ACTIVE"
                db.add(conn)
                sj.status = "COMPLETED"
                sj.completed_at = datetime.utcnow()
                sj.records_processed = harmonized
                db.add(sj)
                await db.commit()
                # Phase 17: Mark BackgroundJob COMPLETE (D-12 output schema)
                if bg_job_id is not None:
                    await update_background_job(
                        bg_job_id,
                        status="COMPLETE",
                        progress_current=1,
                        output={
                            "platform": conn.platform.lower(),
                            "sync_job_id": dv360_info["job_id"],
                            "records_fetched": sj.records_fetched or 0,
                            "records_processed": harmonized,
                        },
                    )
                new_asset_ids = {aid for aid, _ in new_assets}
                for aid, oid in new_assets:
                    asyncio.create_task(run_autofill_for_asset(asset_id=aid, org_id=oid))
                asyncio.create_task(backfill_failed_autofill_for_connection(conn.id, conn.organization_id, new_asset_ids))
                # Phase 23 (D-09): trigger duration backfill if NULL-duration VIDEO assets exist
                try:
                    _null_count = await has_null_duration_assets(db, conn.organization_id)
                    if _null_count > 0:
                        logger.info("Triggering duration backfill for org %s (%d NULL-duration video assets)", conn.organization_id, _null_count)
                        asyncio.create_task(run_duration_backfill(conn.organization_id))
                except Exception as _e:
                    logger.warning("Failed to trigger duration backfill for connection %s: %s", conn.id, _e)
                logger.info(f"DV360 daily sync completed: {sync_result}")
            except Exception as e:
                logger.error(f"DV360 daily sync harmonization failed: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await _notify_connection_status(conn, "ERROR")
                conn.sync_status = "ERROR"
                db.add(conn)
                await db.commit()
                # Phase 17: Mark BackgroundJob FAILED (D-13)
                if bg_job_id is not None:
                    import traceback as _tb
                    await update_background_job(
                        bg_job_id,
                        status="FAILED",
                        progress_current=1,
                        error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                    )

    if dv360_asset_queue and conn_id_for_assets:
        await _run_dv360_asset_downloads(conn_id_for_assets, dv360_asset_queue)


async def _run_google_ads_asset_downloads(connection_id, asset_queue: dict) -> None:
    from app.services.sync.google_ads_sync import google_ads_sync
    from app.services.sync.dv360_sync import _CookiesExpiredError
    from sqlalchemy import select, update as _upd
    from app.models.platform import PlatformConnection
    from app.models.system_config import SystemConfig
    import uuid
    import traceback as _tb

    connection = None
    bg_job_id = None

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

        # Phase 17: Create BackgroundJob before downloads begin (D-05)
        bg_job_id = await create_background_job(
            job_type="download",
            org_id=connection.organization_id,
            platform_connection_id=connection.id,
            metadata={"platform": "google_ads", "asset_count": len(asset_queue)},
            params={
                "asset_ids": [str(aid) for aid in asset_queue.keys()],
                "platform": "GOOGLE_ADS",
                "platform_connection_id": str(connection.id),
            },
            initial_status="RUNNING",
            progress_total=len(asset_queue),
        )

        # Resume support: find assets already downloaded so we can skip them
        from sqlalchemy import select as _sel
        from app.models.performance import GoogleAdsRawPerformance
        asset_id_strs = [str(aid) for aid in asset_queue.keys()]
        async with get_session_factory()() as _skip_db:
            _already_done = await _skip_db.execute(
                _sel(GoogleAdsRawPerformance.ad_id).where(
                    GoogleAdsRawPerformance.ad_id.in_(asset_id_strs),
                    GoogleAdsRawPerformance.video_url.isnot(None),
                    GoogleAdsRawPerformance.video_url != "",
                )
            )
            already_downloaded = {row[0] for row in _already_done.fetchall()}

        # Phase 17: Process assets one at a time; increment progress after each success (D-05, D-15)
        downloaded = []
        failed = []
        cookie_expired_count = 0
        for asset_id, asset_info in asset_queue.items():
            # Skip if already downloaded (resume support)
            if str(asset_id) in already_downloaded:
                downloaded.append({"asset_id": str(asset_id), "url": "(already downloaded)"})
                continue
            single_queue = {asset_id: asset_info}
            try:
                async with get_session_factory()() as db:
                    result = await google_ads_sync.download_assets_post_commit(db, connection, single_queue)
                video_url = (result or {}).get("video_url") or ""
                if video_url or not (result or {}).get("video_failures"):
                    downloaded.append({"asset_id": str(asset_id), "url": video_url})
                else:
                    fail_msg = next(iter((result or {}).get("video_failures", {}).values()), "silent failure")
                    failed.append({"asset_id": str(asset_id), "error": fail_msg})
            except _CookiesExpiredError:
                cookie_expired_count += 1
                failed.append({"asset_id": str(asset_id), "error": "YouTube cookies expired"})
            except Exception as asset_err:
                failed.append({"asset_id": str(asset_id), "error": str(asset_err)})
            # Progress tracks confirmed successes only, not total attempts
            await update_background_job(bg_job_id, status="RUNNING", progress_current=len(downloaded))

        # Only declare global cookie expiry when every single failure was a cookie error
        # and nothing succeeded. Mixed failures (some cookie, some non-cookie) mean the
        # issue is per-video access restrictions, not expired credentials.
        if cookie_expired_count > 0 and len(downloaded) == 0 and len(failed) == cookie_expired_count:
            raise _CookiesExpiredError("All Google Ads video downloads failed with cookie errors")

        # Phase 17: Mark COMPLETE/PARTIAL with D-11 output manifest
        final_status = "COMPLETE" if not failed else ("PARTIAL" if downloaded else "FAILED")
        output = {"downloaded": downloaded, "failed": failed}
        await update_background_job(
            bg_job_id,
            status=final_status,
            progress_current=len(asset_queue),
            output=output,
        )

    except _CookiesExpiredError:
        async with get_session_factory()() as fresh_db:
            _sc_row = (await fresh_db.execute(select(SystemConfig).limit(1))).scalar_one_or_none()
            _ts_still_valid = False
            if _sc_row and _sc_row.youtube_cookies_encrypted:
                try:
                    from app.core.security import decrypt_token as _dt_sec
                    from datetime import datetime as _dt_now
                    _raw = _dt_sec(_sc_row.youtube_cookies_encrypted)
                    _now = _dt_now.now().timestamp()
                    _ts_still_valid = any(
                        int(p[4]) > _now
                        for ln in _raw.splitlines()
                        if not ln.strip().startswith("#") and len(p := ln.strip().split("\t")) >= 7
                        and p[4].isdigit() and int(p[4]) > 0
                    )
                except Exception:
                    pass
            if _ts_still_valid:
                logger.warning("Google Ads asset download: yt-dlp reported cookies invalid but timestamps are still valid — likely IP/rate-limiting, not true expiry. Skipping flag write.")
            else:
                await fresh_db.execute(_upd(SystemConfig).values(youtube_cookies_runtime_expired=True))
                await fresh_db.commit()
        logger.warning("Google Ads asset download aborted: YouTube cookies expired — flag written to DB")
        if bg_job_id is not None:
            await update_background_job(
                bg_job_id,
                status="FAILED",
                error={
                    "type": "_CookiesExpiredError",
                    "message": "YouTube cookies expired",
                    "traceback": "",
                },
                output={
                    "downloaded": [],
                    "failed": [{"asset_id": str(aid), "error": "YouTube cookies expired"} for aid in asset_queue.keys()],
                },
            )
    except Exception as e:
        logger.warning(f"Google Ads asset download failed (non-fatal): {e}")
        if bg_job_id is not None:
            await update_background_job(
                bg_job_id,
                status="FAILED",
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": _tb.format_exc()[:10000],
                },
                output={
                    "downloaded": [],
                    "failed": [{"asset_id": str(aid), "error": str(e)} for aid in asset_queue.keys()],
                },
            )


async def _run_meta_creatives_deferred(connection_id, ad_ids: list, org_id=None) -> None:
    from app.services.sync.meta_sync import meta_sync
    from app.models.system_config import SystemConfig
    from sqlalchemy import select
    import uuid
    import traceback as _tb

    bg_job_id = None

    try:
        conn_uuid = connection_id if isinstance(connection_id, uuid.UUID) else uuid.UUID(str(connection_id))
        org_uuid = org_id if isinstance(org_id, uuid.UUID) else uuid.UUID(str(org_id)) if org_id else None

        # Phase 17: Create BackgroundJob before creative fetch begins (D-05)
        bg_job_id = await create_background_job(
            job_type="download",
            org_id=org_uuid,
            platform_connection_id=conn_uuid,
            metadata={"platform": "meta", "asset_count": len(ad_ids)},
            params={
                "asset_ids": [str(aid) for aid in ad_ids],
                "platform": "META",
                "platform_connection_id": str(conn_uuid),
            },
            initial_status="RUNNING",
            progress_total=len(ad_ids),
        )

        # Phase 17: Process ad_ids one at a time; increment progress after each success (D-05, D-15)
        downloaded = []
        failed = []
        for ad_id in ad_ids:
            try:
                await meta_sync.fetch_and_store_creatives_deferred(connection_id, [ad_id])
                downloaded.append({"asset_id": str(ad_id), "url": ""})
            except Exception as asset_err:
                failed.append({"asset_id": str(ad_id), "error": str(asset_err)})
            # Progress tracks confirmed successes only, not total attempts
            await update_background_job(bg_job_id, status="RUNNING", progress_current=len(downloaded))

        # Phase 17: Mark COMPLETE/PARTIAL with D-11 output manifest
        final_status = "COMPLETE" if not failed else ("PARTIAL" if downloaded else "FAILED")
        output = {"downloaded": downloaded, "failed": failed}
        await update_background_job(
            bg_job_id,
            status=final_status,
            progress_current=len(ad_ids),
            output=output,
        )

    except Exception as e:
        logger.warning(f"Meta creatives deferred fetch failed (non-fatal): {e}")
        if bg_job_id is not None:
            await update_background_job(
                bg_job_id,
                status="FAILED",
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": _tb.format_exc()[:10000],
                },
                output={
                    "downloaded": [],
                    "failed": [{"asset_id": str(aid), "error": str(e)} for aid in ad_ids],
                },
            )


async def _run_tiktok_creatives_deferred(connection_id, ad_ids: list, org_id=None) -> None:
    from app.services.sync.tiktok_sync import tiktok_sync
    from app.models.system_config import SystemConfig
    from sqlalchemy import select
    import uuid
    import traceback as _tb

    bg_job_id = None

    try:
        conn_uuid = connection_id if isinstance(connection_id, uuid.UUID) else uuid.UUID(str(connection_id))
        org_uuid = org_id if isinstance(org_id, uuid.UUID) else uuid.UUID(str(org_id)) if org_id else None

        # Phase 17: Create BackgroundJob before creative fetch begins (D-05)
        bg_job_id = await create_background_job(
            job_type="download",
            org_id=org_uuid,
            platform_connection_id=conn_uuid,
            metadata={"platform": "tiktok", "asset_count": len(ad_ids)},
            params={
                "asset_ids": [str(aid) for aid in ad_ids],
                "platform": "TIKTOK",
                "platform_connection_id": str(conn_uuid),
            },
            initial_status="RUNNING",
            progress_total=len(ad_ids),
        )

        # Phase 17: Process ad_ids one at a time; increment progress after each success (D-05, D-15)
        downloaded = []
        failed = []
        for ad_id in ad_ids:
            try:
                await tiktok_sync.enrich_creatives_deferred(connection_id, [ad_id])
                downloaded.append({"asset_id": str(ad_id), "url": ""})
            except Exception as asset_err:
                failed.append({"asset_id": str(ad_id), "error": str(asset_err)})
            # Progress tracks confirmed successes only, not total attempts
            await update_background_job(bg_job_id, status="RUNNING", progress_current=len(downloaded))

        # Phase 17: Mark COMPLETE/PARTIAL with D-11 output manifest
        final_status = "COMPLETE" if not failed else ("PARTIAL" if downloaded else "FAILED")
        output = {"downloaded": downloaded, "failed": failed}
        await update_background_job(
            bg_job_id,
            status=final_status,
            progress_current=len(ad_ids),
            output=output,
        )

    except Exception as e:
        logger.warning(f"TikTok creatives deferred fetch failed (non-fatal): {e}")
        if bg_job_id is not None:
            await update_background_job(
                bg_job_id,
                status="FAILED",
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": _tb.format_exc()[:10000],
                },
                output={
                    "downloaded": [],
                    "failed": [{"asset_id": str(aid), "error": str(e)} for aid in ad_ids],
                },
            )


async def _run_dv360_asset_downloads(connection_id, asset_queue: dict) -> None:
    from app.services.sync.dv360_sync import dv360_sync, _CookiesExpiredError
    from app.services.ai_autofill import backfill_failed_autofill_for_connection
    from sqlalchemy import select, update as _upd
    from app.models.platform import PlatformConnection
    from app.models.system_config import SystemConfig
    import uuid
    import traceback as _tb

    connection = None
    bg_job_id = None

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

        inner_queue = asset_queue.get("queue", {})
        asset_count = len(inner_queue)

        # Phase 17: Create BackgroundJob before downloads begin (D-05)
        bg_job_id = await create_background_job(
            job_type="download",
            org_id=connection.organization_id,
            platform_connection_id=connection.id,
            metadata={"platform": "dv360", "asset_count": asset_count},
            params={
                "asset_ids": [str(aid) for aid in inner_queue.keys()],
                "platform": "DV360",
                "platform_connection_id": str(connection.id),
            },
            initial_status="RUNNING",
            progress_total=asset_count,
        )

        downloaded = []
        failed = []
        try:
            async with get_session_factory()() as db:
                result = await dv360_sync.download_assets_post_commit(db, connection, asset_queue, bg_job_id=str(bg_job_id))
            downloaded = result.get("downloaded", []) if result else []
            failed = result.get("failed", []) if result else []
        except _CookiesExpiredError:
            raise
        except Exception as asset_err:
            failed = [{"asset_id": ad_id, "error": str(asset_err)} for ad_id in inner_queue]

        if len(downloaded) == 0 and len(failed) > 0:
            raise Exception(
                f"{len(failed)} DV360 asset download(s) failed: "
                + "; ".join(f"{f['asset_id']}: {f['error']}" for f in failed[:3])
                + ("..." if len(failed) > 3 else "")
            )

        asyncio.create_task(backfill_failed_autofill_for_connection(connection.id, connection.organization_id))

        # Phase 17: Mark COMPLETE (all downloaded), PARTIAL (some failed), or leave for exception path
        output = {"downloaded": downloaded, "failed": failed}
        dl_status = "PARTIAL" if failed else "COMPLETE"
        await update_background_job(
            bg_job_id,
            status=dl_status,
            progress_current=len(downloaded),
            output=output,
        )

    except _CookiesExpiredError:
        async with get_session_factory()() as fresh_db:
            _sc_row = (await fresh_db.execute(select(SystemConfig).limit(1))).scalar_one_or_none()
            _ts_still_valid = False
            if _sc_row and _sc_row.youtube_cookies_encrypted:
                try:
                    from app.core.security import decrypt_token as _dt_sec
                    from datetime import datetime as _dt_now
                    _raw = _dt_sec(_sc_row.youtube_cookies_encrypted)
                    _now = _dt_now.now().timestamp()
                    _ts_still_valid = any(
                        int(p[4]) > _now
                        for ln in _raw.splitlines()
                        if not ln.strip().startswith("#") and len(p := ln.strip().split("\t")) >= 7
                        and p[4].isdigit() and int(p[4]) > 0
                    )
                except Exception:
                    pass
            if _ts_still_valid:
                logger.warning("DV360 asset download: yt-dlp reported cookies invalid but timestamps are still valid — likely IP/rate-limiting, not true expiry. Skipping flag write.")
            else:
                await fresh_db.execute(_upd(SystemConfig).values(youtube_cookies_runtime_expired=True))
                await fresh_db.commit()
        logger.warning("DV360 asset download aborted: YouTube cookies expired — flag written to DB")
        if bg_job_id is not None:
            await update_background_job(
                bg_job_id,
                status="FAILED",
                error={
                    "type": "_CookiesExpiredError",
                    "message": "YouTube cookies expired",
                    "traceback": "",
                },
                output={
                    "downloaded": [],
                    "failed": [{"asset_id": str(aid), "error": "YouTube cookies expired"} for aid in asset_queue.keys()],
                },
            )
    except Exception as e:
        logger.warning(f"DV360 asset download failed (non-fatal): {e}")
        if bg_job_id is not None:
            await update_background_job(
                bg_job_id,
                status="FAILED",
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": _tb.format_exc()[:10000],
                },
                output={
                    "downloaded": [],
                    "failed": [{"asset_id": str(aid), "error": str(e)} for aid in asset_queue.keys()],
                },
            )


async def run_full_resync(connection_id: str) -> None:
    """Full resync: re-fetch all historical data (24 months) with latest field mappings."""
    from sqlalchemy import select
    from app.models.platform import PlatformConnection
    from app.models.performance import SyncJob
    from app.services.sync.meta_sync import meta_sync, MetaTokenError
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
    _token_err: Optional[MetaTokenError] = None
    _terr_conn_id = None
    _terr_job_id = None
    _terr_org_id = None
    _terr_platform = None
    # Phase 17: bg_job_id must be accessible in both the first-phase async-with
    # block and the DV360 second-phase blocks below (D-01, Python scoping).
    bg_job_id = None

    await _supersede_running_jobs(connection_id)

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

        # Phase 17: Create BackgroundJob alongside SyncJob (D-01, D-03)
        bg_job_id = await create_background_job(
            job_type="sync_full",
            org_id=connection.organization_id,
            platform_connection_id=connection.id,
            metadata={"sync_job_id": job_id, "platform": connection.platform},
            params={"platform": connection.platform, "platform_connection_id": str(connection.id), "date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "sync_type": "full"},
        )
        await update_background_job(
            bg_job_id,
            status="RUNNING",
            progress_total=1,
            progress_current=0,
        )

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

        except MetaTokenError as e:
            logger.error(f"Full resync token error for connection {connection_id}: {e}")
            _token_err = e
            _terr_conn_id = connection.id
            _terr_job_id = job.id
            _terr_org_id = str(connection.organization_id)
            _terr_platform = connection.platform
            try:
                await db.rollback()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Full resync fetch failed for connection {connection_id}: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            try:
                await db.rollback()
            except Exception:
                pass
            from sqlalchemy import update as _upd
            async with get_session_factory()() as fresh_db:
                await fresh_db.execute(_upd(PlatformConnection).where(PlatformConnection.id == uuid.UUID(connection_id)).values(sync_status="ERROR"))
                await fresh_db.execute(_upd(SyncJob).where(SyncJob.id == uuid.UUID(job_id)).values(status="FAILED", error_message=f"{type(e).__name__}: {e}"[:4000], completed_at=datetime.utcnow()))
                await fresh_db.commit()
            # Phase 17: Mark BackgroundJob FAILED (D-13)
            if bg_job_id is not None:
                import traceback as _tb
                await update_background_job(
                    bg_job_id,
                    status="FAILED",
                    progress_current=1,
                    error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                )
            await _notify_connection_status(connection, "ERROR")
            return

        if not is_dv360 and _token_err is None:
            try:
                harmonized, new_assets = await _harmonize_with_deadlock_retry(harmonizer, db, connection, date_from, date_to)
                connection.last_synced_at = datetime.utcnow()
                connection.sync_status = "ACTIVE"
                db.add(connection)
                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                job.records_processed = harmonized
                db.add(job)
                asyncio.create_task(create_org_notification(
                    org_id=str(connection.organization_id),
                    type="SYNC_COMPLETE",
                    title=f"{PLATFORM_DISPLAY.get(connection.platform, str(connection.platform).title())} Sync Complete",
                    message=f"Full resync complete for {connection.ad_account_name}.",
                    data={"platform": connection.platform, "connection_id": str(connection.id)},
                ))
                await db.commit()
                # Phase 17: Mark BackgroundJob COMPLETE (D-12 output schema)
                if bg_job_id is not None:
                    await update_background_job(
                        bg_job_id,
                        status="COMPLETE",
                        progress_current=1,
                        output={
                            "platform": connection.platform.lower(),
                            "sync_job_id": job_id,
                            "records_fetched": job.records_fetched or 0,
                            "records_processed": harmonized,
                        },
                    )
                new_asset_ids = {aid for aid, _ in new_assets}
                for aid, oid in new_assets:
                    asyncio.create_task(run_autofill_for_asset(asset_id=aid, org_id=oid))
                asyncio.create_task(backfill_failed_autofill_for_connection(connection.id, connection.organization_id, new_asset_ids))
                # Phase 23 (D-09): trigger duration backfill if NULL-duration VIDEO assets exist
                try:
                    _null_count = await has_null_duration_assets(db, connection.organization_id)
                    if _null_count > 0:
                        logger.info("Triggering duration backfill for org %s (%d NULL-duration video assets)", connection.organization_id, _null_count)
                        asyncio.create_task(run_duration_backfill(connection.organization_id))
                except Exception as _e:
                    logger.warning("Failed to trigger duration backfill for connection %s: %s", connection.id, _e)
                if connection.platform == "GOOGLE_ADS" and sync_result.get("_asset_queue"):
                    asyncio.create_task(_run_google_ads_asset_downloads(connection.id, sync_result["_asset_queue"]))
                elif connection.platform == "META" and sync_result.get("_creative_ad_ids"):
                    asyncio.create_task(_run_meta_creatives_deferred(connection.id, sync_result["_creative_ad_ids"], org_id=connection.organization_id))
                elif connection.platform == "TIKTOK" and sync_result.get("_creative_ad_ids"):
                    asyncio.create_task(_run_tiktok_creatives_deferred(connection.id, sync_result["_creative_ad_ids"], org_id=connection.organization_id))
                logger.info(f"Full resync completed for {connection.platform} {connection.ad_account_id}: {sync_result}")
            except Exception as e:
                logger.error(f"Full resync harmonization failed for connection {connection_id}: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await db.rollback()
                job.status = "FAILED"
                job.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                job.completed_at = datetime.utcnow()
                db.add(job)
                await _notify_connection_status(connection, "ERROR")
                connection.sync_status = "ERROR"
                db.add(connection)
                await db.commit()
                # Phase 17: Mark BackgroundJob FAILED (D-13)
                if bg_job_id is not None:
                    import traceback as _tb
                    await update_background_job(
                        bg_job_id,
                        status="FAILED",
                        progress_current=1,
                        error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                    )

    if is_dv360 and dv360_info:
        try:
            logger.info(f"DV360 full resync: polling reports with no DB session held")
            dv360_report_data = await dv360_sync.fetch_report_data(
                dv360_info["access_token"], dv360_info["connection_id"],
                dv360_info["refresh_token_encrypted"],
                dv360_info["advertiser_id"],
                dv360_info["date_from"], dv360_info["date_to"],
                force_refetch_metadata=True,
                bg_job_id=bg_job_id,
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
                    await _notify_connection_status(conn, "ERROR")
                    conn.sync_status = "ERROR"
                    db.add(conn)
                await db.commit()
            # Phase 17: Mark BackgroundJob FAILED (D-13)
            if bg_job_id is not None:
                import traceback as _tb
                await update_background_job(
                    bg_job_id,
                    status="FAILED",
                    progress_current=1,
                    error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                )
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
                logger.error(f"DV360 full resync upsert failed: {type(e).__name__}: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"{type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await _notify_connection_status(conn, "ERROR")
                conn.sync_status = "ERROR"
                db.add(conn)
                await db.commit()
                # Phase 17: Mark BackgroundJob FAILED (D-13)
                if bg_job_id is not None:
                    import traceback as _tb
                    await update_background_job(
                        bg_job_id,
                        status="FAILED",
                        progress_current=1,
                        error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                    )
                return

            dv360_asset_queue = sync_result.get("_asset_queue")
            conn_id_for_assets = conn.id if dv360_asset_queue else None

            try:
                harmonized, new_assets = await _harmonize_with_deadlock_retry(harmonizer, db, conn, dv360_info["date_from"], dv360_info["date_to"])
                conn.last_synced_at = datetime.utcnow()
                conn.sync_status = "ACTIVE"
                db.add(conn)
                sj.status = "COMPLETED"
                sj.completed_at = datetime.utcnow()
                sj.records_processed = harmonized
                db.add(sj)
                asyncio.create_task(create_org_notification(
                    org_id=str(conn.organization_id),
                    type="SYNC_COMPLETE",
                    title=f"{PLATFORM_DISPLAY.get(conn.platform, str(conn.platform).title())} Sync Complete",
                    message=f"Full resync complete for {conn.ad_account_name}.",
                    data={"platform": conn.platform, "connection_id": str(conn.id)},
                ))
                await db.commit()
                # Phase 17: Mark BackgroundJob COMPLETE (D-12 output schema)
                if bg_job_id is not None:
                    await update_background_job(
                        bg_job_id,
                        status="COMPLETE",
                        progress_current=1,
                        output={
                            "platform": conn.platform.lower(),
                            "sync_job_id": dv360_info["job_id"],
                            "records_fetched": sj.records_fetched or 0,
                            "records_processed": harmonized,
                        },
                    )
                new_asset_ids = {aid for aid, _ in new_assets}
                for aid, oid in new_assets:
                    asyncio.create_task(run_autofill_for_asset(asset_id=aid, org_id=oid))
                asyncio.create_task(backfill_failed_autofill_for_connection(conn.id, conn.organization_id, new_asset_ids))
                # Phase 23 (D-09): trigger duration backfill if NULL-duration VIDEO assets exist
                try:
                    _null_count = await has_null_duration_assets(db, conn.organization_id)
                    if _null_count > 0:
                        logger.info("Triggering duration backfill for org %s (%d NULL-duration video assets)", conn.organization_id, _null_count)
                        asyncio.create_task(run_duration_backfill(conn.organization_id))
                except Exception as _e:
                    logger.warning("Failed to trigger duration backfill for connection %s: %s", conn.id, _e)
                logger.info(f"DV360 full resync completed: {sync_result}")
            except Exception as e:
                logger.error(f"DV360 full resync harmonization failed: {type(e).__name__}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await _notify_connection_status(conn, "ERROR")
                conn.sync_status = "ERROR"
                db.add(conn)
                await db.commit()
                # Phase 17: Mark BackgroundJob FAILED (D-13)
                if bg_job_id is not None:
                    import traceback as _tb
                    await update_background_job(
                        bg_job_id,
                        status="FAILED",
                        progress_current=1,
                        error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                    )

    if _token_err and _terr_conn_id:
        from sqlalchemy import update as _upd
        async with get_session_factory()() as fresh_db:
            await fresh_db.execute(_upd(PlatformConnection).where(PlatformConnection.id == _terr_conn_id).values(sync_status="EXPIRED"))
            await fresh_db.execute(_upd(SyncJob).where(SyncJob.id == _terr_job_id).values(status="FAILED", error_message=f"TokenError: {_token_err}"[:4000], completed_at=datetime.utcnow()))
            await fresh_db.commit()
        # Phase 17: Mark BackgroundJob FAILED for MetaTokenError (D-13)
        if bg_job_id is not None:
            await update_background_job(
                bg_job_id,
                status="FAILED",
                progress_current=1,
                error={"type": "MetaTokenError", "message": str(_token_err), "traceback": ""},
            )
        platform_name = PLATFORM_DISPLAY.get(_terr_platform, str(_terr_platform).title())
        asyncio.create_task(create_org_notification(org_id=_terr_org_id, type="TOKEN_EXPIRED", title=f"{platform_name} Token Expired", message=f"Your {platform_name} access token has expired. Reconnect to resume syncing.", data={"platform": _terr_platform, "connection_id": str(_terr_conn_id)}))
        return

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
    # Phase 17: bg_job_id must be accessible in both the first-phase async-with
    # block and the DV360 second-phase blocks below (D-01, Python scoping).
    bg_job_id = None

    await _supersede_running_jobs(connection_id)

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

        # Phase 17: Create BackgroundJob alongside SyncJob (D-01, D-03)
        bg_job_id = await create_background_job(
            job_type="sync_initial",
            org_id=connection.organization_id,
            platform_connection_id=connection.id,
            metadata={"sync_job_id": job_id, "platform": connection.platform},
            params={"platform": connection.platform, "platform_connection_id": str(connection.id), "date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "sync_type": "initial"},
        )
        await update_background_job(
            bg_job_id,
            status="RUNNING",
            progress_total=1,
            progress_current=0,
        )

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
            try:
                await db.rollback()
            except Exception:
                pass
            from sqlalchemy import update as _upd
            async with get_session_factory()() as fresh_db:
                await fresh_db.execute(_upd(PlatformConnection).where(PlatformConnection.id == uuid.UUID(connection_id)).values(sync_status="ERROR"))
                await fresh_db.execute(_upd(SyncJob).where(SyncJob.id == uuid.UUID(job_id)).values(status="FAILED", error_message=f"{type(e).__name__}: {e}"[:4000], completed_at=datetime.utcnow()))
                await fresh_db.commit()
            # Phase 17: Mark BackgroundJob FAILED (D-13)
            if bg_job_id is not None:
                import traceback as _tb
                await update_background_job(
                    bg_job_id,
                    status="FAILED",
                    progress_current=1,
                    error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                )
            await _notify_connection_status(connection, "ERROR")
            return

        if not is_dv360:
            try:
                harmonized, new_assets = await _harmonize_with_deadlock_retry(harmonizer, db, connection, date_from, date_to)
                connection.initial_sync_completed = True
                connection.last_synced_at = datetime.utcnow()
                db.add(connection)
                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                job.records_processed = harmonized
                db.add(job)
                asyncio.create_task(create_org_notification(
                    org_id=str(connection.organization_id),
                    type="SYNC_COMPLETE",
                    title=f"{PLATFORM_DISPLAY.get(connection.platform, str(connection.platform).title())} Sync Complete",
                    message=f"Initial sync complete. Your {PLATFORM_DISPLAY.get(connection.platform, str(connection.platform).title())} creatives are now available.",
                    data={"platform": connection.platform, "connection_id": str(connection.id)},
                ))
                await db.commit()
                # Phase 17: Mark BackgroundJob COMPLETE (D-12 output schema)
                if bg_job_id is not None:
                    await update_background_job(
                        bg_job_id,
                        status="COMPLETE",
                        progress_current=1,
                        output={
                            "platform": connection.platform.lower(),
                            "sync_job_id": job_id,
                            "records_fetched": job.records_fetched or 0,
                            "records_processed": harmonized,
                        },
                    )
                new_asset_ids = {aid for aid, _ in new_assets}
                for aid, oid in new_assets:
                    asyncio.create_task(run_autofill_for_asset(asset_id=aid, org_id=oid))
                asyncio.create_task(backfill_failed_autofill_for_connection(connection.id, connection.organization_id, new_asset_ids))
                # Phase 23 (D-09): trigger duration backfill if NULL-duration VIDEO assets exist
                try:
                    _null_count = await has_null_duration_assets(db, connection.organization_id)
                    if _null_count > 0:
                        logger.info("Triggering duration backfill for org %s (%d NULL-duration video assets)", connection.organization_id, _null_count)
                        asyncio.create_task(run_duration_backfill(connection.organization_id))
                except Exception as _e:
                    logger.warning("Failed to trigger duration backfill for connection %s: %s", connection.id, _e)
                if connection.platform == "GOOGLE_ADS" and sync_result.get("_asset_queue"):
                    asyncio.create_task(_run_google_ads_asset_downloads(connection.id, sync_result["_asset_queue"]))
                elif connection.platform == "META" and sync_result.get("_creative_ad_ids"):
                    asyncio.create_task(_run_meta_creatives_deferred(connection.id, sync_result["_creative_ad_ids"], org_id=connection.organization_id))
                elif connection.platform == "TIKTOK" and sync_result.get("_creative_ad_ids"):
                    asyncio.create_task(_run_tiktok_creatives_deferred(connection.id, sync_result["_creative_ad_ids"], org_id=connection.organization_id))
                trigger_historical = True
            except Exception as e:
                logger.error(f"Initial sync harmonization failed for {connection_id}: {type(e).__name__}: {e}")
                await db.rollback()
                job.status = "FAILED"
                job.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                db.add(job)
                await db.commit()
                # Phase 17: Mark BackgroundJob FAILED (D-13)
                if bg_job_id is not None:
                    import traceback as _tb
                    await update_background_job(
                        bg_job_id,
                        status="FAILED",
                        progress_current=1,
                        error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                    )

    if is_dv360 and dv360_info:
        try:
            logger.info(f"DV360 initial sync: polling reports with no DB session held")
            dv360_report_data = await dv360_sync.fetch_report_data(
                dv360_info["access_token"], dv360_info["connection_id"],
                dv360_info["refresh_token_encrypted"],
                dv360_info["advertiser_id"], date_from, date_to,
                force_refetch_metadata=True,
                bg_job_id=bg_job_id,
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
            # Phase 17: Mark BackgroundJob FAILED (D-13)
            if bg_job_id is not None:
                import traceback as _tb
                await update_background_job(
                    bg_job_id,
                    status="FAILED",
                    progress_current=1,
                    error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                )
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
                logger.error(f"DV360 initial sync upsert failed: {type(e).__name__}: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"{type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await db.commit()
                # Phase 17: Mark BackgroundJob FAILED (D-13)
                if bg_job_id is not None:
                    import traceback as _tb
                    await update_background_job(
                        bg_job_id,
                        status="FAILED",
                        progress_current=1,
                        error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                    )
                return

            dv360_asset_queue = sync_result.get("_asset_queue")
            conn_id_for_assets = conn.id if dv360_asset_queue else None

            try:
                harmonized, new_assets = await _harmonize_with_deadlock_retry(harmonizer, db, conn, date_from, date_to)
                conn.initial_sync_completed = True
                conn.last_synced_at = datetime.utcnow()
                db.add(conn)
                sj.status = "COMPLETED"
                sj.completed_at = datetime.utcnow()
                sj.records_processed = harmonized
                db.add(sj)
                asyncio.create_task(create_org_notification(
                    org_id=str(conn.organization_id),
                    type="SYNC_COMPLETE",
                    title=f"{PLATFORM_DISPLAY.get(conn.platform, str(conn.platform).title())} Sync Complete",
                    message=f"Initial sync complete. Your {PLATFORM_DISPLAY.get(conn.platform, str(conn.platform).title())} creatives are now available.",
                    data={"platform": conn.platform, "connection_id": str(conn.id)},
                ))
                await db.commit()
                # Phase 17: Mark BackgroundJob COMPLETE (D-12 output schema)
                if bg_job_id is not None:
                    await update_background_job(
                        bg_job_id,
                        status="COMPLETE",
                        progress_current=1,
                        output={
                            "platform": conn.platform.lower(),
                            "sync_job_id": dv360_info["job_id"],
                            "records_fetched": sj.records_fetched or 0,
                            "records_processed": harmonized,
                        },
                    )
                new_asset_ids = {aid for aid, _ in new_assets}
                for aid, oid in new_assets:
                    asyncio.create_task(run_autofill_for_asset(asset_id=aid, org_id=oid))
                asyncio.create_task(backfill_failed_autofill_for_connection(conn.id, conn.organization_id, new_asset_ids))
                # Phase 23 (D-09): trigger duration backfill if NULL-duration VIDEO assets exist
                try:
                    _null_count = await has_null_duration_assets(db, conn.organization_id)
                    if _null_count > 0:
                        logger.info("Triggering duration backfill for org %s (%d NULL-duration video assets)", conn.organization_id, _null_count)
                        asyncio.create_task(run_duration_backfill(conn.organization_id))
                except Exception as _e:
                    logger.warning("Failed to trigger duration backfill for connection %s: %s", conn.id, _e)
                trigger_historical = True
                logger.info(f"DV360 initial sync completed: {sync_result}")
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
                # Phase 17: Mark BackgroundJob FAILED (D-13)
                if bg_job_id is not None:
                    import traceback as _tb
                    await update_background_job(
                        bg_job_id,
                        status="FAILED",
                        progress_current=1,
                        error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                    )

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
    # Phase 17: bg_job_id must be accessible in both the first-phase async-with
    # block and the DV360 second-phase blocks below (D-01, Python scoping).
    bg_job_id = None

    await _supersede_running_jobs(connection_id)

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

        # Phase 17: Create BackgroundJob alongside SyncJob (D-01, D-03)
        bg_job_id = await create_background_job(
            job_type="sync_historical",
            org_id=connection.organization_id,
            platform_connection_id=connection.id,
            metadata={"sync_job_id": job_id, "platform": connection.platform},
            params={"platform": connection.platform, "platform_connection_id": str(connection.id), "date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "sync_type": "historical"},
        )
        await update_background_job(
            bg_job_id,
            status="RUNNING",
            progress_total=1,
            progress_current=0,
        )

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
            try:
                await db.rollback()
            except Exception:
                pass
            from sqlalchemy import update as _upd
            async with get_session_factory()() as fresh_db:
                await fresh_db.execute(_upd(PlatformConnection).where(PlatformConnection.id == uuid.UUID(connection_id)).values(sync_status="ERROR"))
                await fresh_db.execute(_upd(SyncJob).where(SyncJob.id == uuid.UUID(job_id)).values(status="FAILED", error_message=f"{type(e).__name__}: {e}"[:4000], completed_at=datetime.utcnow()))
                await fresh_db.commit()
            # Phase 17: Mark BackgroundJob FAILED (D-13)
            if bg_job_id is not None:
                import traceback as _tb
                await update_background_job(
                    bg_job_id,
                    status="FAILED",
                    progress_current=1,
                    error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                )
            await _notify_connection_status(connection, "ERROR")
            return

        if not is_dv360:
            try:
                harmonized, new_assets = await _harmonize_with_deadlock_retry(harmonizer, db, connection, date_from, date_to)
                connection.historical_sync_completed = True
                db.add(connection)
                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                job.records_processed = harmonized
                db.add(job)
                await db.commit()
                # Phase 17: Mark BackgroundJob COMPLETE (D-12 output schema)
                if bg_job_id is not None:
                    await update_background_job(
                        bg_job_id,
                        status="COMPLETE",
                        progress_current=1,
                        output={
                            "platform": connection.platform.lower(),
                            "sync_job_id": job_id,
                            "records_fetched": job.records_fetched or 0,
                            "records_processed": harmonized,
                        },
                    )
                new_asset_ids = {aid for aid, _ in new_assets}
                for aid, oid in new_assets:
                    asyncio.create_task(run_autofill_for_asset(asset_id=aid, org_id=oid))
                asyncio.create_task(backfill_failed_autofill_for_connection(connection.id, connection.organization_id, new_asset_ids))
                # Phase 23 (D-09): trigger duration backfill if NULL-duration VIDEO assets exist
                try:
                    _null_count = await has_null_duration_assets(db, connection.organization_id)
                    if _null_count > 0:
                        logger.info("Triggering duration backfill for org %s (%d NULL-duration video assets)", connection.organization_id, _null_count)
                        asyncio.create_task(run_duration_backfill(connection.organization_id))
                except Exception as _e:
                    logger.warning("Failed to trigger duration backfill for connection %s: %s", connection.id, _e)
                if connection.platform == "GOOGLE_ADS" and sync_result.get("_asset_queue"):
                    asyncio.create_task(_run_google_ads_asset_downloads(connection.id, sync_result["_asset_queue"]))
                elif connection.platform == "META" and sync_result.get("_creative_ad_ids"):
                    asyncio.create_task(_run_meta_creatives_deferred(connection.id, sync_result["_creative_ad_ids"], org_id=connection.organization_id))
                elif connection.platform == "TIKTOK" and sync_result.get("_creative_ad_ids"):
                    asyncio.create_task(_run_tiktok_creatives_deferred(connection.id, sync_result["_creative_ad_ids"], org_id=connection.organization_id))
            except Exception as e:
                logger.error(f"Historical sync harmonization failed for {connection_id}: {type(e).__name__}: {e}")
                await db.rollback()
                job.status = "FAILED"
                job.error_message = f"Harmonization: {type(e).__name__}: {e}"[:4000]
                db.add(job)
                await db.commit()
                # Phase 17: Mark BackgroundJob FAILED (D-13)
                if bg_job_id is not None:
                    import traceback as _tb
                    await update_background_job(
                        bg_job_id,
                        status="FAILED",
                        progress_current=1,
                        error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                    )

    if is_dv360 and dv360_info:
        try:
            logger.info(f"DV360 historical sync: polling reports with no DB session held")
            dv360_report_data = await dv360_sync.fetch_report_data(
                dv360_info["access_token"], dv360_info["connection_id"],
                dv360_info["refresh_token_encrypted"],
                dv360_info["advertiser_id"],
                dv360_info["date_from"], dv360_info["date_to"],
                force_refetch_metadata=True,
                bg_job_id=bg_job_id,
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
            # Phase 17: Mark BackgroundJob FAILED (D-13)
            if bg_job_id is not None:
                import traceback as _tb
                await update_background_job(
                    bg_job_id,
                    status="FAILED",
                    progress_current=1,
                    error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                )
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
                logger.error(f"DV360 historical sync upsert failed: {type(e).__name__}: {e}")
                await db.rollback()
                sj.status = "FAILED"
                sj.error_message = f"{type(e).__name__}: {e}"[:4000]
                sj.completed_at = datetime.utcnow()
                db.add(sj)
                await db.commit()
                # Phase 17: Mark BackgroundJob FAILED (D-13)
                if bg_job_id is not None:
                    import traceback as _tb
                    await update_background_job(
                        bg_job_id,
                        status="FAILED",
                        progress_current=1,
                        error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                    )
                return

            dv360_asset_queue = sync_result.get("_asset_queue")
            conn_id_for_assets = conn.id if dv360_asset_queue else None

            try:
                harmonized, new_assets = await _harmonize_with_deadlock_retry(harmonizer, db, conn, dv360_info["date_from"], dv360_info["date_to"])
                conn.historical_sync_completed = True
                db.add(conn)
                sj.status = "COMPLETED"
                sj.completed_at = datetime.utcnow()
                sj.records_processed = harmonized
                db.add(sj)
                await db.commit()
                # Phase 17: Mark BackgroundJob COMPLETE (D-12 output schema)
                if bg_job_id is not None:
                    await update_background_job(
                        bg_job_id,
                        status="COMPLETE",
                        progress_current=1,
                        output={
                            "platform": conn.platform.lower(),
                            "sync_job_id": dv360_info["job_id"],
                            "records_fetched": sj.records_fetched or 0,
                            "records_processed": harmonized,
                        },
                    )
                new_asset_ids = {aid for aid, _ in new_assets}
                for aid, oid in new_assets:
                    asyncio.create_task(run_autofill_for_asset(asset_id=aid, org_id=oid))
                asyncio.create_task(backfill_failed_autofill_for_connection(conn.id, conn.organization_id, new_asset_ids))
                # Phase 23 (D-09): trigger duration backfill if NULL-duration VIDEO assets exist
                try:
                    _null_count = await has_null_duration_assets(db, conn.organization_id)
                    if _null_count > 0:
                        logger.info("Triggering duration backfill for org %s (%d NULL-duration video assets)", conn.organization_id, _null_count)
                        asyncio.create_task(run_duration_backfill(conn.organization_id))
                except Exception as _e:
                    logger.warning("Failed to trigger duration backfill for connection %s: %s", conn.id, _e)
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
                # Phase 17: Mark BackgroundJob FAILED (D-13)
                if bg_job_id is not None:
                    import traceback as _tb
                    await update_background_job(
                        bg_job_id,
                        status="FAILED",
                        progress_current=1,
                        error={"type": type(e).__name__, "message": str(e), "traceback": _tb.format_exc()[:10000]},
                    )

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


async def purge_read_notifications() -> None:
    """Delete read notifications older than 3 days."""
    from sqlalchemy import delete
    from app.models.user import Notification
    cutoff = datetime.utcnow() - timedelta(days=3)
    async with get_session_factory()() as db:
        result = await db.execute(
            delete(Notification).where(
                Notification.is_read == True,
                Notification.created_at < cutoff,
            )
        )
        deleted = result.rowcount
        if deleted:
            await db.commit()
            logger.info(f"Purged {deleted} read notifications older than 3 days")


async def startup_scheduler(db_session=None) -> None:
    """Load all active connections and schedule their daily syncs.
    Also triggers initial sync for any connections that missed it."""
    from sqlalchemy import select, update as _sa_update
    from app.models.platform import PlatformConnection
    from app.models.jobs import BackgroundJob
    from datetime import datetime as _dt, timedelta as _td

    # Reset jobs that were left RUNNING or stuck PENDING when the process was killed mid-flight.
    # PENDING jobs older than 5 minutes never reached RUNNING (e.g. pool exhaustion killed the update).
    stale_pending_cutoff = _dt.utcnow() - _td(minutes=5)
    async with get_session_factory()() as db:
        running_result = await db.execute(
            _sa_update(BackgroundJob)
            .where(BackgroundJob.status == "RUNNING")
            .values(
                status="FAILED",
                error={"type": "ProcessRestart", "message": "Server restarted while job was running", "traceback": ""},
                ended_at=_dt.utcnow(),
            )
            .returning(BackgroundJob.id)
        )
        pending_result = await db.execute(
            _sa_update(BackgroundJob)
            .where(BackgroundJob.status == "PENDING", BackgroundJob.created_at < stale_pending_cutoff)
            .values(
                status="FAILED",
                error={"type": "ProcessRestart", "message": "Job never started — server restarted before execution began", "traceback": ""},
                ended_at=_dt.utcnow(),
            )
            .returning(BackgroundJob.id)
        )
        running_ids = [row[0] for row in running_result.all()]
        pending_ids = [row[0] for row in pending_result.all()]
        await db.commit()
        if running_ids:
            logger.warning("Startup: reset %d orphaned RUNNING job(s) to FAILED", len(running_ids))
        if pending_ids:
            logger.warning("Startup: reset %d orphaned PENDING job(s) to FAILED", len(pending_ids))

    pending_initial = []

    async with get_session_factory()() as db:
        result = await db.execute(
            select(PlatformConnection).where(PlatformConnection.is_active == True)
        )
        connections = result.scalars().all()

        # Connections with INTERRUPTED jobs will be resumed by _auto_resume_interrupted_jobs().
        # Exclude them here to prevent a duplicate initial sync from firing.
        interrupted_result = await db.execute(
            select(BackgroundJob.platform_connection_id)
            .where(BackgroundJob.status == "INTERRUPTED", BackgroundJob.platform_connection_id.isnot(None))
            .distinct()
        )
        has_interrupted_job: set = {row[0] for row in interrupted_result.all()}

        for conn in connections:
            timezone = conn.timezone or "UTC"
            schedule_connection(str(conn.id), timezone)
            if not conn.initial_sync_completed and conn.id not in has_interrupted_job:
                pending_initial.append(str(conn.id))

    from app.core.config import settings as _settings
    from app.services.sync.scoring_job import run_scoring_batch

    if _settings.SCHEDULER_ENABLED:
        scheduler.add_job(
            run_scoring_batch,
            trigger=IntervalTrigger(minutes=15),
            id="scoring_batch",
            replace_existing=True,
            max_instances=10,
        )
        logger.info("Registered scoring_batch job (every 15 minutes)")
        from app.services.sync.maintenance import cleanup_old_background_jobs, reset_stale_background_jobs
        scheduler.add_job(
            cleanup_old_background_jobs,
            trigger=CronTrigger(hour=3, minute=0),
            id="cleanup_background_jobs",
            replace_existing=True,
        )
        logger.info("Registered cleanup_background_jobs job (daily at 03:00 UTC)")
        scheduler.add_job(
            reset_stale_background_jobs,
            trigger=IntervalTrigger(minutes=10),
            id="reset_stale_background_jobs",
            replace_existing=True,
        )
        logger.info("Registered reset_stale_background_jobs job (every 10 minutes)")
        scheduler.add_job(
            purge_read_notifications,
            trigger=CronTrigger(hour=3, minute=0),
            id="purge_read_notifications",
            replace_existing=True,
        )
        logger.info("Registered purge_read_notifications job (daily at 03:00 UTC)")
    else:
        logger.info("SCHEDULER_ENABLED=False — skipping scoring_batch registration")

    scheduler.start()
    logger.info(f"Scheduler started with {len(connections)} active connections")

    if pending_initial:
        logger.info(f"Found {len(pending_initial)} connections needing initial sync, triggering now...")
        for conn_id in pending_initial:
            asyncio.create_task(run_initial_sync(conn_id))


async def trigger_download_retry(params: dict, job_id: str) -> None:
    """Re-run a download job. Resume skip logic handles already-downloaded assets."""
    from sqlalchemy import select as _sel
    from app.models.platform import PlatformConnection
    import uuid as _uuid

    platform = params.get("platform")
    platform_connection_id = params.get("platform_connection_id")
    asset_ids = params.get("asset_ids", [])

    if not platform or not platform_connection_id or not asset_ids:
        logger.warning("trigger_download_retry: missing required params — platform=%s connection=%s asset_ids=%s", platform, platform_connection_id, len(asset_ids))
        return

    conn_uuid = _uuid.UUID(str(platform_connection_id))

    async with get_session_factory()() as db:
        result = await db.execute(_sel(PlatformConnection).where(PlatformConnection.id == conn_uuid))
        connection = result.scalar_one_or_none()

    if not connection:
        logger.warning("trigger_download_retry: connection %s not found", platform_connection_id)
        return

    if platform == "GOOGLE_ADS":
        from app.services.sync.google_ads_sync import google_ads_sync
        asset_queue = {}
        async with get_session_factory()() as db:
            from app.models.performance import GoogleAdsRawPerformance
            from sqlalchemy import select as _s2
            rows = (await db.execute(_s2(GoogleAdsRawPerformance.ad_id, GoogleAdsRawPerformance.video_id).where(GoogleAdsRawPerformance.ad_id.in_(asset_ids), GoogleAdsRawPerformance.platform_connection_id == conn_uuid))).fetchall()
            for ad_id, video_id in rows:
                asset_queue[ad_id] = {"video_id": video_id}
        asyncio.create_task(_run_google_ads_asset_downloads(conn_uuid, asset_queue))
    elif platform == "META":
        asyncio.create_task(_run_meta_creatives_deferred(conn_uuid, asset_ids, org_id=connection.organization_id))
    elif platform == "TIKTOK":
        asyncio.create_task(_run_tiktok_creatives_deferred(conn_uuid, asset_ids, org_id=connection.organization_id))
    elif platform == "DV360":
        asyncio.create_task(_run_dv360_asset_downloads(conn_uuid, {"queue": {aid: {} for aid in asset_ids}}))
    else:
        logger.warning("trigger_download_retry: unknown platform %s", platform)


async def trigger_dv360_sync_retry(params: dict, new_job_id: str, resume_query_id: Optional[str]) -> None:
    """Re-run a DV360 sync job, resuming the Bid Manager poll loop if resume_query_id is given."""
    from sqlalchemy import select as _sel
    from app.models.platform import PlatformConnection
    from app.services.sync.dv360_sync import dv360_sync
    from app.services.sync.harmonizer import harmonizer
    from app.services.sync.job_tracker import update_background_job as _ubj
    import uuid as _uuid

    platform_connection_id = params.get("platform_connection_id")
    date_from_str = params.get("date_from")
    date_to_str = params.get("date_to")
    sync_type = params.get("sync_type", "daily")

    if not platform_connection_id or not date_from_str or not date_to_str:
        logger.warning("trigger_dv360_sync_retry: missing params — %s", params)
        return

    conn_uuid = _uuid.UUID(str(platform_connection_id))
    job_uuid = _uuid.UUID(str(new_job_id))
    date_from = date.fromisoformat(date_from_str)
    date_to = date.fromisoformat(date_to_str)

    async with get_session_factory()() as db:
        connection = (await db.execute(_sel(PlatformConnection).where(PlatformConnection.id == conn_uuid))).scalar_one_or_none()

    if not connection:
        logger.warning("trigger_dv360_sync_retry: connection %s not found", platform_connection_id)
        return

    await _ubj(job_uuid, status="RUNNING", progress_total=1, progress_current=0)

    try:
        async with get_session_factory()() as db:
            access_token = await dv360_sync._get_valid_token(db, connection)

        force_refetch = sync_type != "daily"
        dv360_report_data = await dv360_sync.fetch_report_data(
            access_token, connection.id,
            connection.refresh_token_encrypted,
            connection.ad_account_id, date_from, date_to,
            force_refetch_metadata=force_refetch,
            bg_job_id=job_uuid,
            resume_query_id=resume_query_id,
        )

        async with get_session_factory()() as db:
            from app.models.performance import SyncJob
            job = SyncJob(
                platform_connection_id=connection.id,
                job_type="RETRY",
                status="RUNNING",
                started_at=datetime.utcnow(),
                date_from=date_from,
                date_to=date_to,
            )
            db.add(job)
            await db.flush()
            retry_job_id = str(job.id)

            sync_result = await dv360_sync.store_report_data(db, connection, dv360_report_data, retry_job_id)
            await db.commit()

        asset_queue = sync_result.get("_asset_queue") if isinstance(sync_result, dict) else None

        async with get_session_factory()() as db:
            conn2 = (await db.execute(_sel(PlatformConnection).where(PlatformConnection.id == conn_uuid))).scalar_one_or_none()
            if conn2:
                try:
                    from app.models.performance import SyncJob as SJ2
                    from sqlalchemy import select as sel2
                    sj2 = (await db.execute(sel2(SJ2).where(SJ2.id == _uuid.UUID(retry_job_id)))).scalar_one_or_none()
                    await harmonizer.harmonize(db, conn2, sj2)
                    await db.commit()
                except Exception as _h_err:
                    logger.warning("trigger_dv360_sync_retry: harmonizer failed (non-fatal): %s", _h_err)

        await _ubj(job_uuid, status="COMPLETE", progress_current=1, output={"sync_type": sync_type, "resumed": resume_query_id is not None})

        if asset_queue and conn_uuid:
            asyncio.create_task(_run_dv360_asset_downloads(conn_uuid, asset_queue))

    except Exception as _e:
        import traceback as _tb
        logger.error("trigger_dv360_sync_retry failed: %s: %s", type(_e).__name__, _e)
        await _ubj(job_uuid, status="FAILED", error={"type": type(_e).__name__, "message": str(_e), "traceback": _tb.format_exc()[:10000]})
