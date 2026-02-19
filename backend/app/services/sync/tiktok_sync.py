import asyncio
import httpx
import logging
import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import TikTokRawPerformance
from app.core.security import decrypt_token

logger = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"

AD_REPORT_DIMENSIONS = ["ad_id", "stat_time_day"]

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
    "paid_likes",
    "paid_comments",
    "paid_shares",
    "paid_follows",
    "result",
    "result_rate",
    "cost_per_result",
]

AD_INFO_FIELDS = [
    "ad_id",
    "ad_name",
    "campaign_id",
    "campaign_name",
    "adgroup_id",
    "adgroup_name",
    "status",
    "objective_type",
    "ad_format",
    "creative_type",
    "identity_type",
    "display_name",
    "landing_page_url",
    "video_id",
    "image_ids",
    "call_to_action",
    "optimization_goal",
    "billing_event",
    "buying_type",
]


class TikTokSyncService:

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

        if all_ad_ids:
            logger.info(f"  Fetching ad info for {len(all_ad_ids)} unique ads via /ad/get/")
            await self._enrich_from_ad_get(db, connection, access_token, advertiser_id, list(all_ad_ids))

        logger.info(f"TikTok sync complete: fetched={total_fetched}, upserted={total_upserted}")
        return {"fetched": total_fetched, "upserted": total_upserted}

    async def _fetch_ad_reports(
        self,
        access_token: str,
        advertiser_id: str,
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        records = []
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
                            "metrics": json.dumps(AD_REPORT_METRICS),
                            "start_date": date_from.strftime("%Y-%m-%d"),
                            "end_date": date_to.strftime("%Y-%m-%d"),
                            "page": page,
                            "page_size": page_size,
                        },
                        headers={"Access-Token": access_token},
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    if data.get("code") != 0:
                        logger.error(f"TikTok report error: {data.get('message')}")
                        break

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
                        logger.error(f"TikTok HTTP error: {e}")
                        break

        return records

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
        except Exception:
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
                "report_date": dims.get("stat_time_day"),
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
                "profile_visits": self._safe_int(m.get("profile_visits")),
                "profile_visits_rate": self._safe_float(m.get("profile_visits_rate")),
                "paid_likes": self._safe_int(m.get("paid_likes")),
                "paid_comments": self._safe_int(m.get("paid_comments")),
                "paid_shares": self._safe_int(m.get("paid_shares")),
                "paid_follows": self._safe_int(m.get("paid_follows")),
                "total_likes": self._safe_int(m.get("likes")),
                "total_comments": self._safe_int(m.get("comments")),
                "total_shares": self._safe_int(m.get("shares")),
                "total_follows": self._safe_int(m.get("follows")),
                "engagement_rate": self._safe_float(m.get("engagement_rate")),
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
                "is_validated": True,
                "is_processed": False,
            })

        stmt = pg_insert(TikTokRawPerformance).values(rows)
        update_cols = {c.name: getattr(stmt.excluded, c.name)
                       for c in TikTokRawPerformance.__table__.columns
                       if c.name not in ("id", "platform_connection_id", "report_date",
                                         "ad_id", "ad_account_id", "retrieved_at")}
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
        batch_size = 100
        for i in range(0, len(ad_ids), batch_size):
            batch = ad_ids[i:i + batch_size]
            try:
                ads = await self._fetch_ad_info(access_token, advertiser_id, batch)
            except Exception as e:
                logger.error(f"  Failed to fetch ad info batch: {e}")
                continue

            for ad in ads:
                ad_id = str(ad.get("ad_id", ""))
                if not ad_id:
                    continue

                image_ids_raw = ad.get("image_ids")
                image_ids_str = ",".join(image_ids_raw) if isinstance(image_ids_raw, list) else None

                ad_format = ad.get("ad_format")
                creative_type = ad.get("creative_type")
                is_spark = ad.get("identity_type") in ("CUSTOMIZED_USER", "AUTH_CODE")

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
                        campaign_objective=ad.get("objective_type"),
                        ad_status=ad.get("status"),
                        ad_format=ad_format,
                        creative_type=creative_type,
                        is_spark_ad=is_spark,
                        identity_type=ad.get("identity_type"),
                        display_name=ad.get("display_name"),
                        landing_page_url=ad.get("landing_page_url"),
                        video_id=str(ad.get("video_id", "")) if ad.get("video_id") else None,
                        image_ids=image_ids_str,
                        optimization_goal=ad.get("optimization_goal"),
                        billing_event=ad.get("billing_event"),
                        buying_type=ad.get("buying_type"),
                    )
                )

            await db.flush()
            logger.info(f"  Enriched {len(batch)} ads from /ad/get/")

        await db.commit()

    async def _fetch_ad_info(
        self, access_token: str, advertiser_id: str, ad_ids: List[str]
    ) -> List[Dict[str, Any]]:
        if not ad_ids:
            return []

        all_ads = []
        page = 1

        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                resp = await client.get(
                    f"{TIKTOK_API_BASE}/ad/get/",
                    params={
                        "advertiser_id": advertiser_id,
                        "filtering": json.dumps({"ad_ids": [str(aid) for aid in ad_ids]}),
                        "fields": json.dumps(AD_INFO_FIELDS),
                        "page_size": 100,
                        "page": page,
                    },
                    headers={"Access-Token": access_token},
                )
                if resp.status_code != 200:
                    logger.error(f"TikTok /ad/get/ HTTP {resp.status_code}")
                    break

                data = resp.json()
                if data.get("code") != 0:
                    logger.error(f"TikTok /ad/get/ error: {data.get('message')}")
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
