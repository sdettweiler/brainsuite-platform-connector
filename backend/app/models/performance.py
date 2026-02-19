import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Date, Text, Integer, Float, Numeric, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class MetaRawPerformance(Base):
    __tablename__ = "meta_raw_performance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_connections.id"), nullable=False)
    sync_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sync_jobs.id"), nullable=True)

    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    ad_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    campaign_objective: Mapped[str] = mapped_column(String(255), nullable=True)
    buying_type: Mapped[str] = mapped_column(String(100), nullable=True)
    bid_strategy: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_set_id: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_set_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    optimization_goal: Mapped[str] = mapped_column(String(255), nullable=True)
    billing_event: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ad_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    configured_status: Mapped[str] = mapped_column(String(100), nullable=True)
    effective_status: Mapped[str] = mapped_column(String(100), nullable=True)
    destination_type: Mapped[str] = mapped_column(String(255), nullable=True)

    creative_id: Mapped[str] = mapped_column(String(255), nullable=True)
    thumbnail_url: Mapped[str] = mapped_column(Text, nullable=True)
    asset_url: Mapped[str] = mapped_column(Text, nullable=True)
    ad_format: Mapped[str] = mapped_column(String(100), nullable=True)
    placement: Mapped[str] = mapped_column(String(255), nullable=True)
    targeting_details: Mapped[dict] = mapped_column(JSONB, nullable=True)

    currency: Mapped[str] = mapped_column(String(3), nullable=True)
    spend: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=True)
    reach: Mapped[int] = mapped_column(Integer, nullable=True)
    frequency: Mapped[float] = mapped_column(Float, nullable=True)
    cpm: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cpp: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    unique_clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    cpc: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    ctr: Mapped[float] = mapped_column(Float, nullable=True)
    unique_ctr: Mapped[float] = mapped_column(Float, nullable=True)
    inline_link_clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    inline_link_click_ctr: Mapped[float] = mapped_column(Float, nullable=True)
    cost_per_inline_link_click: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    outbound_clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    outbound_clicks_ctr: Mapped[float] = mapped_column(Float, nullable=True)
    cost_per_outbound_click: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)

    video_play_actions: Mapped[int] = mapped_column(Integer, nullable=True)
    video_p25_watched: Mapped[int] = mapped_column(Integer, nullable=True)
    video_p50_watched: Mapped[int] = mapped_column(Integer, nullable=True)
    video_p75_watched: Mapped[int] = mapped_column(Integer, nullable=True)
    video_p95_watched: Mapped[int] = mapped_column(Integer, nullable=True)
    video_p100_watched: Mapped[int] = mapped_column(Integer, nullable=True)
    video_30_sec_watched: Mapped[int] = mapped_column(Integer, nullable=True)
    video_avg_time_watched_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    video_thruplay_watched: Mapped[int] = mapped_column(Integer, nullable=True)
    cost_per_thruplay: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cost_per_10_sec_video_view: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)

    video_views: Mapped[int] = mapped_column(Integer, nullable=True)
    video_view_rate: Mapped[float] = mapped_column(Float, nullable=True)

    estimated_ad_recallers: Mapped[int] = mapped_column(Integer, nullable=True)
    estimated_ad_recall_rate: Mapped[float] = mapped_column(Float, nullable=True)
    cost_per_estimated_ad_recaller: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    estimated_ad_recall_lift: Mapped[float] = mapped_column(Float, nullable=True)

    post_engagement: Mapped[int] = mapped_column(Integer, nullable=True)
    page_engagement: Mapped[int] = mapped_column(Integer, nullable=True)
    reactions: Mapped[int] = mapped_column(Integer, nullable=True)

    conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    conversion_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cvr: Mapped[float] = mapped_column(Float, nullable=True)
    roas: Mapped[float] = mapped_column(Float, nullable=True)
    purchase: Mapped[int] = mapped_column(Integer, nullable=True)
    purchase_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cost_per_purchase: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    purchase_roas: Mapped[float] = mapped_column(Float, nullable=True)
    lead: Mapped[int] = mapped_column(Integer, nullable=True)
    cost_per_lead: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    subscribe: Mapped[int] = mapped_column(Integer, nullable=True)
    omni_purchase: Mapped[int] = mapped_column(Integer, nullable=True)
    omni_purchase_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    omni_purchase_roas: Mapped[float] = mapped_column(Float, nullable=True)

    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("platform_connection_id", "report_date", "ad_id", "ad_account_id", name="uq_meta_daily_ad"),
        Index("ix_meta_raw_date_account", "report_date", "ad_account_id"),
        Index("ix_meta_raw_ad_id", "ad_id"),
    )


