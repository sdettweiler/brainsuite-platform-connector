"""Add last_heartbeat_at to background_jobs for liveness detection

Revision ID: hb9a8b7c6d5e4
Revises: z8a9b1c2d3e5
Create Date: 2026-05-22

Allows startup hook and periodic stale detector to distinguish live jobs
(fresh heartbeat) from dead jobs (stale/missing heartbeat) without blindly
interrupting everything on restart.
"""
from alembic import op
import sqlalchemy as sa

revision = "hb9a8b7c6d5e4"
down_revision = "z8a9b1c2d3e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "background_jobs",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("background_jobs", "last_heartbeat_at")
