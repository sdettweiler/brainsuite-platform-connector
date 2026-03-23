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
from app.models.platform import PlatformConnection
from app.schemas.creative import (
    DashboardFilterParams, DashboardStats, CreativeAssetResponse,
    AssetDetailResponse, ComparisonRequest,
)
from app.api.v1.deps import get_current_user

router = APIRouter()


def _get_performer_tag(
    total_score: Optional[float],
    spend: float,
    roas: Optional[float],
) -> str:
    """Classify asset performance based on BrainSuite total_score."""
    if total_score is None:
        return "Average"
    if total_score >= 70:
        return "Top Performer"
    if total_score >= 45:
        return "Average"
    return "Below Average"


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
            (
                func.sum(HarmonizedPerformance.conversion_value) /
                func.nullif(func.sum(HarmonizedPerformance.spend), 0)
            ).label("avg_roas"),
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
            (
                func.sum(HarmonizedPerformance.video_views) /
                func.nullif(func.sum(HarmonizedPerformance.impressions), 0) * 100
            ).label("avg_vtr"),
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
        performer_tag = _get_performer_tag(
            None,
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
            "asset_url": asset.asset_url,
            "scoring_status": None,
            "total_score": None,
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

    HP = HarmonizedPerformance
    _imp = func.nullif(func.sum(HP.impressions), 0)
    _clk = func.nullif(func.sum(HP.clicks), 0)
    _spd = func.nullif(func.sum(HP.spend), 0)

    perf_result = await db.execute(
        select(
            func.sum(HP.spend).label("spend"),
            func.sum(HP.impressions).label("impressions"),
            func.sum(HP.reach).label("reach"),
            (func.sum(HP.impressions) / func.nullif(func.sum(HP.reach), 0)).label("frequency"),
            func.sum(HP.clicks).label("clicks"),
            (func.sum(HP.clicks) / _imp * 100).label("ctr"),
            (func.sum(HP.spend) / _imp * 1000).label("cpm"),
            (func.sum(HP.spend) / func.nullif(func.sum(HP.reach), 0) * 1000).label("cpp"),
            (func.sum(HP.spend) / _clk).label("cpc"),
            func.sum(HP.outbound_clicks).label("outbound_clicks"),
            (func.sum(HP.outbound_clicks) / _imp * 100).label("outbound_ctr"),
            func.sum(HP.unique_clicks).label("unique_clicks"),
            (func.sum(HP.unique_clicks) / _imp * 100).label("unique_ctr"),
            func.sum(HP.inline_link_clicks).label("inline_link_clicks"),
            (func.sum(HP.inline_link_clicks) / _imp * 100).label("inline_link_click_ctr"),

            func.sum(HP.video_plays).label("video_plays"),
            func.sum(HP.video_views).label("video_views"),
            (func.sum(HP.video_views) / _imp * 100).label("vtr"),
            func.sum(HP.video_3_sec_watched).label("video_3_sec_watched"),
            func.sum(HP.video_30_sec_watched).label("video_30_sec_watched"),
            func.sum(HP.video_p25).label("video_p25"),
            func.sum(HP.video_p50).label("video_p50"),
            func.sum(HP.video_p75).label("video_p75"),
            func.sum(HP.video_p100).label("video_p100"),
            (func.sum(HP.video_p100) / func.nullif(func.sum(HP.video_plays), 0) * 100).label("video_completion_rate"),
            (func.sum(HP.spend) / func.nullif(func.sum(HP.video_views), 0)).label("cost_per_view"),
            func.sum(HP.thruplay).label("thruplay"),
            (func.sum(HP.spend) / func.nullif(func.sum(HP.thruplay), 0)).label("cost_per_thruplay"),
            func.sum(HP.focused_view).label("focused_view"),
            (func.sum(HP.spend) / func.nullif(func.sum(HP.focused_view), 0)).label("cost_per_focused_view"),
            func.sum(HP.trueview_views).label("trueview_views"),

            func.sum(HP.post_engagements).label("post_engagements"),
            func.sum(HP.likes).label("likes"),
            func.sum(HP.comments).label("comments"),
            func.sum(HP.shares).label("shares"),
            func.sum(HP.follows).label("follows"),

            func.sum(HP.conversions).label("conversions"),
            func.sum(HP.conversion_value).label("conversion_value"),
            (func.sum(HP.conversions) / _clk * 100).label("cvr"),
            (func.sum(HP.spend) / func.nullif(func.sum(HP.conversions), 0)).label("cost_per_conversion"),
            (func.sum(HP.conversion_value) / _spd).label("roas"),
            func.sum(HP.purchases).label("purchases"),
            func.sum(HP.purchase_value).label("purchase_value"),
            (func.sum(HP.purchase_value) / _spd).label("purchase_roas"),
            func.sum(HP.leads).label("leads"),
            (func.sum(HP.spend) / func.nullif(func.sum(HP.leads), 0)).label("cost_per_lead"),
            func.sum(HP.app_installs).label("app_installs"),
            (func.sum(HP.spend) / func.nullif(func.sum(HP.app_installs), 0)).label("cost_per_install"),
            func.sum(HP.in_app_purchases).label("in_app_purchases"),
            func.sum(HP.in_app_purchase_value).label("in_app_purchase_value"),
            func.sum(HP.subscribe).label("subscribe"),
            func.sum(HP.offline_purchases).label("offline_purchases"),
            func.sum(HP.offline_purchase_value).label("offline_purchase_value"),
            func.sum(HP.messaging_conversations_started).label("messaging_conversations_started"),
            func.sum(HP.estimated_ad_recallers).label("estimated_ad_recallers"),
            (func.sum(HP.estimated_ad_recallers) / _imp * 100).label("estimated_ad_recall_rate"),

            func.count(func.distinct(HP.campaign_id)).label("campaigns_count"),
        ).where(
            HP.asset_id == asset_id,
            HP.report_date >= date_from,
            HP.report_date <= date_to,
        )
    )
    perf = perf_result.one()

    # Timeseries data
    kpi_list = [k.strip() for k in kpis.split(",")] if kpis else ["spend", "ctr", "roas"]
    kpi_list = kpi_list[:3]  # Max 3 KPIs

    ts_result = await db.execute(
        select(
            HarmonizedPerformance.report_date,
            func.sum(HarmonizedPerformance.spend).label("spend"),
            func.sum(HarmonizedPerformance.impressions).label("impressions"),
            func.sum(HarmonizedPerformance.clicks).label("clicks"),
            func.sum(HarmonizedPerformance.conversions).label("conversions"),
            func.sum(HarmonizedPerformance.conversion_value).label("conversion_value"),
            func.sum(HarmonizedPerformance.video_views).label("video_views"),
        ).where(
            HarmonizedPerformance.asset_id == asset_id,
            HarmonizedPerformance.report_date >= date_from,
            HarmonizedPerformance.report_date <= date_to,
        ).group_by(
            HarmonizedPerformance.report_date,
        ).order_by(HarmonizedPerformance.report_date)
    )
    ts_rows = ts_result.all()

    all_kpis = ["spend", "impressions", "clicks", "ctr", "cpm", "conversions",
                "conversion_value", "cvr", "roas", "video_views", "vtr"]
    timeseries = {k: [] for k in all_kpis}
    for row in ts_rows:
        spend = float(row.spend or 0)
        impressions = float(row.impressions or 0)
        clicks = float(row.clicks or 0)
        conversions = float(row.conversions or 0)
        conversion_value = float(row.conversion_value or 0)
        video_views = float(row.video_views or 0)

        computed = {
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "conversion_value": conversion_value,
            "video_views": video_views,
            "ctr": (clicks / impressions * 100) if impressions else 0,
            "cpm": (spend / impressions * 1000) if impressions else 0,
            "cvr": (conversions / clicks * 100) if clicks else 0,
            "roas": (conversion_value / spend) if spend else 0,
            "vtr": (video_views / impressions * 100) if impressions else 0,
        }

        for kpi in all_kpis:
            timeseries[kpi].append({
                "date": row.report_date.isoformat(),
                "value": computed.get(kpi, 0),
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
        "performance": {k: v for k, v in {
            "spend": float(perf.spend) if perf.spend else None,
            "impressions": int(perf.impressions) if perf.impressions else None,
            "reach": int(perf.reach) if perf.reach else None,
            "frequency": float(perf.frequency) if perf.frequency else None,
            "clicks": int(perf.clicks) if perf.clicks else None,
            "ctr": float(perf.ctr) if perf.ctr else None,
            "cpm": float(perf.cpm) if perf.cpm else None,
            "cpp": float(perf.cpp) if perf.cpp else None,
            "cpc": float(perf.cpc) if perf.cpc else None,
            "outbound_clicks": int(perf.outbound_clicks) if perf.outbound_clicks else None,
            "outbound_ctr": float(perf.outbound_ctr) if perf.outbound_ctr else None,
            "unique_clicks": int(perf.unique_clicks) if perf.unique_clicks else None,
            "unique_ctr": float(perf.unique_ctr) if perf.unique_ctr else None,
            "inline_link_clicks": int(perf.inline_link_clicks) if perf.inline_link_clicks else None,
            "inline_link_click_ctr": float(perf.inline_link_click_ctr) if perf.inline_link_click_ctr else None,
            "video_plays": int(perf.video_plays) if perf.video_plays else None,
            "video_views": int(perf.video_views) if perf.video_views else None,
            "vtr": float(perf.vtr) if perf.vtr else None,
            "video_3_sec_watched": int(perf.video_3_sec_watched) if perf.video_3_sec_watched else None,
            "video_30_sec_watched": int(perf.video_30_sec_watched) if perf.video_30_sec_watched else None,
            "video_p25": int(perf.video_p25) if perf.video_p25 else None,
            "video_p50": int(perf.video_p50) if perf.video_p50 else None,
            "video_p75": int(perf.video_p75) if perf.video_p75 else None,
            "video_p100": int(perf.video_p100) if perf.video_p100 else None,
            "video_completion_rate": float(perf.video_completion_rate) if perf.video_completion_rate else None,
            "cost_per_view": float(perf.cost_per_view) if perf.cost_per_view else None,
            "thruplay": int(perf.thruplay) if perf.thruplay else None,
            "cost_per_thruplay": float(perf.cost_per_thruplay) if perf.cost_per_thruplay else None,
            "focused_view": int(perf.focused_view) if perf.focused_view else None,
            "cost_per_focused_view": float(perf.cost_per_focused_view) if perf.cost_per_focused_view else None,
            "trueview_views": int(perf.trueview_views) if perf.trueview_views else None,
            "post_engagements": int(perf.post_engagements) if perf.post_engagements else None,
            "likes": int(perf.likes) if perf.likes else None,
            "comments": int(perf.comments) if perf.comments else None,
            "shares": int(perf.shares) if perf.shares else None,
            "follows": int(perf.follows) if perf.follows else None,
            "conversions": int(perf.conversions) if perf.conversions else None,
            "conversion_value": float(perf.conversion_value) if perf.conversion_value else None,
            "cvr": float(perf.cvr) if perf.cvr else None,
            "cost_per_conversion": float(perf.cost_per_conversion) if perf.cost_per_conversion else None,
            "roas": float(perf.roas) if perf.roas else None,
            "purchases": int(perf.purchases) if perf.purchases else None,
            "purchase_value": float(perf.purchase_value) if perf.purchase_value else None,
            "purchase_roas": float(perf.purchase_roas) if perf.purchase_roas else None,
            "leads": int(perf.leads) if perf.leads else None,
            "cost_per_lead": float(perf.cost_per_lead) if perf.cost_per_lead else None,
            "app_installs": int(perf.app_installs) if perf.app_installs else None,
            "cost_per_install": float(perf.cost_per_install) if perf.cost_per_install else None,
            "in_app_purchases": int(perf.in_app_purchases) if perf.in_app_purchases else None,
            "in_app_purchase_value": float(perf.in_app_purchase_value) if perf.in_app_purchase_value else None,
            "subscribe": int(perf.subscribe) if perf.subscribe else None,
            "offline_purchases": int(perf.offline_purchases) if perf.offline_purchases else None,
            "offline_purchase_value": float(perf.offline_purchase_value) if perf.offline_purchase_value else None,
            "messaging_conversations_started": int(perf.messaging_conversations_started) if perf.messaging_conversations_started else None,
            "estimated_ad_recallers": int(perf.estimated_ad_recallers) if perf.estimated_ad_recallers else None,
            "estimated_ad_recall_rate": float(perf.estimated_ad_recall_rate) if perf.estimated_ad_recall_rate else None,
        }.items() if v is not None},
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
    for platform in ["META", "TIKTOK", "GOOGLE_ADS", "DV360"]:
        perf_subq = (
            select(
                HarmonizedPerformance.asset_id,
                func.sum(HarmonizedPerformance.spend).label("total_spend"),
                (
                    func.sum(HarmonizedPerformance.clicks) /
                    func.nullif(func.sum(HarmonizedPerformance.impressions), 0) * 100
                ).label("avg_ctr"),
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
                "asset_url": row[0].asset_url,
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
            func.sum(HarmonizedPerformance.spend).label("total_spend"),
        )
        .join(CreativeAsset, CreativeAsset.id == HarmonizedPerformance.asset_id)
        .where(CreativeAsset.organization_id == current_user.organization_id)
    )
    stats = stats_result.one()

    # Connected accounts from PlatformConnection (all, not just those with data)
    connections_result = await db.execute(
        select(PlatformConnection)
        .where(
            PlatformConnection.organization_id == current_user.organization_id,
            PlatformConnection.is_active == True,
        )
        .order_by(PlatformConnection.platform, PlatformConnection.ad_account_name)
    )
    connections = connections_result.scalars().all()

    connected_accounts = [
        {
            "id": str(c.id),
            "platform": c.platform,
            "ad_account_id": c.ad_account_id,
            "ad_account_name": c.ad_account_name or c.ad_account_id,
            "currency": c.currency,
            "sync_status": c.sync_status,
            "last_synced_at": c.last_synced_at.isoformat() if c.last_synced_at else None,
        }
        for c in connections
    ]

    return {
        "widgets": widgets,
        "overall_stats": {
            "total_assets": int(stats.total_assets or 0),
            "total_accounts": len(connected_accounts),
            "total_spend": float(stats.total_spend or 0),
        },
        "connected_accounts": connected_accounts,
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
                (
                    func.sum(HarmonizedPerformance.clicks) /
                    func.nullif(func.sum(HarmonizedPerformance.impressions), 0) * 100
                ).label("ctr"),
                (
                    func.sum(HarmonizedPerformance.spend) /
                    func.nullif(func.sum(HarmonizedPerformance.impressions), 0) * 1000
                ).label("cpm"),
                func.sum(HarmonizedPerformance.conversions).label("conversions"),
                (
                    func.sum(HarmonizedPerformance.conversion_value) /
                    func.nullif(func.sum(HarmonizedPerformance.spend), 0)
                ).label("roas"),
                func.sum(HarmonizedPerformance.video_views).label("video_views"),
                (
                    func.sum(HarmonizedPerformance.video_views) /
                    func.nullif(func.sum(HarmonizedPerformance.impressions), 0) * 100
                ).label("vtr"),
            ).where(
                HarmonizedPerformance.asset_id == asset_id,
                HarmonizedPerformance.report_date >= payload.date_from,
                HarmonizedPerformance.report_date <= payload.date_to,
            )
        )
        perf = perf_result.one()

        # Daily timeseries for comparison chart — aggregate by date
        ts_result = await db.execute(
            select(
                HarmonizedPerformance.report_date,
                func.sum(HarmonizedPerformance.spend).label("spend"),
                func.sum(HarmonizedPerformance.impressions).label("impressions"),
                func.sum(HarmonizedPerformance.clicks).label("clicks"),
                func.sum(HarmonizedPerformance.conversion_value).label("conversion_value"),
            ).where(
                HarmonizedPerformance.asset_id == asset_id,
                HarmonizedPerformance.report_date >= payload.date_from,
                HarmonizedPerformance.report_date <= payload.date_to,
            ).group_by(HarmonizedPerformance.report_date)
            .order_by(HarmonizedPerformance.report_date)
        )

        ts_data = []
        for row in ts_result.all():
            s = float(row.spend or 0)
            imp = float(row.impressions or 0)
            cl = float(row.clicks or 0)
            cv = float(row.conversion_value or 0)
            ts_data.append({
                "date": row.report_date.isoformat(),
                "spend": s,
                "ctr": (cl / imp * 100) if imp else 0,
                "roas": (cv / s) if s else 0,
            })

        comparison.append({
            "id": str(asset.id),
            "ad_name": asset.ad_name,
            "platform": asset.platform,
            "asset_format": asset.asset_format,
            "thumbnail_url": asset.thumbnail_url,
            "asset_url": asset.asset_url,
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
            "timeseries": ts_data,
        })

    return {"assets": comparison, "date_from": payload.date_from, "date_to": payload.date_to}
