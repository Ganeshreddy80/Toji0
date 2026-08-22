from __future__ import annotations

import threading
from typing import List
from portfolio_engine.core.models import PortfolioSnapshot


class HistoryStore:
    """Thread-safe storage registry tracking historical portfolio snapshots over time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshots: List[PortfolioSnapshot] = []

    def add_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        """Append a portfolio snapshot to history."""
        with self._lock:
            self._snapshots.append(snapshot)

    def get_history(self) -> List[PortfolioSnapshot]:
        """Fetch list of all historical portfolio snapshots."""
        with self._lock:
            return list(self._snapshots)

    def clear(self) -> None:
        """Reset history register."""
        with self._lock:
            self._snapshots.clear()
