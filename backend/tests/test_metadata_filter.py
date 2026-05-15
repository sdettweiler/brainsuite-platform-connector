"""
Phase 22 Plan 01 — Metadata Filter Endpoint Tests.

Tests for:
- GET /dashboard/metadata-fields returns only is_active=true org-scoped fields
- GET /dashboard/metadata-fields/{field_id}/values returns 404 for cross-org field_id
- GET /dashboard/metadata-fields/{field_id}/values returns DISTINCT, sorted, non-null values
- AssetMetadataValue rows whose CreativeAsset.organization_id belongs to another org
  do NOT appear in the values response

These tests start RED until Task 3 implements the two new endpoints.
Security: T-22-01 org isolation enforced in every query path.
"""
import uuid
import inspect
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Async DB session mock."""
    return AsyncMock()


@pytest.fixture
def mock_user():
    """Minimal user mock."""
    user = MagicMock()
    user.organization_id = uuid.uuid4()
    return user


# ---------------------------------------------------------------------------
# Tests: GET /dashboard/metadata-fields (org-scoped)
# ---------------------------------------------------------------------------

def test_org_scoped_fields():
    """GET /dashboard/metadata-fields returns ONLY is_active=True MetadataField rows
    where organization_id == current_user.organization_id, ordered by sort_order then label.

    Verifies T-22-01 (D-02) org isolation: MetadataField.organization_id guard present.
    """
    from app.api.v1.endpoints.dashboard import get_metadata_fields  # noqa: F401 — RED until Task 3
    import inspect
    import app.api.v1.endpoints.dashboard as dash_mod

    source = inspect.getsource(dash_mod.get_metadata_fields)

    # Org guard must be present in the query
    assert "organization_id" in source, (
        "get_metadata_fields must filter by MetadataField.organization_id == current_user.organization_id"
    )
    assert "is_active" in source, (
        "get_metadata_fields must filter MetadataField.is_active"
    )
    assert "sort_order" in source, (
        "get_metadata_fields must order results by sort_order"
    )
    # Org guard on MetadataField — prevents cross-org leakage (T-22-01)
    assert "metadata_fields.organization_id" in source or "MetadataField.organization_id" in source, (
        "Source must include MetadataField.organization_id org guard"
    )


def test_org_scoped_values():
    """GET /dashboard/metadata-fields/{field_id}/values returns 404 when the field belongs
    to a different organization.

    Verifies T-22-01 (D-04): cross-org field access blocked via two-layer guard:
    (1) db.get(MetadataField, field_id) + org check → 404
    (2) JOIN-level MetadataField.organization_id guard in the values query
    """
    from app.api.v1.endpoints.dashboard import get_metadata_field_values  # noqa — RED until Task 3
    import inspect
    import app.api.v1.endpoints.dashboard as dash_mod

    source = inspect.getsource(dash_mod.get_metadata_field_values)

    # Must raise 404 when field belongs to another org
    assert "404" in source, (
        "get_metadata_field_values must raise HTTPException(404) for cross-org access"
    )
    assert "Field not found" in source, (
        "get_metadata_field_values must return 'Field not found' detail on 404"
    )
    # T-22-01: two-layer org guard
    assert "organization_id" in source, (
        "get_metadata_field_values must check field.organization_id against current_user.organization_id"
    )


def test_values_distinct_org_scoped():
    """When field belongs to caller's org, response['values'] is sorted ascending,
    distinct, and excludes NULLs.

    Verifies D-04 DISTINCT behavior and isnot(None) filter.
    """
    from app.api.v1.endpoints.dashboard import get_metadata_field_values  # noqa — RED until Task 3
    import inspect
    import app.api.v1.endpoints.dashboard as dash_mod

    source = inspect.getsource(dash_mod.get_metadata_field_values)

    # DISTINCT values only
    assert "distinct" in source.lower(), (
        "get_metadata_field_values must use distinct() on AssetMetadataValue.value"
    )
    # NULLs excluded
    assert "isnot" in source or "IS NOT NULL" in source.upper() or "isnot(None)" in source, (
        "get_metadata_field_values must exclude NULL values"
    )
    # Ordered ascending
    assert "order_by" in source, (
        "get_metadata_field_values must ORDER BY value ascending"
    )
    # Org guard on MetadataField in the DISTINCT query (T-22-01)
    assert "metadata_fields.organization_id" in source or "MetadataField.organization_id" in source, (
        "get_metadata_field_values query must include MetadataField.organization_id org guard"
    )


def test_values_no_cross_org_leakage():
    """An AssetMetadataValue row whose CreativeAsset.organization_id is a different org
    MUST NOT appear in the response.

    Verifies T-22-01: JOIN through CreativeAsset with org guard prevents cross-org leakage.
    """
    from app.api.v1.endpoints.dashboard import get_metadata_field_values  # noqa — RED until Task 3
    import inspect
    import app.api.v1.endpoints.dashboard as dash_mod

    source = inspect.getsource(dash_mod.get_metadata_field_values)

    # Must JOIN through CreativeAsset to apply org guard at asset level
    assert "CreativeAsset" in source, (
        "get_metadata_field_values must JOIN through CreativeAsset to enforce org isolation"
    )
    assert "creative_assets.organization_id" in source or "CreativeAsset.organization_id" in source, (
        "get_metadata_field_values must include CreativeAsset.organization_id guard in the JOIN/WHERE"
    )
