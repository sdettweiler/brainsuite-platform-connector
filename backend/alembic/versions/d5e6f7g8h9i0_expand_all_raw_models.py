"""expand all raw performance models and harmonized model per field reference v3

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e6f7g8h9i0"
down_revision = "c4d5e6f7g8h9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── META RAW PERFORMANCE ──
    meta_cols = [
        ("buying_type", sa.String(100)),
        ("bid_strategy", sa.String(255)),
        ("optimization_goal", sa.String(255)),
        ("billing_event", sa.String(255)),
        ("configured_status", sa.String(100)),
        ("effective_status", sa.String(100)),
        ("destination_type", sa.String(255)),
        ("cpp", sa.Numeric(18, 4)),
        ("unique_clicks", sa.Integer()),
        ("unique_ctr", sa.Float()),
        ("inline_link_clicks", sa.Integer()),
        ("inline_link_click_ctr", sa.Float()),
        ("cost_per_inline_link_click", sa.Numeric(18, 4)),
        ("outbound_clicks", sa.Integer()),
        ("outbound_clicks_ctr", sa.Float()),
        ("cost_per_outbound_click", sa.Numeric(18, 4)),
        ("video_play_actions", sa.Integer()),
        ("video_p25_watched", sa.Integer()),
        ("video_p50_watched", sa.Integer()),
        ("video_p75_watched", sa.Integer()),
        ("video_p95_watched", sa.Integer()),
        ("video_p100_watched", sa.Integer()),
        ("video_30_sec_watched", sa.Integer()),
        ("video_avg_time_watched_ms", sa.Integer()),
        ("video_thruplay_watched", sa.Integer()),
        ("cost_per_thruplay", sa.Numeric(18, 4)),
        ("cost_per_10_sec_video_view", sa.Numeric(18, 4)),
        ("estimated_ad_recallers", sa.Integer()),
        ("estimated_ad_recall_rate", sa.Float()),
        ("cost_per_estimated_ad_recaller", sa.Numeric(18, 4)),
        ("post_engagement", sa.Integer()),
        ("page_engagement", sa.Integer()),
        ("reactions", sa.Integer()),
        ("purchase", sa.Integer()),
        ("purchase_value", sa.Numeric(18, 4)),
        ("cost_per_purchase", sa.Numeric(18, 4)),
        ("purchase_roas", sa.Float()),
        ("lead", sa.Integer()),
        ("cost_per_lead", sa.Numeric(18, 4)),
        ("subscribe", sa.Integer()),
        ("omni_purchase", sa.Integer()),
        ("omni_purchase_value", sa.Numeric(18, 4)),
        ("omni_purchase_roas", sa.Float()),
    ]
    for col_name, col_type in meta_cols:
        op.add_column("meta_raw_performance", sa.Column(col_name, col_type, nullable=True))

    # ── TIKTOK RAW PERFORMANCE ──
    tiktok_cols = [
        ("buying_type", sa.String(100)),
        ("optimization_goal", sa.String(255)),
        ("billing_event", sa.String(255)),
        ("ad_status", sa.String(100)),
        ("creative_type", sa.String(100)),
        ("is_spark_ad", sa.Boolean()),
        ("identity_type", sa.String(100)),
        ("display_name", sa.String(500)),
        ("landing_page_url", sa.Text()),
        ("video_id", sa.String(255)),
        ("image_ids", sa.Text()),
        ("asset_url", sa.Text()),
        ("reach", sa.Integer()),
        ("frequency", sa.Float()),
        ("cpc", sa.Numeric(18, 4)),
        ("cpc_destination", sa.Numeric(18, 4)),
        ("ctr_destination", sa.Float()),
        ("cost_per_1000_reached", sa.Numeric(18, 4)),
        ("profile_visits", sa.Integer()),
        ("profile_visits_rate", sa.Float()),
        ("paid_likes", sa.Integer()),
        ("paid_comments", sa.Integer()),
        ("paid_shares", sa.Integer()),
        ("paid_follows", sa.Integer()),
        ("total_likes", sa.Integer()),
        ("total_comments", sa.Integer()),
        ("total_shares", sa.Integer()),
        ("total_follows", sa.Integer()),
        ("video_play_actions", sa.Integer()),
        ("video_watched_2s", sa.Integer()),
        ("video_watched_6s", sa.Integer()),
        ("video_views_p25", sa.Integer()),
        ("video_views_p50", sa.Integer()),
        ("video_views_p75", sa.Integer()),
        ("video_views_p100", sa.Integer()),
        ("avg_play_time_per_user", sa.Float()),
        ("avg_play_time_per_video_view", sa.Float()),
        ("total_play_duration", sa.Float()),
        ("focused_view_6s", sa.Integer()),
        ("focused_view_15s", sa.Integer()),
        ("focused_view_rate", sa.Float()),
        ("cost_per_focused_view", sa.Numeric(18, 4)),
        ("conversion_rate", sa.Float()),
        ("conversion_rate_clicks", sa.Float()),
        ("cost_per_conversion", sa.Numeric(18, 4)),
        ("result", sa.Integer()),
        ("result_rate", sa.Float()),
        ("cost_per_result", sa.Numeric(18, 4)),
        ("real_time_conversions", sa.Integer()),
        ("cta_conversions", sa.Integer()),
        ("vta_conversions", sa.Integer()),
        ("cta_purchase", sa.Integer()),
        ("vta_purchase", sa.Integer()),
        ("total_purchase_value", sa.Numeric(18, 4)),
        ("purchase_roas", sa.Float()),
    ]
    for col_name, col_type in tiktok_cols:
        op.add_column("tiktok_raw_performance", sa.Column(col_name, col_type, nullable=True))

    # ── YOUTUBE RAW PERFORMANCE ──
    youtube_cols = [
        ("customer_id", sa.String(255)),
        ("customer_descriptive_name", sa.String(1000)),
        ("campaign_status", sa.String(100)),
        ("campaign_channel_type", sa.String(255)),
        ("campaign_channel_sub_type", sa.String(255)),
        ("campaign_bidding_strategy_type", sa.String(255)),
        ("ad_group_status", sa.String(100)),
        ("ad_group_type", sa.String(255)),
        ("ad_type", sa.String(100)),
        ("ad_status", sa.String(100)),
        ("ad_final_urls", sa.Text()),
        ("video_id", sa.String(255)),
        ("video_title", sa.String(1000)),
        ("video_duration_millis", sa.Integer()),
        ("ad_headlines", sa.Text()),
        ("ad_descriptions", sa.Text()),
        ("ad_call_to_action_text", sa.String(255)),
        ("average_cpc", sa.Numeric(18, 4)),
        ("average_cpv", sa.Numeric(18, 4)),
        ("youtube_public_views", sa.Integer()),
        ("video_plays", sa.Integer()),
        ("avg_watch_time_per_impression", sa.Float()),
        ("engagements", sa.Integer()),
        ("engagement_rate", sa.Float()),
        ("interactions", sa.Integer()),
        ("active_view_viewability", sa.Float()),
        ("earned_subscribers", sa.Integer()),
        ("all_conversions", sa.Float()),
        ("all_conversions_value", sa.Numeric(18, 4)),
        ("view_through_conversions", sa.Integer()),
        ("engaged_view_conversions", sa.Integer()),
        ("cross_device_conversions", sa.Float()),
        ("cost_per_conversion", sa.Numeric(18, 4)),
        ("value_per_conversion", sa.Numeric(18, 4)),
        ("conversions_from_interactions_rate", sa.Float()),
        ("purchase_roas", sa.Float()),
        ("reach", sa.Integer()),
        ("frequency", sa.Float()),
    ]
    for col_name, col_type in youtube_cols:
        op.add_column("youtube_raw_performance", sa.Column(col_name, col_type, nullable=True))

    # ── HARMONIZED PERFORMANCE ──
    harmonized_cols = [
        ("cpp", sa.Numeric(18, 4)),
        ("outbound_clicks", sa.Integer()),
        ("outbound_ctr", sa.Float()),
        ("cpv", sa.Numeric(18, 4)),
        ("video_plays", sa.Integer()),
        ("video_p25", sa.Integer()),
        ("video_p50", sa.Integer()),
        ("video_p75", sa.Integer()),
        ("video_p100", sa.Integer()),
        ("video_avg_watch_time_seconds", sa.Float()),
        ("thruplay", sa.Integer()),
        ("cost_per_thruplay", sa.Numeric(18, 4)),
        ("focused_view", sa.Integer()),
        ("cost_per_focused_view", sa.Numeric(18, 4)),
        ("trueview_views", sa.Integer()),
        ("post_engagements", sa.Integer()),
        ("likes", sa.Integer()),
        ("comments", sa.Integer()),
        ("shares", sa.Integer()),
        ("follows", sa.Integer()),
        ("cost_per_conversion", sa.Numeric(18, 4)),
        ("purchases", sa.Integer()),
        ("purchase_value", sa.Numeric(18, 4)),
        ("purchase_roas", sa.Float()),
        ("leads", sa.Integer()),
        ("cost_per_lead", sa.Numeric(18, 4)),
    ]
    for col_name, col_type in harmonized_cols:
        op.add_column("harmonized_performance", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    meta_drop = [
        "buying_type", "bid_strategy", "optimization_goal", "billing_event",
        "configured_status", "effective_status", "destination_type", "cpp",
        "unique_clicks", "unique_ctr", "inline_link_clicks", "inline_link_click_ctr",
        "cost_per_inline_link_click", "outbound_clicks", "outbound_clicks_ctr",
        "cost_per_outbound_click", "video_play_actions", "video_p25_watched",
        "video_p50_watched", "video_p75_watched", "video_p95_watched",
        "video_p100_watched", "video_30_sec_watched", "video_avg_time_watched_ms",
        "video_thruplay_watched", "cost_per_thruplay", "cost_per_10_sec_video_view",
        "estimated_ad_recallers", "estimated_ad_recall_rate",
        "cost_per_estimated_ad_recaller", "post_engagement", "page_engagement",
        "reactions", "purchase", "purchase_value", "cost_per_purchase",
        "purchase_roas", "lead", "cost_per_lead", "subscribe",
        "omni_purchase", "omni_purchase_value", "omni_purchase_roas",
    ]
    for col in meta_drop:
        op.drop_column("meta_raw_performance", col)

    tiktok_drop = [
        "buying_type", "optimization_goal", "billing_event", "ad_status",
        "creative_type", "is_spark_ad", "identity_type", "display_name",
        "landing_page_url", "video_id", "image_ids", "asset_url",
        "reach", "frequency", "cpc", "cpc_destination", "ctr_destination",
        "cost_per_1000_reached", "profile_visits", "profile_visits_rate",
        "paid_likes", "paid_comments", "paid_shares", "paid_follows",
        "total_likes", "total_comments", "total_shares", "total_follows",
        "video_play_actions", "video_watched_2s", "video_watched_6s",
        "video_views_p25", "video_views_p50", "video_views_p75", "video_views_p100",
        "avg_play_time_per_user", "avg_play_time_per_video_view", "total_play_duration",
        "focused_view_6s", "focused_view_15s", "focused_view_rate",
        "cost_per_focused_view", "conversion_rate", "conversion_rate_clicks",
        "cost_per_conversion", "result", "result_rate", "cost_per_result",
        "real_time_conversions", "cta_conversions", "vta_conversions",
        "cta_purchase", "vta_purchase", "total_purchase_value", "purchase_roas",
    ]
    for col in tiktok_drop:
        op.drop_column("tiktok_raw_performance", col)

    youtube_drop = [
        "customer_id", "customer_descriptive_name", "campaign_status",
        "campaign_channel_type", "campaign_channel_sub_type",
        "campaign_bidding_strategy_type", "ad_group_status", "ad_group_type",
        "ad_type", "ad_status", "ad_final_urls", "video_id", "video_title",
        "video_duration_millis", "ad_headlines", "ad_descriptions",
        "ad_call_to_action_text", "average_cpc", "average_cpv",
        "youtube_public_views", "video_plays", "avg_watch_time_per_impression",
        "engagements", "engagement_rate", "interactions",
        "active_view_viewability", "earned_subscribers",
        "all_conversions", "all_conversions_value", "view_through_conversions",
        "engaged_view_conversions", "cross_device_conversions",
        "cost_per_conversion", "value_per_conversion",
        "conversions_from_interactions_rate", "purchase_roas",
        "reach", "frequency",
    ]
    for col in youtube_drop:
        op.drop_column("youtube_raw_performance", col)

    harmonized_drop = [
        "cpp", "outbound_clicks", "outbound_ctr", "cpv",
        "video_plays", "video_p25", "video_p50", "video_p75", "video_p100",
        "video_avg_watch_time_seconds", "thruplay", "cost_per_thruplay",
        "focused_view", "cost_per_focused_view", "trueview_views",
        "post_engagements", "likes", "comments", "shares", "follows",
        "cost_per_conversion", "purchases", "purchase_value", "purchase_roas",
        "leads", "cost_per_lead",
    ]
    for col in harmonized_drop:
        op.drop_column("harmonized_performance", col)
