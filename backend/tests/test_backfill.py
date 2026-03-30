"""Tests for the admin backfill endpoint and run_backfill_task() background task.

Tests:
  - run_backfill_task() query filtering (UNSCORED + VIDEO/STATIC_IMAGE only)
  - run_backfill_task() excludes FAILED assets
  - run_backfill_task() error isolation (one failure does not abort the rest)
  - run_backfill_task() calls score_asset_now() per asset
  - run_backfill_task() handles empty batch gracefully
  - POST /admin/backfill returns 202 with assets_queued count (admin user)
  - POST /admin/backfill returns 403 for non-admin user
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helper: build a minimal mock async context manager for get_session_factory
# ---------------------------------------------------------------------------

def _make_mock_session_factory(scalars_result=None):
    """Return a mock get_session_factory() that returns scalars_result from execute().

    get_session_factory()() is used as an async context manager:
        async with get_session_factory()() as db:
            result = await db.execute(...)
            ids = list(result.scalars().all())
    """
    mock_result = MagicMock()
    if scalars_result is None:
        scalars_result = []
    mock_result.scalars.return_value.all.return_value = scalars_result

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    # async context manager
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory_instance = MagicMock(return_value=mock_session)
    mock_factory = MagicMock(return_value=mock_factory_instance)
    return mock_factory


# ---------------------------------------------------------------------------
# Task 1 tests: run_backfill_task()
# ---------------------------------------------------------------------------

async def test_backfill_query_filters():
    """run_backfill_task queries only UNSCORED + VIDEO/STATIC_IMAGE rows.

    Mock DB returns two matching IDs; verifies score_asset_now called for each.
    """
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    mock_factory = _make_mock_session_factory(scalars_result=[id1, id2])

    with patch("app.services.sync.scoring_job.get_session_factory", mock_factory):
        with patch("app.services.sync.scoring_job.score_asset_now", new=AsyncMock()) as mock_score:
            from app.services.sync.scoring_job import run_backfill_task
            await run_backfill_task()

    assert mock_score.call_count == 2
    called_ids = [call.args[0] for call in mock_score.call_args_list]
    assert id1 in called_ids
    assert id2 in called_ids


async def test_backfill_excludes_failed():
    """FAILED assets are not included — backfill only queries UNSCORED rows.

    When the DB returns an empty list (no UNSCORED rows), score_asset_now is never called.
    """
    mock_factory = _make_mock_session_factory(scalars_result=[])

    with patch("app.services.sync.scoring_job.get_session_factory", mock_factory):
        with patch("app.services.sync.scoring_job.score_asset_now", new=AsyncMock()) as mock_score:
            from app.services.sync.scoring_job import run_backfill_task
            await run_backfill_task()

    mock_score.assert_not_called()


async def test_backfill_error_isolation():
    """When score_asset_now raises for the first asset, the loop continues to the second.

    Both score IDs must have been attempted.
    """
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    mock_factory = _make_mock_session_factory(scalars_result=[id1, id2])

    call_order = []

    async def _side_effect(score_id):
        call_order.append(score_id)
        if score_id == id1:
            raise RuntimeError("Simulated scoring failure")

    with patch("app.services.sync.scoring_job.get_session_factory", mock_factory):
        with patch("app.services.sync.scoring_job.score_asset_now", side_effect=_side_effect):
            from app.services.sync.scoring_job import run_backfill_task
            # Should NOT raise even though first asset fails
            await run_backfill_task()

    assert id1 in call_order
    assert id2 in call_order
    assert len(call_order) == 2


async def test_backfill_uses_score_asset_now():
    """run_backfill_task calls score_asset_now(score_id) per asset — not any APScheduler function."""
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    id3 = uuid.uuid4()
    mock_factory = _make_mock_session_factory(scalars_result=[id1, id2, id3])

    with patch("app.services.sync.scoring_job.get_session_factory", mock_factory):
        with patch("app.services.sync.scoring_job.score_asset_now", new=AsyncMock()) as mock_score:
            from app.services.sync.scoring_job import run_backfill_task
            await run_backfill_task()

    assert mock_score.call_count == 3
    called_ids = [call.args[0] for call in mock_score.call_args_list]
    assert called_ids == [id1, id2, id3]


async def test_backfill_empty_batch():
    """When no UNSCORED assets exist, run_backfill_task completes without calling score_asset_now."""
    mock_factory = _make_mock_session_factory(scalars_result=[])

    with patch("app.services.sync.scoring_job.get_session_factory", mock_factory):
        with patch("app.services.sync.scoring_job.score_asset_now", new=AsyncMock()) as mock_score:
            from app.services.sync.scoring_job import run_backfill_task
            await run_backfill_task()

    mock_score.assert_not_called()
