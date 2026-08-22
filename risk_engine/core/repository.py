"""Snapshot persistence repository for the Risk Engine subsystem."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from risk_engine.core.exceptions import RepositoryError
from risk_engine.core.interfaces import IRiskRepository
from risk_engine.core.models import RiskSnapshot

logger = logging.getLogger(__name__)


class RiskRepository(IRiskRepository):
    """Persist and retrieve RiskSnapshots."""

    def __init__(self, storage_engine: Any | None = None) -> None:
        self._storage = storage_engine
        self._by_id: dict[str, RiskSnapshot] = {}
        self._by_symbol: dict[str, list[RiskSnapshot]] = {}

    def save_snapshot(self, snapshot: RiskSnapshot) -> None:
        """Persist a risk snapshot."""
        if not snapshot.snapshot_id or not snapshot.symbol:
            raise RepositoryError("Snapshot must contain a valid ID and symbol.")

        # 1. Update in-memory indices
        self._by_id[snapshot.snapshot_id] = snapshot

        symbol = snapshot.symbol
        if symbol not in self._by_symbol:
            self._by_symbol[symbol] = []

        snapshots_list = self._by_symbol[symbol]
        snapshots_list.append(snapshot)
        snapshots_list.sort(key=lambda s: s.timestamp)

        # 2. Persist to storage backend if provided
        if self._storage:
            try:
                row = {
                    "snapshot_id": snapshot.snapshot_id,
                    "symbol": snapshot.symbol,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "data": snapshot.model_dump_json(),
                }
                self._storage.write_rows("risk_states", [row])
            except Exception as e:
                logger.error("Repository: Failed to write risk state snapshot row: %s", e)
                raise RepositoryError(f"Failed to persist snapshot to storage: {e}") from e

    def load_snapshot(self, snapshot_id: str) -> RiskSnapshot | None:
        """Load a specific risk snapshot by its unique ID."""
        # 1. Check in-memory index
        if snapshot_id in self._by_id:
            return self._by_id[snapshot_id]

        # 2. Check storage backend if available
        if self._storage:
            try:
                query = "SELECT data FROM risk_states WHERE snapshot_id = %s"
                rows = self._storage.execute(query, (snapshot_id,))
                if rows:
                    raw_data = rows[0].get("data")
                    data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    snapshot = RiskSnapshot(**data_dict)
                    self._by_id[snapshot_id] = snapshot
                    return snapshot
            except Exception as e:
                logger.error("Repository: Failed to load risk snapshot %s: %s", snapshot_id, e)
                raise RepositoryError(f"Failed to load snapshot from storage: {e}") from e

        return None

    def load_latest_snapshot(self, symbol: str) -> RiskSnapshot | None:
        """Load the most recent risk snapshot for a given symbol."""
        # 1. Check in-memory index
        snapshots_list = self._by_symbol.get(symbol)
        if snapshots_list:
            return snapshots_list[-1]

        # 2. Check storage backend if available
        if self._storage:
            try:
                query = (
                    "SELECT data FROM risk_states WHERE symbol = %s "
                    "ORDER BY timestamp DESC LIMIT 1"
                )
                rows = self._storage.execute(query, (symbol,))
                if rows:
                    latest_row = max(
                        rows,
                        key=lambda r: datetime.fromisoformat(r.get("timestamp", ""))
                        if isinstance(r.get("timestamp"), str)
                        else r.get("timestamp"),
                    )
                    raw_data = latest_row.get("data")
                    data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    return RiskSnapshot(**data_dict)
            except Exception as e:
                logger.error("Repository: Failed to load latest risk snapshot for %s: %s", symbol, e)
                raise RepositoryError(f"Failed to load latest snapshot from storage: {e}") from e

        return None

    def get_historical_snapshots(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[RiskSnapshot]:
        """Load historical risk snapshots for a symbol over a specific timeframe."""
        results: list[RiskSnapshot] = []

        # 1. Load from storage engine if available
        if self._storage:
            try:
                query = (
                    "SELECT data, timestamp FROM risk_states WHERE symbol = %s "
                    "AND timestamp >= %s AND timestamp <= %s"
                )
                rows = self._storage.execute(query, (symbol, start.isoformat(), end.isoformat()))
                for row in rows:
                    raw_data = row.get("data")
                    data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    snapshot = RiskSnapshot(**data_dict)
                    if start <= snapshot.timestamp <= end:
                        results.append(snapshot)
                results.sort(key=lambda s: s.timestamp)
                return results
            except Exception as e:
                logger.error("Repository: Failed to load historical risk snapshots for %s: %s", symbol, e)
                raise RepositoryError(f"Failed to load historical snapshots from storage: {e}") from e

        # 2. Fall back to in-memory index
        snapshots_list = self._by_symbol.get(symbol)
        if snapshots_list:
            for snapshot in snapshots_list:
                if start <= snapshot.timestamp <= end:
                    results.append(snapshot)

        return results
