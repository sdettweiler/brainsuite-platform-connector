"""rename_youtube_to_google_ads

Revision ID: a1b2c3d4e5f6
Revises: 09fdc18ec8e1
Create Date: 2026-02-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '09fdc18ec8e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table('youtube_raw_performance', 'google_ads_raw_performance')

    op.execute("DROP INDEX IF EXISTS ix_youtube_raw_date_account")
    op.execute("DROP INDEX IF EXISTS ix_youtube_raw_ad_id")

    op.drop_constraint('uq_youtube_daily_ad', 'google_ads_raw_performance', type_='unique')
    op.create_unique_constraint(
        'uq_google_ads_daily_ad',
        'google_ads_raw_performance',
        ['platform_connection_id', 'report_date', 'ad_id', 'ad_account_id']
    )
    op.create_index('ix_google_ads_raw_date_account', 'google_ads_raw_performance', ['report_date', 'ad_account_id'])
    op.create_index('ix_google_ads_raw_ad_id', 'google_ads_raw_performance', ['ad_id'])

    op.execute("""
        UPDATE platform_connections
        SET platform = 'GOOGLE_ADS'
        WHERE platform = 'YOUTUBE'
    """)

    op.execute("""
        UPDATE creative_assets
        SET platform = 'GOOGLE_ADS'
        WHERE platform = 'YOUTUBE'
    """)

    op.execute("""
        UPDATE harmonized_performance
        SET platform = 'GOOGLE_ADS'
        WHERE platform = 'YOUTUBE'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE harmonized_performance
        SET platform = 'YOUTUBE'
        WHERE platform = 'GOOGLE_ADS'
    """)

    op.execute("""
        UPDATE creative_assets
        SET platform = 'YOUTUBE'
        WHERE platform = 'GOOGLE_ADS'
    """)

    op.execute("""
        UPDATE platform_connections
        SET platform = 'YOUTUBE'
        WHERE platform = 'GOOGLE_ADS'
    """)

    op.drop_index('ix_google_ads_raw_ad_id', table_name='google_ads_raw_performance')
    op.drop_index('ix_google_ads_raw_date_account', table_name='google_ads_raw_performance')
    op.drop_constraint('uq_google_ads_daily_ad', 'google_ads_raw_performance', type_='unique')
    op.create_unique_constraint(
        'uq_youtube_daily_ad',
        'google_ads_raw_performance',
        ['platform_connection_id', 'report_date', 'ad_id', 'ad_account_id']
    )
    op.create_index('ix_youtube_raw_ad_id', 'google_ads_raw_performance', ['ad_id'])
    op.create_index('ix_youtube_raw_date_account', 'google_ads_raw_performance', ['report_date', 'ad_account_id'])

    op.rename_table('google_ads_raw_performance', 'youtube_raw_performance')
