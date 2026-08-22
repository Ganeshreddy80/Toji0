"""Unit tests for the Storage Engines layer."""

from __future__ import annotations

import pytest

from data.storage.base import (
    MockObjectStorageEngine,
    MockParquetStorageEngine,
    MockPostgresStorageEngine,
    MockRedisStorageEngine,
    MockVectorStorageEngine,
)


def test_postgres_mock_storage():
    db = MockPostgresStorageEngine()
    assert db.engine_type == "postgres"

    db.connect()
    assert db.connected is True

    rows = [{"id": 1, "symbol": "BTC/USDT"}, {"id": 2, "symbol": "ETH/USDT"}]
    inserted = db.write_rows("assets", rows)
    assert inserted == 2

    # Query mock table
    records = db.execute("SELECT * FROM assets")
    assert len(records) == 2
    assert records[0]["symbol"] == "BTC/USDT"

    db.disconnect()
    assert db.connected is False


def test_redis_mock_storage():
    db = MockRedisStorageEngine()
    assert db.engine_type == "redis"

    db.connect()
    db.set("key_1", "value_1")
    assert db.get("key_1") == "value_1"

    subscribers = db.publish("trades", "trade_payload")
    assert subscribers == 1
    assert db.channels["trades"][0] == "trade_payload"

    db.disconnect()


def test_parquet_mock_storage():
    db = MockParquetStorageEngine()
    assert db.engine_type == "parquet"

    db.write_table("data.parquet", {"col1": [1, 2]})
    assert db.read_table("data.parquet") == {"col1": [1, 2]}


def test_object_mock_storage():
    db = MockObjectStorageEngine()
    assert db.engine_type == "object_storage"

    db.put_object("raw-data", "btc.csv", b"timestamp,close\n1,95000\n")
    assert db.get_object("raw-data", "btc.csv") == b"timestamp,close\n1,95000\n"

    with pytest.raises(KeyError):
        db.get_object("raw-data", "eth.csv")


def test_vector_mock_storage():
    db = MockVectorStorageEngine()
    assert db.engine_type == "vector_store"

    # Upsert two vectors
    db.upsert_vectors(
        "news",
        [
            ("1", [1.0, 0.0, 0.0], {"title": "Bullish news"}),
            ("2", [0.0, 1.0, 0.0], {"title": "Bearish news"}),
        ],
    )

    # Query with close proximity vector
    results = db.query_similarity("news", [0.9, 0.1, 0.0], limit=1)
    assert len(results) == 1
    assert results[0]["title"] == "Bullish news"
