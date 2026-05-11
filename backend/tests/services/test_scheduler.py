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
