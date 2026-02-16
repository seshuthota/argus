"""S3-backed artifact storage."""

from __future__ import annotations

from typing import Any

from .base import BaseStorage


class S3Storage(BaseStorage):
    """Artifact storage backend for Amazon S3."""

    @property
    def scheme(self) -> str:
        return "s3"

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        super().__init__(bucket=bucket, prefix=prefix)
        self._client = client or self._build_client(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

    @staticmethod
    def _build_client(
        *,
        aws_access_key_id: str | None,
        aws_secret_access_key: str | None,
    ) -> Any:
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - import is environment-specific
            raise RuntimeError(
                "S3 storage requires boto3. Install boto3 to enable s3:// report uploads."
            ) from exc

        kwargs: dict[str, Any] = {}
        if aws_access_key_id:
            kwargs["aws_access_key_id"] = aws_access_key_id
        if aws_secret_access_key:
            kwargs["aws_secret_access_key"] = aws_secret_access_key
        return boto3.client("s3", **kwargs)

    def save_bytes(
        self,
        *,
        data: bytes,
        object_key: str,
        content_type: str | None = None,
    ) -> str:
        put_kwargs: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": object_key,
            "Body": data,
        }
        if content_type:
            put_kwargs["ContentType"] = content_type
        self._client.put_object(**put_kwargs)
        return self.build_uri(object_key)

