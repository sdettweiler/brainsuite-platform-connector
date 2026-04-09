"""Scoring endpoints — rescore trigger, status polling, score detail, refetch."""
from typing import List, Optional
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
import uuid

from app.db.base import get_db, get_session_factory
from app.models.user import User
from app.models.scoring import CreativeScoreResult
from app.models.creative import CreativeAsset
from app.api.v1.deps import get_current_user, get_current_admin
from app.services.brainsuite_score import (
    brainsuite_score_service,
    extract_score_data,
    persist_and_replace_visualizations,
)
from app.services.sync.scoring_job import score_asset_now, run_backfill_task

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/admin/backfill", status_code=202)
async def admin_backfill_scoring(
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin),
):
    """Queue all UNSCORED assets (cross-tenant) for the live scoring pipeline.

    Returns immediately with a count of assets queued.
    Progress is visible per-asset in the dashboard.
    """
    async with get_session_factory()() as db:
        result = await db.execute(
            select(func.count(CreativeScoreResult.id))
            .where(
                CreativeScoreResult.scoring_status == "UNSCORED",
                CreativeScoreResult.endpoint_type.in_(["VIDEO", "STATIC_IMAGE"]),
            )
        )
        assets_queued = result.scalar_one()

    background_tasks.add_task(run_backfill_task)
    logger.info(
        "admin_backfill_scoring: queuing %d UNSCORED assets (requested by user %s)",
        assets_queued,
        current_admin.id,
    )
    return {"status": "backfill_started", "assets_queued": assets_queued}


