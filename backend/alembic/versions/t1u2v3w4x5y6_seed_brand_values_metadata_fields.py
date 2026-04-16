"""seed brainsuite_brand_values and brainsuite_brand_values_language metadata fields per org

Revision ID: t1u2v3w4x5y6
Revises: s0t1u2v3w4x5
Create Date: 2026-04-16

Seeds brainsuite_brand_values (TEXT, sort_order=10) and brainsuite_brand_values_language
(SELECT, sort_order=11, 31 language options) for all existing organizations.
Idempotent on metadata_fields via ON CONFLICT DO NOTHING.
Fulfills FMAP-08 -- brand_values fields exist as default non-mandatory metadata for every org.
"""
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime

revision = "t1u2v3w4x5y6"
down_revision = "s0t1u2v3w4x5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()

    now = datetime.utcnow()

    fields_def = [
        ("brainsuite_brand_values", "Brand Values", "TEXT", False, None, 10),
        ("brainsuite_brand_values_language", "Brand Values Language", "SELECT", False, None, 11),
    ]

    # 31 language enum values -- exact match to f2g3h4i5j6k7 (D-03)
    language_values = [
        ("ar", "Arabic"),
        ("bg", "Bulgarian"),
        ("cs", "Czech"),
        ("da", "Danish"),
        ("de", "German"),
        ("el", "Greek"),
        ("en", "English"),
        ("es", "Spanish"),
        ("fi", "Finnish"),
        ("fr", "French"),
        ("he", "Hebrew"),
        ("hi", "Hindi"),
        ("hr", "Croatian"),
        ("hu", "Hungarian"),
        ("id", "Indonesian"),
        ("it", "Italian"),
        ("ja", "Japanese"),
        ("ko", "Korean"),
        ("ms", "Malay"),
        ("nl", "Dutch"),
        ("no", "Norwegian"),
        ("pl", "Polish"),
        ("pt", "Portuguese"),
        ("ro", "Romanian"),
        ("sk", "Slovak"),
        ("sl", "Slovenian"),
        ("sv", "Swedish"),
        ("th", "Thai"),
        ("tr", "Turkish"),
        ("vi", "Vietnamese"),
        ("zh", "Chinese"),
    ]

    for org_id_row in orgs:
        org_id = str(org_id_row[0])
        bvl_field_id = None

        for name, label, ftype, required, default, sort in fields_def:
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
                "name": name,
                "label": label,
                "ftype": ftype,
                "required": required,
                "default_val": default,
                "sort": sort,
                "now": now,
            })

            if name == "brainsuite_brand_values_language":
                bvl_field_id = field_id

        # Seed the 31 language values for brainsuite_brand_values_language
        # NOTE: No ON CONFLICT DO NOTHING -- metadata_field_values has no unique constraint
        # This matches the exact pattern from f2g3h4i5j6k7
        if bvl_field_id is not None:
            for idx, (val, lbl) in enumerate(language_values):
                conn.execute(sa.text("""
                    INSERT INTO metadata_field_values
                        (id, field_id, value, label, sort_order, created_at)
                    VALUES
                        (:id, :field_id, :value, :label, :sort, :now)
                """), {
                    "id": str(uuid.uuid4()),
                    "field_id": bvl_field_id,
                    "value": val,
                    "label": lbl,
                    "sort": idx,
                    "now": now,
                })


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        DELETE FROM metadata_field_values
        WHERE field_id IN (
            SELECT id FROM metadata_fields
            WHERE name IN ('brainsuite_brand_values', 'brainsuite_brand_values_language')
        )
    """))
    conn.execute(sa.text("""
        DELETE FROM metadata_fields
        WHERE name IN ('brainsuite_brand_values', 'brainsuite_brand_values_language')
    """))
