"""add_dv360_raw_performance

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-24 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dv360_raw_performance',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('platform_connection_id', UUID(as_uuid=True), sa.ForeignKey('platform_connections.id'), nullable=False),
        sa.Column('sync_job_id', UUID(as_uuid=True), sa.ForeignKey('sync_jobs.id'), nullable=True),
        sa.Column('report_date', sa.Date, nullable=False),
        sa.Column('ad_account_id', sa.String(255), nullable=False),
        sa.Column('advertiser_id', sa.String(255), nullable=True),
        sa.Column('advertiser_name', sa.String(1000), nullable=True),
        sa.Column('campaign_id', sa.String(255), nullable=True),
        sa.Column('campaign_name', sa.String(1000), nullable=True),
        sa.Column('insertion_order_id', sa.String(255), nullable=True),
        sa.Column('insertion_order_name', sa.String(1000), nullable=True),
        sa.Column('line_item_id', sa.String(255), nullable=True),
        sa.Column('line_item_name', sa.String(1000), nullable=True),
        sa.Column('line_item_type', sa.String(255), nullable=True),
        sa.Column('creative_id', sa.String(255), nullable=True),
        sa.Column('creative_name', sa.String(1000), nullable=True),
        sa.Column('creative_type', sa.String(100), nullable=True),
        sa.Column('creative_source', sa.String(255), nullable=True),
        sa.Column('ad_id', sa.String(255), nullable=False),
        sa.Column('ad_name', sa.String(1000), nullable=True),
        sa.Column('ad_type', sa.String(100), nullable=True),
        sa.Column('exchange', sa.String(255), nullable=True),
        sa.Column('environment', sa.String(100), nullable=True),
        sa.Column('thumbnail_url', sa.Text, nullable=True),
        sa.Column('asset_url', sa.Text, nullable=True),
        sa.Column('video_duration_seconds', sa.Float, nullable=True),
        sa.Column('asset_format', sa.String(50), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True),
        sa.Column('spend', sa.Numeric(18, 4), nullable=True),
        sa.Column('impressions', sa.Integer, nullable=True),
        sa.Column('clicks', sa.Integer, nullable=True),
        sa.Column('ctr', sa.Float, nullable=True),
        sa.Column('cpm', sa.Numeric(18, 4), nullable=True),
        sa.Column('cpc', sa.Numeric(18, 4), nullable=True),
        sa.Column('total_media_cost', sa.Numeric(18, 4), nullable=True),
        sa.Column('billable_impressions', sa.Integer, nullable=True),
        sa.Column('active_view_measurable_impressions', sa.Integer, nullable=True),
        sa.Column('active_view_viewable_impressions', sa.Integer, nullable=True),
        sa.Column('active_view_viewability', sa.Float, nullable=True),
        sa.Column('reach', sa.Integer, nullable=True),
        sa.Column('frequency', sa.Float, nullable=True),
        sa.Column('video_views', sa.Integer, nullable=True),
        sa.Column('video_plays', sa.Integer, nullable=True),
        sa.Column('video_completions', sa.Integer, nullable=True),
        sa.Column('video_first_quartile', sa.Integer, nullable=True),
        sa.Column('video_midpoint', sa.Integer, nullable=True),
        sa.Column('video_third_quartile', sa.Integer, nullable=True),
        sa.Column('video_completion_rate', sa.Float, nullable=True),
        sa.Column('video_view_rate', sa.Float, nullable=True),
        sa.Column('trueview_views', sa.Integer, nullable=True),
        sa.Column('companion_impressions', sa.Integer, nullable=True),
        sa.Column('companion_clicks', sa.Integer, nullable=True),
        sa.Column('total_conversions', sa.Float, nullable=True),
        sa.Column('post_click_conversions', sa.Float, nullable=True),
        sa.Column('post_view_conversions', sa.Float, nullable=True),
        sa.Column('conversion_value', sa.Numeric(18, 4), nullable=True),
        sa.Column('roas', sa.Float, nullable=True),
        sa.Column('cost_per_conversion', sa.Numeric(18, 4), nullable=True),
        sa.Column('engagements', sa.Integer, nullable=True),
        sa.Column('engagement_rate', sa.Float, nullable=True),
        sa.Column('rich_media_interactions', sa.Integer, nullable=True),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('is_validated', sa.Boolean, server_default=sa.text('false')),
        sa.Column('is_processed', sa.Boolean, server_default=sa.text('false')),
        sa.UniqueConstraint('platform_connection_id', 'report_date', 'ad_id', 'ad_account_id', name='uq_dv360_daily_ad'),
    )
    op.create_index('ix_dv360_raw_date_account', 'dv360_raw_performance', ['report_date', 'ad_account_id'])
    op.create_index('ix_dv360_raw_ad_id', 'dv360_raw_performance', ['ad_id'])


def downgrade() -> None:
    op.drop_index('ix_dv360_raw_ad_id', table_name='dv360_raw_performance')
    op.drop_index('ix_dv360_raw_date_account', table_name='dv360_raw_performance')
    op.drop_table('dv360_raw_performance')
