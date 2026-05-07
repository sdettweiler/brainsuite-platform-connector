"""Add youtube_cookies_runtime_expired flag to system_config

Revision ID: z8a9b1c2d3e5
Revises: y7z8a1b2c3d4
Create Date: 2026-05-07

Tracks whether YouTube cookies were rejected at runtime (by yt-dlp), separate
from timestamp-based expiry. Set True when _CookiesExpiredError fires during
download; reset to False when new cookies are saved via the admin UI.
"""
from alembic import op
import sqlalchemy as sa

revision = "z8a9b1c2d3e5"
down_revision = "y7z8a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "youtube_cookies_runtime_expired",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("system_config", "youtube_cookies_runtime_expired")
