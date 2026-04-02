"""BrainSuite scoring batch job — runs via APScheduler every 15 minutes.

Public API:
  run_scoring_batch()   — batch scheduler entry point (called by APScheduler)
  score_asset_now(score_id) — score a single asset immediately (called by rescore endpoint)

Batch execution model:
  Phase 1 — fetch up to BATCH_SIZE UNSCORED assets, mark PENDING (single DB session).
  Phase 2 — submit all assets to BrainSuite concurrently via asyncio.gather.
  Phase 3 — poll all submitted jobs concurrently via asyncio.gather.
             Each job polls indefinitely: 30s interval for the first 30 min,
             then 90s until BrainSuite returns a terminal status (Succeeded/Failed/Stale).
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.base import get_session_factory
from app.models.creative import CreativeAsset, AssetMetadataValue
from app.models.scoring import CreativeScoreResult
from app.models.metadata import MetadataField
from app.services.brainsuite_score import (
    brainsuite_score_service,
    build_scoring_payload,
    extract_score_data,
    persist_and_replace_visualizations,
)
from app.services.brainsuite_exceptions import BrainSuiteJobError
from app.services.brainsuite_static_score import (
    brainsuite_static_score_service,
    build_static_scoring_payload,
)
from app.services.object_storage import get_object_storage

logger = logging.getLogger(__name__)

BATCH_SIZE = 20


async def run_scoring_batch() -> int:
    """Process up to BATCH_SIZE UNSCORED VIDEO and IMAGE assets and submit to BrainSuite.

    Routes each asset to the correct BrainSuite service based on endpoint_type:
      - VIDEO        → BrainSuiteScoreService (ACE_VIDEO_SMV_API)
      - STATIC_IMAGE → BrainSuiteStaticScoreService (ACE_STATIC_SOCIAL_STATIC_API)
      - UNSUPPORTED  → excluded from query (scoring_status=UNSUPPORTED, not UNSCORED)

    Phase 1: Query batch in one DB session, mark PENDING, release session.
    Phase 2: For each asset, download from internal storage, submit via the
             announce→upload→start flow, poll, store result.
             NO DB session is held during HTTP calls.
    Phase 3: Count remaining UNSCORED assets and return the count so the
             scheduler can adapt its interval (fast mode when queue is non-empty).

    Returns:
        Number of UNSCORED assets remaining after this batch (0 = queue drained).
    """
    logger.info("Starting scoring batch run")

    # -----------------------------------------------------------------------
    # Phase 1: Fetch batch and mark PENDING (single DB session, then release)
    # -----------------------------------------------------------------------
    batch = []
    async with get_session_factory()() as db:
        result = await db.execute(
            select(CreativeScoreResult, CreativeAsset)
            .join(CreativeAsset, CreativeAsset.id == CreativeScoreResult.creative_asset_id)
            .where(
                CreativeScoreResult.scoring_status == "UNSCORED",
                CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"]),
            )
            .order_by(CreativeScoreResult.created_at.asc())
            .limit(BATCH_SIZE)
        )
        rows = result.all()

        if not rows:
            logger.info("Scoring batch: no UNSCORED VIDEO or STATIC_IMAGE assets found, exiting")
            return 0

        for score_row, asset_row in rows:
            batch.append({
                "score_id": score_row.id,
                "asset_id": asset_row.id,
                "asset": asset_row,
                "endpoint_type": score_row.endpoint_type,
            })
            score_row.scoring_status = "PENDING"
            score_row.pending_at = datetime.now(timezone.utc)

        await db.commit()

    logger.info("Scoring batch: found %d assets to score, marked PENDING", len(batch))

    # -----------------------------------------------------------------------
    # Phase 2: Submit all assets to BrainSuite concurrently
    # -----------------------------------------------------------------------
    submit_results = await asyncio.gather(
        *[_submit_asset(item["score_id"], item["asset"], item["endpoint_type"]) for item in batch],
        return_exceptions=False,
    )

    # Build poll list — only assets that were successfully submitted (job_id not None)
    poll_items = [
        (item["score_id"], job_id, item["endpoint_type"])
        for item, job_id in zip(batch, submit_results)
        if job_id is not None
    ]
    logger.info(
        "Scoring batch: %d/%d assets submitted successfully, starting concurrent polling",
        len(poll_items), len(batch),
    )

    # -----------------------------------------------------------------------
    # Phase 3: Poll all submitted jobs concurrently
    # -----------------------------------------------------------------------
    if poll_items:
        await asyncio.gather(
            *[_poll_asset(score_id, job_id, endpoint_type) for score_id, job_id, endpoint_type in poll_items],
        )

    # -----------------------------------------------------------------------
    # Phase 3: Count remaining UNSCORED assets for adaptive scheduling
    # -----------------------------------------------------------------------
    from sqlalchemy import func as sa_func
    async with get_session_factory()() as db:
        remaining_result = await db.execute(
            select(sa_func.count()).select_from(CreativeScoreResult).where(
                CreativeScoreResult.scoring_status == "UNSCORED",
                CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"]),
            )
        )
        remaining = remaining_result.scalar() or 0

    logger.info("Scoring batch complete: %d UNSCORED assets remaining in queue", remaining)
    return remaining


async def score_asset_now(score_id: uuid.UUID) -> None:
    """Score a single asset immediately — called by the rescore endpoint.

    Loads the score row + asset from DB, marks PENDING, then delegates to
    _process_asset(). Designed to run as a FastAPI BackgroundTask.
    """
    logger.info("score_asset_now: loading score_id=%s", score_id)
    async with get_session_factory()() as db:
        result = await db.execute(
            select(CreativeScoreResult, CreativeAsset)
            .join(CreativeAsset, CreativeAsset.id == CreativeScoreResult.creative_asset_id)
            .where(CreativeScoreResult.id == score_id)
        )
        row = result.one_or_none()

    if not row:
        logger.error("score_asset_now: score_id=%s not found", score_id)
        return

    score_row, asset = row
    endpoint_type = score_row.endpoint_type

    if endpoint_type == "UNSUPPORTED":
        logger.warning(
            "score_asset_now: asset %s is UNSUPPORTED, skipping",
            score_row.creative_asset_id,
        )
        return

    if endpoint_type not in ("VIDEO", "STATIC_IMAGE"):
        logger.error(
            "score_asset_now: unknown endpoint_type=%s for score_id=%s",
            endpoint_type,
            score_id,
        )
        return

    # Mark PENDING before handing off (same as batch does before processing)
    async with get_session_factory()() as db:
        row2 = await db.get(CreativeScoreResult, score_id)
        if row2:
            row2.scoring_status = "PENDING"
            row2.pending_at = datetime.now(timezone.utc)
            row2.error_reason = None
            await db.commit()

    job_id = await _submit_asset(score_id, asset, endpoint_type)
    if job_id is not None:
        await _poll_asset(score_id, job_id, endpoint_type)


async def _submit_asset(score_id, asset: CreativeAsset, endpoint_type: str) -> str | None:
    """Download asset and submit to BrainSuite. Returns job_id string on success, None on failure."""
    asset_id = asset.id
    logger.info("Submitting asset %s: endpoint_type=%s platform=%s", asset_id, endpoint_type, getattr(asset, "platform", "?"))
    try:
        asset_url = asset.asset_url
        if not asset_url:
            raise ValueError("No S3 asset URL available")

        s3_key = asset_url.lstrip("/")
        if s3_key.startswith("objects/"):
            s3_key = s3_key[len("objects/"):]

        file_bytes, _ = get_object_storage().download_blob(s3_key)
        if not file_bytes:
            raise ValueError(f"Asset not found in object storage: {s3_key}")
        logger.info("Asset %s: downloaded %d bytes", asset_id, len(file_bytes))

        metadata_dict: dict[str, str] = {}
        async with get_session_factory()() as db:
            meta_result = await db.execute(
                select(MetadataField.name, AssetMetadataValue.value)
                .join(AssetMetadataValue, AssetMetadataValue.field_id == MetadataField.id)
                .where(AssetMetadataValue.asset_id == asset_id, MetadataField.name.like("brainsuite_%"))
            )
            for field_name, field_value in meta_result.all():
                if field_value is not None:
                    metadata_dict[field_name] = field_value

        filename = os.path.basename(s3_key) or (asset.ad_name or f"{asset_id}")

        if endpoint_type == "VIDEO":
            job_id = await brainsuite_score_service.submit_job_with_upload(
                file_bytes=file_bytes,
                filename=filename,
                briefing_data=build_scoring_payload(asset_name=filename, platform=asset.platform, placement=asset.placement, metadata=metadata_dict),
            )
        else:
            job_id = await brainsuite_static_score_service.submit_job_with_upload(
                file_bytes=file_bytes,
                filename=filename,
                announce_payload=build_static_scoring_payload(asset_name=filename, platform=asset.platform, placement=asset.placement, metadata=metadata_dict),
            )

        async with get_session_factory()() as db:
            score_row = await db.get(CreativeScoreResult, score_id)
            if score_row:
                score_row.brainsuite_job_id = str(job_id)
                score_row.scoring_status = "PROCESSING"
                score_row.submitted_at = datetime.now(timezone.utc)
                score_row.updated_at = datetime.now(timezone.utc)
            await db.commit()

        logger.info("Asset %s submitted: job_id=%s", asset_id, job_id)
        return str(job_id)

    except BrainSuiteJobError as exc:
        logger.warning("Submit failed for asset %s: %s", asset_id, exc)
        await _mark_failed(score_id, str(exc)[:500])
        return None
    except Exception as exc:
        error_reason = f"{type(exc).__name__}: {str(exc)[:500]}"
        logger.error("Unexpected submit error for asset %s: %s", asset_id, error_reason, exc_info=True)
        await _mark_failed(score_id, error_reason)
        return None


async def _poll_asset(score_id, job_id: str, endpoint_type: str) -> None:
    """Poll a submitted BrainSuite job to completion and persist the result."""
    logger.info("Polling job_id=%s (score_id=%s)", job_id, score_id)
    try:
        if endpoint_type == "VIDEO":
            result_data = await brainsuite_score_service.poll_job_status(job_id)
            asset_id_result = await _get_asset_id(score_id)
        else:
            result_data = await brainsuite_static_score_service.poll_job_status(job_id)
            asset_id_result = await _get_asset_id(score_id)

        raw_output = result_data.get("output", {})
        stored_output = await persist_and_replace_visualizations(raw_output, str(asset_id_result))
        score_data = extract_score_data({**result_data, "output": stored_output}, strip_viz=False)

        async with get_session_factory()() as db:
            score_row = await db.get(CreativeScoreResult, score_id)
            if score_row:
                score_row.total_score = score_data["total_score"]
                score_row.total_rating = score_data["total_rating"]
                score_row.score_dimensions = score_data["score_dimensions"]
                score_row.scoring_status = "COMPLETE"
                score_row.scored_at = datetime.now(timezone.utc)
                score_row.updated_at = datetime.now(timezone.utc)
            await db.commit()

        logger.info("Scoring complete for job_id=%s: score=%.1f rating=%s", job_id, score_data["total_score"], score_data["total_rating"])

    except BrainSuiteJobError as exc:
        error_reason = str(exc)[:500]
        logger.warning("BrainSuite job error for job_id=%s: %s", job_id, error_reason)
        await _mark_failed(score_id, error_reason)

    except Exception as exc:
        error_reason = f"{type(exc).__name__}: {str(exc)[:500]}"
        logger.error("Unexpected poll error for job_id=%s: %s", job_id, error_reason, exc_info=True)
        await _mark_failed(score_id, error_reason)


async def _get_asset_id(score_id) -> uuid.UUID:
    """Fetch the creative_asset_id for a score record."""
    async with get_session_factory()() as db:
        row = await db.get(CreativeScoreResult, score_id)
        return row.creative_asset_id


async def run_backfill_task() -> None:
    """Queue all UNSCORED VIDEO and STATIC_IMAGE assets cross-tenant via score_asset_now().

    Designed to run as a FastAPI BackgroundTask.
    Fetches all UNSCORED score IDs in a single session (then releases),
    then iterates without holding a DB connection during HTTP calls.
    """
    logger.info("Backfill task started")

    score_ids: list[uuid.UUID] = []
    async with get_session_factory()() as db:
        result = await db.execute(
            select(CreativeScoreResult.id)
            .where(
                CreativeScoreResult.scoring_status == "UNSCORED",
                CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"]),
            )
            .order_by(CreativeScoreResult.created_at.asc())
        )
        score_ids = list(result.scalars().all())

    logger.info("Backfill task: found %d UNSCORED assets to score", len(score_ids))

    scored = 0
    failed = 0
    for score_id in score_ids:
        try:
            await score_asset_now(score_id)
            scored += 1
        except Exception as exc:
            failed += 1
            logger.error(
                "Backfill: unexpected error for score_id=%s: %s",
                score_id,
                exc,
                exc_info=True,
            )

    logger.info(
        "Backfill task complete: %d scored, %d failed out of %d total",
        scored,
        failed,
        len(score_ids),
    )


async def _mark_failed(score_id, error_reason: str) -> None:
    """Mark a CreativeScoreResult as FAILED with the given error_reason."""
    logger.info("Marking score_id=%s as FAILED: %s", score_id, error_reason[:200])
    try:
        async with get_session_factory()() as db:
            score_row = await db.get(CreativeScoreResult, score_id)
            if score_row:
                score_row.scoring_status = "FAILED"
                score_row.error_reason = error_reason
                score_row.updated_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception as exc:
        logger.error(
            "Failed to mark score record %s as FAILED: %s",
            score_id,
            exc,
        )
