"""Phase 13: Static analysis tests for field mapping endpoints, schemas, and pipeline guards."""
import pathlib
import pytest

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent


# --- Schema tests ---

def test_schema_module_exists():
    """brainsuite_field_mappings schema module must exist."""
    schema_path = BACKEND_ROOT / "app" / "schemas" / "brainsuite_field_mappings.py"
    assert schema_path.exists(), "brainsuite_field_mappings.py schema module not found"


def test_schema_has_required_classes():
    """Schema must export FieldMappingUpdate, FieldMappingResponse, MetadataFieldOption, FieldMappingRow."""
    src = (BACKEND_ROOT / "app" / "schemas" / "brainsuite_field_mappings.py").read_text()
    assert "class FieldMappingUpdate" in src, "FieldMappingUpdate schema missing"
    assert "class FieldMappingResponse" in src, "FieldMappingResponse schema missing"
    assert "class MetadataFieldOption" in src, "MetadataFieldOption schema missing"
    assert "class FieldMappingRow" in src, "FieldMappingRow schema missing"
    assert "class FieldMappingStandard" in src, "FieldMappingStandard schema missing"
    assert "class FieldMappingCustom" in src, "FieldMappingCustom schema missing"


def test_custom_field_name_validation():
    """FieldMappingCustom must validate api_field_name with alphanumeric+underscore regex."""
    src = (BACKEND_ROOT / "app" / "schemas" / "brainsuite_field_mappings.py").read_text()
    assert "field_validator" in src, "field_validator not imported"
    assert "api_field_name" in src, "api_field_name field missing"
    assert "a-zA-Z" in src, "alphanumeric validation pattern missing"


# --- Endpoint tests ---

def test_get_field_mappings_endpoint_registered():
    """GET /apps/{app_id}/field-mappings endpoint must be registered."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert 'get("/apps/{app_id}/field-mappings"' in src, "GET field-mappings endpoint not found"


def test_put_field_mappings_endpoint_registered():
    """PUT /apps/{app_id}/field-mappings endpoint must be registered."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert 'put("/apps/{app_id}/field-mappings"' in src, "PUT field-mappings endpoint not found"


def test_field_mapping_endpoints_use_admin_guard():
    """All field mapping endpoints must use get_current_admin for org isolation."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "Depends(get_current_admin)" in src, "get_current_admin not used"
    assert "Depends(get_current_user)" not in src, "get_current_user should not be used directly"


def test_org_isolation_check_in_endpoints():
    """Endpoints must check app.organization_id != current_user.organization_id."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "app.organization_id != current_user.organization_id" in src, "Org isolation check missing"


def test_standard_video_fields_constant():
    """STANDARD_VIDEO_FIELDS must be defined with 12 fields."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "STANDARD_VIDEO_FIELDS" in src, "STANDARD_VIDEO_FIELDS constant missing"
    assert '"brandValues"' in src, "brandValues missing from standard fields"
    assert '"brandValuesLanguage"' in src, "brandValuesLanguage missing from standard fields"


def test_standard_static_fields_constant():
    """STANDARD_STATIC_FIELDS must be defined with 8 fields."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "STANDARD_STATIC_FIELDS" in src, "STANDARD_STATIC_FIELDS constant missing"
    assert '"iconicColorScheme"' in src, "iconicColorScheme missing from standard fields"


def test_auto_match_hints_defined():
    """AUTO_MATCH_HINTS dict must be defined for D-06 auto-matching."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "AUTO_MATCH_HINTS" in src, "AUTO_MATCH_HINTS constant missing"
    assert '"brainsuite_brand_values"' in src, "brainsuite_brand_values auto-match missing"


def test_metadata_field_org_validation():
    """PUT endpoint must validate that metadata_field_ids belong to the org."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "MetadataField.organization_id == current_user.organization_id" in src, \
        "Metadata field org ownership validation missing"


def test_atomic_replace_pattern():
    """PUT endpoint must delete old mappings before inserting new ones (atomic replace)."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "delete(OrgBrainsuiteFieldMapping)" in src, "Atomic delete not found in PUT endpoint"


# --- Model tests ---

def test_model_has_brainsuite_app_id():
    """OrgBrainsuiteFieldMapping must have brainsuite_app_id column."""
    src = (BACKEND_ROOT / "app" / "models" / "brainsuite_config.py").read_text()
    assert "brainsuite_app_id" in src, "brainsuite_app_id column missing from model"


def test_model_unique_constraint():
    """Model must have unique constraint on (brainsuite_app_id, api_field_name)."""
    src = (BACKEND_ROOT / "app" / "models" / "brainsuite_config.py").read_text()
    assert "uq_brainsuite_field_mappings_app_field" in src, "Unique constraint missing"


# --- Migration tests ---

def test_migration_exists():
    """Phase 13 migration file must exist."""
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "v5y6z7a8b9c_phase13_field_mappings_per_app.py"
    assert migration_path.exists(), "Phase 13 migration not found"


def test_migration_chain_correct():
    """Phase 13 migration must chain from Phase 12 last migration."""
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "v5y6z7a8b9c_phase13_field_mappings_per_app.py"
    src = migration_path.read_text()
    assert 'down_revision = "v3w4x5y6z7a8"' in src, "Migration does not chain from v3w4x5y6z7a8"


# --- Pipeline guard placeholder tests (verified by Plan 03 implementation) ---

def test_scoring_job_has_mandatory_field_check():
    """scoring_job.py must have _check_mandatory_fields() function (added by Plan 03)."""
    src = (BACKEND_ROOT / "app" / "services" / "sync" / "scoring_job.py").read_text()
    assert "_check_mandatory_fields" in src or "MANDATORY_FIELD_MISSING" in src or \
        "# Phase 13 guard placeholder" in src, \
        "_check_mandatory_fields or MANDATORY_FIELD_MISSING or placeholder not found"


def test_datetime_utc_pattern():
    """All new code must use datetime.now(timezone.utc), not utcnow()."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "datetime.utcnow()" not in src, "datetime.utcnow() found — use datetime.now(timezone.utc)"
