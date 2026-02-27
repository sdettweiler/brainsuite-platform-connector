"""
DV360 data sync service.

Dual-API architecture:
- Display & Video 360 API v4 (displayvideo.googleapis.com/v4):
  Entity metadata — campaigns, insertion orders, line items, creatives,
  ad groups, ad group ads (YouTube video IDs), advertiser timezone.
  Also provides dimension backfill (campaign names, IO goals, creative types)
  for fields not in the slimmed Bid Manager report.
- Bid Manager API v2 (doubleclickbidmanager.googleapis.com/v2):
  Two-report YOUTUBE architecture:
  Report 1 (perf): 19 non-conversion metrics with type=YOUTUBE:
    Core: IMPRESSIONS, CLICKS, CLICK_RATE
    Spend: MEDIA_COST_ADVERTISER
    Video: VIDEO_VIEWS, VIDEO_VIEWS_RATE, VIDEO_COMPLETE_IMPRESSIONS,
           VIDEO_FIRST/MIDPOINT/THIRD_QUARTILE_IMPRESSIONS, VIDEO_SKIPS
    Cost: COST_PER_VIDEO_VIEW
    Active View: ACTIVE_VIEW_MEASURABLE/VIEWABLE/PERCENT_VIEWABLE_IMPRESSIONS
    Companion: VIDEO_COMPANION_IMPRESSIONS, VIDEO_COMPANION_CLICKS
    Other: BILLABLE_IMPRESSIONS, ENGAGEMENTS
  Report 2 (conv): 4 conversion-only metrics with type=YOUTUBE:
    TOTAL_CONVERSIONS, POST_VIEW_CONVERSIONS, POST_CLICK_CONVERSIONS,
    REVENUE_CONVERSION_COST_ADVERTISER
  Both use 8 groupBys (date, advertiser, advertiser_name,
  advertiser_currency, insertion_order, line_item, line_item_type,
  youtube_ad_video_id).

The sync flow:
1. Fetch entity metadata maps from DV360 API v4
2. Map line items to YouTube video IDs via adGroup→adGroupAd chain
3. Run Report 1 (performance) + Report 2 (conversion) via Bid Manager
4. Fetch YouTube oEmbed metadata for video IDs from both reports
5. Parse CSV results and enrich with v4 metadata
6. Upsert Report 1 records (full row upsert)
7. Merge Report 2 conversion data into existing rows (UPDATE only)
8. Download creative assets (thumbnails via YouTube CDN, videos via yt-dlp)

Note: YOUTUBE reports can take up to 2 hours to process on Google's backend.
The poll loop uses adaptive intervals (30s→60s→120s) with a 2-hour max wait
and automatic OAuth token refresh to handle long-running reports.
"""
import httpx
import csv
import io
import os
import re
import logging
import asyncio
import subprocess
import json
from datetime import date, timedelta, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, NamedTuple, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import Dv360RawPerformance
from app.core.security import decrypt_token
from app.services.platform.dv360_oauth import dv360_oauth

logger = logging.getLogger(__name__)

_CREATIVES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "static", "creatives")

_SAFE_FILENAME_RE = re.compile(r'[^a-zA-Z0-9_\-]')

def _sanitize_for_filename(val: str) -> str:
    return _SAFE_FILENAME_RE.sub('_', val)[:200]

BID_MANAGER_API_BASE = "https://doubleclickbidmanager.googleapis.com/v2"
DV360_API_BASE = "https://displayvideo.googleapis.com/v4"


_AD_TYPE_MAP = {
    "inStreamAd": "In-Stream",
    "bumperAd": "Bumper",
    "nonSkippableAd": "Non-Skippable In-Stream",
    "videoDiscoverAd": "Video Discovery",
    "videoPerformanceAd": "Video Performance",
    "mastheadAd": "Masthead",
}


class EntityMaps(NamedTuple):
    campaigns: Dict[str, Dict[str, Any]]
    insertion_orders: Dict[str, Dict[str, Any]]
    line_items: Dict[str, Dict[str, Any]]
    creatives: Dict[str, Dict[str, Any]]
    line_item_videos: Dict[str, List[Dict[str, Any]]] = {}
    advertiser_timezone: str = ""
    youtube_metadata: Dict[str, Dict[str, Any]] = {}
    video_metadata: Dict[str, Dict[str, Any]] = {}


