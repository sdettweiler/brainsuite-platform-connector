"""Phase 12: Static analysis tests for schema migration + pipeline re-wire."""
import pathlib
import inspect
import pytest


BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_brainsuite_app_has_system_app_name():
    """BrainsuiteApp model must have system_app_name column."""
    from app.models.platform import BrainsuiteApp
    assert hasattr(BrainsuiteApp, "system_app_name"), "BrainsuiteApp missing system_app_name"


def test_org_config_no_video_app_name():
    """OrgBrainsuiteConfig must NOT have video_app_name (dropped in Phase 12)."""
    src = (BACKEND_ROOT / "app" / "models" / "brainsuite_config.py").read_text()
    assert "video_app_name" not in src, "video_app_name still in brainsuite_config.py"


def test_org_config_no_static_app_name():
    """OrgBrainsuiteConfig must NOT have static_app_name (dropped in Phase 12)."""
    src = (BACKEND_ROOT / "app" / "models" / "brainsuite_config.py").read_text()
    assert "static_app_name" not in src, "static_app_name still in brainsuite_config.py"


def test_scoring_job_no_video_app_name():
    """scoring_job.py must not reference video_app_name (re-wired in Phase 12)."""
    src = (BACKEND_ROOT / "app" / "services" / "sync" / "scoring_job.py").read_text()
    assert "video_app_name" not in src, "video_app_name still in scoring_job.py"


def test_scoring_job_no_static_app_name():
    """scoring_job.py must not reference static_app_name (re-wired in Phase 12)."""
    src = (BACKEND_ROOT / "app" / "services" / "sync" / "scoring_job.py").read_text()
    assert "static_app_name" not in src, "static_app_name still in scoring_job.py"


def test_scoring_job_imports_brainsuite_app():
    """scoring_job.py must import BrainsuiteApp for system_app_name lookup."""
    src = (BACKEND_ROOT / "app" / "services" / "sync" / "scoring_job.py").read_text()
    assert "from app.models.platform import BrainsuiteApp" in src, "BrainsuiteApp import missing from scoring_job.py"


def test_scoring_job_uses_system_app_name():
    """scoring_job.py must reference system_app_name (the replacement column)."""
    src = (BACKEND_ROOT / "app" / "services" / "sync" / "scoring_job.py").read_text()
    assert "system_app_name" in src, "system_app_name not found in scoring_job.py"


def test_brainsuite_app_response_has_system_app_name():
    """BrainsuiteAppResponse schema must include system_app_name."""
    from app.schemas.platform import BrainsuiteAppResponse
    src = inspect.getsource(BrainsuiteAppResponse)
    assert "system_app_name" in src, "system_app_name missing from BrainsuiteAppResponse"


def test_migration_file_exists():
    """Phase 12 migration file must exist."""
    versions_dir = BACKEND_ROOT / "alembic" / "versions"
    migration = versions_dir / "u2v3w4x5y6z7_phase12_system_app_name.py"
    assert migration.exists(), "Migration file u2v3w4x5y6z7_phase12_system_app_name.py not found"


def test_migration_chains_from_phase11():
    """Phase 12 migration must chain from Phase 11 head."""
    versions_dir = BACKEND_ROOT / "alembic" / "versions"
    migration = versions_dir / "u2v3w4x5y6z7_phase12_system_app_name.py"
    src = migration.read_text()
    assert 'down_revision = "t1u2v3w4x5y6"' in src, "Migration does not chain from t1u2v3w4x5y6"