@router.post("/{asset_id}/rescore")
async def rescore_asset(
    asset_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger immediate scoring for an asset (runs in background, does not wait for scheduler)."""
    result = await db.execute(
        select(CreativeAsset).where(
            CreativeAsset.id == asset_id,
            CreativeAsset.organization_id == current_user.organization_id,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    score_result = await db.execute(
        select(CreativeScoreResult).where(
            CreativeScoreResult.creative_asset_id == asset_id
        )
    )
    score_record = score_result.scalar_one_or_none()

    if score_record is None:
        score_record = CreativeScoreResult(
            creative_asset_id=asset_id,
            organization_id=current_user.organization_id,
            scoring_status="PENDING",
            endpoint_type=None,
        )
        db.add(score_record)
    else:
        if score_record.endpoint_type == "UNSUPPORTED":
            raise HTTPException(
                status_code=422,
                detail="Asset type is not supported for scoring (endpoint_type=UNSUPPORTED)",
            )
        if score_record.scoring_status in ("PENDING", "PROCESSING"):
            return {"status": "already_in_progress", "asset_id": str(asset_id)}
        score_record.scoring_status = "PENDING"
        score_record.error_reason = None
        score_record.brainsuite_job_id = None
        score_record.updated_at = datetime.now(timezone.utc)

    await db.flush()
    score_id = score_record.id
    await db.commit()

    background_tasks.add_task(score_asset_now, score_id)
    logger.info("rescore_asset: queued immediate scoring for asset %s (score_id=%s)", asset_id, score_id)
    return {"status": "scoring_started", "asset_id": str(asset_id)}


@router.get("/status")
async def get_scoring_status(
    asset_ids: str = Query(..., description="Comma-separated asset UUIDs"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current scoring_status and total_score for a batch of assets."""
    # Parse and validate asset_ids
    raw_ids = [s.strip() for s in asset_ids.split(",") if s.strip()]
    if not raw_ids:
        raise HTTPException(status_code=400, detail="asset_ids must be a non-empty comma-separated list")

    # Limit to 100 IDs
    raw_ids = raw_ids[:100]

    try:
        parsed_ids = [uuid.UUID(s) for s in raw_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="One or more asset_ids are not valid UUIDs")

    # Query score records for this org
    score_result = await db.execute(
        select(CreativeScoreResult).where(
            CreativeScoreResult.creative_asset_id.in_(parsed_ids),
            CreativeScoreResult.organization_id == current_user.organization_id,
        )
    )
    score_records = score_result.scalars().all()

    # Build a lookup map
    record_map = {str(r.creative_asset_id): r for r in score_records}

    # Build response — include all requested IDs even if no record exists
    items = []
    for asset_id in parsed_ids:
        key = str(asset_id)
        record = record_map.get(key)
        if record:
            items.append({
                "asset_id": key,
                "scoring_status": record.scoring_status,
                "total_score": record.total_score,
                "total_rating": record.total_rating,
            })
        else:
            items.append({
                "asset_id": key,
                "scoring_status": "UNSCORED",
                "total_score": None,
                "total_rating": None,
            })

    return items


@router.get("/{asset_id}")
async def get_score_detail(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return full score detail including score_dimensions for a single asset."""
    # Verify asset belongs to user's org
    asset_result = await db.execute(
        select(CreativeAsset).where(
            CreativeAsset.id == asset_id,
            CreativeAsset.organization_id == current_user.organization_id,
        )
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Query score record
    score_result = await db.execute(
        select(CreativeScoreResult).where(
            CreativeScoreResult.creative_asset_id == asset_id
        )
    )
    score_record = score_result.scalar_one_or_none()

    if not score_record:
        return {"asset_id": str(asset_id), "scoring_status": "UNSCORED"}

    return {
        "asset_id": str(asset_id),
        "scoring_status": score_record.scoring_status,
        "total_score": score_record.total_score,
        "total_rating": score_record.total_rating,
        "score_dimensions": score_record.score_dimensions,
        "error_reason": score_record.error_reason,
        "scored_at": score_record.scored_at.isoformat() if score_record.scored_at else None,
    }


@router.post("/{asset_id}/refetch")
async def refetch_score(
    asset_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-fetch results from the existing BrainSuite job and re-persist visualizations.

    Does NOT re-submit the video — only re-calls GET /{jobId} using the stored
    brainsuite_job_id, downloads all visualization assets to our storage, and
    updates score_dimensions.  Useful for assets scored before visualization
    persistence was added, or to refresh expired visualization links.

    Requires scoring_status to be COMPLETE or FAILED with a stored brainsuite_job_id.
    """
    # Verify asset belongs to user's org
    asset_result = await db.execute(
        select(CreativeAsset).where(
            CreativeAsset.id == asset_id,
            CreativeAsset.organization_id == current_user.organization_id,
        )
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Get score record
    score_result = await db.execute(
        select(CreativeScoreResult).where(
            CreativeScoreResult.creative_asset_id == asset_id
        )
    )
    score_record = score_result.scalar_one_or_none()

    if not score_record:
        raise HTTPException(status_code=404, detail="No score record found for this asset")

    if not score_record.brainsuite_job_id:
        raise HTTPException(
            status_code=400,
            detail="No BrainSuite job ID stored — asset has not been submitted for scoring",
        )

    if score_record.scoring_status not in ("COMPLETE", "FAILED"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot refetch while scoring_status is '{score_record.scoring_status}'",
        )

    background_tasks.add_task(
        _run_refetch_job,
        str(asset_id),
        str(score_record.id),
        score_record.brainsuite_job_id,
    )
    return {"status": "refetch_queued", "asset_id": str(asset_id)}


async def _run_refetch_job(asset_id: str, score_id: str, job_id: str) -> None:
    """Background task: re-fetch BrainSuite job result and persist visualizations."""
    logger.info("Refetch started for asset %s job %s", asset_id, job_id)
    try:
        # Re-fetch the completed job from BrainSuite (returns immediately — already Succeeded)
        result_data = await brainsuite_score_service.poll_job_status(
            job_id, max_polls=3, poll_interval=5
        )

        # Persist visualization URLs before they expire
        raw_output = result_data.get("output", {})
        stored_output = await persist_and_replace_visualizations(raw_output, asset_id)
        result_data_updated = {**result_data, "output": stored_output}

        score_data = extract_score_data(result_data_updated, strip_viz=False)

        async with get_session_factory()() as db:
            score_row = await db.get(CreativeScoreResult, uuid.UUID(score_id))
            if score_row:
                score_row.score_dimensions = score_data["score_dimensions"]
                score_row.updated_at = datetime.now(timezone.utc)
            await db.commit()

        logger.info("Refetch complete for asset %s", asset_id)

    except Exception as exc:
        logger.error("Refetch failed for asset %s job %s: %s: %s", asset_id, job_id, type(exc).__name__, exc, exc_info=True)
