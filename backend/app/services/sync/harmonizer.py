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
    "app_installs", "cost_per_install", "in_app_purchases", "in_app_purchase_value", "in_app_purchase_roas",
    "subscribe", "offline_purchases", "offline_purchase_value", "messaging_conversations_started",
    "estimated_ad_recallers", "estimated_ad_recall_rate",
    "quality_ranking", "engagement_rate_ranking", "conversion_rate_ranking", "creative_fatigue",
    "unique_clicks", "unique_ctr", "inline_link_clicks", "inline_link_click_ctr",
    "video_3_sec_watched", "video_30_sec_watched",
    "exchange_rate", "platform_extras", "harmonized_at",
    "publisher_platform", "platform_position",
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

    @staticmethod
    def _safe_add(a, b):
        if a is None and b is None:
            return None
        return (a or 0) + (b or 0)

    @staticmethod
    def _safe_add_decimal(a, b):
        if a is None and b is None:
            return None
        return Decimal(str(a or 0)) + Decimal(str(b or 0))

    @staticmethod
    def _first_non_null(*values):
        for v in values:
            if v is not None:
                return v
        return None

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
                ad_id = raw.ad_id
                report_date = raw.report_date
                ad_account_id = raw.ad_account_id
                original_currency = raw.currency or connection.currency or "USD"
                exchange_rate = await currency_converter.get_rate(
                    db, original_currency, org_currency, report_date
                )
                convert = self._make_converter(exchange_rate)

                asset = await self._ensure_asset(
                    db,
                    connection=connection,
                    platform="META",
                    ad_id=ad_id,
                    ad_name=raw.ad_name,
                    campaign_id=raw.campaign_id,
                    campaign_name=raw.campaign_name,
                    campaign_objective=raw.campaign_objective,
                    ad_set_id=raw.ad_set_id,
                    ad_set_name=raw.ad_set_name,
                    ad_account_id=ad_account_id,
                    asset_format=raw.ad_format,
                    thumbnail_url=raw.thumbnail_url,
                    asset_url=raw.asset_url,
                    creative_id=raw.creative_id,
                    placement=raw.placement,
                    first_seen_at=report_date,
                )

                spend = raw.spend
                impressions = raw.impressions
                reach = raw.reach
                clicks = raw.clicks

                spend_converted = convert(spend)
                cpm = None
                if spend is not None and impressions:
                    cpm = convert(Decimal(str(float(spend) / impressions * 1000)))
                cpc = None
                if spend is not None and clicks:
                    cpc = convert(Decimal(str(float(spend) / clicks)))
                ctr = None
                if clicks is not None and impressions:
                    ctr = float(clicks) / impressions * 100
                outbound_ctr = None
                if raw.outbound_clicks is not None and impressions:
                    outbound_ctr = float(raw.outbound_clicks) / impressions * 100
                vtr = None
                if raw.video_views is not None and impressions:
                    vtr = float(raw.video_views) / impressions * 100
                cvr = None
                if raw.conversions is not None and clicks:
                    cvr = float(raw.conversions) / clicks * 100
                roas = None
                if raw.conversion_value is not None and spend and float(spend) > 0:
                    roas = float(raw.conversion_value) / float(spend)
                purchase_roas = None
                if raw.purchase_value is not None and spend and float(spend) > 0:
                    purchase_roas = float(raw.purchase_value) / float(spend)
                cost_per_thruplay = None
                if spend is not None and raw.video_thruplay_watched:
                    cost_per_thruplay = convert(Decimal(str(float(spend) / raw.video_thruplay_watched)))
                cost_per_lead = None
                if spend is not None and raw.lead:
                    cost_per_lead = convert(Decimal(str(float(spend) / raw.lead)))
                cost_per_conversion = None
                if spend is not None and raw.conversions:
                    cost_per_conversion = convert(Decimal(str(float(spend) / raw.conversions)))
                cost_per_install = None
                if spend is not None and raw.mobile_app_install:
                    cost_per_install = convert(Decimal(str(float(spend) / raw.mobile_app_install)))
                unique_ctr = None
                if raw.unique_clicks is not None and impressions:
                    unique_ctr = float(raw.unique_clicks) / impressions * 100
                inline_link_click_ctr = None
                if raw.inline_link_clicks is not None and impressions:
                    inline_link_click_ctr = float(raw.inline_link_clicks) / impressions * 100
                ad_recall_rate = None
                if raw.estimated_ad_recallers is not None and impressions:
                    ad_recall_rate = float(raw.estimated_ad_recallers) / impressions * 100
                frequency = None
                if impressions is not None and reach:
                    frequency = float(impressions) / reach
                in_app_roas = None
                if raw.mobile_app_purchase_value is not None and spend and float(spend) > 0:
                    in_app_roas = float(raw.mobile_app_purchase_value) / float(spend)

                video_avg_watch_seconds = None
                if raw.video_avg_time_watched_ms is not None:
                    video_avg_watch_seconds = raw.video_avg_time_watched_ms / 1000.0

                video_completion_rate = None
                if raw.video_p100_watched is not None and impressions:
                    video_completion_rate = float(raw.video_p100_watched) / impressions * 100

                row = {
                    "asset_id": asset.id,
                    "platform_connection_id": connection.id,
                    "report_date": report_date,
                    "platform": "META",
                    "ad_account_id": ad_account_id,
                    "campaign_id": raw.campaign_id,
                    "campaign_name": raw.campaign_name,
                    "campaign_objective": raw.campaign_objective,
                    "ad_set_id": raw.ad_set_id,
                    "ad_set_name": raw.ad_set_name,
                    "ad_id": ad_id,
                    "ad_name": raw.ad_name,
                    "asset_format": raw.ad_format or "IMAGE",
                    "publisher_platform": raw.publisher_platform,
                    "platform_position": raw.platform_position,
                    "org_currency": org_currency,
                    "original_currency": original_currency,
                    "exchange_rate": exchange_rate,
                    "spend": spend_converted,
                    "impressions": impressions,
                    "reach": reach,
                    "frequency": frequency,
                    "cpm": cpm,
                    "cpp": None,
                    "clicks": clicks,
                    "cpc": cpc,
                    "ctr": ctr,
                    "outbound_clicks": raw.outbound_clicks,
                    "outbound_ctr": outbound_ctr,
                    "cpv": cost_per_thruplay,
                    "video_plays": raw.video_play_actions,
                    "video_views": raw.video_views,
                    "vtr": vtr,
                    "video_p25": raw.video_p25_watched,
                    "video_p50": raw.video_p50_watched,
                    "video_p75": raw.video_p75_watched,
                    "video_p100": raw.video_p100_watched,
                    "video_completion_rate": video_completion_rate,
                    "video_avg_watch_time_seconds": video_avg_watch_seconds,
                    "cost_per_view": cost_per_thruplay,
                    "thruplay": raw.video_thruplay_watched,
                    "cost_per_thruplay": cost_per_thruplay,
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
                    "cvr": cvr,
                    "cost_per_conversion": cost_per_conversion,
                    "roas": roas,
                    "purchases": raw.purchase,
                    "purchase_value": convert(raw.purchase_value),
                    "purchase_roas": purchase_roas,
                    "leads": raw.lead,
                    "cost_per_lead": cost_per_lead,
                    "app_installs": raw.mobile_app_install,
                    "cost_per_install": cost_per_install,
                    "in_app_purchases": raw.mobile_app_purchase,
                    "in_app_purchase_value": convert(raw.mobile_app_purchase_value),
                    "in_app_purchase_roas": in_app_roas,
                    "subscribe": raw.subscribe,
                    "offline_purchases": raw.offline_purchase,
                    "offline_purchase_value": convert(raw.offline_purchase_value),
                    "messaging_conversations_started": raw.messaging_conversation_started_7d,
                    "estimated_ad_recallers": raw.estimated_ad_recallers,
                    "estimated_ad_recall_rate": ad_recall_rate,
                    "quality_ranking": raw.quality_ranking,
                    "engagement_rate_ranking": raw.engagement_rate_ranking,
                    "conversion_rate_ranking": raw.conversion_rate_ranking,
                    "creative_fatigue": raw.creative_fatigue,
                    "unique_clicks": raw.unique_clicks,
                    "unique_ctr": unique_ctr,
                    "inline_link_clicks": raw.inline_link_clicks,
                    "inline_link_click_ctr": inline_link_click_ctr,
                    "video_3_sec_watched": raw.video_3_sec_watched,
                    "video_30_sec_watched": raw.video_30_sec_watched,
                    "platform_extras": {
                        "page_engagement": raw.page_engagement,
                        "buying_type": raw.buying_type,
                        "bid_strategy": raw.bid_strategy,
                        "optimization_goal": raw.optimization_goal,
                        "on_facebook_purchase": raw.on_facebook_purchase,
                        "on_facebook_purchase_value": float(raw.on_facebook_purchase_value) if raw.on_facebook_purchase_value else None,
                        "on_facebook_lead": raw.on_facebook_lead,
                        "offline_lead": raw.offline_lead,
                    },
                }

                await self._upsert_harmonized(db, row)
                raw.is_processed = True
                db.add(raw)
                count += 1

            except Exception as e:
                logger.error(f"Harmonization error for Meta ad {raw.ad_id} on {raw.report_date}: {e}")
                import traceback
                logger.error(traceback.format_exc())

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
                    "leads": raw.app_event_generate_lead,
                    "cost_per_lead": convert(raw.cost_per_lead),
                    "app_installs": raw.app_install,
                    "cost_per_install": convert(raw.cost_per_app_install),
                    "in_app_purchases": raw.app_event_purchase,
                    "in_app_purchase_value": convert(raw.app_event_purchase_value),
                    "in_app_purchase_roas": None,
                    "subscribe": raw.page_event_subscribe,
                    "offline_purchases": None,
                    "offline_purchase_value": None,
                    "messaging_conversations_started": None,
                    "estimated_ad_recallers": None,
                    "estimated_ad_recall_rate": None,
                    "quality_ranking": None,
                    "engagement_rate_ranking": None,
                    "conversion_rate_ranking": None,
                    "creative_fatigue": None,
                    "unique_clicks": None,
                    "unique_ctr": None,
                    "inline_link_clicks": None,
                    "inline_link_click_ctr": None,
                    "video_3_sec_watched": raw.video_watched_2s,
                    "video_30_sec_watched": None,
                    "platform_extras": {
                        "engagement_rate": raw.engagement_rate,
                        "swipe_rate": raw.swipe_rate,
                        "is_spark_ad": raw.is_spark_ad,
                        "focused_view_15s": raw.focused_view_15s,
                        "focused_view_rate": raw.focused_view_rate,
                        "result": raw.result,
                        "result_rate": raw.result_rate,
                        "cost_per_result": float(raw.cost_per_result) if raw.cost_per_result else None,
                        "cta_conversions": raw.cta_conversions,
                        "vta_conversions": raw.vta_conversions,
                        "secondary_goal_result": raw.secondary_goal_result,
                        "publisher": raw.publisher,
                        "live_views": raw.live_views,
                        "onsite_purchase": raw.onsite_purchase,
                        "page_event_complete_payment": raw.page_event_complete_payment,
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
                    "app_installs": None,
                    "cost_per_install": None,
                    "in_app_purchases": None,
                    "in_app_purchase_value": None,
                    "in_app_purchase_roas": None,
                    "subscribe": None,
                    "offline_purchases": None,
                    "offline_purchase_value": None,
                    "messaging_conversations_started": None,
                    "estimated_ad_recallers": None,
                    "estimated_ad_recall_rate": None,
                    "quality_ranking": None,
                    "engagement_rate_ranking": None,
                    "conversion_rate_ranking": None,
                    "creative_fatigue": None,
                    "unique_clicks": None,
                    "unique_ctr": None,
                    "inline_link_clicks": None,
                    "inline_link_click_ctr": None,
                    "video_3_sec_watched": None,
                    "video_30_sec_watched": raw.video_30s_views,
                    "platform_extras": {
                        "placement_type": raw.placement_type,
                        "earned_views": raw.earned_views,
                        "youtube_public_views": raw.youtube_public_views,
                        "all_conversions": raw.all_conversions,
                        "all_conversions_value": float(raw.all_conversions_value) if raw.all_conversions_value else None,
                        "view_through_conversions": raw.view_through_conversions,
                        "engaged_view_conversions": raw.engaged_view_conversions,
                        "active_view_viewability": raw.active_view_viewability,
                        "campaign_bidding_strategy_type": raw.campaign_bidding_strategy_type,
                        "cross_device_conversions": raw.cross_device_conversions,
                        "ad_network_type": raw.ad_network_type,
                        "youtube_earned_views": raw.youtube_earned_views,
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
                    try:
                        first_seen = datetime.strptime(first_seen, "%Y-%m-%d").date()
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
            constraint="uq_harmonized_daily_ad_breakdown",
            set_=update_set,
        )
        await db.execute(stmt)


harmonizer = HarmonizationService()
