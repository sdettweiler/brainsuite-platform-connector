import asyncio
import httpx
import logging
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import TikTokRawPerformance
from app.core.security import decrypt_token

logger = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"

AD_REPORT_DIMENSIONS = ["ad_id", "stat_time_day"]

# Core metrics — valid for all account types and all ad objectives.
AD_REPORT_METRICS = [
    "spend",
    "impressions",
    "reach",
    "frequency",
    "clicks",
    "cpc",
    "ctr",
    "cpm",
    "cost_per_1000_reached",
    "conversion",
    "cost_per_conversion",
    "conversion_rate",
    "real_time_conversion",
    "total_purchase_value",
    "complete_payment_roas",
    "video_play_actions",
    "video_watched_2s",
    "video_watched_6s",
    "average_video_play",
    "average_video_play_per_user",
    "video_views_p25",
    "video_views_p50",
    "video_views_p75",
    "video_views_p100",
    "engaged_view",
    "engaged_view_15s",
    "profile_visits",
    "profile_visits_rate",
    "likes",
    "comments",
    "shares",
    "follows",
    "engagement_rate",
    "result",
    "result_rate",
    "cost_per_result",
    "gross_impressions",
    "secondary_goal_result",
    "cost_per_secondary_goal_result",
    "secondary_goal_result_rate",
    "real_time_conversion_rate",
    "app_install",
    "cost_per_app_install",
    "registration",
    "cost_per_registration",
    "complete_payment",
    "value_per_complete_payment",
    "cost_per_complete_payment",
    "total_complete_payment_rate",
    "total_pageview",
    "onsite_shopping",
    "total_onsite_shopping_value",
    "onsite_form",
    "cost_per_onsite_form",
    "cta_conversion",
    "vta_conversion",
    "cta_purchase",
    "vta_purchase",
]

# Reach & Frequency buying type only — account_type == "REACH_FREQUENCY" required.
_METRICS_RF = ["average_frequency_7_day"]

# Interactive Add-On creative feature — only available if account has this feature enabled.
_METRICS_INTERACTIVE = [
    "interactive_add_on_impression",
    "interactive_add_on_destination_click",
]

# TikTok LIVE / TikTok Shop — requires LIVE or Shop features on the advertiser account.
_METRICS_LIVE_SHOP = [
    "live_views",
    "live_unique_viewed",
    "live_product_clicks",
    "total_live_shopping_amount",
    "subscribe_amount",
]

AD_INFO_FIELDS = [
    "ad_id",
    "ad_name",
    "campaign_id",
    "campaign_name",
    "adgroup_id",
    "adgroup_name",
    "ad_format",
    "creative_type",
    "identity_type",
    "display_name",
    "landing_page_url",
    "video_id",
    "image_ids",
    "call_to_action",
    "operation_status",
    "tiktok_item_id",
]

CAMPAIGN_INFO_FIELDS = [
    "campaign_id",
    "objective_type",
    "budget_mode",
    "operation_status",
]

ADGROUP_INFO_FIELDS = [
    "adgroup_id",
    "campaign_id",
    "optimization_goal",
    "billing_event",
    "operation_status",
]


class TikTokAPIError(Exception):
    pass


