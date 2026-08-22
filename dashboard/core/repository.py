"""Snapshot persistence repository for the Dashboard Platform subsystem."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from dashboard.core.exceptions import RepositoryError
from dashboard.core.interfaces import IDashboardRepository
from dashboard.core.models import DashboardSnapshot

logger = logging.getLogger(__name__)


class DashboardRepository(IDashboardRepository):
    """Persist and retrieve DashboardSnapshots."""

    def __init__(self, storage_engine: Any | None = None) -> None:
        self._storage = storage_engine
        self._by_id: Dict[str, DashboardSnapshot] = {}
        # Mapping: (symbol, timeframe) -> list[DashboardSnapshot]
        self._by_key: Dict[tuple[str, str], List[DashboardSnapshot]] = {}

    def save_snapshot(self, snapshot: DashboardSnapshot) -> None:
        """Persist a dashboard snapshot."""
        if not snapshot.snapshot_id or not snapshot.symbol or not snapshot.timeframe:
            raise RepositoryError("Snapshot must contain a valid ID, symbol, and timeframe.")

        # 1. Update in-memory indices
        self._by_id[snapshot.snapshot_id] = snapshot

        key = (snapshot.symbol.upper(), snapshot.timeframe.lower())
        if key not in self._by_key:
            self._by_key[key] = []

        snapshots_list = self._by_key[key]
        snapshots_list.append(snapshot)
        snapshots_list.sort(key=lambda s: s.timestamp)

        # 2. Persist to storage backend if provided
        if self._storage:
            try:
                row = {
                    "snapshot_id": snapshot.snapshot_id,
                    "symbol": snapshot.symbol,
                    "timeframe": snapshot.timeframe,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "data": snapshot.model_dump_json(),
                }
                self._storage.write_rows("dashboard_snapshots", [row])
            except Exception as e:
                logger.error("Repository: Failed to write dashboard snapshot row: %s", e)
                raise RepositoryError(f"Failed to persist snapshot to storage: {e}") from e

    def load_snapshot(self, snapshot_id: str) -> DashboardSnapshot | None:
        """Load a specific dashboard snapshot by its unique ID."""
        # 1. Check in-memory index
        if snapshot_id in self._by_id:
            return self._by_id[snapshot_id]

        # 2. Check storage backend if available
        if self._storage:
            try:
                query = "SELECT data FROM dashboard_snapshots WHERE snapshot_id = %s"
                rows = self._storage.execute(query, (snapshot_id,))
                if rows:
                    raw_data = rows[0].get("data")
                    data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    snapshot = DashboardSnapshot(**data_dict)
                    self._by_id[snapshot_id] = snapshot
                    return snapshot
            except Exception as e:
                logger.error("Repository: Failed to load snapshot %s: %s", snapshot_id, e)
                raise RepositoryError(f"Failed to load snapshot from storage: {e}") from e

        return None

    def load_latest_snapshot(self, symbol: str, timeframe: str) -> DashboardSnapshot | None:
        """Load the most recent dashboard snapshot for a symbol and timeframe."""
        key = (symbol.upper(), timeframe.lower())
        # 1. Check in-memory index
        snapshots_list = self._by_key.get(key)
        if snapshots_list:
            return snapshots_list[-1]

        # 2. Check storage backend if available
        if self._storage:
            try:
                query = (
                    "SELECT data FROM dashboard_snapshots WHERE symbol = %s "
                    "AND timeframe = %s ORDER BY timestamp DESC LIMIT 1"
                )
                rows = self._storage.execute(query, (symbol, timeframe))
                if rows:
                    latest_row = max(
                        rows,
                        key=lambda r: datetime.fromisoformat(r.get("timestamp", ""))
                        if isinstance(r.get("timestamp"), str)
                        else r.get("timestamp"),
                    )
                    raw_data = latest_row.get("data")
                    data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    return DashboardSnapshot(**data_dict)
            except Exception as e:
                logger.error("Repository: Failed to load latest snapshot for %s/%s: %s", symbol, timeframe, e)
                raise RepositoryError(f"Failed to load latest snapshot from storage: {e}") from e

        return None

    def get_historical_snapshots(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> list[DashboardSnapshot]:
        """Load historical snapshots for a symbol and timeframe over a specific range."""
        results: List[DashboardSnapshot] = []
        key = (symbol.upper(), timeframe.lower())

        # 1. Load from storage engine if available
        if self._storage:
            try:
                query = (
                    "SELECT data, timestamp FROM dashboard_snapshots WHERE symbol = %s "
                    "AND timeframe = %s AND timestamp >= %s "
                    "AND timestamp <= %s"
                )
                rows = self._storage.execute(query, (symbol, timeframe, start.isoformat(), end.isoformat()))
                for row in rows:
                    raw_data = row.get("data")
                    data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    snapshot = DashboardSnapshot(**data_dict)
                    if start <= snapshot.timestamp <= end:
                        results.append(snapshot)
                results.sort(key=lambda s: s.timestamp)
                return results
            except Exception as e:
                logger.error("Repository: Failed to load historical snapshots: %s", e)
                raise RepositoryError(f"Failed to load historical snapshots from storage: {e}") from e

        # 2. Fall back to in-memory index
        snapshots_list = self._by_key.get(key)
        if snapshots_list:
            for snapshot in snapshots_list:
                if start <= snapshot.timestamp <= end:
                    results.append(snapshot)

        return results
