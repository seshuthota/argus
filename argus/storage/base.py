"""Base abstractions for report artifact storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Any


class BaseStorage(ABC):
    """Abstract storage backend for JSON report artifacts."""

    def __init__(self, *, bucket: str, prefix: str = "") -> None:
        bucket_name = bucket.strip()
        if not bucket_name:
            raise ValueError("bucket must be non-empty")
        self.bucket = bucket_name
        self.prefix = self._normalize_prefix(prefix)

    @property
    @abstractmethod
    def scheme(self) -> str:
        """Storage URI scheme (for example `s3` or `gs`)."""

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        return prefix.strip().strip("/")

    def build_object_key(self, relative_path: str) -> str:
        path = relative_path.strip().lstrip("/")
        if not path:
            raise ValueError("relative_path must be non-empty")
        if self.prefix:
            return f"{self.prefix}/{path}"
        return path

    def build_uri(self, object_key: str) -> str:
        return f"{self.scheme}://{self.bucket}/{object_key}"

    @abstractmethod
    def save_bytes(
        self,
        *,
        data: bytes,
        object_key: str,
        content_type: str | None = None,
    ) -> str:
        """Persist bytes to storage and return the full URI."""

    def save_text(
        self,
        *,
        text: str,
        relative_path: str,
        content_type: str | None = "application/json",
    ) -> str:
        object_key = self.build_object_key(relative_path)
        return self.save_bytes(
            data=text.encode("utf-8"),
            object_key=object_key,
            content_type=content_type,
        )

    def save_json(self, payload: dict[str, Any], *, relative_path: str) -> str:
        return self.save_text(
            text=json.dumps(payload, indent=2),
            relative_path=relative_path,
            content_type="application/json",
        )