class TikTokSyncService:

    def __init__(self):
        # Proactively-built metrics list per advertiser (account_type + feature detection).
        # Populated in sync_date_range before the first /report call; never relies on error signals.
        self._metrics_cache: dict = {}   # advertiser_id -> metrics list
        self._ad_info_cache: dict = {}   # advertiser_id -> stripped AD_INFO_FIELDS list
        self._advertiser_info_cache: dict = {}  # advertiser_id -> /advertiser/info/ response
        # Campaign / adgroup metadata caches — keyed by advertiser_id then entity id.
        self._campaign_lookup: dict = {}  # advertiser_id -> {campaign_id -> data}
        self._adgroup_lookup: dict = {}   # advertiser_id -> {adgroup_id -> data}

    async def sync_date_range(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        date_from: date,
        date_to: date,
        sync_job_id: Optional[str] = None,
    ) -> Dict[str, int]:
        access_token = decrypt_token(connection.access_token_encrypted)
        advertiser_id = connection.ad_account_id

        # Build the metrics list proactively from account info — no error-signal discovery.
        if advertiser_id not in self._metrics_cache:
            await self._build_report_metrics(access_token, advertiser_id)

        total_fetched = 0
        total_upserted = 0
        all_ad_ids = set()

        chunk_start = date_from
        while chunk_start <= date_to:
            chunk_end = min(chunk_start + timedelta(days=29), date_to)
            logger.info(f"TikTok sync: {advertiser_id} chunk {chunk_start} → {chunk_end}")
            records = await self._fetch_ad_reports(
                access_token, advertiser_id, chunk_start, chunk_end
            )
            logger.info(f"  Got {len(records)} records from reporting API")

            for r in records:
                ad_id = r.get("dimensions", {}).get("ad_id")
                if ad_id:
                    all_ad_ids.add(ad_id)

            upserted = await self._upsert_records(db, connection, records, sync_job_id)
            total_fetched += len(records)
            total_upserted += upserted
            chunk_start = chunk_end + timedelta(days=1)

        # Ad creative enrichment (thumbnails) deferred to post-commit task to release DB session.

        logger.info(f"TikTok sync complete: fetched={total_fetched}, upserted={total_upserted}")
        return {"fetched": total_fetched, "upserted": total_upserted, "_creative_ad_ids": list(all_ad_ids) if all_ad_ids else []}

    async def _fetch_advertiser_info(self, access_token: str, advertiser_id: str) -> Dict[str, Any]:
        """Fetch /advertiser/info/ and cache result. Returns empty dict on failure."""
        if advertiser_id in self._advertiser_info_cache:
            return self._advertiser_info_cache[advertiser_id]
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{TIKTOK_API_BASE}/advertiser/info/",
                    params={
                        "advertiser_ids": json.dumps([advertiser_id]),
                        "fields": json.dumps(["account_type", "promotion_area", "industry"]),
                    },
                    headers={"Access-Token": access_token},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 0:
                    items = data.get("data", {}).get("list", [])
                    info = items[0] if items else {}
                    self._advertiser_info_cache[advertiser_id] = info
                    logger.info("TikTok advertiser %s: account_type=%s", advertiser_id, info.get("account_type"))
                    return info
        except Exception as e:
            logger.warning("Failed to fetch TikTok advertiser info for %s: %s", advertiser_id, e)
        self._advertiser_info_cache[advertiser_id] = {}
        return {}

    async def _build_report_metrics(self, access_token: str, advertiser_id: str) -> None:
        """Proactively determine which metrics to request based on account type and features.
        Called once per advertiser per server lifetime before the first /report call."""
        info = await self._fetch_advertiser_info(access_token, advertiser_id)
        metrics = list(AD_REPORT_METRICS)

        account_type = info.get("account_type", "AUCTION")
        if account_type == "REACH_FREQUENCY":
            metrics.extend(_METRICS_RF)
            logger.info("TikTok advertiser %s: RF account — adding RF metrics", advertiser_id)

        # Interactive Add-On and Live/Shop features can't be determined from advertiser info alone.
        # They require specific account features; excluded by default to avoid API errors.
        # To enable per-account, add them here based on a feature flag or connection metadata.

        self._metrics_cache[advertiser_id] = metrics
        logger.info("TikTok advertiser %s: using %d report metrics (account_type=%s)", advertiser_id, len(metrics), account_type)

    async def _fetch_ad_reports(
        self,
        access_token: str,
        advertiser_id: str,
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        metrics = list(self._metrics_cache.get(advertiser_id, AD_REPORT_METRICS))
        records: List[Dict[str, Any]] = []
        page = 1
        page_size = 1000

        async with httpx.AsyncClient(timeout=60) as client:
            while True:
                try:
                    resp = await client.get(
                        f"{TIKTOK_API_BASE}/report/integrated/get/",
                        params={
                            "advertiser_id": advertiser_id,
                            "report_type": "BASIC",
                            "data_level": "AUCTION_AD",
                            "dimensions": json.dumps(AD_REPORT_DIMENSIONS),
                            "metrics": json.dumps(metrics),
                            "start_date": date_from.strftime("%Y-%m-%d"),
                            "end_date": date_to.strftime("%Y-%m-%d"),
                            "page": page,
                            "page_size": page_size,
                        },
                        headers={"Access-Token": access_token},
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    if data.get("code") == 40100:
                        logger.warning("TikTok report rate limit (code 40100), backing off 60s")
                        await asyncio.sleep(60)
                        continue

                    if data.get("code") != 0:
                        msg = data.get("message", "")
                        # Adaptive field stripping: some metrics are only valid for
                        # TikTok Shop / live-enabled accounts. Strip and retry once.
                        if "Invalid metric fields" in msg:
                            match = re.search(r"Invalid metric fields:\s*\[([^\]]+)\]", msg)
                            if match:
                                bad = {f.strip().strip("'\"") for f in match.group(1).split(",")}
                                before = len(metrics)
                                metrics = [f for f in metrics if f not in bad]
                                if len(metrics) < before:
                                    self._metrics_cache[advertiser_id] = metrics
                                    logger.debug(
                                        "TikTok: stripped %d unexpected metric(s) for advertiser %s: %s",
                                        before - len(metrics), advertiser_id, sorted(bad),
                                    )
                                    records = []
                                    page = 1
                                    continue
                        raise TikTokAPIError(
                            f"TikTok API error (code={data.get('code')}): {msg}"
                        )

                    page_data = data.get("data", {})
                    records.extend(page_data.get("list", []))

                    page_info = page_data.get("page_info", {})
                    total_pages = page_info.get("total_page", 1)
                    if page >= total_pages:
                        break
                    page += 1

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        logger.warning("TikTok rate limit, backing off 60s")
                        await asyncio.sleep(60)
                    else:
                        raise TikTokAPIError(f"TikTok HTTP error {e.response.status_code}: {e}") from e

        return records

    @staticmethod
    def _parse_date(val) -> Optional[date]:
        if not val:
            return None
        if isinstance(val, date):
            return val
        try:
            return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(val) -> Optional[int]:
        if val is None or val == "" or val == "-":
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        if val is None or val == "" or val == "-":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_decimal(val) -> Optional[Decimal]:
        if val is None or val == "" or val == "-":
            return None
        try:
            return Decimal(str(val))
        except (ValueError, InvalidOperation):
            return None

    async def _upsert_records(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        records: List[Dict[str, Any]],
        sync_job_id: Optional[str],
    ) -> int:
        if not records:
            return 0

        rows = []
        for r in records:
            dims = r.get("dimensions", {})
            m = r.get("metrics", {})

            spend = self._safe_decimal(m.get("spend")) or Decimal("0")
            impressions = self._safe_int(m.get("impressions")) or 0
            clicks = self._safe_int(m.get("clicks")) or 0
            conversions = self._safe_int(m.get("conversion"))
            conversion_val = self._safe_decimal(m.get("total_purchase_value"))
            roas = (float(conversion_val) / float(spend)) if spend and conversion_val else None
            cvr = self._safe_float(m.get("conversion_rate"))

            video_views = self._safe_int(m.get("video_play_actions"))
            video_p100 = self._safe_int(m.get("video_views_p100"))
            video_completion_rate = (video_p100 / video_views * 100) if video_p100 and video_views else None

            purchase_roas = self._safe_float(m.get("complete_payment_roas"))

            focused_view_6s = self._safe_int(m.get("engaged_view"))
            focused_view_15s = self._safe_int(m.get("engaged_view_15s"))
            focused_view_rate = (focused_view_6s / impressions * 100) if focused_view_6s and impressions else None
            cost_per_focused_view = (float(spend) / focused_view_6s) if spend and focused_view_6s else None

            rows.append({
                "platform_connection_id": connection.id,
                "sync_job_id": sync_job_id,
                "report_date": self._parse_date(dims.get("stat_time_day")),
                "ad_account_id": connection.ad_account_id,
                "ad_id": dims.get("ad_id"),
                "currency": connection.currency,
                "spend": spend,
                "impressions": impressions,
                "reach": self._safe_int(m.get("reach")),
                "frequency": self._safe_float(m.get("frequency")),
                "clicks": clicks,
                "cpc": self._safe_decimal(m.get("cpc")),
                "ctr": self._safe_float(m.get("ctr")),
                "cpm": self._safe_decimal(m.get("cpm")),
                "cost_per_1000_reached": self._safe_decimal(m.get("cost_per_1000_reached")),
                "gross_impression": self._safe_int(m.get("gross_impressions")),
                "gross_reach": None,
                "avg_7_day_frequency": self._safe_float(m.get("average_frequency_7_day")),
                "profile_visits": self._safe_int(m.get("profile_visits")),
                "profile_visits_rate": self._safe_float(m.get("profile_visits_rate")),
                "total_likes": self._safe_int(m.get("likes")),
                "total_comments": self._safe_int(m.get("comments")),
                "total_shares": self._safe_int(m.get("shares")),
                "total_follows": self._safe_int(m.get("follows")),
                "engagement_rate": self._safe_float(m.get("engagement_rate")),
                "total_interactive_add_on_clicks": self._safe_int(m.get("interactive_add_on_destination_click")),
                "total_interactive_add_on_impressions": self._safe_int(m.get("interactive_add_on_impression")),
                "video_play_actions": video_views,
                "video_watched_2s": self._safe_int(m.get("video_watched_2s")),
                "video_watched_6s": self._safe_int(m.get("video_watched_6s")),
                "video_views_p25": self._safe_int(m.get("video_views_p25")),
                "video_views_p50": self._safe_int(m.get("video_views_p50")),
                "video_views_p75": self._safe_int(m.get("video_views_p75")),
                "video_views_p100": video_p100,
                "video_completion_rate": video_completion_rate,
                "avg_play_time_per_user": self._safe_float(m.get("average_video_play_per_user")),
                "avg_play_time_per_video_view": self._safe_float(m.get("average_video_play")),
                "focused_view_6s": focused_view_6s,
                "focused_view_15s": focused_view_15s,
                "focused_view_rate": focused_view_rate,
                "cost_per_focused_view": Decimal(str(cost_per_focused_view)) if cost_per_focused_view else None,
                "video_views": video_views,
                "conversions": conversions,
                "conversion_rate": self._safe_float(m.get("conversion_rate")),
                "cost_per_conversion": self._safe_decimal(m.get("cost_per_conversion")),
                "conversion_value": conversion_val,
                "cvr": cvr,
                "roas": roas,
                "result": self._safe_int(m.get("result")),
                "result_rate": self._safe_float(m.get("result_rate")),
                "cost_per_result": self._safe_decimal(m.get("cost_per_result")),
                "real_time_conversions": self._safe_int(m.get("real_time_conversion")),
                "total_purchase_value": self._safe_decimal(m.get("total_purchase_value")),
                "purchase_roas": purchase_roas,
                "real_time_conversion_rate": self._safe_float(m.get("real_time_conversion_rate")),
                "cta_conversions": self._safe_int(m.get("cta_conversion")),
                "vta_conversions": self._safe_int(m.get("vta_conversion")),
                "cta_purchase": self._safe_int(m.get("cta_purchase")),
                "vta_purchase": self._safe_int(m.get("vta_purchase")),
                "app_install": self._safe_int(m.get("app_install")),
                "cost_per_app_install": self._safe_decimal(m.get("cost_per_app_install")),
                "unique_app_install": None,
                "app_event_purchase": None,
                "app_event_purchase_value": None,
                "cost_per_purchase": None,
                "app_event_generate_lead": self._safe_int(m.get("registration")),
                "cost_per_lead": self._safe_decimal(m.get("cost_per_registration")),
                "page_event_complete_payment": self._safe_int(m.get("complete_payment")),
                "page_event_complete_payment_value": self._safe_decimal(m.get("value_per_complete_payment")),
                "page_event_complete_payment_roas": self._safe_float(m.get("total_complete_payment_rate")),
                "cost_per_page_event_complete_payment": self._safe_decimal(m.get("cost_per_complete_payment")),
                "page_event_subscribe": self._safe_int(m.get("subscribe_amount")),
                "page_event_view_content": self._safe_int(m.get("total_pageview")),
                "onsite_form_submit": self._safe_int(m.get("onsite_form")),
                "cost_per_onsite_form_submit": self._safe_decimal(m.get("cost_per_onsite_form")),
                "onsite_purchase": self._safe_int(m.get("onsite_shopping")),
                "onsite_purchase_value": self._safe_decimal(m.get("total_onsite_shopping_value")),
                "live_views": self._safe_int(m.get("live_views")),
                "live_unique_views": self._safe_int(m.get("live_unique_viewed")),
                "live_product_clicks": self._safe_int(m.get("live_product_clicks")),
                "live_add_to_cart": None,
                "live_purchase": None,
                "live_purchase_value": self._safe_decimal(m.get("total_live_shopping_amount")),
                "secondary_goal_result": self._safe_int(m.get("secondary_goal_result")),
                "cost_per_secondary_goal_result": self._safe_decimal(m.get("cost_per_secondary_goal_result")),
                "secondary_goal_result_rate": self._safe_float(m.get("secondary_goal_result_rate")),
                "is_validated": True,
                "is_processed": False,
            })

        stmt = pg_insert(TikTokRawPerformance).values(rows)
        update_cols = {c.name: getattr(stmt.excluded, c.name)
                       for c in TikTokRawPerformance.__table__.columns
                       if c.name not in ("id", "platform_connection_id", "report_date",
                                         "ad_id", "ad_account_id", "retrieved_at",
                                         # populated by deferred enrich_from_ad_get — preserve on re-sync
                                         "campaign_id", "campaign_name", "ad_group_id", "ad_group_name",
                                         "ad_name", "campaign_objective", "ad_status", "ad_format",
                                         "creative_type", "is_spark_ad", "identity_type", "display_name",
                                         "landing_page_url", "video_id", "image_ids", "optimization_goal",
                                         "billing_event", "buying_type", "campaign_budget_mode",
                                         "campaign_status", "adgroup_status", "call_to_action", "post_link", "thumbnail_url",
                                         # populated by deferred _enrich_from_ad_get — preserve on re-sync
                                         "asset_url", "video_source_url")}
        update_cols["is_processed"] = False
        stmt = stmt.on_conflict_do_update(
            constraint="uq_tiktok_daily_ad",
            set_=update_cols,
        )
        await db.execute(stmt)
        return len(rows)

    async def _enrich_from_ad_get(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        access_token: str,
        advertiser_id: str,
        ad_ids: List[str],
    ) -> None:
        org_id = str(connection.organization_id)
        batch_size = 100
        for i in range(0, len(ad_ids), batch_size):
            batch = ad_ids[i:i + batch_size]
            try:
                ads = await self._fetch_ad_info(access_token, advertiser_id, batch)
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.error("Failed to fetch ad info batch for %s: %s", advertiser_id, e, exc_info=True)
                continue

            # Build campaign + adgroup lookups using instance caches — fetch only IDs
            # not already populated by a previous batch or prefetch_and_write_metadata call.
            campaign_ids = list({str(ad.get("campaign_id")) for ad in ads if ad.get("campaign_id")})
            adgroup_ids = list({str(ad.get("adgroup_id")) for ad in ads if ad.get("adgroup_id")})

            adv_campaign_cache = self._campaign_lookup.setdefault(advertiser_id, {})
            adv_adgroup_cache = self._adgroup_lookup.setdefault(advertiser_id, {})

            missing_campaigns = [cid for cid in campaign_ids if cid not in adv_campaign_cache]
            missing_adgroups = [agid for agid in adgroup_ids if agid not in adv_adgroup_cache]

            if missing_campaigns:
                try:
                    campaigns = await self._fetch_campaign_info(access_token, advertiser_id, missing_campaigns)
                    adv_campaign_cache.update({str(c.get("campaign_id")): c for c in campaigns})
                except Exception as e:
                    logger.warning("Failed to fetch campaign info for advertiser %s: %s", advertiser_id, e)

            if missing_adgroups:
                try:
                    adgroups = await self._fetch_adgroup_info(access_token, advertiser_id, missing_adgroups)
                    adv_adgroup_cache.update({str(ag.get("adgroup_id")): ag for ag in adgroups})
                except Exception as e:
                    logger.warning("Failed to fetch adgroup info for advertiser %s: %s", advertiser_id, e)

            campaign_lookup = adv_campaign_cache
            adgroup_lookup = adv_adgroup_cache

            for ad in ads:
                ad_id = str(ad.get("ad_id", ""))
                if not ad_id:
                    continue

                campaign_data = campaign_lookup.get(str(ad.get("campaign_id", "")), {})
                adgroup_data = adgroup_lookup.get(str(ad.get("adgroup_id", "")), {})

                image_ids_raw = ad.get("image_ids")
                image_ids_str = ",".join(image_ids_raw) if isinstance(image_ids_raw, list) else None

                ad_format = ad.get("ad_format")
                creative_type = ad.get("creative_type")
                is_spark = ad.get("identity_type") == "AUTH_CODE"

                display_name = ad.get("display_name")
                video_id_val = ad.get("video_id")
                post_link = f"https://www.tiktok.com/@{display_name}/video/{video_id_val}" if display_name and video_id_val else None

                thumbnail_url, asset_url, video_source_url, asset_video_duration = await self._download_ad_assets(
                    access_token, advertiser_id, org_id, ad_id, video_id_val, image_ids_raw, is_spark, display_name, ad.get("tiktok_item_id")
                )

                await db.execute(
                    update(TikTokRawPerformance)
                    .where(
                        TikTokRawPerformance.ad_id == ad_id,
                        TikTokRawPerformance.platform_connection_id == connection.id,
                    )
                    .values(
                        campaign_id=str(ad.get("campaign_id", "")),
                        campaign_name=ad.get("campaign_name"),
                        ad_group_id=str(ad.get("adgroup_id", "")),
                        ad_group_name=ad.get("adgroup_name"),
                        ad_name=ad.get("ad_name"),
                        campaign_objective=campaign_data.get("objective_type"),
                        campaign_budget_mode=campaign_data.get("budget_mode"),
                        campaign_status=campaign_data.get("operation_status"),
                        ad_status=ad.get("operation_status"),
                        adgroup_status=adgroup_data.get("operation_status"),
                        optimization_goal=adgroup_data.get("optimization_goal"),
                        billing_event=adgroup_data.get("billing_event"),
                        ad_format=ad_format,
                        creative_type=creative_type,
                        is_spark_ad=is_spark,
                        identity_type=ad.get("identity_type"),
                        display_name=display_name,
                        landing_page_url=ad.get("landing_page_url"),
                        video_id=str(video_id_val) if video_id_val else None,
                        image_ids=image_ids_str,
                        call_to_action=ad.get("call_to_action"),
                        post_link=post_link,
                        **({"thumbnail_url": thumbnail_url} if thumbnail_url else {}),
                        **({"asset_url": asset_url} if asset_url else {}),
                        **({"video_source_url": video_source_url} if video_source_url else {}),
                    )
                )

                # Populate video_duration on CreativeAsset inline — no separate backfill needed.
                if asset_video_duration is not None:
                    from app.models.creative import CreativeAsset
                    await db.execute(
                        update(CreativeAsset).where(
                            CreativeAsset.organization_id == connection.organization_id,
                            CreativeAsset.platform == "TIKTOK",
                            CreativeAsset.ad_id == ad_id,
                            CreativeAsset.video_duration.is_(None),
                        ).values(video_duration=asset_video_duration)
                    )

            await db.flush()
            logger.info(f"  Enriched {len(batch)} ads from /ad/get/")

        await db.commit()

    async def enrich_creatives_deferred(
        self,
        connection_id,
        ad_ids: List[str],
    ) -> None:
        """Post-commit creative enrichment: opens own DB session so it doesn't hold the sync session."""
        from app.db.base import get_session_factory
        from app.models.platform import PlatformConnection
        from sqlalchemy import select
        import uuid
        try:
            async with get_session_factory()() as db:
                conn = (await db.execute(
                    select(PlatformConnection).where(
                        PlatformConnection.id == (connection_id if isinstance(connection_id, uuid.UUID) else uuid.UUID(str(connection_id)))
                    )
                )).scalar_one_or_none()
                if not conn:
                    return
                from datetime import datetime, timezone
                if conn.token_expiry and conn.token_expiry < datetime.now(timezone.utc):
                    logger.warning("TikTok deferred creative enrichment: access token expired for connection %s — enrichment may fail", connection_id)
                access_token = decrypt_token(conn.access_token_encrypted)
                advertiser_id = conn.ad_account_id
                logger.info(f"TikTok deferred creative enrichment: {len(ad_ids)} ads for {advertiser_id}")
                await self._enrich_from_ad_get(db, conn, access_token, advertiser_id, ad_ids)
        except Exception as e:
            logger.warning("TikTok deferred creative enrichment failed (non-fatal): %s", e)

    async def prefetch_and_write_metadata(
        self,
        connection_id,
        ad_ids: List[str],
    ) -> Optional[Dict[str, Dict]]:
        """Phase 1 of two-phase enrichment: fetch all ad/campaign/adgroup metadata, write to DB.
        Returns {str(ad_id) -> {video_id, image_ids, is_spark, display_name}} hints for Phase 2,
        or None on failure so caller can fall back to enrich_creatives_deferred."""
        from app.db.base import get_session_factory
        from app.models.platform import PlatformConnection
        from sqlalchemy import select
        import uuid
        try:
            async with get_session_factory()() as db:
                conn = (await db.execute(
                    select(PlatformConnection).where(
                        PlatformConnection.id == (connection_id if isinstance(connection_id, uuid.UUID) else uuid.UUID(str(connection_id)))
                    )
                )).scalar_one_or_none()
                if not conn:
                    return None
                from datetime import datetime, timezone
                if conn.token_expiry and conn.token_expiry < datetime.now(timezone.utc):
                    logger.warning("TikTok prefetch_and_write_metadata: token expired for connection %s", connection_id)
                access_token = decrypt_token(conn.access_token_encrypted)
                advertiser_id = conn.ad_account_id

                download_hints: Dict[str, Dict] = {}
                flushed = 0

                for i in range(0, len(ad_ids), 100):
                    batch = ad_ids[i:i + 100]
                    try:
                        ads = await self._fetch_ad_info(access_token, advertiser_id, batch)
                    except Exception as e:
                        logger.warning("prefetch_and_write_metadata: ad info fetch failed for batch %d: %s", i, e)
                        continue

                    campaign_ids = list({str(ad.get("campaign_id")) for ad in ads if ad.get("campaign_id")})
                    adgroup_ids = list({str(ad.get("adgroup_id")) for ad in ads if ad.get("adgroup_id")})

                    adv_campaign_cache = self._campaign_lookup.setdefault(advertiser_id, {})
                    adv_adgroup_cache = self._adgroup_lookup.setdefault(advertiser_id, {})

                    missing_campaigns = [cid for cid in campaign_ids if cid not in adv_campaign_cache]
                    missing_adgroups = [agid for agid in adgroup_ids if agid not in adv_adgroup_cache]

                    if missing_campaigns:
                        try:
                            campaigns = await self._fetch_campaign_info(access_token, advertiser_id, missing_campaigns)
                            adv_campaign_cache.update({str(c.get("campaign_id")): c for c in campaigns})
                        except Exception as e:
                            logger.warning("prefetch_and_write_metadata: campaign fetch failed: %s", e)

                    if missing_adgroups:
                        try:
                            adgroups = await self._fetch_adgroup_info(access_token, advertiser_id, missing_adgroups)
                            adv_adgroup_cache.update({str(ag.get("adgroup_id")): ag for ag in adgroups})
                        except Exception as e:
                            logger.warning("prefetch_and_write_metadata: adgroup fetch failed: %s", e)

                    for ad in ads:
                        ad_id = str(ad.get("ad_id", ""))
                        if not ad_id:
                            continue

                        campaign_data = adv_campaign_cache.get(str(ad.get("campaign_id", "")), {})
                        adgroup_data = adv_adgroup_cache.get(str(ad.get("adgroup_id", "")), {})

                        image_ids_raw = ad.get("image_ids")
                        image_ids_str = ",".join(image_ids_raw) if isinstance(image_ids_raw, list) else None
                        video_id_val = ad.get("video_id")
                        is_spark = ad.get("identity_type") == "AUTH_CODE"
                        display_name = ad.get("display_name")
                        post_link = f"https://www.tiktok.com/@{display_name}/video/{video_id_val}" if display_name and video_id_val else None

                        await db.execute(
                            update(TikTokRawPerformance)
                            .where(
                                TikTokRawPerformance.ad_id == ad_id,
                                TikTokRawPerformance.platform_connection_id == conn.id,
                            )
                            .values(
                                campaign_id=str(ad.get("campaign_id", "")),
                                campaign_name=ad.get("campaign_name"),
                                ad_group_id=str(ad.get("adgroup_id", "")),
                                ad_group_name=ad.get("adgroup_name"),
                                ad_name=ad.get("ad_name"),
                                campaign_objective=campaign_data.get("objective_type"),
                                campaign_budget_mode=campaign_data.get("budget_mode"),
                                campaign_status=campaign_data.get("operation_status"),
                                ad_status=ad.get("operation_status"),
                                adgroup_status=adgroup_data.get("operation_status"),
                                optimization_goal=adgroup_data.get("optimization_goal"),
                                billing_event=adgroup_data.get("billing_event"),
                                        ad_format=ad.get("ad_format"),
                                creative_type=ad.get("creative_type"),
                                is_spark_ad=is_spark,
                                identity_type=ad.get("identity_type"),
                                display_name=display_name,
                                landing_page_url=ad.get("landing_page_url"),
                                video_id=str(video_id_val) if video_id_val else None,
                                image_ids=image_ids_str,
                                call_to_action=ad.get("call_to_action"),
                                post_link=post_link,
                            )
                        )

                        download_hints[ad_id] = {
                            "video_id": video_id_val,
                            "image_ids": image_ids_raw,
                            "is_spark": is_spark,
                            "display_name": display_name,
                            "tiktok_item_id": ad.get("tiktok_item_id"),
                        }

                        flushed += 1
                        if flushed % 100 == 0:
                            await db.flush()

                await db.commit()
                logger.info("TikTok prefetch_and_write_metadata: wrote metadata for %d ads", len(download_hints))
                return download_hints
        except Exception as e:
            logger.warning("TikTok prefetch_and_write_metadata failed (non-fatal): %s", e)
            return None

    async def download_assets_deferred(
        self,
        connection_id,
        ad_id: str,
        hints: Dict,
    ) -> None:
        """Phase 2 of two-phase enrichment: download and store assets for a single ad using pre-fetched hints."""
        from app.db.base import get_session_factory
        from app.models.platform import PlatformConnection
        from sqlalchemy import select
        import uuid
        try:
            async with get_session_factory()() as db:
                conn = (await db.execute(
                    select(PlatformConnection).where(
                        PlatformConnection.id == (connection_id if isinstance(connection_id, uuid.UUID) else uuid.UUID(str(connection_id)))
                    )
                )).scalar_one_or_none()
                if not conn:
                    return
                from datetime import datetime, timezone
                if conn.token_expiry and conn.token_expiry < datetime.now(timezone.utc):
                    logger.warning("TikTok download_assets_deferred: token expired for connection %s", connection_id)
                access_token = decrypt_token(conn.access_token_encrypted)
                advertiser_id = conn.ad_account_id
                org_id = str(conn.organization_id)

                video_id_val = hints.get("video_id")
                image_ids_raw = hints.get("image_ids")
                is_spark = hints.get("is_spark", False)
                display_name = hints.get("display_name")
                tiktok_item_id = hints.get("tiktok_item_id")

                logger.info(
                    "TikTok asset download ad %s: is_spark=%s video_id=%s image_ids=%s item_id=%s",
                    ad_id, is_spark, bool(video_id_val), bool(image_ids_raw), bool(tiktok_item_id),
                )

                thumbnail_url, asset_url, video_source_url, asset_video_duration = await self._download_ad_assets(
                    access_token, advertiser_id, org_id, ad_id, video_id_val, image_ids_raw, is_spark, display_name, tiktok_item_id
                )

                logger.info(
                    "TikTok asset download ad %s result: thumb=%s asset=%s video_src=%s",
                    ad_id, bool(thumbnail_url), bool(asset_url), bool(video_source_url),
                )

                update_vals = {}
                if thumbnail_url:
                    update_vals["thumbnail_url"] = thumbnail_url
                if asset_url:
                    update_vals["asset_url"] = asset_url
                if video_source_url:
                    update_vals["video_source_url"] = video_source_url

                if update_vals:
                    await db.execute(
                        update(TikTokRawPerformance)
                        .where(
                            TikTokRawPerformance.ad_id == ad_id,
                            TikTokRawPerformance.platform_connection_id == conn.id,
                        )
                        .values(**update_vals)
                    )
                else:
                    logger.warning("TikTok ad %s: no assets stored — thumb=%s asset=%s (spark=%s video_id=%s image_ids=%s)", ad_id, bool(thumbnail_url), bool(asset_url), is_spark, bool(video_id_val), bool(image_ids_raw))

                if asset_video_duration is not None:
                    from app.models.creative import CreativeAsset
                    await db.execute(
                        update(CreativeAsset).where(
                            CreativeAsset.organization_id == conn.organization_id,
                            CreativeAsset.platform == "TIKTOK",
                            CreativeAsset.ad_id == ad_id,
                            CreativeAsset.video_duration.is_(None),
                        ).values(video_duration=asset_video_duration)
                    )

                await db.commit()
        except Exception as e:
            logger.warning("TikTok download_assets_deferred failed for ad %s (non-fatal): %s", ad_id, e, exc_info=True)

    async def _download_ad_assets(
        self,
        access_token: str,
        advertiser_id: str,
        org_id: str,
        ad_id: str,
        video_id_val,
        image_ids_raw,
        is_spark: bool,
        display_name: Optional[str] = None,
        tiktok_item_id: Optional[str] = None,
    ) -> tuple[Optional[str], Optional[str], Optional[str], Optional[float]]:
        """Download thumbnail + full asset for one ad.
        Returns (thumbnail_url, asset_url, video_source_url, video_duration_sec).
        Spark ads: thumbnail only via image_ids; asset_url/video_source_url always None.
        Video ads: cover from /file/video/ad/ as thumbnail fallback; full video to asset_url.
        Image ads: full image to asset_url; same URL serves as thumbnail.
        All download failures are non-fatal (returns Nones)."""
        thumbnail_url: Optional[str] = None
        asset_url: Optional[str] = None
        video_source_url: Optional[str] = None
        asset_video_duration: Optional[float] = None

        _thumb_image_ids = (
            image_ids_raw if isinstance(image_ids_raw, list)
            else (image_ids_raw.split(",") if image_ids_raw else [])
        )
        if _thumb_image_ids:
            cover_url = await self._fetch_cover_image_url(access_token, advertiser_id, _thumb_image_ids[:1])
            if cover_url:
                thumbnail_url = await self._download_tiktok_thumbnail(cover_url, org_id, ad_id)

        try:
            if video_id_val and not is_spark:
                video_info = await self._fetch_video_info(access_token, advertiser_id, [str(video_id_val)])
                if video_info:
                    raw_video_url, raw_cover_url = video_info
                    if raw_video_url:
                        asset_url, asset_video_duration = await self._download_video_asset(raw_video_url, org_id, ad_id)
                        video_source_url = raw_video_url
                    if not thumbnail_url and raw_cover_url:
                        thumbnail_url = await self._download_tiktok_thumbnail(raw_cover_url, org_id, ad_id)
                else:
                    if not thumbnail_url and tiktok_item_id:
                        oembed_thumb = await self._fetch_tiktok_oembed_thumbnail(tiktok_item_id)
                        if oembed_thumb:
                            thumbnail_url = await self._download_tiktok_thumbnail(oembed_thumb, org_id, ad_id)

            elif image_ids_raw and not video_id_val and not is_spark:
                image_ids_list = (
                    image_ids_raw if isinstance(image_ids_raw, list)
                    else (image_ids_raw.split(",") if image_ids_raw else [])
                )
                if image_ids_list:
                    image_url = await self._fetch_cover_image_url(access_token, advertiser_id, image_ids_list[:1])
                    if image_url:
                        asset_url = await self._download_image_asset(image_url, org_id, ad_id)
                    else:
                        logger.info("TikTok ad %s: /file/image/ad/ returned no URL", ad_id)

            elif is_spark:
                # Spark ad — try info endpoint first, then oEmbed for thumbnail.
                if not thumbnail_url and video_id_val:
                    video_info = await self._fetch_video_info(access_token, advertiser_id, [str(video_id_val)])
                    if video_info and video_info[1]:
                        thumbnail_url = await self._download_tiktok_thumbnail(video_info[1], org_id, ad_id)
                if not thumbnail_url and tiktok_item_id:
                    oembed_thumb = await self._fetch_tiktok_oembed_thumbnail(tiktok_item_id)
                    if oembed_thumb:
                        thumbnail_url = await self._download_tiktok_thumbnail(oembed_thumb, org_id, ad_id)

            else:
                logger.info("TikTok ad %s: no video_id and no image_ids — nothing to download", ad_id)

        except Exception as e:
            logger.warning("Asset download failed for ad %s (non-fatal): %s", ad_id, e, exc_info=True)
            asset_url = None
            video_source_url = None

        return thumbnail_url, asset_url, video_source_url, asset_video_duration

    async def _resolve_tiktok_handle(self, tiktok_item_id: str) -> Optional[str]:
        """Resolve @handle for a public TikTok post by following redirects from /video/{id}."""
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://www.tiktok.com/video/{tiktok_item_id}",
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                )
                final_url = str(resp.url)
                match = re.search(r'/@([^/]+)/video/', final_url)
                if match:
                    logger.debug("Resolved TikTok handle=%s for item_id=%s", match.group(1), tiktok_item_id)
                    return match.group(1)
                logger.warning("TikTok handle resolve: no @handle in final URL %s (item_id=%s status=%s)", final_url, tiktok_item_id, resp.status_code)
        except Exception as e:
            logger.warning("TikTok handle resolution failed for item_id=%s: %s", tiktok_item_id, e)
        return None

    async def _fetch_tiktok_oembed_thumbnail(
        self,
        tiktok_item_id: str,
    ) -> Optional[str]:
        """Fetch thumbnail URL via TikTok oEmbed. Resolves @handle first since oEmbed requires @handle/video/{id} format."""
        handle = await self._resolve_tiktok_handle(tiktok_item_id)
        if handle:
            post_url = f"https://www.tiktok.com/@{handle}/video/{tiktok_item_id}"
        else:
            post_url = f"https://www.tiktok.com/video/{tiktok_item_id}"
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    "https://www.tiktok.com/oembed",
                    params={"url": post_url},
                    headers={"User-Agent": "Mozilla/5.0 (compatible; BrainsuiteBot/1.0)"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    thumb = data.get("thumbnail_url")
                    if thumb:
                        logger.info("TikTok oEmbed thumbnail retrieved for item_id=%s handle=%s", tiktok_item_id, handle)
                        return thumb
                else:
                    logger.warning("TikTok oEmbed %s for item_id=%s url=%s", resp.status_code, tiktok_item_id, post_url)
        except Exception as e:
            logger.warning("TikTok oEmbed exception for item_id=%s: %s", tiktok_item_id, e, exc_info=True)
        return None

    async def _fetch_cover_image_url(
        self,
        access_token: str,
        advertiser_id: str,
        image_ids: List[str],
    ) -> Optional[str]:
        """Fetch the cover image download URL for given image IDs via /file/image/ad/."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{TIKTOK_API_BASE}/file/image/ad/",
                    params={
                        "advertiser_id": advertiser_id,
                        "image_ids": json.dumps([str(iid) for iid in image_ids]),
                    },
                    headers={"Access-Token": access_token},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") != 0:
                    logger.warning("TikTok /file/image/ad/ error: %s", data.get("message"))
                    return None
                images = data.get("data", {}).get("list", [])
                if images:
                    return images[0].get("image_url")
        except httpx.HTTPStatusError as e:
            logger.warning("TikTok /file/image/ad/ http_%s advertiser=%s image_ids=%s body=%s", e.response.status_code, advertiser_id, image_ids, e.response.text[:300])
        except httpx.RequestError as e:
            logger.warning("Failed to fetch TikTok cover image URL: %s", e)
        return None

    async def _fetch_video_info(
        self,
        access_token: str,
        advertiser_id: str,
        video_ids: List[str],
    ) -> Optional[tuple]:
        """Fetch video download URL and thumbnail via GET /file/video/ad/info/.
        Returns (video_url, cover_url) or None. Single call covers both needs.
        TikTok response fields: preview_url (video), video_cover_url or poster_url (thumbnail).
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{TIKTOK_API_BASE}/file/video/ad/info/",
                    params={
                        "advertiser_id": advertiser_id,
                        "video_ids": json.dumps([str(vid) for vid in video_ids]),
                    },
                    headers={"Access-Token": access_token},
                )
                resp.raise_for_status()
                data = resp.json()
                code = data.get("code")
                if code != 0:
                    logger.warning("TikTok /file/video/ad/info/ api_code=%s msg=%s video_ids=%s", code, data.get("message"), video_ids)
                    return None
                videos = data.get("data", {}).get("list", [])
                if not videos:
                    logger.warning("TikTok /file/video/ad/info/ empty list for video_ids=%s advertiser=%s", video_ids, advertiser_id)
                    return None
                v = videos[0]
                video_url = v.get("preview_url") or v.get("video_url")
                cover_url = v.get("video_cover_url") or v.get("poster_url")
                logger.info("TikTok /file/video/ad/info/ ok video_id=%s video_url=%s cover_url=%s", video_ids[0], bool(video_url), bool(cover_url))
                return video_url, cover_url
        except httpx.HTTPStatusError as e:
            logger.warning("TikTok /file/video/ad/info/ http_%s advertiser=%s video_ids=%s body=%s", e.response.status_code, advertiser_id, video_ids, e.response.text[:300])
        except httpx.RequestError as e:
            logger.warning("TikTok /file/video/ad/info/ request error: %s", e)
        return None

    async def _download_video_asset(
        self,
        url: str,
        org_id: str,
        ad_id: str,
    ) -> tuple[Optional[str], Optional[float]]:
        """Download a TikTok video from URL, upload to S3/MinIO. Returns (served_url, duration_seconds).
        Storage path: creatives/{org_id}/video_tiktok_{ad_id}.mp4
        Decision D-04: Inline download; failures are non-fatal (log + return None, None).
        Decision D-06: Result stored in asset_url (scoring/autofill input, not thumbnail).
        """
        from app.services.object_storage import get_object_storage
        from app.services.sync.video_utils import probe_duration_from_bytes
        obj_storage = get_object_storage()

        filename = f"video_tiktok_{ad_id}.mp4"
        relative_path = f"creatives/{org_id}/{filename}"

        if obj_storage.file_exists(relative_path):
            return obj_storage.served_url(relative_path), None

        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            served_url = obj_storage.upload_bytes(resp.content, relative_path, content_type="video/mp4")
            duration = await asyncio.to_thread(probe_duration_from_bytes, resp.content, ".mp4")
            logger.info("Downloaded TikTok video for ad %s: %s (%d bytes, duration=%s)", ad_id, filename, len(resp.content), duration)
            return served_url, duration
        except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
            logger.warning("Failed to download TikTok video for ad %s: %s", ad_id, e, exc_info=True)
            return None, None

    async def _download_image_asset(
        self,
        image_url: str,
        org_id: str,
        ad_id: str,
    ) -> Optional[str]:
        """Download a TikTok full-resolution image and upload to S3/MinIO. Returns served URL or None.
        Storage path: creatives/{org_id}/image_tiktok_{ad_id}.jpg
        Decision D-03: Full-resolution image for scoring/autofill input; separate from thumbnail_url.
        Decision D-04: Failures are non-fatal (log + return None).
        """
        from app.services.object_storage import get_object_storage
        obj_storage = get_object_storage()

        filename = f"image_tiktok_{ad_id}.jpg"
        relative_path = f"creatives/{org_id}/{filename}"

        if obj_storage.file_exists(relative_path):
            return obj_storage.served_url(relative_path)

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
            if len(resp.content) < 100:
                logger.warning("TikTok image for ad %s too small (%d bytes), skipping", ad_id, len(resp.content))
                return None
            served_url = obj_storage.upload_bytes(resp.content, relative_path, content_type="image/jpeg")
            logger.info("Downloaded TikTok image for ad %s: %s (%d bytes)", ad_id, filename, len(resp.content))
            return served_url
        except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
            logger.warning("Failed to download TikTok image for ad %s: %s", ad_id, e, exc_info=True)
            return None

    async def _download_tiktok_thumbnail(
        self,
        image_url: str,
        org_id: str,
        ad_id: str,
    ) -> Optional[str]:
        """Download a TikTok cover image and upload to GCS. Returns served URL or None."""
        from app.services.object_storage import get_object_storage
        obj_storage = get_object_storage()

        filename = f"thumb_tiktok_{ad_id}.jpg"
        relative_path = f"creatives/{org_id}/{filename}"

        if obj_storage.file_exists(relative_path):
            return obj_storage.served_url(relative_path)

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
            if len(resp.content) < 100:
                logger.warning("TikTok thumbnail for ad %s too small (%d bytes), skipping", ad_id, len(resp.content))
                return None
            served_url = obj_storage.upload_bytes(resp.content, relative_path, content_type="image/jpeg")
            logger.info("Downloaded TikTok thumbnail for ad %s: %s (%d bytes)", ad_id, filename, len(resp.content))
            return served_url
        except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
            logger.warning("Failed to download TikTok thumbnail for ad %s: %s", ad_id, e, exc_info=True)
            return None

    async def _fetch_campaign_info(
        self,
        access_token: str,
        advertiser_id: str,
        campaign_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Fetch campaign-level metadata (objective, budget_mode, status) via /campaign/get/."""
        all_campaigns: List[Dict[str, Any]] = []
        page = 1
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                resp = await client.get(
                    f"{TIKTOK_API_BASE}/campaign/get/",
                    params={
                        "advertiser_id": advertiser_id,
                        "filtering": json.dumps({"campaign_ids": [str(cid) for cid in campaign_ids]}),
                        "fields": json.dumps(CAMPAIGN_INFO_FIELDS),
                        "page_size": 100,
                        "page": page,
                    },
                    headers={"Access-Token": access_token},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 40100:
                    logger.warning("TikTok /campaign/get/ rate limit (code 40100), backing off 60s")
                    await asyncio.sleep(60)
                    continue
                if data.get("code") != 0:
                    logger.warning("TikTok /campaign/get/ error: %s", data.get("message"))
                    break
                page_data = data.get("data", {})
                all_campaigns.extend(page_data.get("list", []))
                page_info = page_data.get("page_info", {})
                if page >= page_info.get("total_page", 1):
                    break
                page += 1
        return all_campaigns

    async def _fetch_adgroup_info(
        self,
        access_token: str,
        advertiser_id: str,
        adgroup_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Fetch adgroup-level metadata (optimization_goal, billing_event, status) via /adgroup/get/."""
        all_adgroups: List[Dict[str, Any]] = []
        page = 1
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                resp = await client.get(
                    f"{TIKTOK_API_BASE}/adgroup/get/",
                    params={
                        "advertiser_id": advertiser_id,
                        "filtering": json.dumps({"adgroup_ids": [str(agid) for agid in adgroup_ids]}),
                        "fields": json.dumps(ADGROUP_INFO_FIELDS),
                        "page_size": 100,
                        "page": page,
                    },
                    headers={"Access-Token": access_token},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 40100:
                    logger.warning("TikTok /adgroup/get/ rate limit (code 40100), backing off 60s")
                    await asyncio.sleep(60)
                    continue
                if data.get("code") != 0:
                    logger.warning("TikTok /adgroup/get/ error: %s", data.get("message"))
                    break
                page_data = data.get("data", {})
                all_adgroups.extend(page_data.get("list", []))
                page_info = page_data.get("page_info", {})
                if page >= page_info.get("total_page", 1):
                    break
                page += 1
        return all_adgroups

    async def _fetch_ad_info(
        self, access_token: str, advertiser_id: str, ad_ids: List[str]
    ) -> List[Dict[str, Any]]:
        if not ad_ids:
            return []

        fields = list(self._ad_info_cache.get(advertiser_id, AD_INFO_FIELDS))
        all_ads: List[Dict[str, Any]] = []
        page = 1

        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                resp = await client.get(
                    f"{TIKTOK_API_BASE}/ad/get/",
                    params={
                        "advertiser_id": advertiser_id,
                        "filtering": json.dumps({"ad_ids": [str(aid) for aid in ad_ids]}),
                        "fields": json.dumps(fields),
                        "page_size": 100,
                        "page": page,
                    },
                    headers={"Access-Token": access_token},
                )
                if resp.status_code != 200:
                    logger.error("TikTok /ad/get/ HTTP %s", resp.status_code)
                    break

                data = resp.json()
                if data.get("code") == 40100:
                    logger.warning("TikTok /ad/get/ rate limit (code 40100), backing off 60s")
                    await asyncio.sleep(60)
                    continue

                if data.get("code") != 0:
                    msg = data.get("message", "")
                    # Adaptive field stripping: TikTok reports the first bad field as
                    # "... error is <fieldname>" — strip it and retry once.
                    match = re.search(r"error is (\w+)", msg)
                    if match:
                        bad_field = match.group(1)
                        if bad_field in fields:
                            fields = [f for f in fields if f != bad_field]
                            self._ad_info_cache[advertiser_id] = fields
                            logger.warning(
                                "TikTok /ad/get/: stripped unsupported field '%s' for advertiser %s, retrying",
                                bad_field, advertiser_id,
                            )
                            all_ads = []
                            page = 1
                            continue
                    logger.error("TikTok /ad/get/ error: %s", msg)
                    break

                page_data = data.get("data", {})
                ads_list = page_data.get("list", [])
                all_ads.extend(ads_list)

                page_info = page_data.get("page_info", {})
                total_pages = page_info.get("total_page", 1)
                if page >= total_pages:
                    break
                page += 1

        return all_ads


tiktok_sync = TikTokSyncService()
