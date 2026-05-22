"""Add last_heartbeat_at to background_jobs for liveness detection

Revision ID: a1b2c3d4e5f6
Revises: z8a9b1c2d3e5
Create Date: 2026-05-22

Allows startup hook and periodic stale detector to distinguish live jobs
(fresh heartbeat) from dead jobs (stale/missing heartbeat) without blindly
interrupting everything on restart.
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
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
