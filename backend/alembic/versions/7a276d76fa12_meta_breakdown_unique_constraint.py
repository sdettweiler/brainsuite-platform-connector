"""meta_breakdown_unique_constraint

Revision ID: 7a276d76fa12
Revises: e6f7g8h9i0j1
Create Date: 2026-02-20 14:47:03.655213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '7a276d76fa12'
down_revision: Union[str, None] = 'e6f7g8h9i0j1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_meta_daily_ad', 'meta_raw_performance', type_='unique')
    op.create_unique_constraint(
        'uq_meta_daily_ad_breakdown',
        'meta_raw_performance',
        ['platform_connection_id', 'report_date', 'ad_id', 'ad_account_id', 'publisher_platform', 'platform_position']
    )


def downgrade() -> None:
    op.drop_constraint('uq_meta_daily_ad_breakdown', 'meta_raw_performance', type_='unique')
    op.create_unique_constraint('uq_meta_daily_ad', 'meta_raw_performance', ['platform_connection_id', 'report_date', 'ad_id', 'ad_account_id'])
