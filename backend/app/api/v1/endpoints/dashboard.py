"""
Dashboard and performance data endpoints.
All monetary values returned in organization currency.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text, case
from sqlalchemy.orm import selectinload
import uuid

from app.db.base import get_db
from app.models.user import User
from app.models.creative import CreativeAsset, AssetMetadataValue, AssetProjectMapping
from app.models.performance import HarmonizedPerformance
from app.schemas.creative import (
    DashboardFilterParams, DashboardStats, CreativeAssetResponse,
    AssetDetailResponse, ComparisonRequest,
)
from app.api.v1.deps import get_current_user
from app.services.ace_score import get_performer_tag

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    platforms: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate stats for dashboard header — with period comparison."""
    if not date_from:
        date_from = date.today() - timedelta(days=30)
    if not date_to:
        date_to = date.today() - timedelta(days=1)

    period_days = (date_to - date_from).days + 1
    prev_from = date_from - timedelta(days=period_days)
    prev_to = date_from - timedelta(days=1)

    platform_list = [p.strip().upper() for p in platforms.split(",")] if platforms else None

    async def get_stats(df: date, dt: date):
        base = select(
            func.coalesce(func.sum(HarmonizedPerformance.spend), 0).label("total_spend"),
            func.coalesce(func.sum(HarmonizedPerformance.impressions), 0).label("total_impressions"),
            func.avg(HarmonizedPerformance.roas).label("avg_roas"),
        ).join(
            CreativeAsset, CreativeAsset.id == HarmonizedPerformance.asset_id
        ).where(
            CreativeAsset.organization_id == current_user.organization_id,
            HarmonizedPerformance.report_date >= df,
            HarmonizedPerformance.report_date <= dt,
        )
        if platform_list:
            base = base.where(HarmonizedPerformance.platform.in_(platform_list))
        return (await db.execute(base)).one()

    async def count_assets(df: date, dt: date):
        q = select(func.count(func.distinct(HarmonizedPerformance.asset_id))).join(
            CreativeAsset, CreativeAsset.id == HarmonizedPerformance.asset_id
        ).where(
            CreativeAsset.organization_id == current_user.organization_id,
            HarmonizedPerformance.report_date >= df,
            HarmonizedPerformance.report_date <= dt,
        )
        return (await db.execute(q)).scalar() or 0

    curr = await get_stats(date_from, date_to)
    prev = await get_stats(prev_from, prev_to)
    curr_assets = await count_assets(date_from, date_to)
    prev_assets = await count_assets(prev_from, prev_to)

    # New assets in period = assets with first_seen_at in period
    new_q = select(func.count(CreativeAsset.id)).where(
        CreativeAsset.organization_id == current_user.organization_id,
        CreativeAsset.first_seen_at >= date_from,
        CreativeAsset.first_seen_at <= date_to,
    )
    new_assets = (await db.execute(new_q)).scalar() or 0

    return DashboardStats(
        total_spend=curr.total_spend or Decimal(0),
        total_impressions=int(curr.total_impressions or 0),
        avg_roas=float(curr.avg_roas) if curr.avg_roas else None,
        total_active_assets=curr_assets,
        new_assets_in_period=new_assets,
        prev_total_spend=prev.total_spend,
        prev_total_impressions=int(prev.total_impressions or 0),
        prev_avg_roas=float(prev.avg_roas) if prev.avg_roas else None,
        prev_total_active_assets=prev_assets,
    )


