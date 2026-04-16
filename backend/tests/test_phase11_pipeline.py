"""Phase 11 Plan 03 — Pipeline re-wire unit tests.

Tests verify:
  - _mark_unscored helper signature and PENDING guard
  - Partial config detection logic in _process_asset
  - Per-org token dict caching in BrainSuiteScoreService and BrainSuiteStaticScoreService
  - No hardcoded app name strings remain in either score service
  - No global settings credential reads remain in either score service
  - scoring_job.py has required imports for OrgBrainsuiteConfig and decrypt_token

These are static analysis + instantiation tests — no live DB or HTTP calls needed.
"""
import inspect
import pathlib

import pytest

# ---------------------------------------------------------------------------
# Paths to service source files (used for text-based assertions)
# ---------------------------------------------------------------------------

_BACKEND = pathlib.Path(__file__).parent.parent
_SCORE_PY = _BACKEND / "app" / "services" / "brainsuite_score.py"
_STATIC_PY = _BACKEND / "app" / "services" / "brainsuite_static_score.py"
_JOB_PY = _BACKEND / "app" / "services" / "sync" / "scoring_job.py"


# ---------------------------------------------------------------------------
# 1. test_no_config_unscored
# ---------------------------------------------------------------------------

def test_no_config_unscored():
    """_mark_unscored sets scoring_status=UNSCORED and only transitions PENDING rows."""
    from app.services.sync.scoring_job import _mark_unscored

    # Verify function signature
    sig = inspect.signature(_mark_unscored)
    params = list(sig.parameters.keys())
    assert "score_id" in params
    assert "error_reason" in params

    # Read source to verify PENDING guard and UNSCORED assignment
    source = inspect.getsource(_mark_unscored)
    assert 'scoring_status == "PENDING"' in source, (
        "_mark_unscored must guard on scoring_status == 'PENDING' to avoid resetting PROCESSING assets"
    )
    assert 'scoring_status = "UNSCORED"' in source, (
        "_mark_unscored must set scoring_status = 'UNSCORED'"
    )
    assert "error_reason" in source, (
        "_mark_unscored must store the error_reason on the score row"
    )


# ---------------------------------------------------------------------------
# 2. test_partial_config_unscored
# ---------------------------------------------------------------------------

def test_partial_config_unscored():
    """_process_asset checks client_id, client_secret_encrypted, and required_app_name."""
    source = _JOB_PY.read_text()

    # All three required-field checks must be present
    assert "not org_config.client_id" in source, (
        "_process_asset must check org_config.client_id is present"
    )
    assert "not org_config.client_secret_encrypted" in source, (
        "_process_asset must check org_config.client_secret_encrypted is present"
    )
    assert "not required_app_name" in source, (
        "_process_asset must check required_app_name (set from video_app_name or static_app_name based on endpoint_type)"
    )

    # required_app_name is determined by endpoint_type — check the branch logic
    assert 'endpoint_type == "VIDEO"' in source, (
        "_process_asset must set required_app_name from video_app_name for VIDEO endpoint"
    )
    assert 'endpoint_type == "STATIC_IMAGE"' in source, (
        "_process_asset must set required_app_name from static_app_name for STATIC_IMAGE endpoint"
    )

    # Verify UNSCORED fallback is called (not an exception raise)
    assert "await _mark_unscored(score_id," in source, (
        "_process_asset must call _mark_unscored (not raise) on missing/incomplete config"
    )


# ---------------------------------------------------------------------------
# 3. test_token_cache_per_org (video service)
# ---------------------------------------------------------------------------

def test_token_cache_per_org():
    """BrainSuiteScoreService uses dict-based per-org token caching (not scalar)."""
    from app.services.brainsuite_score import BrainSuiteScoreService

    svc = BrainSuiteScoreService()

    # New dict attributes must exist
    assert hasattr(svc, "_tokens"), "BrainSuiteScoreService must have _tokens dict"
    assert isinstance(svc._tokens, dict), "_tokens must be a dict (org_id -> token)"

    assert hasattr(svc, "_token_expires"), "BrainSuiteScoreService must have _token_expires dict"
    assert isinstance(svc._token_expires, dict), "_token_expires must be a dict (org_id -> expiry)"

    # Old scalar attributes must be gone
    assert not hasattr(svc, "_token"), (
        "BrainSuiteScoreService must NOT have scalar _token attribute (replaced by _tokens dict)"
    )
    assert not hasattr(svc, "_token_expires_at"), (
        "BrainSuiteScoreService must NOT have scalar _token_expires_at attribute (replaced by _token_expires dict)"
    )


