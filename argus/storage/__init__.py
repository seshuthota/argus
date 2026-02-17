"""Remote storage backends for report artifact persistence."""

from .base import BaseStorage
from .factory import create_storage, is_remote_storage_uri
from .gcs_storage import GCSStorage
from .s3_storage import S3Storage

__all__ = [
    "BaseStorage",
    "S3Storage",
    "GCSStorage",
    "create_storage",
    "is_remote_storage_uri",
]

