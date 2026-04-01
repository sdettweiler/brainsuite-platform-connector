"""
TDD tests for GET /dashboard/correlation-data endpoint.

RED phase: These tests fail because the endpoint and helper function
_serialize_correlation_asset do not exist yet.
"""
import pytest
from unittest.mock import MagicMock

import app.api.v1.endpoints.dashboard as dashboard_module


def _mock_row(roas=None, total_score=75.0, total_spend=100.0,
              platform="META", ad_name="Test Ad", thumbnail_url="/thumb.jpg",
              asset_id="abc-123", ctr=None, vtr=None, cpm=None, cvr=None,
              cpc=None, conversions=None):
    row = MagicMock()
    row.roas = roas
    row.total_score = total_score
    row.total_spend = total_spend
    row.platform = platform
    row.ad_name = ad_name
    row.thumbnail_url = thumbnail_url
    row.id = asset_id
    row.ctr = ctr
    row.vtr = vtr
    row.cpm = cpm
    row.cvr = cvr
    row.cpc = cpc
    row.conversions = conversions
    return row


def test_correlation_endpoint_exists():
    """The get_correlation_data function must be defined in the dashboard module."""
    assert hasattr(dashboard_module, "get_correlation_data"), (
        "get_correlation_data not found in dashboard module"
    )


def test_serialize_helper_exists():
    """The _serialize_correlation_asset helper must be defined at module level."""
    assert hasattr(dashboard_module, "_serialize_correlation_asset"), (
        "_serialize_correlation_asset not found in dashboard module"
    )


def test_zero_roas_preserved():
    """roas=0.0 must be returned as 0.0, not coerced to None by falsy check."""
    row = _mock_row(roas=0.0)
    result = dashboard_module._serialize_correlation_asset(row)
    assert result["roas"] == 0.0, (
        f"Expected roas=0.0 but got {result['roas']!r}. "
        "Use `row.roas is not None` not `if row.roas`."
    )


def test_null_roas_returns_none():
    """roas=None must be returned as None — frontend handles exclusion."""
    row = _mock_row(roas=None)
    result = dashboard_module._serialize_correlation_asset(row)
    assert result["roas"] is None, (
        f"Expected roas=None but got {result['roas']!r}"
    )


def test_positive_roas_preserved():
    """Positive roas values must pass through as floats."""
    row = _mock_row(roas=3.5)
    result = dashboard_module._serialize_correlation_asset(row)
    assert result["roas"] == 3.5, (
        f"Expected roas=3.5 but got {result['roas']!r}"
    )


def test_serialization_returns_expected_keys():
    """Output must contain all expected keys for scatter chart including new metric fields."""
    row = _mock_row(roas=2.0)
    result = dashboard_module._serialize_correlation_asset(row)
    expected_keys = {
        "id", "ad_name", "platform", "thumbnail_url", "total_score",
        "roas", "spend", "ctr", "vtr", "cpm", "cvr", "cpc", "conversions",
    }
    assert set(result.keys()) == expected_keys, (
        f"Expected keys {expected_keys}, got {set(result.keys())}"
    )


def test_no_pagination_keys():
    """Correlation response must not include pagination keys (page, total_pages)."""
    row = _mock_row(roas=1.5)
    result = dashboard_module._serialize_correlation_asset(row)
    assert "page" not in result, "page key must not appear in correlation asset"
    assert "total_pages" not in result, "total_pages key must not appear in correlation asset"


def test_spend_field_maps_to_total_spend():
    """The 'spend' key in output must map from row.total_spend."""
    row = _mock_row(total_spend=500.0)
    result = dashboard_module._serialize_correlation_asset(row)
    assert result["spend"] == 500.0, (
        f"Expected spend=500.0 but got {result['spend']!r}"
    )


def test_new_metric_fields_returned_as_float():
    """ctr, vtr, cpm, cvr, cpc, conversions must be returned as floats when present."""
    row = _mock_row(
        roas=2.0, ctr=1.5, vtr=10.2, cpm=3.75, cvr=0.8, cpc=0.45, conversions=42.0
    )
    result = dashboard_module._serialize_correlation_asset(row)
    assert result["ctr"] == 1.5, f"Expected ctr=1.5 but got {result['ctr']!r}"
    assert result["vtr"] == 10.2, f"Expected vtr=10.2 but got {result['vtr']!r}"
    assert result["cpm"] == 3.75, f"Expected cpm=3.75 but got {result['cpm']!r}"
    assert result["cvr"] == 0.8, f"Expected cvr=0.8 but got {result['cvr']!r}"
    assert result["cpc"] == 0.45, f"Expected cpc=0.45 but got {result['cpc']!r}"
    assert result["conversions"] == 42.0, f"Expected conversions=42.0 but got {result['conversions']!r}"


def test_new_metric_fields_null_when_absent():
    """All new metric fields must return None when row values are None."""
    row = _mock_row(roas=1.0)  # ctr/vtr/cpm/cvr/cpc/conversions all default to None
    result = dashboard_module._serialize_correlation_asset(row)
    for field in ("ctr", "vtr", "cpm", "cvr", "cpc", "conversions"):
        assert result[field] is None, (
            f"Expected {field}=None but got {result[field]!r}"
        )
