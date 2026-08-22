"""Thread-safe S3 Storage Abstraction with Checksum Tracking and Metadata (Sprint 12A)."""

from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class S3ObjectMetadata(BaseModel):
    """Immutable metadata model for an S3 object."""

    bucket: str = Field(..., description="S3 bucket name.")
    key: str = Field(..., description="S3 object key.")
    size_bytes: int = Field(default=0, ge=0, description="Content size in bytes.")
    etag: str = Field(default="", description="ETag string.")
    checksum: str = Field(default="", description="SHA-256 content checksum.")
    content_type: str = Field(default="application/octet-stream", description="MIME content type.")
    last_modified: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata_dict: Dict[str, str] = Field(default_factory=dict)
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class S3Storage:
    """Thread-safe in-memory S3 Storage abstraction supporting uploads, downloads, and metadata tracking."""

    def __init__(self, max_objects: int = 5000) -> None:
        self._lock = threading.RLock()
        self._max_objects = max_objects
        # (bucket, key) -> bytes
        self._storage: Dict[Tuple[str, str], bytes] = {}
        # (bucket, key) -> S3ObjectMetadata
        self._metadata: Dict[Tuple[str, str], S3ObjectMetadata] = {}

    def upload_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata_dict: Optional[Dict[str, str]] = None,
    ) -> S3ObjectMetadata:
        """Upload object bytes and return immutable S3ObjectMetadata with checksum."""
        with self._lock:
            if len(self._storage) >= self._max_objects and (bucket, key) not in self._storage:
                oldest_tuple = next(iter(self._storage))
                del self._storage[oldest_tuple]
                del self._metadata[oldest_tuple]

            checksum = hashlib.sha256(data).hexdigest()
            etag = f'"{checksum[:32]}"'
            meta = S3ObjectMetadata(
                bucket=bucket,
                key=key,
                size_bytes=len(data),
                etag=etag,
                checksum=checksum,
                content_type=content_type,
                metadata_dict=metadata_dict or {},
            )

            self._storage[(bucket, key)] = data
            self._metadata[(bucket, key)] = meta

            logger.info("Uploaded S3 object 's3://%s/%s' (%d bytes, checksum=%s)", bucket, key, len(data), checksum[:8])
            return meta

    def download_object(self, bucket: str, key: str) -> Tuple[bytes, S3ObjectMetadata]:
        """Download object bytes and metadata."""
        with self._lock:
            if (bucket, key) not in self._storage:
                raise KeyError(f"S3 object 's3://{bucket}/{key}' not found")
            return self._storage[(bucket, key)], self._metadata[(bucket, key)]

    def get_metadata(self, bucket: str, key: str) -> Optional[S3ObjectMetadata]:
        """Get object metadata by bucket and key."""
        with self._lock:
            return self._metadata.get((bucket, key))

    def list_objects(self, bucket: Optional[str] = None) -> List[S3ObjectMetadata]:
        """List object metadata, optionally filtered by bucket."""
        with self._lock:
            if bucket:
                return [m for (b, k), m in self._metadata.items() if b == bucket]
            return list(self._metadata.values())

    def count(self) -> int:
        """Return total count of stored objects."""
        with self._lock:
            return len(self._storage)

    def clear(self) -> None:
        """Clear all stored objects."""
        with self._lock:
            self._storage.clear()
            self._metadata.clear()
