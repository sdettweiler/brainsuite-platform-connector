"""
DV360 data sync service.

Dual-API architecture:
- Display & Video 360 API v4 (displayvideo.googleapis.com/v4):
  Entity metadata — campaigns, insertion orders, line items, creatives.
  Provides names, types, statuses, and creative asset details.
- Bid Manager API v2 (doubleclickbidmanager.googleapis.com/v2):
  Reporting — create query, run, poll for completion, download CSV results.
  Provides performance metrics (impressions, clicks, spend, conversions, video).

The sync flow:
1. Fetch entity metadata maps from DV360 API v4 (campaigns, IOs, line items, creatives)
2. Create + run a Bid Manager report query for the date range
3. Parse CSV results and enrich records with v4 metadata (creative thumbnails/assets)
4. Download creative assets (images via httpx, videos via yt-dlp)
5. Upsert enriched records into dv360_raw_performance
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


class EntityMaps(NamedTuple):
    campaigns: Dict[str, Dict[str, Any]]
    insertion_orders: Dict[str, Dict[str, Any]]
    line_items: Dict[str, Dict[str, Any]]
    creatives: Dict[str, Dict[str, Any]]


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

        records = await self._run_report(
            access_token, advertiser_id, date_from, date_to
        )
        upserted = await self._upsert_records(db, connection, records, sync_job_id, entity_maps)

        return {"fetched": len(records), "upserted": upserted}

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

        async with httpx.AsyncClient(timeout=60) as client:
            campaign_task = self._fetch_campaigns(client, headers, advertiser_id)
            io_task = self._fetch_insertion_orders(client, headers, advertiser_id)
            li_task = self._fetch_line_items(client, headers, advertiser_id)
            creative_task = self._fetch_creatives(client, headers, advertiser_id)

            results = await asyncio.gather(
                campaign_task, io_task, li_task, creative_task,
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

        logger.info(
            f"DV360 v4 metadata for advertiser {advertiser_id}: "
            f"{len(campaigns)} campaigns, {len(insertion_orders)} IOs, "
            f"{len(line_items)} line items, {len(creatives)} creatives"
        )

        return EntityMaps(
            campaigns=campaigns,
            insertion_orders=insertion_orders,
            line_items=line_items,
            creatives=creatives,
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
                    ios[str(io_id)] = {
                        "name": io_item.get("displayName", ""),
                        "status": io_item.get("entityStatus", ""),
                        "campaign_id": str(io_item.get("campaignId", "")),
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

    async def _run_report(
        self,
        access_token: str,
        advertiser_id: str,
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        """Create and run a Bid Manager v2 report query, then download CSV results."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        query_body = {
            "metadata": {
                "title": f"brainsuite_dv360_{advertiser_id}_{date_from}_{date_to}",
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
                "type": "STANDARD",
                "groupBys": [
                    "FILTER_DATE",
                    "FILTER_ADVERTISER",
                    "FILTER_ADVERTISER_NAME",
                    "FILTER_ADVERTISER_CURRENCY",
                    "FILTER_ADVERTISER_TIMEZONE",
                    "FILTER_AD_POSITION",
                    "FILTER_AD_TYPE",
                    "FILTER_INSERTION_ORDER",
                    "FILTER_INSERTION_ORDER_GOAL_TYPE",
                    "FILTER_LINE_ITEM",
                    "FILTER_LINE_ITEM_TYPE",
                    "FILTER_CREATIVE_ID",
                    "FILTER_CREATIVE_TYPE",
                    "FILTER_CREATIVE_SOURCE",
                    "FILTER_CHANNEL_ID",
                    "FILTER_CHANNEL_TYPE",
                    "FILTER_CHANNEL_NAME",
                    "FILTER_YOUTUBE_AD_VIDEO_ID",
                    "FILTER_MEDIA_PLAN",
                    "FILTER_MEDIA_PLAN_NAME",
                    "FILTER_MEDIA_TYPE",
                ],
                "metrics": [
                    "METRIC_IMPRESSIONS",
                    "METRIC_CLICKS",
                    "METRIC_CTR",
                    "METRIC_TOTAL_MEDIA_COST_ADVERTISER",
                    "METRIC_MEDIA_COST_ECPM_ADVERTISER",
                    "METRIC_MEDIA_COST_ECPC_ADVERTISER",
                    "METRIC_TOTAL_CONVERSIONS",
                    "METRIC_LAST_CLICKS",
                    "METRIC_LAST_IMPRESSIONS",
                    "METRIC_REVENUE_ADVERTISER",
                    "METRIC_TRUEVIEW_VIEWS",
                    "METRIC_RICH_MEDIA_VIDEO_COMPLETIONS",
                    "METRIC_RICH_MEDIA_VIDEO_FIRST_QUARTILE_COMPLETES",
                    "METRIC_RICH_MEDIA_VIDEO_MIDPOINTS",
                    "METRIC_RICH_MEDIA_VIDEO_THIRD_QUARTILE_COMPLETES",
                    "METRIC_VIDEO_COMPLETION_RATE",
                    "METRIC_ACTIVE_VIEW_VIEWABLE_IMPRESSIONS",
                    "METRIC_ACTIVE_VIEW_MEASURABLE_IMPRESSIONS",
                    "METRIC_ACTIVE_VIEW_PCT_VIEWABLE_IMPRESSIONS",
                    "METRIC_ENGAGEMENTS",
                    "METRIC_ENGAGEMENT_RATE",
                    "METRIC_RICH_MEDIA_VIDEO_PLAYS",
                    "METRIC_BILLABLE_COST_ADVERTISER",
                    "METRIC_BILLABLE_IMPRESSIONS",
                    "METRIC_AVERAGE_IMPRESSION_FREQUENCY_PER_USER",
                    "METRIC_TRUEVIEW_VIEW_RATE",
                    "METRIC_COST_PER_ACTION_ADVERTISER",
                ],
                "filters": [
                    {
                        "type": "FILTER_ADVERTISER",
                        "value": advertiser_id,
                    }
                ],
            },
        }

        records = []

        async with httpx.AsyncClient(timeout=120) as client:
            create_resp = await client.post(
                f"{BID_MANAGER_API_BASE}/queries",
                headers=headers,
                json=query_body,
            )
            if create_resp.status_code != 200:
                logger.error(f"Bid Manager v2: Create query failed ({create_resp.status_code}): {create_resp.text[:500]}")
                return []

            query_data = create_resp.json()
            query_id = query_data.get("queryId")
            if not query_id:
                logger.error(f"Bid Manager v2: No queryId returned: {query_data}")
                return []

            run_resp = await client.post(
                f"{BID_MANAGER_API_BASE}/queries/{query_id}:run",
                headers=headers,
                json={},
            )
            if run_resp.status_code != 200:
                logger.error(f"Bid Manager v2: Run query failed ({run_resp.status_code}): {run_resp.text[:500]}")
                return []

            report_url = None
            for attempt in range(30):
                await asyncio.sleep(10)
                status_resp = await client.get(
                    f"{BID_MANAGER_API_BASE}/queries/{query_id}/reports",
                    headers=headers,
                )
                if status_resp.status_code != 200:
                    continue

                reports = status_resp.json().get("reports", [])
                if reports:
                    latest = reports[0]
                    metadata = latest.get("metadata", {})
                    status = metadata.get("status", {})
                    if status.get("state") == "DONE":
                        report_url = metadata.get("googleCloudStoragePath")
                        break
                    elif status.get("state") == "FAILED":
                        logger.error(f"Bid Manager v2: Report failed: {status}")
                        return []

            if not report_url:
                logger.error(f"Bid Manager v2: Report timed out for advertiser {advertiser_id}")
                return []

            csv_resp = await client.get(
                report_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if csv_resp.status_code != 200:
                logger.error(f"Bid Manager v2: CSV download failed ({csv_resp.status_code})")
                return []

            records = self._parse_csv(csv_resp.text)

            try:
                await client.delete(
                    f"{BID_MANAGER_API_BASE}/queries/{query_id}",
                    headers=headers,
                )
            except Exception:
                pass

        return records

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
        for r in records:
            spend = safe_decimal(r.get("Revenue (Adv Currency)") or r.get("Total Media Cost (Advertiser Currency)"))
            impressions = safe_int(r.get("Impressions"))
            clicks = safe_int(r.get("Clicks"))
            total_conversions = safe_float(r.get("Total Conversions"))
            conversion_value = safe_decimal(r.get("Revenue (Adv Currency)"))
            roas_val = float(conversion_value / spend) if spend and conversion_value and spend > 0 else None

            csv_creative_id = r.get("Creative ID") or ""
            csv_io_id = r.get("Insertion Order ID") or ""
            csv_li_id = r.get("Line Item ID") or ""
            csv_advertiser_id = r.get("Advertiser ID") or ""

            csv_campaign_id = r.get("Campaign ID") or ""
            csv_campaign_name = r.get("Campaign") or ""
            csv_li_type = r.get("Line Item Type") or ""
            csv_creative_type = r.get("Creative Type") or ""
            csv_creative_source = r.get("Creative Source") or ""
            csv_ad_type = r.get("Ad Type") or ""
            csv_yt_video_id = r.get("YouTube Ad Video ID") or ""

            parsed_date = r.get("_parsed_date")
            if csv_creative_id and csv_li_id:
                ad_id = f"{csv_li_id}_{csv_creative_id}"
            elif csv_creative_id:
                ad_id = csv_creative_id
            else:
                ad_id = f"{csv_li_id}_{parsed_date.isoformat() if parsed_date else ''}"

            campaign_id = csv_campaign_id
            campaign_name = csv_campaign_name
            io_name = r.get("Insertion Order") or ""
            li_name = r.get("Line Item") or ""
            li_type = csv_li_type
            creative_name = r.get("Creative") or ""
            creative_type = csv_creative_type
            creative_source = csv_creative_source
            thumbnail_url = ""
            asset_url = ""
            video_url = ""
            video_duration = None
            asset_format = ""

            if entity_maps:
                if not campaign_id:
                    io_meta = entity_maps.insertion_orders.get(str(csv_io_id))
                    if io_meta:
                        campaign_id = io_meta.get("campaign_id", "")
                    if not campaign_id:
                        li_meta = entity_maps.line_items.get(str(csv_li_id))
                        if li_meta and li_meta.get("campaign_id"):
                            campaign_id = li_meta.get("campaign_id", "")

                if campaign_id and not campaign_name:
                    c_meta = entity_maps.campaigns.get(campaign_id)
                    if c_meta:
                        campaign_name = c_meta.get("name", "")

                cr_meta = entity_maps.creatives.get(str(csv_creative_id))
                if cr_meta:
                    if not creative_name:
                        creative_name = cr_meta.get("name", "")
                    thumbnail_url = cr_meta.get("thumbnail_url", "")
                    asset_format = cr_meta.get("asset_format", "")

            if not campaign_name and campaign_id:
                campaign_name = f"Campaign {campaign_id}"

            if org_dir and org_id and csv_yt_video_id:
                try:
                    vid_path, vid_served = await self._download_video_asset(
                        csv_yt_video_id, org_dir, org_id, ad_id
                    )
                    if vid_served:
                        video_url = vid_served
                        asset_url = vid_served
                        video_duration = self._get_video_duration(vid_path)
                    thumb_path, thumb_served = await self._download_youtube_thumbnail(
                        csv_yt_video_id, org_dir, org_id, ad_id
                    )
                    if thumb_served:
                        thumbnail_url = thumb_served
                except Exception as e:
                    logger.warning(f"  Asset download failed for DV360 ad {ad_id}: {e}")
            elif org_dir and org_id and thumbnail_url and thumbnail_url.startswith("http"):
                try:
                    _, img_served = await self._download_image_asset(
                        thumbnail_url, org_dir, org_id, ad_id
                    )
                    if img_served:
                        asset_url = img_served
                        thumbnail_url = img_served
                except Exception as e:
                    logger.warning(f"  Image download failed for DV360 ad {ad_id}: {e}")

            avg_freq = safe_float(r.get("Average Impression Frequency per User"))

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
                "line_item_type": li_type,
                "creative_id": csv_creative_id,
                "creative_name": creative_name,
                "creative_type": creative_type,
                "creative_source": creative_source,
                "ad_id": ad_id,
                "ad_name": creative_name or li_name,
                "ad_type": csv_ad_type,
                "ad_position": r.get("Ad Position") or "",
                "advertiser_timezone": r.get("Advertiser Time Zone") or "",
                "channel_id": r.get("Channel ID") or "",
                "channel_type": r.get("Channel Type") or "",
                "channel_name": r.get("Channel") or "",
                "io_goal_type": r.get("Insertion Order Goal Type") or "",
                "youtube_ad_video_id": csv_yt_video_id,
                "media_type": r.get("Media Type") or "",
                "thumbnail_url": thumbnail_url,
                "asset_url": asset_url,
                "video_url": video_url,
                "video_duration_seconds": video_duration,
                "asset_format": asset_format,
                "currency": r.get("Advertiser Currency") or connection.currency,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "ctr": safe_float(r.get("CTR")),
                "cpm": safe_decimal(r.get("Media Cost eCPM (Advertiser Currency)")),
                "cpc": safe_decimal(r.get("Media Cost eCPC (Advertiser Currency)")),
                "total_media_cost": safe_decimal(r.get("Total Media Cost (Advertiser Currency)")),
                "billable_cost": safe_decimal(r.get("Billable Cost (Advertiser Currency)")),
                "billable_impressions": safe_int(r.get("Billable Impressions")),
                "average_impression_frequency": avg_freq,
                "frequency": avg_freq,
                "total_conversions": total_conversions,
                "post_click_conversions": safe_float(r.get("Post-Click Conversions")),
                "post_view_conversions": safe_float(r.get("Post-View Conversions")),
                "conversion_value": conversion_value,
                "roas": roas_val,
                "cost_per_conversion": safe_decimal(r.get("Cost Per Action (Advertiser Currency)")),
                "trueview_views": safe_int(r.get("TrueView Views")),
                "video_views": safe_int(r.get("TrueView Views")),
                "video_completions": safe_int(r.get("Complete Views (Video)")),
                "video_first_quartile": safe_int(r.get("First-Quartile Views (Video)")),
                "video_midpoint": safe_int(r.get("Midpoint Views (Video)")),
                "video_third_quartile": safe_int(r.get("Third-Quartile Views (Video)")),
                "video_completion_rate": safe_float(r.get("Completion Rate (Video)")),
                "video_view_rate": safe_float(r.get("TrueView View Rate")),
                "video_plays": safe_int(r.get("Starts (Video)")),
                "companion_impressions": safe_int(r.get("Companion Impressions")),
                "companion_clicks": safe_int(r.get("Companion Clicks")),
                "active_view_viewable_impressions": safe_int(r.get("Active View: Viewable Impressions")),
                "active_view_measurable_impressions": safe_int(r.get("Active View: Measurable Impressions")),
                "active_view_viewability": safe_float(r.get("Active View: % Viewable Impressions")),
                "engagements": safe_int(r.get("Engagements")),
                "engagement_rate": safe_float(r.get("Engagement Rate")),
                "is_validated": True,
                "is_processed": False,
            })

        if not rows:
            return 0

        seen_keys = {}
        for row in rows:
            key = (str(row["platform_connection_id"]), str(row["report_date"]), row["ad_id"], row["ad_account_id"])
            seen_keys[key] = row
        rows = list(seen_keys.values())
        logger.info(f"DV360 upsert: {len(rows)} unique rows after dedup")

        if not rows:
            return 0

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
                    "channel_id": stmt.excluded.channel_id,
                    "channel_type": stmt.excluded.channel_type,
                    "channel_name": stmt.excluded.channel_name,
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
                    "total_media_cost": stmt.excluded.total_media_cost,
                    "billable_cost": stmt.excluded.billable_cost,
                    "billable_impressions": stmt.excluded.billable_impressions,
                    "average_impression_frequency": stmt.excluded.average_impression_frequency,
                    "frequency": stmt.excluded.frequency,
                    "total_conversions": stmt.excluded.total_conversions,
                    "cost_per_conversion": stmt.excluded.cost_per_conversion,
                    "roas": stmt.excluded.roas,
                    "video_completions": stmt.excluded.video_completions,
                    "video_view_rate": stmt.excluded.video_view_rate,
                    "companion_impressions": stmt.excluded.companion_impressions,
                    "companion_clicks": stmt.excluded.companion_clicks,
                    "is_processed": False,
                }
            )
            await db.execute(stmt)
            await db.flush()

        return len(rows)


dv360_sync = DV360SyncService()
