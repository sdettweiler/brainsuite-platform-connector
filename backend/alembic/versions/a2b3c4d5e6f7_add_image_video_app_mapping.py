"""add image and video app mapping to platform connections

Revision ID: a2b3c4d5e6f7
Revises: 41dcacc7071c
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a2b3c4d5e6f7'
down_revision = '41dcacc7071c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('platform_connections',
        sa.Column('brainsuite_app_id_image', postgresql.UUID(as_uuid=True), sa.ForeignKey('brainsuite_apps.id'), nullable=True))
    op.add_column('platform_connections',
        sa.Column('brainsuite_app_id_video', postgresql.UUID(as_uuid=True), sa.ForeignKey('brainsuite_apps.id'), nullable=True))


def downgrade() -> None:
    op.drop_column('platform_connections', 'brainsuite_app_id_video')
    op.drop_column('platform_connections', 'brainsuite_app_id_image')
