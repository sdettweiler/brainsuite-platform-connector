"""
Meta Ads data sync service.
Fetches ad-level performance data in daily breakdowns using the Insights API.
Implements cursor-based pagination to retrieve all pages.
"""
import httpx
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import MetaRawPerformance, SyncJob
from app.core.security import decrypt_token

logger = logging.getLogger(__name__)

META_GRAPH_URL = "https://graph.facebook.com/v21.0"


class MetaAPIError(Exception):
    """Raised when Meta API returns a non-recoverable error."""
    pass

# Fields we fetch from Insights API
INSIGHTS_FIELDS = [
    "date_start",
    "date_stop",
    "account_id",
    "campaign_id",
    "campaign_name",
    "objective",
    "adset_id",
    "adset_name",
    "ad_id",
    "ad_name",
    "spend",
    "impressions",
    "clicks",
    "ctr",
    "reach",
    "frequency",
    "cpm",
    "cpc",
    "actions",          # conversions
    "action_values",    # conversion value
    "video_p25_watched_actions",
    "video_p50_watched_actions",
    "video_p75_watched_actions",
    "video_p100_watched_actions",
    "video_play_actions",
]

# Fields for creative metadata
CREATIVE_FIELDS = [
    "creative",
    "preview_shareable_link",
]


class MetaSyncService:

    async def sync_date_range(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        date_from: date,
        date_to: date,
        sync_job_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """Fetch and store performance data for a date range."""
        access_token = decrypt_token(connection.access_token_encrypted)
        account_id = f"act_{connection.ad_account_id}"

        total_fetched = 0
        total_upserted = 0
        api_errors = []

        logger.info(f"Meta sync: account={account_id}, range={date_from} to {date_to}")

        chunk_start = date_from
        while chunk_start <= date_to:
            chunk_end = min(chunk_start + timedelta(days=29), date_to)
            logger.info(f"  Fetching chunk {chunk_start} → {chunk_end}")
            try:
                records = await self._fetch_insights(
                    access_token, account_id, chunk_start, chunk_end
                )
            except MetaAPIError as e:
                api_errors.append(str(e))
                chunk_start = chunk_end + timedelta(days=1)
                continue
            logger.info(f"  Got {len(records)} records from API")
            upserted = await self._upsert_records(
                db, connection, records, sync_job_id
            )
            total_fetched += len(records)
            total_upserted += upserted
            chunk_start = chunk_end + timedelta(days=1)

        if api_errors and total_fetched == 0:
            raise MetaAPIError(f"All API requests failed: {api_errors[0]}")

        logger.info(f"Meta sync complete: fetched={total_fetched}, upserted={total_upserted}")
        return {"fetched": total_fetched, "upserted": total_upserted}

    async def _fetch_insights(
        self,
        access_token: str,
        account_id: str,
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        """Fetch insights with automatic cursor pagination."""
        records = []
        url = f"{META_GRAPH_URL}/{account_id}/insights"
        params = {
            "access_token": access_token,
            "level": "ad",
            "fields": ",".join(INSIGHTS_FIELDS),
            "time_range": f'{{"since":"{date_from.isoformat()}","until":"{date_to.isoformat()}"}}',
            "time_increment": 1,  # Daily breakdown
            "limit": 500,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            while url:
                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    data = resp.json()

                    if "error" in data:
                        logger.error(f"Meta API error: {data['error']}")
                        break

                    records.extend(data.get("data", []))

                    # Handle cursor pagination
                    paging = data.get("paging", {})
                    cursors = paging.get("cursors", {})
                    next_cursor = cursors.get("after")
                    has_next = "next" in paging

                    if has_next and next_cursor:
                        url = f"{META_GRAPH_URL}/{account_id}/insights"
                        params = {
                            "access_token": access_token,
                            "after": next_cursor,
                            "limit": 500,
                        }
                    else:
                        url = None
                        params = {}

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        logger.warning("Meta rate limit hit, backing off 60s")
                        import asyncio
                        await asyncio.sleep(60)
                    else:
                        error_msg = ""
                        try:
                            error_body = e.response.json()
                            error_msg = str(error_body.get("error", {}).get("message", error_body))
                            logger.error(f"Meta API error {e.response.status_code}: {error_body}")
                        except Exception:
                            error_msg = e.response.text[:500]
                            logger.error(f"Meta HTTP error {e.response.status_code}: {error_msg}")
                        raise MetaAPIError(f"HTTP {e.response.status_code}: {error_msg}")

        return records

    async def _upsert_records(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        records: List[Dict[str, Any]],
        sync_job_id: Optional[str],
    ) -> int:
        """Upsert raw records into meta_raw_performance."""
        if not records:
            return 0

        rows = []
        for r in records:
            # Parse conversions from actions array
            actions = r.get("actions", [])
            conversions = sum(
                int(a.get("value", 0))
                for a in actions
                if a.get("action_type") in ("purchase", "offsite_conversion.fb_pixel_purchase", "lead", "complete_registration")
            )
            action_values = r.get("action_values", [])
            conversion_value = sum(
                float(a.get("value", 0))
                for a in action_values
                if a.get("action_type") in ("purchase", "offsite_conversion.fb_pixel_purchase")
            )

            # Video views from video_play_actions
            video_plays = r.get("video_play_actions", [{}])
            video_views = int(video_plays[0].get("value", 0)) if video_plays else None

            # Video completion from p100
            video_p100 = r.get("video_p100_watched_actions", [{}])
            video_completed = int(video_p100[0].get("value", 0)) if video_p100 else None

            spend = Decimal(str(r.get("spend", 0) or 0))
            impressions = int(r.get("impressions", 0) or 0)
            cvr = (conversions / int(r.get("clicks", 1) or 1)) if conversions else None
            roas = (conversion_value / float(spend)) if spend and conversion_value else None
            video_view_rate = (video_views / impressions * 100) if video_views and impressions else None

            rows.append({
                "platform_connection_id": connection.id,
                "sync_job_id": sync_job_id,
                "report_date": date.fromisoformat(r.get("date_start")),
                "ad_account_id": connection.ad_account_id,
                "campaign_id": r.get("campaign_id"),
                "campaign_name": r.get("campaign_name"),
                "campaign_objective": r.get("objective"),
                "ad_set_id": r.get("adset_id"),
                "ad_set_name": r.get("adset_name"),
                "ad_id": r.get("ad_id"),
                "ad_name": r.get("ad_name"),
                "currency": connection.currency,
                "spend": spend,
                "impressions": impressions,
                "clicks": int(r.get("clicks", 0) or 0),
                "ctr": float(r.get("ctr", 0) or 0),
                "reach": int(r.get("reach", 0) or 0),
                "frequency": float(r.get("frequency", 0) or 0),
                "cpm": Decimal(str(r.get("cpm", 0) or 0)),
                "cpc": Decimal(str(r.get("cpc", 0) or 0)),
                "conversions": conversions,
                "conversion_value": Decimal(str(conversion_value)),
                "cvr": cvr,
                "roas": roas,
                "video_views": video_views,
                "video_view_rate": video_view_rate,
                "is_validated": True,
                "is_processed": False,
            })

        # Use PostgreSQL ON CONFLICT DO UPDATE
        stmt = pg_insert(MetaRawPerformance).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_meta_daily_ad",
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
                "video_view_rate": stmt.excluded.video_view_rate,
                "is_processed": False,
            }
        )
        await db.execute(stmt)
        return len(rows)

    async def fetch_ad_creatives(
        self,
        access_token: str,
        ad_id: str,
    ) -> Dict[str, Any]:
        """Fetch creative details for a specific ad."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{META_GRAPH_URL}/{ad_id}",
                params={
                    "access_token": access_token,
                    "fields": "id,name,creative{id,thumbnail_url,video_id,image_url,object_type,effective_object_story_id},adset{targeting}",
                },
            )
            if resp.status_code != 200:
                return {}
            return resp.json()


meta_sync = MetaSyncService()
