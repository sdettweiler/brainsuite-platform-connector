"""
Meta Ads data sync service.
Fetches ad-level performance data in daily breakdowns using the Insights API.
Also fetches creative details (image/video URLs) and downloads assets locally.
Implements cursor-based pagination to retrieve all pages.
"""
import asyncio
import httpx
import logging
import os
import uuid as uuid_mod
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import MetaRawPerformance, SyncJob
from app.core.security import decrypt_token

logger = logging.getLogger(__name__)

META_GRAPH_URL = "https://graph.facebook.com/v21.0"

CREATIVES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "static", "creatives")
)

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
    "actions",
    "action_values",
    "video_p25_watched_actions",
    "video_p50_watched_actions",
    "video_p75_watched_actions",
    "video_p100_watched_actions",
    "video_play_actions",
]


class MetaAPIError(Exception):
    pass


class MetaSyncService:

    async def sync_date_range(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        date_from: date,
        date_to: date,
        sync_job_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """Fetch and store performance data for a date range, then fetch creatives."""
        access_token = decrypt_token(connection.access_token_encrypted)
        account_id = f"act_{connection.ad_account_id}"

        total_fetched = 0
        total_upserted = 0
        api_errors = []
        all_ad_ids = set()

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

            for r in records:
                ad_id = r.get("ad_id")
                if ad_id:
                    all_ad_ids.add(ad_id)

            upserted = await self._upsert_records(
                db, connection, records, sync_job_id
            )
            total_fetched += len(records)
            total_upserted += upserted
            chunk_start = chunk_end + timedelta(days=1)

        if api_errors and total_fetched == 0:
            raise MetaAPIError(f"All API requests failed: {api_errors[0]}")

        if all_ad_ids:
            logger.info(f"  Fetching creatives for {len(all_ad_ids)} unique ads")
            await self._fetch_and_store_creatives(
                db, connection, access_token, account_id, list(all_ad_ids)
            )

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
            "time_increment": 1,
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

            video_plays = r.get("video_play_actions", [{}])
            video_views = int(video_plays[0].get("value", 0)) if video_plays else None

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

    async def _fetch_and_store_creatives(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        access_token: str,
        account_id: str,
        ad_ids: List[str],
    ) -> None:
        """Batch-fetch creative details for ads, download assets, update DB records."""
        org_dir = os.path.join(CREATIVES_DIR, str(connection.organization_id))
        os.makedirs(org_dir, exist_ok=True)

        batch_size = 50
        for i in range(0, len(ad_ids), batch_size):
            batch = ad_ids[i:i + batch_size]
            try:
                creatives = await self._batch_fetch_ad_creatives(access_token, account_id, batch)
            except Exception as e:
                logger.error(f"  Failed to fetch creative batch: {e}")
                continue

            for ad_id, creative_info in creatives.items():
                creative_data = creative_info.get("creative", {})
                creative_id = creative_data.get("id")
                object_type = creative_data.get("object_type", "").upper()
                image_url = creative_data.get("image_url")
                thumbnail_url = creative_data.get("thumbnail_url")
                video_id = creative_data.get("video_id")

                if object_type in ("VIDEO", "SHARE"):
                    ad_format = "VIDEO"
                elif object_type in ("PHOTO", "LINK"):
                    ad_format = "IMAGE"
                else:
                    ad_format = "IMAGE" if image_url else "VIDEO" if video_id else "IMAGE"

                source_url = image_url or thumbnail_url
                local_path = None
                served_url = None

                if source_url:
                    local_path, served_url = await self._download_asset(
                        source_url, org_dir, connection.organization_id, ad_id, "img"
                    )

                if video_id and not local_path:
                    video_source = await self._get_video_source(access_token, video_id)
                    if video_source:
                        local_path, served_url = await self._download_asset(
                            video_source, org_dir, connection.organization_id, ad_id, "vid"
                        )
                    if thumbnail_url and not served_url:
                        local_path, served_url = await self._download_asset(
                            thumbnail_url, org_dir, connection.organization_id, ad_id, "thumb"
                        )

                await db.execute(
                    update(MetaRawPerformance)
                    .where(
                        MetaRawPerformance.ad_id == ad_id,
                        MetaRawPerformance.platform_connection_id == connection.id,
                    )
                    .values(
                        creative_id=creative_id,
                        ad_format=ad_format,
                        thumbnail_url=served_url or thumbnail_url or image_url,
                    )
                )

            await db.flush()
            logger.info(f"  Updated creatives for batch of {len(batch)} ads")

        await db.commit()

    async def _batch_fetch_ad_creatives(
        self,
        access_token: str,
        account_id: str,
        ad_ids: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch creative details for a batch of ads using the ads endpoint with filtering."""
        result = {}
        ids_str = ",".join(f'"{aid}"' for aid in ad_ids)
        url = f"{META_GRAPH_URL}/{account_id}/ads"
        params = {
            "access_token": access_token,
            "fields": "id,creative{id,thumbnail_url,image_url,video_id,object_type}",
            "filtering": f'[{{"field":"id","operator":"IN","value":[{ids_str}]}}]',
            "limit": 100,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            while url:
                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    data = resp.json()

                    if "error" in data:
                        logger.error(f"Meta creatives API error: {data['error']}")
                        break

                    for ad in data.get("data", []):
                        result[ad["id"]] = ad

                    paging = data.get("paging", {})
                    if "next" in paging:
                        url = paging["next"]
                        params = {}
                    else:
                        url = None

                except Exception as e:
                    logger.error(f"Failed to fetch ad creatives: {e}")
                    break

        return result

    async def _get_video_source(self, access_token: str, video_id: str) -> Optional[str]:
        """Get the source URL for a video asset."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{META_GRAPH_URL}/{video_id}",
                    params={"access_token": access_token, "fields": "source"},
                )
                if resp.status_code == 200:
                    return resp.json().get("source")
        except Exception as e:
            logger.warning(f"Failed to get video source for {video_id}: {e}")
        return None

    async def _download_asset(
        self,
        url: str,
        org_dir: str,
        org_id,
        ad_id: str,
        prefix: str,
    ) -> tuple:
        """Download a file from URL and save locally. Returns (local_path, served_url)."""
        try:
            ext = ".jpg"
            if ".png" in url.lower():
                ext = ".png"
            elif ".mp4" in url.lower():
                ext = ".mp4"
            elif ".webp" in url.lower():
                ext = ".webp"

            filename = f"{prefix}_{ad_id}{ext}"
            local_path = os.path.join(org_dir, filename)

            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                served_url = f"/static/creatives/{org_id}/{filename}"
                return local_path, served_url

            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()

                content_type = resp.headers.get("content-type", "")
                if "png" in content_type:
                    ext = ".png"
                elif "mp4" in content_type or "video" in content_type:
                    ext = ".mp4"
                elif "webp" in content_type:
                    ext = ".webp"

                filename = f"{prefix}_{ad_id}{ext}"
                local_path = os.path.join(org_dir, filename)

                with open(local_path, "wb") as f:
                    f.write(resp.content)

            served_url = f"/static/creatives/{org_id}/{filename}"
            logger.info(f"  Downloaded asset: {filename} ({len(resp.content)} bytes)")
            return local_path, served_url

        except Exception as e:
            logger.warning(f"  Failed to download asset for ad {ad_id}: {e}")
            return None, None


meta_sync = MetaSyncService()
