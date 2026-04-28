"""Add brainsuite_intended_messages_language default metadata field

Revision ID: w4x5y6z7a8b9
Revises: v5y6z7a8b9c
Create Date: 2026-04-24

Adds the missing intendedMessagesLanguage SELECT field to all orgs and seeds
language options. Idempotent — skips orgs that already have the field.
"""
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime

revision = "w4x5y6z7a8b9"
down_revision = "v5y6z7a8b9c"
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


def upgrade() -> None:
    conn = op.get_bind()
    orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()
    now = datetime.utcnow()

    for org_row in orgs:
        org_id = str(org_row[0])

        # Insert field if missing
        field_id = str(uuid.uuid4())
        conn.execute(sa.text("""
            INSERT INTO metadata_fields
                (id, organization_id, name, label, field_type, is_required,
                 default_value, is_active, sort_order, created_at, updated_at)
            SELECT :id, :org_id,
                   'brainsuite_intended_messages_language',
                   'Intended Messages Language',
                   'SELECT', false, null, true, 12, :now, :now
            WHERE NOT EXISTS (
                SELECT 1 FROM metadata_fields
                WHERE organization_id = :org_id
                  AND name = 'brainsuite_intended_messages_language'
            )
        """), {"id": field_id, "org_id": org_id, "now": now})

        # Fetch actual field id (may have existed before)
        row = conn.execute(sa.text(
            "SELECT id FROM metadata_fields WHERE organization_id = :org_id AND name = 'brainsuite_intended_messages_language'"
        ), {"org_id": org_id}).fetchone()
        if not row:
            continue
        fid = str(row[0])

        existing = conn.execute(sa.text(
            "SELECT COUNT(*) FROM metadata_field_values WHERE field_id = :fid"
        ), {"fid": fid}).scalar()
        if existing == 0:
            for idx, (val, lbl) in enumerate(_LANGUAGES):
                conn.execute(sa.text("""
                    INSERT INTO metadata_field_values (id, field_id, value, label, sort_order, created_at)
                    VALUES (:id, :fid, :val, :lbl, :sort, :now)
                """), {"id": str(uuid.uuid4()), "fid": fid, "val": val, "lbl": lbl, "sort": idx, "now": now})


def downgrade() -> None:
    pass
