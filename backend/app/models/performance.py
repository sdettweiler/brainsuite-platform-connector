import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Date, Text, Integer, Float, Numeric, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class MetaRawPerformance(Base):
    """Raw Meta/Facebook Ads performance data — stored in original currency."""
    __tablename__ = "meta_raw_performance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_connections.id"), nullable=False)
    sync_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sync_jobs.id"), nullable=True)

    # Date + identifiers
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    ad_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    campaign_objective: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_set_id: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_set_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    ad_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ad_name: Mapped[str] = mapped_column(String(1000), nullable=True)

    # Creative metadata
    creative_id: Mapped[str] = mapped_column(String(255), nullable=True)
    thumbnail_url: Mapped[str] = mapped_column(Text, nullable=True)
    ad_format: Mapped[str] = mapped_column(String(100), nullable=True)  # IMAGE, VIDEO, CAROUSEL
    placement: Mapped[str] = mapped_column(String(255), nullable=True)
    targeting_details: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Performance — original currency
    currency: Mapped[str] = mapped_column(String(3), nullable=True)
    spend: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    ctr: Mapped[float] = mapped_column(Float, nullable=True)
    reach: Mapped[int] = mapped_column(Integer, nullable=True)
    frequency: Mapped[float] = mapped_column(Float, nullable=True)
    cpm: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cpc: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    conversion_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cvr: Mapped[float] = mapped_column(Float, nullable=True)
    roas: Mapped[float] = mapped_column(Float, nullable=True)
    video_views: Mapped[int] = mapped_column(Integer, nullable=True)
    video_view_rate: Mapped[float] = mapped_column(Float, nullable=True)
    estimated_ad_recall_lift: Mapped[float] = mapped_column(Float, nullable=True)

    # Tracking
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("platform_connection_id", "report_date", "ad_id", "ad_account_id", name="uq_meta_daily_ad"),
        Index("ix_meta_raw_date_account", "report_date", "ad_account_id"),
        Index("ix_meta_raw_ad_id", "ad_id"),
    )


class TikTokRawPerformance(Base):
    """Raw TikTok Ads performance data — stored in original currency."""
    __tablename__ = "tiktok_raw_performance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_connections.id"), nullable=False)
    sync_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sync_jobs.id"), nullable=True)

    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    ad_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    campaign_objective: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_group_id: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_group_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    ad_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ad_name: Mapped[str] = mapped_column(String(1000), nullable=True)

    # Creative metadata
    creative_url: Mapped[str] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str] = mapped_column(Text, nullable=True)
    ad_format: Mapped[str] = mapped_column(String(100), nullable=True)
    targeting_segment: Mapped[str] = mapped_column(String(500), nullable=True)

    # Performance — original currency
    currency: Mapped[str] = mapped_column(String(3), nullable=True)
    spend: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    ctr: Mapped[float] = mapped_column(Float, nullable=True)
    cpm: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    conversion_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cvr: Mapped[float] = mapped_column(Float, nullable=True)
    roas: Mapped[float] = mapped_column(Float, nullable=True)
    video_views: Mapped[int] = mapped_column(Integer, nullable=True)
    video_completion_rate: Mapped[float] = mapped_column(Float, nullable=True)
    engagement_rate: Mapped[float] = mapped_column(Float, nullable=True)
    swipe_rate: Mapped[float] = mapped_column(Float, nullable=True)

    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("platform_connection_id", "report_date", "ad_id", "ad_account_id", name="uq_tiktok_daily_ad"),
        Index("ix_tiktok_raw_date_account", "report_date", "ad_account_id"),
        Index("ix_tiktok_raw_ad_id", "ad_id"),
    )


