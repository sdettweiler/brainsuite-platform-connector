"""Phase 16: background_jobs table with autovacuum tuning

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-08

Creates background_jobs table with org_id FK (non-nullable), platform_connection_id FK
(nullable), and JSONB columns for output/metadata/error. Two composite indexes on
(org_id, status) and (org_id, job_type, started_at). Autovacuum tuned to 50x default
sensitivity via ALTER TABLE SET after table creation (visible in pg_class.reloptions).

Note on autovacuum parameters:
    autovacuum_vacuum_scale_factor=0.05 (default: 0.20) -- trigger VACUUM at 5% bloat
    autovacuum_analyze_scale_factor=0.02 (default: 0.10) -- trigger ANALYZE at 2% dead tuples
These are set via ALTER TABLE SET immediately after CREATE TABLE so they are stored in
pg_class.reloptions. To change them later, use a new migration with another ALTER TABLE SET.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("platform_connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("platform_connections.id"), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("progress_current", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        "ALTER TABLE background_jobs SET ("
        "autovacuum_vacuum_scale_factor = 0.05, "
        "autovacuum_analyze_scale_factor = 0.02"
        ")"
    )
    op.create_index(
        "ix_background_jobs_org_status",
        "background_jobs",
        ["org_id", "status"],
    )
    op.create_index(
        "ix_background_jobs_org_type_started",
        "background_jobs",
        ["org_id", "job_type", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_background_jobs_org_type_started", table_name="background_jobs")
    op.drop_index("ix_background_jobs_org_status", table_name="background_jobs")
    op.drop_table("background_jobs")
