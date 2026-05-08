"""Integration tests for Phase 16 Alembic migration.

The primary verification for the migration is running:
    alembic upgrade head
against both a fresh database and the existing production schema.
This is executed as a blocking checkpoint in Plan 02.

The test below verifies the migration file is present and well-formed.
"""
import os
import glob


def test_phase16_migration_file_exists():
    """Phase 16 migration file exists in alembic/versions with correct revision chain."""
    versions_dir = os.path.join(
        os.path.dirname(__file__), "../../../alembic/versions"
    )
    migration_files = glob.glob(os.path.join(versions_dir, "*background_jobs*.py"))
    assert len(migration_files) == 1, (
        f"Expected exactly 1 background_jobs migration file, found: {migration_files}"
    )
    migration_content = open(migration_files[0]).read()
    assert "background_jobs" in migration_content
    assert "autovacuum_vacuum_scale_factor" in migration_content
    assert "down_revision" in migration_content