class YouTubeRawPerformance(Base):
    """Raw YouTube/Google Ads performance data — stored in original currency."""
    __tablename__ = "youtube_raw_performance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_connections.id"), nullable=False)
    sync_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sync_jobs.id"), nullable=True)

    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    ad_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    campaign_objective: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_group_id: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_group_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    ad_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ad_name: Mapped[str] = mapped_column(String(1000), nullable=True)

    # Creative metadata
    video_url: Mapped[str] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str] = mapped_column(Text, nullable=True)
    video_duration: Mapped[int] = mapped_column(Integer, nullable=True)  # seconds
    placement_type: Mapped[str] = mapped_column(String(100), nullable=True)  # IN_STREAM, DISCOVERY

    # Performance — original currency
    currency: Mapped[str] = mapped_column(String(3), nullable=True)
    spend: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    ctr: Mapped[float] = mapped_column(Float, nullable=True)
    cpm: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    conversion_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cvr: Mapped[float] = mapped_column(Float, nullable=True)
    roas: Mapped[float] = mapped_column(Float, nullable=True)
    view_rate: Mapped[float] = mapped_column(Float, nullable=True)
    cost_per_view: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    earned_views: Mapped[int] = mapped_column(Integer, nullable=True)
    video_view_through_rate: Mapped[float] = mapped_column(Float, nullable=True)
    video_quartile_p25: Mapped[float] = mapped_column(Float, nullable=True)
    video_quartile_p50: Mapped[float] = mapped_column(Float, nullable=True)
    video_quartile_p75: Mapped[float] = mapped_column(Float, nullable=True)
    video_quartile_p100: Mapped[float] = mapped_column(Float, nullable=True)

    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("platform_connection_id", "report_date", "ad_id", "ad_account_id", name="uq_youtube_daily_ad"),
        Index("ix_youtube_raw_date_account", "report_date", "ad_account_id"),
        Index("ix_youtube_raw_ad_id", "ad_id"),
    )


class HarmonizedPerformance(Base):
    """Consolidated, currency-converted performance data feeding all reports."""
    __tablename__ = "harmonized_performance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("creative_assets.id"), nullable=False)
    platform_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_connections.id"), nullable=False)

    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    ad_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    campaign_objective: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_set_id: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_set_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    ad_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ad_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    asset_format: Mapped[str] = mapped_column(String(50), nullable=True)

    # All monetary metrics in organization currency
    org_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    original_currency: Mapped[str] = mapped_column(String(3), nullable=True)
    exchange_rate: Mapped[float] = mapped_column(Float, nullable=True, default=1.0)

    spend: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    ctr: Mapped[float] = mapped_column(Float, nullable=True)
    reach: Mapped[int] = mapped_column(Integer, nullable=True)
    frequency: Mapped[float] = mapped_column(Float, nullable=True)
    cpm: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cpc: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    conversion_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cvr: Mapped[float] = mapped_column(Float, nullable=True)
    roas: Mapped[float] = mapped_column(Float, nullable=True)

    # Video metrics (NULL for non-video)
    video_views: Mapped[int] = mapped_column(Integer, nullable=True)
    vtr: Mapped[float] = mapped_column(Float, nullable=True)  # video through rate
    video_completion_rate: Mapped[float] = mapped_column(Float, nullable=True)
    cost_per_view: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)

    # Platform-specific extras
    platform_extras: Mapped[dict] = mapped_column(JSONB, default=dict)

    harmonized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=True)

    asset: Mapped["CreativeAsset"] = relationship("CreativeAsset", back_populates="harmonized_performance")

    __table_args__ = (
        UniqueConstraint("platform_connection_id", "report_date", "ad_id", "ad_account_id", name="uq_harmonized_daily_ad"),
        Index("ix_harmonized_date", "report_date"),
        Index("ix_harmonized_asset", "asset_id"),
        Index("ix_harmonized_platform", "platform"),
    )


class CurrencyRate(Base):
    """Daily exchange rates cache."""
    __tablename__ = "currency_rates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("rate_date", "from_currency", "to_currency", name="uq_daily_rate"),
        Index("ix_currency_rate_date", "rate_date"),
    )


class SyncJob(Base):
    """Tracks data sync job executions."""
    __tablename__ = "sync_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_connections.id"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # INITIAL_30D, HISTORICAL, DAILY, MANUAL
    status: Mapped[str] = mapped_column(String(50), default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=True)
    date_to: Mapped[date] = mapped_column(Date, nullable=True)
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    job_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
