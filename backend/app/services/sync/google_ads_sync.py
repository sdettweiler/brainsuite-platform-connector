"""
Google Ads data sync service.
Uses Google Ads API v23 with GAQL (Google Ads Query Language).
All video ad performance data lives in Google Ads, not YouTube Data API.
"""
import asyncio
import httpx
import logging
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import GoogleAdsRawPerformance
from app.core.security import decrypt_token
from app.services.platform.google_ads_oauth import google_ads_oauth

_CREATIVES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "creatives")
)

logger = logging.getLogger(__name__)

GOOGLE_ADS_API_BASE = "https://googleads.googleapis.com/v23"


class GoogleAdsSyncService:

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

        asset_map = await self._fetch_youtube_asset_map(access_token, customer_id)

        org_id = str(connection.organization_id)
        org_dir = os.path.join(_CREATIVES_DIR, org_id)
        os.makedirs(org_dir, exist_ok=True)

        total_fetched = 0
        total_upserted = 0

        chunk_start = date_from
        while chunk_start <= date_to:
            chunk_end = min(chunk_start + timedelta(days=29), date_to)
            records = await self._fetch_video_ad_performance(
                access_token, customer_id, chunk_start, chunk_end
            )
            upserted = await self._upsert_records(
                db, connection, records, sync_job_id, asset_map, org_id, org_dir
            )
            total_fetched += len(records)
            total_upserted += upserted
            chunk_start = chunk_end + timedelta(days=1)

        return {"fetched": total_fetched, "upserted": total_upserted}

    async def _fetch_youtube_asset_map(
        self, access_token: str, customer_id: str
    ) -> Dict[str, str]:
        """Build a map of asset resource name -> YouTube video ID."""
        from app.core.config import settings

        query = """
            SELECT asset.resource_name,
                   asset.youtube_video_asset.youtube_video_id
            FROM asset
            WHERE asset.type = 'YOUTUBE_VIDEO'
        """
        asset_map: Dict[str, str] = {}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{GOOGLE_ADS_API_BASE}/customers/{customer_id}/googleAds:search",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "developer-token": settings.GOOGLE_DEVELOPER_TOKEN or "",
                    "login-customer-id": customer_id,
                },
                json={"query": query},
            )
            if resp.status_code == 200:
                for r in resp.json().get("results", []):
                    asset = r.get("asset", {})
                    res_name = asset.get("resourceName", "")
                    yt_id = asset.get("youtubeVideoAsset", {}).get("youtubeVideoId", "")
                    if res_name and yt_id:
                        asset_map[res_name] = yt_id
            else:
                logger.warning(f"Failed to fetch YouTube assets: {resp.status_code}")

        logger.info(f"Built YouTube asset map with {len(asset_map)} entries for {customer_id}")
        return asset_map

    async def _get_valid_token(
        self, db: AsyncSession, connection: PlatformConnection
    ) -> str:
        """Refresh access token if needed."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        if connection.token_expiry and connection.token_expiry > now:
            return decrypt_token(connection.access_token_encrypted)

        refresh_token = decrypt_token(connection.refresh_token_encrypted)
        new_tokens = await google_ads_oauth.refresh_access_token(refresh_token)
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
                ad_group_ad.ad.video_ad.video.asset,
                ad_group_ad.ad.video_responsive_ad.videos,
                segments.date,
                metrics.cost_micros,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.average_cpm,
                metrics.conversions,
                metrics.conversions_value,
                metrics.video_trueview_views,
                metrics.video_trueview_view_rate,
                metrics.video_quartile_p25_rate,
                metrics.video_quartile_p50_rate,
                metrics.video_quartile_p75_rate,
                metrics.video_quartile_p100_rate,
                metrics.engagements,
                metrics.engagement_rate
            FROM ad_group_ad
            WHERE
                segments.date BETWEEN '{date_from.strftime("%Y-%m-%d")}' AND '{date_to.strftime("%Y-%m-%d")}'
                AND campaign.advertising_channel_type IN ('VIDEO', 'DISPLAY', 'PERFORMANCE_MAX')
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
                if results:
                    logger.info(f"Fetched {len(results)} records for {customer_id} ({date_from} to {date_to})")
                else:
                    logger.info(f"No results for {customer_id} ({date_from} to {date_to})")
                records.extend(results)

                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break

        logger.info(f"Total records fetched for {customer_id}: {len(records)}")
        return records

    def _extract_youtube_id(
        self, ad: Dict[str, Any], asset_map: Dict[str, str]
    ) -> Optional[str]:
        video_ad = ad.get("videoAd", {})
        asset_ref = video_ad.get("video", {}).get("asset", "")
        if asset_ref and asset_ref in asset_map:
            return asset_map[asset_ref]

        responsive_ad = ad.get("videoResponsiveAd", {})
        videos = responsive_ad.get("videos", [])
        for v in videos:
            asset_ref = v.get("asset", "")
            if asset_ref and asset_ref in asset_map:
                return asset_map[asset_ref]

        return None

    async def _download_thumbnail(
        self,
        youtube_video_id: str,
        org_dir: str,
        org_id: str,
        ad_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        from app.services.object_storage import get_object_storage
        obj_storage = get_object_storage()

        filename = f"thumb_yt_{ad_id}.jpg"
        relative_path = f"creatives/{org_id}/{filename}"
        local_path = os.path.join(org_dir, filename)

        if obj_storage.file_exists(relative_path):
            return None, obj_storage.served_url(relative_path)

        thumb_candidates = [
            f"https://img.youtube.com/vi/{youtube_video_id}/maxresdefault.jpg",
            f"https://img.youtube.com/vi/{youtube_video_id}/sddefault.jpg",
            f"https://img.youtube.com/vi/{youtube_video_id}/hqdefault.jpg",
        ]
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = None
                for thumb_url in thumb_candidates:
                    resp = await client.get(thumb_url)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        break
                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(resp.content)
            served_url = obj_storage.upload_file(local_path, relative_path, content_type="image/jpeg")
            try:
                os.remove(local_path)
            except OSError:
                pass
            logger.info(f"  Downloaded YouTube thumbnail: {filename} ({len(resp.content)} bytes)")
            return None, served_url
        except Exception as e:
            logger.warning(f"  Failed to download YouTube thumbnail for ad {ad_id} (video {youtube_video_id}): {e}")
            return None, None

    async def _download_video(
        self,
        youtube_video_id: str,
        org_dir: str,
        org_id: str,
        ad_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        from app.services.object_storage import get_object_storage
        obj_storage = get_object_storage()

        filename = f"vid_yt_{ad_id}.mp4"
        relative_path = f"creatives/{org_id}/{filename}"
        local_path = os.path.join(org_dir, filename)

        if obj_storage.file_exists(relative_path):
            return local_path if os.path.exists(local_path) else None, obj_storage.served_url(relative_path)

        url = f"https://www.youtube.com/watch?v={youtube_video_id}"

        def _do_download():
            import yt_dlp
            import tempfile
            ydl_opts = {
                "outtmpl": local_path,
                "format": "bv*+ba/b",
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 30,
                "merge_output_format": "mp4",
                "ignore_no_formats_error": True,
                "js_runtimes": {"node": {}},
                "remote_components": {"ejs:github": True},
            }
            cookies_data = os.environ.get("YOUTUBE_COOKIES", "")
            cookie_file = None
            if cookies_data:
                cleaned = "\n".join(
                    line.lstrip() for line in cookies_data.splitlines()
                )
                cookie_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False
                )
                cookie_file.write(cleaned)
                cookie_file.close()
                ydl_opts["cookiefile"] = cookie_file.name
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            finally:
                if cookie_file and os.path.exists(cookie_file.name):
                    os.remove(cookie_file.name)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _do_download)

            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                size_mb = os.path.getsize(local_path) / (1024 * 1024)
                served_url = obj_storage.upload_file(local_path, relative_path, content_type="video/mp4")
                logger.info(f"  Downloaded YouTube video: {filename} ({size_mb:.1f} MB)")
                return local_path, served_url
            else:
                logger.warning(f"  yt-dlp finished but file not found: {local_path}")
                return None, None
        except Exception as e:
            logger.warning(f"  Failed to download YouTube video for ad {ad_id} (video {youtube_video_id}): {e}")
            if os.path.exists(local_path):
                os.remove(local_path)
            return None, None

    async def _upsert_records(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        records: List[Dict[str, Any]],
        sync_job_id: Optional[str],
        asset_map: Optional[Dict[str, str]] = None,
        org_id: Optional[str] = None,
        org_dir: Optional[str] = None,
    ) -> int:
        if not records:
            return 0

        asset_map = asset_map or {}

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

            report_date_str = segments.get("date", "")
            report_date = date.fromisoformat(report_date_str) if report_date_str else None

            youtube_video_id = self._extract_youtube_id(ad, asset_map)
            ad_id_str = str(ad.get("id", ""))

            video_url = None
            thumbnail_url = None
            if youtube_video_id and org_id and org_dir:
                _, thumbnail_url = await self._download_thumbnail(
                    youtube_video_id, org_dir, org_id, ad_id_str
                )
                _, video_url = await self._download_video(
                    youtube_video_id, org_dir, org_id, ad_id_str
                )
            if not thumbnail_url and youtube_video_id:
                thumbnail_url = f"https://img.youtube.com/vi/{youtube_video_id}/maxresdefault.jpg"
            if not video_url and youtube_video_id:
                video_url = f"https://www.youtube.com/watch?v={youtube_video_id}"

            rows.append({
                "platform_connection_id": connection.id,
                "sync_job_id": sync_job_id,
                "report_date": report_date,
                "ad_account_id": connection.ad_account_id,
                "campaign_id": str(campaign.get("id", "")),
                "campaign_name": campaign.get("name"),
                "campaign_objective": campaign.get("advertisingChannelSubType"),
                "ad_group_id": str(ad_group.get("id", "")),
                "ad_group_name": ad_group.get("name"),
                "ad_id": ad_id_str,
                "ad_name": ad.get("name"),
                "video_id": youtube_video_id,
                "video_url": video_url,
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
                "video_views": int(metrics.get("videoTrueviewViews", 0) or 0),
                "view_rate": float(metrics.get("videoTrueviewViewRate", 0) or 0),
                "video_view_through_rate": float(metrics.get("videoQuartileP100Rate", 0) or 0),
                "video_quartile_p25": float(metrics.get("videoQuartileP25Rate", 0) or 0),
                "video_quartile_p50": float(metrics.get("videoQuartileP50Rate", 0) or 0),
                "video_quartile_p75": float(metrics.get("videoQuartileP75Rate", 0) or 0),
                "video_quartile_p100": float(metrics.get("videoQuartileP100Rate", 0) or 0),
                "is_validated": True,
                "is_processed": False,
            })

        stmt = pg_insert(GoogleAdsRawPerformance).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_google_ads_daily_ad",
            set_={
                "spend": stmt.excluded.spend,
                "impressions": stmt.excluded.impressions,
                "clicks": stmt.excluded.clicks,
                "conversions": stmt.excluded.conversions,
                "roas": stmt.excluded.roas,
                "video_views": stmt.excluded.video_views,
                "video_id": stmt.excluded.video_id,
                "video_url": stmt.excluded.video_url,
                "thumbnail_url": stmt.excluded.thumbnail_url,
                "is_processed": False,
            }
        )
        await db.execute(stmt)
        return len(rows)


google_ads_sync = GoogleAdsSyncService()
