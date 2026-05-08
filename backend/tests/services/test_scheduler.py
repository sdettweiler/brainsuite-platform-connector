"""Unit tests for startup_scheduler() cleanup job registration (Phase 16)."""
import pytest
from unittest.mock import MagicMock, patch, call
from apscheduler.triggers.cron import CronTrigger


@pytest.mark.asyncio
async def test_cleanup_job_registration():
    """cleanup_background_jobs is registered with CronTrigger(hour=3, minute=0)
    inside the SCHEDULER_ENABLED guard in startup_scheduler()."""
    mock_scheduler = MagicMock()
    mock_settings = MagicMock()
    mock_settings.SCHEDULER_ENABLED = True

    with patch("app.core.config.settings", mock_settings), \
         patch("app.services.sync.scheduler.scheduler", mock_scheduler):
        from app.services.sync.scheduler import startup_scheduler
        await startup_scheduler()

    # Extract all add_job calls and find the cleanup_background_jobs one
    add_job_calls = mock_scheduler.add_job.call_args_list
    job_ids = [c.kwargs.get("id") or (c.args[1] if len(c.args) > 1 else None)
               for c in add_job_calls]
    # Prefer keyword argument 'id' from each call
    job_ids_kw = []
    for c in add_job_calls:
        job_ids_kw.append(c.kwargs.get("id"))

    assert "cleanup_background_jobs" in job_ids_kw, (
        f"Expected cleanup_background_jobs in registered job ids, got: {job_ids_kw}"
    )

    # Verify the trigger is CronTrigger(hour=3, minute=0)
    cleanup_call = next(
        c for c in add_job_calls if c.kwargs.get("id") == "cleanup_background_jobs"
    )
    trigger = cleanup_call.kwargs.get("trigger")
    assert isinstance(trigger, CronTrigger), (
        f"Expected CronTrigger, got: {type(trigger)}"
    )
    # CronTrigger fields: hour=3, minute=0
    fields = {f.name: str(f) for f in trigger.fields}
    assert fields.get("hour") == "3", f"Expected hour=3, got: {fields.get('hour')}"
    assert fields.get("minute") == "0", f"Expected minute=0, got: {fields.get('minute')}"
