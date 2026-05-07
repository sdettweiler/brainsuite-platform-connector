"""youtube_cookie_download_stats

Revision ID: b0c1d2e3f4a5
Revises: z8a9b1c2d3e5
Create Date: 2026-05-07

Adds per-cookie-session download counter and refresh timestamp to system_config.
These are reset whenever cookies are updated and used to report stats in the
COOKIE_FAILED notification ("expired after X videos and Y days").
"""
from alembic import op
import sqlalchemy as sa

revision = "b0c1d2e3f4a5"
down_revision = "b1c2d3e4f5g6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column("youtube_cookies_download_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "system_config",
        sa.Column("youtube_cookies_refreshed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("system_config", "youtube_cookies_refreshed_at")
    op.drop_column("system_config", "youtube_cookies_download_count")
