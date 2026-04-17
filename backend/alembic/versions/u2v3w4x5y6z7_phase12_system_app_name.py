"""Phase 12: add brainsuite_apps.system_app_name, drop org_brainsuite_config.video/static_app_name

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = "u2v3w4x5y6z7"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("brainsuite_apps", sa.Column("system_app_name", sa.String(255), nullable=True))
    op.drop_column("org_brainsuite_config", "video_app_name")
    op.drop_column("org_brainsuite_config", "static_app_name")


def downgrade() -> None:
    op.add_column("org_brainsuite_config", sa.Column("video_app_name", sa.String(255), nullable=True))
    op.add_column("org_brainsuite_config", sa.Column("static_app_name", sa.String(255), nullable=True))
    op.drop_column("brainsuite_apps", "system_app_name")
