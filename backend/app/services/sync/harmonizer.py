import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.creative import CreativeAsset
from app.models.performance import (
    MetaRawPerformance,
    TikTokRawPerformance,
    YouTubeRawPerformance,
    HarmonizedPerformance,
)
from app.models.platform import PlatformConnection
from app.models.user import Organization
from app.services.currency import currency_converter
from app.services.ace_score import generate_ace_score

logger = logging.getLogger(__name__)

HARMONIZED_UPDATE_COLS = [
    "spend", "impressions", "reach", "frequency",
    "cpm", "cpp", "clicks", "cpc", "ctr",
    "outbound_clicks", "outbound_ctr", "cpv",
    "video_plays", "video_views", "vtr",
    "video_p25", "video_p50", "video_p75", "video_p100",
    "video_completion_rate", "video_avg_watch_time_seconds",
    "cost_per_view",
    "thruplay", "cost_per_thruplay",
    "focused_view", "cost_per_focused_view",
    "trueview_views",
    "post_engagements", "likes", "comments", "shares", "follows",
    "conversions", "conversion_value", "cvr", "cost_per_conversion", "roas",
    "purchases", "purchase_value", "purchase_roas",
    "leads", "cost_per_lead",
    "exchange_rate", "platform_extras", "harmonized_at",
]


