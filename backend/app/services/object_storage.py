import logging
import mimetypes
from typing import Optional, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class ObjectStorageService:
    def __init__(self):
        self._client = None
        self._presigned_client = None
        self._bucket_name = settings.S3_BUCKET_NAME

    def _ensure_client(self):
        if self._client is None:
            kwargs = {
                "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
                "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
                "region_name": settings.AWS_REGION or "us-east-1",
                "config": Config(signature_version="s3v4"),
            }
            if settings.S3_ENDPOINT_URL:
                kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
            self._client = boto3.client("s3", **kwargs)
            logger.info(
                f"S3 client initialized (bucket={self._bucket_name}, "
                f"endpoint={settings.S3_ENDPOINT_URL or 'AWS default'})"
            )
        return self._client

    @property
    def bucket_name(self) -> str:
        return self._bucket_name

    def _object_name(self, relative_path: str) -> str:
        return relative_path

    def served_url(self, relative_path: str) -> str:
        return f"/objects/{relative_path}"

    def upload_file(self, local_path: str, relative_path: str, content_type: Optional[str] = None) -> str:
        client = self._ensure_client()
        if content_type is None:
            content_type, _ = mimetypes.guess_type(local_path)
            if content_type is None:
                content_type = "application/octet-stream"
        extra_args = {"ContentType": content_type}
        client.upload_file(
            local_path,
            self._bucket_name,
            self._object_name(relative_path),
            ExtraArgs=extra_args,
        )
        served = self.served_url(relative_path)
        logger.info(f"Uploaded to S3: {relative_path} ({content_type})")
        return served

    def file_exists(self, relative_path: str) -> bool:
        try:
            client = self._ensure_client()
            client.head_object(Bucket=self._bucket_name, Key=self._object_name(relative_path))
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise

    def download_blob(self, relative_path: str) -> Tuple[Optional[bytes], Optional[str]]:
        try:
            client = self._ensure_client()
            response = client.get_object(Bucket=self._bucket_name, Key=self._object_name(relative_path))
            data = response["Body"].read()
            content_type = response.get("ContentType", "application/octet-stream")
            return data, content_type
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return None, None
            logger.warning(f"Failed to download blob {relative_path}: {type(e).__name__}: {e}")
            return None, None

    def get_blob_metadata(self, relative_path: str) -> Optional[dict]:
        try:
            client = self._ensure_client()
            response = client.head_object(Bucket=self._bucket_name, Key=self._object_name(relative_path))
            return {
                "content_type": response.get("ContentType", "application/octet-stream"),
                "size": response.get("ContentLength", 0),
            }
        except ClientError:
            return None

    def _ensure_presigned_client(self):
        """Separate boto3 client for presigned URL generation.

        Presigned URLs embed the endpoint host in the HMAC signature — the host
        must be the one the browser will actually use.  We initialise this client
        with S3_PUBLIC_URL (browser-reachable) rather than S3_ENDPOINT_URL
        (Docker-internal).  generate_presigned_url() is purely cryptographic and
        makes no network call, so it works even though the backend container
        cannot reach S3_PUBLIC_URL itself.
        """
        if self._presigned_client is None:
            endpoint = settings.S3_PUBLIC_URL or settings.S3_ENDPOINT_URL
            kwargs = {
                "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
                "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
                "region_name": settings.AWS_REGION or "us-east-1",
                "config": Config(signature_version="s3v4"),
            }
            if endpoint:
                kwargs["endpoint_url"] = endpoint
            self._presigned_client = boto3.client("s3", **kwargs)
            logger.info(f"S3 presigned client initialized (endpoint={endpoint})")
        return self._presigned_client

    def generate_signed_url(self, relative_path: str, ttl_sec: int = 3600) -> Optional[str]:
        try:
            client = self._ensure_presigned_client()
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket_name, "Key": self._object_name(relative_path)},
                ExpiresIn=ttl_sec,
            )
            return url
        except ClientError as e:
            logger.warning(f"Signed URL generation failed: {e}")
            return None

    def delete_blob(self, relative_path: str) -> bool:
        try:
            client = self._ensure_client()
            client.delete_object(Bucket=self._bucket_name, Key=self._object_name(relative_path))
            logger.info(f"Deleted from S3: {relative_path}")
            return True
        except ClientError as e:
            logger.warning(f"Failed to delete blob {relative_path}: {type(e).__name__}: {e}")
            return False

    def list_blobs(self, prefix: str) -> list:
        try:
            client = self._ensure_client()
            full_prefix = self._object_name(prefix)
            paginator = client.get_paginator("list_objects_v2")
            paths = []
            for page in paginator.paginate(Bucket=self._bucket_name, Prefix=full_prefix):
                for obj in page.get("Contents", []):
                    paths.append(obj["Key"])
            return paths
        except ClientError as e:
            logger.warning(f"Failed to list blobs with prefix {prefix}: {type(e).__name__}: {e}")
            return []

    def delete_blobs_by_prefix(self, prefix: str) -> int:
        paths = self.list_blobs(prefix)
        deleted = 0
        for path in paths:
            if self.delete_blob(path):
                deleted += 1
        return deleted


_instance: Optional[ObjectStorageService] = None


def get_object_storage() -> ObjectStorageService:
    global _instance
    if _instance is None:
        _instance = ObjectStorageService()
    return _instance
