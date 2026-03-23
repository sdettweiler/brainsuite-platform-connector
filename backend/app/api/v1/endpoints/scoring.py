"""Scoring endpoints — rescore trigger, status polling, score detail."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import uuid

from app.db.base import get_db
from app.models.user import User
from app.models.scoring import CreativeScoreResult
from app.models.creative import CreativeAsset
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.post("/{asset_id}/rescore")
async def rescore_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset asset scoring_status to UNSCORED to trigger re-scoring on next batch run."""
    # Verify asset exists and belongs to user's org
    result = await db.execute(
        select(CreativeAsset).where(
            CreativeAsset.id == asset_id,
            CreativeAsset.organization_id == current_user.organization_id,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Query existing score record
    score_result = await db.execute(
        select(CreativeScoreResult).where(
            CreativeScoreResult.creative_asset_id == asset_id
        )
    )
    score_record = score_result.scalar_one_or_none()

    if score_record is None:
        # Create a new UNSCORED record
        score_record = CreativeScoreResult(
            creative_asset_id=asset_id,
            organization_id=current_user.organization_id,
            scoring_status="UNSCORED",
        )
        db.add(score_record)
    else:
        # Reset to UNSCORED
        score_record.scoring_status = "UNSCORED"
        score_record.error_reason = None
        score_record.brainsuite_job_id = None
        score_record.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return {"status": "queued", "asset_id": str(asset_id)}


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
