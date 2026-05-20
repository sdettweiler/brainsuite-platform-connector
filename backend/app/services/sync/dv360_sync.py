"""
DV360 data sync service.

Dual-API architecture:
- Display & Video 360 API v4 (displayvideo.googleapis.com/v4):
  Entity metadata — campaigns, insertion orders, line items, creatives,
  ad groups, ad group ads (YouTube video IDs), advertiser timezone.
  Also provides dimension backfill (campaign names, IO goals, creative types)
  for fields not in the slimmed Bid Manager report.
- Bid Manager API v2 (doubleclickbidmanager.googleapis.com/v2):
  Single YOUTUBE-type report with 11 API-verified metrics:
    Core: IMPRESSIONS, CLICKS, CTR
    Spend: MEDIA_COST_ADVERTISER, MEDIA_COST_ECPM_ADVERTISER,
           MEDIA_COST_ECPC_ADVERTISER, REVENUE_ADVERTISER
    Video: TRUEVIEW_VIEWS, TRUEVIEW_VIEW_RATE, VIDEO_COMPLETION_RATE,
           TRUEVIEW_CPV_ADVERTISER
  Uses 8 groupBys (date, advertiser, advertiser_name,
  advertiser_currency, insertion_order, line_item, line_item_type,
  youtube_ad_video_id).
  Note: VIDEO_*, ACTIVE_VIEW_*, COMPANION_*, ENGAGEMENTS, BILLABLE_*,
  and all conversion metrics are incompatible with YOUTUBE type +
  FILTER_YOUTUBE_AD_VIDEO_ID groupBy.

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
import secrets
import logging
import asyncio
import subprocess
import json
import tempfile
import glob
import shutil
from datetime import date, timedelta, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any, NamedTuple, Tuple
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import Dv360RawPerformance
from app.core.security import decrypt_token
from app.services.platform.dv360_oauth import dv360_oauth
from app.services.sync.video_utils import get_video_duration
from app.services.sync.proxy_cache import get_proxy_config, get_concurrency_semaphore


class _CookiesExpiredError(Exception):
    """Raised when yt-dlp reports YouTube cookies are no longer valid."""


logger = logging.getLogger(__name__)

_SAFE_FILENAME_RE = re.compile(r'[^a-zA-Z0-9_\-]')

def _sanitize_for_filename(val: str) -> str:
    return _SAFE_FILENAME_RE.sub('_', val)[:200]

BID_MANAGER_API_BASE = "https://doubleclickbidmanager.googleapis.com/v2"
DV360_API_BASE = "https://displayvideo.googleapis.com/v4"

# Limit concurrent DV360 entity-metadata calls to 5 slots globally.
# DV360 quota is ~10 req/s per user per method; 5 concurrent keeps us well under
# that even when several connections sync at the same time.
_DV360_API_SEMAPHORE = asyncio.Semaphore(5)


async def _dv360_get(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    params: Optional[dict] = None,
) -> httpx.Response:
    """Semaphore-gated GET with exponential backoff on 429 RESOURCE_EXHAUSTED."""
    backoff = 5
    for attempt in range(4):
        async with _DV360_API_SEMAPHORE:
            resp = await client.get(url, headers=headers, params=params or {})
        if resp.status_code != 429:
            return resp
        logger.warning(
            "DV360 API 429 on %s — backing off %ds (attempt %d/4)",
            url.rsplit("/", 1)[-1], backoff, attempt + 1,
        )
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)
    return resp  # return the final response so callers can log the failure


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

    async def fetch_report_data(
        self,
        access_token: str,
        connection_id,
        refresh_token_encrypted: str,
        advertiser_id: str,
        date_from: date,
        date_to: date,
        force_refetch_metadata: bool = False,
        bg_job_id=None,
        resume_query_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        entity_maps = await self._fetch_entity_metadata(access_token, advertiser_id)

        perf_records = await self._run_report(
            access_token, advertiser_id, date_from, date_to,
            connection_id=connection_id,
            refresh_token_encrypted=refresh_token_encrypted,
            bg_job_id=bg_job_id,
            resume_query_id=resume_query_id,
        )

        csv_video_ids = set()
        for r in perf_records:
            vid = (r.get("Video ID") or r.get("YouTube Ad Video ID") or "").strip()
            if vid:
                csv_video_ids.add(vid)

        conv_records = []
        try:
            conv_records = await self._run_conversion_report(
                access_token, advertiser_id, date_from, date_to,
                connection_id=connection_id,
                refresh_token_encrypted=refresh_token_encrypted,
            )
            for r in conv_records:
                vid = (r.get("Video ID") or r.get("YouTube Ad Video ID") or "").strip()
                if vid:
                    csv_video_ids.add(vid)
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            logger.warning("DV360: Conversion report failed (non-fatal, Floodlight may not be configured): %s: %s", type(e).__name__, e, exc_info=True)

        # For full resyncs fetch oEmbed for all account videos; for daily only fill gaps.
        known_video_ids = set(entity_maps.video_metadata.keys())
        if force_refetch_metadata:
            oembed_ids = known_video_ids | csv_video_ids
        else:
            oembed_ids = csv_video_ids - known_video_ids

        youtube_metadata: Dict[str, Dict[str, Any]] = {}
        if oembed_ids:
            logger.info(f"DV360: fetching oEmbed for {len(oembed_ids)} video IDs ({'full account' if force_refetch_metadata else 'report only'})")
            youtube_metadata = await self._fetch_youtube_metadata(list(oembed_ids))

        video_metadata = dict(entity_maps.video_metadata)
        for vid in csv_video_ids:
            if vid not in video_metadata:
                video_metadata[vid] = {"ad_type_label": "", "ad_name": "", "line_item_id": ""}

        entity_maps = entity_maps._replace(
            youtube_metadata=youtube_metadata,
            video_metadata=video_metadata,
        )

        return {
            "perf_records": perf_records,
            "conv_records": conv_records,
            "entity_maps": entity_maps,
        }

    async def store_report_data(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        report_data: Dict[str, Any],
        sync_job_id: Optional[str] = None,
    ) -> Dict[str, int]:
        perf_records = report_data["perf_records"]
        conv_records = report_data["conv_records"]
        entity_maps = report_data["entity_maps"]

        perf_upserted, asset_queue = await self._upsert_records(db, connection, perf_records, sync_job_id, entity_maps)

        conv_upserted = 0
        if conv_records:
            try:
                conv_upserted = await self._upsert_conversion_records(
                    db, connection, conv_records, sync_job_id, entity_maps
                )
            except (SQLAlchemyError, ValueError) as e:
                logger.warning("DV360: Conversion upsert failed (non-fatal): %s: %s", type(e).__name__, e, exc_info=True)

        return {
            "fetched": len(perf_records),
            "conv_fetched": len(conv_records),
            "upserted": perf_upserted + conv_upserted,
            "_asset_queue": asset_queue,
        }

    async def sync_date_range(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        date_from: date,
        date_to: date,
        sync_job_id: Optional[str] = None,
    ) -> Dict[str, int]:
        access_token = await self._get_valid_token(db, connection)
        report_data = await self.fetch_report_data(
            access_token, connection.id,
            connection.refresh_token_encrypted,
            connection.ad_account_id, date_from, date_to,
        )
        return await self.store_report_data(db, connection, report_data, sync_job_id)

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
                logger.warning(f"DV360 v4: Failed to fetch campaigns: {type(results[0]).__name__}: {results[0]}")

            if isinstance(results[1], dict):
                insertion_orders = results[1]
            else:
                logger.warning(f"DV360 v4: Failed to fetch insertion orders: {type(results[1]).__name__}: {results[1]}")

            if isinstance(results[2], dict):
                line_items = results[2]
            else:
                logger.warning(f"DV360 v4: Failed to fetch line items: {type(results[2]).__name__}: {results[2]}")

            if isinstance(results[3], dict):
                creatives = results[3]
            else:
                logger.warning(f"DV360 v4: Failed to fetch creatives: {type(results[3]).__name__}: {results[3]}")

            ad_groups = results[4] if isinstance(results[4], dict) else {}
            ad_group_ads = results[5] if isinstance(results[5], list) else []
            if not ad_group_ads and line_items:
                logger.warning("DV360 v4: adGroupAds returned empty but %d line items exist — video metadata may be incomplete", len(line_items))
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

        return EntityMaps(
            campaigns=campaigns,
            insertion_orders=insertion_orders,
            line_items=line_items,
            creatives=creatives,
            line_item_videos=line_item_videos,
            advertiser_timezone=advertiser_timezone,
            youtube_metadata={},
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

            resp = await _dv360_get(
                client, f"{DV360_API_BASE}/advertisers/{advertiser_id}/campaigns", headers, params,
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

            resp = await _dv360_get(
                client, f"{DV360_API_BASE}/advertisers/{advertiser_id}/insertionOrders", headers, params,
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

            resp = await _dv360_get(
                client, f"{DV360_API_BASE}/advertisers/{advertiser_id}/lineItems", headers, params,
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

            resp = await _dv360_get(
                client, f"{DV360_API_BASE}/advertisers/{advertiser_id}/creatives", headers, params,
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

                    width_px = dims.get("widthPixels") if dims else None
                    height_px = dims.get("heightPixels") if dims else None
                    asset_format = "VIDEO" if "VIDEO" in creative_type.upper() else "DISPLAY"

                    creatives[str(cr_id)] = {
                        "name": cr.get("displayName", ""),
                        "type": creative_type,
                        "hosting_source": hosting_source,
                        "thumbnail_url": thumbnail,
                        "asset_format": asset_format,
                        "width_px": width_px,
                        "height_px": height_px,
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

            resp = await _dv360_get(
                client, f"{DV360_API_BASE}/advertisers/{advertiser_id}/adGroups", headers, params,
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

            resp = await _dv360_get(
                client, f"{DV360_API_BASE}/advertisers/{advertiser_id}/adGroupAds", headers, params,
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
            resp = await _dv360_get(
                client, f"{DV360_API_BASE}/advertisers/{advertiser_id}", headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                tz = data.get("generalConfig", {}).get("timeZone", "")
                if tz:
                    logger.info(f"DV360 v4: Advertiser {advertiser_id} timezone: {tz}")
                    return tz
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.warning("DV360 v4: Failed to fetch advertiser timezone: %s: %s", type(e).__name__, e, exc_info=True)
        return ""

    async def _fetch_youtube_metadata(
        self,
        video_ids: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch video title and thumbnail via YouTube oEmbed (no auth required)."""
        if not video_ids:
            return {}

        sem = asyncio.Semaphore(20)

        async def _fetch_one(client: httpx.AsyncClient, vid: str):
            async with sem:
                try:
                    resp = await client.get(
                        "https://www.youtube.com/oembed",
                        params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return vid, {"title": data.get("title", ""), "author_name": data.get("author_name", "")}
                    if resp.status_code not in (401, 403, 404):
                        logger.warning("oEmbed HTTP %s for video %s — may be transient", resp.status_code, vid)
                    else:
                        logger.debug("oEmbed failed for video %s: HTTP %s", vid, resp.status_code)
                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    logger.debug("oEmbed failed for video %s: %s", vid, e)
            return vid, None

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            results = await asyncio.gather(*[_fetch_one(client, vid) for vid in video_ids])

        metadata = {vid: data for vid, data in results if data is not None}
        logger.info(f"YouTube oEmbed: fetched metadata for {len(metadata)}/{len(video_ids)} videos")
        return metadata

    async def _refresh_token_standalone(
        self,
        connection_id,
        refresh_token_encrypted: str,
    ) -> str:
        from app.db.base import get_session_factory
        from app.core.security import encrypt_token
        from sqlalchemy import select
        import uuid

        refresh_token = decrypt_token(refresh_token_encrypted)
        new_tokens = await dv360_oauth.refresh_access_token(refresh_token)
        new_access = new_tokens.get("access_token")

        async with get_session_factory()() as db:
            result = await db.execute(
                select(PlatformConnection).where(
                    PlatformConnection.id == (uuid.UUID(str(connection_id)) if isinstance(connection_id, str) else connection_id)
                )
            )
            conn = result.scalar_one_or_none()
            if conn:
                from datetime import timezone as tz
                conn.access_token_encrypted = encrypt_token(new_access)
                conn.token_expiry = datetime.now(tz.utc) + timedelta(seconds=new_tokens.get("expires_in", 3600))
                db.add(conn)
                await db.commit()

        logger.info("Bid Manager: OAuth token refreshed via standalone session")
        return new_access

    async def _create_and_poll_report(
        self,
        access_token: str,
        query_body: Dict[str, Any],
        label: str = "report",
        connection_id=None,
        refresh_token_encrypted: str = None,
        bg_job_id=None,
        resume_query_id: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        current_token = access_token
        headers = {
            "Authorization": f"Bearer {current_token}",
            "Content-Type": "application/json",
        }

        if resume_query_id:
            query_id = resume_query_id
            logger.info(f"Bid Manager v2 [{label}]: Resuming existing query {query_id}")
        else:
            # Retry up to 3 times for transient network errors (ConnectError, etc.)
            last_connect_exc = None
            async with httpx.AsyncClient(timeout=30) as _setup_client:
                for _attempt in range(3):
                    try:
                        create_resp = await _setup_client.post(
                            f"{BID_MANAGER_API_BASE}/queries",
                            headers=headers,
                            json=query_body,
                        )
                        last_connect_exc = None
                        break
                    except httpx.ConnectError as exc:
                        last_connect_exc = exc
                        wait = 5 * (2 ** _attempt)
                        logger.warning("Bid Manager v2 [%s]: ConnectError on create attempt %d, retrying in %ds: %s", label, _attempt + 1, wait, exc)
                        await asyncio.sleep(wait)
                if last_connect_exc is not None:
                    logger.error("Bid Manager v2 [%s]: ConnectError after 3 attempts: %s", label, last_connect_exc)
                    return None

                if create_resp.status_code != 200:
                    logger.error(f"Bid Manager v2 [{label}]: Create query failed ({create_resp.status_code}): {create_resp.text[:500]}")
                    return None

                query_data = create_resp.json()
                query_id = query_data.get("queryId")
                if not query_id:
                    logger.error(f"Bid Manager v2 [{label}]: No queryId returned: {query_data}")
                    return []

                run_resp = await _setup_client.post(
                    f"{BID_MANAGER_API_BASE}/queries/{query_id}:run",
                    headers=headers,
                    json={},
                )
                if run_resp.status_code != 200:
                    logger.error(f"Bid Manager v2 [{label}]: Run query failed ({run_resp.status_code}): {run_resp.text[:500]}")
                    return None

        # Write checkpoint before entering poll loop so an INTERRUPTED job can resume
        if bg_job_id is not None:
            try:
                from app.services.sync.job_tracker import update_background_job as _ubj
                import uuid as _uuid
                _jid = bg_job_id if isinstance(bg_job_id, _uuid.UUID) else _uuid.UUID(str(bg_job_id))
                await _ubj(_jid, output={"dv360_query_id": query_id, "dv360_poll_started_at": datetime.utcnow().isoformat()})
            except Exception as _ck_err:
                logger.warning("DV360: checkpoint write failed (non-fatal): %s", _ck_err)

        logger.info(f"Bid Manager v2 [{label}]: Query {query_id} {'resumed' if resume_query_id else 'created and running'}, polling for results (YouTube reports may take up to 2 hours)")

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

            if connection_id and refresh_token_encrypted and (elapsed - last_token_refresh) > 2700:
                try:
                    current_token = await self._refresh_token_standalone(connection_id, refresh_token_encrypted)
                    headers["Authorization"] = f"Bearer {current_token}"
                    last_token_refresh = elapsed
                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    logger.warning("Bid Manager v2 [%s]: Token refresh failed: %s: %s", label, type(e).__name__, e, exc_info=True)

            # Fresh client per poll tick — avoids RemoteProtocolError on stale pooled connections
            try:
                async with httpx.AsyncClient(timeout=60) as _poll_client:
                    status_resp = await _poll_client.get(
                        f"{BID_MANAGER_API_BASE}/queries/{query_id}/reports",
                        headers=headers,
                    )
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.warning("Bid Manager v2 [%s]: Poll error: %s: %s", label, type(e).__name__, e, exc_info=True)
                continue

            if status_resp.status_code == 401 and connection_id and refresh_token_encrypted:
                try:
                    current_token = await self._refresh_token_standalone(connection_id, refresh_token_encrypted)
                    headers["Authorization"] = f"Bearer {current_token}"
                    last_token_refresh = elapsed
                    continue
                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    logger.warning("Bid Manager v2 [%s]: Token refresh on 401 failed: %s: %s", label, type(e).__name__, e, exc_info=True)

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
                async with httpx.AsyncClient(timeout=30) as _cleanup_client:
                    await _cleanup_client.delete(
                        f"{BID_MANAGER_API_BASE}/queries/{query_id}",
                        headers=headers,
                    )
            except (httpx.RequestError, httpx.HTTPStatusError):
                pass
            return None

        # CSV download — fresh client with long timeout for potentially large GCS files
        try:
            async with httpx.AsyncClient(timeout=600, follow_redirects=True) as _csv_client:
                csv_resp = await _csv_client.get(
                    report_url,
                    headers={"Authorization": f"Bearer {current_token}"},
                )
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error(f"Bid Manager v2 [{label}]: CSV download failed: {type(e).__name__}: {e}")
            return None
        if csv_resp.status_code != 200:
            logger.error(f"Bid Manager v2 [{label}]: CSV download failed ({csv_resp.status_code})")
            return None

        records = self._parse_csv(csv_resp.text)
        logger.info(f"Bid Manager v2 [{label}]: Downloaded CSV with {len(records)} data rows")

        try:
            async with httpx.AsyncClient(timeout=30) as _cleanup_client:
                await _cleanup_client.delete(
                    f"{BID_MANAGER_API_BASE}/queries/{query_id}",
                    headers=headers,
                )
        except (httpx.RequestError, httpx.HTTPStatusError):
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
        "METRIC_CTR",
        "METRIC_MEDIA_COST_ADVERTISER",
        "METRIC_MEDIA_COST_ECPM_ADVERTISER",
        "METRIC_MEDIA_COST_ECPC_ADVERTISER",
        "METRIC_REVENUE_ADVERTISER",
        "METRIC_TRUEVIEW_VIEWS",
        "METRIC_TRUEVIEW_VIEW_RATE",
        "METRIC_VIDEO_COMPLETION_RATE",
        "METRIC_TRUEVIEW_CPV_ADVERTISER",
    ]

    async def _run_report(
        self,
        access_token: str,
        advertiser_id: str,
        date_from: date,
        date_to: date,
        connection_id=None,
        refresh_token_encrypted: str = None,
        bg_job_id=None,
        resume_query_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query_body = self._build_query_body(
            advertiser_id, date_from, date_to,
            self._PERF_METRICS, title_suffix="_perf",
        )
        result = await self._create_and_poll_report(
            access_token, query_body, label="perf",
            connection_id=connection_id,
            refresh_token_encrypted=refresh_token_encrypted,
            bg_job_id=bg_job_id,
            resume_query_id=resume_query_id,
        )
        return result if result is not None else []

    async def _run_conversion_report(
        self,
        access_token: str,
        advertiser_id: str,
        date_from: date,
        date_to: date,
        connection_id=None,
        refresh_token_encrypted: str = None,
    ) -> List[Dict[str, Any]]:
        logger.info(
            "DV360: All conversion metrics incompatible with "
            "YOUTUBE + FILTER_YOUTUBE_AD_VIDEO_ID — skipping conversion report"
        )
        return []

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
        org_id: str,
        ad_id: str,
        prefix: str = "img",
    ) -> Tuple[Optional[str], Optional[str]]:
        try:
            from app.services.object_storage import get_object_storage
            obj_storage = get_object_storage()
            loop = asyncio.get_running_loop()

            safe_id = _sanitize_for_filename(ad_id)
            ext = ".jpg"
            if ".png" in url.lower():
                ext = ".png"
            elif ".webp" in url.lower():
                ext = ".webp"

            filename = f"{prefix}_dv360_{safe_id}{ext}"
            relative_path = f"creatives/{org_id}/{filename}"

            if await loop.run_in_executor(None, obj_storage.file_exists, relative_path):
                return None, obj_storage.served_url(relative_path)

            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()

                content_type = resp.headers.get("content-type", "")
                if "png" in content_type:
                    ext = ".png"
                elif "webp" in content_type:
                    ext = ".webp"

                filename = f"{prefix}_dv360_{safe_id}{ext}"
                relative_path = f"creatives/{org_id}/{filename}"

            served_url = await loop.run_in_executor(None, obj_storage.upload_bytes, resp.content, relative_path)
            logger.info(f"  Downloaded DV360 asset: {filename} ({len(resp.content)} bytes)")
            return None, served_url
        except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
            logger.warning("Failed to download DV360 image for ad %s: %s: %s", ad_id, type(e).__name__, e, exc_info=True)
            return None, None

    def _check_youtube_cookies(self, env_var: str = "YOUTUBE_COOKIES") -> str:
        """Check YouTube cookie status. Returns 'valid', 'expired', or 'missing'."""
        cookies_data = os.environ.get(env_var, "")
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

    def _get_cookie_env_vars_to_try(self) -> List[str]:
        """Return list of cookie env var names to try, in priority order."""
        to_try = []
        primary = self._check_youtube_cookies("YOUTUBE_COOKIES")
        backup = self._check_youtube_cookies("YOUTUBE_COOKIES_BACKUP")
        if primary == "valid":
            to_try.append("YOUTUBE_COOKIES")
        if backup == "valid":
            to_try.append("YOUTUBE_COOKIES_BACKUP")
        return to_try

    async def _get_cookies_from_db(self) -> List[str]:
        """Fetch decrypted YouTube cookies from system_config (primary, then backup).

        Falls back to env vars if DB has no cookies (graceful migration path per D-11).
        Returns: list of cookie strings in preference order.

        Security (T-14-10): Decrypted cookie content is never logged.
        Only decrypt failures are logged (without the cipher text).
        """
        from app.core.security import decrypt_token
        from app.db.base import get_session_factory
        from app.models.system_config import SystemConfig
        from sqlalchemy import select

        cookies = []

        try:
            async with get_session_factory()() as db:
                result = await db.execute(select(SystemConfig).limit(1))
                config = result.scalar_one_or_none()

                if config:
                    if config.youtube_cookies_encrypted:
                        try:
                            cookies.append(decrypt_token(config.youtube_cookies_encrypted))
                        except Exception:
                            logger.warning("Failed to decrypt primary YouTube cookie from DB")
                    if config.youtube_cookies_backup_encrypted:
                        try:
                            cookies.append(decrypt_token(config.youtube_cookies_backup_encrypted))
                        except Exception:
                            logger.warning("Failed to decrypt backup YouTube cookie from DB")
        except Exception as e:
            logger.warning("Failed to read cookies from DB, falling back to env vars: %s", e)

        # Fall back to env vars if DB is empty (per D-11 graceful migration)
        if not cookies:
            env_primary = os.environ.get("YOUTUBE_COOKIES", "").strip()
            env_backup = os.environ.get("YOUTUBE_COOKIES_BACKUP", "").strip()
            if env_primary:
                cookies.append(env_primary)
            if env_backup:
                cookies.append(env_backup)

        return cookies

    async def _download_video_asset(
        self,
        youtube_video_id: str,
        org_id: str,
        ad_id: str,
        bg_job_id=None,
    ) -> Tuple[Optional[float], Optional[str], Optional[str]]:
        from app.services.object_storage import get_object_storage
        obj_storage = get_object_storage()
        loop = asyncio.get_running_loop()

        safe_id = _sanitize_for_filename(ad_id)
        filename = f"vid_dv360_{safe_id}.mp4"
        relative_path = f"creatives/{org_id}/{filename}"

        if await loop.run_in_executor(None, obj_storage.file_exists, relative_path):
            return None, obj_storage.served_url(relative_path), None

        # Read cookies from DB first, fall back to env vars if DB is empty (D-11)
        cookies = await self._get_cookies_from_db()

        # Load proxy config from shared cache (PERF-04, D-07)
        proxy_enabled, proxy_url = await get_proxy_config()
        if proxy_enabled and proxy_url:
            # Sticky session injection — IPRoyal only (user-session-ID format)
            # Other providers (DataImpulse etc.) use plain user:pass and reject the suffix
            _session_id = secrets.token_urlsafe(9)
            if "@" in proxy_url and "iproyal.com" in proxy_url:
                _user_part, _host_part = proxy_url.rsplit("@", 1)
                if "://" in _user_part:
                    _scheme_end = _user_part.index("://") + 3
                    _scheme = _user_part[:_scheme_end]
                    _creds = _user_part[_scheme_end:]
                    if ":" in _creds:
                        _username, _password = _creds.split(":", 1)
                        proxy_url = f"{_scheme}{_username}-session-{_session_id}:{_password}@{_host_part}"

        url = f"https://www.youtube.com/watch?v={youtube_video_id}"

        tmpdir = tempfile.mkdtemp()
        tmp_base = os.path.join(tmpdir, "video")

        async def _do_download(proxy: Optional[str], cookie_data: str) -> bool:
            """Download video in a single yt-dlp session.

            Combines extraction and download in one call so cookies and proxy are
            present for format selection. Returns True on success, raises
            _CookiesExpiredError or Exception on failure.
            """
            import yt_dlp

            _expired = [False]

            def _redact(msg: str) -> str:
                """Redact proxy credentials from log/exception message (D-05).

                Uses proxy_url from outer _download_video_asset scope so credentials
                are redacted even on the PO-first attempt where proxy param is None.
                """
                if not proxy_url:
                    return msg
                return re.sub(r'https?://[^@/]+@([^/:]+)[^"\s]*', r'[PROXY:\1]', msg)

            class _YDLLogger:
                def debug(self, msg):
                    if msg.startswith("[debug] "):
                        logger.debug("yt-dlp: %s", _redact(msg))
                    else:
                        logger.info("yt-dlp: %s", _redact(msg))
                def info(self, msg): logger.info("yt-dlp: %s", _redact(msg))
                def warning(self, msg):
                    if "no longer valid" in msg:
                        _expired[0] = True
                    logger.warning("yt-dlp: %s", _redact(msg))
                def error(self, msg):
                    if "no longer valid" in msg:
                        _expired[0] = True
                    logger.error("yt-dlp: %s", _redact(msg))

            ydl_opts: dict = {
                "outtmpl": f"{tmp_base}.%(ext)s",
                # Use pre-merged format — no ffmpeg required for format selection.
                # "best" picks the highest-quality single stream (typically 720p/1080p mp4).
                "format": "best/b",
                "quiet": True,
                # no_warnings intentionally omitted: yt-dlp's report_warning() returns early
                # when no_warnings=True, suppressing the custom logger's warning() call even
                # with a custom logger attached. We need warning() to detect "no longer valid".
                "socket_timeout": 30,
                "ignore_no_formats_error": True,
                "logger": _YDLLogger(),
                "remote_components": ["ejs:github"],
            }
            if proxy:
                ydl_opts["proxy"] = proxy

            # Accept cookie string directly (T-14-10: never log cookie content)
            cookie_file = None
            if cookie_data:
                _raw_lines = cookie_data.splitlines()
                _valid_lines = []
                _skipped = 0
                for _ln in _raw_lines:
                    _stripped = _ln.lstrip()
                    # Keep comments, blank lines, and lines with exactly 7 tab-separated fields.
                    # Netscape cookie data lines must have 7 fields; anything else is corrupt.
                    if not _stripped or _stripped.startswith('#') or len(_stripped.split('\t')) == 7:
                        _valid_lines.append(_stripped)
                    else:
                        _skipped += 1
                if _skipped:
                    logger.warning("[DL:%s] Stripped %d corrupt cookie line(s) from %s cookie file", _dl_tag, _skipped, label)
                # MozillaCookieJar requires the first line to match "# (Netscape )?HTTP Cookie File"
                _NETSCAPE_HEADER = "# Netscape HTTP Cookie File"
                if not any(ln.strip().startswith("# ") and "HTTP Cookie File" in ln for ln in _valid_lines[:3]):
                    _valid_lines.insert(0, _NETSCAPE_HEADER)
                    logger.warning("[DL:%s] Cookie file missing Netscape header — injected", _dl_tag)
                cleaned = "\n".join(_valid_lines)
                cookie_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False
                )
                cookie_file.write(cleaned)
                cookie_file.close()
                ydl_opts["cookiefile"] = cookie_file.name

            def download_sync():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

            try:
                await loop.run_in_executor(None, download_sync)
                if _expired[0]:
                    raise _CookiesExpiredError("YouTube cookies are no longer valid")
                return True
            except _CookiesExpiredError:
                raise
            except Exception as e:
                if _expired[0]:
                    raise _CookiesExpiredError("YouTube cookies are no longer valid") from e
                redacted_error = _redact(str(e))
                logger.error("yt-dlp exception: %s", redacted_error)
                raise
            finally:
                if cookie_file and os.path.exists(cookie_file.name):
                    os.remove(cookie_file.name)

        _dl_tag = youtube_video_id

        # Build download attempt list (D-04):
        # proxy off: [primary, backup] or [""] if no cookies (existing behavior preserved)
        # proxy on:  ["", primary, backup] — PO-first (no proxy, no cookies), then proxy variants
        attempts = cookies if cookies else [""]
        if proxy_enabled and proxy_url:
            attempts = ["", *attempts]

        # Phase 25 (PERF-02): semaphore only wraps yt-dlp download — upload/DB run after release.
        semaphore = await get_concurrency_semaphore()
        actual_path: Optional[str] = None
        winning_label: Optional[str] = None
        logger.info("[DL:%s] DV360 — waiting for slot (%d attempt(s))", _dl_tag, len(attempts))
        try:
            async with semaphore:
                if bg_job_id:
                    from app.services.sync.job_tracker import get_job_status as _gjstat
                    if await _gjstat(bg_job_id) == "INTERRUPTED":
                        logger.info("[DL:%s] Job interrupted — slot released without downloading", _dl_tag)
                        return None, None, None
                logger.info("[DL:%s] Slot acquired", _dl_tag)
                for i, cookie in enumerate(attempts):
                    if not cookie:
                        label = "no cookies"
                    elif cookies and cookie == cookies[0]:
                        label = "primary"
                    else:
                        label = "backup"
                    logger.info("[DL:%s] Attempt %d/%d (%s)", _dl_tag, i + 1, len(attempts), label)

                    # PO-first: first attempt when proxy enabled uses no proxy and no cookies
                    if i == 0 and proxy_enabled and proxy_url:
                        attempt_proxy: Optional[str] = None
                    else:
                        attempt_proxy = proxy_url if proxy_enabled else None

                    try:
                        await _do_download(proxy=attempt_proxy, cookie_data=cookie)

                        _VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".flv", ".m4v"}
                        matches = [
                            m for m in glob.glob(f"{tmp_base}.*")
                            if os.path.getsize(m) > 0 and os.path.splitext(m)[1].lower() in _VIDEO_EXTS
                        ]
                        actual_path = matches[0] if matches else None
                        if actual_path:
                            winning_label = label
                            break  # semaphore released after this block; upload runs outside
                        else:
                            logger.warning("[DL:%s] yt-dlp finished but output file missing", _dl_tag)
                    except _CookiesExpiredError:
                        if i < len(attempts) - 1:
                            logger.info("[DL:%s] %s cookies expired — trying backup slot", _dl_tag, label)
                            continue
                        logger.warning("[DL:%s] All cookie slots expired — aborting", _dl_tag)
                        if cookies:
                            try:
                                from app.services.notifications import create_superadmin_notification
                                from app.models.system_config import SystemConfig as _SC2
                                from app.db.base import get_session_factory as _gsf2
                                from sqlalchemy import select as _sel
                                from datetime import datetime as _dt, timezone as _tz
                                _dl_count, _days = 0, None
                                try:
                                    async with _gsf2()() as _stats_db:
                                        _cfg = (await _stats_db.execute(_sel(_SC2).limit(1))).scalar_one_or_none()
                                        if _cfg:
                                            _dl_count = _cfg.youtube_cookies_download_count or 0
                                            if _cfg.youtube_cookies_refreshed_at:
                                                _days = (_dt.now(_tz.utc) - _cfg.youtube_cookies_refreshed_at).days
                                except Exception:
                                    pass
                                _stats = f"expired after {_dl_count} video{'s' if _dl_count != 1 else ''}"
                                if _days is not None:
                                    _stats += f" and {_days} day{'s' if _days != 1 else ''}"
                                await create_superadmin_notification(
                                    type="COOKIE_FAILED",
                                    title="YouTube cookies expired",
                                    message=f"yt-dlp download aborted — YouTube cookies are no longer valid. Update cookies in Admin settings. ({_stats})",
                                    data={"deeplink": "/configuration/admin"},
                                )
                            except Exception as notif_err:
                                logger.warning("Failed to send COOKIE_FAILED notification: %s", notif_err)
                        raise
                    except Exception as e:
                        err_str = str(e)
                        is_format_error = "Requested format is not available" in err_str or "no video formats" in err_str.lower()
                        if is_format_error:
                            logger.warning("[DL:%s] No video formats available — skipping", _dl_tag)
                            break
                        # yt-dlp __exit__ raises when saving back a corrupt cookie file even after
                        # a successful download. Recover the file if it landed on disk.
                        _VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".flv", ".m4v"}
                        _recovery = [m for m in glob.glob(f"{tmp_base}.*") if os.path.getsize(m) > 0 and os.path.splitext(m)[1].lower() in _VIDEO_EXTS]
                        if _recovery:
                            logger.info("[DL:%s] Download succeeded despite exception (%s) — recovering file", _dl_tag, type(e).__name__)
                            actual_path = _recovery[0]
                            winning_label = label
                            break
                        if i < len(attempts) - 1:
                            logger.info("[DL:%s] Attempt %d failed (%s) — trying next", _dl_tag, i + 1, type(e).__name__)
                            continue
                        logger.warning("[DL:%s] FAILED: %s: %s", _dl_tag, type(e).__name__, e, exc_info=True)

            # Semaphore released — upload, DB update, frame extraction run concurrently with other downloads
            if actual_path:
                size_mb = os.path.getsize(actual_path) / (1024 * 1024)
                logger.info("[DL:%s] Slot released — uploading (%.1f MB)", _dl_tag, size_mb)
                duration = get_video_duration(actual_path)
                served_url = await loop.run_in_executor(None, obj_storage.upload_file, actual_path, relative_path, "video/mp4")
                logger.info("[DL:%s] COMPLETE: %s (%.1f MB, %s cookies)", _dl_tag, filename, size_mb, winning_label)
                try:
                    from sqlalchemy import update as _sa_update
                    from app.models.system_config import SystemConfig as _SC
                    from app.db.base import get_session_factory as _gsf
                    async with _gsf()() as _sc_db:
                        _upd_vals: dict = {"youtube_cookies_download_count": _SC.youtube_cookies_download_count + 1}
                        if winning_label == "primary":
                            _upd_vals["youtube_cookies_runtime_expired"] = False
                        elif winning_label == "backup":
                            _upd_vals["youtube_cookies_backup_runtime_expired"] = False
                        await _sc_db.execute(_sa_update(_SC).values(**_upd_vals))
                        await _sc_db.commit()
                except Exception as _cnt_err:
                    logger.debug("Could not increment YT download counter: %s", _cnt_err)
                from app.services.sync.thumbnail_utils import extract_first_frame_and_upload
                thumb_path = f"creatives/{org_id}/thumb_dv360_{safe_id}.jpg"
                frame_thumb = None
                if not await loop.run_in_executor(None, obj_storage.file_exists, thumb_path):
                    frame_thumb = await extract_first_frame_and_upload(actual_path, org_id, ad_id, "dv360", obj_storage)
                return duration, served_url, frame_thumb
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        logger.warning("[DL:%s] No file produced — all attempts failed", _dl_tag)
        return None, None, None

    async def _download_youtube_thumbnail(
        self,
        youtube_video_id: str,
        org_id: str,
        ad_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        from app.services.object_storage import get_object_storage
        obj_storage = get_object_storage()
        loop = asyncio.get_running_loop()

        safe_id = _sanitize_for_filename(ad_id)
        filename = f"thumb_dv360_{safe_id}.jpg"
        relative_path = f"creatives/{org_id}/{filename}"

        if await loop.run_in_executor(None, obj_storage.file_exists, relative_path):
            return None, obj_storage.served_url(relative_path)

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
                        served_url = await loop.run_in_executor(None, obj_storage.upload_bytes, resp.content, relative_path, "image/jpeg")
                        return None, served_url
        except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
            logger.warning("Failed to download YouTube thumbnail for ad %s: %s: %s", ad_id, type(e).__name__, e, exc_info=True)
        return None, None

    async def _upsert_records(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        records: List[Dict[str, Any]],
        sync_job_id: Optional[str],
        entity_maps: Optional[EntityMaps] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        if not records:
            return 0, {}

        first_row = records[0]
        csv_columns = list(first_row.keys())
        logger.info(f"DV360 perf CSV columns ({len(csv_columns)}): {csv_columns}")

        org_id = str(connection.organization_id) if hasattr(connection, "organization_id") and connection.organization_id else None

        def safe_decimal(val, default=None):
            try:
                return Decimal(str(val)) if val else default
            except (ValueError, InvalidOperation):
                return default

        def safe_int(val, default=None):
            try:
                return int(float(val)) if val else default
            except (ValueError, TypeError):
                return default

        def safe_float(val, default=None):
            try:
                if not val:
                    return default
                s = str(val).strip().rstrip("%")
                return float(s) if s else default
            except (ValueError, TypeError):
                return default

        rows = []
        asset_download_queue = {}
        for r in records:
            spend = safe_decimal(r.get("Media Cost (Advertiser Currency)"))
            impressions = safe_int(r.get("Impressions"))
            clicks = safe_int(r.get("Clicks"))
            trueview_views = safe_int(
                r.get("TrueView: Views") or r.get("TrueView Views")
            )
            total_media_cost = safe_decimal(r.get("Revenue (Adv Currency)"))
            cost_per_view = safe_decimal(
                r.get("YouTube: Revenue eCPV (Adv Currency)")
                or r.get("TrueView CPV (Adv Currency)")
                or r.get("TrueView CPV (Advertiser Currency)")
                or r.get("CPV")
            )

            s_f = float(spend) if spend else 0
            ctr = safe_float(r.get("Click Rate (CTR)"))
            cpm = safe_decimal(
                r.get("Media Cost eCPM (Adv Currency)")
            ) or (Decimal(str(s_f / impressions * 1000)) if spend and impressions else None)
            cpc = safe_decimal(
                r.get("Media Cost eCPC (Adv Currency)")
            ) or (Decimal(str(s_f / clicks)) if spend and clicks else None)
            video_view_rate = safe_float(
                r.get("TrueView: View Rate") or r.get("TrueView VR")
            )
            video_completion_rate = safe_float(
                r.get("Completion Rate (Video)") or r.get("Complete Rate (Video)")
            )

            csv_io_id = r.get("Insertion Order ID") or ""
            csv_li_id = r.get("Line Item ID") or ""
            csv_advertiser_id = r.get("Advertiser ID") or ""
            csv_li_type = r.get("Line Item Type") or ""

            csv_yt_video_id = (
                r.get("Video ID", "").strip()
                or r.get("YouTube Ad Video ID", "").strip()
            )
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
            asset_format = "VIDEO" if csv_yt_video_id else ""
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
            ad_id = csv_li_id

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
                "width_px": None,
                "height_px": None,
                "currency": r.get("Advertiser Currency") or connection.currency,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "ctr": ctr,
                "cpm": cpm,
                "cpc": cpc,
                "cost_per_view": cost_per_view,
                "total_media_cost": total_media_cost,
                "billable_impressions": None,
                "total_conversions": None,
                "post_click_conversions": None,
                "post_view_conversions": None,
                "conversion_value": None,
                "roas": None,
                "cost_per_conversion": None,
                "trueview_views": trueview_views,
                "video_views": trueview_views,
                "video_completions": None,
                "video_first_quartile": None,
                "video_midpoint": None,
                "video_third_quartile": None,
                "video_skips": None,
                "video_completion_rate": video_completion_rate,
                "video_view_rate": video_view_rate,
                "video_plays": None,
                "companion_impressions": None,
                "companion_clicks": None,
                "active_view_viewable_impressions": None,
                "active_view_measurable_impressions": None,
                "active_view_viewability": None,
                "engagements": None,
                "engagement_rate": None,
                "is_validated": True,
                "is_processed": False,
            })

        if not rows:
            return 0, {}

        _ADDITIVE_FIELDS = [
            "spend", "impressions", "clicks",
            "trueview_views", "video_views",
            "video_completions", "video_first_quartile",
            "video_midpoint", "video_third_quartile",
            "video_skips", "companion_impressions",
            "companion_clicks", "active_view_viewable_impressions",
            "active_view_measurable_impressions",
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
            tv = row.get("trueview_views") or row.get("video_views")
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
            if vc and tv:
                row["video_completion_rate"] = vc / tv * 100
            elif vc and vs is not None:
                denom = vc + vs
                row["video_completion_rate"] = (vc / denom * 100) if denom > 0 else None
            row["engagement_rate"] = (eng / imp * 100) if eng and imp else None
            row["active_view_viewability"] = (av_v / av_m * 100) if av_m and av_v else row.get("active_view_viewability")

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
            return 0, {}

        BATCH_SIZE = 25
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
                    "width_px": stmt.excluded.width_px,
                    "height_px": stmt.excluded.height_px,
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

        return len(rows), {"org_id": org_id, "queue": asset_download_queue}

    async def download_assets_post_commit(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        asset_info: Dict[str, Any],
        bg_job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        org_id = asset_info.get("org_id")
        queue = asset_info.get("queue", {})

        if not org_id or not queue:
            return {"downloaded": [], "failed": []}

        db_cookies = await self._get_cookies_from_db()
        can_download_video = len(db_cookies) > 0
        logger.info(
            f"  Downloading assets for {len(queue)} unique ads... "
            f"(cookies: {'available' if can_download_video else 'none'})"
        )
        if not can_download_video:
            logger.warning("  No valid cookies found — attempting cookieless video downloads")

        from sqlalchemy import update as sa_update

        # Pre-flight: abort if cookies already flagged expired
        try:
            _pre_cfg = (await db.execute(text("SELECT youtube_cookies_runtime_expired FROM system_config LIMIT 1"))).first()
            if _pre_cfg and _pre_cfg[0]:
                raise _CookiesExpiredError("YouTube cookies already flagged as expired — skipping video downloads")
        except _CookiesExpiredError:
            raise
        except Exception:
            pass

        # Group by YouTube video ID; separate image-only ads
        _yt_vid_to_ads: dict = {}
        _image_only: dict = {}
        for _ad_id, _info in queue.items():
            _yt = _info.get("youtube_video_id", "")
            if _yt:
                _yt_vid_to_ads.setdefault(_yt, []).append(_ad_id)
            else:
                _thumb = _info.get("thumbnail_url", "")
                if _thumb and _thumb.startswith("http"):
                    _image_only[_ad_id] = _thumb

        import uuid as _uuid
        from app.services.sync.job_tracker import get_job_status as _get_status, update_background_job as _ubj

        _dl_lock = asyncio.Lock()
        _cookies_expired = [False]
        _succeeded_count = [0]
        _failed_count = [0]

        thumb_results: dict = {}   # ad_id -> served thumbnail URL
        video_results: dict = {}   # ad_id -> {video_url, asset_url, video_duration_seconds}
        video_failures: dict = {}  # ad_id -> error string

        async def _dl_unit(yt_vid: str, ad_ids: list) -> None:
            """Download thumbnail + video for one unique YouTube video ID, map results to all ads."""
            if bg_job_id:
                _jid = bg_job_id if isinstance(bg_job_id, _uuid.UUID) else _uuid.UUID(str(bg_job_id))
                if await _get_status(_jid) == "INTERRUPTED":
                    logger.info("DV360 download: job %s interrupted — skipping %s", _jid, yt_vid)
                    return

            # Thumbnail: pass yt_vid as storage key — one file per unique video, shared across ads
            thumb_served = None
            try:
                _, thumb_served = await self._download_youtube_thumbnail(yt_vid, org_id, yt_vid)
            except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
                logger.warning("Thumbnail failed for video %s: %s: %s", yt_vid, type(e).__name__, e)

            # Video: semaphore-gated, also keyed by yt_vid
            try:
                vid_duration, vid_served, frame_thumb = await self._download_video_asset(
                    yt_vid, org_id, yt_vid, bg_job_id=bg_job_id
                )
                effective_thumb = thumb_served or frame_thumb
                async with _dl_lock:
                    if vid_served:
                        _succeeded_count[0] += len(ad_ids)
                        for _ad_id in ad_ids:
                            video_results[_ad_id] = {
                                "video_url": vid_served,
                                "asset_url": vid_served,
                                "video_duration_seconds": vid_duration,
                            }
                            if effective_thumb:
                                thumb_results[_ad_id] = effective_thumb
                    else:
                        _failed_count[0] += len(ad_ids)
                        for _ad_id in ad_ids:
                            video_failures[_ad_id] = "download failed — no output file produced"
                        logger.warning("[DL:%s] No file produced — skipping %d ad(s)", yt_vid, len(ad_ids))
                        if thumb_served:
                            for _ad_id in ad_ids:
                                thumb_results[_ad_id] = thumb_served
            except _CookiesExpiredError:
                async with _dl_lock:
                    _cookies_expired[0] = True
                    _failed_count[0] += len(ad_ids)
                    if thumb_served:
                        for _ad_id in ad_ids:
                            thumb_results[_ad_id] = thumb_served
            except Exception as e:
                async with _dl_lock:
                    _failed_count[0] += len(ad_ids)
                    for _ad_id in ad_ids:
                        video_failures[_ad_id] = f"{type(e).__name__}: {e}"
                    if thumb_served:
                        for _ad_id in ad_ids:
                            thumb_results[_ad_id] = thumb_served
                logger.warning("Video download failed for %s: %s: %s", yt_vid, type(e).__name__, e, exc_info=True)
            finally:
                if bg_job_id:
                    await _ubj(bg_job_id, progress_current=_succeeded_count[0], output={"stats": {"succeeded": _succeeded_count[0], "failed": _failed_count[0]}})

        async def _dl_image(ad_id: str, thumb_url: str) -> None:
            """Download image-only ad thumbnail (no YouTube video)."""
            try:
                _, img_served = await self._download_image_asset(thumb_url, org_id, ad_id)
                if img_served:
                    async with _dl_lock:
                        thumb_results[ad_id] = img_served
            except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
                logger.warning("Image download failed for ad %s: %s: %s", ad_id, type(e).__name__, e)

        # Launch all download units (thumbnail+video per unique yt_vid) and image-only downloads concurrently
        _tasks = [_dl_unit(yt_vid, ads) for yt_vid, ads in _yt_vid_to_ads.items()]
        _tasks += [_dl_image(ad_id, thumb_url) for ad_id, thumb_url in _image_only.items()]
        await asyncio.gather(*_tasks)

        # Commit thumbnails before checking cookie expiry so they're preserved on partial failure
        _image_only_ad_ids = set(_image_only.keys())
        if thumb_results:
            for ad_id, served_url in thumb_results.items():
                set_vals: dict = {"thumbnail_url": served_url}
                if ad_id in _image_only_ad_ids:
                    set_vals["asset_url"] = served_url
                await db.execute(
                    sa_update(Dv360RawPerformance)
                    .where(
                        Dv360RawPerformance.platform_connection_id == connection.id,
                        Dv360RawPerformance.ad_id == ad_id,
                    )
                    .values(**set_vals)
                )
            await db.commit()
            logger.info(f"  Thumbnails committed: {len(thumb_results)} ads updated")

        if _cookies_expired[0]:
            raise _CookiesExpiredError("YouTube cookies expired during batch download")

        if video_results:
            for ad_id, r in video_results.items():
                set_vals = {}
                if r["video_url"]:
                    set_vals["video_url"] = r["video_url"]
                if r["asset_url"]:
                    set_vals["asset_url"] = r["asset_url"]
                if r["video_duration_seconds"] is not None:
                    set_vals["video_duration_seconds"] = r["video_duration_seconds"]
                if set_vals:
                    await db.execute(
                        sa_update(Dv360RawPerformance)
                        .where(
                            Dv360RawPerformance.platform_connection_id == connection.id,
                            Dv360RawPerformance.ad_id == ad_id,
                        )
                        .values(**set_vals)
                    )
            await db.commit()
            logger.info(f"  Videos committed: {len(video_results)} ads updated")

        logger.info(f"  Asset downloads complete: {len(video_results)} videos, {len(thumb_results)} thumbnails")

        # Propagate to CreativeAsset and reset autofill tracking
        all_downloaded: dict = {
            **{ad_id: url for ad_id, url in thumb_results.items() if ad_id in _image_only_ad_ids},
            **{ad_id: r["asset_url"] for ad_id, r in video_results.items() if r.get("asset_url")},
        }
        if all_downloaded:
            from sqlalchemy import select, or_
            from sqlalchemy import update as _sa_update
            from app.models.creative import CreativeAsset
            from app.models.ai_inference import AIInferenceTracking
            from datetime import datetime as _dt
            from app.services.sync.thumbnail_utils import is_raw_cdn_url

            for ad_id, served_url in all_downloaded.items():
                await db.execute(
                    _sa_update(CreativeAsset)
                    .where(
                        CreativeAsset.platform_connection_id == connection.id,
                        CreativeAsset.ad_id == ad_id,
                        or_(CreativeAsset.asset_url.is_(None), CreativeAsset.asset_url == ""),
                    )
                    .values(asset_url=served_url)
                )

            for ad_id, thumb_url in thumb_results.items():
                await db.execute(
                    _sa_update(CreativeAsset)
                    .where(
                        CreativeAsset.platform_connection_id == connection.id,
                        CreativeAsset.ad_id == ad_id,
                        or_(
                            CreativeAsset.thumbnail_url.is_(None),
                            CreativeAsset.thumbnail_url == "",
                            CreativeAsset.thumbnail_url.like("%img.youtube.com%"),
                            CreativeAsset.thumbnail_url.like("%ytimg.com%"),
                        ),
                    )
                    .values(thumbnail_url=thumb_url)
                )

            updated_ids_result = await db.execute(
                select(CreativeAsset.id)
                .where(
                    CreativeAsset.platform_connection_id == connection.id,
                    CreativeAsset.ad_id.in_(list(all_downloaded.keys())),
                )
            )
            updated_ids = [row[0] for row in updated_ids_result.all()]

            if updated_ids:
                await db.execute(
                    _sa_update(AIInferenceTracking)
                    .where(
                        AIInferenceTracking.asset_id.in_(updated_ids),
                        AIInferenceTracking.ai_inference_status.in_(["COMPLETE", "FAILED"]),
                    )
                    .values(ai_inference_status="FAILED", updated_at=_dt.utcnow())
                )

            await db.commit()
            logger.info(f"  CreativeAsset URLs propagated and autofill reset for {len(updated_ids)} assets")

        if video_failures and not video_results:
            raise Exception(
                f"{len(video_failures)} DV360 video download(s) failed: "
                + "; ".join(f"{k}: {v}" for k, v in list(video_failures.items())[:3])
                + ("..." if len(video_failures) > 3 else "")
            )

        downloaded_list = (
            [{"asset_id": ad_id, "url": r["asset_url"]} for ad_id, r in video_results.items() if r.get("asset_url")]
            + [{"asset_id": ad_id, "url": url} for ad_id, url in thumb_results.items() if ad_id not in video_results]
        )
        failed_list = [{"asset_id": ad_id, "error": err} for ad_id, err in video_failures.items()]
        return {
            "downloaded": downloaded_list,
            "failed": failed_list,
            "stats": {"succeeded": _succeeded_count[0], "failed": _failed_count[0]},
        }

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

        first_row = records[0]
        csv_columns = list(first_row.keys())
        logger.info(f"DV360 conv CSV columns ({len(csv_columns)}): {csv_columns}")

        def safe_float(val, default=None):
            try:
                return float(val) if val else default
            except (ValueError, TypeError):
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
            csv_yt_video_id = (
                r.get("Video ID", "").strip()
                or r.get("YouTube Ad Video ID", "").strip()
            )

            if not csv_yt_video_id and entity_maps:
                li_videos = entity_maps.line_item_videos.get(str(csv_li_id))
                if li_videos and len(li_videos) > 0:
                    csv_yt_video_id = li_videos[0].get("youtube_video_id", "")

            parsed_date = r.get("_parsed_date")
            ad_id = csv_li_id

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
