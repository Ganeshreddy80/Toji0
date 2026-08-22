"""Thread-safe state store for the Dashboard Platform subsystem."""

from __future__ import annotations

import threading
from typing import Dict, Tuple

from dashboard.core.exceptions import StateStoreError
from dashboard.core.interfaces import IDashboardStateStore
from dashboard.core.models import DashboardSnapshot


class DashboardStateStore(IDashboardStateStore):
    """Thread-safe in-memory state store tracking active dashboard snapshots."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Active snapshot mapping: (symbol, timeframe) -> DashboardSnapshot
        self._snapshots: Dict[Tuple[str, str], DashboardSnapshot] = {}

    def get_snapshot(self, symbol: str, timeframe: str) -> DashboardSnapshot | None:
        """Retrieve the active dashboard snapshot for a symbol and timeframe."""
        with self._lock:
            return self._snapshots.get((symbol.upper(), timeframe.lower()))

    def update_snapshot(self, snapshot: DashboardSnapshot) -> None:
        """Update the active dashboard snapshot in a thread-safe manner."""
        if not snapshot.symbol or not snapshot.timeframe:
            raise StateStoreError("Snapshot must have a valid symbol and timeframe.")

        key = (snapshot.symbol.upper(), snapshot.timeframe.lower())
        with self._lock:
            self._snapshots[key] = snapshot

    def get_all_snapshots(self) -> list[DashboardSnapshot]:
        """Retrieve all active dashboard snapshots."""
        with self._lock:
            return list(self._snapshots.values())

    def clear(self) -> None:
        """Purge all tracked states from memory."""
        with self._lock:
            self._snapshots.clear()