class TikTokRawPerformance(Base):
    __tablename__ = "tiktok_raw_performance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_connections.id"), nullable=False)
    sync_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sync_jobs.id"), nullable=True)

    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    ad_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    campaign_objective: Mapped[str] = mapped_column(String(255), nullable=True)
    buying_type: Mapped[str] = mapped_column(String(100), nullable=True)
    ad_group_id: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_group_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    optimization_goal: Mapped[str] = mapped_column(String(255), nullable=True)
    billing_event: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ad_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    ad_status: Mapped[str] = mapped_column(String(100), nullable=True)

    creative_type: Mapped[str] = mapped_column(String(100), nullable=True)
    ad_format: Mapped[str] = mapped_column(String(100), nullable=True)
    is_spark_ad: Mapped[bool] = mapped_column(Boolean, nullable=True)
    identity_type: Mapped[str] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str] = mapped_column(String(500), nullable=True)
    landing_page_url: Mapped[str] = mapped_column(Text, nullable=True)
    video_id: Mapped[str] = mapped_column(String(255), nullable=True)
    image_ids: Mapped[str] = mapped_column(Text, nullable=True)
    creative_url: Mapped[str] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str] = mapped_column(Text, nullable=True)
    asset_url: Mapped[str] = mapped_column(Text, nullable=True)
    targeting_segment: Mapped[str] = mapped_column(String(500), nullable=True)

    currency: Mapped[str] = mapped_column(String(3), nullable=True)
    spend: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=True)
    reach: Mapped[int] = mapped_column(Integer, nullable=True)
    frequency: Mapped[float] = mapped_column(Float, nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    cpc: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cpc_destination: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    ctr: Mapped[float] = mapped_column(Float, nullable=True)
    ctr_destination: Mapped[float] = mapped_column(Float, nullable=True)
    cpm: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cost_per_1000_reached: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)

    profile_visits: Mapped[int] = mapped_column(Integer, nullable=True)
    profile_visits_rate: Mapped[float] = mapped_column(Float, nullable=True)
    paid_likes: Mapped[int] = mapped_column(Integer, nullable=True)
    paid_comments: Mapped[int] = mapped_column(Integer, nullable=True)
    paid_shares: Mapped[int] = mapped_column(Integer, nullable=True)
    paid_follows: Mapped[int] = mapped_column(Integer, nullable=True)
    total_likes: Mapped[int] = mapped_column(Integer, nullable=True)
    total_comments: Mapped[int] = mapped_column(Integer, nullable=True)
    total_shares: Mapped[int] = mapped_column(Integer, nullable=True)
    total_follows: Mapped[int] = mapped_column(Integer, nullable=True)
    engagement_rate: Mapped[float] = mapped_column(Float, nullable=True)

    video_play_actions: Mapped[int] = mapped_column(Integer, nullable=True)
    video_watched_2s: Mapped[int] = mapped_column(Integer, nullable=True)
    video_watched_6s: Mapped[int] = mapped_column(Integer, nullable=True)
    video_views_p25: Mapped[int] = mapped_column(Integer, nullable=True)
    video_views_p50: Mapped[int] = mapped_column(Integer, nullable=True)
    video_views_p75: Mapped[int] = mapped_column(Integer, nullable=True)
    video_views_p100: Mapped[int] = mapped_column(Integer, nullable=True)
    video_completion_rate: Mapped[float] = mapped_column(Float, nullable=True)
    avg_play_time_per_user: Mapped[float] = mapped_column(Float, nullable=True)
    avg_play_time_per_video_view: Mapped[float] = mapped_column(Float, nullable=True)
    total_play_duration: Mapped[float] = mapped_column(Float, nullable=True)
    focused_view_6s: Mapped[int] = mapped_column(Integer, nullable=True)
    focused_view_15s: Mapped[int] = mapped_column(Integer, nullable=True)
    focused_view_rate: Mapped[float] = mapped_column(Float, nullable=True)
    cost_per_focused_view: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    video_views: Mapped[int] = mapped_column(Integer, nullable=True)

    conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    conversion_rate: Mapped[float] = mapped_column(Float, nullable=True)
    conversion_rate_clicks: Mapped[float] = mapped_column(Float, nullable=True)
    cost_per_conversion: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    conversion_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cvr: Mapped[float] = mapped_column(Float, nullable=True)
    roas: Mapped[float] = mapped_column(Float, nullable=True)
    result: Mapped[int] = mapped_column(Integer, nullable=True)
    result_rate: Mapped[float] = mapped_column(Float, nullable=True)
    cost_per_result: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    real_time_conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    cta_conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    vta_conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    cta_purchase: Mapped[int] = mapped_column(Integer, nullable=True)
    vta_purchase: Mapped[int] = mapped_column(Integer, nullable=True)
    total_purchase_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    purchase_roas: Mapped[float] = mapped_column(Float, nullable=True)

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
    __tablename__ = "youtube_raw_performance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_connections.id"), nullable=False)
    sync_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sync_jobs.id"), nullable=True)

    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    ad_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(255), nullable=True)
    customer_descriptive_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    campaign_id: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    campaign_status: Mapped[str] = mapped_column(String(100), nullable=True)
    campaign_objective: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign_channel_type: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign_channel_sub_type: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign_bidding_strategy_type: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_group_id: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_group_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    ad_group_status: Mapped[str] = mapped_column(String(100), nullable=True)
    ad_group_type: Mapped[str] = mapped_column(String(255), nullable=True)
    ad_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ad_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    ad_type: Mapped[str] = mapped_column(String(100), nullable=True)
    ad_status: Mapped[str] = mapped_column(String(100), nullable=True)
    ad_final_urls: Mapped[str] = mapped_column(Text, nullable=True)

    video_id: Mapped[str] = mapped_column(String(255), nullable=True)
    video_title: Mapped[str] = mapped_column(String(1000), nullable=True)
    video_duration_millis: Mapped[int] = mapped_column(Integer, nullable=True)
    ad_headlines: Mapped[str] = mapped_column(Text, nullable=True)
    ad_descriptions: Mapped[str] = mapped_column(Text, nullable=True)
    ad_call_to_action_text: Mapped[str] = mapped_column(String(255), nullable=True)
    video_url: Mapped[str] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str] = mapped_column(Text, nullable=True)
    video_duration: Mapped[int] = mapped_column(Integer, nullable=True)
    placement_type: Mapped[str] = mapped_column(String(100), nullable=True)

    currency: Mapped[str] = mapped_column(String(3), nullable=True)
    spend: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    ctr: Mapped[float] = mapped_column(Float, nullable=True)
    cpm: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    average_cpc: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    average_cpv: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)

    video_views: Mapped[int] = mapped_column(Integer, nullable=True)
    view_rate: Mapped[float] = mapped_column(Float, nullable=True)
    youtube_public_views: Mapped[int] = mapped_column(Integer, nullable=True)
    video_plays: Mapped[int] = mapped_column(Integer, nullable=True)
    video_quartile_p25: Mapped[float] = mapped_column(Float, nullable=True)
    video_quartile_p50: Mapped[float] = mapped_column(Float, nullable=True)
    video_quartile_p75: Mapped[float] = mapped_column(Float, nullable=True)
    video_quartile_p100: Mapped[float] = mapped_column(Float, nullable=True)
    avg_watch_time_per_impression: Mapped[float] = mapped_column(Float, nullable=True)
    video_view_through_rate: Mapped[float] = mapped_column(Float, nullable=True)

    engagements: Mapped[int] = mapped_column(Integer, nullable=True)
    engagement_rate: Mapped[float] = mapped_column(Float, nullable=True)
    interactions: Mapped[int] = mapped_column(Integer, nullable=True)
    active_view_viewability: Mapped[float] = mapped_column(Float, nullable=True)
    earned_subscribers: Mapped[int] = mapped_column(Integer, nullable=True)

    conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    all_conversions: Mapped[float] = mapped_column(Float, nullable=True)
    conversion_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    all_conversions_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    view_through_conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    engaged_view_conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    cross_device_conversions: Mapped[float] = mapped_column(Float, nullable=True)
    cost_per_conversion: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    value_per_conversion: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    conversions_from_interactions_rate: Mapped[float] = mapped_column(Float, nullable=True)
    cvr: Mapped[float] = mapped_column(Float, nullable=True)
    roas: Mapped[float] = mapped_column(Float, nullable=True)
    purchase_roas: Mapped[float] = mapped_column(Float, nullable=True)
    cost_per_view: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    earned_views: Mapped[int] = mapped_column(Integer, nullable=True)

    reach: Mapped[int] = mapped_column(Integer, nullable=True)
    frequency: Mapped[float] = mapped_column(Float, nullable=True)

    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("platform_connection_id", "report_date", "ad_id", "ad_account_id", name="uq_youtube_daily_ad"),
        Index("ix_youtube_raw_date_account", "report_date", "ad_account_id"),
        Index("ix_youtube_raw_ad_id", "ad_id"),
    )


