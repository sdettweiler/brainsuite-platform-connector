"""
Jobs REST API tests — Phase 19.

Tests: MON-01 through MON-07 (GET /jobs list, GET /jobs/{id} detail, DELETE /jobs bulk clear).

Run: cd backend && python -m pytest tests/test_jobs_api.py -x -q
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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


def test_list_jobs_200():
    # GET /api/v1/jobs superadmin -> 200, list of JobListItem, no 'output' or 'error' keys in items
    pytest.skip("stub — implement after list_jobs endpoint exists in jobs.py")


def test_list_jobs_filter_by_type():
    # GET /api/v1/jobs?job_type=sync_daily -> only rows with job_type == "sync_daily"
    pytest.skip("stub — implement after list_jobs endpoint exists")


def test_list_jobs_filter_by_status():
    # GET /api/v1/jobs?status=FAILED -> only rows with status == "FAILED"
    pytest.skip("stub — implement after list_jobs endpoint exists")


def test_list_jobs_pagination():
    # GET /api/v1/jobs?limit=2&offset=0 -> max 2 rows returned; verify limit/offset applied to query
    pytest.skip("stub — implement after list_jobs endpoint exists")


def test_get_job_detail_200():
    # GET /api/v1/jobs/{id} superadmin -> 200, JobDetail with output and error fields present (may be None)
    pytest.skip("stub — implement after get_job endpoint exists")


def test_get_job_detail_404():
    # GET /api/v1/jobs/{nonexistent_id} -> 404 HTTPException
    pytest.skip("stub — implement after get_job endpoint exists")


def test_delete_jobs_204():
    # DELETE /api/v1/jobs?job_type=sync_daily&status=COMPLETE superadmin -> 204, matching rows deleted
    pytest.skip("stub — implement after delete_jobs endpoint exists")


def test_get_jobs_403_non_superadmin():
    # GET /api/v1/jobs with non-superadmin user -> 403 HTTPException raised by get_current_superadmin
    pytest.skip("stub — implement after list_jobs endpoint exists")


def test_delete_jobs_403_non_superadmin():
    # DELETE /api/v1/jobs with non-superadmin user -> 403 HTTPException
    pytest.skip("stub — implement after delete_jobs endpoint exists")
