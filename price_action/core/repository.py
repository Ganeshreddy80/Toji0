"""Snapshot persistence repository for the Price Action Subsystem."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from price_action.core.enums import PatternStatus, PatternType
from price_action.core.exceptions import RepositoryError
from price_action.core.interfaces import IPatternRepository
from price_action.core.models import PatternMatch, PatternSnapshot

logger = logging.getLogger(__name__)


import threading

class PriceActionRepository(IPatternRepository):
    """Persist and retrieve Price Action snapshots and matches."""

    def __init__(self, storage_engine: Any | None = None) -> None:
        self._storage = storage_engine
        # In-memory indices for memory-only fallback / test/replay
        self._by_id: dict[str, PatternSnapshot] = {}
        # symbol -> list of snapshots sorted chronologically
        self._by_symbol: dict[str, list[PatternSnapshot]] = {}
        self._lock = threading.RLock()

    def save_snapshot(self, snapshot: PatternSnapshot) -> None:
        """Persist a pattern snapshot."""
        if not snapshot.snapshot_id or not snapshot.symbol:
            raise RepositoryError("Snapshot must contain a valid ID and symbol.")

        # 1. Update in-memory indices
        with self._lock:
            self._by_id[snapshot.snapshot_id] = snapshot

            symbol = snapshot.symbol
            if symbol not in self._by_symbol:
                self._by_symbol[symbol] = []

            snapshots_list = self._by_symbol[symbol]
            snapshots_list.append(snapshot)
            snapshots_list.sort(key=lambda s: s.timestamp)
            if len(snapshots_list) > 1000:
                removed = snapshots_list.pop(0)
                self._by_id.pop(removed.snapshot_id, None)

        # 2. Persist to storage backend if provided
        if self._storage:
            try:
                row = {
                    "snapshot_id": snapshot.snapshot_id,
                    "symbol": snapshot.symbol,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "data": snapshot.model_dump_json(),
                }
                self._storage.write_rows("price_action_snapshots", [row])
            except Exception as e:
                logger.error("Repository: Failed to write snapshot row: %s", e)
                raise RepositoryError(f"Failed to persist snapshot to storage: {e}") from e

    def load_snapshot(self, snapshot_id: str) -> PatternSnapshot | None:
        """Load a specific pattern snapshot by its unique ID."""
        # 1. Check in-memory index
        with self._lock:
            if snapshot_id in self._by_id:
                return self._by_id[snapshot_id]

        # 2. Check storage backend if available
        if self._storage:
            try:
                query = "SELECT data FROM price_action_snapshots WHERE snapshot_id = %s"
                rows = self._storage.execute(query, (snapshot_id,))
                if rows:
                    raw_data = rows[0].get("data")
                    data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    snapshot = PatternSnapshot(**data_dict)
                    # Cache in-memory
                    with self._lock:
                        self._by_id[snapshot_id] = snapshot
                    return snapshot
            except Exception as e:
                logger.error("Repository: Failed to load snapshot %s: %s", snapshot_id, e)
                raise RepositoryError(f"Failed to load snapshot from storage: {e}") from e

        return None

    def load_latest_snapshot(self, symbol: str) -> PatternSnapshot | None:
        """Load the most recent snapshot for a given symbol."""
        # 1. Check in-memory index
        with self._lock:
            snapshots_list = self._by_symbol.get(symbol)
            if snapshots_list:
                return snapshots_list[-1]

        # 2. Check storage backend if available
        if self._storage:
            try:
                query = (
                    "SELECT data FROM price_action_snapshots WHERE symbol = %s "
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
                    return PatternSnapshot(**data_dict)
            except Exception as e:
                logger.error("Repository: Failed to load latest snapshot for %s: %s", symbol, e)
                raise RepositoryError(f"Failed to load latest snapshot from storage: {e}") from e

        return None

    def get_historical_snapshots(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[PatternSnapshot]:
        """Load historical snapshots for a symbol over a specific timeframe."""
        results: list[PatternSnapshot] = []

        # 1. Load from storage engine if available
        if self._storage:
            try:
                query = (
                    "SELECT data, timestamp FROM price_action_snapshots WHERE symbol = %s "
                    "AND timestamp >= %s AND timestamp <= %s"
                )
                rows = self._storage.execute(query, (symbol, start.isoformat(), end.isoformat()))
                for row in rows:
                    raw_data = row.get("data")
                    data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    snapshot = PatternSnapshot(**data_dict)
                    if start <= snapshot.timestamp <= end:
                        results.append(snapshot)
                results.sort(key=lambda s: s.timestamp)
                return results
            except Exception as e:
                logger.error(
                    "Repository: Failed to load historical snapshots for %s: %s", symbol, e
                )
                raise RepositoryError(f"Failed to load historical snapshots from storage: {e}") from e

        # 2. Fall back to in-memory index
        with self._lock:
            snapshots_list = self._by_symbol.get(symbol)
            if snapshots_list:
                for snapshot in snapshots_list:
                    if start <= snapshot.timestamp <= end:
                        results.append(snapshot)

        return results

    def load_patterns(
        self,
        symbol: str,
        timeframe: str | None = None,
        pattern_type: PatternType | None = None,
        status: PatternStatus | None = None,
    ) -> list[PatternMatch]:
        """Load pattern match history from the repository."""
        unique_matches: dict[str, PatternMatch] = {}

        # If database query is possible
        if self._storage:
            try:
                query = "SELECT data FROM price_action_snapshots WHERE symbol = %s"
                rows = self._storage.execute(query, (symbol,))
                for row in rows:
                    raw_data = row.get("data")
                    data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    snapshot = PatternSnapshot(**data_dict)
                    for tf, state in snapshot.states.items():
                        if timeframe is not None and tf != timeframe:
                            continue
                        all_matches = state.active_patterns + state.historical_patterns
                        for match in all_matches:
                            if pattern_type is not None and match.pattern_type != pattern_type:
                                continue
                            if status is not None and match.status != status:
                                continue
                            unique_matches[match.match_id] = match
                return list(unique_matches.values())
            except Exception as e:
                logger.error("Repository: Failed to query patterns: %s", e)
                raise RepositoryError(f"Failed to load patterns from storage: {e}") from e

        # Fall back to in-memory snapshots
        with self._lock:
            snapshots_list = self._by_symbol.get(symbol)
            if snapshots_list:
                for snapshot in snapshots_list:
                    for tf, state in snapshot.states.items():
                        if timeframe is not None and tf != timeframe:
                            continue
                        all_matches = state.active_patterns + state.historical_patterns
                        for match in all_matches:
                            if pattern_type is not None and match.pattern_type != pattern_type:
                                continue
                            if status is not None and match.status != status:
                                continue
                            unique_matches[match.match_id] = match

        return list(unique_matches.values())
