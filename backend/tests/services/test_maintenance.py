"""Unit tests for cleanup_old_background_jobs (Phase 16)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_cleanup_old_background_jobs_deletes_old_records():
    """Cleanup function issues DELETE WHERE created_at < 30 days ago."""
    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    mock_session_factory = MagicMock(return_value=mock_db)

    with patch("app.services.sync.maintenance.get_session_factory", return_value=mock_session_factory):
        from app.services.sync.maintenance import cleanup_old_background_jobs
        await cleanup_old_background_jobs()

    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_old_background_jobs_rollback_on_error():
    """Cleanup function calls rollback and re-raises on DB error."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("DB error"))
    mock_db.rollback = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    mock_session_factory = MagicMock(return_value=mock_db)

    with patch("app.services.sync.maintenance.get_session_factory", return_value=mock_session_factory):
        from app.services.sync.maintenance import cleanup_old_background_jobs
        with pytest.raises(Exception, match="DB error"):
            await cleanup_old_background_jobs()

    mock_db.rollback.assert_called_once()
