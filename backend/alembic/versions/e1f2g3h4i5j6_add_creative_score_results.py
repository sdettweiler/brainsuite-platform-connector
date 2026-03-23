"""add creative_score_results table and drop ace_score columns

Revision ID: e1f2g3h4i5j6
Revises: k2l3m4n5o6p7
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e1f2g3h4i5j6"
down_revision = "k2l3m4n5o6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the creative_score_results table
    op.create_table(
        "creative_score_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "creative_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("creative_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("scoring_status", sa.String(50), nullable=False, server_default="UNSCORED"),
        sa.Column("brainsuite_job_id", sa.String(255), nullable=True),
        sa.Column("total_score", sa.Float, nullable=True),
        sa.Column("total_rating", sa.String(50), nullable=True),
        sa.Column("score_dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_reason", sa.Text, nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("creative_asset_id", name="uq_score_per_asset"),
    )

    # Indexes for common query patterns
    op.create_index("ix_score_results_status", "creative_score_results", ["scoring_status"])
    op.create_index("ix_score_results_asset", "creative_score_results", ["creative_asset_id"])

    # Drop the legacy BrainSuite dummy columns from creative_assets
    op.drop_column("creative_assets", "ace_score")
    op.drop_column("creative_assets", "ace_score_confidence")
    op.drop_column("creative_assets", "brainsuite_metadata")


def downgrade() -> None:
    # Re-add the dropped columns
    op.add_column(
        "creative_assets",
        sa.Column("ace_score", sa.Float, nullable=True),
    )
    op.add_column(
        "creative_assets",
        sa.Column("ace_score_confidence", sa.String(50), nullable=True),
    )
    op.add_column(
        "creative_assets",
        sa.Column("brainsuite_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Drop the scoring table and its indexes
    op.drop_index("ix_score_results_asset", table_name="creative_score_results")
    op.drop_index("ix_score_results_status", table_name="creative_score_results")
    op.drop_table("creative_score_results")
