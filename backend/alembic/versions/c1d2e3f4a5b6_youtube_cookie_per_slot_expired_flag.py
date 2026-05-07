"""youtube_cookie_per_slot_expired_flag

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-05-07

Adds a separate runtime-expired flag for the backup cookie slot so primary
and backup expiry are tracked independently. The existing
youtube_cookies_runtime_expired column becomes primary-only.
"""
from alembic import op
import sqlalchemy as sa

revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "youtube_cookies_backup_runtime_expired",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("system_config", "youtube_cookies_backup_runtime_expired")
