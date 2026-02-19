"""add asset_url to meta_raw_performance

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4d5e6f7g8h9'
down_revision = 'b3c4d5e6f7g8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('meta_raw_performance', sa.Column('asset_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('meta_raw_performance', 'asset_url')
