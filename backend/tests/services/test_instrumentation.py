"""Instrumentation tests — Phase 17 (INSTR-01 through INSTR-05).

Wave 0: stub file with skip-only bodies. Plan 17-06 (Wave 3) replaces each
skip with a real assertion after all Wave 2 production files are complete.

Requirement coverage:
  test_create_background_job_returns_uuid    — D-16 helper contract
  test_update_background_job_sets_status     — D-16 helper contract (ended_at on COMPLETE/FAILED)
  test_sync_job_creates_background_job       — INSTR-01 (D-01, D-03, D-12)
  test_download_progress_increments          — INSTR-02 (D-05, D-11, D-15)
  test_autofill_output_schema                — INSTR-03 (D-06, D-10)
  test_scoring_output_schema                 — INSTR-04 (D-07, D-08)
  test_error_traceback_truncated_at_10000_chars — D-13 (all job types)
"""
import pytest


# ---------------------------------------------------------------------------
# Helper tests (D-16)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_background_job_returns_uuid():
    # TODO (17-06): Mock get_session_factory in job_tracker scope.
    # Call create_background_job("sync_daily", org_id=<uuid>, ...).
    # Assert returned value is uuid.UUID instance.
    # Assert mock_db.add was called with a BackgroundJob instance.
    # Assert mock_db.commit was called.
    pytest.skip("Wave 0 stub — implement in 17-06")


@pytest.mark.asyncio
async def test_update_background_job_sets_status():
    # TODO (17-06): Mock get_session_factory; mock_db.get returns a MagicMock BackgroundJob.
    # Call update_background_job(job_id, status="COMPLETE").
    # Assert job.status == "COMPLETE".
    # Assert job.ended_at is not None (Pitfall 3 guard).
    # Call again with status="RUNNING" — assert ended_at is NOT set.
    pytest.skip("Wave 0 stub — implement in 17-06")


# ---------------------------------------------------------------------------
# INSTR-01: Sync instrumentation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_job_creates_background_job():
    # TODO (17-06): Mock get_session_factory + create_background_job + update_background_job
    # in scheduler module scope.
    # Call run_daily_sync(connection_id) with a mock that returns a valid PlatformConnection.
    # Assert create_background_job was called with job_type="sync_daily",
    #   org_id=connection.organization_id, platform_connection_id=connection.id.
    # Assert update_background_job was called with status="RUNNING".
    # Assert update_background_job was called with status="COMPLETE" and output dict
    #   containing keys: "platform", "sync_job_id", "records_fetched", "records_processed" (D-12).
    pytest.skip("Wave 0 stub — implement in 17-06")


# ---------------------------------------------------------------------------
# INSTR-02: Download instrumentation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_download_progress_increments():
    # TODO (17-06): Mock get_session_factory + create_background_job + update_background_job
    # + google_ads_sync.download_assets_post_commit.
    # Call _run_google_ads_asset_downloads(connection_id, asset_queue={3 assets}).
    # Assert create called once with job_type="download".
    # Assert update called with status="RUNNING", progress_total=3.
    # Assert final update has status="COMPLETE" and output with "downloaded"/"failed" lists (D-11).
    pytest.skip("Wave 0 stub — implement in 17-06")


# ---------------------------------------------------------------------------
# INSTR-03: Autofill instrumentation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_autofill_output_schema():
    # TODO (17-06): Mock create_background_job + update_background_job + _autofill in
    # ai_autofill scope. Call run_autofill_for_asset(asset_id, org_id).
    # Assert create called once with job_type="autofill".
    # Assert final update has status="COMPLETE" and output containing
    #   "fields" (list), "whisper_transcript", "language" (D-10).
    pytest.skip("Wave 0 stub — implement in 17-06")


# ---------------------------------------------------------------------------
# INSTR-04 + INSTR-05: Scoring instrumentation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scoring_output_schema():
    # TODO (17-06): Mock create_background_job + update_background_job + scoring deps.
    # Call _process_asset(score_id, mock_asset, "VIDEO").
    # Assert create called once with job_type="scoring", metadata containing
    #   "asset_id" and "creative_score_result_id" (D-09).
    # Assert update called with status="RUNNING".
    pytest.skip("Wave 0 stub — implement in 17-06")


# ---------------------------------------------------------------------------
# D-13: Error schema (all job types)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_traceback_truncated_at_10000_chars():
    # TODO (17-06): Construct a long exception (>10000 chars), trigger FAILED path
    # in any instrumented service. Assert error["traceback"] has len <= 10000,
    # error["type"] == exception class name, error["message"] == str(exc).
    pytest.skip("Wave 0 stub — implement in 17-06")
