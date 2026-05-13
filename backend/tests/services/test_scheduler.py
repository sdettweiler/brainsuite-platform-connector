"""Unit tests for startup_scheduler() cleanup job registration (Phase 16)."""
import pytest
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, AsyncMock, patch
from apscheduler.triggers.cron import CronTrigger

# Pre-import modules that startup_scheduler lazily imports so that their
# module-level code (e.g. Fernet init in security.py) runs against real
# settings before any test patches replace app.core.config.settings.
import app.core.security  # noqa: F401
import app.services.sync.scoring_job  # noqa: F401
import app.services.sync.maintenance  # noqa: F401


@pytest.mark.asyncio
async def test_cleanup_job_registration():
    """cleanup_background_jobs is registered with CronTrigger(hour=3, minute=0)
    inside the SCHEDULER_ENABLED guard in startup_scheduler()."""
    mock_scheduler = MagicMock()
    mock_settings = MagicMock()
    mock_settings.SCHEDULER_ENABLED = True

    # execute() must be awaitable but its return value must be a plain MagicMock
    # so that result.scalars() is a sync call (not a coroutine).
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_execute_result

    @asynccontextmanager
    async def _mock_session():
        yield mock_db

    def _mock_session_factory():
        return _mock_session()

    mock_get_session_factory = MagicMock(return_value=_mock_session_factory)

    with patch("app.core.config.settings", mock_settings), \
         patch("app.services.sync.scheduler.scheduler", mock_scheduler), \
         patch("app.services.sync.scheduler.get_session_factory", mock_get_session_factory):
        from app.services.sync.scheduler import startup_scheduler
        await startup_scheduler()

    add_job_calls = mock_scheduler.add_job.call_args_list
    job_ids_kw = [c.kwargs.get("id") for c in add_job_calls]

    assert "cleanup_background_jobs" in job_ids_kw, (
        f"Expected cleanup_background_jobs in registered job ids, got: {job_ids_kw}"
    )

    cleanup_call = next(
        c for c in add_job_calls if c.kwargs.get("id") == "cleanup_background_jobs"
    )
    trigger = cleanup_call.kwargs.get("trigger")
    assert isinstance(trigger, CronTrigger), (
        f"Expected CronTrigger, got: {type(trigger)}"
    )
    fields = {f.name: str(f) for f in trigger.fields}
    assert fields.get("hour") == "3", f"Expected hour=3, got: {fields.get('hour')}"
    assert fields.get("minute") == "0", f"Expected minute=0, got: {fields.get('minute')}"


# ---------------------------------------------------------------------------
# Phase 19.3 (TDD RED): scoring_enabled gate tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_downloads_skipped_when_scoring_disabled():
    """All 4 platform download functions must return early when SystemConfig.scoring_enabled=False.

    RED baseline: before Wave 2 adds the scoring_enabled gate, create_background_job IS called
    for meta/tiktok deferred functions (which have no connection lookup before the job create).
    This test therefore FAILS before Wave 2 — confirming the gate is absent.
    """
    from app.services.sync.scheduler import (
        _run_google_ads_asset_downloads,
        _run_dv360_asset_downloads,
        _run_tiktok_creatives_deferred,
        _run_meta_creatives_deferred,
    )

    # mock_cfg simulates SystemConfig(scoring_enabled=False)
    mock_cfg = MagicMock()
    mock_cfg.scoring_enabled = False

    mock_scalar = MagicMock()
    # scalar_one_or_none() is synchronous in SQLAlchemy — use MagicMock not AsyncMock
    mock_scalar.scalar_one_or_none = MagicMock(return_value=mock_cfg)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_scalar)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    # get_session_factory()() is the session context manager — mock_session_factory() returns mock_db
    mock_session_factory = MagicMock(return_value=mock_db)

    with patch("app.services.sync.scheduler.get_session_factory", return_value=mock_session_factory), \
         patch("app.services.sync.scheduler.create_background_job", new_callable=AsyncMock) as mock_create_job:

        await _run_google_ads_asset_downloads("00000000-0000-0000-0000-000000000001", {})
        await _run_dv360_asset_downloads("00000000-0000-0000-0000-000000000001", {"queue": {}})
        await _run_tiktok_creatives_deferred("00000000-0000-0000-0000-000000000001", [])
        await _run_meta_creatives_deferred("00000000-0000-0000-0000-000000000001", [])

        assert mock_create_job.call_count == 0, (
            f"create_background_job was called {mock_create_job.call_count} time(s) "
            "despite scoring_enabled=False — scoring_enabled gate is missing in download functions!"
        )


@pytest.mark.asyncio
async def test_downloads_proceed_when_scoring_enabled():
    """Download functions must NOT return early when SystemConfig.scoring_enabled=True.

    This test verifies the normal path is not broken after Wave 2 adds the gate.
    We use _run_meta_creatives_deferred (no connection lookup before job creation) so
    the test is not sensitive to connection-lookup mocking complexity.

    Pre-Wave 2: passes trivially (no gate → create_background_job always called with empty ad_ids=0).
    Post-Wave 2 with scoring_enabled=True: gate allows through → still called.
    """
    from app.services.sync.scheduler import _run_meta_creatives_deferred

    mock_cfg = MagicMock()
    mock_cfg.scoring_enabled = True

    mock_scalar = MagicMock()
    # scalar_one_or_none() is synchronous in SQLAlchemy — use MagicMock not AsyncMock
    mock_scalar.scalar_one_or_none = MagicMock(return_value=mock_cfg)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_scalar)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    # get_session_factory()() is the session context manager — mock_session_factory() returns mock_db
    mock_session_factory = MagicMock(return_value=mock_db)

    with patch("app.services.sync.scheduler.get_session_factory", return_value=mock_session_factory), \
         patch("app.services.sync.scheduler.create_background_job", new_callable=AsyncMock) as mock_create_job, \
         patch("app.services.sync.scheduler.update_background_job", new_callable=AsyncMock):

        # scoring_enabled=True — function must NOT return early before creating the job
        try:
            await _run_meta_creatives_deferred("00000000-0000-0000-0000-000000000001", [])
        except Exception:
            pass  # downstream failures OK; early return before job creation is NOT

        assert mock_create_job.call_count >= 1, (
            "create_background_job was never called with scoring_enabled=True — "
            "gate incorrectly blocks when scoring is enabled!"
        )
