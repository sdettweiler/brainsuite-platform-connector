"""Add proxy configuration to system_config

Revision ID: a9b1c2d3e5f6
Revises: z8a9b1c2d3e5
Create Date: 2026-05-15

Adds two columns to system_config for residential proxy support (Phase 20):
  proxy_url_encrypted (Text, nullable=True) — Fernet-encrypted proxy URL including credentials
  proxy_enabled (Boolean, NOT NULL, default False) — toggle to enable/disable proxy for downloads

Both default to null/false: existing deployments are unaffected until ops explicitly enables.
"""
from alembic import op
import sqlalchemy as sa

revision = "a9b1c2d3e5f6"
down_revision = "z8a9b1c2d3e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "proxy_url_encrypted",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "proxy_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("system_config", "proxy_enabled")
    op.drop_column("system_config", "proxy_url_encrypted")
