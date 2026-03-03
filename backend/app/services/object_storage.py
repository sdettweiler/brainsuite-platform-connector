import os
import logging
import mimetypes
from typing import Optional, Tuple

from google.cloud import storage
from google.auth import identity_pool

logger = logging.getLogger(__name__)

REPLIT_SIDECAR_ENDPOINT = "http://127.0.0.1:1106"

_CREDENTIAL_CONFIG = {
    "type": "external_account",
    "audience": "replit",
    "subject_token_type": "access_token",
    "token_url": f"{REPLIT_SIDECAR_ENDPOINT}/token",
    "credential_source": {
        "url": f"{REPLIT_SIDECAR_ENDPOINT}/credential",
        "format": {
            "type": "json",
            "subject_token_field_name": "access_token",
        },
    },
    "universe_domain": "googleapis.com",
}


def _get_bucket_name() -> str:
    bucket = os.environ.get("DEFAULT_OBJECT_STORAGE_BUCKET_ID", "")
    if not bucket:
        raise RuntimeError("DEFAULT_OBJECT_STORAGE_BUCKET_ID not set")
    return bucket


def _get_public_prefix() -> str:
    paths = os.environ.get("PUBLIC_OBJECT_SEARCH_PATHS", "")
    if not paths:
        raise RuntimeError("PUBLIC_OBJECT_SEARCH_PATHS not set")
    first = paths.split(",")[0].strip()
    parts = first.strip("/").split("/", 1)
    if len(parts) < 2:
        return "public"
    return parts[1]


class ObjectStorageService:
    def __init__(self):
        self._client: Optional[storage.Client] = None
        self._bucket_name = ""
        self._public_prefix = ""

    def _ensure_client(self) -> storage.Client:
        if self._client is None:
            self._bucket_name = _get_bucket_name()
            self._public_prefix = _get_public_prefix()
            creds = identity_pool.Credentials.from_info(_CREDENTIAL_CONFIG)
            self._client = storage.Client(project="", credentials=creds)
            logger.info(f"Object storage client initialized (bucket={self._bucket_name})")
        return self._client

    @property
    def bucket_name(self) -> str:
        if not self._bucket_name:
            self._bucket_name = _get_bucket_name()
        return self._bucket_name

    @property
    def public_prefix(self) -> str:
        if not self._public_prefix:
            self._public_prefix = _get_public_prefix()
        return self._public_prefix

    def _object_name(self, relative_path: str) -> str:
        return f"{self.public_prefix}/{relative_path}"

    def served_url(self, relative_path: str) -> str:
        return f"/objects/{relative_path}"

    def upload_file(self, local_path: str, relative_path: str, content_type: Optional[str] = None) -> str:
        client = self._ensure_client()
        bucket = client.bucket(self.bucket_name)
        object_name = self._object_name(relative_path)

        if content_type is None:
            content_type, _ = mimetypes.guess_type(local_path)
            if content_type is None:
                content_type = "application/octet-stream"

        blob = bucket.blob(object_name)
        blob.upload_from_filename(local_path, content_type=content_type)
        served = self.served_url(relative_path)
        logger.info(f"Uploaded to object storage: {relative_path} ({content_type})")
        return served

    def file_exists(self, relative_path: str) -> bool:
        try:
            client = self._ensure_client()
            bucket = client.bucket(self.bucket_name)
            object_name = self._object_name(relative_path)
            blob = bucket.blob(object_name)
            return blob.exists()
        except Exception:
            return False

    def download_blob(self, relative_path: str) -> Tuple[Optional[bytes], Optional[str]]:
        try:
            client = self._ensure_client()
            bucket = client.bucket(self.bucket_name)
            object_name = self._object_name(relative_path)
            blob = bucket.blob(object_name)
            if not blob.exists():
                return None, None
            blob.reload()
            content_type = blob.content_type or "application/octet-stream"
            data = blob.download_as_bytes()
            return data, content_type
        except Exception as e:
            logger.warning(f"Failed to download blob {relative_path}: {type(e).__name__}: {e}")
            return None, None

    def get_blob_metadata(self, relative_path: str) -> Optional[dict]:
        try:
            client = self._ensure_client()
            bucket = client.bucket(self.bucket_name)
            object_name = self._object_name(relative_path)
            blob = bucket.blob(object_name)
            if not blob.exists():
                return None
            blob.reload()
            return {
                "content_type": blob.content_type or "application/octet-stream",
                "size": blob.size,
            }
        except Exception:
            return None

    def generate_signed_url(self, relative_path: str, ttl_sec: int = 3600) -> Optional[str]:
        import json
        import requests
        from datetime import datetime, timedelta, timezone

        object_name = self._object_name(relative_path)
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_sec)).isoformat()
        try:
            resp = requests.post(
                f"{REPLIT_SIDECAR_ENDPOINT}/object-storage/signed-object-url",
                json={
                    "bucket_name": self.bucket_name,
                    "object_name": object_name,
                    "method": "GET",
                    "expires_at": expires_at,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("signed_url")
            logger.warning(f"Signed URL request failed ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Signed URL generation failed: {type(e).__name__}: {e}")
        return None


_instance: Optional[ObjectStorageService] = None


def get_object_storage() -> ObjectStorageService:
    global _instance
    if _instance is None:
        _instance = ObjectStorageService()
    return _instance
