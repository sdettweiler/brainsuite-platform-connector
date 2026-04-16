"""add org_brainsuite_config and org_brainsuite_field_mappings tables

Revision ID: s0t1u2v3w4x5
Revises: r9s0t1u2v3w4
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "s0t1u2v3w4x5"
down_revision = "r9s0t1u2v3w4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_brainsuite_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_id", sa.String(500), nullable=True),
        sa.Column("client_secret_encrypted", sa.String(1000), nullable=True),
        sa.Column("video_app_name", sa.String(255), nullable=True),
        sa.Column("static_app_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", name="uq_org_brainsuite_config_org"),
    )
    op.create_index(
        "ix_org_brainsuite_config_org_id",
        "org_brainsuite_config",
        ["organization_id"],
    )

    op.create_table(
        "org_brainsuite_field_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("app_type", sa.String(20), nullable=False),
        sa.Column("api_field_name", sa.String(255), nullable=False),
        sa.Column(
            "metadata_field_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("metadata_fields.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_mandatory", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_custom", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_org_brainsuite_field_mappings_org_app",
        "org_brainsuite_field_mappings",
        ["organization_id", "app_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_org_brainsuite_field_mappings_org_app",
        table_name="org_brainsuite_field_mappings",
    )
    op.drop_table("org_brainsuite_field_mappings")
    op.drop_index(
        "ix_org_brainsuite_config_org_id",
        table_name="org_brainsuite_config",
    )
    op.drop_table("org_brainsuite_config")
