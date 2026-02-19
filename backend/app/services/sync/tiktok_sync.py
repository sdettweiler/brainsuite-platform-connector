"""
TikTok Ads data sync service.
Uses TikTok Marketing API v1.3 for ad-level performance data.
"""
import httpx
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import TikTokRawPerformance
from app.core.security import decrypt_token

logger = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"

# Fields for ad-level reports
AD_REPORT_DIMENSIONS = ["ad_id", "stat_time_day"]
AD_REPORT_METRICS = [
    "spend",
    "impressions",
    "clicks",
    "ctr",
    "cpm",
    "reach",
    "conversion",
    "cost_per_conversion",
    "conversion_rate",
    "real_time_conversion",
    "total_purchase_value",
    "total_sales_lead_value",
    "video_play_actions",
    "video_watched_2s",
    "video_watched_6s",
    "average_video_play",
    "video_views_p25",
    "video_views_p50",
    "video_views_p75",
    "video_views_p100",
    "profile_visits",
    "likes",
    "comments",
    "shares",
    "follows",
    "engagements",
    "engagement_rate",
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

        # Fetch in 30-day chunks
        chunk_start = date_from
        while chunk_start <= date_to:
            chunk_end = min(chunk_start + timedelta(days=29), date_to)
            records = await self._fetch_ad_reports(
                access_token, advertiser_id, chunk_start, chunk_end
            )
            upserted = await self._upsert_records(db, connection, records, sync_job_id)
            total_fetched += len(records)
            total_upserted += upserted
            chunk_start = chunk_end + timedelta(days=1)

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
                            "dimensions": '["ad_id","stat_time_day"]',
                            "metrics": "[" + ",".join(f'"{m}"' for m in AD_REPORT_METRICS) + "]",
                            "start_date": date_from.strftime("%Y-%m-%d"),
                            "end_date": date_to.strftime("%Y-%m-%d"),
                            "page": page,
                            "page_size": page_size,
                        },
                        headers={
                            "Access-Token": access_token,
                        },
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
                        import asyncio
                        await asyncio.sleep(60)
                    else:
                        logger.error(f"TikTok HTTP error: {e}")
                        break

        return records

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
            metrics = r.get("metrics", {})

            spend = Decimal(str(metrics.get("spend", 0) or 0))
            impressions = int(metrics.get("impressions", 0) or 0)
            conversions = int(metrics.get("conversion", 0) or 0)
            conversion_value = Decimal(str(metrics.get("total_purchase_value", 0) or 0))
            video_views = int(metrics.get("video_play_actions", 0) or 0)
            video_p100 = float(metrics.get("video_views_p100", 0) or 0)
            video_completion_rate = (video_p100 / video_views * 100) if video_p100 and video_views else None

            engagements = int(metrics.get("engagements", 0) or 0)
            engagement_rate = float(metrics.get("engagement_rate", 0) or 0)
            roas = float(conversion_value / spend) if spend and conversion_value else None
            cvr = float(metrics.get("conversion_rate", 0) or 0)

            rows.append({
                "platform_connection_id": connection.id,
                "sync_job_id": sync_job_id,
                "report_date": dims.get("stat_time_day"),
                "ad_account_id": connection.ad_account_id,
                "ad_id": dims.get("ad_id"),
                "currency": connection.currency,
                "spend": spend,
                "impressions": impressions,
                "clicks": int(metrics.get("clicks", 0) or 0),
                "ctr": float(metrics.get("ctr", 0) or 0),
                "cpm": Decimal(str(metrics.get("cpm", 0) or 0)),
                "conversions": conversions,
                "conversion_value": conversion_value,
                "cvr": cvr,
                "roas": roas,
                "video_views": video_views,
                "video_completion_rate": video_completion_rate,
                "engagement_rate": engagement_rate,
                "is_validated": True,
                "is_processed": False,
            })

        stmt = pg_insert(TikTokRawPerformance).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_tiktok_daily_ad",
            set_={
                "spend": stmt.excluded.spend,
                "impressions": stmt.excluded.impressions,
                "clicks": stmt.excluded.clicks,
                "ctr": stmt.excluded.ctr,
                "conversions": stmt.excluded.conversions,
                "conversion_value": stmt.excluded.conversion_value,
                "cvr": stmt.excluded.cvr,
                "roas": stmt.excluded.roas,
                "video_views": stmt.excluded.video_views,
                "video_completion_rate": stmt.excluded.video_completion_rate,
                "is_processed": False,
            }
        )
        await db.execute(stmt)
        return len(rows)

    async def fetch_ad_info(
        self, access_token: str, advertiser_id: str, ad_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Fetch ad creative details for given ad IDs."""
        if not ad_ids:
            return []

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{TIKTOK_API_BASE}/ad/get/",
                params={
                    "advertiser_id": advertiser_id,
                    "filtering": f'{{"ad_ids":{ad_ids[:100]}}}',
                    "fields": '["ad_id","ad_name","ad_format","video_id","image_ids","campaign_id","adgroup_id","status"]',
                    "page_size": 100,
                },
                headers={"Access-Token": access_token},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            return data.get("data", {}).get("list", [])


tiktok_sync = TikTokSyncService()
