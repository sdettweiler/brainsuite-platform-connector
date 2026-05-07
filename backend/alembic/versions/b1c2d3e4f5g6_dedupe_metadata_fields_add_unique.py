"""Deduplicate metadata_fields and add unique constraint on (org, name)

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f8
Create Date: 2026-05-07

Root cause: no unique constraint on (organization_id, name) allowed
two separate code paths (auth.py registration + w4x5y6z7a8b9 migration)
to both create brainsuite_intended_messages_language for the same org.

This migration:
1. For each duplicate (org_id, name) pair, keeps the field with the most
   associated values (oldest if tied), reassigns asset_metadata_values and
   field_mapping references, deletes duplicate field values and field rows.
2. Adds UNIQUE (organization_id, name) to prevent recurrence.
"""
from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5g6"
down_revision = "a1b2c3d4e5f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Find all (org, name) pairs that have more than one field row
    dupes = conn.execute(sa.text("""
        SELECT
            organization_id,
            name,
            array_agg(id::text ORDER BY
                (SELECT COUNT(*) FROM metadata_field_values WHERE field_id = mf.id) DESC,
                created_at ASC
            ) AS ids
        FROM metadata_fields mf
        GROUP BY organization_id, name
        HAVING COUNT(*) > 1
    """)).fetchall()

    for row in dupes:
        org_id, name, ids = row
        keep_id = ids[0]
        delete_ids = ids[1:]

        for del_id in delete_ids:
            # Reassign asset metadata values from the duplicate to the kept field
            conn.execute(sa.text(
                "UPDATE asset_metadata_values SET field_id = :keep WHERE field_id = :del"
            ), {"keep": keep_id, "del": del_id})

            # Reassign BrainSuite field mappings
            conn.execute(sa.text(
                "UPDATE org_brainsuite_field_mappings SET metadata_field_id = :keep WHERE metadata_field_id = :del"
            ), {"keep": keep_id, "del": del_id})

            # Drop the duplicate's allowed values, then the field row
            conn.execute(sa.text(
                "DELETE FROM metadata_field_values WHERE field_id = :del"
            ), {"del": del_id})
            conn.execute(sa.text(
                "DELETE FROM metadata_fields WHERE id = :del"
            ), {"del": del_id})

    op.create_unique_constraint(
        "uq_metadata_fields_org_name",
        "metadata_fields",
        ["organization_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_metadata_fields_org_name", "metadata_fields", type_="unique")