class HarmonizedPerformance(Base):
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

    org_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    original_currency: Mapped[str] = mapped_column(String(3), nullable=True)
    exchange_rate: Mapped[float] = mapped_column(Float, nullable=True, default=1.0)

    spend: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=True)
    reach: Mapped[int] = mapped_column(Integer, nullable=True)
    frequency: Mapped[float] = mapped_column(Float, nullable=True)
    cpm: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cpp: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    cpc: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    ctr: Mapped[float] = mapped_column(Float, nullable=True)
    outbound_clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    outbound_ctr: Mapped[float] = mapped_column(Float, nullable=True)
    cpv: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)

    video_plays: Mapped[int] = mapped_column(Integer, nullable=True)
    video_views: Mapped[int] = mapped_column(Integer, nullable=True)
    vtr: Mapped[float] = mapped_column(Float, nullable=True)
    video_p25: Mapped[int] = mapped_column(Integer, nullable=True)
    video_p50: Mapped[int] = mapped_column(Integer, nullable=True)
    video_p75: Mapped[int] = mapped_column(Integer, nullable=True)
    video_p100: Mapped[int] = mapped_column(Integer, nullable=True)
    video_completion_rate: Mapped[float] = mapped_column(Float, nullable=True)
    video_avg_watch_time_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    cost_per_view: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)

    thruplay: Mapped[int] = mapped_column(Integer, nullable=True)
    cost_per_thruplay: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    focused_view: Mapped[int] = mapped_column(Integer, nullable=True)
    cost_per_focused_view: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    trueview_views: Mapped[int] = mapped_column(Integer, nullable=True)

    post_engagements: Mapped[int] = mapped_column(Integer, nullable=True)
    likes: Mapped[int] = mapped_column(Integer, nullable=True)
    comments: Mapped[int] = mapped_column(Integer, nullable=True)
    shares: Mapped[int] = mapped_column(Integer, nullable=True)
    follows: Mapped[int] = mapped_column(Integer, nullable=True)

    conversions: Mapped[int] = mapped_column(Integer, nullable=True)
    conversion_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    cvr: Mapped[float] = mapped_column(Float, nullable=True)
    cost_per_conversion: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    roas: Mapped[float] = mapped_column(Float, nullable=True)
    purchases: Mapped[int] = mapped_column(Integer, nullable=True)
    purchase_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)
    purchase_roas: Mapped[float] = mapped_column(Float, nullable=True)
    leads: Mapped[int] = mapped_column(Integer, nullable=True)
    cost_per_lead: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=True)

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
    __tablename__ = "sync_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_connections.id"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=True)
    date_to: Mapped[date] = mapped_column(Date, nullable=True)
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    job_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
