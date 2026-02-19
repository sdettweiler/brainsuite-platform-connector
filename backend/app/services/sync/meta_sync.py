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
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "creatives")
)

INSIGHTS_FIELDS = [
    "date_start",
    "date_stop",
    "account_id",
    "campaign_id",
    "campaign_name",
    "objective",
    "buying_type",
    "bid_strategy",
    "adset_id",
    "adset_name",
    "optimization_goal",
    "billing_event",
    "destination_type",
    "ad_id",
    "ad_name",
    "configured_status",
    "effective_status",
    "spend",
    "impressions",
    "reach",
    "frequency",
    "cpm",
    "cpp",
    "clicks",
    "unique_clicks",
    "cpc",
    "ctr",
    "unique_ctr",
    "inline_link_clicks",
    "inline_link_click_ctr",
    "cost_per_inline_link_click",
    "outbound_clicks",
    "outbound_clicks_ctr",
    "cost_per_outbound_click",
    "video_play_actions",
    "video_p25_watched_actions",
    "video_p50_watched_actions",
    "video_p75_watched_actions",
    "video_p95_watched_actions",
    "video_p100_watched_actions",
    "video_30_sec_watched_actions",
    "video_avg_time_watched_actions",
    "video_thruplay_watched_actions",
    "cost_per_thruplay",
    "cost_per_10_sec_video_view",
    "estimated_ad_recallers",
    "estimated_ad_recall_rate",
    "cost_per_estimated_ad_recallers",
    "estimated_ad_recall_lift_in_people",
    "actions",
    "action_values",
    "cost_per_action_type",
    "purchase_roas",
    "page_engagement",
    "post_engagement",
    "post_reactions",
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

        if not all_ad_ids:
            existing = await db.execute(
                select(MetaRawPerformance.ad_id).where(
                    MetaRawPerformance.platform_connection_id == connection.id,
                ).distinct()
            )
            for row in existing:
                all_ad_ids.add(row[0])
            if all_ad_ids:
                logger.info(f"  No new ads, but checking creatives for {len(all_ad_ids)} existing ads")

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

    @staticmethod
    def _extract_action_value(actions: list, action_types: tuple, as_type=int):
        for a in actions:
            if a.get("action_type") in action_types:
                try:
                    return as_type(a["value"])
                except (ValueError, KeyError, TypeError):
                    pass
        return None

    @staticmethod
    def _sum_action_values(actions: list, action_types: tuple, as_type=int):
        total = None
        for a in actions:
            if a.get("action_type") in action_types:
                try:
                    v = as_type(a["value"])
                    total = (total or 0) + v
                except (ValueError, KeyError, TypeError):
                    pass
        return total

    @staticmethod
    def _extract_video_metric(r: dict, field: str) -> Optional[int]:
        vals = r.get(field, [])
        if vals and isinstance(vals, list) and len(vals) > 0:
            try:
                return int(vals[0].get("value", 0))
            except (ValueError, TypeError):
                pass
        return None

    @staticmethod
    def _safe_int(val) -> Optional[int]:
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_decimal(val) -> Optional[Decimal]:
        if val is None:
            return None
        try:
            return Decimal(str(val))
        except Exception:
            return None

    @staticmethod
    def _extract_outbound_clicks(r: dict) -> Optional[int]:
        oc = r.get("outbound_clicks", [])
        if isinstance(oc, list) and len(oc) > 0:
            try:
                return int(oc[0].get("value", 0))
            except (ValueError, TypeError):
                pass
        return None

    @staticmethod
    def _extract_outbound_clicks_ctr(r: dict) -> Optional[float]:
        oc = r.get("outbound_clicks_ctr", [])
        if isinstance(oc, list) and len(oc) > 0:
            try:
                return float(oc[0].get("value", 0))
            except (ValueError, TypeError):
                pass
        return None

    @staticmethod
    def _extract_cost_per_outbound_click(r: dict) -> Optional[Decimal]:
        cpo = r.get("cost_per_outbound_click", [])
        if isinstance(cpo, list) and len(cpo) > 0:
            try:
                return Decimal(str(cpo[0].get("value", 0)))
            except Exception:
                pass
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

        PURCHASE_TYPES = ("purchase", "offsite_conversion.fb_pixel_purchase")
        LEAD_TYPES = ("lead", "offsite_conversion.fb_pixel_lead")
        SUBSCRIBE_TYPES = ("subscribe", "offsite_conversion.fb_pixel_complete_registration")
        CONVERSION_TYPES = PURCHASE_TYPES + LEAD_TYPES + SUBSCRIBE_TYPES

        rows = []
        for r in records:
            actions = r.get("actions") or []
            action_values = r.get("action_values") or []
            cost_per_action = r.get("cost_per_action_type") or []

            conversions = self._sum_action_values(actions, CONVERSION_TYPES, int)
            conversion_value_f = self._sum_action_values(action_values, PURCHASE_TYPES, float)
            conversion_value = Decimal(str(conversion_value_f)) if conversion_value_f else None

            purchase = self._sum_action_values(actions, PURCHASE_TYPES, int)
            purchase_val_f = self._sum_action_values(action_values, PURCHASE_TYPES, float)
            purchase_value = Decimal(str(purchase_val_f)) if purchase_val_f else None
            cost_per_purchase = self._extract_action_value(cost_per_action, PURCHASE_TYPES, lambda v: Decimal(str(v)))
            lead = self._sum_action_values(actions, LEAD_TYPES, int)
            cost_per_lead = self._extract_action_value(cost_per_action, LEAD_TYPES, lambda v: Decimal(str(v)))
            subscribe = self._sum_action_values(actions, SUBSCRIBE_TYPES, int)

            post_engagement = self._extract_action_value(actions, ("post_engagement",), int)
            page_engagement = self._extract_action_value(actions, ("page_engagement",), int)
            reactions = self._safe_int(r.get("post_reactions"))

            video_play_actions = self._extract_video_metric(r, "video_play_actions")
            video_p25 = self._extract_video_metric(r, "video_p25_watched_actions")
            video_p50 = self._extract_video_metric(r, "video_p50_watched_actions")
            video_p75 = self._extract_video_metric(r, "video_p75_watched_actions")
            video_p95 = self._extract_video_metric(r, "video_p95_watched_actions")
            video_p100 = self._extract_video_metric(r, "video_p100_watched_actions")
            video_30_sec = self._extract_video_metric(r, "video_30_sec_watched_actions")
            video_thruplay = self._extract_video_metric(r, "video_thruplay_watched_actions")

            video_avg_time_vals = r.get("video_avg_time_watched_actions", [])
            video_avg_time_ms = None
            if video_avg_time_vals and isinstance(video_avg_time_vals, list) and len(video_avg_time_vals) > 0:
                try:
                    video_avg_time_ms = int(float(video_avg_time_vals[0].get("value", 0)) * 1000)
                except (ValueError, TypeError):
                    pass

            spend = self._safe_decimal(r.get("spend")) or Decimal("0")
            impressions = self._safe_int(r.get("impressions")) or 0
            clicks = self._safe_int(r.get("clicks")) or 0
            cvr = (conversions / clicks) if conversions and clicks else None
            roas_val = (float(conversion_value) / float(spend)) if spend and conversion_value else None
            video_view_rate = (video_play_actions / impressions * 100) if video_play_actions and impressions else None

            purchase_roas_raw = r.get("purchase_roas")
            purchase_roas = None
            if isinstance(purchase_roas_raw, list) and len(purchase_roas_raw) > 0:
                purchase_roas = self._safe_float(purchase_roas_raw[0].get("value"))
            elif purchase_roas_raw is not None:
                purchase_roas = self._safe_float(purchase_roas_raw)

            outbound_clicks = self._extract_outbound_clicks(r)
            outbound_clicks_ctr = self._extract_outbound_clicks_ctr(r)
            cost_per_outbound_click = self._extract_cost_per_outbound_click(r)

            rows.append({
                "platform_connection_id": connection.id,
                "sync_job_id": sync_job_id,
                "report_date": date.fromisoformat(r.get("date_start")),
                "ad_account_id": connection.ad_account_id,
                "campaign_id": r.get("campaign_id"),
                "campaign_name": r.get("campaign_name"),
                "campaign_objective": r.get("objective"),
                "buying_type": r.get("buying_type"),
                "bid_strategy": r.get("bid_strategy"),
                "ad_set_id": r.get("adset_id"),
                "ad_set_name": r.get("adset_name"),
                "optimization_goal": r.get("optimization_goal"),
                "billing_event": r.get("billing_event"),
                "destination_type": r.get("destination_type"),
                "ad_id": r.get("ad_id"),
                "ad_name": r.get("ad_name"),
                "configured_status": r.get("configured_status"),
                "effective_status": r.get("effective_status"),
                "currency": connection.currency,
                "spend": spend,
                "impressions": impressions,
                "reach": self._safe_int(r.get("reach")),
                "frequency": self._safe_float(r.get("frequency")),
                "cpm": self._safe_decimal(r.get("cpm")),
                "cpp": self._safe_decimal(r.get("cpp")),
                "clicks": clicks,
                "unique_clicks": self._safe_int(r.get("unique_clicks")),
                "cpc": self._safe_decimal(r.get("cpc")),
                "ctr": self._safe_float(r.get("ctr")),
                "unique_ctr": self._safe_float(r.get("unique_ctr")),
                "inline_link_clicks": self._safe_int(r.get("inline_link_clicks")),
                "inline_link_click_ctr": self._safe_float(r.get("inline_link_click_ctr")),
                "cost_per_inline_link_click": self._safe_decimal(r.get("cost_per_inline_link_click")),
                "outbound_clicks": outbound_clicks,
                "outbound_clicks_ctr": outbound_clicks_ctr,
                "cost_per_outbound_click": cost_per_outbound_click,
                "video_play_actions": video_play_actions,
                "video_p25_watched": video_p25,
                "video_p50_watched": video_p50,
                "video_p75_watched": video_p75,
                "video_p95_watched": video_p95,
                "video_p100_watched": video_p100,
                "video_30_sec_watched": video_30_sec,
                "video_avg_time_watched_ms": video_avg_time_ms,
                "video_thruplay_watched": video_thruplay,
                "cost_per_thruplay": self._safe_decimal(r.get("cost_per_thruplay")),
                "cost_per_10_sec_video_view": self._safe_decimal(r.get("cost_per_10_sec_video_view")),
                "video_views": video_play_actions,
                "video_view_rate": video_view_rate,
                "estimated_ad_recallers": self._safe_int(r.get("estimated_ad_recallers")),
                "estimated_ad_recall_rate": self._safe_float(r.get("estimated_ad_recall_rate")),
                "cost_per_estimated_ad_recaller": self._safe_decimal(r.get("cost_per_estimated_ad_recallers")),
                "estimated_ad_recall_lift": self._safe_float(r.get("estimated_ad_recall_lift_in_people")),
                "post_engagement": post_engagement,
                "page_engagement": page_engagement,
                "reactions": reactions,
                "conversions": conversions,
                "conversion_value": conversion_value,
                "cvr": cvr,
                "roas": roas_val,
                "purchase": purchase,
                "purchase_value": purchase_value,
                "cost_per_purchase": cost_per_purchase,
                "purchase_roas": purchase_roas,
                "lead": lead,
                "cost_per_lead": cost_per_lead,
                "subscribe": subscribe,
                "is_validated": True,
                "is_processed": False,
            })

        stmt = pg_insert(MetaRawPerformance).values(rows)
        update_cols = {c.name: getattr(stmt.excluded, c.name)
                       for c in MetaRawPerformance.__table__.columns
                       if c.name not in ("id", "platform_connection_id", "report_date",
                                         "ad_id", "ad_account_id", "retrieved_at")}
        update_cols["is_processed"] = False
        stmt = stmt.on_conflict_do_update(
            constraint="uq_meta_daily_ad",
            set_=update_cols,
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
        """Batch-fetch creative details for ads, download full-res assets, update DB records."""
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
                image_hash = creative_data.get("image_hash")
                thumbnail_url = creative_data.get("thumbnail_url")
                video_id = creative_data.get("video_id")
                story_spec = creative_data.get("object_story_spec", {})

                has_video_data = "video_data" in story_spec
                if not video_id and has_video_data:
                    video_id = story_spec.get("video_data", {}).get("video_id")

                is_video = object_type == "VIDEO" or bool(video_id) or has_video_data
                if object_type == "SHARE" and not is_video:
                    is_video = False
                ad_format = "VIDEO" if is_video else "IMAGE"

                logger.info(f"  Ad {ad_id}: object_type={object_type}, creative_id={creative_id}, "
                            f"image_url={'yes' if image_url else 'no'}, "
                            f"image_hash={image_hash or 'none'}, "
                            f"thumbnail_url={'yes' if thumbnail_url else 'no'}, "
                            f"video_id={video_id or 'none'}, format={ad_format}")

                asset_served_url = None
                thumb_served_url = None

                if is_video and video_id:
                    video_info = await self._get_video_info(access_token, video_id)
                    video_source = video_info.get("source") if video_info else None
                    if video_source:
                        _, asset_served_url = await self._download_asset(
                            video_source, org_dir, connection.organization_id, ad_id, "vid"
                        )
                    video_thumbs = video_info.get("thumbnails", {}).get("data", []) if video_info else []
                    if video_thumbs and not thumbnail_url:
                        thumbnail_url = video_thumbs[0].get("uri")

                if not is_video:
                    full_image_url = None
                    resolved_hash = image_hash
                    if not resolved_hash:
                        feed_spec = creative_data.get("asset_feed_spec", {})
                        feed_images = feed_spec.get("images", [])
                        if feed_images:
                            resolved_hash = feed_images[0].get("hash")
                            logger.info(f"  Ad {ad_id}: resolved image_hash from asset_feed_spec: {resolved_hash}")
                        feed_videos = feed_spec.get("videos", [])
                        if feed_videos and not resolved_hash:
                            feed_vid_id = feed_videos[0].get("video_id")
                            if feed_vid_id:
                                is_video = True
                                video_id = feed_vid_id
                                ad_format = "VIDEO"
                                logger.info(f"  Ad {ad_id}: resolved as VIDEO from asset_feed_spec video_id={feed_vid_id}")

                    if not is_video:
                        if resolved_hash:
                            full_image_url = await self._get_full_image_url(access_token, account_id, resolved_hash)
                        if not full_image_url:
                            full_image_url = self._extract_image_url_from_story_spec(story_spec)
                        if not full_image_url:
                            full_image_url = image_url

                        if full_image_url:
                            _, asset_served_url = await self._download_asset(
                                full_image_url, org_dir, connection.organization_id, ad_id, "img"
                            )

                if is_video and video_id and not asset_served_url:
                    video_info = await self._get_video_info(access_token, video_id)
                    video_source = video_info.get("source") if video_info else None
                    if video_source:
                        _, asset_served_url = await self._download_asset(
                            video_source, org_dir, connection.organization_id, ad_id, "vid"
                        )
                    video_thumbs = video_info.get("thumbnails", {}).get("data", []) if video_info else []
                    if video_thumbs and not thumbnail_url:
                        thumbnail_url = video_thumbs[0].get("uri")

                if thumbnail_url:
                    _, thumb_served_url = await self._download_asset(
                        thumbnail_url, org_dir, connection.organization_id, ad_id, "thumb"
                    )

                final_thumb = thumb_served_url or thumbnail_url
                final_asset = asset_served_url

                logger.info(f"  Ad {ad_id}: format={ad_format}, "
                            f"asset={'yes' if final_asset else 'no'}, "
                            f"thumb={'yes' if final_thumb else 'no'}")

                await db.execute(
                    update(MetaRawPerformance)
                    .where(
                        MetaRawPerformance.ad_id == ad_id,
                        MetaRawPerformance.platform_connection_id == connection.id,
                    )
                    .values(
                        creative_id=creative_id,
                        ad_format=ad_format,
                        thumbnail_url=final_thumb,
                        asset_url=final_asset,
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
            "fields": "id,creative{id,thumbnail_url,image_url,image_hash,video_id,object_type,object_story_spec,asset_feed_spec}",
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

    async def _get_video_info(self, access_token: str, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video info including source download URL and thumbnails."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{META_GRAPH_URL}/{video_id}",
                    params={
                        "access_token": access_token,
                        "fields": "id,title,source,thumbnails,length",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info(f"  Video {video_id}: source={'yes' if data.get('source') else 'no'}, "
                                f"length={data.get('length', 'unknown')}s")
                    return data
        except Exception as e:
            logger.warning(f"Failed to get video info for {video_id}: {e}")
        return None

    async def _get_full_image_url(self, access_token: str, account_id: str, image_hash: str) -> Optional[str]:
        """Get full-resolution image URL from an image hash via the /adimages endpoint."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{META_GRAPH_URL}/{account_id}/adimages",
                    params={
                        "access_token": access_token,
                        "hashes": f'["{image_hash}"]',
                        "fields": "url,url_128,width,height,name",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    if isinstance(data, dict) and image_hash in data:
                        img_data = data[image_hash]
                        full_url = img_data.get("url")
                        if full_url:
                            logger.info(f"  Image hash {image_hash}: {img_data.get('width')}x{img_data.get('height')}")
                            return full_url
                    elif isinstance(data, list):
                        for img_data in data:
                            full_url = img_data.get("url")
                            if full_url:
                                logger.info(f"  Image hash {image_hash}: {img_data.get('width')}x{img_data.get('height')}")
                                return full_url
        except Exception as e:
            logger.warning(f"Failed to get image from hash {image_hash}: {e}")
        return None

    def _extract_image_url_from_story_spec(self, story_spec: Dict[str, Any]) -> Optional[str]:
        """Extract image URL from object_story_spec (link_data.picture or photo_data.url)."""
        link_data = story_spec.get("link_data", {})
        if link_data:
            picture = link_data.get("picture")
            if picture:
                return picture
            image_hash = link_data.get("image_hash")
            if image_hash:
                return None

        photo_data = story_spec.get("photo_data", {})
        if photo_data:
            url = photo_data.get("url")
            if url:
                return url

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
