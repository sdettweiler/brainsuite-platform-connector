"""add dv360 video_skips column

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-02-27
"""
from alembic import op
import sqlalchemy as sa

revision = "j1k2l3m4n5o6"
down_revision = "i0j1k2l3m4n5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dv360_raw_performance",
        sa.Column("video_skips", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dv360_raw_performance", "video_skips")
