"""
Phase 07 Plan 01 — PERCENT_RANK Performer Tag Tests.

Tests for:
- _compute_performer_tag() pure function unit tests
- 10-asset minimum guard: fewer than 10 scored assets = all null tags
- Boundary conditions: top 10% → "Top Performer", bottom 10% → "Below Average"
- Middle 80% → None
- Old _get_performer_tag() function is removed
- ad_account_id present in asset detail response

These tests start in RED (failing) until implementation is complete.
"""
import uuid
import pytest
import inspect
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Tests: _compute_performer_tag pure function
# ---------------------------------------------------------------------------


def test_compute_performer_tag_function_exists():
    """_compute_performer_tag must exist in dashboard module."""
    import app.api.v1.endpoints.dashboard as dash_mod
    assert hasattr(dash_mod, "_compute_performer_tag"), (
        "_compute_performer_tag must be defined in dashboard.py"
    )


def test_old_get_performer_tag_removed():
    """_get_performer_tag must be removed — replaced by _compute_performer_tag."""
    import app.api.v1.endpoints.dashboard as dash_mod
    assert not hasattr(dash_mod, "_get_performer_tag"), (
        "_get_performer_tag must be removed; use _compute_performer_tag instead"
    )


def test_minimum_guard():
    """Given fewer than 10 scored assets, all performer_tag values are null.

    _compute_performer_tag(0.95, 5) → None (total_scored < 10 guard applies)
    """
    from app.api.v1.endpoints.dashboard import _compute_performer_tag
    # Even a very high percentile rank returns None when total_scored < 10
    assert _compute_performer_tag(0.95, 5) is None
    assert _compute_performer_tag(0.99, 0) is None
    assert _compute_performer_tag(1.0, 9) is None
    assert _compute_performer_tag(0.0, 9) is None
    assert _compute_performer_tag(0.05, 5) is None


def test_minimum_guard_boundary_at_10():
    """Exactly 10 scored assets: minimum guard does NOT apply — tags ARE assigned."""
    from app.api.v1.endpoints.dashboard import _compute_performer_tag
    # With total_scored == 10, the guard is lifted (>= 10 check)
    # pct_rank=1.0 (top) → Top Performer
    assert _compute_performer_tag(1.0, 10) == "Top Performer"
    # pct_rank=0.0 (bottom) → Below Average
    assert _compute_performer_tag(0.0, 10) == "Below Average"


def test_percent_rank_top_performer():
    """pct_rank >= 0.90 with 20 assets → 'Top Performer'."""
    from app.api.v1.endpoints.dashboard import _compute_performer_tag
    assert _compute_performer_tag(0.90, 20) == "Top Performer"
    assert _compute_performer_tag(0.95, 20) == "Top Performer"
    assert _compute_performer_tag(1.0, 20) == "Top Performer"


def test_percent_rank_below_average():
    """pct_rank <= 0.10 with 20 assets → 'Below Average'."""
    from app.api.v1.endpoints.dashboard import _compute_performer_tag
    assert _compute_performer_tag(0.10, 20) == "Below Average"
    assert _compute_performer_tag(0.05, 20) == "Below Average"
    assert _compute_performer_tag(0.0, 20) == "Below Average"


def test_percent_rank_middle_null():
    """Middle 80% (pct_rank > 0.10 and < 0.90) with 20 assets → None."""
    from app.api.v1.endpoints.dashboard import _compute_performer_tag
    assert _compute_performer_tag(0.50, 20) is None
    assert _compute_performer_tag(0.11, 20) is None
    assert _compute_performer_tag(0.89, 20) is None
    assert _compute_performer_tag(0.45, 20) is None


def test_none_pct_rank_returns_none():
    """pct_rank=None always returns None regardless of total_scored."""
    from app.api.v1.endpoints.dashboard import _compute_performer_tag
    assert _compute_performer_tag(None, 20) is None
    assert _compute_performer_tag(None, 0) is None
    assert _compute_performer_tag(None, 100) is None


# ---------------------------------------------------------------------------
# Tests: PERCENT_RANK in dashboard.py implementation
# ---------------------------------------------------------------------------


def test_dashboard_uses_percent_rank():
    """get_dashboard_assets must use func.percent_rank() window function."""
    import app.api.v1.endpoints.dashboard as dash_mod
    source = inspect.getsource(dash_mod)
    assert "percent_rank" in source, (
        "dashboard.py must use func.percent_rank() for performer tagging"
    )


def test_dashboard_uses_compute_performer_tag():
    """get_dashboard_assets must call _compute_performer_tag, not _get_performer_tag."""
    import app.api.v1.endpoints.dashboard as dash_mod
    source = inspect.getsource(dash_mod.get_dashboard_assets)
    assert "_compute_performer_tag" in source, (
        "get_dashboard_assets must call _compute_performer_tag()"
    )
    assert "_get_performer_tag" not in source, (
        "get_dashboard_assets must not call _get_performer_tag() (removed)"
    )


# ---------------------------------------------------------------------------
# Tests: ad_account_id in asset detail response
# ---------------------------------------------------------------------------


def test_asset_detail_has_account_id():
    """GET /dashboard/assets/{id} response must include 'ad_account_id' field."""
    import app.api.v1.endpoints.dashboard as dash_mod
    source = inspect.getsource(dash_mod.get_asset_detail)
    assert '"ad_account_id"' in source or "'ad_account_id'" in source, (
        "get_asset_detail return dict must contain 'ad_account_id' field"
    )


def test_asset_detail_ad_account_id_from_asset():
    """ad_account_id in detail response must come from asset.ad_account_id."""
    import app.api.v1.endpoints.dashboard as dash_mod
    source = inspect.getsource(dash_mod.get_asset_detail)
    assert "asset.ad_account_id" in source, (
        "ad_account_id must be sourced from asset.ad_account_id"
    )
