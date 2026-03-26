"""add endpoint_type column to creative_score_results and add UNSUPPORTED scoring status

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-03-26

Adds:
  - endpoint_type column (String(50), nullable, indexed) to creative_score_results
  - Backfills existing rows to endpoint_type = 'VIDEO' (all existing rows are video creatives)
  - Supports new scoring_status value 'UNSUPPORTED' (no schema change needed — scoring_status
    is already String(50), not a PostgreSQL ENUM type)
"""
from alembic import op
import sqlalchemy as sa

revision = "l3m4n5o6p7q8"
down_revision = "k2l3m4n5o6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add endpoint_type column
    op.add_column(
        "creative_score_results",
        sa.Column("endpoint_type", sa.String(50), nullable=True),
    )

    # Create index for efficient filtering in scoring batch queries
    op.create_index(
        "ix_score_results_endpoint_type",
        "creative_score_results",
        ["endpoint_type"],
    )

    # Backfill existing rows — all pre-Phase-5 rows are video creatives
    op.execute(
        "UPDATE creative_score_results SET endpoint_type = 'VIDEO' WHERE endpoint_type IS NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_score_results_endpoint_type", table_name="creative_score_results")
    op.drop_column("creative_score_results", "endpoint_type")
