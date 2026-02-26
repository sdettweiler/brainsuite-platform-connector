"""widen harmonized publisher_platform and platform_position to 500

Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
Create Date: 2026-02-26 16:50:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "h9i0j1k2l3m4"
down_revision = "g8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("harmonized_performance", "publisher_platform", type_=sa.String(500), existing_type=sa.String(100), existing_nullable=False, existing_server_default="")
    op.alter_column("harmonized_performance", "platform_position", type_=sa.String(500), existing_type=sa.String(100), existing_nullable=False, existing_server_default="")


def downgrade() -> None:
    op.alter_column("harmonized_performance", "publisher_platform", type_=sa.String(100), existing_type=sa.String(500), existing_nullable=False, existing_server_default="")
    op.alter_column("harmonized_performance", "platform_position", type_=sa.String(100), existing_type=sa.String(500), existing_nullable=False, existing_server_default="")
