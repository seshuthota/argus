"""Configuration helpers for environment-backed runtime settings."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _get_env(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


@dataclass(frozen=True)
class S3StorageConfig:
    """Resolved S3 storage settings from environment variables."""

    aws_access_key_id: str | None
    aws_secret_access_key: str | None
    bucket: str | None


@dataclass(frozen=True)
class GCSStorageConfig:
    """Resolved GCS storage settings from environment variables."""

    project: str | None
    bucket: str | None
    creds_path: str | None


def load_s3_storage_config() -> S3StorageConfig:
    """Load S3 config from environment variables."""

    return S3StorageConfig(
        aws_access_key_id=_get_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_get_env("AWS_SECRET_ACCESS_KEY"),
        bucket=_get_env("S3_BUCKET"),
    )


def load_gcs_storage_config() -> GCSStorageConfig:
    """Load GCS config from environment variables."""

    return GCSStorageConfig(
        project=_get_env("GCS_PROJECT"),
        bucket=_get_env("GCS_BUCKET"),
        creds_path=_get_env("GCS_CREDS_PATH"),
    )

