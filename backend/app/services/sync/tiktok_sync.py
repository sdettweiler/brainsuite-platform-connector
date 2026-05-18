import asyncio
import httpx
import logging
import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any
from sqlalchemy.exc import SQLAlchemyError
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
    "result",
    "result_rate",
    "cost_per_result",
    "gross_impressions",
    "secondary_goal_result",
    "cost_per_secondary_goal_result",
    "secondary_goal_result_rate",
    "interactive_add_on_impression",
    "interactive_add_on_destination_click",
    "real_time_conversion_rate",
    "app_install",
    "cost_per_app_install",
    "registration",
    "cost_per_registration",
    "complete_payment",
    "value_per_complete_payment",
    "cost_per_complete_payment",
    "total_complete_payment_rate",
    "total_pageview",
    "onsite_shopping",
    "total_onsite_shopping_value",
    "onsite_form",
    "cost_per_onsite_form",
    "live_views",
    "live_unique_viewed",
    "live_product_clicks",
    "total_live_shopping_amount",
    "subscribe_amount",
    "average_frequency_7_day",
    "cta_conversion",
    "vta_conversion",
    "cta_purchase",
    "vta_purchase",
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
    "campaign_budget_mode",
    "operation_status",
    "is_comment_disable",
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

        # Ad creative enrichment (thumbnails) deferred to post-commit task to release DB session.

        logger.info(f"TikTok sync complete: fetched={total_fetched}, upserted={total_upserted}")
        return {"fetched": total_fetched, "upserted": total_upserted, "_creative_ad_ids": list(all_ad_ids) if all_ad_ids else []}

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
        except (ValueError, InvalidOperation):
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
                "gross_impression": self._safe_int(m.get("gross_impressions")),
                "gross_reach": None,
                "avg_7_day_frequency": self._safe_float(m.get("average_frequency_7_day")),
                "profile_visits": self._safe_int(m.get("profile_visits")),
                "profile_visits_rate": self._safe_float(m.get("profile_visits_rate")),
                "total_likes": self._safe_int(m.get("likes")),
                "total_comments": self._safe_int(m.get("comments")),
                "total_shares": self._safe_int(m.get("shares")),
                "total_follows": self._safe_int(m.get("follows")),
                "engagement_rate": self._safe_float(m.get("engagement_rate")),
                "total_interactive_add_on_clicks": self._safe_int(m.get("interactive_add_on_destination_click")),
                "total_interactive_add_on_impressions": self._safe_int(m.get("interactive_add_on_impression")),
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
                "real_time_conversion_rate": self._safe_float(m.get("real_time_conversion_rate")),
                "cta_conversions": self._safe_int(m.get("cta_conversion")),
                "vta_conversions": self._safe_int(m.get("vta_conversion")),
                "cta_purchase": self._safe_int(m.get("cta_purchase")),
                "vta_purchase": self._safe_int(m.get("vta_purchase")),
                "app_install": self._safe_int(m.get("app_install")),
                "cost_per_app_install": self._safe_decimal(m.get("cost_per_app_install")),
                "unique_app_install": None,
                "app_event_purchase": None,
                "app_event_purchase_value": None,
                "cost_per_purchase": None,
                "app_event_generate_lead": self._safe_int(m.get("registration")),
                "cost_per_lead": self._safe_decimal(m.get("cost_per_registration")),
                "page_event_complete_payment": self._safe_int(m.get("complete_payment")),
                "page_event_complete_payment_value": self._safe_decimal(m.get("value_per_complete_payment")),
                "page_event_complete_payment_roas": self._safe_float(m.get("total_complete_payment_rate")),
                "cost_per_page_event_complete_payment": self._safe_decimal(m.get("cost_per_complete_payment")),
                "page_event_subscribe": self._safe_int(m.get("subscribe_amount")),
                "page_event_view_content": self._safe_int(m.get("total_pageview")),
                "onsite_form_submit": self._safe_int(m.get("onsite_form")),
                "cost_per_onsite_form_submit": self._safe_decimal(m.get("cost_per_onsite_form")),
                "onsite_purchase": self._safe_int(m.get("onsite_shopping")),
                "onsite_purchase_value": self._safe_decimal(m.get("total_onsite_shopping_value")),
                "live_views": self._safe_int(m.get("live_views")),
                "live_unique_views": self._safe_int(m.get("live_unique_viewed")),
                "live_product_clicks": self._safe_int(m.get("live_product_clicks")),
                "live_add_to_cart": None,
                "live_purchase": None,
                "live_purchase_value": self._safe_decimal(m.get("total_live_shopping_amount")),
                "secondary_goal_result": self._safe_int(m.get("secondary_goal_result")),
                "cost_per_secondary_goal_result": self._safe_decimal(m.get("cost_per_secondary_goal_result")),
                "secondary_goal_result_rate": self._safe_float(m.get("secondary_goal_result_rate")),
                "is_validated": True,
                "is_processed": False,
            })

        stmt = pg_insert(TikTokRawPerformance).values(rows)
        update_cols = {c.name: getattr(stmt.excluded, c.name)
                       for c in TikTokRawPerformance.__table__.columns
                       if c.name not in ("id", "platform_connection_id", "report_date",
                                         "ad_id", "ad_account_id", "retrieved_at",
                                         # populated by deferred enrich_from_ad_get — preserve on re-sync
                                         "campaign_id", "campaign_name", "ad_group_id", "ad_group_name",
                                         "ad_name", "campaign_objective", "ad_status", "ad_format",
                                         "creative_type", "is_spark_ad", "identity_type", "display_name",
                                         "landing_page_url", "video_id", "image_ids", "optimization_goal",
                                         "billing_event", "buying_type", "campaign_budget_mode",
                                         "campaign_status", "call_to_action", "post_link", "thumbnail_url",
                                         # populated by deferred _enrich_from_ad_get — preserve on re-sync
                                         "asset_url", "video_source_url")}
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
        org_id = str(connection.organization_id)
        batch_size = 100
        for i in range(0, len(ad_ids), batch_size):
            batch = ad_ids[i:i + batch_size]
            try:
                ads = await self._fetch_ad_info(access_token, advertiser_id, batch)
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.error("Failed to fetch ad info batch for %s: %s", advertiser_id, e, exc_info=True)
                continue

            for ad in ads:
                ad_id = str(ad.get("ad_id", ""))
                if not ad_id:
                    continue

                image_ids_raw = ad.get("image_ids")
                image_ids_str = ",".join(image_ids_raw) if isinstance(image_ids_raw, list) else None

                ad_format = ad.get("ad_format")
                creative_type = ad.get("creative_type")
                is_spark = ad.get("identity_type") == "AUTH_CODE"

                display_name = ad.get("display_name")
                video_id_val = ad.get("video_id")
                post_link = f"https://www.tiktok.com/@{display_name}/video/{video_id_val}" if display_name and video_id_val else None

                thumbnail_url: Optional[str] = None
                _thumb_image_ids = (
                    image_ids_raw if isinstance(image_ids_raw, list)
                    else (image_ids_raw.split(",") if image_ids_raw else [])
                )
                if _thumb_image_ids:
                    cover_url = await self._fetch_cover_image_url(access_token, advertiser_id, _thumb_image_ids[:1])
                    if cover_url:
                        thumbnail_url = await self._download_tiktok_thumbnail(cover_url, org_id, ad_id)

                # --- Download full-resolution video or image asset (D-01, D-03, D-04, D-06) ---
                asset_url: Optional[str] = None
                video_source_url: Optional[str] = None

                asset_video_duration: Optional[float] = None
                try:
                    if video_id_val and not is_spark:
                        # Standard video ad: fetch download URL then download bytes to S3
                        raw_video_url = await self._fetch_video_download_url(
                            access_token, advertiser_id, [str(video_id_val)]
                        )
                        if raw_video_url:
                            asset_url, asset_video_duration = await self._download_video_asset(raw_video_url, org_id, ad_id)
                            video_source_url = raw_video_url  # Store API URL per D-06

                    elif image_ids_raw and not video_id_val and not is_spark:
                        # Image-only ad: download full-resolution image to asset_url (D-03)
                        # Parse image_ids as list or comma-separated string (Pitfall 4 handling)
                        image_ids_list = (
                            image_ids_raw if isinstance(image_ids_raw, list)
                            else (image_ids_raw.split(",") if image_ids_raw else [])
                        )
                        if image_ids_list:
                            image_url = await self._fetch_cover_image_url(
                                access_token, advertiser_id, image_ids_list[:1]
                            )
                            if image_url:
                                asset_url = await self._download_image_asset(image_url, org_id, ad_id)

                    # Spark ads (is_spark=True): skip download per D-02 (leave asset_url=None)

                except Exception as e:
                    logger.warning("Asset download failed for ad %s (non-fatal, sync continues): %s", ad_id, e, exc_info=True)
                    asset_url = None
                    video_source_url = None
                # --- END asset download ---

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
                        display_name=display_name,
                        landing_page_url=ad.get("landing_page_url"),
                        video_id=str(video_id_val) if video_id_val else None,
                        image_ids=image_ids_str,
                        optimization_goal=ad.get("optimization_goal"),
                        billing_event=ad.get("billing_event"),
                        buying_type=ad.get("buying_type"),
                        campaign_budget_mode=ad.get("campaign_budget_mode"),
                        campaign_status=ad.get("operation_status"),
                        call_to_action=ad.get("call_to_action"),
                        post_link=post_link,
                        **({"thumbnail_url": thumbnail_url} if thumbnail_url else {}),
                        **({"asset_url": asset_url} if asset_url else {}),
                        **({"video_source_url": video_source_url} if video_source_url else {}),
                    )
                )

                # Populate video_duration on CreativeAsset inline — no separate backfill needed.
                if asset_video_duration is not None:
                    from app.models.creative import CreativeAsset
                    await db.execute(
                        update(CreativeAsset).where(
                            CreativeAsset.organization_id == connection.organization_id,
                            CreativeAsset.platform == "TIKTOK",
                            CreativeAsset.ad_id == ad_id,
                            CreativeAsset.video_duration.is_(None),
                        ).values(video_duration=asset_video_duration)
                    )

            await db.flush()
            logger.info(f"  Enriched {len(batch)} ads from /ad/get/")

        await db.commit()

    async def enrich_creatives_deferred(
        self,
        connection_id,
        ad_ids: List[str],
    ) -> None:
        """Post-commit creative enrichment: opens own DB session so it doesn't hold the sync session."""
        from app.db.base import get_session_factory
        from app.models.platform import PlatformConnection
        from sqlalchemy import select
        import uuid
        try:
            async with get_session_factory()() as db:
                conn = (await db.execute(
                    select(PlatformConnection).where(
                        PlatformConnection.id == (connection_id if isinstance(connection_id, uuid.UUID) else uuid.UUID(str(connection_id)))
                    )
                )).scalar_one_or_none()
                if not conn:
                    return
                from datetime import datetime, timezone
                if conn.token_expiry and conn.token_expiry < datetime.now(timezone.utc):
                    logger.warning("TikTok deferred creative enrichment: access token expired for connection %s — enrichment may fail", connection_id)
                access_token = decrypt_token(conn.access_token_encrypted)
                advertiser_id = conn.ad_account_id
                logger.info(f"TikTok deferred creative enrichment: {len(ad_ids)} ads for {advertiser_id}")
                await self._enrich_from_ad_get(db, conn, access_token, advertiser_id, ad_ids)
        except Exception as e:
            logger.warning("TikTok deferred creative enrichment failed (non-fatal): %s", e)

    async def _fetch_cover_image_url(
        self,
        access_token: str,
        advertiser_id: str,
        image_ids: List[str],
    ) -> Optional[str]:
        """Fetch the cover image download URL for given image IDs via /file/image/ad/."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{TIKTOK_API_BASE}/file/image/ad/",
                    params={
                        "advertiser_id": advertiser_id,
                        "image_ids": json.dumps([str(iid) for iid in image_ids]),
                    },
                    headers={"Access-Token": access_token},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") != 0:
                    logger.warning("TikTok /file/image/ad/ error: %s", data.get("message"))
                    return None
                images = data.get("data", {}).get("list", [])
                if images:
                    return images[0].get("image_url")
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.warning("Failed to fetch TikTok cover image URL: %s", e)
        return None

    async def _fetch_video_download_url(
        self,
        access_token: str,
        advertiser_id: str,
        video_ids: List[str],
    ) -> Optional[str]:
        """Fetch the video download URL for given video ID via /file/video/ad/.
        Returns download URL or None if unavailable (non-fatal).
        Decision D-01: Use TikTok API endpoint, not yt-dlp.
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{TIKTOK_API_BASE}/file/video/ad/",
                    params={
                        "advertiser_id": advertiser_id,
                        "video_ids": json.dumps([str(vid) for vid in video_ids]),
                    },
                    headers={"Access-Token": access_token},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") != 0:
                    logger.warning("TikTok /file/video/ad/ error: %s", data.get("message"))
                    return None
                videos = data.get("data", {}).get("list", [])
                if videos:
                    return videos[0].get("video_url")
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.warning("Failed to fetch TikTok video URL for advertiser %s: %s", advertiser_id, e)
        return None

    async def _download_video_asset(
        self,
        url: str,
        org_id: str,
        ad_id: str,
    ) -> tuple[Optional[str], Optional[float]]:
        """Download a TikTok video from URL, upload to S3/MinIO. Returns (served_url, duration_seconds).
        Storage path: creatives/{org_id}/video_tiktok_{ad_id}.mp4
        Decision D-04: Inline download; failures are non-fatal (log + return None, None).
        Decision D-06: Result stored in asset_url (scoring/autofill input, not thumbnail).
        """
        from app.services.object_storage import get_object_storage
        from app.services.sync.video_utils import probe_duration_from_bytes
        obj_storage = get_object_storage()

        filename = f"video_tiktok_{ad_id}.mp4"
        relative_path = f"creatives/{org_id}/{filename}"

        if obj_storage.file_exists(relative_path):
            return obj_storage.served_url(relative_path), None

        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            served_url = obj_storage.upload_bytes(resp.content, relative_path, content_type="video/mp4")
            duration = await asyncio.to_thread(probe_duration_from_bytes, resp.content, ".mp4")
            logger.info("Downloaded TikTok video for ad %s: %s (%d bytes, duration=%s)", ad_id, filename, len(resp.content), duration)
            return served_url, duration
        except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
            logger.warning("Failed to download TikTok video for ad %s: %s", ad_id, e, exc_info=True)
            return None, None

    async def _download_image_asset(
        self,
        image_url: str,
        org_id: str,
        ad_id: str,
    ) -> Optional[str]:
        """Download a TikTok full-resolution image and upload to S3/MinIO. Returns served URL or None.
        Storage path: creatives/{org_id}/image_tiktok_{ad_id}.jpg
        Decision D-03: Full-resolution image for scoring/autofill input; separate from thumbnail_url.
        Decision D-04: Failures are non-fatal (log + return None).
        """
        from app.services.object_storage import get_object_storage
        obj_storage = get_object_storage()

        filename = f"image_tiktok_{ad_id}.jpg"
        relative_path = f"creatives/{org_id}/{filename}"

        if obj_storage.file_exists(relative_path):
            return obj_storage.served_url(relative_path)

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
            if len(resp.content) < 100:
                logger.warning("TikTok image for ad %s too small (%d bytes), skipping", ad_id, len(resp.content))
                return None
            served_url = obj_storage.upload_bytes(resp.content, relative_path, content_type="image/jpeg")
            logger.info("Downloaded TikTok image for ad %s: %s (%d bytes)", ad_id, filename, len(resp.content))
            return served_url
        except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
            logger.warning("Failed to download TikTok image for ad %s: %s", ad_id, e, exc_info=True)
            return None

    async def _download_tiktok_thumbnail(
        self,
        image_url: str,
        org_id: str,
        ad_id: str,
    ) -> Optional[str]:
        """Download a TikTok cover image and upload to GCS. Returns served URL or None."""
        from app.services.object_storage import get_object_storage
        obj_storage = get_object_storage()

        filename = f"thumb_tiktok_{ad_id}.jpg"
        relative_path = f"creatives/{org_id}/{filename}"

        if obj_storage.file_exists(relative_path):
            return obj_storage.served_url(relative_path)

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
            if len(resp.content) < 100:
                logger.warning("TikTok thumbnail for ad %s too small (%d bytes), skipping", ad_id, len(resp.content))
                return None
            served_url = obj_storage.upload_bytes(resp.content, relative_path, content_type="image/jpeg")
            logger.info("Downloaded TikTok thumbnail for ad %s: %s (%d bytes)", ad_id, filename, len(resp.content))
            return served_url
        except (httpx.RequestError, httpx.HTTPStatusError, OSError) as e:
            logger.warning("Failed to download TikTok thumbnail for ad %s: %s", ad_id, e, exc_info=True)
            return None

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
