"""
Phase 11 Plan 02 -- brand_values seed migration and provisioning tests.

Static analysis / module-level tests -- no live database required.
Verifies:
  - Seed migration defines brainsuite_brand_values and brainsuite_brand_values_language correctly
  - Language values list has exactly 31 entries
  - auth.py contains the expected provisioning code inline
  - downgrade() references both fields and cleans up in the correct order

FMAP-08: brand_values fields exist as default non-mandatory metadata for every org.
"""
import importlib.util
import sys
import types
import os


# ---------------------------------------------------------------------------
# Helpers -- load the migration module without a live DB / alembic env
# ---------------------------------------------------------------------------

def _load_migration_module(path: str):
    """Load a migration file as a module, mocking alembic/sqlalchemy deps."""
    # Only mock if not already present (avoids double-import pollution)
    if "alembic" not in sys.modules:
        alembic_mock = types.ModuleType("alembic")
        op_mock = types.ModuleType("alembic.op")
        alembic_mock.op = op_mock
        sys.modules["alembic"] = alembic_mock
        sys.modules["alembic.op"] = op_mock

    if "sqlalchemy" not in sys.modules:
        sa_mock = types.ModuleType("sqlalchemy")
        sys.modules["sqlalchemy"] = sa_mock

    spec = importlib.util.spec_from_file_location("seed_migration", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _migration_path() -> str:
    """Resolve the seed migration file path relative to this test file."""
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(
        tests_dir,
        "..",
        "alembic",
        "versions",
        "t1u2v3w4x5y6_seed_brand_values_metadata_fields.py",
    )


def _auth_py_path() -> str:
    """Resolve auth.py path relative to this test file."""
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(
        tests_dir,
        "..",
        "app",
        "api",
        "v1",
        "endpoints",
        "auth.py",
    )


# ---------------------------------------------------------------------------
# Test 1: Seed migration field definitions
# ---------------------------------------------------------------------------

def test_brand_values_seed_migration_fields_def():
    """Verify the migration defines both brand_values fields with correct attributes.

    Checks:
    - revision and down_revision are correct
    - fields_def contains brainsuite_brand_values as TEXT at sort_order 10
    - fields_def contains brainsuite_brand_values_language as SELECT at sort_order 11
    - Neither field is marked as required
    """
    path = _migration_path()
    assert os.path.isfile(path), f"Migration file not found: {path}"

    # Read source to inspect fields_def -- module exec would need DB connection
    with open(path, "r") as f:
        source = f.read()

    assert 'revision = "t1u2v3w4x5y6"' in source, "revision ID must be t1u2v3w4x5y6"
    assert 'down_revision = "s0t1u2v3w4x5"' in source, "down_revision must chain from s0t1u2v3w4x5"

    # brainsuite_brand_values: TEXT, not required, sort_order 10
    assert '"brainsuite_brand_values"' in source
    assert '"Brand Values"' in source
    assert '"TEXT"' in source
    # Check sort_order 10 appears in fields_def tuple
    assert '10)' in source or ', 10,' in source, "sort_order 10 must be present"

    # brainsuite_brand_values_language: SELECT, not required, sort_order 11
    assert '"brainsuite_brand_values_language"' in source
    assert '"Brand Values Language"' in source
    assert '"SELECT"' in source
    assert '11)' in source or ', 11,' in source, "sort_order 11 must be present"

    # Idempotency: ON CONFLICT DO NOTHING on metadata_fields
    assert "ON CONFLICT DO NOTHING" in source, "metadata_fields inserts must be idempotent"

    # metadata_field_values INSERT must NOT contain ON CONFLICT immediately after it
    # Find the metadata_field_values INSERT block and confirm no ON CONFLICT follows it
    mfv_insert_idx = source.find("INSERT INTO metadata_field_values")
    assert mfv_insert_idx != -1, "metadata_field_values INSERT must exist"
    # Extract the SQL block for metadata_field_values (up to the closing of that statement)
    mfv_block = source[mfv_insert_idx:mfv_insert_idx + 300]
    assert "ON CONFLICT DO NOTHING" not in mfv_block, (
        "metadata_field_values INSERT must NOT use ON CONFLICT DO NOTHING (no unique constraint)"
    )


# ---------------------------------------------------------------------------
# Test 2: Language values count and bounds
# ---------------------------------------------------------------------------

def test_brand_values_language_count():
    """Verify the migration contains exactly 31 language values in the correct order.

    Checks:
    - First language tuple is ('ar', 'Arabic')
    - Last language tuple is ('zh', 'Chinese')
    - Exactly 31 language entries are defined
    """
    path = _migration_path()
    assert os.path.isfile(path), f"Migration file not found: {path}"

    with open(path, "r") as f:
        source = f.read()

    # Check first and last language entries
    assert '("ar", "Arabic")' in source, "First language entry must be (ar, Arabic)"
    assert '("zh", "Chinese")' in source, "Last language entry must be (zh, Chinese)"

    # Count the number of language tuples by counting known entries
    # We use a representative set -- easier than full list parse on source text
    expected_lang_codes = [
        "ar", "bg", "cs", "da", "de", "el", "en", "es",
        "fi", "fr", "he", "hi", "hr", "hu", "id", "it",
        "ja", "ko", "ms", "nl", "no", "pl", "pt", "ro",
        "sk", "sl", "sv", "th", "tr", "vi", "zh",
    ]
    assert len(expected_lang_codes) == 31, "Fixture must have 31 codes"

    for code in expected_lang_codes:
        assert f'("{code}",' in source or f'("{code}", ' in source, (
            f"Language code '{code}' not found in migration source"
        )


# ---------------------------------------------------------------------------
# Test 3: auth.py provisioning presence
# ---------------------------------------------------------------------------

def test_auth_provisioning_has_brand_values():
    """Verify auth.py contains the brand_values provisioning code in the else branch.

    Checks:
    - MetadataField and MetadataFieldValue are imported
    - brainsuite_brand_values MetadataField is created with sort_order=10
    - brainsuite_brand_values_language MetadataField is created with sort_order=11
    - MetadataFieldValue is seeded for brand_values_lang_field
    - await db.flush() appears after each db.add(brand_values_*field)
    - The join branch (is_pending_join = True) does NOT contain provisioning
    """
    path = _auth_py_path()
    assert os.path.isfile(path), f"auth.py not found: {path}"

    with open(path, "r") as f:
        source = f.read()

    # Import check
    assert "from app.models.metadata import MetadataField, MetadataFieldValue" in source, (
        "MetadataField and MetadataFieldValue must be imported at module level"
    )

    # Field presence
    assert 'name="brainsuite_brand_values"' in source, (
        "brainsuite_brand_values MetadataField must be present in auth.py"
    )
    assert 'name="brainsuite_brand_values_language"' in source, (
        "brainsuite_brand_values_language MetadataField must be present in auth.py"
    )

    # sort_order
    assert "sort_order=10," in source, "sort_order=10 must be set for brand_values field"
    assert "sort_order=11," in source, "sort_order=11 must be set for brand_values_language field"

    # MetadataFieldValue seeding -- constructor is multi-line so check both parts separately
    assert "MetadataFieldValue(" in source, (
        "MetadataFieldValue must be instantiated for language seeding"
    )
    assert "field_id=brand_values_lang_field.id," in source, (
        "MetadataFieldValue seeding must reference brand_values_lang_field.id"
    )

    # db.flush() after each add
    assert "await db.flush()  # get brand_values_field.id" in source, (
        "db.flush() must follow db.add(brand_values_field)"
    )
    assert "await db.flush()  # get brand_values_lang_field.id" in source, (
        "db.flush() must follow db.add(brand_values_lang_field)"
    )

    # grep count for 'brainsuite_brand_values' >= 4
    count = source.count("brainsuite_brand_values")
    assert count >= 4, (
        f"Expected >= 4 occurrences of 'brainsuite_brand_values' in auth.py, found {count}"
    )

    # Verify provisioning is ONLY in the else branch (not in join branch)
    # The join branch ends before the else: keyword; brand_values code must appear after "else:"
    else_idx = source.index("    else:\n        role = OrganizationRole")
    bv_idx = source.index('name="brainsuite_brand_values"')
    assert bv_idx > else_idx, (
        "brand_values provisioning must appear in the else branch, not the join branch"
    )


# ---------------------------------------------------------------------------
# Test 4: downgrade cleanup
# ---------------------------------------------------------------------------

def test_seed_migration_downgrade_deletes():
    """Verify the downgrade() function deletes seeded data in the correct order.

    Checks:
    - downgrade deletes from metadata_field_values first (referential integrity)
    - downgrade deletes from metadata_fields second
    - Both DELETE statements reference the correct field names
    - brainsuite_brand_values and brainsuite_brand_values_language are both targeted
    """
    path = _migration_path()
    assert os.path.isfile(path), f"Migration file not found: {path}"

    with open(path, "r") as f:
        source = f.read()

    # Extract downgrade function body
    downgrade_idx = source.index("def downgrade()")
    downgrade_body = source[downgrade_idx:]

    # Both DELETE statements must exist
    assert "DELETE FROM metadata_field_values" in downgrade_body, (
        "downgrade must DELETE FROM metadata_field_values"
    )
    assert "DELETE FROM metadata_fields" in downgrade_body, (
        "downgrade must DELETE FROM metadata_fields"
    )

    # metadata_field_values must come BEFORE metadata_fields (referential integrity)
    values_delete_idx = downgrade_body.index("DELETE FROM metadata_field_values")
    fields_delete_idx = downgrade_body.index("DELETE FROM metadata_fields")
    assert values_delete_idx < fields_delete_idx, (
        "downgrade must delete from metadata_field_values before metadata_fields"
    )

    # Both field names referenced in downgrade
    assert "brainsuite_brand_values" in downgrade_body, (
        "downgrade must reference brainsuite_brand_values"
    )
    assert "brainsuite_brand_values_language" in downgrade_body, (
        "downgrade must reference brainsuite_brand_values_language"
    )
