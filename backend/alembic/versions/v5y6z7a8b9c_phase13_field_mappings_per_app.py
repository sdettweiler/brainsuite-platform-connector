"""Add brainsuite_app_id FK to org_brainsuite_field_mappings (Phase 13)

Revision ID: v5y6z7a8b9c
Revises: v3w4x5y6z7a8
Create Date: 2026-04-20

Adds brainsuite_app_id FK column to org_brainsuite_field_mappings so that
each field mapping is scoped to a specific BrainsuiteApp instance rather than
a (org, app_type) pair. Backfills existing rows by matching organization_id
and app_type to brainsuite_apps, then enforces NOT NULL and a unique constraint
on (brainsuite_app_id, api_field_name).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "v5y6z7a8b9c"
down_revision = "v3w4x5y6z7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Acquire a table-level lock before any DDL to prevent concurrent DML from
    # inserting duplicate (brainsuite_app_id, api_field_name) rows during the
    # window between the FK/NOT NULL steps and the unique constraint creation.
    # CR-02: prevents race condition on unique constraint creation.
    conn = op.get_bind()
    conn.execute(sa.text(
        "LOCK TABLE org_brainsuite_field_mappings IN SHARE ROW EXCLUSIVE MODE"
    ))

    # 1. Add brainsuite_app_id as nullable initially (required for backfill)
    op.add_column(
        "org_brainsuite_field_mappings",
        sa.Column("brainsuite_app_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 2. Backfill brainsuite_app_id from brainsuite_apps via org + app_type match
    conn.execute(sa.text("""
        UPDATE org_brainsuite_field_mappings m
        SET brainsuite_app_id = app.id
        FROM brainsuite_apps app
        WHERE m.organization_id = app.organization_id
          AND m.app_type = app.app_type
          AND m.brainsuite_app_id IS NULL
    """))

    # 3. Add FK constraint with CASCADE delete
    op.create_foreign_key(
        "fk_org_brainsuite_field_mappings_app_id",
        "org_brainsuite_field_mappings",
        "brainsuite_apps",
        ["brainsuite_app_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 4. Alter column to NOT NULL after backfill
    # CR-01: Pre-check for orphan rows that could not be backfilled. Any row
    # still NULL here means its (organization_id, app_type) matched zero or
    # multiple brainsuite_apps rows — the NOT NULL ALTER would abort the entire
    # migration, leaving the database in a partial state. Raise early with a
    # clear message so the operator can resolve the rows manually.
    orphan_result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM org_brainsuite_field_mappings WHERE brainsuite_app_id IS NULL"
    ))
    orphan_count = orphan_result.scalar()
    if orphan_count > 0:
        raise RuntimeError(
            f"Migration aborted: {orphan_count} org_brainsuite_field_mappings row(s) could not be "
            "backfilled (no matching brainsuite_apps entry). Resolve these rows manually before upgrading."
        )

    op.alter_column(
        "org_brainsuite_field_mappings",
        "brainsuite_app_id",
        nullable=False,
    )

    # 5. Create unique constraint on (brainsuite_app_id, api_field_name)
    op.create_unique_constraint(
        "uq_brainsuite_field_mappings_app_field",
        "org_brainsuite_field_mappings",
        ["brainsuite_app_id", "api_field_name"],
    )

    # 6. Drop old index that was based on (organization_id, app_type)
    op.drop_index(
        "ix_org_brainsuite_field_mappings_org_app",
        table_name="org_brainsuite_field_mappings",
    )


def downgrade() -> None:
    # 1. Drop unique constraint
    op.drop_constraint(
        "uq_brainsuite_field_mappings_app_field",
        "org_brainsuite_field_mappings",
        type_="unique",
    )

    # 2. Drop FK constraint
    op.drop_constraint(
        "fk_org_brainsuite_field_mappings_app_id",
        "org_brainsuite_field_mappings",
        type_="foreignkey",
    )

    # 3. Drop brainsuite_app_id column
    op.drop_column("org_brainsuite_field_mappings", "brainsuite_app_id")

    # 4. Re-create old index on (organization_id, app_type)
    op.create_index(
        "ix_org_brainsuite_field_mappings_org_app",
        "org_brainsuite_field_mappings",
        ["organization_id", "app_type"],
    )
