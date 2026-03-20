"""
Tests for SEC-05: OAuth redirect URI hardening.

get_redirect_uri_from_request must ignore x-forwarded-host and all other
request headers, using settings.BASE_URL as the sole authority for the
callback host and scheme.
"""
import pytest
from unittest.mock import MagicMock


def _make_request(headers: dict) -> MagicMock:
    """Return a minimal mock starlette Request with the given headers."""
    req = MagicMock()
    req.headers = headers
    req.base_url = "http://localhost:8000/"
    return req


def test_redirect_uri_ignores_forwarded_host():
    """get_redirect_uri_from_request ignores x-forwarded-host and does not use it in the URI."""
    import importlib
    import app.core.config as config_mod
    importlib.reload(config_mod)

    # Supply an x-forwarded-host that points to an attacker's server
    evil_request = _make_request({
        "x-forwarded-host": "evil.com",
        "x-forwarded-proto": "https",
        "host": "evil.com",
    })

    uri = config_mod.Settings.get_redirect_uri_from_request(evil_request, "META")

    assert "evil.com" not in uri, (
        f"URI must not contain the attacker's host. Got: {uri!r}"
    )


def test_redirect_uri_uses_base_url():
    """get_redirect_uri_from_request returns a URI whose prefix matches settings.BASE_URL."""
    import importlib
    import app.core.config as config_mod
    importlib.reload(config_mod)

    # settings.BASE_URL is "http://localhost:8000" in the test environment
    settings = config_mod.settings
    expected_prefix = settings.BASE_URL

    request = _make_request({
        "x-forwarded-host": "evil.com",
        "host": "localhost:8000",
    })

    uri = config_mod.Settings.get_redirect_uri_from_request(request, "TIKTOK")

    # Strip trailing slash from BASE_URL for comparison
    from urllib.parse import urlparse
    parsed_base = urlparse(expected_prefix)
    expected_host = f"{parsed_base.scheme}://{parsed_base.netloc}"

    assert uri.startswith(expected_host), (
        f"URI should start with BASE_URL host '{expected_host}'. Got: {uri!r}"
    )
    assert "/api/v1/platforms/oauth/callback/tiktok" in uri, (
        f"Expected callback path in URI. Got: {uri!r}"
    )
