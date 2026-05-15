"""
Tests for Tasks 14-02-01 and 14-02-02 | COOK-02 | T-14-02 / T-14-05

Behaviors:
- system_config singleton_guard unique constraint prevents second row at DB level
- Cookies stored via Fernet encryption (encrypt_token/decrypt_token roundtrip)
"""
import uuid
import pytest


# ---------------------------------------------------------------------------
# Gap 3: singleton_guard unique constraint enforces exactly one row (14-02-01)
# ---------------------------------------------------------------------------

def test_system_config_model_has_singleton_guard():
    """SystemConfig model has singleton_guard column with unique=True."""
    from app.models.system_config import SystemConfig
    from sqlalchemy import inspect as sa_inspect

    mapper = sa_inspect(SystemConfig)
    col = mapper.columns["singleton_guard"]

    # Column must exist and be unique
    assert col is not None, "singleton_guard column not found on SystemConfig"
    assert col.unique is True, "singleton_guard column must have unique=True"


def test_system_config_model_has_unique_constraint():
    """SystemConfig __table_args__ declares uq_system_config_singleton UNIQUE constraint."""
    from app.models.system_config import SystemConfig
    from sqlalchemy import UniqueConstraint

    constraint_names = {
        c.name
        for c in SystemConfig.__table_args__
        if isinstance(c, UniqueConstraint)
    }

    assert "uq_system_config_singleton" in constraint_names, (
        f"Expected uq_system_config_singleton unique constraint, found: {constraint_names}"
    )


def test_system_config_singleton_guard_default_is_x():
    """SystemConfig singleton_guard column definition has default='X'."""
    from app.models.system_config import SystemConfig
    from sqlalchemy import inspect as sa_inspect

    mapper = sa_inspect(SystemConfig)
    col = mapper.columns["singleton_guard"]

    # The column default is a ColumnDefault whose arg is 'X'
    assert col.default is not None, "singleton_guard column must have a default defined"
    default_arg = col.default.arg
    assert default_arg == "X", (
        f"Expected singleton_guard default arg='X', got {default_arg!r}"
    )


def test_system_config_has_cookie_columns():
    """SystemConfig has both youtube_cookies_encrypted and youtube_cookies_backup_encrypted Text columns."""
    from app.models.system_config import SystemConfig
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import Text

    mapper = sa_inspect(SystemConfig)

    primary_col = mapper.columns["youtube_cookies_encrypted"]
    backup_col = mapper.columns["youtube_cookies_backup_encrypted"]

    assert primary_col is not None, "youtube_cookies_encrypted column missing"
    assert backup_col is not None, "youtube_cookies_backup_encrypted column missing"

    # Both must be nullable (cookies are not set at creation time)
    assert primary_col.nullable is True, "youtube_cookies_encrypted must be nullable"
    assert backup_col.nullable is True, "youtube_cookies_backup_encrypted must be nullable"


# ---------------------------------------------------------------------------
# Gap 4: Fernet encrypt/decrypt roundtrip (14-02-02)
# ---------------------------------------------------------------------------

def test_cookie_encryption():
    """encrypt_token/decrypt_token roundtrip preserves the original cookie string."""
    from app.core.security import encrypt_token, decrypt_token

    # Simulate a real-ish Netscape cookie file fragment
    original = (
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t9999999999\tYSC\ttest_cookie_value\n"
    )

    encrypted = encrypt_token(original)

    # Encrypted value must differ from plaintext
    assert encrypted != original, "encrypt_token must not return plaintext"
    # Encrypted value must be a non-empty string
    assert isinstance(encrypted, str) and len(encrypted) > 0

    decrypted = decrypt_token(encrypted)

    assert decrypted == original, (
        f"Roundtrip failed. Expected:\n{original!r}\nGot:\n{decrypted!r}"
    )


def test_cookie_encryption_different_values_produce_different_ciphertext():
    """Two different cookie strings produce different ciphertext (Fernet uses random IV)."""
    from app.core.security import encrypt_token

    cookie_a = "cookie_content_alpha"
    cookie_b = "cookie_content_beta"

    enc_a = encrypt_token(cookie_a)
    enc_b = encrypt_token(cookie_b)

    assert enc_a != enc_b, (
        "Different inputs should produce different ciphertext"
    )


def test_cookie_encryption_same_value_produces_different_ciphertext_each_time():
    """Fernet uses a random IV, so encrypting the same string twice yields different ciphertext."""
    from app.core.security import encrypt_token

    cookie = "same_cookie_value"
    enc1 = encrypt_token(cookie)
    enc2 = encrypt_token(cookie)

    # Fernet uses random IV — ciphertext should differ each call
    assert enc1 != enc2, (
        "Fernet should produce different ciphertext on each call (random IV)"
    )


# ---------------------------------------------------------------------------
# Phase 20 Wave 0 failing stub — proxy schema column verification
# This test MUST FAIL until Task 2 adds the columns to the SystemConfig model.
# ---------------------------------------------------------------------------

def test_proxy_columns_exist():
    """SystemConfig has proxy_url_encrypted (Text nullable) and proxy_enabled (Boolean default false) columns.

    Fails until Task 2 adds proxy_url_encrypted and proxy_enabled to the SystemConfig ORM model.
    """
    from app.models.system_config import SystemConfig
    from sqlalchemy import inspect as sa_inspect, Text, Boolean

    mapper = sa_inspect(SystemConfig)

    assert "proxy_url_encrypted" in mapper.columns, "proxy_url_encrypted column missing from SystemConfig"
    proxy_url_col = mapper.columns["proxy_url_encrypted"]
    assert proxy_url_col.nullable is True, "proxy_url_encrypted must be nullable"

    assert "proxy_enabled" in mapper.columns, "proxy_enabled column missing from SystemConfig"
    proxy_enabled_col = mapper.columns["proxy_enabled"]
    assert proxy_enabled_col.nullable is False, "proxy_enabled must not be nullable"
