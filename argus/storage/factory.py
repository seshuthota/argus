"""Factory helpers for storage backend resolution from URI."""

from __future__ import annotations

from urllib.parse import urlparse

from ..config import load_gcs_storage_config, load_s3_storage_config
from .base import BaseStorage
from .gcs_storage import GCSStorage
from .s3_storage import S3Storage


def is_remote_storage_uri(uri: str | None) -> bool:
    """Return true when URI uses a supported remote storage scheme."""
    if not uri:
        return False
    return urlparse(uri).scheme.lower() in {"s3", "gs"}


def _bucket_and_prefix(uri: str) -> tuple[str | None, str]:
    parsed = urlparse(uri)
    bucket = parsed.netloc.strip() or None
    prefix = parsed.path.lstrip("/")
    return bucket, prefix


def create_storage(output_uri: str) -> BaseStorage:
    """Create storage backend for a remote output URI."""
    parsed = urlparse(output_uri)
    scheme = parsed.scheme.lower()

    if scheme == "s3":
        bucket, prefix = _bucket_and_prefix(output_uri)
        cfg = load_s3_storage_config()
        resolved_bucket = bucket or cfg.bucket
        if not resolved_bucket:
            raise ValueError(
                "Missing S3 bucket. Provide bucket in output URI or set S3_BUCKET."
            )
        return S3Storage(
            bucket=resolved_bucket,
            prefix=prefix,
            aws_access_key_id=cfg.aws_access_key_id,
            aws_secret_access_key=cfg.aws_secret_access_key,
        )

    if scheme == "gs":
        bucket, prefix = _bucket_and_prefix(output_uri)
        cfg = load_gcs_storage_config()
        resolved_bucket = bucket or cfg.bucket
        if not resolved_bucket:
            raise ValueError(
                "Missing GCS bucket. Provide bucket in output URI or set GCS_BUCKET."
            )
        return GCSStorage(
            bucket=resolved_bucket,
            prefix=prefix,
            project=cfg.project,
            creds_path=cfg.creds_path,
        )

    raise ValueError(f"Unsupported storage URI scheme: {parsed.scheme!r}")

