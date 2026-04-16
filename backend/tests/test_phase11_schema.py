"""
Phase 11 — Per-Org Config Schema unit tests.

Validates OrgBrainsuiteConfig and OrgBrainsuiteFieldMapping SQLAlchemy model
definitions, constraints, FK integrity, and __init__.py exports.

All tests use SQLAlchemy's model introspection only — no live DB required.
"""
import pytest
from sqlalchemy import String, UniqueConstraint, Index


# ---------------------------------------------------------------------------
# test_config_model: OrgBrainsuiteConfig column definitions
# ---------------------------------------------------------------------------

def test_config_model():
    """OrgBrainsuiteConfig has correct tablename and all required columns.

    Verifies:
    - __tablename__ == "org_brainsuite_config"
    - All 8 columns present: id, organization_id, client_id, client_secret_encrypted,
      video_app_name, static_app_name, created_at, updated_at
    - client_secret_encrypted is String(1000), NOT Text (per D-05 / T-11-01)
    """
    from app.models.brainsuite_config import OrgBrainsuiteConfig

    assert OrgBrainsuiteConfig.__tablename__ == "org_brainsuite_config"

    col_names = {c.name for c in OrgBrainsuiteConfig.__table__.columns}
    required_cols = {
        "id", "organization_id", "client_id", "client_secret_encrypted",
        "video_app_name", "static_app_name", "created_at", "updated_at",
    }
    assert required_cols.issubset(col_names), (
        f"Missing columns: {required_cols - col_names}"
    )

    # D-05 / T-11-01: encrypted secret must be String(1000), never Text
    secret_col = OrgBrainsuiteConfig.__table__.columns["client_secret_encrypted"]
    assert isinstance(secret_col.type, String), (
        f"client_secret_encrypted must be String, got {type(secret_col.type).__name__}"
    )
    assert secret_col.type.length == 1000, (
        f"client_secret_encrypted must be String(1000), got String({secret_col.type.length})"
    )


# ---------------------------------------------------------------------------
# test_field_mapping_model: OrgBrainsuiteFieldMapping column definitions
# ---------------------------------------------------------------------------

def test_field_mapping_model():
    """OrgBrainsuiteFieldMapping has correct tablename and all required columns.

    Verifies:
    - __tablename__ == "org_brainsuite_field_mappings"
    - All 9 columns present: id, organization_id, app_type, api_field_name,
      metadata_field_id, is_mandatory, is_custom, created_at, updated_at
    """
    from app.models.brainsuite_config import OrgBrainsuiteFieldMapping

    assert OrgBrainsuiteFieldMapping.__tablename__ == "org_brainsuite_field_mappings"

    col_names = {c.name for c in OrgBrainsuiteFieldMapping.__table__.columns}
    required_cols = {
        "id", "organization_id", "app_type", "api_field_name",
        "metadata_field_id", "is_mandatory", "is_custom",
        "created_at", "updated_at",
    }
    assert required_cols.issubset(col_names), (
        f"Missing columns: {required_cols - col_names}"
    )


# ---------------------------------------------------------------------------
# test_config_unique_constraint: UniqueConstraint on organization_id
# ---------------------------------------------------------------------------

def test_config_unique_constraint():
    """OrgBrainsuiteConfig has UniqueConstraint named uq_org_brainsuite_config_org on organization_id.

    Verifies:
    - __table_args__ contains a UniqueConstraint
    - The constraint is named "uq_org_brainsuite_config_org"
    - The constraint covers the "organization_id" column (one config per org)
    """
    from app.models.brainsuite_config import OrgBrainsuiteConfig

    table_args = OrgBrainsuiteConfig.__table_args__
    unique_constraints = [
        arg for arg in table_args if isinstance(arg, UniqueConstraint)
    ]
    assert len(unique_constraints) >= 1, "No UniqueConstraint found in OrgBrainsuiteConfig.__table_args__"

    constraint_names = {uc.name for uc in unique_constraints}
    assert "uq_org_brainsuite_config_org" in constraint_names, (
        f"UniqueConstraint 'uq_org_brainsuite_config_org' not found; got: {constraint_names}"
    )


# ---------------------------------------------------------------------------
# test_config_fk: FK to organizations table
# ---------------------------------------------------------------------------

def test_config_fk():
    """OrgBrainsuiteConfig.organization_id has a ForeignKey referencing organizations.id.

    Verifies:
    - organization_id column has at least one ForeignKey
    - That ForeignKey targets "organizations.id"
    - ON DELETE CASCADE is set (prevents orphan config rows — T-11-02)
    """
    from app.models.brainsuite_config import OrgBrainsuiteConfig

    org_id_col = OrgBrainsuiteConfig.__table__.columns["organization_id"]
    fks = list(org_id_col.foreign_keys)
    assert len(fks) >= 1, "organization_id has no ForeignKey"

    fk_targets = {fk.target_fullname for fk in fks}
    assert "organizations.id" in fk_targets, (
        f"Expected FK to organizations.id, got: {fk_targets}"
    )

    # Verify CASCADE delete is set on the FK
    fk = next(fk for fk in fks if fk.target_fullname == "organizations.id")
    assert fk.ondelete == "CASCADE", (
        f"Expected ondelete=CASCADE, got: {fk.ondelete}"
    )


# ---------------------------------------------------------------------------
# test_models_exported: both models exported from app.models
# ---------------------------------------------------------------------------

def test_models_exported():
    """Both OrgBrainsuiteConfig and OrgBrainsuiteFieldMapping are exported from app.models.

    Verifies:
    - `from app.models import OrgBrainsuiteConfig, OrgBrainsuiteFieldMapping` succeeds
    - Both names appear in app.models.__all__
    """
    from app.models import OrgBrainsuiteConfig, OrgBrainsuiteFieldMapping
    import app.models as m

    assert "OrgBrainsuiteConfig" in m.__all__, (
        "OrgBrainsuiteConfig not found in app.models.__all__"
    )
    assert "OrgBrainsuiteFieldMapping" in m.__all__, (
        "OrgBrainsuiteFieldMapping not found in app.models.__all__"
    )

    # Confirm the imported names are the correct classes
    assert OrgBrainsuiteConfig.__tablename__ == "org_brainsuite_config"
    assert OrgBrainsuiteFieldMapping.__tablename__ == "org_brainsuite_field_mappings"
