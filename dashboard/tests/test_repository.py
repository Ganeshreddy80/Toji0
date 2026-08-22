import json
import pytest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from dashboard.core.exceptions import RepositoryError
from dashboard.core.models import DashboardSnapshot
from dashboard.core.repository import DashboardRepository


class MockStorageEngine:
    """Mock storage engine simulating SQL query execution and raw rows writing."""

    def __init__(self) -> None:
        self.written_rows: Dict[str, List[Dict[str, Any]]] = {}
        self.should_fail = False

    def write_rows(self, table_name: str, rows: List[Dict[str, Any]]) -> None:
        if self.should_fail:
            raise RuntimeError("Database connection lost.")
        if table_name not in self.written_rows:
            self.written_rows[table_name] = []
        self.written_rows[table_name].extend(rows)

    def execute(self, query: str) -> List[Dict[str, Any]]:
        if self.should_fail:
            raise RuntimeError("Query execution failed.")
        
        # Simple parser for mock tests
        all_rows = self.written_rows.get("dashboard_snapshots", [])
        if "WHERE snapshot_id = " in query:
            snapshot_id = query.split("WHERE snapshot_id = ")[1].strip("'")
            return [r for r in all_rows if r["snapshot_id"] == snapshot_id]
        
        if "ORDER BY timestamp DESC LIMIT 1" in query:
            # Match symbol & timeframe
            parts = query.split("WHERE symbol = ")[1].split(" AND timeframe = ")
            symbol = parts[0].strip("'")
            timeframe = parts[1].split(" ORDER BY ")[0].strip("'")
            matches = [r for r in all_rows if r["symbol"] == symbol and r["timeframe"] == timeframe]
            if matches:
                return [max(matches, key=lambda r: r["timestamp"])]
            return []

        if "timestamp >= " in query:
            parts = query.split("WHERE symbol = ")[1].split(" AND timeframe = ")
            symbol = parts[0].strip("'")
            timeframe = parts[1].split(" AND timestamp >= ")[0].strip("'")
            time_parts = parts[1].split(" AND timestamp >= ")[1].split(" AND timestamp <= ")
            start_str = time_parts[0].strip("'")
            end_str = time_parts[1].strip("'")
            
            matches = [
                r for r in all_rows 
                if r["symbol"] == symbol 
                and r["timeframe"] == timeframe 
                and start_str <= r["timestamp"] <= end_str
            ]
            return matches

        return all_rows


def test_repository_in_memory() -> None:
    """Test repository save, load, and historical functions without storage backend."""
    repo = DashboardRepository()
    now = datetime.now(timezone.utc)
    
    snapshot = DashboardSnapshot(
        snapshot_id="snap-123",
        symbol="ETH/USDT",
        timeframe="15m",
        health_status={},
        timestamp=now,
    )
    
    # Save snapshot
    repo.save_snapshot(snapshot)
    
    # Load by ID
    loaded = repo.load_snapshot("snap-123")
    assert loaded is not None
    assert loaded.snapshot_id == "snap-123"
    assert loaded.symbol == "ETH/USDT"
    
    # Load latest snapshot
    latest = repo.load_latest_snapshot("ETH/USDT", "15m")
    assert latest is not None
    assert latest.snapshot_id == "snap-123"
    
    # Save a newer snapshot
    snapshot2 = DashboardSnapshot(
        snapshot_id="snap-124",
        symbol="ETH/USDT",
        timeframe="15m",
        health_status={},
        timestamp=now + timedelta(minutes=15),
    )
    repo.save_snapshot(snapshot2)
    
    latest_updated = repo.load_latest_snapshot("ETH/USDT", "15m")
    assert latest_updated is not None
    assert latest_updated.snapshot_id == "snap-124"
    
    # Historical snapshots lookup
    history = repo.get_historical_snapshots(
        symbol="ETH/USDT",
        timeframe="15m",
        start=now - timedelta(minutes=1),
        end=now + timedelta(minutes=20),
    )
    assert len(history) == 2
    assert history[0].snapshot_id == "snap-123"
    assert history[1].snapshot_id == "snap-124"


def test_repository_with_storage_backend() -> None:
    """Test repository using mock storage backend."""
    storage = MockStorageEngine()
    repo = DashboardRepository(storage_engine=storage)
    now = datetime.now(timezone.utc)
    
    snapshot = DashboardSnapshot(
        snapshot_id="snap-backend",
        symbol="SOL/USDT",
        timeframe="1d",
        health_status={},
        timestamp=now,
    )
    
    repo.save_snapshot(snapshot)
    assert len(storage.written_rows["dashboard_snapshots"]) == 1
    
    # Clear memory indexes to force backend load
    repo._by_id.clear()
    repo._by_key.clear()
    
    loaded = repo.load_snapshot("snap-backend")
    assert loaded is not None
    assert loaded.snapshot_id == "snap-backend"
    
    # Verify latest loading from database
    latest = repo.load_latest_snapshot("SOL/USDT", "1d")
    assert latest is not None
    assert latest.snapshot_id == "snap-backend"
    
    # Verify historical loading from database
    history = repo.get_historical_snapshots(
        symbol="SOL/USDT",
        timeframe="1d",
        start=now - timedelta(minutes=5),
        end=now + timedelta(minutes=5),
    )
    assert len(history) == 1
    assert history[0].snapshot_id == "snap-backend"


def test_repository_error_handling() -> None:
    """Test invalid input validation and storage backend runtime exceptions."""
    repo = DashboardRepository()
    
    # Validation error for invalid snapshots
    invalid_snap = DashboardSnapshot(
        snapshot_id="",
        symbol="BTC/USD",
        timeframe="1h",
        health_status={},
    )
    with pytest.raises(RepositoryError):
        repo.save_snapshot(invalid_snap)

    # Database exceptions wrapping
    storage = MockStorageEngine()
    repo_faulty = DashboardRepository(storage_engine=storage)
    storage.should_fail = True
    
    snapshot = DashboardSnapshot(
        snapshot_id="snap-fault",
        symbol="BTC/USD",
        timeframe="1h",
        health_status={},
    )
    
    with pytest.raises(RepositoryError):
        repo_faulty.save_snapshot(snapshot)
        
    repo_faulty._by_id.clear()
    repo_faulty._by_key.clear()
        
    with pytest.raises(RepositoryError):
        repo_faulty.load_snapshot("snap-fault")
        
    with pytest.raises(RepositoryError):
        repo_faulty.load_latest_snapshot("BTC/USD", "1h")
        
    with pytest.raises(RepositoryError):
        repo_faulty.get_historical_snapshots(
            symbol="BTC/USD",
            timeframe="1h",
            start=datetime.now(),
            end=datetime.now()
        )

