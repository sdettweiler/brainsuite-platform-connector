"""Superadmin scoring controls: global toggle + per-org quota

Revision ID: y7z8a1b2c3d4
Revises: x6y7z8a9b0c
Create Date: 2026-05-04

Adds:
  - system_config.scoring_enabled (bool, default True) — global auto-scoring toggle
  - org_brainsuite_config.scoring_quota (int, nullable) — per-org scored-asset cap
"""
from alembic import op
import sqlalchemy as sa

revision = "y7z8a1b2c3d4"
down_revision = "x6y7z8a9b0c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Global auto-scoring toggle (default True — existing behaviour preserved)
    op.add_column(
        "system_config",
        sa.Column("scoring_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )

    # Per-org scored-asset quota (NULL = unlimited)
    op.add_column(
        "org_brainsuite_config",
        sa.Column("scoring_quota", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("org_brainsuite_config", "scoring_quota")
    op.drop_column("system_config", "scoring_enabled")
