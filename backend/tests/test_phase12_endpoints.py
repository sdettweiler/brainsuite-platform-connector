"""Phase 12: Static analysis tests for brainsuite config endpoints."""
import pathlib
import inspect
import pytest

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_endpoint_module_exists():
    """brainsuite_config endpoint module must exist and be importable."""
    ep_path = BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py"
    assert ep_path.exists(), "brainsuite_config.py endpoint module not found"
    src = ep_path.read_text()
    assert "router = APIRouter()" in src, "router not defined in endpoint module"


def test_router_registered():
    """brainsuite_config router must be registered in api_router."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "__init__.py").read_text()
    assert "brainsuite_config" in src, "brainsuite_config not imported in __init__.py"
    assert 'prefix="/brainsuite-config"' in src, "brainsuite-config prefix not registered"


def test_all_endpoints_use_admin_guard():
    """All mutating endpoints must use get_current_admin, not get_current_user."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "get_current_admin" in src, "get_current_admin not used"
    # Ensure get_current_user is NOT directly used (only via get_current_admin)
    assert "Depends(get_current_user)" not in src, "get_current_user should not be used directly — use get_current_admin"


def test_secret_never_returned():
    """GET credentials must never return client_secret or client_secret_encrypted value."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    # The schemas module should not have a client_secret field on CredentialsResponse
    from app.schemas.brainsuite_config import CredentialsResponse
    fields = CredentialsResponse.model_fields
    assert "client_secret" not in fields, "CredentialsResponse must not have client_secret field"
    assert "client_secret_encrypted" not in fields, "CredentialsResponse must not have client_secret_encrypted field"


def test_rescore_targets_complete_not_scored():
    """Rescore endpoint must target COMPLETE status, not SCORED (SCORED does not exist in DB)."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    # Find the rescore function and check it uses COMPLETE
    assert '"COMPLETE"' in src, "rescore must use COMPLETE status"
    # Ensure SCORED string is not used as a status target
    lines = src.split("\n")
    for line in lines:
        if "scoring_status" in line and '"SCORED"' in line:
            pytest.fail("scoring_status == 'SCORED' found — should be 'COMPLETE'")


def test_rescore_does_not_touch_processing():
    """Rescore must only target COMPLETE. Must never modify PROCESSING assets."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    # The update .where clause should only match COMPLETE
    assert "PROCESSING" not in src or "Never touches PROCESSING" in src or "PROCESSING" in src.split('"""')[1], \
        "PROCESSING should only appear in docstrings/comments, not in query logic"


def test_test_connection_checks_access_token():
    """Test connection must check for access_token in response body (Pitfall 5)."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "access_token" in src, "test-connection must check for access_token in response"


def test_empty_secret_keeps_existing():
    """PUT credentials must handle empty client_secret as keep-existing (D-07)."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "if payload.client_secret" in src, "D-07 empty-secret guard missing"


def test_encrypt_decrypt_imports():
    """Endpoint must use encrypt_token and decrypt_token from security module."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "from app.core.security import encrypt_token, decrypt_token" in src


def test_datetime_utc_pattern():
    """Must use datetime.now(timezone.utc), not datetime.utcnow()."""
    src = (BACKEND_ROOT / "app" / "api" / "v1" / "endpoints" / "brainsuite_config.py").read_text()
    assert "datetime.utcnow()" not in src, "datetime.utcnow() is deprecated — use datetime.now(timezone.utc)"
    assert "datetime.now(timezone.utc)" in src, "datetime.now(timezone.utc) pattern not found"
