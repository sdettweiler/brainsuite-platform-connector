"""
Jobs REST API tests — Phase 19.

Tests: MON-01 through MON-07 (GET /jobs list, GET /jobs/{id} detail, DELETE /jobs bulk clear).

Run: cd backend && python -m pytest tests/test_jobs_api.py -x -q
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.endpoints.jobs import delete_jobs, get_job, list_jobs


def _make_superuser(is_superuser: bool = True, is_active: bool = True):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.is_superuser = is_superuser
    user.is_active = is_active
    return user


def _make_job(job_id=None, job_type="sync_daily", status="RUNNING", org_id=None):
    job = MagicMock()
    job.id = job_id or uuid.uuid4()
    job.job_type = job_type
    job.org_id = org_id or uuid.uuid4()
    job.status = status
    job.progress_current = 3
    job.progress_total = 10
    job.started_at = None
    job.ended_at = None
    job.metadata_ = {}
    job.output = {"fields": []}
    job.error = None
    return job


@pytest.mark.asyncio
async def test_list_jobs_200():
    # GET /api/v1/jobs superadmin -> 200, list of BackgroundJob rows
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [(_make_job(), "Test Org")]
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_user = _make_superuser()
    result = await list_jobs(limit=50, offset=0, db=mock_db, current_user=mock_user)
    assert isinstance(result, list)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_list_jobs_filter_by_type():
    # GET /api/v1/jobs?job_type=sync_daily -> only rows with job_type == "sync_daily"
    mock_db = AsyncMock()
    mock_result = MagicMock()
    filtered_job = _make_job(job_type="sync_daily")
    mock_result.all.return_value = [(filtered_job, "Test Org")]
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_user = _make_superuser()
    result = await list_jobs(job_type="sync_daily", limit=50, offset=0, db=mock_db, current_user=mock_user)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].job_type == "sync_daily"


@pytest.mark.asyncio
async def test_list_jobs_filter_by_status():
    # GET /api/v1/jobs?status=FAILED -> only rows with status == "FAILED"
    mock_db = AsyncMock()
    mock_result = MagicMock()
    failed_job = _make_job(status="FAILED")
    mock_result.all.return_value = [(failed_job, "Test Org")]
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_user = _make_superuser()
    result = await list_jobs(status="FAILED", limit=50, offset=0, db=mock_db, current_user=mock_user)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].status == "FAILED"


@pytest.mark.asyncio
async def test_list_jobs_pagination():
    # GET /api/v1/jobs?limit=2&offset=0 -> verify limit/offset passed to query (execute called once)
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [(_make_job(), "Org A"), (_make_job(), "Org B")]
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_user = _make_superuser()
    result = await list_jobs(limit=2, offset=0, db=mock_db, current_user=mock_user)
    assert isinstance(result, list)
    mock_db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_job_detail_200():
    # GET /api/v1/jobs/{id} superadmin -> JobDetail schema with output and error fields
    job = _make_job()
    job.platform_connection_id = None  # skip connection lookup
    org_mock = MagicMock()
    org_mock.name = "Test Org"
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(side_effect=[job, org_mock])
    mock_user = _make_superuser()
    from app.schemas.jobs import JobDetail
    result = await get_job(job_id=job.id, db=mock_db, current_user=mock_user)
    assert isinstance(result, JobDetail)
    assert result.job_type == job.job_type
    assert result.output == job.output
    assert result.error is None


@pytest.mark.asyncio
async def test_get_job_detail_404():
    # GET /api/v1/jobs/{nonexistent_id} -> 404 HTTPException
    from fastapi import HTTPException
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)
    mock_user = _make_superuser()
    with pytest.raises(HTTPException) as exc_info:
        await get_job(job_id=uuid.uuid4(), db=mock_db, current_user=mock_user)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_jobs_204():
    # DELETE /api/v1/jobs?job_type=sync_daily&status=COMPLETE superadmin -> 204, matching rows deleted
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_user = _make_superuser()
    result = await delete_jobs(job_type="sync_daily", status="COMPLETE", db=mock_db, current_user=mock_user)
    assert result.status_code == 204
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_jobs_403_non_superadmin():
    # GET /api/v1/jobs with non-superadmin user -> 403 HTTPException raised by get_current_superadmin
    from fastapi import HTTPException
    from app.api.v1.deps import get_current_superadmin
    mock_user = _make_superuser(is_superuser=False)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_superadmin(current_user=mock_user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_jobs_403_non_superadmin():
    # DELETE /api/v1/jobs with non-superadmin user -> 403 HTTPException
    from fastapi import HTTPException
    from app.api.v1.deps import get_current_superadmin
    mock_user = _make_superuser(is_superuser=False)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_superadmin(current_user=mock_user)
    assert exc_info.value.status_code == 403
