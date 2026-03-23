"""seed BrainSuite MetadataField rows per organization

Revision ID: f2g3h4i5j6k7
Revises: e1f2g3h4i5j6
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime

revision = "f2g3h4i5j6k7"
down_revision = "e1f2g3h4i5j6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()

    now = datetime.utcnow()

    fields_def = [
        ("brainsuite_brand_names", "Brand Names", "TEXT", True, None, 1),
        ("brainsuite_asset_language", "Asset Language", "SELECT", True, None, 2),
        ("brainsuite_project_name", "Project Name", "TEXT", False, "Spring Campaign 2026", 3),
        ("brainsuite_asset_name", "Asset Name", "TEXT", False, None, 4),
        ("brainsuite_asset_stage", "Asset Stage", "SELECT", False, "finalVersion", 5),
        ("brainsuite_voice_over", "Voice Over", "TEXT", False, None, 6),
        ("brainsuite_voice_over_language", "Voice Over Language", "SELECT", False, None, 7),
    ]

    # Language enum values (shared by asset_language and voice_over_language)
    # Sorted alphabetically by label
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

    stage_values = [
        ("firstVersion", "First Version", 1),
        ("iteration", "Iteration", 2),
        ("finalVersion", "Final Version", 3),
    ]

    for org_id_row in orgs:
        org_id = org_id_row[0]
        field_ids = {}

        for name, label, ftype, required, default, sort in fields_def:
            field_id = str(uuid.uuid4())
            field_ids[name] = field_id
            conn.execute(sa.text("""
                INSERT INTO metadata_fields
                    (id, organization_id, name, label, field_type, is_required, default_value, is_active, sort_order, created_at, updated_at)
                VALUES
                    (:id, :org_id, :name, :label, :ftype, :required, :default_val, true, :sort, :now, :now)
                ON CONFLICT DO NOTHING
            """), {
                "id": field_id,
                "org_id": str(org_id),
                "name": name,
                "label": label,
                "ftype": ftype,
                "required": required,
                "default_val": default,
                "sort": sort,
                "now": now,
            })

        # Seed allowed values for SELECT fields
        for idx, (val, lbl) in enumerate(language_values):
            for field_name in ("brainsuite_asset_language", "brainsuite_voice_over_language"):
                conn.execute(sa.text("""
                    INSERT INTO metadata_field_values
                        (id, field_id, value, label, sort_order, created_at)
                    VALUES
                        (:id, :field_id, :value, :label, :sort, :now)
                """), {
                    "id": str(uuid.uuid4()),
                    "field_id": field_ids[field_name],
                    "value": val,
                    "label": lbl,
                    "sort": idx,
                    "now": now,
                })

        for val, lbl, sort in stage_values:
            conn.execute(sa.text("""
                INSERT INTO metadata_field_values
                    (id, field_id, value, label, sort_order, created_at)
                VALUES
                    (:id, :field_id, :value, :label, :sort, :now)
            """), {
                "id": str(uuid.uuid4()),
                "field_id": field_ids["brainsuite_asset_stage"],
                "value": val,
                "label": lbl,
                "sort": sort,
                "now": now,
            })


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        DELETE FROM metadata_field_values
        WHERE field_id IN (
            SELECT id FROM metadata_fields WHERE name LIKE 'brainsuite_%'
        )
    """))
    conn.execute(sa.text("""
        DELETE FROM metadata_fields WHERE name LIKE 'brainsuite_%'
    """))
