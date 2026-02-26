"""dv360_add_new_cols_drop_deprecated

Revision ID: g8h9i0j1k2l3
Revises: b2c3d4e5f6g7
Create Date: 2026-02-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'g8h9i0j1k2l3'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('dv360_raw_performance', sa.Column('ad_position', sa.String(100), nullable=True))
    op.add_column('dv360_raw_performance', sa.Column('advertiser_timezone', sa.String(100), nullable=True))
    op.add_column('dv360_raw_performance', sa.Column('channel_id', sa.String(255), nullable=True))
    op.add_column('dv360_raw_performance', sa.Column('channel_type', sa.String(100), nullable=True))
    op.add_column('dv360_raw_performance', sa.Column('channel_name', sa.String(500), nullable=True))
    op.add_column('dv360_raw_performance', sa.Column('io_goal_type', sa.String(255), nullable=True))
    op.add_column('dv360_raw_performance', sa.Column('youtube_ad_video_id', sa.String(255), nullable=True))
    op.add_column('dv360_raw_performance', sa.Column('media_type', sa.String(100), nullable=True))
    op.add_column('dv360_raw_performance', sa.Column('video_url', sa.Text, nullable=True))
    op.add_column('dv360_raw_performance', sa.Column('billable_cost', sa.Numeric(18, 4), nullable=True))
    op.add_column('dv360_raw_performance', sa.Column('average_impression_frequency', sa.Float, nullable=True))

    op.drop_column('dv360_raw_performance', 'exchange')
    op.drop_column('dv360_raw_performance', 'rich_media_interactions')


def downgrade() -> None:
    op.add_column('dv360_raw_performance', sa.Column('exchange', sa.String(255), nullable=True))
    op.add_column('dv360_raw_performance', sa.Column('rich_media_interactions', sa.Integer, nullable=True))

    op.drop_column('dv360_raw_performance', 'average_impression_frequency')
    op.drop_column('dv360_raw_performance', 'billable_cost')
    op.drop_column('dv360_raw_performance', 'video_url')
    op.drop_column('dv360_raw_performance', 'media_type')
    op.drop_column('dv360_raw_performance', 'youtube_ad_video_id')
    op.drop_column('dv360_raw_performance', 'io_goal_type')
    op.drop_column('dv360_raw_performance', 'channel_name')
    op.drop_column('dv360_raw_performance', 'channel_type')
    op.drop_column('dv360_raw_performance', 'channel_id')
    op.drop_column('dv360_raw_performance', 'advertiser_timezone')
    op.drop_column('dv360_raw_performance', 'ad_position')
