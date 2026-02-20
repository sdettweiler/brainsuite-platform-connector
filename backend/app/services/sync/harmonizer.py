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

        groups: Dict[tuple, List] = {}
        for raw in raw_records:
            key = (raw.ad_id, raw.report_date, raw.ad_account_id)
            groups.setdefault(key, []).append(raw)

        for (ad_id, report_date, ad_account_id), breakdown_rows in groups.items():
            try:
                first = breakdown_rows[0]
                original_currency = first.currency or connection.currency or "USD"
                exchange_rate = await currency_converter.get_rate(
                    db, original_currency, org_currency, report_date
                )
                convert = self._make_converter(exchange_rate)

                asset = await self._ensure_asset(
                    db,
                    connection=connection,
                    platform="META",
                    ad_id=ad_id,
                    ad_name=first.ad_name,
                    campaign_id=first.campaign_id,
                    campaign_name=first.campaign_name,
                    campaign_objective=first.campaign_objective,
                    ad_set_id=first.ad_set_id,
                    ad_set_name=first.ad_set_name,
                    ad_account_id=ad_account_id,
                    asset_format=first.ad_format,
                    thumbnail_url=first.thumbnail_url,
                    asset_url=first.asset_url,
                    creative_id=first.creative_id,
                    placement=first.placement,
                    first_seen_at=report_date,
                )

                t_spend = None
                t_impressions = None
                t_reach = None
                t_clicks = None
                t_outbound_clicks = None
                t_video_plays = None
                t_video_views = None
                t_video_p25 = None
                t_video_p50 = None
                t_video_p75 = None
                t_video_p100 = None
                t_thruplay = None
                t_post_engagements = None
                t_likes = None
                t_conversions = None
                t_conversion_value = None
                t_purchases = None
                t_purchase_value = None
                t_leads = None
                t_app_installs = None
                t_in_app_purchases = None
                t_in_app_purchase_value = None
                t_subscribe = None
                t_offline_purchases = None
                t_offline_purchase_value = None
                t_messaging = None
                t_ad_recallers = None
                t_unique_clicks = None
                t_inline_link_clicks = None
                t_video_3_sec = None
                t_video_30_sec = None
                t_on_fb_purchase = None
                t_on_fb_purchase_value = None
                t_on_fb_lead = None
                t_offline_lead = None
                t_page_engagement = None
                total_video_avg_ms_weighted = 0.0
                total_video_avg_weight = 0

                breakdowns_list = []

                for raw in breakdown_rows:
                    t_spend = self._safe_add_decimal(t_spend, raw.spend)
                    t_impressions = self._safe_add(t_impressions, raw.impressions)
                    t_reach = self._safe_add(t_reach, raw.reach)
                    t_clicks = self._safe_add(t_clicks, raw.clicks)
                    t_outbound_clicks = self._safe_add(t_outbound_clicks, raw.outbound_clicks)
                    t_video_plays = self._safe_add(t_video_plays, raw.video_play_actions)
                    t_video_views = self._safe_add(t_video_views, raw.video_views)
                    t_video_p25 = self._safe_add(t_video_p25, raw.video_p25_watched)
                    t_video_p50 = self._safe_add(t_video_p50, raw.video_p50_watched)
                    t_video_p75 = self._safe_add(t_video_p75, raw.video_p75_watched)
                    t_video_p100 = self._safe_add(t_video_p100, raw.video_p100_watched)
                    t_thruplay = self._safe_add(t_thruplay, raw.video_thruplay_watched)
                    t_post_engagements = self._safe_add(t_post_engagements, raw.post_engagement)
                    t_likes = self._safe_add(t_likes, raw.reactions)
                    t_conversions = self._safe_add(t_conversions, raw.conversions)
                    t_conversion_value = self._safe_add_decimal(t_conversion_value, raw.conversion_value)
                    t_purchases = self._safe_add(t_purchases, raw.purchase)
                    t_purchase_value = self._safe_add_decimal(t_purchase_value, raw.purchase_value)
                    t_leads = self._safe_add(t_leads, raw.lead)
                    t_app_installs = self._safe_add(t_app_installs, raw.mobile_app_install)
                    t_in_app_purchases = self._safe_add(t_in_app_purchases, raw.mobile_app_purchase)
                    t_in_app_purchase_value = self._safe_add_decimal(t_in_app_purchase_value, raw.mobile_app_purchase_value)
                    t_subscribe = self._safe_add(t_subscribe, raw.subscribe)
                    t_offline_purchases = self._safe_add(t_offline_purchases, raw.offline_purchase)
                    t_offline_purchase_value = self._safe_add_decimal(t_offline_purchase_value, raw.offline_purchase_value)
                    t_messaging = self._safe_add(t_messaging, raw.messaging_conversation_started_7d)
                    t_ad_recallers = self._safe_add(t_ad_recallers, raw.estimated_ad_recallers)
                    t_unique_clicks = self._safe_add(t_unique_clicks, raw.unique_clicks)
                    t_inline_link_clicks = self._safe_add(t_inline_link_clicks, raw.inline_link_clicks)
                    t_video_3_sec = self._safe_add(t_video_3_sec, raw.video_3_sec_watched)
                    t_video_30_sec = self._safe_add(t_video_30_sec, raw.video_30_sec_watched)
                    t_on_fb_purchase = self._safe_add(t_on_fb_purchase, raw.on_facebook_purchase)
                    t_on_fb_purchase_value = self._safe_add_decimal(t_on_fb_purchase_value, raw.on_facebook_purchase_value)
                    t_on_fb_lead = self._safe_add(t_on_fb_lead, raw.on_facebook_lead)
                    t_offline_lead = self._safe_add(t_offline_lead, raw.offline_lead)
                    t_page_engagement = self._safe_add(t_page_engagement, raw.page_engagement)

                    if raw.video_avg_time_watched_ms is not None and raw.impressions:
                        total_video_avg_ms_weighted += raw.video_avg_time_watched_ms * raw.impressions
                        total_video_avg_weight += raw.impressions

                    if raw.publisher_platform or raw.platform_position:
                        breakdowns_list.append({
                            "publisher_platform": raw.publisher_platform,
                            "platform_position": raw.platform_position,
                            "spend": float(raw.spend) if raw.spend else 0,
                            "impressions": raw.impressions or 0,
                        })

                video_avg_watch_seconds = None
                if total_video_avg_weight > 0:
                    video_avg_watch_seconds = (total_video_avg_ms_weighted / total_video_avg_weight) / 1000.0

                t_spend_converted = convert(t_spend)
                t_cpm = None
                if t_spend is not None and t_impressions:
                    t_cpm = convert(Decimal(str(float(t_spend) / t_impressions * 1000)))
                t_cpc = None
                if t_spend is not None and t_clicks:
                    t_cpc = convert(Decimal(str(float(t_spend) / t_clicks)))
                t_ctr = None
                if t_clicks is not None and t_impressions:
                    t_ctr = float(t_clicks) / t_impressions * 100
                t_outbound_ctr = None
                if t_outbound_clicks is not None and t_impressions:
                    t_outbound_ctr = float(t_outbound_clicks) / t_impressions * 100
                t_vtr = None
                if t_video_views is not None and t_impressions:
                    t_vtr = float(t_video_views) / t_impressions * 100
                t_cvr = None
                if t_conversions is not None and t_clicks:
                    t_cvr = float(t_conversions) / t_clicks * 100
                t_roas = None
                if t_conversion_value is not None and t_spend and float(t_spend) > 0:
                    t_roas = float(t_conversion_value) / float(t_spend)
                t_purchase_roas = None
                if t_purchase_value is not None and t_spend and float(t_spend) > 0:
                    t_purchase_roas = float(t_purchase_value) / float(t_spend)
                t_cost_per_thruplay = None
                if t_spend is not None and t_thruplay:
                    t_cost_per_thruplay = convert(Decimal(str(float(t_spend) / t_thruplay)))
                t_cost_per_lead = None
                if t_spend is not None and t_leads:
                    t_cost_per_lead = convert(Decimal(str(float(t_spend) / t_leads)))
                t_cost_per_conversion = None
                if t_spend is not None and t_conversions:
                    t_cost_per_conversion = convert(Decimal(str(float(t_spend) / t_conversions)))
                t_cost_per_install = None
                if t_spend is not None and t_app_installs:
                    t_cost_per_install = convert(Decimal(str(float(t_spend) / t_app_installs)))
                t_unique_ctr = None
                if t_unique_clicks is not None and t_impressions:
                    t_unique_ctr = float(t_unique_clicks) / t_impressions * 100
                t_inline_link_click_ctr = None
                if t_inline_link_clicks is not None and t_impressions:
                    t_inline_link_click_ctr = float(t_inline_link_clicks) / t_impressions * 100
                t_ad_recall_rate = None
                if t_ad_recallers is not None and t_impressions:
                    t_ad_recall_rate = float(t_ad_recallers) / t_impressions * 100
                t_frequency = None
                if t_impressions is not None and t_reach:
                    t_frequency = float(t_impressions) / t_reach

                t_in_app_roas = None
                if t_in_app_purchase_value is not None and t_spend and float(t_spend) > 0:
                    t_in_app_roas = float(t_in_app_purchase_value) / float(t_spend)

                row = {
                    "asset_id": asset.id,
                    "platform_connection_id": connection.id,
                    "report_date": report_date,
                    "platform": "META",
                    "ad_account_id": ad_account_id,
                    "campaign_id": first.campaign_id,
                    "campaign_name": first.campaign_name,
                    "campaign_objective": first.campaign_objective,
                    "ad_set_id": first.ad_set_id,
                    "ad_set_name": first.ad_set_name,
                    "ad_id": ad_id,
                    "ad_name": first.ad_name,
                    "asset_format": first.ad_format or "IMAGE",
                    "org_currency": org_currency,
                    "original_currency": original_currency,
                    "exchange_rate": exchange_rate,
                    "spend": t_spend_converted,
                    "impressions": t_impressions,
                    "reach": t_reach,
                    "frequency": t_frequency,
                    "cpm": t_cpm,
                    "cpp": None,
                    "clicks": t_clicks,
                    "cpc": t_cpc,
                    "ctr": t_ctr,
                    "outbound_clicks": t_outbound_clicks,
                    "outbound_ctr": t_outbound_ctr,
                    "cpv": t_cost_per_thruplay,
                    "video_plays": t_video_plays,
                    "video_views": t_video_views,
                    "vtr": t_vtr,
                    "video_p25": t_video_p25,
                    "video_p50": t_video_p50,
                    "video_p75": t_video_p75,
                    "video_p100": t_video_p100,
                    "video_avg_watch_time_seconds": video_avg_watch_seconds,
                    "cost_per_view": t_cost_per_thruplay,
                    "thruplay": t_thruplay,
                    "cost_per_thruplay": t_cost_per_thruplay,
                    "focused_view": None,
                    "cost_per_focused_view": None,
                    "trueview_views": None,
                    "post_engagements": t_post_engagements,
                    "likes": t_likes,
                    "comments": None,
                    "shares": None,
                    "follows": None,
                    "conversions": t_conversions,
                    "conversion_value": convert(t_conversion_value),
                    "cvr": t_cvr,
                    "cost_per_conversion": t_cost_per_conversion,
                    "roas": t_roas,
                    "purchases": t_purchases,
                    "purchase_value": convert(t_purchase_value),
                    "purchase_roas": t_purchase_roas,
                    "leads": t_leads,
                    "cost_per_lead": t_cost_per_lead,
                    "app_installs": t_app_installs,
                    "cost_per_install": t_cost_per_install,
                    "in_app_purchases": t_in_app_purchases,
                    "in_app_purchase_value": convert(t_in_app_purchase_value),
                    "in_app_purchase_roas": t_in_app_roas,
                    "subscribe": t_subscribe,
                    "offline_purchases": t_offline_purchases,
                    "offline_purchase_value": convert(t_offline_purchase_value),
                    "messaging_conversations_started": t_messaging,
                    "estimated_ad_recallers": t_ad_recallers,
                    "estimated_ad_recall_rate": t_ad_recall_rate,
                    "quality_ranking": first.quality_ranking,
                    "engagement_rate_ranking": first.engagement_rate_ranking,
                    "conversion_rate_ranking": first.conversion_rate_ranking,
                    "creative_fatigue": first.creative_fatigue,
                    "unique_clicks": t_unique_clicks,
                    "unique_ctr": t_unique_ctr,
                    "inline_link_clicks": t_inline_link_clicks,
                    "inline_link_click_ctr": t_inline_link_click_ctr,
                    "video_3_sec_watched": t_video_3_sec,
                    "video_30_sec_watched": t_video_30_sec,
                    "platform_extras": {
                        "page_engagement": t_page_engagement,
                        "buying_type": first.buying_type,
                        "bid_strategy": first.bid_strategy,
                        "optimization_goal": first.optimization_goal,
                        "on_facebook_purchase": t_on_fb_purchase,
                        "on_facebook_purchase_value": float(t_on_fb_purchase_value) if t_on_fb_purchase_value else None,
                        "on_facebook_lead": t_on_fb_lead,
                        "offline_lead": t_offline_lead,
                        "breakdowns": breakdowns_list,
                    },
                }

                await self._upsert_harmonized(db, row)
                for raw in breakdown_rows:
                    raw.is_processed = True
                    db.add(raw)
                count += 1

            except Exception as e:
                logger.error(f"Harmonization error for Meta ad {ad_id} on {report_date}: {e}")
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
            constraint="uq_harmonized_daily_ad",
            set_=update_set,
        )
        await db.execute(stmt)


harmonizer = HarmonizationService()
