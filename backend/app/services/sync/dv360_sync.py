"""
DV360 data sync service.
Uses Bid Manager API v2 for reporting — create query, run, poll for completion, download CSV results.
"""
import httpx
import csv
import io
import logging
import asyncio
from datetime import date, timedelta, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import Dv360RawPerformance
from app.core.security import decrypt_token
from app.services.platform.dv360_oauth import dv360_oauth

logger = logging.getLogger(__name__)

BID_MANAGER_API_BASE = "https://doubleclickbidmanager.googleapis.com/v2"


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

        total_fetched = 0
        total_upserted = 0

        chunk_start = date_from
        while chunk_start <= date_to:
            chunk_end = min(chunk_start + timedelta(days=29), date_to)
            records = await self._run_report(
                access_token, advertiser_id, chunk_start, chunk_end
            )
            upserted = await self._upsert_records(db, connection, records, sync_job_id)
            total_fetched += len(records)
            total_upserted += upserted
            chunk_start = chunk_end + timedelta(days=1)

        return {"fetched": total_fetched, "upserted": total_upserted}

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

    async def _run_report(
        self,
        access_token: str,
        advertiser_id: str,
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        """Create and run a Bid Manager report query, then download CSV results."""
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
                    "FILTER_INSERTION_ORDER",
                    "FILTER_LINE_ITEM",
                    "FILTER_CREATIVE_ID",
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
                logger.error(f"DV360 create query failed ({create_resp.status_code}): {create_resp.text[:500]}")
                return []

            query_data = create_resp.json()
            query_id = query_data.get("queryId")
            if not query_id:
                logger.error(f"DV360 no queryId returned: {query_data}")
                return []

            run_resp = await client.post(
                f"{BID_MANAGER_API_BASE}/queries/{query_id}:run",
                headers=headers,
                json={},
            )
            if run_resp.status_code != 200:
                logger.error(f"DV360 run query failed ({run_resp.status_code}): {run_resp.text[:500]}")
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
                        logger.error(f"DV360 report failed: {status}")
                        return []

            if not report_url:
                logger.error(f"DV360 report timed out for advertiser {advertiser_id}")
                return []

            csv_resp = await client.get(
                report_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if csv_resp.status_code != 200:
                logger.error(f"DV360 CSV download failed ({csv_resp.status_code})")
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
        """Parse Bid Manager CSV report output into records."""
        records = []
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            if not row.get("Date"):
                continue
            records.append(row)
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

            spend = safe_decimal(r.get("Revenue (Adv Currency)") or r.get("Total Media Cost (Advertiser Currency)"))
            impressions = safe_int(r.get("Impressions"))
            clicks = safe_int(r.get("Clicks"))
            total_conversions = safe_float(r.get("Total Conversions"))
            conversion_value = safe_decimal(r.get("Revenue (Adv Currency)"))
            roas_val = float(conversion_value / spend) if spend and conversion_value and spend > 0 else None

            creative_id = r.get("Creative ID") or r.get("Creative") or ""
            ad_id = creative_id if creative_id else f"{r.get('Line Item ID', '')}_{r.get('Date', '')}"

            rows.append({
                "platform_connection_id": connection.id,
                "sync_job_id": sync_job_id,
                "report_date": r.get("Date"),
                "ad_account_id": connection.ad_account_id,
                "advertiser_id": r.get("Advertiser ID") or r.get("Advertiser"),
                "advertiser_name": r.get("Advertiser"),
                "campaign_id": r.get("Campaign ID") or r.get("Insertion Order ID"),
                "campaign_name": r.get("Campaign") or r.get("Insertion Order"),
                "insertion_order_id": r.get("Insertion Order ID"),
                "insertion_order_name": r.get("Insertion Order"),
                "line_item_id": r.get("Line Item ID"),
                "line_item_name": r.get("Line Item"),
                "creative_id": creative_id,
                "ad_id": ad_id,
                "ad_name": r.get("Creative") or r.get("Line Item"),
                "currency": connection.currency,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "ctr": safe_float(r.get("CTR")),
                "cpm": safe_decimal(r.get("Media Cost eCPM (Advertiser Currency)") or r.get("CPM (Advertiser Currency)")),
                "cpc": safe_decimal(r.get("Media Cost eCPC (Advertiser Currency)") or r.get("CPC (Advertiser Currency)")),
                "total_media_cost": safe_decimal(r.get("Total Media Cost (Advertiser Currency)")),
                "total_conversions": total_conversions,
                "post_click_conversions": safe_float(r.get("Post-Click Conversions") or r.get("Post-Click Conversions")),
                "post_view_conversions": safe_float(r.get("Post-View Conversions") or r.get("Post-View Conversions")),
                "conversion_value": conversion_value,
                "roas": roas_val,
                "trueview_views": safe_int(r.get("TrueView Views")),
                "video_completions": safe_int(r.get("Complete Views (Video)") or r.get("Video Completions")),
                "video_first_quartile": safe_int(r.get("First-Quartile Views (Video)") or r.get("Video First Quartile Views")),
                "video_midpoint": safe_int(r.get("Midpoint Views (Video)") or r.get("Video Midpoint Views")),
                "video_third_quartile": safe_int(r.get("Third-Quartile Views (Video)") or r.get("Video Third Quartile Views")),
                "video_completion_rate": safe_float(r.get("Completion Rate (Video)") or r.get("Video Completion Rate")),
                "video_plays": safe_int(r.get("Starts (Video)") or r.get("Rich Media Video Plays")),
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

        stmt = pg_insert(Dv360RawPerformance).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_dv360_daily_ad",
            set_={
                "spend": stmt.excluded.spend,
                "impressions": stmt.excluded.impressions,
                "clicks": stmt.excluded.clicks,
                "total_conversions": stmt.excluded.total_conversions,
                "roas": stmt.excluded.roas,
                "video_completions": stmt.excluded.video_completions,
                "is_processed": False,
            }
        )
        await db.execute(stmt)
        return len(rows)


dv360_sync = DV360SyncService()
