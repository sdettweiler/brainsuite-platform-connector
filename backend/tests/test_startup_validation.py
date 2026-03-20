"""
Tests for SEC-03: Fernet key startup validation.

Settings must raise a ValidationError when TOKEN_ENCRYPTION_KEY is missing
or malformed, and must succeed with a valid Fernet key.

Strategy: We test Settings() directly by instantiating it with keyword args
rather than reloading the module (which also runs `settings = Settings()` at
module level and would raise outside of our pytest.raises context).
"""
import pytest
from pydantic import ValidationError
from cryptography.fernet import Fernet


def test_missing_fernet_key_raises():
    """Creating Settings with TOKEN_ENCRYPTION_KEY='' raises ValidationError."""
    import importlib
    import app.core.config as config_mod
    importlib.reload(config_mod)

    # Directly instantiate with an empty key — the field_validator must reject it.
    with pytest.raises((ValidationError, ValueError)):
        config_mod.Settings(TOKEN_ENCRYPTION_KEY="")


def test_malformed_fernet_key_raises():
    """Creating Settings with TOKEN_ENCRYPTION_KEY='not-a-valid-key' raises ValidationError."""
    import importlib
    import app.core.config as config_mod
    importlib.reload(config_mod)

    with pytest.raises((ValidationError, ValueError)):
        config_mod.Settings(TOKEN_ENCRYPTION_KEY="not-a-valid-fernet-key")


def test_valid_fernet_key_passes():
    """Creating Settings with a properly encoded Fernet key succeeds without error."""
    import importlib
    import app.core.config as config_mod
    importlib.reload(config_mod)

    valid_key = Fernet.generate_key().decode()

    # Settings reads from env vars; supply the required key via kwargs.
    instance = config_mod.Settings(TOKEN_ENCRYPTION_KEY=valid_key)
    assert instance.TOKEN_ENCRYPTION_KEY == valid_key
