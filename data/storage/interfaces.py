"""Abstract contracts for database and object storage engines."""

from __future__ import annotations

import abc
from typing import Any


class IStorageEngine(abc.ABC):
    """Core contract for any storage engine backend."""

    @property
    @abc.abstractmethod
    def engine_type(self) -> str:
        """Categorical name of engine ('postgres', 'redis', 'parquet', etc.)."""

    @abc.abstractmethod
    def connect(self) -> None:
        """Establish session or client connections."""

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Safely release underlying connection resources."""


class IPostgresStorageEngine(IStorageEngine):
    """Relational SQL execution contract."""

    @abc.abstractmethod
    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        """Run a raw SQL query, returning records as dictionaries."""

    @abc.abstractmethod
    def write_rows(self, table: str, rows: list[dict[str, Any]]) -> int:
        """Insert records bulk style. Returns count of affected rows."""


class IParquetStorageEngine(IStorageEngine):
    """Tabular file storage contract."""

    @abc.abstractmethod
    def write_table(self, file_path: str, data: Any) -> None:
        """Save a pandas DataFrame or Arrow table as a Parquet file."""

    @abc.abstractmethod
    def read_table(self, file_path: str) -> Any:
        """Load a Parquet file back into memory as a DataFrame or Arrow table."""


class IRedisStorageEngine(IStorageEngine):
    """In-memory key-value cache and pub-sub broker contract."""

    @abc.abstractmethod
    def get(self, key: str) -> str | None:
        """Fetch string value associated with key."""

    @abc.abstractmethod
    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Set string value under key with optional expiry time."""

    @abc.abstractmethod
    def publish(self, channel: str, message: str) -> int:
        """Publish message onto channel. Returns active listener count."""


class IObjectStorageEngine(IStorageEngine):
    """File object repository contract (e.g. S3, MinIO)."""

    @abc.abstractmethod
    def put_object(self, bucket: str, key: str, data: bytes) -> None:
        """Upload raw file content to bucket."""

    @abc.abstractmethod
    def get_object(self, bucket: str, key: str) -> bytes:
        """Retrieve raw file contents from bucket."""


class IVectorStorageEngine(IStorageEngine):
    """Vector database storage and semantic query contract."""

    @abc.abstractmethod
    def upsert_vectors(self, collection: str, items: list[tuple[str, list[float], dict[str, Any]]]) -> None:
        """Upsert a list of (id, vector, metadata) items into the database."""

    @abc.abstractmethod
    def query_similarity(
        self, collection: str, query_vector: list[float], limit: int = 5
    ) -> list[dict[str, Any]]:
        """Run a cosine/L2 distance search returning matching item metadata."""
