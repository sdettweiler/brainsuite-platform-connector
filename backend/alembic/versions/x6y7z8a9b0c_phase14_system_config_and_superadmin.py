"""Phase 14: system_config singleton table + SuperAdmin seed

Revision ID: x6y7z8a9b0c
Revises: w4x5y6z7a8b9
Create Date: 2026-04-27

Creates the system_config singleton table for platform-wide configuration
(YouTube cookies encrypted storage). Sets initial SuperAdmin from
INITIAL_SUPERADMIN_EMAIL env var at migration time (no-op if unset).
"""
from alembic import op
import sqlalchemy as sa
import uuid
import os
from datetime import datetime, timezone

revision = "x6y7z8a9b0c"
down_revision = "w4x5y6z7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create system_config table
    op.create_table(
        "system_config",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("singleton_guard", sa.String(1), nullable=False, server_default="X"),
        sa.Column("youtube_cookies_encrypted", sa.Text, nullable=True),
        sa.Column("youtube_cookies_backup_encrypted", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Add unique constraint on singleton_guard (enforces one-row policy at DB level)
    op.create_unique_constraint("uq_system_config_singleton", "system_config", ["singleton_guard"])

    # 3. Insert default singleton row
    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    conn.execute(
        sa.text(
            "INSERT INTO system_config (id, singleton_guard, created_at, updated_at) "
            "VALUES (:id, 'X', :now, :now)"
        ),
        {"id": str(uuid.uuid4()), "now": now},
    )

    # 4. Seed initial SuperAdmin from env var (no-op if unset — set via INITIAL_SUPERADMIN_EMAIL at deploy time)
    superadmin_email = os.environ.get("INITIAL_SUPERADMIN_EMAIL")
    if superadmin_email:
        conn.execute(
            sa.text("UPDATE users SET is_superuser = true WHERE email = :email"),
            {"email": superadmin_email},
        )


def downgrade() -> None:
    op.drop_table("system_config")
    # Intentionally does NOT reset is_superuser on downgrade
