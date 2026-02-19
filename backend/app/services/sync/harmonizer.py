"""
Data harmonization service.
Takes raw platform data, applies currency conversion, and writes to harmonized_performance.
Also creates/updates creative_assets records.
Triple-checked for correctness — this is the source of truth for all reports.
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.creative import CreativeAsset
from app.models.performance import (
    MetaRawPerformance,
    TikTokRawPerformance,
    YouTubeRawPerformance,
    HarmonizedPerformance,
)
from app.models.platform import PlatformConnection
from app.models.user import Organization
from app.services.currency import currency_converter
from app.services.ace_score import generate_ace_score

logger = logging.getLogger(__name__)


class HarmonizationService:

    async def harmonize_connection(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> int:
        """Harmonize all unprocessed raw records for a connection."""
        # Get organization currency
        org = await db.get(Organization, connection.organization_id)
        org_currency = org.currency if org else "USD"

        if connection.platform == "META":
            return await self._harmonize_meta(db, connection, org_currency, date_from, date_to)
        elif connection.platform == "TIKTOK":
            return await self._harmonize_tiktok(db, connection, org_currency, date_from, date_to)
        elif connection.platform == "YOUTUBE":
            return await self._harmonize_youtube(db, connection, org_currency, date_from, date_to)
        return 0

    async def _harmonize_meta(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        org_currency: str,
        date_from: Optional[date],
        date_to: Optional[date],
    ) -> int:
        query = select(MetaRawPerformance).where(
            MetaRawPerformance.platform_connection_id == connection.id,
            MetaRawPerformance.is_processed == False,
        )
        if date_from:
            query = query.where(MetaRawPerformance.report_date >= date_from)
        if date_to:
            query = query.where(MetaRawPerformance.report_date <= date_to)

        result = await db.execute(query)
        raw_records = result.scalars().all()
        count = 0

        for raw in raw_records:
            try:
                # Currency conversion
                original_currency = raw.currency or connection.currency or "USD"
                exchange_rate = await currency_converter.get_rate(
                    db, original_currency, org_currency, raw.report_date
                )

                def convert(val: Optional[Decimal]) -> Optional[Decimal]:
                    if val is None:
                        return None
                    return Decimal(str(float(val) * exchange_rate))

                # Ensure creative asset exists
                asset = await self._ensure_asset(
                    db,
                    connection=connection,
                    platform="META",
                    ad_id=raw.ad_id,
                    ad_name=raw.ad_name,
                    campaign_id=raw.campaign_id,
                    campaign_name=raw.campaign_name,
                    campaign_objective=raw.campaign_objective,
                    ad_set_id=raw.ad_set_id,
                    ad_set_name=raw.ad_set_name,
                    ad_account_id=raw.ad_account_id,
                    asset_format=raw.ad_format,
                    thumbnail_url=raw.thumbnail_url,
                    creative_id=raw.creative_id,
                    placement=raw.placement,
                    first_seen_at=raw.report_date,
                )

                # Upsert harmonized record
                row = {
                    "asset_id": asset.id,
                    "platform_connection_id": connection.id,
                    "report_date": raw.report_date,
                    "platform": "META",
                    "ad_account_id": raw.ad_account_id,
                    "campaign_id": raw.campaign_id,
                    "campaign_name": raw.campaign_name,
                    "campaign_objective": raw.campaign_objective,
                    "ad_set_id": raw.ad_set_id,
                    "ad_set_name": raw.ad_set_name,
                    "ad_id": raw.ad_id,
                    "ad_name": raw.ad_name,
                    "asset_format": raw.ad_format or "IMAGE",
                    "org_currency": org_currency,
                    "original_currency": original_currency,
                    "exchange_rate": exchange_rate,
                    "spend": convert(raw.spend),
                    "impressions": raw.impressions,
                    "clicks": raw.clicks,
                    "ctr": raw.ctr,
                    "reach": raw.reach,
                    "frequency": raw.frequency,
                    "cpm": convert(raw.cpm),
                    "cpc": convert(raw.cpc),
                    "conversions": raw.conversions,
                    "conversion_value": convert(raw.conversion_value),
                    "cvr": raw.cvr,
                    "roas": raw.roas,
                    "video_views": raw.video_views,
                    "vtr": raw.video_view_rate,
                    "platform_extras": {
                        "reach": raw.reach,
                        "frequency": raw.frequency,
                        "estimated_ad_recall_lift": raw.estimated_ad_recall_lift,
                    },
                }

                await self._upsert_harmonized(db, row)

                # Mark as processed
                raw.is_processed = True
                db.add(raw)
                count += 1

            except Exception as e:
                logger.error(f"Harmonization error for Meta record {raw.id}: {e}")

        await db.flush()
        return count

    async def _harmonize_tiktok(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        org_currency: str,
        date_from: Optional[date],
        date_to: Optional[date],
    ) -> int:
        query = select(TikTokRawPerformance).where(
            TikTokRawPerformance.platform_connection_id == connection.id,
            TikTokRawPerformance.is_processed == False,
        )
        if date_from:
            query = query.where(TikTokRawPerformance.report_date >= date_from)
        if date_to:
            query = query.where(TikTokRawPerformance.report_date <= date_to)

        result = await db.execute(query)
        raw_records = result.scalars().all()
        count = 0

        for raw in raw_records:
            try:
                original_currency = raw.currency or connection.currency or "USD"
                exchange_rate = await currency_converter.get_rate(
                    db, original_currency, org_currency, raw.report_date
                )

                def convert(val):
                    if val is None:
                        return None
                    return Decimal(str(float(val) * exchange_rate))

                asset = await self._ensure_asset(
                    db,
                    connection=connection,
                    platform="TIKTOK",
                    ad_id=raw.ad_id,
                    ad_name=raw.ad_name,
                    campaign_id=raw.campaign_id,
                    campaign_name=raw.campaign_name,
                    campaign_objective=raw.campaign_objective,
                    ad_set_id=raw.ad_group_id,
                    ad_set_name=raw.ad_group_name,
                    ad_account_id=raw.ad_account_id,
                    asset_format=raw.ad_format,
                    thumbnail_url=raw.thumbnail_url,
                    asset_url=raw.creative_url,
                    first_seen_at=raw.report_date,
                )

                row = {
                    "asset_id": asset.id,
                    "platform_connection_id": connection.id,
                    "report_date": raw.report_date,
                    "platform": "TIKTOK",
                    "ad_account_id": raw.ad_account_id,
                    "campaign_id": raw.campaign_id,
                    "campaign_name": raw.campaign_name,
                    "campaign_objective": raw.campaign_objective,
                    "ad_set_id": raw.ad_group_id,
                    "ad_set_name": raw.ad_group_name,
                    "ad_id": raw.ad_id,
                    "ad_name": raw.ad_name,
                    "asset_format": raw.ad_format or "VIDEO",
                    "org_currency": org_currency,
                    "original_currency": original_currency,
                    "exchange_rate": exchange_rate,
                    "spend": convert(raw.spend),
                    "impressions": raw.impressions,
                    "clicks": raw.clicks,
                    "ctr": raw.ctr,
                    "cpm": convert(raw.cpm),
                    "conversions": raw.conversions,
                    "conversion_value": convert(raw.conversion_value),
                    "cvr": raw.cvr,
                    "roas": raw.roas,
                    "video_views": raw.video_views,
                    "vtr": raw.video_completion_rate,
                    "video_completion_rate": raw.video_completion_rate,
                    "platform_extras": {
                        "engagement_rate": raw.engagement_rate,
                        "swipe_rate": raw.swipe_rate,
                    },
                }

                await self._upsert_harmonized(db, row)
                raw.is_processed = True
                db.add(raw)
                count += 1

            except Exception as e:
                logger.error(f"Harmonization error for TikTok record {raw.id}: {e}")

        await db.flush()
        return count

    async def _harmonize_youtube(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        org_currency: str,
        date_from: Optional[date],
        date_to: Optional[date],
    ) -> int:
        query = select(YouTubeRawPerformance).where(
            YouTubeRawPerformance.platform_connection_id == connection.id,
            YouTubeRawPerformance.is_processed == False,
        )
        if date_from:
            query = query.where(YouTubeRawPerformance.report_date >= date_from)
        if date_to:
            query = query.where(YouTubeRawPerformance.report_date <= date_to)

        result = await db.execute(query)
        raw_records = result.scalars().all()
        count = 0

        for raw in raw_records:
            try:
                original_currency = raw.currency or connection.currency or "USD"
                exchange_rate = await currency_converter.get_rate(
                    db, original_currency, org_currency, raw.report_date
                )

                def convert(val):
                    if val is None:
                        return None
                    return Decimal(str(float(val) * exchange_rate))

                asset = await self._ensure_asset(
                    db,
                    connection=connection,
                    platform="YOUTUBE",
                    ad_id=raw.ad_id,
                    ad_name=raw.ad_name,
                    campaign_id=raw.campaign_id,
                    campaign_name=raw.campaign_name,
                    campaign_objective=raw.campaign_objective,
                    ad_set_id=raw.ad_group_id,
                    ad_set_name=raw.ad_group_name,
                    ad_account_id=raw.ad_account_id,
                    asset_format="VIDEO",
                    thumbnail_url=raw.thumbnail_url,
                    asset_url=raw.video_url,
                    video_duration=raw.video_duration,
                    placement=raw.placement_type,
                    first_seen_at=raw.report_date,
                )

                row = {
                    "asset_id": asset.id,
                    "platform_connection_id": connection.id,
                    "report_date": raw.report_date,
                    "platform": "YOUTUBE",
                    "ad_account_id": raw.ad_account_id,
                    "campaign_id": raw.campaign_id,
                    "campaign_name": raw.campaign_name,
                    "campaign_objective": raw.campaign_objective,
                    "ad_set_id": raw.ad_group_id,
                    "ad_set_name": raw.ad_group_name,
                    "ad_id": raw.ad_id,
                    "ad_name": raw.ad_name,
                    "asset_format": "VIDEO",
                    "org_currency": org_currency,
                    "original_currency": original_currency,
                    "exchange_rate": exchange_rate,
                    "spend": convert(raw.spend),
                    "impressions": raw.impressions,
                    "clicks": raw.clicks,
                    "ctr": raw.ctr,
                    "cpm": convert(raw.cpm),
                    "conversions": raw.conversions,
                    "conversion_value": convert(raw.conversion_value),
                    "cvr": raw.cvr,
                    "roas": raw.roas,
                    "video_views": raw.video_views,
                    "vtr": raw.view_rate,
                    "video_completion_rate": raw.video_view_through_rate,
                    "cost_per_view": convert(raw.cost_per_view),
                    "platform_extras": {
                        "placement_type": raw.placement_type,
                        "earned_views": raw.earned_views,
                        "video_quartile_p25": raw.video_quartile_p25,
                        "video_quartile_p50": raw.video_quartile_p50,
                        "video_quartile_p75": raw.video_quartile_p75,
                        "video_quartile_p100": raw.video_quartile_p100,
                    },
                }

                await self._upsert_harmonized(db, row)
                raw.is_processed = True
                db.add(raw)
                count += 1

            except Exception as e:
                logger.error(f"Harmonization error for YouTube record {raw.id}: {e}")

        await db.flush()
        return count

    async def _ensure_asset(
        self,
        db: AsyncSession,
        connection: PlatformConnection,
        platform: str,
        ad_id: str,
        **kwargs,
    ) -> CreativeAsset:
        """Get or create a CreativeAsset record."""
        result = await db.execute(
            select(CreativeAsset).where(
                CreativeAsset.organization_id == connection.organization_id,
                CreativeAsset.platform == platform,
                CreativeAsset.ad_id == ad_id,
                CreativeAsset.ad_account_id == kwargs.get("ad_account_id"),
            )
        )
        asset = result.scalar_one_or_none()

        if not asset:
            ace = generate_ace_score(kwargs.get("asset_format"))
            first_seen = kwargs.get("first_seen_at")
            if isinstance(first_seen, str):
                from datetime import datetime
                try:
                    first_seen = datetime.strptime(first_seen, "%Y-%m-%d").date()
                except Exception:
                    first_seen = None

            asset = CreativeAsset(
                organization_id=connection.organization_id,
                platform_connection_id=connection.id,
                platform=platform,
                ad_id=ad_id,
                ad_name=kwargs.get("ad_name"),
                campaign_id=kwargs.get("campaign_id"),
                campaign_name=kwargs.get("campaign_name"),
                campaign_objective=kwargs.get("campaign_objective"),
                ad_set_id=kwargs.get("ad_set_id"),
                ad_set_name=kwargs.get("ad_set_name"),
                ad_account_id=kwargs.get("ad_account_id"),
                asset_format=(kwargs.get("asset_format") or "IMAGE").upper(),
                thumbnail_url=kwargs.get("thumbnail_url"),
                asset_url=kwargs.get("asset_url"),
                creative_id=kwargs.get("creative_id"),
                placement=kwargs.get("placement"),
                video_duration=kwargs.get("video_duration"),
                ace_score=ace["ace_score"],
                ace_score_confidence=ace["ace_score_confidence"],
                brainsuite_metadata=ace["brainsuite_metadata"],
                first_seen_at=first_seen,
                last_seen_at=first_seen,
            )
            db.add(asset)
            await db.flush()
        else:
            # Update mutable fields
            if kwargs.get("thumbnail_url") and not asset.thumbnail_url:
                asset.thumbnail_url = kwargs.get("thumbnail_url")
            if kwargs.get("creative_id") and not asset.creative_id:
                asset.creative_id = kwargs.get("creative_id")
            if kwargs.get("asset_format") and not asset.asset_format:
                asset.asset_format = kwargs.get("asset_format")
            if kwargs.get("first_seen_at"):
                first_seen = kwargs.get("first_seen_at")
                if isinstance(first_seen, str):
                    from datetime import datetime as _dt
                    try:
                        first_seen = _dt.strptime(first_seen, "%Y-%m-%d").date()
                    except Exception:
                        first_seen = None
                if first_seen:
                    existing_first = asset.first_seen_at
                    if isinstance(existing_first, datetime):
                        existing_first = existing_first.date()
                    existing_last = asset.last_seen_at
                    if isinstance(existing_last, datetime):
                        existing_last = existing_last.date()
                    if isinstance(first_seen, datetime):
                        first_seen = first_seen.date()
                    if not existing_first or first_seen < existing_first:
                        asset.first_seen_at = first_seen
                    if not existing_last or first_seen > existing_last:
                        asset.last_seen_at = first_seen
            db.add(asset)
            await db.flush()

        return asset

    async def _upsert_harmonized(self, db: AsyncSession, row: dict) -> None:
        stmt = pg_insert(HarmonizedPerformance).values([row])
        stmt = stmt.on_conflict_do_update(
            constraint="uq_harmonized_daily_ad",
            set_={k: stmt.excluded[k] for k in [
                "spend", "impressions", "clicks", "ctr", "reach", "frequency",
                "cpm", "cpc", "conversions", "conversion_value", "cvr", "roas",
                "video_views", "vtr", "video_completion_rate", "cost_per_view",
                "exchange_rate", "platform_extras", "harmonized_at",
            ] if k in row}
        )
        await db.execute(stmt)


harmonizer = HarmonizationService()