# ---------------------------------------------------------------------------
# 4. test_token_cache_per_org_static (static service)
# ---------------------------------------------------------------------------

def test_token_cache_per_org_static():
    """BrainSuiteStaticScoreService uses dict-based per-org token caching (not scalar)."""
    from app.services.brainsuite_static_score import BrainSuiteStaticScoreService

    svc = BrainSuiteStaticScoreService()

    # New dict attributes must exist
    assert hasattr(svc, "_tokens"), "BrainSuiteStaticScoreService must have _tokens dict"
    assert isinstance(svc._tokens, dict), "_tokens must be a dict (org_id -> token)"

    assert hasattr(svc, "_token_expires"), "BrainSuiteStaticScoreService must have _token_expires dict"
    assert isinstance(svc._token_expires, dict), "_token_expires must be a dict (org_id -> expiry)"

    # Old scalar attributes must be gone
    assert not hasattr(svc, "_token"), (
        "BrainSuiteStaticScoreService must NOT have scalar _token attribute (replaced by _tokens dict)"
    )
    assert not hasattr(svc, "_token_expires_at"), (
        "BrainSuiteStaticScoreService must NOT have scalar _token_expires_at attribute (replaced by _token_expires dict)"
    )


# ---------------------------------------------------------------------------
# 5. test_no_hardcoded_app_names
# ---------------------------------------------------------------------------

def test_no_hardcoded_app_names():
    """No hardcoded app name strings remain in either score service."""
    score_text = _SCORE_PY.read_text()
    static_text = _STATIC_PY.read_text()

    assert "ACE_VIDEO_SMV_API" not in score_text, (
        "brainsuite_score.py must not contain hardcoded 'ACE_VIDEO_SMV_API' — use {app_name} in URL"
    )
    assert "ACE_STATIC_SOCIAL_STATIC_API" not in static_text, (
        "brainsuite_static_score.py must not contain hardcoded 'ACE_STATIC_SOCIAL_STATIC_API' — use {app_name} in URL"
    )


# ---------------------------------------------------------------------------
# 6. test_no_global_settings_reads
# ---------------------------------------------------------------------------

def test_no_global_settings_reads():
    """Score services no longer read global settings for BrainSuite credentials."""
    score_text = _SCORE_PY.read_text()
    static_text = _STATIC_PY.read_text()

    assert "settings.BRAINSUITE_CLIENT_ID" not in score_text, (
        "brainsuite_score.py must not read settings.BRAINSUITE_CLIENT_ID (per-org credentials come from DB)"
    )
    assert "settings.BRAINSUITE_CLIENT_SECRET" not in score_text, (
        "brainsuite_score.py must not read settings.BRAINSUITE_CLIENT_SECRET (per-org credentials come from DB)"
    )
    assert "settings.BRAINSUITE_CLIENT_ID" not in static_text, (
        "brainsuite_static_score.py must not read settings.BRAINSUITE_CLIENT_ID (per-org credentials come from DB)"
    )
    assert "settings.BRAINSUITE_CLIENT_SECRET" not in static_text, (
        "brainsuite_static_score.py must not read settings.BRAINSUITE_CLIENT_SECRET (per-org credentials come from DB)"
    )


# ---------------------------------------------------------------------------
# 7. test_scoring_job_imports_config
# ---------------------------------------------------------------------------

def test_scoring_job_imports_config():
    """scoring_job.py imports OrgBrainsuiteConfig and decrypt_token."""
    source = _JOB_PY.read_text()

    assert "from app.models.brainsuite_config import OrgBrainsuiteConfig" in source, (
        "scoring_job.py must import OrgBrainsuiteConfig from app.models.brainsuite_config"
    )
    assert "from app.core.security import decrypt_token" in source, (
        "scoring_job.py must import decrypt_token from app.core.security"
    )
