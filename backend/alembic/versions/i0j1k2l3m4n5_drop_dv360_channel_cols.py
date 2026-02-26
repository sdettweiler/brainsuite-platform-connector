"""drop_dv360_channel_cols

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-02-26 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i0j1k2l3m4n5"
down_revision: Union[str, None] = "h9i0j1k2l3m4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("dv360_raw_performance", "channel_id")
    op.drop_column("dv360_raw_performance", "channel_type")
    op.drop_column("dv360_raw_performance", "channel_name")


def downgrade() -> None:
    op.add_column("dv360_raw_performance", sa.Column("channel_name", sa.String(500), nullable=True))
    op.add_column("dv360_raw_performance", sa.Column("channel_type", sa.String(100), nullable=True))
    op.add_column("dv360_raw_performance", sa.Column("channel_id", sa.String(255), nullable=True))