class DV360SyncService:

    async def sync_date_range(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        date_from: date,
        date_to: date,
        sync_job_id: Optional[str] = None,
    ) -> Dict[str, int]:
        access_token = await self._get_valid_token(db, connection)
        advertiser_id = connection.ad_account_id

        entity_maps = await self._fetch_entity_metadata(access_token, advertiser_id)

        perf_records = await self._run_report(
            access_token, advertiser_id, date_from, date_to,
            db=db, connection=connection,
        )

        csv_video_ids = set()
        for r in perf_records:
            vid = (r.get("YouTube Ad Video ID") or "").strip()
            if vid:
                csv_video_ids.add(vid)

        conv_records = []
        try:
            conv_records = await self._run_conversion_report(
                access_token, advertiser_id, date_from, date_to,
                db=db, connection=connection,
            )
            for r in conv_records:
                vid = (r.get("YouTube Ad Video ID") or "").strip()
                if vid:
                    csv_video_ids.add(vid)
        except Exception as e:
            logger.warning(f"DV360: Conversion report failed (non-fatal, Floodlight may not be configured): {e}")

        known_ids = set(entity_maps.youtube_metadata.keys())
        new_ids = csv_video_ids - known_ids
        if new_ids:
            logger.info(f"DV360: {len(new_ids)} video IDs from CSV not in adGroupAds, fetching metadata")
            extra_meta = await self._fetch_youtube_metadata(list(new_ids))
            merged_yt_meta = {**entity_maps.youtube_metadata, **extra_meta}
            merged_vid_meta = dict(entity_maps.video_metadata)
            for vid in new_ids:
                if vid not in merged_vid_meta:
                    merged_vid_meta[vid] = {"ad_type_label": "", "ad_name": "", "line_item_id": ""}
            entity_maps = entity_maps._replace(
                youtube_metadata=merged_yt_meta,
                video_metadata=merged_vid_meta,
            )

        perf_upserted = await self._upsert_records(db, connection, perf_records, sync_job_id, entity_maps)

        conv_upserted = 0
        if conv_records:
            try:
                conv_upserted = await self._upsert_conversion_records(
                    db, connection, conv_records, sync_job_id, entity_maps
                )
            except Exception as e:
                logger.warning(f"DV360: Conversion upsert failed (non-fatal): {e}")

        return {"fetched": len(perf_records) + len(conv_records), "upserted": perf_upserted + conv_upserted}

    async def _get_valid_token(
        self, db: AsyncSession, connection: PlatformConnection
    ) -> str:
        from datetime import timezone
        now = datetime.now(timezone.utc)

        if connection.token_expiry and connection.token_expiry > now:
            return decrypt_token(connection.access_token_encrypted)

        refresh_token = decrypt_token(connection.refresh_token_encrypted)
        new_tokens = await dv360_oauth.refresh_access_token(refresh_token)
        new_access = new_tokens.get("access_token")

        from app.core.security import encrypt_token
        connection.access_token_encrypted = encrypt_token(new_access)
        connection.token_expiry = now + timedelta(seconds=new_tokens.get("expires_in", 3600))
        db.add(connection)
        await db.flush()

        return new_access

    async def _fetch_entity_metadata(
        self,
        access_token: str,
        advertiser_id: str,
    ) -> EntityMaps:
        """Fetch entity metadata from DV360 API v4 for enriching report records."""
        headers = {"Authorization": f"Bearer {access_token}"}

        campaigns: Dict[str, Dict[str, Any]] = {}
        insertion_orders: Dict[str, Dict[str, Any]] = {}
        line_items: Dict[str, Dict[str, Any]] = {}
        creatives: Dict[str, Dict[str, Any]] = {}
        advertiser_timezone = ""

        async with httpx.AsyncClient(timeout=60) as client:
            campaign_task = self._fetch_campaigns(client, headers, advertiser_id)
            io_task = self._fetch_insertion_orders(client, headers, advertiser_id)
            li_task = self._fetch_line_items(client, headers, advertiser_id)
            creative_task = self._fetch_creatives(client, headers, advertiser_id)
            ad_group_task = self._fetch_ad_groups(client, headers, advertiser_id)
            ad_group_ads_task = self._fetch_ad_group_ads(client, headers, advertiser_id)
            tz_task = self._fetch_advertiser_timezone(client, headers, advertiser_id)

            results = await asyncio.gather(
                campaign_task, io_task, li_task, creative_task,
                ad_group_task, ad_group_ads_task, tz_task,
                return_exceptions=True,
            )

            if isinstance(results[0], dict):
                campaigns = results[0]
            else:
                logger.warning(f"DV360 v4: Failed to fetch campaigns: {results[0]}")

            if isinstance(results[1], dict):
                insertion_orders = results[1]
            else:
                logger.warning(f"DV360 v4: Failed to fetch insertion orders: {results[1]}")

            if isinstance(results[2], dict):
                line_items = results[2]
            else:
                logger.warning(f"DV360 v4: Failed to fetch line items: {results[2]}")

            if isinstance(results[3], dict):
                creatives = results[3]
            else:
                logger.warning(f"DV360 v4: Failed to fetch creatives: {results[3]}")

            ad_groups = results[4] if isinstance(results[4], dict) else {}
            ad_group_ads = results[5] if isinstance(results[5], list) else []
            if isinstance(results[6], str):
                advertiser_timezone = results[6]

        line_item_videos: Dict[str, List[Dict[str, Any]]] = {}
        ag_to_li: Dict[str, str] = {}
        for ag_id, ag_info in ad_groups.items():
            li_id = ag_info.get("line_item_id", "")
            if li_id:
                ag_to_li[ag_id] = li_id

        video_metadata: Dict[str, Dict[str, Any]] = {}
        for ad in ad_group_ads:
            ag_id = ad.get("ad_group_id", "")
            li_id = ag_to_li.get(ag_id, "")
            video_ids = ad.get("youtube_video_ids", [])
            ad_type_label = ad.get("ad_type_label", "")
            if not video_ids:
                vid = ad.get("youtube_video_id", "")
                if vid:
                    video_ids = [vid]
            if li_id and video_ids:
                if li_id not in line_item_videos:
                    line_item_videos[li_id] = []
                for vid in video_ids:
                    if vid not in video_metadata:
                        video_metadata[vid] = {
                            "ad_type_label": ad_type_label,
                            "ad_name": ad.get("name", ""),
                            "display_url": ad.get("display_url", ""),
                            "final_url": ad.get("final_url", ""),
                            "line_item_id": li_id,
                        }
                    already_in_li = any(
                        e["youtube_video_id"] == vid
                        for e in line_item_videos[li_id]
                    )
                    if not already_in_li:
                        line_item_videos[li_id].append({
                            "youtube_video_id": vid,
                            "ad_type_label": ad_type_label,
                        })

        total_li = len(line_items)
        mapped_li = sum(1 for v in line_item_videos.values() if v)
        unmapped_li = total_li - mapped_li
        all_video_ids = set(video_metadata.keys())

        logger.info(
            f"DV360 v4 metadata for advertiser {advertiser_id}: "
            f"{len(campaigns)} campaigns, {len(insertion_orders)} IOs, "
            f"{total_li} line items, {len(creatives)} creatives, "
            f"{mapped_li}/{total_li} line items mapped to YouTube videos "
            f"({unmapped_li} unmapped), {len(all_video_ids)} unique video IDs, "
            f"timezone={advertiser_timezone}"
        )

        youtube_metadata = await self._fetch_youtube_metadata(list(all_video_ids))

        return EntityMaps(
            campaigns=campaigns,
            insertion_orders=insertion_orders,
            line_items=line_items,
            creatives=creatives,
            line_item_videos=line_item_videos,
            advertiser_timezone=advertiser_timezone,
            youtube_metadata=youtube_metadata,
            video_metadata=video_metadata,
        )

    async def _fetch_campaigns(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        advertiser_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch all campaigns for an advertiser from DV360 API v4."""
        campaigns: Dict[str, Dict[str, Any]] = {}
        page_token = None

        while True:
            params: Dict[str, Any] = {"pageSize": 100}
            if page_token:
                params["pageToken"] = page_token

            resp = await client.get(
                f"{DV360_API_BASE}/advertisers/{advertiser_id}/campaigns",
                headers=headers,
                params=params,
            )
            if resp.status_code != 200:
                logger.warning(f"DV360 v4: List campaigns failed ({resp.status_code}): {resp.text[:300]}")
                break

            data = resp.json()
            for c in data.get("campaigns", []):
                cid = c.get("campaignId")
                if cid:
                    campaigns[str(cid)] = {
                        "name": c.get("displayName", ""),
                        "status": c.get("entityStatus", ""),
                        "goal": c.get("campaignGoal", {}).get("campaignGoalType", ""),
                    }

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return campaigns

    async def _fetch_insertion_orders(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        advertiser_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch all insertion orders for an advertiser from DV360 API v4."""
        ios: Dict[str, Dict[str, Any]] = {}
        page_token = None

        while True:
            params: Dict[str, Any] = {"pageSize": 100}
            if page_token:
                params["pageToken"] = page_token

            resp = await client.get(
                f"{DV360_API_BASE}/advertisers/{advertiser_id}/insertionOrders",
                headers=headers,
                params=params,
            )
            if resp.status_code != 200:
                logger.warning(f"DV360 v4: List IOs failed ({resp.status_code}): {resp.text[:300]}")
                break

            data = resp.json()
            for io_item in data.get("insertionOrders", []):
                io_id = io_item.get("insertionOrderId")
                if io_id:
                    perf_goal = io_item.get("performanceGoal", {})
                    ios[str(io_id)] = {
                        "name": io_item.get("displayName", ""),
                        "status": io_item.get("entityStatus", ""),
                        "campaign_id": str(io_item.get("campaignId", "")),
                        "goal_type": perf_goal.get("performanceGoalType", ""),
                    }

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return ios

    async def _fetch_line_items(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        advertiser_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch all line items for an advertiser from DV360 API v4."""
        lis: Dict[str, Dict[str, Any]] = {}
        page_token = None

        while True:
            params: Dict[str, Any] = {"pageSize": 100}
            if page_token:
                params["pageToken"] = page_token

            resp = await client.get(
                f"{DV360_API_BASE}/advertisers/{advertiser_id}/lineItems",
                headers=headers,
                params=params,
            )
            if resp.status_code != 200:
                logger.warning(f"DV360 v4: List line items failed ({resp.status_code}): {resp.text[:300]}")
                break

            data = resp.json()
            for li in data.get("lineItems", []):
                li_id = li.get("lineItemId")
                if li_id:
                    lis[str(li_id)] = {
                        "name": li.get("displayName", ""),
                        "status": li.get("entityStatus", ""),
                        "type": li.get("lineItemType", ""),
                        "insertion_order_id": str(li.get("insertionOrderId", "")),
                        "campaign_id": str(li.get("campaignId", "")),
                    }

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return lis

    async def _fetch_creatives(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        advertiser_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch all creatives for an advertiser from DV360 API v4."""
        creatives: Dict[str, Dict[str, Any]] = {}
        page_token = None

        while True:
            params: Dict[str, Any] = {"pageSize": 100}
            if page_token:
                params["pageToken"] = page_token

            resp = await client.get(
                f"{DV360_API_BASE}/advertisers/{advertiser_id}/creatives",
                headers=headers,
                params=params,
            )
            if resp.status_code != 200:
                logger.warning(f"DV360 v4: List creatives failed ({resp.status_code}): {resp.text[:300]}")
                break

            data = resp.json()
            for cr in data.get("creatives", []):
                cr_id = cr.get("creativeId")
                if cr_id:
                    dims = cr.get("dimensions", {})
                    assets = cr.get("assets", [])

                    thumbnail = ""
                    for asset in assets:
                        role = asset.get("role", "")
                        asset_content = asset.get("asset", {}).get("content", "")
                        if role == "ASSET_ROLE_MAIN" and asset_content:
                            thumbnail = asset_content
                            break
                        elif role == "ASSET_ROLE_BACKUP_IMAGE" and asset_content and not thumbnail:
                            thumbnail = asset_content

                    exit_events = cr.get("exitEvents", [])
                    landing_url = ""
                    for ev in exit_events:
                        if ev.get("type") == "EXIT_EVENT_TYPE_DEFAULT":
                            landing_url = ev.get("url", "")
                            break

                    creative_type = cr.get("creativeType", "")
                    hosting_source = cr.get("hostingSource", "")

                    asset_format = ""
                    if dims:
                        w = dims.get("widthPixels", "")
                        h = dims.get("heightPixels", "")
                        if w and h:
                            asset_format = f"{w}x{h}"

                    creatives[str(cr_id)] = {
                        "name": cr.get("displayName", ""),
                        "type": creative_type,
                        "hosting_source": hosting_source,
                        "thumbnail_url": thumbnail,
                        "asset_format": asset_format,
                        "landing_url": landing_url,
                    }

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return creatives

    async def _fetch_ad_groups(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        advertiser_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch ad groups to map adGroupId → lineItemId."""
        ad_groups: Dict[str, Dict[str, Any]] = {}
        page_token = None

        while True:
            params: Dict[str, Any] = {"pageSize": 100}
            if page_token:
                params["pageToken"] = page_token

            resp = await client.get(
                f"{DV360_API_BASE}/advertisers/{advertiser_id}/adGroups",
                headers=headers,
                params=params,
            )
            if resp.status_code != 200:
                logger.warning(f"DV360 v4: List ad groups failed ({resp.status_code}): {resp.text[:300]}")
                break

            data = resp.json()
            for ag in data.get("adGroups", []):
                ag_id = ag.get("adGroupId")
                if ag_id:
                    ad_groups[str(ag_id)] = {
                        "name": ag.get("displayName", ""),
                        "line_item_id": str(ag.get("lineItemId", "")),
                        "format": ag.get("adGroupFormat", ""),
                    }

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return ad_groups

    async def _fetch_ad_group_ads(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        advertiser_id: str,
    ) -> List[Dict[str, Any]]:
        """Fetch ad group ads to extract YouTube video IDs."""
        ads: List[Dict[str, Any]] = []
        page_token = None

        while True:
            params: Dict[str, Any] = {"pageSize": 100}
            if page_token:
                params["pageToken"] = page_token

            resp = await client.get(
                f"{DV360_API_BASE}/advertisers/{advertiser_id}/adGroupAds",
                headers=headers,
                params=params,
            )
            if resp.status_code != 200:
                logger.warning(f"DV360 v4: List ad group ads failed ({resp.status_code}): {resp.text[:300]}")
                break

            data = resp.json()
            for ad in data.get("adGroupAds", []):
                video_ids: List[str] = []
                ad_name = ad.get("displayName", "")
                display_url = ""
                final_url = ""
                ad_type_label = ""

                for ad_type_key in ["inStreamAd", "bumperAd", "nonSkippableAd", "videoDiscoverAd", "videoPerformanceAd", "mastheadAd"]:
                    ad_detail = ad.get(ad_type_key)
                    if ad_detail:
                        ad_type_label = _AD_TYPE_MAP.get(ad_type_key, ad_type_key)

                        if ad_type_key == "videoPerformanceAd":
                            for v in ad_detail.get("videos", []):
                                vid = v.get("id", "")
                                if vid:
                                    video_ids.append(vid)
                            display_url = ad_detail.get("displayUrl", "")
                            final_urls = ad_detail.get("finalUrls", [])
                            if final_urls:
                                final_url = final_urls[0]
                        else:
                            common = (
                                ad_detail.get("commonInStreamAttribute")
                                or ad_detail.get("commonVideoResponsiveAdAttribute")
                                or ad_detail
                            )
                            video_ref = common.get("video", {})
                            if video_ref.get("id"):
                                video_ids.append(video_ref["id"])
                            display_url = common.get("displayUrl", "")
                            final_url = common.get("finalUrl", "")
                        break

                ads.append({
                    "ad_group_id": str(ad.get("adGroupId", "")),
                    "ad_group_ad_id": str(ad.get("adGroupAdId", "")),
                    "name": ad_name,
                    "youtube_video_id": video_ids[0] if video_ids else "",
                    "youtube_video_ids": video_ids,
                    "ad_type_label": ad_type_label,
                    "display_url": display_url,
                    "final_url": final_url,
                })

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return ads

    async def _fetch_advertiser_timezone(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        advertiser_id: str,
    ) -> str:
        """Fetch advertiser timezone from DV360 API v4."""
        try:
            resp = await client.get(
                f"{DV360_API_BASE}/advertisers/{advertiser_id}",
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                tz = data.get("generalConfig", {}).get("timeZone", "")
                if tz:
                    logger.info(f"DV360 v4: Advertiser {advertiser_id} timezone: {tz}")
                    return tz
        except Exception as e:
            logger.warning(f"DV360 v4: Failed to fetch advertiser timezone: {e}")
        return ""

    async def _fetch_youtube_metadata(
        self,
        video_ids: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch video title and thumbnail via YouTube oEmbed (no auth required)."""
        metadata: Dict[str, Dict[str, Any]] = {}
        if not video_ids:
            return metadata

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for vid in video_ids:
                try:
                    resp = await client.get(
                        "https://www.youtube.com/oembed",
                        params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        metadata[vid] = {
                            "title": data.get("title", ""),
                            "author_name": data.get("author_name", ""),
                            "thumbnail_url": f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg",
                        }
                    else:
                        logger.debug(f"oEmbed failed for video {vid}: HTTP {resp.status_code}")
                except Exception as e:
                    logger.debug(f"oEmbed failed for video {vid}: {e}")

        logger.info(f"YouTube oEmbed: fetched metadata for {len(metadata)}/{len(video_ids)} videos")
        return metadata

    async def _refresh_token_if_needed(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
    ) -> str:
        from datetime import timezone as tz
        now = datetime.now(tz.utc)
        if connection.token_expiry and connection.token_expiry > now + timedelta(minutes=5):
            return decrypt_token(connection.access_token_encrypted)
        refresh_token = decrypt_token(connection.refresh_token_encrypted)
        new_tokens = await dv360_oauth.refresh_access_token(refresh_token)
        new_access = new_tokens.get("access_token")
        from app.core.security import encrypt_token
        connection.access_token_encrypted = encrypt_token(new_access)
        connection.token_expiry = now + timedelta(seconds=new_tokens.get("expires_in", 3600))
        db.add(connection)
        await db.flush()
        logger.info("Bid Manager: OAuth token refreshed during long poll")
        return new_access

    async def _create_and_poll_report(
        self,
        access_token: str,
        query_body: Dict[str, Any],
        label: str = "report",
        db: AsyncSession = None,
        connection: PlatformConnection = None,
    ) -> Optional[List[Dict[str, Any]]]:
        current_token = access_token
        headers = {
            "Authorization": f"Bearer {current_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            create_resp = await client.post(
                f"{BID_MANAGER_API_BASE}/queries",
                headers=headers,
                json=query_body,
            )
            if create_resp.status_code != 200:
                logger.error(f"Bid Manager v2 [{label}]: Create query failed ({create_resp.status_code}): {create_resp.text[:500]}")
                return None

            query_data = create_resp.json()
            query_id = query_data.get("queryId")
            if not query_id:
                logger.error(f"Bid Manager v2 [{label}]: No queryId returned: {query_data}")
                return []

            run_resp = await client.post(
                f"{BID_MANAGER_API_BASE}/queries/{query_id}:run",
                headers=headers,
                json={},
            )
            if run_resp.status_code != 200:
                logger.error(f"Bid Manager v2 [{label}]: Run query failed ({run_resp.status_code}): {run_resp.text[:500]}")
                return None

            logger.info(f"Bid Manager v2 [{label}]: Query {query_id} created and running, polling for results (YouTube reports may take up to 2 hours)")

            report_url = None
            poll_interval = 30
            max_wait_seconds = 7200
            elapsed = 0
            attempt = 0
            last_token_refresh = 0
            while elapsed < max_wait_seconds:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                attempt += 1

                if elapsed > 300 and poll_interval < 60:
                    poll_interval = 60
                elif elapsed > 1800 and poll_interval < 120:
                    poll_interval = 120

                if db and connection and (elapsed - last_token_refresh) > 2700:
                    try:
                        current_token = await self._refresh_token_if_needed(db, connection)
                        headers["Authorization"] = f"Bearer {current_token}"
                        last_token_refresh = elapsed
                    except Exception as e:
                        logger.warning(f"Bid Manager v2 [{label}]: Token refresh failed: {e}")

                try:
                    status_resp = await client.get(
                        f"{BID_MANAGER_API_BASE}/queries/{query_id}/reports",
                        headers=headers,
                    )
                except Exception as e:
                    logger.warning(f"Bid Manager v2 [{label}]: Poll error: {e}")
                    continue

                if status_resp.status_code == 401 and db and connection:
                    try:
                        current_token = await self._refresh_token_if_needed(db, connection)
                        headers["Authorization"] = f"Bearer {current_token}"
                        last_token_refresh = elapsed
                        continue
                    except Exception as e:
                        logger.warning(f"Bid Manager v2 [{label}]: Token refresh on 401 failed: {e}")

                if status_resp.status_code != 200:
                    continue

                resp_data = status_resp.json()
                reports = resp_data.get("reports", [])
                if reports:
                    latest = reports[0]
                    r_metadata = latest.get("metadata", {})
                    r_status = r_metadata.get("status", {})
                    state = r_status.get("state", "UNKNOWN")
                    if attempt % 10 == 0 or attempt <= 3:
                        elapsed_min = elapsed / 60
                        logger.info(f"Bid Manager v2 [{label}]: Poll #{attempt} ({elapsed_min:.0f}m elapsed), state={state}")
                    if state == "DONE":
                        report_url = r_metadata.get("googleCloudStoragePath")
                        logger.info(f"Bid Manager v2 [{label}]: Report ready after {elapsed/60:.1f} minutes")
                        break
                    elif state == "FAILED":
                        logger.error(f"Bid Manager v2 [{label}]: Report failed: {r_status}")
                        return None
                else:
                    if attempt % 10 == 0 or attempt <= 3:
                        logger.info(f"Bid Manager v2 [{label}]: Poll #{attempt} ({elapsed/60:.0f}m elapsed), no reports yet")

            if not report_url:
                logger.error(f"Bid Manager v2 [{label}]: Report timed out after {max_wait_seconds/60:.0f} minutes")
                try:
                    await client.delete(
                        f"{BID_MANAGER_API_BASE}/queries/{query_id}",
                        headers=headers,
                    )
                except Exception:
                    pass
                return None

            csv_resp = await client.get(
                report_url,
                headers={"Authorization": f"Bearer {current_token}"},
            )
            if csv_resp.status_code != 200:
                logger.error(f"Bid Manager v2 [{label}]: CSV download failed ({csv_resp.status_code})")
                return None

            records = self._parse_csv(csv_resp.text)
            logger.info(f"Bid Manager v2 [{label}]: Downloaded CSV with {len(records)} data rows")

            try:
                await client.delete(
                    f"{BID_MANAGER_API_BASE}/queries/{query_id}",
                    headers=headers,
                )
            except Exception:
                pass

        return records

    def _build_query_body(
        self,
        advertiser_id: str,
        date_from: date,
        date_to: date,
        metrics: List[str],
        title_suffix: str = "",
    ) -> Dict[str, Any]:
        return {
            "metadata": {
                "title": f"brainsuite_dv360_{advertiser_id}_{date_from}_{date_to}{title_suffix}",
                "dataRange": {
                    "range": "CUSTOM_DATES",
                    "customStartDate": {
                        "year": date_from.year,
                        "month": date_from.month,
                        "day": date_from.day,
                    },
                    "customEndDate": {
                        "year": date_to.year,
                        "month": date_to.month,
                        "day": date_to.day,
                    },
                },
                "format": "CSV",
            },
            "params": {
                "type": "YOUTUBE",
                "groupBys": [
                    "FILTER_DATE",
                    "FILTER_ADVERTISER",
                    "FILTER_ADVERTISER_NAME",
                    "FILTER_ADVERTISER_CURRENCY",
                    "FILTER_INSERTION_ORDER",
                    "FILTER_LINE_ITEM",
                    "FILTER_LINE_ITEM_TYPE",
                    "FILTER_YOUTUBE_AD_VIDEO_ID",
                ],
                "metrics": metrics,
                "filters": [
                    {
                        "type": "FILTER_ADVERTISER",
                        "value": advertiser_id,
                    }
                ],
            },
        }

    _PERF_METRICS = [
        "METRIC_IMPRESSIONS",
        "METRIC_CLICKS",
        "METRIC_CLICK_RATE",
        "METRIC_MEDIA_COST_ADVERTISER",
        "METRIC_VIDEO_VIEWS",
        "METRIC_VIDEO_VIEWS_RATE",
        "METRIC_VIDEO_COMPLETE_IMPRESSIONS",
        "METRIC_VIDEO_FIRST_QUARTILE_IMPRESSIONS",
        "METRIC_VIDEO_MIDPOINT_IMPRESSIONS",
        "METRIC_VIDEO_THIRD_QUARTILE_IMPRESSIONS",
        "METRIC_VIDEO_SKIPS",
        "METRIC_COST_PER_VIDEO_VIEW",
        "METRIC_ACTIVE_VIEW_MEASURABLE_IMPRESSIONS",
        "METRIC_ACTIVE_VIEW_VIEWABLE_IMPRESSIONS",
        "METRIC_ACTIVE_VIEW_PERCENT_VIEWABLE_IMPRESSIONS",
        "METRIC_VIDEO_COMPANION_IMPRESSIONS",
        "METRIC_VIDEO_COMPANION_CLICKS",
        "METRIC_BILLABLE_IMPRESSIONS",
        "METRIC_ENGAGEMENTS",
    ]

    _CONV_METRICS = [
        "METRIC_TOTAL_CONVERSIONS",
        "METRIC_POST_VIEW_CONVERSIONS",
        "METRIC_POST_CLICK_CONVERSIONS",
        "METRIC_REVENUE_CONVERSION_COST_ADVERTISER",
    ]

    async def _run_report(
        self,
        access_token: str,
        advertiser_id: str,
        date_from: date,
        date_to: date,
        db: AsyncSession = None,
        connection: PlatformConnection = None,
    ) -> List[Dict[str, Any]]:
        query_body = self._build_query_body(
            advertiser_id, date_from, date_to,
            self._PERF_METRICS, title_suffix="_perf",
        )
        result = await self._create_and_poll_report(
            access_token, query_body, label="perf", db=db, connection=connection
        )
        return result if result is not None else []

    async def _run_conversion_report(
        self,
        access_token: str,
        advertiser_id: str,
        date_from: date,
        date_to: date,
        db: AsyncSession = None,
        connection: PlatformConnection = None,
    ) -> List[Dict[str, Any]]:
        query_body = self._build_query_body(
            advertiser_id, date_from, date_to,
            self._CONV_METRICS, title_suffix="_conv",
        )
        result = await self._create_and_poll_report(
            access_token, query_body, label="conv", db=db, connection=connection
        )
        return result if result is not None else []

    def _parse_csv(self, csv_text: str) -> List[Dict[str, Any]]:
        """Parse Bid Manager v2 CSV report output into records.
        
        Bid Manager CSVs may contain non-data rows at the end such as
        'No data returned by the reporting service.' or 'Filter by Partner ID:'.
        We validate that the Date field is a real date before including.
        The Date column uses YYYY/MM/DD format — we parse it into a date object.
        """
        records = []
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            date_val = row.get("Date", "")
            if not date_val:
                continue
            try:
                parsed = datetime.strptime(date_val.replace("-", "/"), "%Y/%m/%d").date()
                row["_parsed_date"] = parsed
                records.append(row)
            except (ValueError, TypeError):
                continue
        return records

    async def _download_image_asset(
        self,
        url: str,
        org_dir: str,
        org_id: str,
        ad_id: str,
        prefix: str = "img",
    ) -> Tuple[Optional[str], Optional[str]]:
        try:
            safe_id = _sanitize_for_filename(ad_id)
            ext = ".jpg"
            if ".png" in url.lower():
                ext = ".png"
            elif ".webp" in url.lower():
                ext = ".webp"

            filename = f"{prefix}_dv360_{safe_id}{ext}"
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
                elif "webp" in content_type:
                    ext = ".webp"

                filename = f"{prefix}_dv360_{safe_id}{ext}"
                local_path = os.path.join(org_dir, filename)

                with open(local_path, "wb") as f:
                    f.write(resp.content)

            served_url = f"/static/creatives/{org_id}/{filename}"
            logger.info(f"  Downloaded DV360 asset: {filename} ({len(resp.content)} bytes)")
            return local_path, served_url
        except Exception as e:
            logger.warning(f"  Failed to download DV360 image for ad {ad_id}: {e}")
            return None, None

    def _check_youtube_cookies(self) -> str:
        """Check YouTube cookie status. Returns 'valid', 'expired', or 'missing'."""
        cookies_data = os.environ.get("YOUTUBE_COOKIES", "")
        if not cookies_data:
            return "missing"

        now_ts = datetime.now().timestamp()
        has_any_expiry = False
        has_valid = False
        for line in cookies_data.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                try:
                    expiry = int(parts[4])
                    if expiry > 0:
                        has_any_expiry = True
                        if expiry > now_ts:
                            has_valid = True
                except (ValueError, IndexError):
                    pass

        if not has_any_expiry:
            return "valid"
        return "valid" if has_valid else "expired"

    async def _download_video_asset(
        self,
        youtube_video_id: str,
        org_dir: str,
        org_id: str,
        ad_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        safe_id = _sanitize_for_filename(ad_id)
        filename = f"vid_dv360_{safe_id}.mp4"
        local_path = os.path.join(org_dir, filename)

        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            served_url = f"/static/creatives/{org_id}/{filename}"
            return local_path, served_url

        cookie_status = self._check_youtube_cookies()
        if cookie_status == "missing":
            logger.warning(f"  Skipping video download for {youtube_video_id}: YOUTUBE_COOKIES not set")
            return None, None
        if cookie_status == "expired":
            logger.warning(f"  Skipping video download for {youtube_video_id}: YOUTUBE_COOKIES expired — please refresh")
            return None, None

        url = f"https://www.youtube.com/watch?v={youtube_video_id}"

        def _do_download():
            import yt_dlp
            import tempfile
            ydl_opts = {
                "outtmpl": local_path,
                "format": "bv*+ba/b",
                "quiet": True,
                "no_warnings": False,
                "socket_timeout": 30,
                "merge_output_format": "mp4",
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
                served_url = f"/static/creatives/{org_id}/{filename}"
                logger.info(f"  Downloaded DV360 YouTube video: {filename} ({size_mb:.1f} MB)")
                return local_path, served_url
            else:
                logger.warning(f"  yt-dlp finished but file not found: {local_path}")
                return None, None
        except Exception as e:
            logger.warning(f"  Failed to download DV360 YouTube video for ad {ad_id} (video {youtube_video_id}): {e}")
            if os.path.exists(local_path):
                os.remove(local_path)
            return None, None

    async def _download_youtube_thumbnail(
        self,
        youtube_video_id: str,
        org_dir: str,
        org_id: str,
        ad_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        safe_id = _sanitize_for_filename(ad_id)
        filename = f"thumb_dv360_{safe_id}.jpg"
        local_path = os.path.join(org_dir, filename)

        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            served_url = f"/static/creatives/{org_id}/{filename}"
            return local_path, served_url

        candidates = [
            f"https://img.youtube.com/vi/{youtube_video_id}/maxresdefault.jpg",
            f"https://img.youtube.com/vi/{youtube_video_id}/sddefault.jpg",
            f"https://img.youtube.com/vi/{youtube_video_id}/hqdefault.jpg",
        ]
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                for thumb_url in candidates:
                    resp = await client.get(thumb_url)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        with open(local_path, "wb") as f:
                            f.write(resp.content)
                        served_url = f"/static/creatives/{org_id}/{filename}"
                        return local_path, served_url
        except Exception as e:
            logger.warning(f"  Failed to download YouTube thumbnail for ad {ad_id}: {e}")
        return None, None

    def _get_video_duration(self, file_path: str) -> Optional[float]:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", file_path],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = data.get("format", {}).get("duration")
                if duration:
                    return float(duration)
        except Exception as e:
            logger.debug(f"  ffprobe failed for {file_path}: {e}")
        return None

    async def _upsert_records(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        records: List[Dict[str, Any]],
        sync_job_id: Optional[str],
        entity_maps: Optional[EntityMaps] = None,
    ) -> int:
        if not records:
            return 0

        if records:
            first_row = records[0]
            csv_columns = list(first_row.keys())
            logger.info(f"DV360 perf CSV columns ({len(csv_columns)}): {csv_columns}")

        org_id = str(connection.organization_id) if hasattr(connection, "organization_id") and connection.organization_id else None
        org_dir = None
        if org_id:
            org_dir = os.path.join(_CREATIVES_DIR, org_id)
            os.makedirs(org_dir, exist_ok=True)

        def safe_decimal(val, default=None):
            try:
                return Decimal(str(val)) if val else default
            except Exception:
                return default

        def safe_int(val, default=None):
            try:
                return int(float(val)) if val else default
            except Exception:
                return default

        def safe_float(val, default=None):
            try:
                return float(val) if val else default
            except Exception:
                return default

        rows = []
        asset_download_queue = {}
        for r in records:
            spend = safe_decimal(r.get("Media Cost (Advertiser Currency)"))
            impressions = safe_int(r.get("Impressions"))
            clicks = safe_int(r.get("Clicks"))
            video_views = safe_int(
                r.get("Video Views") or r.get("TrueView Views")
            )
            video_completions = safe_int(
                r.get("Video Completions") or r.get("Video Complete Impressions")
                or r.get("Completion") or r.get("Complete Impressions (Video)")
            )
            video_first_quartile = safe_int(
                r.get("First Quartile") or r.get("Video First Quartile Impressions")
                or r.get("First Quartile Impressions")
            )
            video_midpoint = safe_int(
                r.get("Midpoint") or r.get("Video Midpoint Impressions")
                or r.get("Midpoint Impressions")
            )
            video_third_quartile = safe_int(
                r.get("Third Quartile") or r.get("Video Third Quartile Impressions")
                or r.get("Third Quartile Impressions")
            )
            video_skips = safe_int(
                r.get("Skips") or r.get("Video Skips")
            )
            cost_per_view = safe_decimal(
                r.get("CPV") or r.get("Cost Per Video View")
                or r.get("Cost per Video View")
            )
            active_view_measurable = safe_int(
                r.get("Active View: Measurable Impressions")
                or r.get("Active View Measurable Impressions")
            )
            active_view_viewable = safe_int(
                r.get("Active View: Viewable Impressions")
                or r.get("Active View Viewable Impressions")
            )
            active_view_pct = safe_float(
                r.get("Active View: % Viewable Impressions")
                or r.get("Active View % Viewable Impressions")
                or r.get("Active View: Percent Viewable Impressions")
            )
            billable_impressions = safe_int(r.get("Billable Impressions"))
            companion_impressions = safe_int(
                r.get("Companion Impressions") or r.get("Video Companion Impressions")
            )
            companion_clicks = safe_int(
                r.get("Companion Clicks") or r.get("Video Companion Clicks")
            )
            engagements = safe_int(r.get("Engagements"))

            s_f = float(spend) if spend else 0
            ctr = safe_float(r.get("Click Rate (CTR)") or r.get("Click Rate"))
            cpm = Decimal(str(s_f / impressions * 1000)) if spend and impressions else None
            cpc = Decimal(str(s_f / clicks)) if spend and clicks else None
            video_view_rate = safe_float(r.get("View Rate") or r.get("Video Views Rate"))

            if video_completions and video_views and video_views > 0:
                video_completion_rate = video_completions / video_views * 100
            elif video_completions and video_skips is not None:
                denom = video_completions + video_skips
                video_completion_rate = (video_completions / denom * 100) if denom > 0 else None
            else:
                video_completion_rate = None

            engagement_rate = (engagements / impressions * 100) if engagements and impressions else None

            csv_io_id = r.get("Insertion Order ID") or ""
            csv_li_id = r.get("Line Item ID") or ""
            csv_advertiser_id = r.get("Advertiser ID") or ""
            csv_li_type = r.get("Line Item Type") or ""

            csv_yt_video_id = r.get("YouTube Ad Video ID", "").strip()
            ad_type_label = ""
            creative_type = ""
            io_goal_type = ""
            campaign_id = ""
            campaign_name = ""
            io_name = ""
            li_name = ""
            creative_name = ""
            thumbnail_url = ""
            asset_url = ""
            video_url = ""
            video_duration = None
            asset_format = ""
            advertiser_tz = ""

            if entity_maps:
                if not csv_yt_video_id:
                    li_videos = entity_maps.line_item_videos.get(str(csv_li_id))
                    if li_videos and len(li_videos) > 0:
                        csv_yt_video_id = li_videos[0].get("youtube_video_id", "")

                if csv_yt_video_id and entity_maps.video_metadata:
                    vm = entity_maps.video_metadata.get(csv_yt_video_id)
                    if vm:
                        ad_type_label = vm.get("ad_type_label", "")

                io_meta = entity_maps.insertion_orders.get(str(csv_io_id))
                if io_meta:
                    campaign_id = io_meta.get("campaign_id", "")
                    io_name = io_meta.get("name", "")
                    io_goal_type = io_meta.get("goal_type", "")
                if not campaign_id:
                    li_meta = entity_maps.line_items.get(str(csv_li_id))
                    if li_meta:
                        campaign_id = li_meta.get("campaign_id", "")
                        if not li_name:
                            li_name = li_meta.get("name", "")

                if campaign_id:
                    c_meta = entity_maps.campaigns.get(campaign_id)
                    if c_meta:
                        campaign_name = c_meta.get("name", "")

                if csv_yt_video_id and entity_maps.youtube_metadata:
                    yt_meta = entity_maps.youtube_metadata.get(csv_yt_video_id)
                    if yt_meta:
                        creative_name = yt_meta.get("title", "")
                        if not thumbnail_url:
                            thumbnail_url = yt_meta.get("thumbnail_url", "")

                advertiser_tz = entity_maps.advertiser_timezone

                if ad_type_label:
                    creative_type = ad_type_label

            if not campaign_name and campaign_id:
                campaign_name = f"Campaign {campaign_id}"

            parsed_date = r.get("_parsed_date")
            ad_id = csv_yt_video_id if csv_yt_video_id else csv_li_id

            if ad_id not in asset_download_queue:
                asset_download_queue[ad_id] = {
                    "youtube_video_id": csv_yt_video_id,
                    "thumbnail_url": thumbnail_url,
                }

            ad_name = creative_name or li_name or ""
            if not ad_name and csv_yt_video_id and entity_maps and entity_maps.youtube_metadata:
                yt_meta = entity_maps.youtube_metadata.get(csv_yt_video_id)
                if yt_meta:
                    ad_name = yt_meta.get("title", "")

            media_type = "Video" if csv_li_type and "YOUTUBE" in csv_li_type.upper() else ""

            rows.append({
                "platform_connection_id": connection.id,
                "sync_job_id": sync_job_id,
                "report_date": parsed_date,
                "ad_account_id": connection.ad_account_id,
                "advertiser_id": csv_advertiser_id,
                "advertiser_name": r.get("Advertiser") or r.get("Advertiser Name") or "",
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "insertion_order_id": csv_io_id,
                "insertion_order_name": io_name,
                "line_item_id": csv_li_id,
                "line_item_name": li_name,
                "line_item_type": csv_li_type,
                "creative_id": "",
                "creative_name": creative_name,
                "creative_type": creative_type,
                "creative_source": "YouTube" if csv_yt_video_id else "",
                "ad_id": ad_id,
                "ad_name": ad_name,
                "ad_type": ad_type_label,
                "ad_position": "",
                "advertiser_timezone": advertiser_tz,
                "io_goal_type": io_goal_type,
                "youtube_ad_video_id": csv_yt_video_id,
                "media_type": media_type,
                "thumbnail_url": thumbnail_url,
                "asset_url": asset_url,
                "video_url": video_url,
                "video_duration_seconds": video_duration,
                "asset_format": asset_format,
                "currency": r.get("Advertiser Currency") or connection.currency,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "ctr": ctr,
                "cpm": cpm,
                "cpc": cpc,
                "cost_per_view": cost_per_view,
                "total_media_cost": None,
                "billable_impressions": billable_impressions,
                "total_conversions": None,
                "post_click_conversions": None,
                "post_view_conversions": None,
                "conversion_value": None,
                "roas": None,
                "cost_per_conversion": None,
                "trueview_views": video_views,
                "video_views": video_views,
                "video_completions": video_completions,
                "video_first_quartile": video_first_quartile,
                "video_midpoint": video_midpoint,
                "video_third_quartile": video_third_quartile,
                "video_skips": video_skips,
                "video_completion_rate": video_completion_rate,
                "video_view_rate": video_view_rate,
                "video_plays": None,
                "companion_impressions": companion_impressions,
                "companion_clicks": companion_clicks,
                "active_view_viewable_impressions": active_view_viewable,
                "active_view_measurable_impressions": active_view_measurable,
                "active_view_viewability": active_view_pct,
                "engagements": engagements,
                "engagement_rate": engagement_rate,
                "is_validated": True,
                "is_processed": False,
            })

        if not rows:
            return 0

        _ADDITIVE_FIELDS = [
            "spend", "impressions", "clicks",
            "trueview_views", "video_views",
            "video_completions", "video_first_quartile", "video_midpoint",
            "video_third_quartile", "video_skips",
            "companion_impressions", "companion_clicks",
            "active_view_viewable_impressions", "active_view_measurable_impressions",
            "billable_impressions", "engagements",
        ]

        def _add_val(a, b):
            if a is None and b is None:
                return None
            if a is None:
                return b
            if b is None:
                return a
            return a + b

        def _recalc_derived(row):
            s = row.get("spend")
            imp = row.get("impressions")
            clk = row.get("clicks")
            tv = row.get("trueview_views")
            vc = row.get("video_completions")
            vs = row.get("video_skips")
            eng = row.get("engagements")
            av_m = row.get("active_view_measurable_impressions")
            av_v = row.get("active_view_viewable_impressions")

            s_f = float(s) if s else 0
            row["ctr"] = (clk / imp * 100) if imp and clk else None
            row["cpm"] = Decimal(str(s_f / imp * 1000)) if s and imp else None
            row["cpc"] = Decimal(str(s_f / clk)) if s and clk else None
            row["video_view_rate"] = (tv / imp * 100) if imp and tv else None
            row["engagement_rate"] = (eng / imp * 100) if eng and imp else None
            if vc and tv and tv > 0:
                row["video_completion_rate"] = vc / tv * 100
            elif vc is not None and vs is not None:
                denom = vc + vs
                row["video_completion_rate"] = (vc / denom * 100) if denom > 0 else None
            if av_m and av_v is not None:
                row["active_view_viewability"] = (av_v / av_m * 100) if av_m > 0 else None

        seen_keys: Dict[tuple, dict] = {}
        pre_agg = len(rows)
        for row in rows:
            key = (str(row["platform_connection_id"]), str(row["report_date"]), row["ad_id"], row["ad_account_id"])
            if key in seen_keys:
                existing = seen_keys[key]
                for field in _ADDITIVE_FIELDS:
                    existing[field] = _add_val(existing.get(field), row.get(field))
                _recalc_derived(existing)
                existing["line_item_id"] = ""
                existing["line_item_name"] = ""
                existing["line_item_type"] = ""
                existing["insertion_order_id"] = ""
                existing["insertion_order_name"] = ""
            else:
                seen_keys[key] = row
        rows = list(seen_keys.values())
        logger.info(f"DV360 upsert: {pre_agg} rows aggregated to {len(rows)} unique ad_id+date rows")

        if not rows:
            return 0

        if org_dir and org_id and asset_download_queue:
            cookie_status = self._check_youtube_cookies()
            logger.info(
                f"  Downloading assets for {len(asset_download_queue)} unique ads... "
                f"(YouTube cookies: {cookie_status})"
            )
            asset_results = {}
            downloaded_videos = set()
            for ad_id, info in asset_download_queue.items():
                yt_vid = info.get("youtube_video_id", "")
                thumb = info.get("thumbnail_url", "")
                result = {"video_url": "", "asset_url": "", "thumbnail_url": "", "video_duration_seconds": None}

                if yt_vid:
                    if yt_vid not in downloaded_videos:
                        try:
                            vid_path, vid_served = await self._download_video_asset(
                                yt_vid, org_dir, org_id, ad_id
                            )
                            if vid_served:
                                result["video_url"] = vid_served
                                result["asset_url"] = vid_served
                                result["video_duration_seconds"] = self._get_video_duration(vid_path)
                                downloaded_videos.add(yt_vid)
                        except Exception as e:
                            logger.warning(f"  Video download failed for ad {ad_id}: {e}")
                    else:
                        safe_id = _sanitize_for_filename(ad_id)
                        vid_file = f"vid_dv360_{safe_id}.mp4"
                        vid_path = os.path.join(org_dir, vid_file)
                        if os.path.exists(vid_path) and os.path.getsize(vid_path) > 0:
                            result["video_url"] = f"/static/creatives/{org_id}/{vid_file}"
                            result["asset_url"] = result["video_url"]
                            result["video_duration_seconds"] = self._get_video_duration(vid_path)

                    try:
                        thumb_path, thumb_served = await self._download_youtube_thumbnail(
                            yt_vid, org_dir, org_id, ad_id
                        )
                        if thumb_served:
                            result["thumbnail_url"] = thumb_served
                    except Exception as e:
                        logger.warning(f"  Thumbnail download failed for ad {ad_id}: {e}")

                elif thumb and thumb.startswith("http"):
                    try:
                        _, img_served = await self._download_image_asset(
                            thumb, org_dir, org_id, ad_id
                        )
                        if img_served:
                            result["asset_url"] = img_served
                            result["thumbnail_url"] = img_served
                    except Exception as e:
                        logger.warning(f"  Image download failed for ad {ad_id}: {e}")

                asset_results[ad_id] = result

            for row in rows:
                ad_id = row["ad_id"]
                if ad_id in asset_results:
                    r = asset_results[ad_id]
                    if r["video_url"]:
                        row["video_url"] = r["video_url"]
                    if r["asset_url"]:
                        row["asset_url"] = r["asset_url"]
                    if r["thumbnail_url"]:
                        row["thumbnail_url"] = r["thumbnail_url"]
                    if r["video_duration_seconds"] is not None:
                        row["video_duration_seconds"] = r["video_duration_seconds"]

            logger.info(f"  Asset downloads complete: {len(downloaded_videos)} videos, {len(asset_results)} ads processed")

        BATCH_SIZE = 100
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            stmt = pg_insert(Dv360RawPerformance).values(batch)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_dv360_daily_ad",
                set_={
                    "campaign_id": stmt.excluded.campaign_id,
                    "campaign_name": stmt.excluded.campaign_name,
                    "insertion_order_name": stmt.excluded.insertion_order_name,
                    "line_item_name": stmt.excluded.line_item_name,
                    "line_item_type": stmt.excluded.line_item_type,
                    "creative_name": stmt.excluded.creative_name,
                    "creative_type": stmt.excluded.creative_type,
                    "creative_source": stmt.excluded.creative_source,
                    "ad_name": stmt.excluded.ad_name,
                    "ad_type": stmt.excluded.ad_type,
                    "ad_position": stmt.excluded.ad_position,
                    "advertiser_timezone": stmt.excluded.advertiser_timezone,
                    "io_goal_type": stmt.excluded.io_goal_type,
                    "youtube_ad_video_id": stmt.excluded.youtube_ad_video_id,
                    "media_type": stmt.excluded.media_type,
                    "thumbnail_url": stmt.excluded.thumbnail_url,
                    "asset_url": stmt.excluded.asset_url,
                    "video_url": stmt.excluded.video_url,
                    "video_duration_seconds": stmt.excluded.video_duration_seconds,
                    "asset_format": stmt.excluded.asset_format,
                    "spend": stmt.excluded.spend,
                    "impressions": stmt.excluded.impressions,
                    "clicks": stmt.excluded.clicks,
                    "ctr": stmt.excluded.ctr,
                    "cpm": stmt.excluded.cpm,
                    "cpc": stmt.excluded.cpc,
                    "cost_per_view": stmt.excluded.cost_per_view,
                    "total_media_cost": stmt.excluded.total_media_cost,
                    "billable_impressions": stmt.excluded.billable_impressions,
                    "trueview_views": stmt.excluded.trueview_views,
                    "video_views": stmt.excluded.video_views,
                    "video_completions": stmt.excluded.video_completions,
                    "video_first_quartile": stmt.excluded.video_first_quartile,
                    "video_midpoint": stmt.excluded.video_midpoint,
                    "video_third_quartile": stmt.excluded.video_third_quartile,
                    "video_skips": stmt.excluded.video_skips,
                    "video_completion_rate": stmt.excluded.video_completion_rate,
                    "video_view_rate": stmt.excluded.video_view_rate,
                    "video_plays": stmt.excluded.video_plays,
                    "companion_impressions": stmt.excluded.companion_impressions,
                    "companion_clicks": stmt.excluded.companion_clicks,
                    "active_view_viewable_impressions": stmt.excluded.active_view_viewable_impressions,
                    "active_view_measurable_impressions": stmt.excluded.active_view_measurable_impressions,
                    "active_view_viewability": stmt.excluded.active_view_viewability,
                    "engagements": stmt.excluded.engagements,
                    "engagement_rate": stmt.excluded.engagement_rate,
                    "is_processed": False,
                }
            )
            await db.execute(stmt)
            await db.flush()

        return len(rows)

    async def _upsert_conversion_records(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        records: List[Dict[str, Any]],
        sync_job_id: Optional[str],
        entity_maps: Optional[EntityMaps] = None,
    ) -> int:
        if not records:
            return 0

        if records:
            first_row = records[0]
            csv_columns = list(first_row.keys())
            logger.info(f"DV360 conv CSV columns ({len(csv_columns)}): {csv_columns}")

        def safe_float(val, default=None):
            try:
                return float(val) if val else default
            except Exception:
                return default

        def _add_val(a, b):
            if a is None and b is None:
                return None
            if a is None:
                return b
            if b is None:
                return a
            return a + b

        seen_keys: Dict[tuple, dict] = {}
        for r in records:
            csv_io_id = r.get("Insertion Order ID") or ""
            csv_li_id = r.get("Line Item ID") or ""
            csv_advertiser_id = r.get("Advertiser ID") or ""
            csv_yt_video_id = r.get("YouTube Ad Video ID", "").strip()

            if not csv_yt_video_id and entity_maps:
                li_videos = entity_maps.line_item_videos.get(str(csv_li_id))
                if li_videos and len(li_videos) > 0:
                    csv_yt_video_id = li_videos[0].get("youtube_video_id", "")

            parsed_date = r.get("_parsed_date")
            ad_id = csv_yt_video_id if csv_yt_video_id else csv_li_id

            total_conv = safe_float(
                r.get("Total Conversions") or r.get("Conversions")
            )
            post_click = safe_float(
                r.get("Post-Click Conversions") or r.get("Click Conversions")
            )
            post_view = safe_float(
                r.get("Post-View Conversions") or r.get("View Conversions")
                or r.get("Post-Impression Conversions")
            )
            cost_per_conv = safe_float(
                r.get("Revenue eCPA (Advertiser Currency)")
                or r.get("Cost Per Conversion")
                or r.get("Conversion Cost (Advertiser Currency)")
                or r.get("Revenue Conversion Cost (Advertiser Currency)")
            )

            key = (str(connection.id), str(parsed_date), ad_id, connection.ad_account_id)
            if key in seen_keys:
                existing = seen_keys[key]
                existing["total_conversions"] = _add_val(existing["total_conversions"], total_conv)
                existing["post_click_conversions"] = _add_val(existing["post_click_conversions"], post_click)
                existing["post_view_conversions"] = _add_val(existing["post_view_conversions"], post_view)
            else:
                seen_keys[key] = {
                    "platform_connection_id": connection.id,
                    "report_date": parsed_date,
                    "ad_id": ad_id,
                    "ad_account_id": connection.ad_account_id,
                    "total_conversions": total_conv,
                    "post_click_conversions": post_click,
                    "post_view_conversions": post_view,
                    "cost_per_conversion": cost_per_conv,
                }

        if not seen_keys:
            return 0

        conv_rows = list(seen_keys.values())
        logger.info(f"DV360 conv upsert: {len(records)} CSV rows aggregated to {len(conv_rows)} unique keys")

        updated = 0
        from sqlalchemy import update as sa_update
        for cr in conv_rows:
            stmt = (
                sa_update(Dv360RawPerformance)
                .where(
                    Dv360RawPerformance.platform_connection_id == cr["platform_connection_id"],
                    Dv360RawPerformance.report_date == cr["report_date"],
                    Dv360RawPerformance.ad_id == cr["ad_id"],
                    Dv360RawPerformance.ad_account_id == cr["ad_account_id"],
                )
                .values(
                    total_conversions=cr["total_conversions"],
                    post_click_conversions=cr["post_click_conversions"],
                    post_view_conversions=cr["post_view_conversions"],
                    cost_per_conversion=cr["cost_per_conversion"],
                    is_processed=False,
                )
            )
            result = await db.execute(stmt)
            updated += result.rowcount

        await db.flush()
        logger.info(f"DV360 conv upsert: updated {updated} existing rows with conversion data")
        return updated


dv360_sync = DV360SyncService()
