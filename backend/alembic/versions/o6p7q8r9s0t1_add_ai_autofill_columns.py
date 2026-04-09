"""Add AI auto-fill columns to metadata_fields, widen asset_metadata_values.value, create ai_inference_tracking.

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-04-01

Changes:
- metadata_fields: add auto_fill_enabled (Boolean, default false), auto_fill_type (String(50), nullable)
- asset_metadata_values: widen value column from String(500) to Text
- CREATE TABLE ai_inference_tracking with PENDING/COMPLETE/FAILED status, unique asset_id constraint
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from alembic import op

revision = "o6p7q8r9s0t1"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add auto_fill_enabled and auto_fill_type to metadata_fields
    op.add_column(
        "metadata_fields",
        sa.Column("auto_fill_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "metadata_fields",
        sa.Column("auto_fill_type", sa.String(50), nullable=True),
    )

    # Widen asset_metadata_values.value from String(500) to Text
    op.alter_column(
        "asset_metadata_values",
        "value",
        existing_type=sa.String(500),
        type_=sa.Text(),
        existing_nullable=True,
    )

    # Create ai_inference_tracking table
    op.create_table(
        "ai_inference_tracking",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "asset_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("creative_assets.id"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "ai_inference_status",
            sa.String(20),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        "uq_ai_inference_asset", "ai_inference_tracking", ["asset_id"]
    )
    op.create_index(
        "ix_ai_inference_status", "ai_inference_tracking", ["ai_inference_status"]
    )


def downgrade() -> None:
    # Drop ai_inference_tracking table
    op.drop_index("ix_ai_inference_status", table_name="ai_inference_tracking")
    op.drop_constraint("uq_ai_inference_asset", "ai_inference_tracking", type_="unique")
    op.drop_table("ai_inference_tracking")

    # Revert asset_metadata_values.value back to String(500)
    op.alter_column(
        "asset_metadata_values",
        "value",
        existing_type=sa.Text(),
        type_=sa.String(500),
        existing_nullable=True,
    )

    # Drop auto_fill columns from metadata_fields
    op.drop_column("metadata_fields", "auto_fill_type")
    op.drop_column("metadata_fields", "auto_fill_enabled")
