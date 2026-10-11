"""Document storage backend - ported 1:1 (behavior) from domain/storage.ts.

active_backend() = "s3" iff all three of s3_access_key_id/s3_secret_access_key/
s3_bucket are truthy; else "local" - preserve the exact 3-var AND check, not
a looser "bucket configured" reading. url_for() for the local backend hands
back the service's own auth-gated /download route, NOT a real public link -
a genuine Node gap (an emailed download link only works for a recipient with
a valid session unless S3 is configured), preserved as-is, not "fixed".
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from datetime import date

from app.core.config import settings

_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]")


def sanitise(filename: str) -> str:
    return _SANITIZE_RE.sub("_", filename)[:120]


def active_backend() -> str:
    if settings.s3_access_key_id and settings.s3_secret_access_key and settings.s3_bucket:
        return "s3"
    return "local"


def build_key(tenant_id: uuid.UUID, filename: str) -> str:
    return f"{tenant_id}/{date.today().isoformat()}/{uuid.uuid4()}-{sanitise(filename)}"


def checksum_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put(key: str, data: bytes, content_type: str) -> None:
    if active_backend() == "s3":
        _s3_put(key, data, content_type)
    else:
        _local_put(key, data)


def get(key: str) -> bytes:
    if active_backend() == "s3":
        return _s3_get(key)
    return _local_get(key)


def url_for(document_id: uuid.UUID, key: str) -> str:
    if active_backend() == "s3":
        return _s3_presigned_url(key)
    # Local backend has no real public link - hands back the service's own
    # auth-gated download route, matching Node's real behavior exactly.
    return f"/api/v1/documents/{document_id}/download"


def healthy() -> bool:
    if active_backend() == "s3":
        return _s3_healthy()
    try:
        os.makedirs(settings.document_local_dir, exist_ok=True)
        return True
    except OSError:
        return False


def _local_path(key: str) -> str:
    return os.path.join(settings.document_local_dir, key)


def _local_put(key: str, data: bytes) -> None:
    path = _local_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def _local_get(key: str) -> bytes:
    with open(_local_path(key), "rb") as f:
        return f.read()


def _s3_client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint or None,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
        config=Config(s3={"addressing_style": "path" if settings.s3_endpoint else "auto"}),
    )


def _s3_put(key: str, data: bytes, content_type: str) -> None:
    client = _s3_client()
    client.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type, Metadata={"checksum": checksum_of(data)})


def _s3_get(key: str) -> bytes:
    client = _s3_client()
    obj = client.get_object(Bucket=settings.s3_bucket, Key=key)
    return obj["Body"].read()


def _s3_presigned_url(key: str) -> str:
    client = _s3_client()
    return client.generate_presigned_url("get_object", Params={"Bucket": settings.s3_bucket, "Key": key}, ExpiresIn=settings.presigned_url_ttl_seconds)


def _s3_healthy() -> bool:
    try:
        client = _s3_client()
        client.head_bucket(Bucket=settings.s3_bucket)
        return True
    except Exception:  # noqa: BLE001
        return False
