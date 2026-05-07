"""Normalize language codes from 2-letter to locale format (en → en_US)

Revision ID: a1b2c3d4e5f8
Revises: z8a9b1c2d3e5
Create Date: 2026-05-07

Updates metadata_field_values and asset_metadata_values for all language
fields from bare 2-letter codes (en, id, fr) to xx_XX locale codes
(en_US, id_ID, fr_FR) so mat-select options match autofill-written values.
"""
from alembic import op

revision = 'a1b2c3d4e5f8'
down_revision = 'z8a9b1c2d3e5'
branch_labels = None
depends_on = None

_MAPPING = [
    ("ar", "ar_SA"), ("bg", "bg_BG"), ("cs", "cs_CZ"), ("da", "da_DK"),
    ("de", "de_DE"), ("el", "el_GR"), ("en", "en_US"), ("es", "es_ES"),
    ("fi", "fi_FI"), ("fr", "fr_FR"), ("he", "he_IL"), ("hi", "hi_IN"),
    ("hr", "hr_HR"), ("hu", "hu_HU"), ("id", "id_ID"), ("it", "it_IT"),
    ("ja", "ja_JP"), ("ko", "ko_KR"), ("ms", "ms_MY"), ("nl", "nl_NL"),
    ("no", "no_NO"), ("pl", "pl_PL"), ("pt", "pt_BR"), ("ro", "ro_RO"),
    ("sk", "sk_SK"), ("sl", "sl_SI"), ("sv", "sv_SE"), ("th", "th_TH"),
    ("tr", "tr_TR"), ("vi", "vi_VN"), ("zh", "zh_CN"),
]


def upgrade() -> None:
    # Build CASE expression for the value remapping
    case_parts = " ".join(f"WHEN value = '{old}' THEN '{new}'" for old, new in _MAPPING)
    old_values = ", ".join(f"'{old}'" for old, _ in _MAPPING)

    # 1. Update predefined options in metadata_field_values for language fields
    op.execute(f"""
        UPDATE metadata_field_values
        SET value = CASE {case_parts} ELSE value END
        WHERE value IN ({old_values})
          AND field_id IN (
              SELECT id FROM metadata_fields
              WHERE name LIKE '%language%' AND is_active = true
          )
    """)

    # 2. Update per-asset values in asset_metadata_values for language fields
    op.execute(f"""
        UPDATE asset_metadata_values
        SET value = CASE {case_parts} ELSE value END
        WHERE value IN ({old_values})
          AND field_id IN (
              SELECT id FROM metadata_fields
              WHERE name LIKE '%language%' AND is_active = true
          )
    """)


def downgrade() -> None:
    reverse = [(new, old) for old, new in _MAPPING]
    case_parts = " ".join(f"WHEN value = '{old}' THEN '{new}'" for old, new in reverse)
    old_values = ", ".join(f"'{old}'" for old, _ in reverse)

    op.execute(f"""
        UPDATE metadata_field_values
        SET value = CASE {case_parts} ELSE value END
        WHERE value IN ({old_values})
          AND field_id IN (
              SELECT id FROM metadata_fields WHERE name LIKE '%language%'
          )
    """)

    op.execute(f"""
        UPDATE asset_metadata_values
        SET value = CASE {case_parts} ELSE value END
        WHERE value IN ({old_values})
          AND field_id IN (
              SELECT id FROM metadata_fields WHERE name LIKE '%language%'
          )
    """)
