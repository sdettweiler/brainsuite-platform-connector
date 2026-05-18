"""Async duration backfill job for Phase 23 (DASH-03).

Populates video_duration for VIDEO assets that have an asset_url but NULL video_duration.
Covers all platforms — Meta, TikTok, DV360, Google Ads — wherever asset_url is populated.

Contracts:
- D-09: Triggered after every sync completion site via scheduler.py (8 sites total)
- D-10: Targets asset_format='VIDEO' AND video_duration IS NULL AND asset_url IS NOT NULL
- D-11: Processes in sequential batches of 100 (CPU-bound ffprobe; avoids spikes)
- T-23-03: ALL queries parameterized by org_id passed as argument; never bare asset queries
"""
import asyncio
import logging
import os
import tempfile
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session_factory
from app.models.creative import CreativeAsset
from app.services.sync.job_tracker import create_background_job, update_background_job
from app.services.sync.video_utils import get_video_duration
from app.services.object_storage import get_object_storage

logger = logging.getLogger(__name__)


async def has_null_duration_assets(db: AsyncSession, org_id: uuid.UUID) -> int:
    """Return count of VIDEO assets in org with NULL video_duration AND non-null asset_url.

    Cheap gate used by scheduler.py to decide whether to dispatch a backfill job.
    T-23-03: org_id is the only scoping mechanism — caller is responsible for passing
    the correct organization_id (typically connection.organization_id).
    """
    q = select(func.count(CreativeAsset.id)).where(
        CreativeAsset.organization_id == org_id,
        CreativeAsset.asset_format == "VIDEO",
        CreativeAsset.video_duration.is_(None),
        CreativeAsset.asset_url.isnot(None),
    )
    return (await db.execute(q)).scalar() or 0


async def run_duration_backfill(org_id: uuid.UUID, batch_size: int = 100) -> None:
    """Backfill video_duration for NULL-duration VIDEO assets in the given org.

    Called at the end of each sync run (D-09) if any NULL-duration assets exist.
    Processes in batches of 100 to avoid CPU spikes from ffprobe (D-11).

    Args:
        org_id: Organization UUID — sourced from connection.organization_id (trusted, server-side)
        batch_size: Number of assets per batch (default 100 per D-11)
    """
    job_id = await create_background_job(
        job_type="duration_backfill",
        org_id=org_id,
        metadata={"triggered_at": datetime.utcnow().isoformat()},
    )

    try:
        async with get_session_factory()() as db:
            # Compute total NULL-duration VIDEO assets for this org (T-23-03)
            total_q = select(func.count(CreativeAsset.id)).where(
                CreativeAsset.organization_id == org_id,
                CreativeAsset.asset_format == "VIDEO",
                CreativeAsset.video_duration.is_(None),
                CreativeAsset.asset_url.isnot(None),
            )
            total = (await db.execute(total_q)).scalar() or 0

            if total == 0:
                await update_background_job(
                    job_id,
                    status="COMPLETE",
                    progress_current=0,
                    progress_total=0,
                    output={"processed": 0, "skipped": "no_null_assets"},
                )
                return

            await update_background_job(job_id, status="RUNNING", progress_total=total)

            processed = 0
            failures = 0

            while processed < total:
                # Fetch next batch — T-23-03: always filter by organization_id == org_id
                batch_q = (
                    select(CreativeAsset)
                    .where(
                        CreativeAsset.organization_id == org_id,
                        CreativeAsset.asset_format == "VIDEO",
                        CreativeAsset.video_duration.is_(None),
                        CreativeAsset.asset_url.isnot(None),
                    )
                    .limit(batch_size)
                )
                result = await db.execute(batch_q)
                assets = result.scalars().all()

                if not assets:
                    break

                for asset in assets:
                    try:
                        asset_url = asset.asset_url
                        # Derive s3_key using same pattern as scoring_job.py:429-431 (T-23-09)
                        s3_key = asset_url.lstrip("/")
                        if s3_key.startswith("objects/"):
                            s3_key = s3_key[len("objects/"):]

                        try:
                            file_bytes, _ = await asyncio.to_thread(
                                get_object_storage().download_blob, s3_key
                            )
                        except Exception as e:
                            logger.warning(
                                "Backfill download failed for asset %s (key=%s): %s",
                                asset.id, s3_key, e,
                            )
                            failures += 1
                            continue

                        if not file_bytes:
                            logger.warning(
                                "Backfill: empty bytes for asset %s key=%s", asset.id, s3_key
                            )
                            failures += 1
                            continue

                        # Derive suffix from s3_key extension or default to .mp4
                        suffix = os.path.splitext(s3_key)[1] or ".mp4"

                        # Write to temp file, extract duration, then clean up
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                        try:
                            tmp.write(file_bytes)
                            tmp.flush()
                            tmp.close()
                            duration = await asyncio.to_thread(get_video_duration, tmp.name)
                        finally:
                            try:
                                os.unlink(tmp.name)
                            except OSError:
                                pass

                        if duration is not None:
                            asset.video_duration = duration
                        else:
                            logger.warning(
                                "Backfill: ffprobe returned None for asset %s", asset.id
                            )
                            failures += 1

                    except Exception as e:
                        # Per Pitfall 4: log per-asset failures with asset.id; never abort job
                        logger.warning(
                            "Backfill failed for asset %s: %s", asset.id, e
                        )
                        failures += 1
                        continue

                # Commit per batch — proves incremental progress
                await db.commit()
                processed += len(assets)
                await update_background_job(job_id, progress_current=processed)

        await update_background_job(
            job_id,
            status="COMPLETE",
            output={"processed": processed, "failures": failures},
        )

    except Exception as e:
        logger.error("Duration backfill failed for org %s: %s", org_id, e, exc_info=True)
        await update_background_job(
            job_id,
            status="FAILED",
            error={"type": type(e).__name__, "message": str(e)},
        )
