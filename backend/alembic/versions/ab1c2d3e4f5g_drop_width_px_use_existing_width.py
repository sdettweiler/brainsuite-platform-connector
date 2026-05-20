"""Drop duplicate width_px/height_px columns, add width/height to dv360_raw_performance

Revision ID: ab1c2d3e4f5g
Revises: aa1b2c3d4e5f
Create Date: 2026-05-20

creative_assets already had width/height from q8r9s0t1u2v3. My aa1b2c3d4e5f migration
added duplicate width_px/height_px columns. Drop the duplicates and add width/height
to dv360_raw_performance instead.
"""
from alembic import op
import sqlalchemy as sa

revision = "ab1c2d3e4f5g"
down_revision = "aa1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("creative_assets", "width_px")
    op.drop_column("creative_assets", "height_px")
    op.drop_column("dv360_raw_performance", "width_px")
    op.drop_column("dv360_raw_performance", "height_px")
    op.add_column("dv360_raw_performance", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("dv360_raw_performance", sa.Column("height", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("dv360_raw_performance", "height")
    op.drop_column("dv360_raw_performance", "width")
    op.add_column("dv360_raw_performance", sa.Column("height_px", sa.Integer(), nullable=True))
    op.add_column("dv360_raw_performance", sa.Column("width_px", sa.Integer(), nullable=True))
    op.add_column("creative_assets", sa.Column("height_px", sa.Integer(), nullable=True))
    op.add_column("creative_assets", sa.Column("width_px", sa.Integer(), nullable=True))
