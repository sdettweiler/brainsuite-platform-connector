"""Phase 23: add composite index on creative_assets(organization_id, asset_format, video_duration) for duration bounds + filter (DASH-03)

Revision ID: a9b0c1d2e3f4
Revises: f8a2b3c4d5e6
Create Date: 2026-05-18

Chains onto down_revision='f8a2b3c4d5e6' (add_job_params — current alembic head as of May 15 2026).

Resolves RESEARCH.md Open Question Q4: bounds query performance at scale.

The composite index (organization_id, asset_format, video_duration) supports BOTH:
  - MIN/MAX aggregation in GET /dashboard/duration-bounds
  - BETWEEN range filter in GET /dashboard/assets when duration_min/duration_max are set
Without this index, both queries would do a sequential scan over all creative_assets for the org
on every dashboard load with active video filtering.

Column order matches selectivity:
  1. organization_id — high cardinality, ALWAYS in WHERE (T-23-01)
  2. asset_format — low cardinality (3 values), ALWAYS filtered to 'VIDEO' for duration queries
  3. video_duration — range column (BETWEEN / MIN / MAX); allows index range scan

Per CONTEXT.md canonical_refs: the video_duration COLUMN already exists (no migration needed for that).
This migration adds only the INDEX — a separate lightweight schema change.
"""
from alembic import op


revision = "a9b0c1d2e3f4"
down_revision = "f8a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_creative_assets_org_format_duration",
        "creative_assets",
        ["organization_id", "asset_format", "video_duration"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_creative_assets_org_format_duration",
        table_name="creative_assets",
    )
