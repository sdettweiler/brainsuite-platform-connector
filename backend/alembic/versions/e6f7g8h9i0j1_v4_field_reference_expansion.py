"""v4 field reference expansion - all platforms

Revision ID: e6f7g8h9i0j1
Revises: d5e6f7g8h9i0
Create Date: 2026-02-20
"""
from alembic import op
import sqlalchemy as sa

revision = "e6f7g8h9i0j1"
down_revision = "d5e6f7g8h9i0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    meta_cols = [
        ("account_name", sa.String(1000)),
        ("creative_name", sa.String(1000)),
        ("body", sa.Text()),
        ("title", sa.String(1000)),
        ("description", sa.Text()),
        ("call_to_action_type", sa.String(255)),
        ("link_url", sa.Text()),
        ("image_url", sa.Text()),
        ("video_id", sa.String(255)),
        ("instagram_permalink_url", sa.Text()),
        ("post_link", sa.Text()),
        ("instagram_actor_id", sa.String(255)),
        ("branded_content_sponsor_page_id", sa.String(255)),
        ("creative_width_px", sa.Integer()),
        ("creative_height_px", sa.Integer()),
        ("video_length_sec", sa.Float()),
        ("publisher_platform", sa.String(100)),
        ("platform_position", sa.String(100)),
        ("product_id", sa.String(255)),
        ("media_asset_url", sa.Text()),
        ("unique_inline_link_clicks", sa.Integer()),
        ("unique_outbound_clicks", sa.Integer()),
        ("unique_outbound_clicks_ctr", sa.Float()),
        ("video_3_sec_watched", sa.Integer()),
        ("unique_video_view_15_sec", sa.Integer()),
        ("cost_per_unique_video_view_15_sec", sa.Numeric(18, 4)),
        ("quality_ranking", sa.String(100)),
        ("engagement_rate_ranking", sa.String(100)),
        ("conversion_rate_ranking", sa.String(100)),
        ("creative_fatigue", sa.String(100)),
        ("mobile_app_install", sa.Integer()),
        ("cost_per_mobile_app_install", sa.Numeric(18, 4)),
        ("mobile_app_purchase", sa.Integer()),
        ("mobile_app_purchase_value", sa.Numeric(18, 4)),
        ("mobile_app_purchase_roas", sa.Float()),
        ("offline_purchase", sa.Integer()),
        ("offline_purchase_value", sa.Numeric(18, 4)),
        ("cost_per_offline_purchase", sa.Numeric(18, 4)),
        ("offline_lead", sa.Integer()),
        ("messaging_conversation_started_7d", sa.Integer()),
        ("cost_per_messaging_conversation_started", sa.Numeric(18, 4)),
        ("on_facebook_purchase", sa.Integer()),
        ("on_facebook_purchase_value", sa.Numeric(18, 4)),
        ("on_facebook_lead", sa.Integer()),
        ("cost_per_on_facebook_lead", sa.Numeric(18, 4)),
    ]
    for col_name, col_type in meta_cols:
        op.add_column("meta_raw_performance", sa.Column(col_name, col_type, nullable=True))

    tiktok_cols = [
        ("campaign_budget_mode", sa.String(100)),
        ("campaign_status", sa.String(100)),
        ("adgroup_status", sa.String(100)),
        ("creative_asset_url", sa.Text()),
        ("post_link", sa.Text()),
        ("call_to_action", sa.String(255)),
        ("video_source_url", sa.Text()),
        ("video_duration_sec", sa.Float()),
        ("publisher", sa.String(100)),
        ("placement_type", sa.String(100)),
        ("tiktok_creator_auth_code", sa.String(255)),
        ("avg_7_day_frequency", sa.Float()),
        ("gross_impression", sa.Integer()),
        ("gross_reach", sa.Integer()),
        ("total_interactive_add_on_clicks", sa.Integer()),
        ("total_interactive_add_on_impressions", sa.Integer()),
        ("real_time_conversion_rate", sa.Float()),
        ("app_install", sa.Integer()),
        ("cost_per_app_install", sa.Numeric(18, 4)),
        ("unique_app_install", sa.Integer()),
        ("app_event_purchase", sa.Integer()),
        ("app_event_purchase_value", sa.Numeric(18, 4)),
        ("cost_per_purchase", sa.Numeric(18, 4)),
        ("app_event_generate_lead", sa.Integer()),
        ("cost_per_lead", sa.Numeric(18, 4)),
        ("page_event_complete_payment", sa.Integer()),
        ("page_event_complete_payment_value", sa.Numeric(18, 4)),
        ("page_event_complete_payment_roas", sa.Float()),
        ("cost_per_page_event_complete_payment", sa.Numeric(18, 4)),
        ("page_event_subscribe", sa.Integer()),
        ("page_event_view_content", sa.Integer()),
        ("onsite_form_submit", sa.Integer()),
        ("cost_per_onsite_form_submit", sa.Numeric(18, 4)),
        ("onsite_purchase", sa.Integer()),
        ("onsite_purchase_value", sa.Numeric(18, 4)),
        ("live_views", sa.Integer()),
        ("live_unique_views", sa.Integer()),
        ("live_product_clicks", sa.Integer()),
        ("live_add_to_cart", sa.Integer()),
        ("live_purchase", sa.Integer()),
        ("live_purchase_value", sa.Numeric(18, 4)),
        ("secondary_goal_result", sa.Integer()),
        ("cost_per_secondary_goal_result", sa.Numeric(18, 4)),
        ("secondary_goal_result_rate", sa.Float()),
    ]
    for col_name, col_type in tiktok_cols:
        op.add_column("tiktok_raw_performance", sa.Column(col_name, col_type, nullable=True))

    youtube_cols = [
        ("ad_network_type", sa.String(100)),
        ("ad_format_type", sa.String(100)),
        ("youtube_earned_views", sa.Integer()),
        ("search_impression_share", sa.Float()),
        ("search_rank_lost_impression_share", sa.Float()),
        ("search_budget_lost_impression_share", sa.Float()),
        ("video_30s_views", sa.Integer()),
        ("video_duration_sec_derived", sa.Float()),
    ]
    for col_name, col_type in youtube_cols:
        op.add_column("youtube_raw_performance", sa.Column(col_name, col_type, nullable=True))

    harmonized_cols = [
        ("app_installs", sa.Integer()),
        ("cost_per_install", sa.Numeric(18, 4)),
        ("in_app_purchases", sa.Integer()),
        ("in_app_purchase_value", sa.Numeric(18, 4)),
        ("in_app_purchase_roas", sa.Float()),
        ("subscribe", sa.Integer()),
        ("offline_purchases", sa.Integer()),
        ("offline_purchase_value", sa.Numeric(18, 4)),
        ("messaging_conversations_started", sa.Integer()),
        ("estimated_ad_recallers", sa.Integer()),
        ("estimated_ad_recall_rate", sa.Float()),
        ("quality_ranking", sa.String(100)),
        ("engagement_rate_ranking", sa.String(100)),
        ("conversion_rate_ranking", sa.String(100)),
        ("creative_fatigue", sa.String(100)),
        ("unique_clicks", sa.Integer()),
        ("unique_ctr", sa.Float()),
        ("inline_link_clicks", sa.Integer()),
        ("inline_link_click_ctr", sa.Float()),
        ("video_3_sec_watched", sa.Integer()),
        ("video_30_sec_watched", sa.Integer()),
    ]
    for col_name, col_type in harmonized_cols:
        op.add_column("harmonized_performance", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    meta_cols = [
        "account_name", "creative_name", "body", "title", "description",
        "call_to_action_type", "link_url", "image_url", "video_id",
        "instagram_permalink_url", "post_link", "instagram_actor_id",
        "branded_content_sponsor_page_id", "creative_width_px", "creative_height_px",
        "video_length_sec", "publisher_platform", "platform_position", "product_id",
        "media_asset_url", "unique_inline_link_clicks", "unique_outbound_clicks",
        "unique_outbound_clicks_ctr", "video_3_sec_watched", "unique_video_view_15_sec",
        "cost_per_unique_video_view_15_sec", "quality_ranking", "engagement_rate_ranking",
        "conversion_rate_ranking", "creative_fatigue", "mobile_app_install",
        "cost_per_mobile_app_install", "mobile_app_purchase", "mobile_app_purchase_value",
        "mobile_app_purchase_roas", "offline_purchase", "offline_purchase_value",
        "cost_per_offline_purchase", "offline_lead", "messaging_conversation_started_7d",
        "cost_per_messaging_conversation_started", "on_facebook_purchase",
        "on_facebook_purchase_value", "on_facebook_lead", "cost_per_on_facebook_lead",
    ]
    for col_name in meta_cols:
        op.drop_column("meta_raw_performance", col_name)

    tiktok_cols = [
        "campaign_budget_mode", "campaign_status", "adgroup_status",
        "creative_asset_url", "post_link", "call_to_action", "video_source_url",
        "video_duration_sec", "publisher", "placement_type", "tiktok_creator_auth_code",
        "avg_7_day_frequency", "gross_impression", "gross_reach",
        "total_interactive_add_on_clicks", "total_interactive_add_on_impressions",
        "real_time_conversion_rate", "app_install", "cost_per_app_install",
        "unique_app_install", "app_event_purchase", "app_event_purchase_value",
        "cost_per_purchase", "app_event_generate_lead", "cost_per_lead",
        "page_event_complete_payment", "page_event_complete_payment_value",
        "page_event_complete_payment_roas", "cost_per_page_event_complete_payment",
        "page_event_subscribe", "page_event_view_content", "onsite_form_submit",
        "cost_per_onsite_form_submit", "onsite_purchase", "onsite_purchase_value",
        "live_views", "live_unique_views", "live_product_clicks", "live_add_to_cart",
        "live_purchase", "live_purchase_value", "secondary_goal_result",
        "cost_per_secondary_goal_result", "secondary_goal_result_rate",
    ]
    for col_name in tiktok_cols:
        op.drop_column("tiktok_raw_performance", col_name)

    youtube_cols = [
        "ad_network_type", "ad_format_type", "youtube_earned_views",
        "search_impression_share", "search_rank_lost_impression_share",
        "search_budget_lost_impression_share", "video_30s_views",
        "video_duration_sec_derived",
    ]
    for col_name in youtube_cols:
        op.drop_column("youtube_raw_performance", col_name)

    harmonized_cols = [
        "app_installs", "cost_per_install", "in_app_purchases",
        "in_app_purchase_value", "in_app_purchase_roas", "subscribe",
        "offline_purchases", "offline_purchase_value", "messaging_conversations_started",
        "estimated_ad_recallers", "estimated_ad_recall_rate", "quality_ranking",
        "engagement_rate_ranking", "conversion_rate_ranking", "creative_fatigue",
        "unique_clicks", "unique_ctr", "inline_link_clicks", "inline_link_click_ctr",
        "video_3_sec_watched", "video_30_sec_watched",
    ]
    for col_name in harmonized_cols:
        op.drop_column("harmonized_performance", col_name)
