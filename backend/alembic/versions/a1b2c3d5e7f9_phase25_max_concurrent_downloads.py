"""Phase 25 (PERF-02): add max_concurrent_downloads (Integer, NOT NULL, default 3) to system_config.

Revision ID: a1b2c3d5e7f9
Revises: a9b0c1d2e3f4
Create Date: 2026-05-18

Adds one column to system_config for Phase 25 download concurrency control:
  max_concurrent_downloads (Integer, NOT NULL, default 3) — max parallel downloads (1-10)

Chains onto down_revision='a9b0c1d2e3f4' (Phase 23 duration index — most recent v1.4 ship line head).
Phase 26 DEBT-01 will fold this migration into the linear Alembic chain.

server_default="3" ensures existing rows receive the value during ADD COLUMN;
nullable=False is safe because the server default is applied at backfill time.
"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d5e7f9"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "max_concurrent_downloads",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
    )


def downgrade() -> None:
    op.drop_column("system_config", "max_concurrent_downloads")
