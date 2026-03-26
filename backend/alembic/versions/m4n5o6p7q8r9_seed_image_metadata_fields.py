"""seed image-specific MetadataField rows per organization

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime

revision = "m4n5o6p7q8r9"
down_revision = "l3m4n5o6p7q8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()

    now = datetime.utcnow()

    for org_id_row in orgs:
        org_id = str(org_id_row[0])

        # Field 1: brainsuite_intended_messages (TEXT, image-only)
        conn.execute(sa.text("""
            INSERT INTO metadata_fields
                (id, organization_id, name, label, field_type, is_required, default_value, is_active, sort_order, created_at, updated_at)
            VALUES
                (:id, :org_id, :name, :label, :ftype, :required, :default_val, true, :sort, :now, :now)
            ON CONFLICT DO NOTHING
        """), {
            "id": str(uuid.uuid4()),
            "org_id": org_id,
            "name": "brainsuite_intended_messages",
            "label": "Intended Messages",
            "ftype": "TEXT",
            "required": False,
            "default_val": None,
            "sort": 8,
            "now": now,
        })

        # Field 2: brainsuite_iconic_color_scheme (SELECT, image-only)
        field_id = str(uuid.uuid4())
        conn.execute(sa.text("""
            INSERT INTO metadata_fields
                (id, organization_id, name, label, field_type, is_required, default_value, is_active, sort_order, created_at, updated_at)
            VALUES
                (:id, :org_id, :name, :label, :ftype, :required, :default_val, true, :sort, :now, :now)
            ON CONFLICT DO NOTHING
        """), {
            "id": field_id,
            "org_id": org_id,
            "name": "brainsuite_iconic_color_scheme",
            "label": "Iconic Color Scheme",
            "ftype": "SELECT",
            "required": False,
            "default_val": "manufactory",
            "sort": 9,
            "now": now,
        })

        # Seed the allowed value for brainsuite_iconic_color_scheme
        # Only "manufactory" confirmed from docs/BRAINSUITE_API.md (spike pending credentials)
        conn.execute(sa.text("""
            INSERT INTO metadata_field_values
                (id, field_id, value, label, sort_order, created_at)
            VALUES
                (:id, :field_id, :value, :label, :sort, :now)
        """), {
            "id": str(uuid.uuid4()),
            "field_id": field_id,
            "value": "manufactory",
            "label": "Manufactory",
            "sort": 0,
            "now": now,
        })


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        DELETE FROM metadata_field_values
        WHERE field_id IN (
            SELECT id FROM metadata_fields
            WHERE name IN ('brainsuite_intended_messages', 'brainsuite_iconic_color_scheme')
        )
    """))
    conn.execute(sa.text("""
        DELETE FROM metadata_fields
        WHERE name IN ('brainsuite_intended_messages', 'brainsuite_iconic_color_scheme')
    """))
