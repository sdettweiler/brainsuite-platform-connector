"""add pending_at and submitted_at to creative_score_results

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-04-02

"""
from alembic import op
import sqlalchemy as sa

revision = 'p7q8r9s0t1u2'
down_revision = 'o6p7q8r9s0t1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('creative_score_results',
        sa.Column('pending_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('creative_score_results',
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('creative_score_results', 'submitted_at')
    op.drop_column('creative_score_results', 'pending_at')
