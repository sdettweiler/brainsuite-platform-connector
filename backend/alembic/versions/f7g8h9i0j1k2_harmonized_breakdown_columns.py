"""add publisher_platform and platform_position to harmonized_performance

Revision ID: f7g8h9i0j1k2
Revises: e6f7g8h9i0j1
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa

revision = "f7g8h9i0j1k2"
down_revision = "7a276d76fa12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("harmonized_performance", sa.Column("publisher_platform", sa.String(100), nullable=True))
    op.add_column("harmonized_performance", sa.Column("platform_position", sa.String(100), nullable=True))

    op.drop_constraint("uq_harmonized_daily_ad", "harmonized_performance", type_="unique")

    op.create_unique_constraint(
        "uq_harmonized_daily_ad_breakdown",
        "harmonized_performance",
        ["asset_id", "platform_connection_id", "report_date", "ad_id", "ad_account_id", "publisher_platform", "platform_position"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_harmonized_daily_ad_breakdown", "harmonized_performance", type_="unique")

    op.create_unique_constraint(
        "uq_harmonized_daily_ad",
        "harmonized_performance",
        ["asset_id", "platform_connection_id", "report_date", "ad_id", "ad_account_id"],
    )

    op.drop_column("harmonized_performance", "platform_position")
    op.drop_column("harmonized_performance", "publisher_platform")
