"""BrainSuite scoring batch job — runs via APScheduler every 15 minutes."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.base import get_session_factory
from app.models.creative import CreativeAsset, AssetMetadataValue
from app.models.scoring import CreativeScoreResult
from app.models.metadata import MetadataField
from app.services.brainsuite_score import (
    brainsuite_score_service,
    build_scoring_payload,
    extract_score_data,
    BrainSuiteJobError,
)
from app.services.object_storage import get_object_storage

logger = logging.getLogger(__name__)

BATCH_SIZE = 20


async def run_scoring_batch() -> None:
    """Process up to BATCH_SIZE UNSCORED VIDEO assets and submit to BrainSuite.

    Phase 1: Query batch in one DB session, mark PENDING, release session.
    Phase 2: For each asset, generate signed URL, submit job, poll, store result.
             NO DB session is held during HTTP calls.
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
                CreativeAsset.asset_format == "VIDEO",
            )
            .order_by(CreativeScoreResult.created_at.asc())
            .limit(BATCH_SIZE)
        )
        rows = result.all()

        if not rows:
            logger.info("Scoring batch: no UNSCORED VIDEO assets found, exiting")
            return

        for score_row, asset_row in rows:
            batch.append({
                "score_id": score_row.id,
                "asset_id": asset_row.id,
                "asset": asset_row,
            })
            score_row.scoring_status = "PENDING"

        await db.commit()

    logger.info("Scoring batch: found %d assets to score, marked PENDING", len(batch))

    # -----------------------------------------------------------------------
    # Phase 2: Process each asset — NO session held during HTTP calls
    # -----------------------------------------------------------------------
    for item in batch:
        score_id = item["score_id"]
        asset = item["asset"]
        asset_id = item["asset_id"]

        try:
            # Build S3 key from asset_url
            asset_url = asset.asset_url
            if not asset_url:
                raise ValueError("No S3 asset URL available")

            s3_key = asset_url.lstrip("/")
            if s3_key.startswith("objects/"):
                s3_key = s3_key[len("objects/"):]

            # Generate a fresh signed URL (no DB session needed)
            signed_url = get_object_storage().generate_signed_url(s3_key, ttl_sec=3600)
            if not signed_url:
                raise ValueError("Failed to generate signed S3 URL")

            # Load metadata for this asset (new short-lived DB session)
            metadata_dict: dict[str, str] = {}
            async with get_session_factory()() as db:
                meta_result = await db.execute(
                    select(MetadataField.name, AssetMetadataValue.value)
                    .join(AssetMetadataValue, AssetMetadataValue.field_id == MetadataField.id)
                    .where(
                        AssetMetadataValue.asset_id == asset_id,
                        MetadataField.name.like("brainsuite_%"),
                    )
                )
                for field_name, field_value in meta_result.all():
                    if field_value is not None:
                        metadata_dict[field_name] = field_value

            # Build BrainSuite payload
            asset_name = asset.ad_name or f"{asset_id}.mp4"
            payload = build_scoring_payload(
                asset_name=asset_name,
                signed_url=signed_url,
                platform=asset.platform,
                placement=asset.placement,
                metadata=metadata_dict,
            )

            # Submit job (no DB session held)
            job_response = await brainsuite_score_service.create_job_with_retry(payload)

            # Extract job ID — BrainSuite returns "id" or "jobId"
            job_id = job_response.get("id") or job_response.get("jobId")
            if not job_id:
                raise ValueError(f"BrainSuite response missing job ID: {job_response}")

            # Mark PROCESSING
            async with get_session_factory()() as db:
                score_row = await db.get(CreativeScoreResult, score_id)
                if score_row:
                    score_row.brainsuite_job_id = str(job_id)
                    score_row.scoring_status = "PROCESSING"
                    score_row.updated_at = datetime.now(timezone.utc)
                await db.commit()

            logger.info("Scoring job submitted for asset %s, job_id=%s", asset_id, job_id)

            # Poll for completion (no DB session held — may take several minutes)
            result_data = await brainsuite_score_service.poll_job_status(str(job_id))

            # Extract score
            score_data = extract_score_data(result_data)

            # Write results
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

            logger.info(
                "Scoring complete for asset %s: score=%.1f rating=%s",
                asset_id,
                score_data["total_score"],
                score_data["total_rating"],
            )

        except BrainSuiteJobError as exc:
            error_reason = str(exc)[:500]
            logger.warning("BrainSuite job error for asset %s: %s", asset_id, error_reason)
            await _mark_failed(score_id, error_reason)

        except Exception as exc:
            error_reason = f"{type(exc).__name__}: {str(exc)[:500]}"
            logger.error(
                "Unexpected error scoring asset %s: %s",
                asset_id,
                error_reason,
                exc_info=True,
            )
            await _mark_failed(score_id, error_reason)


async def _mark_failed(score_id, error_reason: str) -> None:
    """Mark a CreativeScoreResult as FAILED with the given error_reason."""
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