@router.get("/assets", response_model=dict)
async def get_dashboard_assets(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    platforms: Optional[str] = Query(default=None),
    formats: Optional[str] = Query(default=None),
    objectives: Optional[str] = Query(default=None),
    project_id: Optional[uuid.UUID] = Query(default=None),
    sort_by: str = Query(default="spend"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=250),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated creative assets with aggregated performance for date range."""
    if not date_from:
        date_from = date.today() - timedelta(days=30)
    if not date_to:
        date_to = date.today() - timedelta(days=1)

    platform_list = [p.strip().upper() for p in platforms.split(",")] if platforms else None
    format_list = [f.strip().upper() for f in formats.split(",")] if formats else None
    objective_list = [o.strip() for o in objectives.split(",")] if objectives else None

    # Aggregate performance per asset for the date range
    perf_subq = (
        select(
            HarmonizedPerformance.asset_id,
            func.sum(HarmonizedPerformance.spend).label("total_spend"),
            func.sum(HarmonizedPerformance.impressions).label("total_impressions"),
            func.sum(HarmonizedPerformance.clicks).label("total_clicks"),
            (
                func.sum(HarmonizedPerformance.clicks) /
                func.nullif(func.sum(HarmonizedPerformance.impressions), 0) * 100
            ).label("avg_ctr"),
            (
                func.sum(HarmonizedPerformance.spend) /
                func.nullif(func.sum(HarmonizedPerformance.impressions), 0) * 1000
            ).label("avg_cpm"),
            func.sum(HarmonizedPerformance.conversions).label("total_conversions"),
            func.sum(HarmonizedPerformance.conversion_value).label("total_conversion_value"),
            (
                func.sum(HarmonizedPerformance.conversion_value) /
                func.nullif(func.sum(HarmonizedPerformance.spend), 0)
            ).label("roas"),
            func.sum(HarmonizedPerformance.video_views).label("total_video_views"),
            func.avg(HarmonizedPerformance.vtr).label("avg_vtr"),
        )
        .where(
            HarmonizedPerformance.report_date >= date_from,
            HarmonizedPerformance.report_date <= date_to,
        )
        .group_by(HarmonizedPerformance.asset_id)
        .subquery()
    )

    # Main asset query
    query = (
        select(CreativeAsset, perf_subq)
        .outerjoin(perf_subq, perf_subq.c.asset_id == CreativeAsset.id)
        .where(CreativeAsset.organization_id == current_user.organization_id)
    )

    if platform_list:
        query = query.where(CreativeAsset.platform.in_(platform_list))
    if format_list:
        query = query.where(CreativeAsset.asset_format.in_(format_list))
    if objective_list:
        query = query.where(CreativeAsset.campaign_objective.in_(objective_list))
    if project_id:
        query = query.join(
            AssetProjectMapping,
            and_(
                AssetProjectMapping.asset_id == CreativeAsset.id,
                AssetProjectMapping.project_id == project_id,
            )
        )

    # Only assets with performance in period
    query = query.where(perf_subq.c.total_spend.isnot(None))

    # Sorting
    sort_col_map = {
        "spend": perf_subq.c.total_spend,
        "impressions": perf_subq.c.total_impressions,
        "ctr": perf_subq.c.avg_ctr,
        "cpm": perf_subq.c.avg_cpm,
        "roas": perf_subq.c.roas,
        "vtr": perf_subq.c.avg_vtr,
        "platform": CreativeAsset.platform,
        "format": CreativeAsset.asset_format,
        "ace_score": CreativeAsset.ace_score,
    }
    sort_col = sort_col_map.get(sort_by, perf_subq.c.total_spend)
    if sort_order.lower() == "desc":
        query = query.order_by(sort_col.desc().nullslast())
    else:
        query = query.order_by(sort_col.asc().nullsfirst())

    # Count total
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    assets_out = []
    for row in rows:
        asset = row[0]
        perf = {
            "spend": row.total_spend,
            "impressions": row.total_impressions,
            "clicks": row.total_clicks,
            "ctr": float(row.avg_ctr) if row.avg_ctr else None,
            "cpm": row.avg_cpm,
            "conversions": row.total_conversions,
            "conversion_value": row.total_conversion_value,
            "roas": float(row.roas) if row.roas else None,
            "video_views": row.total_video_views,
            "vtr": float(row.avg_vtr) if row.avg_vtr else None,
        }
        performer_tag = get_performer_tag(
            asset.ace_score,
            float(perf["spend"] or 0),
            perf["roas"],
        )
        assets_out.append({
            "id": str(asset.id),
            "platform": asset.platform,
            "ad_id": asset.ad_id,
            "ad_name": asset.ad_name,
            "campaign_name": asset.campaign_name,
            "campaign_objective": asset.campaign_objective,
            "asset_format": asset.asset_format,
            "thumbnail_url": asset.thumbnail_url,
            "ace_score": asset.ace_score,
            "ace_score_confidence": asset.ace_score_confidence,
            "is_active": asset.is_active,
            "performance": perf,
            "performer_tag": performer_tag,
        })

    return {
        "items": assets_out,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/assets/{asset_id}", response_model=dict)
async def get_asset_detail(
    asset_id: uuid.UUID,
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    kpis: Optional[str] = Query(default=None),  # comma-separated KPI names for chart
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not date_from:
        date_from = date.today() - timedelta(days=30)
    if not date_to:
        date_to = date.today() - timedelta(days=1)

    asset = await db.get(CreativeAsset, asset_id)
    if not asset or asset.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Get metadata values
    meta_result = await db.execute(
        select(AssetMetadataValue).where(AssetMetadataValue.asset_id == asset_id)
    )
    meta_values = {str(v.field_id): v.value for v in meta_result.scalars().all()}

    # Get projects
    proj_result = await db.execute(
        select(AssetProjectMapping).where(AssetProjectMapping.asset_id == asset_id)
    )
    project_ids = [str(p.project_id) for p in proj_result.scalars().all()]

    # Aggregate performance
    perf_result = await db.execute(
        select(
            func.sum(HarmonizedPerformance.spend).label("spend"),
            func.sum(HarmonizedPerformance.impressions).label("impressions"),
            func.sum(HarmonizedPerformance.clicks).label("clicks"),
            func.avg(HarmonizedPerformance.ctr).label("ctr"),
            func.avg(HarmonizedPerformance.cpm).label("cpm"),
            func.sum(HarmonizedPerformance.conversions).label("conversions"),
            func.sum(HarmonizedPerformance.conversion_value).label("conversion_value"),
            func.avg(HarmonizedPerformance.cvr).label("cvr"),
            func.avg(HarmonizedPerformance.roas).label("roas"),
            func.sum(HarmonizedPerformance.video_views).label("video_views"),
            func.avg(HarmonizedPerformance.vtr).label("vtr"),
            func.count(func.distinct(HarmonizedPerformance.campaign_id)).label("campaigns_count"),
        ).where(
            HarmonizedPerformance.asset_id == asset_id,
            HarmonizedPerformance.report_date >= date_from,
            HarmonizedPerformance.report_date <= date_to,
        )
    )
    perf = perf_result.one()

    # Timeseries data
    kpi_list = [k.strip() for k in kpis.split(",")] if kpis else ["spend", "ctr", "roas"]
    kpi_list = kpi_list[:3]  # Max 3 KPIs

    ts_result = await db.execute(
        select(
            HarmonizedPerformance.report_date,
            HarmonizedPerformance.spend,
            HarmonizedPerformance.ctr,
            HarmonizedPerformance.roas,
            HarmonizedPerformance.video_views,
            HarmonizedPerformance.vtr,
            HarmonizedPerformance.cpm,
            HarmonizedPerformance.conversions,
            HarmonizedPerformance.cvr,
        ).where(
            HarmonizedPerformance.asset_id == asset_id,
            HarmonizedPerformance.report_date >= date_from,
            HarmonizedPerformance.report_date <= date_to,
        ).order_by(HarmonizedPerformance.report_date)
    )
    ts_rows = ts_result.all()

    timeseries = {k: [] for k in kpi_list}
    for row in ts_rows:
        for kpi in kpi_list:
            val = getattr(row, kpi, None)
            timeseries[kpi].append({
                "date": row.report_date.isoformat(),
                "value": float(val) if val is not None else 0,
            })

    # Campaigns used in
    campaigns_result = await db.execute(
        select(
            HarmonizedPerformance.campaign_id,
            HarmonizedPerformance.campaign_name,
            func.sum(HarmonizedPerformance.spend).label("spend"),
        ).where(
            HarmonizedPerformance.asset_id == asset_id,
            HarmonizedPerformance.report_date >= date_from,
            HarmonizedPerformance.report_date <= date_to,
        ).group_by(
            HarmonizedPerformance.campaign_id,
            HarmonizedPerformance.campaign_name,
        )
    )
    campaigns = [
        {"campaign_id": r.campaign_id, "campaign_name": r.campaign_name, "spend": float(r.spend or 0)}
        for r in campaigns_result.all()
    ]

    return {
        "id": str(asset.id),
        "platform": asset.platform,
        "ad_id": asset.ad_id,
        "ad_name": asset.ad_name,
        "campaign_name": asset.campaign_name,
        "campaign_objective": asset.campaign_objective,
        "asset_format": asset.asset_format,
        "thumbnail_url": asset.thumbnail_url,
        "asset_url": asset.asset_url,
        "video_duration": asset.video_duration,
        "ace_score": asset.ace_score,
        "ace_score_confidence": asset.ace_score_confidence,
        "brainsuite_metadata": asset.brainsuite_metadata,
        "metadata_values": meta_values,
        "projects": project_ids,
        "campaigns_count": int(perf.campaigns_count or 0),
        "campaigns": campaigns,
        "performance": {
            "spend": float(perf.spend or 0),
            "impressions": int(perf.impressions or 0),
            "clicks": int(perf.clicks or 0),
            "ctr": float(perf.ctr or 0),
            "cpm": float(perf.cpm or 0),
            "conversions": int(perf.conversions or 0),
            "conversion_value": float(perf.conversion_value or 0),
            "cvr": float(perf.cvr or 0),
            "roas": float(perf.roas or 0),
            "video_views": int(perf.video_views or 0),
            "vtr": float(perf.vtr or 0),
        },
        "timeseries": timeseries,
    }


@router.get("/homepage-widgets")
async def get_homepage_widgets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Top 5 spending assets per platform for last 7 days (excluding today)."""
    date_to = date.today() - timedelta(days=1)
    date_from = date_to - timedelta(days=6)

    widgets = {}
    for platform in ["META", "TIKTOK", "YOUTUBE"]:
        perf_subq = (
            select(
                HarmonizedPerformance.asset_id,
                func.sum(HarmonizedPerformance.spend).label("total_spend"),
                func.avg(HarmonizedPerformance.ctr).label("avg_ctr"),
            )
            .where(
                HarmonizedPerformance.platform == platform,
                HarmonizedPerformance.report_date >= date_from,
                HarmonizedPerformance.report_date <= date_to,
            )
            .group_by(HarmonizedPerformance.asset_id)
            .order_by(func.sum(HarmonizedPerformance.spend).desc())
            .limit(5)
            .subquery()
        )

        result = await db.execute(
            select(CreativeAsset, perf_subq)
            .join(perf_subq, perf_subq.c.asset_id == CreativeAsset.id)
            .where(CreativeAsset.organization_id == current_user.organization_id)
        )

        widgets[platform.lower()] = [
            {
                "id": str(row[0].id),
                "ad_name": row[0].ad_name,
                "thumbnail_url": row[0].thumbnail_url,
                "ace_score": row[0].ace_score,
                "spend_l7d": float(row.total_spend or 0),
                "ctr": float(row.avg_ctr or 0),
                "asset_format": row[0].asset_format,
            }
            for row in result.all()
        ]

    # Overall stats
    stats_result = await db.execute(
        select(
            func.count(func.distinct(CreativeAsset.id)).label("total_assets"),
            func.count(func.distinct(HarmonizedPerformance.ad_account_id)).label("total_accounts"),
            func.sum(HarmonizedPerformance.spend).label("total_spend"),
        )
        .join(CreativeAsset, CreativeAsset.id == HarmonizedPerformance.asset_id)
        .where(CreativeAsset.organization_id == current_user.organization_id)
    )
    stats = stats_result.one()

    return {
        "widgets": widgets,
        "overall_stats": {
            "total_assets": int(stats.total_assets or 0),
            "total_accounts": int(stats.total_accounts or 0),
            "total_spend": float(stats.total_spend or 0),
        },
        "date_range": {"from": date_from.isoformat(), "to": date_to.isoformat()},
    }


@router.post("/compare")
async def compare_assets(
    payload: ComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return detailed comparison data for 2-4 assets."""
    if len(payload.asset_ids) < 2 or len(payload.asset_ids) > 4:
        raise HTTPException(status_code=400, detail="Provide 2-4 asset IDs for comparison")

    comparison = []
    for asset_id in payload.asset_ids:
        asset = await db.get(CreativeAsset, asset_id)
        if not asset or asset.organization_id != current_user.organization_id:
            continue

        perf_result = await db.execute(
            select(
                func.sum(HarmonizedPerformance.spend).label("spend"),
                func.sum(HarmonizedPerformance.impressions).label("impressions"),
                func.sum(HarmonizedPerformance.clicks).label("clicks"),
                func.avg(HarmonizedPerformance.ctr).label("ctr"),
                func.avg(HarmonizedPerformance.cpm).label("cpm"),
                func.sum(HarmonizedPerformance.conversions).label("conversions"),
                func.avg(HarmonizedPerformance.roas).label("roas"),
                func.sum(HarmonizedPerformance.video_views).label("video_views"),
                func.avg(HarmonizedPerformance.vtr).label("vtr"),
            ).where(
                HarmonizedPerformance.asset_id == asset_id,
                HarmonizedPerformance.report_date >= payload.date_from,
                HarmonizedPerformance.report_date <= payload.date_to,
            )
        )
        perf = perf_result.one()

        # Daily timeseries for comparison chart
        ts_result = await db.execute(
            select(
                HarmonizedPerformance.report_date,
                HarmonizedPerformance.spend,
                HarmonizedPerformance.ctr,
                HarmonizedPerformance.roas,
            ).where(
                HarmonizedPerformance.asset_id == asset_id,
                HarmonizedPerformance.report_date >= payload.date_from,
                HarmonizedPerformance.report_date <= payload.date_to,
            ).order_by(HarmonizedPerformance.report_date)
        )

        comparison.append({
            "id": str(asset.id),
            "ad_name": asset.ad_name,
            "platform": asset.platform,
            "asset_format": asset.asset_format,
            "thumbnail_url": asset.thumbnail_url,
            "ace_score": asset.ace_score,
            "performance": {
                "spend": float(perf.spend or 0),
                "impressions": int(perf.impressions or 0),
                "clicks": int(perf.clicks or 0),
                "ctr": float(perf.ctr or 0),
                "cpm": float(perf.cpm or 0),
                "conversions": int(perf.conversions or 0),
                "roas": float(perf.roas or 0),
                "video_views": int(perf.video_views or 0),
                "vtr": float(perf.vtr or 0),
            },
            "timeseries": [
                {
                    "date": row.report_date.isoformat(),
                    "spend": float(row.spend or 0),
                    "ctr": float(row.ctr or 0),
                    "roas": float(row.roas or 0),
                }
                for row in ts_result.all()
            ],
        })

    return {"assets": comparison, "date_from": payload.date_from, "date_to": payload.date_to}
