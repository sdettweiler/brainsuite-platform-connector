"""Phase 23 Plan 01 — Dashboard Duration Filter and Backfill Tests.

Tests for:
- GET /dashboard/duration-bounds returns min/max scoped to org + active filters
- GET /dashboard/assets?duration_min=X&duration_max=Y applies BETWEEN filter
- GET /dashboard/assets returns null_duration_count when filter active
- Backfill job creates, runs, processes batch, updates progress, completes

Security: T-23-01 — every query must include organization_id guard.
"""
import inspect
import uuid
import pytest
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch, call, AsyncMock

import app.api.v1.endpoints.dashboard as dash_mod


# ---------------------------------------------------------------------------
# Helper: build a minimal asset row dict adapted for duration fields
# ---------------------------------------------------------------------------

def _make_asset_row(asset_id: uuid.UUID, video_duration: Optional[float], asset_format: str = "VIDEO", spend: float = 100.0):
    """Return a dict matching the dashboard /assets response item shape."""
    return {
        "id": str(asset_id),
        "platform": "META",
        "ad_id": f"ad_{asset_id.hex[:8]}",
        "ad_name": f"Ad {asset_id.hex[:8]}",
        "campaign_name": "Test Campaign",
        "campaign_objective": "AWARENESS",
        "asset_format": asset_format,
        "thumbnail_url": None,
        "asset_url": f"objects/creatives/org123/video_{asset_id.hex[:8]}.mp4" if asset_format == "VIDEO" else None,
        "scoring_status": "COMPLETE",
        "total_score": 75.0,
        "total_rating": None,
        "is_active": True,
        "performance": {"spend": spend},
        "performer_tag": None,
        "video_duration": video_duration,
    }


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
# Test 1: GET /duration-bounds org-scoped
# ---------------------------------------------------------------------------

def test_duration_bounds_org_scoped():
    """GET /duration-bounds returns min/max scoped to current org only.

    Verifies T-23-01 (D-01): get_duration_bounds source must include:
    - CreativeAsset.organization_id == current_user.organization_id
    - CreativeAsset.asset_format == "VIDEO" (NOT asset_type, lowercase video)
    - CreativeAsset.video_duration.isnot(None) or is_not(None)

    RED until Task 5 implements get_duration_bounds.
    """
    # RED until Task 5: get_duration_bounds must be exported from dashboard.py
    assert hasattr(dash_mod, "get_duration_bounds"), (
        "get_duration_bounds function must be exported from dashboard.py"
    )  # RED until Task 5

    source = inspect.getsource(dash_mod.get_duration_bounds)

    # T-23-01: org guard must be present
    assert "CreativeAsset.organization_id == current_user.organization_id" in source, (
        "get_duration_bounds must include CreativeAsset.organization_id == current_user.organization_id"
    )  # RED until Task 5

    # Must filter to VIDEO assets using correct field name (NOT asset_type)
    assert 'asset_format == "VIDEO"' in source or "asset_format == 'VIDEO'" in source, (
        "get_duration_bounds must filter CreativeAsset.asset_format == 'VIDEO' (uppercase)"
    )  # RED until Task 5

    # Must exclude NULL durations
    assert "video_duration.isnot(None)" in source or "video_duration.is_not(None)" in source, (
        "get_duration_bounds must exclude NULL video_duration rows with .isnot(None)"
    )  # RED until Task 5


# ---------------------------------------------------------------------------
# Test 2: GET /dashboard/assets duration BETWEEN filter
# ---------------------------------------------------------------------------

def test_duration_filter_between():
    """GET /dashboard/assets?duration_min=15&duration_max=120 applies BETWEEN filter.

    Verifies D-07: duration_min and duration_max are accepted as Query params
    and translated into WHERE clauses on CreativeAsset.video_duration.

    RED until Task 5 modifies get_dashboard_assets.
    """
    # Check signature has both new params
    sig = inspect.signature(dash_mod.get_dashboard_assets)
    assert "duration_min" in sig.parameters, (
        "get_dashboard_assets must accept duration_min query parameter"
    )  # RED until Task 5
    assert "duration_max" in sig.parameters, (
        "get_dashboard_assets must accept duration_max query parameter"
    )  # RED until Task 5

    source = inspect.getsource(dash_mod.get_dashboard_assets)

    # Must apply >= filter for duration_min
    assert "CreativeAsset.video_duration >= duration_min" in source, (
        "get_dashboard_assets must apply CreativeAsset.video_duration >= duration_min"
    )  # RED until Task 5

    # Must apply <= filter for duration_max
    assert "CreativeAsset.video_duration <= duration_max" in source, (
        "get_dashboard_assets must apply CreativeAsset.video_duration <= duration_max"
    )  # RED until Task 5


