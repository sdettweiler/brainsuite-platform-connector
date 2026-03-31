"""Fix endpoint_type for existing image score rows backfilled incorrectly to VIDEO.

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-03-26

The previous migration (l3m4n5o6p7q8) set endpoint_type = 'VIDEO' for ALL existing
rows. This was wrong for IMAGE assets — they should be STATIC_IMAGE (Meta) or
UNSUPPORTED (other platforms). This migration corrects those rows using a JOIN
against creative_assets to check platform + asset_format.
"""
from alembic import op


revision = "n5o6p7q8r9s0"
down_revision = "m4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix Meta IMAGE assets: VIDEO -> STATIC_IMAGE, also reset status to UNSCORED
    # so they get picked up by the scorer (they were never actually scored as video)
    op.execute("""
        UPDATE creative_score_results csr
        SET endpoint_type = 'STATIC_IMAGE',
            scoring_status = CASE
                WHEN scoring_status IN ('UNSCORED', 'PENDING', 'FAILED') THEN 'UNSCORED'
                ELSE scoring_status
            END
        FROM creative_assets ca
        WHERE ca.id = csr.creative_asset_id
          AND ca.asset_format = 'IMAGE'
          AND ca.platform = 'META'
          AND csr.endpoint_type = 'VIDEO'
    """)

    # Fix non-Meta IMAGE assets: VIDEO -> UNSUPPORTED, status -> UNSUPPORTED
    op.execute("""
        UPDATE creative_score_results csr
        SET endpoint_type = 'UNSUPPORTED',
            scoring_status = 'UNSUPPORTED'
        FROM creative_assets ca
        WHERE ca.id = csr.creative_asset_id
          AND ca.asset_format = 'IMAGE'
          AND ca.platform != 'META'
          AND csr.endpoint_type = 'VIDEO'
    """)


def downgrade() -> None:
    # Revert all IMAGE rows back to VIDEO (restores the incorrect state)
    op.execute("""
        UPDATE creative_score_results csr
        SET endpoint_type = 'VIDEO'
        FROM creative_assets ca
        WHERE ca.id = csr.creative_asset_id
          AND ca.asset_format = 'IMAGE'
    """)
