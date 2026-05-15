"""Phase 22: add composite index on asset_metadata_values(field_id, value) for metadata autocomplete (DASH-01)

Revision ID: e8f9a0b1c2d3
Revises: d2e3f4a5b6c7
Create Date: 2026-05-15

Chains onto down_revision='d2e3f4a5b6c7' (background_jobs_schema — most recent v1.3 head).

DEBT-01 note: The project has multiple Alembic heads. This migration chains onto
d2e3f4a5b6c7 specifically. To apply only this migration, run:
  alembic upgrade e8f9a0b1c2d3
Do NOT use 'alembic upgrade head' if multiple heads are unresolved (DEBT-01).

The composite index on (field_id, value) supports efficient DISTINCT autocomplete
lookups: SELECT DISTINCT value FROM asset_metadata_values WHERE field_id = ?
uses an index range scan instead of a full table scan.

Per D-13: this index was referenced in STATE.md as 'Phase 20 migration' but was
never actually added in Phase 20. Phase 22 owns this migration.
"""
from alembic import op


revision = "e8f9a0b1c2d3"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_asset_metadata_values_field_value",
        "asset_metadata_values",
        ["field_id", "value"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_asset_metadata_values_field_value",
        table_name="asset_metadata_values",
    )
