"""
YouTube / Google Ads data sync service.
Uses Google Ads API v15 with GAQL (Google Ads Query Language).
All video ad performance data lives in Google Ads, not YouTube Data API.
"""
import httpx
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import YouTubeRawPerformance
from app.core.security import decrypt_token
from app.services.platform.youtube_oauth import youtube_oauth

logger = logging.getLogger(__name__)

GOOGLE_ADS_API_BASE = "https://googleads.googleapis.com/v15"


class YouTubeSyncService:

    async def sync_date_range(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        date_from: date,
        date_to: date,
        sync_job_id: Optional[str] = None,
    ) -> Dict[str, int]:
        access_token = await self._get_valid_token(db, connection)
        customer_id = connection.ad_account_id

        total_fetched = 0
        total_upserted = 0

        # Fetch in 30-day chunks
        chunk_start = date_from
        while chunk_start <= date_to:
            chunk_end = min(chunk_start + timedelta(days=29), date_to)
            records = await self._fetch_video_ad_performance(
                access_token, customer_id, chunk_start, chunk_end
            )
            upserted = await self._upsert_records(db, connection, records, sync_job_id)
            total_fetched += len(records)
            total_upserted += upserted
            chunk_start = chunk_end + timedelta(days=1)

        return {"fetched": total_fetched, "upserted": total_upserted}

    async def _get_valid_token(
        self, db: AsyncSession, connection: PlatformConnection
    ) -> str:
        """Refresh access token if needed."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        if connection.token_expiry and connection.token_expiry > now:
            return decrypt_token(connection.access_token_encrypted)

        # Refresh
        refresh_token = decrypt_token(connection.refresh_token_encrypted)
        new_tokens = await youtube_oauth.refresh_access_token(refresh_token)
        new_access = new_tokens.get("access_token")

        from app.core.security import encrypt_token
        from datetime import timedelta
        connection.access_token_encrypted = encrypt_token(new_access)
        connection.token_expiry = now + timedelta(seconds=new_tokens.get("expires_in", 3600))
        db.add(connection)
        await db.flush()

        return new_access

    async def _fetch_video_ad_performance(
        self,
        access_token: str,
        customer_id: str,
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        """Fetch video ad performance via GAQL."""
        from app.core.config import settings

        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                campaign.advertising_channel_type,
                campaign.advertising_channel_sub_type,
                ad_group.id,
                ad_group.name,
                ad_group_ad.ad.id,
                ad_group_ad.ad.name,
                ad_group_ad.ad.type,
                ad_group_ad.ad.video_ad.video.resource_name,
                ad_group_ad.ad.image_ad.image_url,
                segments.date,
                metrics.cost_micros,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.average_cpm,
                metrics.conversions,
                metrics.conversions_value,
                metrics.video_views,
                metrics.video_view_rate,
                metrics.video_quartile_p25_rate,
                metrics.video_quartile_p50_rate,
                metrics.video_quartile_p75_rate,
                metrics.video_quartile_p100_rate,
                metrics.engagements,
                metrics.engagement_rate
            FROM ad_group_ad
            WHERE
                segments.date BETWEEN '{date_from.strftime("%Y-%m-%d")}' AND '{date_to.strftime("%Y-%m-%d")}'
                AND campaign.advertising_channel_type IN ('VIDEO', 'DISPLAY')
                AND ad_group_ad.status != 'REMOVED'
            ORDER BY segments.date DESC
        """

        records = []
        next_page_token = None

        async with httpx.AsyncClient(timeout=60) as client:
            while True:
                body = {"query": query}
                if next_page_token:
                    body["pageToken"] = next_page_token

                resp = await client.post(
                    f"{GOOGLE_ADS_API_BASE}/customers/{customer_id}/googleAds:search",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "developer-token": settings.GOOGLE_DEVELOPER_TOKEN or "",
                        "login-customer-id": customer_id,
                    },
                    json=body,
                )

                if resp.status_code != 200:
                    logger.error(f"Google Ads API error {resp.status_code}: {resp.text[:500]}")
                    break

                data = resp.json()
                results = data.get("results", [])
                records.extend(results)

                next_page_token = data.get("nextPageToken")
                if not next_page_token:
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
            campaign = r.get("campaign", {})
            ad_group = r.get("adGroup", {})
            ad = r.get("adGroupAd", {}).get("ad", {})
            metrics = r.get("metrics", {})
            segments = r.get("segments", {})

            cost_micros = int(metrics.get("costMicros", 0) or 0)
            spend = Decimal(str(cost_micros / 1_000_000))
            impressions = int(metrics.get("impressions", 0) or 0)
            clicks = int(metrics.get("clicks", 0) or 0)
            conversions = float(metrics.get("conversions", 0) or 0)
            conversion_value = Decimal(str(metrics.get("conversionsValue", 0) or 0))

            roas = float(conversion_value / spend) if spend and conversion_value else None
            cvr = (conversions / clicks) if clicks else None

            video_id = ad.get("videoAd", {}).get("video", {}).get("resourceName", "")
            thumbnail_url = ad.get("imageAd", {}).get("imageUrl")

            rows.append({
                "platform_connection_id": connection.id,
                "sync_job_id": sync_job_id,
                "report_date": segments.get("date"),
                "ad_account_id": connection.ad_account_id,
                "campaign_id": str(campaign.get("id", "")),
                "campaign_name": campaign.get("name"),
                "campaign_objective": campaign.get("advertisingChannelSubType"),
                "ad_group_id": str(ad_group.get("id", "")),
                "ad_group_name": ad_group.get("name"),
                "ad_id": str(ad.get("id", "")),
                "ad_name": ad.get("name"),
                "video_url": video_id,
                "thumbnail_url": thumbnail_url,
                "placement_type": campaign.get("advertisingChannelType"),
                "currency": connection.currency,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "ctr": float(metrics.get("ctr", 0) or 0),
                "cpm": Decimal(str(float(metrics.get("averageCpm", 0) or 0) / 1_000_000)),
                "conversions": int(conversions),
                "conversion_value": conversion_value,
                "cvr": cvr,
                "roas": roas,
                "video_views": int(metrics.get("videoViews", 0) or 0),
                "view_rate": float(metrics.get("videoViewRate", 0) or 0),
                "video_view_through_rate": float(metrics.get("videoQuartileP100Rate", 0) or 0),
                "video_quartile_p25": float(metrics.get("videoQuartileP25Rate", 0) or 0),
                "video_quartile_p50": float(metrics.get("videoQuartileP50Rate", 0) or 0),
                "video_quartile_p75": float(metrics.get("videoQuartileP75Rate", 0) or 0),
                "video_quartile_p100": float(metrics.get("videoQuartileP100Rate", 0) or 0),
                "is_validated": True,
                "is_processed": False,
            })

        stmt = pg_insert(YouTubeRawPerformance).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_youtube_daily_ad",
            set_={
                "spend": stmt.excluded.spend,
                "impressions": stmt.excluded.impressions,
                "clicks": stmt.excluded.clicks,
                "conversions": stmt.excluded.conversions,
                "roas": stmt.excluded.roas,
                "video_views": stmt.excluded.video_views,
                "is_processed": False,
            }
        )
        await db.execute(stmt)
        return len(rows)


youtube_sync = YouTubeSyncService()
