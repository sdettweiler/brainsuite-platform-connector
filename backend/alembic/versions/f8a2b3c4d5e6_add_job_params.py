"""Add params JSONB column to background_jobs for retry support

Revision ID: f8a2b3c4d5e6
Revises: a9b1c2d3e5f6, d3e4f5g6h7i8, e8f9a0b1c2d3
Create Date: 2026-05-15

Adds params JSONB column to background_jobs table.
Stores original job invocation parameters so interrupted or failed jobs
can be retried via POST /jobs/{id}/retry without re-collecting inputs.

Merges all three current heads (a9b1c2d3e5f6, d3e4f5g6h7i8, e8f9a0b1c2d3)
into a single new head.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "f8a2b3c4d5e6"
down_revision = ("a9b1c2d3e5f6", "d3e4f5g6h7i8", "e8f9a0b1c2d3")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "background_jobs",
        sa.Column("params", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("background_jobs", "params")