class HarmonizationService:

    async def harmonize_connection(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> int:
        org = await db.get(Organization, connection.organization_id)
        org_currency = org.currency if org else "USD"

        if connection.platform == "META":
            return await self._harmonize_meta(db, connection, org_currency, date_from, date_to)
        elif connection.platform == "TIKTOK":
            return await self._harmonize_tiktok(db, connection, org_currency, date_from, date_to)
        elif connection.platform == "YOUTUBE":
            return await self._harmonize_youtube(db, connection, org_currency, date_from, date_to)
        return 0

    @staticmethod
    def _make_converter(exchange_rate: float):
        def convert(val) -> Optional[Decimal]:
            if val is None:
                return None
            return Decimal(str(float(val) * exchange_rate))
        return convert

    async def _harmonize_meta(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        org_currency: str,
        date_from: Optional[date],
        date_to: Optional[date],
    ) -> int:
        query = select(MetaRawPerformance).where(
            MetaRawPerformance.platform_connection_id == connection.id,
            MetaRawPerformance.is_processed == False,
        )
        if date_from:
            query = query.where(MetaRawPerformance.report_date >= date_from)
        if date_to:
            query = query.where(MetaRawPerformance.report_date <= date_to)

        result = await db.execute(query)
        raw_records = result.scalars().all()
        count = 0

        for raw in raw_records:
            try:
                original_currency = raw.currency or connection.currency or "USD"
                exchange_rate = await currency_converter.get_rate(
                    db, original_currency, org_currency, raw.report_date
                )
                convert = self._make_converter(exchange_rate)

                asset = await self._ensure_asset(
                    db,
                    connection=connection,
                    platform="META",
                    ad_id=raw.ad_id,
                    ad_name=raw.ad_name,
                    campaign_id=raw.campaign_id,
                    campaign_name=raw.campaign_name,
                    campaign_objective=raw.campaign_objective,
                    ad_set_id=raw.ad_set_id,
                    ad_set_name=raw.ad_set_name,
                    ad_account_id=raw.ad_account_id,
                    asset_format=raw.ad_format,
                    thumbnail_url=raw.thumbnail_url,
                    asset_url=raw.asset_url,
                    creative_id=raw.creative_id,
                    placement=raw.placement,
                    first_seen_at=raw.report_date,
                )

                video_avg_watch_seconds = None
                if raw.video_avg_time_watched_ms is not None:
                    video_avg_watch_seconds = raw.video_avg_time_watched_ms / 1000.0

                row = {
                    "asset_id": asset.id,
                    "platform_connection_id": connection.id,
                    "report_date": raw.report_date,
                    "platform": "META",
                    "ad_account_id": raw.ad_account_id,
                    "campaign_id": raw.campaign_id,
                    "campaign_name": raw.campaign_name,
                    "campaign_objective": raw.campaign_objective,
                    "ad_set_id": raw.ad_set_id,
                    "ad_set_name": raw.ad_set_name,
                    "ad_id": raw.ad_id,
                    "ad_name": raw.ad_name,
                    "asset_format": raw.ad_format or "IMAGE",
                    "org_currency": org_currency,
                    "original_currency": original_currency,
                    "exchange_rate": exchange_rate,
                    "spend": convert(raw.spend),
                    "impressions": raw.impressions,
                    "reach": raw.reach,
                    "frequency": raw.frequency,
                    "cpm": convert(raw.cpm),
                    "cpp": convert(raw.cpp),
                    "clicks": raw.clicks,
                    "cpc": convert(raw.cpc),
                    "ctr": raw.ctr,
                    "outbound_clicks": raw.outbound_clicks,
                    "outbound_ctr": raw.outbound_clicks_ctr,
                    "cpv": convert(raw.cost_per_thruplay),
                    "video_plays": raw.video_play_actions,
                    "video_views": raw.video_views,
                    "vtr": raw.video_view_rate,
                    "video_p25": raw.video_p25_watched,
                    "video_p50": raw.video_p50_watched,
                    "video_p75": raw.video_p75_watched,
                    "video_p100": raw.video_p100_watched,
                    "video_avg_watch_time_seconds": video_avg_watch_seconds,
                    "cost_per_view": convert(raw.cost_per_thruplay),
                    "thruplay": raw.video_thruplay_watched,
                    "cost_per_thruplay": convert(raw.cost_per_thruplay),
                    "focused_view": None,
                    "cost_per_focused_view": None,
                    "trueview_views": None,
                    "post_engagements": raw.post_engagement,
                    "likes": raw.reactions,
                    "comments": None,
                    "shares": None,
                    "follows": None,
                    "conversions": raw.conversions,
                    "conversion_value": convert(raw.conversion_value),
                    "cvr": raw.cvr,
                    "cost_per_conversion": convert(raw.cost_per_purchase) if raw.cost_per_purchase else None,
                    "roas": raw.roas,
                    "purchases": raw.purchase,
                    "purchase_value": convert(raw.purchase_value),
                    "purchase_roas": raw.purchase_roas,
                    "leads": raw.lead,
                    "cost_per_lead": convert(raw.cost_per_lead),
                    "platform_extras": {
                        "estimated_ad_recall_lift": raw.estimated_ad_recall_lift,
                        "estimated_ad_recallers": raw.estimated_ad_recallers,
                        "unique_clicks": raw.unique_clicks,
                        "unique_ctr": raw.unique_ctr,
                        "inline_link_clicks": raw.inline_link_clicks,
                        "page_engagement": raw.page_engagement,
                        "subscribe": raw.subscribe,
                        "buying_type": raw.buying_type,
                        "bid_strategy": raw.bid_strategy,
                        "optimization_goal": raw.optimization_goal,
                    },
                }

                await self._upsert_harmonized(db, row)
                raw.is_processed = True
                db.add(raw)
                count += 1

            except Exception as e:
                logger.error(f"Harmonization error for Meta record {raw.id}: {e}")

        await db.flush()
        return count

    async def _harmonize_tiktok(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        org_currency: str,
        date_from: Optional[date],
        date_to: Optional[date],
    ) -> int:
        query = select(TikTokRawPerformance).where(
            TikTokRawPerformance.platform_connection_id == connection.id,
            TikTokRawPerformance.is_processed == False,
        )
        if date_from:
            query = query.where(TikTokRawPerformance.report_date >= date_from)
        if date_to:
            query = query.where(TikTokRawPerformance.report_date <= date_to)

        result = await db.execute(query)
        raw_records = result.scalars().all()
        count = 0

        for raw in raw_records:
            try:
                original_currency = raw.currency or connection.currency or "USD"
                exchange_rate = await currency_converter.get_rate(
                    db, original_currency, org_currency, raw.report_date
                )
                convert = self._make_converter(exchange_rate)

                asset = await self._ensure_asset(
                    db,
                    connection=connection,
                    platform="TIKTOK",
                    ad_id=raw.ad_id,
                    ad_name=raw.ad_name,
                    campaign_id=raw.campaign_id,
                    campaign_name=raw.campaign_name,
                    campaign_objective=raw.campaign_objective,
                    ad_set_id=raw.ad_group_id,
                    ad_set_name=raw.ad_group_name,
                    ad_account_id=raw.ad_account_id,
                    asset_format=raw.ad_format,
                    thumbnail_url=raw.thumbnail_url,
                    asset_url=raw.creative_url or raw.asset_url,
                    first_seen_at=raw.report_date,
                )

                focused_view = raw.focused_view_6s

                row = {
                    "asset_id": asset.id,
                    "platform_connection_id": connection.id,
                    "report_date": raw.report_date,
                    "platform": "TIKTOK",
                    "ad_account_id": raw.ad_account_id,
                    "campaign_id": raw.campaign_id,
                    "campaign_name": raw.campaign_name,
                    "campaign_objective": raw.campaign_objective,
                    "ad_set_id": raw.ad_group_id,
                    "ad_set_name": raw.ad_group_name,
                    "ad_id": raw.ad_id,
                    "ad_name": raw.ad_name,
                    "asset_format": raw.ad_format or "VIDEO",
                    "org_currency": org_currency,
                    "original_currency": original_currency,
                    "exchange_rate": exchange_rate,
                    "spend": convert(raw.spend),
                    "impressions": raw.impressions,
                    "reach": raw.reach,
                    "frequency": raw.frequency,
                    "cpm": convert(raw.cpm),
                    "cpp": None,
                    "clicks": raw.clicks,
                    "cpc": convert(raw.cpc),
                    "ctr": raw.ctr,
                    "outbound_clicks": None,
                    "outbound_ctr": None,
                    "cpv": convert(raw.cost_per_focused_view),
                    "video_plays": raw.video_play_actions,
                    "video_views": raw.video_views,
                    "vtr": raw.video_completion_rate,
                    "video_p25": raw.video_views_p25,
                    "video_p50": raw.video_views_p50,
                    "video_p75": raw.video_views_p75,
                    "video_p100": raw.video_views_p100,
                    "video_completion_rate": raw.video_completion_rate,
                    "video_avg_watch_time_seconds": raw.avg_play_time_per_user,
                    "cost_per_view": convert(raw.cost_per_focused_view),
                    "thruplay": None,
                    "cost_per_thruplay": None,
                    "focused_view": focused_view,
                    "cost_per_focused_view": convert(raw.cost_per_focused_view),
                    "trueview_views": None,
                    "post_engagements": None,
                    "likes": raw.total_likes,
                    "comments": raw.total_comments,
                    "shares": raw.total_shares,
                    "follows": raw.total_follows,
                    "conversions": raw.conversions,
                    "conversion_value": convert(raw.conversion_value),
                    "cvr": raw.cvr,
                    "cost_per_conversion": convert(raw.cost_per_conversion),
                    "roas": raw.roas,
                    "purchases": (raw.cta_purchase or 0) + (raw.vta_purchase or 0) if raw.cta_purchase or raw.vta_purchase else None,
                    "purchase_value": convert(raw.total_purchase_value),
                    "purchase_roas": raw.purchase_roas,
                    "leads": None,
                    "cost_per_lead": None,
                    "platform_extras": {
                        "engagement_rate": raw.engagement_rate,
                        "swipe_rate": raw.swipe_rate,
                        "paid_likes": raw.paid_likes,
                        "paid_comments": raw.paid_comments,
                        "paid_shares": raw.paid_shares,
                        "paid_follows": raw.paid_follows,
                        "is_spark_ad": raw.is_spark_ad,
                        "focused_view_15s": raw.focused_view_15s,
                        "focused_view_rate": raw.focused_view_rate,
                        "result": raw.result,
                        "result_rate": raw.result_rate,
                        "cost_per_result": float(raw.cost_per_result) if raw.cost_per_result else None,
                    },
                }

                await self._upsert_harmonized(db, row)
                raw.is_processed = True
                db.add(raw)
                count += 1

            except Exception as e:
                logger.error(f"Harmonization error for TikTok record {raw.id}: {e}")

        await db.flush()
        return count

    async def _harmonize_youtube(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        org_currency: str,
        date_from: Optional[date],
        date_to: Optional[date],
    ) -> int:
        query = select(YouTubeRawPerformance).where(
            YouTubeRawPerformance.platform_connection_id == connection.id,
            YouTubeRawPerformance.is_processed == False,
        )
        if date_from:
            query = query.where(YouTubeRawPerformance.report_date >= date_from)
        if date_to:
            query = query.where(YouTubeRawPerformance.report_date <= date_to)

        result = await db.execute(query)
        raw_records = result.scalars().all()
        count = 0

        for raw in raw_records:
            try:
                original_currency = raw.currency or connection.currency or "USD"
                exchange_rate = await currency_converter.get_rate(
                    db, original_currency, org_currency, raw.report_date
                )
                convert = self._make_converter(exchange_rate)

                asset = await self._ensure_asset(
                    db,
                    connection=connection,
                    platform="YOUTUBE",
                    ad_id=raw.ad_id,
                    ad_name=raw.ad_name,
                    campaign_id=raw.campaign_id,
                    campaign_name=raw.campaign_name,
                    campaign_objective=raw.campaign_objective,
                    ad_set_id=raw.ad_group_id,
                    ad_set_name=raw.ad_group_name,
                    ad_account_id=raw.ad_account_id,
                    asset_format="VIDEO",
                    thumbnail_url=raw.thumbnail_url,
                    asset_url=raw.video_url,
                    video_duration=raw.video_duration,
                    placement=raw.placement_type,
                    first_seen_at=raw.report_date,
                )

                impressions = raw.impressions or 0
                video_p25 = int(raw.video_quartile_p25 * impressions) if raw.video_quartile_p25 is not None and impressions else None
                video_p50 = int(raw.video_quartile_p50 * impressions) if raw.video_quartile_p50 is not None and impressions else None
                video_p75 = int(raw.video_quartile_p75 * impressions) if raw.video_quartile_p75 is not None and impressions else None
                video_p100 = int(raw.video_quartile_p100 * impressions) if raw.video_quartile_p100 is not None and impressions else None

                row = {
                    "asset_id": asset.id,
                    "platform_connection_id": connection.id,
                    "report_date": raw.report_date,
                    "platform": "YOUTUBE",
                    "ad_account_id": raw.ad_account_id,
                    "campaign_id": raw.campaign_id,
                    "campaign_name": raw.campaign_name,
                    "campaign_objective": raw.campaign_objective,
                    "ad_set_id": raw.ad_group_id,
                    "ad_set_name": raw.ad_group_name,
                    "ad_id": raw.ad_id,
                    "ad_name": raw.ad_name,
                    "asset_format": "VIDEO",
                    "org_currency": org_currency,
                    "original_currency": original_currency,
                    "exchange_rate": exchange_rate,
                    "spend": convert(raw.spend),
                    "impressions": impressions,
                    "reach": raw.reach,
                    "frequency": raw.frequency,
                    "cpm": convert(raw.cpm),
                    "cpp": None,
                    "clicks": raw.clicks,
                    "cpc": convert(raw.average_cpc),
                    "ctr": raw.ctr,
                    "outbound_clicks": None,
                    "outbound_ctr": None,
                    "cpv": convert(raw.average_cpv),
                    "video_plays": raw.video_plays,
                    "video_views": raw.video_views,
                    "vtr": raw.view_rate,
                    "video_p25": video_p25,
                    "video_p50": video_p50,
                    "video_p75": video_p75,
                    "video_p100": video_p100,
                    "video_completion_rate": raw.video_view_through_rate,
                    "video_avg_watch_time_seconds": raw.avg_watch_time_per_impression,
                    "cost_per_view": convert(raw.cost_per_view),
                    "thruplay": None,
                    "cost_per_thruplay": None,
                    "focused_view": None,
                    "cost_per_focused_view": None,
                    "trueview_views": raw.video_views,
                    "post_engagements": raw.engagements,
                    "likes": None,
                    "comments": None,
                    "shares": None,
                    "follows": raw.earned_subscribers,
                    "conversions": raw.conversions,
                    "conversion_value": convert(raw.conversion_value),
                    "cvr": raw.cvr,
                    "cost_per_conversion": convert(raw.cost_per_conversion),
                    "roas": raw.roas,
                    "purchases": None,
                    "purchase_value": None,
                    "purchase_roas": raw.purchase_roas,
                    "leads": None,
                    "cost_per_lead": None,
                    "platform_extras": {
                        "placement_type": raw.placement_type,
                        "earned_views": raw.earned_views,
                        "youtube_public_views": raw.youtube_public_views,
                        "all_conversions": raw.all_conversions,
                        "view_through_conversions": raw.view_through_conversions,
                        "engaged_view_conversions": raw.engaged_view_conversions,
                        "active_view_viewability": raw.active_view_viewability,
                        "campaign_bidding_strategy_type": raw.campaign_bidding_strategy_type,
                    },
                }

                await self._upsert_harmonized(db, row)
                raw.is_processed = True
                db.add(raw)
                count += 1

            except Exception as e:
                logger.error(f"Harmonization error for YouTube record {raw.id}: {e}")

        await db.flush()
        return count

    async def _ensure_asset(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        platform: str,
        ad_id: str,
        **kwargs,
    ) -> CreativeAsset:
        result = await db.execute(
            select(CreativeAsset).where(
                CreativeAsset.organization_id == connection.organization_id,
                CreativeAsset.platform == platform,
                CreativeAsset.ad_id == ad_id,
                CreativeAsset.ad_account_id == kwargs.get("ad_account_id"),
            )
        )
        asset = result.scalar_one_or_none()

        if not asset:
            ace = generate_ace_score(kwargs.get("asset_format"))
            first_seen = kwargs.get("first_seen_at")
            if isinstance(first_seen, str):
                from datetime import datetime
                try:
                    first_seen = datetime.strptime(first_seen, "%Y-%m-%d").date()
                except Exception:
                    first_seen = None

            asset = CreativeAsset(
                organization_id=connection.organization_id,
                platform_connection_id=connection.id,
                platform=platform,
                ad_id=ad_id,
                ad_name=kwargs.get("ad_name"),
                campaign_id=kwargs.get("campaign_id"),
                campaign_name=kwargs.get("campaign_name"),
                campaign_objective=kwargs.get("campaign_objective"),
                ad_set_id=kwargs.get("ad_set_id"),
                ad_set_name=kwargs.get("ad_set_name"),
                ad_account_id=kwargs.get("ad_account_id"),
                asset_format=(kwargs.get("asset_format") or "IMAGE").upper(),
                thumbnail_url=kwargs.get("thumbnail_url"),
                asset_url=kwargs.get("asset_url"),
                creative_id=kwargs.get("creative_id"),
                placement=kwargs.get("placement"),
                video_duration=kwargs.get("video_duration"),
                ace_score=ace["ace_score"],
                ace_score_confidence=ace["ace_score_confidence"],
                brainsuite_metadata=ace["brainsuite_metadata"],
                first_seen_at=first_seen,
                last_seen_at=first_seen,
            )
            db.add(asset)
            await db.flush()
        else:
            if kwargs.get("thumbnail_url") and not asset.thumbnail_url:
                asset.thumbnail_url = kwargs.get("thumbnail_url")
            if kwargs.get("asset_url"):
                asset.asset_url = kwargs.get("asset_url")
            if kwargs.get("creative_id") and not asset.creative_id:
                asset.creative_id = kwargs.get("creative_id")
            if kwargs.get("asset_format") and not asset.asset_format:
                asset.asset_format = kwargs.get("asset_format")
            if kwargs.get("first_seen_at"):
                first_seen = kwargs.get("first_seen_at")
                if isinstance(first_seen, str):
                    from datetime import datetime as _dt
                    try:
                        first_seen = _dt.strptime(first_seen, "%Y-%m-%d").date()
                    except Exception:
                        first_seen = None
                if first_seen:
                    existing_first = asset.first_seen_at
                    if isinstance(existing_first, datetime):
                        existing_first = existing_first.date()
                    existing_last = asset.last_seen_at
                    if isinstance(existing_last, datetime):
                        existing_last = existing_last.date()
                    if isinstance(first_seen, datetime):
                        first_seen = first_seen.date()
                    if not existing_first or first_seen < existing_first:
                        asset.first_seen_at = first_seen
                    if not existing_last or first_seen > existing_last:
                        asset.last_seen_at = first_seen
            db.add(asset)
            await db.flush()

        return asset

    async def _upsert_harmonized(self, db: AsyncSession, row: dict) -> None:
        stmt = pg_insert(HarmonizedPerformance).values([row])
        update_set = {k: stmt.excluded[k] for k in HARMONIZED_UPDATE_COLS if k in row}
        stmt = stmt.on_conflict_do_update(
            constraint="uq_harmonized_daily_ad",
            set_=update_set,
        )
        await db.execute(stmt)


harmonizer = HarmonizationService()