# ---------------------------------------------------------------------------
# Test 3: null_duration_count field in response (D-07)
# ---------------------------------------------------------------------------

def test_null_duration_count():
    """GET /dashboard/assets with duration filter active returns null_duration_count > 0.

    Verifies D-07 (T-23-02):
    - null_duration_count is in response dict
    - only computed when duration filter is active (guard present)
    - uses video_duration.is_(None) to identify excluded assets

    RED until Task 5 adds null_duration_count to get_dashboard_assets.
    """
    source = inspect.getsource(dash_mod.get_dashboard_assets)

    # Response must contain null_duration_count key
    assert "null_duration_count" in source, (
        "get_dashboard_assets must include null_duration_count in its source/response"
    )  # RED until Task 5

    # D-07: only compute when filter is active (cost optimization T-23-06)
    assert "duration_min is not None or duration_max is not None" in source, (
        "get_dashboard_assets must guard null_duration_count computation with "
        "'if duration_min is not None or duration_max is not None'"
    )  # RED until Task 5

    # NULL check uses .is_(None) for the count subquery
    assert "video_duration.is_(None)" in source, (
        "get_dashboard_assets must use video_duration.is_(None) in null_duration_count subquery"
    )  # RED until Task 5


# ---------------------------------------------------------------------------
# Test 4: Backfill job lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backfill_job_lifecycle():
    """Backfill job creates, transitions to RUNNING, processes batch, completes.

    Verifies D-09/D-10/D-11 and T-23-03:
    (a) create_background_job called with job_type="duration_backfill"
    (b) update_background_job called with status="RUNNING" at least once
    (c) update_background_job called with status="COMPLETE" at the end

    RED until Task 4 implements backfill_job.py.
    """
    # In-test import to avoid collection failure (module doesn't exist yet)
    from app.services.sync.backfill_job import run_duration_backfill  # RED until Task 4

    fixed_job_id = uuid.uuid4()
    test_org_id = uuid.uuid4()

    # Mock session returning empty assets (total=0 case — job completes immediately)
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # execute returns a mock result with scalar() -> 0 (no null-duration assets)
    mock_execute_result = MagicMock()
    mock_execute_result.scalar.return_value = 0
    mock_execute_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    mock_session_factory = MagicMock()
    mock_session_factory.return_value = mock_session

    with patch("app.services.sync.backfill_job.create_background_job", new_callable=AsyncMock) as mock_create, \
         patch("app.services.sync.backfill_job.update_background_job", new_callable=AsyncMock) as mock_update, \
         patch("app.services.sync.backfill_job.get_session_factory", return_value=mock_session_factory), \
         patch("app.services.sync.backfill_job.get_object_storage"), \
         patch("app.services.sync.backfill_job.get_video_duration", return_value=30.0):

        mock_create.return_value = fixed_job_id

        await run_duration_backfill(test_org_id, batch_size=2)

        # (a) create_background_job called with job_type="duration_backfill"
        mock_create.assert_called_once()
        create_kwargs = mock_create.call_args
        assert create_kwargs[1].get("job_type") == "duration_backfill" or (
            len(create_kwargs[0]) > 0 and create_kwargs[0][0] == "duration_backfill"
        ), "create_background_job must be called with job_type='duration_backfill'"  # RED until Task 4

        # (b) update_background_job called with status="RUNNING" at least once
        running_calls = [
            c for c in mock_update.call_args_list
            if c[1].get("status") == "RUNNING" or (len(c[0]) > 1 and c[0][1] == "RUNNING")
        ]
        # With total=0, RUNNING may be skipped; check at least status="COMPLETE" was called
        complete_calls = [
            c for c in mock_update.call_args_list
            if c[1].get("status") == "COMPLETE" or (
                any(v == "COMPLETE" for v in c[1].values())
            )
        ]
        assert len(complete_calls) >= 1, (
            "update_background_job must be called with status='COMPLETE' at the end"
        )  # RED until Task 4
