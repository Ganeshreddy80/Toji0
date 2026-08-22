"""Mock implementations of storage engine interfaces for testing."""

from __future__ import annotations

from typing import Any

from data.storage.interfaces import (
    IObjectStorageEngine,
    IParquetStorageEngine,
    IPostgresStorageEngine,
    IRedisStorageEngine,
    IVectorStorageEngine,
)


class MockPostgresStorageEngine(IPostgresStorageEngine):
    """Mock implementation of IPostgresStorageEngine."""

    def __init__(self) -> None:
        self.connected = False
        self.tables: dict[str, list[dict[str, Any]]] = {}

    @property
    def engine_type(self) -> str:
        return "postgres"

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        # Simple mock query parser for tests
        if "SELECT" in query.upper():
            # Return rows of first table mentioned
            for tbl in self.tables:
                if tbl in query.lower():
                    return self.tables[tbl]
        return []

    def write_rows(self, table: str, rows: list[dict[str, Any]]) -> int:
        if table not in self.tables:
            self.tables[table] = []
        self.tables[table].extend(rows)
        return len(rows)


class MockParquetStorageEngine(IParquetStorageEngine):
    """Mock implementation of IParquetStorageEngine."""

    def __init__(self) -> None:
        self.connected = False
        self.files: dict[str, Any] = {}

    @property
    def engine_type(self) -> str:
        return "parquet"

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def write_table(self, file_path: str, data: Any) -> None:
        self.files[file_path] = data

    def read_table(self, file_path: str) -> Any:
        if file_path not in self.files:
            raise FileNotFoundError(f"Mock file '{file_path}' not found")
        return self.files[file_path]


class MockRedisStorageEngine(IRedisStorageEngine):
    """Mock implementation of IRedisStorageEngine."""

    def __init__(self) -> None:
        self.connected = False
        self.data: dict[str, str] = {}
        self.channels: dict[str, list[str]] = {}

    @property
    def engine_type(self) -> str:
        return "redis"

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self.data[key] = value

    def publish(self, channel: str, message: str) -> int:
        if channel not in self.channels:
            self.channels[channel] = []
        self.channels[channel].append(message)
        return 1  # 1 mock subscriber


class MockObjectStorageEngine(IObjectStorageEngine):
    """Mock implementation of IObjectStorageEngine."""

    def __init__(self) -> None:
        self.connected = False
        self.buckets: dict[str, dict[str, bytes]] = {}

    @property
    def engine_type(self) -> str:
        return "object_storage"

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def put_object(self, bucket: str, key: str, data: bytes) -> None:
        if bucket not in self.buckets:
            self.buckets[bucket] = {}
        self.buckets[bucket][key] = data

    def get_object(self, bucket: str, key: str) -> bytes:
        if bucket not in self.buckets or key not in self.buckets[bucket]:
            raise KeyError(f"Mock object '{key}' in bucket '{bucket}' not found")
        return self.buckets[bucket][key]


class MockVectorStorageEngine(IVectorStorageEngine):
    """Mock implementation of IVectorStorageEngine with basic similarity score."""

    def __init__(self) -> None:
        self.connected = False
        # collection -> list[tuple(id, vector, metadata)]
        self.collections: dict[str, list[tuple[str, list[float], dict[str, Any]]]] = {}

    @property
    def engine_type(self) -> str:
        return "vector_store"

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def upsert_vectors(self, collection: str, items: list[tuple[str, list[float], dict[str, Any]]]) -> None:
        if collection not in self.collections:
            self.collections[collection] = []
        self.collections[collection].extend(items)

    def query_similarity(
        self, collection: str, query_vector: list[float], limit: int = 5
    ) -> list[dict[str, Any]]:
        if collection not in self.collections:
            return []

        import numpy as np

        results = []
        q_vec = np.array(query_vector)

        for item_id, vec, metadata in self.collections[collection]:
            v = np.array(vec)
            # Cosine similarity
            dot = np.dot(q_vec, v)
            norm_q = np.linalg.norm(q_vec)
            norm_v = np.linalg.norm(v)
            score = float(dot / (norm_q * norm_v + 1e-10))
            results.append((score, metadata))

        # Sort descending by score
        results.sort(key=lambda x: x[0], reverse=True)
        return [meta for score, meta in results[:limit]]
