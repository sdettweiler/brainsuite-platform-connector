"""Backfill all default metadata fields for orgs missing them

Revision ID: v3w4x5y6z7a8
Revises: u2v3w4x5y6z7
Create Date: 2026-04-17

Seeds all 11 default BrainSuite metadata fields for any organization that is
missing them. Idempotent — skips fields that already exist for an org.
Fixes: new orgs created after migration time received no metadata fields.
"""
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime

revision = "v3w4x5y6z7a8"
down_revision = "u2v3w4x5y6z7"
branch_labels = None
depends_on = None

_LANGUAGES = [
    ("ar", "Arabic"), ("bg", "Bulgarian"), ("cs", "Czech"), ("da", "Danish"),
    ("de", "German"), ("el", "Greek"), ("en", "English"), ("es", "Spanish"),
    ("fi", "Finnish"), ("fr", "French"), ("he", "Hebrew"), ("hi", "Hindi"),
    ("hr", "Croatian"), ("hu", "Hungarian"), ("id", "Indonesian"), ("it", "Italian"),
    ("ja", "Japanese"), ("ko", "Korean"), ("ms", "Malay"), ("nl", "Dutch"),
    ("no", "Norwegian"), ("pl", "Polish"), ("pt", "Portuguese"), ("ro", "Romanian"),
    ("sk", "Slovak"), ("sl", "Slovenian"), ("sv", "Swedish"), ("th", "Thai"),
    ("tr", "Turkish"), ("vi", "Vietnamese"), ("zh", "Chinese"),
]

_TEXT_FIELDS = [
    ("brainsuite_brand_names",      "Brand Names",       True,  None,                   1),
    ("brainsuite_project_name",     "Project Name",      False, "Spring Campaign 2026",  3),
    ("brainsuite_asset_name",       "Asset Name",        False, None,                   4),
    ("brainsuite_voice_over",       "Voice Over",        False, None,                   6),
    ("brainsuite_intended_messages","Intended Messages", False, None,                   8),
    ("brainsuite_brand_values",     "Brand Values",      False, None,                  10),
]

_SELECT_FIELDS = [
    ("brainsuite_asset_language",         "Asset Language",        True,  None,            2),
    ("brainsuite_asset_stage",            "Asset Stage",           False, "finalVersion",   5),
    ("brainsuite_voice_over_language",    "Voice Over Language",   False, None,             7),
    ("brainsuite_iconic_color_scheme",    "Iconic Color Scheme",   False, "manufactory",    9),
    ("brainsuite_brand_values_language",  "Brand Values Language", False, None,            11),
]


def _insert_field(conn, org_id, field_id, name, label, ftype, required, default, sort, now):
    conn.execute(sa.text("""
        INSERT INTO metadata_fields
            (id, organization_id, name, label, field_type, is_required, default_value,
             is_active, sort_order, created_at, updated_at)
        SELECT :id, :org_id, :name, :label, :ftype, :required, :default_val,
               true, :sort, :now, :now
        WHERE NOT EXISTS (
            SELECT 1 FROM metadata_fields
            WHERE organization_id = :org_id AND name = :name
        )
    """), {
        "id": field_id, "org_id": org_id, "name": name, "label": label,
        "ftype": ftype, "required": required, "default_val": default,
        "sort": sort, "now": now,
    })


def _get_field_id(conn, org_id, name):
    row = conn.execute(sa.text(
        "SELECT id FROM metadata_fields WHERE organization_id = :org_id AND name = :name"
    ), {"org_id": org_id, "name": name}).fetchone()
    return str(row[0]) if row else None


def upgrade() -> None:
    conn = op.get_bind()
    orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()
    now = datetime.utcnow()

    for org_row in orgs:
        org_id = str(org_row[0])

        # Seed simple text fields
        for name, label, required, default, sort in _TEXT_FIELDS:
            _insert_field(conn, org_id, str(uuid.uuid4()), name, label, "TEXT", required, default, sort, now)

        # Seed select fields
        for name, label, required, default, sort in _SELECT_FIELDS:
            _insert_field(conn, org_id, str(uuid.uuid4()), name, label, "SELECT", required, default, sort, now)

        # Seed child values for language fields
        for lang_field in ("brainsuite_asset_language", "brainsuite_voice_over_language", "brainsuite_brand_values_language"):
            field_id = _get_field_id(conn, org_id, lang_field)
            if field_id:
                existing = conn.execute(sa.text(
                    "SELECT COUNT(*) FROM metadata_field_values WHERE field_id = :fid"
                ), {"fid": field_id}).scalar()
                if existing == 0:
                    for idx, (val, lbl) in enumerate(_LANGUAGES):
                        conn.execute(sa.text("""
                            INSERT INTO metadata_field_values (id, field_id, value, label, sort_order, created_at)
                            VALUES (:id, :fid, :val, :lbl, :sort, :now)
                        """), {"id": str(uuid.uuid4()), "fid": field_id, "val": val, "lbl": lbl, "sort": idx, "now": now})

        # Seed stage values for brainsuite_asset_stage
        stage_field_id = _get_field_id(conn, org_id, "brainsuite_asset_stage")
        if stage_field_id:
            existing = conn.execute(sa.text(
                "SELECT COUNT(*) FROM metadata_field_values WHERE field_id = :fid"
            ), {"fid": stage_field_id}).scalar()
            if existing == 0:
                for val, lbl, sort in [("firstVersion", "First Version", 1), ("iteration", "Iteration", 2), ("finalVersion", "Final Version", 3)]:
                    conn.execute(sa.text("""
                        INSERT INTO metadata_field_values (id, field_id, value, label, sort_order, created_at)
                        VALUES (:id, :fid, :val, :lbl, :sort, :now)
                    """), {"id": str(uuid.uuid4()), "fid": stage_field_id, "val": val, "lbl": lbl, "sort": sort, "now": now})

        # Seed iconic color scheme values
        iconic_field_id = _get_field_id(conn, org_id, "brainsuite_iconic_color_scheme")
        if iconic_field_id:
            existing = conn.execute(sa.text(
                "SELECT COUNT(*) FROM metadata_field_values WHERE field_id = :fid"
            ), {"fid": iconic_field_id}).scalar()
            if existing == 0:
                conn.execute(sa.text("""
                    INSERT INTO metadata_field_values (id, field_id, value, label, sort_order, created_at)
                    VALUES (:id, :fid, 'manufactory', 'Manufactory', 0, :now)
                """), {"id": str(uuid.uuid4()), "fid": iconic_field_id, "now": now})


def downgrade() -> None:
    pass  # Backfill migrations are not reversible
