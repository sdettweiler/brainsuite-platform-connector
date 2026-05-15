"""
Phase 22 Plan 01 — Metadata Filter Migration Tests.

Tests for:
- Alembic migration e8f9a0b1c2d3 declares composite index
  idx_asset_metadata_values_field_value on asset_metadata_values(field_id, value)

This test uses importlib + inspect to check migration source without requiring
a running database (unit-level check per plan contract).
"""
import importlib.util
import inspect
import os


# ---------------------------------------------------------------------------
# Tests: Alembic migration index declaration
# ---------------------------------------------------------------------------

def test_composite_index_present():
    """Migration e8f9a0b1c2d3 upgrade() calls op.create_index with:
    - name = 'idx_asset_metadata_values_field_value'
    - table = 'asset_metadata_values'
    - columns containing 'field_id' and 'value'

    Uses inspect.getsource() — no DB required.
    """
    # Locate migration file relative to this test file (backend/ layout)
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    migration_path = os.path.join(
        backend_dir,
        "alembic",
        "versions",
        "e8f9a0b1c2d3_phase22_metadata_filter_index.py",
    )

    assert os.path.exists(migration_path), (
        f"Migration file not found at {migration_path}. "
        "Task 2 must create backend/alembic/versions/e8f9a0b1c2d3_phase22_metadata_filter_index.py"
    )

    spec = importlib.util.spec_from_file_location("e8f9a0b1c2d3_migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Verify revision metadata
    assert hasattr(module, "revision"), "Migration module must define revision"
    assert module.revision == "e8f9a0b1c2d3", (
        f"Expected revision 'e8f9a0b1c2d3', got '{module.revision}'"
    )
    assert hasattr(module, "down_revision"), "Migration module must define down_revision"
    assert module.down_revision == "d2e3f4a5b6c7", (
        f"Expected down_revision 'd2e3f4a5b6c7' (background_jobs_schema head), "
        f"got '{module.down_revision}'"
    )

    # Verify upgrade() function body contains required index definition
    assert hasattr(module, "upgrade"), "Migration module must define upgrade()"
    upgrade_source = inspect.getsource(module.upgrade)

    assert "idx_asset_metadata_values_field_value" in upgrade_source, (
        "upgrade() must call op.create_index with name='idx_asset_metadata_values_field_value'"
    )
    assert "asset_metadata_values" in upgrade_source, (
        "upgrade() must create index on table 'asset_metadata_values'"
    )
    assert "field_id" in upgrade_source, (
        "upgrade() index columns must include 'field_id'"
    )
    assert "'value'" in upgrade_source or '"value"' in upgrade_source, (
        "upgrade() index columns must include 'value'"
    )

    # Verify downgrade() function body drops the index
    assert hasattr(module, "downgrade"), "Migration module must define downgrade()"
    downgrade_source = inspect.getsource(module.downgrade)

    assert "idx_asset_metadata_values_field_value" in downgrade_source, (
        "downgrade() must drop 'idx_asset_metadata_values_field_value'"
    )
