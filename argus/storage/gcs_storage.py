"""Google Cloud Storage-backed artifact storage."""

from __future__ import annotations

import os
from typing import Any

from .base import BaseStorage


class GCSStorage(BaseStorage):
    """Artifact storage backend for Google Cloud Storage."""

    @property
    def scheme(self) -> str:
        return "gs"

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "",
        project: str | None = None,
        creds_path: str | None = None,
        client: Any | None = None,
    ) -> None:
        super().__init__(bucket=bucket, prefix=prefix)
        self._client = client or self._build_client(project=project, creds_path=creds_path)
        self._bucket = self._client.bucket(self.bucket)

    @staticmethod
    def _build_client(*, project: str | None, creds_path: str | None) -> Any:
        try:
            from google.cloud import storage  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - import is environment-specific
            raise RuntimeError(
                "GCS storage requires google-cloud-storage. Install it to enable gs:// report uploads."
            ) from exc

        if creds_path:
            os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", creds_path)

        kwargs: dict[str, Any] = {}
        if project:
            kwargs["project"] = project
        return storage.Client(**kwargs)

    def save_bytes(
        self,
        *,
        data: bytes,
        object_key: str,
        content_type: str | None = None,
    ) -> str:
        blob = self._bucket.blob(object_key)
        blob.upload_from_string(data, content_type=content_type)
        return self.build_uri(object_key)

