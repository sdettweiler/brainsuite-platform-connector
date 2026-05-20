"""Add width_px/height_px to creative_assets and dv360_raw_performance; normalize asset_format

Revision ID: aa1b2c3d4e5f
Revises: z8a9b1c2d3e5
Create Date: 2026-05-20

Adds width_px and height_px dimension columns to creative_assets and dv360_raw_performance.
Backfills creative_assets.asset_format to normalized VIDEO/CAROUSEL/IMAGE values so the
frontend can use strict === 'VIDEO' checks again (SINGLE_VIDEO → VIDEO, WxH → IMAGE, etc).
"""
from alembic import op
import sqlalchemy as sa

revision = "aa1b2c3d4e5f"
down_revision = "z8a9b1c2d3e5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("creative_assets", sa.Column("width_px", sa.Integer(), nullable=True))
    op.add_column("creative_assets", sa.Column("height_px", sa.Integer(), nullable=True))

    op.add_column("dv360_raw_performance", sa.Column("width_px", sa.Integer(), nullable=True))
    op.add_column("dv360_raw_performance", sa.Column("height_px", sa.Integer(), nullable=True))

    op.execute("""
        UPDATE creative_assets SET asset_format = CASE
            WHEN asset_format ILIKE '%VIDEO%' THEN 'VIDEO'
            WHEN asset_format ILIKE '%CAROUSEL%' OR asset_format ILIKE '%COLLECTION%' THEN 'CAROUSEL'
            WHEN asset_format IS NOT NULL AND asset_format NOT IN ('VIDEO', 'CAROUSEL', 'IMAGE') THEN 'IMAGE'
            ELSE asset_format
        END
    """)


def downgrade():
    op.drop_column("dv360_raw_performance", "height_px")
    op.drop_column("dv360_raw_performance", "width_px")
    op.drop_column("creative_assets", "height_px")
    op.drop_column("creative_assets", "width_px")
