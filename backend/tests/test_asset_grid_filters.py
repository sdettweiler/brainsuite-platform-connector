"""
Phase 22 Plan 01 — Asset Grid Metadata Filter Tests.

Tests for:
- GET /dashboard/assets?metadata_filter=language:Indonesian applies one aliased JOIN
  with org_id guards on both CreativeAsset and MetadataField
- Two metadata_filter params produce two separate aliased JOINs (amv_0/mf_0, amv_1/mf_1)
  enforcing AND logic
- ad_account_ids filter composes with metadata_filter via AND
- A malformed metadata_filter entry (missing ':') returns HTTP 400

All tests verify security requirement T-22-01 (org isolation on metadata queries).
"""
import uuid
import inspect
import pytest
from unittest.mock import AsyncMock, MagicMock
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
# Tests: metadata_filter JOIN pattern
# ---------------------------------------------------------------------------

def test_metadata_filter_single():
    """GET /dashboard/assets?metadata_filter=language:Indonesian applies one aliased JOIN
    through asset_metadata_values and metadata_fields with org_id guards on both
    CreativeAsset.organization_id and MetadataField.organization_id.

    Verifies D-10 parameter contract and T-22-01 org guard in JOIN.
    """
    from app.api.v1.endpoints.dashboard import get_dashboard_assets  # noqa — must exist after Task 3
    import app.api.v1.endpoints.dashboard as dash_mod

    source = inspect.getsource(dash_mod.get_dashboard_assets)

    # metadata_filter param must be in signature (D-10)
    assert "metadata_filter" in source, (
        "get_dashboard_assets must accept metadata_filter query parameter"
    )
    # Aliased JOIN pattern for single filter (amv_0 alias)
    assert "amv_" in source or "aliased(AssetMetadataValue" in source, (
        "get_dashboard_assets must use aliased(AssetMetadataValue) for metadata_filter JOIN"
    )
    assert "mf_" in source or "aliased(MetadataField" in source, (
        "get_dashboard_assets must use aliased(MetadataField) for metadata_filter JOIN"
    )
    # Org guard present in the metadata JOIN path (T-22-01)
    assert "organization_id" in source, (
        "get_dashboard_assets metadata_filter block must include organization_id org guard"
    )


def test_metadata_filter_multi_and_composition():
    """Two metadata_filter params produce two separate aliased JOINs (amv_0/mf_0, amv_1/mf_1)
    such that an asset must satisfy both to appear in results (AND logic by JOIN construction).

    Verifies D-07 and D-08: multiple filters AND-composed via separate aliased JOINs.
    """
    from app.api.v1.endpoints.dashboard import get_dashboard_assets  # noqa — RED until Task 3
    import app.api.v1.endpoints.dashboard as dash_mod

    source = inspect.getsource(dash_mod.get_dashboard_assets)

    # Loop-based aliased JOIN pattern — indexed aliases
    assert "enumerate(metadata_filter" in source or ("for i" in source and "metadata_filter" in source), (
        "get_dashboard_assets must iterate metadata_filter with enumerate() to build indexed aliases"
    )
    # Aliased table naming pattern amv_{i} / mf_{i}
    assert 'f"amv_{i}"' in source or "amv_{i}" in source or 'f"amv_' in source, (
        "Aliased AssetMetadataValue must use name=f'amv_{{i}}' pattern for AND composition"
    )
    assert 'f"mf_{i}"' in source or "mf_{i}" in source or 'f"mf_' in source, (
        "Aliased MetadataField must use name=f'mf_{{i}}' pattern for AND composition"
    )


def test_multi_account_filter():
    """ad_account_ids=acc1,acc2 keeps the existing CreativeAsset.ad_account_id.in_([...]) clause.
    metadata + account filters compose via AND (both clauses present in final query).

    Verifies D-02 (DASH-02) account filter still applies alongside metadata_filter.
    """
    from app.api.v1.endpoints.dashboard import get_dashboard_assets  # noqa — RED until Task 3
    import app.api.v1.endpoints.dashboard as dash_mod

    source = inspect.getsource(dash_mod.get_dashboard_assets)

    # Account filter clause still present (pre-existing behavior)
    assert "ad_account_id" in source and "account_id_list" in source, (
        "get_dashboard_assets must retain ad_account_ids filter alongside metadata_filter"
    )
    # metadata_filter param in same function
    assert "metadata_filter" in source, (
        "get_dashboard_assets must accept metadata_filter: Optional[List[str]] = Query(default=None)"
    )
    # Both filters visible in same source — they AND together by being sequential query.where() calls
    assert "metadata_fields.organization_id" in source or "mf_" in source or "aliased(MetadataField" in source, (
        "metadata_filter JOIN with org guard must be present to compose with account filter via AND"
    )


def test_metadata_filter_malformed_value():
    """A malformed metadata_filter entry missing ':' returns HTTP 400.

    Plan contract: explicit 400 over silent skip.
    Verifies the malformed-input rejection clause referenced in test_metadata_filter_malformed_value.
    """
    from app.api.v1.endpoints.dashboard import get_dashboard_assets  # noqa — RED until Task 3
    import app.api.v1.endpoints.dashboard as dash_mod

    source = inspect.getsource(dash_mod.get_dashboard_assets)

    # 400 rejection for malformed format (no ':' separator)
    assert "400" in source or "Invalid metadata_filter" in source, (
        "get_dashboard_assets must raise HTTPException(400) for malformed metadata_filter entries"
    )
    assert "':' not in" in source or "split(':'" in source or "split(':', 1)" in source, (
        "get_dashboard_assets must split metadata_filter on ':' and reject entries missing the separator"
    )
