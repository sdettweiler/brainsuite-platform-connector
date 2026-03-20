"""
Tests for SEC-04: Path traversal prevention in the /objects/ endpoint.

The serve_object endpoint must reject any path containing '..' segments,
including URL-encoded variants, with HTTP 400 and detail='Invalid asset path'.

NOTE: Standard HTTP clients (including httpx/TestClient) automatically normalize
raw `../../` sequences in URLs before sending — so `/objects/../../etc/passwd`
becomes `/etc/passwd` at the transport layer, returning a 404 (route not found).
The real attack surface is URL-encoded forms (`%2e%2e`) which bypass transport
normalization and must be caught in the endpoint. The raw `../..` case is still
"safe" (returns 404), but the encoded form is the critical test.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def test_traversal_attack_returns_400(app):
    """Path traversal using mixed encoding (..%2f) returns HTTP 400 with 'Invalid asset path'.

    httpx normalizes bare `../../` at the transport layer, so we use a mixed
    encoding form that survives transport normalization but must be caught by
    the endpoint's PurePosixPath check.
    """
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/objects/..%2fetc/passwd")
    assert response.status_code == 400
    assert response.json().get("detail") == "Invalid asset path"


def test_valid_asset_path_succeeds(app):
    """GET /objects/creatives/valid-image.jpg returns 200 for a legitimate path."""
    mock_storage = MagicMock()
    mock_storage.download_blob.return_value = (b"image-data", "image/jpeg")
    mock_storage.generate_signed_url.return_value = None

    with patch("app.services.object_storage.get_object_storage", return_value=mock_storage):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/objects/creatives/valid-image.jpg")

    assert response.status_code == 200


def test_double_dot_encoded_returns_400(app):
    """GET /objects/%2e%2e%2fetc%2fpasswd (fully URL-encoded traversal) returns HTTP 400."""
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/objects/%2e%2e%2fetc%2fpasswd")
    assert response.status_code == 400
    assert response.json().get("detail") == "Invalid asset path"
