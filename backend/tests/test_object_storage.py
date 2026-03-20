import importlib
import sys
import pytest
from unittest.mock import patch, MagicMock, call
from botocore.exceptions import ClientError


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "mock error"}}, "operation")


@pytest.fixture(autouse=True)
def mock_settings():
    with patch("app.services.object_storage.settings") as mock_s:
        mock_s.S3_ENDPOINT_URL = "http://minio:9000"
        mock_s.S3_BUCKET_NAME = "test-bucket"
        mock_s.AWS_ACCESS_KEY_ID = "testkey"
        mock_s.AWS_SECRET_ACCESS_KEY = "testsecret"
        mock_s.AWS_REGION = "us-east-1"
        yield mock_s


@pytest.fixture
def storage_service():
    # Reset singleton before each test
    import app.services.object_storage as mod
    mod._instance = None
    with patch("app.services.object_storage.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        service = mod.get_object_storage()
        yield service, mock_client
    mod._instance = None


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------

def test_upload_file(storage_service):
    service, mock_client = storage_service
    result = service.upload_file("/tmp/foo.jpg", "creatives/foo.jpg", content_type="image/jpeg")
    mock_client.upload_file.assert_called_once_with(
        "/tmp/foo.jpg",
        "test-bucket",
        "creatives/foo.jpg",
        ExtraArgs={"ContentType": "image/jpeg"},
    )
    assert result == "/objects/creatives/foo.jpg"


def test_upload_file_auto_content_type(storage_service):
    service, mock_client = storage_service
    result = service.upload_file("/tmp/image.png", "creatives/image.png", content_type=None)
    call_args = mock_client.upload_file.call_args
    assert call_args[1]["ExtraArgs"]["ContentType"] == "image/png"
    assert result == "/objects/creatives/image.png"


# ---------------------------------------------------------------------------
# file_exists
# ---------------------------------------------------------------------------

def test_file_exists_true(storage_service):
    service, mock_client = storage_service
    mock_client.head_object.return_value = {"ContentType": "image/jpeg"}
    assert service.file_exists("creatives/foo.jpg") is True
    mock_client.head_object.assert_called_once_with(Bucket="test-bucket", Key="creatives/foo.jpg")


def test_file_exists_false(storage_service):
    service, mock_client = storage_service
    mock_client.head_object.side_effect = _make_client_error("404")
    assert service.file_exists("creatives/foo.jpg") is False


# ---------------------------------------------------------------------------
# download_blob
# ---------------------------------------------------------------------------

def test_download_blob(storage_service):
    service, mock_client = storage_service
    mock_body = MagicMock()
    mock_body.read.return_value = b"filedata"
    mock_client.get_object.return_value = {"Body": mock_body, "ContentType": "image/jpeg"}
    data, content_type = service.download_blob("creatives/foo.jpg")
    assert data == b"filedata"
    assert content_type == "image/jpeg"
    mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="creatives/foo.jpg")


def test_download_blob_not_found(storage_service):
    service, mock_client = storage_service
    mock_client.get_object.side_effect = _make_client_error("404")
    data, content_type = service.download_blob("creatives/missing.jpg")
    assert data is None
    assert content_type is None


# ---------------------------------------------------------------------------
# get_blob_metadata
# ---------------------------------------------------------------------------

def test_get_blob_metadata(storage_service):
    service, mock_client = storage_service
    mock_client.head_object.return_value = {
        "ContentType": "image/jpeg",
        "ContentLength": 12345,
    }
    meta = service.get_blob_metadata("creatives/foo.jpg")
    assert meta == {"content_type": "image/jpeg", "size": 12345}


def test_get_blob_metadata_not_found(storage_service):
    service, mock_client = storage_service
    mock_client.head_object.side_effect = _make_client_error("404")
    assert service.get_blob_metadata("creatives/missing.jpg") is None


# ---------------------------------------------------------------------------
# generate_signed_url
# ---------------------------------------------------------------------------

def test_generate_signed_url(storage_service):
    service, mock_client = storage_service
    mock_client.generate_presigned_url.return_value = "https://minio:9000/test-bucket/creatives/foo.jpg?X-Amz-Signature=abc"
    url = service.generate_signed_url("creatives/foo.jpg", ttl_sec=7200)
    mock_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "test-bucket", "Key": "creatives/foo.jpg"},
        ExpiresIn=7200,
    )
    assert url == "https://minio:9000/test-bucket/creatives/foo.jpg?X-Amz-Signature=abc"


def test_generate_signed_url_error(storage_service):
    service, mock_client = storage_service
    mock_client.generate_presigned_url.side_effect = _make_client_error("AccessDenied")
    url = service.generate_signed_url("creatives/foo.jpg")
    assert url is None


# ---------------------------------------------------------------------------
# delete_blob
# ---------------------------------------------------------------------------

def test_delete_blob(storage_service):
    service, mock_client = storage_service
    result = service.delete_blob("creatives/foo.jpg")
    mock_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="creatives/foo.jpg")
    assert result is True


# ---------------------------------------------------------------------------
# list_blobs
# ---------------------------------------------------------------------------

def test_list_blobs(storage_service):
    service, mock_client = storage_service
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {"Contents": [{"Key": "creatives/a.jpg"}, {"Key": "creatives/b.jpg"}]},
    ]
    mock_client.get_paginator.return_value = mock_paginator
    paths = service.list_blobs("creatives/")
    mock_client.get_paginator.assert_called_once_with("list_objects_v2")
    mock_paginator.paginate.assert_called_once_with(Bucket="test-bucket", Prefix="creatives/")
    assert paths == ["creatives/a.jpg", "creatives/b.jpg"]


# ---------------------------------------------------------------------------
# delete_blobs_by_prefix
# ---------------------------------------------------------------------------

def test_delete_blobs_by_prefix(storage_service):
    service, mock_client = storage_service
    # Mock list_blobs to return two paths
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {"Contents": [{"Key": "creatives/a.jpg"}, {"Key": "creatives/b.jpg"}]},
    ]
    mock_client.get_paginator.return_value = mock_paginator
    count = service.delete_blobs_by_prefix("creatives/")
    assert count == 2
    assert mock_client.delete_object.call_count == 2


# ---------------------------------------------------------------------------
# served_url
# ---------------------------------------------------------------------------

def test_served_url(storage_service):
    service, _ = storage_service
    assert service.served_url("creatives/foo.jpg") == "/objects/creatives/foo.jpg"


# ---------------------------------------------------------------------------
# Static assertions — no GCS or sidecar references
# ---------------------------------------------------------------------------

def test_no_gcs_import():
    import inspect
    import app.services.object_storage as mod
    source = inspect.getsource(mod)
    assert "google.cloud" not in source
    assert "google.auth" not in source


def test_no_sidecar_reference():
    import inspect
    import app.services.object_storage as mod
    source = inspect.getsource(mod)
    assert "127.0.0.1:1106" not in source


def test_s3v4_signature():
    import inspect
    import app.services.object_storage as mod
    source = inspect.getsource(mod)
    assert "s3v4" in source
