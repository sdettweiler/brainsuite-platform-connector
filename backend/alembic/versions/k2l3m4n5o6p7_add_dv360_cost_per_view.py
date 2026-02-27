"""add dv360 cost_per_view column

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-02-27
"""
from alembic import op
import sqlalchemy as sa

revision = "k2l3m4n5o6p7"
down_revision = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dv360_raw_performance",
        sa.Column("cost_per_view", sa.Numeric(18, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dv360_raw_performance", "cost_per_view")
