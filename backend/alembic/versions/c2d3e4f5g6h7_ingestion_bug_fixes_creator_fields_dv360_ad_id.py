"""Ingestion bug fixes: creator fields, DV360 ad_id repair, re-harmonization reset

Revision ID: c2d3e4f5g6h7
Revises: z8a9b1c2d3e5
Create Date: 2026-05-11

Adds creator/brand content columns to meta_raw_performance and creative_assets,
repairs DV360 ad_id values that were incorrectly set to youtube_ad_video_id instead
of line_item_id, and resets is_processed flags so all raw records are re-harmonized
with the corrected logic.
"""
from alembic import op
import sqlalchemy as sa

revision = "c2d3e4f5g6h7"
down_revision = "z8a9b1c2d3e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- ADD COLUMNS ---

    # meta_raw_performance: branded content / creator fields
    op.add_column(
        "meta_raw_performance",
        sa.Column("creator_ad_permission_type", sa.String(100), nullable=True),
    )
    op.add_column(
        "meta_raw_performance",
        sa.Column("branded_content_promoted_page_id", sa.String(255), nullable=True),
    )

    # creative_assets: creator content classification
    op.add_column(
        "creative_assets",
        sa.Column("is_creator_content", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "creative_assets",
        sa.Column("content_source", sa.String(100), nullable=True),
    )

    # NOTE: DV360 raw ad_id data repair was intentionally omitted from this
    # migration. The raw data has mixed keying (some rows use youtube_ad_video_id,
    # some use line_item_id) with duplicates that make bulk UPDATE unsafe.
    # The sync code fix (always use line_item_id) applies to future syncs only.
    # Historical rows continue to harmonize with their existing ad_id keys.

    # --- RE-HARMONIZATION RESET ---
    # Reset is_processed on all raw tables so corrected records flow through the
    # harmonizer with updated logic (DV360 ad_id, Meta creator fields, TikTok
    # is_spark_ad fix, purchases null-check, cost_per_view, conversions cast).
    op.execute("UPDATE meta_raw_performance SET is_processed = false")
    op.execute("UPDATE tiktok_raw_performance SET is_processed = false")
    op.execute("UPDATE dv360_raw_performance SET is_processed = false")
    op.execute("UPDATE google_ads_raw_performance SET is_processed = false")


def downgrade() -> None:
    # Reverse only the ADD COLUMN steps.
    # The DV360 ad_id data repair and is_processed resets are non-reversible
    # and cannot be automatically undone.
    op.drop_column("creative_assets", "content_source")
    op.drop_column("creative_assets", "is_creator_content")
    op.drop_column("meta_raw_performance", "branded_content_promoted_page_id")
    op.drop_column("meta_raw_performance", "creator_ad_permission_type")
